"""Testes de `app/casos/acompanhamento.py::disparar_recalculo`/
`disparar_recalculo_async` — `RF-01`, `RF-19`, `RF-28` (`AC-26`, `AC-30`,
`EC-11`), T-86.

Usa o adaptador de ARQUIVO (`persistencia/arquivo/`, do slug `motor-calculo`,
CONGELADO/`AC-44`) para `FonteParametros` e `RepositorioSnapshots`, e
`persistencia/app_aluno/arquivo.py::RepositorioCasosArquivo` para `Caso` —
mesmo precedente de `tests/app_aluno/test_executor.py` (T-54/T-55): a suíte
principal desta feature roda sem `DATABASE_URL`. `calcular_plano` é o MOTOR
REAL, através do MESMO executor do Bloco 6 (`app/motor/executor.py::
executar_calculo`) — nenhum snapshot fabricado, nenhum dublê de motor.

REGRAS: `RF-01`, `RF-19`, `RF-28`, `AC-26`, `AC-30`, `EC-11`
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.casos.acompanhamento import (
    ErroRecalculoRecusado,
    disparar_recalculo,
    disparar_recalculo_async,
)
from app.casos.maquina import ESTADO_CASO, Caso
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor import executor as executor_modulo
from app.revisao.fila import listar_fila_de_revisao
from engine.estado import EstadoFinanceiro
from engine.tipos import EVENTO_RECALCULO
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, CasoCompleto, caso_completo
from tests.app_aluno.test_executor import ContadorDeChamadas

_PARAMETROS_VERSAO: str = "1.0.1"
_CASO_ID: str = "caso-teste-t86-recalculo"


def _montar_estado_do_caso(caso: CasoCompleto) -> EstadoFinanceiro:
    """Mesmo helper de `tests/app_aluno/test_executor.py` — os dois passos
    que antecedem a fronteira do executor/orquestração de recálculo."""
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


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
    """`Caso` de teste já em `ACOMPANHAMENTO` — o estado de origem real do
    gatilho `recalcula` (`AC-30`/`RF-28`), declarado desde `T-33`."""
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID=_CASO_ID,
            conta_id="conta-teste-t86",
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.ACOMPANHAMENTO)
    return repositorio


@pytest.fixture
def repositorio_eventos_arquivo(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    """`T-91` (`RF-31`/`AC-40`) — trilha de eventos do caso, consumida por
    `disparar_recalculo`/`disparar_recalculo_async` via
    `app.casos.progresso.transicionar_e_registrar`."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


