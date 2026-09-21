"""Testes dos quatro gates de elegibilidade — `engine/gates.py`, RF-17 · §11.3.

`T-29` implementou os Gates 1 (Informação) e 2 (Contenção de risco); `T-30`
acrescenta os Gates 3 (Transformação) e 4 (Oportunidade com prazo) e a
orquestração completa `aplicar_gates_1_a_4`. Como não havia suíte de testes
para `engine/gates.py` (gap pré-existente de `T-29`), este arquivo também
cobre os dois primeiros gates o suficiente para provar a sequência fixa
1→2→3→4 e o curto-circuito no primeiro bloqueador — sem duplicar a extensão
de `T-29` (que fica em `test_D4.py`/`test_valor_quitacao.py` como cobertura
indireta de suas dependências).

Cobre, especificamente para `T-30`:
- `AC-22`: renegociação/troca pendente ⇒ `INTERVENCAO_PENDENTE` +
  `GATE_PENDENTE = TRANSFORMACAO`, fora da ordem ordinária; e a "volta a ser
  elegível" como propriedade natural de reavaliar o gate sobre novo estado
  (não uma máquina de estados própria).
- `EC-16`: oportunidade vigente/executável não bloqueia nem promove
  automaticamente — Gate 4 devolve sempre `None`.
- Sequência fixa e curto-circuito: dívida que viola Gate 1 E Gate 3 ao mesmo
  tempo para no Gate 1.
- `gate_bloqueador` e `motivo` textual em cada bloqueio.

`T-33` audita a cobertura acima (já satisfaz `AC-22`, `AC-41`, `AC-42`,
`AC-44`, `AC-45` e o curto-circuito da sequência fixa) e completa o que
faltava:
- `AC-23`/`AC-43` (Gate 2 — Contenção de risco): risco alto desvia para
  `ORDEM_ACOES` (`INTERVENCAO_PENDENTE` + `GATE_PENDENTE =
  CONTENCAO_RISCO`) mas NUNCA promove a dívida automaticamente ao primeiro
  lugar da ordem-base — provado observando `ParticaoElegibilidade.elegiveis`
  via `particionar_elegibilidade`, não a função de gate isolada.
- `EC-15`: exceção de prioridade excepcional (quitação = própria contenção
  do risco) ainda assim mantém a dívida fora de `elegiveis` — só marca
  `acao.prioridade_excepcional = True` em `ORDEM_ACOES`.
- `particionar_elegibilidade` (`T-32`): testes formais sobre uma carteira
  mista (uma dívida elegível, uma bloqueada por cada um dos quatro
  "motivos" de bloqueio observáveis — Gate 1, Gate 2, Gate 3, `OUTRA`),
  confirmando `elegiveis`, `bloqueadas` e `ORDEM_ACOES`.
- `EC-17`: carteira inteira bloqueada ⇒ `elegiveis == ()`, estado válido,
  não uma falha.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

import engine.gates as gates
from engine.estado import TIPO_DIVIDA, Divida, Oportunidade
from engine.gates import (
    aplicar_gate_2_contencao_risco,
    aplicar_gate_3_transformacao,
    aplicar_gate_4_oportunidade,
    aplicar_gates_1_a_4,
    avaliar_oportunidade_executavel,
    determinar_status_estrategico,
    particionar_elegibilidade,
)
from engine.tipos import (
    DESCONHECIDO,
    DIVIDA_STATUS_ESTRATEGICO,
    GATE_PENDENTE,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from engine.valor_quitacao import ResultadoValorRelevante, compor_VALOR_RELEVANTE_PARA_QUITACAO
from tests.conftest import assertar_exato


def _divida(**overrides: object) -> Divida:
    """Dívida "sem bloqueio" por padrão em todos os campos relevantes aos
    quatro gates — nenhum gate dispara sem override explícito. Mesmo padrão
    de `_sinais`/`_sinais_comportamentais` dos demais testes de regra."""
    base: dict[str, object] = dict(
        DIVIDA_ID="D-01",
        TIPO_DIVIDA=TIPO_DIVIDA.CONSIGNADO,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=Decimal("1000.00"),
        VALOR_QUITACAO_HOJE=Decimal("1000.00"),
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.02"),
        CET=Decimal("0.02"),
        PARCELA_CONTRATUAL=Decimal("100.00"),
        PAGAMENTO_MENSAL_EFETIVO=Decimal("100.00"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=Decimal("0.00"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
    base.update(overrides)
    return Divida(**base)  # type: ignore[arg-type]


def _valor_relevante_ok(divida: Divida) -> ResultadoValorRelevante:
    """Gate 1 resolvido — reaproveita a função real de `T-27` em vez de
    inventar um `ResultadoValorRelevante` avulso, mantendo a composição
    fiel ao caminho de produção."""
    return compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)


# ---------------------------------------------------------------------------
# AC-22 — Gate 3 (Transformação)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC22_renegociacao_pendente_bloqueia_gate_3() -> None:
    """AC-22: `RENEGOCIACAO_PENDENTE = True` ⇒ `INTERVENCAO_PENDENTE` +
    `GATE_PENDENTE = TRANSFORMACAO`, fora da ordem ordinária."""
    divida = _divida(RENEGOCIACAO_PENDENTE=True)
    resultado = aplicar_gate_3_transformacao(divida)
    assert resultado is not None
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 3)
    assert resultado.motivo  # texto auditável, reaproveitável por JUSTIFICATIVA_POSICAO
    assert resultado.acao is not None
    assertar_exato(resultado.acao.gate_origem, 3)


@pytest.mark.regra
def test_AC22_troca_pendente_bloqueia_gate_3() -> None:
    """AC-22, segundo campo de intervenção: `TROCA_PENDENTE = True` produz o
    mesmo efeito de `RENEGOCIACAO_PENDENTE`."""
    divida = _divida(TROCA_PENDENTE=True)
    resultado = aplicar_gate_3_transformacao(divida)
    assert resultado is not None
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)
    assertar_exato(resultado.gate_bloqueador, 3)


@pytest.mark.regra
def test_AC22_nenhuma_intervencao_pendente_gate_3_nao_bloqueia() -> None:
    """Gate 3 devolve `None` quando nem renegociação nem troca estão
    pendentes — dívida segue candidata ao Gate 4."""
    divida = _divida()
    assertar_exato(aplicar_gate_3_transformacao(divida), None)


@pytest.mark.regra
def test_AC22_intervencao_encerrada_volta_a_ser_elegivel() -> None:
    """AC-22: "executada, rejeitada ou encerrada, a dívida volta a ser
    elegível" — propriedade natural de reavaliar o MESMO gate sobre um NOVO
    estado, não uma máquina de estados própria. Mesma dívida, mesmo
    `DIVIDA_ID`, apenas com `RENEGOCIACAO_PENDENTE` transicionado de `True`
    para `False` (simulando o recálculo pós-intervenção, `R-01`)."""
    divida_com_intervencao = _divida(RENEGOCIACAO_PENDENTE=True)
    resultado_antes = aplicar_gate_3_transformacao(divida_com_intervencao)
    assert resultado_antes is not None
    assertar_exato(resultado_antes.gate_bloqueador, 3)

    divida_intervencao_encerrada = replace(divida_com_intervencao, RENEGOCIACAO_PENDENTE=False)
    resultado_depois = aplicar_gate_3_transformacao(divida_intervencao_encerrada)
    assertar_exato(resultado_depois, None)


# ---------------------------------------------------------------------------
# EC-16 — Gate 4 (Oportunidade com prazo): nunca bloqueia
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_EC16_oportunidade_vigente_nao_bloqueia_gate_4() -> None:
    """EC-16: mesmo com oportunidade vigente e totalmente executável
    (benefício + recurso + prazo + sustentabilidade, todos presentes), o
    Gate 4 devolve `None` — desconto não implica primeiro lugar automático,
    a dívida segue elegível para a ordem-base normalmente."""
    oportunidade = Oportunidade(
        beneficio=Decimal("50.00"),
        recurso_disponivel=True,
        prazo=date(2026, 12, 31),
        sustentavel=True,
    )
    divida = _divida(OPORTUNIDADE_VIGENTE=oportunidade)
    assertar_exato(aplicar_gate_4_oportunidade(divida), None)
    # Confirma que a oportunidade É de fato executável — não é um caso onde
    # "não bloqueia" coincide trivialmente com "não é executável".
    assertar_exato(avaliar_oportunidade_executavel(divida), True)


@pytest.mark.regra
def test_EC16_sem_oportunidade_gate_4_tambem_nao_bloqueia() -> None:
    """Gate 4 devolve `None` também no caso trivial (sem oportunidade
    vigente) — reforça que o gate estruturalmente nunca bloqueia, em
    qualquer estado de `OPORTUNIDADE_VIGENTE`."""
    divida = _divida(OPORTUNIDADE_VIGENTE=None)
    assertar_exato(aplicar_gate_4_oportunidade(divida), None)
    assertar_exato(avaliar_oportunidade_executavel(divida), False)


@pytest.mark.regra
@pytest.mark.parametrize(
    "oportunidade",
    [
        Oportunidade(
            beneficio=DESCONHECIDO,
            recurso_disponivel=True,
            prazo=date(2026, 12, 31),
            sustentavel=True,
        ),
        Oportunidade(
            beneficio=Decimal("50.00"),
            recurso_disponivel=False,
            prazo=date(2026, 12, 31),
            sustentavel=True,
        ),
        Oportunidade(
            beneficio=Decimal("50.00"), recurso_disponivel=True, prazo=None, sustentavel=True
        ),
        Oportunidade(
            beneficio=Decimal("50.00"),
            recurso_disponivel=True,
            prazo=date(2026, 12, 31),
            sustentavel=False,
        ),
    ],
    ids=["sem_beneficio", "sem_recurso", "sem_prazo", "nao_sustentavel"],
)
def test_avaliar_oportunidade_executavel_exige_os_quatro_componentes(
    oportunidade: Oportunidade,
) -> None:
    """§11.3: `OPORTUNIDADE_EXECUTAVEL` só é `True` com os quatro
    componentes presentes — falta de qualquer um torna não executável
    (RF-16: componente ausente nunca é tratado como presente). Em nenhum
    dos quatro casos o Gate 4 bloqueia (reforça EC-16 independentemente de
    executabilidade)."""
    divida = _divida(OPORTUNIDADE_VIGENTE=oportunidade)
    assertar_exato(avaliar_oportunidade_executavel(divida), False)
    assertar_exato(aplicar_gate_4_oportunidade(divida), None)


# ---------------------------------------------------------------------------
# Sequência fixa 1→2→3→4 e curto-circuito no primeiro bloqueador
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_sequencia_fixa_nenhum_gate_bloqueia_divida_elegivel() -> None:
    """Dívida sem nenhuma condição de bloqueio passa pelos quatro gates —
    `aplicar_gates_1_a_4` devolve `None`, elegível para a ordem-base."""
    divida = _divida()
    resultado = aplicar_gates_1_a_4(divida, _valor_relevante_ok(divida))
    assertar_exato(resultado, None)


@pytest.mark.regra
def test_sequencia_fixa_para_no_gate_1_mesmo_com_gate_3_tambem_violado() -> None:
    """Dívida que viola SIMULTANEAMENTE o Gate 1 (`QUITADA_A_CONFIRMAR`) e o
    Gate 3 (`RENEGOCIACAO_PENDENTE = True`) para no Gate 1 — a sequência fixa
    1→2→3→4 nunca avalia o Gate 3 quando o Gate 1 já bloqueou. Prova central
    do curto-circuito pedido pela tarefa."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR,
        RENEGOCIACAO_PENDENTE=True,
    )
    resultado = aplicar_gates_1_a_4(divida, _valor_relevante_ok(divida))
    assert resultado is not None
    assertar_exato(resultado.gate_bloqueador, 1)
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.INFORMACAO)


