"""Adaptador Supabase/Postgres da trilha de progresso do caso — `RF-31`,
`AC-40` (T-21), consumido por `app/casos/acompanhamento.py::
registrar_alteracao_cadastral` (`T-87`, `AC-35`).

Grava e lê `app_aluno.eventos_caso` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21) — tabela já criada por aquela migração e, até esta
tarefa, sem nenhum repositório que a usasse (confirmado por busca: nenhum
`.py` do projeto referenciava `eventos_caso` antes de `T-87`). Mesmo padrão
de conexão/transação/commit/rollback de `persistencia/app_aluno/casos.py`
(T-23) e `persistencia/app_aluno/respostas.py` (T-22): reaproveita
`obter_database_url`/`ErroConexaoAusente` de `persistencia.supabase.conexao`
(genéricos, não amarrados a um schema), com `search_path=app_aluno` fixado
por conexão própria deste adaptador.

**Registrar um evento na trilha NUNCA muda `estado`.** `registrar` só faz um
`INSERT` em `eventos_caso` — nenhuma linha deste módulo toca a coluna
`estado` de `app_aluno.casos`, nem chama `app.casos.maquina.transicionar`
nem `persistencia.app_aluno.casos.RepositorioCasos.transicionar_estado*`.
`estado_de`/`estado_para` (colunas opcionais da migração) existem para as
transições REAIS registrarem de onde/para onde foi o estado — este
repositório os aceita como `None` quando o evento não é uma transição (o
caso de `T-87`: alteração cadastral não muda o estado do caso, então ambos
ficam `NULL`, nunca um valor inventado).

Direção de dependência: este módulo importa de `psycopg`/stdlib e de
`persistencia.supabase.conexao` — nunca de `engine/` (escopo desta feature
não toca o motor).

REGRAS: `RF-31`, `AC-40`, `AC-35`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-31", "AC-40", "AC-35")

_SCHEMA: Final[str] = "app_aluno"


class ErroGravacaoEventoCaso(Exception):
    """Mesma disciplina de `persistencia.app_aluno.casos.ErroGravacaoCaso`
    (`EC-05`): levantada quando o `INSERT` falha antes do commit — nunca
    engolida, nunca reportando um evento como registrado sem transação
    confirmada."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/casos.py::_conectar`."""
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


class EventoCaso:
    """Uma linha da trilha — `evento_id` é gerado pelo CHAMADOR (mesmo
    precedente de `app/http/rotas_consentimento.py`/`rotas_revisao.py`:
    `f"EVENTO_{uuid.uuid4().hex}"`), nunca por este repositório."""

    __slots__ = (
        "evento_id",
        "CASO_ID",
        "tipo_evento",
        "estado_de",
        "estado_para",
        "detalhe",
        "ocorrido_em",
    )

    def __init__(
        self,
        *,
        evento_id: str,
        CASO_ID: str,
        tipo_evento: str,
        estado_de: str | None,
        estado_para: str | None,
        detalhe: str | None,
        ocorrido_em: datetime,
    ) -> None:
        self.evento_id = evento_id
        self.CASO_ID = CASO_ID
        self.tipo_evento = tipo_evento
        self.estado_de = estado_de
        self.estado_para = estado_para
        self.detalhe = detalhe
        self.ocorrido_em = ocorrido_em


class RepositorioEventosCaso(Protocol):
    """Contrato do adaptador da trilha do caso — `RepositorioEventosCasoSupabase`
    (abaixo) é a implementação Postgres; `persistencia/app_aluno/arquivo.py`
    (T-24) é a implementação de arquivo sobre o MESMO `Protocol`."""

    def registrar(self, evento: EventoCaso) -> None:
        """Grava uma linha em `eventos_caso`. Nunca decide sobre `estado` de
        `app_aluno.casos` — só registra o fato na trilha (`RF-31`,
        `AC-40`)."""
        ...

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        """Toda a trilha do caso, em qualquer ordem estável — a ordenação
        por `ocorrido_em`, quando necessária, é decisão do chamador."""
        ...


class RepositorioEventosCasoSupabase:
    """Implementa `RepositorioEventosCaso` sobre `app_aluno.eventos_caso`."""

    def registrar(self, evento: EventoCaso) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.eventos_caso (
                        evento_id, "CASO_ID", tipo_evento, estado_de,
                        estado_para, detalhe, ocorrido_em
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        evento.evento_id,
                        evento.CASO_ID,
                        evento.tipo_evento,
                        evento.estado_de,
                        evento.estado_para,
                        evento.detalhe,
                        evento.ocorrido_em,
                    ),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoEventoCaso(
                f"falha ao registrar evento_id={evento.evento_id!r} "
                f"CASO_ID={evento.CASO_ID!r}: {erro}"
            ) from erro

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT evento_id, "CASO_ID", tipo_evento, estado_de,
                       estado_para, detalhe, ocorrido_em
                FROM app_aluno.eventos_caso
                WHERE "CASO_ID" = %s
                """,
                (caso_id,),
            )
            linhas = cursor.fetchall()
        return tuple(_linha_para_evento(linha) for linha in linhas)


def _linha_para_evento(linha: tuple[Any, ...]) -> EventoCaso:
    (
        evento_id,
        caso_id,
        tipo_evento,
        estado_de,
        estado_para,
        detalhe,
        ocorrido_em,
    ) = linha
    return EventoCaso(
        evento_id=evento_id,
        CASO_ID=caso_id,
        tipo_evento=tipo_evento,
        estado_de=estado_de,
        estado_para=estado_para,
        detalhe=detalhe,
        ocorrido_em=_como_utc(ocorrido_em),
    )


def _como_utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)
