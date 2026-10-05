"""Rever as respostas já dadas — `RF-68`, `AC-100`, `AC-101` (T-160).

**O buraco que esta rota fecha.** `RF-10` promete retomada sem redigitar, e o
sistema cumpria: a coleta voltava exatamente onde parou. Mas retomar não é
**conferir**, e não havia nenhuma superfície que mostrasse ao aluno o que ele
já tinha dito. O relato de uso foi direto: *"nem consigo ver o que foi
respondido, e se eu esquecer"*.

Para quem responde cem perguntas sobre o próprio dinheiro ao longo de semanas,
não poder reler o que disse é não poder confiar no plano que sai dali.

## O que esta rota NÃO faz

Não decide o que exibir: devolve **as respostas que existem**, agrupadas pelo
bloco a que pertencem. Não filtra por condicional (`RF-45` é sobre qual
pergunta o servidor ENTREGA a seguir; aqui já foi respondida, logo era
exibível), não ordena por relevância, não julga completude.

Não abre caminho novo de escrita. Corrigir uma resposta é `POST
/caso/{CASO_ID}/resposta`, a MESMA rota da resposta original (`RF-69`) — um
segundo caminho de gravação seria uma segunda regra de validação, e `EC-01`
deixaria de ser soberano.

REGRAS: `RF-68`, `RF-10`, `AC-100`, `AC-101`
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.maquina import ESTADO_CASO, ErroTransicaoNaoDeclarada
from app.casos.progresso import transicionar_e_registrar
from app.concorrencia import duas_em_paralelo
from app.http.edicao import ESTADOS_SOMENTE_LEITURA
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.jornada import PARTES
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import (
    _itens_e_rotulos,
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.serializacao import serializar_valor
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao, RegistroPergunta, TipoResposta
from collection.respostas import RespostasCaso, ValorResposta
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.eventos import RepositorioEventosCaso, RepositorioEventosCasoSupabase
from persistencia.app_aluno.itens import RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas
from report.plano import formatar_dinheiro_br

REGRAS: Final[tuple[str, ...]] = ("RF-68", "RF-10", "AC-100", "AC-101")

roteador = APIRouter(prefix="/caso", tags=["respostas"])

# `T-295`: checklist respondido sem nada marcado grava `frozenset()`; o aluno
# lê isto, nunca `"[]"`. Texto vazio vai como lista vazia ("Respondida." no
# cliente), nunca `""`.
_NENHUM_ITEM_MARCADO: Final[str] = "Nenhum item marcado."


def _respondida(
    registro: RegistroPergunta, respostas: RespostasCaso, item_id: str | None
) -> bool:
    """Tem resposta gravada? `NAO_SEI` conta como respondida — `RF-11`: "não
    sei" é resposta de primeira classe, e escondê-la da revisão faria o aluno
    procurar uma pergunta que ele já resolveu."""
    variavel = registro.VARIAVEL_GRAVADA
    if variavel is None:  # pragma: no cover — defensivo
        return False
    if item_id is not None:
        return respostas.valor_no_item(item_id, variavel) is not None
    return respostas.valor(variavel) is not None


def _serializar_resposta_dada(
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    item_id: str | None,
    rotulo_do_item: str | None = None,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
    rotulos_dos_itens: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Uma linha da revisão: a pergunta **e o que o aluno respondeu**.

    O `rotulo_do_valor` é o texto que ele escolheu, não o `valor_interno`:
    quem respondeu "Empréstimo consignado" precisa reler "Empréstimo
    consignado", nunca `CONSIGNADO`. `montar_contexto_pergunta` já resolve
    essa tradução para a tela de pergunta — reusá-la aqui é o que garante que
    a revisão e a coleta digam a mesma coisa sobre a mesma resposta.

    `None` quando a condição da pergunta fechou depois da resposta (`T-198`,
    `EC-24`): a resposta continua gravada, mas deixa de ser listada — a mesma
    disciplina de `_campos_da_ficha`."""
    try:
        contexto = montar_contexto_pergunta(
            registro,
            respostas,
            item_id=item_id,
            rotulo_do_item=rotulo_do_item,
            itens_por_escopo=itens_por_escopo,
            rotulos=rotulos_dos_itens,
        )
    except ErroPerguntaNaoExibivel:
        return None

    rotulos = [
        opcao.rotulo
        for opcao in contexto.opcoes
        if opcao.valor_interno is not None
        and opcao.valor_interno in contexto.valores_marcados
    ]
    if contexto.valor_atual == frozenset():
        rotulos = [_NENHUM_ITEM_MARCADO]
    elif not rotulos and contexto.valor_atual not in (None, ""):
        bruto = serializar_valor(contexto.valor_atual)
        escolhida = next(
            (o.rotulo for o in contexto.opcoes if o.valor_interno == bruto), None
        )
        rotulos = [escolhida if escolhida is not None else str(bruto)]
    if campo := _valor_do_campo(registro, contexto.valor_atual, respostas, item_id):
        rotulos = [campo]

    return {
        "ID": registro.ID,
        "item_id": item_id,
        "enunciado": contexto.enunciado,
        "respondida_como_nao_sei": contexto.respondida_como_nao_sei,
        # `T-335`: o tipo diz ao cliente como EXIBIR o valor cru (`0.08` é
        # "8%", `2276.76` é "R$ 2.276,76"); a regra continua no servidor.
        "tipo": registro.tipo.value,
        # Lista, não string: `SELECAO_MULTIPLA` tem várias, e juntá-las aqui
        # imporia um separador que é decisão de apresentação.
        "valores": rotulos,
    }


