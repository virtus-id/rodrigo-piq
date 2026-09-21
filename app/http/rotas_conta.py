"""Rotas de cadastro, login e logout — `RF-02`, `AC-03` (T-30).

Três formulários HTML nativos (`<form method="post">`, sem JavaScript):

- `GET/POST /conta/cadastro` — cria a conta e um `Caso` em `CADASTRADO`
  (`ESTADO_CASO.CADASTRADO`, `app/casos/maquina.py`, T-33), atomicamente via
  `persistencia.app_aluno.cadastro.cadastrar_conta_e_caso` (T-30): as duas
  gravações compartilham UMA ÚNICA transação Postgres — se a criação do caso
  falhar, a conta recém-criada é desfeita pelo mesmo `ROLLBACK`, nunca
  ficando "conta órfã sem caso" (mesma disciplina de transação de T-22/T-23:
  a função nunca reporta sucesso sem que AMBAS as linhas estejam commitadas).
- `GET/POST /conta/login` — autentica por `RepositorioContas.autenticar`
  (T-28: mesma mensagem para "conta inexistente" e "senha errada") e abre
  sessão via `iniciar_sessao_conta` (T-29).
- `POST /conta/logout` — encerra a sessão via `encerrar_sessao` (T-29); a
  requisição seguinte a uma rota que exige sessão perde `obter_conta_id`.

**Por que a transação de cadastro vive em `persistencia/app_aluno/
cadastro.py`, não neste módulo.** `RepositorioContasSupabase.criar` e
`RepositorioCasosSupabase.criar` (T-28/T-23) cada um abre e COMMITA a
própria conexão internamente — chamá-los em sequência não seria atômico.
`cadastrar_conta_e_caso` (novo módulo desta tarefa, `persistencia/app_aluno/
cadastro.py`) abre UMA conexão para os dois `INSERT`s. Colocar esse SQL
neste arquivo (`app/http/`) faria `tests/app_aluno/estatica/test_sem_
conteudo_de_questionario_no_codigo.py` (T-08, `AC-37`, já concluída,
INTOCADA por esta tarefa) marcar as strings de `INSERT` como "string longa
suspeita de conteúdo de questionário" — o limiar daquele teste (40
caracteres) não distingue SQL de enunciado por conteúdo, só por tamanho. A
mesma disciplina do resto do projeto (SQL vive em `persistencia/`, nunca em
`app/`) resolve isso sem alargar a lista de exceções daquele teste.

**Sem `python-multipart`.** O extra `app` (`pyproject.toml`) não declara
`python-multipart` — nenhum artefato desta feature o lista como dependência
decidida (diferente de `jinja2`, que o plano §2 já elege como a 4ª
dependência nova). `fastapi.Form(...)`/`Request.form()` exigem essa lib
mesmo para `application/x-www-form-urlencoded` (confirmado: `Starlette.
Request._get_form` importa `python_multipart.parse_options_header`
incondicionalmente). Em vez de introduzir uma dependência nova fora do
plano, `_ler_formulario` decodifica o corpo com `urllib.parse.parse_qsl`
(stdlib) — suficiente para o único `enctype` que um `<form method="post">`
nativo sem `enctype` explícito envia.

A tela de conta é React (`frontend/src/telas/TelaLogin.tsx`); estas
rotas devolvem JSON. Até `T-141` eram templates Jinja2 —
nenhum HTML depende de JavaScript: `action`/`method` nativos do `<form>`,
sem `onsubmit` obrigatório.

REGRAS: `RF-02`, `AC-03`
"""

from __future__ import annotations

from typing import Final
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.requests import HTTPConnection

from app.casos.maquina import Caso
from app.http.sessao import encerrar_sessao
from persistencia.app_aluno.cadastro import cadastrar_conta_e_caso
from persistencia.app_aluno.contas import (
    Conta,
    RepositorioContas,
    RepositorioContasSupabase,
)

REGRAS: Final[tuple[str, ...]] = ("RF-02", "AC-03")


roteador = APIRouter(prefix="/conta", tags=["conta"])


async def _ler_formulario(request: Request) -> dict[str, str]:
    """Decodifica `application/x-www-form-urlencoded` via stdlib — ver a
    nota do módulo sobre por que não usa `Request.form()`/`Form(...)`
    (exigiriam `python-multipart`, fora do plano)."""
    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return dict(pares)


def obter_repositorio_contas() -> RepositorioContas:
    """Ponto único de injeção do repositório de contas — sobrescrito nos
    testes via `app.dependency_overrides` para rodar sem `DATABASE_URL`."""
    return RepositorioContasSupabase()


class CadastroConta:
    """Ponto único de injeção do cadastro atômico — sobrescrito nos testes
    (`app.dependency_overrides`) por um dublê em memória, para rodar sem
    `DATABASE_URL`. Envelopa `cadastrar_conta_e_caso` (a implementação
    Postgres real, `persistencia/app_aluno/cadastro.py`) atrás de um
    `Protocol`-like callable."""

    def __call__(self, email: str, senha: str) -> tuple[Conta, Caso]:
        return cadastrar_conta_e_caso(email, senha)


def obter_cadastro_conta() -> CadastroConta:
    return CadastroConta()


_MENSAGEM_LOGIN_INVALIDO: Final[str] = "E-mail ou senha inválidos."
_MENSAGEM_CADASTRO_EMAIL_DUPLICADO: Final[str] = "Não foi possível concluir o cadastro."


@roteador.post("/logout")
def processar_logout(conexao: HTTPConnection) -> RedirectResponse:
    encerrar_sessao(conexao)
    return RedirectResponse(url="/conta/login", status_code=303)
