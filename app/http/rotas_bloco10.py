"""Rota de resposta do Bloco 10 — `RF-18`, `AC-22`, `AC-23`, `AC-24` (T-77,
T-78).

`POST /caso/{CASO_ID}/bloco-10/resposta` é uma ESPECIALIZAÇÃO de `POST
/caso/{CASO_ID}/resposta` (`app/http/rotas_coleta.py`, T-42/T-44), restrita
às duas perguntas de `app/casos/confirmacao_ataque.py::perguntas_do_
bloco_10` (`B10.C01`, `B10.C01A`) — mesmo precedente de especialização de
`app/http/rotas_bloco11.py` (T-82): os passos comuns (registro → condição →
conversão → validação → gravação) não são reimplementados, só encadeados
sobre o subconjunto de registros deste bloco.

**Duas diferenças em relação a `rotas_coleta.py`, as duas exigidas por
`RF-18`/`AC-22`/`AC-23`:**

1. **Guarda de alcançabilidade (`AC-22`).** Antes de aceitar qualquer
   resposta, esta rota exige `app/casos/confirmacao_ataque.py::
   bloco_10_alcancavel(snapshot)` — com `ATAQUE_IMEDIATO_RECOMENDADO == 0`,
   `B10.C01` nunca é aceita, mesmo que o `ID_PERGUNTA` exista no registro:
   o Bloco 10 inteiro está fechado para este caso. Nenhum snapshot liberado
   também recusa pelo mesmo caminho — sem snapshot não há campo a ler.

2. **Validação cruzada com o snapshot (`AC-23`, `T-78`).** `B10.C01A`
   declara, no registro, `ATAQUE_IMEDIATO_APROVADO <= ATAQUE_IMEDIATO_
   RECOMENDADO` — o limite direito é um campo do snapshot, não uma resposta
   gravada. `validar_cruzada` (`collection/validacao.py`, T-13) só sabe
   consultar `Respostas.valor_no_item`; esta rota fornece `app/casos/
   confirmacao_ataque.py::RespostasDoBloco10`, o adaptador que resolve
   `ZERO`/`ATAQUE_IMEDIATO_RECOMENDADO` a partir do MESMO snapshot que abriu
   o bloco, delegando qualquer outra variável para a `RespostasCaso` real —
   nenhum literal de limite em `.py`, nenhum recálculo.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.confirmacao_ataque` (T-77/T-78),
`app.casos.maquina`, `app.montagem.conversao`, `collection.carga`/
`condicoes`/`validacao`/`respostas`, `engine.snapshot`/`engine.portas` e
`persistencia.app_aluno.casos`/`respostas`/`persistencia.supabase.
repositorio_snapshots` — nunca de `engine/` além dos nomes já liberados
transitivamente por essas portas (`AC-41`).

REGRAS: `RF-18`, `AC-22`, `AC-23`, `AC-24`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.casos.confirmacao_ataque import (
    RespostasDoBloco10,
    bloco_10_alcancavel,
    perguntas_do_bloco_10,
)
from app.casos.maquina import ErroConsentimentoNaoRegistrado
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.montagem.conversao import ErroConversaoInvalida, converter_para_dinheiro
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.condicoes import avaliar
from collection.registro import RegistroPergunta, TipoResposta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso, ValorResposta
from collection.validacao import validar_cruzada
from engine.portas import RepositorioSnapshots
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.respostas import (
    ErroCasoInexistenteParaResposta,
    ErroGravacaoResposta,
    RepositorioRespostas,
    RepositorioRespostasSupabase,
)
from persistencia.supabase.repositorio_snapshots import (
    ErroSnapshotNaoEncontrado,
    RepositorioSnapshotsSupabase,
)

REGRAS: Final[tuple[str, ...]] = ("RF-18", "AC-22", "AC-23", "AC-24")

roteador = APIRouter(prefix="/caso", tags=["bloco-10"])

_TIPOS_QUE_EXIGEM_CONVERSAO_DECIMAL: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.MOEDA, TipoResposta.TAXA}
)

# Mensagens curtas de propósito — mesma disciplina de `rotas_coleta.py`/
# `rotas_bloco11.py` (`AC-37`/T-08: literal fora de docstring sob o limiar
# de 40 caracteres).
_MENSAGEM_PERGUNTA_NAO_ENCONTRADA: Final[str] = "Registro de pergunta inválido: ID desconhecido."
_MENSAGEM_PERGUNTA_NAO_ABERTA: Final[str] = "Pergunta não está aberta para resposta."
_MENSAGEM_BLOCO_10_NAO_ALCANCAVEL: Final[str] = "Bloco 10 indisponível."
_MENSAGEM_FALHA_SALVAR: Final[str] = "Não foi possível salvar."


class ErroPerguntaForaDoBloco10(Exception):
    """`ID_PERGUNTA` recebido não é uma das perguntas de `app/casos/
    confirmacao_ataque.py::perguntas_do_bloco_10` — esta rota é
    especializada, mesmo precedente de `app/http/rotas_bloco11.py::
    ErroPerguntaForaDoBloco11`."""


class ErroBloco10NaoAlcancavel(Exception):
    """`AC-22` — o caso não tem `ATAQUE_IMEDIATO_RECOMENDADO > 0` (ou não tem
    snapshot liberado para consultar); nenhuma resposta do Bloco 10 é aceita
    neste estado, mesmo que o `ID_PERGUNTA` seja válido."""


class ErroPerguntaNaoAberta(Exception):
    """A `condicao_exibicao` do registro avalia como falsa sobre as
    respostas já gravadas do caso — mesma semântica de `rotas_coleta.py::
    ErroPerguntaNaoAberta`."""


class ErroValidacaoCruzadaFalhou(Exception):
    """`AC-23` — mesma semântica de `rotas_coleta.py::
    ErroValidacaoCruzadaFalhou`: carrega os dois nomes de campo e a
    `mensagem` do próprio registro (`0 <= ATAQUE_IMEDIATO_APROVADO <=
    ATAQUE_IMEDIATO_RECOMENDADO`)."""

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


def obter_repositorio_snapshots() -> RepositorioSnapshots:
    """Ponto único de injeção da porta `RepositorioSnapshots` — mesmo padrão
    de `app/http/rotas_coleta_dirigida.py::obter_repositorio_snapshots`.
    Sobrescrito nos testes via `app.dependency_overrides`."""
    return RepositorioSnapshotsSupabase()


async def _ler_formulario(request: Request) -> dict[str, str]:
    """Mesma decodificação de `rotas_coleta.py::_ler_formulario` — stdlib
    (`parse_qsl`), sem `python-multipart`."""
    from urllib.parse import parse_qsl

    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return dict(pares)


def _localizar_registro_do_bloco_10(
    colecao: ColecaoDeRegistros, id_pergunta: str
) -> RegistroPergunta:
    """Restringe a busca às perguntas do Bloco 10 — uma `ID_PERGUNTA` válida
    no questionário geral, mas fora deste subconjunto, é recusada aqui como
    se fosse desconhecida."""
    perguntas_do_bloco = perguntas_do_bloco_10(colecao.registros)
    for registro in perguntas_do_bloco:
        if registro.ID == id_pergunta:
            return registro
    raise ErroPerguntaForaDoBloco10(id_pergunta)


def _exigir_pergunta_aberta(registro: RegistroPergunta, respostas: RespostasCaso) -> None:
    if registro.condicao_exibicao is None:
        return
    if not avaliar(registro.condicao_exibicao, respostas):
        raise ErroPerguntaNaoAberta(registro.ID)


def _resolver_valor(registro: RegistroPergunta, dados: dict[str, str]) -> ValorResposta:
    """Mesma disciplina de `rotas_coleta.py::_resolver_valor` (`RF-11`,
    `RF-13`, `EC-01`): `nao_sei` grava `NAO_SEI` e pula a conversão; `MOEDA`
    (`B10.C01A`) passa pela fronteira `Decimal` única."""
    if dados.get("nao_sei"):
        return NAO_SEI

    valor_bruto = dados.get("valor", "")
    if registro.tipo is TipoResposta.MOEDA:
        return converter_para_dinheiro(valor_bruto)
    return valor_bruto


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


def _exigir_validacao_cruzada(
    registro: RegistroPergunta,
    item_id: str | None,
    respostas_do_bloco_10: RespostasDoBloco10,
) -> None:
    """`AC-23`/`T-78`: mesma disciplina de `rotas_coleta.py::_exigir_
    validacao_cruzada`, mas consultando `RespostasDoBloco10` em vez de
    `RespostasCaso` diretamente — é essa troca que permite `ATAQUE_IMEDIATO_
    RECOMENDADO`/`ZERO` resolverem contra o snapshot, sem nenhum literal de
    limite nesta rota nem em `confirmacao_ataque.py`."""
    if not registro.validacoes_cruzadas:
        return
    chave_do_item = item_id or ""
    for validacao in registro.validacoes_cruzadas:
        resultado = validar_cruzada(validacao, chave_do_item, respostas_do_bloco_10)
        if not resultado.valida:
            raise ErroValidacaoCruzadaFalhou(
                variavel_esquerda=resultado.variavel_esquerda or "",
                variavel_direita=resultado.variavel_direita or "",
                mensagem=resultado.mensagem or "",
            )


def _agora() -> datetime:
    return datetime.now(UTC)


def _resposta_de_erro(mensagem: str, status_code: int) -> JSONResponse:
    return JSONResponse({"erro": mensagem}, status_code=status_code)


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: mesmo precedente de `app/http/rotas_coleta_dirigida.py` —
    `exigir_caso_da_sessao` já garantiu que `CASO_ID` existe e pertence à
    conta da sessão."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento confirmá-lo")


@roteador.post("/{CASO_ID}/bloco-10/resposta")
def responder_bloco_10(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """Os sete passos do plano §5.1 restritos a `B10.C01`/`B10.C01A`, mais a
    guarda de alcançabilidade (`AC-22`) ANTES de qualquer um deles. Devolve
    `200` com a confirmação de gravação somente APÓS a gravação ter
    retornado sem exceção — mesma garantia de `AC-02` que `rotas_coleta.py`
    já oferece.

    **`def`, não `async def` — `T-187`.** Ver a nota em
    `rotas_api_conta.py::cadastrar`. `dados` chega por `Depends`, resolvido
    antes de qualquer checagem abaixo — o corpo é parseado mesmo quando a
    guarda de alcançabilidade recusa a requisição antes de o ler; parsear
    um formulário que acaba não sendo usado é o único efeito, não uma
    mudança de comportamento."""
    # Passo 1 já ocorreu: `exigir_caso_da_sessao` verificou, no servidor, que
    # a sessão possui este CASO_ID.
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    # AC-22: sem snapshot liberado, ou com ATAQUE_IMEDIATO_RECOMENDADO == 0,
    # o Bloco 10 inteiro está fechado — nenhuma resposta é aceita.
    if caso.snapshot_liberado_id is None:
        return _resposta_de_erro(_MENSAGEM_BLOCO_10_NAO_ALCANCAVEL, 400)
    try:
        snapshot = repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return _resposta_de_erro(_MENSAGEM_BLOCO_10_NAO_ALCANCAVEL, 400)
    if not bloco_10_alcancavel(snapshot):
        return _resposta_de_erro(_MENSAGEM_BLOCO_10_NAO_ALCANCAVEL, 400)

    id_pergunta = dados.get("ID_PERGUNTA", "")
    item_id = dados.get("item_id") or None

    try:
        registro = _localizar_registro_do_bloco_10(colecao, id_pergunta)
    except ErroPerguntaForaDoBloco10:
        return _resposta_de_erro(_MENSAGEM_PERGUNTA_NAO_ENCONTRADA, 400)
    if registro.VARIAVEL_GRAVADA is None:
        raise ErroPerguntaForaDoBloco10(registro.ID)  # defensivo — nenhum registro real viola isso

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

    # Passo 5: validação cruzada (AC-23) — o limite superior de B10.C01A vem
    # do snapshot, via RespostasDoBloco10, nunca de um literal aqui.
    respostas_com_valor_corrente = _respostas_com_valor_provisorio(
        respostas_do_caso, registro, item_id, valor
    )
    respostas_do_bloco_10 = RespostasDoBloco10(
        respostas=respostas_com_valor_corrente, snapshot=snapshot
    )
    try:
        _exigir_validacao_cruzada(registro, item_id, respostas_do_bloco_10)
    except ErroValidacaoCruzadaFalhou as erro:
        mensagem = f"{erro.variavel_esquerda}/{erro.variavel_direita}: {erro.mensagem}"
        return _resposta_de_erro(mensagem, 400)

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
    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "ID_PERGUNTA": registro.ID,
            "valor_gravado": str(valor),
        }
    )
