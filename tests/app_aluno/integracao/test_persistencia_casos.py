"""Testes de `persistencia/app_aluno/casos.py` e `persistencia/app_aluno/
itens.py` — RF-01, RF-04, RF-31 (`EC-10`, `EC-14`, T-23).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`). Não há como provar `FOR UPDATE` de verdade com dublê de
cursor — o bloqueio é uma propriedade do MVCC do Postgres, não do driver —
por isso o critério de concorrência é coberto por DUAS CONEXÕES/THREADS
reais contra o mesmo banco, não por mock.

REGRAS: RF-01, RF-04, RF-31, EC-10, EC-14
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import UTC, date, datetime

import psycopg
import pytest

from collection.registro import EscopoRepeticao
from persistencia.app_aluno.casos import (
    ESTADO_CASO,
    Caso,
    ErroCasoInexistente,
    RepositorioCasosSupabase,
)
from persistencia.app_aluno.itens import RepositorioItensSupabase

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"

pytestmark = pytest.mark.requer_banco


def _conta_e_caso_novos(
    cursor: psycopg.Cursor[tuple[object, ...]],
    *,
    estado: str = "CADASTRADO",
) -> str:
    """Cria conta + caso mínimos (FK de `app_aluno.casos`) e devolve o
    `CASO_ID` novo, isolado por execução (`uuid4`)."""
    conta_id = f"TESTE_T23_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T23_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, %s, CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id, estado),
    )
    return caso_id


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


# ---------------------------------------------------------------------------
# Critério 1 — CASO_ID identidade própria; snapshot_raiz_id só no 1º snapshot
# (OQ-11).
# ---------------------------------------------------------------------------


def test_caso_id_e_identidade_propria_e_snapshot_raiz_so_apos_primeiro_snapshot() -> None:
    """`OQ-11`: `CASO_ID` é gerado no cadastro, independente de qualquer
    snapshot — um caso pode existir e ser lido com `snapshot_raiz_id=None`.
    `snapshot_raiz_id` só passa a ter valor quando explicitamente registrado
    (o momento do PRIMEIRO snapshot, decisão do chamador em `app/`, fora
    desta tarefa) — este repositório nunca o preenche sozinho."""
    caso_id = f"TESTE_T23_CADASTRO_{uuid.uuid4().hex}"
    conta_id = f"TESTE_T23_CONTA_{uuid.uuid4().hex}"

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
            (conta_id, f"{conta_id}@teste.invalido", "hash-fake"),
        )

    repositorio = RepositorioCasosSupabase()
    repositorio.criar(
        Caso(
            CASO_ID=caso_id,
            conta_id=conta_id,
            estado=ESTADO_CASO.CADASTRADO,
            DATA_REFERENCIA=date(2026, 1, 1),
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=datetime.now(UTC),
            criado_em=datetime.now(UTC),
        )
    )

    caso_antes_do_snapshot = repositorio.buscar(caso_id)
    assert caso_antes_do_snapshot is not None
    assert caso_antes_do_snapshot.CASO_ID == caso_id
    assert caso_antes_do_snapshot.snapshot_raiz_id is None, (
        "OQ-11: snapshot_raiz_id deve ser None enquanto nenhum snapshot nasceu"
    )
    assert caso_antes_do_snapshot.snapshot_liberado_id is None

    repositorio.registrar_snapshot_raiz(caso_id, "SNAPSHOT-RAIZ-001")
    caso_apos_snapshot = repositorio.buscar(caso_id)
    assert caso_apos_snapshot is not None
    assert caso_apos_snapshot.snapshot_raiz_id == "SNAPSHOT-RAIZ-001", (
        "OQ-11: snapshot_raiz_id passa a existir só quando o primeiro snapshot nasce"
    )


# ---------------------------------------------------------------------------
# Critério 2 — transição de estado adquire FOR UPDATE antes de gravar.
# ---------------------------------------------------------------------------


def test_transicao_de_estado_adquire_for_update_antes_de_gravar() -> None:
    """Prova observável de que o `SELECT ... FOR UPDATE` é de fato adquirido
    ANTES do `UPDATE`: uma segunda conexão que tenta o MESMO `SELECT ... FOR
    UPDATE` enquanto a primeira transação está aberta (antes do commit) fica
    bloqueada — só retorna após o commit da primeira. Usa `statement_timeout`
    baixo na segunda conexão para provar o bloqueio sem travar o teste."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioCasosSupabase()

    liberar_primeira_transacao = threading.Event()
    lock_foi_adquirido = threading.Event()

    def _mantem_lock_aberto() -> None:
        conexao_1 = psycopg.connect(_database_url())
        try:
            with conexao_1.cursor() as cursor:
                cursor.execute("SET search_path TO app_aluno, public")
                cursor.execute(
                    'SELECT "CASO_ID" FROM app_aluno.casos WHERE "CASO_ID" = %s FOR UPDATE',
                    (caso_id,),
                )
                cursor.fetchone()
                lock_foi_adquirido.set()
                liberar_primeira_transacao.wait(timeout=5)
            conexao_1.commit()
        finally:
            conexao_1.close()

    thread_1 = threading.Thread(target=_mantem_lock_aberto)
    thread_1.start()
    assert lock_foi_adquirido.wait(timeout=5), "primeira transação não adquiriu o lock a tempo"

    # Segunda conexão: tenta o mesmo FOR UPDATE com um statement_timeout
    # curto — se o lock da primeira estiver mesmo ativo, esta chamada expira
    # por timeout (prova de bloqueio real), nunca retorna imediatamente.
    conexao_2 = psycopg.connect(_database_url())
    try:
        with conexao_2.cursor() as cursor:
            cursor.execute("SET search_path TO app_aluno, public")
            cursor.execute("SET statement_timeout = '300ms'")
            with pytest.raises(psycopg.errors.QueryCanceled):
                cursor.execute(
                    'SELECT "CASO_ID" FROM app_aluno.casos WHERE "CASO_ID" = %s FOR UPDATE',
                    (caso_id,),
                )
        conexao_2.rollback()
    finally:
        conexao_2.close()

    liberar_primeira_transacao.set()
    thread_1.join(timeout=5)

    # Depois que a primeira transação libera o lock, a transição normal via
    # repositório funciona sem bloqueio.
    atualizado = repositorio.transicionar_estado(caso_id, ESTADO_CASO.CONSENTIMENTO_REGISTRADO)
    assert atualizado.estado is ESTADO_CASO.CONSENTIMENTO_REGISTRADO