@pytest.mark.regra
def test_sequencia_fixa_para_no_gate_2_mesmo_com_gate_3_tambem_violado() -> None:
    """Dívida que viola SIMULTANEAMENTE o Gate 2 (`RISCO_MATERIAL_IMINENTE`)
    e o Gate 3 (`TROCA_PENDENTE`) para no Gate 2 — o Gate 3 só seria avaliado
    se o Gate 2 tivesse passado."""
    divida = _divida(RISCO_MATERIAL_IMINENTE=True, TROCA_PENDENTE=True)
    resultado = aplicar_gates_1_a_4(divida, _valor_relevante_ok(divida))
    assert resultado is not None
    assertar_exato(resultado.gate_bloqueador, 2)
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.CONTENCAO_RISCO)


@pytest.mark.regra
def test_sequencia_fixa_gate_3_bloqueia_quando_1_e_2_passam() -> None:
    """Só quando Gate 1 e Gate 2 passam é que o Gate 3, de fato, chega a
    bloquear — prova a ordem 1→2→3 também no sentido positivo."""
    divida = _divida(RENEGOCIACAO_PENDENTE=True)
    resultado = aplicar_gates_1_a_4(divida, _valor_relevante_ok(divida))
    assert resultado is not None
    assertar_exato(resultado.gate_bloqueador, 3)
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)


