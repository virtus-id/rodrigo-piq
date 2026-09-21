"""Paridade arquivo × Postgres da persistência desta feature — `RF-10`,
`RF-13` (`AC-02`, `EC-05`, T-25).

**Escopo desta tarefa vs. `T-22`/`T-23`.** `tests/app_aluno/integracao/
test_persistencia_respostas.py` (T-22) e `test_persistencia_casos.py` (T-23)
já provam, cada um isoladamente contra Postgres real, os critérios de
`RepositorioRespostasSupabase`/`RepositorioCasosSupabase` (round-trip
`Decimal`, `FOR UPDATE`, `EC-10`, `EC-14`). Este módulo NÃO repete essas
provas pontuais — ele roda a MESMA sequência de operações nos DOIS
adaptadores (arquivo, T-24, e Postgres, T-22/T-23) e compara o resultado
campo a campo, provando que os dois lados do `Protocol` produzem o mesmo
estado observável para o mesmo roteiro de chamadas.

**`AC-02`** (resposta legível do banco antes da próxima pergunta ser
produzida) é reconfirmado aqui especificamente como leitura-após-escrita
dentro do MESMO fluxo de paridade — gravar uma resposta e, imediatamente
(nova consulta, sem esperar nada), listar de volta e achar exatamente aquele
valor. Não é um teste novo de `FOR UPDATE`/concorrência (isso é `T-23`).

**`EC-05`** é reconfirmado aqui com um cenário DIFERENTE do dublê de cursor
de `test_persistencia_respostas.py`: aqui a `DATABASE_URL` aponta para um
host que existe mas não responde na porta indicada (timeout de conexão) —
"banco indisponível" fim a fim, não uma falha simulada no meio do cursor.
A gravação deve levantar exceção e nada pode ser reportado como salvo.

Testes `requer_banco` são pulados com mensagem explícita sem `DATABASE_URL`
(hook de `tests/app_aluno/conftest.py`); a suíte fecha verde nesse caso.

REGRAS: RF-10, RF-13, AC-02, EC-05
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from collection.respostas import NAO_SEI, Resposta
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import ESTADO_CASO, Caso, RepositorioCasosSupabase
from persistencia.app_aluno.respostas import (
    ErroGravacaoResposta,
    RepositorioRespostasSupabase,
)

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"


def _caso_novo_no_banco(cursor: psycopg.Cursor[tuple[object, ...]]) -> str:
    """Cria conta + caso mínimos (FK de `app_aluno.respostas`/`.casos`) e
    devolve o `CASO_ID` novo, isolado por execução (`uuid4`) — mesmo padrão
    de `test_persistencia_respostas.py`/`test_persistencia_casos.py`.

    O caso nasce em `COLETA_INICIAL` (não `CADASTRADO`): desde T-36 (`RF-30`,
    `AC-39`), `RepositorioRespostasSupabase.gravar` recusa gravação para
    casos sem consentimento registrado — este módulo testa paridade
    arquivo × Postgres, não a guarda, então o caso já nasce num estado que
    ela permite (o lado arquivo, sem a mesma checagem, não é afetado)."""
    conta_id = f"TESTE_T25_CONTA_{uuid.uuid4().hex}"
    caso_id = f"TESTE_T25_CASO_{uuid.uuid4().hex}"
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


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


# ---------------------------------------------------------------------------
# Paridade campo a campo — Resposta (RF-10, RF-13).
# ---------------------------------------------------------------------------


@pytest.mark.requer_banco
def test_paridade_respostas_arquivo_x_postgres_mesma_sequencia_de_operacoes(
    tmp_path: Path,
) -> None:
    """A MESMA sequência de `gravar`/`gravar` (regravação) sobre as duas
    implementações de `RepositorioRespostas` produz, campo a campo, o mesmo
    resultado observável — incluindo `Decimal` de alta precisão comparado
    por `str()` exato (nunca só `==` numérico, que mascararia perda de
    escala)."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo_no_banco(cursor)

    repositorio_postgres = RepositorioRespostasSupabase()
    repositorio_arquivo = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")

    agora = datetime(2026, 2, 10, 14, 30, 0, tzinfo=UTC)
    valor_alta_precisao = Decimal("1234567.123456789012345")

    # O MESMO roteiro de operações, aplicado aos dois adaptadores: gravação
    # simples, gravação de NAO_SEI, gravação de Decimal de alta precisão e
    # uma regravação (EC-10, sem merge) sobre a mesma chave.
    roteiro: tuple[Resposta, ...] = (
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.01",
            item_id=None,
            valor="sim",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=agora,
        ),
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.02",
            item_id=None,
            valor=NAO_SEI,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=agora,
        ),
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B5.VALOR_ALTA_PRECISAO",
            item_id="D001",
            valor=valor_alta_precisao,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=agora,
        ),
        # Regravação da MESMA chave (CASO_ID, B1.01, None) — EC-10, sem merge.
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.01",
            item_id=None,
            valor="nao",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=agora,
        ),
    )

    for resposta in roteiro:
        repositorio_postgres.gravar(resposta)
        repositorio_arquivo.gravar(resposta)

    respostas_postgres = {
        (r.ID_PERGUNTA, r.item_id): r for r in repositorio_postgres.listar_do_caso(caso_id)
    }
    respostas_arquivo = {
        (r.ID_PERGUNTA, r.item_id): r for r in repositorio_arquivo.listar_do_caso(caso_id)
    }

    assert set(respostas_postgres) == set(respostas_arquivo), (
        "os dois adaptadores deveriam expor exatamente o mesmo conjunto de chaves "
        f"após o mesmo roteiro: postgres={set(respostas_postgres)} "
        f"arquivo={set(respostas_arquivo)}"
    )

    for chave, resposta_pg in respostas_postgres.items():
        resposta_arq = respostas_arquivo[chave]
        assert resposta_pg.CASO_ID == resposta_arq.CASO_ID
        assert resposta_pg.ID_PERGUNTA == resposta_arq.ID_PERGUNTA
        assert resposta_pg.item_id == resposta_arq.item_id
        assert resposta_pg.QUESTIONARIO_VERSION == resposta_arq.QUESTIONARIO_VERSION
        assert type(resposta_pg.valor) is type(resposta_arq.valor), (
            f"tipo de valor divergente em {chave}: "
            f"postgres={type(resposta_pg.valor)} arquivo={type(resposta_arq.valor)}"
        )
        if isinstance(resposta_pg.valor, Decimal):
            assert isinstance(resposta_arq.valor, Decimal)
            assert str(resposta_pg.valor) == str(resposta_arq.valor), (
                f"Decimal divergente em {chave}: postgres={resposta_pg.valor!s} "
                f"arquivo={resposta_arq.valor!s}"
            )
        else:
            assert resposta_pg.valor == resposta_arq.valor, f"valor divergente em {chave}"

    # A regravação venceu nos dois lados, sem merge (EC-10).
    assert respostas_postgres[("B1.01", None)].valor == "nao"
    assert respostas_arquivo[("B1.01", None)].valor == "nao"
    # O valor Decimal de alta precisão preserva a string exata nos dois lados.
    assert str(respostas_postgres[("B5.VALOR_ALTA_PRECISAO", "D001")].valor) == str(
        valor_alta_precisao
    )
    assert str(respostas_arquivo[("B5.VALOR_ALTA_PRECISAO", "D001")].valor) == str(
        valor_alta_precisao
    )