def _valor_do_campo(
    registro: RegistroPergunta,
    valor_atual: ValorResposta | None,
    respostas: RespostasCaso,
    item_id: str | None,
) -> str | None:
    """`T-303`: opção que abre campo (`abre_campo`) — a revisão mostra o
    rótulo E o valor digitado ("Sim. — R$ 8.000,00"). `DATA` (`T-213`) grava
    a data na própria variável; `MOEDA` (`T-294`), em `variavel_do_campo`."""
    for opcao in registro.opcoes:
        if opcao.abre_campo is TipoResposta.DATA and isinstance(valor_atual, date):
            return f"{opcao.rotulo} — {valor_atual:%d/%m/%Y}"
        if opcao.variavel_do_campo and opcao.valor_interno == valor_atual:
            digitado = (
                respostas.valor_no_item(item_id, opcao.variavel_do_campo)
                if item_id
                else respostas.valor(opcao.variavel_do_campo)
            )
            if isinstance(digitado, Decimal):
                return f"{opcao.rotulo} — {formatar_dinheiro_br(digitado)}"
    return None


@roteador.get("/{CASO_ID}/respostas")
def respostas_do_caso(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas)
    ],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """`RF-68`, `AC-100` — o que o aluno já respondeu, por parte.

    **`AC-101`: parte sem resposta aparece assim mesmo**, com a lista vazia e
    o total de perguntas. Sumir da tela faria o aluno procurar onde ela foi
    parar; aparecer vazia sem explicação sugeriria erro.

    Perguntas repetíveis rendem **uma linha por item** — a ficha da dívida
    `D001` e a da `D002` são respostas diferentes à mesma pergunta, e juntá-las
    esconderia qual valor é de qual dívida."""
    # Duas consultas independentes em paralelo — `T-191`.
    respostas_brutas, (itens_por_escopo, rotulos) = duas_em_paralelo(
        lambda: repositorio_respostas.listar_do_caso(CASO_ID),
        lambda: _itens_e_rotulos(repositorio_itens, CASO_ID, colecao),
    )
    respostas = RespostasCaso(respostas=respostas_brutas)

    partes: list[dict[str, Any]] = []
    for numero, rotulo, blocos in PARTES:
        do_bloco = [r for blc in blocos for r in colecao.registros if r.bloco == blc]
        linhas: list[dict[str, Any]] = []
        # `T-297`: o total conta na mesma unidade das respondidas — uma
        # pergunta de ficha vale uma vez por item cadastrado.
        total = sum(
            1
            if r.escopo_repeticao == EscopoRepeticao.NENHUM
            else len(itens_por_escopo.get(r.escopo_repeticao, ()))
            for r in do_bloco
        )

        for registro in do_bloco:
            if registro.escopo_repeticao != EscopoRepeticao.NENHUM:
                for item_id in itens_por_escopo.get(registro.escopo_repeticao, ()):
                    if _respondida(registro, respostas, item_id) and (
                        linha := _serializar_resposta_dada(
                            registro,
                            respostas,
                            item_id,
                            rotulos.get(item_id),
                            itens_por_escopo,
                            rotulos,
                        )
                    ):
                        linhas.append(linha)
                continue
            if _respondida(registro, respostas, None) and (
                linha := _serializar_resposta_dada(registro, respostas, None)
            ):
                linhas.append(linha)

        partes.append(
            {
                "bloco": numero,
                "rotulo": rotulo,
                "total_de_perguntas": total,
                "respondidas": linhas,
            }
        )

    # `RF-114`/`RF-115` (T-336): o cliente não conhece estados — recebe o
    # veredito. Em cálculo ou conferência as respostas só se leem; só a
    # conferência permite retirar o plano para editar.
    caso = repositorio_casos.buscar(CASO_ID)
    estado = caso.estado if caso is not None else None
    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "editavel": estado not in ESTADOS_SOMENTE_LEITURA,
            "pode_retomar_edicao": estado is ESTADO_CASO.AGUARDANDO_REVISAO,
            # `RF-118` (T-341): depois da liberação o aluno pode pedir plano novo.
            "pode_refazer_plano": estado in ESTADOS_COM_PLANO_LIBERADO,
            "partes": partes,
        }
    )