@pytest.mark.regra
def test_sequencia_fixa_oportunidade_nao_impede_elegibilidade_apos_1_2_3() -> None:
    """EC-16 na sequência completa: dívida sem bloqueio nos Gates 1–3, mas
    com oportunidade vigente executável, ainda assim chega a `None` (elegível
    — o Gate 4 não a desvia nem a bloqueia)."""
    oportunidade = Oportunidade(
        beneficio=Decimal("30.00"),
        recurso_disponivel=True,
        prazo=date(2026, 10, 1),
        sustentavel=True,
    )
    divida = _divida(OPORTUNIDADE_VIGENTE=oportunidade)
    resultado = aplicar_gates_1_a_4(divida, _valor_relevante_ok(divida))
    assertar_exato(resultado, None)


# ---------------------------------------------------------------------------
# T-31 — determinar_status_estrategico: mapeamento STATUS_DIVIDA →
# DIVIDA_STATUS_ESTRATEGICO (Definições §6, tabela completa de §11.3)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC41_em_acordo_executado_estrutura_conhecida_pronta_para_ordenacao() -> None:
    """AC-41: `EM_ACORDO` com acordo já executado (nada pendente em Gate 3)
    e gates resolvidos atinge `PRONTA_PARA_ORDENACAO` — `STATUS_DIVIDA` por
    si só não bloqueia."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.EM_ACORDO,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
    )
    resultado = determinar_status_estrategico(divida, _valor_relevante_ok(divida))
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.NENHUM)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, True)
    assertar_exato(resultado.gate_bloqueador, None)


@pytest.mark.regra
def test_em_acordo_negociacao_aberta_via_renegociacao_pendente_intervencao_pendente() -> None:
    """`EM_ACORDO` com negociação aberta (proxy: `RENEGOCIACAO_PENDENTE =
    True`) ⇒ `INTERVENCAO_PENDENTE` + `GATE_PENDENTE = TRANSFORMACAO` — ponte
    documentada no cabeçalho do módulo entre o sub-caso da tabela e o campo
    já modelado em `Divida` para o Gate 3."""
    divida = _divida(STATUS_DIVIDA=STATUS_DIVIDA.EM_ACORDO, RENEGOCIACAO_PENDENTE=True)
    resultado = determinar_status_estrategico(divida, _valor_relevante_ok(divida))
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 3)


@pytest.mark.regra
def test_em_acordo_estrutura_sujeita_a_mudanca_via_troca_pendente_intervencao_pendente() -> None:
    """`EM_ACORDO` com estrutura sujeita a mudança material (proxy:
    `TROCA_PENDENTE = True`) produz o mesmo efeito do sub-caso anterior."""
    divida = _divida(STATUS_DIVIDA=STATUS_DIVIDA.EM_ACORDO, TROCA_PENDENTE=True)
    resultado = determinar_status_estrategico(divida, _valor_relevante_ok(divida))
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)
    assertar_exato(resultado.gate_bloqueador, 3)


@pytest.mark.regra
def test_AC42_cobranca_sem_pagamento_saldo_conhecido_pronta_para_ordenacao() -> None:
    """AC-42: `COBRANCA_SEM_PAGAMENTO` com saldo conhecido e sem parcela
    mensal conhecida (`PAGAMENTO_MENSAL_EFETIVO` desconhecido) chega a
    `PRONTA_PARA_ORDENACAO` — o Gate 1 exige apenas
    `VALOR_RELEVANTE_PARA_QUITACAO` conhecido, nunca parcela mensal."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.COBRANCA_SEM_PAGAMENTO,
        SALDO_DEVEDOR_ATUAL=Decimal("2500.00"),
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        PAGAMENTO_MENSAL_EFETIVO=DESCONHECIDO,
        PARCELA_CONTRATUAL=DESCONHECIDO,
    )
    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO, Decimal("2500.00"))

    resultado = determinar_status_estrategico(divida, resultado_valor_relevante)
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO
    )
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, True)
    assertar_exato(resultado.gate_bloqueador, None)


