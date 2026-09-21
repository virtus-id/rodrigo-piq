"""`GAB-NFI-12` — valor líquido negativo (`T-129`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1 (Fechamento Canônico — Necessidade Financeira Imediata e
Classificação de Ativos, congelado em 2026-09-09).

    `GAB-NFI-12`
      Cenário .......... `VALOR_ESTIMADO_ATIVO=100.000`,
                         `SALDO_PASSIVO_VINCULADO=105.000`,
                         `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000`
      Resultado ........ `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000`,
                         `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=0`

Âncora: `AC-94` (`US-20`), `RF-57`, §14.12.2 REGRA CANÔNICA, §14.16.

**Tolerância ZERO** (spec §5, "Tolerância" da Rodada 4): `Decimal` exato,
sem `± R$ 0,05` — `assertar_exato` em toda asserção monetária deste
gabarito, nunca `assertar_monetario`.

Este é o gabarito FORMAL, com marcador `gabarito_classificacao_ativos`, que
compõe o portão de homologação `pytest -m "gabarito or invariante or
gabarito_ataque_imediato or gabarito_classificacao_ativos"`. O mesmo cenário
aparece como teste de REGRA em `tests/regras/test_valor_liquido_realizavel.py`
(`T-126`) — os dois lugares são deliberados e devem concordar: divergência
entre eles é erro real, não duplicação.
"""

import pytest

from engine.classificacao_ativos import (
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO,
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL,
)
from engine.precisao import dinheiro
from tests.conftest import assertar_exato


@pytest.mark.gabarito_classificacao_ativos
def test_gab_nfi_12_valor_liquido_negativo() -> None:
    """`GAB-NFI-12` · `AC-94` · §14.16: `VALOR_ESTIMADO_ATIVO=100.000`,
    `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=
    5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000` (negativo, REGRA
    CANÔNICA §14.12.2 — nenhum `MAX` aplicado nesta função) e
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=0` (`MAX` zera o negativo).
    """
    valor_liquido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=True,
        SALDO_PASSIVO_VINCULADO=dinheiro(105000),
        POSSUI_CUSTO_DESMOBILIZACAO=True,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(5000),
    )
    assertar_exato(valor_liquido, dinheiro(-10000))

    disponivel = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=valor_liquido
    )
    assertar_exato(disponivel, dinheiro(0))
