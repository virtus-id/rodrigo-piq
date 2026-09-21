"""Cadastro atômico de `Conta` + `Caso` — `RF-02`, `AC-03` (T-30).

`RepositorioContasSupabase.criar` (T-28) e `RepositorioCasosSupabase.criar`
(T-23), cada um em `persistencia/app_aluno/{contas,casos}.py`, abrem e
COMMITAM a própria conexão internamente — chamá-los em sequência não seria
atômico (a conta commitaria antes de o caso sequer começar a ser gravado).
Como `app_aluno.contas` e `app_aluno.casos` vivem no MESMO banco Postgres
(schema `app_aluno`; `casos.conta_id` é FK de `contas.conta_id`), a
atomicidade real exige as duas gravações na MESMA conexão/transação — este
módulo existe só para isso: `cadastrar_conta_e_caso` abre UMA conexão
(reaproveitando `obter_database_url`, genérico, e `app.http.senhas.
hashear_senha`, puro) e faz os dois `INSERT`s antes de um único commit. Se o
segundo falhar, o `ROLLBACK` desfaz também o primeiro — nunca uma conta
órfã sem caso.

Este módulo vive em `persistencia/` (não em `app/http/rotas_conta.py`, que o
chama) pela mesma razão que todo SQL desta feature vive em `persistencia/`:
é a fronteira que os testes estáticos de `app/` (T-08, `AC-37`) varrem à
procura de conteúdo de questionário — strings de SQL não são conteúdo de
pergunta, mas são longas o bastante para acionar o limiar heurístico
daquele teste. Isolar o SQL aqui, junto dos demais adaptadores da feature,
evita alargar a lista de exceções daquele teste com um padrão amplo demais.

Direção de dependência: este módulo importa de `app.http.senhas` (hash
puro), `app.casos.maquina` (`ESTADO_CASO`/`Caso`, tipos de domínio) e
`persistencia.app_aluno.contas` (`Conta`, `ErroEmailDuplicado`) e de
`psycopg`/stdlib — nunca de `engine/`.

REGRAS: `RF-02`, `AC-03`
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Final

import psycopg

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.senhas import hashear_senha
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado
from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-02", "AC-03")

_SCHEMA: Final[str] = "app_aluno"

# QUESTIONARIO_VERSION do caso recém-cadastrado. `collection/carga.py`
# (T-16) expõe a versão corrente dos registros — este módulo não decide o
# número, só evita um literal solto: fixado aqui por não haver, nesta
# tarefa, ainda um ponto único de "versão corrente do questionário"
# consumido por T-30 (o valor é sobrescrito pela carga real quando o Bloco
# 1 começa, fora deste escopo).
QUESTIONARIO_VERSION_INICIAL: Final[str] = "PENDENTE"


class ErroCadastro(Exception):
    """Levantado quando o cadastro atômico de conta+caso falha antes do
    commit — nunca engolida: nem a conta nem o caso ficam persistidos
    parcialmente (mesma disciplina de `EC-05` de T-22/T-23)."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/casos.py::_conectar`:
    `search_path` fixado em `app_aluno`, commit ao sair sem exceção,
    rollback e propagação ao sair com exceção — reescrito aqui (não
    reaproveitado) pelas mesmas razões documentadas naquele módulo:
    `persistencia.supabase.conexao.conectar` fixa `search_path=motor_calculo`
    e está congelado (`AC-44`)."""
    conexao = psycopg.connect(obter_database_url())
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def cadastrar_conta_e_caso(email: str, senha: str) -> tuple[Conta, Caso]:
    """Cria `Conta` e `Caso` (em `ESTADO_CASO.CADASTRADO`) na MESMA
    transação: se o `INSERT` do caso falhar, o `ROLLBACK` desfaz também o
    `INSERT` da conta — nunca uma conta órfã sem caso. Levanta
    `ErroEmailDuplicado` se `email` já existir (mesma exceção de
    `RepositorioContasSupabase.criar`, T-28)."""
    conta_id = f"CONTA_{uuid.uuid4().hex}"
    caso_id = f"CASO_{uuid.uuid4().hex}"
    senha_hash = hashear_senha(senha)
    agora = datetime.now(UTC)
    hoje = date.today()

    try:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_aluno.contas "
                "(conta_id, email, senha_hash, criado_em) VALUES (%s, %s, %s, %s)",
                (conta_id, email, senha_hash, agora),
            )
            cursor.execute(
                'INSERT INTO app_aluno.casos ("CASO_ID", conta_id, estado, '
                '"DATA_REFERENCIA", "QUESTIONARIO_VERSION", snapshot_raiz_id, '
                "snapshot_liberado_id, ultima_interacao_em, criado_em) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    caso_id,
                    conta_id,
                    ESTADO_CASO.CADASTRADO.value,
                    hoje,
                    QUESTIONARIO_VERSION_INICIAL,
                    None,
                    None,
                    agora,
                    agora,
                ),
            )
    except ErroConexaoAusente:
        raise
    except psycopg.errors.UniqueViolation as erro:
        raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}") from erro
    except psycopg.Error as erro:
        raise ErroCadastro(f"falha ao cadastrar conta+caso email={email!r}: {erro}") from erro

    conta = Conta(conta_id=conta_id, email=email, senha_hash=senha_hash, criado_em=agora)
    caso = Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=ESTADO_CASO.CADASTRADO,
        DATA_REFERENCIA=hoje,
        QUESTIONARIO_VERSION=QUESTIONARIO_VERSION_INICIAL,
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=agora,
        criado_em=agora,
    )
    return conta, caso
