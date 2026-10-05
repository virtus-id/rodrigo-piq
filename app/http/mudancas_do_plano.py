"""O que mudou nos dados de entrada entre duas versões do plano — `RF-123`,
`AC-192` (T-345).

O revisor de um plano refeito (v2 ou mais) precisa saber **o que o aluno
mudou** — renda, despesas, taxas, parcelas — sem comparar à mão duas listas
de cinquenta campos. A comparação é entre os `ContextoEstadoInputs` das duas
versões (`report.plano.montar_contexto_estado_inputs`): cada campo já chega
com o rótulo e o valor FORMATADOS pelo servidor, e é por esses valores que se
compara. Nenhuma conta, nenhuma formatação nova (Lei nº 3, `AC-08`).

Campo igual não aparece. Campo que só existe de um lado — um campo novo no
motor, uma dívida cadastrada ou removida — aparece como "novo" ou "removido",
nunca como erro: duas versões do cálculo podem não ter exatamente os mesmos
campos.

REGRAS: `RF-123`, `AC-192`
"""

from __future__ import annotations

from typing import Any, Final

from report.plano import ContextoCampo, ContextoEstadoInputs

#: As três situações de uma mudança — o cliente só as exibe.
ALTERADO: Final[str] = "alterado"
NOVO: Final[str] = "novo"
REMOVIDO: Final[str] = "removido"

_SECAO_DADOS: Final[str] = "Dados gerais"
_SECAO_PERFIL: Final[str] = "Como lida com os gastos"
_SECAO_SINAIS: Final[str] = "Sinais de comportamento"


def _mudanca(
    secao: str, nome: str, de: str | None, para: str | None, situacao: str
) -> dict[str, Any]:
    return {"secao": secao, "nome": nome, "de": de, "para": para, "situacao": situacao}


def _por_codigo(campos: tuple[ContextoCampo, ...]) -> dict[str, ContextoCampo]:
    return {campo.codigo: campo for campo in campos}


def _comparar(
    secao: str,
    atual: tuple[ContextoCampo, ...],
    anterior: tuple[ContextoCampo, ...],
) -> list[dict[str, Any]]:
    """Campos de uma seção, na ordem em que o plano atual os apresenta; os que só
    existiam antes vêm depois, como "removidos"."""
    antes = _por_codigo(anterior)
    agora = _por_codigo(atual)
    mudancas: list[dict[str, Any]] = []
    for codigo, campo in agora.items():
        if codigo not in antes:
            mudancas.append(_mudanca(secao, campo.nome, None, campo.valor, NOVO))
        elif antes[codigo].valor != campo.valor:
            mudancas.append(_mudanca(secao, campo.nome, antes[codigo].valor, campo.valor, ALTERADO))
    for codigo, campo in antes.items():
        if codigo not in agora:
            mudancas.append(_mudanca(secao, campo.nome, campo.valor, None, REMOVIDO))
    return mudancas


def mudancas_entre(
    atual: ContextoEstadoInputs, anterior: ContextoEstadoInputs
) -> list[dict[str, Any]]:
    """Todas as mudanças de `anterior` para `atual`; lista vazia = nada mudou."""
    mudancas = [
        *_comparar(_SECAO_DADOS, atual.campos, anterior.campos),
        *_comparar(_SECAO_PERFIL, atual.perfil_comportamental, anterior.perfil_comportamental),
        *_comparar(_SECAO_SINAIS, atual.sinais_comportamentais, anterior.sinais_comportamentais),
    ]
    dividas_antes = {divida.DIVIDA_ID: divida for divida in anterior.dividas}
    dividas_agora = {divida.DIVIDA_ID: divida for divida in atual.dividas}
    for divida_id, divida in dividas_agora.items():
        if divida_id not in dividas_antes:
            mudancas.append(_mudanca(divida.nome, "Dívida", None, divida.nome, NOVO))
        else:
            mudancas.extend(_comparar(divida.nome, divida.campos, dividas_antes[divida_id].campos))
    for divida_id, divida in dividas_antes.items():
        if divida_id not in dividas_agora:
            mudancas.append(_mudanca(divida.nome, "Dívida", divida.nome, None, REMOVIDO))
    return mudancas
