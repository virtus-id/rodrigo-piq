"""`GAB-AI-03` — sem disposição de uso da reserva (`T-110`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-03`
      Cenário .......... `DISPOSICAO_USO_RESERVA = NAO`
      Resultado ........ `RESERVA_MOBILIZAVEL = 0`

Âncora: `AC-72` (`US-15`), `RF-43`, §13.1 Regra 1, §13.10. `AC-72` é
explícito quanto ao alcance: o resultado é `0` "independentemente de
`RESERVA_TOTAL` e do valor informado pelo usuário" — por isso o cenário é
exercitado sobre uma varredura de totais e valores informados, e não sobre um
par só.

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato`;
`assertar_monetario` é proibido sobre `RESERVA_MOBILIZAVEL` (`T-109`).
"""

import pytest

from engine.ataque_imediato import derivar_RESERVA_MOBILIZAVEL
from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE
from engine.precisao import dinheiro
from engine.tipos import DinheiroTalvez
from tests.conftest import assertar_exato


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_03_sem_disposicao_de_uso() -> None:
    """`GAB-AI-03` · `AC-72` · §13.10: `DISPOSICAO_USO_RESERVA = NAO` →
    `RESERVA_MOBILIZAVEL = 0`.

    A Regra 1 da §13.1 é a primeira guarda e vence a Regra 2: quem não está
    disposto a usar a reserva não mobiliza nada, por mais alto que seja o
    total. Aqui o total é `20.000` e o informado `20.000` — se a Regra 2
    fosse avaliada antes, o `MIN` devolveria 20.000.
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(20000),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.gabarito_ataque_imediato
@pytest.mark.parametrize(
    ("RESERVA_TOTAL", "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO"),
    [
        (dinheiro(20000), dinheiro(5000)),
        (dinheiro(20000), dinheiro(30000)),
        (dinheiro(0), dinheiro(0)),
        (dinheiro(999999), dinheiro("0.01")),
    ],
)
def test_gab_ai_03_zero_independe_do_total_e_do_informado(
    RESERVA_TOTAL: DinheiroTalvez,
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez,
) -> None:
    """`AC-72` na sua forma literal: com `DISPOSICAO_USO_RESERVA = NAO` o
    resultado é exatamente `0` "independentemente de `RESERVA_TOTAL` e do
    valor informado pelo usuário".

    As quatro combinações incluem os pares de `GAB-AI-01` e `GAB-AI-02`: os
    mesmos números que produziriam 5.000 e 20.000 com disposição de uso
    produzem `0` sem ela. É a prova de que a Regra 1 ignora o informado —
    não o soma, não o pondera (§13.1, `EC-23`).
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        RESERVA_TOTAL=RESERVA_TOTAL,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO,
    )

    assertar_exato(obtido, dinheiro(0))
