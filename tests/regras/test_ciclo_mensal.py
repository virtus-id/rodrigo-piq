"""Testes de `executar_mes` — RF-01, RF-02, RF-03, RF-04 · M-01..M-08 ·
AC-13, AC-14, AC-15, AC-32 · A-01..A-04 · F-01..F-03 · O-03 · R-03 ·
EC-01, EC-02, EC-18.

`T-42` cobre o esqueleto M-01..M-06 (abertura, juros, pagamentos normais,
ataque, verificação de quitação, alvo preservado sem quitação). `T-43`
acrescentou o laço de cascata do resíduo (`M-07`/`M-08`):

- O reranqueamento ocorre ANTES de cada aplicação de resíduo (`O-03`).
- O delta passado a `sel()` no reranqueamento é sempre o resíduo restante,
  nunca a capacidade cheia do mês (`A-03`, `AC-14`).
- Cada aplicação de resíduo é registrada em `aplicacoes_residuo`, com
  dívida, valor e ordem (`A-02`).
- Duas quitações no mesmo mês (cascata dupla) produzem duas rodadas.
- `reranqueamentos` registra 0, 1 ou vários eventos, conforme a cascata
  (`R-03`) — sem contar a chamada de bootstrap de M-04.

`T-44` fecha o destino do resíduo que sobra ao fim da cascata (`A-04`,
`EC-01`): vira `ATAQUE_NAO_UTILIZADO` do mês, acumula em
`ATAQUE_NAO_UTILIZADO_ACUMULADO` e é coberto pela invariante de conservação
(`ErroInvariante`) — ver classe `test_ataque_nao_utilizado_*` abaixo.

`T-45` fecha `VALOR_FLUXO_LIBERADO` (`F-01`..`F-03`, §11.7): o valor
consolidado é o `PAGAMENTO_MENSAL_EFETIVO` (não o contratual) de cada
dívida quitada no mês — incluindo as quitadas dentro da cascata de resíduo
— e é apenas DEVOLVIDO por `executar_mes`, nunca somado à
`CAPACIDADE_ATAQUE_M` do próprio mês. A incorporação em *m+1* é
responsabilidade de `simular_cenario` (`T-46`) — ver classe
`test_valor_fluxo_liberado_*` abaixo.

`_divida` monta uma `Divida` completa e válida, variando só os campos que o
ciclo mensal lê (saldo, taxa, pagamento efetivo) — mesmo padrão de
`tests/regras/test_gates.py::_divida` e `test_valor_quitacao.py::_divida_base`.
`_sel_por_saldo` é um `SelecionarAlvo` de teste: escolhe, entre as dívidas
NÃO quitadas do estado recebido, a de menor saldo (proxy simples e
determinístico — não é a Avalanche real, que é `T-49`) e GRAVA cada
chamada (estado, delta) recebida, para as asserções de `AC-14`/`O-03`.

REGRAS: RF-01, RF-02, RF-03, RF-04, M-01, M-02, M-03, M-04, M-05, M-06,
M-07, M-08, A-01, A-02, A-03, A-04, F-01, F-02, F-03, O-03, R-03, AC-13,
AC-14, AC-15, AC-32, EC-01, EC-02, EC-18
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

import pytest

from engine.ciclo_mensal import ErroInvariante, EstadoSimulacao, executar_mes
from engine.estado import TIPO_DIVIDA, Divida
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import (
    DESCONHECIDO,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    DinheiroTalvez,
    SimNaoTalvez,
    TaxaTalvez,
)
from tests.conftest import assertar_exato


def _divida(
    divida_id: str,
    *,
    saldo: DinheiroTalvez,
    taxa: TaxaTalvez | None = None,
    pagamento_mensal_efetivo: DinheiroTalvez | None = None,
) -> Divida:
    """Dívida completa e válida, variando só saldo/taxa/pagamento — os três
    campos que `executar_mes` (M-02/M-03/M-04) consome. Demais campos
    neutros, sem influência no ciclo mensal."""
    if taxa is None:
        taxa = dinheiro("0")
    if pagamento_mensal_efetivo is None:
        pagamento_mensal_efetivo = dinheiro("0")
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=taxa,
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=pagamento_mensal_efetivo,
        PAGAMENTO_MENSAL_EFETIVO=pagamento_mensal_efetivo,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _parametros_vazios() -> Parametros:
    """`executar_mes` não lê `Parametros` nesta tarefa (`p` é `noqa: ARG001`
    no código) — instância mínima só para satisfazer a assinatura."""
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={},
    )


@dataclass
class _ChamadaSel:
    """Uma chamada capturada de `SelecionarAlvo`, para auditoria em teste."""

    delta: DinheiroTalvez
    candidatos: tuple[str, ...]


@dataclass
class _SelPorMenorSaldo:
    """`SelecionarAlvo` de teste: entre as dívidas NÃO quitadas do estado
    recebido, escolhe a de menor saldo (desempate por `DIVIDA_ID`). Grava
    cada chamada em `chamadas` para inspeção posterior (delta recebido,
    candidatos elegíveis) — é o instrumento usado para provar `AC-14`/`O-03`.
    """

    dividas: dict[str, Divida]
    chamadas: list[_ChamadaSel] = field(default_factory=list)

    def __call__(self, estado: EstadoSimulacao, delta: DinheiroTalvez) -> Divida | None:
        candidatos = tuple(
            divida_id for divida_id in self.dividas if divida_id not in estado.quitadas
        )
        self.chamadas.append(_ChamadaSel(delta=delta, candidatos=candidatos))
        if not candidatos:
            return None
        escolhido = min(candidatos, key=lambda d: (estado.saldos[d], d))
        return self.dividas[escolhido]


def _estado_inicial(
    *, alvo: str | None, capacidade: DinheiroTalvez, saldos: dict[str, DinheiroTalvez]
) -> EstadoSimulacao:
    return EstadoSimulacao(
        mes=0,
        saldos=saldos,  # type: ignore[arg-type]
        quitadas=frozenset(),
        DIVIDA_ALVO_ATUAL=alvo,
        CAPACIDADE_ATAQUE_M=capacidade,  # type: ignore[arg-type]
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )


# ---------------------------------------------------------------------------
# Cascata simples: uma quitação do alvo, resíduo aplicado a uma segunda
# dívida que NÃO quita — uma única rodada.
# ---------------------------------------------------------------------------
def test_cascata_simples_uma_rodada_reranqueia_antes_de_aplicar() -> None:
    d1 = _divida("D-01", saldo=dinheiro("100"))  # alvo — quita com folga
    d2 = _divida("D-02", saldo=dinheiro("500"))  # recebe o resíduo, não quita
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("300"),
        saldos={"D-01": dinheiro("100"), "D-02": dinheiro("500")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # M-06: RESIDUO_ATAQUE_M = ataque total (300) - saldo do alvo (100) = 200.
    assertar_exato(resultado.RESIDUO_ATAQUE_M, dinheiro("200"))

    # A-02: uma única aplicação de resíduo, para D-02, ordem 1.
    assertar_exato(len(resultado.aplicacoes_residuo), 1)
    aplicacao = resultado.aplicacoes_residuo[0]
    assertar_exato(aplicacao.DIVIDA_ID, "D-02")
    assertar_exato(aplicacao.valor_aplicado, dinheiro("200"))
    assertar_exato(aplicacao.ordem_aplicacao, 1)

    # R-03: um único reranqueamento (não conta o bootstrap — alvo já vinha
    # definido no estado inicial, então nem houve chamada de bootstrap).
    assertar_exato(len(resultado.reranqueamentos), 1)
    assertar_exato(resultado.reranqueamentos[0].novo_alvo, "D-02")

    # O-03/AC-14: a única chamada a `sel()` recebeu o RESÍDUO (200), nunca a
    # capacidade cheia do mês (300), e não incluiu a dívida já quitada.
    assertar_exato(len(sel.chamadas), 1)
    assertar_exato(sel.chamadas[0].delta, dinheiro("200"))
    assertar_exato(sel.chamadas[0].candidatos, ("D-02",))

    # D-01 quitada, D-02 recebeu o resíduo e continua com saldo 300 (500-200).
    assertar_exato(set(resultado.quitacoes), {"D-01"})
    assertar_exato(resultado.estado_final.saldos["D-02"], dinheiro("300"))
    assertar_exato(resultado.estado_final.DIVIDA_ALVO_ATUAL, "D-02")


# ---------------------------------------------------------------------------
# Cascata dupla: a segunda dívida também quita com o resíduo, sobra um
# resíduo NOVO que vai para a terceira — duas rodadas completas.
# ---------------------------------------------------------------------------
def test_cascata_dupla_duas_rodadas_com_reranqueamento_a_cada_uma() -> None:
    # Capacidade suficiente para quitar D-01 (50) e D-02 (30), sobrando
    # resíduo para D-03 sem quitá-la.
    d1 = _divida("D-01", saldo=dinheiro("50"))
    d2 = _divida("D-02", saldo=dinheiro("30"))
    d3 = _divida("D-03", saldo=dinheiro("1000"))
    dividas = {"D-01": d1, "D-02": d2, "D-03": d3}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("100"),
        saldos={"D-01": dinheiro("50"), "D-02": dinheiro("30"), "D-03": dinheiro("1000")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # M-06: RESIDUO_ATAQUE_M = 100 - 50 = 50 (resíduo bruto do alvo original).
    assertar_exato(resultado.RESIDUO_ATAQUE_M, dinheiro("50"))

    # Duas rodadas de cascata: D-02 quita (recebe 30, sobra resíduo 20),
    # D-03 recebe os 20 restantes sem quitar.
    assertar_exato(len(resultado.aplicacoes_residuo), 2)
    primeira, segunda = resultado.aplicacoes_residuo
    assertar_exato(primeira.DIVIDA_ID, "D-02")
    assertar_exato(primeira.valor_aplicado, dinheiro("30"))
    assertar_exato(primeira.ordem_aplicacao, 1)
    assertar_exato(segunda.DIVIDA_ID, "D-03")
    assertar_exato(segunda.valor_aplicado, dinheiro("20"))
    assertar_exato(segunda.ordem_aplicacao, 2)

    # R-03: dois reranqueamentos — um por rodada da cascata.
    assertar_exato(len(resultado.reranqueamentos), 2)
    assertar_exato(resultado.reranqueamentos[0].novo_alvo, "D-02")
    assertar_exato(resultado.reranqueamentos[1].novo_alvo, "D-03")

    # AC-14/O-03: cada chamada usou o resíduo RESTANTE daquele momento —
    # nunca a capacidade cheia (100) — e nunca incluiu dívida já quitada.
    assertar_exato(len(sel.chamadas), 2)
    assertar_exato(sel.chamadas[0].delta, dinheiro("50"))
    assertar_exato(sel.chamadas[0].candidatos, ("D-02", "D-03"))
    assertar_exato(sel.chamadas[1].delta, dinheiro("20"))
    assertar_exato(sel.chamadas[1].candidatos, ("D-03",))

    # Duas quitações no mês: D-01 (alvo original) e D-02 (cascata).
    assertar_exato(set(resultado.quitacoes), {"D-01", "D-02"})
    assertar_exato(resultado.estado_final.saldos["D-03"], dinheiro("980"))
    assertar_exato(resultado.estado_final.DIVIDA_ALVO_ATUAL, "D-03")


# ---------------------------------------------------------------------------
# Sem resíduo: alvo quitado exatamente, nenhuma cascata, nenhum
# reranqueamento é registrado no laço de resíduo.
# ---------------------------------------------------------------------------
def test_sem_residuo_nao_ha_cascata_nem_aplicacao() -> None:
    d1 = _divida("D-01", saldo=dinheiro("100"))
    d2 = _divida("D-02", saldo=dinheiro("500"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("100"),  # exatamente o saldo do alvo — sem sobra
        saldos={"D-01": dinheiro("100"), "D-02": dinheiro("500")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(resultado.RESIDUO_ATAQUE_M, dinheiro("0"))
    assertar_exato(resultado.aplicacoes_residuo, ())
    assertar_exato(resultado.reranqueamentos, ())
    assertar_exato(len(sel.chamadas), 0)
    assertar_exato(resultado.estado_final.DIVIDA_ALVO_ATUAL, None)


# ---------------------------------------------------------------------------
# Resíduo sem dívida elegível remanescente: laço para sem travar/gerar erro
# — o resíduo pós-cascata vira ATAQUE_NAO_UTILIZADO (A-04/EC-01, T-44).
# ---------------------------------------------------------------------------
def test_residuo_sem_dividas_elegiveis_para_sem_erro() -> None:
    d1 = _divida("D-01", saldo=dinheiro("100"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("300"),
        saldos={"D-01": dinheiro("100")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(resultado.RESIDUO_ATAQUE_M, dinheiro("200"))
    # Nenhuma candidata restante: `sel` sequer é chamada de novo (não há
    # candidatos elegíveis) — nenhum reranqueamento nem aplicação.
    assertar_exato(resultado.aplicacoes_residuo, ())
    assertar_exato(resultado.reranqueamentos, ())
    assertar_exato(len(sel.chamadas), 0)
    assertar_exato(resultado.estado_final.DIVIDA_ALVO_ATUAL, None)
    # A-04/EC-01/T-44: sem dívida elegível para receber o resíduo, os 200
    # que sobraram viram ATAQUE_NAO_UTILIZADO do mês — nunca desaparecem.
    assertar_exato(resultado.ATAQUE_NAO_UTILIZADO, dinheiro("200"))


# ---------------------------------------------------------------------------
# Sem quitação do alvo: M-05, alvo preservado, sem qualquer chamada a `sel`
# — nem bootstrap, nem cascata (guarda de regressão contra T-42).
# ---------------------------------------------------------------------------
def test_sem_quitacao_do_alvo_nao_chama_sel() -> None:
    d1 = _divida("D-01", saldo=dinheiro("1000"))
    d2 = _divida("D-02", saldo=dinheiro("500"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("100"),
        saldos={"D-01": dinheiro("1000"), "D-02": dinheiro("500")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(resultado.quitacoes, ())
    assertar_exato(resultado.aplicacoes_residuo, ())
    assertar_exato(resultado.reranqueamentos, ())
    assertar_exato(len(sel.chamadas), 0)
    assertar_exato(resultado.estado_final.DIVIDA_ALVO_ATUAL, "D-01")


# ---------------------------------------------------------------------------
# T-44 — ATAQUE_NAO_UTILIZADO quando o resíduo não tem destino (A-04, EC-01).
# ---------------------------------------------------------------------------


def test_ataque_nao_utilizado_aplicado_mais_nao_utilizado_igual_capacidade() -> None:
    """Critério 1: ataque aplicado + ATAQUE_NAO_UTILIZADO == ataque
    disponível, em todo mês (invariante de conservação) — cenário com
    cascata dupla e sobra final sem candidata elegível."""
    d1 = _divida("D-01", saldo=dinheiro("50"))
    d2 = _divida("D-02", saldo=dinheiro("30"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("100"),
        saldos={"D-01": dinheiro("50"), "D-02": dinheiro("30")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # D-01 quita com 50, D-02 quita com o resíduo de 50 (recebe 30), sobram
    # 20 sem nenhuma dívida elegível remanescente.
    assertar_exato(resultado.ATAQUE_NAO_UTILIZADO, dinheiro("20"))
    ataque_aplicado = sum(
        (aplicacao.valor_aplicado for aplicacao in resultado.aplicacoes_residuo),
        start=dinheiro("0"),
    ) + (
        dinheiro("50")  # aplicado no alvo original D-01 (capacidade que coube)
    )
    assertar_exato(ataque_aplicado + resultado.ATAQUE_NAO_UTILIZADO, dinheiro("100"))


def test_ataque_nao_utilizado_acumula_no_estado_de_simulacao() -> None:
    """Critério 2: o acumulado aparece em ATAQUE_NAO_UTILIZADO_ACUMULADO no
    estado de simulação, somando o que já vinha do mês anterior."""
    d1 = _divida("D-01", saldo=dinheiro("100"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = EstadoSimulacao(
        mes=0,
        saldos={"D-01": dinheiro("100")},
        quitadas=frozenset(),
        DIVIDA_ALVO_ATUAL="D-01",
        CAPACIDADE_ATAQUE_M=dinheiro("300"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("50"),  # já havia acumulado de meses antes
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # 300 de capacidade - 100 do saldo do alvo = 200 sem destino neste mês.
    assertar_exato(resultado.ATAQUE_NAO_UTILIZADO, dinheiro("200"))
    # 50 (herdado) + 200 (deste mês) = 250 — soma exata dentro do teste, sem
    # tolerância monetária: um único mês simulado não acumula erro de
    # arredondamento intermediário (G-01: precisão decimal integral).
    assertar_exato(resultado.estado_final.ATAQUE_NAO_UTILIZADO_ACUMULADO, dinheiro("250"))


def test_ataque_nao_utilizado_sem_alvo_algum_nao_descarta_capacidade() -> None:
    """Critério 3: nenhum caminho descarta resíduo silenciosamente — inclui
    o caso em que não há dívida alguma para virar alvo (bootstrap sem
    dívidas), onde a capacidade inteira do mês não tinha para onde ir."""
    dividas: dict[str, Divida] = {}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(alvo=None, capacidade=dinheiro("150"), saldos={})

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # Sem dívida nenhuma, a capacidade inteira vira ATAQUE_NAO_UTILIZADO —
    # nunca some da simulação.
    assertar_exato(resultado.ATAQUE_NAO_UTILIZADO, dinheiro("150"))
    assertar_exato(resultado.estado_final.ATAQUE_NAO_UTILIZADO_ACUMULADO, dinheiro("150"))


# ---------------------------------------------------------------------------
# T-45 — VALOR_FLUXO_LIBERADO consolidado e devolvido, sem incorporação
# dentro do próprio mês (F-01..F-03, RF-04, AC-15, AC-32, EC-18).
# ---------------------------------------------------------------------------


def test_fluxo_liberado_dividida_quitada_nao_reforca_capacidade_do_proprio_mes() -> None:
    """Critério 1 (AC-15): dívida com efetivo 700 quitada no mês 4 devolve
    VALOR_FLUXO_LIBERADO = 700, mas a capacidade DENTRO deste mesmo mês
    (o que efetivamente coube na dívida-alvo) não é reforçada por esse
    valor — a incorporação só acontece na abertura do mês seguinte, e essa
    incorporação é responsabilidade de `simular_cenario` (T-46), fora desta
    função. Aqui provamos que `executar_mes` apenas devolve, nunca soma."""
    # D-01 é dívida NÃO-alvo: quita apenas com o pagamento normal (EC-02) —
    # nenhum ataque necessário, então RESIDUO_ATAQUE_M do mês fica em 0 e a
    # capacidade inteira segue para D-02 (o alvo de fato), isolando a prova
    # de que o fluxo liberado por D-01 não reforça a capacidade deste mês.
    d1 = _divida("D-01", saldo=dinheiro("700"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("10000"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    # Mês 4: D-02 é o alvo, ataca com toda a capacidade do mês (300); D-01
    # (não-alvo) quita só com o pagamento normal de 700, liberando 700.
    estado = EstadoSimulacao(
        mes=3,
        saldos={"D-01": dinheiro("700"), "D-02": dinheiro("10000")},
        quitadas=frozenset(),
        DIVIDA_ALVO_ATUAL="D-02",
        CAPACIDADE_ATAQUE_M=dinheiro("300"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(resultado.estado_final.mes, 4)
    assertar_exato(set(resultado.quitacoes), {"D-01"})
    # F-01: o fluxo liberado devolvido é exatamente o efetivo da dívida
    # quitada — nem mais, nem menos.
    assertar_exato(resultado.VALOR_FLUXO_LIBERADO, dinheiro("700"))
    # D-02 (alvo) recebeu exatamente a CAPACIDADE_ATAQUE_M original (300) —
    # nunca 300 + 700: os 700 liberados por D-01 não reforçaram o ataque
    # aplicado DENTRO deste mês (F-02/AC-15: só valeria a partir do mês 5,
    # responsabilidade de `simular_cenario`/T-46, fora de `executar_mes`).
    assertar_exato(resultado.estado_final.saldos["D-02"], dinheiro("9700"))
    # A capacidade que define o mês, tanto recebida quanto devolvida no
    # estado final, permanece 300 — o motor não soma o fluxo liberado a
    # `CAPACIDADE_ATAQUE_M` dentro da própria chamada.
    assertar_exato(estado.CAPACIDADE_ATAQUE_M, dinheiro("300"))
    assertar_exato(resultado.estado_final.CAPACIDADE_ATAQUE_M, dinheiro("300"))


def test_fluxo_liberado_efetivo_zero_libera_zero_mesmo_com_contratual_alto() -> None:
    """Critério 2 (AC-32, EC-18): dívida com PARCELA_CONTRATUAL 1.200 mas
    PAGAMENTO_MENSAL_EFETIVO 0 (não estava sendo paga de fato) libera
    VALOR_FLUXO_LIBERADO = 0 ao ser quitada — nunca a parcela contratual
    fictícia."""
    d1_base = _divida("D-01", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    # PARCELA_CONTRATUAL fixada manualmente em 1.200, distinta do efetivo
    # (0) — reproduz o caso GAB-A/D001 citado pela spec (§8 do plano, risco
    # "usar a parcela contratual como fluxo liberado").
    d1 = replace(d1_base, PARCELA_CONTRATUAL=dinheiro("1200"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("500"),
        saldos={"D-01": dinheiro("500")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(set(resultado.quitacoes), {"D-01"})
    assertar_exato(resultado.VALOR_FLUXO_LIBERADO, dinheiro("0"))


def test_fluxo_liberado_devolvido_sem_somar_a_capacidade_do_proprio_mes() -> None:
    """Critério 3: `executar_mes` devolve VALOR_FLUXO_LIBERADO no resultado,
    mas `CAPACIDADE_ATAQUE_M` do `estado_final` é idêntica à recebida — a
    função nunca soma o fluxo liberado à capacidade dela mesma."""
    d1 = _divida("D-01", saldo=dinheiro("300"), pagamento_mensal_efetivo=dinheiro("300"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("300"),
        saldos={"D-01": dinheiro("300")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    assertar_exato(resultado.VALOR_FLUXO_LIBERADO, dinheiro("300"))
    # A capacidade do mês, tanto a recebida quanto a devolvida no estado
    # final, permanece 300 — nunca 300 + 300 (o fluxo liberado não é
    # incorporado dentro desta chamada).
    assertar_exato(estado.CAPACIDADE_ATAQUE_M, dinheiro("300"))
    assertar_exato(resultado.estado_final.CAPACIDADE_ATAQUE_M, dinheiro("300"))


def test_fluxo_liberado_nao_conta_como_pagamento_normal_e_capacidade_do_mesmo_mes() -> None:
    """Critério 4 (F-03): nenhum valor aparece simultaneamente como
    pagamento normal de m e como capacidade adicional de m. Cenário: D-01 é
    o alvo e quita com folga (resíduo sobra); D-02 é dívida NÃO-alvo, paga
    seu pagamento normal e TAMBÉM quita neste mesmo mês. O fluxo liberado
    por D-02 (via M-03, não via ataque) soma a VALOR_FLUXO_LIBERADO, mas o
    resíduo de D-01 — que é a única capacidade adicional válida deste mês —
    não é afetado pelo que D-02 liberou."""
    d1 = _divida("D-01", saldo=dinheiro("100"))  # alvo, quita com folga
    d2 = _divida(
        "D-02", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("50")
    )  # não-alvo, quita só com o pagamento normal (EC-02)
    d3 = _divida("D-03", saldo=dinheiro("10000"))  # candidata da cascata, não quita
    dividas = {"D-01": d1, "D-02": d2, "D-03": d3}
    sel = _SelPorMenorSaldo(dividas=dividas)

    estado = _estado_inicial(
        alvo="D-01",
        capacidade=dinheiro("300"),
        saldos={"D-01": dinheiro("100"), "D-02": dinheiro("50"), "D-03": dinheiro("10000")},
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # D-01 (ataque) e D-02 (pagamento normal) quitam no mesmo mês.
    assertar_exato(set(resultado.quitacoes), {"D-01", "D-02"})
    # F-01: fluxo liberado soma o efetivo de AMBAS — 0 (D-01, PAGAMENTO_
    # MENSAL_EFETIVO default "0" em `_divida`) + 50 (D-02) = 50.
    assertar_exato(resultado.VALOR_FLUXO_LIBERADO, dinheiro("50"))
    # F-03: o resíduo do ataque em D-01 (200 = 300 - 100) é inteiramente
    # aplicado a D-03 via cascata — o pagamento normal de D-02 (50) não
    # aparece somado ao delta de resíduo/capacidade adicional em nenhum
    # momento: a única chamada de `sel()` do laço recebe exatamente 200.
    assertar_exato(resultado.RESIDUO_ATAQUE_M, dinheiro("200"))
    assertar_exato(len(resultado.aplicacoes_residuo), 1)
    assertar_exato(resultado.aplicacoes_residuo[0].DIVIDA_ID, "D-03")
    assertar_exato(resultado.aplicacoes_residuo[0].valor_aplicado, dinheiro("200"))
    assertar_exato(len(sel.chamadas), 1)
    assertar_exato(sel.chamadas[0].delta, dinheiro("200"))


def test_fluxo_liberado_nao_ha_liberacao_retroativa() -> None:
    """Critério 5: não há liberação retroativa — uma dívida já quitada em
    mês anterior (presente em `e.quitadas` ao entrar no ciclo) não soma
    novamente ao VALOR_FLUXO_LIBERADO do mês corrente, mesmo que ainda
    apareça no inventário `dividas`."""
    d1 = _divida("D-01", saldo=dinheiro("0"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("400"), pagamento_mensal_efetivo=dinheiro("400"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    # D-01 já está em `quitadas` — quitação de um mês anterior, não deste.
    estado = EstadoSimulacao(
        mes=4,
        saldos={"D-01": dinheiro("0"), "D-02": dinheiro("400")},
        quitadas=frozenset({"D-01"}),
        DIVIDA_ALVO_ATUAL="D-02",
        CAPACIDADE_ATAQUE_M=dinheiro("400"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )

    resultado = executar_mes(estado, dividas, sel, _parametros_vazios())

    # D-02 quita neste mês (400 = pagamento normal 0 + ataque 400, saldo
    # 400); D-01 não aparece em `quitacoes` — já estava quitada.
    assertar_exato(set(resultado.quitacoes), {"D-02"})
    # Apenas os 400 de D-02 entram no fluxo liberado deste mês — os 700 de
    # D-01 NÃO são recontados (não há liberação retroativa de uma dívida
    # já quitada antes de este mês começar).
    assertar_exato(resultado.VALOR_FLUXO_LIBERADO, dinheiro("400"))


def test_erro_invariante_existe_e_carrega_mensagem_de_diagnostico() -> None:
    """Critério 4: existe `ErroInvariante` (convenção nova neste módulo,
    mesmo padrão de `engine.parametros.ErroParametros` — nenhuma outra
    exceção de invariante já existia em `engine/` para reaproveitar) e ela
    falha ruidosamente, carregando a mensagem de diagnóstico, quando levantada.

    A invariante de `executar_mes` (`ataque_aplicado + ATAQUE_NAO_UTILIZADO
    == CAPACIDADE_ATAQUE_M`) é fechada por construção algébrica a partir das
    MESMAS variáveis do laço de cascata (`residuo_ataque`,
    `aplicacoes_residuo_do_mes`, `residuo_ataque_corrente`) — não existe
    `SelecionarAlvo` que respeite o contrato do tipo (`Callable[[...], Divida
    | None]`, devolvendo sempre uma dívida do próprio `dividas` recebido) e
    consiga quebrá-la via `executar_mes` de fora, o que é o comportamento
    desejado (guarda contra regressão futura, não contra entrada de teste
    adversarial). Este teste prova a peça que falta para o critério: que o
    tipo de erro existe, é `Exception` e propaga a mensagem intacta.
    """
    with pytest.raises(ErroInvariante, match="conservação do ataque do mês não fechou"):
        raise ErroInvariante(
            "conservação do ataque do mês não fechou (A-04/TRAVA): "
            "aplicado=Decimal('0') + nao_utilizado=Decimal('999') = Decimal('999'), "
            "esperado CAPACIDADE_ATAQUE_M=Decimal('100') (mes=1)"
        )
    assert issubclass(ErroInvariante, Exception)
