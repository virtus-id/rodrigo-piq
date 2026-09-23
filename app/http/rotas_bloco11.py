"""Rota de confirmação de quitação do Bloco 11 — `RF-29`, `AC-05`, `AC-30`,
`AC-31` (T-82).

`POST /caso/{CASO_ID}/bloco-11/resposta` é uma ESPECIALIZAÇÃO de `POST
/caso/{CASO_ID}/resposta` (`app/http/rotas_coleta.py`, T-42/T-44) — os mesmos
sete passos do plano §5.1 (isolamento → registro → condição → conversão →
validação → gravação → aviso), restritos às perguntas de `app/casos/
acompanhamento.py::perguntas_do_bloco_11_confirmacao_quitacao` (`B11.Q01`–
`B11.Q06`, mais `B11.Q04A`) — e um passo A MAIS, específico deste bloco:
depois de gravar `B11.Q01`, IDENTIFICA o `EVENTO_RECALCULO` correspondente
(`app/casos/acompanhamento.py::evento_da_resposta_b11_q01`, que por sua vez
chama `app/eventos/mapeamento.py::evento_recalculo_da_resposta`, T-81) e o
inclui na resposta HTTP — sem disparar nenhum recálculo (ver a fronteira com
`T-86`, abaixo).

**Por que esta rota existe separada de `rotas_coleta.py`, e não uma
ramificação dentro dela.** `POST /caso/{CASO_ID}/resposta` é genérica sobre
QUALQUER `ID_PERGUNTA` das 291; ela não sabe (e não deveria saber) que
`B11.Q01` é especial. Colocar a lógica de identificação de evento ali
significaria um `if ID_PERGUNTA == "B11.Q01"` dentro de uma rota que hoje é
inteiramente genérica — o oposto do padrão do restante desta feature (nenhum
`if` por pergunta, ver `collection/condicoes.py`, `collection/repeticao.py`).
Em vez disso, esta rota especializada só aceita as perguntas do Bloco 11 de
confirmação de quitação (recusando qualquer outra `ID_PERGUNTA` como
desconhecida) e reaproveita as mesmas funções puras de `rotas_coleta.py` para
os sete passos comuns — nenhuma regra de conversão, validação cruzada ou
gravação é duplicada aqui.

**`AC-31`: `A_CONFIRMAR` (e `NAO`) não disparam nada.** `evento_da_resposta_
b11_q01` devolve `None` para essas duas respostas — estrutural, não um `if`
desta rota (ver `app/eventos/mapeamento.py`, T-81). Esta rota RESPEITA esse
`None` simplesmente não incluindo nenhum evento na resposta HTTP e não
chamando mais nada além da gravação já feita: nenhuma diferença de
comportamento entre `NAO`/`A_CONFIRMAR` e qualquer outra pergunta comum
existe no código desta rota além do campo `evento_recalculo` da resposta
JSON, que fica `null`.

**`AC-05`: o enunciado exibe o `DIVIDA_ID` da ficha corrente.** A
interpolação de `[Dxxx]` em `B11.Q01` (`collection/registros/bloco-11.yaml`,
T-18; `collection/interpolacao.py::interpolar`, T-12) usa `item_id` recebido
no formulário como o identificador do item corrente — hoje sempre um
`DIVIDA_ID` (ver a nota extensa em `app/casos/acompanhamento.py` sobre a
fronteira temporária com `ACAO_ID`/`T-83`: `AcaoRequerida` ainda não publica
`ACAO_ID`). Esta rota devolve o enunciado JÁ INTERPOLADO na confirmação, para
que `AC-05` seja observável na resposta HTTP sem depender de uma tela.

**Fronteira com `T-86` — o que esta rota NÃO faz.** Identificar o evento
("enfileirar o recálculo", na redação da tarefa) significa, aqui, apenas
calcular `EVENTO_RECALCULO | None` e devolvê-lo no corpo da resposta HTTP.
Esta rota **não** importa `app/motor/executor.py` (que não existe: nasce em
`T-86`), não chama `engine.eventos.avaliar_gatilho_recalculo` nem `engine.
motor.calcular_plano`, e não dispara a transição `ACOMPANHAMENTO →
CALCULANDO` (`app/casos/maquina.py`, gatilho `recalcula`) declarada para
`AC-30`/`RF-28`. O consumidor futuro de `T-86` é quem lê `evento_recalculo`
(hoje só devolvido na resposta HTTP; persistir/consumir esse valor por outro
canal é decisão de `T-86`, não desta tarefa) e decide acionar o executor.

**Formato do payload e da resposta.** Mesmo `application/x-www-form-
urlencoded` de `rotas_coleta.py` (`ID_PERGUNTA`, `item_id`, `valor`,
`nao_sei`). A resposta é JSON (não HTML): o critério de aceite fala em
"marca `QUITADA` e enfileira o recálculo" e em "o enunciado exibe o
`DIVIDA_ID`" — dados observáveis, e um router novo sem template dedicado
(escopo desta tarefa: só os dois arquivos citados no backlog) segue o mesmo
precedente de `app/http/rotas_coleta_dirigida.py` (T-75), que devolve JSON
pela mesma razão.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.acompanhamento` (T-82), `app.casos.maquina`,
`app.montagem.conversao`, `collection.carga`/`condicoes`/`interpolacao`/
`respostas`/`validacao` e `persistencia.app_aluno.respostas` — nunca de
`app/motor/executor.py` e nunca de `engine/` além dos nomes já liberados por
essas portas (`AC-41`).

REGRAS: `RF-29`, `AC-05`, `AC-30`, `AC-31`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.casos.acompanhamento import (
    evento_da_resposta_b11_q01,
    perguntas_do_bloco_11_confirmacao_quitacao,
)
from app.casos.maquina import ErroConsentimentoNaoRegistrado
from app.eventos.mapeamento import VARIAVEL_STATUS_QUITACAO_REAL
from app.http.isolamento import exigir_caso_da_sessao
from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
)
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.condicoes import avaliar
from collection.interpolacao import ContextoItem, interpolar
from collection.registro import RegistroPergunta, TipoResposta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso, ValorResposta
from collection.validacao import validar_cruzada
from persistencia.app_aluno.respostas import (
    ErroCasoInexistenteParaResposta,
    ErroGravacaoResposta,
    RepositorioRespostas,
    RepositorioRespostasSupabase,
)

REGRAS: Final[tuple[str, ...]] = ("RF-29", "AC-05", "AC-30", "AC-31")

roteador = APIRouter(prefix="/caso", tags=["bloco-11"])

_ID_PERGUNTA_STATUS_QUITACAO: Final[str] = "B11.Q01"

# Tipos que passam pela fronteira Decimal única — B11.Q03/B11.Q04A são MOEDA;
# as demais perguntas do bloco gravam a string bruta do formulário, mesma
# disciplina de `rotas_coleta.py::_TIPOS_QUE_EXIGEM_CONVERSAO_DECIMAL`.
_TIPOS_QUE_EXIGEM_CONVERSAO_DECIMAL: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.MOEDA, TipoResposta.TAXA}
)

# Mensagens curtas de propósito — mesma disciplina de `rotas_coleta.py`
# (`AC-37`/T-08: literal fora de docstring sob o limiar de 40 caracteres).
_MENSAGEM_PERGUNTA_NAO_ENCONTRADA: Final[str] = "Registro de pergunta inválido: ID desconhecido."
_MENSAGEM_PERGUNTA_NAO_ABERTA: Final[str] = "Pergunta não está aberta para resposta."
_MENSAGEM_FALHA_SALVAR: Final[str] = "Não foi possível salvar."


class ErroPerguntaForaDoBloco11(Exception):
    """`ID_PERGUNTA` recebido não é uma das seis perguntas de confirmação de
    quitação (`app/casos/acompanhamento.py::perguntas_do_bloco_11_
    confirmacao_quitacao`) — esta rota é especializada e recusa qualquer
    outra pergunta, mesmo que exista no questionário (ela pertence a `POST
    /caso/{CASO_ID}/resposta`, não a esta)."""


class ErroPerguntaNaoAberta(Exception):
    """A `condicao_exibicao` do registro avalia como falsa sobre as
    respostas já gravadas do caso — mesma semântica de `rotas_coleta.py::
    ErroPerguntaNaoAberta`."""


class ErroValidacaoCruzadaFalhou(Exception):
    """`EC-02` — mesma semântica de `rotas_coleta.py::
    ErroValidacaoCruzadaFalhou`: carrega os dois nomes de campo e a
    `mensagem` do próprio registro."""

    def __init__(self, variavel_esquerda: str, variavel_direita: str, mensagem: str) -> None:
        self.variavel_esquerda = variavel_esquerda
        self.variavel_direita = variavel_direita
        self.mensagem = mensagem
        super().__init__(mensagem)


def obter_colecao_de_registros() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros — mesmo padrão de
    `rotas_coleta.py::obter_colecao_de_registros`. Sobrescrito nos testes via
    `app.dependency_overrides`."""
    return carregar_registros()


