"""Testes de `engine/troca.py::calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE` —
RF-11 · `T-01`/`T-02` (nomenclatura da spec) · `T-71` (tarefa do backlog).

Casos unitários da FUNÇÃO — não o gabarito `GAB-05` completo (quitação de
R$ 30.000 por operação de R$ 40.000), que é `T-72`, tarefa separada e
dependente desta. Mesmo padrão de helpers de `test_simular_cenario.py`
(`_diagnostico`/`_estado_financeiro_neutro`/`_parametros`), reaproveitado
aqui porque `calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE` delega a
`simular_cenario` internamente sobre uma dívida sintética isolada.

`_sel_trivial` é o `SelecionarAlvo` de teste: como cada simulação desta
tarefa tem sempre uma única dívida (a sintética montada por
`engine/troca.py`, ou a dívida antiga no teste de comparação), não há
ranqueamento real a fazer — só devolver a única candidata não quitada.

REGRAS: RF-11, T-01, T-02
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
from engine.diagnostico import Diagnostico
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
    TIPO_DIVIDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.estado import TIPO_RENDA as _TIPO_RENDA
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
    DinheiroTalvez,
    SimNaoTalvez,
)
from engine.troca import (
    ErroDinheiroNovoNegativo,
    OperacaoTroca,
    calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE,
)
from tests.conftest import assertar_exato


def _diagnostico(*, capacidade_conservadora: DinheiroTalvez) -> Diagnostico:
    """Mesmo helper de `test_simular_cenario.py::_diagnostico` — só
    `CAPACIDADE_ATAQUE_CONSERVADORA` é lido por `simular_cenario`."""
    classificacao_neutra = ClassificacaoRisco(sinais=(), contagem=0, nivel=NIVEL_RISCO.BAIXO)
    return Diagnostico(
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
        BASE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_POTENCIAL=capacidade_conservadora,  # type: ignore[arg-type]
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


def _estado_financeiro_neutro() -> EstadoFinanceiro:
    """Mesmo helper de `test_simular_cenario.py::_estado_financeiro_neutro`
    — `simular_cenario` não lê `e` nesta cadeia de tarefas (`noqa: ARG001`)."""
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
    return EstadoFinanceiro(
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


def _parametros(*, horizonte_maximo_anos: int = 10, horizonte_alerta_anos: int = 5) -> Parametros:
    """Mesmo helper de `test_simular_cenario.py::_parametros`."""
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={
            "P_HORIZONTE_MAXIMO_SIMULACAO": Decimal(horizonte_maximo_anos),
            "P_HORIZONTE_ALERTA": Decimal(horizonte_alerta_anos),
        },
    )


def _sel_trivial(estado: EstadoSimulacao, _delta: DinheiroTalvez) -> Divida | None:
    """`SelecionarAlvo` para uma simulação de UMA dívida isolada: devolve a
    única candidata ainda não quitada — não há ranqueamento real a fazer.
    Cada chamada de `calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE` simula um
    Mapping de um único `DIVIDA_ID` (ver `engine/troca.py`), então
    `estado.saldos` sempre tem, no máximo, uma chave não quitada."""
    candidatos = tuple(
        divida_id for divida_id in estado.saldos if divida_id not in estado.quitadas
    )
    if not candidatos:
        return None
    (unica_id,) = candidatos
    return Divida(
        DIVIDA_ID=unica_id,
        TIPO_DIVIDA=TIPO_DIVIDA.OUTRA,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=estado.saldos[unica_id],
        VALOR_QUITACAO_HOJE=estado.saldos[unica_id],
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        CET=dinheiro("0"),
        PARCELA_CONTRATUAL=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


# ---------------------------------------------------------------------------
# Critério 1 — o cenário equivalente é calculado apenas sobre o valor
# efetivamente substituído (não sobre SALDO_NOVA_OPERACAO).
# ---------------------------------------------------------------------------
def test_cenario_equivalente_usa_apenas_o_valor_substituido() -> None:
    # Dívida antiga de 30.000, nova operação de 40.000 (10.000 de dinheiro
    # novo). O cenário equivalente deve simular exatamente 30.000 — nunca
    # 40.000 — como saldo de abertura.
    operacao = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("40000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("1000"),
    )
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    resultado = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-ANTIGA", operacao, estado, dg, _sel_trivial, p
    )

    # Pagamento (1000) é rateado proporcionalmente ao saldo de cada
    # componente dentro do saldo total contratado (40.000): a parcela
    # substituída (30.000) recebe 30000/40000 * 1000 = 750/mês.
    pagamento_proporcional_equivalente = dinheiro("30000") * dinheiro("1000") / dinheiro("40000")
    saldo_esperado_apos_mes_1 = dinheiro("30000") - pagamento_proporcional_equivalente

    primeiro_mes = resultado.cenario_equivalente.meses[0]
    (saldo_obtido,) = primeiro_mes.estado_final.saldos.values()
    # Se o cenário equivalente tivesse simulado 40.000 (o total da nova
    # operação, em vez de só o valor substituído), o saldo de abertura já
    # divergiria do valor esperado abaixo.
    assertar_exato(saldo_obtido, saldo_esperado_apos_mes_1)


# ---------------------------------------------------------------------------
# Critério 2 — DINHEIRO_NOVO entra como novo endividamento (componente
# identificável e separado) e NUNCA reduz o custo comparado do cenário
# equivalente.
# ---------------------------------------------------------------------------
def test_dinheiro_novo_e_endividamento_separado_e_identificavel() -> None:
    operacao_com_dinheiro_novo = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("40000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("4000"),
    )
    # Mesma taxa e mesmo pagamento POR REAL EMPRESTADO (10% do saldo/mês),
    # sem dinheiro novo — usada como controle: se DINHEIRO_NOVO não
    # contaminar o cenário equivalente, os dois devem produzir o MESMO
    # CUSTO_FUTURO_TOTAL para a parte substituída.
    operacao_sem_dinheiro_novo = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("30000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("3000"),
    )
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    resultado = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-ANTIGA", operacao_com_dinheiro_novo, estado, dg, _sel_trivial, p
    )
    resultado_controle = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-ANTIGA", operacao_sem_dinheiro_novo, estado, dg, _sel_trivial, p
    )

    assertar_exato(resultado.DINHEIRO_NOVO, dinheiro("10000"))
    assert resultado.cenario_dinheiro_novo is not None, (
        "DINHEIRO_NOVO > 0 deve produzir um cenário separado e identificável"
    )
    assertar_exato(resultado_controle.cenario_dinheiro_novo, None)
    # O CUSTO_FUTURO_TOTAL do cenário equivalente é o MESMO com ou sem
    # dinheiro novo, para a mesma parcela substituída — prova de que
    # DINHEIRO_NOVO nunca reduz (nem aumenta) o custo comparado do cenário
    # equivalente: ele só existe no cenário separado.
    assertar_exato(
        resultado.cenario_equivalente.CUSTO_FUTURO_TOTAL,
        resultado_controle.cenario_equivalente.CUSTO_FUTURO_TOTAL,
    )


def test_dinheiro_novo_zero_nao_produz_cenario_separado() -> None:
    """Troca sem dinheiro na mão (SALDO_NOVA_OPERACAO == VALOR_SUBSTITUIDO):
    nada a isolar, `cenario_dinheiro_novo` é `None`."""
    operacao = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("30000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("3000"),
    )
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    resultado = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-ANTIGA", operacao, estado, dg, _sel_trivial, p
    )

    assertar_exato(resultado.DINHEIRO_NOVO, dinheiro("0"))
    assertar_exato(resultado.cenario_dinheiro_novo, None)


def test_saldo_nova_operacao_menor_que_substituido_e_erro() -> None:
    """`T-01`: `DINHEIRO_NOVO` é sempre >= 0 — dado inconsistente é recusado
    ruidosamente, nunca tolerado como "dinheiro novo negativo"."""
    operacao = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("20000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("2000"),
    )
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    try:
        calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
            "D-ANTIGA", operacao, estado, dg, _sel_trivial, p
        )
    except ErroDinheiroNovoNegativo:
        pass
    else:
        raise AssertionError("SALDO_NOVA_OPERACAO < VALOR_SUBSTITUIDO deveria levantar erro")


# ---------------------------------------------------------------------------
# Critério 3 — o resultado é comparável ao cenário sem troca, mês a mês.
# ---------------------------------------------------------------------------
def test_cenario_equivalente_e_comparavel_mes_a_mes_ao_cenario_sem_troca() -> None:
    """Simula a dívida ANTIGA isolada (cenário "sem troca", via
    `simular_cenario` diretamente — a mesma função usada por qualquer outro
    cenário do motor) e compara, posição a posição de `.meses`, contra o
    `cenario_equivalente` de uma troca "neutra" (mesma taxa, mesmo
    pagamento, sem dinheiro novo): os dois têm a MESMA granularidade
    (`ResultadoMes` a `ResultadoMes`) e, neste caso simétrico, a MESMA
    trajetória de saldo mês a mês."""
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    divida_antiga = Divida(
        DIVIDA_ID="D-ANTIGA",
        TIPO_DIVIDA=TIPO_DIVIDA.OUTRA,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("30000"),
        VALOR_QUITACAO_HOJE=dinheiro("30000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        CET=dinheiro("0"),
        PARCELA_CONTRATUAL=dinheiro("3000"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("3000"),  # proporcional ao pagamento do outro
        # caso: 4000 * 30000/40000
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=True,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
    cenario_sem_troca = simular_cenario(estado, dg, {"D-ANTIGA": divida_antiga}, _sel_trivial, p)

    operacao = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("30000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("3000"),
    )
    resultado = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-ANTIGA", operacao, estado, dg, _sel_trivial, p
    )
    cenario_equivalente = resultado.cenario_equivalente

    # Mesma granularidade — mesmo número de meses, comparável posição a
    # posição (ResultadoMes a ResultadoMes).
    assertar_exato(len(cenario_equivalente.meses), len(cenario_sem_troca.meses))
    for mes_equivalente, mes_sem_troca in zip(
        cenario_equivalente.meses, cenario_sem_troca.meses, strict=True
    ):
        (saldo_equivalente,) = mes_equivalente.estado_final.saldos.values()
        (saldo_sem_troca,) = mes_sem_troca.estado_final.saldos.values()
        assertar_exato(saldo_equivalente, saldo_sem_troca)
    assertar_exato(cenario_equivalente.PRAZO_TOTAL, cenario_sem_troca.PRAZO_TOTAL)
    assertar_exato(cenario_equivalente.CUSTO_FUTURO_TOTAL, cenario_sem_troca.CUSTO_FUTURO_TOTAL)


# ---------------------------------------------------------------------------
# Critério 4 — o módulo cita T-01 e T-02 explicitamente.
# ---------------------------------------------------------------------------
def test_modulo_cita_regras_t01_t02() -> None:
    import engine.troca as troca_modulo

    assertar_exato("T-01" in troca_modulo.REGRAS, True)
    assertar_exato("T-02" in troca_modulo.REGRAS, True)
    assertar_exato("RF-11" in troca_modulo.REGRAS, True)
