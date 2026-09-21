"""Testes da família F — fluxo liberado (`F-01`..`F-03`).

RF-04, §4.2, §11.7: cada teste é nomeado com o ID da regra `F-*` que exercita
e verifica saída OBSERVÁVEL de `simular_cenario` (`Cenario`/`ResultadoMes`) —
nunca chama `executar_mes` isoladamente nem inspeciona estado interno. Mesmo
padrão de helpers de `tests/regras/test_simular_cenario.py`.

REGRAS: RF-04, F-01, F-02, F-03, AC-15, AC-32, EC-18
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
    parcela_contratual: DinheiroTalvez | None = None,
    pagamento_mensal_efetivo: DinheiroTalvez | None = None,
) -> Divida:
    """Mesmo padrão de `test_simular_cenario.py::_divida`, estendido com
    `parcela_contratual` independente do efetivo — necessário para `AC-32`/
    `EC-18` (contratual > 0, efetivo 0)."""
    if taxa is None:
        taxa = dinheiro("0")
    if pagamento_mensal_efetivo is None:
        pagamento_mensal_efetivo = dinheiro("0")
    if parcela_contratual is None:
        parcela_contratual = pagamento_mensal_efetivo
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
        PARCELA_CONTRATUAL=parcela_contratual,
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
    """Escolhe, entre as dívidas NÃO quitadas, a de menor saldo."""

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
# F-01 / AC-32 / EC-18 — dívida quitada libera o PAGAMENTO_MENSAL_EFETIVO
# que de fato saía do orçamento, nunca a parcela contratual. Dívida com
# contratual R$ 1.200 e efetivo 0 libera exatamente 0 (AC-32/EC-18).
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_F01_AC32_EC18_libera_efetivo_nunca_contratual_fictício() -> None:
    # D-01: contratual 1.200, efetivo 0 (não estava sendo paga de fato) —
    # AC-32/EC-18. D-01 é o alvo (única dívida) e quita com a capacidade.
    d1 = _divida(
        "D-01",
        saldo=dinheiro("100"),
        parcela_contratual=dinheiro("1200"),
        pagamento_mensal_efetivo=dinheiro("0"),
    )
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    # VALOR_FLUXO_LIBERADO = 0, nunca 1.200 (a parcela contratual fictícia).
    assertar_exato(mes_1.VALOR_FLUXO_LIBERADO, dinheiro("0"))


# ---------------------------------------------------------------------------
# F-02 — nomeado explicitamente pela tarefa: o fluxo liberado consolidado
# no mês m só entra na capacidade de ataque em m+1, nunca no próprio mês.
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_F02_fluxo_liberado_entra_em_m_mais_1() -> None:
    # D-01 (alvo, menor saldo) quita só com o pagamento normal efetivo de
    # 700, liberando 700. D-02 tem saldo grande e recebe o ataque normal.
    d1 = _divida("D-01", saldo=dinheiro("700"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("2000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    assertar_exato(mes_1.VALOR_FLUXO_LIBERADO, dinheiro("700"))
    # O fluxo de 700 NÃO está presente na capacidade do próprio mês 1.
    assertar_exato(mes_1.estado_final.CAPACIDADE_ATAQUE_M, dinheiro("100"))
    # Só aparece na capacidade de abertura do mês 2 (100 base + 700 fluxo).
    mes_2 = cenario.meses[1]
    assertar_exato(mes_2.estado_final.CAPACIDADE_ATAQUE_M, dinheiro("800"))


# ---------------------------------------------------------------------------
# F-03 / AC-15 — nenhum valor conta ao mesmo tempo como pagamento normal de
# m e como capacidade adicional de m: o fluxo liberado por D-01 no mês 1
# não reforça a cascata de resíduo do próprio mês 1 (só o RESIDUO_ATAQUE_M
# do próprio ataque cascateia, nunca o VALOR_FLUXO_LIBERADO).
# ---------------------------------------------------------------------------
def test_F03_AC15_fluxo_liberado_nao_reforca_cascata_do_proprio_mes() -> None:
    d1 = _divida("D-01", saldo=dinheiro("700"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("2000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    # Ataque total sobre D-01 = pagamento normal do alvo (700) + capacidade
    # (100) = 800; aplicado = min(800, 700) = 700 ⇒ quita com
    # RESIDUO_ATAQUE_M = 100 (não 800: o fluxo liberado de 700 não é
    # capacidade adicional deste mês). A cascata de resíduo (100) aplica-se
    # a D-02 — nunca os 700 do fluxo liberado.
    assertar_exato(mes_1.RESIDUO_ATAQUE_M, dinheiro("100"))
    assertar_exato(len(mes_1.aplicacoes_residuo), 1)
    assertar_exato(mes_1.aplicacoes_residuo[0].valor_aplicado, dinheiro("100"))
    assertar_exato(mes_1.estado_final.saldos["D-02"], dinheiro("1900"))


# ---------------------------------------------------------------------------
# EC-18 (isolado) — dívida quitada que não estava sendo paga de fato libera
# zero, mesmo com um valor devido/contratual maior que zero.
# ---------------------------------------------------------------------------
def test_EC18_dividia_nao_paga_de_fato_libera_zero() -> None:
    d1 = _divida(
        "D-01",
        saldo=dinheiro("50"),
        parcela_contratual=dinheiro("500"),
        pagamento_mensal_efetivo=dinheiro("0"),
    )
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("50"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    assertar_exato(mes_1.VALOR_FLUXO_LIBERADO, dinheiro("0"))
