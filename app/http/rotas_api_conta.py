"""API JSON de conta, consentimento e progresso do cálculo — `RF-50`,
`RF-51` (T-141).

As últimas telas que ainda eram Jinja2 do lado do aluno viram React. Estas
rotas entregam os MESMOS dados que `conta/*.html`, `consentimento/*.html` e
`calculo/*.html` recebiam.

**O que estas rotas NÃO mudam.** A sessão continua sendo instalada pelo
servidor (`iniciar_sessao_conta`), o cookie continua `Secure`+`HttpOnly`, e
`RF-02` continua valendo: "conta inexistente" e "senha errada" devolvem a
MESMA mensagem e o MESMO status. Diferenciá-las diria a um atacante quais
e-mails existem.

**Consentimento sem texto continua bloqueando** (`PEND-01`): sem YAML em
`app/consentimento/textos/`, a resposta é `503` com o motivo nomeado, nunca
"sem consentimento = pode seguir".

REGRAS: `RF-02`, `RF-30`, `RF-50`, `RF-51`, `AC-39`
"""

from __future__ import annotations

from typing import Annotated, Final, Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection

from app.consentimento.registro import (
    ErroTextoConsentimentoAusente,
    ErroTextoConsentimentoInvalido,
    carregar_texto_vigente,
)
from app.http.isolamento import exigir_caso_da_sessao
from app.http.rotas_conta import (
    CadastroConta,
    _ler_formulario,
    obter_cadastro_conta,
    obter_repositorio_contas,
)
from app.http.sessao import encerrar_sessao, iniciar_sessao_conta, obter_conta_id
from persistencia.app_aluno.casos import RepositorioCasosSupabase
from persistencia.app_aluno.contas import ErroEmailDuplicado, RepositorioContas

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-30", "RF-50", "RF-51", "AC-39")

roteador = APIRouter(prefix="/api", tags=["api-conta"])

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_LOGIN_INVALIDO: Final[str] = "E-mail ou senha inválidos."
_MENSAGEM_TEXTO_AUSENTE: Final[str] = "Texto de consentimento indisponível."
_MENSAGEM_CADASTRO_DUPLICADO: Final[str] = "Não foi possível concluir o cadastro."
_MENSAGEM_SESSAO_AUSENTE: Final[str] = "Sessão inválida ou expirada."


class CasosDaConta(Protocol):
    """O que `GET /api/conta/eu` precisa de um repositório de casos — e nada
    além (`T-154`).

    **Protocol próprio, e não um método novo em `RepositorioCasos`.**
    Acrescentar `listar_da_conta` ao contrato largo obrigaria as 20+
    implementações e dublês existentes a crescerem junto — inclusive
    `RepositorioCasosArquivo` e testes que nada têm a ver com descoberta de
    sessão. Um contrato que só uma rota consome pertence perto dela, estreito:
    quem implementa declara o que usa, e o resto do sistema não muda por causa
    de uma rota nova."""

    def listar_da_conta(self, conta_id: str) -> tuple[str, ...]: ...


def obter_casos_da_conta() -> CasosDaConta:
    """Ponto único de injeção de `CasosDaConta` — sobrescrito nos testes via
    `app.dependency_overrides`, mesmo padrão dos demais `obter_*`."""
    return RepositorioCasosSupabase()


@roteador.post("/conta/cadastro")
async def cadastrar(
    request: Request,
    cadastro: Annotated[CadastroConta, Depends(obter_cadastro_conta)],
) -> JSONResponse:
    """`RF-02` — cria conta e caso ATOMICAMENTE e já abre a sessão.

    **Não é só tela.** `cadastrar_conta_e_caso` grava as duas coisas numa
    transação: sem esta rota não existe criação de conta no sistema.

    E-mail duplicado devolve uma mensagem que **não confirma** que aquele
    e-mail já existe — dizer "já cadastrado" entregaria a um atacante a
    lista de quem usa o sistema."""
    dados = await _ler_formulario(request)
    try:
        conta, caso = cadastro(dados.get("email", "").strip(), dados.get("senha", ""))
    except ErroEmailDuplicado:
        return JSONResponse({"erro": _MENSAGEM_CADASTRO_DUPLICADO}, status_code=400)

    iniciar_sessao_conta(request, conta_id=conta.conta_id)
    return JSONResponse(
        {
            "email": conta.email,
            "conta_id": conta.conta_id,
            "CASO_ID": caso.CASO_ID,
            # Conta nova nunca nasce revisora (`Conta.e_revisor = False` por
            # default) — ver a nota de `entrar`, abaixo, sobre o que este
            # campo é e o que ele não é.
            "e_revisor": conta.e_revisor,
        },
        status_code=201,
    )


