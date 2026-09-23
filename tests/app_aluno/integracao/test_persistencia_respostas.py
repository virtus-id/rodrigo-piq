"""Testes de `persistencia/app_aluno/respostas.py` — RF-10, RF-11, RF-13
(`AC-02`, `EC-05`, `EC-10`, T-22).

**`EC-05` é provado por DUBLÊ de cursor**, não por banco real: simula uma
falha do driver ANTES do commit (o cenário "banco fica indisponível no meio
da gravação") e prova que `gravar` propaga a exceção — nunca reporta sucesso
sem transação confirmada. Este teste roda sempre, sem `DATABASE_URL`.

**Os demais critérios (gravação de `NAO_SEI` distinguível de ausência,
round-trip de `Decimal` de alta precisão, sobrescrita sem merge) são
provados contra Postgres REAL** (`@pytest.mark.requer_banco`), aplicando as
migrações `001_inicial.sql`/`002_app_aluno.sql` a um banco de teste — mesmo
padrão de `tests/integracao/test_repositorio_snapshots.py` (T-76) e
`tests/regras/test_supabase_adaptadores.py` (T-75). Pulados com mensagem
explícita sem `DATABASE_URL` (o hook de `tests/app_aluno/conftest.py`
aplica o skip automaticamente a qualquer teste com este marcador).

**Honestidade sobre o que foi validado nesta tarefa vs. `T-25`.** `T-25` é a
tarefa dedicada a testar a persistência desta feature contra Postgres real,
incluindo paridade arquivo × Postgres (que depende de `persistencia/
app_aluno/arquivo.py`, T-24, ainda não implementado). Este módulo antecipa
uma cobertura mínima contra banco real — quando executado com
`DATABASE_URL` apontando para um Postgres com as migrações aplicadas — mas
não substitui `T-25`.

REGRAS: RF-10, RF-11, RF-13, AC-02, EC-05, EC-10
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from collection.respostas import NAO_SEI, Resposta
from persistencia.app_aluno.respostas import (
    ErroGravacaoResposta,
    RepositorioRespostasSupabase,
)

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"


# ---------------------------------------------------------------------------
# EC-05 — dublê de cursor que falha ANTES do commit. Roda sempre.
# ---------------------------------------------------------------------------


class _CursorQueFalha:
    """Dublê de cursor `psycopg`: `execute` levanta `psycopg.OperationalError`
    (simula "banco indisponível ou pausado no meio da coleta", EC-05 da
    spec), ANTES de qualquer commit acontecer."""

    def __enter__(self) -> _CursorQueFalha:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise psycopg.OperationalError("conexão perdida — dublê de teste EC-05")


class _ConexaoQueFalha:
    """Dublê de conexão: `cursor()` devolve `_CursorQueFalha`; `commit`
    marca uma flag para o teste provar que ele NUNCA é alcançado quando a
    gravação falha antes dele."""

    def __init__(self) -> None:
        self.commit_chamado = False
        self.rollback_chamado = False

    def cursor(self) -> _CursorQueFalha:
        return _CursorQueFalha()

    def commit(self) -> None:
        self.commit_chamado = True

    def rollback(self) -> None:
        self.rollback_chamado = True

    def close(self) -> None:
        pass


class _PoolQueDevolveConexaoFalsa:
    """Dublê de `ConnectionPool` (`T-187`): `getconn` sempre devolve a
    conexão falsa do teste; `putconn` só sinaliza, nunca fecha nada de
    verdade. `_conectar` (T-187) pega conexão do pool em vez de chamar
    `psycopg.connect` a cada operação — substituir `psycopg.connect` não
    intercepta mais nada; este dublê troca o seam certo."""

    def __init__(self, conexao: object) -> None:
        self._conexao = conexao

    def getconn(self) -> object:
        return self._conexao

    def putconn(self, _conexao: object) -> None:
        pass


def test_ec05_falha_de_gravacao_propaga_excecao_e_nunca_comita(monkeypatch: Any) -> None:
    """EC-05: com o cursor levantando erro antes do commit, `gravar` propaga
    uma exceção (nunca engole, nunca devolve sucesso) e `commit()` nunca é
    chamado na conexão dublê."""
    conexao_dublê = _ConexaoQueFalha()

    monkeypatch.setattr(
        "persistencia.app_aluno.respostas.obter_pool",
        lambda: _PoolQueDevolveConexaoFalsa(conexao_dublê),
    )

    repositorio = RepositorioRespostasSupabase()
    resposta = Resposta(
        CASO_ID="CASO-EC05",
        ID_PERGUNTA="B1.01",
        item_id=None,
        valor="qualquer",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )

    with pytest.raises(ErroGravacaoResposta):
        repositorio.gravar(resposta)

    assert conexao_dublê.commit_chamado is False, (
        "EC-05: commit nunca deveria ser alcançado quando o cursor falha antes dele"
    )
    assert conexao_dublê.rollback_chamado is True, (
        "a conexão deveria ser revertida explicitamente após a falha"
    )


# ---------------------------------------------------------------------------
# Demais critérios — Postgres real, marcador requer_banco.
# ---------------------------------------------------------------------------


def _caso_novo(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Cria conta + caso mínimos (FK de `app_aluno.respostas`) e devolve o
    `CASO_ID` novo, isolado por execução (`uuid4`) — não colide com dados de
    execuções anteriores num banco de teste persistente.

    O caso nasce em `COLETA_INICIAL` (não `CADASTRADO`): desde T-36 (`RF-30`,
    `AC-39`), `RepositorioRespostasSupabase.gravar` recusa gravação para
    casos sem consentimento registrado — este módulo testa round-trip de
    dado, não a guarda (coberta em `tests/app_aluno/test_guarda_
    consentimento_resposta.py`), então o caso já nasce num estado que a
    guarda permite."""
    conta_id = f"TESTE_T22_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T22_CASO_{uuid.uuid4().hex}"
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


