"""Fichas repetíveis — `RF-04`, `RF-51`, `RF-53`, `AC-04` (T-134).

**A lacuna que estas rotas fecham.** A ficha repetível (antes
`report/templates/coleta/
ficha_repetivel.html` existe desde `T-47`, está testada, e **nenhuma rota a
renderiza**: era a tela mais cara já construída neste projeto e estava morta.
Pior — **108 das 247 perguntas** têm `escopo_repeticao != NENHUM` (Blocos 3,
5, 7, 8 e 11), e sem uma rota que liste/crie/remova itens o aluno não
cadastra nem uma dívida. O Bloco 5 inteiro, que é o núcleo do PIQ, dependia
disto.

**O que estas rotas NÃO fazem.** Não decidem quais perguntas pertencem à
ficha (`collection/repeticao.py::perguntas_da_ficha`, por
`escopo_repeticao`), não geram identificador (`RepositorioItens::
proximo_identificador`, que garante não-reaproveitamento mesmo após remoção)
e não decidem se uma ficha está completa (`pendencias_obrigatorias`). Tudo
isso já existe e é apenas orquestrado aqui — mesma disciplina de
`rotas_pergunta.py`.

**Remoção é marcação, nunca `DELETE`.** `RepositorioItens.remover` grava
`removido_em`; o identificador daquele item **nunca** volta a ser gerado
(`AC-04`). Uma ficha removida some da lista, mas sua memória permanece.

REGRAS: `RF-04`, `RF-51`, `RF-53`, `AC-04`
"""

from __future__ import annotations

from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.progresso import pendencias_obrigatorias
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
from collection.registro import EscopoRepeticao
from collection.repeticao import perguntas_da_ficha
from collection.respostas import RespostasCaso
from persistencia.app_aluno.itens import RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

REGRAS: Final[tuple[str, ...]] = ("RF-04", "RF-51", "RF-53", "AC-04")

roteador = APIRouter(prefix="/caso", tags=["fichas"])

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_ESCOPO_INVALIDO: Final[str] = "Escopo de repetição inválido."
_MENSAGEM_ITEM_INEXISTENTE: Final[str] = "Item não encontrado no caso."


def _escopo_valido(escopo: str) -> EscopoRepeticao | None:
    """`escopo` da URL → membro do enum, ou `None`. Nunca um default
    "parecido": escopo desconhecido é `400`, não uma ficha de outro tipo."""
    try:
        membro = EscopoRepeticao(escopo)
    except ValueError:
        return None
    return None if membro is EscopoRepeticao.NENHUM else membro


def _campos_da_ficha(
    colecao: ColecaoDeRegistros,
    escopo: EscopoRepeticao,
    respostas: RespostasCaso,
    CASO_ID: str,
    item_id: str,
) -> list[dict[str, Any]]:
    """As perguntas da ficha, já serializadas, para UM item.

    Pergunta cuja `condicao_exibicao` é falsa **naquele item** é omitida —
    quem decide é `montar_contexto_pergunta`, no servidor (`RF-52`); o
    cliente recebe só o que deve desenhar."""
    campos: list[dict[str, Any]] = []
    for registro in perguntas_da_ficha(colecao.registros, escopo):
        try:
            contexto = montar_contexto_pergunta(registro, respostas, item_id=item_id)
        except ErroPerguntaNaoExibivel:
            continue
        campos.append(serializar_pergunta(contexto, CASO_ID=CASO_ID, item_id=item_id))
    return campos


@roteador.get("/{CASO_ID}/fichas/{escopo}")
def listar_fichas(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> JSONResponse:
    """`RF-04`/`AC-04` — as fichas ATIVAS do escopo, com seus campos.

    `completa` é leitura de `pendencias_obrigatorias` (T-44), nunca uma
    segunda checagem de obrigatoriedade escrita aqui."""
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    respostas = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))
    itens_por_escopo = _itens_por_escopo(repositorio_itens, CASO_ID)
    pendentes = {
        (pendencia.ID, pendencia.item_id)
        for pendencia in pendencias_obrigatorias(colecao.registros, respostas, itens_por_escopo)
    }

    fichas: list[dict[str, Any]] = []
    for item_id in itens_por_escopo.get(membro, ()):
        campos = _campos_da_ficha(colecao, membro, respostas, CASO_ID, item_id)
        completa = not any(item == item_id for _id, item in pendentes)
        fichas.append({"item_id": item_id, "completa": completa, "campos": campos})

    return JSONResponse({"CASO_ID": CASO_ID, "escopo": membro.value, "fichas": fichas})


@roteador.post("/{CASO_ID}/fichas/{escopo}")
def criar_ficha(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> JSONResponse:
    """`AC-04` — cria um item com identificador estável (`D001`, `M002`…).

    O identificador vem de `RepositorioItens.proximo_identificador`, que
    conta TODAS as linhas do par `(CASO_ID, escopo)` — removidas inclusive —
    para que um número já usado nunca volte. Criar uma ficha não altera
    nenhuma das existentes: nenhuma resposta é tocada aqui."""
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    item_id = repositorio_itens.proximo_identificador(CASO_ID, membro)
    respostas = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))
    campos = _campos_da_ficha(colecao, membro, respostas, CASO_ID, item_id)

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "escopo": membro.value,
            "ficha": {"item_id": item_id, "completa": False, "campos": campos},
        },
        status_code=201,
    )


@roteador.delete("/{CASO_ID}/fichas/{escopo}/{item_id}")
def remover_ficha(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    item_id: str,
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> JSONResponse:
    """`AC-04` — marca o item como removido; **nunca** apaga a linha.

    É essa memória que impede o reaproveitamento do identificador. Remover
    a ficha `D002` não faz a próxima nascer `D002`."""
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    ativos = {
        item.item_id
        for item in repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
        if item.escopo is membro
    }
    if item_id not in ativos:
        return JSONResponse({"erro": _MENSAGEM_ITEM_INEXISTENTE}, status_code=404)

    repositorio_itens.remover(CASO_ID, item_id)
    return JSONResponse({"CASO_ID": CASO_ID, "escopo": membro.value, "removido": item_id})


@roteador.get("/{CASO_ID}/escopos")
def listar_escopos(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
) -> JSONResponse:
    """Os escopos de repetição que o questionário de fato usa.

    Derivado dos próprios registros (`escopo_repeticao`), nunca de uma lista
    escrita aqui — um escopo novo no YAML aparece sem tocar neste código
    (`RF-03`)."""
    usados = sorted(
        {
            registro.escopo_repeticao.value
            for registro in colecao.registros
            if registro.escopo_repeticao is not EscopoRepeticao.NENHUM
        }
    )
    return JSONResponse({"CASO_ID": CASO_ID, "escopos": usados})
