"""Monta a aplicação FastAPI com sessão assinada — `RF-02`, `AC-03`.

`plans/app-aluno.plan.md` §2 decide `SessionMiddleware` (Starlette, sobre
`itsdangerous`) com cookie `HttpOnly` + `Secure` + `SameSite=Lax`, e §7
(State Management) fecha o contrato: a sessão expira, é invalidada por
logout, e **nunca** contém dado financeiro nem autoriza acesso por si só —
o isolamento por `CASO_ID` é sempre reverificado no servidor (`app/http/
isolamento.py`, T-31), nunca confiado ao cookie.

**Chave de assinatura.** Vem exclusivamente da variável de ambiente
`CHAVE_ASSINATURA_SESSAO` — nunca um literal no código. Sem ela, a aplicação
recusa subir: um fallback "seguro por padrão" (gerar uma chave aleatória em
memória, por exemplo) seria pior que falhar alto, porque invalidaria toda
sessão a cada reinício do processo sem avisar ninguém, e um literal fixo
"para dev" vazaria para produção por esquecimento — é exatamente o tipo de
inseguridade silenciosa que `sdd.config.md` proíbe.

**Rota de saúde sem banco.** `/saude` não importa nada de `persistencia/`
nem de `engine/`: responde a partir do processo já vivo, para servir de
sonda de vida (liveness) independente da disponibilidade do Supabase — a
verificação de prontidão contra o banco (readiness), se vier a existir, é
outra rota, fora do escopo desta tarefa.

**Edição de T-30.** `criar_aplicacao()` passa a registrar
`app.http.rotas_conta.roteador` (cadastro, login, logout — `RF-02`,
`AC-03`), a primeira rota desta feature que de fato toca `persistencia/`.
O teste estático de T-29 (`test_rota_de_saude_nao_importa_persistencia`)
continua válido: ele varre só os imports de módulo — `rotas_conta` importa
de `persistencia.app_aluno.contas`, mas quem importa `rotas_conta` é este
módulo (`aplicacao.py`), então o import de `persistencia/` passa a existir
aqui de forma transitiva. `/saude` em si nunca chama nada do router novo.

**Edição de T-36.** `criar_aplicacao()` também registra
`app.http.rotas_consentimento.roteador` (`POST /caso/{CASO_ID}/consentimento`
— `RF-30`, `AC-39`), a rota que registra o aceite e dispara a transição
`registra_consentimento`.

**Edição de T-42.** `criar_aplicacao()` também registra
`app.http.rotas_coleta.roteador` (`POST /caso/{CASO_ID}/resposta` — `RF-05`,
`RF-07`, `RF-10`, `RF-11`, `RF-13`), os sete passos do plano §5.1 para uma
única resposta de coleta.

**Edição de T-56.** `criar_aplicacao()` também registra
`app.http.rotas_calculo.roteador` (`POST /caso/{CASO_ID}/calculo` e
`GET /caso/{CASO_ID}/calculo/progresso` — `RF-16`, `AC-12`), a rota que
dispara o Bloco 6 e a tela de progresso enquanto o caso está em
`CALCULANDO`.

**Edição de T-63/T-64.** `criar_aplicacao()` também registra
`app.http.rotas_plano.roteador` (`GET /caso/{CASO_ID}/plano/pdf` — `RF-20`,
`RF-21`, `AC-14`, `AC-16`, T-63 — e `GET /caso/{CASO_ID}/plano` — `RF-20`,
`RF-21`, `RF-23`, `AC-25`, T-64), a exportação em PDF e a tela HTML do
plano, ambas a partir do mesmo template/mesma guarda de liberação.

**Edição de T-145.** A montagem `/estaticos` foi REMOVIDA. Ela servia
`htmx.min.js`, `mascaras.js` e `estilo.css` para as telas Jinja2; com a
interface em React, o bundle é servido pelo Vite (desenvolvimento) ou por
quem hospedar os estáticos do build (produção), e o backend passou a ser
só API JSON + o PDF. Manter uma montagem sobre um diretório vazio seria
superfície HTTP sem função. O texto abaixo é registro histórico:

> `StaticFiles` é um
`Mount`, não uma `APIRoute`: a auditoria de isolamento por `CASO_ID`
(`tests/app_aluno/e2e/test_mecanismo_isolamento.py::
rotas_sem_isolamento_por_caso`, T-31/T-32) só enumera `APIRoute`, então este
mount nunca precisa — nem pode — declarar `exigir_caso_da_sessao`: é um
arquivo público, sem dado de caso algum.

**Edição de T-69.** `criar_aplicacao()` também registra
`app.http.rotas_revisao.roteador` (`GET /revisao/fila` — `RF-23`, `RF-25`,
`AC-25`, `AC-28`), a tela da fila de revisão. **Esta rota NÃO recebe
`CASO_ID`** (lista todos os casos em `AGUARDANDO_REVISAO`, nunca um caso
por sessão de aluno) e por isso fica fora do escopo da auditoria de
isolamento por `CASO_ID` — ver a nota extensa em `app/http/rotas_revisao.py`
sobre o modelo de autorização desta tela (hoje: qualquer requisição que
alcance a URL, sem sessão de revisor distinta da de aluno, porque o sistema
não modela papéis — `OQ-03`; limitação de piloto documentada, não
acidental).

**Edição de T-94.** `criar_aplicacao()` também registra
`app.http.saude.roteador` (`GET /saude/banco` — `RF-10`, `EC-05`), a rota de
keep-alive do banco durante a janela do piloto (`docs/operacao-piloto.md`).
**Diferente de `/saude` acima, esta rota TOCA o banco** (`SELECT 1` puro,
sem tabela de dado do aluno) — é o alvo de um agendador externo (cron/GitHub
Actions), nunca chamada pelo fluxo do aluno. Também não recebe `CASO_ID` e
fica fora da auditoria de isolamento, pelo mesmo motivo da fila de revisão.

**Edição de T-102.** `criar_aplicacao()` também registra
`app.http.rotas_operador.roteador` (`GET /operador/painel` — `RF-35`), o
painel dedicado do operador que lista todos os casos do piloto com estado,
o que aguarda revisão e tempo desde a última atividade. Protegida pela
MESMA `exigir_papel_revisor` de `T-100` — mesma nota de `/revisao/*` acima:
não recebe `CASO_ID` e fica fora da auditoria de isolamento por caso do
aluno, porque o operador vê todos os casos por definição de papel.

**Edição de T-121.** `criar_aplicacao()` também registra
`app.http.rotas_bloco10.roteador` (`POST /caso/{CASO_ID}/bloco-10/resposta`
— `RF-18`), a confirmação do Ataque Imediato criada por `T-77`. Recebe
`CASO_ID` na URL e usa `exigir_caso_da_sessao`, mesmo mecanismo de
`rotas_coleta.py` — entra na auditoria de isolamento por caso sem exceção.

REGRAS: `RF-02`, `RF-30`
"""