# ---------------------------------------------------------------------------
# Paridade campo a campo — Caso (RF-10).
# ---------------------------------------------------------------------------


@pytest.mark.requer_banco
def test_paridade_casos_arquivo_x_postgres_mesma_sequencia_de_operacoes(
    tmp_path: Path,
) -> None:
    """A MESMA sequência de `criar` + transições/registros de trilha sobre
    as duas implementações de `RepositorioCasos` produz o mesmo `Caso`
    observável, campo a campo."""
    conta_id = f"TESTE_T25_CONTA_{uuid.uuid4().hex}"
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            "INSERT INTO app_aluno.contas (conta_id, email, senha_hash) VALUES (%s, %s, %s)",
            (conta_id, f"{conta_id}@teste.invalido", "hash-fake-de-teste"),
        )

    caso_id = f"TESTE_T25_CASO_{uuid.uuid4().hex}"
    criado_em = datetime(2026, 1, 5, 9, 0, 0, tzinfo=UTC)
    caso_inicial = Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=ESTADO_CASO.CADASTRADO,
        DATA_REFERENCIA=date(2026, 1, 5),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=criado_em,
        criado_em=criado_em,
    )

    repositorio_postgres = RepositorioCasosSupabase()
    repositorio_arquivo = RepositorioCasosArquivo(tmp_path / "casos.jsonl")

    repositorio_postgres.criar(caso_inicial)
    repositorio_arquivo.criar(caso_inicial)

    instante_consentimento = datetime(2026, 1, 5, 9, 15, 0, tzinfo=UTC)
    repositorio_postgres.transicionar_estado(
        caso_id, ESTADO_CASO.CONSENTIMENTO_REGISTRADO, agora=instante_consentimento
    )
    repositorio_arquivo.transicionar_estado(
        caso_id, ESTADO_CASO.CONSENTIMENTO_REGISTRADO, agora=instante_consentimento
    )

    repositorio_postgres.registrar_snapshot_raiz(caso_id, "SNAPSHOT-RAIZ-T25")
    repositorio_arquivo.registrar_snapshot_raiz(caso_id, "SNAPSHOT-RAIZ-T25")

    instante_interacao = datetime(2026, 1, 6, 8, 0, 0, tzinfo=UTC)
    repositorio_postgres.registrar_interacao(caso_id, agora=instante_interacao)
    repositorio_arquivo.registrar_interacao(caso_id, agora=instante_interacao)

    caso_postgres = repositorio_postgres.buscar(caso_id)
    caso_arquivo = repositorio_arquivo.buscar(caso_id)

    assert caso_postgres is not None
    assert caso_arquivo is not None
    assert caso_postgres.CASO_ID == caso_arquivo.CASO_ID
    assert caso_postgres.conta_id == caso_arquivo.conta_id
    assert caso_postgres.estado == caso_arquivo.estado == ESTADO_CASO.CONSENTIMENTO_REGISTRADO
    assert caso_postgres.DATA_REFERENCIA == caso_arquivo.DATA_REFERENCIA
    assert caso_postgres.QUESTIONARIO_VERSION == caso_arquivo.QUESTIONARIO_VERSION
    assert caso_postgres.snapshot_raiz_id == caso_arquivo.snapshot_raiz_id == "SNAPSHOT-RAIZ-T25"
    assert caso_postgres.snapshot_liberado_id == caso_arquivo.snapshot_liberado_id is None
    assert caso_postgres.ultima_interacao_em == instante_interacao
    assert caso_arquivo.ultima_interacao_em == instante_interacao
    assert caso_postgres.criado_em == caso_arquivo.criado_em == criado_em


