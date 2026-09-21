"""Testes de `POST/GET /revisao/caso/{CASO_ID_REVISAO}/decisao` — a ação de
liberar e reprovar na tela do revisor (`RF-24`, `AC-27`, `EC-12`, T-71).

`RepositorioCasosArquivo`/`RepositorioSnapshotsArquivo` (persistência real de
arquivo, T-24) e `SnapshotOrdem` REAL produzido por `executar_calculo` sobre
a fixture de caso completo (T-53) — mesmo padrão de `tests/app_aluno/
test_rotas_revisao.py`/`test_rotas_revisao_comparacao.py` (T-69/T-70): nenhum
snapshot fabricado à mão. `RepositorioRevisoesArquivo`-equivalente não existe
ainda além do dublê local abaixo (T-71 não introduz um adaptador de arquivo
de revisões — fora do escopo desta tarefa, que só consome `RepositorioRevisoes`
pelo `Protocol` recortado de `app/revisao/fila.py`), então um dublê em
memória cobre o papel de `RepositorioRevisoesDaDecisao`.

Cobre os quatro critérios de aceite de T-71:

1. Liberar e reprovar gravam `RegistroRevisao` com autor e data — o autor é
   sempre o `conta_id` da sessão do revisor (`exigir_papel_revisor`), nunca
   um campo do formulário: o teste envia um `POST` sem NENHUM campo `autor`
   e confirma que o registro gravado carrega o `conta_id` da sessão.
2. Não existe rota de edição nem de remoção de registro de revisão —
   verificado enumerando `app.routes` (mesmo padrão de `test_mecanismo_
   isolamento.py::rotas_sem_isolamento_por_caso`, T-32): nenhum `PUT`,
   `PATCH` ou `DELETE` existe sob `/revisao/*`.
3. Após a liberação, o plano fica acessível ao aluno (`GET /caso/{CASO_ID}/
   plano` devolve o conteúdo do plano); após a reprovação, o mesmo caso
   permanece inacessível (a rota do aluno devolve a tela de "em revisão",
   nunca o plano) — provado contra a rota REAL do aluno (`app/http/
   rotas_plano.py`, T-64), não uma checagem interna.
4. A observação do revisor é gravada junto à decisão.

REGRAS: `RF-24`, `AC-27`, `EC-12`
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_papel_revisor, obter_repositorio_casos
from app.http.rotas_plano import obter_repositorio_snapshots as obter_repositorio_snapshots_do_aluno
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_eventos_da_decisao,
    obter_repositorio_revisoes_da_decisao,
    obter_repositorio_snapshots_da_fila,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from app.revisao.fila import DECISAO_REVISAO, RegistroRevisao
from engine.estado import EstadoFinanceiro
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.e2e.test_mecanismo_isolamento import _rotas_api_achatadas
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_PARAMETROS_VERSAO = "1.0.1"
_CONTA_ID_REVISOR = "conta-revisor-teste-t71"


class _RepositorioRevisoesDublê:
    """Dublê em memória de `RepositorioRevisoesDaDecisao` — só `gravar`,
    mesmo recorte mínimo que a rota exige (`app/revisao/fila.py::
    RepositorioRevisoesDaDecisao`). Guarda os registros gravados para os
    testes inspecionarem autor/data/observação."""

    def __init__(self) -> None:
        self.registros: dict[str, RegistroRevisao] = {}

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        self.registros[revisao_id] = registro


def _montar_estado() -> EstadoFinanceiro:
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


def _criar_caso(repositorio_casos: RepositorioCasosArquivo, caso_id: str, conta_id: str) -> None:
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio_casos.criar(
        Caso(
            CASO_ID=caso_id,
            conta_id=conta_id,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.CALCULANDO)


def _calcular_snapshot(
    caso_id: str,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> SnapshotOrdem:
    """Produz um `SnapshotOrdem` REAL e deixa o caso em `AGUARDANDO_REVISAO`
    — mesmo padrão de `tests/app_aluno/test_rotas_revisao.py::
    _calcular_snapshot`."""
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
        anterior=None,
    )
    snapshot = executar_calculo(_montar_estado(), insumos)
    repositorio_casos.registrar_snapshot_raiz(caso_id, snapshot.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.AGUARDANDO_REVISAO)
    return snapshot


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    return RepositorioCasosArquivo(tmp_path / "casos.jsonl")


@pytest.fixture
def repositorio_snapshots(tmp_path: Path) -> RepositorioSnapshotsArquivo:
    return RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")


@pytest.fixture
def repositorio_eventos(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    """`T-91` (`RF-31`/`AC-40`) — trilha de eventos do caso, consumida por
    `liberar`/`reprovar` via `app.casos.progresso.transicionar_e_registrar`."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


