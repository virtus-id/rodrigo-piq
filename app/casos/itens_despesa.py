"""Ficha de despesa por item marcado — `T-217` (`RF-04`, `RF-05`, `RF-52`).

A §11 da spec, `B3.D01`–`B3.D11`: "Cada item marcado → abre B3.DF01–DF04";
"Outro → texto curto OPT"; e em `B3.D11`, "Sim → ficha REP: nome (texto
curto) + B3.DF01–DF04". Todas essas fichas são o MESMO escopo,
`ITEM_DESPESA` — é por isso que `app/montagem/estado.py::
_despesas_operacionais_atuais` soma `VALOR_DESPESA` de todos os itens sem
saber de qual categoria cada um veio.

**O item sabe de onde nasceu.** `ItemRepetido.origem` (migração `006`) é
`"<ID da pergunta>:<valor_interno>"` — `B3.D01:ALUGUEL` — ou `B3.D11`. É o
que permite, ao regravar o checklist, saber qual ficha é de qual opção:
marcar cria a ficha, desmarcar a remove (`RepositorioItens.remover`, lógico:
a linha fica, e as respostas do item deixam de ser lidas).

**Sem limite de itens.** Nada aqui conta nem corta: uma ficha por opção
marcada, e a despesa não listada ganha quantas o aluno adicionar.

Este módulo só DECIDE (`sincronizar`); quem grava é a rota
(`app/http/rotas_coleta.py`). Nenhuma regra de cálculo aqui.

REGRAS: `RF-04`, `RF-05`, `RF-52`
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import ValorResposta
from persistencia.app_aluno.itens import ItemRepetido

REGRAS: Final[tuple[str, ...]] = ("RF-04", "RF-05", "RF-52")

#: Os checklists de despesa, `B3.D01`–`B3.D10` (§11).
CHECKLISTS_DE_DESPESA: Final[frozenset[str]] = frozenset(f"B3.D{n:02d}" for n in range(1, 11))
#: "Existe alguma despesa mensal relevante que ainda não apareceu?" — a origem
#: das fichas que o aluno cria pela lista.
DESPESA_NAO_LISTADA: Final[str] = "B3.D11"

_OUTRO: Final[str] = "OUTRO"
_SIM: Final[str] = "SIM"


@dataclass(frozen=True, slots=True)
class Sincronizacao:
    """O que a resposta pede: as ORIGENS dos itens a criar e os `item_id`
    a remover."""

    criar: tuple[str, ...] = ()
    remover: tuple[str, ...] = ()


def _pergunta_de(item: ItemRepetido) -> str | None:
    return item.origem.partition(":")[0] if item.origem else None


def _opcao_de(item: ItemRepetido) -> str:
    return item.origem.partition(":")[2] if item.origem else ""


def sincronizar(
    registro: RegistroPergunta, valor: ValorResposta, itens_ativos: Iterable[ItemRepetido]
) -> Sincronizacao:
    """As fichas `ITEM_DESPESA` que a resposta a `registro` cria e remove.

    Checklist: uma ficha por opção marcada, na ordem das opções; a ficha de
    opção desmarcada sai. `B3.D11`: "Sim" abre uma ficha quando ainda não há
    nenhuma (as demais o aluno adiciona pela lista); qualquer outra resposta
    remove as que havia. Outra pergunta: nada."""
    da_pergunta = [
        item
        for item in itens_ativos
        if item.escopo is EscopoRepeticao.ITEM_DESPESA and _pergunta_de(item) == registro.ID
    ]
    if registro.ID == DESPESA_NAO_LISTADA:
        if valor == _SIM:
            return Sincronizacao(criar=() if da_pergunta else (DESPESA_NAO_LISTADA,))
        return Sincronizacao(remover=tuple(item.item_id for item in da_pergunta))
    if registro.ID not in CHECKLISTS_DE_DESPESA:
        return Sincronizacao()

    marcadas = valor if isinstance(valor, frozenset) else frozenset()
    existentes = {_opcao_de(item) for item in da_pergunta}
    return Sincronizacao(
        criar=tuple(
            f"{registro.ID}:{opcao.valor_interno}"
            for opcao in registro.opcoes
            if opcao.valor_interno in marcadas and opcao.valor_interno not in existentes
        ),
        remover=tuple(item.item_id for item in da_pergunta if _opcao_de(item) not in marcadas),
    )


def pede_nome(origem: str | None) -> bool:
    """"Outro" e a despesa não listada pedem um nome curto ao aluno."""
    return origem is not None and (
        origem == DESPESA_NAO_LISTADA or origem.endswith(f":{_OUTRO}")
    )


def rotulo_do_item(
    item: ItemRepetido, registros_por_id: Mapping[str, RegistroPergunta]
) -> str | None:
    """O nome do item para o aluno: o que ele digitou, senão o rótulo da
    opção marcada ("Aluguel"). `None` sem nenhum dos dois — a tela cai no
    identificador."""
    if item.nome:
        return item.nome
    registro = registros_por_id.get(_pergunta_de(item) or "")
    if registro is None:
        return None
    valor = _opcao_de(item)
    return next((o.rotulo for o in registro.opcoes if o.valor_interno == valor), None)


def rotulos_dos_itens(
    itens: Iterable[ItemRepetido], registros: tuple[RegistroPergunta, ...]
) -> dict[str, str]:
    """`item_id` → rótulo, só dos itens que têm um."""
    por_id = {registro.ID: registro for registro in registros}
    rotulos: dict[str, str] = {}
    for item in itens:
        rotulo = rotulo_do_item(item, por_id)
        if rotulo is not None:
            rotulos[item.item_id] = rotulo
    return rotulos
