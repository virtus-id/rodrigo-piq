"""Adaptador Supabase/Postgres de `Conta` — `RF-02` (NFR de segurança: senha
nunca armazenada em texto claro nem registrada em log).

Grava e lê contas em `app_aluno.contas` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21: `conta_id`, `email UNIQUE`, `senha_hash`,
`criado_em`). Mesmo padrão de conexão/transação/commit/rollback de
`persistencia/app_aluno/respostas.py` e `persistencia/app_aluno/casos.py`
(T-22/T-23): reaproveita `obter_database_url`/`ErroConexaoAusente` de
`persistencia.supabase.conexao` (genéricos, não amarrados a um schema), sem
tocar naquele módulo (congelado, `AC-44`), com `search_path=app_aluno`
fixado por conexão própria deste adaptador.

**Hash, nunca senha em texto claro.** Este módulo NUNCA recebe nem grava a
senha em texto claro numa coluna: `criar` recebe a senha em texto claro do
chamador só para hasheá-la imediatamente via `app.http.senhas.hashear_senha`
antes de qualquer `INSERT` — a variável local não é logada, e nenhuma
exceção deste módulo interpola a senha em sua mensagem (só `email`/`conta_id`,
nunca `senha`). A senha em texto claro não sobrevive além do escopo da
função que a recebe.

**Verificação não distingue "conta inexistente" de "senha errada".**
`autenticar` devolve `None` para AMBOS os casos — a mesma mensagem/resultado,
nunca uma exceção que permita ao chamador diferenciá-los. Sobre a decisão de
NÃO mitigar a diferença de tempo (timing attack) entre os dois casos nesta
tarefa, ver a justificativa em `app/http/senhas.py` (YAGNI declarado para o
piloto de 1 a 3 alunos, `OQ-06` — o que é garantido aqui é que a MENSAGEM/
resultado de erro não vaza qual dos dois casos ocorreu, que é o critério de
aceite de T-28).

**`e_revisor` (`RF-23`, `RF-25`, T-100).** Extensão pequena e necessária
desta tarefa: `app_aluno.contas.e_revisor` (`persistencia/supabase/
migracoes/003_papel_revisor.sql`) distingue papel de revisor do papel de
aluno — `NOT NULL DEFAULT false`, nenhuma conta vira revisora por acidente.
`buscar_por_id` (novo método) é o que `app/http/isolamento.py::
exigir_papel_revisor` (T-100) chama, a cada requisição, para ler `e_revisor`
FRESCO do banco a partir do `conta_id` da sessão — mesma disciplina de "sem
cache de autorização em sessão" já aplicada a `RepositorioCasos.
pertence_a_conta` (T-31): a sessão (`app/http/sessao.py`) nunca carrega
`e_revisor`, só `conta_id`.

**Provisionamento de conta revisora — fora de escopo de UI (T-100).** Não
existe, nesta feature, tela nem rota de "promover a revisor": a única
maneira de uma conta se tornar revisora é a operação manual abaixo
(`promover_a_revisor`, ou o SQL equivalente executado diretamente por quem
administra o banco):

```sql
UPDATE app_aluno.contas SET e_revisor = true WHERE email = 'revisor@exemplo.invalido';
```

`promover_a_revisor` (função deste módulo) existe só para permitir que os
testes desta tarefa provisionem uma conta revisora sem SQL solto espalhado
pela suíte — não é chamada por nenhuma rota HTTP, e não há dependência do
FastAPI que a exponha.

Direção de dependência: este módulo importa de `app.http.senhas` (hash/
verify puro) e de `psycopg`/stdlib — nunca de `engine/` (escopo desta
feature não toca o motor).

REGRAS: `RF-02`, `RF-23`, `RF-25`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from app.http.senhas import hashear_senha, verificar_senha
from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-23", "RF-25")

_SCHEMA: Final[str] = "app_aluno"


@dataclass(frozen=True, slots=True)
class Conta:
    """Uma conta de aluno (`RF-02`). `senha_hash` é sempre o hash Argon2id —
    nunca a senha em texto claro (ver docstring do módulo). `e_revisor`
    (`RF-23`, `RF-25`, T-100) distingue papel de revisor do papel de aluno —
    `False` por padrão para toda conta nova (nenhuma vira revisora por
    acidente)."""

    conta_id: str
    email: str
    senha_hash: str
    criado_em: datetime
    e_revisor: bool = False


class ErroEmailDuplicado(Exception):
    """Levantado quando `criar` recebe um `email` já cadastrado (a coluna é
    `UNIQUE`) — nomeia o e-mail, nunca a senha."""


class ErroContaInexistente(Exception):
    """Levantado por `promover_a_revisor` quando `email` não corresponde a
    nenhuma conta cadastrada — nomeia o e-mail, nunca inventa uma conta."""


class ErroGravacaoConta(Exception):
    """Levantado quando a gravação de uma conta falha antes do commit — nunca
    engolida: o chamador vê exatamente esta exceção (ou a original do
    driver, propagada), mesma disciplina de `EC-05` aplicada em
    `persistencia/app_aluno/respostas.py` (T-22). NUNCA interpola a senha em
    texto claro em sua mensagem — apenas `email`/`conta_id`."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/casos.py::_conectar`:
    `search_path` fixado em `app_aluno`, commit ao sair sem exceção,
    rollback e propagação ao sair com exceção."""
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


def _linha_para_conta(linha: tuple[Any, ...]) -> Conta:
    conta_id, email, senha_hash, criado_em, e_revisor = linha
    return Conta(
        conta_id=conta_id,
        email=email,
        senha_hash=senha_hash,
        criado_em=criado_em if criado_em.tzinfo is not None else criado_em.replace(tzinfo=UTC),
        e_revisor=e_revisor,
    )


class RepositorioContas(Protocol):
    """Contrato do adaptador de contas — `RepositorioContasSupabase` (abaixo)
    é a implementação Postgres."""

    def criar(self, conta_id: str, email: str, senha: str) -> None:
        """Cadastra uma nova conta. `senha` chega em texto claro e é
        hasheada (Argon2id) ANTES de qualquer gravação — a coluna
        `senha_hash` nunca recebe texto claro. Levanta `ErroEmailDuplicado`
        se `email` já existir."""
        ...

    def buscar_por_email(self, email: str) -> Conta | None:
        """`None` se `email` não existir — nunca lança para "não
        encontrado", só para falha de acesso ao banco."""
        ...

    def buscar_por_id(self, conta_id: str) -> Conta | None:
        """`None` se `conta_id` não existir. `RF-23`/`RF-25` (T-100): é este
        método que `app/http/isolamento.py::exigir_papel_revisor` chama, a
        cada requisição, para ler `e_revisor` FRESCO do banco a partir do
        `conta_id` da sessão — nunca de um valor cacheado em sessão."""
        ...

    def autenticar(self, email: str, senha: str) -> Conta | None:
        """`None` se `email` não existe OU se `senha` está errada — os dois
        casos são INDISTINGUÍVEIS pelo retorno (mesmo valor, nenhuma
        exceção diferenciadora). Devolve a `Conta` só quando ambos, e-mail
        existente e senha correta, se confirmam."""
        ...


