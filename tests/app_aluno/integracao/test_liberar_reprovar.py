"""Testes de `app/revisao/fila.py::liberar`/`reprovar` contra Postgres real —
`RF-23`, `RF-24`, `AC-26`, `EC-12` (T-68).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`). A prova de "liberar duas vezes é recusado, nunca produz dois
registros conflitantes" é feita aqui com DUAS THREADS/CONEXÕES de fato
concorrentes contra o mesmo `CASO_ID` — mesmo precedente de
`test_persistencia_casos.py::test_duas_transicoes_concorrentes_nao_
produzem_estados_divergentes` (T-23): o bloqueio `SELECT ... FOR UPDATE`
usado por `transicionar_estado_se` (T-56) é uma propriedade do MVCC do
Postgres, não simulável por dublê de cursor.

Um `SnapshotOrdem` REAL é produzido pela mesma cadeia do motor já usada por
`tests/app_aluno/test_fila_de_revisao.py`/`test_executor.py` (`caso_completo()`
+ `executar_calculo` sobre o adaptador de ARQUIVO) — nunca um dublê que
fabrica um snapshot falso; o motor em si não fala com Postgres, só o
adaptador de casos/revisões usado pela orquestração `liberar`/`reprovar` é
que é o real, contra o banco.

REGRAS: RF-23, RF-24, AC-26, EC-12
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from app.casos.maquina import ESTADO_CASO
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from app.revisao.fila import (
    CLASSIFICACAO_ERRO,
    DECISAO_REVISAO,
    ErroRevisaoJaDecidida,
    liberar,
    reprovar,
)
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.app_aluno.casos import Caso, RepositorioCasosSupabase
from persistencia.app_aluno.eventos import RepositorioEventosCasoSupabase
from persistencia.app_aluno.revisoes import RepositorioRevisoesSupabase
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

pytestmark = pytest.mark.requer_banco

_PARAMETROS_VERSAO: str = "1.0.1"


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _snapshot_real(tmp_path: Path, sufixo: str) -> SnapshotOrdem:
    """Produz um `SnapshotOrdem` REAL, pela mesma cadeia do motor de
    `tests/app_aluno/test_executor.py`, sobre um `RepositorioCasosArquivo`
    LOCAL (o motor em si não toca Postgres — só a orquestração de
    `liberar`/`reprovar`, testada abaixo contra o banco de verdade)."""
    caso_id_arquivo = f"caso-teste-t68-motor-{sufixo}"
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )

    repositorio_casos_arquivo = RepositorioCasosArquivo(tmp_path / f"casos-{sufixo}.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio_casos_arquivo.criar(
        Caso(
            CASO_ID=caso_id_arquivo,
            conta_id=f"conta-teste-t68-{sufixo}",
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio_casos_arquivo.transicionar_estado(caso_id_arquivo, ESTADO_CASO.CALCULANDO)

    repositorio_snapshots_arquivo = RepositorioSnapshotsArquivo(
        tmp_path / f"snapshots-{sufixo}.jsonl"
    )
    repositorio_eventos_arquivo = RepositorioEventosCasoArquivo(
        tmp_path / f"eventos-{sufixo}.jsonl"
    )
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        caso_id=caso_id_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    return executar_calculo(estado, insumos)


def _conta_e_caso_em_aguardando_revisao(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Cria conta + caso mínimos já em `AGUARDANDO_REVISAO` (FK de
    `app_aluno.revisoes`/pré-condição de `liberar`/`reprovar`), isolado por
    execução (`uuid4`)."""
    conta_id = f"TESTE_T68_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T68_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, 'AGUARDANDO_REVISAO', CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id),
    )
    return caso_id


