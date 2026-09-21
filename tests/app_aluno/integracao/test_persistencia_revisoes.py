"""Testes de `persistencia/app_aluno/revisoes.py` — `RF-24`, `AC-27` (T-67).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`) — mesmo padrão de `test_persistencia_consentimentos.py` (T-35)
e `test_snapshot_imutavel.py` (T-26) para a prova de `UPDATE`/`DELETE`
recusado.

REGRAS: RF-24, AC-27
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from app.revisao.fila import CLASSIFICACAO_ERRO, DECISAO_REVISAO, RegistroRevisao
from persistencia.app_aluno.revisoes import RepositorioRevisoesSupabase

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _conta_e_caso_novos(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Cria conta + caso mínimos (FK de `app_aluno.revisoes` via
    `app_aluno.casos`) e devolve o `CASO_ID` novo, isolado por execução."""
    conta_id = f"TESTE_T67_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T67_CASO_{uuid.uuid4().hex}"
    cursor.execute(
        "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
        (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
    )
    cursor.execute(
        """
        INSERT INTO app_aluno.casos
            ("CASO_ID", conta_id, estado, "DATA_REFERENCIA", "QUESTIONARIO_VERSION")
        VALUES (%s, %s, 'CADASTRADO', CURRENT_DATE, '1.0.0')
        """,
        (caso_id, conta_id),
    )
    return caso_id


def test_liberacao_e_gravada_com_autor_e_data_e_consultavel_por_caso() -> None:
    """`AC-27`: autor e data são gravados, e o registro é consultável."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioRevisoesSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)
    registro = RegistroRevisao(
        SNAPSHOT_ID=f"TESTE_T67_SNAPSHOT_{uuid.uuid4().hex}",
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO.LIBERADO,
        autor="revisor.teste@piq.invalido",
        decidido_em=agora,
        classificacao_erro=None,
        observacao=None,
    )
    revisao_id = f"TESTE_T67_REVISAO_{uuid.uuid4().hex}"

    repositorio.gravar(revisao_id, registro)
    encontrados = repositorio.listar_do_caso(caso_id)

    assert len(encontrados) == 1
    lido = encontrados[0]
    assert lido.CASO_ID == caso_id
    assert lido.SNAPSHOT_ID == registro.SNAPSHOT_ID
    assert lido.decisao is DECISAO_REVISAO.LIBERADO
    assert lido.autor == "revisor.teste@piq.invalido"
    assert lido.decidido_em == agora
    assert lido.classificacao_erro is None
    assert lido.observacao is None


def test_reprovacao_tambem_e_gravada_com_classificacao_e_observacao() -> None:
    """Liberação **e** reprovação são ambas registradas — pelo mesmo
    caminho de `gravar`, sem método separado."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioRevisoesSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)
    registro = RegistroRevisao(
        SNAPSHOT_ID=f"TESTE_T67_SNAPSHOT_{uuid.uuid4().hex}",
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO.REPROVADO,
        autor="revisor.teste@piq.invalido",
        decidido_em=agora,
        classificacao_erro=CLASSIFICACAO_ERRO.CALCULO,
        observacao="valor de ATAQUE_IMEDIATO divergente do esperado",
    )
    revisao_id = f"TESTE_T67_REVISAO_{uuid.uuid4().hex}"

    repositorio.gravar(revisao_id, registro)
    lido = repositorio.obter(revisao_id)

    assert lido is not None
    assert lido.decisao is DECISAO_REVISAO.REPROVADO
    assert lido.classificacao_erro is CLASSIFICACAO_ERRO.CALCULO
    assert lido.observacao == "valor de ATAQUE_IMEDIATO divergente do esperado"


def test_obter_revisao_inexistente_devolve_none() -> None:
    """`obter` nunca lança para "não encontrado" — só `None`, mesmo contrato
    de `RepositorioCasos.buscar`."""
    repositorio = RepositorioRevisoesSupabase()

    assert repositorio.obter(f"TESTE_T67_INEXISTENTE_{uuid.uuid4().hex}") is None


def test_listar_do_caso_sem_revisao_devolve_vazio() -> None:
    """Caso sem nenhuma revisão registrada devolve tupla vazia — nunca
    lança, nunca inventa um registro."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioRevisoesSupabase()

    assert repositorio.listar_do_caso(caso_id) == ()


def _inserir_revisao_minima(
    cursor: psycopg.Cursor[tuple[object, ...]], caso_id: str
) -> tuple[str, str]:
    """Insere uma linha mínima diretamente por SQL em `app_aluno.revisoes`
    — mesmo precedente de `test_snapshot_imutavel.py::_inserir_snapshot_
    minimo` (T-26): o objetivo é provar a recusa de `UPDATE`/`DELETE` pelo
    banco, não exercitar o adaptador. Devolve `(revisao_id, autor_original)`
    para comparação posterior."""
    revisao_id = f"TESTE_T67_{uuid.uuid4().hex}"
    autor_original = f"TESTE_T67_autor_original_{uuid.uuid4().hex}"
    cursor.execute(
        """
        INSERT INTO app_aluno.revisoes (
            revisao_id, snapshot_id, "CASO_ID", decisao, autor, decidido_em
        ) VALUES (%s, %s, %s, 'LIBERADO', %s, now())
        """,
        (revisao_id, f"TESTE_T67_SNAPSHOT_{uuid.uuid4().hex}", caso_id, autor_original),
    )
    return revisao_id, autor_original


def _ler_autor(cursor: psycopg.Cursor[tuple[object, ...]], revisao_id: str) -> str:
    cursor.execute(
        "SELECT autor FROM app_aluno.revisoes WHERE revisao_id = %s",
        (revisao_id,),
    )
    linha = cursor.fetchone()
    assert linha is not None, f"revisão {revisao_id} deveria existir após o INSERT"
    valor = linha[0]
    assert isinstance(valor, str)
    return valor


def test_update_direto_em_revisoes_e_recusado_e_registro_permanece_inalterado() -> None:
    """`UPDATE`/`DELETE` direto na tabela é recusado pelo banco (`REVOKE` +
    trigger de `T-21`). Um `UPDATE` real via `psycopg` contra
    `app_aluno.revisoes` levanta erro do Postgres, e após a tentativa (com
    rollback) o valor original de `autor` continua exatamente o mesmo."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)
        revisao_id, autor_original = _inserir_revisao_minima(cursor, caso_id)

    with psycopg.connect(_database_url()) as conexao_ataque:
        with conexao_ataque.cursor() as cursor_ataque, pytest.raises(psycopg.Error) as excinfo:
            cursor_ataque.execute("SET search_path TO app_aluno, public")
            cursor_ataque.execute(
                "UPDATE app_aluno.revisoes SET autor = %s WHERE revisao_id = %s",
                ("TESTE_T67_tentativa_de_sobrescrita", revisao_id),
            )
        conexao_ataque.rollback()

    assert "RF-24" in str(excinfo.value) or "append-only" in str(excinfo.value).lower(), (
        f"esperava que o erro citasse a defesa RF-24, obteve: {excinfo.value!r}"
    )

    with psycopg.connect(_database_url()) as conexao_leitura, conexao_leitura.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        autor_apos_tentativa = _ler_autor(cursor, revisao_id)

    assert autor_apos_tentativa == autor_original, (
        "o registro deveria permanecer INALTERADO após a tentativa de UPDATE "
        f"recusada — esperava {autor_original!r}, obteve {autor_apos_tentativa!r}"
    )


def test_delete_direto_em_revisoes_e_recusado_e_registro_permanece() -> None:
    """`DELETE` direto na tabela também é recusado pelo banco — a linha
    continua existindo após a tentativa (com rollback)."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)
        revisao_id, autor_original = _inserir_revisao_minima(cursor, caso_id)

    with psycopg.connect(_database_url()) as conexao_ataque:
        with conexao_ataque.cursor() as cursor_ataque, pytest.raises(psycopg.Error) as excinfo:
            cursor_ataque.execute("SET search_path TO app_aluno, public")
            cursor_ataque.execute(
                "DELETE FROM app_aluno.revisoes WHERE revisao_id = %s",
                (revisao_id,),
            )
        conexao_ataque.rollback()

    assert "RF-24" in str(excinfo.value) or "append-only" in str(excinfo.value).lower(), (
        f"esperava que o erro citasse a defesa RF-24, obteve: {excinfo.value!r}"
    )

    with psycopg.connect(_database_url()) as conexao_leitura, conexao_leitura.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        autor_apos_tentativa = _ler_autor(cursor, revisao_id)

    assert autor_apos_tentativa == autor_original, (
        "o registro não deveria ter sido removido nem alterado após a tentativa "
        f"de DELETE recusada — esperava {autor_original!r}, obteve {autor_apos_tentativa!r}"
    )


def test_interface_do_repositorio_nao_expoe_atualizar_nem_remover() -> None:
    """A interface do repositório de revisões não expõe `atualizar` nem
    `remover` — mesmo precedente de `RepositorioSnapshots`."""
    metodos = {
        nome
        for nome in dir(RepositorioRevisoesSupabase)
        if not nome.startswith("_")
    }

    assert "atualizar" not in metodos
    assert "remover" not in metodos
    assert metodos == {"gravar", "obter", "listar_do_caso"}