def obter_repositorio_respostas() -> RepositorioRespostas:
    """Ponto único de injeção do repositório de respostas — mesmo padrão de
    `rotas_coleta.py::obter_repositorio_respostas`. Sobrescrito nos testes
    via `app.dependency_overrides`."""
    return RepositorioRespostasSupabase()


async def _ler_formulario(request: Request) -> dict[str, str]:
    """Mesma decodificação de `rotas_coleta.py::_ler_formulario` — stdlib
    (`parse_qsl`), sem `python-multipart`."""
    from urllib.parse import parse_qsl

    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return dict(pares)


def _localizar_registro_do_bloco_11(
    colecao: ColecaoDeRegistros, id_pergunta: str
) -> RegistroPergunta:
    """Restringe a busca às seis perguntas de confirmação de quitação — uma
    `ID_PERGUNTA` válida no questionário geral, mas fora deste subconjunto
    (ex.: `B11.01`, ou qualquer pergunta de outro bloco), é recusada aqui
    como se fosse desconhecida: esta rota é especializada, não genérica."""
    perguntas_do_bloco = perguntas_do_bloco_11_confirmacao_quitacao(colecao.registros)
    for registro in perguntas_do_bloco:
        if registro.ID == id_pergunta:
            return registro
    raise ErroPerguntaForaDoBloco11(id_pergunta)


