"""`GAB-AI-07` — a necessidade elegível é TETO, não parcela (`T-111`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-07`
      Cenário .......... `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 10.000`;
                         recursos recomendáveis totais `= 25.000`
      Resultado ........ `ATAQUE_IMEDIATO_RECOMENDADO = 10.000` (**não**
                         25.000)

Âncora: `AC-76` (`US-16`), `RF-47`, `RF-48`, §13.5, §13.10.

"Nunca recomendar recurso sem destinação financeira elegível" (§13.5): ter
25.000 mobilizáveis não é razão para mobilizar 25.000. O elegível LIMITA a
soma dos cinco componentes recomendados — jamais entra nela.

`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` entra por **argumento nomeado
explícito** (`RF-48`, `AC-80`). É o teto de toda a §13 e a variável de maior
risco desta rodada: a §13.5 a define apenas em prosa e `OQ-29` segue aberta —
é o enunciado deste gabarito que fornece os 10.000, e derivá-la no motor
seria inventar metodologia.

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato`;
`assertar_monetario` é proibido sobre `ATAQUE_IMEDIATO_RECOMENDADO`
(`T-109`).
"""

import pytest

from engine.ataque_imediato import calcular_ATAQUE_IMEDIATO_RECOMENDADO
from engine.precisao import dinheiro
from tests.conftest import assertar_exato


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_07_teto_da_necessidade_elegivel() -> None:
    """`GAB-AI-07` · `AC-76` · §13.10: elegível `10.000` contra `25.000` de
    recursos recomendáveis totais → `ATAQUE_IMEDIATO_RECOMENDADO = 10.000`,
    **não** `25.000`.

    Os 25.000 do enunciado são distribuídos pelos CINCO componentes da §13.3
    em potências de dois (1.000 + 2.000 + 4.000 + 8.000 + 10.000 = 25.000)
    para que a soma seja auditável parcela a parcela: nenhuma combinação
    própria desses cinco valores dá 10.000, então o resultado só pode vir do
    `MIN` contra o elegível — nunca de uma parcela esquecida.

    Uma implementação que somasse o elegível em vez de limitar por ele daria
    35.000; uma que ignorasse o teto daria 25.000.
    """
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(10000),
        CAIXA_RECOMENDADO=dinheiro(1000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(2000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(4000),
        ATIVOS_RECOMENDADOS=dinheiro(8000),
        RESERVA_RECOMENDADA=dinheiro(10000),
    )

    assertar_exato(obtido, dinheiro(10000))
    # A negativa que o próprio enunciado publica entre parênteses.
    assert obtido != dinheiro(25000), (
        "o elegível é TETO, não parcela: recurso sem destinação elegível não é "
        "recomendado (§13.5, AC-76)"
    )
