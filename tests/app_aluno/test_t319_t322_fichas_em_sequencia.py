"""Ficha curta na tela da pergunta-gatilho, obrigatoriedade no formulário,
despesas em sequência e a investigação do relato de despesas — `T-319` a
`T-322` (decisões do produto, 2026-10-01).

Sobre os registros REAIS e a aplicação real com repositórios de arquivo
(auxiliares de `test_ficha_repetivel.py`).

REGRAS: `RF-106`, `AC-168`, `RF-107`, `AC-169`, `RF-108`, `AC-170`, `AC-171`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.app_aluno.test_ficha_repetivel import (
    _CASO_ID,
    _cliente_real,
    _criar_em,
    _responder,
)

_DESPESA = "ITEM_DESPESA"
_PREENCHER_DESPESA = (
    ("B3.DF01", "500"),
    ("B3.DF02", "FIXA"),
    ("B3.DF03", "OBRIGATORIA"),
    ("B3.DF04", "CONFIRMADA"),
)


def _pergunta(cliente: TestClient, ID: str) -> dict[str, Any]:
    corpo: dict[str, Any] = cliente.get(f"/caso/{_CASO_ID}/pergunta/{ID}").json()
    pergunta: dict[str, Any] = corpo["pergunta"]
    return pergunta


def _formulario(cliente: TestClient, escopo: str, item_id: str) -> dict[str, Any]:
    corpo: dict[str, Any] = cliente.get(f"/caso/{_CASO_ID}/formulario/{escopo}/{item_id}").json()
    return corpo


def _concluir(cliente: TestClient, escopo: str, item_id: str) -> Any:
    return cliente.post(f"/caso/{_CASO_ID}/concluir/{escopo}/{item_id}")


def _ids(perguntas: list[dict[str, Any]]) -> list[str]:
    return [p["ID"] for p in perguntas]


def _checklist_de_moradia(cliente: TestClient) -> list[str]:
    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "B3.D01", "valor": ["ALUGUEL", "AGUA", "ENERGIA"]},
    )
    assert resposta.status_code == 200, resposta.text
    corpo = cliente.get(f"/caso/{_CASO_ID}/fichas/{_DESPESA}").json()
    return [ficha["item_id"] for ficha in corpo["fichas"]]


# --- T-319 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("gatilho", "valor", "escopo", "perguntas"),
    [
        ("B3.03", "SIM", "RENDA_ADICIONAL_ID", ["B3.03A", "B3.03B", "B3.03C"]),
        ("B3.05", "SIM", "RECURSO_EXTRAORDINARIO_ID", ["B3.05A", "B3.05C", "B3.05D"]),
        ("B3.05", "TALVEZ", "RECURSO_EXTRAORDINARIO_ID", ["B3.05A", "B3.05C", "B3.05D"]),
        (
            "B3.NM01",
            "SIM",
            "DESPESA_NAO_MENSAL_ID",
            ["B3.NM02A", "B3.NM02B", "B3.NM02C", "B3.NM02D"],
        ),
        ("B3.S01", "SIM", "VINCULO_ID", ["B3.S02", "B3.S03", "B3.S04", "B3.S04L"]),
        ("B3.D11", "SIM", _DESPESA, ["B3.DF01", "B3.DF02", "B3.DF03", "B3.DF04"]),
    ],
)
def test_ac168_gatilho_traz_o_formulario_do_item_novo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    gatilho: str,
    valor: str,
    escopo: str,
    perguntas: list[str],
) -> None:
    """`T-319`: a pergunta que abre ficha curta traz, pelo valor que a abre,
    as perguntas que o primeiro item exibiria — decididas no servidor com a
    mãe provisória. "Não" não abre nada."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    ficha_nova = _pergunta(cliente, gatilho)["ficha_nova"]

    assert "NAO" not in ficha_nova
    nova = ficha_nova[valor]
    assert nova["escopo"] == escopo
    assert _ids(nova["perguntas"])[: len(perguntas)] == perguntas
    assert all(p["escopo_repeticao"] == escopo for p in nova["perguntas"])
    assert all(p["valor_atual"] is None for p in nova["perguntas"])
    assert nova["pede_nome"] is (escopo == _DESPESA)


def test_ac168_com_item_ja_criado_a_pergunta_nao_traz_ficha_nova(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Escopo que já tem item segue o caminho da lista (`T-311`); dívida e
    pergunta que não abre ficha não ganham a chave."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.03", "SIM")

    assert "ficha_nova" not in _pergunta(cliente, "B3.03")
    assert "ficha_nova" not in _pergunta(cliente, "B3.04")