def _primeiro_snapshot(
    estado: EstadoFinanceiro,
    fonte_parametros: FonteParametrosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Monta o snapshot RAIZ do caso (`versao=1`, sem `anterior`) pelo MESMO
    executor do Bloco 6 — reproduz fielmente "o caso já tem um plano
    liberado e está em `ACOMPANHAMENTO`", a pré-condição real de
    `disparar_recalculo`. Transiciona o caso por COLETA_INICIAL → CALCULANDO
    → ACOMPANHAMENTO (saltando os estados intermediários por atribuição
    direta do adaptador de arquivo, que não valida contra a máquina — mesmo
    artifício de `tests/app_aluno/test_executor.py::
    test_ec06_timeout_com_snapshot_ja_anexado_nao_reverte`), só para chegar
    ao ponto de partida que este módulo de teste precisa: um caso em
    ACOMPANHAMENTO com um snapshot raiz já anexado."""
    from app.motor.executor import ParametrosDoCalculo, executar_calculo

    repositorio_casos.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)
    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    snapshot_raiz = executar_calculo(estado, insumos)
    repositorio_casos.registrar_snapshot_raiz(_CASO_ID, snapshot_raiz.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(_CASO_ID, ESTADO_CASO.ACOMPANHAMENTO)


# ---------------------------------------------------------------------------
# AC-30 — versao = anterior.versao + 1, snapshot_anterior_id = anterior.
# SNAPSHOT_ID, e o anterior permanece íntegro e recuperável.
# ---------------------------------------------------------------------------


def test_ac30_recalculo_encadeia_versao_e_snapshot_anterior_id(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-30`: duas chamadas encadeadas (versao 1 → versao 2) — o segundo
    snapshot aponta para o primeiro, e o primeiro permanece intacto e
    recuperável via `RepositorioSnapshots.historico`."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None
    assert caso.snapshot_raiz_id is not None

    historico_antes = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)
    assert len(historico_antes) == 1
    snapshot_anterior = historico_antes[0]
    assert snapshot_anterior.versao == 1
    assert snapshot_anterior.snapshot_anterior_id is None

    snapshot_recalculado = disparar_recalculo(
        estado=estado_financeiro,
        caso=caso,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert snapshot_recalculado.versao == snapshot_anterior.versao + 1
    assert snapshot_recalculado.snapshot_anterior_id == snapshot_anterior.SNAPSHOT_ID

    # O snapshot anterior permanece íntegro e recuperável — o histórico
    # cresce (append-only), nunca sobrescreve a entrada já existente.
    # Comparação por SNAPSHOT_ID/versao/encadeamento (não por igualdade
    # estrutural do dataclass inteiro): o `EstadoFinanceiro` embutido em
    # `estado_inputs` sofre ida-e-volta pelo adaptador de arquivo — que
    # desserializa `Desconhecido.DESCONHECIDO` como a `str` equivalente em
    # alguns campos —, uma particularidade do adaptador de teste alheia aos
    # critérios desta tarefa (identidade e encadeamento do snapshot).
    historico_depois = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)
    assert len(historico_depois) == 2
    assert historico_depois[0].SNAPSHOT_ID == snapshot_anterior.SNAPSHOT_ID
    assert historico_depois[0].versao == snapshot_anterior.versao
    assert historico_depois[1].SNAPSHOT_ID == snapshot_recalculado.SNAPSHOT_ID
    assert historico_depois[1].versao == snapshot_recalculado.versao
    assert historico_depois[1].snapshot_anterior_id == historico_depois[0].SNAPSHOT_ID


# ---------------------------------------------------------------------------
# AC-26 — o snapshot de recálculo entra na fila de revisão como qualquer
# outro.
# ---------------------------------------------------------------------------


def test_ac26_snapshot_de_recalculo_entra_na_fila_de_revisao(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-26`: depois do recálculo, o caso está em `AGUARDANDO_REVISAO`
    (mesma transição de sucesso do Bloco 6, `snapshot_anexado`) e
    `listar_fila_de_revisao` — o MESMO mecanismo de fila do Bloco 6, sem
    lógica nova — devolve o snapshot recalculado como item da fila."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None

    snapshot_recalculado = disparar_recalculo(
        estado=estado_financeiro,
        caso=caso,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    # `disparar_recalculo` não transiciona AGUARDANDO_REVISAO por si só —
    # essa transição de SUCESSO é do CHAMADOR (mesmo padrão de
    # `app/http/rotas_calculo.py::_executar_e_avancar` para o Bloco 6,
    # T-56): aqui simulamos exatamente esse chamador.
    from app.casos.maquina import transicionar

    transicionar(ESTADO_CASO.CALCULANDO, ESTADO_CASO.AGUARDANDO_REVISAO)
    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.AGUARDANDO_REVISAO)

    fila = listar_fila_de_revisao(
        [_CASO_ID], repositorio_casos_arquivo, repositorio_snapshots_arquivo
    )

    assert len(fila) == 1
    assert fila[0].CASO_ID == _CASO_ID
    assert fila[0].snapshot.SNAPSHOT_ID == snapshot_recalculado.SNAPSHOT_ID
    assert fila[0].entra_por_politica is True


# ---------------------------------------------------------------------------
# EC-11 — com evento e hash_inputs idêntico, o snapshot é versionado assim
# mesmo.
# ---------------------------------------------------------------------------


def test_ec11_hash_inputs_identico_ainda_versiona_com_evento(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`EC-11`: o MESMO `EstadoFinanceiro` (portanto o MESMO `hash_inputs`)
    usado no primeiro cálculo é reenviado com um evento — o novo snapshot é
    produzido assim mesmo (`versao` avança), nunca suprimido por "nada
    mudou". Prova que `disparar_recalculo` não introduz nenhuma comparação
    de `hash_inputs` que pule a chamada ao executor."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None
    assert caso.snapshot_raiz_id is not None

    snapshot_anterior = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)[-1]

    # O mesmo `estado_financeiro` — nada material mudou — mas com evento.
    snapshot_recalculado = disparar_recalculo(
        estado=estado_financeiro,
        caso=caso,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert snapshot_recalculado.hash_inputs == snapshot_anterior.hash_inputs
    assert snapshot_recalculado.versao == snapshot_anterior.versao + 1
    assert snapshot_recalculado.EVENTO_RECALCULO is EVENTO_RECALCULO.QUITACAO_CONFIRMADA


# ---------------------------------------------------------------------------
# Quarto critério — o recálculo passa pelo MESMO executor do Bloco 6, sem
# segunda via de invocação do motor.
# ---------------------------------------------------------------------------


def test_recalculo_usa_o_mesmo_executor_calcular_plano_uma_unica_vez(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`calcular_plano` (o símbolo importado dentro de `app/motor/
    executor.py`, o MESMO módulo do Bloco 6) é chamado exatamente uma vez —
    nenhuma segunda via de invocação do motor dentro de `disparar_
    recalculo`. Mesmo espião `ContadorDeChamadas` de `tests/app_aluno/
    test_executor.py` (T-54), reaproveitado em vez de duplicado."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None

    contador = ContadorDeChamadas(getattr(executor_modulo, "calcular_plano"))  # noqa: B009

    with contador.substituir_em(executor_modulo):
        disparar_recalculo(
            estado=estado_financeiro,
            caso=caso,
            evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
            fonte_parametros=fonte_parametros_arquivo,
            repositorio_snapshots=repositorio_snapshots_arquivo,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos_arquivo,
            parametros_versao=_PARAMETROS_VERSAO,
        )

    assert contador.chamadas == 1


def test_recalculo_recusa_quando_caso_esta_fora_de_acompanhamento(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """Um caso fora de `ACOMPANHAMENTO` é recusado ANTES de qualquer
    tentativa de cálculo — `transicionar_estado_se` (a mesma trava
    condicional de `T-56`) encontra o `estado` real do repositório já
    diferente de `ACOMPANHAMENTO` e devolve `None`, e `disparar_recalculo`
    levanta `ErroRecalculoRecusado`, nunca uma transição forçada."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None

    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.COLETA_DIRIGIDA)
    caso_fora_de_acompanhamento = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_fora_de_acompanhamento is not None

    with pytest.raises(ErroRecalculoRecusado):
        disparar_recalculo(
            estado=estado_financeiro,
            caso=caso_fora_de_acompanhamento,
            evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
            fonte_parametros=fonte_parametros_arquivo,
            repositorio_snapshots=repositorio_snapshots_arquivo,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos_arquivo,
            parametros_versao=_PARAMETROS_VERSAO,
        )


