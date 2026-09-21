"""Serialização explícita de `ContextoPergunta` para JSON — `RF-51`, `RF-52`
(T-133).

**Por que um serializador escrito à mão, e não `dataclasses.asdict`.** O
`asdict` até percorre a estrutura, mas o resultado **não** passa por
`json.dumps`: `TipoResposta` é `Enum`, `valores_marcados` é `frozenset`, e
`valor_atual` pode ser `Decimal`, `date`, `frozenset` ou o sentinela
`NAO_SEI`. Verificado: `Object of type TipoResposta is not JSON
serializable`.

**E há uma razão melhor do que a técnica.** Um `asdict` cego despejaria o
`RegistroPergunta` inteiro no cliente — incluindo `condicao_exibicao`,
`validacoes_cruzadas` e `obrigatoriedade`. Seria exatamente a duplicação do
grafo condicional que `RF-52` proíbe e que `AC-73` audita. Escolher campo a
campo é a trava: o que não é escrito aqui não atravessa a fronteira.

**O que o cliente recebe, e só:** o que ele precisa para DESENHAR a tela —
enunciado já interpolado, opções já resolvidas, o tipo do campo (para
escolher o widget e a máscara), o valor atual (para reabrir preenchido) e o
aviso de materialidade. Nada que permita decidir SE a pergunta aparece: essa
decisão já foi tomada no servidor, e o cliente recebe o resultado, nunca a
regra.

REGRAS: `RF-51`, `RF-52`, `RF-45`
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Final

from app.http.renderizacao import ContextoPergunta
from collection.registro import OpcaoRegistro
from collection.respostas import NAO_SEI, ValorResposta

REGRAS: Final[tuple[str, ...]] = ("RF-51", "RF-52", "RF-45")

# O sentinela de "não sei" vira uma string canônica no JSON — nunca `null`
# (que significaria "não respondida") e nunca `0`. É a mesma distinção que
# `RF-11`/`RF-12` exigem no servidor, preservada na fronteira HTTP.
VALOR_NAO_SEI: Final[str] = "NAO_SEI"


def serializar_valor(valor: ValorResposta | None) -> Any:
    """O valor já respondido, em forma transportável.

    `Decimal` vira **string**, nunca `float`: `RF-13` proíbe que valor
    monetário atravesse ponto flutuante, e `JSON.parse` no navegador
    transformaria um número em `double` silenciosamente. O cliente recebe
    `"1234.56"` e o exibe formatado; quem interpreta continua sendo
    `app/montagem/conversao.py`, no servidor.
    """
    if valor is None:
        return None
    if valor is NAO_SEI:
        return VALOR_NAO_SEI
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, frozenset):
        return sorted(valor)
    if isinstance(valor, bool | int | str):
        return valor
    return str(valor)  # pragma: no cover — defensivo


def serializar_opcao(opcao: OpcaoRegistro) -> dict[str, Any]:
    """`rotulo` e `valor_interno` vão como estão — traduzir qualquer um dos
    dois é proibido (`collection/registro.py::OpcaoRegistro`)."""
    return {
        "rotulo": opcao.rotulo,
        "valor_interno": opcao.valor_interno,
        "admite_nao_sei": opcao.admite_nao_sei,
    }


def serializar_pergunta(
    contexto: ContextoPergunta,
    *,
    CASO_ID: str,
    item_id: str | None = None,
    posicao: int | None = None,
    total_na_ficha: int | None = None,
) -> dict[str, Any]:
    """`ContextoPergunta` → dicionário JSON.

    Campo a campo, deliberadamente. `condicao_exibicao`,
    `validacoes_cruzadas`, `obrigatoriedade` e `interpolacoes` do registro
    **não** entram: são a regra, e a regra fica no servidor (`RF-52`).

    `VARIAVEL_GRAVADA` também não entra (T-144). É o nome interno do campo
    em que a resposta é gravada — vocabulário do modelo de dados, sem uso
    nenhum no cliente, que identifica a pergunta por `ID`. O POST de
    resposta manda `ID_PERGUNTA` e é o SERVIDOR que resolve para qual
    variável aquilo vai (`rotas_coleta.py`); mandar o nome ao navegador só
    daria a impressão de que ele pode escolher.

    **`posicao`/`total_na_ficha` — `RF-63`, `AC-92` (T-148).** O localizador
    do protótipo diz *"Dívida 3 · pergunta 4 de 12"*, e até aqui o payload
    não tinha como sustentar essa frase. A contagem é do **servidor**: é ele
    que conhece o conjunto de perguntas exibíveis da ficha (`RF-45`). O
    cliente recebe dois inteiros e compõe o texto — se ele contasse, estaria
    contando um conjunto que não conhece, e `RF-05` atravessaria a fronteira.

    Os dois vêm `None` fora de ficha repetível, e aí o localizador cai no
    rótulo do bloco. `None` é o caso honesto: não existe "pergunta 4 de 12"
    numa pergunta que não pertence a ficha nenhuma. `OQ-30` registrou essa
    decisão e foi respondida em 2026-09-17.
    """
    registro = contexto.registro
    return {
        "CASO_ID": CASO_ID,
        "ID": registro.ID,
        "bloco": registro.bloco,
        "tipo": registro.tipo.value,
        "enunciado": contexto.enunciado,
        "opcoes": [serializar_opcao(opcao) for opcao in contexto.opcoes],
        "escopo_repeticao": registro.escopo_repeticao.value,
        "item_id": item_id,
        "posicao": posicao,
        "total_na_ficha": total_na_ficha,
        "admite_nao_sei": registro.admite_nao_sei,
        "valor_atual": serializar_valor(contexto.valor_atual),
        "respondida_como_nao_sei": contexto.respondida_como_nao_sei,
        "valores_marcados": sorted(contexto.valores_marcados),
        "aviso": contexto.aviso.texto if contexto.aviso is not None else None,
    }
