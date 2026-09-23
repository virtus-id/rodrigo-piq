"""Adaptador Supabase/Postgres de revisões — `RF-24` (`AC-27`), T-67.

Grava e lê `app.revisao.fila.RegistroRevisao` em `app_aluno.revisoes`
(`persistencia/supabase/migracoes/002_app_aluno.sql`, T-21), schema dedicado
desta feature. Mesmo padrão de conexão/transação de `persistencia/app_aluno/
casos.py`, `respostas.py` e `consentimentos.py` (T-22/T-23/T-35): reaproveita
`obter_pool`/`ErroConexaoAusente` de `persistencia.supabase.conexao`
(genéricos, não amarrados a um schema) — o MESMO pool do processo inteiro,
`T-187`, nunca uma conexão própria — com `search_path=app_aluno` fixado a
cada checkout (a conexão física pode ter servido `motor_calculo` no
checkout anterior).

**Append-only, mesmo padrão estrutural de `RepositorioSnapshots`
(`engine/portas.py`).** `RepositorioRevisoes` expõe exatamente `gravar`,
`obter` e `listar_do_caso` — **não existe `atualizar` nem `remover`** no
`Protocol`: a violação de `AC-27` ("o registro não pode ser alterado nem
removido por nenhuma rota") é estruturalmente INEXPRIMÍVEL nesta interface,
não uma checagem em runtime — não há verbo de mutação para nenhuma rota
chamar. A tabela `app_aluno.revisoes` reforça a mesma garantia do lado do
banco (`REVOKE UPDATE, DELETE FROM PUBLIC` + trigger
`impedir_sobrescrita_revisao_v01`, T-21): mesmo um adaptador futuro com bug
que tentasse `UPDATE`/`DELETE` diretamente via SQL seria recusado pelo
Postgres.

**Liberação e reprovação são ambas gravadas pelo mesmo `gravar`** — não há
dois métodos nem dois caminhos de código: `RegistroRevisao.decisao`
(`DECISAO_REVISAO.LIBERADO`/`REPROVADO`) já carrega a distinção, e este
adaptador só persiste o que recebe, sem decidir política de revisão
(`app/revisao/fila.py` é quem define os dois sinais que levam a essa
decisão).

**`classificacao_erro` (`RF-26`, `T-72`).** Persistido/lido como o `.value`
(string) do enum `app.revisao.fila.CLASSIFICACAO_ERRO` — a coluna do banco
continua `text`, sem migração de schema (T-21 já a criava como texto
livre); a validação de domínio fechado acontece inteiramente no tipo
Python, na fronteira deste adaptador (`_linha_para_registro`/`gravar`).

Direção de dependência: este módulo importa de `app.revisao.fila` (os tipos
`RegistroRevisao`/`DECISAO_REVISAO`/`CLASSIFICACAO_ERRO`) e de
`psycopg`/stdlib — nunca de `engine/` (escopo desta feature não toca o
motor).

REGRAS: `RF-24`, `AC-27`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from app.revisao.fila import CLASSIFICACAO_ERRO, DECISAO_REVISAO, RegistroRevisao
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

REGRAS: Final[tuple[str, ...]] = ("RF-24", "AC-27")

_SCHEMA: Final[str] = "app_aluno"


class ErroGravacaoRevisao(Exception):
    """Levantado quando a gravação de uma revisão falha antes do commit —
    nunca engolida: o chamador vê exatamente esta exceção (ou a original do
    driver, propagada), mesma disciplina de `EC-05` aplicada em
    `persistencia/app_aluno/respostas.py` (T-22)."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/casos.py::_conectar`:
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


def _linha_para_registro(linha: tuple[Any, ...]) -> RegistroRevisao:
    (
        _revisao_id,
        snapshot_id,
        caso_id,
        decisao,
        autor,
        decidido_em,
        classificacao_erro,
        observacao,
    ) = linha
    return RegistroRevisao(
        SNAPSHOT_ID=snapshot_id,
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO(decisao),
        autor=autor,
        decidido_em=_como_utc(decidido_em),
        classificacao_erro=(
            CLASSIFICACAO_ERRO(classificacao_erro) if classificacao_erro is not None else None
        ),
        observacao=observacao,
    )


class RepositorioRevisoes(Protocol):
    """Contrato do adaptador de revisões — `RepositorioRevisoesSupabase`
    (abaixo) é a implementação Postgres. **Só `gravar`, `obter` e
    `listar_do_caso`** — mesmo precedente EXATO de `engine/portas.py::
    RepositorioSnapshots`: nenhum `atualizar`/`remover` é declarado aqui, e
    por isso nenhuma implementação deste `Protocol` pode ser chamada para
    mutar ou apagar um registro já gravado (`AC-27`)."""

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        """Grava `registro` — liberação ou reprovação, pelo mesmo caminho.
        `revisao_id` é gerado pelo chamador antes desta chamada, mesmo
        precedente de `RepositorioConsentimentos.gravar` (T-35): este método
        só persiste o que recebe, nunca decide o identificador. Append-only:
        cada chamada é uma NOVA linha, nunca a atualização de uma
        existente."""
        ...

    def obter(self, revisao_id: str) -> RegistroRevisao | None:
        """`None` se `revisao_id` não existir — nunca lança para "não
        encontrado", só para falha de acesso ao banco (mesmo contrato de
        `RepositorioCasos.buscar`)."""
        ...

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroRevisao, ...]:
        """Todos os registros de revisão de `caso_id`, em ordem de decisão
        — consultável por caso, mesmo precedente de `RepositorioConsentimentos.
        listar_do_caso` (T-35)."""
        ...


class RepositorioRevisoesSupabase:
    """Implementa `RepositorioRevisoes` sobre `app_aluno.revisoes`."""

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.revisoes (
                        revisao_id, snapshot_id, "CASO_ID", decisao, autor,
                        decidido_em, classificacao_erro, observacao
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        revisao_id,
                        registro.SNAPSHOT_ID,
                        registro.CASO_ID,
                        registro.decisao.value,
                        registro.autor,
                        registro.decidido_em,
                        (
                            registro.classificacao_erro.value
                            if registro.classificacao_erro is not None
                            else None
                        ),
                        registro.observacao,
                    ),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoRevisao(
                f"falha ao gravar revisão SNAPSHOT_ID={registro.SNAPSHOT_ID!r} "
                f"CASO_ID={registro.CASO_ID!r}: {erro}"
            ) from erro

    def obter(self, revisao_id: str) -> RegistroRevisao | None:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT revisao_id, snapshot_id, "CASO_ID", decisao, autor,
                       decidido_em, classificacao_erro, observacao
                FROM app_aluno.revisoes
                WHERE revisao_id = %s
                """,
                (revisao_id,),
            )
            linha = cursor.fetchone()

        return _linha_para_registro(linha) if linha is not None else None

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroRevisao, ...]:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT revisao_id, snapshot_id, "CASO_ID", decisao, autor,
                       decidido_em, classificacao_erro, observacao
                FROM app_aluno.revisoes
                WHERE "CASO_ID" = %s
                ORDER BY decidido_em ASC
                """,
                (caso_id,),
            )
            linhas = cursor.fetchall()

        return tuple(_linha_para_registro(linha) for linha in linhas)
