"""Testes de `app/http/rotas_calculo.py` — a rota e a tela de progresso do
Bloco 6 (`RF-16`, `AC-12`, T-56).

Cobre os quatro critérios de aceite da tarefa:

1. Guarda `OBR` pendente nomeando o que falta.
2. Nenhuma pergunta é exibida durante o Bloco 6.
3. A tela de progresso aparece enquanto `CALCULANDO`, nunca uma tela travada.
4. Dois disparos concorrentes resultam em uma única execução — coberto AQUI
   só pela recusa em memória (rota nunca chama `transicionar_estado_se` duas
   vezes na mesma requisição); a prova real de concorrência contra Postgres
   com duas threads/conexões vive em
   `tests/app_aluno/integracao/test_disparo_concorrente_bloco6.py`
   (`requer_banco`).

Dublês em memória para todos os repositórios/portas, mesmo mecanismo de
injeção que a produção usa (`app.dependency_overrides`) — sem tocar Postgres
nem o motor de verdade (o `calcular_plano` real É usado, porque é uma função
pura e rápida sobre um caso pequeno; a fronteira que este teste audita é a
orquestração HTTP, não o motor).

REGRAS: `RF-16`, `AC-12`
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_calculo import (
    ParametrosExternosDoBloco6,
    obter_colecao_de_registros,
    obter_fonte_parametros,
    obter_parametros_externos_do_bloco6,
    obter_repositorio_eventos,
    obter_repositorio_itens,
    obter_repositorio_respostas,
    obter_repositorio_snapshots,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import Resposta, RespostasCaso
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.eventos import EventoCaso
from persistencia.app_aluno.itens import ItemRepetido
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    PARAMETROS_EXTERNOS_PADRAO,
    caso_completo,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_VERSAO_PARAMETROS_REAL = "1.0.1"


# ---------------------------------------------------------------------------
# Dublês em memória — mesmo padrão de `tests/app_aluno/test_rotas_
# consentimento.py::_RepositorioCasosDublê` (T-36).
# ---------------------------------------------------------------------------


class _RepositorioCasosDublê:
    """Dublê em memória: um único `Caso`, mutável por `transicionar_estado`/
    `transicionar_estado_se` — suficiente para provar a orquestração HTTP."""

    def __init__(self, caso_inicial: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso_inicial
        self._conta_id_da_sessao = conta_id_da_sessao
        self.chamadas_transicionar_estado_se: list[tuple[ESTADO_CASO, ESTADO_CASO]] = []

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao

    def transicionar_estado(
        self, caso_id: str, novo_estado: ESTADO_CASO, agora: datetime | None = None
    ) -> Caso:
        self._caso = _com_estado(self._caso, novo_estado, agora)
        return self._caso

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        self.chamadas_transicionar_estado_se.append((estado_esperado, novo_estado))
        if self._caso.estado is not estado_esperado:
            return None
        self._caso = _com_estado(self._caso, novo_estado, agora)
        return self._caso

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        pass

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui


def _com_estado(caso: Caso, novo_estado: ESTADO_CASO, agora: datetime | None) -> Caso:
    return Caso(
        CASO_ID=caso.CASO_ID,
        conta_id=caso.conta_id,
        estado=novo_estado,
        DATA_REFERENCIA=caso.DATA_REFERENCIA,
        QUESTIONARIO_VERSION=caso.QUESTIONARIO_VERSION,
        snapshot_raiz_id=caso.snapshot_raiz_id,
        snapshot_liberado_id=caso.snapshot_liberado_id,
        ultima_interacao_em=agora or datetime.now(UTC),
        criado_em=caso.criado_em,
    )


class _RepositorioRespostasDublê:
    """Dublê em memória — `listar_do_caso` devolve as respostas fabricadas
    pelo teste; `gravar` não é usado por esta rota (o Bloco 6 não coleta)."""

    def __init__(self, respostas: tuple[Resposta, ...]) -> None:
        self._respostas = respostas

    def gravar(self, resposta: Resposta) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return self._respostas


class _RepositorioItensDublê:
    """Dublê em memória — só `listar_do_caso` é usado por esta rota."""

    def __init__(self, itens: tuple[ItemRepetido, ...] = ()) -> None:
        self._itens = itens

    def proximo_identificador(
        self, CASO_ID: str, escopo: EscopoRepeticao
    ) -> str:  # pragma: no cover
        raise NotImplementedError

    def remover(
        self, caso_id: str, item_id: str, agora: datetime | None = None
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        return self._itens


class _RepositorioSnapshotsDublê:
    """Guarda snapshots em lista — mesmo papel de `RepositorioSnapshots` de
    arquivo (T-24), sem tocar disco."""

    def __init__(self) -> None:
        self.snapshots: list[SnapshotOrdem] = []

    def anexar(self, s: SnapshotOrdem) -> None:
        self.snapshots.append(s)

    def obter(self, snapshot_id: str) -> SnapshotOrdem:  # pragma: no cover
        raise NotImplementedError

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:
        return tuple(self.snapshots)


class _RepositorioEventosDublê:
    """`T-91` (`RF-31`/`AC-40`) — dublê em memória da trilha de eventos do
    caso: guarda em lista, sem tocar disco, mesmo papel de
    `_RepositorioSnapshotsDublê`."""

    def __init__(self) -> None:
        self.eventos: list[EventoCaso] = []

    def registrar(self, evento: EventoCaso) -> None:
        self.eventos.append(evento)

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(e for e in self.eventos if e.CASO_ID == caso_id)


class _ParametrosExternosFabricados(ParametrosExternosDoBloco6):
    """Fornece os quatro parâmetros de `OQ-16` a partir de um valor fixo —
    equivalente à fixture `PARAMETROS_EXTERNOS_PADRAO` de `tests/app_aluno/
    fixtures/caso_completo.py`, usada pelos testes que precisam passar da
    guarda de `OQ-16` para exercitar o restante da rota."""

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        return dict(PARAMETROS_EXTERNOS_PADRAO)


def _caso_fabricado(
    estado: ESTADO_CASO = ESTADO_CASO.COLETA_INICIAL, caso_id: str = "CASO-CALCULO-1"
) -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id="CONTA-1",
        estado=estado,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _registro_obrigatorio_sintetico(ID: str, variavel_gravada: str) -> RegistroPergunta:
    """Registro `OBR` fabricado — mesmo padrão de `tests/app_aluno/
    test_progresso.py::_registro_sintetico` — usado para provar a guarda sem
    depender dos 245 registros reais."""
    return RegistroPergunta(
        ID=ID,
        bloco=99,
        enunciado="Enunciado sintético de teste, nunca uma pergunta real da §11.",
        tipo=TipoResposta.TEXTO_CURTO,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=(),
        VARIAVEL_GRAVADA=variavel_gravada,
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=False,
        salto_consequencia=None,
    )


def _montar_aplicacao_de_teste(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: _RepositorioCasosDublê,
    colecao: ColecaoDeRegistros,
    respostas: tuple[Resposta, ...] = (),
    itens: tuple[ItemRepetido, ...] = (),
    repositorio_snapshots: _RepositorioSnapshotsDublê | None = None,
    parametros_externos: ParametrosExternosDoBloco6 | None = None,
) -> tuple[TestClient, _RepositorioSnapshotsDublê]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", _VERSAO_PARAMETROS_REAL)

    snapshots = repositorio_snapshots or _RepositorioSnapshotsDublê()

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        lambda: _RepositorioRespostasDublê(respostas)
    )
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: _RepositorioItensDublê(itens)
    aplicacao.dependency_overrides[obter_fonte_parametros] = lambda: FonteParametrosArquivo()
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: snapshots
    aplicacao.dependency_overrides[obter_parametros_externos_do_bloco6] = (
        lambda: (parametros_externos or _ParametrosExternosFabricados())
    )
    # T-91 (RF-31/AC-40): a rota agora também exige o repositório da trilha
    # de eventos — dublê novo por chamada, nenhum teste desta suíte precisa
    # inspecioná-lo (o foco é RF-16/AC-12).
    aplicacao.dependency_overrides[obter_repositorio_eventos] = lambda: _RepositorioEventosDublê()

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/abrir-sessao/CONTA-1")
    return cliente, snapshots


# ---------------------------------------------------------------------------
# Critério 1 — a transição é recusada com campo OBR pendente, nomeando o que
# falta.
# ---------------------------------------------------------------------------


def test_disparo_e_recusado_com_obr_pendente_nomeando_o_que_falta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = _registro_obrigatorio_sintetico("T56.OBR01", "VARIAVEL_OBRIGATORIA_TESTE")
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=(registro,))
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos=repositorio_casos, colecao=colecao, respostas=()
    )

    resposta = cliente.post("/caso/CASO-CALCULO-1/calculo")

    assert resposta.status_code == 400
    assert "T56.OBR01" in resposta.text
    # A transição nunca foi tentada: nenhuma chamada a transicionar_estado_se.
    assert repositorio_casos.chamadas_transicionar_estado_se == []
    caso_apos = repositorio_casos.buscar("CASO-CALCULO-1")
    assert caso_apos is not None
    assert caso_apos.estado == ESTADO_CASO.COLETA_INICIAL


def test_disparo_prossegue_quando_obr_esta_respondido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com um caso REAL completo (fixture `caso_completo`, T-53) — nenhuma
    pendência de `OBR`, `EstadoFinanceiro` monta com sucesso — a rota chega a
    tentar (e conseguir) a transição condicional `COLETA_INICIAL →
    CALCULANDO`, nunca recusada por pendência (400)."""
    caso = caso_completo()
    itens = (
        ItemRepetido(
            item_id=caso.DIVIDA_ID,
            CASO_ID="CASO-CALCULO-1",
            escopo=EscopoRepeticao.DIVIDA_ID,
            removido_em=None,
            criado_em=datetime.now(UTC),
        ),
    )
    respostas_com_caso_id = tuple(
        Resposta(
            CASO_ID="CASO-CALCULO-1",
            ID_PERGUNTA=r.ID_PERGUNTA,
            item_id=r.item_id,
            valor=r.valor,
            QUESTIONARIO_VERSION=r.QUESTIONARIO_VERSION,
            respondida_em=r.respondida_em,
        )
        for r in caso.respostas.respostas
    )
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        colecao=colecao,
        respostas=respostas_com_caso_id,
        itens=itens,
    )

    resposta = cliente.post("/caso/CASO-CALCULO-1/calculo")

    assert repositorio_casos.chamadas_transicionar_estado_se == [
        (ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.CALCULANDO)
    ]
    assert resposta.status_code != 400
    assert resposta.status_code != 422


