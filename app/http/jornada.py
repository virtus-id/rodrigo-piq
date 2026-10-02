"""A pergunta anterior, a seguinte e a trilha da coleta — `RF-70` (`T-309`,
`T-318`) e `RF-100` (`T-310`).

Os dois leem o MESMO percurso de `progresso.py::percurso_da_coleta` — a
varredura da retomada —, nunca a ordem dos registros: a ficha é percorrida
item a item (`T-202`) e o Bloco 9 vem depois do Bloco 5, e era a ordem dos
registros, agrupada por parte, que fazia "‹ Pergunta anterior" saltar
perguntas (`T-309`).

REGRAS: `RF-68`, `RF-70`, `RF-100`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from app.casos.progresso import PendenciaObrigatoria, percurso_da_coleta
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import RespostasCaso

REGRAS: Final[tuple[str, ...]] = ("RF-68", "RF-70", "RF-100")

# As cinco partes da Etapa B, na linguagem do aluno — os mesmos rótulos do
# protótipo validado (linhas 278–282) e da tela "Meu progresso". Ficam no
# SERVIDOR porque é ele que conhece o bloco de cada registro.
#
# `T-297`: o Bloco 9 (`B9.02`, `B9.04`) também é coleta inicial, e a spec só
# prevê cinco partes (`RF-68`). Ele entra em "Seu compromisso" — as duas
# perguntas são sobre perseverar no plano — depois do Bloco 1.
PARTES: Final[tuple[tuple[int, str, tuple[int, ...]], ...]] = (
    (1, "Seu compromisso", (1, 9)),
    (2, "Como você controla os gastos", (2,)),
    (3, "O que entra e o que sai por mês", (3,)),
    (4, "Salário, margem e o que você tem", (4,)),
    (5, "Suas dívidas, uma por uma", (5,)),
)

_PARTE_DO_BLOCO: Final[dict[int, int]] = {
    bloco: numero for numero, _, blocos in PARTES for bloco in blocos
}

Percurso = tuple[tuple[PendenciaObrigatoria, bool], ...]


def anterior_no_percurso(
    percurso: Percurso, ID: str, item_id: str | None
) -> dict[str, str | None] | None:
    """`RF-70`, `AC-105` — a última pergunta RESPONDIDA antes desta no
    percurso. `None` quando não há (primeira pergunta) ou quando a pergunta
    não está no percurso (fora da coleta inicial)."""
    chaves = [(ocorrencia.ID, ocorrencia.item_id) for ocorrencia, _ in percurso]
    if (ID, item_id) not in chaves:
        return None
    antes = percurso[: chaves.index((ID, item_id))]
    return next(
        (
            {"ID": ocorrencia.ID, "item_id": ocorrencia.item_id}
            for ocorrencia, em_branco in reversed(antes)
            if not em_branco
        ),
        None,
    )


def seguinte_no_percurso(
    percurso: Percurso, ID: str, item_id: str | None
) -> dict[str, str | None] | None:
    """`RF-70`, `T-318` — a pergunta imediatamente depois desta no percurso,
    para quem voltou com "‹ Pergunta anterior" e quer avançar sem responder
    de novo. Só quando ESTA já está respondida: na fronteira (em branco) o
    aluno precisa responder, e não há "seguinte". A seguinte pode estar em
    branco — é a próxima a responder naquele trecho, onde o "Continuar"
    também o levaria. `None` também na última e fora da coleta inicial."""
    chaves = [(ocorrencia.ID, ocorrencia.item_id) for ocorrencia, _ in percurso]
    if (ID, item_id) not in chaves:
        return None
    posicao = chaves.index((ID, item_id))
    if percurso[posicao][1] or posicao + 1 == len(percurso):
        return None
    seguinte = percurso[posicao + 1][0]
    return {"ID": seguinte.ID, "item_id": seguinte.item_id}


def trilha_da_coleta(
    registros: tuple[RegistroPergunta, ...], percurso: Percurso, bloco_atual: int
) -> list[dict[str, object]] | None:
    """`RF-100` — as cinco partes com o estado de cada uma: `atual` (a da
    tela), `concluida` ou `proxima`. `None` fora das cinco partes.

    **Por partes, nunca por perguntas** (`T-293`): o total de perguntas
    cresce a cada ficha criada, e uma barra sobre ele pareceria regredir.

    Concluída = começa ANTES da frente da coleta (a primeira em branco do
    percurso) e não é a parte da frente: tudo dela antes da frente está
    respondido por definição. É o que mantém "Seu compromisso" concluída
    enquanto o Bloco 9, que vem no fim do percurso, ainda espera."""
    atual = _PARTE_DO_BLOCO.get(bloco_atual)
    if atual is None:
        return None
    bloco_por_id = {registro.ID: registro.bloco for registro in registros}
    partes = [_PARTE_DO_BLOCO.get(bloco_por_id.get(o.ID, 0)) for o, _ in percurso]
    frente = next((i for i, (_, em_branco) in enumerate(percurso) if em_branco), len(percurso))
    parte_da_frente = partes[frente] if frente < len(partes) else None

    def estado(numero: int) -> str:
        if numero == atual:
            return "atual"
        inicio = next((i for i, parte in enumerate(partes) if parte == numero), None)
        if inicio is not None and inicio < frente and numero != parte_da_frente:
            return "concluida"
        return "proxima"

    return [
        {"numero": numero, "rotulo": rotulo, "estado": estado(numero)}
        for numero, rotulo, _ in PARTES
    ]


def anexar_ao_payload(
    pergunta: dict[str, object],
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> None:
    """`anterior`, `seguinte` e `trilha` na pergunta serializada — uma varredura para os
    dois. Quem chama são as duas montagens da pergunta da coleta (`GET
    /pergunta` e `proxima` do `POST`), nunca as filhas de `T-307`."""
    percurso = percurso_da_coleta(registros, respostas, itens_por_escopo)
    item_id = pergunta.get("item_id")
    chave = (str(pergunta["ID"]), item_id if isinstance(item_id, str) else None)
    pergunta["anterior"] = anterior_no_percurso(percurso, *chave)
    # `T-318`: a seguinte, para avançar depois de voltar.
    pergunta["seguinte"] = seguinte_no_percurso(percurso, *chave)
    bloco = pergunta.get("bloco")
    pergunta["trilha"] = (
        trilha_da_coleta(registros, percurso, bloco) if isinstance(bloco, int) else None
    )


def parte_da_pergunta(registros: tuple[RegistroPergunta, ...], ID: str) -> str | None:
    """`RF-100`, `T-331` — "Parte N de 5 · rótulo" da pergunta `ID`, para o
    Painel de usuários (`RF-112`) dizer em que parte da coleta o aluno está.
    `None` quando a pergunta não pertence às cinco partes."""
    bloco = next((registro.bloco for registro in registros if registro.ID == ID), None)
    numero = _PARTE_DO_BLOCO.get(bloco) if bloco is not None else None
    if numero is None:
        return None
    return f"Parte {numero} de {len(PARTES)} · {PARTES[numero - 1][1]}"
