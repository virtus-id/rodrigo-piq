"""Adaptador Supabase/Postgres de `Conta` — `RF-02` (NFR de segurança: senha
nunca armazenada em texto claro nem registrada em log).

Grava e lê contas em `app_aluno.contas` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21: `conta_id`, `email UNIQUE`, `senha_hash`,
`criado_em`). Mesmo padrão de conexão/transação/commit/rollback de
`persistencia/app_aluno/respostas.py` e `persistencia/app_aluno/casos.py`
(T-22/T-23): reaproveita `obter_pool`/`ErroConexaoAusente` de
`persistencia.supabase.conexao` (genéricos, não amarrados a um schema) — o
MESMO pool do processo inteiro, `T-187`, nunca uma conexão própria — com
`search_path=app_aluno` fixado a cada checkout (a conexão física pode ter
servido `motor_calculo` no checkout anterior).

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
existe, nesta feature, tela nem rota de "promover a revisor". O papel se
concede por operação administrativa deliberada, fora da aplicação: três
funções deste módulo (`promover_a_revisor`, `revogar_revisor`,
`listar_revisores`), expostas pela linha de comando em
`scripts/papel_revisor.py` (`T-183`). Nenhuma delas é chamada por rota
HTTP, e nenhuma dependência do FastAPI as expõe.

**Por que não há rota, e por que isso não muda.** O primeiro revisor é um
problema de origem: não há revisor para autorizar a promoção do primeiro
revisor. Qualquer rota que resolvesse isso teria de aceitar um segredo de
ambiente como autoridade — e passaria a ser, permanentemente, uma porta
pública que concede acesso de leitura ao caso de TODOS os alunos a quem
tiver aquele segredo. Um comando que exige acesso ao servidor e à
`DATABASE_URL` tem superfície de ataque zero pela internet. A raridade da
operação (uma vez na instalação, depois quase nunca) não paga o risco
permanente de manter a porta aberta.

O SQL equivalente continua válido para quem administra o banco direto:

```sql
UPDATE app_aluno.contas SET e_revisor = true WHERE email = 'revisor@exemplo.invalido';
```

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
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

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
    #: `None` = conta provisionada, senha ainda não definida (`T-179`) — o
    #: estado de quem comprou e ainda não usou o link de primeiro acesso.
    #: `autenticar` recusa este caso explicitamente: sem senha definida,
    #: nenhum login passa.
    senha_hash: str | None
    criado_em: datetime
    e_revisor: bool = False
    #: `None` = conta ativa. Timestamp = bloqueada (reembolso da Hotmart,
    #: migração `005`) — `autenticar` recusa a partir daqui, mesma
    #: disciplina de `senha_hash is None`, acima.
    bloqueado_em: datetime | None = None


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
    pool = obter_pool()
    conexao = pool.getconn()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        pool.putconn(conexao)


def _linha_para_conta(linha: tuple[Any, ...]) -> Conta:
    conta_id, email, senha_hash, criado_em, e_revisor, bloqueado_em = linha
    return Conta(
        conta_id=conta_id,
        email=email,
        senha_hash=senha_hash,
        criado_em=criado_em if criado_em.tzinfo is not None else criado_em.replace(tzinfo=UTC),
        e_revisor=e_revisor,
        bloqueado_em=bloqueado_em,
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

    def provisionar(self, conta_id: str, email: str) -> None:
        """Cria conta SEM senha (`T-179`) — o caminho de quem compra pela
        Hotmart, que nunca informa senha. `senha_hash` fica `NULL` até o
        aluno definir a dele; enquanto isso, `autenticar` recusa. Levanta
        `ErroEmailDuplicado` se `email` já existir."""
        ...

    def definir_senha(self, conta_id: str, senha: str) -> None:
        """Grava a senha escolhida pelo aluno (`T-179`) — primeiro acesso e
        recuperação terminam aqui, depois de o token provar posse do
        e-mail. Levanta `ErroContaInexistente` se `conta_id` não existir."""
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

    def bloquear(self, conta_id: str) -> None:
        """Marca a conta como bloqueada (`bloqueado_em`, migração `005`) —
        `autenticar` passa a recusá-la. Chamado pelo webhook
        `PURCHASE_REFUNDED` da Hotmart (`app/http/rotas_provisionamento.py`).
        Idempotente: bloquear uma conta já bloqueada não é erro, só não
        muda o timestamp original."""
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

    def provisionar(self, conta_id: str, email: str) -> None:
        """Cria uma conta SEM senha — `T-179`.

        **O caminho de quem compra, não de quem se cadastra.** O webhook da
        Hotmart traz nome e e-mail; senha, nunca. A conta nasce com
        `senha_hash = NULL` (migração `004`) e o aluno a define depois, pelo
        link de primeiro acesso.

        Enquanto `senha_hash` for `NULL`, `autenticar` recusa — conta sem
        senha não é conta aberta."""
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.contas (conta_id, email, senha_hash, criado_em)
                    VALUES (%s, %s, NULL, %s)
                    """,
                    (conta_id, email, datetime.now(UTC)),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.errors.UniqueViolation as erro:
            raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}") from erro
        except psycopg.Error as erro:
            raise ErroGravacaoConta(
                f"falha ao provisionar conta conta_id={conta_id!r} email={email!r}: {erro}"
            ) from erro

    def definir_senha(self, conta_id: str, senha: str) -> None:
        """Grava a senha que o aluno escolheu — `T-179`.

        Serve ao primeiro acesso E à recuperação: os dois terminam aqui,
        depois de o token provar a posse do e-mail. A senha em texto claro
        vive só na variável local, hasheada antes de qualquer gravação.

        `ErroContaInexistente` se `conta_id` não existir — nunca cria conta
        por efeito colateral de definir senha."""
        senha_hash = hashear_senha(senha)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.contas
                    SET senha_hash = %s
                    WHERE conta_id = %s
                    """,
                    (senha_hash, conta_id),
                )
                if cursor.rowcount == 0:
                    raise ErroContaInexistente(
                        f"definir_senha recusada: conta_id={conta_id!r} não existe"
                    )
        except ErroConexaoAusente:
            raise
        except ErroContaInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoConta(
                f"falha ao definir senha conta_id={conta_id!r}: {erro}"
            ) from erro

    def buscar_por_email(self, email: str) -> Conta | None:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT conta_id, email, senha_hash, criado_em, e_revisor, bloqueado_em
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
                SELECT conta_id, email, senha_hash, criado_em, e_revisor, bloqueado_em
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
        # **Conta provisionada e sem senha definida NÃO autentica** —
        # `T-179`. Desde a migração `004`, `senha_hash` aceita `NULL`: é o
        # estado de quem comprou (webhook da Hotmart criou a conta) e ainda
        # não definiu a própria senha pelo link de primeiro acesso.
        #
        # Sem esta guarda, `verificar_senha(None, ...)` teria comportamento
        # indefinido — e uma conta sem senha seria uma conta aberta. O
        # retorno é `None`, indistinguível de "não existe" e de "senha
        # errada", pela mesma razão dos dois ramos acima (`RF-02`).
        if conta.senha_hash is None:
            return None
        # **Conta bloqueada por reembolso NÃO autentica** (migração `005`).
        # Mesma disciplina do guard acima: `None`, indistinguível de "não
        # existe" e de "senha errada" — quem tenta entrar não aprende que a
        # conta já existiu.
        if conta.bloqueado_em is not None:
            return None
        if not verificar_senha(conta.senha_hash, senha):
            return None
        return conta

    def bloquear(self, conta_id: str) -> None:
        """`COALESCE`: se já estava bloqueada, preserva o timestamp
        original — reembolso duplicado (a Hotmart pode reenviar o mesmo
        webhook) não apaga QUANDO o bloqueio realmente aconteceu."""
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.contas
                    SET bloqueado_em = COALESCE(bloqueado_em, %s)
                    WHERE conta_id = %s
                    """,
                    (datetime.now(UTC), conta_id),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoConta(f"falha ao bloquear conta_id={conta_id!r}: {erro}") from erro


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


