"""Ficha curta em uma tela, "Outro" com descrição, despesa não listada e
progresso por item — `T-314` a `T-317` (decisões do produto, 2026-10-01).

Sobre os registros REAIS e a aplicação real com repositórios de arquivo
(auxiliares de `test_ficha_repetivel.py`).

REGRAS: `RF-102`, `AC-164`, `RF-103`, `AC-165`, `RF-104`, `AC-166`, `RF-105`,
`AC-167`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from collection.carga import carregar_registros
from tests.app_aluno.test_ficha_repetivel import (
    _CASO_ID,
    _cliente_real,
    _criar_em,
    _responder,
)

_EXT = "RECURSO_EXTRAORDINARIO_ID"


def _formulario(cliente: TestClient, escopo: str, item_id: str) -> dict[str, Any]:
    resposta = cliente.get(f"/caso/{_CASO_ID}/formulario/{escopo}/{item_id}")
    assert resposta.status_code == 200, resposta.text
    corpo: dict[str, Any] = resposta.json()
    return corpo


def _ids(perguntas: list[dict[str, Any]]) -> list[str]:
    return [p["ID"] for p in perguntas]


def test_ac164_formulario_traz_as_perguntas_exibiveis_do_item_com_as_complementares(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-314`: as perguntas do item numa lista só; as que uma opção abre vêm
    em `complementares` da mãe (não na lista), decididas no servidor."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "SIM")

    corpo = _formulario(cliente, _EXT, "EXT001")

    assert corpo["item_id"] == "EXT001"
    assert corpo["completa"] is False
    assert _ids(corpo["perguntas"]) == ["B3.05A", "B3.05C", "B3.05D"]
    assert all(p["item_id"] == "EXT001" for p in corpo["perguntas"])
    tipo = corpo["perguntas"][0]
    assert _ids(tipo["complementares"]["OUTRO"]) == ["B3.05AO", "B3.05B"]
    assert _ids(tipo["complementares"]["FERIAS_ABONO"]) == ["B3.05BF"]
    assert _ids(tipo["complementares"]["13O_SALARIO"]) == ["B3.05B"]

    for ID, valor in (
        ("B3.05A", "OUTRO"),
        ("B3.05AO", "Venda do carro"),
        ("B3.05B", "1000"),
        ("B3.05C", "ATE_30D"),
        ("B3.05D", "CONFIRMADO"),
    ):
        assert _responder(cliente, ID, valor, "EXT001").status_code == 200, ID

    depois = _formulario(cliente, _EXT, "EXT001")
    assert depois["completa"] is True
    assert depois["perguntas"][0]["valor_atual"] == "OUTRO"


def test_ac164_escopo_invalido_e_item_de_outro_escopo_sao_recusados(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "SIM")

    assert cliente.get(f"/caso/{_CASO_ID}/formulario/NADA/EXT001").status_code == 400
    assert (
        cliente.get(f"/caso/{_CASO_ID}/formulario/DIVIDA_ID/EXT001").status_code == 404
    )
    assert cliente.get(f"/caso/{_CASO_ID}/formulario/{_EXT}/EXT999").status_code == 404


def test_ac165_descricao_de_outro_so_abre_com_outro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-315`: `DESCRICAO_RECURSO_EXTRAORDINARIO` só é aceita com o tipo
    "Outro" — a condição é do registro, avaliada no servidor."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "SIM")
    _responder(cliente, "B3.05A", "13O_SALARIO", "EXT001")

    assert _responder(cliente, "B3.05AO", "Algo", "EXT001").status_code == 400

    _responder(cliente, "B3.05A", "OUTRO", "EXT001")
    assert _responder(cliente, "B3.05AO", "Venda do carro", "EXT001").status_code == 200


@pytest.mark.parametrize(
    ("mae", "opcao", "descricao"),
    [
        ("B3.03A", "OUTRA_RENDA_RECORRENTE", "B3.03AO"),
        ("B3.05A", "OUTRO", "B3.05AO"),
        ("B3.NM02A", "OUTRA", "B3.NM02AO"),
        ("B3.NM02C", "OUTRA", "B3.NM02CO"),
        ("B3.S06A", "OUTRA_DO_REGIME", "B3.S06AO"),
    ],
)
def test_ac165_outro_das_fichas_curtas_abre_a_descricao_na_mesma_tela(
    mae: str, opcao: str, descricao: str
) -> None:
    """`T-315`: a descrição é texto curto, no mesmo escopo, logo depois da mãe
    e aberta só pelo "Outro" — o que faz dela uma complementar (`T-307`)."""
    registros = carregar_registros().registros
    por_id = {r.ID: r for r in registros}
    ordem = [r.ID for r in registros]
    filha, da_mae = por_id[descricao], por_id[mae]

    assert ordem.index(descricao) == ordem.index(mae) + 1
    assert filha.tipo.value == "TEXTO_CURTO"
    assert filha.escopo_repeticao is da_mae.escopo_repeticao
    assert opcao in {o.valor_interno for o in da_mae.opcoes}
    assert opcao in repr(filha.condicao_exibicao)


def test_ac166_despesa_nao_listada_sim_abre_o_item_novo_direto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-316`: "Sim" em `B3.D11` leva à primeira pergunta do item novo (nome
    + `B3.DF01`–`DF04` no formulário), sem passar pela lista."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    corpo = _responder(cliente, "B3.D11", "SIM").json()

    assert corpo["abrir_fichas"] == []
    proxima = corpo["proxima"]["pergunta"]
    assert (proxima["ID"], proxima["escopo_repeticao"]) == ("B3.DF01", "ITEM_DESPESA")
    formulario = _formulario(cliente, "ITEM_DESPESA", proxima["item_id"])
    assert formulario["pede_nome"] is True
    assert formulario["rotulo"] is None
    assert _ids(formulario["perguntas"]) == ["B3.DF01", "B3.DF02", "B3.DF03", "B3.DF04"]


def test_ac167_posicao_do_item_e_itens_concluidos_vem_do_servidor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-317`: "Valor extraordinário 2 de 2" e a barra por itens concluídos."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "SIM")
    for ID, valor in (
        ("B3.05A", "13O_SALARIO"),
        ("B3.05B", "1000"),
        ("B3.05C", "ATE_30D"),
        ("B3.05D", "CONFIRMADO"),
    ):
        _responder(cliente, ID, valor, "EXT001")
    segundo = _criar_em(cliente, _EXT).json()["ficha"]["item_id"]

    corpo = _formulario(cliente, _EXT, segundo)

    assert (corpo["posicao_do_item"], corpo["total_de_itens"]) == (2, 2)
    assert corpo["itens_concluidos"] == 1
    assert corpo["trilha"] is not None
