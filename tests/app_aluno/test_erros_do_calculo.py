"""Caminhos de erro do Bloco 6 pela RESPOSTA AO ALUNO — `RF-16`, `EC-03`,
`EC-04`, `EC-06` (T-58).

**O que este arquivo NÃO repete.** `tests/app_aluno/test_executor.py` (T-54/
T-55) já cobre exaustivamente, no nível de `app/motor/executor.py` chamado
diretamente (sem HTTP), os quatro critérios de aceite desta tarefa:

- `EC-04` (nenhuma chamada a `calcular_plano`, estado permanece o anterior):
  `test_ec04_erro_parametros_nao_chama_calcular_plano_e_transiciona_para_erro`,
  `test_ec04_erro_parametros_relanca_a_excecao_original`.
- `EC-03` (`ERRO_DE_CALCULO`, `hash_inputs` registrado, nenhum snapshot
  parcial anexado): `test_ec03_erro_invariante_transiciona_para_erro_de_
  calculo`, `test_ec03_erro_invariante_nao_anexa_nenhum_snapshot`,
  `test_ec03_hash_inputs_e_registrado_no_log`.
- `EC-06` (nunca preso em `CALCULANDO`): `test_ec06_timeout_sem_snapshot_
  reverte_ao_estado_anterior`, `test_ec06_timeout_com_snapshot_ja_anexado_
  nao_reverte`.
- Allowlist de log (parcial, só o caminho `EC-04`): `test_ec04_nenhum_log_
  de_erro_parametros_contem_dado_fora_da_allowlist`.

Repetir essas provas aqui, chamando `executar_calculo`/`executar_calculo_
com_timeout_async` de novo, seria duplicação — a lógica interna já está
provada. O ângulo que FALTA, e que este arquivo cobre, é o observável a
partir de fora do processo: a RESPOSTA HTTP que o aluno recebe (`app/http/
rotas_calculo.py`, T-56) quando cada um dos três caminhos ocorre durante um
disparo real do Bloco 6 sobre um caso COMPLETO (fixture `caso_completo`,
T-53) — e uma auditoria de log sobre esse cenário mais realista, cobrindo
também `EC-03`/`EC-06` (que `test_executor.py` não audita quanto à
allowlist, só `EC-04`).

Os três testes:

1. `EC-04` via `FonteParametrosArquivo` real com versão inexistente
   (`ErroParametros` de verdade, não um dublê) — a resposta ao aluno não
   contém plano parcial, nenhum snapshot é anexado e o `GET .../progresso`
   subsequente mostra o caso fora de `CALCULANDO`.
2. `EC-03` via um dublê de `calcular_plano` que levanta `ErroInvariante` —
   a resposta ao aluno (`erro.html`) não contém nenhum valor monetário do
   caso nem "plano"/"ordem"/"parcela", e o `GET .../progresso` mostra
   `ERRO_DE_CALCULO`.
3. `EC-06` via um dublê de `calcular_plano` lento e um timeout curto — o
   `GET .../progresso`, após aguardar a task de fundo concluir, nunca
   mostra `CALCULANDO`: mostra o estado anterior (sem snapshot) ou um
   estado terminal de sucesso (com snapshot).

E um quarto teste, comum aos três caminhos: nenhum log emitido durante os
três cenários contém um valor monetário do caso completo (os literais de
`R$` da fixture, como `"5.000,00"`/`"300,00"`/`"8.000,00"`).

REGRAS: `RF-16`, `EC-03`, `EC-04`, `EC-06`
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
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
from app.motor import executor as executor_modulo
from collection.carga import ColecaoDeRegistros
from collection.respostas import Resposta, RespostasCaso
from engine.ciclo_mensal import ErroInvariante
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.eventos import EventoCaso
from persistencia.app_aluno.itens import ItemRepetido
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    PARAMETROS_EXTERNOS_PADRAO,
    caso_completo,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-t58-nao-usar-em-producao"
_CASO_ID = "CASO-T58-ERROS"
_CONTA_ID = "CONTA-T58-ERROS"

# Fragmentos monetários de verdade da fixture `caso_completo` — usados pelo
# teste de allowlist de log para provar que NENHUM deles vaza, nos três
# caminhos de erro, no texto de qualquer registro de log emitido.
_FRAGMENTOS_MONETARIOS_DO_CASO: tuple[str, ...] = ("5.000,00", "300,00", "8.000,00", "6.500,00")

# Os sete únicos campos que `app/motor/executor.py::_registrar_evento` aceita
# — mesma allowlist normativa espelhada em `tests/app_aluno/test_executor.py`
# (`_CAMPOS_DA_ALLOWLIST`). Usada para separar os campos EXTRA que este
# módulo registra dos atributos internos que todo `logging.LogRecord` do
# Python já carrega (`created`, `msg`, `args`, `levelno`, ... — infraestrutura
# do próprio `logging`, nunca dado de negócio, e por isso fora do escopo
# desta auditoria).
_CAMPOS_DA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "CASO_ID",
        "SNAPSHOT_ID",
        "hash_inputs",
        "ENGINE_VERSION",
        "PARAMETROS_VERSION",
        "estado",
        "transicao",
    }
)


# ---------------------------------------------------------------------------
# Dublês em memória — mesmo padrão de `tests/app_aluno/test_rotas_calculo.py`
# (T-56), reduzidos ao que os três cenários de erro exigem.
# ---------------------------------------------------------------------------


class _RepositorioCasosDublê:
    """Único `Caso` mutável — mesma semântica de `transicionar_estado`/
    `transicionar_estado_se` do dublê de T-56, reaproveitada aqui para não
    depender de Postgres nem do adaptador de arquivo (que já é T-24)."""

    def __init__(self, caso_inicial: Caso) -> None:
        self._caso = caso_inicial

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == _CONTA_ID

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
    def __init__(self, respostas: tuple[Resposta, ...]) -> None:
        self._respostas = respostas

    def gravar(self, resposta: Resposta) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return self._respostas


class _RepositorioItensDublê:
    def __init__(self, itens: tuple[ItemRepetido, ...]) -> None:
        self._itens = itens

    def proximo_identificador(self, CASO_ID: str, escopo: object) -> str:  # pragma: no cover
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
    """Guarda snapshots anexados em lista — usado para provar `EC-03`
    ("resposta ao aluno não contém plano parcial") por FORA: nenhum snapshot
    chega a existir neste repositório."""

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
    caso, mesmo papel de `_RepositorioSnapshotsDublê`."""

    def __init__(self) -> None:
        self.eventos: list[EventoCaso] = []

    def registrar(self, evento: EventoCaso) -> None:
        self.eventos.append(evento)

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(e for e in self.eventos if e.CASO_ID == caso_id)


