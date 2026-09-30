"""Vínculos e margem por vínculo — `RF-89`, `RF-90` (`T-255`, `T-258`,
`T-260`, `T-282`).

`AC-136`–`AC-139`, `AC-156`, `EC-35`, `EC-41`, `DE-05`, sobre os registros
REAIS e a aplicação real com repositórios de arquivo (mesmos auxiliares de
`test_ficha_repetivel.py`). `T-282` (`DE-04`): sem vínculo cadastrado, a
dívida consignada não trava a coleta — a pendência vai para o inventário e
só o cálculo final bloqueia.

REGRAS: `RF-89`, `RF-90`, `AC-136`, `AC-137`, `AC-139`, `AC-156`, `EC-35`,
`EC-41`
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.casos.inventario import (
    TIPO_PENDENCIA_INVENTARIO,
    mensagem_da_pendencia,
    pendencias_de_inventario,
)
from app.http.rotas_inventario import (
    obter_colecao_de_registros_do_inventario,
    obter_repositorio_itens_do_inventario,
    obter_repositorio_respostas_do_inventario,
)
from app.montagem.entrada import avisos_da_gravacao, conferir_renda_dos_vinculos
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao, RegistroPergunta, TipoResposta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from persistencia.app_aluno.arquivo import RepositorioItensArquivo, RepositorioRespostasArquivo
from tests.app_aluno.test_ficha_repetivel import (
    _CASO_ID,
    _cliente_real,
    _criar_em,
    _fichas,
    _responder,
)


@cache
def _registros() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _registro(ID: str) -> RegistroPergunta:
    (registro,) = [r for r in _registros() if r.ID == ID]
    return registro


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-VINCULOS",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def _cliente_com_inventario(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    cliente = _cliente_real(monkeypatch, tmp_path)
    aplicacao: Any = cliente.app
    aplicacao.dependency_overrides[obter_colecao_de_registros_do_inventario] = (
        carregar_registros
    )
    aplicacao.dependency_overrides[obter_repositorio_respostas_do_inventario] = lambda: (
        RepositorioRespostasArquivo(caminho_arquivo=tmp_path / "respostas.jsonl")
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_do_inventario] = lambda: (
        RepositorioItensArquivo(caminho_arquivo=tmp_path / "itens.jsonl")
    )
    return cliente


def _proxima_do_item(cliente: TestClient, item_id: str) -> str:
    corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta", params={"item_id": item_id}).json()
    ID: str = corpo["pergunta"]["ID"]
    return ID


def _campos(cliente: TestClient, escopo: str, item_id: str) -> list[str]:
    (ficha,) = [f for f in _fichas(cliente, escopo) if f["item_id"] == item_id]
    return [c["ID"] for c in ficha["campos"]]


# ---------------------------------------------------------------------------
# T-255 — `B3.S04L` e `B3.S05C` no registro real.
# ---------------------------------------------------------------------------


def test_t255_registros_novos_do_vinculo_na_carga_real() -> None:
    liquida = _registro("B3.S04L")
    assert liquida.VARIAVEL_GRAVADA == "RENDA_LIQUIDA_VINCULO"
    assert liquida.tipo is TipoResposta.MOEDA
    assert liquida.admite_nao_sei
    assert liquida.escopo_repeticao is EscopoRepeticao.VINCULO_ID

    consignacao = _registro("B3.S05C")
    assert consignacao.VARIAVEL_GRAVADA == "CONSIGNACAO_EXISTE_VINCULO"
    assert consignacao.escopo_repeticao is EscopoRepeticao.VINCULO_ID
    assert {o.valor_interno for o in consignacao.opcoes} == {"SIM", "NAO", "NAO_SEI"}


def test_t255_visiveis_na_ficha_do_vinculo_e_fechadas_sem_vinculo_consignavel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    vinculo = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]

    assert {"B3.S04L", "B3.S05C"} <= set(_campos(cliente, "VINCULO_ID", vinculo))
    assert _responder(cliente, "B3.S04L", "NAO_SEI", vinculo).status_code == 200
    assert _responder(cliente, "B3.S05C", "NAO_SEI", vinculo).status_code == 200

    _responder(cliente, "B3.S01", "NAO")
    fechada = cliente.get(
        f"/caso/{_CASO_ID}/pergunta/B3.S04L", params={"item_id": vinculo}
    )
    assert fechada.status_code == 404


# ---------------------------------------------------------------------------
# T-260 — independência (AC-136), pertença (AC-137), EC-35.
# ---------------------------------------------------------------------------


def test_ac136_dois_vinculos_independentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    v1 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    v2 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    assert v1 != v2
    for ID, valor in (("B3.S03", "Prefeitura"), ("B3.S04", "5000"), ("B3.S04L", "4000")):
        assert _responder(cliente, ID, valor, v1).status_code == 200
    gravadas = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    antes = {r for r in gravadas.listar_do_caso(_CASO_ID) if r.item_id == v1}

    for ID, valor in (("B3.S03", "Estado"), ("B3.S04", "3000"), ("B3.S04L", "2500")):
        assert _responder(cliente, ID, valor, v2).status_code == 200

    assert {r for r in gravadas.listar_do_caso(_CASO_ID) if r.item_id == v1} == antes
    assert [f["item_id"] for f in _fichas(cliente, "VINCULO_ID")] == [v1, v2]


def test_ac137_margem_sem_pai_recusada_e_toda_margem_tem_um_pai_do_caso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    v1 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    v2 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    assert _criar_em(cliente, "MARGEM_ID").status_code == 422
    for pai in (v1, v2, v2):
        assert _criar_em(cliente, "MARGEM_ID", item_pai_id=pai).status_code in (200, 201)

    itens = RepositorioItensArquivo(tmp_path / "itens.jsonl").listar_do_caso(
        _CASO_ID, incluir_removidos=False
    )
    vinculos = {i.item_id for i in itens if i.escopo is EscopoRepeticao.VINCULO_ID}
    margens = [i for i in itens if i.escopo is EscopoRepeticao.MARGEM_ID]
    assert len(margens) == 3
    assert all(m.item_pai_id in vinculos for m in margens)


def test_ec35_remover_vinculo_deixa_margem_e_consignado_em_aberto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Com outro vínculo ainda ativo, a dívida que apontava o removido volta
    a pedir o vínculo (`AC-139`); a margem do removido fica em aberto."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    removido = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    _criar_em(cliente, "VINCULO_ID")
    margem = _criar_em(cliente, "MARGEM_ID", item_pai_id=removido).json()["ficha"]["item_id"]
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]
    _responder(cliente, "B5.A01", "Banco", divida)
    _responder(cliente, "B5.A02", "CONSIGNADO", divida)
    _responder(cliente, "B5.A02V", removido, divida)
    assert _proxima_do_item(cliente, divida) != "B5.A02V"

    cliente.delete(f"/caso/{_CASO_ID}/fichas/VINCULO_ID/{removido}")

    assert _proxima_do_item(cliente, divida) == "B5.A02V"
    assert {f["item_id"]: f["completa"] for f in _fichas(cliente, "MARGEM_ID")}[margem] is False


# ---------------------------------------------------------------------------
# T-258 — conferência da renda dos vínculos (AC-156, EC-41).
# ---------------------------------------------------------------------------


def _caso_de_renda(principal: str, *liquidas: object) -> RespostasCaso:
    return RespostasCaso(
        respostas=(
            _resposta("RENDA_PRINCIPAL", Decimal(principal)),
            *(
                _resposta("RENDA_LIQUIDA_VINCULO", liquida, item_id=f"V{i:03d}")
                for i, liquida in enumerate(liquidas, start=1)
            ),
        )
    )


def test_ac156_soma_igual_a_renda_do_bloco_3_nao_diverge() -> None:
    conferencia = conferir_renda_dos_vinculos(
        _caso_de_renda("6500", Decimal("4000"), Decimal("2500"))
    )
    assert conferencia is not None
    assert conferencia.SOMA_LIQUIDAS == Decimal("6500")
    assert conferencia.divergente is False


def test_ac156_ec41_soma_diferente_diverge_e_nada_e_somado_a_renda() -> None:
    respostas = _caso_de_renda("6000", Decimal("4000"), Decimal("2500"))
    conferencia = conferir_renda_dos_vinculos(respostas)
    assert conferencia is not None
    assert conferencia.RENDA_BLOCO_3 == Decimal("6000")
    assert conferencia.divergente is True
    (aviso,) = avisos_da_gravacao("RENDA_LIQUIDA_VINCULO", "V002", respostas)
    assert aviso.codigo == "DIVERGENCIA_RENDA_VINCULOS"
    assert avisos_da_gravacao("RENDA_PRINCIPAL", None, respostas) == (aviso,)


def test_t258_sem_liquida_informada_nao_ha_conferencia() -> None:
    assert conferir_renda_dos_vinculos(_caso_de_renda("6000")) is None
    assert conferir_renda_dos_vinculos(_caso_de_renda("6000", NAO_SEI)) is None
    assert avisos_da_gravacao("RENDA_PRINCIPAL", None, _caso_de_renda("6000", NAO_SEI)) == ()


def test_ac156_aviso_no_post_nao_bloqueia_a_gravacao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.01", "6500")
    _responder(cliente, "B3.S01", "SIM")
    v1 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    v2 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    _responder(cliente, "B3.S04L", "4000", v1)
    igual = _responder(cliente, "B3.S04L", "2500", v2)
    assert igual.status_code == 200
    assert igual.json()["avisos"] == []

    divergente = _responder(cliente, "B3.01", "6000")
    assert divergente.status_code == 200
    assert [a["codigo"] for a in divergente.json()["avisos"]] == ["DIVERGENCIA_RENDA_VINCULOS"]


# ---------------------------------------------------------------------------
# T-282 — consignado sem vínculo: não trava a ficha; pendência de inventário.
# ---------------------------------------------------------------------------


def test_t282_sem_vinculo_a_pergunta_do_vinculo_nao_aparece_e_a_ficha_segue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_com_inventario(monkeypatch, tmp_path)
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]
    _responder(cliente, "B5.A01", "Banco", divida)
    _responder(cliente, "B5.A02", "CONSIGNADO", divida)

    assert _proxima_do_item(cliente, divida) != "B5.A02V"
    assert "B5.A02V" not in _campos(cliente, "DIVIDA_ID", divida)
    direta = cliente.get(f"/caso/{_CASO_ID}/pergunta/B5.A02V", params={"item_id": divida})
    assert direta.status_code == 404

    (pendencia,) = cliente.get(f"/caso/{_CASO_ID}/inventario").json()["pendencias"]
    assert pendencia["codigo"] == "CONSIGNADO_SEM_VINCULO"
    assert pendencia["escopo"] == "VINCULO_ID"
    assert pendencia["ID_PARA_CORRIGIR"] == "B3.S01"

    _criar_em(cliente, "VINCULO_ID")
    assert _proxima_do_item(cliente, divida) == "B5.A02V"
    assert cliente.get(f"/caso/{_CASO_ID}/inventario").json()["pendencias"] == []


def test_t282_pendencia_so_para_consignado_e_some_com_vinculo() -> None:
    consignado = (_resposta("TIPO_DIVIDA", "CONSIGNADO", item_id="D001"),)
    pessoal = (_resposta("TIPO_DIVIDA", "PESSOAL", item_id="D001"),)
    dividas = {EscopoRepeticao.DIVIDA_ID: ("D001",)}

    (pendencia,) = pendencias_de_inventario(
        _registros(), RespostasCaso(respostas=consignado), dividas
    )
    assert pendencia.tipo is TIPO_PENDENCIA_INVENTARIO.CONSIGNADO_SEM_VINCULO
    assert "consignad" in mensagem_da_pendencia(pendencia)
    assert pendencias_de_inventario(_registros(), RespostasCaso(respostas=pessoal), dividas) == ()
    com_vinculo = dividas | {EscopoRepeticao.VINCULO_ID: ("V001",)}
    assert (
        pendencias_de_inventario(_registros(), RespostasCaso(respostas=consignado), com_vinculo)
        == ()
    )
