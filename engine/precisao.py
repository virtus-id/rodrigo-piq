"""Contexto decimal único do motor e as fronteiras de precisão — G-01, G-02.

RF-12: todo cálculo interno mantém precisão decimal integral; arredondamento
existe apenas na camada de exibição. Este módulo é a ÚNICA porta de entrada
(`dinheiro`) e a ÚNICA porta de saída para exibição (`quantizar_exibicao`) de
valor monetário no motor — ver plans/motor-calculo.plan.md §4.

Nota de tipo (T-04): `Dinheiro` é importado de `engine/tipos.py`, onde é
`type Dinheiro = Decimal` — alias transparente de `Decimal`. A direção do
import é segura: `tipos.py` não importa nada deste módulo.
"""

from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from typing import Final

from engine.tipos import Dinheiro

REGRAS: Final[tuple[str, ...]] = ("G-01", "G-02")

# prec=34 == decimal128 (IEEE 754-2008). Único contexto do motor. Nunca lido
# do ambiente: é aberto via `localcontext()` na fronteira de cada operação,
# porque o contexto padrão do módulo `decimal` é thread-local e herdá-lo
# quebraria o determinismo exigido pela NFR de determinismo da spec.
CONTEXTO_MOTOR: Final[Context] = Context(prec=34, rounding=ROUND_HALF_UP)


def dinheiro(valor: str | int | Decimal) -> Dinheiro:
    """G-01: único construtor autorizado de valor monetário.

    Recusa `float` em tempo de checagem estática — a assinatura não o aceita,
    então `mypy --strict` rejeita a chamada. Recusa também em tempo de
    execução: se um `float` escapar da checagem estática (ex.: código não
    tipado, `Any`), a função detecta e levanta `TypeError` em vez de aceitar
    silenciosamente uma contaminação binária.
    """
    if isinstance(valor, float):
        raise TypeError(
            "dinheiro() recusa float — RF-12/G-01: valor monetário nunca passa "
            "por ponto flutuante binário. Use str, int ou Decimal."
        )
    if not isinstance(valor, (str, int, Decimal)):
        raise TypeError(
            f"dinheiro() recusa tipo {type(valor).__name__!r} — "
            "apenas str, int ou Decimal são aceitos."
        )
    with localcontext(CONTEXTO_MOTOR):
        return +Decimal(valor)


def quantizar_exibicao(valor: Dinheiro) -> Decimal:
    """G-01: arredondamento SÓ aqui, 2 casas, ROUND_HALF_UP.

    Nunca chamado por `engine/` — apenas por `report/` (ainda não existe
    neste slug). A função vive em `engine/precisao.py` porque é conhecimento
    do motor sobre como exibir seus próprios valores, não porque o motor a
    invoca internamente.
    """
    with localcontext(CONTEXTO_MOTOR):
        return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