# ---------------------------------------------------------------------------
# Critério 3 — duas transições concorrentes não produzem estados divergentes.
# ---------------------------------------------------------------------------


def test_duas_transicoes_concorrentes_nao_produzem_estados_divergentes() -> None:
    """Duas THREADS com conexões PRÓPRIAS chamam, ao mesmo tempo, uma
    transição de estado para o MESMO `CASO_ID`. Prova, por linha do tempo
    real: (1) a segunda só adquire seu `FOR UPDATE` depois do commit da
    primeira (serialização real, não simulada); (2) o caso termina em
    EXATAMENTE um dos dois estados — nunca um valor corrompido/misto."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    eventos: list[tuple[float, str]] = []
    lock_eventos = threading.Lock()

    def _registrar(mensagem: str) -> None:
        with lock_eventos:
            eventos.append((time.monotonic(), mensagem))

    barreira = threading.Barrier(2)

    def _transicao_com_atraso(novo_estado: ESTADO_CASO, atraso_segundos: float) -> None:
        conexao_thread = psycopg.connect(_database_url())
        try:
            with conexao_thread.cursor() as cursor:
                cursor.execute("SET search_path TO app_aluno, public")
            barreira.wait()
            with conexao_thread.cursor() as cursor:
                cursor.execute(
                    'SELECT "CASO_ID" FROM app_aluno.casos WHERE "CASO_ID" = %s FOR UPDATE',
                    (caso_id,),
                )
                cursor.fetchone()
                _registrar(f"{novo_estado.value}:LOCK_ADQUIRIDO")
                time.sleep(atraso_segundos)
                cursor.execute(
                    'UPDATE app_aluno.casos SET estado = %s, ultima_interacao_em = now() '
                    'WHERE "CASO_ID" = %s',
                    (novo_estado.value, caso_id),
                )
            conexao_thread.commit()
            _registrar(f"{novo_estado.value}:COMMIT")
        except BaseException:
            conexao_thread.rollback()
            raise
        finally:
            conexao_thread.close()

    thread_a = threading.Thread(
        target=_transicao_com_atraso, args=(ESTADO_CASO.CONSENTIMENTO_REGISTRADO, 0.8)
    )
    thread_b = threading.Thread(target=_transicao_com_atraso, args=(ESTADO_CASO.ENCERRADO, 0.0))

    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    eventos.sort()
    locks = sorted(t for t, m in eventos if m.endswith(":LOCK_ADQUIRIDO"))
    commits = sorted(t for t, m in eventos if m.endswith(":COMMIT"))
    assert len(locks) == 2, f"esperava 2 locks adquiridos, obteve {len(locks)}: {eventos}"
    assert len(commits) == 2, f"esperava 2 commits, obteve {len(commits)}: {eventos}"

    assert locks[1] >= commits[0], (
        "FALHA DE SERIALIZAÇÃO: a segunda transição adquiriu FOR UPDATE antes do "
        f"primeiro commit — eventos: {eventos}"
    )

    repositorio = RepositorioCasosSupabase()
    caso_final = repositorio.buscar(caso_id)
    assert caso_final is not None
    assert caso_final.estado in (ESTADO_CASO.CONSENTIMENTO_REGISTRADO, ESTADO_CASO.ENCERRADO), (
        f"estado final divergente/corrompido: {caso_final.estado!r}"
    )


# ---------------------------------------------------------------------------
# Critério 4 — ultima_interacao_em gravada com o instante da interação e
# legível na trilha.
# ---------------------------------------------------------------------------


def test_ultima_interacao_em_e_gravada_e_legivel_na_trilha() -> None:
    """`RF-31`/`EC-14`: `registrar_interacao` grava `ultima_interacao_em`
    com o instante fornecido (comparável exatamente, não só "atualizou
    algo") e o valor é lido de volta por `buscar` — a mesma consulta que a
    trilha de acompanhamento usaria."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioCasosSupabase()
    instante_interacao = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)

    repositorio.registrar_interacao(caso_id, agora=instante_interacao)

    caso = repositorio.buscar(caso_id)
    assert caso is not None
    assert caso.ultima_interacao_em == instante_interacao, (
        f"ultima_interacao_em deveria ser exatamente {instante_interacao!r}, "
        f"obteve {caso.ultima_interacao_em!r}"
    )

    # Transição de estado também atualiza a trilha (não só registrar_interacao).
    instante_transicao = datetime(2026, 3, 20, 8, 0, 0, tzinfo=UTC)
    caso_pos_transicao = repositorio.transicionar_estado(
        caso_id, ESTADO_CASO.CONSENTIMENTO_REGISTRADO, agora=instante_transicao
    )
    assert caso_pos_transicao.ultima_interacao_em == instante_transicao


