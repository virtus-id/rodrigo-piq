"""Teste de concorrência real do disparo do Bloco 6 — `RF-16`, `AC-12` (T-56,
critério de aceite 4: "dois disparos concorrentes resultam em uma única
execução").

Exige Postgres real (`@pytest.mark.requer_banco`), pulado com mensagem
explícita sem `DATABASE_URL` (hook de `tests/app_aluno/conftest.py`). Mesmo
padrão de `tests/app_aluno/integracao/test_persistencia_casos.py::T-23`: duas
THREADS com CONEXÕES PRÓPRIAS chamam, ao mesmo tempo,
`RepositorioCasos.transicionar_estado_se` (T-56, extensão de T-23) para o
MESMO `CASO_ID` — não há como provar `SELECT ... FOR UPDATE` condicional de
verdade com dublê de cursor, o bloqueio é uma propriedade do MVCC do
Postgres, não do driver.

REGRAS: `RF-16`, `AC-12`
"""

from __future__ import annotations

import threading
import time
import uuid

import psycopg
import pytest

from app.casos.maquina import ESTADO_CASO
from persistencia.app_aluno.casos import Caso, RepositorioCasosSupabase

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _conta_e_caso_novos(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Mesmo padrão de `test_persistencia_casos.py::_conta_e_caso_novos` — o
    caso nasce em `COLETA_INICIAL`, o estado de origem real do gatilho
    `bloco_6_executa` (`app/casos/maquina.py`)."""
    conta_id = f"TESTE_T56_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T56_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, 'COLETA_INICIAL', CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id),
    )
    return caso_id


def test_duas_chamadas_concorrentes_de_transicionar_estado_se_resultam_em_uma_unica_vencedora() -> (
    None
):
    """Prova, por linha do tempo real, exatamente o que o critério de
    aceite 4 exige: das duas requisições concorrentes que tentariam disparar
    o Bloco 6 sobre o MESMO caso, só UMA consegue a transição condicional
    `COLETA_INICIAL → CALCULANDO` (e, portanto, só uma agendaria
    `calcular_plano` na rota real, `app/http/rotas_calculo.py::
    disparar_calculo`) — a outra recebe `None`, sem gravar nada."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    resultados: dict[str, Caso | None] = {}
    lock_resultados = threading.Lock()
    barreira = threading.Barrier(2)

    def _tentar_disparo(nome: str, atraso_segundos: float) -> None:
        # Cada thread com sua PRÓPRIA conexão — mesma disciplina de T-23
        # (duas conexões de fato concorrentes, nunca a mesma conexão
        # compartilhada por duas threads).
        repositorio = RepositorioCasosSupabase()
        barreira.wait()
        time.sleep(atraso_segundos)
        resultado = repositorio.transicionar_estado_se(
            caso_id, ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.CALCULANDO
        )
        with lock_resultados:
            resultados[nome] = resultado

    thread_a = threading.Thread(target=_tentar_disparo, args=("A", 0.0))
    thread_b = threading.Thread(target=_tentar_disparo, args=("B", 0.0))

    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert set(resultados.keys()) == {"A", "B"}
    vencedoras = [nome for nome, caso in resultados.items() if caso is not None]
    perdedoras = [nome for nome, caso in resultados.items() if caso is None]

    assert len(vencedoras) == 1, (
        f"esperava exatamente UMA execução vencedora, obteve {len(vencedoras)}: {resultados}"
    )
    assert len(perdedoras) == 1

    caso_vencedor = resultados[vencedoras[0]]
    assert caso_vencedor is not None
    assert caso_vencedor.estado == ESTADO_CASO.CALCULANDO

    # O estado final no banco é CALCULANDO — a perdedora não sobrescreveu nem
    # reverteu o que a vencedora gravou.
    repositorio = RepositorioCasosSupabase()
    caso_final = repositorio.buscar(caso_id)
    assert caso_final is not None
    assert caso_final.estado == ESTADO_CASO.CALCULANDO


def test_segunda_chamada_so_adquire_lock_apos_commit_da_primeira() -> None:
    """Prova de serialização real (mesmo padrão de `test_persistencia_
    casos.py::test_transicao_de_estado_adquire_for_update_antes_de_gravar`):
    a segunda thread só consegue seu resultado (vencedor ou perdedor) DEPOIS
    que a primeira já commitou — nunca lê o estado "no meio" da primeira
    transação."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    eventos: list[tuple[float, str]] = []
    lock_eventos = threading.Lock()

    def _registrar(mensagem: str) -> None:
        with lock_eventos:
            eventos.append((time.monotonic(), mensagem))

    barreira = threading.Barrier(2)

    def _tentar_disparo_com_atraso(nome: str, atraso_segundos: float) -> None:
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
                _registrar(f"{nome}:LOCK_ADQUIRIDO")
                time.sleep(atraso_segundos)
                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET estado = 'CALCULANDO', ultima_interacao_em = now()
                    WHERE "CASO_ID" = %s AND estado = 'COLETA_INICIAL'
                    """,
                    (caso_id,),
                )
                _registrar(f"{nome}:UPDATE_AFETOU_{cursor.rowcount}_LINHAS")
            conexao_thread.commit()
            _registrar(f"{nome}:COMMIT")
        except BaseException:
            conexao_thread.rollback()
            raise
        finally:
            conexao_thread.close()

    thread_a = threading.Thread(target=_tentar_disparo_com_atraso, args=("A", 0.8))
    thread_b = threading.Thread(target=_tentar_disparo_com_atraso, args=("B", 0.0))

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
        "FALHA DE SERIALIZAÇÃO: a segunda tentativa adquiriu FOR UPDATE antes do "
        f"primeiro commit — eventos: {eventos}"
    )

    # Exatamente um UPDATE afetou 1 linha (a vencedora); o outro afetou 0
    # (a condição WHERE estado = 'COLETA_INICIAL' já não valia mais).
    afetou_uma_linha = [m for _, m in eventos if m.endswith("_1_LINHAS")]
    afetou_zero_linhas = [m for _, m in eventos if m.endswith("_0_LINHAS")]
    assert len(afetou_uma_linha) == 1, eventos
    assert len(afetou_zero_linhas) == 1, eventos
