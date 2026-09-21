"""`UPDATE`/`DELETE` de `RegistroRevisao` é recusado pelo banco — `RF-24`,
`AC-27`, T-73.

**Este módulo é deliberadamente mínimo — nunca duplicado.** A prova completa
de `AC-27` contra Postgres real (INSERT mínimo, tentativa de `UPDATE`,
tentativa de `DELETE`, confirmação de que o registro permanece inalterado
após cada tentativa, e a checagem de que a mensagem de erro cita a defesa
`RF-24`) já existe em `tests/app_aluno/integracao/test_persistencia_
revisoes.py` (T-67):

- `test_update_direto_em_revisoes_e_recusado_e_registro_permanece_inalterado`
- `test_delete_direto_em_revisoes_e_recusado_e_registro_permanece`
- `test_interface_do_repositorio_nao_expoe_atualizar_nem_remover`

Mesmo precedente de `tests/app_aluno/integracao/test_snapshot_imutavel.py`
(T-26), que documenta e referencia a cobertura irmã em vez de reescrevê-la.
Este arquivo nasce como o ponto de entrada nomeado que `T-73` pede
(`tests/app_aluno/integracao/test_revisao_imutavel.py`) e reafirma a garantia
com UM teste próprio (`DELETE`, o verbo que, junto com `UPDATE`, `AC-27`
exige recusado) mais um teste de sanidade que a suíte irmã de fato existe e
cobre os dois verbos — para que apagar a suíte irmã por engano quebre este
teste também, em vez de deixar `AC-27` silenciosamente descoberto.

REGRAS: RF-24, AC-27
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from app.revisao.fila import DECISAO_REVISAO, RegistroRevisao
from persistencia.app_aluno.revisoes import RepositorioRevisoesSupabase

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _conta_e_caso_novos(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Mesmo helper de `test_persistencia_revisoes.py` — conta + caso
    mínimos, isolados por execução (FK de `app_aluno.revisoes`)."""
    conta_id = f"TESTE_T73_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T73_CASO_{uuid.uuid4().hex}"
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


def test_ac27_delete_de_registro_de_revisao_gravado_pelo_repositorio_e_recusado() -> None:
    """`AC-27`: um `RegistroRevisao` gravado pelo repositório real (não por
    `INSERT` manual, ao contrário de `test_persistencia_revisoes.py`, que
    prova o mesmo ponto por SQL direto) continua existindo e inalterado após
    uma tentativa de `DELETE` direto na tabela."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _conta_e_caso_novos(cursor)

    repositorio = RepositorioRevisoesSupabase()
    agora = datetime.now(UTC).replace(microsecond=0)
    registro = RegistroRevisao(
        SNAPSHOT_ID=f"TESTE_T73_SNAPSHOT_{uuid.uuid4().hex}",
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO.LIBERADO,
        autor="revisor.teste@piq.invalido",
        decidido_em=agora,
        classificacao_erro=None,
        observacao=None,
    )
    revisao_id = f"TESTE_T73_REVISAO_{uuid.uuid4().hex}"
    repositorio.gravar(revisao_id, registro)

    with psycopg.connect(_database_url()) as conexao_ataque:
        with conexao_ataque.cursor() as cursor_ataque, pytest.raises(psycopg.Error):
            cursor_ataque.execute("SET search_path TO app_aluno, public")
            cursor_ataque.execute(
                "DELETE FROM app_aluno.revisoes WHERE revisao_id = %s",
                (revisao_id,),
            )
        conexao_ataque.rollback()

    lido_apos_tentativa = repositorio.obter(revisao_id)
    assert lido_apos_tentativa is not None, (
        "o registro deveria continuar existindo — DELETE deveria ter sido recusado"
    )
    assert lido_apos_tentativa.autor == "revisor.teste@piq.invalido"
    assert lido_apos_tentativa.decisao is DECISAO_REVISAO.LIBERADO


def test_cobertura_completa_de_ac27_vive_em_test_persistencia_revisoes() -> None:
    """Sanidade: os dois testes que provam `UPDATE` e `DELETE` recusados
    (com verificação de mensagem citando `RF-24` e de que o valor original
    permanece byte a byte) continuam existindo em `test_persistencia_
    revisoes.py` — apagar aquele arquivo por engano quebra este teste, em
    vez de deixar `AC-27` silenciosamente sem cobertura."""
    from tests.app_aluno.integracao import test_persistencia_revisoes as suite_irma

    assert hasattr(
        suite_irma, "test_update_direto_em_revisoes_e_recusado_e_registro_permanece_inalterado"
    )
    assert hasattr(suite_irma, "test_delete_direto_em_revisoes_e_recusado_e_registro_permanece")
    assert hasattr(suite_irma, "test_interface_do_repositorio_nao_expoe_atualizar_nem_remover")
