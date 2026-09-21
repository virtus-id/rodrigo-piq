"""Determinismo puro de `_compor_ACAO_ID` como propriedade estrutural —
RF-28, AC-48, OQ-21, OQ-22 · plano §R2.9, T-81.

`_compor_ACAO_ID` (`engine/gates.py`, T-80) é a função privada que compõe
`ACAO_ID` só a partir de `(DIVIDA_ID, TIPO_ACAO)`, sem contador, sem UUID,
sem estado externo (OQ-21, respondida). Este módulo prova o contrato de
determinismo por PROPRIEDADE — mesmos insumos sempre produzem o mesmo
`ACAO_ID`, insumos diferentes produzem `ACAO_ID` diferente — em vez de só
por exemplo isolado, e complementa `tests/regras/test_gates.py`, que cobre
a estabilidade entre "snapshots" simulados (`AC-48`, `OQ-22`).

Mesmo padrão de acesso a função privada de módulo já usado na suíte
(`tests/regras/test_motor.py`: `import engine.motor as motor_mod`, depois
`motor_mod._algo`), em vez de importar o nome underscore diretamente.
"""

from __future__ import annotations

import pytest

import engine.gates as gates_mod
from tests.conftest import assertar_exato

pytestmark = pytest.mark.regra


def test_acao_id_determinismo_puro() -> None:
    """RF-28 · OQ-21 — mesmos insumos sempre produzem o mesmo `ACAO_ID`
    (determinismo puro); insumos diferentes (dívida OU tipo diferente)
    produzem `ACAO_ID` diferente. Tolerância zero — `ACAO_ID` não é valor
    monetário, todas as comparações usam `assertar_exato`."""
    # Mesmos insumos, duas chamadas independentes — igualdade exata.
    id_a1 = gates_mod._compor_ACAO_ID(divida_id="D001", tipo_acao="INFORMACAO")
    id_a2 = gates_mod._compor_ACAO_ID(divida_id="D001", tipo_acao="INFORMACAO")
    assertar_exato(id_a1, id_a2)

    # Dívida diferente, mesmo TIPO_ACAO — ACAO_ID diferente (assertar_exato
    # não tem variante de desigualdade; a comparação abaixo é sobre o mesmo
    # valor exato — tolerância zero — só que a expectativa é de diferença).
    id_divida_diferente = gates_mod._compor_ACAO_ID(divida_id="D002", tipo_acao="INFORMACAO")
    assert id_a1 != id_divida_diferente, (
        f"esperava ACAO_ID diferente para DIVIDA_ID diferente, obteve o mesmo: {id_a1!r}"
    )

    # Mesma dívida, TIPO_ACAO diferente — ACAO_ID diferente.
    id_tipo_diferente = gates_mod._compor_ACAO_ID(divida_id="D001", tipo_acao="RENEGOCIACAO")
    assert id_a1 != id_tipo_diferente, (
        f"esperava ACAO_ID diferente para TIPO_ACAO diferente, obteve o mesmo: {id_a1!r}"
    )

    # Ação de economia (DIVIDA_ID=None) — mesma propriedade, insumo isolado.
    id_economia_1 = gates_mod._compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")
    id_economia_2 = gates_mod._compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")
    assertar_exato(id_economia_1, id_economia_2)
    assert id_economia_1 != id_a1, (
        "ACAO_ID da ação de economia coincidiu com o de uma ação ligada a dívida "
        f"(colisão estrutural indesejada): {id_economia_1!r}"
    )
