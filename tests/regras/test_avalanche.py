"""Testes de `criar_selecionar_alvo_avalanche` — RF-05 · O-01..O-03 · AC-19 ·
T-49.

Cobre:

1. `test_O01_ordena_por_beneficio_marginal_decrescente` — entre duas
   dívidas elegíveis com benefícios diferentes, a de maior
   `BENEFICIO_MARGINAL_AMORTIZACAO` é escolhida.
2. `test_O01_desempate_por_divida_id` — duas dívidas com o MESMO benefício
   marginal (mesmo saldo/taxa/pagamento, só `DIVIDA_ID` diferente):
   desempate lexicográfico crescente decide.
3. `test_devolve_none_sem_divida_elegivel` — carteira vazia e carteira
   inteiramente quitada devolvem `None`, sem levantar exceção.
4. `test_O02_alvo_fixo_devolvido_sem_recalcular` — com
   `EstadoSimulacao.DIVIDA_ALVO_ATUAL` apontando para uma dívida ainda não
   quitada, a função devolve essa mesma dívida mesmo que outra tivesse
   benefício maior — sem chamar `calcular_beneficio_marginal` (verificado
   por monkeypatch que levantaria se fosse invocado).
5. `test_integracao_minima_via_simular_cenario` — a fábrica usada como
   `sel` de `simular_cenario` (T-46) produz um cenário coerente: a dívida
   de maior benefício marginal (taxa mais alta) é atacada primeiro.

`_divida` segue o padrão de `tests/regras/test_beneficio_marginal.py::_divida`
— `QUITACAO_CONSULTADA=SIM`/`STATUS_VALIDADE_PROPOSTA=VIGENTE` para que
`VALOR_RELEVANTE_PARA_QUITACAO` seja determinístico (`= SALDO_DEVEDOR_ATUAL`
quando igual a `VALOR_QUITACAO_HOJE`, sem cair no fallback de §11.2).

REGRAS: RF-05, O-01, O-02, O-03, AC-19, §5.1, §11.1
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import TIPO_DIVIDA, Divida, EstadoFinanceiro
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
    """Mesmo padrão de `test_beneficio_marginal.py::_divida` — dívida
    completa e válida, `VALOR_RELEVANTE_PARA_QUITACAO` determinístico
    (`QUITACAO_CONSULTADA=SIM`, `STATUS_VALIDADE_PROPOSTA=VIGENTE`,
    `VALOR_QUITACAO_HOJE == SALDO_DEVEDOR_ATUAL`)."""
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


def _estado(
    *,
    saldos: dict[str, Decimal],
    quitadas: frozenset[str] = frozenset(),
    alvo: str | None = None,
) -> EstadoSimulacao:
    return EstadoSimulacao(
        mes=1,
        saldos=saldos,
        quitadas=quitadas,
        DIVIDA_ALVO_ATUAL=alvo,
        CAPACIDADE_ATAQUE_M=dinheiro("100"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )


@pytest.mark.regra
def test_O01_ordena_por_beneficio_marginal_decrescente() -> None:
    """`O-01`: entre duas dívidas elegíveis, a Avalanche escolhe a de maior
    `BENEFICIO_MARGINAL_AMORTIZACAO`. D-ALTA tem taxa bem mais alta que
    D-BAIXA (mesmo saldo/pagamento) — o benefício marginal de amortizar
    D-ALTA é maior."""
    d_baixa = _divida(
        DIVIDA_ID="D-BAIXA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("200"),
    )
    d_alta = _divida(
        DIVIDA_ID="D-ALTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.08"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("200"),
    )
    dividas = {"D-BAIXA": d_baixa, "D-ALTA": d_alta}
    sel = criar_selecionar_alvo_avalanche(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-BAIXA": dinheiro("1000"), "D-ALTA": dinheiro("1000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-ALTA")


@pytest.mark.regra
def test_O01_desempate_por_divida_id() -> None:
    """Critério 2: duas dívidas com exatamente o mesmo
    `BENEFICIO_MARGINAL_AMORTIZACAO` (saldo, taxa e pagamento idênticos) —
    desempate final por `DIVIDA_ID` em ordem alfabética/lexicográfica
    crescente. "D-A" < "D-B" ⇒ "D-A" escolhida, independentemente da ordem
    de inserção no dicionário."""
    comuns = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("600"),
    )
    d_b = _divida(DIVIDA_ID="D-B", **comuns)
    d_a = _divida(DIVIDA_ID="D-A", **comuns)
    # Inserção proposital em ordem "errada" (D-B antes de D-A) — a função
    # não pode depender da ordem de iteração do dict para desempatar.
    dividas = {"D-B": d_b, "D-A": d_a}
    sel = criar_selecionar_alvo_avalanche(dividas, _parametros_reais())

    estado = _estado(saldos={"D-B": dinheiro("1000"), "D-A": dinheiro("1000")}, alvo=None)
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-A")


@pytest.mark.regra
def test_devolve_none_sem_divida_elegivel() -> None:
    """Sem candidata elegível — carteira vazia OU todas quitadas — `sel`
    devolve `None`, nunca levanta exceção."""
    d1 = _divida(DIVIDA_ID="D-01")
    parametros = _parametros_reais()

    sel_vazia = criar_selecionar_alvo_avalanche({}, parametros)
    estado_vazio = _estado(saldos={}, alvo=None)
    assertar_exato(sel_vazia(estado_vazio, dinheiro("100")), None)

    sel_quitada = criar_selecionar_alvo_avalanche({"D-01": d1}, parametros)
    estado_quitado = _estado(
        saldos={"D-01": dinheiro("0")}, quitadas=frozenset({"D-01"}), alvo=None
    )
    assertar_exato(sel_quitada(estado_quitado, dinheiro("100")), None)


@pytest.mark.regra
def test_O02_alvo_fixo_devolvido_sem_recalcular(monkeypatch: pytest.MonkeyPatch) -> None:
    """`O-02`: com `DIVIDA_ALVO_ATUAL` apontando para uma dívida ainda não
    quitada, a função devolve essa mesma dívida sem recalcular a
    ordenação — mesmo que outra candidata tivesse benefício marginal
    maior. Prova reforçada com monkeypatch: se `calcular_beneficio_marginal`
    fosse chamada, o teste falharia (levanta `AssertionError`)."""
    import engine.metodos.avalanche as avalanche_mod

    def _falha_se_chamado(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "calcular_beneficio_marginal não deveria ser chamada quando o "
            "alvo corrente ainda é elegível (O-02: alvo fixo)."
        )

    monkeypatch.setattr(avalanche_mod, "calcular_beneficio_marginal", _falha_se_chamado)

    d_alvo = _divida(
        DIVIDA_ID="D-ALVO",
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),  # benefício baixo
    )
    d_melhor = _divida(
        DIVIDA_ID="D-MELHOR",
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),  # benefício bem maior
    )
    dividas = {"D-ALVO": d_alvo, "D-MELHOR": d_melhor}
    sel = criar_selecionar_alvo_avalanche(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-ALVO": dinheiro("1000"), "D-MELHOR": dinheiro("1000")},
        alvo="D-ALVO",
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-ALVO")


@pytest.mark.regra
def test_integracao_minima_via_simular_cenario() -> None:
    """Integração mínima: a fábrica usada como `sel` de `simular_cenario`
    (T-46) ataca primeiro a dívida de maior benefício marginal (aqui, a de
    taxa mais alta) — `ORDEM_QUITACAO` reflete essa prioridade."""
    d_alta = _divida(
        DIVIDA_ID="D-ALTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("500"),
        VALOR_QUITACAO_HOJE=dinheiro("500"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.10"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_baixa = _divida(
        DIVIDA_ID="D-BAIXA",
        SALDO_DEVEDOR_ATUAL=dinheiro("500"),
        VALOR_QUITACAO_HOJE=dinheiro("500"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-ALTA": d_alta, "D-BAIXA": d_baixa}
    parametros = _parametros_reais()
    sel = criar_selecionar_alvo_avalanche(dividas, parametros)

    classificacao_neutra = ClassificacaoRisco(sinais=(), contagem=0, nivel=NIVEL_RISCO.BAIXO)
    dg = Diagnostico(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=dinheiro("0"),
        PAGAMENTOS_EFETIVOS_DIVIDAS=dinheiro("0"),
        RESULTADO_CAIXA_OBSERVADO=dinheiro("0"),
        RESULTADO_MENSAL_ATUAL=dinheiro("0"),
        GAP_CAIXA_VS_ESTRUTURAL=dinheiro("0"),
        DEFICIT_MENSAL=dinheiro("0"),
        PISO_CAPACIDADE=dinheiro("0"),
        STATUS_FINANCEIRO=STATUS_FINANCEIRO.CAPACIDADE_POSITIVA,
        MODO_ESTABILIZACAO=False,
        GAP_AUTOPERCEPCAO=False,
        BASE_CONSERVADORA=dinheiro("100"),
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=dinheiro("100"),
        CAPACIDADE_ATAQUE_CONSERVADORA=dinheiro("100"),
        CAPACIDADE_ATAQUE_POTENCIAL=dinheiro("100"),
        NIVEL_CONTROLE=NIVEL_CONTROLE.FORTE,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=False,
        classificacao_risco_recaida=classificacao_neutra,
        classificacao_risco_comportamental_geral=classificacao_neutra,
        # T-90/OQ-23: contrato de tipo/posição, sem valor de negócio real.
        RESERVA_MOBILIZAVEL=dinheiro("0"),
        ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("0"),
    )

    from engine.estado import (
        COBERTURA_MEIOS_PAGAMENTO,
        COBERTURA_PEQUENOS_GASTOS,
        CONHECIMENTO_GASTO,
        DEFASAGEM_REGISTRO,
        DISPOSICAO_USO_RESERVA,
        FREQUENCIA_REGISTRO,
        GASTOS_NAO_IDENTIFICADOS,
        REGISTRO_GASTOS,
        RESERVA_EXISTE,
        REVISAO_SEMANAL,
        PerfilComportamental,
        SinaisComportamentais,
    )
    from engine.estado import TIPO_RENDA as _TIPO_RENDA

    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    sinais = SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
        MECANISMO_DEFICIT=frozenset(),
        HISTORICO_RECAIDA=SimNaoTalvez.NAO,
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
        PACTO="ESTABELECIDO",
        RISCO_IMPULSO="NENHUMA",
        LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
        NECESSIDADE_VITORIA=0,
        HISTORICO_ABANDONO=SimNaoTalvez.NAO,
        JANELA_NOVA_DIVIDA=None,
    )
    e = EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 1, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("0"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("0"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("0"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("0"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(),
        perfil_comportamental=perfil,
        sinais_comportamentais=sinais,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=0,
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro("0"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro("0"),
        DINHEIRO_DISPONIVEL=dinheiro("0"),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )

    cenario = simular_cenario(e, dg, dividas, sel, parametros)

    # D-ALTA (maior benefício marginal, taxa 10%) é atacada primeiro e
    # quita antes de D-BAIXA (taxa 1%) — a Avalanche prioriza o maior
    # custo evitado por real amortizado.
    assertar_exato(cenario.ORDEM_QUITACAO[0], "D-ALTA")
    assertar_exato(set(cenario.ORDEM_QUITACAO), {"D-ALTA", "D-BAIXA"})
