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
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.concorrencia import duas_em_paralelo
from app.http.isolamento import exigir_caso_da_sessao
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import (
    _itens_e_rotulos,
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.serializacao import serializar_valor
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import RespostasCaso
from persistencia.app_aluno.itens import RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

REGRAS: Final[tuple[str, ...]] = ("RF-68", "RF-10", "AC-100", "AC-101")

roteador = APIRouter(prefix="/caso", tags=["respostas"])

# As cinco partes da Etapa B, na linguagem do aluno — os mesmos rótulos do
# protótipo validado (linhas 278–282) e da tela "Meu progresso". Aqui eles
# ficam no SERVIDOR porque é ele que conhece o número do bloco de cada
# registro; o cliente recebe a parte já nomeada e não precisa saber que
# "Bloco 3" existe.
#
# `T-297`: o Bloco 9 (`B9.02`, `B9.04`) também é coleta inicial, e a spec só
# prevê cinco partes (`RF-68`). Ele entra em "Seu compromisso" — as duas
# perguntas são sobre perseverar no plano — depois do Bloco 1.
_PARTES: Final[tuple[tuple[int, str, tuple[int, ...]], ...]] = (
    (1, "Seu compromisso", (1, 9)),
    (2, "Como você controla os gastos", (2,)),
    (3, "O que entra e o que sai por mês", (3,)),
    (4, "Salário, margem e o que você tem", (4,)),
    (5, "Suas dívidas, uma por uma", (5,)),
)

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

    return {
        "ID": registro.ID,
        "item_id": item_id,
        "enunciado": contexto.enunciado,
        "respondida_como_nao_sei": contexto.respondida_como_nao_sei,
        # Lista, não string: `SELECAO_MULTIPLA` tem várias, e juntá-las aqui
        # imporia um separador que é decisão de apresentação.
        "valores": rotulos,
    }


@roteador.get("/{CASO_ID}/respostas")
def respostas_do_caso(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas)
    ],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
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
    for numero, rotulo, blocos in _PARTES:
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

    return JSONResponse({"CASO_ID": CASO_ID, "partes": partes})
