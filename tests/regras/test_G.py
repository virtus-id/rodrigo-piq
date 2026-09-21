"""Testes da família G — precisão e arredondamento de exibição.

RF-12, AC-40: precisão decimal integral em todo cálculo interno, arredondamento
apenas na camada de exibição (`G-01`), ROUND_HALF_UP.
"""

from decimal import Decimal

import pytest

from engine.precisao import quantizar_exibicao
from tests.conftest import assertar_exato


@pytest.mark.regra
def test_G01_arredondamento_half_up() -> None:
    """AC-40: 10,125 exibido em 2 casas resulta em 10,13 (ROUND_HALF_UP).

    Comparação exata do próprio comportamento de arredondamento — não é valor
    monetário acumulado, então `assertar_exato` é o helper correto (tolerância
    ± 0,05 mascararia justamente o comportamento que este teste prova).
    """
    obtido = quantizar_exibicao(Decimal("10.125"))
    assertar_exato(obtido, Decimal("10.13"))
