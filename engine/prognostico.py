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
from typing import Final

from engine.ciclo_mensal import Cenario, EstadoSimulacao, SelecionarAlvo, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import DESCONHECIDO, Dinheiro, Meses

REGRAS: Final[tuple[str, ...]] = ("RF-77", "RF-78")


@dataclass(frozen=True, slots=True)
class MesDoPlano:
    """`T-176` — um mês de um plano (o seguido ou o acelerado), para o mural e
    para o detalhe de cada mês do relatório. A soma dos saldos é do motor: o
    app só lê (Lei nº 3)."""

    MES: Meses
    DIVIDA_ALVO: str | None  # quem recebe o extra no mês; `None` sem alvo
    VALOR_EXTRA: Dinheiro  # ataque do mês (cresce quando uma dívida acaba)
    SALDO_TOTAL: Dinheiro  # soma dos saldos de todas as dívidas ao fim do mês
    QUITACOES: tuple[str, ...]  # dívidas quitadas no mês


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
    #: Mês da primeira dívida que se quita sozinha; `None` se nenhuma (RF-77, T-174).
    MESES_PRIMEIRA_VITORIA: Meses | None = None
    #: (DIVIDA_ID, mês) de cada dívida que se quita sozinha no horizonte (T-175).
    QUITACOES: tuple[tuple[str, Meses], ...] = ()


@dataclass(frozen=True, slots=True)
class PrognosticoComExtra:
    """`RF-78` — o plano recomendado com a contribuição extra do aluno somada
    ao ataque (sem nova margem de segurança: é o valor que o aluno diz poder)."""

    CONTRIBUICAO_EXTRA_MENSAL: Dinheiro
    PRAZO_TOTAL: Meses
    CUSTO_FUTURO_TOTAL: Dinheiro
    MESES_PRIMEIRA_VITORIA: Meses | None
    ESTOUROU_HORIZONTE: bool
    #: Ataque mensal total do verde: ataque do plano + extra (T-174).
    ATAQUE_MENSAL_TOTAL: Dinheiro | None = None
    #: (DIVIDA_ID, mês) de cada dívida quitada no verde (T-175).
    QUITACOES: tuple[tuple[str, Meses], ...] = ()
    #: Prazo do plano recomendado menos o prazo do verde (nunca negativo) — a
    #: conta é do motor, o app só lê (Lei nº 3).
    MESES_ANTECIPADOS: Meses = 0
    #: Custo futuro do plano recomendado menos o do verde (nunca negativo).
    ECONOMIA_CUSTO: Dinheiro = dinheiro(0)
    #: O mês a mês do plano acelerado (T-176).
    MESES: tuple[MesDoPlano, ...] = ()


@dataclass(frozen=True, slots=True)
class Prognostico:
    """Campo `SnapshotOrdem.prognostico` (`RF-77`, `RF-78`). O azul é o próprio
    snapshot; `com_extra` (verde) só existe com contribuição extra informada."""

    sem_acao: PrognosticoSemAcao
    com_extra: PrognosticoComExtra | None = None
    #: O mês a mês do plano seguido (cenário recomendado), T-176.
    MESES_DO_PLANO: tuple[MesDoPlano, ...] = ()


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
    selecionar_alvo: SelecionarAlvo | None = None,
    aportes_do_verde: Mapping[Meses, Dinheiro] | None = None,
) -> Prognostico | None:
    """`RF-77` — `None` sem dívida simulável (`AC-134`). `RF-78` — com
    `estado.CONTRIBUICAO_EXTRA_MENSAL` > 0 e o seletor do método recomendado,
    simula também o verde: mesmo método, ataque somado do valor extra e
    `aportes_do_verde` (recursos extraordinários, de qualquer certeza)."""
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
        MESES_DO_PLANO=_meses_do_plano(cenario_recomendado),
        com_extra=_com_extra(
            estado,
            diagnostico_pre,
            dividas,
            parametros,
            selecionar_alvo,
            aportes_do_verde,
            cenario_recomendado,
        ),
        sem_acao=PrognosticoSemAcao(
            HORIZONTE_MESES=horizonte,
            SALDO_INICIAL_TOTAL=saldo_inicial,
            SALDO_NO_HORIZONTE=saldo_no_horizonte,
            DIVIDAS_QUITADAS_SOZINHAS=quitadas,
            DIVIDAS_QUE_CRESCEM=crescem,
            DEFICIT_MENSAL=deficit_mensal,
            DEFICIT_ACUMULADO=_deficit_acumulado(sem_acao, resultado, horizonte),
            MESES_PRIMEIRA_VITORIA=(
                sem_acao.MESES_PRIMEIRA_VITORIA
                if sem_acao.MESES_PRIMEIRA_VITORIA is not None
                and sem_acao.MESES_PRIMEIRA_VITORIA <= horizonte
                else None
            ),
            QUITACOES=_quitacoes(sem_acao, horizonte),
        )
    )