def test_ac168_mae_cria_o_item_e_os_campos_vao_para_ele(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Salvar: a mãe cria o item (`T-311`), a `proxima` o nomeia, os campos
    são gravados nele e a conclusão é aceita, sem próximo item."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    proxima = _responder(cliente, "B3.03", "SIM").json()["proxima"]["pergunta"]
    item_id = proxima["item_id"]
    assert (proxima["escopo_repeticao"], item_id) == ("RENDA_ADICIONAL_ID", "REND001")
    for ID, valor in (("B3.03A", "ALUGUEL"), ("B3.03B", "800"), ("B3.03C", "FIXA")):
        assert _responder(cliente, ID, valor, item_id).status_code == 200, ID

    resposta = _concluir(cliente, "RENDA_ADICIONAL_ID", item_id)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["proximo_item"] is None


# --- T-320 -----------------------------------------------------------------


def test_ac169_resposta_em_branco_nao_conta_como_respondida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reproduz o relato: "Salvar" com seleções em branco gravava `""` e a
    ficha saía "Completa". Branco não é resposta."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    item = _checklist_de_moradia(cliente)[0]
    _responder(cliente, "B3.DF01", "500", item)
    for ID in ("B3.DF02", "B3.DF03", "B3.DF04"):
        _responder(cliente, ID, "", item)

    assert _formulario(cliente, _DESPESA, item)["completa"] is False


def test_ac169_concluir_com_campo_em_branco_e_recusado_com_a_lista(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-320`: concluir recusa com `400`, a mensagem legível e as perguntas
    que faltam (com o enunciado ao aluno); "Não sei" conta como resposta."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    item = _checklist_de_moradia(cliente)[0]
    _responder(cliente, "B3.DF01", "NAO_SEI", item)
    _responder(cliente, "B3.DF02", "FIXA", item)

    recusa = _concluir(cliente, _DESPESA, item)

    assert recusa.status_code == 400
    corpo = recusa.json()
    assert [(p["ID"], p["item_id"]) for p in corpo["pendencias"]] == [
        ("B3.DF03", item),
        ("B3.DF04", item),
    ]
    assert corpo["erro"].startswith("Antes de salvar, responda nesta ficha:")
    assert "obrigatório ou não obrigatório" in corpo["erro"]

    for ID, valor in _PREENCHER_DESPESA[2:]:
        _responder(cliente, ID, valor, item)
    assert _concluir(cliente, _DESPESA, item).status_code == 200


def test_ac169_despesa_sem_nome_nao_conclui(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A despesa não listada precisa do nome antes de concluir."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    item = _responder(cliente, "B3.D11", "SIM").json()["proxima"]["pergunta"]["item_id"]
    for ID, valor in _PREENCHER_DESPESA:
        _responder(cliente, ID, valor, item)

    recusa = _concluir(cliente, _DESPESA, item)
    assert recusa.status_code == 400
    assert "Nome da despesa" in recusa.json()["erro"]

    cliente.put(f"/caso/{_CASO_ID}/fichas/{_DESPESA}/{item}", data={"nome": "Pet"})
    assert _concluir(cliente, _DESPESA, item).status_code == 200


def test_ac169_concluir_recusa_escopo_e_item_invalidos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    item = _checklist_de_moradia(cliente)[0]

    assert _concluir(cliente, "NADA", item).status_code == 400
    assert _concluir(cliente, "DIVIDA_ID", item).status_code == 404


# --- T-321 -----------------------------------------------------------------


def test_ac170_concluir_aponta_o_proximo_item_pendente_do_escopo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-321`: o próximo pendente vem do servidor — depois do atual, senão o
    primeiro pendente antes dele; `None` quando todos estão concluídos."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    primeiro, segundo, terceiro = _checklist_de_moradia(cliente)

    def preencher(item: str) -> Any:
        for ID, valor in _PREENCHER_DESPESA:
            _responder(cliente, ID, valor, item)
        resposta = _concluir(cliente, _DESPESA, item)
        assert resposta.status_code == 200, resposta.text
        return resposta.json()["proximo_item"]

    assert preencher(segundo) == terceiro
    assert preencher(terceiro) == primeiro
    assert preencher(primeiro) is None


# --- T-322 -----------------------------------------------------------------


def test_ac171_item_seguinte_e_item_novo_abrem_sem_valores_de_outro_item(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hipótese (a), lado do servidor: o formulário do item seguinte e o do
    item criado pela lista não trazem `valor_atual` de outro item, e o
    `[despesa]` do enunciado é o do próprio item."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    primeiro, segundo, _ = _checklist_de_moradia(cliente)
    for ID, valor in _PREENCHER_DESPESA:
        _responder(cliente, ID, valor, primeiro)
    novo = _criar_em(cliente, _DESPESA).json()["ficha"]["item_id"]

    for item in (segundo, novo):
        perguntas = _formulario(cliente, _DESPESA, item)["perguntas"]
        assert all(p["item_id"] == item for p in perguntas)
        assert all(p["valor_atual"] is None for p in perguntas), item
    assert _formulario(cliente, _DESPESA, segundo)["perguntas"][0]["enunciado"] == (
        "Qual é o valor mensal de Água?"
    )


@pytest.mark.parametrize(
    "escopo",
    [
        "ITEM_DESPESA",
        "RENDA_ADICIONAL_ID",
        "DESPESA_NAO_MENSAL_ID",
        "RECURSO_EXTRAORDINARIO_ID",
        "VINCULO_ID",
    ],
)
def test_ac171_formulario_de_ficha_curta_so_tem_perguntas_do_proprio_escopo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, escopo: str
) -> None:
    """Hipótese (b): nenhuma pergunta de outro escopo (ex.: `B5.A01`, "Para
    quem você deve") no formulário, nem nas complementares."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    for ID, valor in (("B3.03", "SIM"), ("B3.05", "SIM"), ("B3.NM01", "SIM"), ("B3.S01", "SIM")):
        _responder(cliente, ID, valor)
    _responder(cliente, "B5.00", "2")
    _checklist_de_moradia(cliente)
    item = cliente.get(f"/caso/{_CASO_ID}/fichas/{escopo}").json()["fichas"][0]["item_id"]

    perguntas = _formulario(cliente, escopo, item)["perguntas"]
    todas = perguntas + [
        filha
        for pergunta in perguntas
        for filhas in (pergunta.get("complementares") or {}).values()
        for filha in filhas
    ]
    assert todas
    assert {p["escopo_repeticao"] for p in todas} == {escopo}
    assert not any(p["ID"].startswith("B5.") for p in todas)
