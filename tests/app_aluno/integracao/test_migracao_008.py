"""Migração `008_extraordinarios_por_item.sql` contra Postgres real — `RF-98`
(`T-271`, `DE-02`, `R9-11`).

Tudo roda numa ÚNICA transação desfeita no fim (`rollback`): a migração
nunca fica aplicada no banco por causa deste teste. Pulado sem
`DATABASE_URL` (hook de `tests/app_aluno/conftest.py`).

REGRAS: `RF-98`
"""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest

_MIGRACAO = (
    Path(__file__).resolve().parents[3]
    / "persistencia/supabase/migracoes/008_extraordinarios_por_item.sql"
)
_VARIAVEIS = (
    "TIPO_RECURSO_EXTRAORDINARIO",
    "VALOR_RECURSO_EXTRAORDINARIO",
    "JANELA_RECURSO_EXTRAORDINARIO",
    "CERTEZA_RECURSO_EXTRAORDINARIO",
)


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _caso(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    conta_id = f"TESTE_T271_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T271_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, 'COLETA_INICIAL', CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id),
    )
    return caso_id


def _responder_legado(cursor: psycopg.Cursor[tuple[object, ...]], caso_id: str) -> None:
    textos = ("13O_SALARIO", None, "1_3M", "CONFIRMADO")
    for variavel, texto in zip(_VARIAVEIS, textos, strict=True):
        cursor.execute(
            """
            INSERT INTO app_aluno.respostas
                ("CASO_ID", "ID_PERGUNTA", item_id, valor_texto, valor_numerico,
                 "QUESTIONARIO_VERSION")
            VALUES (%s, %s, '', %s, %s, '1.0.0')
            """,
            (caso_id, variavel, texto, 3000 if texto is None else None),
        )


@pytest.mark.requer_banco
def test_t271_legado_vai_para_ext001_e_rodar_duas_vezes_e_rodar_uma() -> None:
    sql = _MIGRACAO.read_text(encoding="utf-8")
    with psycopg.connect(_database_url()) as conexao:
        try:
            with conexao.cursor() as cursor:
                legado = _caso(cursor)
                _responder_legado(cursor, legado)
                ja_tem_item = _caso(cursor)
                _responder_legado(cursor, ja_tem_item)
                cursor.execute(
                    "INSERT INTO app_aluno.itens_repetidos (item_id, \"CASO_ID\", escopo)"
                    " VALUES (%s, %s, 'RECURSO_EXTRAORDINARIO_ID')",
                    (f"{ja_tem_item}:EXT001", ja_tem_item),
                )

                def estado() -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
                    cursor.execute(
                        """
                        SELECT "CASO_ID", "ID_PERGUNTA", item_id FROM app_aluno.respostas
                        WHERE "CASO_ID" IN (%s, %s) ORDER BY 1, 2
                        """,
                        (legado, ja_tem_item),
                    )
                    respostas = cursor.fetchall()
                    cursor.execute(
                        "SELECT item_id, escopo FROM app_aluno.itens_repetidos"
                        " WHERE \"CASO_ID\" IN (%s, %s) ORDER BY 1",
                        (legado, ja_tem_item),
                    )
                    return respostas, cursor.fetchall()

                cursor.execute(sql)
                uma_vez = estado()
                cursor.execute(sql)

                assert estado() == uma_vez
                respostas, itens = uma_vez
                assert {(c, i) for c, _v, i in respostas if c == legado} == {(legado, "EXT001")}
                assert {i for c, _v, i in respostas if c == ja_tem_item} == {""}
                assert (f"{legado}:EXT001", "RECURSO_EXTRAORDINARIO_ID") in itens
        finally:
            conexao.rollback()
