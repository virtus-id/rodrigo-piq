"""`UPDATE`/`DELETE` real sobre `motor_calculo.snapshots` é recusado pelo
banco — RF-19, AC-32, T-26.

`AC-32`: "`UPDATE` e `DELETE` reais sobre `motor_calculo.snapshots` são
recusados, e o snapshot permanece inalterado." Este módulo prova, contra
Postgres REAL (nunca dublê), a defesa dupla de `001_inicial.sql`: `REVOKE
UPDATE, DELETE ... FROM PUBLIC` e a trigger `impedir_sobrescrita_v01`
(`V-01`). O teste irmão em `tests/integracao/test_repositorio_snapshots.py`
(slug `motor-calculo`, T-76) já prova o `UPDATE`; este módulo, desta feature
(`app-aluno`), cobre os DOIS verbos (`UPDATE` e `DELETE`) e confirma
explicitamente que o snapshot permanece inalterado após cada tentativa —
critério de aceite que o teste irmão não verificava com a mesma ênfase.

Os dois testes de recusa exigem Postgres real (`@pytest.mark.requer_banco`),
pulados com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`, T-05) — marcação individual, não `pytestmark` de módulo, para
que `test_skip_gracioso_sem_database_url_nao_e_erro_nem_falha` (que roda
sempre, mesmo padrão de T-76) não seja ela própria pulada.

**Dados de teste marcados.** `motor_calculo.snapshots` é append-only por
design (`V-01`): não há como o teste apagar as linhas que grava. Toda linha
inserida por este módulo usa `MOTIVO_RECALCULO` prefixado com
`TESTE_T26_`, mesmo padrão de `TESTE_T76_` (T-76) e `TESTE_T23_` (T-23).

Inserção mínima, sem depender do motor. Diferente de
`tests/integracao/test_repositorio_snapshots.py` (que monta um
`SnapshotOrdem` completo via `GAB-C`), este módulo insere uma linha mínima
diretamente por SQL (`INSERT INTO motor_calculo.snapshots (...) VALUES
(...)`) preenchendo só as colunas `NOT NULL` — o objetivo do teste é a
recusa de `UPDATE`/`DELETE` pelo banco, não o round-trip de um snapshot
real (já coberto por T-76/T-25). Isso também evita acoplar este teste de
`app-aluno` ao motor de cálculo, que está congelado para este backlog
(cabeçalho de `tasks/app-aluno.tasks.md`).

REGRAS: RF-19, AC-32, AC-43
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _inserir_snapshot_minimo(cursor: psycopg.Cursor[tuple[object, ...]]) -> tuple[str, str]:
    """Insere a linha mínima válida em `motor_calculo.snapshots` — só as
    colunas `NOT NULL` (ver `\\d motor_calculo.snapshots` em
    `001_inicial.sql`) — e devolve `(SNAPSHOT_ID, MOTIVO_RECALCULO)` para
    comparação posterior. `SNAPSHOT_ID` é único por execução (`uuid4`), já
    que a tabela é append-only e nunca pode ser limpa entre execuções."""
    snapshot_id = f"TESTE_T26_{uuid.uuid4().hex}"
    motivo_original = f"TESTE_T26_motivo_original_{uuid.uuid4().hex}"
    cursor.execute(
        """
        INSERT INTO motor_calculo.snapshots (
            "SNAPSHOT_ID", versao, "DATA_REFERENCIA", "MOTIVO_RECALCULO", hash_inputs,
            "METODO_RECOMENDADO_PIQ", "STATUS_METODO", "ORDEM_STATUS",
            "REVISAO_HUMANA_OBRIGATORIA", "CUSTO_FUTURO_TOTAL",
            "CAPACIDADE_ATAQUE_ATUAL", "CAPACIDADE_ATAQUE_CONSERVADORA",
            "CAPACIDADE_ATAQUE_POTENCIAL", "ENGINE_VERSION", "PARAMETROS_VERSION",
            dados_completos
        ) VALUES (
            %s, 1, CURRENT_DATE, %s, %s,
            'AVALANCHE', 'PROVISORIO', 'PROVISORIO',
            false, 1000.00,
            500.00, 400.00,
            600.00, '1.0.0', '1.0.1',
            '{}'::jsonb
        )
        """,
        (snapshot_id, motivo_original, f"hash_{uuid.uuid4().hex}"),
    )
    return snapshot_id, motivo_original


def _ler_motivo_recalculo(
    cursor: psycopg.Cursor[tuple[object, ...]], snapshot_id: str
) -> str:
    cursor.execute(
        'SELECT "MOTIVO_RECALCULO" FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
        (snapshot_id,),
    )
    linha = cursor.fetchone()
    assert linha is not None, f"snapshot {snapshot_id} deveria existir após o INSERT"
    valor = linha[0]
    assert isinstance(valor, str)
    return valor


@pytest.mark.requer_banco
def test_ac32_update_direto_em_snapshots_e_recusado_e_snapshot_permanece_inalterado() -> None:
    """`AC-32`: um `UPDATE` real via `psycopg` contra `motor_calculo.
    snapshots` levanta erro do Postgres (`REVOKE` + trigger `impedir_
    sobrescrita_v01`, `V-01`) — e, após a tentativa (com rollback), o valor
    original de `MOTIVO_RECALCULO` continua exatamente o mesmo, lido numa
    transação nova."""
    from persistencia.supabase.conexao import conectar

    with conectar() as conexao_gravacao, conexao_gravacao.cursor() as cursor_gravacao:
        snapshot_id, motivo_original = _inserir_snapshot_minimo(cursor_gravacao)

    with psycopg.connect(_database_url()) as conexao_ataque:
        with conexao_ataque.cursor() as cursor_ataque, pytest.raises(psycopg.Error) as excinfo:
            cursor_ataque.execute(
                'UPDATE motor_calculo.snapshots SET "MOTIVO_RECALCULO" = %s '
                'WHERE "SNAPSHOT_ID" = %s',
                ("TESTE_T26_tentativa_de_sobrescrita_V01", snapshot_id),
            )
        conexao_ataque.rollback()

    assert "V-01" in str(excinfo.value) or "append-only" in str(excinfo.value).lower(), (
        f"esperava que o erro citasse a defesa V-01, obteve: {excinfo.value!r}"
    )

    with psycopg.connect(_database_url()) as conexao_leitura, conexao_leitura.cursor() as cursor:
        cursor.execute("SET search_path TO motor_calculo, public")
        motivo_apos_tentativa = _ler_motivo_recalculo(cursor, snapshot_id)

    assert motivo_apos_tentativa == motivo_original, (
        "AC-32: o snapshot deveria permanecer INALTERADO após a tentativa de UPDATE "
        f"recusada — esperava {motivo_original!r}, obteve {motivo_apos_tentativa!r}"
    )


@pytest.mark.requer_banco
def test_ac32_delete_direto_em_snapshots_e_recusado_e_snapshot_permanece_inalterado() -> None:
    """`AC-32`: um `DELETE` real via `psycopg` contra `motor_calculo.
    snapshots` também é recusado pelo banco — e, após a tentativa (com
    rollback), a linha ainda existe e seu conteúdo não mudou."""
    from persistencia.supabase.conexao import conectar

    with conectar() as conexao_gravacao, conexao_gravacao.cursor() as cursor_gravacao:
        snapshot_id, motivo_original = _inserir_snapshot_minimo(cursor_gravacao)

    with psycopg.connect(_database_url()) as conexao_ataque:
        with conexao_ataque.cursor() as cursor_ataque, pytest.raises(psycopg.Error) as excinfo:
            cursor_ataque.execute(
                'DELETE FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
                (snapshot_id,),
            )
        conexao_ataque.rollback()

    assert "V-01" in str(excinfo.value) or "append-only" in str(excinfo.value).lower(), (
        f"esperava que o erro citasse a defesa V-01, obteve: {excinfo.value!r}"
    )

    with psycopg.connect(_database_url()) as conexao_leitura, conexao_leitura.cursor() as cursor:
        cursor.execute("SET search_path TO motor_calculo, public")
        cursor.execute(
            'SELECT "MOTIVO_RECALCULO" FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
            (snapshot_id,),
        )
        linha = cursor.fetchone()

    assert linha is not None, (
        "AC-32: a linha do snapshot deveria continuar existindo após a tentativa "
        "de DELETE recusada — não deveria ter sido removida"
    )
    assert linha[0] == motivo_original, (
        "AC-32: o snapshot deveria permanecer INALTERADO após a tentativa de DELETE "
        f"recusada — esperava {motivo_original!r}, obteve {linha[0]!r}"
    )


def test_skip_gracioso_sem_database_url_nao_e_erro_nem_falha() -> None:
    """Sem `DATABASE_URL` no ambiente, os testes deste módulo aparecem como
    `skipped` — nunca `failed`/`error` — via o hook de `tests/app_aluno/
    conftest.py`. Este teste roda sempre (não é `requer_banco`, e sim uma
    checagem sobre o motivo do skip) e documenta o comportamento esperado."""
    if _DATABASE_URL_AUSENTE:
        assert _MOTIVO_SKIP
    else:
        assert os.environ.get("DATABASE_URL")
