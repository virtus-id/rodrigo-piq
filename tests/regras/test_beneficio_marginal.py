"""Testes de `calcular_beneficio_marginal` e `determinar_ordem_status_por_origem`
— RF-05, RF-21 · §11.1 · AC-19, AC-33 · T-41.

Formaliza a verificação ad-hoc que T-39 (implementação) e T-40 (fallback +
`ORDEM_STATUS`) já fizeram e descartaram, cobrindo:

1. `test_AC19_formula_do_beneficio_marginal` — fórmula normativa exata,
   calculada de forma independente (aritmética Decimal escrita só neste
   teste, sem reaproveitar `engine/beneficio_marginal.py`).
2. `test_AC33_fallback_por_taxa_e_ordem_provisoria` — dado insuficiente para
   simular (`PAGAMENTO_MENSAL_EFETIVO` desconhecido) mas taxa presente ⇒
   `origem="FALLBACK_TAXA"` e `ORDEM_STATUS.PROVISORIA`.
3. `test_AC33_fallback_por_cet_quando_taxa_tambem_desconhecida` — taxa
   também ausente, só `CET` disponível ⇒ `origem="FALLBACK_CET"` e
   `ORDEM_STATUS.PROVISORIA` (fallback de 2º nível).
4. `test_caso_extremo_sem_simulacao_taxa_ou_cet_e_indisponivel` — nem
   simulação, nem taxa, nem `CET` ⇒ `origem="INDISPONIVEL"`,
   `BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO` (nunca fabricado) e
   `ORDEM_STATUS.PROVISORIA`.
5. `test_simulacao_bem_sucedida_e_definitiva_na_data` — dados completos,
   nenhuma trajetória estoura horizonte ⇒ `origem="SIMULACAO"` e
   `ORDEM_STATUS.DEFINITIVA_NA_DATA`.
"""

from decimal import Decimal

import pytest

