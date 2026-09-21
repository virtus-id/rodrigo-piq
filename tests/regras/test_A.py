"""Testes da família A — cascata de resíduo do ataque (`A-01`..`A-04`).

RF-03, §4.1, §11.1: cada teste é nomeado com o ID da regra `A-*` que exercita
e verifica saída OBSERVÁVEL de `simular_cenario` (`Cenario`/`ResultadoMes`) —
nunca chama `executar_mes` isoladamente nem inspeciona estado interno. Mesmo
padrão de helpers de `tests/regras/test_simular_cenario.py`.

REGRAS: RF-03, A-01, A-02, A-03, A-04, EC-01
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
    """Escolhe, entre as dívidas NÃO quitadas, a de menor saldo. Grava cada
    chamada para provar o delta passado em cada rodada (`A-03`)."""

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
# A-01 — RESIDUO_ATAQUE_M é o que sobra do ataque depois de zerar o saldo
# do alvo original, calculado em M-06.
# ---------------------------------------------------------------------------
def test_A01_residuo_e_o_que_sobra_apos_zerar_o_alvo() -> None:
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Ataque de 100 sobre saldo 40 ⇒ RESIDUO_ATAQUE_M = 60.
    assertar_exato(cenario.meses[0].RESIDUO_ATAQUE_M, dinheiro("60"))


# ---------------------------------------------------------------------------
# A-02 — a aplicação do resíduo à dívida selecionada é registrada como um
# evento auditável (uma instância por rodada da cascata).
# ---------------------------------------------------------------------------
def test_A02_aplicacao_do_residuo_e_registrada_por_rodada() -> None:
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    aplicacoes = cenario.meses[0].aplicacoes_residuo
    assertar_exato(len(aplicacoes), 1)
    assertar_exato(aplicacoes[0].DIVIDA_ID, "D-02")
    assertar_exato(aplicacoes[0].valor_aplicado, dinheiro("60"))
    assertar_exato(aplicacoes[0].ordem_aplicacao, 1)


# ---------------------------------------------------------------------------
# A-03 — nomeado explicitamente pela tarefa: o delta usado pelo
# reranqueamento de resíduo é o resíduo restante, NUNCA a capacidade cheia
# do mês.
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_A03_delta_do_residuo_nao_usa_capacidade_cheia() -> None:
    d1 = _divida("D-01", saldo=dinheiro("70"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # Capacidade do mês = 100. D-01 (70) quita com sobra de 30. O
    # reranqueamento da cascata deve receber delta = 30 (resíduo restante),
    # nunca 100 (capacidade cheia) de novo.
    assertar_exato(len(sel.chamadas), 2)
    assertar_exato(sel.chamadas[0].delta, dinheiro("100"))  # bootstrap
    assertar_exato(sel.chamadas[1].delta, dinheiro("30"))  # reranqueamento de resíduo


# ---------------------------------------------------------------------------
# A-04 / EC-01 — resíduo sem destino ao fim da cascata (sem dívida
# elegível remanescente) vira ATAQUE_NAO_UTILIZADO, mantido como caixa do
# usuário, nunca descartado.
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_A04_EC01_residuo_sem_destino_vira_ataque_nao_utilizado() -> None:
    # Única dívida do cenário: quita com sobra grande, sem candidata
    # remanescente para receber a cascata.
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    # Resíduo de 60 não tem destino (sem outra dívida elegível) ⇒
    # ATAQUE_NAO_UTILIZADO = 60, sem cascata (nenhuma aplicação/reranqueamento
    # por resíduo — a cascata tenta reranquear, não encontra candidata, e
    # para sem aplicar nada).
    assertar_exato(mes_1.ATAQUE_NAO_UTILIZADO, dinheiro("60"))
    assertar_exato(mes_1.aplicacoes_residuo, ())
    # O valor não desaparece: acumula no estado, atravessando os meses
    # (TRAVA — nunca some da simulação).
    assertar_exato(mes_1.estado_final.ATAQUE_NAO_UTILIZADO_ACUMULADO, dinheiro("60"))
