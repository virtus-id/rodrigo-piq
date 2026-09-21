"""`GAB-AI-01` — valor aceito abaixo do total (`T-110`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1 (congelado em 2026-09-07). A §13.10 é normativa e literal: "a
implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-01`
      Cenário .......... `RESERVA_TOTAL = 20.000`; usuário aceita analisar
                         `5.000`
      Resultado ........ `RESERVA_MOBILIZAVEL = 5.000`

Âncora: `AC-70` (`US-15`), `RF-43`, §13.1 Regra 2, §13.10.

**Tolerância ZERO** (spec §5, NFR "Tolerância dos `GAB-AI`", `OQ-34`
respondida): `assertar_exato` em toda asserção monetária.
`assertar_monetario` (± R$ 0,05) é **proibido** sobre `RESERVA_MOBILIZAVEL`,
que está em `SIMBOLOS_TOLERANCIA_ZERO` desde `T-109` — o lint
`tests/estatica/test_uso_de_tolerancia.py` pega o uso indevido.

Este é o gabarito FORMAL, com marcador `gabarito_ataque_imediato`, que compõe
o portão de homologação `pytest -m "gabarito or invariante or
gabarito_ataque_imediato"`. O mesmo número aparece como teste de REGRA em
`tests/regras/test_reserva_mobilizavel.py` (`T-102`) — os dois lugares são
deliberados e devem concordar: divergência entre eles é erro real, não
duplicação.
"""

import pytest

from engine.ataque_imediato import derivar_RESERVA_MOBILIZAVEL
from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE
from engine.precisao import dinheiro
from tests.conftest import assertar_exato


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_01_valor_aceito_abaixo_do_total() -> None:
    """`GAB-AI-01` · `AC-70` · §13.10: `RESERVA_TOTAL = 20.000` e o usuário
    aceita submeter `5.000` à análise → `RESERVA_MOBILIZAVEL = 5.000`.

    O `MIN` da Regra 2 (§13.1) devolve o valor informado, que é o menor dos
    dois. `RESERVA_MOBILIZAVEL` "não é percentual calculado pelo motor" — é o
    máximo que o usuário aceita, e o motor "apenas valida e limita" (§13.1).
    Nem 20.000 (que ignoraria a decisão do usuário) nem qualquer fração de
    20.000 (que seria a fórmula proibida pela TRAVA CANÔNICA da §13.1,
    `RF-49`/`AC-81`).
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(5000),
    )

    assertar_exato(obtido, dinheiro(5000))
