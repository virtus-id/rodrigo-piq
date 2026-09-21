"""Testes de `calcular_status_financeiro` — RF-26, AC-37, AC-38, AC-39.

`PISO_CAPACIDADE` classifica `STATUS_FINANCEIRO` em uma das três faixas, mas
`CAPACIDADE_ATAQUE_ATUAL` deriva SOMENTE de `RESULTADO_MENSAL_ATUAL`. Os três
testes de AC cobrem cada faixa do domínio; um quarto verifica o gabarito
`GAB-B` de ponta a ponta com `Parametros` reais.
"""

from datetime import date
from decimal import Decimal

import pytest

from engine.diagnostico import PagamentosEResultados, calcular_status_financeiro
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
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import CONFIABILIDADE_DADOS, STATUS_FINANCEIRO, SimNaoTalvez
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_b

_PERFIL_NEUTRO = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)

_SINAIS_NEUTROS = SinaisComportamentais(
    NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
    MECANISMO_DEFICIT=frozenset(),
    HISTORICO_RECAIDA=SimNaoTalvez.NAO,
    NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
    PACTO="ESTABELECIDO",
    RISCO_IMPULSO="NENHUMA",
    LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
    NECESSIDADE_VITORIA=0,  # T-18: neutro, não dispara INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE
    HISTORICO_ABANDONO=SimNaoTalvez.NAO,
    JANELA_NOVA_DIVIDA=None,  # T-34: NOVA_DIVIDA_PREVISTA=NAO acima, ausência estrutural
)


def _estado(renda: Decimal) -> EstadoFinanceiro:
    """`EstadoFinanceiro` sintético com `RENDA_TOTAL_RECORRENTE` parametrizável
    e o resto neutro — só a renda importa para `PISO_CAPACIDADE` aqui."""
    from engine.estado import TIPO_RENDA

    return EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 9, 1),
        RENDA_TOTAL_RECORRENTE=renda,
        TIPO_RENDA=TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro(0),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro(0),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro(0),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro(0),
        INVENTARIO_COMPLETO=True,
        dividas=(),
        perfil_comportamental=_PERFIL_NEUTRO,
        sinais_comportamentais=_SINAIS_NEUTROS,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=5,  # T-23: neutro, só a renda importa neste teste
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro(0),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(0),
        DINHEIRO_DISPONIVEL=dinheiro(0),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )


def _pagamentos(resultado_mensal_atual: Decimal) -> PagamentosEResultados:
    """`PagamentosEResultados` sintético — só `RESULTADO_MENSAL_ATUAL` importa
    para `calcular_status_financeiro`; os demais campos são neutros/zerados."""
    deficit = dinheiro(0) if resultado_mensal_atual >= dinheiro(0) else -resultado_mensal_atual
    return PagamentosEResultados(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=dinheiro(0),
        PAGAMENTOS_EFETIVOS_DIVIDAS=dinheiro(0),
        RESULTADO_CAIXA_OBSERVADO=resultado_mensal_atual,
        RESULTADO_MENSAL_ATUAL=resultado_mensal_atual,
        GAP_CAIXA_VS_ESTRUTURAL=dinheiro(0),
        DEFICIT_MENSAL=deficit,
        completo=True,
        dividas_com_devido_desconhecido=(),
        dividas_com_efetivo_desconhecido=(),
    )


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


@pytest.mark.regra
def test_AC37_deficit_capacidade_zero() -> None:
    """AC-37: `RESULTADO_MENSAL_ATUAL = -500` ⇒ `DEFICIT` e capacidade 0."""
    parametros = _parametros_reais()
    resultado = calcular_status_financeiro(
        _pagamentos(dinheiro(-500)), _estado(dinheiro(10_000)), parametros
    )
    assertar_exato(resultado.STATUS_FINANCEIRO, STATUS_FINANCEIRO.DEFICIT)
    assertar_exato(resultado.CAPACIDADE_ATAQUE_ATUAL, dinheiro(0))


@pytest.mark.regra
def test_AC38_equilibrio_fragil_capacidade_nao_e_zero_nem_piso() -> None:
    """AC-38: resultado 200, piso 300 ⇒ `EQUILIBRIO_FRAGIL` e capacidade 200
    — nem 0 (piso não zera), nem 300 (piso não eleva)."""
    parametros = _parametros_reais()
    # renda 10.000 × 3% = 300 > P_PISO_CAPACIDADE_ABSOLUTO (100) ⇒ piso 300.
    resultado = calcular_status_financeiro(
        _pagamentos(dinheiro(200)), _estado(dinheiro(10_000)), parametros
    )
    assertar_exato(resultado.PISO_CAPACIDADE, dinheiro(300))
    assertar_exato(resultado.STATUS_FINANCEIRO, STATUS_FINANCEIRO.EQUILIBRIO_FRAGIL)
    assertar_exato(resultado.CAPACIDADE_ATAQUE_ATUAL, dinheiro(200))


@pytest.mark.regra
def test_AC39_capacidade_positiva() -> None:
    """AC-39: resultado 500, piso 300 ⇒ `CAPACIDADE_POSITIVA` e capacidade 500."""
    parametros = _parametros_reais()
    resultado = calcular_status_financeiro(
        _pagamentos(dinheiro(500)), _estado(dinheiro(10_000)), parametros
    )
    assertar_exato(resultado.STATUS_FINANCEIRO, STATUS_FINANCEIRO.CAPACIDADE_POSITIVA)
    assertar_exato(resultado.CAPACIDADE_ATAQUE_ATUAL, dinheiro(500))


@pytest.mark.gabarito
def test_gab_b_piso_status_e_capacidade() -> None:
    """`GAB-B`/AC-06: `PISO_CAPACIDADE` = 300, `STATUS_FINANCEIRO` =
    `EQUILIBRIO_FRAGIL`, `CAPACIDADE_ATAQUE_ATUAL` = 200."""
    from engine.diagnostico import calcular_pagamentos_e_resultados

    estado = carregar_gab_b()
    parametros = _parametros_reais()
    pagamentos = calcular_pagamentos_e_resultados(estado)

    resultado = calcular_status_financeiro(pagamentos, estado, parametros)

    assertar_exato(resultado.PISO_CAPACIDADE, dinheiro(300))
    assertar_exato(resultado.STATUS_FINANCEIRO, STATUS_FINANCEIRO.EQUILIBRIO_FRAGIL)
    assertar_exato(resultado.CAPACIDADE_ATAQUE_ATUAL, dinheiro(200))
