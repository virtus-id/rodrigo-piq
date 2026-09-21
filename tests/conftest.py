"""Helpers de asserção compartilhados pela suíte — duas tolerâncias, nunca uma só.

RF-12, AC-40, NFR "Tolerância de homologação" (specs/motor-calculo.spec.md §5):
`± R$ 0,05` existe exclusivamente para valor monetário ACUMULADO. Todo o resto
— método recomendado, ordem, gates, status, número de meses, primeira vitória,
`D*`, aplicação de resíduo, gatilho de recálculo e `NAO_APLICAVEL` vs
`PROVISORIO` — usa tolerância zero. Os dois helpers vivem em funções distintas
(plans/motor-calculo.plan.md §9) justamente para que a tolerância errada não
vaze por engano: `assertar_monetario` nunca é aceitável fora de dinheiro
acumulado, e `test_uso_de_tolerancia` (tests/estatica/) varre a AST da suíte
para impedir esse uso indevido.
"""

from decimal import Decimal
from typing import Final

from engine.tipos import Dinheiro

TOLERANCIA_MONETARIA: Final = Decimal("0.05")  # G-02


def assertar_monetario(obtido: Dinheiro, esperado: Dinheiro) -> None:
    """± R$ 0,05. USO EXCLUSIVO em valor monetário ACUMULADO.

    Nunca use este helper para método recomendado, ordem, gates, status,
    número de meses, primeira vitória, D*, aplicação de resíduo, gatilho de
    recálculo ou NAO_APLICAVEL vs PROVISORIO — para esses, `assertar_exato`.
    """
    diferenca = abs(obtido - esperado)
    assert diferenca <= TOLERANCIA_MONETARIA, (
        f"valor monetário fora da tolerância de homologação (± {TOLERANCIA_MONETARIA}): "
        f"obtido={obtido!r} esperado={esperado!r} diferenca={diferenca!r}"
    )


def assertar_exato(obtido: object, esperado: object) -> None:
    """Tolerância ZERO. Obrigatório para: METODO_RECOMENDADO_PIQ, ORDEM_QUITACAO,
    gates, DIVIDA_STATUS_ESTRATEGICO, STATUS_METODO, ORDEM_STATUS, número de
    meses, MESES_PRIMEIRA_VITORIA, D*, aplicação de resíduo, gatilho de
    recálculo, e NAO_APLICAVEL vs PROVISORIO.
    """
    assert obtido == esperado, (
        f"comparação exata falhou (tolerância zero): obtido={obtido!r} esperado={esperado!r}"
    )