@pytest.mark.requer_banco
def test_ac02_gravar_e_listar_do_caso_le_a_resposta_antes_da_proxima_pergunta() -> None:
    """AC-02: a resposta está legível do banco imediatamente após `gravar`
    retornar — sem passo assíncrono nem espera."""
    from persistencia.supabase.conexao import obter_database_url

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo(cursor)

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.01",
            item_id=None,
            valor="sim",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    respostas = repositorio.listar_do_caso(caso_id)
    assert len(respostas) == 1
    assert respostas[0].valor == "sim"


@pytest.mark.requer_banco
def test_gravar_nao_sei_produz_linha_distinguivel_de_ausencia() -> None:
    """Critério de aceite: gravar `NAO_SEI` produz `valor_nao_sei = true`
    com `valor_numerico`/`valor_texto` nulos, e essa linha é DISTINGUÍVEL de
    uma pergunta nunca respondida (ausência total da linha) — consulta
    direta às três colunas, não só ao valor desserializado em Python."""
    from persistencia.supabase.conexao import obter_database_url

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo(cursor)

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.02",
            item_id=None,
            valor=NAO_SEI,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            """
            SELECT valor_texto, valor_numerico, valor_nao_sei
            FROM app_aluno.respostas
            WHERE "CASO_ID" = %s AND "ID_PERGUNTA" = %s AND item_id = ''
            """,
            (caso_id, "B1.02"),
        )
        linha = cursor.fetchone()

    assert linha is not None, "a linha deveria existir — distinta de pergunta nunca respondida"
    valor_texto, valor_numerico, valor_nao_sei = linha
    assert valor_nao_sei is True
    assert valor_texto is None
    assert valor_numerico is None

    # E a ausência de linha para uma pergunta nunca respondida continua
    # sendo ausência real — nunca uma linha fabricada com valor_nao_sei.
    respostas = repositorio.listar_do_caso(caso_id)
    perguntas_respondidas = {r.ID_PERGUNTA for r in respostas}
    assert "B1.99_NUNCA_RESPONDIDA" not in perguntas_respondidas


@pytest.mark.requer_banco
def test_round_trip_decimal_alta_precisao_preserva_string_exata() -> None:
    """Critério de aceite: `Decimal` de alta precisão preserva a STRING
    exata após gravar e reler — comparação por `str()`, não só por `==`
    numérico (que mascararia perda de escala/precisão)."""
    valor_original = Decimal("1234567.123456789012345")  # 15 casas decimais

    from persistencia.supabase.conexao import obter_database_url

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo(cursor)

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B5.VALOR_ALTA_PRECISAO",
            item_id="D001",
            valor=valor_original,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    respostas = repositorio.listar_do_caso(caso_id)
    (resposta_lida,) = [r for r in respostas if r.ID_PERGUNTA == "B5.VALOR_ALTA_PRECISAO"]

    assert isinstance(resposta_lida.valor, Decimal)
    assert str(resposta_lida.valor) == str(valor_original), (
        f"round-trip perdeu precisão: gravado {valor_original!s}, lido {resposta_lida.valor!s}"
    )
    assert resposta_lida.valor == valor_original


@pytest.mark.requer_banco
def test_ec10_regravar_mesma_chave_sobrescreve_sem_merge() -> None:
    """EC-10: duas gravações confirmadas sobre a MESMA `(CASO_ID,
    ID_PERGUNTA, item_id)` resultam numa única linha com o valor da ÚLTIMA
    confirmada — nenhum campo da gravação antiga sobrevive misturado."""
    from persistencia.supabase.conexao import obter_database_url

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo(cursor)

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B5.VALOR",
            item_id="D001",
            valor=Decimal("100.00"),
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )
    # segunda sessão regrava a MESMA chave com um valor totalmente diferente
    # (NAO_SEI em vez de Decimal) — prova que não há merge parcial possível
    # entre um valor numérico antigo e um "não sei" novo.
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B5.VALOR",
            item_id="D001",
            valor=NAO_SEI,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            """
            SELECT count(*) FROM app_aluno.respostas
            WHERE "CASO_ID" = %s AND "ID_PERGUNTA" = %s AND item_id = %s
            """,
            (caso_id, "B5.VALOR", "D001"),
        )
        (total,) = cursor.fetchone()  # type: ignore[misc]

    assert total == 1, f"esperava exatamente 1 linha para a chave, encontrou {total}"

    respostas = repositorio.listar_do_caso(caso_id)
    (resposta_final,) = [
        r for r in respostas if r.ID_PERGUNTA == "B5.VALOR" and r.item_id == "D001"
    ]
    assert resposta_final.valor is NAO_SEI, "a última gravação confirmada deveria vencer, sem merge"
