"""Testes de `persistencia/app_aluno/consentimentos.py` — `RF-30`, `AC-39`
(T-35).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`) — mesmo padrão de `test_persistencia_casos.py` (T-23).

REGRAS: RF-30, AC-39
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from app.consentimento.registro import RegistroConsentimento
from persistencia.app_aluno.consentimentos import RepositorioConsentimentosSupabase

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _conta_e_caso_novos(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Cria conta + caso mínimos (FK de `app_aluno.consentimentos` via
    `app_aluno.casos`) e devolve o `CASO_ID` novo, isolado por execução."""
    conta_id = f"TESTE_T35_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T35_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, 'CADASTRADO', CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id),
    )
    return caso_id


def test_registro_gravado_e_consultavel_por_caso() -> None:
    """Critério de aceite: "o registro grava versão do texto, aceite e
    data, e é consultável por caso"."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioConsentimentosSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)
    registro = RegistroConsentimento(
        CASO_ID=caso_id, versao_texto="1.0.0", aceite=True, aceito_em=agora
    )

    repositorio.gravar(f"TESTE_T35_CONSENT_{uuid.uuid4().hex}", registro)
    encontrados = repositorio.listar_do_caso(caso_id)

    assert len(encontrados) == 1
    lido = encontrados[0]
    assert lido.CASO_ID == caso_id
    assert lido.versao_texto == "1.0.0"
    assert lido.aceite is True
    assert lido.aceito_em == agora


def test_listar_do_caso_sem_consentimento_devolve_vazio() -> None:
    """Caso sem nenhum consentimento registrado devolve tupla vazia — nunca
    lança, nunca inventa um registro (`AC-39`: a ausência é o estado real)."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioConsentimentosSupabase()

    assert repositorio.listar_do_caso(caso_id) == ()
