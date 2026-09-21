"""Testes de `simular_cenario` — RF-01, RF-02 · M-10..M-12 · AC-13 · EC-13 ·
`T-46`.

`executar_mes` (testado em `test_ciclo_mensal.py`) resolve um mês isolado.
Este arquivo testa o ENCADEAMENTO de vários meses:

- `PRAZO_TOTAL`, `CUSTO_FUTURO_TOTAL`, `ORDEM_QUITACAO` e
  `MESES_PRIMEIRA_VITORIA` são produzidos no `Cenario` resultante.
- Mês sem quitação e sem evento não gera reranqueamento extra (`AC-13`).
- Estouro do horizonte encerra e sinaliza; alerta a partir de
  `P_HORIZONTE_ALERTA` (`EC-13`).
- `Cenario.meses` preserva o rastro completo, um `ResultadoMes` por mês
  simulado.
- O cenário que estoura o horizonte roda em modo "estabilização" e é
  marcado condicional (`ESTOUROU_HORIZONTE = True`), sem lançar exceção.

Mesmo padrão de `_divida`/`_SelPorMenorSaldo`/`_parametros_vazios` de
`test_ciclo_mensal.py`, com `_parametros` estendido para carregar
`P_HORIZONTE_MAXIMO_SIMULACAO`/`P_HORIZONTE_ALERTA` (lidos de verdade por
`simular_cenario`, ao contrário de `executar_mes`).

REGRAS: RF-01, RF-02, M-10, M-11, M-12, R-02, AC-13, EC-13
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

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
    """Mesmo helper de `test_ciclo_mensal.py::_divida` — dívida completa e
    válida, variando só saldo/taxa/pagamento."""
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
    """`simular_cenario` lê `P_HORIZONTE_MAXIMO_SIMULACAO`/`P_HORIZONTE_
    ALERTA` de verdade (diferente de `executar_mes`, que não lê `Parametros`
    nesta tarefa) — valores default iguais aos de `parameters/parametros-
    1.0.1.json` (10 anos / 5 anos), sobrepostos por parâmetro de teste
    quando o caso precisar de um horizonte pequeno para ser exercitável.
    """
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
    `Diagnostico` — os demais campos são neutros, presentes apenas para
    satisfazer o dataclass completo (`Diagnostico` é `T-24`, fora do
    escopo desta tarefa)."""
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
    """`simular_cenario` não lê `e` nesta tarefa (parte do contrato do
    plano, `noqa: ARG001`) — instância mínima só para satisfazer a
    assinatura, mesmo padrão de `_parametros_vazios()` em
    `test_ciclo_mensal.py`."""
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
    """Mesmo `SelecionarAlvo` de teste de `test_ciclo_mensal.py` — escolhe,
    entre as dívidas NÃO quitadas, a de menor saldo. Grava cada chamada
    para provar `AC-13` (nenhuma chamada extra entre meses sem quitação)."""

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
# Critério 1 — PRAZO_TOTAL, CUSTO_FUTURO_TOTAL, ORDEM_QUITACAO e
# MESES_PRIMEIRA_VITORIA são produzidos no Cenario resultante.
# ---------------------------------------------------------------------------
def test_cenario_produz_prazo_custo_ordem_e_primeira_vitoria() -> None:
    d1 = _divida("D-01", saldo=dinheiro("100"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("200"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-01 (100) quita no mês 1 com a capacidade cheia; D-02 (200) quita no
    # mês 3 (100 + 100 + 100 = 300 de ataque acumulado até então).
    assertar_exato(cenario.ORDEM_QUITACAO, ("D-01", "D-02"))
    assertar_exato(cenario.MESES_PRIMEIRA_VITORIA, 1)
    assertar_exato(cenario.PRAZO_TOTAL, 3)
    assertar_exato(len(cenario.meses), 3)
    # CUSTO_FUTURO_TOTAL é produzido (Dinheiro exato, não None/DESCONHECIDO)
    # — o valor em si não tem fórmula normativa própria (ver docstring de
    # simular_cenario); o critério de aceite é que o campo EXISTE e é
    # coerente com o total pago (300 = 100 + 200, sem juros neste cenário).
    assertar_exato(cenario.CUSTO_FUTURO_TOTAL, dinheiro("300"))


# ---------------------------------------------------------------------------
# Critério 2 — mês sem quitação e sem evento não gera reranqueamento extra
# (AC-13): a mesma DIVIDA_ALVO_ATUAL atravessa vários meses sem quitação,
# sem qualquer chamada adicional a `sel()` além do bootstrap.
# ---------------------------------------------------------------------------
def test_meses_sem_quitacao_nao_reranqueiam_entre_si() -> None:
    # D-01 tem saldo grande o suficiente para levar vários meses de ataque
    # sem quitar — cada mês sem quitação não deve chamar `sel()` de novo.
    d1 = _divida("D-01", saldo=dinheiro("1000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # 1000 / 100 por mês = 10 meses exatos para quitar.
    assertar_exato(cenario.PRAZO_TOTAL, 10)
    assertar_exato(cenario.ORDEM_QUITACAO, ("D-01",))
    # AC-13: uma única chamada a `sel()` em toda a simulação — o bootstrap
    # do mês 1 (D-01 ainda não tinha alvo). Os nove meses seguintes, sem
    # quitação nenhuma, preservam o alvo sem reranquear (`M-05`/`M-12`/
    # `R-02`) — nenhuma chamada extra é feita por `simular_cenario` entre
    # meses.
    assertar_exato(len(sel.chamadas), 1)
    # Todo mês sem quitação preserva o mesmo alvo, sem reranqueamentos — só
    # o último mês (o que quita D-01) devolve DIVIDA_ALVO_ATUAL=None (M-06:
    # dívida quitada sai do papel de alvo), então é verificado à parte.
    meses_sem_quitacao, mes_da_quitacao = cenario.meses[:-1], cenario.meses[-1]
    for resultado_mes in meses_sem_quitacao:
        assertar_exato(resultado_mes.estado_final.DIVIDA_ALVO_ATUAL, "D-01")
        assertar_exato(resultado_mes.reranqueamentos, ())
    assertar_exato(set(mes_da_quitacao.quitacoes), {"D-01"})
    assertar_exato(mes_da_quitacao.estado_final.DIVIDA_ALVO_ATUAL, None)
    assertar_exato(mes_da_quitacao.reranqueamentos, ())


# ---------------------------------------------------------------------------
# Critério 3 e 5 — estouro do horizonte encerra e sinaliza (EC-13); o
# cenário roda em modo "estabilização" (marcado condicional via
# ESTOUROU_HORIZONTE=True) sem lançar exceção.
# ---------------------------------------------------------------------------
def test_estouro_do_horizonte_encerra_e_sinaliza_sem_abortar() -> None:
    # D-01 nunca quita: capacidade 1/mês contra saldo 1_000_000, e o
    # horizonte de teste é de apenas 1 ano (12 meses) para o caso ser
    # exercitável sem rodar 10 anos de verdade.
    d1 = _divida("D-01", saldo=dinheiro("1000000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("1"))
    p = _parametros(horizonte_maximo_anos=1, horizonte_alerta_anos=1)

    # Não lança exceção alguma — devolve um Cenario normalmente.
    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    assertar_exato(cenario.ESTOUROU_HORIZONTE, True)
    # Encerrou exatamente em P_HORIZONTE_MAXIMO_SIMULACAO × 12 = 12 meses —
    # nem um mês a mais.
    assertar_exato(cenario.PRAZO_TOTAL, 12)
    assertar_exato(len(cenario.meses), 12)
    # Nenhuma dívida foi quitada — o cenário fica condicional/incompleto.
    assertar_exato(cenario.ORDEM_QUITACAO, ())
    assertar_exato(cenario.MESES_PRIMEIRA_VITORIA, None)


def test_alerta_horizonte_dispara_a_partir_de_p_horizonte_alerta_antes_do_maximo() -> None:
    """EC-13: o alerta de `P_HORIZONTE_ALERTA` (mais cedo) é um sinal
    DIFERENTE do estouro (`P_HORIZONTE_MAXIMO_SIMULACAO`) — dispara sem
    encerrar a simulação."""
    d1 = _divida("D-01", saldo=dinheiro("1000000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("1"))
    # Alerta em 1 ano (12 meses), máximo em 2 anos (24 meses) — o cenário
    # ainda estoura o horizonte máximo (nunca quita), mas o alerta dispara
    # antes, no mês 12, sem encerrar a simulação naquele ponto.
    p = _parametros(horizonte_maximo_anos=2, horizonte_alerta_anos=1)

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    assertar_exato(cenario.ESTOUROU_HORIZONTE, True)
    assertar_exato(cenario.PRAZO_TOTAL, 24)
    assertar_exato(cenario.MESES_ATE_ALERTA_HORIZONTE, 12)


# ---------------------------------------------------------------------------
# Critério 4 — Cenario.meses preserva o rastro completo (um ResultadoMes
# por mês simulado) para auditoria.
# ---------------------------------------------------------------------------
def test_meses_preserva_rastro_completo_para_auditoria() -> None:
    d1 = _divida("D-01", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("50"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("50"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # D-01 quita no mês 1, D-02 quita no mês 2 — dois meses simulados, dois
    # ResultadoMes no rastro, na ordem cronológica.
    assertar_exato(cenario.PRAZO_TOTAL, 2)
    assertar_exato(len(cenario.meses), 2)
    assertar_exato(cenario.meses[0].estado_final.mes, 1)
    assertar_exato(cenario.meses[1].estado_final.mes, 2)
    assertar_exato(set(cenario.meses[0].quitacoes), {"D-01"})
    assertar_exato(set(cenario.meses[1].quitacoes), {"D-02"})


# ---------------------------------------------------------------------------
# M-11 — o VALOR_FLUXO_LIBERADO do mês N só entra na CAPACIDADE_ATAQUE_M do
# mês N+1, nunca do próprio mês N (AC-15, encadeado por simular_cenario).
# ---------------------------------------------------------------------------
def test_fluxo_liberado_incorporado_apenas_na_abertura_do_mes_seguinte() -> None:
    # D-01 (não-alvo) quita só com o pagamento normal de 700 no mês 1,
    # liberando 700. D-02 (alvo, menor saldo — escolhida no bootstrap) tem
    # saldo grande e ataca 100/mês.
    d1 = _divida("D-01", saldo=dinheiro("700"), pagamento_mensal_efetivo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("2000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    # D-01 (menor saldo, 700) é o alvo escolhido no bootstrap; ataque total
    # = pagamento normal do alvo (700, M-04) + capacidade (100) = 800,
    # aplicado = min(800, 700) = 700 ⇒ quita, sobra RESIDUO_ATAQUE_M = 100.
    # F-01: libera o EFETIVO (700), não o ataque bruto. O resíduo de 100
    # cascateia (M-07/M-08) para D-02, única candidata restante.
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    assertar_exato(mes_1.RESIDUO_ATAQUE_M, dinheiro("100"))
    assertar_exato(mes_1.VALOR_FLUXO_LIBERADO, dinheiro("700"))
    # A capacidade do mês 1 (recebida e devolvida) permanece 100 — o fluxo
    # de D-01 não reforça o ataque dentro do próprio mês 1 (a cascata usa o
    # RESIDUO_ATAQUE_M do próprio ataque de 100, não o fluxo liberado).
    assertar_exato(mes_1.estado_final.CAPACIDADE_ATAQUE_M, dinheiro("100"))
    # D-02 recebeu o resíduo de 100 via cascata neste mesmo mês: 2000-100=1900.
    assertar_exato(mes_1.estado_final.saldos["D-02"], dinheiro("1900"))

    # Mês 2: alvo herdado é D-02 (recebeu a cascata no mês 1, M-05/M-06); a
    # capacidade sobe para 100 (base) + 700 (fluxo liberado no mês 1) = 800
    # — incorporado na ABERTURA do mês 2 por simular_cenario. D-02 (1900)
    # ataca com pagamento normal (0) + 800 = 800: saldo final 1100.
    mes_2 = cenario.meses[1]
    assertar_exato(mes_2.estado_final.DIVIDA_ALVO_ATUAL, "D-02")
    assertar_exato(mes_2.estado_final.saldos["D-02"], dinheiro("1100"))
