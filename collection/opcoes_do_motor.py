"""Opções de resposta produzidas pelo motor — `RF-08` (`AC-20`, `AC-42`).

`plans/app-aluno.plan.md` §4.1. `OrigemOpcoes` declara, por pergunta, de onde
vêm as opções apresentadas ao aluno: do próprio registro (`REGISTRO`, o caso
comum das 291 perguntas) ou do `SnapshotOrdem` que o motor já produziu para o
caso (`SNAPSHOT`, ex.: as regras propostas de `B12.16`).

`opcoes_efetivas` é a função que resolve a origem: com `fonte=REGISTRO`,
devolve exatamente `registro.opcoes`, sem tocar no snapshot. Com
`fonte=SNAPSHOT`, as opções são as que o motor produziu para aquele caso —
nenhuma opção fixa em código aparece fora dessa lista (`AC-20`); sem snapshot
disponível, a lista é vazia e a pergunta não é exibível, nunca uma opção
inventada.

A trava normativa de `campo_do_snapshot` é `AC-42`: o acesso é sempre uma
LEITURA de um campo de `SnapshotOrdem` por nome (`getattr`, caminho pontilhado
— mesmo mecanismo de `collection/interpolacao.py::_resolver_campo_do_snapshot`
— nunca por índice numérico nem por expressão), jamais um recálculo: nenhuma
soma, subtração ou comparação numérica é aplicada ao campo.

`B12.15`/`B12.16` são casos de prova do gerador (spec §9, `OQ-12`): este
módulo prova que o contrato de `OrigemOpcoes`/`opcoes_efetivas` cabe para
eles, mas sua coleta efetiva (o Bloco 12 como fluxo) está fora de escopo.

REGRAS: `RF-08`, `AC-20`, `AC-42`
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from engine.snapshot import SnapshotOrdem

if TYPE_CHECKING:
    # Import só de tipo — mesmo motivo de `collection/condicoes.py`:
    # `registro.py` importa `OrigemOpcoes` deste módulo em tempo de execução
    # (T-09), e um import direto de `OpcaoRegistro`/`RegistroPergunta` aqui
    # criaria um ciclo real na carga do interpretador.
    from collection.registro import EscopoRepeticao, OpcaoRegistro, RegistroPergunta
    from collection.respostas import RespostasCaso

REGRAS: Final[tuple[str, ...]] = ("RF-08", "AC-20", "AC-42")


@dataclass(frozen=True, slots=True)
class OrigemOpcoes:
    """RF-08 — de onde vêm as opções de resposta de uma pergunta.
    `fonte=REGISTRO` é o caso comum: as opções são as do próprio
    `RegistroPergunta.opcoes`. `fonte=SNAPSHOT` é o caso do motor: as opções
    nascem de um campo de `SnapshotOrdem` (ex.: as regras propostas para
    `B12.16`), nunca de uma lista fixa em código."""

    fonte: Literal["REGISTRO", "SNAPSHOT", "ITENS_DO_ESCOPO"]
    campo_do_snapshot: str | None
    # Só é lido quando `fonte == "SNAPSHOT"`: caminho de campo separado por
    # pontos (mesma convenção de `Marcador.referencia` em
    # `collection/interpolacao.py`), navegado por `getattr` — nunca por
    # índice nem por expressão. `None` quando `fonte == "REGISTRO"`.
    # `T-256` (RF-90): com `fonte == "ITENS_DO_ESCOPO"`, as opções são os
    # itens ativos de `escopo` no caso — o vínculo em que a dívida é
    # descontada. Rótulo: o nome do item, senão a resposta a
    # `variavel_rotulo` naquele item, senão o próprio identificador.
    escopo: EscopoRepeticao | None = None
    variavel_rotulo: str | None = None


def _ler_campo_do_snapshot(snapshot: SnapshotOrdem, campo: str) -> object:
    """AC-42 — LEITURA de um campo de `SnapshotOrdem` por nome, nunca
    recálculo: o único acesso é `getattr` percorrendo o caminho pontilhado,
    sem nenhuma soma, subtração ou comparação numérica sobre o valor."""
    valor: object = snapshot
    for nome_do_passo in campo.split("."):
        if not hasattr(valor, nome_do_passo):
            return None
        valor = getattr(valor, nome_do_passo)
    return valor


def opcoes_efetivas(
    registro: RegistroPergunta,
    snapshot: SnapshotOrdem | None,
    *,
    respostas: RespostasCaso | None = None,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
    rotulos: Mapping[str, str] | None = None,
) -> tuple[OpcaoRegistro, ...]:
    """RF-08 — resolve as opções efetivas de `registro` a partir de sua
    `origem_opcoes`.

    `fonte=REGISTRO`: devolve `registro.opcoes` sem tocar em `snapshot`.

    `fonte=SNAPSHOT`: devolve exatamente as opções lidas do campo nomeado em
    `campo_do_snapshot` (`AC-42`). Sem snapshot disponível, ou com o campo
    ausente, ou com um valor que não seja uma coleção de opções, devolve
    tupla vazia — nunca uma opção fixa em código (`AC-20`); a pergunta não é
    exibível nesse caso, e cabe a quem consome esta função tratar a lista
    vazia como "não exibir", nunca substituí-la por um padrão.

    `fonte=ITENS_DO_ESCOPO` (`T-256`): os itens ativos do caso — ver
    `_opcoes_dos_itens`."""
    origem = registro.origem_opcoes
    if origem.fonte == "REGISTRO":
        return registro.opcoes
    if origem.fonte == "ITENS_DO_ESCOPO":
        return _opcoes_dos_itens(origem, respostas, itens_por_escopo or {}, rotulos or {})

    # fonte == "SNAPSHOT"
    if snapshot is None or origem.campo_do_snapshot is None:
        return ()

    valor = _ler_campo_do_snapshot(snapshot, origem.campo_do_snapshot)
    if isinstance(valor, tuple) and all(_e_opcao_registro(item) for item in valor):
        return valor
    return ()


def sem_itens_para_escolher(
    registro: RegistroPergunta, itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]]
) -> bool:
    """`T-282` (`DE-04`) — pergunta cujas opções são itens do caso
    (`ITENS_DO_ESCOPO`) sem nenhum item ativo no escopo: não há o que
    escolher, então ela não é exibida nem fica em aberto — a falta vira
    pendência de inventário (`app/casos/inventario.py`), que só bloqueia o
    cálculo final."""
    origem = registro.origem_opcoes
    return (
        origem.fonte == "ITENS_DO_ESCOPO"
        and origem.escopo is not None
        and not itens_por_escopo.get(origem.escopo)
    )


def _opcoes_dos_itens(
    origem: OrigemOpcoes,
    respostas: RespostasCaso | None,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    rotulos: Mapping[str, str],
) -> tuple[OpcaoRegistro, ...]:
    """`T-256` (RF-90) — uma opção por item ATIVO de `origem.escopo`, na
    ordem de criação. `itens_por_escopo` é o do caso de quem pergunta: item
    de outro caso nunca chega aqui. Sem item, tupla vazia — nunca uma opção
    inventada (`AC-20`)."""
    from collection.registro import OpcaoRegistro

    if origem.escopo is None:
        return ()

    def rotulo(item_id: str) -> str:
        if item_id in rotulos:
            return rotulos[item_id]
        if respostas is not None and origem.variavel_rotulo is not None:
            valor = respostas.valor_no_item(item_id, origem.variavel_rotulo)
            if isinstance(valor, str) and valor.strip():
                return valor
        return item_id

    return tuple(
        OpcaoRegistro(rotulo=rotulo(item_id), valor_interno=item_id)
        for item_id in itens_por_escopo.get(origem.escopo, ())
    )


def _e_opcao_registro(item: object) -> bool:
    """Confirma, por atributo, que `item` tem a forma de uma `OpcaoRegistro`
    — sem importar o tipo em tempo de execução (evita o ciclo com
    `collection/registro.py`) e sem nenhuma aritmética sobre o valor."""
    return hasattr(item, "rotulo") and hasattr(item, "valor_interno")
