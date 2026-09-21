"""Teste de integração da costura coleta → motor → snapshot — `RF-16`, `RF-19`,
`AC-12`, `AC-43` (T-57).

Caso completo de fixture (`tests/app_aluno/fixtures/caso_completo.py`, T-53) →
`EstadoFinanceiro` (`app/montagem/estado.py`, já testado isoladamente) →
`calcular_plano` (`engine/motor.py`, motor já verificado por sua própria suíte
de gabaritos/invariantes) → `SnapshotOrdem` no repositório
(`persistencia/arquivo/repositorio_snapshots.py`, T-24). É a COSTURA que este
slug cria, nunca o motor em si — nenhum gabarito numérico é reproduzido aqui.

**Por que a via é HTTP, não a chamada direta de `executar_calculo`.** O
critério de aceite fala literalmente em "resposta HTTP com conteúdo de
plano" — só a rota real (`app/http/rotas_calculo.py::disparar_calculo`, T-56,
já testada por `tests/app_aluno/test_rotas_calculo.py` quanto às quatro
garantias daquela tarefa) produz uma sequência de respostas HTTP observável:
o `POST /caso/{CASO_ID}/calculo` dispara o Bloco 6 e agenda a execução em
segundo plano; o `GET /caso/{CASO_ID}/calculo/progresso`, consultado depois
que a execução termina, é a resposta que measura se algum conteúdo de plano
já vazou antes do snapshot estar persistido. `tests/app_aluno/test_rotas_
calculo.py` já cobre a orquestração HTTP isolada (guarda `OBR`, ausência de
formulário, tela de progresso, disparo único em memória) com dublês para
TODAS as portas — o que falta, e que esta tarefa cobre, é a costura de ponta
a ponta com os adaptadores de ARQUIVO reais (`FonteParametrosArquivo`,
`RepositorioSnapshotsArquivo`) e um espião sobre a fronteira do motor
(`engine.motor.calcular_plano`), sem tocar Postgres.

**Espião sobre a fronteira (critério de aceite 1).** O espião substitui
`app.motor.executor.calcular_plano` — o NOME importado dentro do módulo que
efetivamente chama a função (`from engine.motor import calcular_plano`) — por
um `monkeypatch` que conta as chamadas e delega ao `calcular_plano` real. Não
audita nenhuma função interna do motor (`engine.ciclo_mensal`, `engine.gates`,
...) — só a única fronteira que `app/motor/executor.py` atravessa (`AC-41`,
T-06), exatamente o "espião sobre a fronteira" que o critério pede.

**Adaptador de arquivo, sem `DATABASE_URL` (critério de aceite 4).**
`RepositorioSnapshotsArquivo`/`FonteParametrosArquivo` (T-24, `persistencia/
arquivo/`, CONGELADOS por este slug) — nenhum `psycopg`, nenhuma variável de
ambiente de banco. O arquivo `snapshots.jsonl` vive em `tmp_path` (isolado por
teste, nunca o arquivo do repositório real).

REGRAS: `RF-16`, `RF-19`, `AC-12`, `AC-43`
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.motor.executor as executor_motor
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
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta, RespostasCaso
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.eventos import EventoCaso
from persistencia.app_aluno.itens import ItemRepetido
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import (
    PARAMETROS_EXTERNOS_PADRAO,
    caso_completo,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-t57"
_VERSAO_PARAMETROS_REAL = "1.0.1"
_CASO_ID = "CASO-T57-COSTURA"
_CONTA_ID = "CONTA-T57"

REGRAS = ("RF-16", "RF-19", "AC-12", "AC-43")


# ---------------------------------------------------------------------------
# Dublês mínimos — só o que a fronteira desta costura exige. Casos e itens
# precisam de estado mutável (a rota transiciona COLETA_INICIAL → CALCULANDO
# → AGUARDANDO_REVISAO); respostas e parâmetros externos são fixos, vindos da
# fixture de caso completo (T-53). Repositório de snapshots e fonte de
# parâmetros são os adaptadores de ARQUIVO reais — nunca dublês — porque são
# exatamente o que os critérios de aceite 2 e 4 auditam.
# ---------------------------------------------------------------------------


class _RepositorioCasosDublê:
    """Mesmo padrão de `tests/app_aluno/test_rotas_calculo.py::
    _RepositorioCasosDublê` — um único `Caso` mutável, suficiente para a
    máquina de estados real percorrer COLETA_INICIAL → CALCULANDO →
    AGUARDANDO_REVISAO."""

    def __init__(self, caso_inicial: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso_inicial
        self._conta_id_da_sessao = conta_id_da_sessao

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
        if self._caso.estado is not estado_esperado:
            return None
        self._caso = _com_estado(self._caso, novo_estado, agora)
        return self._caso

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        self._caso = Caso(
            CASO_ID=self._caso.CASO_ID,
            conta_id=self._caso.conta_id,
            estado=self._caso.estado,
            DATA_REFERENCIA=self._caso.DATA_REFERENCIA,
            QUESTIONARIO_VERSION=self._caso.QUESTIONARIO_VERSION,
            snapshot_raiz_id=snapshot_raiz_id,
            snapshot_liberado_id=self._caso.snapshot_liberado_id,
            ultima_interacao_em=self._caso.ultima_interacao_em,
            criado_em=self._caso.criado_em,
        )

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui


# Alias só para não repetir a mesma tupla de 5 elementos em cada assinatura de
# teste/fixture abaixo (cliente, repositório de snapshots real, contagem de
# chamadas do espião, caminho do arquivo de snapshots, dublê de casos).
_ContextoDoTeste = tuple[
    TestClient, RepositorioSnapshotsArquivo, list[int], Path, _RepositorioCasosDublê
]


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
    def __init__(self, respostas: tuple[Resposta, ...]) -> None:
        self._respostas = respostas

    def gravar(self, resposta: Resposta) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return self._respostas


class _RepositorioItensDublê:
    def __init__(self, itens: tuple[ItemRepetido, ...]) -> None:
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


class _ParametrosExternosFabricados(ParametrosExternosDoBloco6):
    """Os quatro parâmetros de `OQ-16`, fornecidos pela fixture de caso
    completo (T-53) — a mesma lacuna documentada em `app/http/
    rotas_calculo.py`, suprida aqui como em `test_rotas_calculo.py`."""

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        return dict(PARAMETROS_EXTERNOS_PADRAO)


class _RepositorioEventosDublê:
    """`T-91` (`RF-31`/`AC-40`) — dublê em memória da trilha de eventos do
    caso; não é um dos adaptadores auditados pelos critérios de aceite desta
    tarefa (1, 2, 4), então um dublê simples basta (mesmo padrão de
    `_RepositorioItensDublê`, acima)."""

    def __init__(self) -> None:
        self.eventos: list[EventoCaso] = []

    def registrar(self, evento: EventoCaso) -> None:
        self.eventos.append(evento)

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(e for e in self.eventos if e.CASO_ID == caso_id)


def _caso_inicial() -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _respostas_e_itens_do_caso_completo() -> tuple[tuple[Resposta, ...], tuple[ItemRepetido, ...]]:
    """Reidrata as respostas da fixture `caso_completo` (T-53) com o
    `CASO_ID` desta rota — mesmo padrão de `test_rotas_calculo.py`."""
    caso = caso_completo()
    respostas = tuple(
        Resposta(
            CASO_ID=_CASO_ID,
            ID_PERGUNTA=r.ID_PERGUNTA,
            item_id=r.item_id,
            valor=r.valor,
            QUESTIONARIO_VERSION=r.QUESTIONARIO_VERSION,
            respondida_em=r.respondida_em,
        )
        for r in caso.respostas.respostas
    )
    itens = (
        ItemRepetido(
            item_id=caso.DIVIDA_ID,
            CASO_ID=_CASO_ID,
            escopo=EscopoRepeticao.DIVIDA_ID,
            removido_em=None,
            criado_em=datetime.now(UTC),
        ),
    )
    return respostas, itens


def _snapshot_ids_no_arquivo(caminho_arquivo: Path) -> tuple[str, ...]:
    """Lê `snapshots.jsonl` diretamente (mesmo formato de `persistencia/
    arquivo/repositorio_snapshots.py::RepositorioSnapshotsArquivo._ler_
    linhas`) e devolve os `SNAPSHOT_ID` presentes.

    `RepositorioSnapshotsArquivo.historico(caso_id)` não serve aqui: aquele
    método busca pela RAIZ da cadeia de um identificador que, nesta feature,
    só é conhecido depois que uma tarefa futura persistir `Caso.snapshot_
    raiz_id` (`registrar_snapshot_raiz` — nenhum caminho de código de T-54/
    T-55/T-56 chama esse método ainda). O `SNAPSHOT_ID` real é derivado de
    `hash_inputs`+`versao` (`engine/snapshot.py::montar_SnapshotOrdem`), não
    do `CASO_ID` — por isso este teste lê o arquivo bruto para confirmar
    presença, sem inventar uma associação caso→raiz que a costura ainda não
    persiste."""
    if not caminho_arquivo.is_file():
        return ()
    ids: list[str] = []
    with caminho_arquivo.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            ids.append(json.loads(linha)["SNAPSHOT_ID"])
    return tuple(ids)


def _aguardar(
    condicao: Callable[[], bool],
    *,
    cliente: TestClient,
    caso_id: str,
    tempo_limite_segundos: float = 5.0,
) -> bool:
    """Polling curto e determinístico: a tarefa de segundo plano
    (`asyncio.create_task`, `app/http/rotas_calculo.py::_executar_e_avancar`)
    só avança quando o event loop do `TestClient` recebe uma nova requisição
    para processar — um `time.sleep` puro na thread do teste NUNCA cede
    controle a esse loop. Por isso cada iteração faz um `GET .../calculo/
    progresso` real (a mesma rota de polling que o HTMX do navegador chamaria
    em produção, `report/templates/calculo/progresso.html`) antes de checar
    `condicao()` de novo — é essa requisição que dá ao loop a chance de
    concluir o próximo passo da task em segundo plano. `calcular_plano`,
    sobre um único caso pequeno, é tipicamente da ordem de milissegundos; o
    tempo-limite de 5s é folga generosa, nunca o caminho feliz do teste."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < tempo_limite_segundos:
        if condicao():
            return True
        cliente.get(f"/caso/{caso_id}/calculo/progresso")
        time.sleep(0.01)
    return condicao()