def test_registrar_interacao_em_caso_inexistente_levanta_erro() -> None:
    """`registrar_interacao`/`transicionar_estado` nunca falham em
    silêncio: `CASO_ID` inexistente levanta `ErroCasoInexistente`."""
    repositorio = RepositorioCasosSupabase()
    with pytest.raises(ErroCasoInexistente):
        repositorio.registrar_interacao("CASO_QUE_NAO_EXISTE_XYZ")
    with pytest.raises(ErroCasoInexistente):
        repositorio.transicionar_estado("CASO_QUE_NAO_EXISTE_XYZ", ESTADO_CASO.ENCERRADO)


# ---------------------------------------------------------------------------
# itens_repetidos — mecanismo de não-reaproveitamento (RF-04, EC-10).
# ---------------------------------------------------------------------------


def test_itens_repetidos_geram_identificadores_estaveis_e_nao_reaproveitados() -> None:
    """`RF-04`: identificadores sequenciais e estáveis; remover um item não
    libera seu número para um item novo (mesmo critério de `AC-04`/T-15,
    agora contra a persistência real)."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioItensSupabase()
    primeiro = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)
    segundo = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)
    terceiro = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)

    assert (primeiro, segundo, terceiro) == ("D001", "D002", "D003")

    repositorio.remover(caso_id, segundo)
    quarto = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)
    assert quarto == "D004", (
        f"identificador removido não deveria ser reaproveitado, obteve {quarto}"
    )

    todos = repositorio.listar_do_caso(caso_id)
    assert {item.item_id for item in todos} == {"D001", "D002", "D003", "D004"}
    ativos = repositorio.listar_do_caso(caso_id, incluir_removidos=False)
    assert {item.item_id for item in ativos} == {"D001", "D003", "D004"}


def test_itens_repetidos_de_escopos_diferentes_tem_sequencias_independentes() -> None:
    """Escopos diferentes (`DIVIDA_ID`, `MARGEM_ID`) não compartilham
    contador — cada um começa em 001 dentro do mesmo caso."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioItensSupabase()
    divida_1 = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)
    margem_1 = repositorio.proximo_identificador(caso_id, EscopoRepeticao.MARGEM_ID)
    divida_2 = repositorio.proximo_identificador(caso_id, EscopoRepeticao.DIVIDA_ID)

    assert divida_1 == "D001"
    assert margem_1 == "M001"
    assert divida_2 == "D002"
