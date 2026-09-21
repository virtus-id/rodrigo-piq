"""`GAB-AI-06` — residual, reserva recomendada e recomendado (`T-111`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-06`
      Cenário .......... `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 20.000`;
                         `CAIXA_RECOMENDADO = 5.000`;
                         `INVESTIMENTOS_RECOMENDADOS = 7.000`;
                         `EXTRAORDINARIOS_RECOMENDADOS = 0`;
                         `ATIVOS_RECOMENDADOS = 0`;
                         `RESERVA_MOBILIZAVEL = 10.000`
      Resultado ........ `NECESSIDADE_RESIDUAL = 8.000`;
                         `RESERVA_RECOMENDADA = 8.000`;
                         `ATAQUE_IMEDIATO_RECOMENDADO = 20.000`

Âncora: `AC-75` (`US-16`), `RF-46`, `RF-47`, `RF-48`, §13.4, §13.5, §13.7,
§13.10.

É o único gabarito ENCADEADO da §13.10: as três funções da §13.4/§13.5 rodam
em sequência, e os três números intermediários do enunciado precisam bater —
não só o último. O encadeamento é a ordem de utilização da §13.7 (caixa →
investimentos → extraordinários → ativos → **reserva por último**), e é
justamente ele que a tabela publica: 20.000 − 12.000 = 8.000 de residual;
`MIN(10.000, 8.000) = 8.000` de reserva; 5.000 + 7.000 + 8.000 = 20.000, que
o `MIN` contra o elegível confirma em 20.000.

`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` entra por **argumento nomeado
explícito** (`RF-48`, `AC-80`): a §13.5 a define só em prosa, `OQ-29` segue
aberta com o especialista, e é o enunciado do gabarito que fornece o valor.
Nenhuma função a busca em `EstadoFinanceiro` nem em `Diagnostico`.

`RESULTADO_MENSAL_ATUAL >= 0` (do próprio enunciado de `AC-75`): a TRAVA
MODO ESTABILIZAÇÃO da §13.4 fica desarmada — armada, este gabarito daria
reserva `0` e recomendado `12.000`, que é o cenário de `GAB-AI-05`.

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato` nos três
valores; `assertar_monetario` é proibido sobre `NECESSIDADE_RESIDUAL` e
`ATAQUE_IMEDIATO_RECOMENDADO` (`T-109`).
"""

import pytest

from engine.ataque_imediato import (
    calcular_ATAQUE_IMEDIATO_RECOMENDADO,
    calcular_NECESSIDADE_RESIDUAL,
    derivar_RESERVA_RECOMENDADA,
)
from engine.precisao import dinheiro
from tests.conftest import assertar_exato

# Superávit de referência — `AC-75` enuncia `RESULTADO_MENSAL_ATUAL >= 0`.
SUPERAVIT = dinheiro(1500)


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_06_residual_e_recomendado_completo() -> None:
    """`GAB-AI-06` · `AC-75` · §13.10 — os TRÊS números do enunciado, na
    ordem em que a §13.4/§13.5 os produz.

    ```
    NECESSIDADE_RESIDUAL        = MAX(0, 20.000 − 5.000 − 7.000 − 0 − 0) = 8.000
    RESERVA_RECOMENDADA         = MIN(10.000, 8.000)                     = 8.000
    ATAQUE_IMEDIATO_RECOMENDADO = MIN(20.000, 5.000+7.000+0+0+8.000)     = 20.000
    ```

    Cada saída alimenta a etapa seguinte pelo valor obtido, não por um
    literal reescrito: se o residual saísse errado, a reserva e o recomendado
    saem errados junto, e o teste aponta a primeira asserção que quebrou.

    A reserva é o ÚLTIMO componente (§13.7, ordem 5) e entra "apenas [pela]
    necessidade residual": dos 10.000 mobilizáveis, só 8.000 são
    recomendados — os 2.000 restantes não são mobilizados só por existirem
    (REGRA CANÔNICA da §13.4).
    """
    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(5000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(7000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )
    assertar_exato(NECESSIDADE_RESIDUAL, dinheiro(8000))

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(10000),
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    assertar_exato(RESERVA_RECOMENDADA, dinheiro(8000))

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(5000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(7000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )

    assertar_exato(obtido, dinheiro(20000))