def test_recalculo_recusa_quando_transicao_condicional_ja_perdeu_a_corrida(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`transicionar_estado_se` devolve `None` quando o `estado` corrente já
    não é `ACOMPANHAMENTO` no momento da gravação — `ErroRecalculoRecusado`
    é levantada, e nenhum cálculo é tentado (mesma trava de concorrência de
    `T-56`)."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None

    # Simula uma segunda chamada perdendo a corrida: o estado real já mudou
    # por fora, mas o objeto `caso` em mãos ainda reflete ACOMPANHAMENTO —
    # `transicionar()` (validação da máquina) passa, mas `transicionar_
    # estado_se` (checagem real no repositório) encontra o estado já
    # diferente e devolve None.
    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)

    with pytest.raises(ErroRecalculoRecusado):
        disparar_recalculo(
            estado=estado_financeiro,
            caso=caso,
            evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
            fonte_parametros=fonte_parametros_arquivo,
            repositorio_snapshots=repositorio_snapshots_arquivo,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos_arquivo,
            parametros_versao=_PARAMETROS_VERSAO,
        )


# ---------------------------------------------------------------------------
# Variante assíncrona — mesma orquestração, mesmo executor (executar_calculo_
# async).
# ---------------------------------------------------------------------------


def test_disparar_recalculo_async_produz_o_mesmo_encadeamento(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`disparar_recalculo_async` delega a `executar_calculo_async` (o MESMO
    executor, variante assíncrona) e produz o mesmo encadeamento de `AC-30`
    (`asyncio.run`, stdlib — mesmo precedente de `tests/app_aluno/
    test_executor.py`, sem dependência nova de teste assíncrono)."""
    _primeiro_snapshot(
        estado_financeiro,
        fonte_parametros_arquivo,
        repositorio_snapshots_arquivo,
        repositorio_casos_arquivo,
        repositorio_eventos_arquivo,
    )
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None
    assert caso.snapshot_raiz_id is not None
    snapshot_anterior = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)[-1]

    snapshot_recalculado = asyncio.run(
        disparar_recalculo_async(
            estado=estado_financeiro,
            caso=caso,
            evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
            fonte_parametros=fonte_parametros_arquivo,
            repositorio_snapshots=repositorio_snapshots_arquivo,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos_arquivo,
            parametros_versao=_PARAMETROS_VERSAO,
        )
    )

    assert snapshot_recalculado.versao == snapshot_anterior.versao + 1
    assert snapshot_recalculado.snapshot_anterior_id == snapshot_anterior.SNAPSHOT_ID