def _exigir_pergunta_aberta(registro: RegistroPergunta, respostas: RespostasCaso) -> None:
    if registro.condicao_exibicao is None:
        return
    if not avaliar(registro.condicao_exibicao, respostas):
        raise ErroPerguntaNaoAberta(registro.ID)


def _resolver_valor(registro: RegistroPergunta, dados: dict[str, str]) -> ValorResposta:
    """Mesma disciplina de `rotas_coleta.py::_resolver_valor` (`RF-11`,
    `RF-13`, `EC-01`): `nao_sei` grava `NAO_SEI` e pula a conversão; `MOEDA`
    passa pela fronteira `Decimal` única."""
    if dados.get("nao_sei"):
        return NAO_SEI

    valor_bruto = dados.get("valor", "")
    if registro.tipo is TipoResposta.MOEDA:
        return converter_para_dinheiro(valor_bruto)
    return valor_bruto


def _exigir_validacao_cruzada(
    registro: RegistroPergunta, item_id: str | None, respostas: RespostasCaso
) -> None:
    if not registro.validacoes_cruzadas:
        return
    chave_do_item = item_id or ""
    for validacao in registro.validacoes_cruzadas:
        resultado = validar_cruzada(validacao, chave_do_item, respostas)
        if not resultado.valida:
            raise ErroValidacaoCruzadaFalhou(
                variavel_esquerda=resultado.variavel_esquerda or "",
                variavel_direita=resultado.variavel_direita or "",
                mensagem=resultado.mensagem or "",
            )


def _enunciado_interpolado(
    registro: RegistroPergunta, item_id: str | None, respostas: RespostasCaso
) -> str:
    """`AC-05` — devolve o enunciado com `[Dxxx]` já resolvido para o
    `DIVIDA_ID` da ficha corrente (ver a nota do módulo sobre a fronteira
    `DIVIDA_ID`/`ACAO_ID`). Perguntas sem marcador (a maioria) devolvem o
    enunciado inalterado — `interpolar` é total sobre uma tupla vazia de
    `marcadores`. `RespostasCaso` já satisfaz estruturalmente o `Protocol`
    `collection.interpolacao.Respostas` (mesma assinatura de `valor`,
    `collection/respostas.py`) — nenhum adaptador é necessário."""
    ctx = ContextoItem(item_id=item_id, respostas=respostas, snapshot=None)
    return interpolar(registro.enunciado, registro.interpolacoes, ctx)


def _respostas_com_valor_provisorio(
    respostas: RespostasCaso,
    registro: RegistroPergunta,
    item_id: str | None,
    valor: ValorResposta,
) -> RespostasCaso:
    """Mesmo propósito de `rotas_coleta.py::_respostas_com_valor_provisorio`
    — a validação cruzada precisa enxergar o valor recém-resolvido junto dos
    já persistidos, sem gravá-lo."""
    if registro.VARIAVEL_GRAVADA is None:
        return respostas
    provisoria = Resposta(
        CASO_ID="",
        ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION="",
        respondida_em=_agora(),
    )
    return RespostasCaso(respostas=(*respostas.respostas, provisoria))


def _agora() -> datetime:
    return datetime.now(UTC)


def _valor_interno_textual(valor: ValorResposta) -> str:
    """O `valor_interno` gravado para `B11.Q01` é sempre uma das três opções
    de `SELECAO_UNICA` (`QUITADA`/`NAO`/`A_CONFIRMAR`) — sempre `str` em
    tempo de execução para esta pergunta específica; convertido aqui só para
    satisfazer a assinatura de `evento_da_resposta_b11_q01`, sem reinterpretar
    o domínio."""
    return str(valor)


def _resposta_de_erro(mensagem: str, status_code: int) -> JSONResponse:
    return JSONResponse({"erro": mensagem}, status_code=status_code)


