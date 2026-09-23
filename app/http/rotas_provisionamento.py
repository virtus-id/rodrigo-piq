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
from fastapi.concurrency import run_in_threadpool
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
def provisionar(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
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
    aluno, por e-mail ou pelo canal da plataforma.

    **`def`, não `async def` — `T-187`.** `provisionamento(...)` grava no
    banco e `enviador.enviar` fala por SMTP — as duas bloqueantes. Ver a
    nota em `rotas_api_conta.py::cadastrar`."""
    confere = _segredo_confere(segredo)
    if confere is None:
        # Variável ausente no ambiente. `503`, nunca "aceita qualquer um".
        return JSONResponse({"erro": _MENSAGEM_SEM_SEGREDO}, status_code=503)
    if not confere:
        return JSONResponse({"erro": _MENSAGEM_NAO_AUTORIZADO}, status_code=401)

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


# -----------------------------------------------------------------------------
# Webhook da Hotmart — adaptador para `/conta`, adicionado operacionalmente
# em 2026-09-22, fora do fluxo Discovery → Spec do `CLAUDE.md`. Registrar
# como tarefa formal (RF próprio) fica para o dev reconciliar.
# -----------------------------------------------------------------------------

_VARIAVEL_HOTMART_HOTTOK: Final[str] = "HOTMART_HOTTOK"
_VARIAVEL_HOTMART_PRODUTO_ID: Final[str] = "HOTMART_PRODUTO_ID"
_NOME_HEADER_HOTTOK: Final[str] = "X-HOTMART-HOTTOK"
_EVENTO_APROVADA: Final[str] = "PURCHASE_APPROVED"
#: Confirmado contra o webhook de teste real da Hotmart em 2026-09-22.
#: Chargeback (`PURCHASE_CHARGEBACK`) e cancelamento não estão cobertos —
#: só o que foi pedido.
_EVENTO_REEMBOLSADA: Final[str] = "PURCHASE_REFUNDED"

_MENSAGEM_JSON_INVALIDO: Final[str] = "Corpo não é JSON válido."


def _hottok_confere(recebido: str | None) -> bool | None:
    """Mesmo contrato de `_segredo_confere`: `None` = variável ausente
    (`503`), `True`/`False` = bate ou não com o token configurado no painel
    da Hotmart (Ferramentas → Webhook → Token).

    **Aceita o token tanto no header `X-HOTMART-HOTTOK` quanto no campo
    `hottok` do corpo.** A Hotmart documenta as duas formas conforme a
    versão do webhook; validar as duas é mais barato do que apostar em
    qual esta conta usa, e não abre exceção nenhuma — as duas exigem o
    mesmo valor exato."""
    esperado = os.environ.get(_VARIAVEL_HOTMART_HOTTOK)
    if not esperado:
        return None
    if not recebido:
        return False
    return secrets.compare_digest(recebido, esperado)


@roteador.post("/hotmart")
async def receber_webhook_hotmart(
    request: Request,
    provisionamento: Annotated[ProvisionaContaECaso, Depends(obter_provisionamento)],
    repositorio_contas: Annotated[
        RepositorioContas, Depends(obter_repositorio_contas_provisionamento)
    ],
    repositorio_tokens: Annotated[
        RepositorioTokensAcesso, Depends(obter_repositorio_tokens)
    ],
    enviador: Annotated[EnviadorDeEmail, Depends(obter_enviador)],
    hottok_header: Annotated[str | None, Header(alias=_NOME_HEADER_HOTTOK)] = None,
) -> JSONResponse:
    """Traduz dois webhooks da Hotmart. `PURCHASE_APPROVED` segue o mesmo
    caminho de `provisionar` acima — mesma criação de conta+caso, mesmo
    e-mail de primeiro acesso, sem reimplementar nada daquela rota, só
    trocando de onde vem o `email`. `PURCHASE_REFUNDED` bloqueia a conta
    (`RepositorioContas.bloquear`, migração `005`) — `autenticar` passa a
    recusá-la; a conta e o histórico continuam no banco, só o acesso é
    cortado.

    **Responde `200` para tudo que não seja "processar e falhou".** Evento
    que não é um dos dois acima (cancelamento, chargeback, outro produto)
    não é erro — é a Hotmart me contando algo que esta rota não trata. Um
    `4xx`/`5xx` nesses casos faria a Hotmart reenviar o mesmo evento sem
    parar; só a autenticação e o corpo malformado merecem recusa de
    verdade.

    **Filtro por produto, se `HOTMART_PRODUTO_ID` estiver configurado.**
    Sem ele, qualquer produto aprovado nesta conta Hotmart provisiona no
    PIQ — inofensivo enquanto só existir um webhook apontando para cá, mas
    a variável existe para quando não for mais o caso.

    **Continua `async def` — `T-187`.** `await request.json()` é I/O real;
    tudo que vem depois (checagem do `hottok` no corpo, gravação no banco,
    envio de e-mail) é bloqueante e vive em `_processar_webhook_hotmart`,
    chamada por `run_in_threadpool` — mesmo padrão de
    `rotas_calculo.py::disparar_calculo`."""
    confere = _hottok_confere(hottok_header)
    if confere is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_SEGREDO}, status_code=503)

    try:
        corpo: dict[str, object] = await request.json()
    except ValueError:
        return JSONResponse({"erro": _MENSAGEM_JSON_INVALIDO}, status_code=400)

    return await run_in_threadpool(
        _processar_webhook_hotmart,
        corpo,
        confere,
        provisionamento,
        repositorio_contas,
        repositorio_tokens,
        enviador,
    )


def _processar_webhook_hotmart(
    corpo: dict[str, object],
    confere: bool | None,
    provisionamento: ProvisionaContaECaso,
    repositorio_contas: RepositorioContas,
    repositorio_tokens: RepositorioTokensAcesso,
    enviador: EnviadorDeEmail,
) -> JSONResponse:
    """A parte síncrona e bloqueante de `receber_webhook_hotmart` — `T-187`.
    Corpo idêntico ao que vivia direto na rota antes desta tarefa; só o
    ponto de chamada mudou."""
    if not confere:
        # O token também pode vir no corpo (`hottok`), não só no header —
        # ver a nota de `_hottok_confere`. Só dá pra checar isso depois de
        # ler o corpo, então a recusa por header sozinho fica pendurada até
        # aqui.
        confere = _hottok_confere(str(corpo.get("hottok") or "") or None)
        if not confere:
            return JSONResponse({"erro": _MENSAGEM_NAO_AUTORIZADO}, status_code=401)

    dados = corpo.get("data")
    produto = (dados or {}).get("product", {}) if isinstance(dados, dict) else {}

    # Diagnóstico de operação: nome do evento e id do produto, nunca e-mail
    # nem dado do comprador — mesma disciplina de `EnviadorSMTP` sobre não
    # logar PII. Existe para responder "que eventos a Hotmart manda aqui,
    # de fato" sem precisar reproduzir o payload real a cada dúvida.
    evento = corpo.get("event")
    print(f"webhook hotmart: event={evento!r} produto_id={produto.get('id')!r}")

    if evento not in (_EVENTO_APROVADA, _EVENTO_REEMBOLSADA):
        return JSONResponse({"ignorado": "evento"}, status_code=200)

    produto_esperado = os.environ.get(_VARIAVEL_HOTMART_PRODUTO_ID)
    if produto_esperado and str(produto.get("id", "")) != produto_esperado:
        return JSONResponse({"ignorado": "produto"}, status_code=200)

    comprador = (dados or {}).get("buyer", {}) if isinstance(dados, dict) else {}
    email = str(comprador.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"erro": _MENSAGEM_EMAIL_AUSENTE}, status_code=400)

    if evento == _EVENTO_REEMBOLSADA:
        # **Sem desbloqueio automático em compra nova** — decisão
        # deliberada (ver a migração `005`). Uma conta bloqueada some do
        # `buscar_por_email`? Não: continua existindo, só não autentica.
        # Se não existir conta com este e-mail, não há o que bloquear —
        # `200` de qualquer forma, a Hotmart não tem retry infinito à toa.
        alvo = repositorio_contas.buscar_por_email(email)
        if alvo is not None:
            repositorio_contas.bloquear(alvo.conta_id)
        return JSONResponse({"bloqueado": alvo is not None}, status_code=200)

    try:
        conta, _caso = provisionamento(email)
        conta_id = conta.conta_id
    except ErroEmailDuplicado:
        # Mesma disciplina de `provisionar`: compra repetida reemite o
        # link, nunca é erro.
        existente = repositorio_contas.buscar_por_email(email)
        if existente is None:  # pragma: no cover — defensivo: o UNIQUE acusou
            return JSONResponse({"erro": _MENSAGEM_NAO_AUTORIZADO}, status_code=401)
        conta_id = existente.conta_id

    token: TokenEmitido = repositorio_tokens.emitir(conta_id)

    email_enviado = True
    try:
        mensagem = primeiro_acesso(token.valor)
        enviador.enviar(email, mensagem.assunto, mensagem.corpo)
    except (ErroConfiguracaoEmail, ErroEnvioEmail, ErroUrlBaseAusente):
        email_enviado = False

    # Diferente de `/conta`: o token NÃO volta no corpo. Quem chama é a
    # Hotmart, não um sistema que precise repassá-lo — o único caminho de
    # entrega ao aluno é o e-mail que acabou de sair.
    return JSONResponse({"provisionado": True, "email_enviado": email_enviado}, status_code=200)


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
def definir_senha(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
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
    acabou de escolher é exercitada na hora.

    **`def`, não `async def` — `T-187`.** `consumir`/`definir_senha` (do
    repositório) gravam no banco. Ver a nota em
    `rotas_api_conta.py::cadastrar`."""
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
def pedir_recuperacao(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
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
    junto com o limitador do login, na tarefa dedicada.

    **`def`, não `async def` — `T-187`.** Consulta o banco e envia e-mail
    por SMTP — as duas bloqueantes. Ver a nota em
    `rotas_api_conta.py::cadastrar`."""
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
