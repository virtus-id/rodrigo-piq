"""`GAB-NFI-05` — ação sem valor monetário (`T-139`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1. A §14.16 é normativa e literal: "a implementação deve reproduzir
**exatamente** estes resultados".

    `GAB-NFI-05`
      Cenário .......... Ação = solicitar proposta (sem exigência de
                         desembolso financeiro imediato)
      Resultado ........ `VALOR_ACAO_FINANCEIRA_IMEDIATA = 0`

Âncora: `AC-105` (`US-22`), `RF-61`, `RF-62`, §14.2.1.

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

from engine.gates import AcaoRequerida
from engine.precisao import dinheiro
from tests.conftest import assertar_exato


@pytest.mark.gabarito_necessidade_financeira
def test_gab_nfi_05_acao_sem_valor_monetario() -> None:
    """`GAB-NFI-05` · `AC-105` · §14.2.1: ação "solicitar proposta", sem
    exigência de desembolso financeiro imediato → `VALOR_ACAO_FINANCEIRA_
    IMEDIATA=0` exato — ação sem desembolso é sempre `0`, nunca `DESCONHECIDO`
    nem um valor inventado.
    """
    acao_sem_desembolso = AcaoRequerida(
        ACAO_ID="D-01:RENEGOCIACAO",
        DIVIDA_ID="D-01",
        TIPO_ACAO="RENEGOCIACAO",
        descricao="solicitar proposta de quitação — sem desembolso",
        gate_origem=2,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
    )

    assertar_exato(acao_sem_desembolso.VALOR_ACAO_FINANCEIRA_IMEDIATA, dinheiro(0))
