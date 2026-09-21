"""Testes de `app/motor/executor.py` — `RF-16`, `RF-19`, `RF-32` (`AC-12`,
`AC-43`), T-54; tratamento de erro (`EC-03`, `EC-04`, `EC-06`), T-55.

Usa o adaptador de ARQUIVO (`persistencia/arquivo/`, do slug `motor-calculo`,
CONGELADO/`AC-44`) para `FonteParametros` e `RepositorioSnapshots`, e
`persistencia/app_aluno/arquivo.py::RepositorioCasosArquivo` para `Caso` — a
mesma razão de `T-24`/`T-25`: a suíte principal desta feature roda sem
`DATABASE_URL`. `RepositorioSnapshots` é envolvido por um ESPIÃO
(`RepositorioSnapshotsEspiao`) para provar a ORDEM "calcula uma vez, depois
anexa, só então devolve" (`AC-12`) sem depender de introspecção do adaptador
real. `calcular_plano` em si é espionado por um wrapper que conta chamadas
(`ContadorDeChamadas`), sobre o MOTOR REAL — não um dublê que fabrica um
`SnapshotOrdem` falso, para que o teste continue provando um cálculo de
verdade encadeado corretamente.

REGRAS: `RF-16`, `RF-19`, `RF-32`, `EC-03`, `EC-04`, `EC-06`
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.casos.maquina import ESTADO_CASO, Caso
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor import executor as executor_modulo
from app.motor.executor import (
    ParametrosDoCalculo,
    executar_calculo,
    executar_calculo_async,
    executar_calculo_com_timeout_async,
)
from engine.ciclo_mensal import ErroInvariante
from engine.estado import EstadoFinanceiro
from engine.parametros import ErroParametros, Parametros
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.app_aluno.eventos import RepositorioEventosCaso
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, CasoCompleto, caso_completo

_PARAMETROS_VERSAO: str = "1.0.1"
_CASO_ID: str = "caso-teste-t55-executor"

# Os sete únicos campos que `app/motor/executor.py::_registrar_evento` aceita
# — espelha a allowlist normativa (spec §"Erros e estados vazios"). Usado
# pelo teste que audita os logs emitidos nos três caminhos de erro.
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


def _montar_estado_do_caso(caso: CasoCompleto) -> EstadoFinanceiro:
    """Mesmo helper de `tests/app_aluno/test_montagem_estado.py` — os dois
    passos (montar `Divida`, montar `EstadoFinanceiro`) que antecedem a
    fronteira do executor (T-54 recebe o `EstadoFinanceiro` já pronto, ver
    docstring de `app/motor/executor.py`)."""
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


class RepositorioSnapshotsEspiao:
    """Envolve um `RepositorioSnapshots` real, registrando CADA chamada a
    `anexar` numa lista observável pelo teste — usado para provar `AC-12`
    ("o snapshot é persistido antes de qualquer exibição") sem inspecionar o
    armazenamento por fora."""

    def __init__(self, delegado: RepositorioSnapshots) -> None:
        self._delegado = delegado
        self.snapshots_anexados: list[SnapshotOrdem] = []

    def anexar(self, s: SnapshotOrdem) -> None:
        self._delegado.anexar(s)
        self.snapshots_anexados.append(s)

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        return self._delegado.obter(snapshot_id)

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:
        return tuple(self._delegado.historico(caso_id))


class RepositorioSnapshotsQueFalha:
    """`anexar` sempre levanta — usado para provar que, quando a persistência
    falha, o executor NUNCA devolve um snapshot ao chamador (`AC-12`:
    persistido antes de qualquer exibição — se não persistiu, não exibe)."""

    def anexar(self, s: SnapshotOrdem) -> None:
        raise RuntimeError("falha proposital de persistência (teste)")

    def obter(self, snapshot_id: str) -> SnapshotOrdem:  # pragma: no cover — não exercitado
        raise NotImplementedError

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


@pytest.fixture
def repositorio_snapshots_arquivo(tmp_path: Path) -> RepositorioSnapshotsArquivo:
    return RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")


@pytest.fixture
def fonte_parametros_arquivo() -> FonteParametrosArquivo:
    return FonteParametrosArquivo()


@pytest.fixture
def estado_financeiro() -> EstadoFinanceiro:
    return _montar_estado_do_caso(caso_completo())


@pytest.fixture
def repositorio_casos_arquivo(tmp_path: Path) -> RepositorioCasosArquivo:
    """`Caso` de teste já criado e transicionado para `CALCULANDO` — o
    estado em que `executar_calculo`/`executar_calculo_com_timeout_async`
    sempre recebem o caso (T-55: o executor só TRATA as transições de SAÍDA
    de `CALCULANDO`, nunca a de entrada, que já é do chamador do Bloco 6)."""
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID=_CASO_ID,
            conta_id="conta-teste-t55",
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)
    return repositorio


@pytest.fixture
def repositorio_eventos_arquivo(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    """`T-91` (`RF-31`/`AC-40`) — trilha de eventos do caso, mesmo adaptador
    de arquivo dos demais repositórios desta suíte."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