def test_liberar_registra_decisao_e_preenche_snapshot_liberado_id_no_banco(
    tmp_path: Path,
) -> None:
    """Critério 1, contra Postgres real: após `liberar`, `app_aluno.revisoes`
    tem exatamente um registro `LIBERADO` e `app_aluno.casos.
    snapshot_liberado_id` aponta para o snapshot liberado."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_em_aguardando_revisao(cursor)

    snapshot = _snapshot_real(tmp_path, "liberacao")
    repositorio_revisoes = RepositorioRevisoesSupabase()
    repositorio_casos = RepositorioCasosSupabase()
    repositorio_eventos = RepositorioEventosCasoSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)

    caso_liberado = liberar(
        revisao_id=f"TESTE_T68_REVISAO_{uuid.uuid4().hex}",
        caso_id=caso_id,
        snapshot=snapshot,
        autor="revisor.teste@piq.invalido",
        decidido_em=agora,
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )

    assert caso_liberado.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_liberado.snapshot_liberado_id == snapshot.SNAPSHOT_ID

    registros = repositorio_revisoes.listar_do_caso(caso_id)
    assert len(registros) == 1
    assert registros[0].decisao is DECISAO_REVISAO.LIBERADO
    assert registros[0].autor == "revisor.teste@piq.invalido"

    caso_persistido = repositorio_casos.buscar(caso_id)
    assert caso_persistido is not None
    assert caso_persistido.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_persistido.snapshot_liberado_id == snapshot.SNAPSHOT_ID


def test_reprovar_registra_decisao_e_nao_preenche_snapshot_liberado_id_ec12(
    tmp_path: Path,
) -> None:
    """`EC-12`, contra Postgres real: após `reprovar`, o caso vai a
    `REPROVADO_EM_REVISAO`, `snapshot_liberado_id` continua `None`, e a
    revisão gravada é `REPROVADO` com autor e data."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_em_aguardando_revisao(cursor)

    snapshot = _snapshot_real(tmp_path, "reprovacao")
    repositorio_revisoes = RepositorioRevisoesSupabase()
    repositorio_casos = RepositorioCasosSupabase()
    repositorio_eventos = RepositorioEventosCasoSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)

    caso_reprovado = reprovar(
        revisao_id=f"TESTE_T68_REVISAO_{uuid.uuid4().hex}",
        caso_id=caso_id,
        snapshot=snapshot,
        autor="revisor.teste@piq.invalido",
        decidido_em=agora,
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        classificacao_erro=CLASSIFICACAO_ERRO.CALCULO,
    )

    assert caso_reprovado.estado is ESTADO_CASO.REPROVADO_EM_REVISAO
    assert caso_reprovado.snapshot_liberado_id is None

    registros = repositorio_revisoes.listar_do_caso(caso_id)
    assert len(registros) == 1
    assert registros[0].decisao is DECISAO_REVISAO.REPROVADO
    assert registros[0].autor == "revisor.teste@piq.invalido"
    assert registros[0].decidido_em == agora