from __future__ import annotations

import os
from typing import Final

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.http.rotas_acoes import roteador as roteador_acoes
from app.http.rotas_api_conta import roteador as roteador_api_conta
from app.http.rotas_api_plano import roteador as roteador_api_plano
from app.http.rotas_bloco10 import roteador as roteador_bloco10
from app.http.rotas_bloco11 import roteador as roteador_bloco11
from app.http.rotas_calculo import roteador as roteador_calculo
from app.http.rotas_coleta import roteador as roteador_coleta
from app.http.rotas_coleta_dirigida import roteador as roteador_coleta_dirigida
from app.http.rotas_consentimento import roteador as roteador_consentimento
from app.http.rotas_conta import roteador as roteador_conta
from app.http.rotas_etapas import roteador as roteador_etapas
from app.http.rotas_fichas import roteador as roteador_fichas
from app.http.rotas_inicio import roteador as roteador_inicio
from app.http.rotas_operador import roteador as roteador_operador
from app.http.rotas_pergunta import roteador as roteador_pergunta
from app.http.rotas_plano import roteador as roteador_plano
from app.http.rotas_provisionamento import roteador as roteador_provisionamento
from app.http.rotas_respostas import roteador as roteador_respostas
from app.http.rotas_revisao import roteador as roteador_revisao
from app.http.saude import roteador as roteador_saude_banco

# Nome da variável de ambiente que supre a chave de assinatura da sessão.
# Nunca um literal de chave no código (critério de aceite desta tarefa).
_VARIAVEL_CHAVE_ASSINATURA_SESSAO: Final[str] = "CHAVE_ASSINATURA_SESSAO"