@pytest.mark.regra
def test_cobranca_sem_pagamento_sem_valor_relevante_bloqueia_gate_1() -> None:
    """`COBRANCA_SEM_PAGAMENTO` sem `VALOR_RELEVANTE_PARA_QUITACAO` conhecido
    (saldo também desconhecido) é bloqueada pelo Gate 1 —
    `INFORMACAO_PENDENTE`, nunca elegível sem o dado material."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.COBRANCA_SEM_PAGAMENTO,
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
    )
    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    resultado = determinar_status_estrategico(divida, resultado_valor_relevante)
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.INFORMACAO)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 1)


@pytest.mark.regra
def test_AC45_outra_em_analise_sem_ataque_sem_passar_pelos_gates() -> None:
    """AC-45: `STATUS_DIVIDA = OUTRA` ⇒ `EM_ANALISE`, sem ataque — desvio
    ANTES dos gates. Mesmo com `RENEGOCIACAO_PENDENTE = True` (que bloquearia
    no Gate 3) e valor relevante desconhecido (que bloquearia no Gate 1), o
    resultado é `EM_ANALISE`/`gate_bloqueador = None` — prova de que os
    gates 1-4 nem chegam a rodar."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.OUTRA,
        RENEGOCIACAO_PENDENTE=True,
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
    )
    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    resultado = determinar_status_estrategico(divida, resultado_valor_relevante)
    assertar_exato(resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.EM_ANALISE)
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.NENHUM)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, None)


@pytest.mark.regra
def test_ativa_sem_bloqueio_pronta_para_ordenacao() -> None:
    """`ATIVA` sem nenhuma condição de bloqueio atravessa os quatro gates e
    chega a `PRONTA_PARA_ORDENACAO` — caso de referência sem sub-casos."""
    divida = _divida(STATUS_DIVIDA=STATUS_DIVIDA.ATIVA)
    resultado = determinar_status_estrategico(divida, _valor_relevante_ok(divida))
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO
    )
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, True)


@pytest.mark.regra
def test_AC44_quitada_a_confirmar_informacao_pendente_via_gate_1() -> None:
    """`QUITADA_A_CONFIRMAR` é inelegível — `INFORMACAO_PENDENTE` +
    `GATE_PENDENTE = INFORMACAO` — coberto pelo Gate 1 dentro da
    orquestração completa (AC-44), confirmando que `T-29` já resolve este
    status sem lógica extra nesta função."""
    divida = _divida(STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR)
    resultado = determinar_status_estrategico(divida, _valor_relevante_ok(divida))
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.INFORMACAO)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 1)


@pytest.mark.regra
def test_nenhum_caminho_usa_status_divida_isolado_para_decidir_elegibilidade() -> None:
    """Prova negativa do último critério de aceite: duas dívidas com o MESMO
    `STATUS_DIVIDA` (`ATIVA`) mas gates diferentes produzem
    `DIVIDA_ELEGIVEL_ORDEM` diferente — a decisão vem do estado dos gates,
    nunca de `STATUS_DIVIDA` isoladamente."""
    divida_elegivel = _divida(STATUS_DIVIDA=STATUS_DIVIDA.ATIVA)
    divida_bloqueada = _divida(STATUS_DIVIDA=STATUS_DIVIDA.ATIVA, RISCO_MATERIAL_IMINENTE=True)

    resultado_elegivel = determinar_status_estrategico(
        divida_elegivel, _valor_relevante_ok(divida_elegivel)
    )
    resultado_bloqueada = determinar_status_estrategico(
        divida_bloqueada, _valor_relevante_ok(divida_bloqueada)
    )

    assertar_exato(resultado_elegivel.DIVIDA_ELEGIVEL_ORDEM, True)
    assertar_exato(resultado_bloqueada.DIVIDA_ELEGIVEL_ORDEM, False)


# ---------------------------------------------------------------------------
# T-33 — AC-23/AC-43: Gate 2 (Contenção de risco) desvia, nunca promove
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC43_risco_material_iminente_desvia_para_intervencao_pendente() -> None:
    """AC-43: `RISCO_MATERIAL_IMINENTE = True` ⇒ `INTERVENCAO_PENDENTE` +
    `GATE_PENDENTE = CONTENCAO_RISCO`, com `AcaoRequerida` alimentando
    `ORDEM_ACOES` (fila paralela, gate_origem = 2)."""
    divida = _divida(RISCO_MATERIAL_IMINENTE=True)
    resultado = aplicar_gate_2_contencao_risco(divida)
    assert resultado is not None
    assertar_exato(
        resultado.DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE
    )
    assertar_exato(resultado.GATE_PENDENTE, GATE_PENDENTE.CONTENCAO_RISCO)
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 2)
    assert resultado.acao is not None
    assertar_exato(resultado.acao.gate_origem, 2)
    assertar_exato(resultado.acao.prioridade_excepcional, False)


@pytest.mark.regra
def test_gate2_risco_alto_nao_e_primeira_divida() -> None:
    """AC-23: risco alto NUNCA torna a dívida automaticamente a primeira.
    Carteira com uma dívida de risco material iminente (D-01) e uma dívida
    comum sem nenhum bloqueio (D-02): a dívida de risco é desviada para
    `ORDEM_ACOES`/`bloqueadas`, nunca aparece em `elegiveis` — muito menos
    em primeiro lugar. `elegiveis` contém só a dívida comum."""
    divida_risco = _divida(DIVIDA_ID="D-01", RISCO_MATERIAL_IMINENTE=True)
    divida_comum = _divida(DIVIDA_ID="D-02")

    particao = particionar_elegibilidade((divida_risco, divida_comum))

    assertar_exato(tuple(d.DIVIDA_ID for d in particao.elegiveis), ("D-02",))
    assertar_exato(len(particao.bloqueadas), 1)
    assertar_exato(particao.bloqueadas[0].DIVIDA_ID, "D-01")
    assertar_exato(particao.bloqueadas[0].gate_bloqueador, 2)
    assertar_exato(len(particao.ORDEM_ACOES), 1)
    assertar_exato(particao.ORDEM_ACOES[0].DIVIDA_ID, "D-01")


# ---------------------------------------------------------------------------
# T-33 — EC-15: quitação é a própria contenção do risco (prioridade
# excepcional em ORDEM_ACOES, nunca promoção automática na ordem-base)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_EC15_quitacao_e_a_propria_contencao_marca_prioridade_excepcional() -> None:
    """EC-15: quando a própria quitação é a ação que contém o risco e é
    executável, `acao.prioridade_excepcional = True` e a justificativa fica
    expressa em `motivo` — mas a dívida AINDA sai da ordem-base
    (`DIVIDA_ELEGIVEL_ORDEM = False`), nunca "primeiro lugar automático"
    (AC-23)."""
    divida = _divida(RISCO_MATERIAL_IMINENTE=True)
    resultado = aplicar_gate_2_contencao_risco(divida, quitacao_e_a_propria_contencao=True)
    assert resultado is not None
    assertar_exato(resultado.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado.gate_bloqueador, 2)
    assert resultado.acao is not None
    assertar_exato(resultado.acao.prioridade_excepcional, True)
    assert resultado.motivo  # justificativa expressa, texto auditável (Q-05)


@pytest.mark.regra
def test_EC15_sem_a_excecao_prioridade_excepcional_e_false() -> None:
    """Contraprova de EC-15: sem o parâmetro de exceção (padrão), o mesmo
    risco material iminente NÃO marca prioridade excepcional — a exceção é
    sempre explícita, nunca inferida de `RISCO_MATERIAL_IMINENTE = True`
    sozinho."""
    divida = _divida(RISCO_MATERIAL_IMINENTE=True)
    resultado = aplicar_gate_2_contencao_risco(divida, quitacao_e_a_propria_contencao=False)
    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.prioridade_excepcional, False)


# ---------------------------------------------------------------------------
# T-33/T-32 — particionar_elegibilidade: carteira mista (uma dívida elegível
# e uma bloqueada por cada um dos quatro "motivos" observáveis)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_particionar_elegibilidade_carteira_mista_classifica_cada_divida() -> None:
    """`T-32`: carteira com uma dívida elegível e uma bloqueada por Gate 1
    (`QUITADA_A_CONFIRMAR`), uma por Gate 2 (`RISCO_MATERIAL_IMINENTE`), uma
    por Gate 3 (`RENEGOCIACAO_PENDENTE`) e uma pelo desvio `OUTRA`
    (`EM_ANALISE`, antes dos gates). Confirma `elegiveis`, `bloqueadas` e
    `ORDEM_ACOES` — cada dívida no grupo certo, com o `gate_bloqueador`
    correto quando aplicável."""
    divida_elegivel = _divida(DIVIDA_ID="D-00")
    divida_gate1 = _divida(DIVIDA_ID="D-01", STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR)
    divida_gate2 = _divida(DIVIDA_ID="D-02", RISCO_MATERIAL_IMINENTE=True)
    divida_gate3 = _divida(DIVIDA_ID="D-03", RENEGOCIACAO_PENDENTE=True)
    divida_outra = _divida(DIVIDA_ID="D-04", STATUS_DIVIDA=STATUS_DIVIDA.OUTRA)

    particao = particionar_elegibilidade(
        (divida_elegivel, divida_gate1, divida_gate2, divida_gate3, divida_outra)
    )

    assertar_exato(tuple(d.DIVIDA_ID for d in particao.elegiveis), ("D-00",))

    bloqueadas_por_id = {r.DIVIDA_ID: r for r in particao.bloqueadas}
    assertar_exato(set(bloqueadas_por_id.keys()), {"D-01", "D-02", "D-03", "D-04"})
    assertar_exato(bloqueadas_por_id["D-01"].gate_bloqueador, 1)
    assertar_exato(
        bloqueadas_por_id["D-01"].DIVIDA_STATUS_ESTRATEGICO,
        DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
    )
    assertar_exato(bloqueadas_por_id["D-02"].gate_bloqueador, 2)
    assertar_exato(bloqueadas_por_id["D-02"].GATE_PENDENTE, GATE_PENDENTE.CONTENCAO_RISCO)
    assertar_exato(bloqueadas_por_id["D-03"].gate_bloqueador, 3)
    assertar_exato(bloqueadas_por_id["D-03"].GATE_PENDENTE, GATE_PENDENTE.TRANSFORMACAO)
    assertar_exato(bloqueadas_por_id["D-04"].gate_bloqueador, None)
    assertar_exato(
        bloqueadas_por_id["D-04"].DIVIDA_STATUS_ESTRATEGICO, DIVIDA_STATUS_ESTRATEGICO.EM_ANALISE
    )

    # ORDEM_ACOES: T-87 (RF-32) faz o Gate 1 também produzir AcaoRequerida
    # nos dois ramos de bloqueio — D-01 (QUITADA_A_CONFIRMAR) passa a
    # aparecer aqui junto de D-02 (Gate 2) e D-03 (Gate 3); só o desvio
    # OUTRA (D-04) nunca preenche `acao` — ver ResultadoGates.acao.
    # RF-31: DIVIDA_ID é `str | None` (None só em TIPO_ACAO="ECONOMIA", que
    # não ocorre aqui) — narrowing explícito antes de `sorted`, mesmo padrão
    # de exaustividade já usado por `engine/` (T-86).
    ids_das_acoes: list[str] = []
    for acao_em_ordem in particao.ORDEM_ACOES:
        assert acao_em_ordem.DIVIDA_ID is not None
        ids_das_acoes.append(acao_em_ordem.DIVIDA_ID)
    ids_em_ordem_acoes = tuple(sorted(ids_das_acoes))
    assertar_exato(ids_em_ordem_acoes, ("D-01", "D-02", "D-03"))

    acao_d01 = next(a for a in particao.ORDEM_ACOES if a.DIVIDA_ID == "D-01")
    assertar_exato(acao_d01.TIPO_ACAO, "INFORMACAO")
    assertar_exato(acao_d01.CAMPO_PENDENTE, "STATUS_DIVIDA")
    assertar_exato(acao_d01.gate_origem, 1)


@pytest.mark.regra
def test_particionar_elegibilidade_ordena_elegiveis_por_divida_id() -> None:
    """Ordenação total e determinística (O-05/H-04): `elegiveis` sai ordenada
    por `DIVIDA_ID`, independentemente da ordem de entrada."""
    divida_b = _divida(DIVIDA_ID="D-02")
    divida_a = _divida(DIVIDA_ID="D-01")

    particao = particionar_elegibilidade((divida_b, divida_a))

    assertar_exato(tuple(d.DIVIDA_ID for d in particao.elegiveis), ("D-01", "D-02"))


# ---------------------------------------------------------------------------
# T-33 — EC-17: nenhuma dívida elegível não produz alvo (estado válido)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_EC17_nenhuma_elegivel_nao_produz_alvo() -> None:
    """EC-17/AC-59: carteira inteira bloqueada (uma por `QUITADA_A_CONFIRMAR`,
    uma por `RISCO_MATERIAL_IMINENTE`) ⇒ `elegiveis == ()` — estado VÁLIDO,
    não uma falha. `bloqueadas` continua com as duas dívidas e `ORDEM_ACOES`
    vem preenchida com as DUAS ações — T-87 (RF-32) faz o Gate 1 também
    produzir `AcaoRequerida` (`TIPO_ACAO="INFORMACAO"`,
    `CAMPO_PENDENTE="STATUS_DIVIDA"`), além da já existente do Gate 2."""
    divida_quitada_a_confirmar = _divida(
        DIVIDA_ID="D-01", STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR
    )
    divida_risco = _divida(DIVIDA_ID="D-02", RISCO_MATERIAL_IMINENTE=True)

    particao = particionar_elegibilidade((divida_quitada_a_confirmar, divida_risco))

    assertar_exato(particao.elegiveis, ())
    assertar_exato(len(particao.bloqueadas), 2)
    assertar_exato(len(particao.ORDEM_ACOES), 2)
    # RF-31: DIVIDA_ID é `str | None` — narrowing explícito antes de `sorted`
    # (mesmo padrão de exaustividade de `engine/`, T-86).
    ids_das_acoes: list[str] = []
    for acao_em_ordem in particao.ORDEM_ACOES:
        assert acao_em_ordem.DIVIDA_ID is not None
        ids_das_acoes.append(acao_em_ordem.DIVIDA_ID)
    ids_em_ordem_acoes = tuple(sorted(ids_das_acoes))
    assertar_exato(ids_em_ordem_acoes, ("D-01", "D-02"))

    acao_d01 = next(a for a in particao.ORDEM_ACOES if a.DIVIDA_ID == "D-01")
    assertar_exato(acao_d01.TIPO_ACAO, "INFORMACAO")
    assertar_exato(acao_d01.CAMPO_PENDENTE, "STATUS_DIVIDA")
    assertar_exato(acao_d01.gate_origem, 1)


@pytest.mark.regra
def test_EC17_inventario_vazio_nao_produz_alvo() -> None:
    """EC-17, caso extremo: inventário vazio também produz `elegiveis == ()`
    sem erro — nenhuma dívida para classificar."""
    particao = particionar_elegibilidade(())
    assertar_exato(particao.elegiveis, ())
    assertar_exato(particao.bloqueadas, ())


# ---------------------------------------------------------------------------
# T-81 — RF-28, AC-48, OQ-21/OQ-22: estabilidade de ACAO_ID entre "snapshots"
# ---------------------------------------------------------------------------
# `_compor_ACAO_ID` (engine/gates.py, T-80) é função pura: mesmos insumos
# (DIVIDA_ID, TIPO_ACAO) sempre produzem o mesmo ACAO_ID, sem contador, sem
# UUID, sem estado externo (OQ-21). Os dois testes abaixo simulam dois
# cálculos independentes ("snapshots") do motor — chamando a função duas
# vezes, sem reaproveitar uma variável já calculada — para provar AC-48
# (estabilidade entre snapshots) e OQ-22 (mesma propriedade também vale para
# a ação de economia). O determinismo puro em si, como propriedade
# estrutural, é coberto por `tests/estatica/test_acao_id_determinismo_puro.py`.


@pytest.mark.regra
def test_acao_id_estavel_entre_snapshots_mesma_divida_mesmo_tipo() -> None:
    """AC-48: um mesmo caso recalculado em dois snapshots consecutivos, sem
    que a ação pendente mude de natureza, produz o mesmo ACAO_ID para a
    mesma dívida com o mesmo TIPO_ACAO — cada chamada abaixo simula um
    cálculo independente do motor (T-80/T-83/T-84 reaproveitam
    `_compor_ACAO_ID` nos três pontos de emissão)."""
    # "Snapshot" 1 — primeiro cálculo do motor sobre o caso.
    acao_id_snapshot_1 = gates._compor_ACAO_ID(divida_id="D001", tipo_acao="INFORMACAO")

    # "Snapshot" 2 — recálculo independente, mesma dívida, mesmo TIPO_ACAO.
    acao_id_snapshot_2 = gates._compor_ACAO_ID(divida_id="D001", tipo_acao="INFORMACAO")

    assertar_exato(acao_id_snapshot_1, acao_id_snapshot_2)


@pytest.mark.regra
def test_acao_id_estavel_para_acao_economia_entre_snapshots() -> None:
    """OQ-22: a ação de economia (TIPO_ACAO="ECONOMIA", DIVIDA_ID=None) é
    estável entre snapshots, mesmo que o valor de ECONOMIA_POTENCIAL_IMEDIATA
    mude entre um recálculo e outro — o ACAO_ID depende só de TIPO_ACAO, não
    do valor monetário subjacente."""
    # "Snapshot" 1.
    acao_id_snapshot_1 = gates._compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")

    # "Snapshot" 2 — recálculo independente; o valor de
    # ECONOMIA_POTENCIAL_IMEDIATA poderia ter mudado, mas não é insumo de
    # _compor_ACAO_ID, então o ACAO_ID permanece o mesmo.
    acao_id_snapshot_2 = gates._compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")

    assertar_exato(acao_id_snapshot_1, acao_id_snapshot_2)


# ---------------------------------------------------------------------------
# T-83 — RF-30/AC-50: derivação de TIPO_ACAO a partir de GATE_PENDENTE
# (Gate 1 -> "INFORMACAO", Gate 2 -> "RENEGOCIACAO", AMB-R2-02 resolvida).
#
# Até T-87, Gate 1 (`aplicar_gate_1_informacao`) devolvia `acao=None` nos
# dois ramos de bloqueio — por isso o primeiro e o terceiro critério de
# aceite de T-83 eram provados diretamente sobre a função de derivação
# isolada (`gates._derivar_TIPO_ACAO`), não por integração ponta a ponta via
# Gate 1. T-87 (RF-32) fez o Gate 1 passar a construir `AcaoRequerida` de
# verdade nos dois ramos — a cobertura de integração correspondente vive em
# `test_gate1_quitada_a_confirmar_emite_acao_informacao`/
# `test_gate1_saldo_desconhecido_emite_acao_informacao` (AC-56/AC-57)
# abaixo. Este teste isolado permanece útil como prova direta e independente
# da derivação em si (RF-30), sem depender do caminho de integração.
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC50_derivar_tipo_acao_gate1_informacao() -> None:
    """AC-50: `GATE_PENDENTE.INFORMACAO` (Gate 1) deriva `TIPO_ACAO =
    "INFORMACAO"` — prova direta da função de derivação isolada, independente
    do caminho de integração via Gate 1 (RF-30)."""
    assertar_exato(gates._derivar_TIPO_ACAO(GATE_PENDENTE.INFORMACAO), "INFORMACAO")


@pytest.mark.regra
def test_derivar_tipo_acao_gate2_contencao_risco_e_renegociacao() -> None:
    """`AMB-R2-02` (resolvida): `GATE_PENDENTE.CONTENCAO_RISCO` (Gate 2)
    deriva `TIPO_ACAO = "RENEGOCIACAO"` — Gate 2 não tem valor próprio no
    domínio fechado de quatro; contenção de risco é semanticamente mais
    próxima de renegociação (plano §R2.10.1)."""
    assertar_exato(gates._derivar_TIPO_ACAO(GATE_PENDENTE.CONTENCAO_RISCO), "RENEGOCIACAO")


@pytest.mark.regra
def test_derivar_tipo_acao_le_gate_pendente_nunca_gate_origem() -> None:
    """A derivação lê `GATE_PENDENTE`, nunca `gate_origem` — assinatura de
    `_derivar_TIPO_ACAO` recebe exclusivamente `GATE_PENDENTE`, que é o
    único discriminador capaz de separar Gate 2 de Gate 3 (ambos
    `INTERVENCAO_PENDENTE` em `gate_origem`/`DIVIDA_STATUS_ESTRATEGICO`)."""
    import inspect

    # engine/gates.py usa `from __future__ import annotations` — a anotação
    # chega como string ("GATE_PENDENTE"), não como o objeto do enum.
    parametros = inspect.signature(gates._derivar_TIPO_ACAO).parameters
    assertar_exato(tuple(parametros), ("gate_pendente",))
    assertar_exato(parametros["gate_pendente"].annotation, GATE_PENDENTE.__name__)


@pytest.mark.regra
def test_AMBR2_02_gate2_emite_acao_com_tipo_acao_renegociacao() -> None:
    """`AMB-R2-02` (resolvida), integração real: `aplicar_gate_2_contencao_
    risco` já constrói `AcaoRequerida` (desde T-29/T-79) — a partir de
    T-83, `TIPO_ACAO` deixa de ser `""` provisório e passa a
    `"RENEGOCIACAO"`, com `ACAO_ID` composto por `_compor_ACAO_ID` (T-80)."""
    divida = _divida(RISCO_MATERIAL_IMINENTE=True)
    resultado = aplicar_gate_2_contencao_risco(divida)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "RENEGOCIACAO")
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:RENEGOCIACAO")


# ---------------------------------------------------------------------------
# T-84 — RF-30/AC-51/AC-52: derivação de TIPO_ACAO no Gate 3, com prioridade
# RENEGOCIACAO sobre TROCA quando ambos RENEGOCIACAO_PENDENTE e
# TROCA_PENDENTE são True na mesma dívida (AMB-R2-03, resolvida).
#
# Testados por integração real: `aplicar_gate_3_transformacao` já constrói
# `AcaoRequerida` desde T-30/T-79 — a partir de T-84, `TIPO_ACAO` deixa de
# ser `""` provisório e passa a "RENEGOCIACAO"/"TROCA", com `ACAO_ID`
# composto por `_compor_ACAO_ID` (T-80). Mesmo padrão de integração já usado
# para o Gate 2 em T-83 (`test_AMBR2_02_gate2_emite_acao_com_tipo_acao_
# renegociacao`).
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC51_gate3_renegociacao_pendente_produz_tipo_acao_renegociacao() -> None:
    """AC-51: `RENEGOCIACAO_PENDENTE=True` e `TROCA_PENDENTE=False` produz
    `TIPO_ACAO = "RENEGOCIACAO"`."""
    divida = _divida(RENEGOCIACAO_PENDENTE=True, TROCA_PENDENTE=False)
    resultado = aplicar_gate_3_transformacao(divida)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "RENEGOCIACAO")
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:RENEGOCIACAO")


