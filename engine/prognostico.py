"""Prognóstico "sem ação" — `RF-77` · `AC-132`..`AC-134` · `EC-57`.

O que acontece se o aluno **não fizer nada**: cada dívida segue só com o
pagamento mensal efetivo de hoje, sem ataque e sem reaplicar a parcela de uma
dívida quitada nas demais, pelo mesmo horizonte do cenário recomendado.

**Nada novo no ciclo mensal.** A projeção reaproveita `simular_cenario` com
capacidade de ataque **zero** e um `SelecionarAlvo` que nunca escolhe alvo: o
`VALOR_FLUXO_LIBERADO` de uma dívida quitada vira `ATAQUE_NAO_UTILIZADO`
(caixa do aluno) e jamais ataca outra dívida (`A-04`, `EC-01`). Juros,
pagamento normal e quitação natural são os de sempre (`M-02`, `M-03`, `M-06`).

**Déficit.** Em cada mês, `caixa = RESULTADO_MENSAL_ATUAL + liberado acumulado`
(o que as dívidas já quitadas deixaram de consumir entra a partir do mês
seguinte, `F-02`); o déficit do mês é `max(0, -caixa)`. O total é a soma
simples, **sem juros inventados** sobre o que faltou (decisão do produto,
2026-10-06): nenhuma taxa de financiamento do déficit existe nos parâmetros.

O campo é opcional no snapshot: `None` quando não há dívida simulável.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from decimal import localcontext

from engine.ciclo_mensal import Cenario, EstadoSimulacao, SelecionarAlvo, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import DESCONHECIDO, Dinheiro, Meses


@dataclass(frozen=True, slots=True)
class PrognosticoSemAcao:
    """`RF-77` — a situação ao fim do horizonte se o aluno não fizer nada."""

    HORIZONTE_MESES: Meses
    SALDO_INICIAL_TOTAL: Dinheiro
    SALDO_NO_HORIZONTE: Dinheiro
    DIVIDAS_QUITADAS_SOZINHAS: int
    #: Dívidas cujo saldo no horizonte é MAIOR que o inicial (parcela que não
    #: cobre os juros, `AC-134`).
    DIVIDAS_QUE_CRESCEM: int
    DEFICIT_MENSAL: Dinheiro  # hoje; 0 quando o resultado do mês não é negativo
    DEFICIT_ACUMULADO: Dinheiro  # soma dos déficits mensais no horizonte, sem juros


@dataclass(frozen=True, slots=True)
class Prognostico:
    """Campo `SnapshotOrdem.prognostico` (`RF-77`). Hoje só o cenário "sem
    ação"; o plano recomendado é o próprio snapshot."""

    sem_acao: PrognosticoSemAcao


def _sem_alvo(_estado: EstadoSimulacao, _delta: Dinheiro) -> Divida | None:
    """`SelecionarAlvo` que nunca escolhe: ninguém ataca nada."""
    return None


_SEM_ALVO: SelecionarAlvo = _sem_alvo


def calcular_prognostico(
    *,
    estado: EstadoFinanceiro,
    diagnostico_pre: Diagnostico,
    dividas: Mapping[str, Divida],
    cenario_recomendado: Cenario,
    parametros: Parametros,
) -> Prognostico | None:
    """`RF-77` — `None` sem dívida simulável (`AC-134`)."""
    if not dividas:
        return None

    diagnostico_sem_acao = replace(diagnostico_pre, CAPACIDADE_ATAQUE_CONSERVADORA=dinheiro(0))
    sem_acao = simular_cenario(estado, diagnostico_sem_acao, dividas, _SEM_ALVO, parametros)

    # Mesmo horizonte do plano recomendado (já limitado por
    # `P_HORIZONTE_MAXIMO_SIMULACAO`); no mínimo 1 mês.
    horizonte: Meses = max(1, cenario_recomendado.PRAZO_TOTAL)

    saldo_inicial = _soma(
        divida.SALDO_DEVEDOR_ATUAL
        for divida in dividas.values()
        if divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
    )
    saldos_no_horizonte = _saldos_no_mes(sem_acao, dividas, horizonte)
    saldo_no_horizonte = _soma(saldos_no_horizonte.values())

    quitadas = sum(1 for saldo in saldos_no_horizonte.values() if saldo == dinheiro(0))
    crescem = sum(
        1
        for divida_id, saldo in saldos_no_horizonte.items()
        if (inicial := dividas[divida_id].SALDO_DEVEDOR_ATUAL) is not DESCONHECIDO
        and saldo > inicial
    )

    resultado = diagnostico_pre.RESULTADO_MENSAL_ATUAL
    deficit_mensal = dinheiro(0)
    with localcontext(CONTEXTO_MOTOR):
        if resultado < dinheiro(0):
            deficit_mensal = -resultado

    return Prognostico(
        sem_acao=PrognosticoSemAcao(
            HORIZONTE_MESES=horizonte,
            SALDO_INICIAL_TOTAL=saldo_inicial,
            SALDO_NO_HORIZONTE=saldo_no_horizonte,
            DIVIDAS_QUITADAS_SOZINHAS=quitadas,
            DIVIDAS_QUE_CRESCEM=crescem,
            DEFICIT_MENSAL=deficit_mensal,
            DEFICIT_ACUMULADO=_deficit_acumulado(sem_acao, resultado, horizonte),
        )
    )


def _soma(valores: Iterable[Dinheiro]) -> Dinheiro:
    total = dinheiro(0)
    with localcontext(CONTEXTO_MOTOR):
        for valor in valores:
            total = total + valor
    return total


def _saldos_no_mes(
    cenario: Cenario, dividas: Mapping[str, Divida], mes: Meses
) -> Mapping[str, Dinheiro]:
    """Saldo de cada dívida ao fim do mês `mes`; depois que a simulação acabou
    (tudo quitado), o saldo é zero."""
    if not cenario.meses:
        return {
            divida_id: divida.SALDO_DEVEDOR_ATUAL
            for divida_id, divida in dividas.items()
            if divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        }
    indice = min(mes, len(cenario.meses)) - 1
    return cenario.meses[indice].estado_final.saldos


def _deficit_acumulado(cenario: Cenario, resultado: Dinheiro, horizonte: Meses) -> Dinheiro:
    """Soma, mês a mês, de `max(0, -(resultado + liberado acumulado))` (`RF-77`)."""
    total = dinheiro(0)
    liberado = dinheiro(0)
    with localcontext(CONTEXTO_MOTOR):
        for mes in range(1, horizonte + 1):
            caixa = resultado + liberado
            if caixa < dinheiro(0):
                total = total - caixa
            if mes <= len(cenario.meses):
                liberado = liberado + cenario.meses[mes - 1].VALOR_FLUXO_LIBERADO
    return total