class _ParametrosExternosFabricados(ParametrosExternosDoBloco6):
    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        return dict(PARAMETROS_EXTERNOS_PADRAO)


class _CalculoQueLevantaErroInvariante:
    """Mesmo dublê de `test_executor.py` — nunca fabrica um `SnapshotOrdem`
    parcial, o oposto do que `EC-03` exige."""

    def __call__(self, *args: object, **kwargs: object) -> SnapshotOrdem:
        raise ErroInvariante("conservação do ataque do mês não fechou (teste t58)")


class _CalculoLento:
    """Dublê de `calcular_plano` que excede qualquer timeout curto de
    teste — usado para exercitar `EC-06` pela rota real."""

    def __call__(self, *args: object, **kwargs: object) -> SnapshotOrdem:
        time.sleep(5)
        raise AssertionError("não deveria terminar dentro do tempo do teste")


def _reduzir_timeout_do_bloco_6(monkeypatch: pytest.MonkeyPatch, segundos: float) -> None:
    """`app/http/rotas_calculo.py::_executar_e_avancar` chama
    `executar_calculo_com_timeout_async(estado, insumos)` SEM passar
    `tempo_limite_segundos` — o parâmetro default (`TEMPO_LIMITE_PADRAO_
    SEGUNDOS`, 30s) já foi resolvido e vinculado à função em tempo de
    definição, então sobrescrever a CONSTANTE do módulo via `monkeypatch.
    setattr(executor_modulo, "TEMPO_LIMITE_PADRAO_SEGUNDOS", ...)` NÃO afeta
    o default já fixado na assinatura de `executar_calculo_com_timeout_
    async`. O parâmetro é keyword-only (depois de `*` na assinatura), então
    seu default mora em `__kwdefaults__`, não em `__defaults__` — o patch
    precisa alterar esse dicionário. `monkeypatch.setattr` restaura o valor
    original ao final do teste, mesma garantia de qualquer outro patch desta
    suíte."""
    kwdefaults = executor_modulo.executar_calculo_com_timeout_async.__kwdefaults__
    assert kwdefaults is not None
    monkeypatch.setitem(kwdefaults, "tempo_limite_segundos", segundos)


