"""Testes de `GET /caso/{CASO_ID}/coleta-dirigida/bloco-7` — `RF-17`,
`AC-19`, `T-75`.

Mesmo padrão de dublê em memória de `tests/app_aluno/test_rotas_plano.py`:
`_RepositorioCasosDublê`/`_RepositorioSnapshotsDublê`, sem tocar Postgres, e
`SnapshotOrdem` REAL produzido por `calcular_plano` sobre a fixture de caso
completo (T-53), com os booleanos de gate sobrescritos via `dataclasses.
replace` (mesma técnica de `tests/app_aluno/test_acoes.py`, T-74, e de
`tests/app_aluno/test_coleta_dirigida.py`, T-75).

O router `app.http.rotas_coleta_dirigida.roteador` ainda não está registrado
em `app/http/aplicacao.py` (fora do escopo de arquivos declarado por `T-75`)
— os testes montam a aplicação e incluem o router manualmente, mesma técnica
já usada por outras suítes desta feature antes de a integração final existir.

REGRAS: `RF-17`, `AC-19`
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
from app.http.rotas_coleta import obter_repositorio_respostas
from app.http.rotas_coleta_dirigida import (
    obter_colecao_de_registros,
    obter_repositorio_snapshots,
)
from app.http.rotas_coleta_dirigida import roteador as roteador_coleta_dirigida
from app.http.sessao import iniciar_sessao_conta
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import carregar_registros
from collection.respostas import Resposta
from engine.motor import calcular_plano
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_VERSAO_PARAMETROS_REAL = "1.0.1"
_CONTA_ID = "CONTA-COLETA-DIRIGIDA-1"
_DIVIDA_ID_D001 = "D001"
_DIVIDA_ID_D002 = "D002"
_SALDO_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")


class _RepositorioCasosDublê:
    """Mesmo padrão de `tests/app_aluno/test_rotas_plano.py::
    _RepositorioCasosDublê`, restrito aos métodos que esta rota usa."""

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
    """Mesmo padrão de `tests/app_aluno/test_rotas_plano.py::
    _RepositorioSnapshotsDublê`: um único snapshot em memória."""

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


def _snapshot_com_renegociacao_em(divida_id_renegociacao: str | None) -> SnapshotOrdem:
    """Duas dívidas: `D001` sempre elegível; `D002` sobrescrita com
    `RENEGOCIACAO_PENDENTE=True` (Gate 3) quando `divida_id_renegociacao`
    aponta para ela — mesma técnica de `tests/app_aluno/
    test_coleta_dirigida.py`."""
    respostas_d001 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D001)
    divida_d001 = montar_divida(respostas_d001, _DIVIDA_ID_D001)

    respostas_d002 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D002)
    divida_d002 = montar_divida(respostas_d002, _DIVIDA_ID_D002)
    if divida_id_renegociacao == _DIVIDA_ID_D002:
        divida_d002 = replace(
            divida_d002,
            SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
            RENEGOCIACAO_PENDENTE=True,
        )

    caso = caso_completo()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_d001, divida_d002),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def _caso_fabricado(*, snapshot_liberado_id: str | None, caso_id: str = "CASO-BLOCO7-1") -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.COLETA_DIRIGIDA,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot_liberado_id,
        snapshot_liberado_id=snapshot_liberado_id,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _RepositorioRespostasDublê:
    """Dublê em memória — `T-157`.

    Estas rotas só LEEM respostas, para montar o contexto de cada pergunta da
    ficha dirigida; nenhuma delas grava. `gravar` levanta de propósito: se um
    dia a rota passar a escrever, o teste falha alto em vez de gravar num
    dicionário que ninguém confere."""

    def gravar(self, resposta: Resposta) -> None:  # pragma: no cover — não usado
        raise NotImplementedError("as rotas de coleta dirigida não gravam resposta")

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return ()


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: _RepositorioCasosDublê,
    repositorio_snapshots: RepositorioSnapshots,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_coleta_dirigida)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: repositorio_snapshots
    aplicacao.dependency_overrides[obter_colecao_de_registros] = carregar_registros
    # `T-157`: sem este override a rota constrói `RepositorioRespostasSupabase`
    # e tenta alcançar o Postgres real. Estes eram os ÚNICOS testes de rota do
    # slug a exigir banco, e nada em `AC-19` é de integração — o gate deixava
    # de ficar verde sem Docker no ar, e um gate que só passa às vezes ensina
    # quem desenvolve a ignorar vermelho.
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        _RepositorioRespostasDublê
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def test_ac19_bloco_7_so_para_a_divida_com_renegociacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AC-19` — com ação de renegociação só para `D002`, a rota devolve
    `D002` e nenhuma outra dívida."""
    snapshot = _snapshot_com_renegociacao_em(_DIVIDA_ID_D002)
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, _CONTA_ID)
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/coleta-dirigida/bloco-7")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["dividas"] == [_DIVIDA_ID_D002]
    assert _DIVIDA_ID_D001 not in corpo["dividas"]
    assert len(corpo["perguntas"]) > 0


def test_sem_snapshot_liberado_nao_abre_bloco_7(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terceiro critério: sem `snapshot_liberado_id`, nenhuma dívida é
    exibida — a rota nunca inventa uma."""
    snapshot_nao_usado = _snapshot_com_renegociacao_em(_DIVIDA_ID_D002)
    caso = _caso_fabricado(snapshot_liberado_id=None)
    repositorio_casos = _RepositorioCasosDublê(caso, _CONTA_ID)
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot_nao_usado)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/coleta-dirigida/bloco-7")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["dividas"] == []
    assert corpo["perguntas"] == []


def test_ordem_acoes_vazia_nao_abre_bloco_7(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terceiro critério (via `ORDEM_ACOES` vazia, não ausência de
    snapshot): nenhum gate disparado ⇒ nenhuma dívida no Bloco 7."""
    snapshot = _snapshot_com_renegociacao_em(None)
    assert snapshot.ORDEM_ACOES == ()
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, _CONTA_ID)
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/coleta-dirigida/bloco-7")

    assert resposta.status_code == 200
    assert resposta.json()["dividas"] == []


def test_isolamento_recusa_sessao_de_outra_conta(monkeypatch: pytest.MonkeyPatch) -> None:
    """`RF-02`/`AC-03`: uma sessão de outra conta recebe `404`, nunca vê a
    dívida sinalizada de um caso alheio."""
    snapshot = _snapshot_com_renegociacao_em(_DIVIDA_ID_D002)
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    repositorio_casos = _RepositorioCasosDublê(caso, "CONTA-DONA-DO-CASO")
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/caso/{caso.CASO_ID}/coleta-dirigida/bloco-7")

    assert resposta.status_code == 404