@pytest.fixture
def _cliente_com_espiao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[_ContextoDoTeste]:
    """Monta a aplicação real com os adaptadores de ARQUIVO (critério de
    aceite 4) e um espião sobre `calcular_plano` na fronteira que `app/motor/
    executor.py` atravessa (critério de aceite 1)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", _VERSAO_PARAMETROS_REAL)

    contagem_chamadas: list[int] = []
    # Mesmo padrão (e mesma limitação pré-existente de `mypy --strict`, já
    # presente em `tests/app_aluno/test_erros_do_calculo.py`) de
    # `app/motor/executor.py::calcular_plano` não ser reexportado
    # explicitamente pelo módulo — fora do escopo desta tarefa corrigir.
    calcular_plano_real = executor_motor.calcular_plano  # type: ignore[attr-defined]

    def _calcular_plano_espiao(*args: object, **kwargs: object) -> SnapshotOrdem:
        contagem_chamadas.append(1)
        return calcular_plano_real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(executor_motor, "calcular_plano", _calcular_plano_espiao)

    caminho_snapshots = tmp_path / "snapshots.jsonl"
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminho_snapshots)
    fonte_parametros = FonteParametrosArquivo()

    respostas, itens = _respostas_e_itens_do_caso_completo()
    repositorio_casos = _RepositorioCasosDublê(_caso_inicial(), conta_id_da_sessao=_CONTA_ID)
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        lambda: _RepositorioRespostasDublê(respostas)
    )
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: _RepositorioItensDublê(itens)
    aplicacao.dependency_overrides[obter_fonte_parametros] = lambda: fonte_parametros
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: repositorio_snapshots
    aplicacao.dependency_overrides[obter_parametros_externos_do_bloco6] = (
        lambda: _ParametrosExternosFabricados()
    )
    # T-91 (RF-31/AC-40): a rota agora também exige o repositório da trilha
    # de eventos — dublê em memória, fora do escopo dos critérios de aceite
    # 1/2/4 auditados por esta suíte.
    aplicacao.dependency_overrides[obter_repositorio_eventos] = lambda: _RepositorioEventosDublê()

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    # `with TestClient(...) as cliente:` (nunca `TestClient(...)` solto) é
    # ESSENCIAL aqui: sem o `with`, `starlette.testclient.TestClient` abre e
    # fecha um `BlockingPortal`/event loop NOVO a cada `.post()`/`.get()`
    # (`TestClient._portal_factory`) — o portal é fechado ao final de CADA
    # requisição, o que cancela qualquer `asyncio.create_task` ainda pendente
    # (exatamente a task de `_executar_e_avancar` que persiste o snapshot e
    # SÓ DEPOIS transiciona o caso). Usar `with` mantém um ÚNICO portal vivo
    # durante todo o teste, permitindo que a execução em segundo plano do
    # Bloco 6 rode até o fim entre uma requisição e a próxima.
    with TestClient(aplicacao, base_url="https://teste.local") as cliente:
        cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
        yield (
            cliente,
            repositorio_snapshots,
            contagem_chamadas,
            caminho_snapshots,
            repositorio_casos,
        )


def test_costura_completa_calcula_uma_vez_e_snapshot_ja_esta_persistido_antes_da_resposta_com_plano(
    _cliente_com_espiao: _ContextoDoTeste,
) -> None:
    """`AC-12` — fixture completa → `EstadoFinanceiro` → `calcular_plano`
    (espiado) → snapshot no repositório de arquivo ANTES de qualquer resposta
    HTTP com conteúdo de plano."""
    cliente, _repositorio_snapshots, contagem_chamadas, caminho_snapshots, repositorio_casos = (
        _cliente_com_espiao
    )

    resposta_post = cliente.post(f"/caso/{_CASO_ID}/calculo")
    assert resposta_post.status_code == 200
    # A resposta do POST é a tela de progresso — nunca contém conteúdo de
    # plano (nenhuma ordem de quitação, custo ou prazo).
    assert "hx-post" not in resposta_post.text
    assert 'name="valor"' not in resposta_post.text

    # A execução do Bloco 6 roda em segundo plano (`asyncio.create_task`,
    # `app/http/rotas_calculo.py::_executar_e_avancar`): primeiro o
    # snapshot é anexado (`executor.py::executar_calculo`), só DEPOIS o
    # caso sai de CALCULANDO. Aguardar a SAÍDA de CALCULANDO é a condição
    # mais forte — é exatamente o instante em que uma resposta HTTP passaria
    # a poder mostrar conteúdo de plano.
    def _caso_saiu_de_calculando() -> bool:
        caso = repositorio_casos.buscar(_CASO_ID)
        return caso is not None and caso.estado is not ESTADO_CASO.CALCULANDO

    concluiu = _aguardar(_caso_saiu_de_calculando, cliente=cliente, caso_id=_CASO_ID)
    assert concluiu, "o Bloco 6 não terminou dentro do tempo-limite do teste"

    caso_final = repositorio_casos.buscar(_CASO_ID)
    assert caso_final is not None
    assert caso_final.estado is ESTADO_CASO.AGUARDANDO_REVISAO

    # Critério de aceite 1: `calcular_plano` foi chamado EXATAMENTE uma vez
    # nesta execução — nenhum retry, nenhuma segunda tentativa de
    # verificação.
    assert len(contagem_chamadas) == 1

    # O snapshot já está no repositório ANTES de qualquer resposta HTTP com
    # conteúdo de plano: no instante em que o caso deixou de estar
    # CALCULANDO (checado acima — o único gatilho que poderia liberar uma
    # resposta com conteúdo de plano), o arquivo de snapshots já contém a
    # linha gravada por `anexar` (T-54: `anexar` roda ANTES da transição de
    # saída de CALCULANDO em `_executar_e_avancar`).
    ids_apos_saida_de_calculando = _snapshot_ids_no_arquivo(caminho_snapshots)
    assert len(ids_apos_saida_de_calculando) == 1

    # A única resposta HTTP seguinte possível (`GET .../calculo/progresso`)
    # hoje não expõe nenhum campo do plano em si
    # (`report/templates/calculo/concluido.html` — a apresentação do
    # snapshot é escopo de outra entrega) — confirmado abaixo para que,
    # se essa apresentação for adicionada no futuro, ela só possa aparecer
    # depois do ponto já provado acima.
    resposta_progresso = cliente.get(f"/caso/{_CASO_ID}/calculo/progresso")
    assert resposta_progresso.status_code == 200
    assert "Calculando seu plano" not in resposta_progresso.text
    assert "ORDEM_QUITACAO" not in resposta_progresso.text


def test_snapshot_no_repositorio_foi_gravado_por_anexar(
    _cliente_com_espiao: _ContextoDoTeste,
) -> None:
    """`AC-43` — o snapshot no repositório foi gravado por
    `RepositorioSnapshots.anexar` (T-24), nunca por outro caminho: o
    adaptador de arquivo só grava linhas em `anexar` (não há `INSERT`/escrita
    alternativa em `persistencia/arquivo/repositorio_snapshots.py`), então a
    própria PRESENÇA do snapshot no arquivo, lido de volta por `obter`, já
    prova que passou por `anexar` — não existe outro método de escrita na
    porta `engine.portas.RepositorioSnapshots` para este adaptador chamar."""
    cliente, repositorio_snapshots, _contagem_chamadas, caminho_snapshots, _repositorio_casos = (
        _cliente_com_espiao
    )

    cliente.post(f"/caso/{_CASO_ID}/calculo")
    concluiu = _aguardar(
        lambda: len(_snapshot_ids_no_arquivo(caminho_snapshots)) > 0,
        cliente=cliente,
        caso_id=_CASO_ID,
    )
    assert concluiu, "o Bloco 6 não terminou dentro do tempo-limite do teste"

    ids = _snapshot_ids_no_arquivo(caminho_snapshots)
    assert len(ids) == 1

    # O ÚNICO caminho de escrita do adaptador de arquivo é `anexar` (em
    # modo append, nunca reescrita/truncamento — ver docstring do módulo,
    # V-01). Ler de volta pelo mesmo repositório (`obter`) confirma que o
    # dado persistido é exatamente o que `anexar` gravou: um `SnapshotOrdem`
    # completo, desserializado campo a campo.
    snapshot = repositorio_snapshots.obter(ids[0])
    assert isinstance(snapshot, SnapshotOrdem)
    assert snapshot.SNAPSHOT_ID == ids[0]


def test_snapshot_devolvido_carrega_engine_version_e_parametros_version_nao_vazios(
    _cliente_com_espiao: _ContextoDoTeste,
) -> None:
    """Terceiro critério de aceite: `ENGINE_VERSION` e `PARAMETROS_VERSION`
    (carimbo de versão obrigatório em toda saída do motor, `V-03`,
    `sdd.config.md` §4) não são vazios no snapshot persistido pela costura
    completa."""
    cliente, repositorio_snapshots, _contagem_chamadas, caminho_snapshots, _repositorio_casos = (
        _cliente_com_espiao
    )

    cliente.post(f"/caso/{_CASO_ID}/calculo")
    concluiu = _aguardar(
        lambda: len(_snapshot_ids_no_arquivo(caminho_snapshots)) > 0,
        cliente=cliente,
        caso_id=_CASO_ID,
    )
    assert concluiu, "o Bloco 6 não terminou dentro do tempo-limite do teste"

    ids = _snapshot_ids_no_arquivo(caminho_snapshots)
    snapshot = repositorio_snapshots.obter(ids[0])

    assert snapshot.ENGINE_VERSION != ""
    assert snapshot.PARAMETROS_VERSION != ""
    assert snapshot.PARAMETROS_VERSION == _VERSAO_PARAMETROS_REAL
