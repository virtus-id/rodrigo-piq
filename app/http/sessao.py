"""Helpers de leitura/escrita da identidade da conta na sessão — `RF-02`,
`AC-03`.

`plans/app-aluno.plan.md` §7 (State Management) é explícito: a sessão
**nunca** contém dado financeiro nem autoriza acesso por si só — ela só
carrega a identidade da conta, e o isolamento por `CASO_ID` é reverificado
**no servidor**, a cada requisição, por quem lê o banco (`app/http/
isolamento.py`, T-31 — fora do escopo desta tarefa). Este módulo isola o
resto da aplicação do **formato interno** da sessão: nenhum outro arquivo
lê/escreve a chave do dicionário de sessão diretamente — todos passam por
`obter_conta_id`/`iniciar_sessao_conta`/`encerrar_sessao`.

O que a sessão carrega, e só isso: `conta_id`. Nunca `CASO_ID` de terceiros,
nunca valor monetário, nunca papel autorizador (não existe "é revisor" na
sessão — quem decide isso é uma consulta ao banco, não um bit no cookie).

**`T-100` concretiza essa garantia**: `app/http/isolamento.py::
exigir_papel_revisor` consulta `RepositorioContas.buscar_por_id(conta_id)` a
cada requisição para ler `e_revisor` — este módulo nunca ganhou (e não deve
ganhar) uma chave `e_revisor` na sessão.

REGRAS: `RF-02`
"""

from __future__ import annotations

from typing import Final

from starlette.requests import HTTPConnection

# Única chave que este módulo grava/lê na sessão. Nenhum outro arquivo deve
# indexar `request.session[...]` diretamente — é isso que garante que o
# formato interno da sessão pode mudar sem tocar em rotas.
_CHAVE_CONTA_ID: Final[str] = "conta_id"


def iniciar_sessao_conta(conexao: HTTPConnection, conta_id: str) -> None:
    """Abre a sessão da conta autenticada, gravando **apenas** `conta_id`.
    Chamado pela rota de login (T-30) após senha verificada — nunca antes."""
    conexao.session[_CHAVE_CONTA_ID] = conta_id


def obter_conta_id(conexao: HTTPConnection) -> str | None:
    """`conta_id` da sessão corrente, ou `None` se não houver sessão aberta.
    Devolver `None` aqui NUNCA autoriza acesso a nada por si só — é dado
    apenas de identidade; a checagem de posse do `CASO_ID` é sempre uma
    consulta ao banco, feita por quem depende deste valor (`AC-03`)."""
    valor = conexao.session.get(_CHAVE_CONTA_ID)
    return valor if isinstance(valor, str) else None


def encerrar_sessao(conexao: HTTPConnection) -> None:
    """Logout: limpa toda a sessão. A requisição seguinte não carrega mais
    `conta_id` nenhum."""
    conexao.session.clear()
