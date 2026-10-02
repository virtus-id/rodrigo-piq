"""Testes de `app/http/rotas_plano.py` — a rota do PDF do plano (`RF-20`,
`RF-21`, `AC-14`, `AC-16`, T-63) e a rota de tela do plano (`RF-20`,
`RF-21`, `RF-23`, `AC-25`, T-64).

Dublês em memória para os repositórios (`Caso`, `SnapshotOrdem`), mesmo
mecanismo de injeção que a produção usa (`app.dependency_overrides`) — sem
tocar Postgres. `calcular_plano` real é usado sobre a fixture de caso
completo (T-53) para produzir o `SnapshotOrdem` — nunca fabricado à mão,
mesmo padrão de `tests/app_aluno/test_rotas_calculo.py`.

Cobre as duas rotas (`GET /caso/{CASO_ID}/plano/pdf` e `GET /caso/{CASO_ID}/
plano`) protegidas por isolamento (`T-31`), e os quatro critérios de aceite
de T-64:

1. `AC-25`: snapshot sem liberação registrada não é acessível ao aluno, nem
   em tela nem em PDF.
2. A tela serve o `snapshot_liberado_id` do caso, não o último calculado.
3. A rota respeita o isolamento por caso de `T-31`.
4. Caso sem nenhum snapshot liberado exibe o estado do caso, nunca um plano
   vazio.

REGRAS: `RF-20`, `RF-21`, `RF-23`, `AC-14`, `AC-16`, `AC-25`
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import obter_repositorio_itens, obter_repositorio_respostas
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta
from engine.estado import EstadoFinanceiro
from engine.motor import calcular_plano
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.itens import ItemRepetido
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from report.plano import carregar_textos_canonicos, formatar_dinheiro_br
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo
from tests.app_aluno.fixtures.sem_respostas import sem_respostas_nem_itens
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_b, carregar_gab_c

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_VERSAO_PARAMETROS_REAL = "1.0.1"


class _RepositorioCasosDublê:
    """Dublê em memória — mesmo padrão de `tests/app_aluno/test_rotas_
    calculo.py::_RepositorioCasosDublê`, restrito aos métodos que a rota de
    plano usa."""

    def __init__(self, caso_inicial: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso_inicial
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao

    def transicionar_estado(self, caso_id, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def transicionar_estado_se(self, caso_id, estado_esperado, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_interacao(self, caso_id, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id, snapshot_raiz_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_liberado(self, caso_id, snapshot_liberado_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui


class _RepositorioSnapshotsDublê:
    """Guarda um único snapshot em memória, indexado por `SNAPSHOT_ID` —
    `obter` levanta `ErroSnapshotNaoEncontrado` para qualquer outro id,
    mesmo contrato do adaptador Postgres real."""

    def __init__(self, snapshot: SnapshotOrdem) -> None:
        self._snapshot = snapshot

    def anexar(self, s: SnapshotOrdem) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        if snapshot_id != self._snapshot.SNAPSHOT_ID:
            raise ErroSnapshotNaoEncontrado(f"sem snapshot com SNAPSHOT_ID={snapshot_id!r}")
        return self._snapshot

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


def _snapshot_real() -> SnapshotOrdem:
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def _caso_fabricado(
    *, snapshot_liberado_id: str | None, caso_id: str = "CASO-PDF-ROTA-1"
) -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id="CONTA-PDF-ROTA-1",
        estado=ESTADO_CASO.PLANO_LIBERADO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot_liberado_id,
        snapshot_liberado_id=snapshot_liberado_id,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: _RepositorioCasosDublê,
    repositorio_snapshots: RepositorioSnapshots,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: repositorio_snapshots
    sem_respostas_nem_itens(aplicacao)  # `T-267`: fonte lida das respostas

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/abrir-sessao/CONTA-PDF-ROTA-1")
    return cliente


def test_exporta_pdf_do_snapshot_liberado_com_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GET /caso/{CASO_ID}/plano/pdf` devolve `200` com
    `media_type=application/pdf` quando o caso tem um snapshot liberado —
    exercitando o caminho completo, mas pulando a produção de bytes reais se
    a biblioteca nativa do WeasyPrint estiver indisponível (limitação de
    ambiente, ver `tests/app_aluno/test_pdf.py`)."""
    try:
        from weasyprint import HTML

        HTML(string="<html><body></body></html>").write_pdf()
    except OSError as erro:
        pytest.skip(f"biblioteca nativa do WeasyPrint indisponível neste ambiente: {erro}")

    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/plano/pdf")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_recusa_pdf_quando_caso_nao_tem_snapshot_liberado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 4: sem `snapshot_liberado_id` (situação de HOJE,
    antes da Entrega 8 — fila de revisão ainda não popula o campo), a rota
    devolve `404` sem tentar buscar snapshot nenhum."""
    caso = _caso_fabricado(snapshot_liberado_id=None)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    snapshot_nao_usado = _snapshot_real()
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot_nao_usado)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/plano/pdf")

    assert resposta.status_code == 404


def test_recusa_pdf_quando_snapshot_liberado_nao_e_encontrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`snapshot_liberado_id` aponta para um `SNAPSHOT_ID` que o repositório
    não conhece — `404`, nunca um erro 500 vazando detalhe interno."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id="SNAPSHOT-INEXISTENTE")
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/plano/pdf")

    assert resposta.status_code == 404


def test_isolamento_por_caso_e_respeitado_na_rota_de_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RF-02`/`AC-03`: sessão sem `CASO_ID` correspondente recebe `404` —
    o mecanismo de `app/http/isolamento.py` (T-31) protege esta rota."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/caso/CASO-DE-OUTRA-CONTA/plano/pdf")

    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# T-64 — `GET /caso/{CASO_ID}/plano`, a tela HTML do plano do aluno.
# ---------------------------------------------------------------------------


def test_tela_do_plano_exibe_o_snapshot_liberado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Critério de aceite 2: a tela serve o `snapshot_liberado_id` do caso —
    o título canônico (`Q-03`, T-59) e o carimbo de versão do snapshot
    aparecem na resposta."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/api/plano")

    assert resposta.status_code == 200
    plano = resposta.json()["plano"]
    assert plano is not None
    assert plano["titulo"] == "Sua ordem projetada de quitação"
    assert plano["ENGINE_VERSION"] == snapshot.ENGINE_VERSION
    assert plano["PARAMETROS_VERSION"] == snapshot.PARAMETROS_VERSION


class _RepositorioSnapshotsComHistoricoDublê:
    """Variante de `_RepositorioSnapshotsDublê` que guarda DOIS snapshots —
    o `liberado` (o que `Caso.snapshot_liberado_id` aponta) e o
    `ultimo_calculado` (um recálculo mais recente, hipoteticamente ainda em
    `AGUARDANDO_REVISAO`, sem liberação) — para provar que a rota busca
    exatamente o primeiro, nunca o segundo, mesmo os dois existindo no
    repositório."""

    def __init__(self, liberado: SnapshotOrdem, ultimo_calculado: SnapshotOrdem) -> None:
        self._por_id = {
            liberado.SNAPSHOT_ID: liberado,
            ultimo_calculado.SNAPSHOT_ID: ultimo_calculado,
        }

    def anexar(self, s: SnapshotOrdem) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        if snapshot_id not in self._por_id:
            raise ErroSnapshotNaoEncontrado(f"sem snapshot com SNAPSHOT_ID={snapshot_id!r}")
        return self._por_id[snapshot_id]

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


def test_tela_do_plano_nao_serve_o_ultimo_calculado_quando_diverge_do_liberado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 2 (contraprova) e `AC-25`: com DOIS snapshots no
    repositório — o liberado e um "último calculado" hipotético, ainda sem
    liberação — a tela serve exatamente o snapshot liberado. Comparado por
    `ENGINE_VERSION`, único campo desta fixture que difere de forma
    observável entre os dois snapshots (a fixture real produz o mesmo
    conteúdo determinístico a cada chamada; o "último calculado" é
    fabricado com um `SNAPSHOT_ID`/`ENGINE_VERSION` artificialmente
    diferentes, só para tornar a divergência auditável no HTML)."""
    snapshot_liberado = _snapshot_real()
    ultimo_calculado = replace(
        snapshot_liberado,
        SNAPSHOT_ID="SNAPSHOT-ULTIMO-CALCULADO-NAO-LIBERADO",
        ENGINE_VERSION="ENGINE-VERSION-NAO-LIBERADA",
    )
    caso = _caso_fabricado(snapshot_liberado_id=snapshot_liberado.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsComHistoricoDublê(
        liberado=snapshot_liberado, ultimo_calculado=ultimo_calculado
    )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/api/plano")

    assert resposta.status_code == 200
    plano = resposta.json()["plano"]
    assert plano is not None
    assert plano["ENGINE_VERSION"] == snapshot_liberado.ENGINE_VERSION
    assert "ENGINE-VERSION-NAO-LIBERADA" not in resposta.text


def test_ac25_tela_do_plano_sem_snapshot_liberado_exibe_estado_do_caso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-25` + critério de aceite 4: sem `snapshot_liberado_id`, a tela
    devolve `200` com o ESTADO do caso — nunca `404`, nunca uma tela de
    plano vazia."""
    caso = _caso_fabricado(snapshot_liberado_id=None)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    snapshot_nao_usado = _snapshot_real()
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot_nao_usado)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/api/plano")

    assert resposta.status_code == 200
    corpo = resposta.json()
    # `plano: null` com o ESTADO nomeado — nunca `404`, nunca um plano vazio
    # que o aluno leria como se fosse o dele.
    assert corpo["plano"] is None
    assert corpo["estado"] == caso.estado.value
    assert corpo["mensagem"]


def test_ac25_tela_do_plano_sem_liberacao_exibe_mensagem_por_estado_cadastrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 4, caso concreto: um caso em `CADASTRADO` (coleta
    nem começou) sem snapshot liberado mostra a mensagem correspondente a
    ESSE estado — prova de que a leitura é de `Caso.estado`, não um texto
    fixo único para "sem liberação"."""
    caso = Caso(
        CASO_ID="CASO-PDF-ROTA-CADASTRADO",
        conta_id="CONTA-PDF-ROTA-1",
        estado=ESTADO_CASO.CADASTRADO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(_snapshot_real())

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/api/plano")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["plano"] is None
    # A mensagem é a DAQUELE estado — prova de que a rota lê `Caso.estado`,
    # nunca um texto único de "sem liberação".
    assert "consentimento" in corpo["mensagem"].lower()


def test_ac25_pdf_continua_recusado_sem_snapshot_liberado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-25`: "nem em tela nem em PDF" — reforço explícito de que a rota
    de PDF (T-63, já coberta acima) permanece `404` sem liberação registrada,
    o mesmo caso de dados desta bateria de testes de T-64."""
    caso = _caso_fabricado(snapshot_liberado_id=None)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(_snapshot_real())

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/plano/pdf")

    assert resposta.status_code == 404


def test_isolamento_por_caso_e_respeitado_na_rota_de_tela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério de aceite 3: `RF-02`/`AC-03` — sessão sem `CASO_ID`
    correspondente recebe `404` na rota de tela, mesmo mecanismo de
    `app/http/isolamento.py` (T-31) que já protege a rota de PDF."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/caso/CASO-DE-OUTRA-CONTA/api/plano")

    assert resposta.status_code == 404


def test_t267_ac141_fonte_de_comprovacao_por_divida_no_plano(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RF-92` (`T-267`): cada dívida da ordem traz o rótulo do nível da sua
    fonte, de `textos-canonicos.yaml`, lido das respostas — sem conta sobre
    o snapshot."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    divida_id = caso_completo().DIVIDA_ID
    fonte = Resposta(
        CASO_ID=caso.CASO_ID,
        ID_PERGUNTA="FONTE_DADO",
        item_id=divida_id,
        valor="ATENDIMENTO_CREDOR",
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )

    class _Respostas:
        def listar_do_caso(self, _caso_id: str) -> tuple[Resposta, ...]:
            return (fonte,)

    class _Itens:
        def listar_do_caso(
            self, _caso_id: str, incluir_removidos: bool = False
        ) -> tuple[ItemRepetido, ...]:
            return (
                ItemRepetido(
                    item_id=divida_id,
                    CASO_ID=caso.CASO_ID,
                    escopo=EscopoRepeticao.DIVIDA_ID,
                    removido_em=None,
                    criado_em=datetime(2026, 9, 30, tzinfo=UTC),
                ),
            )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=_RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1"),
        repositorio_snapshots=_RepositorioSnapshotsDublê(snapshot),
    )
    aplicacao = cliente.app
    assert isinstance(aplicacao, FastAPI)
    aplicacao.dependency_overrides[obter_repositorio_respostas] = _Respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = _Itens

    ordem = cliente.get(f"/caso/{caso.CASO_ID}/api/plano").json()["plano"]["ordem"]

    assert [p["fonte"] for p in ordem if p["DIVIDA_ID"] == divida_id] == [
        carregar_textos_canonicos().rotulos_de_comprovacao["PENDENTE_DE_CONFIRMACAO"]
    ]


@pytest.mark.parametrize("seguro", ["SIM", "NAO"])
def test_t245_orientacao_do_seguro_so_para_divida_com_seguro(
    monkeypatch: pytest.MonkeyPatch, seguro: str
) -> None:
    """`RF-82` (`T-245`, `DE-03`): a orientação sobre o seguro prestamista,
    de `textos-canonicos.yaml`, aparece só na dívida com
    `SEGURO_PRESTAMISTA = SIM` — lida das respostas, como a fonte."""
    snapshot = _snapshot_real()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    divida_id = caso_completo().DIVIDA_ID
    resposta = Resposta(
        CASO_ID=caso.CASO_ID,
        ID_PERGUNTA="SEGURO_PRESTAMISTA",
        item_id=divida_id,
        valor=seguro,
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )

    class _Respostas:
        def listar_do_caso(self, _caso_id: str) -> tuple[Resposta, ...]:
            return (resposta,)

    class _Itens:
        def listar_do_caso(
            self, _caso_id: str, incluir_removidos: bool = False
        ) -> tuple[ItemRepetido, ...]:
            return (
                ItemRepetido(
                    item_id=divida_id,
                    CASO_ID=caso.CASO_ID,
                    escopo=EscopoRepeticao.DIVIDA_ID,
                    removido_em=None,
                    criado_em=datetime(2026, 9, 30, tzinfo=UTC),
                ),
            )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=_RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1"),
        repositorio_snapshots=_RepositorioSnapshotsDublê(snapshot),
    )
    aplicacao = cliente.app
    assert isinstance(aplicacao, FastAPI)
    aplicacao.dependency_overrides[obter_repositorio_respostas] = _Respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = _Itens

    ordem = cliente.get(f"/caso/{caso.CASO_ID}/api/plano").json()["plano"]["ordem"]

    orientacao = carregar_textos_canonicos().orientacao_seguro_prestamista
    assert orientacao.startswith("Esta dívida tem seguro prestamista.")
    esperado = orientacao if seguro == "SIM" else None
    assert {p["DIVIDA_ID"]: p["orientacao_seguro"] for p in ordem}[divida_id] == esperado
    assert all(p["orientacao_seguro"] is None for p in ordem if p["DIVIDA_ID"] != divida_id)


def _plano_do_aluno(monkeypatch: pytest.MonkeyPatch, snapshot: SnapshotOrdem) -> dict[str, Any]:
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=_RepositorioCasosDublê(caso, "CONTA-PDF-ROTA-1"),
        repositorio_snapshots=_RepositorioSnapshotsDublê(snapshot),
    )
    plano: dict[str, Any] = cliente.get(f"/caso/{caso.CASO_ID}/api/plano").json()["plano"]
    return plano


def test_t304_plano_traz_mes_de_quitacao_e_valor_mensal_destinado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T-304` (`DE-08`, `RF-96`): por dívida, o mês previsto de quitação —
    LIDO do cronograma gravado do cenário recomendado — e, no plano, o valor
    mensal destinado (`CAPACIDADE_ATAQUE_CONSERVADORA`), formatado."""
    snapshot = _snapshot_real()
    cenario = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]
    esperado = {d: m.estado_final.mes for m in cenario.meses for d in m.quitacoes}
    assert esperado, "o caso completo quita a dívida dentro do horizonte"

    plano = _plano_do_aluno(monkeypatch, snapshot)

    assert {p["DIVIDA_ID"]: p["mes_de_quitacao"] for p in plano["ordem"]} == esperado
    assert plano["valor_mensal_destinado"] == formatar_dinheiro_br(
        snapshot.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    )


