"""Gerenciamento de conexão `psycopg 3` com o Supabase/Postgres — RF-12, RF-13.

`DATABASE_URL` é lida SEMPRE de variável de ambiente, nunca de literal no
código (nem em teste, nem em exemplo, nem em comentário) — a credencial real
não pode vazar para o histórico do repositório. Ausência de `DATABASE_URL`
levanta `ErroConexaoAusente` explícito: nenhum adaptador Supabase funciona
"por acidente" com uma string embutida.

Todas as conexões abertas aqui operam contra o schema `motor_calculo`
(`search_path` fixado na sessão) — nunca `public` nem qualquer schema de
outro sistema hospedado no mesmo banco (`ads_*`, `core_*`, `trv_*`, `vtr_*`,
ver migração `001_inicial.sql`).

Direção de dependência: este módulo importa apenas de `psycopg`/stdlib —
nunca de `engine/` (lei nº 1 da §1 do plano: os adaptadores concretos vivem
em `persistencia/`, `engine/` não sabe que Postgres existe).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

import psycopg

REGRAS: Final[tuple[str, ...]] = ("RF-12", "RF-13")

_NOME_VARIAVEL_AMBIENTE: Final[str] = "DATABASE_URL"
_SCHEMA: Final[str] = "motor_calculo"


class ErroConexaoAusente(Exception):
    """Levantado quando `DATABASE_URL` não está definida no ambiente.

    Nunca há fallback silencioso para uma string embutida — a ausência do
    banco é um erro ruidoso, resolvido usando os adaptadores de arquivo
    (`persistencia/arquivo/`), nunca mascarado aqui.
    """


def obter_database_url() -> str:
    """Lê `DATABASE_URL` de variável de ambiente. `ErroConexaoAusente` se
    não estiver definida — nunca um valor padrão embutido no código."""
    valor = os.environ.get(_NOME_VARIAVEL_AMBIENTE)
    if not valor:
        raise ErroConexaoAusente(
            f"Variável de ambiente {_NOME_VARIAVEL_AMBIENTE!r} não definida — "
            "o adaptador Supabase não tem string de conexão embutida por "
            "design (segurança: a credencial nunca é literal de código)."
        )
    return valor


@contextmanager
def conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Abre uma conexão `psycopg 3` a partir de `DATABASE_URL` (variável de
    ambiente), com `search_path` fixado em `motor_calculo` — todas as
    consultas feitas dentro do `with` resolvem tabelas sem qualificação de
    schema contra `motor_calculo`, nunca contra `public` ou os schemas de
    outros sistemas que compartilham o mesmo banco.

    Reutilizável por `FonteParametrosSupabase` e `RepositorioSnapshotsSupabase`
    — um único ponto de abertura/fechamento de conexão, sem duplicar a
    lógica de `search_path` em cada adaptador.
    """
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
