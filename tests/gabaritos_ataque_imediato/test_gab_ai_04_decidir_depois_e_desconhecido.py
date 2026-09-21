"""`GAB-AI-04` — "prefiro decidir depois": desconhecido, nunca zero (`T-110`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-04`
      Cenário .......... Usuário responde "Prefiro decidir depois"
      Resultado ........ `RESERVA_MOBILIZAVEL = DESCONHECIDA`; nenhum valor da
                         reserva entra no recomendado

Âncora: `AC-73` (`US-15`), `RF-43`, `RF-46`, §13.1 Regra 3, §13.4, §13.10.

**O resultado esperado é `DESCONHECIDA`, não `0`** — e a distinção é
normativa, não estilística. A §13.1 proíbe converter o estado desconhecido
"silenciosamente em zero como informação": zero seria uma decisão que o
usuário não tomou. Por isso a asserção principal deste gabarito é sobre a
IDENTIDADE do sentinela (`is DESCONHECIDO`), não sobre igualdade numérica.

A segunda metade do enunciado — "nenhum valor da reserva entra no
recomendado" — é o encadeamento §13.1 → §13.4 → §13.5: a pendência continua
legível como `DinheiroTalvez` (`RF-41`, `Diagnostico.RESERVA_MOBILIZAVEL`,
plano R3.8), enquanto a ARITMÉTICA recebe `RESERVA_RECOMENDADA = 0` "até
decisão válida" (§13.9, `EC-26`).

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato`;
`assertar_monetario` é proibido sobre `RESERVA_MOBILIZAVEL`,
`NECESSIDADE_RESIDUAL` e `ATAQUE_IMEDIATO_RECOMENDADO` (`T-109`).
"""

from decimal import Decimal

import pytest

from engine.ataque_imediato import (
    calcular_ATAQUE_IMEDIATO_RECOMENDADO,
    derivar_RESERVA_MOBILIZAVEL,
    derivar_RESERVA_RECOMENDADA,
)
from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO
from tests.conftest import assertar_exato

# Resultado mensal SUPERAVITÁRIO: a TRAVA MODO_ESTABILIZAÇÃO da §13.4 (`< 0`)
# fica desarmada, para que o `0` da reserva recomendada abaixo seja atribuível
# **só** ao desconhecido — e não ao déficit, que é o cenário de `GAB-AI-05`.
SUPERAVIT = dinheiro(1500)


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_04_decidir_depois_e_desconhecido() -> None:
    """`GAB-AI-04` · `AC-73` · §13.10, primeira metade:
    `RESERVA_MOBILIZAVEL = DESCONHECIDA`.

    "Prefiro decidir depois de ver a análise" chega ao motor como
    `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` desconhecido — o usuário tem
    reserva (`20.000`) e não descartou usá-la (`TALVEZ`), apenas não decidiu
    o quanto. A Regra 3 da §13.1 responde antes da Regra 2 e devolve o
    sentinela.

    A asserção é de IDENTIDADE (`is DESCONHECIDO`), e não de igualdade com
    `0`: o desconhecido não é valor monetário, e é essa incomparabilidade
    que impede um consumidor de tratá-lo como número por descuido (§13.1).
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )

    assert obtido is DESCONHECIDO, (
        "GAB-AI-04 espera o sentinela DESCONHECIDO, não um valor monetário "
        f"(obtido={obtido!r})"
    )
    # "não `0`" é afirmação do próprio enunciado (§13.10) e de `AC-73` — o
    # desconhecido NUNCA é convertido silenciosamente em zero como informação.
    assert obtido != dinheiro(0), "desconhecido nunca pode ser lido como zero (§13.1)"
    assert not isinstance(obtido, Decimal), "desconhecido não é valor monetário (§13.1)"


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_04_reserva_nao_entra_no_recomendado() -> None:
    """`GAB-AI-04` · `AC-73` · §13.10, segunda metade: "nenhum valor da
    reserva entra no recomendado".

    Encadeamento completo, a partir do mesmo `DESCONHECIDO` derivado acima:

    1. `RESERVA_RECOMENDADA = 0` — §13.9/`EC-26`, "0 até decisão válida",
       mesmo com `NECESSIDADE_RESIDUAL = 30.000` disponível para cobrir e
       `RESERVA_TOTAL = 20.000` no bolso do usuário.
    2. `ATAQUE_IMEDIATO_RECOMENDADO = 12.000` — exatamente a soma dos QUATRO
       componentes não protetivos (4.000 + 3.000 + 2.000 + 3.000), sem uma
       fração sequer da reserva. Se algum valor de reserva vazasse, o
       resultado subiria acima de 12.000 (o elegível de 60.000 deixa folga
       de propósito, para que o `MIN` da §13.5 não mascare o vazamento).
    """
    RESERVA_MOBILIZAVEL = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )
    assert RESERVA_MOBILIZAVEL is DESCONHECIDO

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL=dinheiro(30000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(60000),
        CAIXA_RECOMENDADO=dinheiro(4000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(3000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(2000),
        ATIVOS_RECOMENDADOS=dinheiro(3000),
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )

    assertar_exato(obtido, dinheiro(12000))
