"""Cadastro atômico de `Conta` + `Caso` — `RF-02`, `AC-03` (T-30).

`RepositorioContasSupabase.criar` (T-28) e `RepositorioCasosSupabase.criar`
(T-23), cada um em `persistencia/app_aluno/{contas,casos}.py`, abrem e
COMMITAM a própria conexão internamente — chamá-los em sequência não seria
atômico (a conta commitaria antes de o caso sequer começar a ser gravado).
Como `app_aluno.contas` e `app_aluno.casos` vivem no MESMO banco Postgres
(schema `app_aluno`; `casos.conta_id` é FK de `contas.conta_id`), a
atomicidade real exige as duas gravações na MESMA conexão/transação — este
módulo existe só para isso: `cadastrar_conta_e_caso` retira UMA conexão do
pool compartilhado (`obter_pool`, `T-187`, genérico, e `app.http.senhas.
hashear_senha`, puro) e faz os dois `INSERT`s antes de um único commit. Se o
segundo falhar, o `ROLLBACK` desfaz também o primeiro — nunca uma conta
órfã sem caso.

Este módulo vive em `persistencia/` (não em `app/http/rotas_conta.py`, que o
chama) pela mesma razão que todo SQL desta feature vive em `persistencia/`:
é a fronteira que os testes estáticos de `app/` (T-08, `AC-37`) varrem à
procura de conteúdo de questionário — strings de SQL não são conteúdo de
pergunta, mas são longas o bastante para acionar o limiar heurístico
daquele teste. Isolar o SQL aqui, junto dos demais adaptadores da feature,
evita alargar a lista de exceções daquele teste com um padrão amplo demais.

Direção de dependência: este módulo importa de `app.http.senhas` (hash
puro), `app.casos.maquina` (`ESTADO_CASO`/`Caso`, tipos de domínio) e
`persistencia.app_aluno.contas` (`Conta`, `ErroEmailDuplicado`),
`collection.carga` (a versão corrente do questionário, `T-179` — mesmo
precedente de `persistencia/app_aluno/arquivo.py`) e de `psycopg`/stdlib —
nunca de `engine/`.

REGRAS: `RF-02`, `AC-03`
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Final

import psycopg

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.senhas import hashear_senha
from collection.carga import carregar_registros
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

REGRAS: Final[tuple[str, ...]] = ("RF-02", "AC-03")

_SCHEMA: Final[str] = "app_aluno"

def _questionario_version_corrente() -> str:
    """A versão do questionário que o caso novo carrega — `T-179`.

    **Era o literal `"PENDENTE"` até aqui.** O comentário que o acompanhava
    admitia ser provisório ("o valor é sobrescrito pela carga real quando o
    Bloco 1 começa, fora deste escopo") — mas nada o sobrescrevia, e todo
    caso criado pela rota real nascia com `QUESTIONARIO_VERSION =
    "PENDENTE"`. Como esse campo é o que diz QUAL versão do questionário o
    aluno respondeu, o dado de auditoria e de reprodutibilidade
    metodológica saía corrompido desde a criação.

    `carregar_registros()` é o ponto único que a nota original procurava:
    ele já existe (`T-16`) e é o mesmo que `scripts/subir_demo.py` usa.
    Lido a cada cadastro, e não em constante de módulo, para que uma
    atualização do questionário valha para os casos seguintes sem reiniciar
    o processo."""
    return carregar_registros().QUESTIONARIO_VERSION


class ErroCadastro(Exception):
    """Levantado quando o cadastro atômico de conta+caso falha antes do
    commit — nunca engolida: nem a conta nem o caso ficam persistidos
    parcialmente (mesma disciplina de `EC-05` de T-22/T-23)."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/casos.py::_conectar`:
    `search_path` fixado em `app_aluno`, commit ao sair sem exceção,
    rollback e propagação ao sair com exceção. `conectar()` daquele módulo
    não serve aqui mesmo com o pool compartilhado (`T-187`): fixa
    `search_path=motor_calculo`, o schema errado para este adaptador."""
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


def provisionar_conta_e_caso(email: str) -> tuple[Conta, Caso]:
    """Cria `Conta` SEM SENHA + `Caso` na MESMA transação — `T-179`.

    **O caminho de quem COMPRA, não de quem se cadastra.** O webhook da
    Hotmart traz e-mail; senha, nunca. A conta nasce com `senha_hash =
    NULL` (migração `004`) e o aluno a define depois, pelo link de primeiro
    acesso — até lá, `autenticar` recusa.

    Mesma atomicidade de `cadastrar_conta_e_caso`: se o `INSERT` do caso
    falhar, o `ROLLBACK` desfaz também o da conta — nunca conta órfã.

    `ErroEmailDuplicado` se `email` já existir. Quem chama decide o que
    fazer com isso; a rota de provisionamento trata como reenvio de link,
    não como erro (uma compra repetida do mesmo aluno é normal)."""
    conta_id = f"CONTA_{uuid.uuid4().hex}"
    caso_id = f"CASO_{uuid.uuid4().hex}"
    agora = datetime.now(UTC)
    hoje = date.today()
    questionario_version = _questionario_version_corrente()

    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_aluno.contas "
                "(conta_id, email, senha_hash, criado_em) VALUES (%s, %s, NULL, %s)",
                (conta_id, email, agora),
            )
            cursor.execute(
                'INSERT INTO app_aluno.casos ("CASO_ID", conta_id, estado, '
                '"DATA_REFERENCIA", "QUESTIONARIO_VERSION", snapshot_raiz_id, '
                "snapshot_liberado_id, ultima_interacao_em, criado_em) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    caso_id,
                    conta_id,
                    ESTADO_CASO.CADASTRADO.value,
                    hoje,
                    questionario_version,
                    None,
                    None,
                    agora,
                    agora,
                ),
            )
    except ErroConexaoAusente:
        raise
    except psycopg.errors.UniqueViolation as erro:
        raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}") from erro
    except psycopg.Error as erro:
        raise ErroCadastro(f"falha ao provisionar conta+caso email={email!r}: {erro}") from erro

    conta = Conta(conta_id=conta_id, email=email, senha_hash=None, criado_em=agora)
    caso = Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=ESTADO_CASO.CADASTRADO,
        DATA_REFERENCIA=hoje,
        QUESTIONARIO_VERSION=questionario_version,
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=agora,
        criado_em=agora,
    )
    return conta, caso


def cadastrar_conta_e_caso(email: str, senha: str) -> tuple[Conta, Caso]:
    """Cria `Conta` e `Caso` (em `ESTADO_CASO.CADASTRADO`) na MESMA
    transação: se o `INSERT` do caso falhar, o `ROLLBACK` desfaz também o
    `INSERT` da conta — nunca uma conta órfã sem caso. Levanta
    `ErroEmailDuplicado` se `email` já existir (mesma exceção de
    `RepositorioContasSupabase.criar`, T-28)."""
    conta_id = f"CONTA_{uuid.uuid4().hex}"
    caso_id = f"CASO_{uuid.uuid4().hex}"
    senha_hash = hashear_senha(senha)
    agora = datetime.now(UTC)
    hoje = date.today()
    # Uma leitura só: `carregar_registros()` reparseia os YAML a cada
    # chamada, e o `Caso` devolvido no fim precisa da MESMA versão gravada.
    questionario_version = _questionario_version_corrente()

    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_aluno.contas "
                "(conta_id, email, senha_hash, criado_em) VALUES (%s, %s, %s, %s)",
                (conta_id, email, senha_hash, agora),
            )
            cursor.execute(
                'INSERT INTO app_aluno.casos ("CASO_ID", conta_id, estado, '
                '"DATA_REFERENCIA", "QUESTIONARIO_VERSION", snapshot_raiz_id, '
                "snapshot_liberado_id, ultima_interacao_em, criado_em) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    caso_id,
                    conta_id,
                    ESTADO_CASO.CADASTRADO.value,
                    hoje,
                    questionario_version,
                    None,
                    None,
                    agora,
                    agora,
                ),
            )
    except ErroConexaoAusente:
        raise
    except psycopg.errors.UniqueViolation as erro:
        raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}") from erro
    except psycopg.Error as erro:
        raise ErroCadastro(f"falha ao cadastrar conta+caso email={email!r}: {erro}") from erro

    conta = Conta(conta_id=conta_id, email=email, senha_hash=senha_hash, criado_em=agora)
    caso = Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=ESTADO_CASO.CADASTRADO,
        DATA_REFERENCIA=hoje,
        QUESTIONARIO_VERSION=questionario_version,
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=agora,
        criado_em=agora,
    )
    return conta, caso
