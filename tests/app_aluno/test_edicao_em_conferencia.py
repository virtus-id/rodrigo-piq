"""`AC-176`, `AC-177`, `AC-179` — em cálculo ou conferência as respostas só se
leem, e o aluno pode retirar o plano da conferência (`RF-114`, `RF-115`,
`T-336`).

Sem `DATABASE_URL`: dublês em memória por `app.dependency_overrides`, o mesmo
mecanismo da produção. `AC-178` (o lado do revisor) vive em
`test_rotas_revisao_decisao.py`, onde está o ferramental da decisão.

REGRAS: `RF-114`, `RF-115`, `AC-176`, `AC-177`, `AC-179`
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, Final

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.edicao import MENSAGEM_EM_CONFERENCIA
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.rotas_respostas import obter_repositorio_eventos_da_retomada
from app.http.sessao import iniciar_sessao_conta
from collection.carga import carregar_registros
from collection.respostas import Resposta
from persistencia.app_aluno.eventos import EventoCaso

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-producao"
_CONTA: Final[str] = "CONTA-EDICAO"
_CASO: Final[str] = "CASO-EDICAO"
_SNAPSHOT_RAIZ: Final[str] = "SNAPSHOT-V1"
_FORM: Final[dict[str, str]] = {"content-type": "application/x-www-form-urlencoded"}

_EM_LEITURA = (ESTADO_CASO.AGUARDANDO_REVISAO, ESTADO_CASO.CALCULANDO)
_EDITAVEIS = (ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.PLANO_LIBERADO, ESTADO_CASO.ACOMPANHAMENTO)


class _Casos:
    """`buscar`, `pertence_a_conta` e a transição condicional — o que as rotas usam."""

    def __init__(self, estado: ESTADO_CASO) -> None:
        agora = datetime(2026, 1, 1, tzinfo=UTC)
        self.caso = Caso(
            CASO_ID=_CASO,
            conta_id=_CONTA,
            estado=estado,
            DATA_REFERENCIA=date(2026, 3, 15),
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=_SNAPSHOT_RAIZ,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )

    def buscar(self, caso_id: str) -> Caso | None:
        return self.caso if caso_id == _CASO else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == _CASO and conta_id == _CONTA

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        if self.caso.estado is not estado_esperado:
            return None
        self.caso = replace(self.caso, estado=novo_estado)
        return self.caso


class _Eventos:
    def __init__(self) -> None:
        self.eventos: list[EventoCaso] = []

    def registrar(self, evento: EventoCaso) -> None:
        self.eventos.append(evento)

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(self.eventos)


class _Respostas:
    def __init__(self) -> None:
        self.gravadas: list[Resposta] = []

    def gravar(self, resposta: Resposta) -> None:
        self.gravadas.append(resposta)

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(self.gravadas)


class _Itens:
    def listar_do_caso(self, caso_id: str, *, incluir_removidos: bool = False) -> tuple[()]:
        return ()


def _cliente(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> tuple[TestClient, _Casos, _Eventos, _Respostas]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    casos, eventos, respostas = _Casos(estado), _Eventos(), _Respostas()
    colecao = carregar_registros()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: casos
    aplicacao.dependency_overrides[obter_repositorio_eventos_da_retomada] = lambda: eventos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: _Itens()

    @aplicacao.post("/_teste/sessao")
    def abrir_sessao(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=_CONTA)
        return {"ok": "1"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/sessao")
    return cliente, casos, eventos, respostas


def _responder(cliente: TestClient) -> Any:
    # `B1.01`: SELECAO_UNICA sem condicional nem ficha — a pergunta mais simples.
    return cliente.post(
        f"/caso/{_CASO}/resposta", content="ID_PERGUNTA=B1.01&valor=ESTABELECIDO", headers=_FORM
    )


def _escritas_de_ficha(cliente: TestClient) -> dict[str, Any]:
    return {
        "criar": cliente.post(f"/caso/{_CASO}/fichas/DIVIDA_ID"),
        "nomear": cliente.put(
            f"/caso/{_CASO}/fichas/DIVIDA_ID/D001", content="nome=X", headers=_FORM
        ),
        "remover": cliente.delete(f"/caso/{_CASO}/fichas/DIVIDA_ID/D001"),
        "concluir": cliente.post(f"/caso/{_CASO}/concluir/DIVIDA_ID/D001"),
    }


# --------------------------------------------------------------------------- AC-176


@pytest.mark.parametrize("estado", _EM_LEITURA)
def test_ac176_gravar_resposta_em_calculo_ou_conferencia_e_recusado(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> None:
    cliente, _, _, respostas = _cliente(monkeypatch, estado)

    resposta = _responder(cliente)

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == MENSAGEM_EM_CONFERENCIA
    assert respostas.gravadas == [], "nada pode ser gravado"


@pytest.mark.parametrize("estado", _EM_LEITURA)
def test_ac176_as_quatro_rotas_de_ficha_tambem_recusam(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> None:
    cliente, _, _, _ = _cliente(monkeypatch, estado)

    for nome, resposta in _escritas_de_ficha(cliente).items():
        assert resposta.status_code == 409, nome
        assert resposta.json()["detail"] == MENSAGEM_EM_CONFERENCIA, nome


@pytest.mark.parametrize("estado", _EDITAVEIS)
def test_ac176_fora_de_calculo_e_conferencia_a_gravacao_segue_livre(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> None:
    cliente, _, _, respostas = _cliente(monkeypatch, estado)

    resposta = _responder(cliente)

    assert resposta.status_code == 200
    assert len(respostas.gravadas) == 1


@pytest.mark.parametrize(
    ("estado", "editavel", "pode_retomar"),
    [
        (ESTADO_CASO.AGUARDANDO_REVISAO, False, True),
        (ESTADO_CASO.CALCULANDO, False, False),
        (ESTADO_CASO.COLETA_INICIAL, True, False),
        (ESTADO_CASO.PLANO_LIBERADO, True, False),
    ],
)
def test_ac176_a_lista_de_respostas_diz_se_da_para_editar(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO, editavel: bool, pode_retomar: bool
) -> None:
    cliente, _, _, _ = _cliente(monkeypatch, estado)

    corpo = cliente.get(f"/caso/{_CASO}/respostas").json()

    assert corpo["editavel"] is editavel
    assert corpo["pode_retomar_edicao"] is pode_retomar


def test_ac176_o_409_nao_vaza_a_existencia_de_caso_alheio(monkeypatch: pytest.MonkeyPatch) -> None:
    """A posse é checada ANTES: caso de outra conta é `404`, nunca o `409` da conferência."""
    cliente, _, _, _ = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)

    resposta = cliente.post(
        "/caso/CASO-DE-OUTRA-CONTA/resposta", content="ID_PERGUNTA=B1.01&valor=X", headers=_FORM
    )

    assert resposta.status_code == 404


# --------------------------------------------------------------------------- AC-177


def test_ac177_retirar_o_plano_devolve_o_caso_a_coleta_sem_tocar_no_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, casos, eventos, respostas = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)

    resposta = cliente.post(f"/caso/{_CASO}/retomar-edicao")

    assert resposta.status_code == 200
    assert resposta.json()["estado"] == "COLETA_INICIAL"
    assert casos.caso.estado is ESTADO_CASO.COLETA_INICIAL
    assert casos.caso.snapshot_raiz_id == _SNAPSHOT_RAIZ, "o snapshot v1 fica intacto"
    assert [e.tipo_evento for e in eventos.eventos] == ["aluno_retoma_edicao"]
    assert respostas.gravadas == [], "nenhuma resposta é apagada nem criada"


def test_ac177_depois_de_retirar_a_edicao_volta_a_valer(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _, _, respostas = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)
    assert _responder(cliente).status_code == 409

    assert cliente.post(f"/caso/{_CASO}/retomar-edicao").status_code == 200

    assert _responder(cliente).status_code == 200
    assert len(respostas.gravadas) == 1
    corpo = cliente.get(f"/caso/{_CASO}/respostas").json()
    assert corpo["editavel"] is True


def test_ac177_retirar_duas_vezes_a_segunda_e_recusada(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _, eventos, _ = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)

    assert cliente.post(f"/caso/{_CASO}/retomar-edicao").status_code == 200
    segunda = cliente.post(f"/caso/{_CASO}/retomar-edicao")

    assert segunda.status_code == 409
    assert len(eventos.eventos) == 1, "só a transição que de fato ocorreu vai à trilha"


# --------------------------------------------------------------------------- AC-179


@pytest.mark.parametrize(
    "estado", [ESTADO_CASO.CALCULANDO, ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.PLANO_LIBERADO]
)
def test_ac179_fora_da_conferencia_retomar_e_recusado_sem_mudar_nada(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> None:
    cliente, casos, eventos, _ = _cliente(monkeypatch, estado)

    resposta = cliente.post(f"/caso/{_CASO}/retomar-edicao")

    assert resposta.status_code == 409
    assert resposta.json()["erro"]
    assert casos.caso.estado is estado
    assert eventos.eventos == []


def test_ac179_sem_sessao_nao_retira_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, casos, _, _ = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)
    cliente.cookies.clear()

    assert cliente.post(f"/caso/{_CASO}/retomar-edicao").status_code == 401
    assert casos.caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO
