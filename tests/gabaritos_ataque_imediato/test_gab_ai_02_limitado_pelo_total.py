"""`GAB-AI-02` — informado acima do total, limitado pelo total (`T-110`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-02`
      Cenário .......... `RESERVA_TOTAL = 20.000`; usuário informa máximo de
                         `30.000`
      Resultado ........ `RESERVA_MOBILIZAVEL = 20.000` (limitado pelo total)

Âncora: `AC-71` (`US-15`), `RF-43`, §13.1 Regra 2, §13.10.

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato`;
`assertar_monetario` é proibido sobre `RESERVA_MOBILIZAVEL` (`T-109`).

Nota de nomenclatura (`OQ-24`, respondida em 2026-09-07, `RF-42`/`AC-69`): os
dois números deste gabarito têm nomes distintos e não intercambiáveis — a
resposta crua do usuário é `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (30.000)
e `RESERVA_MOBILIZAVEL` é o valor DERIVADO (20.000). É exatamente aqui que
confundi-los produziria 30.000.
"""

import pytest

from engine.ataque_imediato import derivar_RESERVA_MOBILIZAVEL
from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE
from engine.precisao import dinheiro
from tests.conftest import assertar_exato


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_02_limitado_pelo_total() -> None:
    """`GAB-AI-02` · `AC-71` · §13.10: `RESERVA_TOTAL = 20.000` e o usuário
    informa máximo de `30.000` → `RESERVA_MOBILIZAVEL = 20.000`, limitado
    pelo total — **nunca `30.000`**.

    O `MIN` da Regra 2 (§13.1) corta pelo total: ninguém mobiliza mais reserva
    do que tem, e o papel do motor é "apenas validar e limitar". Uma
    implementação que devolvesse o informado, ou que somasse os dois, daria
    30.000 ou 50.000.
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(30000),
    )

    assertar_exato(obtido, dinheiro(20000))
    # A afirmação negativa que o enunciado faz explicitamente ("limitado pelo
    # total"): o valor informado não vaza para a saída.
    assert obtido != dinheiro(30000), "o informado nunca ultrapassa o total (§13.1, AC-71)"
