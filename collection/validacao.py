"""Validação cruzada entre campos, dentro do mesmo item — `RF-07` (`AC-06`,
`EC-02`).

`plans/app-aluno.plan.md` §4.1. `ValidacaoCruzada` declara, no YAML, um
comparador genérico entre duas variáveis do mesmo item de `escopo`
(`variavel_esquerda operador variavel_direita`) e a `mensagem` a exibir em
caso de falha — a redação vem do registro, nunca deste módulo (`AC-37`). O
caso normativo é `VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`, por
`MARGEM_ID` (§15.1, canônica linha 5167).

`validar_cruzada` é o comparador genérico: os cinco operadores (`<=`, `>=`,
`<`, `>`, `==`) passam por um único ponto de aplicação (`_OPERADORES`, mapa
operador→função de `operator`). Não existe `if operador == "<=": ...`
repetido em lugar nenhum deste módulo. A comparação ocorre estritamente
dentro do `item_id` recebido — variáveis de itens diferentes do mesmo escopo
nunca se comparam, porque o único acesso a valor é `respostas.valor_no_item`
com aquele `item_id` fixo.

NENHUM `ID` de pergunta e NENHUMA redação de erro ao usuário são literais
aqui — auditado por `AC-37`
(`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`).
A mensagem exibida ao aluno é sempre `ValidacaoCruzada.mensagem`, dado do
registro.

REGRAS: `RF-07`, `AC-06`, `EC-02`
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Protocol

if TYPE_CHECKING:
    # Import só de tipo — mesmo motivo de `collection/condicoes.py`: evitar
    # ciclo real na carga do interpretador com `collection/registro.py`.
    from collection.registro import EscopoRepeticao

REGRAS: Final[tuple[str, ...]] = ("RF-07", "AC-06", "EC-02")

# Valor de resposta comparado por `validar_cruzada` — mesmo desenho de
# `collection/condicoes.py::ValorResposta` e
# `collection/interpolacao.py::ValorResposta`: este módulo compara, nunca
# interpreta o domínio de uma pergunta específica.
type ValorResposta = object


class Respostas(Protocol):
    """Fonte de respostas consultada por `validar_cruzada`, restrita a UM
    item do escopo — a chave real de uma variável `REP` é
    `(CASO_ID, ID_PERGUNTA, item_id)` (plano §4.3). `collection/respostas.py`
    (T-22) é quem implementa este contrato sobre a persistência real; este
    módulo só o consome (mesmo padrão de `collection/condicoes.py::Respostas`
    e `collection/interpolacao.py::Respostas`)."""

    def valor_no_item(self, item_id: str, variavel: str) -> ValorResposta | None:
        """Valor de `variavel` gravado para o item `item_id`. `None`
        (ausência) é "ainda não respondida" — `validar_cruzada` nunca compara
        contra um valor de outro item."""
        ...


# Único ponto de aplicação dos cinco operadores — mapa operador→função do
# módulo padrão `operator`. Um só caminho de código para os cinco: nenhum
# `if`/`elif` repetido por operador em lugar nenhum deste módulo. `Any` aqui
# reflete o próprio contrato de `operator.le/ge/lt/gt` (exigem um par que
# suporte os dunders de comparação, não qualquer `object`) — quem garante que
# os dois valores do item são comparáveis entre si é o registro YAML, nunca
# este módulo.
_OPERADORES: Final[dict[str, Callable[[Any, Any], bool]]] = {
    "<=": lambda a, b: operator.le(a, b),
    ">=": lambda a, b: operator.ge(a, b),
    "<": lambda a, b: operator.lt(a, b),
    ">": lambda a, b: operator.gt(a, b),
    "==": lambda a, b: operator.eq(a, b),
}


@dataclass(frozen=True, slots=True)
class ValidacaoCruzada:
    """RF-07 — comparador genérico entre duas variáveis do mesmo item de
    `escopo`, declarado no YAML. Caso normativo: `VALOR_UTILIZADO_MARGEM <=
    VALOR_TOTAL_MARGEM`, por `MARGEM_ID`."""

    variavel_esquerda: str
    operador: str  # um de "<=", ">=", "<", ">", "==" — ver `_OPERADORES`
    variavel_direita: str
    escopo: EscopoRepeticao  # compara DENTRO do mesmo item deste escopo
    mensagem: str  # redação ao usuário, do registro — nunca deste módulo


@dataclass(frozen=True, slots=True)
class ResultadoValidacao:
    """Resultado de `validar_cruzada`. `valida=True` não carrega os campos de
    falha. `valida=False` nomeia OS DOIS campos envolvidos
    (`variavel_esquerda`/`variavel_direita`) e traz `mensagem`, sempre a do
    registro — nunca uma redação composta neste módulo (`EC-02`)."""

    valida: bool
    variavel_esquerda: str | None = None
    variavel_direita: str | None = None
    mensagem: str | None = None


def _erro_operador_desconhecido(operador_recebido: str) -> ValueError:
    # Mensagem TÉCNICA interna (nunca exibida ao aluno) — curta, dentro do
    # limiar de `AC-37`/`T-08` (strings acima de 40 caracteres fora de
    # docstring são auditadas).
    return ValueError(f"operador desconhecido: {operador_recebido!r}")


def validar_cruzada(
    validacao: ValidacaoCruzada, item_id: str, respostas: Respostas
) -> ResultadoValidacao:
    """RF-07 — aplica `validacao` estritamente dentro de `item_id`: os dois
    valores comparados vêm sempre do mesmo item, nunca de itens diferentes do
    escopo. Variável ainda não respondida em `item_id` é tratada como válida
    (nada para comparar ainda) — a obrigatoriedade da resposta é assunto de
    `Obrigatoriedade`, não deste comparador.

    EC-02: quando a comparação falha, o `ResultadoValidacao` nomeia os dois
    campos e carrega `validacao.mensagem` — a redação ao usuário é sempre a
    do registro, nunca composta aqui."""
    aplicar = _OPERADORES.get(validacao.operador)
    if aplicar is None:
        raise _erro_operador_desconhecido(validacao.operador)

    valor_esquerdo = respostas.valor_no_item(item_id, validacao.variavel_esquerda)
    valor_direito = respostas.valor_no_item(item_id, validacao.variavel_direita)
    if valor_esquerdo is None or valor_direito is None:
        return ResultadoValidacao(valida=True)

    if aplicar(valor_esquerdo, valor_direito):
        return ResultadoValidacao(valida=True)

    return ResultadoValidacao(
        valida=False,
        variavel_esquerda=validacao.variavel_esquerda,
        variavel_direita=validacao.variavel_direita,
        mensagem=validacao.mensagem,
    )