def obter_repositorio_eventos_da_retomada() -> RepositorioEventosCaso:
    """Ponto de injeção da trilha de eventos — sobrescrito nos testes."""
    return RepositorioEventosCasoSupabase()


_MENSAGEM_NAO_EM_CONFERENCIA: Final[str] = "Seu plano não está em conferência."

#: `RF-118`: de onde o aluno pode pedir um plano novo. `COLETA_DIRIGIDA` e
#: `CONFIRMACAO_ATAQUE` são etapas do próprio fluxo e ficam de fora.
ESTADOS_COM_PLANO_LIBERADO: Final[frozenset[ESTADO_CASO]] = frozenset(
    {ESTADO_CASO.PLANO_LIBERADO, ESTADO_CASO.ACOMPANHAMENTO}
)
_MENSAGEM_AINDA_NAO_LIBERADO: Final[str] = "Seu plano ainda não foi liberado."


@roteador.post("/{CASO_ID}/retomar-edicao")
def retomar_edicao(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos_da_retomada)
    ],
) -> JSONResponse:
    """`RF-115`, `AC-177`, `AC-179` — o aluno retira o plano da conferência
    para editar as respostas.

    `AGUARDANDO_REVISAO → COLETA_INICIAL` pela MÁQUINA e pela trava
    condicional de `RF-31` (`transicionar_e_registrar`): se o revisor decidiu
    um instante antes, a transição não se aplica e a resposta é `409` — quem
    chega primeiro vence (`EC-42`). O snapshot não é tocado e as respostas
    ficam como estão; o reenvio é o cálculo de sempre, que gera a nova versão
    encadeada à anterior. Fora de `AGUARDANDO_REVISAO` (em `CALCULANDO`, por
    exemplo) a rota recusa sem mexer em nada."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None or caso.estado is not ESTADO_CASO.AGUARDANDO_REVISAO:
        return JSONResponse({"erro": _MENSAGEM_NAO_EM_CONFERENCIA}, status_code=409)
    try:
        atualizado = transicionar_e_registrar(
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            caso_id=CASO_ID,
            de=ESTADO_CASO.AGUARDANDO_REVISAO,
            para=ESTADO_CASO.COLETA_INICIAL,
        )
    except ErroTransicaoNaoDeclarada:  # pragma: no cover — a tabela a declara
        return JSONResponse({"erro": _MENSAGEM_NAO_EM_CONFERENCIA}, status_code=409)
    if atualizado is None:
        return JSONResponse({"erro": _MENSAGEM_NAO_EM_CONFERENCIA}, status_code=409)
    return JSONResponse({"CASO_ID": CASO_ID, "estado": ESTADO_CASO.COLETA_INICIAL.value})


@roteador.post("/{CASO_ID}/refazer-plano")
def refazer_plano(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos_da_retomada)
    ],
) -> JSONResponse:
    """`RF-118`, `AC-181`, `AC-182` — o aluno pede um plano novo depois da
    liberação.

    `PLANO_LIBERADO`/`ACOMPANHAMENTO → COLETA_INICIAL` pela MÁQUINA e pela
    trava condicional de `RF-31` (`transicionar_e_registrar`). Não toca no plano
    liberado (`snapshot_liberado_id`) nem na cadeia de snapshots: o aluno segue
    vendo o plano atual, e o reenvio (o cálculo de sempre) gera a versão
    seguinte encadeada à anterior e a põe na fila. Só o aluno pede — o revisor
    devolve com mensagem (`RF-113`), nunca reabre o plano. Fora desses dois
    estados a rota recusa sem mexer em nada."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None or caso.estado not in ESTADOS_COM_PLANO_LIBERADO:
        return JSONResponse({"erro": _MENSAGEM_AINDA_NAO_LIBERADO}, status_code=409)
    try:
        atualizado = transicionar_e_registrar(
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            caso_id=CASO_ID,
            de=caso.estado,
            para=ESTADO_CASO.COLETA_INICIAL,
        )
    except ErroTransicaoNaoDeclarada:  # pragma: no cover — a tabela as declara
        return JSONResponse({"erro": _MENSAGEM_AINDA_NAO_LIBERADO}, status_code=409)
    if atualizado is None:
        return JSONResponse({"erro": _MENSAGEM_AINDA_NAO_LIBERADO}, status_code=409)
    return JSONResponse({"CASO_ID": CASO_ID, "estado": ESTADO_CASO.COLETA_INICIAL.value})
