"""Guarda "sem consentimento, nenhuma resposta é gravada" contra Postgres
real — `RF-30`, `AC-39` (T-36).

Reconfirma `tests/app_aluno/test_guarda_consentimento_resposta.py` (que roda
com dublê de cursor, sem banco) contra Postgres de verdade: cria um caso REAL
em `CADASTRADO`, tenta gravar uma resposta pelo caminho de produção
(`RepositorioRespostasSupabase.gravar`) e confirma, com uma consulta direta
à tabela, que NENHUMA linha foi inserida.

`@pytest.mark.requer_banco`, pulado com mensagem explícita sem
`DATABASE_URL` (hook de `tests/app_aluno/conftest.py`).

REGRAS: `RF-30`, `AC-39`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from app.casos.maquina import ErroConsentimentoNaoRegistrado
from collection.respostas import Resposta
from persistencia.app_aluno.respostas import RepositorioRespostasSupabase

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _conta_e_caso_novos(
    cursor: psycopg.Cursor[tuple[object, ...]], estado: str
) -> str:
    """Cria conta + caso mínimos no `estado` pedido e devolve o `CASO_ID`
    novo, isolado por execução — mesmo padrão de `test_persistencia_
    respostas.py`."""
    conta_id = f"TESTE_T36_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T36_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, %s, CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id, estado),
    )
    return caso_id


def _total_de_respostas(cursor: psycopg.Cursor[tuple[object, ...]], caso_id: str) -> int:
    cursor.execute(
        'SELECT count(*) FROM app_aluno.respostas WHERE "CASO_ID" = %s',
        (caso_id,),
    )
    (total,) = cursor.fetchone()  # type: ignore[misc]
    return int(total)  # type: ignore[arg-type]


def test_ac39_caso_em_cadastrado_recusa_gravacao_e_nenhuma_linha_e_inserida() -> None:
    """`AC-39`, contra banco real: caso em `CADASTRADO`, tentativa de gravar
    resposta pelo caminho de produção — recusada, e `app_aluno.respostas`
    continua com zero linhas para este caso."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor, "CADASTRADO")

    repositorio = RepositorioRespostasSupabase()

    with pytest.raises(ErroConsentimentoNaoRegistrado):
        repositorio.gravar(
            Resposta(
                CASO_ID=caso_id,
                ID_PERGUNTA="B1.01",
                item_id=None,
                valor="sim",
                QUESTIONARIO_VERSION="1.0.0",
                respondida_em=datetime.now(UTC),
            )
        )

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        assert _total_de_respostas(cursor, caso_id) == 0


def test_caso_em_consentimento_registrado_tambem_recusa_gravacao() -> None:
    """Reforço do critério 4: o carimbo de consentimento já existe mas
    `inicia_coleta` ainda não disparou — a gravação continua recusada."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor, "CONSENTIMENTO_REGISTRADO")

    repositorio = RepositorioRespostasSupabase()

    with pytest.raises(ErroConsentimentoNaoRegistrado):
        repositorio.gravar(
            Resposta(
                CASO_ID=caso_id,
                ID_PERGUNTA="B1.01",
                item_id=None,
                valor="sim",
                QUESTIONARIO_VERSION="1.0.0",
                respondida_em=datetime.now(UTC),
            )
        )

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        assert _total_de_respostas(cursor, caso_id) == 0


def test_caso_em_coleta_inicial_permite_gravacao_normalmente() -> None:
    """Contraprova contra banco real: com o caso em `COLETA_INICIAL`, a
    gravação é aceita e a linha aparece em `app_aluno.respostas`."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor, "COLETA_INICIAL")

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.01",
            item_id=None,
            valor="sim",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        assert _total_de_respostas(cursor, caso_id) == 1