@roteador.post("/{CASO_ID}/bloco-11/resposta")
def responder_confirmacao_quitacao(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
) -> JSONResponse:
    """Os sete passos do plano §5.1 restritos a `B11.Q01`–`B11.Q06`
    (`B11.Q04A` incluída), mais a identificação do evento de recálculo
    quando a pergunta respondida é `B11.Q01` (`AC-30`/`AC-31`). Devolve `200`
    com a confirmação de gravação (mais `evento_recalculo`, quando
    aplicável) somente APÓS a gravação ter retornado sem exceção — mesma
    garantia de `AC-02` que `rotas_coleta.py` já oferece.

    **`def`, não `async def` — `T-187`.** Ver a nota em
    `rotas_api_conta.py::cadastrar`."""
    # Passo 1 já ocorreu: `exigir_caso_da_sessao` verificou, no servidor, que
    # a sessão possui este CASO_ID.
    id_pergunta = dados.get("ID_PERGUNTA", "")
    item_id = dados.get("item_id") or None

    try:
        registro = _localizar_registro_do_bloco_11(colecao, id_pergunta)
    except ErroPerguntaForaDoBloco11:
        return _resposta_de_erro(_MENSAGEM_PERGUNTA_NAO_ENCONTRADA, 400)
    if registro.VARIAVEL_GRAVADA is None:
        raise ErroPerguntaForaDoBloco11(registro.ID)  # defensivo — nenhum registro real viola isso

    respostas_do_caso = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))

    # Passo 2 (segunda metade): a pergunta precisa estar de fato aberta.
    try:
        _exigir_pergunta_aberta(registro, respostas_do_caso)
    except ErroPerguntaNaoAberta:
        return _resposta_de_erro(_MENSAGEM_PERGUNTA_NAO_ABERTA, 400)

    # Passos 3 e 4: NAO_SEI pula a conversão; MOEDA passa pela fronteira
    # Decimal única. EC-01: recusa sem gravar, nunca coage a 0.
    try:
        valor = _resolver_valor(registro, dados)
    except ErroConversaoInvalida as erro:
        mensagem = f"{registro.VARIAVEL_GRAVADA}: {erro.motivo}"
        return _resposta_de_erro(mensagem, 400)

    # Passo 5: validação cruzada, só quando o registro a declara.
    respostas_com_valor_corrente = _respostas_com_valor_provisorio(
        respostas_do_caso, registro, item_id, valor
    )
    try:
        _exigir_validacao_cruzada(registro, item_id, respostas_com_valor_corrente)
    except ErroValidacaoCruzadaFalhou as erro:
        mensagem = f"{erro.variavel_esquerda}/{erro.variavel_direita}: {erro.mensagem}"
        return _resposta_de_erro(mensagem, 400)

    # AC-05: o enunciado (com `[Dxxx]` já resolvido, quando aplicável) é
    # calculado ANTES da gravação — é só leitura, não depende do passo 6.
    enunciado = _enunciado_interpolado(registro, item_id, respostas_do_caso)

    # Passo 6: gravação com transação confirmada. EC-05: falha nunca reporta
    # sucesso — devolve erro explícito e NÃO avança.
    resposta = Resposta(
        CASO_ID=CASO_ID,
        ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
        respondida_em=_agora(),
    )
    try:
        repositorio.gravar(resposta)
    except ErroConsentimentoNaoRegistrado:
        return _resposta_de_erro(_MENSAGEM_PERGUNTA_NAO_ABERTA, 400)
    except (ErroGravacaoResposta, ErroCasoInexistenteParaResposta):
        return _resposta_de_erro(_MENSAGEM_FALHA_SALVAR, 503)

    # Neste ponto a resposta JÁ ESTÁ commitada no banco — encerrar o
    # processo agora não a perde (AC-02, mesma garantia de `rotas_coleta.py`).
    #
    # AC-30/AC-31: só quando a pergunta respondida é B11.Q01 (a única que
    # carrega STATUS_QUITACAO_REAL) esta rota IDENTIFICA o evento de
    # recálculo correspondente — nunca dispara o executor (T-86, ver a nota
    # do módulo sobre essa fronteira). Qualquer outra pergunta do bloco
    # (B11.Q02–Q06) nunca produz evento: `evento_recalculo` fica `null`.
    evento_recalculo = None
    if registro.VARIAVEL_GRAVADA == VARIAVEL_STATUS_QUITACAO_REAL:
        evento = evento_da_resposta_b11_q01(_valor_interno_textual(valor))
        evento_recalculo = evento.name if evento is not None else None

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "ID_PERGUNTA": registro.ID,
            "enunciado": enunciado,
            "evento_recalculo": evento_recalculo,
        }
    )