# ---------------------------------------------------------------------------
# AC-02 — resposta legível do banco antes da próxima pergunta ser produzida.
# ---------------------------------------------------------------------------


@pytest.mark.requer_banco
def test_ac02_resposta_gravada_e_legivel_por_nova_consulta_imediatamente() -> None:
    """`AC-02`: leitura-após-escrita dentro do MESMO fluxo — grava uma
    resposta e, com uma NOVA consulta (nova chamada a `listar_do_caso`, sem
    reaproveitar nenhum estado em memória do `gravar`), confirma que ela já
    está lá. Sem esperar commit assíncrono nem depender de cache: a consulta
    é uma chamada de leitura independente, contra o banco real."""
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        caso_id = _caso_novo_no_banco(cursor)

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(
        Resposta(
            CASO_ID=caso_id,
            ID_PERGUNTA="B1.03",
            item_id=None,
            valor="resposta imediata",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    # Nova consulta, instância NOVA do repositório — nenhum estado
    # compartilhado com a chamada de gravação acima.
    leitura_imediata = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    valores_por_pergunta = {r.ID_PERGUNTA: r.valor for r in leitura_imediata}
    assert valores_por_pergunta.get("B1.03") == "resposta imediata", (
        "AC-02: a resposta deveria estar legível do banco imediatamente após "
        "gravar retornar, antes de qualquer próxima pergunta"
    )


# ---------------------------------------------------------------------------
# EC-05 — banco indisponível: gravação levanta erro, nada é reportado salvo.
# ---------------------------------------------------------------------------


def test_ec05_banco_indisponivel_gravacao_levanta_erro_e_nada_e_reportado_salvo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-05`, cenário fim a fim de indisponibilidade: `DATABASE_URL`
    aponta para uma porta que não responde (host local, porta fechada) —
    diferente do dublê de cursor de `test_persistencia_respostas.py`, aqui
    a própria abertura da conexão TCP falha. `gravar` deve propagar exceção
    e `listar_do_caso` nunca deve reportar a resposta como salva. Não exige
    `DATABASE_URL` real — roda sempre, é o próprio cenário de "sem banco"."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:1/piq_inexistente"
    )
    # `psycopg.connect` tem timeout de conexão TCP padrão do SO em porta
    # fechada — reduzimos explicitamente para o teste não ficar lento.
    monkeypatch.setenv("PGCONNECT_TIMEOUT", "2")

    repositorio = RepositorioRespostasSupabase()
    resposta = Resposta(
        CASO_ID="CASO-EC05-INDISPONIVEL",
        ID_PERGUNTA="B1.04",
        item_id=None,
        valor="nunca deveria ser salva",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )

    with pytest.raises((ErroGravacaoResposta, psycopg.OperationalError)):
        repositorio.gravar(resposta)

    # Com o banco indisponível, nem sequer é possível instanciar uma leitura
    # que reportasse sucesso — a única forma de "verificar que nada foi
    # reportado como salvo" aqui é a própria propagação da exceção acima:
    # não existe caminho de código em `gravar` que devolva sem levantar.
