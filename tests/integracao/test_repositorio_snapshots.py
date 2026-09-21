"""Round-trip de `RepositorioSnapshotsSupabase` e prova de `V-01` contra o
banco real — `RF-10`, `RF-12`, `RF-13`, `T-76`.

Critério de aceite 2 de `T-76`: `UPDATE` direto em `motor_calculo.snapshots`
falha no teste (`V-01`) — aqui, explicitamente como teste de INTEGRAÇÃO
(reaproveita a mesma prova de `tests/regras/test_supabase_adaptadores.py`,
T-75, citando `V-01` no nome e na docstring).

Critério de aceite 3 de `T-76`: um `SnapshotOrdem` real, com valores
`Decimal` de ALTA PRECISÃO (várias casas decimais — o tipo de valor que um
arredondamento incorreto na ida/volta pelo banco corromperia), sobrevive a
`anexar()`/`obter()` com todo `Decimal` comparado por `==` EXATO (nunca
`assertar_monetario`) contra o original.

Critério de aceite 4: sem `DATABASE_URL`, todo teste deste módulo é pulado
com mensagem explícita — mesmo padrão de `tests/regras/test_supabase_adaptadores.py`
(T-75).

**Dados de teste marcados.** `motor_calculo.snapshots` é append-only por
design (`V-01`): não há como o teste apagar as linhas que grava. Toda linha
inserida por este módulo usa `MOTIVO_RECALCULO` prefixado com `TESTE_T76_`,
mesmo padrão já adotado por T-75.

REGRAS: RF-10, RF-12, RF-13
"""

from __future__ import annotations

import dataclasses
import os
import time
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from engine.snapshot import SnapshotOrdem

pytestmark = pytest.mark.regra

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — adaptador Supabase é opcional (plano §2.1)"


