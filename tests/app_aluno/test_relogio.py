"""O "hoje" do app no fuso do aluno — `T-302` (`DATA_REFERENCIA`).

Achado no teste ponta a ponta: cadastro às ~22h de 30/09 (Brasília) gravou
`DATA_REFERENCIA = 2026-10-01`, porque `date.today()` lia o fuso do servidor
(UTC).
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path

from app.relogio import hoje

_RAIZ = Path(__file__).resolve().parents[2]


def test_t302_22h_de_30_09_em_brasilia_ainda_e_30_09() -> None:
    # 22h BRT = 01h UTC do dia seguinte.
    assert hoje(datetime(2026, 10, 1, 1, 0, tzinfo=UTC)) == date(2026, 9, 30)
    assert hoje(datetime(2026, 10, 1, 3, 0, tzinfo=UTC)) == date(2026, 10, 1)


def test_t302_nenhuma_data_civil_vem_do_relogio_do_servidor() -> None:
    """`date.today()` em `app/`/`persistencia/` é o defeito — o único "hoje"
    é `app/relogio.py::hoje`."""
    achados = []
    for pasta in ("app", "persistencia"):
        for arquivo in (_RAIZ / pasta).rglob("*.py"):
            for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
                if (
                    isinstance(no, ast.Call)
                    and isinstance(no.func, ast.Attribute)
                    and no.func.attr == "today"
                ):
                    achados.append(f"{arquivo.relative_to(_RAIZ)}:{no.lineno}")
    assert achados == []