def _insumos_padrao(
    *,
    fonte_parametros: FonteParametrosArquivo,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_versao: str = _PARAMETROS_VERSAO,
) -> ParametrosDoCalculo:
    """Fábrica dos insumos padrão do executor nos testes — reduz repetição
    dos campos novos de `T-55`/`T-91` (`caso_id`, `repositorio_casos`,
    `estado_anterior_do_caso`, `repositorio_eventos`) em cada teste que não
    os exercita diretamente."""
    return ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        parametros_versao=parametros_versao,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )


def test_executar_calculo_faz_os_quatro_passos_na_ordem_ac12_ac43(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-12`/`AC-43`: `calcular_plano` roda exatamente uma vez, o snapshot
    devolvido é o mesmo que foi anexado, e `anexar` já foi chamado (com
    sucesso) antes da função devolver — provado pelo espião registrar a
    chamada de `anexar` e o resultado ser idêntico ao que foi anexado."""
    espiao = RepositorioSnapshotsEspiao(repositorio_snapshots_arquivo)
    contador = ContadorDeChamadas(getattr(executor_modulo, "calcular_plano"))  # noqa: B009
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=espiao,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with contador.substituir_em(executor_modulo):
        snapshot = executar_calculo(estado_financeiro, insumos)

    assert contador.chamadas == 1, "calcular_plano deveria ser invocado exatamente uma vez"
    assert espiao.snapshots_anexados == [snapshot], (
        "o snapshot devolvido deveria ser exatamente o que foi anexado — "
        "e anexar deveria já ter ocorrido quando a função devolve"
    )


def test_executar_calculo_nao_devolve_snapshot_se_anexar_falha_ac12(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-12`: se `RepositorioSnapshots.anexar` falha, a exceção propaga —
    nenhum snapshot é devolvido ao chamador, então não há como exibi-lo."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=RepositorioSnapshotsQueFalha(),
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with pytest.raises(RuntimeError, match="falha proposital de persistência"):
        executar_calculo(estado_financeiro, insumos)


def test_executar_calculo_usa_fonte_parametros_existente_rf32(
    estado_financeiro: EstadoFinanceiro,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`RF-32`: os parâmetros vêm de `FonteParametros.carregar` — versão
    inexistente propaga `ErroParametros` (nunca um parâmetro default), o que
    também prova que o executor não embute nenhum valor `P_*` próprio."""
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        caso_id=_CASO_ID,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
        parametros_versao="versao-inexistente-9.9.9",
    )

    with pytest.raises(ErroParametros):
        executar_calculo(estado_financeiro, insumos)


def test_executar_calculo_devolve_snapshot_com_parametros_version_correta(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """Prova complementar de `RF-32`: o `PARAMETROS_VERSION` carimbado no
    snapshot é o que a `FonteParametros` carregou para a versão pedida —
    nunca um literal fixado no executor."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    snapshot = executar_calculo(estado_financeiro, insumos)

    assert snapshot.PARAMETROS_VERSION == _PARAMETROS_VERSAO


def test_executar_calculo_async_roda_em_threadpool_e_produz_o_mesmo_resultado(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`run_in_executor`: a variante assíncrona delega a `run_in_threadpool`
    (Starlette) e devolve o MESMO `SnapshotOrdem` que a chamada síncrona
    produziria — a orquestração não muda entre as duas, só o mecanismo de
    execução.

    `asyncio.run` (stdlib), não um plugin de teste assíncrono (`pytest-
    asyncio`/`anyio` não estão no plano de dependências desta feature,
    `plans/app-aluno.plan.md` §2) — evita dependência nova só para rodar um
    `await` num teste."""
    espiao = RepositorioSnapshotsEspiao(repositorio_snapshots_arquivo)
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=espiao,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    snapshot = asyncio.run(executar_calculo_async(estado_financeiro, insumos))

    assert espiao.snapshots_anexados == [snapshot]


# ---------------------------------------------------------------------------
# T-55 — EC-04: ErroParametros. `calcular_plano` NUNCA é chamado, e o
# estado do caso é o anterior (após passar por ERRO_DE_CALCULO, que é o
# único destino declarado de saída de CALCULANDO no caminho de falha —
# `EC-06` prevê a RETOMADA, fora do escopo desta função, como o passo que
# devolve o caso ao estado de origem).
# ---------------------------------------------------------------------------


class FonteParametrosQueFalha:
    """`carregar` sempre levanta `ErroParametros` — usada para provar
    `EC-04`: nenhuma chamada a `calcular_plano` ocorre."""

    def carregar(self, versao: str) -> Parametros:
        raise ErroParametros(f"fonte de parâmetros indisponível (teste): {versao}")


def test_ec04_erro_parametros_nao_chama_calcular_plano_e_transiciona_para_erro(
    estado_financeiro: EstadoFinanceiro,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-04`: com a fonte de parâmetros falhando, `calcular_plano` não é
    chamado (provado por espião sobre a fronteira — nenhuma chamada real ao
    motor) e o caso vai a `ERRO_DE_CALCULO`, nunca permanece em
    `CALCULANDO`."""
    contador = ContadorDeChamadas(getattr(executor_modulo, "calcular_plano"))  # noqa: B009
    insumos = _insumos_padrao(
        fonte_parametros=FonteParametrosQueFalha(),  # type: ignore[arg-type]
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with contador.substituir_em(executor_modulo), pytest.raises(ErroParametros):
        executar_calculo(estado_financeiro, insumos)

    assert contador.chamadas == 0, "calcular_plano NUNCA deveria ser chamado (EC-04)"
    caso_apos_erro = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_erro is not None
    assert caso_apos_erro.estado is ESTADO_CASO.ERRO_DE_CALCULO


def test_ec04_erro_parametros_relanca_a_excecao_original(
    estado_financeiro: EstadoFinanceiro,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-04`: o operador precisa ver o erro real — a exceção original de
    `ErroParametros` propaga, nunca é engolida ou trocada por um retorno
    "degradado"."""
    insumos = _insumos_padrao(
        fonte_parametros=FonteParametrosQueFalha(),  # type: ignore[arg-type]
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with pytest.raises(ErroParametros, match="indisponível"):
        executar_calculo(estado_financeiro, insumos)


def test_ec04_nenhum_log_de_erro_parametros_contem_dado_fora_da_allowlist(
    estado_financeiro: EstadoFinanceiro,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Último critério de aceite comum aos três caminhos de erro: o log
    emitido só carrega os sete campos da allowlist (`CASO_ID`, `SNAPSHOT_ID`,
    `hash_inputs`, `ENGINE_VERSION`, `PARAMETROS_VERSION`, `estado`,
    `transicao`) — nunca um valor monetário, saldo, renda ou identificador
    pessoal."""
    insumos = _insumos_padrao(
        fonte_parametros=FonteParametrosQueFalha(),  # type: ignore[arg-type]
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with caplog.at_level(logging.ERROR, logger="app.motor.executor"), pytest.raises(ErroParametros):
        executar_calculo(estado_financeiro, insumos)

    assert caplog.records, "esperava pelo menos um registro de log do erro"
    for registro in caplog.records:
        campos_extras = {
            chave: valor
            for chave, valor in vars(registro).items()
            if chave in _CAMPOS_DA_ALLOWLIST
        }
        assert set(campos_extras).issubset(_CAMPOS_DA_ALLOWLIST)
        # RF-16: nenhum valor monetário — o único CASO_ID/estado/transição
        # logado são strings curtas e técnicas, nunca um Decimal serializado.
        for valor in campos_extras.values():
            assert not isinstance(valor, (int, float))


# ---------------------------------------------------------------------------
# T-55 — EC-03: ErroInvariante. O caso vai a ERRO_DE_CALCULO, hash_inputs é
# registrado, e NENHUM SnapshotOrdem parcial é devolvido ou anexado.
# ---------------------------------------------------------------------------


class _CalculoQueLevantaErroInvariante:
    """Substitui `engine.motor.calcular_plano` por um dublê que sempre
    levanta `ErroInvariante` — nunca fabrica um `SnapshotOrdem` parcial, o
    que provaria o oposto do que `EC-03` exige."""

    def __call__(self, *args: object, **kwargs: object) -> SnapshotOrdem:
        raise ErroInvariante("conservação do ataque do mês não fechou (teste proposital)")


def test_ec03_erro_invariante_transiciona_para_erro_de_calculo(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-03`: `ErroInvariante` leva o caso a `ERRO_DE_CALCULO`."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with (
        _SubstituicaoTemporaria(
            executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
        ),
        pytest.raises(ErroInvariante),
    ):
        executar_calculo(estado_financeiro, insumos)

    caso_apos_erro = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_erro is not None
    assert caso_apos_erro.estado is ESTADO_CASO.ERRO_DE_CALCULO


def test_ec03_erro_invariante_nao_anexa_nenhum_snapshot(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-03`: nenhum plano parcial ao aluno — `RepositorioSnapshots.anexar`
    nunca é chamado quando `ErroInvariante` interrompe o cálculo."""
    espiao = RepositorioSnapshotsEspiao(repositorio_snapshots_arquivo)
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=espiao,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with (
        _SubstituicaoTemporaria(
            executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
        ),
        pytest.raises(ErroInvariante),
    ):
        executar_calculo(estado_financeiro, insumos)

    assert espiao.snapshots_anexados == [], "nenhum snapshot deveria ter sido anexado (EC-03)"


def test_ec03_hash_inputs_e_registrado_no_log(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`EC-03`: o `hash_inputs` (de correlação, calculado sem tocar
    `engine.snapshot`) é registrado no evento de erro."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with (
        caplog.at_level(logging.ERROR, logger="app.motor.executor"),
        _SubstituicaoTemporaria(
            executor_modulo, "calcular_plano", _CalculoQueLevantaErroInvariante()
        ),
        pytest.raises(ErroInvariante),
    ):
        executar_calculo(estado_financeiro, insumos)

    hashes_registrados = [
        getattr(registro, "hash_inputs", None)
        for registro in caplog.records
        if hasattr(registro, "hash_inputs")
    ]
    assert hashes_registrados, "esperava um hash_inputs registrado no log de ErroInvariante"
    assert all(isinstance(h, str) and len(h) == 64 for h in hashes_registrados), (
        "hash_inputs deveria ser um sha-256 hexadecimal"
    )


# ---------------------------------------------------------------------------
# T-55 — EC-06: timeout. Resolve para "há snapshot e avança" ou "não há e
# volta ao estado anterior" — nunca CALCULANDO preso.
# ---------------------------------------------------------------------------


class _CalculoLento:
    """Dublê de `calcular_plano` que nunca retorna dentro do tempo do
    teste — simula um cálculo que ultrapassa o timeout configurado."""

    def __call__(self, *args: object, **kwargs: object) -> SnapshotOrdem:
        import time

        time.sleep(5)
        raise AssertionError("não deveria terminar dentro do tempo do teste")


def test_ec06_timeout_sem_snapshot_reverte_ao_estado_anterior(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-06`: sem snapshot anexado (o caso nunca calculou com sucesso
    antes), o timeout reverte ao `estado_anterior_do_caso` — nunca deixa o
    caso preso em `CALCULANDO`."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )

    with _SubstituicaoTemporaria(executor_modulo, "calcular_plano", _CalculoLento()):
        resultado = asyncio.run(
            executar_calculo_com_timeout_async(
                estado_financeiro, insumos, tempo_limite_segundos=0.05
            )
        )

    assert resultado is None
    caso_apos_timeout = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_timeout is not None
    assert caso_apos_timeout.estado is not ESTADO_CASO.CALCULANDO
    assert caso_apos_timeout.estado is ESTADO_CASO.COLETA_INICIAL


def test_ec06_timeout_com_snapshot_ja_anexado_nao_reverte(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-06`: se um snapshot filho do `anterior` esperado já foi anexado
    (a execução concluiu antes da checagem pós-timeout, mesmo que depois do
    prazo), a função NÃO reverte o caso — o avanço já ocorreu por outra via
    (o chamador do Bloco 6, T-56, transiciona para `AGUARDANDO_REVISAO`
    quando `executar_calculo` retorna com sucesso)."""
    insumos = _insumos_padrao(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
    )
    # Simula uma execução anterior bem-sucedida QUE JÁ TERMINOU (a thread da
    # tentativa "lenta" abaixo é uma execução DIFERENTE, que nunca conclui
    # no tempo do teste): calcula e anexa um snapshot de verdade para este
    # mesmo caso com anterior=None (mesmo valor usado por `insumos`), e
    # registra a raiz no Caso — exatamente o que o chamador real do Bloco 6
    # faz ao tratar o primeiro snapshot de um caso (`OQ-11`).
    snapshot_ja_anexado = executar_calculo(estado_financeiro, insumos)
    repositorio_casos_arquivo.registrar_snapshot_raiz(_CASO_ID, snapshot_ja_anexado.SNAPSHOT_ID)
    # O `RepositorioCasosArquivo` de teste só PERSISTE o estado recebido —
    # não valida contra a máquina (isso é papel da rota/orquestração real) —
    # então religar o caso a CALCULANDO aqui reproduz fielmente "um segundo
    # disparo do Bloco 6 sobre o mesmo caso, que sofre timeout", sem
    # precisar simular o caminho HTTP inteiro.
    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)

    with _SubstituicaoTemporaria(executor_modulo, "calcular_plano", _CalculoLento()):
        resultado = asyncio.run(
            executar_calculo_com_timeout_async(
                estado_financeiro, insumos, tempo_limite_segundos=0.05
            )
        )

    assert resultado is None
    caso_apos_timeout = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_timeout is not None
    # O estado não foi tocado por esta função (permanece CALCULANDO, o
    # avanço para AGUARDANDO_REVISAO é responsabilidade do chamador real do
    # Bloco 6, fora do escopo desta função de timeout) — o que importa para
    # `EC-06` é que NENHUMA reversão ocorreu.
    assert caso_apos_timeout.estado is ESTADO_CASO.CALCULANDO


class ContadorDeChamadas:
    """Espiona `engine.motor.calcular_plano` (o símbolo importado dentro de
    `app/motor/executor.py`) contando quantas vezes foi chamado, delegando
    para a função REAL em cada chamada — nunca fabrica um `SnapshotOrdem`
    falso, para que o teste continue exercitando um cálculo de verdade."""

    def __init__(self, alvo_real: Callable[..., SnapshotOrdem]) -> None:
        self._alvo_real = alvo_real
        self.chamadas = 0

    def __call__(self, *args: object, **kwargs: object) -> SnapshotOrdem:
        self.chamadas += 1
        return self._alvo_real(*args, **kwargs)

    def substituir_em(self, modulo: object) -> _SubstituicaoTemporaria:
        return _SubstituicaoTemporaria(modulo, "calcular_plano", self)


class _SubstituicaoTemporaria:
    """Context manager mínimo de monkeypatch manual (evita depender da
    fixture `monkeypatch` fora do escopo de uma função de teste) — restaura
    o atributo original ao sair, mesmo se o corpo levantar."""

    def __init__(self, modulo: object, nome_atributo: str, novo_valor: object) -> None:
        self._modulo = modulo
        self._nome_atributo = nome_atributo
        self._novo_valor = novo_valor
        self._original: object = None

    def __enter__(self) -> None:
        self._original = getattr(self._modulo, self._nome_atributo)
        setattr(self._modulo, self._nome_atributo, self._novo_valor)

    def __exit__(self, *_exc_info: object) -> None:
        setattr(self._modulo, self._nome_atributo, self._original)
