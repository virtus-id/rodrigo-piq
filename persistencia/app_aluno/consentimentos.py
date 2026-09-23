"""Adaptador Supabase/Postgres de consentimento — `RF-30`, `AC-39` (`PEND-01`).

Grava e lê `app.consentimento.registro.RegistroConsentimento` em
`app_aluno.consentimentos` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21), schema dedicado desta feature. Mesmo padrão de
conexão/transação de `persistencia/app_aluno/casos.py` e `respostas.py`
(T-22/T-23): reaproveita `obter_pool`/`ErroConexaoAusente` de
`persistencia.supabase.conexao` (genéricos, não amarrados a um schema) — o
MESMO pool do processo inteiro, `T-187`, nunca uma conexão própria — com
`search_path=app_aluno` fixado a cada checkout (a conexão física pode ter
servido `motor_calculo` no checkout anterior).

**Este módulo só grava o CARIMBO de aceite — nunca o texto.** `versao_texto`
é o identificador da versão (`QUESTIONARIO_VERSION` do texto vigente, lido
por `app.consentimento.registro.carregar_texto_vigente`); nenhuma redação de
`PEND-01` passa por aqui. É consultável por `CASO_ID` (`listar_do_caso`).

Direção de dependência: este módulo importa de `app.consentimento.registro`
(o tipo `RegistroConsentimento`) e de `psycopg`/stdlib — nunca de `engine/`
(escopo desta feature não toca o motor).

REGRAS: `RF-30`, `AC-39`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from app.consentimento.registro import RegistroConsentimento
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

REGRAS: Final[tuple[str, ...]] = ("RF-30", "AC-39")

_SCHEMA: Final[str] = "app_aluno"


class ErroGravacaoConsentimento(Exception):
    """Levantado quando a gravação de um consentimento falha antes do
    commit — nunca engolida: o chamador vê exatamente esta exceção (ou a
    original do driver, propagada), mesma disciplina de `EC-05` aplicada em
    `persistencia/app_aluno/respostas.py` (T-22)."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/respostas.py::_conectar`:
    `search_path` fixado em `app_aluno`, commit ao sair sem exceção,
    rollback e propagação ao sair com exceção."""
    pool = obter_pool()
    conexao = pool.getconn()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        pool.putconn(conexao)


def _como_utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


def _linha_para_registro(linha: tuple[Any, ...]) -> RegistroConsentimento:
    _consentimento_id, caso_id, versao_texto, aceite, aceito_em = linha
    return RegistroConsentimento(
        CASO_ID=caso_id,
        versao_texto=versao_texto,
        aceite=aceite,
        aceito_em=_como_utc(aceito_em),
    )


class RepositorioConsentimentos(Protocol):
    """Contrato do adaptador de consentimentos — `RepositorioConsentimentos
    Supabase` (abaixo) é a implementação Postgres; um futuro adaptador de
    arquivo (fora do escopo desta tarefa) implementaria o mesmo `Protocol`,
    mesmo precedente de `RepositorioCasos`/`RepositorioRespostas`."""

    def gravar(self, consentimento_id: str, registro: RegistroConsentimento) -> None:
        """Grava `registro`. `consentimento_id` é gerado pelo chamador
        antes desta chamada — este método só persiste o que recebe, nunca
        decide o identificador."""
        ...

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroConsentimento, ...]:
        """Todos os registros de consentimento de `caso_id`, em ordem de
        aceite — consultável por caso (critério de aceite de `T-35`)."""
        ...


class RepositorioConsentimentosSupabase:
    """Implementa `RepositorioConsentimentos` sobre `app_aluno.consentimentos`."""

    def gravar(self, consentimento_id: str, registro: RegistroConsentimento) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.consentimentos (
                        consentimento_id, "CASO_ID", versao_texto,
                        aceite, aceito_em
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        consentimento_id,
                        registro.CASO_ID,
                        registro.versao_texto,
                        registro.aceite,
                        registro.aceito_em,
                    ),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoConsentimento(
                f"falha ao gravar consentimento CASO_ID={registro.CASO_ID!r}: {erro}"
            ) from erro

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroConsentimento, ...]:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT consentimento_id, "CASO_ID", versao_texto, aceite, aceito_em
                FROM app_aluno.consentimentos
                WHERE "CASO_ID" = %s
                ORDER BY aceito_em ASC
                """,
                (caso_id,),
            )
            linhas = cursor.fetchall()

        return tuple(_linha_para_registro(linha) for linha in linhas)
