"""Provisionamento de conta por compra aprovada — `RF-02`, `T-179`.

**O aluno compra na Hotmart, não se cadastra no PIQ.** Não existe (nem vai
existir) tela de cadastro público: a conta nasce de uma compra aprovada, por
webhook, e o comprador nunca informa senha nesse momento — a plataforma
entrega e-mail, nada mais.

**Por que uma rota nova, e não `POST /api/conta/cadastro`.** Aquela foi
desenhada para TELA: exige senha no corpo e instala cookie de sessão no
chamador. As duas coisas são erradas para uma máquina — o webhook não tem
senha para informar, e uma sessão instalada no servidor da Hotmart não
serve a ninguém. Separar "máquina provisiona" de "pessoa se cadastra"
mantém as duas rotas honestas sobre o que fazem.

**Autenticação por segredo compartilhado.** O header
`X-PIQ-Provisionamento` precisa bater com `SEGREDO_PROVISIONAMENTO`
(variável de ambiente, nunca literal — mesma disciplina de
`CHAVE_ASSINATURA_SESSAO`). A comparação é por `secrets.compare_digest`,
resistente a timing: comparar com `==` vazaria, caractere a caractere, o
segredo correto para quem medisse o tempo de resposta.

Sem a variável no ambiente, a rota responde `503` — **nunca "sem segredo
configurado = aceita qualquer um"**, que transformaria um esquecimento de
deploy em porta aberta para criar contas.

**E-mail já provisionado NÃO é erro** (decisão do especialista,
2026-09-21). Uma compra repetida do mesmo aluno é normal: ele perdeu o
link, comprou de novo, renovou. A rota emite um token novo para a conta
existente e responde exatamente como no caso novo — o chamador não
distingue "criei agora" de "já existia", pela mesma razão que o login não
distingue "conta inexistente" de "senha errada" (`RF-02`).

**O caso nasce em `CADASTRADO`, nunca em `COLETA_INICIAL`.** É o
consentimento que abre a coleta (`RF-30`, `T-173`): provisionar não é
consentir, e o aluno ainda precisa aceitar o termo. Pular esse estado é o
que `scripts/subir_demo.py` faz — e é justamente o que `PEND-01` proíbe
com pessoa real.

REGRAS: `RF-02`, `RF-30`
"""

from __future__ import annotations

import os
import secrets
from typing import Annotated, Final, Protocol

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.http.rotas_conta import _ler_formulario
from app.notificacao.email import (
    EnviadorDeEmail,
    ErroConfiguracaoEmail,
    ErroEnvioEmail,
    obter_enviador,
)
from app.notificacao.mensagens import (
    ErroUrlBaseAusente,
    primeiro_acesso,
    recuperacao_de_senha,
)
from persistencia.app_aluno.cadastro import provisionar_conta_e_caso
from persistencia.app_aluno.contas import (
    Conta,
    ErroEmailDuplicado,
    RepositorioContas,
    RepositorioContasSupabase,
)
from persistencia.app_aluno.tokens_acesso import (
    ErroTokenInvalido,
    RepositorioTokensAcesso,
    RepositorioTokensAcessoSupabase,
    TokenEmitido,
)

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-30")

roteador = APIRouter(prefix="/api/provisionamento", tags=["provisionamento"])

_VARIAVEL_SEGREDO: Final[str] = "SEGREDO_PROVISIONAMENTO"
_NOME_HEADER: Final[str] = "X-PIQ-Provisionamento"

# Mensagens curtas — limiar de `AC-37` (T-08).
_MENSAGEM_NAO_AUTORIZADO: Final[str] = "Não autorizado."
_MENSAGEM_SEM_SEGREDO: Final[str] = "Provisionamento indisponível."
_MENSAGEM_EMAIL_AUSENTE: Final[str] = "E-mail obrigatório."


class ProvisionaContaECaso(Protocol):
    """Ponto de injeção da criação atômica conta+caso — sobrescrito nos
    testes, mesmo padrão de `obter_cadastro_conta`."""

    def __call__(self, email: str) -> tuple[Conta, object]: ...


def obter_provisionamento() -> ProvisionaContaECaso:
    return provisionar_conta_e_caso


def obter_repositorio_contas_provisionamento() -> RepositorioContas:
    return RepositorioContasSupabase()


def obter_repositorio_tokens() -> RepositorioTokensAcesso:
    return RepositorioTokensAcessoSupabase()