@roteador.post("/conta/login")
async def entrar(
    request: Request,
    repositorio: Annotated[RepositorioContas, Depends(obter_repositorio_contas)],
) -> JSONResponse:
    """`RF-02` — autentica e instala a sessão.

    Conta inexistente e senha errada devolvem **a mesma** mensagem e o mesmo
    `401`: `repositorio.autenticar` já devolve `None` para os dois casos, e
    esta rota não pode (nem deve) diferenciá-los.

    **`e_revisor` no payload é dica de interface, não autorização** (`RF-59`,
    `AC-80`, T-148). Ele existe para que a interface não ofereça ao aluno o
    caminho para a fila, a conferência e o painel — quem vê "Fila", clica e
    recebe `403` conclui que o sistema está quebrado, ou que há algo seu que
    não está conseguindo ver.

    O que ele **não** é: controle de acesso. Quem autoriza é
    `exigir_papel_revisor`, que consulta `RepositorioContas.buscar_por_id`
    **contra o banco, a cada requisição** (`app/http/isolamento.py`).
    `app/http/sessao.py` grava só `conta_id`, por design — e continua assim
    depois desta tarefa. Um cliente que forje `e_revisor: true` não ganha
    acesso a nada: ganha telas que o servidor recusa. Esconder um botão nunca
    foi segurança, e este código não finge que seja."""
    dados = await _ler_formulario(request)
    conta = repositorio.autenticar(dados.get("email", "").strip(), dados.get("senha", ""))
    if conta is None:
        return JSONResponse({"erro": _MENSAGEM_LOGIN_INVALIDO}, status_code=401)

    iniciar_sessao_conta(request, conta_id=conta.conta_id)
    return JSONResponse(
        {
            "email": conta.email,
            "conta_id": conta.conta_id,
            "e_revisor": conta.e_revisor,
        }
    )


@roteador.get("/conta/eu")
def quem_esta_na_sessao(
    conexao: HTTPConnection,
    repositorio_casos: Annotated[CasosDaConta, Depends(obter_casos_da_conta)],
    repositorio_contas: Annotated[RepositorioContas, Depends(obter_repositorio_contas)],
) -> JSONResponse:
    """`RF-02`, `RF-59` (T-154) — quem é a sessão, e qual é o caso dela.

    **O buraco que esta rota fecha.** Até aqui o `CASO_ID` só aparecia na
    resposta do *cadastro*: quem fizesse login numa sessão nova, ou apenas
    recarregasse a página, não tinha como descobrir o próprio caso. O cliente
    dependia de `?caso=` na URL, e sem ele o aluno ficava preso na tela de
    login com a sessão já instalada — credencial aceita, aplicação
    inalcançável. O mesmo valia para o revisor e o papel dele (`RF-59`).

    **A pergunta é "quem sou eu", não "posso ver o caso X".** A sessão é a
    única entrada: nenhum identificador vem do cliente, então não há o que
    forjar. `pertence_a_conta` continua sendo a verificação de acesso, feita
    a cada requisição pelas rotas que recebem `CASO_ID` — esta aqui só
    enumera o que já é da conta autenticada.

    `e_revisor` sai do banco, nunca da sessão (`app/http/sessao.py` grava só
    `conta_id`, por design): recarregar a página passa a devolver o papel
    correto, e revogar alguém tem efeito na requisição seguinte, não quando o
    cookie expirar.

    Sem sessão, `401` — o mesmo que qualquer rota de caso devolve."""
    conta_id = obter_conta_id(conexao)
    if conta_id is None:
        return JSONResponse({"erro": _MENSAGEM_SESSAO_AUSENTE}, status_code=401)

    conta = repositorio_contas.buscar_por_id(conta_id)
    if conta is None:  # pragma: no cover — sessão válida de conta removida
        return JSONResponse({"erro": _MENSAGEM_SESSAO_AUSENTE}, status_code=401)

    casos = repositorio_casos.listar_da_conta(conta_id)
    return JSONResponse(
        {
            "email": conta.email,
            "conta_id": conta.conta_id,
            "e_revisor": conta.e_revisor,
            # O piloto tem um caso por conta (`cadastrar_conta_e_caso` cria
            # os dois juntos). A lista vai inteira mesmo assim, porque
            # devolver só o primeiro esconderia o dia em que houver dois —
            # e `CASO_ID` é a conveniência para o caso de hoje.
            "CASO_ID": casos[0] if casos else None,
            "casos": list(casos),
        }
    )


@roteador.post("/conta/logout")
def sair(conexao: HTTPConnection) -> JSONResponse:
    """Encerra a sessão. Sem corpo, sem redirect — o cliente decide para
    onde ir depois."""
    encerrar_sessao(conexao)
    return JSONResponse({"encerrada": True})


@roteador.get("/caso/{CASO_ID}/consentimento")
def texto_do_consentimento(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
) -> JSONResponse:
    """`RF-30` — o texto vigente, para a tela de aceite.

    `PEND-01` em aberto (nenhum YAML publicado) ⇒ `503` nomeando a lacuna.
    Nunca uma tela de consentimento vazia, e nunca seguir sem aceite."""
    try:
        texto = carregar_texto_vigente()
    except (ErroTextoConsentimentoAusente, ErroTextoConsentimentoInvalido):
        return JSONResponse({"erro": _MENSAGEM_TEXTO_AUSENTE}, status_code=503)

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "QUESTIONARIO_VERSION": texto.QUESTIONARIO_VERSION,
            "titulo": texto.titulo,
            "corpo": texto.corpo,
        }
    )