@pytest.mark.regra
def test_AC52_gate3_troca_pendente_produz_tipo_acao_troca() -> None:
    """AC-52: `TROCA_PENDENTE=True` e `RENEGOCIACAO_PENDENTE=False` produz
    `TIPO_ACAO = "TROCA"`."""
    divida = _divida(RENEGOCIACAO_PENDENTE=False, TROCA_PENDENTE=True)
    resultado = aplicar_gate_3_transformacao(divida)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "TROCA")
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:TROCA")


@pytest.mark.regra
def test_AMBR2_03_gate3_ambos_pendentes_produz_tipo_acao_renegociacao() -> None:
    """`AMB-R2-03` (resolvida): `RENEGOCIACAO_PENDENTE=True` e
    `TROCA_PENDENTE=True` simultaneamente produz `TIPO_ACAO = "RENEGOCIACAO"`
    — prioridade fixa, "TROCA" só é emitido quando TROCA_PENDENTE=True e
    RENEGOCIACAO_PENDENTE=False (ver test_AC52 acima)."""
    divida = _divida(RENEGOCIACAO_PENDENTE=True, TROCA_PENDENTE=True)
    resultado = aplicar_gate_3_transformacao(divida)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "RENEGOCIACAO")
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:RENEGOCIACAO")


@pytest.mark.regra
def test_derivar_tipo_acao_gate_3_usa_discriminador_existente() -> None:
    """A derivação usa o discriminador já existente (par
    `renegociacao_pendente`/`troca_pendente`, o mesmo par de campos que
    compõe `origem` em `aplicar_gate_3_transformacao`), sem introduzir um
    quinto valor de `TIPO_ACAO` — os dois resultados possíveis pertencem a
    `TIPO_ACAO_VALORES`."""
    renegociacao = gates._derivar_TIPO_ACAO_gate_3(
        renegociacao_pendente=True, troca_pendente=False
    )
    troca = gates._derivar_TIPO_ACAO_gate_3(renegociacao_pendente=False, troca_pendente=True)
    ambos = gates._derivar_TIPO_ACAO_gate_3(renegociacao_pendente=True, troca_pendente=True)

    assertar_exato(renegociacao, "RENEGOCIACAO")
    assertar_exato(troca, "TROCA")
    assertar_exato(ambos, "RENEGOCIACAO")
    assert {renegociacao, troca, ambos} <= gates.TIPO_ACAO_VALORES


# ---------------------------------------------------------------------------
# T-87 — RF-32/AC-56/AC-57/EC-22: Gate 1 emite AcaoRequerida nos dois ramos
# de bloqueio, em vez de acao=None.
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_gate1_quitada_a_confirmar_emite_acao_informacao() -> None:
    """AC-56: `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` produz `ResultadoGates.
    acao` não `None`, com `TIPO_ACAO="INFORMACAO"` e
    `CAMPO_PENDENTE="STATUS_DIVIDA"`."""
    divida = _divida(STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR)
    resultado = gates.aplicar_gate_1_informacao(divida, _valor_relevante_ok(divida))

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "INFORMACAO")
    assertar_exato(resultado.acao.CAMPO_PENDENTE, "STATUS_DIVIDA")
    assertar_exato(resultado.acao.gate_origem, 1)
    assertar_exato(resultado.acao.DIVIDA_ID, divida.DIVIDA_ID)
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:INFORMACAO")


@pytest.mark.regra
def test_gate1_saldo_desconhecido_emite_acao_informacao() -> None:
    """AC-57: `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` dentro de `compor_VALOR_
    RELEVANTE_PARA_QUITACAO` produz `ResultadoGates.acao` não `None`, com
    `TIPO_ACAO="INFORMACAO"` e `CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"`."""
    divida = _divida(
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
    )
    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO, DESCONHECIDO)

    resultado = gates.aplicar_gate_1_informacao(divida, resultado_valor_relevante)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.TIPO_ACAO, "INFORMACAO")
    assertar_exato(resultado.acao.CAMPO_PENDENTE, "SALDO_DEVEDOR_ATUAL")
    assertar_exato(resultado.acao.gate_origem, 1)
    assertar_exato(resultado.acao.DIVIDA_ID, divida.DIVIDA_ID)
    assertar_exato(resultado.acao.ACAO_ID, f"{divida.DIVIDA_ID}:INFORMACAO")


@pytest.mark.regra
def test_gate1_dois_ramos_mutuamente_exclusivos() -> None:
    """EC-22: os dois ramos de bloqueio do Gate 1 são mutuamente exclusivos
    por construção — uma dívida com `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` E
    `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` simultaneamente é bloqueada pelo
    PRIMEIRO ramo (o `if` de `STATUS_DIVIDA` retorna antes do segundo `if`
    ser avaliado) — `CAMPO_PENDENTE` sai `"STATUS_DIVIDA"`, nunca
    `"SALDO_DEVEDOR_ATUAL"`, e nunca os dois ao mesmo tempo."""
    divida = _divida(
        STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR,
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
    )
    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    resultado = gates.aplicar_gate_1_informacao(divida, resultado_valor_relevante)

    assert resultado is not None
    assert resultado.acao is not None
    assertar_exato(resultado.acao.CAMPO_PENDENTE, "STATUS_DIVIDA")
    assert resultado.acao.CAMPO_PENDENTE != "SALDO_DEVEDOR_ATUAL"