def _segredo_confere(recebido: str | None) -> bool | None:
    """`True`/`False` se o segredo está configurado; `None` se a variável
    de ambiente não existe (o chamador responde `503`).

    `compare_digest` em vez de `==`: ver a nota do módulo sobre timing."""
    esperado = os.environ.get(_VARIAVEL_SEGREDO)
    if not esperado:
        return None
    if not recebido:
        return False
    return secrets.compare_digest(recebido, esperado)


@roteador.post("/conta")
async def provisionar(
    request: Request,
    provisionamento: Annotated[ProvisionaContaECaso, Depends(obter_provisionamento)],
    repositorio_contas: Annotated[
        RepositorioContas, Depends(obter_repositorio_contas_provisionamento)
    ],
    repositorio_tokens: Annotated[
        RepositorioTokensAcesso, Depends(obter_repositorio_tokens)
    ],
    enviador: Annotated[EnviadorDeEmail, Depends(obter_enviador)],
    segredo: Annotated[str | None, Header(alias=_NOME_HEADER)] = None,
) -> JSONResponse:
    """Cria conta + caso a partir de uma compra aprovada e devolve o token
    de primeiro acesso.

    **Não instala sessão.** Quem chama é uma máquina; o aluno autentica
    depois, pelo link, com a senha que ele mesmo definir.

    O token volta no corpo em CLARO — é a única vez em que ele existe assim
    (o banco guarda só o hash). Quem chama é responsável por entregá-lo ao
    aluno, por e-mail ou pelo canal da plataforma."""
    confere = _segredo_confere(segredo)
    if confere is None:
        # Variável ausente no ambiente. `503`, nunca "aceita qualquer um".
        return JSONResponse({"erro": _MENSAGEM_SEM_SEGREDO}, status_code=503)
    if not confere:
        return JSONResponse({"erro": _MENSAGEM_NAO_AUTORIZADO}, status_code=401)

    dados = await _ler_formulario(request)
    email = dados.get("email", "").strip().lower()
    if not email:
        return JSONResponse({"erro": _MENSAGEM_EMAIL_AUSENTE}, status_code=400)

    try:
        conta, _caso = provisionamento(email)
        conta_id = conta.conta_id
    except ErroEmailDuplicado:
        # **Compra repetida não é erro** — ver a nota do módulo. O aluno já
        # tem conta; emitimos um token novo (que revoga o anterior) e
        # respondemos como no caso novo.
        existente = repositorio_contas.buscar_por_email(email)
        if existente is None:  # pragma: no cover — defensivo: o UNIQUE acusou
            return JSONResponse({"erro": _MENSAGEM_NAO_AUTORIZADO}, status_code=401)
        conta_id = existente.conta_id

    token: TokenEmitido = repositorio_tokens.emitir(conta_id)

    # **A falha de e-mail NÃO derruba o provisionamento** — `T-182`.
    #
    # A conta e o caso já estão gravados; o token, emitido. Devolver `500`
    # aqui faria a Hotmart reprocessar o webhook — e o reprocessamento
    # emitiria OUTRO token, revogando este, num laço que nunca entrega
    # nada. Pior: o aluno pagou e o sistema responderia "falhou".
    #
    # O token volta no corpo de qualquer forma, então quem chama sempre tem
    # como entregar o link por outro canal (página de obrigado, WhatsApp).
    # `email_enviado` diz o que aconteceu, sem esconder nem travar.
    email_enviado = True
    try:
        mensagem = primeiro_acesso(token.valor)
        enviador.enviar(email, mensagem.assunto, mensagem.corpo)
    except (ErroConfiguracaoEmail, ErroEnvioEmail, ErroUrlBaseAusente):
        # O erro já não carrega o destinatário (ver `email.py`); aqui nem a
        # exceção sobe. Quem precisa saber é o chamador, pelo campo abaixo.
        email_enviado = False

    return JSONResponse(
        {
            "token": token.valor,
            "expira_em": token.expira_em.isoformat(),
            "email_enviado": email_enviado,
        },
        status_code=201,
    )