# ---------------------------------------------------------------------------
# Critério 2 — nenhuma pergunta é exibida durante o Bloco 6.
# ---------------------------------------------------------------------------


def test_tela_de_progresso_nao_contem_formulario_de_pergunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tela de progresso não usa `pergunta.html`/`ficha_repetivel.html`:
    nenhum `<form>` de coleta (sem `hx-post=".../resposta"`, sem
    `name="valor"`, sem `<fieldset>`/`<legend>` de pergunta)."""
    caso = caso_completo()
    dividas_ids = (caso.DIVIDA_ID,)
    itens = tuple(
        ItemRepetido(
            item_id=item_id,
            CASO_ID="CASO-CALCULO-1",
            escopo=EscopoRepeticao.DIVIDA_ID,
            removido_em=None,
            criado_em=datetime.now(UTC),
        )
        for item_id in dividas_ids
    )
    respostas_com_caso_id = tuple(
        Resposta(
            CASO_ID="CASO-CALCULO-1",
            ID_PERGUNTA=r.ID_PERGUNTA,
            item_id=r.item_id,
            valor=r.valor,
            QUESTIONARIO_VERSION=r.QUESTIONARIO_VERSION,
            respondida_em=r.respondida_em,
        )
        for r in caso.respostas.respostas
    )
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        colecao=colecao,
        respostas=respostas_com_caso_id,
        itens=itens,
    )

    resposta = cliente.post("/caso/CASO-CALCULO-1/calculo")

    assert resposta.status_code == 200
    assert "hx-post" not in resposta.text
    assert 'name="valor"' not in resposta.text
    assert "<fieldset>" not in resposta.text
    assert "<form" not in resposta.text


def test_get_progresso_nao_contem_formulario_de_pergunta(monkeypatch: pytest.MonkeyPatch) -> None:
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.CALCULANDO), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos=repositorio_casos, colecao=colecao
    )

    resposta = cliente.get("/caso/CASO-CALCULO-1/calculo/progresso")

    assert resposta.status_code == 200
    assert "<form" not in resposta.text
    assert 'name="valor"' not in resposta.text


# ---------------------------------------------------------------------------
# Critério 3 — a tela de progresso aparece enquanto CALCULANDO, nunca uma
# tela travada.
# ---------------------------------------------------------------------------


def test_get_progresso_exibe_progresso_quando_calculando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.CALCULANDO), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos=repositorio_casos, colecao=colecao
    )

    resposta = cliente.get("/caso/CASO-CALCULO-1/calculo/progresso")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == ESTADO_CASO.CALCULANDO.value
    # O cliente continua consultando o servidor, nunca finge que terminou.
    # Antes (Jinja) esse sinal era um `meta refresh`/`hx-get` no HTML; agora
    # é este campo — e ele é uma LEITURA de `Caso.estado`, não uma decisão
    # desta rota (Lei nº 3).
    assert corpo["calculando"] is True
    assert corpo["erro_de_calculo"] is False


@pytest.mark.parametrize(
    "estado_terminal",
    [ESTADO_CASO.AGUARDANDO_REVISAO, ESTADO_CASO.ERRO_DE_CALCULO, ESTADO_CASO.PLANO_LIBERADO],
)
def test_get_progresso_nao_trava_em_estado_terminal(
    monkeypatch: pytest.MonkeyPatch, estado_terminal: ESTADO_CASO
) -> None:
    """Critério 3, segunda metade: qualquer estado diferente de CALCULANDO
    devolve uma tela TERMINAL — nunca a mesma tela de progresso reapresentada
    (o que seria a "tela travada" proibida)."""
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(estado_terminal), conta_id_da_sessao="CONTA-1"
    )

    cliente, _snapshots = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos=repositorio_casos, colecao=colecao
    )

    resposta = cliente.get("/caso/CASO-CALCULO-1/calculo/progresso")

    assert resposta.status_code == 200
    assert "Calculando seu plano" not in resposta.text
    # A tela terminal não reagenda outra checagem — nem meta-refresh nem
    # hx-trigger de polling continuado.
    assert "http-equiv=\"refresh\"" not in resposta.text
    assert "hx-trigger" not in resposta.text


# ---------------------------------------------------------------------------
# Critério 4 (parcial — em memória) — a rota nunca dispara duas transições
# condicionais bem-sucedidas para o mesmo caso na mesma sequência de
# chamadas; a segunda encontra o estado já mudado.
# ---------------------------------------------------------------------------


def test_transicionar_estado_se_recusa_segunda_chamada_quando_estado_ja_mudou() -> None:
    """Prova unitária do dublê (mesma semântica exigida do adaptador real,
    Postgres e arquivo): a segunda chamada de `transicionar_estado_se` com o
    mesmo `estado_esperado`, depois que a primeira já mudou o estado,
    devolve `None` — nunca sobrescreve de novo."""
    repositorio = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL), conta_id_da_sessao="CONTA-1"
    )

    primeira = repositorio.transicionar_estado_se(
        "CASO-CALCULO-1", ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.CALCULANDO
    )
    segunda = repositorio.transicionar_estado_se(
        "CASO-CALCULO-1", ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.CALCULANDO
    )

    assert primeira is not None
    assert primeira.estado == ESTADO_CASO.CALCULANDO
    assert segunda is None