def _caso_fabricado(estado: ESTADO_CASO) -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=estado,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _respostas_e_itens_do_caso_completo() -> tuple[tuple[Resposta, ...], tuple[ItemRepetido, ...]]:
    """O caso COMPLETO real de `T-53` (`caso_completo`), com `CASO_ID`/
    `item_id` recarimbados para `_CASO_ID` — os mesmos valores monetários de
    verdade (`SALDO_DEVEDOR_ATUAL`, `PAGAMENTO_MENSAL_EFETIVO`,
    `RENDA_TOTAL_RECORRENTE` etc.) que o teste de allowlist de log audita."""
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
    from collection.registro import EscopoRepeticao

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


@contextmanager
def _montar_aplicacao_de_teste(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fonte_parametros: object,
    repositorio_snapshots: _RepositorioSnapshotsDublê,
    parametros_version_vigente: str = "1.0.1",
) -> Iterator[tuple[TestClient, _RepositorioCasosDublê]]:
    """`with TestClient(...) as cliente:` (nunca `TestClient(...)` solto) é
    ESSENCIAL aqui — mesma descoberta e mesmo padrão de `tests/app_aluno/
    integracao/test_coleta_para_motor.py::_cliente_com_espiao` (T-57): sem o
    `with`, `starlette.testclient.TestClient` abre e fecha um `BlockingPortal`
    (event loop) NOVO a cada `.post()`/`.get()`, o que cancela qualquer
    `asyncio.create_task` ainda pendente — exatamente a task de
    `app/http/rotas_calculo.py::_executar_e_avancar` que trata os três
    caminhos de erro desta tarefa. Usar `with` mantém um ÚNICO portal vivo
    durante todo o teste, permitindo que a execução em segundo plano do
    Bloco 6 rode até o fim entre uma requisição e a próxima (`_aguardar_
    saida_de_calculando`, abaixo, é quem dá ao loop a chance de avançar)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", parametros_version_vigente)

    respostas, itens = _respostas_e_itens_do_caso_completo()
    repositorio_casos = _RepositorioCasosDublê(_caso_fabricado(ESTADO_CASO.COLETA_INICIAL))
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
    # de eventos — dublê novo por chamada, nenhum teste desta suíte precisa
    # inspecioná-lo (o foco é RF-16/EC-03/EC-04/EC-06).
    aplicacao.dependency_overrides[obter_repositorio_eventos] = lambda: _RepositorioEventosDublê()

    @aplicacao.post("/_teste/abrir-sessao")
    def abrir_sessao(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=_CONTA_ID)
        return {"conta_id": _CONTA_ID}

    with TestClient(aplicacao, base_url="https://teste.local") as cliente:
        cliente.post("/_teste/abrir-sessao")
        yield cliente, repositorio_casos


def _aguardar_saida_de_calculando(
    cliente: TestClient, *, tempo_limite_segundos: float = 5.0
) -> str:
    """A rota `POST` agenda a execução em segundo plano (`asyncio.create_
    task`, `app/http/rotas_calculo.py::_executar_e_avancar`) e responde antes
    dela terminar. **A task só avança quando o event loop do `TestClient`
    recebe uma nova requisição para processar** — um `time.sleep` puro na
    thread do teste NUNCA cede controle a esse loop (mesma descoberta de
    `tests/app_aluno/integracao/test_coleta_para_motor.py::_aguardar`, T-57).
    Por isso cada iteração faz um `GET .../calculo/progresso` real (a mesma
    rota de polling que o HTMX do navegador chamaria em produção,
    `report/templates/calculo/progresso.html`) antes de checar o texto de
    novo — é essa requisição que dá ao loop a chance de concluir o próximo
    passo da task em segundo plano.

    **A saída se lê do campo `calculando`, não do texto** (T-144): a rota
    devolve JSON desde que a tela virou React. Procurar a palavra
    "Calculando" no corpo faria este helper retornar na PRIMEIRA iteração,
    antes de a task reverter o caso — e o teste de `EC-06` passaria a medir
    o estado errado, sem esperar nada."""
    limite = time.monotonic() + tempo_limite_segundos
    ultimo_texto = ""
    while time.monotonic() < limite:
        resposta = cliente.get(f"/caso/{_CASO_ID}/calculo/progresso")
        ultimo_texto = resposta.text
        if not resposta.json()["calculando"]:
            return ultimo_texto
        time.sleep(0.01)
    raise AssertionError(f"caso continuou em CALCULANDO além do prazo: {ultimo_texto!r}")


# ---------------------------------------------------------------------------
# EC-04 — fonte de parâmetros que falha: nenhuma chamada a calcular_plano,
# estado permanece o anterior. `FonteParametrosArquivo` REAL com versão
# inexistente (`ErroParametros` de verdade), não um dublê fabricado.
# ---------------------------------------------------------------------------


def test_ec04_fonte_de_parametros_falha_nenhuma_chamada_ao_motor_e_estado_permanece(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contador_chamadas = 0
    # `app/motor/executor.py` não reexporta `calcular_plano` explicitamente
    # (`__all__`) — mesma limitação pré-existente já documentada em
    # `tests/app_aluno/integracao/test_coleta_para_motor.py` (T-57), fora do
    # escopo desta tarefa corrigir.
    calcular_plano_original = executor_modulo.calcular_plano  # type: ignore[attr-defined]

    def _calcular_plano_espiao(*args: object, **kwargs: object) -> SnapshotOrdem:
        nonlocal contador_chamadas
        contador_chamadas += 1
        return calcular_plano_original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(executor_modulo, "calcular_plano", _calcular_plano_espiao)

    snapshots = _RepositorioSnapshotsDublê()
    with _montar_aplicacao_de_teste(
        monkeypatch,
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=snapshots,
        parametros_version_vigente="versao-inexistente-t58-9.9.9",
    ) as (cliente, repositorio_casos):
        resposta_disparo = cliente.post(f"/caso/{_CASO_ID}/calculo")
        assert resposta_disparo.status_code == 200, resposta_disparo.text

        texto_progresso_final = _aguardar_saida_de_calculando(cliente)

        # EC-04: calcular_plano NUNCA foi chamado.
        assert contador_chamadas == 0, "calcular_plano não deveria ser chamado (EC-04)"
        # EC-04: nenhum snapshot anexado.
        assert snapshots.snapshots == []
        # EC-04: o estado observável (GET .../progresso) não é o "sucesso" de
        # um cálculo que nunca ocorreu — é o caminho de erro (ERRO_DE_
        # CALCULO, aqui ainda não retomado pelo operador).
        caso_apos = repositorio_casos.buscar(_CASO_ID)
        assert caso_apos is not None
        assert caso_apos.estado is ESTADO_CASO.ERRO_DE_CALCULO
        assert json.loads(texto_progresso_final)["calculando"] is False


# ---------------------------------------------------------------------------
# EC-03 — ErroInvariante: caso vai a ERRO_DE_CALCULO, hash_inputs registrado,
# resposta ao aluno NÃO contém plano parcial.
# ---------------------------------------------------------------------------


def test_ec03_erro_invariante_resposta_ao_aluno_nao_contem_plano_parcial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
    )

    snapshots = _RepositorioSnapshotsDublê()
    with _montar_aplicacao_de_teste(
        monkeypatch,
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=snapshots,
    ) as (cliente, repositorio_casos):
        resposta_disparo = cliente.post(f"/caso/{_CASO_ID}/calculo")
        assert resposta_disparo.status_code == 200, resposta_disparo.text

        _aguardar_saida_de_calculando(cliente)

        # EC-03: nenhum snapshot foi anexado — não há como a resposta conter
        # um plano, nem parcial.
        assert snapshots.snapshots == []

        resposta_progresso = cliente.get(f"/caso/{_CASO_ID}/calculo/progresso")
        assert resposta_progresso.status_code == 200
        texto = resposta_progresso.text
        # A resposta ao aluno é a tela terminal de erro — nenhum conteúdo de
        # plano (ordem, parcela, método, valor monetário) aparece nela.
        for termo_de_plano in ("ORDEM", "PARCELA", "método", "R$"):
            assert termo_de_plano not in texto, f"'{termo_de_plano}' vazou na resposta de erro"

        caso_apos = repositorio_casos.buscar(_CASO_ID)
        assert caso_apos is not None
        assert caso_apos.estado is ESTADO_CASO.ERRO_DE_CALCULO


def test_ec03_hash_inputs_e_registrado_com_caso_completo_real(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mesmo critério de `test_executor.py::test_ec03_hash_inputs_e_
    registrado_no_log`, provado aqui sobre o cenário mais realista desta
    tarefa (rota HTTP + caso completo), não uma repetição do mesmo teste."""
    monkeypatch.setattr(
        executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
    )

    with _montar_aplicacao_de_teste(
        monkeypatch,
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=_RepositorioSnapshotsDublê(),
    ) as (cliente, _repositorio_casos):
        with caplog.at_level(logging.ERROR, logger="app.motor.executor"):
            cliente.post(f"/caso/{_CASO_ID}/calculo")
            _aguardar_saida_de_calculando(cliente)

    hashes_registrados = [
        getattr(registro, "hash_inputs", None)
        for registro in caplog.records
        if hasattr(registro, "hash_inputs")
    ]
    assert hashes_registrados, "esperava um hash_inputs registrado (EC-03)"
    assert all(isinstance(h, str) and len(h) == 64 for h in hashes_registrados)


