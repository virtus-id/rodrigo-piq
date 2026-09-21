"""Rota de keep-alive do banco durante a janela do piloto — `RF-10`, `EC-05`
(T-94).

**Por que esta rota existe, separada de `/saude`.** `app/http/aplicacao.py`
já registra `GET /saude` (T-29), de propósito **liveness**: responde sem
tocar `persistencia/` nem `engine/`, prova só que o processo está de pé.
Este módulo registra uma rota SEPARADA, `GET /saude/banco`, que TOCA o banco
de propósito — para ser chamada por um agendador EXTERNO (cron, GitHub
Actions, etc., ver `docs/operacao-piloto.md`) durante a janela do piloto, e
manter o Supabase free tier fora da pausa por inatividade (~7 dias sem
atividade, `plans/app-aluno.plan.md` §6/§10). Nenhuma dependência nova de
agendamento entra no projeto — o agendamento em si é infraestrutura externa
ao processo ASGI, exatamente como o plano descreve ("keep-alive agendado",
sem introduzir `apscheduler`/similar fora do extra `app` já decidido).

**A query é mínima e só de leitura, por desenho.** `SELECT 1` puro — sem
nome de tabela, sem schema, sem `app_aluno.contas`/`.respostas`/`.casos`.
Nenhum dado do aluno é lido, listado ou tocado por esta rota (critério de
aceite desta tarefa); o único propósito é manter a conexão viva contra o
projeto Supabase, não inspecionar ou validar dado nenhum. Por não depender
de nenhum schema desta feature, a rota reaproveita `persistencia.supabase.
conexao.obter_database_url`/`ErroConexaoAusente` (módulo genérico e
congelado, `AC-44`) sem abrir conexão própria com `search_path` fixado —
`SET search_path` não é necessário para `SELECT 1`.

**`EC-05` já é tratado, não reimplementado aqui.** A mensagem honesta ao
aluno ("não foi possível salvar" — ver `_MENSAGEM_FALHA_SALVAR` em
`app/http/rotas_coleta.py`, T-42) e a garantia de que nenhuma resposta é
reportada como persistida sem ter sido já existem naquela rota, que é o
ÚNICO caminho de gravação de resposta de coleta. Esta rota de keep-alive não
grava resposta nenhuma e não altera aquele comportamento — ela só reduz a
FREQUÊNCIA com que `EC-05` chega a ocorrer durante o piloto, ao manter o
banco acordado. Quando o banco está de fato indisponível (pausado ou não
respondendo), `GET /saude/banco` devolve `503` com a mesma mensagem curta de
propósito, para o agendador externo (e um operador olhando o log) enxergar
o mesmo estado que o aluno veria ao tentar responder.

Direção de dependência: este módulo importa de `fastapi`/stdlib e de
`persistencia.supabase.conexao` — nunca de `engine/`, nunca de
`persistencia.app_aluno.*` (nenhuma tabela de dado do aluno é referenciada).

REGRAS: `RF-10`, `EC-05`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Final

import psycopg
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-10", "EC-05")

roteador = APIRouter(tags=["saude"])

# Mensagem curta de propósito — mesma disciplina de `app/http/rotas_coleta.py`
# (`AC-37`, T-08): fica sob o limiar de 40 caracteres do teste estático.
_MENSAGEM_BANCO_INDISPONIVEL: Final[str] = "banco indisponível"


class ErroTocarBanco(Exception):
    """Levantado quando a query mínima de keep-alive falha — conexão
    recusada, timeout ou banco pausado. Nunca engolida silenciosamente: o
    chamador (a rota HTTP) devolve `503`, nunca `200` sobre uma falha real."""


def tocar_banco() -> None:
    """Query mínima de keep-alive: `SELECT 1` puro, sem tabela nenhuma —
    nenhum dado do aluno é lido (critério de aceite desta tarefa). Levanta
    `ErroTocarBanco`/`ErroConexaoAusente` em qualquer falha; nunca devolve
    silenciosamente um "sucesso" que não ocorreu."""
    try:
        with psycopg.connect(obter_database_url()) as conexao:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except ErroConexaoAusente:
        raise
    except psycopg.Error as erro:
        raise ErroTocarBanco(str(erro)) from erro


def obter_funcao_tocar_banco() -> Callable[[], None]:
    """Ponto único de injeção de `tocar_banco` — sobrescrito nos testes via
    `app.dependency_overrides`, mesmo padrão de `app/http/isolamento.py::
    obter_repositorio_casos`, para provar `200`/`503` sem depender de
    Postgres real no caminho de erro."""
    return tocar_banco


@roteador.get("/saude/banco")
def saude_banco(
    funcao_tocar_banco: Annotated[Callable[[], None], Depends(obter_funcao_tocar_banco)],
) -> JSONResponse:
    """`GET /saude/banco`: toca o banco com a query mínima acima e devolve
    `200` se a conexão respondeu, `503` caso contrário — nunca reporta
    sucesso sobre uma conexão que falhou (mesma disciplina de `EC-05` já
    aplicada em `app/http/rotas_coleta.py`, T-42, para a gravação de
    resposta). Alvo do agendador externo do keep-alive durante o piloto."""
    try:
        funcao_tocar_banco()
    except (ErroConexaoAusente, ErroTocarBanco):
        return JSONResponse(
            status_code=503,
            content={"status": "erro", "detalhe": _MENSAGEM_BANCO_INDISPONIVEL},
        )
    return JSONResponse(status_code=200, content={"status": "ok"})