def revogar_revisor(email: str) -> None:
    """Tira o papel de revisor de uma conta — `RF-23`/`RF-25`, `T-183`.

    **Existe porque `promover_a_revisor` sozinha é irreversível.** Promover
    o e-mail errado — um caractere trocado que bata com outra conta real —
    dava a um aluno acesso de leitura ao caso de todos os outros, e desfazer
    isso exigia SQL direto em produção, no susto. Uma operação de
    autorização que não tem como ser desfeita pela via normal empurra quem
    administra para a via perigosa justamente no pior momento.

    A conta NÃO é apagada: perde o papel e volta a ser conta comum, com o
    caso e o histórico dela intactos.

    Levanta `ErroContaInexistente` se `email` não corresponder a nenhuma
    conta. Revogar de quem já não é revisor é sucesso silencioso — o estado
    final é o pedido, e falhar aqui só faria quem administra hesitar diante
    de um comando que já fez o que devia."""
    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                UPDATE app_aluno.contas
                SET e_revisor = false
                WHERE email = %s
                """,
                (email,),
            )
            if cursor.rowcount == 0:
                raise ErroContaInexistente(f"revogação recusada: email={email!r} não existe")
    except ErroConexaoAusente:
        raise
    except ErroContaInexistente:
        raise
    except psycopg.Error as erro:
        raise ErroGravacaoConta(f"falha ao revogar revisor email={email!r}: {erro}") from erro


def listar_revisores() -> tuple[Conta, ...]:
    """Quem tem o papel de revisor, agora — `RF-23`/`RF-25`, `T-183`.

    **Conferir é parte da operação, não um extra.** Promover às cegas e não
    ter como listar o resultado deixa quem administra sem saber se acertou
    o e-mail, e sem como auditar depois quem ficou com acesso aos casos de
    todos os alunos. Uma lista vazia é resposta legítima (e é o estado do
    sistema recém-instalado), nunca um erro.

    Ordenado por `criado_em` para que a saída seja estável entre chamadas —
    uma lista que muda de ordem sozinha não serve para comparar antes e
    depois."""
    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT conta_id, email, senha_hash, criado_em, e_revisor, bloqueado_em
                FROM app_aluno.contas
                WHERE e_revisor = true
                ORDER BY criado_em, email
                """
            )
            return tuple(_linha_para_conta(linha) for linha in cursor.fetchall())
    except ErroConexaoAusente:
        raise
    except psycopg.Error as erro:
        raise ErroGravacaoConta(f"falha ao listar revisores: {erro}") from erro
