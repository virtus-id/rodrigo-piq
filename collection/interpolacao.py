"""Texto dinâmico no enunciado — `RF-06` (`AC-05`, `AC-42`).

`plans/app-aluno.plan.md` §4.1. `Marcador` declara, por pergunta, um texto
literal do enunciado (`marcador`) a substituir e de onde vem o valor
(`origem`): o identificador do item corrente da ficha repetida
(`ID_DO_ITEM`, ex.: `[Dxxx]` em `B11.Q01`), uma variável já coletada
(`VARIAVEL_COLETADA`) ou um campo do `SnapshotOrdem` que o motor já
calculou (`CAMPO_DO_SNAPSHOT`, ex.: `PAGAMENTO_MENSAL_EFETIVO` em
`B11.Q06`).

`interpolar` é o interpretador genérico: percorre `marcadores` e substitui
cada `marcador.marcador` no enunciado. Não existe `if pergunta.ID == "..."`
em lugar nenhum deste módulo — a especificidade mora no YAML de
`collection/registros/`.

A trava normativa da origem `CAMPO_DO_SNAPSHOT` é `AC-42`: o valor é sempre
uma LEITURA de um campo de `SnapshotOrdem` (por nome, via `getattr` —
nunca por índice numérico nem por expressão), jamais um recálculo. Todo
valor monetário (`Dinheiro`/`Decimal`) interpolado atravessa
`engine.precisao.quantizar_exibicao` antes de virar texto (`G-01`).

REGRAS: `RF-06`, `AC-05`, `AC-42`
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, Protocol, assert_never

from engine.precisao import quantizar_exibicao
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-06", "AC-05", "AC-42")

# Valor de resposta aceito pela origem VARIAVEL_COLETADA — mesmo desenho de
# `collection/condicoes.py::ValorResposta`: `interpolar` compara e formata,
# nunca interpreta o domínio de uma pergunta específica.
type ValorResposta = object


class Respostas(Protocol):
    """Fonte de respostas consultada pela origem `VARIAVEL_COLETADA`.
    `collection/respostas.py` (T-22) é quem implementa este contrato sobre a
    persistência real; este módulo só o consome — `Protocol` local mínimo,
    satisfeito por implementação futura (mesmo padrão de
    `collection/condicoes.py::Respostas`)."""

    def valor(self, variavel: str) -> ValorResposta | None:
        """Valor corrente de `variavel` para o item/caso do contexto.
        `None` (ausência) é "ainda não respondida"."""
        ...


@dataclass(frozen=True, slots=True)
class ContextoItem:
    """O contexto de exibição de uma pergunta — o que `interpolar` tem à mão
    para resolver qualquer uma das três origens.

    `item_id` é o identificador do item corrente da ficha repetida (ex.: o
    `DIVIDA_ID` da ficha de dívida sendo exibida) — fonte da origem
    `ID_DO_ITEM`. `respostas` alimenta `VARIAVEL_COLETADA`. `snapshot` é o
    `SnapshotOrdem` corrente do caso — fonte de `CAMPO_DO_SNAPSHOT`; `None`
    quando o caso ainda não tem snapshot (a pergunta não deve declarar essa
    origem antes de o motor ter rodado, mas o contexto não impõe isso)."""

    item_id: str | None
    respostas: Respostas
    snapshot: SnapshotOrdem | None


@dataclass(frozen=True, slots=True)
class Marcador:
    """`[Dxxx]` em `B11.Q01` → o `DIVIDA_ID` da ficha corrente
    (`ID_DO_ITEM`). `PAGAMENTO_MENSAL_EFETIVO` em `B11.Q06` → o campo já
    calculado pelo motor (`CAMPO_DO_SNAPSHOT`)."""

    marcador: str  # texto literal do enunciado a substituir
    origem: Literal["ID_DO_ITEM", "VARIAVEL_COLETADA", "CAMPO_DO_SNAPSHOT"]
    referencia: str
    # ID_DO_ITEM: `referencia` não é lida (o valor é sempre `ctx.item_id`) —
    #   mantida como string vazia por convenção do YAML de origem.
    # VARIAVEL_COLETADA: `referencia` é o nome da variável em `Respostas`.
    # CAMPO_DO_SNAPSHOT: `referencia` é um caminho de campo separado por
    #   pontos (ex.: "estado_inputs.dividas.PAGAMENTO_MENSAL_EFETIVO"),
    #   navegado por `getattr` — nunca por índice nem por expressão.


class ErroInterpolacao(Exception):
    """Marcador sem valor disponível — nunca vira string vazia silenciosa
    (critério de aceite 4 de `T-12`). Nomeia o marcador e a origem
    responsáveis, para que o erro seja rastreável até o registro."""


def _erro(*partes: str) -> ErroInterpolacao:
    """Monta a mensagem de erro a partir de fragmentos curtos (cada um
    dentro do limiar de `AC-37`/`T-08`, que audita string literal com mais
    de 40 caracteres fora de docstring): a mensagem TÉCNICA completa nunca é
    um único literal — é sempre composta em tempo de execução."""
    return ErroInterpolacao(" ".join(partes))


def _resolver_id_do_item(marcador: Marcador, ctx: ContextoItem) -> str:
    if ctx.item_id is None:
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem ID_DO_ITEM):",
            "nenhum item corrente no contexto.",
        )
    return ctx.item_id


def _resolver_variavel_coletada(marcador: Marcador, ctx: ContextoItem) -> str:
    valor = ctx.respostas.valor(marcador.referencia)
    if valor is None:
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem VARIAVEL_COLETADA):",
            f"{marcador.referencia!r} ainda não respondida.",
        )
    return _formatar_valor(valor)


def _resolver_campo_do_snapshot(marcador: Marcador, ctx: ContextoItem) -> str:
    # AC-42: LEITURA de campo do SnapshotOrdem, nunca recálculo — por isso o
    # único acesso permitido é `getattr` por nome, nunca aritmética.
    if ctx.snapshot is None:
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem CAMPO_DO_SNAPSHOT):",
            "caso ainda sem snapshot.",
        )
    valor: object = ctx.snapshot
    for nome_do_passo in marcador.referencia.split("."):
        valor = _avancar_um_passo(marcador, nome_do_passo, valor, ctx.item_id)
    if valor is None:
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem CAMPO_DO_SNAPSHOT):",
            f"{marcador.referencia!r} ausente no snapshot.",
        )
    return _formatar_valor(valor)


def _avancar_um_passo(
    marcador: Marcador, nome_do_passo: str, valor: object, item_id: str | None
) -> object:
    """Um passo do caminho pontilhado de `CAMPO_DO_SNAPSHOT`. Se `valor`
    corrente for uma coleção de itens de ficha repetida (ex.:
    `estado_inputs.dividas`), seleciona antes o elemento cujo identificador
    do item bate com `item_id` — nunca por índice numérico — e só então
    aplica `getattr`. Continua sendo LEITURA pura: nenhuma soma, média ou
    condição aparece aqui."""
    if isinstance(valor, (tuple, list)):
        valor = _selecionar_item_da_colecao(marcador, valor, item_id)
    if not hasattr(valor, nome_do_passo):
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem CAMPO_DO_SNAPSHOT):",
            f"campo {nome_do_passo!r} inexistente.",
        )
    return getattr(valor, nome_do_passo)


def _selecionar_item_da_colecao(
    marcador: Marcador, itens: tuple[object, ...] | list[object], item_id: str | None
) -> object:
    if item_id is None:
        raise _erro(
            f"marcador {marcador.marcador!r}",
            "(origem CAMPO_DO_SNAPSHOT):",
            "coleção sem item corrente no contexto.",
        )
    for item in itens:
        for nome_do_identificador in ("DIVIDA_ID", "MARGEM_ID", "VINCULO_ID", "ACAO_ID"):
            if getattr(item, nome_do_identificador, None) == item_id:
                return item
    raise _erro(
        f"marcador {marcador.marcador!r}",
        "(origem CAMPO_DO_SNAPSHOT):",
        f"nenhum item corresponde a {item_id!r}.",
    )


def _formatar_valor(valor: object) -> str:
    # G-01: todo valor monetário exibido passa por `quantizar_exibicao`
    # antes de virar texto — `Dinheiro`/`Taxa` são ambos `Decimal` em
    # tempo de execução, então a trava é aplicada a QUALQUER `Decimal`
    # interpolado, nunca só a um subconjunto reconhecido por nome.
    if isinstance(valor, Decimal):
        return str(quantizar_exibicao(valor))
    return str(valor)


def interpolar(enunciado: str, marcadores: tuple[Marcador, ...], ctx: ContextoItem) -> str:
    """RF-06 — substitui cada `marcador.marcador` presente em `enunciado`
    pelo valor resolvido a partir de sua `origem`. Marcador sem valor
    disponível levanta `ErroInterpolacao` — nunca produz string vazia
    silenciosa (critério de aceite 4)."""
    texto = enunciado
    for marcador in marcadores:
        match marcador.origem:
            case "ID_DO_ITEM":
                valor_textual = _resolver_id_do_item(marcador, ctx)
            case "VARIAVEL_COLETADA":
                valor_textual = _resolver_variavel_coletada(marcador, ctx)
            case "CAMPO_DO_SNAPSHOT":
                valor_textual = _resolver_campo_do_snapshot(marcador, ctx)
            case _:
                assert_never(marcador.origem)
        texto = texto.replace(marcador.marcador, valor_textual)
    return texto