# ---------------------------------------------------------------------------
# EC-06 — timeout: nunca preso em CALCULANDO.
# ---------------------------------------------------------------------------


def test_ec06_timeout_nunca_deixa_o_caso_preso_em_calculando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rota real (T-56) não expõe `tempo_limite_segundos` como parâmetro
    configurável por requisição — para exercitar `EC-06` num teste rápido,
    `_reduzir_timeout_do_bloco_6` sobrescreve o default vinculado de
    `executar_calculo_com_timeout_async`, e o dublê `_CalculoLento` garante
    que o cálculo nunca conclui dentro dele."""
    monkeypatch.setattr(executor_modulo, "calcular_plano", _CalculoLento())
    _reduzir_timeout_do_bloco_6(monkeypatch, 0.05)

    snapshots = _RepositorioSnapshotsDublê()
    with _montar_aplicacao_de_teste(
        monkeypatch,
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=snapshots,
    ) as (cliente, repositorio_casos):
        resposta_disparo = cliente.post(f"/caso/{_CASO_ID}/calculo")
        assert resposta_disparo.status_code == 200, resposta_disparo.text

        # `_CalculoLento` bloqueia a THREAD real por 5s (`time.sleep`, via
        # `run_in_threadpool`) — o tempo-limite de espera aqui precisa cobrir
        # isso, mesmo que `EC-06` já deva ter revertido o caso bem antes
        # (assim que `asyncio.wait_for` expira em ~0.05s de tempo do loop).
        texto_final = _aguardar_saida_de_calculando(cliente, tempo_limite_segundos=8.0)

        # EC-06: sem snapshot confirmado, a resolução segura é sempre
        # reverter — nunca CALCULANDO, e aqui, sem sucesso anterior, também
        # nunca um sucesso fabricado.
        assert json.loads(texto_final)["calculando"] is False
        assert snapshots.snapshots == []
        caso_apos = repositorio_casos.buscar(_CASO_ID)
        assert caso_apos is not None
        assert caso_apos.estado is not ESTADO_CASO.CALCULANDO
        # Estado observável ao aluno: o caso voltou ao estado de origem do
        # Bloco 6 (COLETA_INICIAL) — nunca ficou em AGUARDANDO_REVISAO/
        # PLANO_LIBERADO sem que um snapshot de verdade tenha sido anexado.
        assert caso_apos.estado is ESTADO_CASO.COLETA_INICIAL


# ---------------------------------------------------------------------------
# Critério comum aos três caminhos — nenhum valor monetário nos logs.
# ---------------------------------------------------------------------------


def test_nenhum_log_dos_tres_caminhos_de_erro_contem_valor_monetario_do_caso(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Roda os três cenários (EC-04, EC-03, EC-06) em sequência sobre o
    MESMO caso completo (valores monetários reais da fixture, não um dublê
    numérico artificial) e audita TODO o texto de TODO log emitido — não só
    os sete campos nomeados de `_registrar_evento` (já auditados em
    `test_executor.py`), mas o `getMessage()` completo de cada registro,
    incluindo o `str(erro)` das exceções relançadas."""
    with caplog.at_level(logging.DEBUG):
        # EC-04
        with _montar_aplicacao_de_teste(
            monkeypatch,
            fonte_parametros=FonteParametrosArquivo(),
            repositorio_snapshots=_RepositorioSnapshotsDublê(),
            parametros_version_vigente="versao-inexistente-t58-log-9.9.9",
        ) as (cliente, _casos):
            cliente.post(f"/caso/{_CASO_ID}/calculo")
            _aguardar_saida_de_calculando(cliente)

        # EC-03 — caso novo (dependências recriadas do zero a cada chamada).
        monkeypatch.setattr(
            executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
        )
        with _montar_aplicacao_de_teste(
            monkeypatch,
            fonte_parametros=FonteParametrosArquivo(),
            repositorio_snapshots=_RepositorioSnapshotsDublê(),
        ) as (cliente, _casos):
            cliente.post(f"/caso/{_CASO_ID}/calculo")
            _aguardar_saida_de_calculando(cliente)

        # EC-06
        monkeypatch.setattr(executor_modulo, "calcular_plano", _CalculoLento())
        _reduzir_timeout_do_bloco_6(monkeypatch, 0.05)
        with _montar_aplicacao_de_teste(
            monkeypatch,
            fonte_parametros=FonteParametrosArquivo(),
            repositorio_snapshots=_RepositorioSnapshotsDublê(),
        ) as (cliente, _casos):
            cliente.post(f"/caso/{_CASO_ID}/calculo")
            _aguardar_saida_de_calculando(cliente, tempo_limite_segundos=8.0)

    assert caplog.records, "esperava pelo menos um registro de log nos três cenários"
    for registro in caplog.records:
        mensagem_completa = registro.getMessage()
        for fragmento in _FRAGMENTOS_MONETARIOS_DO_CASO:
            assert fragmento not in mensagem_completa, (
                f"valor monetário {fragmento!r} vazou no log: {mensagem_completa!r}"
            )
        # Nenhum campo EXTRA do registro estruturado (`_registrar_evento`) —
        # ou seja, fora dos atributos internos que todo `LogRecord` já
        # carrega — é um `Decimal`/`float`: mesma checagem de `test_
        # executor.py`, repetida aqui sobre os três cenários (não só EC-04).
        campos_extras = {
            chave: valor for chave, valor in vars(registro).items() if chave in _CAMPOS_DA_ALLOWLIST
        }
        assert set(campos_extras).issubset(_CAMPOS_DA_ALLOWLIST)
        for valor in campos_extras.values():
            assert not isinstance(valor, (int, float))