@pytest.fixture
def repositorio_revisoes() -> _RepositorioRevisoesDublê:
    return _RepositorioRevisoesDublê()


def _montar_aplicacao(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> FastAPI:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = lambda: (
        repositorio_snapshots
    )
    aplicacao.dependency_overrides[obter_repositorio_revisoes_da_decisao] = lambda: (
        repositorio_revisoes
    )
    aplicacao.dependency_overrides[obter_repositorio_eventos_da_decisao] = lambda: (
        repositorio_eventos
    )
    aplicacao.dependency_overrides[exigir_papel_revisor] = lambda: _CONTA_ID_REVISOR
    # A rota do aluno (GET /caso/{CASO_ID}/plano, T-64) usa seus PRÓPRIOS
    # pontos de injeção (`app.http.isolamento.obter_repositorio_casos`,
    # `app.http.rotas_plano.obter_repositorio_snapshots`) — distintos dos
    # "_da_fila" da rota de revisão (Protocols/instâncias de injeção
    # separadas por módulo, ver app/revisao/fila.py e app/http/rotas_plano.py).
    # Sobrescreve também os dois, com as MESMAS instâncias de repositório,
    # para que a rota do aluno e a rota de revisão enxerguem o mesmo estado
    # gravado — sem isso a rota do aluno tentaria abrir conexão Postgres real.
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots_do_aluno] = lambda: (
        repositorio_snapshots
    )
    return aplicacao