def test_duas_liberacoes_concorrentes_do_mesmo_caso_produzem_um_unico_vencedor(
    tmp_path: Path,
) -> None:
    """Critério 3, prova REAL de concorrência: duas THREADS com conexões
    PRÓPRIAS chamam `liberar` ao mesmo tempo sobre o MESMO `CASO_ID`. A
    serialização de `transicionar_estado_se` (T-56, `SELECT ... FOR UPDATE`)
    garante que só UMA das duas grava a transição vencedora — a outra recebe
    `ErroRevisaoJaDecidida`. Ao final: o caso está em `PLANO_LIBERADO` com
    `snapshot_liberado_id` apontando para exatamente uma das duas tentativas
    — nunca dois estados conflitantes."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_em_aguardando_revisao(cursor)

    snapshot_a = _snapshot_real(tmp_path, "concorrente-a")
    snapshot_b = _snapshot_real(tmp_path, "concorrente-b")

    resultados: dict[str, object] = {}
    barreira = threading.Barrier(2)

    def _tentar_liberar(rotulo: str, snapshot: SnapshotOrdem, atraso_segundos: float) -> None:
        repositorio_revisoes = RepositorioRevisoesSupabase()
        repositorio_casos = RepositorioCasosSupabase()
        repositorio_eventos = RepositorioEventosCasoSupabase()
        barreira.wait()
        time.sleep(atraso_segundos)
        try:
            caso = liberar(
                revisao_id=f"TESTE_T68_REVISAO_{rotulo}_{uuid.uuid4().hex}",
                caso_id=caso_id,
                snapshot=snapshot,
                autor=f"revisor-{rotulo}@piq.invalido",
                decidido_em=datetime.now(UTC).replace(microsecond=0),
                repositorio_revisoes=repositorio_revisoes,
                repositorio_casos=repositorio_casos,
                repositorio_eventos=repositorio_eventos,
            )
            resultados[rotulo] = caso
        except ErroRevisaoJaDecidida as erro:
            resultados[rotulo] = erro

    thread_a = threading.Thread(target=_tentar_liberar, args=("a", snapshot_a, 0.0))
    thread_b = threading.Thread(target=_tentar_liberar, args=("b", snapshot_b, 0.05))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    vencedores = [r for r in resultados.values() if not isinstance(r, ErroRevisaoJaDecidida)]
    recusados = [r for r in resultados.values() if isinstance(r, ErroRevisaoJaDecidida)]
    assert len(vencedores) == 1, f"esperava exatamente um vencedor, obteve: {resultados}"
    assert len(recusados) == 1, f"esperava exatamente uma recusa, obteve: {resultados}"

    # O `RegistroRevisao` de AMBAS as tentativas é gravado (T-68: registrar
    # primeiro, ver a nota da docstring do módulo) — mas só UMA transição de
    # PLANO_LIBERADO ocorre, e é essa a garantia que este teste prova: nunca
    # dois estados conflitantes no CASO, mesmo com dois registros de
    # tentativa.
    repositorio_casos_leitura = RepositorioCasosSupabase()
    caso_final = repositorio_casos_leitura.buscar(caso_id)
    assert caso_final is not None
    assert caso_final.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_final.snapshot_liberado_id in (snapshot_a.SNAPSHOT_ID, snapshot_b.SNAPSHOT_ID)


def test_liberar_apos_ja_liberado_e_recusado_sequencialmente(tmp_path: Path) -> None:
    """Critério 3, caso sequencial simples: a segunda chamada de `liberar`
    sobre um caso já `PLANO_LIBERADO` é recusada com `ErroRevisaoJaDecidida`
    — nunca devolve sucesso silencioso (decisão de RECUSA, não idempotência,
    documentada na docstring de `app/revisao/fila.py`)."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_em_aguardando_revisao(cursor)

    repositorio_revisoes = RepositorioRevisoesSupabase()
    repositorio_casos = RepositorioCasosSupabase()
    repositorio_eventos = RepositorioEventosCasoSupabase()
    snapshot = _snapshot_real(tmp_path, "sequencial")

    liberar(
        revisao_id=f"TESTE_T68_REVISAO_{uuid.uuid4().hex}",
        caso_id=caso_id,
        snapshot=snapshot,
        autor="revisor.teste@piq.invalido",
        decidido_em=datetime.now(UTC).replace(microsecond=0),
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )

    with pytest.raises(ErroRevisaoJaDecidida):
        liberar(
            revisao_id=f"TESTE_T68_REVISAO_{uuid.uuid4().hex}",
            caso_id=caso_id,
            snapshot=snapshot,
            autor="outro-revisor.teste@piq.invalido",
            decidido_em=datetime.now(UTC).replace(microsecond=0),
            repositorio_revisoes=repositorio_revisoes,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
        )

    caso_final = repositorio_casos.buscar(caso_id)
    assert caso_final is not None
    assert caso_final.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_final.snapshot_liberado_id == snapshot.SNAPSHOT_ID
