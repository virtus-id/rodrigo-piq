"""`AC-180` — `B3.01` diz o que informar (`RF-117`, `T-338`).

O motor desconta as parcelas das dívidas da renda; quem informa o que cai na
conta (depois dos consignados) faz cada consignado ser contado duas vezes. O
enunciado precisa dizer, com todas as letras, que o valor é ANTES de
empréstimos e consignados.
"""

from __future__ import annotations

from collection.carga import carregar_registros

_ENUNCIADO = (
    "Quanto você recebe por mês, em média, depois do imposto de renda e da "
    "previdência, mas antes de empréstimos e consignados? (Não desconte "
    "parcelas de empréstimo nem consignado: você cadastra essas dívidas mais "
    "adiante. Plano de saúde, sindicato e outros descontos de folha entram "
    "nas despesas.)"
)


def test_ac180_o_enunciado_de_b3_01_e_exatamente_o_aprovado() -> None:
    registro = next(r for r in carregar_registros().registros if r.ID == "B3.01")

    assert registro.enunciado == _ENUNCIADO


def test_ac180_a_spec_canonica_traz_o_mesmo_texto() -> None:
    """A fonte da transcrição (`AC-36`): spec e questionário não divergem."""
    from pathlib import Path

    spec = Path("specs/piq-app-spec.md").read_text(encoding="utf-8")

    assert f"> {_ENUNCIADO}" in spec