def _montar_cliente_com_sessao(aplicacao: FastAPI, *, conta_id: str) -> TestClient:
    """Cliente com uma sessão de ALUNO aberta (não revisor) — usado para
    verificar acesso à rota do aluno após a decisão. `exigir_caso_da_sessao`
    não é sobrescrita: o isolamento por posse do caso continua real."""

    @aplicacao.post("/_teste/login-aluno")
    def login_aluno(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"status": "ok"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/login-aluno")
    return cliente


# ---------------------------------------------------------------------------
# Critério 1 — liberar e reprovar gravam RegistroRevisao com autor e data; o
# autor é sempre o conta_id da SESSÃO do revisor, nunca um campo do form.
# ---------------------------------------------------------------------------


def test_liberar_grava_registro_com_autor_da_sessao_e_data(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-LIBERAR"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-liberar")
    snapshot = _calcular_snapshot(
        caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    antes = datetime.now(UTC)
    resposta = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=LIBERAR&observacao=Tudo+confere",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    depois = datetime.now(UTC)

    assert resposta.status_code == 200
    assert len(repositorio_revisoes.registros) == 1
    registro = next(iter(repositorio_revisoes.registros.values()))
    # O AUTOR é o conta_id da SESSÃO do revisor (dependency override acima),
    # nunca um campo enviado no corpo do formulário — o POST acima não
    # contém nenhum campo "autor".
    assert registro.autor == _CONTA_ID_REVISOR
    assert registro.decisao is DECISAO_REVISAO.LIBERADO
    assert registro.SNAPSHOT_ID == snapshot.SNAPSHOT_ID
    assert registro.CASO_ID == caso_id
    assert antes <= registro.decidido_em <= depois


def test_reprovar_grava_registro_com_autor_da_sessao_e_data(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-REPROVAR"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-reprovar")
    snapshot = _calcular_snapshot(
        caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=REPROVAR&observacao=Valor+incorreto",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 200
    registro = next(iter(repositorio_revisoes.registros.values()))
    assert registro.autor == _CONTA_ID_REVISOR
    assert registro.decisao is DECISAO_REVISAO.REPROVADO
    assert registro.SNAPSHOT_ID == snapshot.SNAPSHOT_ID
    assert registro.decidido_em is not None


# ---------------------------------------------------------------------------
# Critério 4 — a observação do revisor é gravada junto à decisão.
# ---------------------------------------------------------------------------


def test_observacao_do_revisor_e_gravada_junto_a_decisao(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-OBSERVACAO"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-observacao")
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=LIBERAR&observacao=Observacao+de+teste+especifica",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 200
    registro = next(iter(repositorio_revisoes.registros.values()))
    assert registro.observacao == "Observacao de teste especifica"


def test_observacao_ausente_e_gravada_como_none_nunca_string_vazia(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-SEM-OBSERVACAO"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-sem-observacao")
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=LIBERAR",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 200
    registro = next(iter(repositorio_revisoes.registros.values()))
    assert registro.observacao is None


# ---------------------------------------------------------------------------
# Critério 2 — nenhuma rota de edição nem de remoção de registro de revisão
# existe, verificado enumerando as rotas registradas.
# ---------------------------------------------------------------------------


def test_nenhuma_rota_de_edicao_ou_remocao_existe_sob_revisao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enumera `app.routes` (mesmo mecanismo de `tests/app_aluno/e2e/
    test_mecanismo_isolamento.py::_rotas_api_achatadas`, T-32) e prova que
    nenhuma rota sob `/revisao/*` declara os métodos HTTP `PUT`, `PATCH` ou
    `DELETE` — a única forma de mutar/remover um `RegistroRevisao` seria uma
    rota destes métodos, e nenhuma existe."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    rotas_de_revisao: list[APIRoute] = [
        rota for rota in _rotas_api_achatadas(aplicacao.routes) if rota.path.startswith("/revisao")
    ]
    assert rotas_de_revisao, "esperava ao menos uma rota registrada sob /revisao"

    metodos_de_mutacao_proibidos = {"PUT", "PATCH", "DELETE"}
    for rota in rotas_de_revisao:
        metodos_da_rota = rota.methods or set()
        violacao = metodos_da_rota & metodos_de_mutacao_proibidos
        assert not violacao, f"rota {rota.path!r} declara método de mutação proibido: {violacao}"

    # Reforço: a rota de decisão em si só aceita GET (formulário) e POST
    # (processamento) — nunca um terceiro método de edição/remoção. O
    # FastAPI registra cada `@roteador.get`/`@roteador.post` como uma
    # `APIRoute` própria (mesmo path, `methods` distintos), por isso a união
    # de todos os `methods` das rotas deste path é comparada de uma vez.
    rotas_decisao = [
        rota for rota in rotas_de_revisao if rota.path == "/revisao/caso/{CASO_ID_REVISAO}/decisao"
    ]
    assert rotas_decisao, "esperava a rota de decisão registrada"
    metodos_da_rota_decisao: set[str] = set()
    for rota in rotas_decisao:
        metodos_da_rota_decisao |= rota.methods or set()
    assert {"GET", "POST"} <= metodos_da_rota_decisao
    assert metodos_da_rota_decisao <= {"GET", "HEAD", "POST"}


def test_repositorio_de_revisoes_nao_expoe_atualizar_nem_remover() -> None:
    """Complemento estrutural ao critério 2: a interface de persistência
    (`persistencia.app_aluno.revisoes.RepositorioRevisoes`, T-67) não declara
    `atualizar`/`remover` — mesmo que uma rota futura tentasse mutar um
    registro, não haveria verbo do repositório para chamar."""
    from persistencia.app_aluno.revisoes import RepositorioRevisoes

    metodos = {nome for nome in dir(RepositorioRevisoes) if not nome.startswith("_")}
    assert metodos == {"gravar", "obter", "listar_do_caso"}
    assert "atualizar" not in metodos
    assert "remover" not in metodos


# ---------------------------------------------------------------------------
# Critério 3 — após a liberação, o plano fica acessível ao aluno; após a
# reprovação, não. Provado contra a rota REAL do aluno (GET /caso/{CASO_ID}/
# plano, T-64), não uma checagem interna sobre snapshot_liberado_id.
# ---------------------------------------------------------------------------


def test_apos_liberar_o_plano_fica_acessivel_ao_aluno(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-ACESSO-APOS-LIBERAR"
    conta_id_aluno = "conta-aluno-acesso-liberar"
    _criar_caso(repositorio_casos, caso_id, conta_id_aluno)
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente_revisor = TestClient(aplicacao, base_url="https://teste.local")

    # Antes de liberar: a rota do aluno não mostra o plano (nenhum snapshot
    # liberado ainda) — confirma a premissa do teste.
    cliente_aluno = _montar_cliente_com_sessao(aplicacao, conta_id=conta_id_aluno)
    resposta_antes = cliente_aluno.get(f"/caso/{caso_id}/api/plano")
    assert resposta_antes.status_code == 200
    assert "Sua ordem projetada de quitação" not in resposta_antes.text

    resposta_decisao = cliente_revisor.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=LIBERAR",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resposta_decisao.status_code == 200

    # Depois de liberar: a MESMA rota do aluno agora mostra o plano — prova
    # de acesso via o caminho real, não uma leitura interna de
    # snapshot_liberado_id.
    resposta_depois = cliente_aluno.get(f"/caso/{caso_id}/api/plano")
    assert resposta_depois.status_code == 200
    assert "Sua ordem projetada de quitação" in resposta_depois.text

    caso_apos = repositorio_casos.buscar(caso_id)
    assert caso_apos is not None
    assert caso_apos.estado is ESTADO_CASO.PLANO_LIBERADO


def test_apos_reprovar_o_plano_nao_fica_acessivel_ao_aluno(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-ACESSO-APOS-REPROVAR"
    conta_id_aluno = "conta-aluno-acesso-reprovar"
    _criar_caso(repositorio_casos, caso_id, conta_id_aluno)
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente_revisor = TestClient(aplicacao, base_url="https://teste.local")

    resposta_decisao = cliente_revisor.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=REPROVAR&observacao=Erro+de+calculo",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resposta_decisao.status_code == 200

    # A rota do ALUNO (real, T-64) continua sem mostrar o plano — nenhum
    # snapshot foi liberado, o caso foi para REPROVADO_EM_REVISAO.
    cliente_aluno = _montar_cliente_com_sessao(aplicacao, conta_id=conta_id_aluno)
    resposta_aluno = cliente_aluno.get(f"/caso/{caso_id}/api/plano")
    assert resposta_aluno.status_code == 200
    assert "Sua ordem projetada de quitação" not in resposta_aluno.text

    caso_apos = repositorio_casos.buscar(caso_id)
    assert caso_apos is not None
    assert caso_apos.estado is ESTADO_CASO.REPROVADO_EM_REVISAO
    assert caso_apos.snapshot_liberado_id is None


# ---------------------------------------------------------------------------
# Caminhos não-felizes.
# ---------------------------------------------------------------------------


def test_decisao_invalida_devolve_422_sem_gravar_nada(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    caso_id = "CASO-DECISAO-INVALIDA"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-invalida")
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=NAO_EXISTE",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 422
    assert repositorio_revisoes.registros == {}


def test_segunda_decisao_sobre_o_mesmo_caso_e_recusada_com_409(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    """Reforço de `EC-12`/`AC-27`: uma segunda decisão sobre um caso que já
    saiu de `AGUARDANDO_REVISAO` é recusada na TRANSIÇÃO
    (`ErroRevisaoJaDecidida`) — o `Caso` nunca chega a um segundo estado.
    A ordem de operações de `app.revisao.fila.liberar`/`reprovar` (T-68,
    documentada na docstring daquele módulo) grava o `RegistroRevisao`
    ANTES de transicionar — de propósito, para que um registro "órfão" de
    transição seja sempre auditável, nunca um estado avançado sem registro.
    Por isso a segunda chamada AINDA grava um segundo `RegistroRevisao`
    (a decisão em si é sempre auditada) mas falha ao tentar avançar o
    `Caso`, que permanece exatamente no estado da primeira decisão."""
    caso_id = "CASO-DECISAO-DUPLA"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-dupla")
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    primeira = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=LIBERAR",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert primeira.status_code == 200

    segunda = cliente.post(
        f"/revisao/caso/{caso_id}/decisao",
        content="decisao=REPROVAR",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert segunda.status_code == 409
    # O CASO nunca avança uma segunda vez: permanece PLANO_LIBERADO da
    # primeira decisão, nunca REPROVADO_EM_REVISAO da segunda tentativa.
    caso_apos = repositorio_casos.buscar(caso_id)
    assert caso_apos is not None
    assert caso_apos.estado is ESTADO_CASO.PLANO_LIBERADO


def test_formulario_de_decisao_e_exibido_sem_campo_autor(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    repositorio_revisoes: _RepositorioRevisoesDublê,
) -> None:
    """`GET` do formulário: o autor não aparece em lugar nenhum do que o
    servidor entrega à tela — prova adicional (pelo lado da UI) de que ele
    nunca é solicitado ao revisor como entrada editável.

    **T-144**: a tela virou React e a rota devolve JSON. A garantia é a
    mesma e ficou mais forte: antes bastava não haver `<input name="autor">`
    no template; agora nenhum campo de autor chega ao cliente, então não há
    o que pré-preencher nem sobrescrever. O autor sai da sessão, em
    `processar_decisao`."""
    caso_id = "CASO-DECISAO-FORMULARIO"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-formulario")
    _calcular_snapshot(caso_id, repositorio_casos, repositorio_snapshots, repositorio_eventos)

    aplicacao = _montar_aplicacao(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_eventos=repositorio_eventos,
        repositorio_revisoes=repositorio_revisoes,
    )
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.get(f"/revisao/caso/{caso_id}/decisao")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "autor" not in resposta.text.lower()
    assert corpo["decisoes"] == ["LIBERAR", "REPROVAR"]
