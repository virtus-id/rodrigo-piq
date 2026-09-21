"""Cenário de substituição equivalente da troca — RF-11 · `T-01`/`T-02` ·
`GAB-05`.

`T-01`/`T-02` (nomenclatura da spec, `specs/motor-calculo.spec.md` RF-11):
quando uma dívida antiga é trocada/portada por uma nova operação de crédito
com `DINHEIRO_NOVO > 0` (valor adicional além do necessário para quitar a
dívida antiga — "dinheiro na mão"), o `CENARIO_SUBSTITUICAO_EQUIVALENTE` é
calculado **apenas** sobre a parcela que substitui/quita a dívida antiga —
nunca sobre o valor total da nova operação. O `DINHEIRO_NOVO` é tratado como
endividamento adicional puro, e NUNCA reduz ou compensa o custo comparado do
cenário equivalente (jamais entra como "economia" ou "vantagem" da troca).

**Por que a separação existe.** Comparar o valor total da nova operação
(ex.: R$ 40.000) contra o saldo da dívida antiga (ex.: R$ 30.000) sempre
pareceria "pior" numericamente — mais dívida contratada é sempre mais custo
bruto — mas isso mascararia a pergunta que a troca de fato coloca: a
condição da NOVA operação (taxa, prazo) é vantajosa em relação à condição da
dívida ANTIGA, só na parte que troca uma pela outra? Por isso o valor
substituído (a "parte que troca") é isolado do dinheiro novo (a "parte que
endivida a mais") antes de qualquer comparação.

**Abordagem.** Reaproveita o motor de simulação já existente
(`engine/ciclo_mensal.py::simular_cenario`) em vez de inventar uma segunda
fórmula de evolução de saldo: a parcela substituída é modelada como uma
`Divida` sintética isolada — mesmo saldo que a dívida antiga tinha
(`VALOR_SUBSTITUIDO`), mas com as condições (taxa, pagamento) da NOVA
operação — e simulada isoladamente do resto da carteira, exatamente como
`engine/trajetoria.py` já isola uma dívida por vez (`RF-05`). O resultado é
um `Cenario` — mesma estrutura devolvida por `simular_cenario` para qualquer
outro método —, o que o torna comparável mês a mês (`Cenario.meses`, uma
tupla de `ResultadoMes`) contra o cenário SEM troca (a dívida antiga, também
isolada e simulada da mesma forma). O `DINHEIRO_NOVO`, quando > 0, é
simulado à parte, como uma segunda `Divida` sintética independente — nunca
somado, subtraído nem misturado ao cenário equivalente: os dois `Cenario`s
resultantes (`cenario_equivalente` e `cenario_dinheiro_novo`) são devolvidos
separados, exatamente para que nenhum caminho consumidor tenha a chance de
tratar o dinheiro novo como parte do custo comparado da troca.

REGRAS: RF-11, T-01, T-02
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import localcontext
from typing import Final

from engine.ciclo_mensal import Cenario, SelecionarAlvo, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import TIPO_DIVIDA, Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import (
    DESCONHECIDO,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    Dinheiro,
    SimNaoTalvez,
    Taxa,
)

REGRAS: Final[tuple[str, ...]] = ("RF-11", "T-01", "T-02")

_SUFIXO_EQUIVALENTE = "-SUBSTITUIDA"
_SUFIXO_DINHEIRO_NOVO = "-DINHEIRO-NOVO"


class ErroDinheiroNovoNegativo(Exception):
    """`T-01`: `DINHEIRO_NOVO` é sempre >= 0 por definição — é o excedente
    da nova operação sobre o valor efetivamente substituído. Um saldo de
    nova operação menor que o valor substituído é dado inconsistente
    (a operação não cobriria nem a quitação da dívida antiga), não um caso
    de "dinheiro novo negativo" a tolerar silenciosamente."""


@dataclass(frozen=True, slots=True)
class OperacaoTroca:
    """Entrada de `calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE` — os dados da
    nova operação de crédito que substitui/porta a dívida antiga.

    `VALOR_SUBSTITUIDO` é a parte da nova operação que efetivamente quita a
    dívida antiga — normalmente igual ao `SALDO_DEVEDOR_ATUAL` dela no
    momento da troca, mas modelado como campo explícito (em vez de lido
    direto da dívida antiga) porque a spec não garante que os dois sempre
    coincidam (ex.: quitação com desconto). `SALDO_NOVA_OPERACAO` é o valor
    total contratado — pode ser maior que `VALOR_SUBSTITUIDO`, e a diferença
    é o `DINHEIRO_NOVO` (`T-01`).

    `TAXA_EFETIVA_MENSAL_NORMALIZADA`/`PAGAMENTO_MENSAL_EFETIVO` são as
    condições da NOVA operação — aplicadas tanto à parcela substituída
    quanto ao dinheiro novo, já que ambos vêm do mesmo contrato e têm a
    mesma taxa; o pagamento mensal de cada componente é proporcional ao seu
    saldo dentro da operação (ver `_dividir_pagamento_proporcional`).
    """

    SALDO_NOVA_OPERACAO: Dinheiro
    VALOR_SUBSTITUIDO: Dinheiro
    TAXA_EFETIVA_MENSAL_NORMALIZADA: Taxa
    PAGAMENTO_MENSAL_EFETIVO: Dinheiro


@dataclass(frozen=True, slots=True)
class ResultadoSubstituicaoEquivalente:
    """Saída de `calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE`.

    `cenario_equivalente` (`CENARIO_SUBSTITUICAO_EQUIVALENTE`, `T-01`) cobre
    SÓ o `VALOR_SUBSTITUIDO` — é o único campo comparável ao cenário sem
    troca (`Cenario.meses`, mês a mês, mesma granularidade de `ResultadoMes`
    que qualquer outro cenário do motor).

    `cenario_dinheiro_novo` é `None` quando `DINHEIRO_NOVO == 0` (troca sem
    dinheiro na mão — nada a isolar). Quando presente, é o cenário do
    excedente simulado ISOLADO — nunca somado, subtraído nem incorporado ao
    `cenario_equivalente` (`T-02`): existe apenas para que o endividamento
    adicional seja visível e auditável, nunca para "compensar" o custo da
    troca em si.
    """

    DINHEIRO_NOVO: Dinheiro
    cenario_equivalente: Cenario
    cenario_dinheiro_novo: Cenario | None


def _dividir_pagamento_proporcional(
    pagamento_total: Dinheiro, parte: Dinheiro, saldo_total: Dinheiro
) -> Dinheiro:
    """Rateia `PAGAMENTO_MENSAL_EFETIVO` da nova operação entre seus dois
    componentes (parcela substituída / dinheiro novo), proporcionalmente ao
    saldo de cada um dentro do saldo total contratado — mesma taxa e mesmo
    contrato, então o pagamento mensal de cada fatia acompanha seu peso no
    saldo. `saldo_total == 0` não ocorre em uso normal (validado antes pelo
    chamador); devolve `pagamento_total` inteiro nesse caso-limite defensivo,
    em vez de dividir por zero.
    """
    if saldo_total == dinheiro(0):
        return pagamento_total
    with localcontext(CONTEXTO_MOTOR):
        return pagamento_total * parte / saldo_total


def _divida_sintetica(divida_id: str, saldo: Dinheiro, operacao: OperacaoTroca) -> Divida:
    """Constrói a `Divida` sintética de UM componente da nova operação
    (parcela substituída OU dinheiro novo), isolada do resto da carteira —
    mesmo padrão de isolamento de `engine/trajetoria.py::
    simular_trajetoria_isolada` (`RF-05`), reaproveitado aqui em vez de
    inventar uma segunda forma de evolução de saldo.

    Campos neutros (sem efeito em `simular_cenario`/`executar_mes` para uma
    única dívida isolada): `PESO_EMOCIONAL`, `RENEGOCIACAO_PENDENTE`,
    `TROCA_PENDENTE`, `RISCO_MATERIAL_IMINENTE`, `OPORTUNIDADE_VIGENTE`.
    """
    pagamento = _dividir_pagamento_proporcional(
        operacao.PAGAMENTO_MENSAL_EFETIVO, saldo, operacao.SALDO_NOVA_OPERACAO
    )
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.OUTRA,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=operacao.TAXA_EFETIVA_MENSAL_NORMALIZADA,
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=pagamento,
        PAGAMENTO_MENSAL_EFETIVO=pagamento,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro(0),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
    divida_antiga_id: str,
    operacao: OperacaoTroca,
    estado: EstadoFinanceiro,
    dg: Diagnostico,
    sel: SelecionarAlvo,
    p: Parametros,
) -> ResultadoSubstituicaoEquivalente:
    """`T-01`/`T-02`: calcula o `CENARIO_SUBSTITUICAO_EQUIVALENTE` — a
    simulação, isolada do resto da carteira, de SÓ a parcela da nova
    operação que substitui a dívida antiga (`operacao.VALOR_SUBSTITUIDO`).

    `T-01`: o cenário equivalente NUNCA usa `operacao.SALDO_NOVA_OPERACAO`
    como saldo simulado — apenas `VALOR_SUBSTITUIDO`. Se
    `SALDO_NOVA_OPERACAO > VALOR_SUBSTITUIDO`, a diferença é `DINHEIRO_NOVO`
    e é simulada em uma `Divida` sintética SEPARADA
    (`cenario_dinheiro_novo`) — nunca somada, subtraída ou combinada ao
    cenário equivalente.

    `T-02`: `DINHEIRO_NOVO` é sempre >= 0 (validado abaixo) e é devolvido
    como componente identificável (`ResultadoSubstituicaoEquivalente.
    DINHEIRO_NOVO`) — endividamento adicional puro, nunca "economia" nem
    redutor do custo do cenário equivalente. Nenhuma linha desta função soma
    `DINHEIRO_NOVO` (ou o cenário dele) ao `cenario_equivalente`.

    O resultado é comparável ao cenário SEM troca mês a mês: ambos são
    `Cenario`s produzidos por `simular_cenario` sobre uma dívida isolada
    (a mesma função usada para qualquer outro cenário do motor), então
    `cenario_equivalente.meses[i]` e `cenario_sem_troca.meses[i]` são
    `ResultadoMes` da mesma natureza, comparáveis posição a posição pelo
    chamador (`T-72`/`GAB-05`).
    """
    if operacao.SALDO_NOVA_OPERACAO < operacao.VALOR_SUBSTITUIDO:
        raise ErroDinheiroNovoNegativo(
            "SALDO_NOVA_OPERACAO "
            f"({operacao.SALDO_NOVA_OPERACAO!r}) menor que VALOR_SUBSTITUIDO "
            f"({operacao.VALOR_SUBSTITUIDO!r}) — a nova operação não cobriria "
            "nem a quitação da dívida antiga; dado inconsistente."
        )

    with localcontext(CONTEXTO_MOTOR):
        dinheiro_novo = operacao.SALDO_NOVA_OPERACAO - operacao.VALOR_SUBSTITUIDO

    # T-01: cenário equivalente calculado SÓ sobre VALOR_SUBSTITUIDO — nunca
    # sobre SALDO_NOVA_OPERACAO. Dívida sintética isolada, simulada sozinha
    # (mesmo padrão de isolamento de uma dívida por vez, RF-05).
    divida_equivalente_id = f"{divida_antiga_id}{_SUFIXO_EQUIVALENTE}"
    divida_equivalente = _divida_sintetica(
        divida_equivalente_id, operacao.VALOR_SUBSTITUIDO, operacao
    )
    cenario_equivalente = simular_cenario(
        estado, dg, {divida_equivalente_id: divida_equivalente}, sel, p
    )

    # T-02: DINHEIRO_NOVO só existe como cenário SEPARADO, quando > 0 —
    # jamais incorporado ao cenario_equivalente acima. Sem dinheiro novo
    # (troca "limpa", igual ao saldo antigo), não há nada a isolar.
    cenario_dinheiro_novo: Cenario | None = None
    if dinheiro_novo > dinheiro(0):
        divida_dinheiro_novo_id = f"{divida_antiga_id}{_SUFIXO_DINHEIRO_NOVO}"
        divida_dinheiro_novo = _divida_sintetica(divida_dinheiro_novo_id, dinheiro_novo, operacao)
        cenario_dinheiro_novo = simular_cenario(
            estado, dg, {divida_dinheiro_novo_id: divida_dinheiro_novo}, sel, p
        )

    return ResultadoSubstituicaoEquivalente(
        DINHEIRO_NOVO=dinheiro_novo,
        cenario_equivalente=cenario_equivalente,
        cenario_dinheiro_novo=cenario_dinheiro_novo,
    )