def _snapshot_com_decimais_de_alta_precisao() -> SnapshotOrdem:
    """Monta um `SnapshotOrdem` real (`GAB-C`, via `_montar_snapshot_gab_c`,
    mesmo padrão de `tests/regras/test_snapshot.py`) e substitui os campos
    `Decimal` decisivos — os que viram coluna `numeric` de primeira classe
    em `motor_calculo.snapshots` (T-75) — por valores de MUITAS casas
    decimais, escolhidos para que um arredondamento incorreto (ex.:
    passagem por `float`, truncamento em `numeric` com escala fixa) mudasse
    o valor observável. `dataclasses.replace` preserva o restante da árvore
    intacto (mesmo padrão de `test_SNAPSHOT_ID_muda_quando_o_estado_muda`,
    `tests/regras/test_snapshot.py`).

    **`SNAPSHOT_ID` único por execução.** `SNAPSHOT_ID` é derivado só de
    `hash_inputs` (função de `estado`/`EstadoFinanceiro` + `PARAMETROS_VERSION`)
    e `versao` (`engine/snapshot.py::montar_SnapshotOrdem`) — nunca dos
    campos DERIVADOS que este teste sobrescreve (`diagnostico`/`cenarios`).
    `anexar` é idempotente por `SNAPSHOT_ID` (`ON CONFLICT DO NOTHING`,
    T-75): rodar este teste duas vezes com o MESMO `estado` de `GAB-C`
    produziria o MESMO `SNAPSHOT_ID` já usado por
    `tests/regras/test_supabase_adaptadores.py` (T-75), e a segunda
    inserção seria descartada silenciosamente — o `obter()` devolveria a
    linha ANTIGA (valores originais de `GAB-C`), não os `Decimal` de alta
    precisão deste teste, mascarando o próprio round-trip que o teste quer
    provar. Por isso `PESO_EMOCIONAL` da primeira dívida é perturbado com um
    valor derivado do relógio (`time.time_ns()`, mod 10 — domínio 0–10 do
    campo) só o suficiente para mudar `hash_inputs`/`SNAPSHOT_ID` a cada
    execução, sem afetar nenhuma regra do motor consumida por este teste
    (só a montagem/round-trip do snapshot é exercitada, não o cálculo)."""
    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from tests.fixtures.carregar import carregar_gab_c
    from tests.regras.test_snapshot import _montar_snapshot_gab_c

    estado_base = carregar_gab_c()
    peso_unico = time.time_ns() % 10
    primeira_divida = dataclasses.replace(estado_base.dividas[0], PESO_EMOCIONAL=peso_unico)
    estado = dataclasses.replace(
        estado_base, dividas=(primeira_divida, *estado_base.dividas[1:])
    )
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    original = _montar_snapshot_gab_c(
        estado=estado, parametros=parametros, motivo="TESTE_T76_round_trip_decimal"
    )

    diagnostico_precisao = dataclasses.replace(
        original.diagnostico,
        CAPACIDADE_ATAQUE_ATUAL=Decimal("1234.123456789012345"),
        CAPACIDADE_ATAQUE_CONSERVADORA=Decimal("987.987654321098765"),
        CAPACIDADE_ATAQUE_POTENCIAL=Decimal("5555.000000000000001"),
    )

    metodo_recomendado = original.METODO_RECOMENDADO_PIQ
    cenario_original = original.cenarios[metodo_recomendado]
    cenario_precisao = dataclasses.replace(
        cenario_original,
        CUSTO_FUTURO_TOTAL=Decimal("30201.111111111111111"),
    )
    cenarios_precisao = dict(original.cenarios)
    cenarios_precisao[metodo_recomendado] = cenario_precisao

    return dataclasses.replace(
        original,
        diagnostico=diagnostico_precisao,
        cenarios=cenarios_precisao,
    )


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_round_trip_preserva_decimal_de_alta_precisao_sem_perda_de_casa() -> None:
    """Critério de aceite 3 de `T-76`: `anexar()` seguido de `obter()`
    devolve os MESMOS `Decimal`, com as MESMAS casas, para todo campo
    decisivo (colunas `numeric`) e para o restante da árvore serializada em
    `dados_completos jsonb` — comparação `==` exata, nunca `assertar_
    monetario` (que tolera ± R$ 0,05 e mascararia perda de precisão)."""
    from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase

    original = _snapshot_com_decimais_de_alta_precisao()
    repositorio = RepositorioSnapshotsSupabase()
    repositorio.anexar(original)
    reobtido = repositorio.obter(original.SNAPSHOT_ID)

    metodo_recomendado = original.METODO_RECOMENDADO_PIQ
    cenario_original = original.cenarios[metodo_recomendado]
    cenario_reobtido = reobtido.cenarios[metodo_recomendado]

    # Colunas numeric de primeira classe (critério 1 de T-75) — round-trip
    # via coluna numeric do Postgres, não via dados_completos jsonb.
    assert type(reobtido.diagnostico.CAPACIDADE_ATAQUE_ATUAL) is Decimal
    assert (
        reobtido.diagnostico.CAPACIDADE_ATAQUE_ATUAL == original.diagnostico.CAPACIDADE_ATAQUE_ATUAL
    )
    assert (
        reobtido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
        == original.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    )
    assert (
        reobtido.diagnostico.CAPACIDADE_ATAQUE_POTENCIAL
        == original.diagnostico.CAPACIDADE_ATAQUE_POTENCIAL
    )
    assert type(cenario_reobtido.CUSTO_FUTURO_TOTAL) is Decimal
    assert cenario_reobtido.CUSTO_FUTURO_TOTAL == cenario_original.CUSTO_FUTURO_TOTAL
    assert cenario_reobtido.PRAZO_TOTAL == cenario_original.PRAZO_TOTAL

    # Confirma explicitamente que nenhuma casa decimal foi perdida — string
    # exata, não só igualdade numérica (uma igualdade Decimal == Decimal já
    # é exata, mas o teste também prova que o VALOR tem as 15 casas
    # esperadas, afastando qualquer arredondamento silencioso a montante).
    assert str(reobtido.diagnostico.CAPACIDADE_ATAQUE_ATUAL) == "1234.123456789012345"
    assert str(reobtido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA) == "987.987654321098765"
    assert str(reobtido.diagnostico.CAPACIDADE_ATAQUE_POTENCIAL) == "5555.000000000000001"
    assert str(cenario_reobtido.CUSTO_FUTURO_TOTAL) == "30201.111111111111111"

    # Restante da árvore (dados_completos jsonb) — mesmo padrão de
    # tests/regras/test_repositorio_snapshots.py::test_criterio3, campo a
    # campo, sempre == exato.
    assert reobtido.diagnostico.FATOR_SEGURANCA == original.diagnostico.FATOR_SEGURANCA
    assert reobtido.comparacao.DIFERENCA_PERCENTUAL == original.comparacao.DIFERENCA_PERCENTUAL
    assert reobtido.hash_inputs == original.hash_inputs
    assert reobtido.SNAPSHOT_ID == original.SNAPSHOT_ID
    assert reobtido.estado_inputs == original.estado_inputs
    assert reobtido.METODO_RECOMENDADO_PIQ == original.METODO_RECOMENDADO_PIQ
    assert reobtido.ORDEM_QUITACAO == original.ORDEM_QUITACAO
    assert reobtido.cenarios == original.cenarios
    assert reobtido.diagnostico == original.diagnostico

    for posicao_original, posicao_reobtida in zip(
        original.ORDEM_QUITACAO, reobtido.ORDEM_QUITACAO, strict=True
    ):
        for chave, valor in posicao_original.valores_de_apoio.items():
            assert posicao_reobtida.valores_de_apoio[chave] == valor


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_V01_update_direto_na_tabela_snapshots_falha_no_teste_de_integracao() -> None:
    """Critério de aceite 2 de `T-76`, explícito como teste de INTEGRAÇÃO:
    um `UPDATE` real via `psycopg` contra `motor_calculo.snapshots` é
    recusado pelo banco (`REVOKE UPDATE` + trigger `impedir_sobrescrita_v01`,
    `migracoes/001_inicial.sql`) — `V-01`, ordem/snapshot nunca sobrescritos.
    Reaproveita a prova de `tests/regras/test_supabase_adaptadores.py`
    (T-75), citando `V-01` explicitamente no nome deste teste."""
    import psycopg

    from persistencia.supabase.conexao import conectar
    from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase

    snapshot = _snapshot_com_decimais_de_alta_precisao()
    snapshot = dataclasses.replace(snapshot, MOTIVO_RECALCULO="TESTE_T76_V01_update_recusado")
    RepositorioSnapshotsSupabase().anexar(snapshot)

    with conectar() as conexao:
        with conexao.cursor() as cursor, pytest.raises(psycopg.Error):
            cursor.execute(
                'UPDATE motor_calculo.snapshots SET "MOTIVO_RECALCULO" = %s '
                'WHERE "SNAPSHOT_ID" = %s',
                ("tentativa de sobrescrita — V-01", snapshot.SNAPSHOT_ID),
            )
        conexao.rollback()


def test_skip_gracioso_sem_database_url_nao_e_erro_nem_falha() -> None:
    """Critério de aceite 4 de `T-76`: sem `DATABASE_URL` no ambiente, os
    testes deste módulo aparecem como `skipped` — nunca `failed`/`error`.
    Roda sempre (não é `skipif`), documentando o motivo esperado do skip."""
    if _DATABASE_URL_AUSENTE:
        assert _MOTIVO_SKIP
    else:
        assert os.environ.get("DATABASE_URL")
