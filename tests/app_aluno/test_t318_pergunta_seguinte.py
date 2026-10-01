"""Pergunta seguinte no percurso — `T-318` (decisão do produto, 2026-10-01).

Quem voltou com "‹ Pergunta anterior" avança sem responder de novo. O
servidor nomeia `seguinte` com a MESMA varredura de `anterior` (`T-309`).

REGRAS: `RF-70`, `AC-105`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.casos.progresso import PendenciaObrigatoria
from app.http.jornada import seguinte_no_percurso
from tests.app_aluno.test_ficha_repetivel import _CASO_ID, _cliente_real, _responder


def _pergunta(cliente: TestClient, ID: str, item_id: str | None) -> dict[str, Any]:
    parametros = {"item_id": item_id} if item_id else {}
    corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta/{ID}", params=parametros).json()
    pergunta: dict[str, Any] = corpo["pergunta"]
    return pergunta


def _par(destino: dict[str, Any] | None) -> tuple[str, str | None] | None:
    return None if destino is None else (destino["ID"], destino["item_id"])


def test_t318_seguinte_so_depois_de_uma_respondida() -> None:
    percurso = tuple(
        (PendenciaObrigatoria(ID=ID, item_id=item), branco)
        for ID, item, branco in (
            ("B3.05", None, False),
            ("B3.05A", "EXT001", False),
            ("B3.05B", "EXT001", True),
        )
    )
    assert seguinte_no_percurso(percurso, "B3.05", None) == {
        "ID": "B3.05A",
        "item_id": "EXT001",
    }
    assert seguinte_no_percurso(percurso, "B3.05A", "EXT001") == {
        "ID": "B3.05B",
        "item_id": "EXT001",
    }
    # Na fronteira o aluno precisa responder; fora do percurso, nada.
    assert seguinte_no_percurso(percurso, "B3.05B", "EXT001") is None
    assert seguinte_no_percurso(percurso, "B3.05A", "EXT002") is None


def test_t318_voltar_e_avancar_chega_a_pergunta_certa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Responde a ficha `EXT001` (Férias/abono: `B3.05A`, `B3.05BF`, `B3.05C`)
    até a fronteira `B3.05D`, volta três com `anterior` e
    avança um com `seguinte`: chega à pergunta logo depois, com o item."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    proxima = _responder(cliente, "B3.05", "SIM").json()["proxima"]["pergunta"]
    for valor in ("FERIAS_ABONO", "1000", "ATE_30D"):
        corpo = _responder(cliente, proxima["ID"], valor, "EXT001").json()
        assert "seguinte" in corpo["proxima"]["pergunta"]  # a do `POST` também traz
        # A `proxima` global seria `B1.01` (em branco); seguimos no item.
        proxima = cliente.get(
            f"/caso/{_CASO_ID}/pergunta", params={"item_id": "EXT001"}
        ).json()["pergunta"]
    fronteira = _pergunta(cliente, "B3.05D", "EXT001")
    assert fronteira["seguinte"] is None

    atual = fronteira
    for _ in range(3):
        anterior = _par(atual["anterior"])
        assert anterior is not None
        atual = _pergunta(cliente, *anterior)
    assert _par(atual) == ("B3.05A", "EXT001")
    assert _par(atual["seguinte"]) == ("B3.05BF", "EXT001")
    # Da última respondida, a seguinte é a pendente; e do gatilho entra no item.
    assert _par(_pergunta(cliente, "B3.05C", "EXT001")["seguinte"]) == ("B3.05D", "EXT001")
    assert _par(_pergunta(cliente, "B3.05", None)["seguinte"]) == ("B3.05A", "EXT001")
