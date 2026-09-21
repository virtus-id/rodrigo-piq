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

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.motor import calcular_plano
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

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
