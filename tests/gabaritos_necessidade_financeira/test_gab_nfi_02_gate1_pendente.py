"""`GAB-NFI-02` — Gate 1 pendente (`T-139`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1. A §14.16 é normativa e literal: "a implementação deve reproduzir
**exatamente** estes resultados".

    `GAB-NFI-02`
      Cenário .......... `VALOR_RELEVANTE_PARA_QUITACAO = 20.000`;
                         `Gate1 = PENDENTE`
      Resultado ........ `NECESSIDADE_IMEDIATA_DIVIDA = 0`

Âncora: `AC-102` (`US-22`), `RF-64`, §14.1.1 (ramo 1).

**Tolerância ZERO** (spec §5, NFR "Tolerância dos `GAB-NFI`"): `assertar_exato`
em toda asserção monetária.

Este é o gabarito FORMAL, com marcador `gabarito_necessidade_financeira`, que
compõe o portão de homologação `pytest -m "gabarito or invariante or
gabarito_ataque_imediato or gabarito_classificacao_ativos or
gabarito_necessidade_financeira"`. O mesmo número aparece como teste de REGRA
em `tests/regras/test_necessidade_imediata.py` (`T-137`) — os dois lugares
são deliberados e devem concordar: divergência entre eles é erro real, não
duplicação.
"""

import pytest

from engine.gates import NECESSIDADE_IMEDIATA_DIVIDA
from engine.precisao import dinheiro
from engine.tipos import DIVIDA_STATUS_ESTRATEGICO, GATE_PENDENTE
from tests.conftest import assertar_exato


@pytest.mark.gabarito_necessidade_financeira
def test_gab_nfi_02_gate1_pendente() -> None:
    """`GAB-NFI-02` · `AC-102` · §14.1.1: `VALOR_RELEVANTE_PARA_QUITACAO=
    20.000` com `Gate1=PENDENTE` → `NECESSIDADE_IMEDIATA_DIVIDA=0` exato —
    Gate 1 pendente vence antes de qualquer outra condição ser avaliada
    (ramo 1).
    """
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(20000),
    )

    assertar_exato(resultado, dinheiro(0))
