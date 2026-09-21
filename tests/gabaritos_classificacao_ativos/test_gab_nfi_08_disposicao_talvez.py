"""`GAB-NFI-08` — investimento com disposição TALVEZ (`T-129`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1 (Fechamento Canônico — Necessidade Financeira Imediata e
Classificação de Ativos, congelado em 2026-09-09).

    `GAB-NFI-08`
      Cenário .......... `DISPOSICAO_USO_INVESTIMENTO=TALVEZ`, investimento
                         efetivamente resgatável
      Resultado ........ `MOBILIZACAO_POSSIVEL`

Âncora: `AC-90` (`US-19`), `RF-53`, §14.3.1 Regra 3, §14.16.

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

from engine.classificacao_ativos import classificar_investimento
from engine.estado import DISPOSICAO_USO_INVESTIMENTO, LIQUIDEZ_INVESTIMENTOS, ItemInvestimento
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO
from tests.conftest import assertar_exato


@pytest.mark.gabarito_classificacao_ativos
def test_gab_nfi_08_disposicao_talvez() -> None:
    """`GAB-NFI-08` · `AC-90` · §14.16: `DISPOSICAO_USO_INVESTIMENTO=TALVEZ`,
    investimento efetivamente resgatável (liquidez não `BLOQUEADO`, a
    Regra 1 não dispara) → `MOBILIZACAO_POSSIVEL` (Regra 3, §14.3.1).
    """
    item = ItemInvestimento(
        ITEM_ID="INV-GAB-NFI-08",
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(10000),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D7,
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.TALVEZ,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(10000),
        TEM_CUSTO_CONHECIDO=False,
        SEM_CUSTO_PERDA_RELEVANTE=True,
    )

    obtido = classificar_investimento(item)

    assertar_exato(obtido, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL)
