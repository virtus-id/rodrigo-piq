"""`GAB-NFI-03` — Gate 3 pendente (`T-139`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1. A §14.16 é normativa e literal: "a implementação deve reproduzir
**exatamente** estes resultados".

    `GAB-NFI-03`
      Cenário .......... `Gate3 = PENDENTE`; Gate 1 resolvido;
                         `VALOR_RELEVANTE_PARA_QUITACAO` positivo
      Resultado ........ `NECESSIDADE_IMEDIATA_DIVIDA = 0`

Âncora: `AC-103` (`US-22`), `RF-64`, §14.1.1 (ramo 2).

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

from engine.gates import NECESSIDADE_IMEDIATA_DIVIDA, AcaoRequerida
from engine.precisao import dinheiro
from engine.tipos import DIVIDA_STATUS_ESTRATEGICO, GATE_PENDENTE
from tests.conftest import assertar_exato


@pytest.mark.gabarito_necessidade_financeira
def test_gab_nfi_03_gate3_pendente() -> None:
    """`GAB-NFI-03` · `AC-103` · §14.1.1: `Gate3=PENDENTE`, Gate 1 resolvido,
    `VALOR_RELEVANTE_PARA_QUITACAO` positivo → `NECESSIDADE_IMEDIATA_DIVIDA=0`
    exato — Gate 3 pendente vence sobre o status estratégico e sobre
    qualquer ação financeira imediata, mesmo com Gate 1 já resolvido
    (ramo 2, nunca alcança ramo 3 ou 4).
    """
    acao_ignorada = AcaoRequerida(
        ACAO_ID="D-01:RENEGOCIACAO",
        DIVIDA_ID="D-01",
        TIPO_ACAO="RENEGOCIACAO",
        descricao="ação de teste, ignorada pelo ramo 2",
        gate_origem=3,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(9999),
    )

    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.TRANSFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE,
        acao_financeira_imediata_executavel=acao_ignorada,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(30000),
    )

    assertar_exato(resultado, dinheiro(0))
