"""`GAB-NFI-04` — oportunidade Gate 4 (`T-139`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1. A §14.16 é normativa e literal: "a implementação deve reproduzir
**exatamente** estes resultados".

    `GAB-NFI-04`
      Cenário .......... `VALOR_ACAO_FINANCEIRA_IMEDIATA = 8.000`;
                         mesma dívida com
                         `VALOR_RELEVANTE_PARA_QUITACAO = 15.000`
      Resultado ........ `NECESSIDADE_IMEDIATA_DIVIDA = 8.000`
                         (não somar `8.000 + 15.000`)

Âncora: `AC-104` (`US-23`), `RF-64`, `RF-65`, §14.1.1 (ramo 3) — trava de
dupla contagem.

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
def test_gab_nfi_04_oportunidade_gate4() -> None:
    """`GAB-NFI-04` · `AC-104` · `RF-65` · §14.1.1: ação de Gate 2/4
    executável com `VALOR_ACAO_FINANCEIRA_IMEDIATA=8.000`, mesma dívida com
    `VALOR_RELEVANTE_PARA_QUITACAO=15.000` → `NECESSIDADE_IMEDIATA_DIVIDA=
    8.000` exato, **nunca** `23.000` — a trava de dupla contagem impede
    somar os dois valores da mesma dívida; o ramo 3 vence e a cadeia
    `if`/`elif` nunca alcança o ramo 4.
    """
    acao_gate4 = AcaoRequerida(
        ACAO_ID="D-01:OPORTUNIDADE",
        DIVIDA_ID="D-01",
        TIPO_ACAO="RENEGOCIACAO",
        descricao="oportunidade de Gate 4 executável agora",
        gate_origem=2,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(8000),
    )

    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=acao_gate4,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )

    assertar_exato(resultado, dinheiro(8000))
    assert resultado != dinheiro(23000), (
        "dupla contagem: NECESSIDADE_IMEDIATA_DIVIDA nunca soma "
        "VALOR_ACAO_FINANCEIRA_IMEDIATA com VALOR_RELEVANTE_PARA_QUITACAO"
    )