def test_t304_sem_quitacao_no_cronograma_o_mes_fica_nao_disponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dívida que não aparece em nenhuma `quitacoes` do cronograma gravado
    (ex.: estourou o horizonte) vai como `None` — "não disponível" na tela,
    nunca um mês estimado."""
    snapshot = _snapshot_real()
    metodo = snapshot.METODO_RECOMENDADO_PIQ
    sem_cronograma = replace(
        snapshot,
        cenarios={**snapshot.cenarios, metodo: replace(snapshot.cenarios[metodo], meses=())},
    )

    plano = _plano_do_aluno(monkeypatch, sem_cronograma)

    assert [p["mes_de_quitacao"] for p in plano["ordem"]] == [None] * len(plano["ordem"])


# Valores que são CÓDIGO, não texto ao aluno: `nao_projetados[].motivo`.
# `T-306` (absorvida por `T-326`) tirou `cenario` e `descricao` daqui — hoje
# são rótulo e texto em português. Qualquer outro campo com identificador
# falha.
_CHAVES_DE_CODIGO = frozenset({"motivo"})
_IDENTIFICADOR = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")


def _identificadores(valor: object, chave: str = "") -> list[str]:
    if isinstance(valor, dict):
        return [i for k, v in valor.items() for i in _identificadores(v, k)]
    if isinstance(valor, list):
        return [i for v in valor for i in _identificadores(v, chave)]
    if isinstance(valor, str) and chave not in _CHAVES_DE_CODIGO:
        return [f"{chave}: {achado}" for achado in _IDENTIFICADOR.findall(valor)]
    return []


@pytest.mark.parametrize("carregar", [carregar_gab_a, carregar_gab_b, carregar_gab_c, None])
def test_t305_plano_do_aluno_sem_justificativa_tecnica_nem_identificadores(
    monkeypatch: pytest.MonkeyPatch, carregar: Callable[[], EstadoFinanceiro] | None
) -> None:
    """`T-305`: `JUSTIFICATIVA_POSICAO` ("critério: maior BENEFICIO_
    MARGINAL_AMORTIZACAO … (O-01)") não é enviada ao aluno — fica para o
    revisor —, e nenhum valor textual do payload do aluno carrega
    identificador em MAIÚSCULAS_COM_UNDERSCORE."""
    snapshot = (
        _snapshot_real()
        if carregar is None
        else calcular_plano(carregar(), FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL))
    )

    plano = _plano_do_aluno(monkeypatch, snapshot)

    assert all("JUSTIFICATIVA_POSICAO" not in p for p in plano["ordem"])
    assert all(p["explicacao"] for p in plano["ordem"])
    assert _identificadores(plano) == []