#: Tamanho mínimo de senha — `T-181`.
#:
#: Oito caracteres é o piso da OWASP (Authentication Cheat Sheet) e o que o
#: NIST SP 800-63B fixa como mínimo. Até aqui **não havia política nenhuma**:
#: `cadastro.py` hasheava o que recebesse, e uma senha de um caractere era
#: aceita. Argon2id forte sobre senha `"a"` não protege ninguém.
#:
#: Sem exigência de maiúscula/dígito/símbolo, também por recomendação do
#: NIST: regras de composição empurram para `Senha1!` — previsível — e o
#: comprimento é o que de fato importa.
TAMANHO_MINIMO_SENHA: Final[int] = 8

_MENSAGEM_SENHA_CURTA: Final[str] = (
    f"A senha precisa ter ao menos {TAMANHO_MINIMO_SENHA} caracteres."
)
_MENSAGEM_TOKEN_INVALIDO: Final[str] = "Link inválido ou expirado."


@roteador.post("/senha")
async def definir_senha(
    request: Request,
    repositorio_contas: Annotated[
        RepositorioContas, Depends(obter_repositorio_contas_provisionamento)
    ],
    repositorio_tokens: Annotated[
        RepositorioTokensAcesso, Depends(obter_repositorio_tokens)
    ],
) -> JSONResponse:
    """O aluno define a própria senha, provando posse do e-mail pelo token.

    Serve ao PRIMEIRO ACESSO e à RECUPERAÇÃO — os dois terminam aqui, e é
    por isso que não há duas rotas: o fato é o mesmo ("provei que sou dono
    deste e-mail, quero definir a senha").

    **A ordem importa.** A senha é validada ANTES de o token ser consumido:
    senha curta não pode queimar o link do aluno, obrigando-o a pedir outro
    por um erro de digitação.

    **Não instala sessão.** Depois de definir a senha, o aluno entra pelo
    login normal — assim o fluxo de autenticação é um só, e a senha que ele
    acabou de escolher é exercitada na hora."""
    dados = await _ler_formulario(request)
    token = dados.get("token", "").strip()
    senha = dados.get("senha", "")

    if len(senha) < TAMANHO_MINIMO_SENHA:
        return JSONResponse({"erro": _MENSAGEM_SENHA_CURTA}, status_code=400)

    try:
        conta_id = repositorio_tokens.consumir(token)
    except ErroTokenInvalido:
        # Não existe, já usado ou expirado — indistinguíveis de propósito.
        return JSONResponse({"erro": _MENSAGEM_TOKEN_INVALIDO}, status_code=400)

    repositorio_contas.definir_senha(conta_id, senha)

    return JSONResponse({"senha_definida": True})


@roteador.post("/recuperacao")
async def pedir_recuperacao(
    request: Request,
    repositorio_contas: Annotated[
        RepositorioContas, Depends(obter_repositorio_contas_provisionamento)
    ],
    repositorio_tokens: Annotated[
        RepositorioTokensAcesso, Depends(obter_repositorio_tokens)
    ],
    enviador: Annotated[EnviadorDeEmail, Depends(obter_enviador)],
) -> JSONResponse:
    """"Esqueci minha senha" — `T-182`.

    **Responde SEMPRE `200`, exista a conta ou não.** Distinguir os dois
    casos transformaria esta rota num verificador de e-mails: qualquer um
    descobriria quem usa o PIQ testando endereços. É a mesma disciplina do
    login, que não distingue "conta inexistente" de "senha errada"
    (`RF-02`) — e aqui importa mais, porque a rota é pública e sem segredo.

    Quem tem conta recebe o link; quem não tem, não recebe nada. Os dois
    veem a mesma resposta.

    **Sem rate limiting ainda** (`BLOQUEIA-8` da auditoria): esta rota
    dispara envio de e-mail a cada chamada, então é um amplificador. Entra
    junto com o limitador do login, na tarefa dedicada."""
    dados = await _ler_formulario(request)
    email = dados.get("email", "").strip().lower()

    conta = repositorio_contas.buscar_por_email(email) if email else None
    if conta is not None:
        token = repositorio_tokens.emitir(conta.conta_id)
        try:
            mensagem = recuperacao_de_senha(token.valor)
            enviador.enviar(conta.email, mensagem.assunto, mensagem.corpo)
        except (ErroConfiguracaoEmail, ErroEnvioEmail, ErroUrlBaseAusente):
            # Falha de envio não muda a resposta — ver a nota acima. O
            # aluno tentaria de novo, e um erro aqui diria a um atacante
            # que o e-mail existe.
            pass

    return JSONResponse({"pedido_registrado": True})
