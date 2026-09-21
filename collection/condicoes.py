"""Árvore declarativa de condição de exibição — o núcleo de `RF-05`.

`plans/app-aluno.plan.md` §4.1. Os seis nós fecham o domínio de `Condicao`:
`CondicaoIgual`, `CondicaoContem`, `CondicaoExisteItem`, `CondicaoE`,
`CondicaoOu`, `CondicaoNao`. `CondicaoIgual`/`CondicaoContem` referenciam a
variável **por nome** (`VARIAVEL_GRAVADA`), nunca por bloco: é isso que faz a
condicional composta ENTRE blocos ser o caso comum, não uma exceção — `B12.08`
é literalmente um `CondicaoOu` de quatro termos declarado no YAML, sem nenhuma
linha de código específica dela (`AC-21`).

`avaliar` é o interpretador genérico da árvore (`T-11`): percorre os nós e
devolve booleano. Não existe `if pergunta.ID == "..."` em lugar nenhum deste
módulo — a especificidade mora inteira no YAML de `collection/registros/`.

NENHUM `ID` de pergunta é literal aqui — auditado por `AC-37`
(`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`).

REGRAS: `RF-05`, `AC-21`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, assert_never

if TYPE_CHECKING:
    # Import só de tipo: `registro.py` importa `Condicao` deste módulo em
    # tempo de execução (T-10), e um import direto de `EscopoRepeticao` aqui
    # criaria um ciclo real na carga do interpretador. `EscopoRepeticao` só
    # é usado como anotação neste arquivo — nunca instanciado nem comparado
    # em runtime — então `from __future__ import annotations` já garante que
    # o nome nunca precisa existir fora da checagem de tipo.
    from collection.registro import EscopoRepeticao

REGRAS: Final[tuple[str, ...]] = ("RF-05", "AC-21")

# Valor de resposta aceito pelo interpretador. `avaliar` compara por
# igualdade/pertencimento — nunca por identidade de tipo específico de
# pergunta. Uma resposta "não sei" (`NaoSei`/`NAO_SEI`, T-22) nunca é igual a
# uma `str` concreta nem pertence a um `frozenset[str]`, o que já garante que
# ela não satisfaz `CondicaoIgual`/`CondicaoContem`/`CondicaoExisteItem` sem
# nenhum tratamento especial neste módulo.
type ValorResposta = object


class Respostas(Protocol):
    """Fonte de respostas consultada por `avaliar` — a chave primária real de
    uma resposta é `(CASO_ID, ID_PERGUNTA, item_id)` (plano §4.3): uma
    variável `REP` (`escopo_repeticao != NENHUM`) tem um valor POR ITEM, não
    um único valor de caso. `Protocol` em vez de `Mapping` porque
    `CondicaoExisteItem` precisa varrer todos os itens de um escopo, o que um
    `dict` de variável→valor não expressa. `collection/respostas.py` (T-22) é
    quem implementa este contrato sobre a persistência real; este módulo só
    o consome."""

    def valor(self, variavel: str) -> ValorResposta | None:
        """Valor corrente de uma variável não repetida (`escopo_repeticao ==
        NENHUM`). `None` (ausência) é "ainda não respondida"."""
        ...

    def valores_do_escopo(
        self, escopo: EscopoRepeticao, variavel: str
    ) -> tuple[ValorResposta, ...]:
        """Os valores de `variavel` gravados em cada item de `escopo` (um por
        `item_id`) — usado por `CondicaoExisteItem`. Escopo sem nenhum item
        cadastrado devolve tupla vazia, nunca erro."""
        ...


@dataclass(frozen=True, slots=True)
class CondicaoIgual:
    """Verdadeira quando a resposta gravada em `variavel` é exatamente
    `valor`. `variavel` é um nome de `VARIAVEL_GRAVADA` — de QUALQUER bloco,
    nunca um campo de bloco específico."""

    variavel: str
    valor: str


@dataclass(frozen=True, slots=True)
class CondicaoContem:
    """Verdadeira quando `valor` está entre as respostas marcadas em
    `variavel` — caso de checklist múltipla (ex. `MECANISMO_DEFICIT`)."""

    variavel: str
    valor: str


@dataclass(frozen=True, slots=True)
class CondicaoExisteItem:
    """Verdadeira quando existe, entre os itens do `escopo` (ex. uma ficha de
    dívida repetida), algum cujo `variavel` tenha sido gravada com um valor em
    `valor_em` — caso de "existe dívida de cartão no Bloco 5"."""

    escopo: EscopoRepeticao
    variavel: str
    valor_em: frozenset[str]


@dataclass(frozen=True, slots=True)
class CondicaoE:
    """Verdadeira quando TODOS os `termos` são verdadeiros."""

    termos: tuple[Condicao, ...]


@dataclass(frozen=True, slots=True)
class CondicaoOu:
    """Verdadeira quando QUALQUER um dos `termos` é verdadeiro — `B12.08` é
    um `CondicaoOu` de quatro termos, sem código específico dela."""

    termos: tuple[Condicao, ...]


@dataclass(frozen=True, slots=True)
class CondicaoNao:
    """Negação de `termo`."""

    termo: Condicao


type Condicao = (
    CondicaoIgual | CondicaoContem | CondicaoExisteItem | CondicaoE | CondicaoOu | CondicaoNao
)


def avaliar(condicao: Condicao, respostas: Respostas) -> bool:
    """RF-05 — interpretador genérico da árvore de `Condicao`. Percorre os
    nós e devolve booleano; variável ausente de `respostas` avalia como
    falso, sem levantar exceção (caso comum de "ainda não respondida").
    Resposta `NAO_SEI` nunca satisfaz `CondicaoIgual`/`CondicaoContem` de um
    valor concreto: ela não é igual a nenhuma `str` nem pertence a nenhum
    `frozenset[str]`, então a comparação por `==`/`in` já resolve isso sem
    nenhum tratamento específico."""
    match condicao:
        case CondicaoIgual(variavel=variavel, valor=valor):
            return respostas.valor(variavel) == valor
        case CondicaoContem(variavel=variavel, valor=valor):
            marcados = respostas.valor(variavel)
            return isinstance(marcados, frozenset) and valor in marcados
        case CondicaoExisteItem(escopo=escopo, variavel=variavel, valor_em=valor_em):
            valores_dos_itens = respostas.valores_do_escopo(escopo, variavel)
            return any(
                isinstance(valor_do_item, str) and valor_do_item in valor_em
                for valor_do_item in valores_dos_itens
            )
        case CondicaoE(termos=termos):
            return all(avaliar(termo, respostas) for termo in termos)
        case CondicaoOu(termos=termos):
            return any(avaliar(termo, respostas) for termo in termos)
        case CondicaoNao(termo=termo):
            return not avaliar(termo, respostas)
        case _:
            assert_never(condicao)
