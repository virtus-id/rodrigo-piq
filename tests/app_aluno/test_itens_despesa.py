"""T-217 (itens 1–5) — ficha `ITEM_DESPESA` por item marcado em `B3.D01`–`D11`;
T-219 — completude da ficha de ação.

A coleção é a real (`collection/registros/*.yaml`); os repositórios são os de
arquivo sobre `tmp_path`, com o de respostas ligado ao de itens (o `NOT
EXISTS` do adaptador Postgres). O de ponta a ponta usa o fluxo de cálculo com
os dublês de `test_rotas_calculo.py`, como `test_plano_ponta_a_ponta.py`.

REGRAS: `RF-04`, `RF-05`, `RF-52`, `RF-53`, `AC-04`, `AC-12`
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.http import rotas_calculo, rotas_coleta
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_calculo import (
    obter_fonte_parametros,
    obter_parametros_externos_do_bloco6,
    obter_repositorio_eventos,
    obter_repositorio_snapshots,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_estado_financeiro
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta
from engine.estado import EstadoFinanceiro
from persistencia.app_aluno.arquivo import RepositorioItensArquivo, RepositorioRespostasArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import CASO_ID, caso_completo
from tests.app_aluno.test_rotas_calculo import (
    _caso_fabricado,
    _ParametrosExternosFabricados,
    _RepositorioCasosDublê,
    _RepositorioEventosDublê,
    _RepositorioSnapshotsDublê,
)

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID: Final[str] = "CONTA-1"
_DESPESA: Final[str] = EscopoRepeticao.ITEM_DESPESA.value


def _repositorios(tmp_path: Path) -> tuple[RepositorioRespostasArquivo, RepositorioItensArquivo]:
    itens = RepositorioItensArquivo(caminho_arquivo=tmp_path / "itens.jsonl")
    respostas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl", repositorio_itens=itens
    )
    return respostas, itens


def _cliente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """Aplicação com a coleção real, repositórios de arquivo e os dublês do
    cálculo — um caso novo em `COLETA_INICIAL` a cada chamada."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", "1.0.1")
    respostas, itens = _repositorios(tmp_path)
    casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL, caso_id=CASO_ID), conta_id_da_sessao=_CONTA_ID
    )

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: casos
    # A rota do cálculo tem os seus próprios pontos de injeção.
    for modulo in (rotas_coleta, rotas_calculo):
        aplicacao.dependency_overrides[modulo.obter_colecao_de_registros] = carregar_registros
        aplicacao.dependency_overrides[modulo.obter_repositorio_respostas] = lambda: respostas
        aplicacao.dependency_overrides[modulo.obter_repositorio_itens] = lambda: itens
    aplicacao.dependency_overrides[obter_fonte_parametros] = FonteParametrosArquivo
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = _RepositorioSnapshotsDublê
    aplicacao.dependency_overrides[obter_repositorio_eventos] = _RepositorioEventosDublê
    aplicacao.dependency_overrides[obter_parametros_externos_do_bloco6] = (
        _ParametrosExternosFabricados
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def _responder(
    cliente: TestClient, id_pergunta: str, valores: list[str] | str, item_id: str | None = None
) -> Any:
    """`POST /resposta` — `valores` em lista é o checklist (um `valor` por
    opção marcada, como o formulário envia)."""
    corpo = [("ID_PERGUNTA", id_pergunta)]
    corpo += [("valor", v) for v in ([valores] if isinstance(valores, str) else valores)]
    corpo += [("item_id", item_id)] if item_id else []
    resposta = cliente.post(
        f"/caso/{CASO_ID}/resposta",
        content=urlencode(corpo),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _fichas(cliente: TestClient, escopo: str = _DESPESA) -> list[dict[str, Any]]:
    resposta = cliente.get(f"/caso/{CASO_ID}/fichas/{escopo}")
    assert resposta.status_code == 200, resposta.text
    fichas: list[dict[str, Any]] = resposta.json()["fichas"]
    return fichas


def _rotulos(cliente: TestClient) -> list[str]:
    return [ficha["rotulo"] for ficha in _fichas(cliente)]


# ---------------------------------------------------------------------------
# Item 1 — uma ficha por item marcado, com o rótulo do item.
# ---------------------------------------------------------------------------


def test_cada_item_marcado_no_checklist_abre_uma_ficha_com_o_rotulo_dele(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)

    _responder(cliente, "B3.D01", ["ENERGIA", "ALUGUEL"])

    assert _rotulos(cliente) == ["Aluguel", "Energia"]


def test_enunciado_da_ficha_mostra_o_rotulo_e_nao_o_identificador(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL"])
    item_id = _fichas(cliente)[0]["item_id"]

    pergunta = cliente.get(f"/caso/{CASO_ID}/pergunta", params={"item_id": item_id}).json()

    assert pergunta["pergunta"]["ID"] == "B3.DF01"
    assert pergunta["pergunta"]["enunciado"] == "Qual é o valor mensal de Aluguel?"
    assert _fichas(cliente)[0]["campos"][0]["enunciado"] == "Qual é o valor mensal de Aluguel?"


def test_a_retomada_pergunta_o_valor_de_cada_item_depois_do_checklist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nenhuma tela a mais: com o item criado, a própria coleta chega à ficha
    — no caso completo, é a próxima pergunta depois do checklist."""
    _semear_caso_completo_sem_despesas(tmp_path)
    cliente = _cliente(monkeypatch, tmp_path)

    confirmacao = _responder(cliente, "B3.D01", ["ALUGUEL"])

    assert confirmacao["proxima"]["pergunta"]["ID"] == "B3.DF01"
    assert confirmacao["proxima"]["pergunta"]["enunciado"] == "Qual é o valor mensal de Aluguel?"


# ---------------------------------------------------------------------------
# Item 2 — desmarcar remove a ficha e o valor dela.
# ---------------------------------------------------------------------------


def test_desmarcar_um_item_remove_a_ficha_dele_e_preserva_as_outras(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL", "ENERGIA"])
    ids = {f["rotulo"]: f["item_id"] for f in _fichas(cliente)}
    _responder(cliente, "B3.DF01", "1500", ids["Aluguel"])

    _responder(cliente, "B3.D01", ["ALUGUEL"])

    fichas = _fichas(cliente)
    assert [(f["rotulo"], f["item_id"]) for f in fichas] == [("Aluguel", ids["Aluguel"])]
    valores = {c["ID"]: c["valor_atual"] for c in fichas[0]["campos"]}
    assert valores["B3.DF01"] is not None


def test_remarcar_um_item_abre_ficha_nova_sem_o_valor_antigo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ENERGIA"])
    antigo = _fichas(cliente)[0]["item_id"]
    _responder(cliente, "B3.DF01", "200", antigo)

    _responder(cliente, "B3.D01", [])
    _responder(cliente, "B3.D01", ["ENERGIA"])

    ficha = _fichas(cliente)[0]
    assert ficha["item_id"] != antigo
    assert {c["ID"]: c["valor_atual"] for c in ficha["campos"]}["B3.DF01"] is None


def test_checklist_de_uma_categoria_nao_toca_as_fichas_de_outra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL"])
    _responder(cliente, "B3.D02", ["SUPERMERCADO"])

    _responder(cliente, "B3.D01", [])

    assert _rotulos(cliente) == ["Supermercado"]


# ---------------------------------------------------------------------------
# Itens 3 e 5 — "Outro" e B3.D11 = Sim pedem um nome curto, que vira o título.
# ---------------------------------------------------------------------------


def _nomear(cliente: TestClient, item_id: str, nome: str) -> Any:
    return cliente.put(
        f"/caso/{CASO_ID}/fichas/{_DESPESA}/{item_id}",
        content=urlencode({"nome": nome}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_outro_abre_a_lista_de_fichas_para_o_aluno_dar_o_nome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)

    confirmacao = _responder(cliente, "B3.D01", ["ALUGUEL", "OUTRO"])

    assert confirmacao["abrir_fichas"] == [_DESPESA]
    pede_nome = {f["rotulo"]: f["pede_nome"] for f in _fichas(cliente)}
    assert pede_nome == {"Aluguel": False, "Outro": True}


def test_checklist_sem_outro_nao_abre_a_lista(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)

    assert _responder(cliente, "B3.D01", ["ALUGUEL"])["abrir_fichas"] == []


def test_nome_dado_ao_outro_vira_o_titulo_e_o_enunciado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["OUTRO"])
    item_id = _fichas(cliente)[0]["item_id"]

    assert _nomear(cliente, item_id, "Jardineiro").status_code == 200

    assert _rotulos(cliente) == ["Jardineiro"]
    pergunta = cliente.get(f"/caso/{CASO_ID}/pergunta", params={"item_id": item_id}).json()
    assert pergunta["pergunta"]["enunciado"] == "Qual é o valor mensal de Jardineiro?"


def test_nome_vazio_ou_de_item_que_nao_pede_nome_e_recusado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL", "OUTRO"])
    ids = {f["rotulo"]: f["item_id"] for f in _fichas(cliente)}

    assert _nomear(cliente, ids["Outro"], "   ").status_code == 400
    assert _nomear(cliente, ids["Outro"], "x" * 61).status_code == 400
    assert _nomear(cliente, ids["Aluguel"], "Casa").status_code == 400
    assert _nomear(cliente, "DESP999", "Casa").status_code == 404
    assert _rotulos(cliente) == ["Aluguel", "Outro"]


def test_despesa_nao_listada_sim_abre_uma_ficha_que_pede_nome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)

    confirmacao = _responder(cliente, "B3.D11", "SIM")

    assert confirmacao["abrir_fichas"] == [_DESPESA]
    [ficha] = _fichas(cliente)
    assert ficha["pede_nome"] is True
    assert [c["ID"] for c in ficha["campos"]] == ["B3.DF01", "B3.DF02", "B3.DF03", "B3.DF04"]
    _nomear(cliente, ficha["item_id"], "Pet")
    assert _rotulos(cliente) == ["Pet"]


def test_despesa_nao_listada_nao_remove_so_as_fichas_dela(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL"])
    _responder(cliente, "B3.D11", "SIM")

    _responder(cliente, "B3.D11", "NAO")

    assert _rotulos(cliente) == ["Aluguel"]


def test_ficha_adicionada_pela_lista_de_despesas_pede_nome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D11", "SIM")

    criada = cliente.post(f"/caso/{CASO_ID}/fichas/{_DESPESA}")

    assert criada.status_code == 201
    assert criada.json()["ficha"]["pede_nome"] is True
    assert len(_fichas(cliente)) == 2


# ---------------------------------------------------------------------------
# Item 4 — sem limite de itens.
# ---------------------------------------------------------------------------


def test_todos_os_itens_de_uma_categoria_abrem_ficha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    [registro] = [r for r in carregar_registros().registros if r.ID == "B3.D01"]
    todas = [o.valor_interno for o in registro.opcoes if o.valor_interno]

    _responder(cliente, "B3.D01", todas)

    assert len(_fichas(cliente)) == len(todas) == 10


# ---------------------------------------------------------------------------
# De ponta a ponta — a montagem recebe a soma dos itens marcados.
# ---------------------------------------------------------------------------


def _semear_caso_completo_sem_despesas(tmp_path: Path) -> None:
    """O caso completo (todo `OBR` respondido) sem a ficha de despesa da
    fixture — as despesas deste teste nascem do checklist."""
    respostas, itens = _repositorios(tmp_path)
    divida = itens.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    nao_mensal = itens.proximo_identificador(CASO_ID, EscopoRepeticao.DESPESA_NAO_MENSAL_ID)
    base = caso_completo(DIVIDA_ID=divida, DESPESA_NAO_MENSAL_ID=nao_mensal, ITEM_DESPESA_ID="-")
    for resposta in base.respostas.respostas:
        if resposta.item_id != "-":
            respostas.gravar(resposta)


def _despesas_na_montagem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Decimal:
    """`POST /calculo` e o `DESPESAS_OPERACIONAIS_ATUAIS` que a montagem
    produziu — lido por um espião sobre `montar_estado_financeiro`."""
    montados: list[EstadoFinanceiro] = []
    original = montar_estado_financeiro

    def espiao(*args: Any, **kwargs: Any) -> EstadoFinanceiro:
        estado = original(*args, **kwargs)
        montados.append(estado)
        return estado

    monkeypatch.setattr(rotas_calculo, "montar_estado_financeiro", espiao)
    resposta = _cliente(monkeypatch, tmp_path).post(f"/caso/{CASO_ID}/calculo")
    assert resposta.status_code == 200, resposta.text
    [estado] = montados
    return estado.DESPESAS_OPERACIONAIS_ATUAIS


def test_ponta_a_ponta_montagem_soma_os_itens_marcados_e_tira_o_desmarcado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _semear_caso_completo_sem_despesas(tmp_path)
    cliente = _cliente(monkeypatch, tmp_path)
    _responder(cliente, "B3.D01", ["ALUGUEL", "ENERGIA"])
    ids = {f["rotulo"]: f["item_id"] for f in _fichas(cliente)}
    _responder(cliente, "B3.DF01", "1.500,00", ids["Aluguel"])
    _responder(cliente, "B3.DF01", "230,50", ids["Energia"])

    assert _despesas_na_montagem(monkeypatch, tmp_path) == converter_para_dinheiro("1.730,50")

    _responder(_cliente(monkeypatch, tmp_path), "B3.D01", ["ALUGUEL"])

    assert _despesas_na_montagem(monkeypatch, tmp_path) == converter_para_dinheiro("1.500,00")


def test_resposta_de_item_removido_continua_gravada(tmp_path: Path) -> None:
    """Remoção lógica: a linha fica (auditoria), só deixa de ser lida."""
    respostas, itens = _repositorios(tmp_path)
    item_id = itens.proximo_identificador(CASO_ID, EscopoRepeticao.ITEM_DESPESA, "B3.D01:AGUA")
    resposta = Resposta(
        CASO_ID=CASO_ID,
        ID_PERGUNTA="VALOR_DESPESA",
        item_id=item_id,
        valor=Decimal("80"),
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 1, 1, tzinfo=UTC),
    )
    respostas.gravar(resposta)

    itens.remover(CASO_ID, item_id)

    assert respostas.listar_do_caso(CASO_ID) == ()
    assert RepositorioRespostasArquivo(tmp_path / "respostas.jsonl").listar_do_caso(CASO_ID) == (
        resposta,
    )
    [removido] = itens.listar_do_caso(CASO_ID)
    assert removido.origem == "B3.D01:AGUA"


# ---------------------------------------------------------------------------
# T-219 — a ficha de ação considera as perguntas do próprio escopo.
# ---------------------------------------------------------------------------


def test_t219_ficha_de_acao_com_pergunta_aberta_em_branco_nao_e_completa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente(monkeypatch, tmp_path)
    escopo = EscopoRepeticao.ACAO_ID.value
    assert cliente.post(f"/caso/{CASO_ID}/fichas/{escopo}").status_code == 201

    [ficha] = _fichas(cliente, escopo)

    assert ficha["campos"]
    assert ficha["completa"] is False
