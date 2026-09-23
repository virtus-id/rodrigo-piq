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

**Pool de conexões, um único para o processo inteiro — `T-187`.** Medido em
produção (2026-09-23): o servidor da aplicação fica em Boston e o Postgres
em São Paulo — abrir uma conexão nova (TCP+TLS+autenticação) custa ~730ms;
rodar uma consulta numa conexão já aberta custa ~240ms. Antes desta tarefa,
`conectar()` abria e fechava uma conexão a cada chamada — todo request
pagava os ~730ms, mais de uma vez quando a rota tocava o banco mais de uma
vez (`GET /api/conta/eu` sozinha chega a ~4s assim). O pool devolve a
conexão para reaproveitamento em vez de fechá-la; o custo de abrir passa a
ser pago raramente (a cada crescimento do pool), não a cada requisição.

`obter_pool()` é o único ponto de criação — este módulo E todos os
`_conectar()` de `persistencia/app_aluno/*.py` (contas, casos, respostas,
tokens_acesso, revisoes, consentimentos, eventos, itens, cadastro) chamam
esta mesma função e recebem a MESMA instância. Não é decisão de estética:
um pool por módulo re-introduziria o problema, só que com N conexões
mínimas em vez de uma — o ganho do pool vem de ser compartilhado.

Direção de dependência: este módulo importa apenas de `psycopg`/`psycopg_pool`
/stdlib — nunca de `engine/` (lei nº 1 da §1 do plano: os adaptadores
concretos vivem em `persistencia/`, `engine/` não sabe que Postgres existe).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

import psycopg
from psycopg_pool import ConnectionPool

REGRAS: Final[tuple[str, ...]] = ("RF-12", "RF-13")

_NOME_VARIAVEL_AMBIENTE: Final[str] = "DATABASE_URL"
_SCHEMA: Final[str] = "motor_calculo"

# `max_connections` do Postgres é 60 (medido 2026-09-23) — compartilhado com
# TODOS os sistemas hospedados no mesmo projeto Supabase (`ads_*`, `core_*`,
# `trv_*`, `vtr_*`), não uma cota exclusiva do PIQ. 10 é conservador de
# propósito: sobra para os outros sistemas, e já é folgado para o piloto —
# cada checkout dura só o tempo de uma consulta (~240ms), não o request
# inteiro, então 10 conexões giram rápido o bastante para servir dezenas de
# alunos simultâneos sem fila. Subir este número é uma linha, quando o
# piloto crescer o bastante para justificar — não antes.
_TAMANHO_MINIMO_POOL: Final[int] = 2
_TAMANHO_MAXIMO_POOL: Final[int] = 10

_pool: ConnectionPool | None = None
# Trava só para a CRIAÇÃO do pool (dupla checagem abaixo) — o pool em si já
# é thread-safe por desenho do psycopg_pool; `getconn`/`putconn` não
# precisam desta trava.
_trava_criacao_do_pool: Final[threading.Lock] = threading.Lock()


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


def obter_pool() -> ConnectionPool:
    """O pool de conexões do processo — um único, nunca um por módulo
    (`T-187`). Ver a nota do módulo para a medição que justifica existir.

    **Criado só na primeira chamada, nunca na importação do módulo.** Um
    pool aberto no import faria `DATABASE_URL` ausente derrubar a
    aplicação ao SUBIR, não ao ATENDER a primeira requisição que precisa
    de banco — mudaria o comportamento que `ErroConexaoAusente` documenta
    (os adaptadores de arquivo continuam funcionando sem banco nenhum) e
    quebraria toda a suíte de testes que roda sem `DATABASE_URL`.

    **Trava de dupla checagem.** A primeira requisição concorrente pode
    encontrar `_pool is None` em mais de uma thread ao mesmo tempo (o
    Starlette atende rotas síncronas numa threadpool) — sem a trava, duas
    pools nasceriam e uma ficaria órfã, com conexões abertas que ninguém
    mais devolve nem fecha."""
    global _pool
    if _pool is None:
        with _trava_criacao_do_pool:
            if _pool is None:  # ainda `None` depois de esperar a trava?
                _pool = ConnectionPool(
                    obter_database_url(),
                    min_size=_TAMANHO_MINIMO_POOL,
                    max_size=_TAMANHO_MAXIMO_POOL,
                    open=True,
                )
    return _pool


@contextmanager
def conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Retira uma conexão do pool compartilhado (`obter_pool`), com
    `search_path` fixado em `motor_calculo` — todas as consultas feitas
    dentro do `with` resolvem tabelas sem qualificação de schema contra
    `motor_calculo`, nunca contra `public` ou os schemas de outros sistemas
    que compartilham o mesmo banco.

    **O `SET search_path` roda a CADA checkout, não uma vez só.** A mesma
    conexão física pode ter servido `app_aluno` no checkout anterior — sem
    fixar de novo aqui, uma consulta sem qualificação de schema resolveria
    contra o schema errado, silenciosamente.

    Reutilizável por `FonteParametrosSupabase` e `RepositorioSnapshotsSupabase`
    — um único ponto de retirada/devolução de conexão, sem duplicar a
    lógica de `search_path` em cada adaptador.
    """
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