def _com_extra(
    estado: EstadoFinanceiro,
    diagnostico_pre: Diagnostico,
    dividas: Mapping[str, Divida],
    parametros: Parametros,
    selecionar_alvo: SelecionarAlvo | None,
    aportes: Mapping[Meses, Dinheiro] | None,
    cenario_recomendado: Cenario,
) -> PrognosticoComExtra | None:
    extra = estado.CONTRIBUICAO_EXTRA_MENSAL
    capacidade = diagnostico_pre.CAPACIDADE_ATAQUE_CONSERVADORA
    if selecionar_alvo is None or extra is None or extra <= dinheiro(0):
        return None
    with localcontext(CONTEXTO_MOTOR):
        total = capacidade + extra
    cenario = simular_cenario(
        estado,
        replace(diagnostico_pre, CAPACIDADE_ATAQUE_CONSERVADORA=total),
        dividas,
        selecionar_alvo,
        parametros,
        aportes if aportes is not None else {},
    )
    with localcontext(CONTEXTO_MOTOR):
        antecipados = max(0, cenario_recomendado.PRAZO_TOTAL - cenario.PRAZO_TOTAL)
        economia = max(
            dinheiro(0), cenario_recomendado.CUSTO_FUTURO_TOTAL - cenario.CUSTO_FUTURO_TOTAL
        )
    return PrognosticoComExtra(
        ATAQUE_MENSAL_TOTAL=total,
        MESES_ANTECIPADOS=antecipados,
        ECONOMIA_CUSTO=economia,
        CONTRIBUICAO_EXTRA_MENSAL=extra,
        PRAZO_TOTAL=cenario.PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=cenario.CUSTO_FUTURO_TOTAL,
        MESES_PRIMEIRA_VITORIA=cenario.MESES_PRIMEIRA_VITORIA,
        QUITACOES=_quitacoes(cenario, cenario.PRAZO_TOTAL),
        MESES=_meses_do_plano(cenario),
        ESTOUROU_HORIZONTE=cenario.ESTOUROU_HORIZONTE,
    )


def _meses_do_plano(cenario: Cenario) -> tuple[MesDoPlano, ...]:
    """Um `MesDoPlano` por mês simulado de `cenario`; no último mês não há alvo
    (as dívidas acabaram) e o extra é o que a simulação registrou."""
    meses: list[MesDoPlano] = []
    for resultado in cenario.meses:
        estado = resultado.estado_final
        alvo = estado.DIVIDA_ALVO_ATUAL
        meses.append(
            MesDoPlano(
                MES=estado.mes,
                DIVIDA_ALVO=alvo,
                VALOR_EXTRA=estado.CAPACIDADE_ATAQUE_M if alvo is not None else dinheiro(0),
                SALDO_TOTAL=_soma(estado.saldos.values()),
                QUITACOES=resultado.quitacoes,
            )
        )
    return tuple(meses)


def _quitacoes(cenario: Cenario, ate_o_mes: Meses) -> tuple[tuple[str, Meses], ...]:
    """(DIVIDA_ID, mês) de cada quitação até `ate_o_mes`, na ordem em que acontecem."""
    return tuple(
        (divida_id, resultado.estado_final.mes)
        for resultado in cenario.meses
        if resultado.estado_final.mes <= ate_o_mes
        for divida_id in resultado.quitacoes
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
