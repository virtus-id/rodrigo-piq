"""Rota `GET` de coleta — `RF-45`, `RF-46`, `AC-72`, `AC-74`, `EC-23`,
`EC-24` (T-123).

**A lacuna que esta rota fecha.** `T-45` entregou
`app/casos/progresso.py::proxima_pergunta_nao_respondida` e `T-43` entregou
`app/http/renderizacao.py::montar_contexto_pergunta`, ambos testados — mas a
rota que os costura ficou explicitamente fora de escopo (ver a nota de
abertura de `app/http/renderizacao.py`, que registra a ausência). O efeito
prático era que o aluno se cadastrava, consentia e **não alcançava pergunta
nenhuma**: `POST /caso/{CASO_ID}/resposta` existia sem nenhum caminho que
dissesse QUAL pergunta responder.

**`RF-45` — o cliente nunca avalia condicional.** Esta rota devolve UMA
pergunta já decidida exibível. Quando a `condicao_exibicao` de um registro é
falsa, quem avança até a próxima é o servidor (`EC-24`), reusando a MESMA
`avaliar` de `collection/condicoes.py` por dentro de
`montar_contexto_pergunta` — nunca uma segunda implementação, e nunca o
grafo condicional atravessando a fronteira para o navegador. É essa
restrição que separa este desenho do SPA recusado em
`plans/app-aluno.plan.md` §2 (ver a subseção "Revisão de 2026-09-14"), e
`AC-73` é a trava executável dela (`T-126`).

**Isolamento (`AC-74`).** Os dois caminhos declaram o path parameter com o
nome canônico `CASO_ID` (`sdd.config.md` §7) e a dependência
`exigir_caso_da_sessao("CASO_ID")` — é exatamente o par que a auditoria de
`tests/app_aluno/e2e/test_mecanismo_isolamento.py::
rotas_sem_isolamento_por_caso` reconhece ao enumerar as `APIRoute`
registradas. Sem sessão ⇒ `401`; caso de outra conta ou inexistente ⇒ `404`
indistinguível.

**Nada é calculado aqui (Lei nº 3).** `avanco_permitido` e
`total_pendencias` são LEITURA de `pendencias_obrigatorias` (`T-44`), a
mesma fonte que `rotas_coleta.py` já usa ao confirmar uma gravação — esta
rota não reimplementa obrigatoriedade nem conta pendência por conta
própria.

REGRAS: `RF-45`, `RF-46`, `AC-72`, `AC-74`, `EC-23`, `EC-24`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.casos.progresso import (
    PendenciaObrigatoria,
    pendencias_obrigatorias,
    posicao_na_ficha,
    proxima_pergunta_nao_respondida,
)
from app.http.concorrencia import duas_em_paralelo
from app.http.isolamento import exigir_caso_da_sessao
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import (
    _itens_por_escopo,
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import RespostasCaso
from persistencia.app_aluno.itens import RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

REGRAS: Final[tuple[str, ...]] = (
    "RF-45",
    "RF-46",
    "AC-72",
    "AC-74",
    "EC-23",
    "EC-24",
)


roteador = APIRouter(prefix="/caso", tags=["coleta"])

# Mensagem curta de propósito — limiar de `AC-37` (T-08). A mesma para
# "não existe" e "condição falsa": a existência de uma pergunta fechada
# nunca vaza (`RF-45`).
_MENSAGEM_INDISPONIVEL: Final[str] = "Pergunta indisponível."


class ErroPerguntaDesconhecida(Exception):
    """`ID_PERGUNTA` da URL não corresponde a nenhum `RegistroPergunta`
    carregado — recusado antes de qualquer avaliação de condição, nunca
    tratado como pergunta "sempre aberta" por omissão. Mesmo critério de
    `app/http/rotas_coleta.py::ErroPerguntaDesconhecida`, exceção própria
    porque o tratamento aqui é `404` (pergunta inexistente numa URL `GET`),
    não o `400` de um corpo de formulário inválido."""


def _localizar_registro(colecao: ColecaoDeRegistros, id_pergunta: str) -> RegistroPergunta:
    """Registro por `ID` — mesma varredura de
    `app/http/rotas_coleta.py::_localizar_registro`."""
    for registro in colecao.registros:
        if registro.ID == id_pergunta:
            return registro
    raise ErroPerguntaDesconhecida(id_pergunta)


def _primeira_exibivel(
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[RegistroPergunta, PendenciaObrigatoria] | None:
    """`EC-24` — a primeira pendência cuja pergunta é de fato EXIBÍVEL.

    `proxima_pergunta_nao_respondida` (T-45) já exclui pergunta cuja
    condição não vale, mas quem levanta `ErroPerguntaNaoExibivel` é
    `montar_contexto_pergunta` — e é ele a autoridade, porque é a mesma
    `avaliar` usada na gravação. Varrer aqui as pendências EM ORDEM e parar
    na primeira que monta contexto sem erro mantém as duas leituras
    coerentes sem reimplementar nenhuma delas.

    Devolve `None` quando não há mais pendência exibível — coleta completa
    do ponto de vista do grafo condicional corrente (`EC-23`)."""
    pendencia = proxima_pergunta_nao_respondida(colecao.registros, respostas, itens_por_escopo)
    if pendencia is None:
        return None

    registro = _localizar_registro(colecao, pendencia.ID)
    try:
        montar_contexto_pergunta(registro, respostas, item_id=pendencia.item_id)
    except ErroPerguntaNaoExibivel:
        return None
    return registro, pendencia


@roteador.get("/{CASO_ID}/pergunta", response_class=HTMLResponse)
def proxima_pergunta(
    request: Request,
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> Response:
    """`RF-46`, `AC-72` — a primeira pergunta não respondida e exibível.

    Coleta completa (`EC-23`) devolve a tela de conclusão, nunca `500` nem
    uma pergunta arbitrária.

    **Duas consultas em paralelo (`T-191`).** `respostas` e
    `itens_por_escopo` não dependem uma da outra — cada uma só precisa de
    `CASO_ID`. Esta é a rota mais frequente do sistema (uma chamada por
    pergunta, até ~291 vezes por aluno); em sequência, cada uma paga
    ~484ms de distância Boston↔São Paulo (`T-187`) por nada."""
    respostas_brutas, itens_por_escopo = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: _itens_por_escopo(repositorio_itens, CASO_ID),
    )
    respostas = RespostasCaso(respostas=respostas_brutas)

    encontrada = _primeira_exibivel(colecao, respostas, itens_por_escopo)
    if encontrada is None:
        return _coleta_completa(request, CASO_ID)

    registro, pendencia = encontrada
    return _renderizar_pergunta(
        request, CASO_ID, registro, respostas, colecao, itens_por_escopo, pendencia.item_id
    )


@roteador.get("/{CASO_ID}/pergunta/{ID_PERGUNTA}", response_class=HTMLResponse)
def pergunta_especifica(
    request: Request,
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    ID_PERGUNTA: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    item_id: str | None = None,
) -> Response:
    """`RF-46` — uma pergunta específica do caso, para reabrir um campo já
    respondido (`AC-33`) sem varrer a coleta inteira.

    Pergunta inexistente ⇒ `404`. Pergunta cuja condição é falsa ⇒ `404`
    também: do ponto de vista do aluno ela não existe, e dizer "existe mas
    está fechada" devolveria ao cliente justamente a informação de
    condicional que `RF-45` mantém no servidor.

    Mesmo paralelismo de `proxima_pergunta`, acima (`T-191`)."""
    respostas_brutas, itens_por_escopo = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: _itens_por_escopo(repositorio_itens, CASO_ID),
    )
    respostas = RespostasCaso(respostas=respostas_brutas)

    try:
        registro = _localizar_registro(colecao, ID_PERGUNTA)
    except ErroPerguntaDesconhecida:
        return _resposta_nao_encontrada(request, CASO_ID)

    try:
        return _renderizar_pergunta(
            request, CASO_ID, registro, respostas, colecao, itens_por_escopo, item_id
        )
    except ErroPerguntaNaoExibivel:
        return _resposta_nao_encontrada(request, CASO_ID)


def _renderizar_pergunta(
    request: Request,
    CASO_ID: str,
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    colecao: ColecaoDeRegistros,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    item_id: str | None,
) -> Response:
    """Monta a página de uma pergunta. `avanco_permitido`/`total_pendencias`
    são leitura de `pendencias_obrigatorias` — nunca recontados aqui.

    `T-144`: a tela é React e a resposta é sempre JSON. A decisão de QUAL
    pergunta exibir continua inteira no servidor (`RF-52`) — o cliente
    recebe uma pergunta já decidida e nunca avalia `condicao_exibicao`."""
    contexto = montar_contexto_pergunta(registro, respostas, item_id=item_id)
    pendencias = pendencias_obrigatorias(colecao.registros, respostas, itens_por_escopo)
    # `RF-63` (T-148): o localizador do `.top` — "Dívida 3 · pergunta 4 de
    # 12". `None` fora de ficha repetível, e aí o cliente cai no rótulo do
    # bloco. Quem conta é o servidor: ele é que conhece o conjunto exibível.
    posicao = posicao_na_ficha(registro, colecao.registros, respostas)

    return JSONResponse(
        {
            "pergunta": serializar_pergunta(
                contexto,
                CASO_ID=CASO_ID,
                item_id=item_id,
                posicao=posicao.posicao if posicao is not None else None,
                total_na_ficha=posicao.total_na_ficha if posicao is not None else None,
            ),
            "avanco_permitido": not pendencias,
            "total_pendencias": len(pendencias),
        }
    )


def _coleta_completa(request: Request, CASO_ID: str) -> Response:
    """`EC-23` — não há mais pergunta pendente e exibível."""
    return JSONResponse({"pergunta": None, "coleta_completa": True, "CASO_ID": CASO_ID})


def _resposta_nao_encontrada(request: Request, CASO_ID: str) -> Response:
    """`404` com a mesma resposta para "não existe" e "condição falsa" — a
    existência de uma pergunta fechada nunca vaza (`RF-45`)."""
    return JSONResponse({"erro": _MENSAGEM_INDISPONIVEL}, status_code=404)
