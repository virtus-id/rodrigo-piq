"""Testes da família M — ciclo mensal canônico em 12 passos (`M-01`..`M-12`).

RF-01, §2: cada teste é nomeado com o ID da regra `M-*` que exercita e
verifica saída OBSERVÁVEL de `simular_cenario` (`Cenario`/`ResultadoMes`) —
nunca chama `executar_mes` isoladamente nem inspeciona estado interno. Mesmo
padrão de helpers de `tests/regras/test_simular_cenario.py`
(`_divida`/`_parametros`/`_diagnostico`/`_estado_financeiro_neutro`/
`_SelPorMenorSaldo`), reaproveitado aqui em vez de reinventado — `T-47`
testa através da mesma superfície pública, `simular_cenario`.

REGRAS: RF-01, M-01, M-02, M-03, M-04, M-05, M-06, M-07, M-08, M-09, M-10,
M-11, M-12, AC-13, AC-14
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import TIPO_DIVIDA, Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
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
    """Mesmo helper de `test_ciclo_mensal.py`/`test_simular_cenario.py` —
    dívida completa e válida, variando só saldo/taxa/pagamento."""
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


def _parametros(*, horizonte_maximo_anos: int = 10, horizonte_alerta_anos: int = 5) -> Parametros:
    """Mesmo helper de `test_simular_cenario.py` — valores default iguais
    aos de `parameters/parametros-1.0.1.json` (10 anos / 5 anos)."""
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={
            "P_HORIZONTE_MAXIMO_SIMULACAO": Decimal(horizonte_maximo_anos),
            "P_HORIZONTE_ALERTA": Decimal(horizonte_alerta_anos),
        },
    )


def _diagnostico(*, capacidade_conservadora: DinheiroTalvez) -> Diagnostico:
    """`simular_cenario` só lê `CAPACIDADE_ATAQUE_CONSERVADORA` de
    `Diagnostico` — os demais campos são neutros."""
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
    """`simular_cenario` não lê `e` (parte do contrato do plano) — instância
    mínima só para satisfazer a assinatura."""
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


@dataclass
class _ChamadaSel:
    delta: DinheiroTalvez
    candidatos: tuple[str, ...]


@dataclass
class _SelPorMenorSaldo:
    """Mesmo `SelecionarAlvo` de teste de `test_simular_cenario.py` — escolhe,
    entre as dívidas NÃO quitadas, a de menor saldo. Grava cada chamada para
    provar `AC-13`/`M-07` (quando reranqueia e quando não)."""

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


# ---------------------------------------------------------------------------
# M-02 — juros, encargos e evolução contratual aplicados ao saldo de abertura
# antes de qualquer pagamento (§9, segundo dos doze passos).
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_M02_juros_evoluem_saldo_antes_do_pagamento() -> None:
    # Saldo 1000, taxa de 10% ao mês, capacidade 0 (só evolução de juros):
    # 1000 * 1.10 = 1100 no mês 1. Pagamento normal = efetivo (0) ⇒ não abate.
    d1 = _divida("D-01", saldo=dinheiro("1000"), taxa=dinheiro("0.10"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    assertar_exato(cenario.meses[0].estado_final.saldos["D-01"], dinheiro("1100"))


# ---------------------------------------------------------------------------
# M-03 — pagamento mensal normal de dívida não-alvo, limitado ao saldo.
# ---------------------------------------------------------------------------
def test_M03_pagamento_normal_nao_alvo_limitado_ao_saldo() -> None:
    # D-01 (não-alvo, menor saldo é D-02) tem saldo residual 50 e pagamento
    # normal contratado de 200 — limitado ao saldo restante (50), nunca
    # negativo.
    d1 = _divida("D-01", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("200"))
    d2 = _divida("D-02", saldo=dinheiro("10"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("10"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-02 é o alvo (menor saldo) e quita no mês 1 com a capacidade de 10.
    # D-01 (não-alvo) recebe o pagamento normal de 200, limitado ao saldo 50
    # ⇒ quita também no mês 1, sem saldo negativo.
    assertar_exato(set(cenario.meses[0].quitacoes), {"D-01", "D-02"})
    assertar_exato(cenario.meses[0].estado_final.saldos["D-01"], dinheiro("0"))


# ---------------------------------------------------------------------------
# M-04 — ataque adicional aplicado à DIVIDA_ALVO_ATUAL (pagamento normal +
# capacidade de ataque do mês).
# ---------------------------------------------------------------------------
def test_M04_ataque_adicional_aplicado_ao_alvo() -> None:
    d1 = _divida("D-01", saldo=dinheiro("150"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Mês 1: ataque de 100 sobre saldo 150 ⇒ resta 50. Ainda não quita.
    assertar_exato(cenario.meses[0].estado_final.saldos["D-01"], dinheiro("50"))
    assertar_exato(cenario.meses[0].quitacoes, ())


# ---------------------------------------------------------------------------
# M-05 — sem quitação do alvo no mês, DIVIDA_ALVO_ATUAL é preservado para o
# mês seguinte, sem reranqueamento (AC-13).
# ---------------------------------------------------------------------------
def test_M05_alvo_nao_quitado_e_preservado_para_o_mes_seguinte() -> None:
    d1 = _divida("D-01", saldo=dinheiro("1000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-01 leva 10 meses para quitar (1000/100) — nos primeiros 9 meses o
    # alvo permanece D-01, sem reranqueamento (única chamada a `sel` é o
    # bootstrap do mês 1).
    assertar_exato(len(sel.chamadas), 1)
    for resultado_mes in cenario.meses[:-1]:
        assertar_exato(resultado_mes.estado_final.DIVIDA_ALVO_ATUAL, "D-01")


# ---------------------------------------------------------------------------
# M-06 — dívida quitada dispara RESIDUO_ATAQUE_M; inclui a que se encerra só
# com pagamento normal (EC-02), fora do escopo direto de M-06 mas coberto
# pelo mesmo passo (M-05/M-06 juntos na fonte normativa).
# ---------------------------------------------------------------------------
def test_M06_quitacao_do_alvo_calcula_residuo() -> None:
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Ataque de 100 sobre saldo 40 ⇒ quita com sobra de 60 (RESIDUO_ATAQUE_M),
    # sem dívida elegível para receber a cascata (única dívida do cenário).
    assertar_exato(set(cenario.meses[0].quitacoes), {"D-01"})
    assertar_exato(cenario.meses[0].RESIDUO_ATAQUE_M, dinheiro("60"))
    assertar_exato(cenario.meses[0].ATAQUE_NAO_UTILIZADO, dinheiro("60"))


# ---------------------------------------------------------------------------
# M-07 — nomeado explicitamente pela tarefa: havendo RESIDUO_ATAQUE_M > 0,
# reranqueia ANTES de aplicar o resíduo à nova dívida-alvo.
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_M07_residuo_reranqueia_antes_de_aplicar() -> None:
    # D-01 (alvo, menor saldo) quita com sobra; D-02 é a única candidata
    # remanescente e recebe o resíduo via reranqueamento (M-07).
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    # Ataque de 100 sobre D-01 (saldo 40) ⇒ quita, resíduo = 60.
    assertar_exato(mes_1.RESIDUO_ATAQUE_M, dinheiro("60"))
    # O reranqueamento (evento registrado) ocorreu ANTES da aplicação do
    # resíduo — prova observável: exatamente um reranqueamento e uma
    # aplicação de resíduo neste mês, e a aplicação recaiu sobre a dívida
    # que o reranqueamento selecionou (D-02, única candidata elegível).
    assertar_exato(len(mes_1.reranqueamentos), 1)
    assertar_exato(mes_1.reranqueamentos[0].novo_alvo, "D-02")
    assertar_exato(len(mes_1.aplicacoes_residuo), 1)
    assertar_exato(mes_1.aplicacoes_residuo[0].DIVIDA_ID, "D-02")
    assertar_exato(mes_1.aplicacoes_residuo[0].valor_aplicado, dinheiro("60"))
    # Saldo observável de D-02 reflete o resíduo aplicado no mesmo mês.
    assertar_exato(mes_1.estado_final.saldos["D-02"], dinheiro("440"))
    # O delta passado à segunda chamada a `sel` (reranqueamento) é o
    # resíduo remanescente (60), nunca a capacidade cheia do mês (100) —
    # AC-14, comportamento observável via a instrumentação de `sel`.
    assertar_exato(sel.chamadas[-1].delta, dinheiro("60"))


# ---------------------------------------------------------------------------
# M-08 — repete o passo 7 enquanto houver resíduo E houver dívida elegível
# (cascata dupla: duas quitações em cascata no mesmo mês).
# ---------------------------------------------------------------------------
def test_M08_cascata_repete_enquanto_houver_residuo_e_elegivel() -> None:
    d1 = _divida("D-01", saldo=dinheiro("10"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("20"), pagamento_mensal_efetivo=dinheiro("0"))
    d3 = _divida("D-03", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2, "D-03": d3}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    # D-01 (10) quita com ataque de 100 ⇒ resíduo 90. Cascata: D-02 (20) é
    # o novo alvo, quita com 20 ⇒ resíduo 70. Segunda rodada: D-03 (500)
    # recebe os 70 restantes, não quita. Duas rodadas de cascata.
    assertar_exato(set(mes_1.quitacoes), {"D-01", "D-02"})
    assertar_exato(len(mes_1.reranqueamentos), 2)
    assertar_exato(len(mes_1.aplicacoes_residuo), 2)
    assertar_exato(mes_1.aplicacoes_residuo[0].DIVIDA_ID, "D-02")
    assertar_exato(mes_1.aplicacoes_residuo[0].valor_aplicado, dinheiro("20"))
    assertar_exato(mes_1.aplicacoes_residuo[1].DIVIDA_ID, "D-03")
    assertar_exato(mes_1.aplicacoes_residuo[1].valor_aplicado, dinheiro("70"))
    assertar_exato(mes_1.estado_final.saldos["D-03"], dinheiro("430"))
    assertar_exato(mes_1.ATAQUE_NAO_UTILIZADO, dinheiro("0"))


# ---------------------------------------------------------------------------
# M-09 — encerramento do mês: cada mês simulado produz exatamente um
# ResultadoMes consolidado, na ordem cronológica (Cenario.meses).
# ---------------------------------------------------------------------------
def test_M09_encerramento_do_mes_produz_um_resultado_por_mes() -> None:
    d1 = _divida("D-01", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("50"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-01 quita no mês 1, D-02 no mês 2: dois ResultadoMes, um por mês.
    assertar_exato(len(cenario.meses), 2)
    assertar_exato(cenario.meses[0].estado_final.mes, 1)
    assertar_exato(cenario.meses[1].estado_final.mes, 2)


# ---------------------------------------------------------------------------
# M-10 — consolida o VALOR_FLUXO_LIBERADO de toda dívida quitada no mês.
# ---------------------------------------------------------------------------
def test_M10_consolida_fluxo_liberado_das_quitadas_no_periodo() -> None:
    d1 = _divida("D-01", saldo=dinheiro("30"), pagamento_mensal_efetivo=dinheiro("30"))
    d2 = _divida("D-02", saldo=dinheiro("1000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-01 é o alvo (menor saldo) e quita no mês 1 (pagamento normal do
    # alvo 30 + capacidade 100 = 130, aplicado = 30 ⇒ libera 30, o
    # PAGAMENTO_MENSAL_EFETIVO de fato, consolidado em VALOR_FLUXO_LIBERADO).
    assertar_exato(set(cenario.meses[0].quitacoes), {"D-01"})
    assertar_exato(cenario.meses[0].VALOR_FLUXO_LIBERADO, dinheiro("30"))


# ---------------------------------------------------------------------------
# M-11 — o fluxo liberado consolidado no mês N só é incorporado à
# capacidade de ataque a partir de m+1.
# ---------------------------------------------------------------------------
def test_M11_fluxo_liberado_incorporado_somente_a_partir_de_m_mais_1() -> None:
    d1 = _divida("D-01", saldo=dinheiro("700"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("2000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Mês 1: capacidade permanece 100 (o fluxo liberado de D-01 não reforça
    # o próprio mês). Mês 2: capacidade sobe para 100 + 700 = 800.
    assertar_exato(cenario.meses[0].estado_final.CAPACIDADE_ATAQUE_M, dinheiro("100"))
    assertar_exato(cenario.meses[1].estado_final.CAPACIDADE_ATAQUE_M, dinheiro("800"))


# ---------------------------------------------------------------------------
# M-12 — a ordem só é reavaliada quando houve quitação no período (ou
# evento externo material, fora do escopo desta tarefa); sem quitação,
# DIVIDA_ALVO_ATUAL é preservado (mesmo comportamento coberto por AC-13).
# ---------------------------------------------------------------------------
def test_M12_reavaliacao_da_ordem_so_ocorre_apos_quitacao() -> None:
    d1 = _divida("D-01", saldo=dinheiro("300"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # 300/100 = 3 meses. Mês 1: bootstrap chama `sel` uma vez. Meses 2 e 3
    # não quitam nada (mês 2) ou quitam no fim (mês 3) — nenhuma chamada
    # extra a `sel` ocorre antes da quitação efetiva.
    assertar_exato(len(sel.chamadas), 1)
    assertar_exato(cenario.meses[0].estado_final.DIVIDA_ALVO_ATUAL, "D-01")
    assertar_exato(cenario.meses[1].estado_final.DIVIDA_ALVO_ATUAL, "D-01")


# ---------------------------------------------------------------------------
# AC-14 (complementar a M-07/M-08) — o delta do reranqueamento por resíduo é
# sempre o resíduo remanescente, nunca a capacidade cheia do mês.
# ---------------------------------------------------------------------------
def test_AC14_delta_do_reranqueamento_por_residuo_nunca_e_a_capacidade_cheia() -> None:
    d1 = _divida("D-01", saldo=dinheiro("70"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Bootstrap: delta = capacidade cheia (100). Reranqueamento por
    # resíduo: delta = resíduo remanescente (30), nunca 100 de novo.
    assertar_exato(sel.chamadas[0].delta, dinheiro("100"))
    assertar_exato(sel.chamadas[1].delta, dinheiro("30"))