# Nome do cookie de sessão — declarado numa única constante, para que rotas
# e testes não repitam o literal.
NOME_COOKIE_SESSAO: Final[str] = "piq_sessao"


class ErroConfiguracaoSessao(RuntimeError):
    """A variável de ambiente da chave de assinatura da sessão está ausente
    ou vazia. Nunca há fallback inseguro silencioso para este erro."""


def _obter_chave_assinatura_sessao() -> str:
    chave = os.environ.get(_VARIAVEL_CHAVE_ASSINATURA_SESSAO)
    if not chave:
        # Mensagem curta de propósito (tests/app_aluno/estatica/
        # test_sem_conteudo_de_questionario_no_codigo.py, AC-37, limita o
        # tamanho de literal de string tolerado fora de docstring): o nome
        # da variável de ambiente já diz o que falta.
        raise ErroConfiguracaoSessao(
            f"{_VARIAVEL_CHAVE_ASSINATURA_SESSAO} ausente ou vazia."
        )
    return chave


def criar_aplicacao() -> FastAPI:
    """Monta a `FastAPI` com `SessionMiddleware` e a rota de saúde. Chamada
    pelo processo ASGI (`uvicorn`) e pelos testes — nunca instanciada duas
    vezes com middlewares divergentes."""
    aplicacao = FastAPI(title="PIQ — App do Aluno")

    aplicacao.add_middleware(
        SessionMiddleware,
        secret_key=_obter_chave_assinatura_sessao(),
        session_cookie=NOME_COOKIE_SESSAO,
        https_only=True,  # Secure
        same_site="lax",  # SameSite=Lax
        # HttpOnly é o padrão do SessionMiddleware do Starlette — o cookie de
        # sessão nunca fica acessível a JavaScript no navegador.
    )

    @aplicacao.get("/saude")
    def saude() -> dict[str, str]:
        """Rota de saúde: responde sem tocar `persistencia/` nem `engine/` —
        prova que o processo está de pé, independente do banco."""
        return {"status": "ok"}

    aplicacao.include_router(roteador_conta)
    aplicacao.include_router(roteador_consentimento)
    aplicacao.include_router(roteador_coleta)
    aplicacao.include_router(roteador_pergunta)
    # T-134/T-135: fichas repetíveis (108 perguntas dependiam disto) e os
    # dois roteadores que existiam desde T-75/T-82 sem nunca serem
    # registrados — código testado e inalcançável por `uvicorn` até aqui.
    aplicacao.include_router(roteador_fichas)
    aplicacao.include_router(roteador_coleta_dirigida)
    aplicacao.include_router(roteador_bloco11)
    # T-139: as três saídas de PLANO_LIBERADO. Sem elas, o caso chegava ao
    # plano liberado e morria ali — Blocos 7, 8, 10 e 11 eram inalcançáveis.
    aplicacao.include_router(roteador_etapas)
    # T-147: a tela Início — a fase do caso e a ÚNICA próxima etapa. É o
    # ponto de entrada do aluno (`RF-58`); sem ela, a interface voltaria a
    # oferecer todas as telas de uma vez e a deixar a escolha com quem não
    # tem como fazê-la.
    aplicacao.include_router(roteador_inicio)
    # T-160: rever o que já foi respondido. `RF-10` dava retomada; faltava
    # conferência — o aluno não tinha como reler o que disse sobre o próprio
    # dinheiro, nem achar o que esqueceu.
    aplicacao.include_router(roteador_respostas)
    # T-140: API JSON do plano, da fila e do painel — as telas viram React.
    aplicacao.include_router(roteador_api_plano)
    aplicacao.include_router(roteador_api_conta)
    # `T-179`: a porta de entrada do webhook de compra. Protegida por
    # segredo próprio, nunca por sessão — quem chama é máquina.
    aplicacao.include_router(roteador_provisionamento)
    # T-143: Bloco 11 — ações e seu andamento, por ACAO_ID.
    aplicacao.include_router(roteador_acoes)
    aplicacao.include_router(roteador_calculo)
    aplicacao.include_router(roteador_bloco10)
    aplicacao.include_router(roteador_plano)
    aplicacao.include_router(roteador_revisao)
    aplicacao.include_router(roteador_operador)
    aplicacao.include_router(roteador_saude_banco)

    return aplicacao
