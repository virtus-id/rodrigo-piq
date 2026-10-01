"""Pergunta anterior no percurso, trilha por partes e a ficha que nasce com o
primeiro item — `T-309`, `T-310`, `T-311` (decisões do produto, 2026-10-01).

Sobre os registros REAIS e a aplicação real com repositórios de arquivo
(auxiliares de `test_ficha_repetivel.py`). A ficha de valores extraordinários
tem item a item e condicional (`B3.05B` × `B3.05BF`) — é o caso que fazia
"‹ Pergunta anterior" saltar perguntas.

REGRAS: `RF-70`, `AC-105`, `RF-100`, `AC-162`, `RF-101`, `AC-163`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.casos.progresso import PendenciaObrigatoria
from app.http.jornada import trilha_da_coleta
from collection.carga import carregar_registros
from tests.app_aluno.test_ficha_repetivel import (
    _CASO_ID,
    _cliente_real,
    _criar_em,
    _responder,
)

_ESCOPO = "RECURSO_EXTRAORDINARIO_ID"


def _par(pergunta: dict[str, Any]) -> tuple[str, str | None]:
    return pergunta["ID"], pergunta["item_id"]


def _do_item(cliente: TestClient, item_id: str) -> dict[str, Any]:
    corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta", params={"item_id": item_id}).json()
    pergunta: dict[str, Any] = corpo["pergunta"]
    return pergunta


def _anterior(cliente: TestClient, ID: str, item_id: str | None) -> tuple[str, str | None] | None:
    # Sem item, o parâmetro é OMITIDO: `item_id=""` fazia a rota tratar a
    # pergunta como de outro item e a asserção passava sem verificar nada.
    params = {"item_id": item_id} if item_id else {}
    corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta/{ID}", params=params).json()
    anterior = corpo["pergunta"]["anterior"]
    return None if anterior is None else (anterior["ID"], anterior["item_id"])


def test_t309_t311_anterior_e_a_pergunta_exibida_logo_antes_no_percurso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Percorre duas fichas, com a condicional de Férias/abono, gravando a
    ordem EXIBIDA; cada pergunta aponta como anterior a exibida logo antes.

    Reproduz o defeito: o cliente montava a ordem a partir de `/respostas`
    (registro → item, e agrupada por parte) — `B3.05B@EXT002` voltava para
    `B3.05D@EXT001` e `B3.05A@EXT002` para `B3.05A@EXT001`."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    # `T-311`: o "Sim" cria `EXT001` e a próxima é a primeira pergunta dele.
    gatilho = _responder(cliente, "B3.05", "SIM").json()
    assert gatilho["abrir_fichas"] == []
    exibidas = [("B3.05", None), _par(gatilho["proxima"]["pergunta"])]
    assert exibidas[1] == ("B3.05A", "EXT001")

    # As perguntas antes de `B3.05` estão em branco aqui, então a `proxima`
    # global seria `B1.01`; o percurso do item é o que a ficha mostra.
    for valor in ("FERIAS_ABONO", "1000", "ATE_30D"):
        ID, item = exibidas[-1]
        corpo = _responder(cliente, ID, valor, item).json()
        assert corpo["abrir_fichas"] == []  # item ainda aberto: segue nele
        assert "anterior" in corpo["proxima"]["pergunta"]
        exibidas.append(_par(_do_item(cliente, "EXT001")))
    assert [ID for ID, _ in exibidas[2:]] == ["B3.05BF", "B3.05C", "B3.05D"]

    # `T-311`: terminado o item, a lista do escopo reabre.
    fim = _responder(cliente, "B3.05D", "CONFIRMADO", "EXT001").json()
    assert fim["abrir_fichas"] == [_ESCOPO]

    segundo = _criar_em(cliente, _ESCOPO).json()["ficha"]["item_id"]
    primeira = cliente.get(f"/caso/{_CASO_ID}/pergunta", params={"item_id": segundo}).json()
    exibidas.append(_par(primeira["pergunta"]))
    _responder(cliente, "B3.05A", "13O_SALARIO", segundo)
    exibidas.append(_par(_do_item(cliente, segundo)))
    assert exibidas[-1] == ("B3.05B", segundo)

    assert _anterior(cliente, *exibidas[0]) is None
    for antes, agora in zip(exibidas, exibidas[1:], strict=False):
        assert _anterior(cliente, *agora) == antes, agora


def _percurso(*ocorrencias: tuple[str, bool]) -> tuple[tuple[PendenciaObrigatoria, bool], ...]:
    return tuple((PendenciaObrigatoria(ID=ID, item_id=None), branco) for ID, branco in ocorrencias)


def _estados(trilha: list[dict[str, object]] | None) -> list[object]:
    assert trilha is not None
    return [parte["estado"] for parte in trilha]


def test_t310_trilha_por_partes_com_o_bloco_9_no_fim_do_percurso() -> None:
    """`AC-162` — concluída, atual e próximas, do servidor. O Bloco 9 (parte 1)
    vem no fim do percurso e não tira "Seu compromisso" de concluída."""
    registros = carregar_registros().registros
    percurso = _percurso(
        ("B1.01", False),
        ("B2.01", False),
        ("B3.01", False),
        ("B3.02", True),
        ("B4.01", True),
        ("B9.02", True),
    )

    assert _estados(trilha_da_coleta(registros, percurso, 3)) == [
        "concluida",
        "concluida",
        "atual",
        "proxima",
        "proxima",
    ]
    # Voltando a uma pergunta da parte 2, a 3 (da frente) não vira concluída.
    assert _estados(trilha_da_coleta(registros, percurso, 2)) == [
        "concluida",
        "atual",
        "proxima",
        "proxima",
        "proxima",
    ]
    assert trilha_da_coleta(registros, percurso, 7) is None


def test_t310_pergunta_e_lista_de_fichas_trazem_a_trilha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    proxima = _responder(cliente, "B3.05", "SIM").json()["proxima"]["pergunta"]
    lista = cliente.get(f"/caso/{_CASO_ID}/fichas/{_ESCOPO}").json()

    for trilha in (proxima["trilha"], lista["trilha"]):
        assert [p["rotulo"] for p in trilha][2] == "O que entra e o que sai por mês"
        assert _estados(trilha)[2] == "atual"
        assert len(trilha) == 5


def test_t311_escopo_com_item_nao_cria_outro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Responder de novo o gatilho não duplica a ficha que já existe."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.03", "SIM")
    _responder(cliente, "B3.03", "SIM")

    fichas = cliente.get(f"/caso/{_CASO_ID}/fichas/RENDA_ADICIONAL_ID").json()["fichas"]
    assert [f["item_id"] for f in fichas] == ["REND001"]
