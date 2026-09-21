"""`GAB-NFI-10` — ativo não essencial com fluxo negativo (`T-129`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1 (Fechamento Canônico — Necessidade Financeira Imediata e
Classificação de Ativos, congelado em 2026-09-09).

    `GAB-NFI-10`
      Cenário .......... `ESSENCIALIDADE=NAO_ESSENCIAL`,
                         `POSSIBILIDADE_VENDA=SIM`,
                         `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=30.000`,
                         `FLUXO_LIQUIDO_RECORRENTE_ATIVO=-500`
      Resultado ........ `MOBILIZACAO_RECOMENDAVEL`

Âncora: `AC-92` (`US-19`), `RF-54`, §14.8 ramo 8c, §14.16.

**Tolerância ZERO** (spec §5, mesma régua dos `GAB-AI`, `T-129`):
`assertar_exato` — comparação de `Enum`, não de valor monetário.

Este é o gabarito FORMAL, com marcador `gabarito_classificacao_ativos`, que
compõe o portão de homologação `pytest -m "gabarito or invariante or
gabarito_ataque_imediato or gabarito_classificacao_ativos"`. O mesmo cenário
aparece como teste de REGRA em `tests/regras/test_classificacao_ativos.py`
(`T-127`) — os dois lugares são deliberados e devem concordar: divergência
entre eles é erro real, não duplicação.
"""

import pytest

from engine.classificacao_ativos import classificar_ativo_fisico
from engine.estado import ESSENCIALIDADE, POSSIBILIDADE_VENDA, TIPO_ATIVO_FISICO, ItemAtivo
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO
from tests.conftest import assertar_exato


@pytest.mark.gabarito_classificacao_ativos
def test_gab_nfi_10_fluxo_negativo() -> None:
    """`GAB-NFI-10` · `AC-92` · §14.16: `ESSENCIALIDADE=NAO_ESSENCIAL`,
    `POSSIBILIDADE_VENDA=SIM`, valor líquido disponível `30.000`, fluxo
    líquido recorrente `-500` → `MOBILIZACAO_RECOMENDAVEL` (ramo 8c,
    §14.8: `FLUXO_LIQUIDO_RECORRENTE_ATIVO <= 0`).

    `FLUXO=-500` construído com `RENDA_RECORRENTE_ATIVO=0`,
    `CUSTO_RECORRENTE_ATIVO=500`. `VALOR_ESTIMADO_ATIVO=30.000`, sem
    passivo vinculado nem custo de desmobilização, produz
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=30.000`.
    """
    item = ItemAtivo(
        ITEM_ID="ATV-GAB-NFI-10",
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
        ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
        VALOR_ESTIMADO_ATIVO=dinheiro(30000),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=dinheiro(0),
        CUSTO_RECORRENTE_ATIVO=dinheiro(500),
    )

    obtido = classificar_ativo_fisico(item)

    assertar_exato(obtido, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL)
