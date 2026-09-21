"""Testes mínimos do adaptador Supabase/Postgres — `RF-10`, `RF-12`, `RF-13`,
`T-75`.

**Escopo desta tarefa.** Só o suficiente para provar que os três adaptadores
(`FonteParametrosSupabase`, `RepositorioSnapshotsSupabase`, a migração de
imutabilidade) funcionam de fato contra um banco real. A suíte completa de
integração/paridade arquivo × Postgres (round-trip de todo `Decimal`, cadeia
de `historico` fora de ordem, etc. — o mesmo nível de cobertura que
`tests/regras/test_repositorio_snapshots.py` já dá ao adaptador de arquivo)
é `T-76`, tarefa de TESTE separada e dependente desta — não duplicada aqui.

**Pulado inteiro sem `DATABASE_URL`.** A suíte de homologação do motor
(`pytest -q`) nunca depende do Supabase: sem a variável de ambiente, todo
teste deste módulo é pulado com mensagem explícita — mesmo padrão que `T-76`
formaliza com mais testes de integração.

**Dados de teste marcados.** `motor_calculo.snapshots` é append-only por
design (`V-01`, `migracoes/001_inicial.sql`): não há como o teste apagar as
linhas que grava. Toda linha inserida por este módulo usa `MOTIVO_RECALCULO`
prefixado com `TESTE_T75_`, para ficar claramente identificável como dado de
teste no banco compartilhado — documentado aqui em vez de tentar um `DELETE`
que o banco recusaria de qualquer forma.

REGRAS: RF-10, RF-12, RF-13
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.regra

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — adaptador Supabase é opcional (plano §2.1)"


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_fonte_parametros_supabase_carrega_parametros_identicos_ao_arquivo() -> None:
    """`FonteParametrosSupabase.carregar("1.0.1")` devolve um `Parametros`
    com os mesmos valores que `FonteParametrosArquivo` — prova mínima de
    que a leitura de `motor_calculo.parametros` funciona contra o banco
    real. Pré-requisito: a linha `PARAMETROS_VERSION = '1.0.1'` já existe
    na tabela (carregada a partir de `parameters/parametros-1.0.1.json`
    pela rotina de seed do ambiente — fora do escopo desta tarefa criar
    essa carga automatizada)."""
    from decimal import Decimal

    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.fonte_parametros import FonteParametrosSupabase

    esperado = FonteParametrosArquivo().carregar("1.0.1")
    obtido = FonteParametrosSupabase().carregar("1.0.1")

    assert obtido.PARAMETROS_VERSION == esperado.PARAMETROS_VERSION
    assert obtido.ENGINE_VERSION == esperado.ENGINE_VERSION
    assert obtido.DATA_VIGENCIA == esperado.DATA_VIGENCIA
    for nome in (
        "P_DIFERENCA_ECONOMICA_MATERIAL",
        "P_FATOR_SEGURANCA_MINIMO",
        "P_HORIZONTE_MAXIMO_SIMULACAO",
    ):
        valor_obtido = obtido.numero(nome)
        valor_esperado = esperado.numero(nome)
        assert isinstance(valor_obtido, Decimal), (
            f"{nome} deveria chegar como Decimal do numeric, nunca float"
        )
        assert valor_obtido == valor_esperado


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_snapshots_colunas_decisivas_sao_numeric_nao_apenas_jsonb() -> None:
    """Critério de aceite 1 de `T-75`: `CUSTO_FUTURO_TOTAL`, capacidades e
    `PRAZO_TOTAL` são colunas `numeric`/`integer` de primeira classe em
    `motor_calculo.snapshots` — consulta real a `information_schema.columns`,
    não inspeção do código Python."""
    from persistencia.supabase.conexao import conectar

    with conectar() as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'motor_calculo' AND table_name = 'snapshots'
            """
        )
        tipos_por_coluna = {nome: tipo for nome, tipo in cursor.fetchall()}

    for coluna in (
        "CUSTO_FUTURO_TOTAL",
        "CAPACIDADE_ATAQUE_ATUAL",
        "CAPACIDADE_ATAQUE_CONSERVADORA",
        "CAPACIDADE_ATAQUE_POTENCIAL",
    ):
        assert tipos_por_coluna.get(coluna) == "numeric", (
            f"{coluna} deveria ser numeric, encontrado {tipos_por_coluna.get(coluna)!r}"
        )
    assert tipos_por_coluna.get("PRAZO_TOTAL") == "integer"
    assert tipos_por_coluna.get("dados_completos") == "jsonb"


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_anexar_e_obter_round_trip_minimo_e_idempotente() -> None:
    """Critérios de aceite 2 (parcial) e 5 de `T-75`: `anexar` grava um
    snapshot real via `RepositorioSnapshotsSupabase`, `obter` devolve o
    mesmo `SNAPSHOT_ID`, e chamar `anexar` DUAS VEZES com o MESMO
    `SnapshotOrdem` não duplica a linha nem levanta erro (idempotência por
    `SNAPSHOT_ID`, derivado de `hash_inputs` + `versao` desde T-67)."""
    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.conexao import conectar
    from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase
    from tests.fixtures.carregar import carregar_gab_c
    from tests.regras.test_snapshot import _montar_snapshot_gab_c

    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    snapshot = _montar_snapshot_gab_c(
        estado=estado, parametros=parametros, motivo="TESTE_T75_idempotencia"
    )

    repositorio = RepositorioSnapshotsSupabase()
    repositorio.anexar(snapshot)
    repositorio.anexar(snapshot)  # segunda chamada — não deve duplicar nem falhar

    with conectar() as conexao, conexao.cursor() as cursor:
        cursor.execute(
            'SELECT count(*) FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
            (snapshot.SNAPSHOT_ID,),
        )
        (total,) = cursor.fetchone()  # type: ignore[misc]
    assert total == 1, (
        f"anexar duas vezes com o mesmo SnapshotOrdem deveria resultar em 1 "
        f"linha (ON CONFLICT DO NOTHING), encontrou {total}"
    )

    reobtido = repositorio.obter(snapshot.SNAPSHOT_ID)
    assert reobtido.SNAPSHOT_ID == snapshot.SNAPSHOT_ID
    assert reobtido.hash_inputs == snapshot.hash_inputs


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_update_e_delete_em_snapshots_sao_recusados_pelo_banco() -> None:
    """Critério de aceite 2 de `T-75`: `UPDATE`/`DELETE` reais em
    `motor_calculo.snapshots` são recusados pelo banco (`REVOKE` + trigger
    `impedir_sobrescrita_v01`) — executados de fato via `psycopg`, erro do
    Postgres capturado, nunca simulado."""
    import psycopg

    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.conexao import conectar
    from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase
    from tests.fixtures.carregar import carregar_gab_c
    from tests.regras.test_snapshot import _montar_snapshot_gab_c

    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    snapshot = _montar_snapshot_gab_c(
        estado=estado, parametros=parametros, motivo="TESTE_T75_bloqueio_update_delete"
    )
    RepositorioSnapshotsSupabase().anexar(snapshot)

    with conectar() as conexao:
        with conexao.cursor() as cursor, pytest.raises(psycopg.Error):
            cursor.execute(
                'UPDATE motor_calculo.snapshots SET "MOTIVO_RECALCULO" = %s '
                'WHERE "SNAPSHOT_ID" = %s',
                ("tentativa de sobrescrita", snapshot.SNAPSHOT_ID),
            )
        conexao.rollback()

        with conexao.cursor() as cursor, pytest.raises(psycopg.Error):
            cursor.execute(
                'DELETE FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
                (snapshot.SNAPSHOT_ID,),
            )
        conexao.rollback()