class RepositorioContasSupabase:
    """Implementa `RepositorioContas` sobre `app_aluno.contas`."""

    def criar(self, conta_id: str, email: str, senha: str) -> None:
        # A senha em texto claro vive só nesta variável local, hasheada
        # imediatamente — nunca gravada nem logada em texto claro.
        senha_hash = hashear_senha(senha)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.contas (conta_id, email, senha_hash, criado_em)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conta_id, email, senha_hash, datetime.now(UTC)),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.errors.UniqueViolation as erro:
            raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}") from erro
        except psycopg.Error as erro:
            raise ErroGravacaoConta(
                f"falha ao criar conta conta_id={conta_id!r} email={email!r}: {erro}"
            ) from erro

    def buscar_por_email(self, email: str) -> Conta | None:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT conta_id, email, senha_hash, criado_em, e_revisor
                FROM app_aluno.contas
                WHERE email = %s
                """,
                (email,),
            )
            linha = cursor.fetchone()

        return _linha_para_conta(linha) if linha is not None else None

    def buscar_por_id(self, conta_id: str) -> Conta | None:
        """`RF-23`/`RF-25`, T-100 — mesma disciplina de `RepositorioCasos.
        pertence_a_conta` (T-31): consulta o banco a cada chamada, sem
        nenhum cache. Quem depende deste método (`app/http/isolamento.py::
        exigir_papel_revisor`) é reexecutado a cada requisição."""
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT conta_id, email, senha_hash, criado_em, e_revisor
                FROM app_aluno.contas
                WHERE conta_id = %s
                """,
                (conta_id,),
            )
            linha = cursor.fetchone()

        return _linha_para_conta(linha) if linha is not None else None

    def autenticar(self, email: str, senha: str) -> Conta | None:
        """`RF-02`: a mensagem/resultado de erro não distingue "conta
        inexistente" de "senha errada" — ambos os ramos abaixo devolvem
        `None`, sem exceção. `verificar_senha` (ver `app/http/senhas.py`)
        nunca levanta para senha errada; qualquer exceção de acesso ao banco
        (`ErroConexaoAusente`, `psycopg.Error`) continua propagando, pois é
        uma falha de infraestrutura, não um resultado de autenticação."""
        conta = self.buscar_por_email(email)
        if conta is None:
            return None
        if not verificar_senha(conta.senha_hash, senha):
            return None
        return conta


def promover_a_revisor(email: str) -> None:
    """Provisionamento de conta revisora — `RF-23`/`RF-25`, T-100.

    **Fora de escopo de UI, deliberadamente.** Não existe, nesta feature,
    tela nem rota HTTP de "promover a revisor" — nenhuma dependência do
    FastAPI expõe esta função. É uma operação manual de administração de
    banco (SQL direto ou esta função, chamada por um script/console
    operacional fora da aplicação), documentada aqui para que o
    procedimento não fique disperso em SQL solto pela suíte de testes.

    Levanta `ErroContaInexistente` se `email` não corresponder a nenhuma
    conta — nunca cria uma conta nova (a promoção pressupõe uma conta já
    cadastrada pelo fluxo normal de `RepositorioContas.criar`)."""
    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                UPDATE app_aluno.contas
                SET e_revisor = true
                WHERE email = %s
                """,
                (email,),
            )
            if cursor.rowcount == 0:
                raise ErroContaInexistente(f"promoção recusada: email={email!r} não existe")
    except ErroConexaoAusente:
        raise
    except ErroContaInexistente:
        raise
    except psycopg.Error as erro:
        raise ErroGravacaoConta(f"falha ao promover a revisor email={email!r}: {erro}") from erro
