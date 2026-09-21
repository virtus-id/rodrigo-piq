"""Dependência de isolamento por `CASO_ID` — `RF-02`, `AC-03` (T-31).

`plans/app-aluno.plan.md` §5.1, passo 1: toda rota que carrega um `CASO_ID`
verifica, **no servidor**, se a sessão corrente possui aquele caso. Nunca se
confia no cookie nem na interface — o cookie de `app/http/sessao.py` só
carrega `conta_id`, e um `CASO_ID` de terceiro colado na URL/formulário por
qualquer meio (edição manual, réplay, JavaScript de terceiros) é recusado
aqui, antes de o handler da rota ler qualquer dado do caso.

**Fábrica, não decorador fixo.** `exigir_caso_da_sessao(nome_parametro)`
devolve uma dependência do FastAPI parametrizada pelo nome do path/query
parameter que carrega o `CASO_ID` daquela rota — cada rota futura (coleta,
plano, revisão, item repetido por `DIVIDA_ID`/`MARGEM_ID`) declara
`Depends(exigir_caso_da_sessao("caso_id"))` (ou o nome que usar) na sua
assinatura. Hoje NENHUMA rota real recebe `CASO_ID` (as rotas de coleta,
plano e revisão são tarefas futuras da Entrega 5+) — esta tarefa entrega só
o mecanismo, auditável por `tests/app_aluno/e2e/test_isolamento_por_caso.py`
(T-32), que enumera `app.routes` e prova que toda rota registrada com
`CASO_ID` declara esta dependência.

**Ordem das verificações (a única que a spec autoriza):**
1. Sessão ausente ⇒ `401`, ANTES de qualquer leitura de dado do caso —
   `obter_conta_id` devolvendo `None` nunca chega a consultar o banco.
2. Sessão presente ⇒ consulta `RepositorioCasos.pertence_a_conta`, SEMPRE
   contra o banco, a cada requisição — nunca um valor gravado em sessão
   (`app/http/sessao.py` documenta a mesma garantia do lado de quem grava:
   a sessão não carrega papel autorizador nem posse de caso).
3. Caso inexistente OU de outra conta ⇒ `404`, nunca `403` — as duas
   situações produzem exatamente o mesmo resultado observável
   (`RepositorioCasos.pertence_a_conta` já funde as duas em um só booleano),
   para que a existência do caso de terceiro não vaze.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.sessao` e dos `Protocol`s `RepositorioCasos`/`RepositorioContas`
(`persistencia.app_aluno.casos`/`persistencia.app_aluno.contas`) — nunca de
`engine/`.

**`exigir_papel_revisor` (`RF-23`, `RF-25`, T-100).** Segunda dependência
reutilizável deste módulo, fechando a lacuna que `app/http/rotas_revisao.py`
(T-69) documentou honestamente: `/revisao/*` ficava sem autenticação
própria. O MESMO PRECEDENTE de `exigir_caso_da_sessao` é replicado aqui —
sessão ausente recusa ANTES de qualquer leitura de dado (`401`), e a posse
do papel de revisor é consultada no banco A CADA REQUISIÇÃO, sem nenhum
cache em sessão (`app/http/sessao.py` nunca grava `e_revisor` — só
`conta_id`). A única diferença de resultado em relação a `exigir_caso_da_
sessao`: aqui uma sessão de conta EXISTENTE mas sem o papel devolve `403`,
nunca `404` — a existência da tela de revisão não é segredo (é um recurso
conhecido do sistema), só o ACESSO é negado a quem não tem o papel. Isso é
deliberadamente diferente da disciplina de `exigir_caso_da_sessao` (que
funde "não existe" e "não é meu" em um único `404` para não vazar a
existência de um caso de OUTRA CONTA) — não há aqui um recurso de terceiro
cuja existência precise ficar oculta, só um papel que falta.

**Não recria o sistema de papéis que `OQ-03` descartou.** `OQ-03` fechou
"fila única, sem atribuição de casos dentro da fila" (revisor A vs. revisor
B com filas separadas) — este mecanismo não introduz fila por revisor
nenhuma; `e_revisor` é um único booleano que só distingue "pode entrar em
`/revisao/*`" de "não pode", sem nenhuma noção de qual revisor viu qual
caso.

REGRAS: `RF-02`, `AC-03`, `RF-23`, `RF-25`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Final

from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection

from app.http.sessao import obter_conta_id
from persistencia.app_aluno.casos import RepositorioCasos, RepositorioCasosSupabase
from persistencia.app_aluno.contas import RepositorioContas, RepositorioContasSupabase

REGRAS: Final[tuple[str, ...]] = ("RF-02", "AC-03", "RF-23", "RF-25")

# Mensagens curtas de propósito — já constam de `EXCECOES_PERMITIDAS` de
# `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`
# (T-08, AC-37): "Sessão inválida ou expirada." e "Caso não encontrado.".
_MENSAGEM_SESSAO_AUSENTE: Final[str] = "Sessão inválida ou expirada."
_MENSAGEM_CASO_NAO_ENCONTRADO: Final[str] = "Caso não encontrado."
_MENSAGEM_PAPEL_REVISOR_AUSENTE: Final[str] = "Acesso restrito a revisores."


def obter_repositorio_casos() -> RepositorioCasos:
    """Ponto único de injeção do repositório de casos — sobrescrito nos
    testes via `app.dependency_overrides` para rodar sem `DATABASE_URL`,
    mesmo padrão de `app/http/rotas_conta.py::obter_repositorio_contas`."""
    return RepositorioCasosSupabase()


def exigir_caso_da_sessao(nome_parametro: str) -> Callable[..., str]:
    """Fábrica: devolve uma dependência do FastAPI que valida a posse do
    `CASO_ID` recebido no parâmetro `nome_parametro` (path ou query) da
    própria rota, e devolve o `CASO_ID` validado — o handler recebe o valor
    já verificado, nunca precisando reconferir.

    A dependência devolvida assina `(conexao, repositorio, **kwargs)`, com
    `kwargs` contendo exatamente UM parâmetro — de nome `nome_parametro` —
    injetado via `__signature__` reescrita dinamicamente. O FastAPI só
    inspeciona `__signature__` para decidir de onde extrair cada valor (path
    ou query da rota que declarar esta dependência); ele sempre invoca a
    função por *keyword*, então o parâmetro chega em `kwargs` sob o nome
    declarado, não sob um nome fixo do código-fonte — é isso que permite uma
    única fábrica servir rotas com parâmetros de nomes diferentes (`CASO_ID`
    em posições/rotas distintas) sem reescrever a função a cada rota nova.
    """

    def dependencia(
        conexao: HTTPConnection,
        repositorio: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
        **kwargs: str,
    ) -> str:
        caso_id = kwargs[nome_parametro]

        # 1. Sessão ausente ⇒ recusada ANTES de qualquer leitura de dado do
        # caso — nenhuma consulta ao banco acontece neste ramo.
        conta_id = obter_conta_id(conexao)
        if conta_id is None:
            raise HTTPException(status_code=401, detail=_MENSAGEM_SESSAO_AUSENTE)

        # 2. Consulta ao banco a cada requisição — sem cache de autorização
        # em sessão. 3. Caso inexistente ou de outra conta: mesmo 404, nunca
        # 403 — a existência do caso de terceiro não vaza.
        if not repositorio.pertence_a_conta(caso_id, conta_id):
            raise HTTPException(status_code=404, detail=_MENSAGEM_CASO_NAO_ENCONTRADO)

        return caso_id

    _declarar_parametro_caso_id(dependencia, nome_parametro)
    return dependencia


def _declarar_parametro_caso_id(dependencia: Callable[..., str], nome_parametro: str) -> None:
    """Substitui, na assinatura pública de `dependencia`, o `**kwargs` por
    um parâmetro nomeado `nome_parametro` — é essa assinatura que o FastAPI
    inspeciona para decidir de onde extrair o valor (path ou query da rota
    que declarar esta dependência). A função continua aceitando `**kwargs`
    em tempo de execução (o corpo real não muda), só a introspecção muda."""
    import inspect

    assinatura_original = inspect.signature(dependencia)
    parametros = [
        parametro
        for parametro in assinatura_original.parameters.values()
        if parametro.kind is not inspect.Parameter.VAR_KEYWORD
    ]
    novo_parametro = inspect.Parameter(
        nome_parametro, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str
    )
    # Um parâmetro sem `default` não pode vir DEPOIS de um com `default`
    # (`repositorio: RepositorioCasos = Depends(...)`) — insere antes do
    # primeiro parâmetro que já tem valor padrão, para respeitar a ordem
    # exigida por `inspect.Signature`.
    indice_insercao = next(
        (indice for indice, p in enumerate(parametros) if p.default is not inspect.Parameter.empty),
        len(parametros),
    )
    parametros.insert(indice_insercao, novo_parametro)
    dependencia.__signature__ = assinatura_original.replace(parameters=parametros)  # type: ignore[attr-defined]


def obter_repositorio_contas_para_papel() -> RepositorioContas:
    """Ponto único de injeção do repositório de contas para `exigir_papel_
    revisor` — sobrescrito nos testes via `app.dependency_overrides`,
    mesmo padrão de `obter_repositorio_casos`. Declarado à parte (em vez de
    reaproveitar `app.http.rotas_conta.obter_repositorio_contas`) para que
    este módulo não precise importar de `app/http/rotas_conta.py` só por
    causa de um ponto de injeção — cada rota que precisa de `RepositorioContas`
    tem o seu, mesma disciplina de `obter_repositorio_casos_da_fila` em
    `app/http/rotas_revisao.py`."""
    return RepositorioContasSupabase()


def exigir_papel_revisor(
    conexao: HTTPConnection,
    repositorio: Annotated[RepositorioContas, Depends(obter_repositorio_contas_para_papel)],
) -> str:
    """Dependência do FastAPI que fecha a lacuna documentada em T-69:
    `/revisao/*` exige uma sessão com `e_revisor = true` — mesmo mecanismo
    genérico que `T-71` (rotas de decisão de liberar/reprovar) reutiliza.

    **Ordem das verificações (mesma disciplina de `exigir_caso_da_sessao`):**
    1. Sessão ausente ⇒ `401`, ANTES de qualquer leitura de dado — nenhuma
       consulta ao banco acontece neste ramo.
    2. Sessão presente ⇒ consulta `RepositorioContas.buscar_por_id`, SEMPRE
       contra o banco, a cada requisição — nunca um valor gravado em sessão
       (`app/http/sessao.py` não grava `e_revisor`).
    3. Conta autenticada sem `e_revisor = true` ⇒ `403`, NUNCA `404` — a
       existência da tela de revisão não é segredo, só o acesso é negado
       (diferente de `exigir_caso_da_sessao`, que funde as duas situações em
       um único `404` porque ali existe um recurso de TERCEIRO cuja
       existência precisa ficar oculta; aqui não há terceiro nenhum).

    Devolve o `conta_id` já verificado — o handler recebe o valor pronto,
    sem precisar reconferir o papel."""
    conta_id = obter_conta_id(conexao)
    if conta_id is None:
        raise HTTPException(status_code=401, detail=_MENSAGEM_SESSAO_AUSENTE)

    conta = repositorio.buscar_por_id(conta_id)
    if conta is None or not conta.e_revisor:
        raise HTTPException(status_code=403, detail=_MENSAGEM_PAPEL_REVISOR_AUSENTE)

    return conta_id
