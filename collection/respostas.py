"""Resposta do aluno como dado de primeira classe — `RF-10`, `RF-11`, `RF-13`
(`AC-02`, `EC-05`, `EC-10`).

`plans/app-aluno.plan.md` §4.2. `NaoSei`/`NAO_SEI` espelha o desenho de
`engine.tipos.Desconhecido`/`DESCONHECIDO` (mesmo padrão: `Enum` de um único
membro, nunca instanciado fora da constante) — mas são conceitos DISTINTOS:
`Desconhecido` é do motor (`engine/`), `NaoSei` é da camada de coleta
(`collection/`). A tradução de um para o outro é trabalho de `app/montagem/`
(RF-12), fora desta tarefa — este módulo nunca importa de `engine.tipos`.

`NAO_SEI` é resposta de PRIMEIRA CLASSE: distinguível de "não respondido"
(ausência da linha em `app_aluno.respostas`) e de qualquer valor concreto.
`None` significa exclusivamente "não perguntado" — NUNCA "não sei". Por isso
`ValorResposta` não inclui `None` no tipo-soma: uma pergunta sem resposta é a
ausência de um `Resposta`, não um `Resposta` com `valor=None`.

`ValorResposta` NUNCA admite `float` (`RF-13`): o único caminho numérico é
`Decimal`, que trafega como `numeric` no Postgres — precisão exata do
formulário até a coluna, sem passar por ponto flutuante binário em nenhum
ponto da fronteira.

Este módulo também oferece `RespostasCaso`, a implementação REAL dos três
`Protocol` locais que `collection/condicoes.py`, `collection/interpolacao.py`
e `collection/validacao.py` já declaram como placeholder (documentados como
"T-22 é quem implementa este contrato sobre a persistência real"):
`valor(variavel)`, `valor_no_item(item_id, variavel)` e
`valores_do_escopo(escopo, variavel)`. `RespostasCaso` é construída a partir
de um snapshot em memória das respostas de um caso (produzido pelo adaptador
de persistência) — ela não fala com o banco a cada chamada.

REGRAS: `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-05`, `EC-10`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collection.registro import EscopoRepeticao

REGRAS: Final[tuple[str, ...]] = ("RF-10", "RF-11", "RF-13", "AC-02", "EC-05", "EC-10")


class NaoSei(Enum):
    """RF-11 — "não sei" é resposta de PRIMEIRA CLASSE, distinguível de "não
    respondido" (ausência da linha) e de qualquer valor. Espelha
    `engine.tipos.Desconhecido` sem importá-lo para dentro da coleta: a
    tradução para `DESCONHECIDO` acontece só em `app/montagem/` (RF-12,
    trabalho de tarefa futura, não desta)."""

    NAO_SEI = "NAO_SEI"


NAO_SEI: Final = NaoSei.NAO_SEI

# NUNCA float. NUNCA None para "não sei" — None significaria "não perguntado".
type ValorResposta = str | int | Decimal | date | frozenset[str] | NaoSei


@dataclass(frozen=True, slots=True)
class Resposta:
    """Uma resposta gravada, chave primária real `(CASO_ID, ID_PERGUNTA,
    item_id)` — `item_id` é `None` para pergunta não repetível (a
    persistência grava `''` na coluna, ver `persistencia/app_aluno/
    respostas.py`; aqui, em memória, `None` é mais honesto sobre "não há
    item"). `respondida_em` é auditoria (quando a resposta chegou), nunca
    entrada do motor."""

    CASO_ID: str
    ID_PERGUNTA: str
    item_id: str | None  # DIVIDA_ID/VINCULO_ID/MARGEM_ID/... quando REP
    valor: ValorResposta
    QUESTIONARIO_VERSION: str
    respondida_em: datetime  # auditoria, não entrada do motor


@dataclass(frozen=True, slots=True)
class RespostasCaso:
    """Implementação real dos três `Protocol` locais consumidos por
    `collection/condicoes.py::Respostas`, `collection/interpolacao.py::
    Respostas` e `collection/validacao.py::Respostas` — construída sobre um
    snapshot em memória de todas as `Resposta` de um caso, entregue por
    `persistencia/app_aluno/respostas.py::RepositorioRespostas.listar_do_caso`.

    O índice por `(ID_PERGUNTA, item_id)` é recomputado a cada chamada a
    partir de `self.respostas` — sem cache mutável dentro do dataclass
    `frozen` (nenhum `object.__setattr__` por fora do construtor). O volume
    de respostas de um caso (no máximo 291) torna isso irrelevante em
    desempenho; simplicidade e imutabilidade real do dataclass pesam mais.

    Perguntas não repetíveis usam `item_id=""` como chave interna (mesma
    convenção da coluna `item_id` da migração `002_app_aluno.sql`, que nunca
    é `NULL` para poder compor a chave primária por igualdade simples)."""

    respostas: tuple[Resposta, ...]

    def _indice(self) -> dict[tuple[str, str], ValorResposta]:
        return {(r.ID_PERGUNTA, r.item_id or ""): r.valor for r in self.respostas}

    def valor(self, variavel: str) -> ValorResposta | None:
        """Valor corrente de uma variável não repetida. `None` (ausência) é
        "ainda não respondida"."""
        return self._indice().get((variavel, ""))

    def valor_no_item(self, item_id: str, variavel: str) -> ValorResposta | None:
        """Valor de `variavel` gravado para o item `item_id`. `None`
        (ausência) é "ainda não respondida" naquele item."""
        return self._indice().get((variavel, item_id))

    def valores_do_escopo(
        self, escopo: EscopoRepeticao, variavel: str
    ) -> tuple[ValorResposta, ...]:
        """Os valores de `variavel` gravados em cada item de `escopo` (um por
        `item_id`) — usado por `CondicaoExisteItem`. `escopo` não é usado
        para filtrar aqui: a filtragem por escopo já ocorreu na formação de
        `self.respostas` pelo chamador (o item_id por si é a unidade), mas o
        parâmetro é mantido para satisfazer o `Protocol` de
        `collection/condicoes.py`. Escopo sem nenhum item respondido devolve
        tupla vazia, nunca erro."""
        return tuple(
            valor
            for (nome_variavel, item_id), valor in self._indice().items()
            if nome_variavel == variavel and item_id != ""
        )