from engine.beneficio_marginal import (
    calcular_beneficio_marginal,
    determinar_ordem_status_por_origem,
)
from engine.estado import TIPO_DIVIDA, Divida
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import (
    DESCONHECIDO,
    ORDEM_STATUS,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
    """Dívida "de referência" — todos os campos obrigatórios preenchidos com
    dado completo por padrão; cada teste sobrescreve só o que precisa para
    montar seu cenário (mesmo padrão de `tests/regras/test_gates.py::_divida`)."""
    base: dict[str, object] = dict(
        DIVIDA_ID="D-01",
        TIPO_DIVIDA=TIPO_DIVIDA.CONSIGNADO,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        CET=Decimal("0.05"),
        PARCELA_CONTRATUAL=dinheiro("600"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("600"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
    base.update(overrides)
    return Divida(**base)  # type: ignore[arg-type]


@pytest.mark.regra
def test_AC19_formula_do_beneficio_marginal() -> None:
    """AC-19: `BENEFICIO_MARGINAL_AMORTIZACAO = (DESEMBOLSO_FUTURO_SEM_DELTA
    - DESEMBOLSO_FUTURO_COM_DELTA) / DELTA_REALMENTE_APLICADO`.

    Cenário: saldo R$ 1.000, taxa 5% a.m., pagamento nominal R$ 600,
    `delta_disponivel` = R$ 200. As duas trajetórias quitam em 2 meses —
    valores calculados aqui à mão, com aritmética Decimal independente da
    implementação sob teste (nenhuma chamada a `simular_trajetoria_isolada`
    nem a qualquer função interna de `engine/beneficio_marginal.py`):

    Trajetória A (sem delta):
      mês1: saldo = 1000*1.05 = 1050; pag = min(600,1050) = 600; saldo = 450
      mês2: saldo =  450*1.05 =  472.5; pag = min(600,472.5)=472.5; saldo=0
      DESEMBOLSO_FUTURO_SEM_DELTA = 600 + 472.5 = 1072.5

    Trajetória B (com delta=200 só no mês1 ⇒ pagamento nominal mês1 = 800):
      mês1: saldo = 1000*1.05 = 1050; pag = min(800,1050) = 800; saldo = 250
      mês2: saldo =  250*1.05 =  262.5; pag = min(600,262.5)=262.5; saldo=0
      DESEMBOLSO_FUTURO_COM_DELTA = 800 + 262.5 = 1062.5

    DELTA_REALMENTE_APLICADO = pagamento_efetivo_mes1_B - PAGAMENTO_MENSAL_EFETIVO
                              = 800 - 600 = 200 (delta integralmente aplicado,
                                saldo pós-juros do mês1, 1050, > 800)

    BENEFICIO_MARGINAL_AMORTIZACAO = (1072.5 - 1062.5) / 200 = 10 / 200 = 0.05
    """
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("600"),
    )
    parametros = _parametros_reais()
    delta_disponivel = dinheiro("200")

    resultado = calcular_beneficio_marginal(divida, delta_disponivel, parametros)

    desembolso_sem_delta_esperado = dinheiro("1072.5")
    desembolso_com_delta_esperado = dinheiro("1062.5")
    delta_aplicado_esperado = dinheiro("200")
    beneficio_esperado = (
        desembolso_sem_delta_esperado - desembolso_com_delta_esperado
    ) / delta_aplicado_esperado

    assertar_exato(resultado.origem, "SIMULACAO")
    assertar_exato(resultado.DESEMBOLSO_FUTURO_SEM_DELTA, desembolso_sem_delta_esperado)
    assertar_exato(resultado.DESEMBOLSO_FUTURO_COM_DELTA, desembolso_com_delta_esperado)
    assertar_exato(resultado.DELTA_REALMENTE_APLICADO, delta_aplicado_esperado)
    assertar_exato(resultado.BENEFICIO_MARGINAL_AMORTIZACAO, beneficio_esperado)
    assertar_exato(resultado.BENEFICIO_MARGINAL_AMORTIZACAO, Decimal("0.05"))


@pytest.mark.regra
def test_AC33_fallback_por_taxa_e_ordem_provisoria() -> None:
    """AC-33/RF-21: `PAGAMENTO_MENSAL_EFETIVO = DESCONHECIDO` torna a
    simulação impossível (`ChaveTrajetoria` exige os três campos concretos),
    mas `TAXA_EFETIVA_MENSAL_NORMALIZADA` está presente — fallback de 1º
    nível. `origem="FALLBACK_TAXA"` e, via `determinar_ordem_status_por_origem`,
    `ORDEM_STATUS.PROVISORIA`."""
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.03"),
        CET=Decimal("0.035"),
        PAGAMENTO_MENSAL_EFETIVO=DESCONHECIDO,
    )
    parametros = _parametros_reais()

    resultado = calcular_beneficio_marginal(divida, dinheiro("200"), parametros)

    assertar_exato(resultado.origem, "FALLBACK_TAXA")
    assertar_exato(resultado.BENEFICIO_MARGINAL_AMORTIZACAO, Decimal("0.03"))
    assertar_exato(determinar_ordem_status_por_origem(resultado.origem), ORDEM_STATUS.PROVISORIA)


@pytest.mark.regra
def test_AC33_fallback_por_cet_quando_taxa_tambem_desconhecida() -> None:
    """RF-21, fallback de 2º nível: `PAGAMENTO_MENSAL_EFETIVO` E
    `TAXA_EFETIVA_MENSAL_NORMALIZADA` desconhecidos (simulação impossível e
    fallback de 1º nível também indisponível), mas `CET` presente.
    `origem="FALLBACK_CET"` e `ORDEM_STATUS.PROVISORIA`."""
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=DESCONHECIDO,
        CET=Decimal("0.04"),
        PAGAMENTO_MENSAL_EFETIVO=DESCONHECIDO,
    )
    parametros = _parametros_reais()

    resultado = calcular_beneficio_marginal(divida, dinheiro("200"), parametros)

    assertar_exato(resultado.origem, "FALLBACK_CET")
    assertar_exato(resultado.BENEFICIO_MARGINAL_AMORTIZACAO, Decimal("0.04"))
    assertar_exato(determinar_ordem_status_por_origem(resultado.origem), ORDEM_STATUS.PROVISORIA)


@pytest.mark.regra
def test_caso_extremo_sem_simulacao_taxa_ou_cet_e_indisponivel() -> None:
    """Caso extremo (extensão desta implementação, docstring do módulo):
    nem simulação (`PAGAMENTO_MENSAL_EFETIVO` desconhecido), nem taxa, nem
    `CET` disponíveis ⇒ `origem="INDISPONIVEL"`,
    `BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO` — nunca um número
    fabricado — e `ORDEM_STATUS.PROVISORIA`."""
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=DESCONHECIDO,
        CET=DESCONHECIDO,
        PAGAMENTO_MENSAL_EFETIVO=DESCONHECIDO,
    )
    parametros = _parametros_reais()

    resultado = calcular_beneficio_marginal(divida, dinheiro("200"), parametros)

    assertar_exato(resultado.origem, "INDISPONIVEL")
    assertar_exato(resultado.BENEFICIO_MARGINAL_AMORTIZACAO, DESCONHECIDO)
    assertar_exato(determinar_ordem_status_por_origem(resultado.origem), ORDEM_STATUS.PROVISORIA)


@pytest.mark.regra
def test_simulacao_bem_sucedida_e_definitiva_na_data() -> None:
    """Dados completos, nenhuma trajetória estoura o horizonte ⇒
    `origem="SIMULACAO"` e, via `determinar_ordem_status_por_origem`,
    `ORDEM_STATUS.DEFINITIVA_NA_DATA`."""
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("600"),
    )
    parametros = _parametros_reais()

    resultado = calcular_beneficio_marginal(divida, dinheiro("200"), parametros)

    assertar_exato(resultado.origem, "SIMULACAO")
    assertar_exato(
        determinar_ordem_status_por_origem(resultado.origem), ORDEM_STATUS.DEFINITIVA_NA_DATA
    )
