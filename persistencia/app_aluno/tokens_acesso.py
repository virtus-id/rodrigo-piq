"""Tokens de primeiro acesso e redefinição de senha — `RF-02`, `T-179`.

**O problema que resolve.** O aluno compra na Hotmart e a conta nasce por
webhook, sem senha — ele nunca a informou. Para definir a própria senha ele
precisa provar que é o dono daquele e-mail, e o token é essa prova: enviado
ao endereço, só quem o recebe consegue usá-lo.

**O mesmo mecanismo serve aos dois fluxos** — primeiro acesso e "esqueci
minha senha". Por isso o módulo não se chama `tokens_de_cadastro`: o fato
modelado é *"prova de posse do e-mail para definir senha"*, e ele vale nos
dois casos. Um segundo sistema para recuperação seria a mesma coisa com
outro nome.

**O token é guardado como HASH, nunca em claro.** Mesma disciplina de
`senha_hash`: quem ler o banco — um backup, um dump, um operador — não
consegue se passar por ninguém. O valor em claro existe só no instante em
que é gerado e enviado; o banco guarda `sha256` dele.

**SHA-256 aqui, Argon2id nas senhas — e a diferença importa.** Argon2id é
caro de propósito, para resistir a força bruta sobre segredos que humanos
escolhem (curtos, previsíveis). Um token de 256 bits gerado por
`secrets.token_urlsafe` não é adivinhável por força bruta em nenhuma escala
concebível, então o custo de Argon2id não compraria segurança — só tornaria
cada validação 100 ms mais lenta. O que se quer aqui é que o banco não
guarde o segredo utilizável, e `sha256` entrega isso.

**Uso único e com prazo.** `usado_em` fecha o token na primeira validação
bem-sucedida; `expira_em` o fecha pelo tempo. Um link de definir senha que
funcione para sempre é uma credencial permanente na caixa de entrada de
alguém.

Direção de dependência: só `persistencia/supabase/conexao.py` e stdlib —
nunca `app/` nem `engine/`.

REGRAS: `RF-02`
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Protocol

import psycopg

from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-02",)

_SCHEMA: Final[str] = "app_aluno"

#: Quanto tempo o link vale. 48 horas cobre com folga quem compra à noite e
#: só abre o e-mail no dia seguinte, sem deixar uma credencial viva por
#: semanas numa caixa de entrada. Expirado, o aluno pede outro pelo fluxo de
#: recuperação — que é o mesmo mecanismo.
VALIDADE_PADRAO: Final[timedelta] = timedelta(hours=48)


class ErroTokenInvalido(Exception):
    """O token não existe, já foi usado ou expirou.

    **Um erro só para os três casos, de propósito.** Distinguir "não existe"
    de "expirou" diria a quem tenta adivinhar que ele acertou um token real
    — a mesma razão pela qual `autenticar` não distingue "conta inexistente"
    de "senha errada" (`RF-02`)."""


@dataclass(frozen=True, slots=True)
class TokenEmitido:
    """O par que a emissão produz: o valor em CLARO (para enviar ao aluno,
    nunca gravado) e a conta a que pertence."""

    valor: str
    conta_id: str
    expira_em: datetime


def _hash_do_token(valor: str) -> str:
    """`sha256` hexadecimal — ver a nota do módulo sobre por que não
    Argon2id aqui."""
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """Mesmo padrão de `contas.py::_conectar`."""
    conexao = psycopg.connect(obter_database_url())
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        conexao.close()


class RepositorioTokensAcesso(Protocol):
    """Contrato do adaptador de tokens."""

    def emitir(self, conta_id: str, validade: timedelta | None = None) -> TokenEmitido:
        """Gera um token novo para `conta_id` e **revoga os anteriores**.

        A revogação não é detalhe: sem ela, um pedido de "esqueci minha
        senha" deixaria o link antigo funcionando — e quem tivesse acesso ao
        e-mail antigo continuaria entrando."""
        ...

    def consumir(self, valor: str) -> str:
        """Valida e marca como usado, devolvendo o `conta_id`. Levanta
        `ErroTokenInvalido` se não existe, já foi usado ou expirou.

        **Consumir é atômico**: a marcação de uso acontece na mesma
        transação da validação, para que dois pedidos simultâneos com o
        mesmo token não definam a senha duas vezes."""
        ...


class RepositorioTokensAcessoSupabase:
    """Implementa `RepositorioTokensAcesso` sobre
    `app_aluno.tokens_primeiro_acesso`."""

    def emitir(self, conta_id: str, validade: timedelta | None = None) -> TokenEmitido:
        # 32 bytes de entropia — `token_urlsafe(32)` produz ~43 caracteres
        # seguros para URL. É o que vai no link, e o único momento em que o
        # valor existe em claro.
        valor = secrets.token_urlsafe(32)
        agora = datetime.now(UTC)
        expira_em = agora + (validade if validade is not None else VALIDADE_PADRAO)

        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                # Revoga os anteriores desta conta — ver a nota do Protocol.
                # `usado_em = now()` em vez de `DELETE`: a trilha de que um
                # token foi emitido e substituído tem valor de auditoria.
                cursor.execute(
                    """
                    UPDATE app_aluno.tokens_primeiro_acesso
                    SET usado_em = %s
                    WHERE conta_id = %s AND usado_em IS NULL
                    """,
                    (agora, conta_id),
                )
                cursor.execute(
                    """
                    INSERT INTO app_aluno.tokens_primeiro_acesso
                        (token_hash, conta_id, criado_em, expira_em)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (_hash_do_token(valor), conta_id, agora, expira_em),
                )
        except ErroConexaoAusente:
            raise

        return TokenEmitido(valor=valor, conta_id=conta_id, expira_em=expira_em)

    def consumir(self, valor: str) -> str:
        agora = datetime.now(UTC)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                # `UPDATE ... RETURNING` com as condições no `WHERE`: valida
                # e consome num único comando atômico. Dois pedidos
                # simultâneos com o mesmo token — o segundo não encontra
                # linha, porque o primeiro já preencheu `usado_em`.
                cursor.execute(
                    """
                    UPDATE app_aluno.tokens_primeiro_acesso
                    SET usado_em = %s
                    WHERE token_hash = %s
                      AND usado_em IS NULL
                      AND expira_em > %s
                    RETURNING conta_id
                    """,
                    (agora, _hash_do_token(valor), agora),
                )
                linha = cursor.fetchone()
        except ErroConexaoAusente:
            raise

        if linha is None:
            # Não existe, já usado ou expirado — ver `ErroTokenInvalido`.
            raise ErroTokenInvalido("token de acesso inválido")
        return str(linha[0])
