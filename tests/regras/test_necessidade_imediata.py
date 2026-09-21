"""Testes de `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_
ELEGIVEL` — `engine/gates.py`, `RF-64`, `RF-65` · §14.1/§14.1.1 · `T-137`.

Cobre `GAB-NFI-01` a `GAB-NFI-05` (§14.16) mais precedência forçada, trava de
dupla contagem, incompletude e os demais critérios de `T-137`. Cada teste
cita `AC-NN`/`EC-NN`/`GAB-NFI-NN` na docstring, conforme exigido pela tarefa.

`NECESSIDADE_IMEDIATA_DIVIDA` é função pura de quatro parâmetros keyword-only
(`GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO`,
`acao_financeira_imediata_executavel`, `VALOR_RELEVANTE_PARA_QUITACAO`) — os
testes desta função constroem os quatro insumos diretamente, sem passar por
`Divida`/`particionar_elegibilidade`, exatamente como a assinatura da função
pede (`T-134`). `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` soma sobre uma
`ParticaoElegibilidade` completa (`T-135`) — os testes dela constroem
`Divida`/`ResultadoGates` reais via `particionar_elegibilidade`, para exercer
a soma sobre o inventário de ponta a ponta.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.estado import TIPO_DIVIDA, Divida
from engine.gates import (
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
    NECESSIDADE_IMEDIATA_DIVIDA,
    AcaoRequerida,
    particionar_elegibilidade,
)
from engine.precisao import dinheiro
from engine.tipos import (
    DESCONHECIDO,
    DIVIDA_STATUS_ESTRATEGICO,
    GATE_PENDENTE,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from tests.conftest import assertar_exato


def _divida(**overrides: object) -> Divida:
    """Dívida "sem bloqueio" por padrão — mesmo padrão de
    `tests/regras/test_gates.py::_divida`, reaproveitado aqui para os testes
    de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` que precisam de um
    inventário real via `particionar_elegibilidade`."""
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


def _acao(**overrides: object) -> AcaoRequerida:
    """`AcaoRequerida` mínima para os testes de
    `NECESSIDADE_IMEDIATA_DIVIDA` que precisam do parâmetro
    `acao_financeira_imediata_executavel` — valores neutros por padrão,
    sobrescritos caso a caso."""
    base: dict[str, object] = dict(
        ACAO_ID="D-01:RENEGOCIACAO",
        DIVIDA_ID="D-01",
        TIPO_ACAO="RENEGOCIACAO",
        descricao="ação de teste",
        gate_origem=2,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
    )
    base.update(overrides)
    return AcaoRequerida(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GAB-NFI-01 a GAB-NFI-05 (§14.16) — NECESSIDADE_IMEDIATA_DIVIDA
# ---------------------------------------------------------------------------


@pytest.mark.regra
@pytest.mark.gabarito
def test_GAB_NFI_01_divida_ordinaria_elegivel() -> None:
    """`GAB-NFI-01`/`AC-101`: dívida ordinária elegível
    (`VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `PRONTA_PARA_ORDENACAO`, sem
    gate pendente, sem ação) → `20.000` exato, o valor integral (ramo 4)."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(20000),
    )
    assertar_exato(resultado, dinheiro(20000))


@pytest.mark.regra
@pytest.mark.gabarito
def test_GAB_NFI_02_gate_1_pendente_vence_tudo() -> None:
    """`GAB-NFI-02`/`AC-102`: `VALOR_RELEVANTE_PARA_QUITACAO=20.000` com
    `Gate1=PENDENTE` → `0` exato — Gate 1 pendente vence antes de qualquer
    outra condição ser avaliada (ramo 1)."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(20000),
    )
    assertar_exato(resultado, dinheiro(0))


@pytest.mark.regra
@pytest.mark.gabarito
def test_GAB_NFI_03_gate_3_pendente_vence_status_e_acao() -> None:
    """`GAB-NFI-03`/`AC-103`: `Gate3=PENDENTE`, Gate 1 resolvido, valor
    positivo → `0` exato — Gate 3 pendente vence sobre o status estratégico
    e sobre qualquer ação financeira imediata, mesmo com Gate 1 já
    resolvido (ramo 2, nunca alcança ramo 3 ou 4)."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.TRANSFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE,
        acao_financeira_imediata_executavel=_acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(9999)),
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(30000),
    )
    assertar_exato(resultado, dinheiro(0))


@pytest.mark.regra
@pytest.mark.gabarito
def test_GAB_NFI_04_acao_gate_2_ou_4_nunca_soma_com_valor_relevante() -> None:
    """`GAB-NFI-04`/`AC-104`: ação de Gate 2/4 executável com
    `VALOR_ACAO_FINANCEIRA_IMEDIATA=8.000`, mesma dívida com
    `VALOR_RELEVANTE_PARA_QUITACAO=15.000` → `8.000` exato, **nunca**
    `23.000` (trava de dupla contagem, `RF-65`) — ramo 3 vence e a cadeia
    `if`/`elif` nunca alcança o ramo 4."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=_acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(8000)),
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )
    assertar_exato(resultado, dinheiro(8000))
    assert resultado != dinheiro(23000), (
        "dupla contagem: NECESSIDADE_IMEDIATA_DIVIDA nunca soma "
        "VALOR_ACAO_FINANCEIRA_IMEDIATA com VALOR_RELEVANTE_PARA_QUITACAO"
    )


@pytest.mark.regra
@pytest.mark.gabarito
def test_GAB_NFI_05_acao_sem_desembolso_tem_valor_zero() -> None:
    """`GAB-NFI-05`/`AC-105`: ação "solicitar proposta", sem exigência de
    desembolso financeiro imediato → `VALOR_ACAO_FINANCEIRA_IMEDIATA=0`
    exato (§14.2.1: ação sem desembolso é sempre `0`, nunca `DESCONHECIDO`
    nem um valor inventado)."""
    acao_sem_desembolso = _acao(
        TIPO_ACAO="RENEGOCIACAO",
        descricao="solicitar proposta de quitação — sem desembolso",
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
    )
    assertar_exato(acao_sem_desembolso.VALOR_ACAO_FINANCEIRA_IMEDIATA, dinheiro(0))

    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=acao_sem_desembolso,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(5000),
    )
    assertar_exato(resultado, dinheiro(0))


# ---------------------------------------------------------------------------
# Precedência forçada e integralidade de VALOR_RELEVANTE_PARA_QUITACAO
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_precedencia_forcada_gate_1_pendente_e_status_elegivel_simultaneos() -> None:
    """`AC-102`/`RF-65`: dívida que satisfaz Gate 1 pendente **e** status
    elegível (`PRONTA_PARA_ORDENACAO`) simultaneamente → `0` (ramo 1 vence),
    nunca o valor do ramo 4. Cenário artificialmente contraditório (na
    prática `determinar_status_estrategico` nunca produz essa combinação),
    construído aqui para provar a ordem estrita da cadeia por si só,
    independente de qualquer invariante de outro módulo."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(50000),
    )
    assertar_exato(resultado, dinheiro(0))


@pytest.mark.regra
def test_valor_relevante_para_quitacao_e_sempre_integral_nunca_fracao() -> None:
    """`AC-107`/§14.1.2: valor alto onde uma fração "pareceria razoável"
    (ex. metade) → resultado é o valor **cheio**, sem multiplicação, `MIN`/
    `MAX` ou fração. `VALOR_RELEVANTE_PARA_QUITACAO` responde "quanto
    poderia ser usado agora", não "quanto vale a pena disponibilizar"."""
    valor_alto = dinheiro(120000)
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.EM_ATAQUE,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=valor_alto,
    )
    assertar_exato(resultado, valor_alto)
    assert resultado != dinheiro(60000), (
        "NECESSIDADE_IMEDIATA_DIVIDA nunca aplica fração/metade sobre "
        "VALOR_RELEVANTE_PARA_QUITACAO (AC-107)"
    )


@pytest.mark.regra
def test_gate_1_e_gate_3_pendentes_simultaneamente_gate_3_nunca_avaliado() -> None:
    """Gate 1 **e** Gate 3 pendentes simultaneamente → `0`, Gate 3 nunca
    avaliado — a cadeia `if`/`elif` para no primeiro ramo verdadeiro
    (`GATE_PENDENTE.INFORMACAO`), mesmo que o parâmetro recebido também
    fosse compatível com o bloqueio de Gate 3 num outro cenário. Aqui
    provado passando `GATE_PENDENTE.INFORMACAO` (o único valor que o
    parâmetro pode assumir por chamada) — o teste documenta que o ramo 2
    (Gate 3) estruturalmente nunca é alcançado quando o ramo 1 já decidiu."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=DESCONHECIDO,
    )
    assertar_exato(resultado, dinheiro(0))


# ---------------------------------------------------------------------------
# Ação de Gate 2/4: executável vs. não executável agora; valor DESCONHECIDO
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_acao_desconhecida_executavel_com_precedencia_material() -> None:
    """`RF-63`/`AC-109`/`EC-40`-`EC-46`: ação de Gate 2/4 executável agora
    com valor `DESCONHECIDO` (§14.2.2, "valor desconhecido em ação
    prioritária") → `NECESSIDADE_IMEDIATA_DIVIDA=DESCONHECIDO`, propagado
    — o ramo 3 ainda decide, não cai para o ramo 4/5. Este teste **não
    afirma nada sobre `STATUS_METODO`** (fora de escopo, fatia 4C)."""
    acao_com_valor_desconhecido = _acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO)
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=acao_com_valor_desconhecido,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )
    assertar_exato(resultado, DESCONHECIDO)
    assert resultado != dinheiro(15000), (
        "ação com valor DESCONHECIDO não cai para o ramo 4 "
        "(VALOR_RELEVANTE_PARA_QUITACAO) — o ramo 3 já decidiu DESCONHECIDO"
    )


@pytest.mark.regra
def test_acao_nao_executavel_agora_nao_entra_no_ramo_3() -> None:
    """`AC-101`/§14.1.1, ramo 3: ação de Gate 2/4 existente mas **não**
    executável agora — modelada como `acao_financeira_imediata_executavel=
    None` (o chamador só passa a ação quando ela É executável agora; ver
    docstring de `NECESSIDADE_IMEDIATA_DIVIDA`) — não entra no ramo 3, cai
    para 4/5. Aqui cai para o ramo 4 (status elegível)."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=None,  # ação existe mas não executável agora
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(12000),
    )
    assertar_exato(resultado, dinheiro(12000))


@pytest.mark.regra
def test_acao_executavel_com_valor_zero_conhecido_distinto_de_desconhecido() -> None:
    """§14.2.1: ação executável com valor `0` conhecido (regularização sem
    custo) → `0`, distinto de `DESCONHECIDO` — o ramo 3 devolve o `0`
    conhecido da ação, não um `DESCONHECIDO` por falta de dado."""
    acao_regularizacao_sem_custo = _acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0))
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=acao_regularizacao_sem_custo,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(7000),
    )
    assertar_exato(resultado, dinheiro(0))
    assert resultado is not DESCONHECIDO, (
        "0 conhecido não é o mesmo estado que DESCONHECIDO por falta de dado"
    )


# ---------------------------------------------------------------------------
# Status fora do domínio elegível (ramo 5)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_status_fora_do_dominio_elegivel_sem_gate_sem_acao_e_zero() -> None:
    """§14.1.1, ramo 5: status fora de `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}`
    (ex. `EM_ANALISE`), sem gate pendente, sem ação → `0` (nenhum dos
    quatro ramos anteriores se aplica)."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.EM_ANALISE,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(9000),
    )
    assertar_exato(resultado, dinheiro(0))


# ---------------------------------------------------------------------------
# Transição de estado: ação (ramo 3) → gate resolvido → status (ramo 4)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_transicao_de_acao_para_status_nunca_soma_os_dois_no_mesmo_estado() -> None:
    """`RF-65`/`AC-104`: dívida com ação (ramo 3) e, em segundo estado
    SIMULADO (nova chamada, não acumulação), gate resolvido → passa a
    contribuir por status (ramo 4) se elegível — nunca soma os dois valores
    no mesmo estado. Cada chamada representa um instante; a "transição" é
    modelada como duas chamadas independentes sobre a mesma dívida."""
    # Estado 1: ação de Gate 2/4 executável, valor 8.000.
    resultado_estado_1 = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=_acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(8000)),
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )
    assertar_exato(resultado_estado_1, dinheiro(8000))

    # Estado 2: gate/ação resolvidos (dívida "volta ao estoque ordinário
    # elegível", §14.2.3) — contribui pelo status, valor relevante integral.
    resultado_estado_2 = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=None,
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )
    assertar_exato(resultado_estado_2, dinheiro(15000))

    # Nenhum dos dois estados isolados produz a soma dos dois valores.
    assert resultado_estado_1 != dinheiro(23000)
    assert resultado_estado_2 != dinheiro(23000)


@pytest.mark.regra
def test_auditoria_dois_valores_positivos_diferentes_nunca_soma() -> None:
    """`RF-65`/`AC-104`, prova de auditoria — mesmo caso de `GAB-NFI-04`,
    repetido aqui como prova isolada e nomeada de auditoria: dívida com os
    dois valores positivos e diferentes (`VALOR_ACAO_FINANCEIRA_IMEDIATA=
    8.000`, `VALOR_RELEVANTE_PARA_QUITACAO=15.000`) → resultado é
    exatamente um dos dois, nunca a soma."""
    resultado = NECESSIDADE_IMEDIATA_DIVIDA(
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        acao_financeira_imediata_executavel=_acao(VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(8000)),
        VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(15000),
    )
    assert resultado in (dinheiro(8000), dinheiro(15000)), (
        f"resultado deveria ser exatamente um dos dois valores, obteve {resultado!r}"
    )
    assertar_exato(resultado, dinheiro(8000))
    assert resultado != dinheiro(8000) + dinheiro(15000)


# ---------------------------------------------------------------------------
# NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL — incompletude e soma sobre
# inventário real (via particionar_elegibilidade)
# ---------------------------------------------------------------------------


SEM_ACOES: dict[str, AcaoRequerida] = {}
# Mapa vazio reaproveitável — `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
# aceita qualquer `Mapping[str, AcaoRequerida]`; `dict` puro já satisfaz o
# protocolo. Cenários que precisam de ação associada a uma dívida específica
# constroem o próprio `dict` literal no local de uso.


@pytest.mark.regra
def test_incompletude_material_uma_divida_desconhecida_propaga_desconhecido() -> None:
    """`AC-108`/`EC-46`: inventário com uma dívida `DESCONHECIDO` e demais
    conhecidas/somáveis → `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=
    DESCONHECIDO`. A dívida "desconhecida" é modelada com
    `RISCO_MATERIAL_IMINENTE=True` (Gate 2, bloqueada) e uma ação financeira
    imediata executável associada com `VALOR_ACAO_FINANCEIRA_IMEDIATA=
    DESCONHECIDO` (§14.2.2, "valor desconhecido em ação prioritária") — o
    único caminho estrutural pelo qual uma dívida contribui `DESCONHECIDO`
    para a soma (ramo 3 de `NECESSIDADE_IMEDIATA_DIVIDA`; uma dívida com
    `SALDO_DEVEDOR_ATUAL=DESCONHECIDO` seria bloqueada pelo Gate 1 e
    contribuiria `0` pelo ramo 1, não `DESCONHECIDO` — ver ramo 1 vs. ramo 3
    na docstring de `NECESSIDADE_IMEDIATA_DIVIDA`). Compara explicitamente
    contra a soma das conhecidas, provando que essa soma parcial **não** é
    retornada."""
    divida_conhecida_1 = _divida(
        DIVIDA_ID="D-01",
        SALDO_DEVEDOR_ATUAL=Decimal("1000.00"),
        VALOR_QUITACAO_HOJE=Decimal("1000.00"),
    )
    divida_conhecida_2 = _divida(
        DIVIDA_ID="D-02",
        SALDO_DEVEDOR_ATUAL=Decimal("2000.00"),
        VALOR_QUITACAO_HOJE=Decimal("2000.00"),
    )
    divida_com_acao_desconhecida = _divida(
        DIVIDA_ID="D-03",
        RISCO_MATERIAL_IMINENTE=True,
    )
    acao_valor_desconhecido = _acao(
        ACAO_ID="D-03:RENEGOCIACAO",
        DIVIDA_ID="D-03",
        VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO,
    )

    particao = particionar_elegibilidade(
        (divida_conhecida_1, divida_conhecida_2, divida_com_acao_desconhecida)
    )
    resultado = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
        particao=particao,
        acoes_por_divida={"D-03": acao_valor_desconhecido},
    )

    assertar_exato(resultado, DESCONHECIDO)
    soma_das_conhecidas = dinheiro(1000) + dinheiro(2000)
    assert resultado != soma_das_conhecidas, (
        "propagação de DESCONHECIDO (AC-108/EC-46): a soma parcial das "
        "dívidas conhecidas nunca é apresentada como total definitivo"
    )


@pytest.mark.regra
def test_inventario_todo_com_zero_e_zero_legitimo_distinto_de_incompletude() -> None:
    """`EC-45`: inventário todo com `0` → `0` legítimo — teste **distinto**
    do de incompletude acima: aqui não há `DESCONHECIDO` nenhum, todas as
    dívidas contribuem `0` porque `VALOR_RELEVANTE_PARA_QUITACAO=0` para
    todas, e o resultado agregado é `0` conhecido, não `DESCONHECIDO`."""
    divida_saldo_zero_1 = _divida(
        DIVIDA_ID="D-01", SALDO_DEVEDOR_ATUAL=Decimal("0.00"), VALOR_QUITACAO_HOJE=Decimal("0.00")
    )
    divida_saldo_zero_2 = _divida(
        DIVIDA_ID="D-02", SALDO_DEVEDOR_ATUAL=Decimal("0.00"), VALOR_QUITACAO_HOJE=Decimal("0.00")
    )

    particao = particionar_elegibilidade((divida_saldo_zero_1, divida_saldo_zero_2))
    resultado = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
        particao=particao, acoes_por_divida=SEM_ACOES
    )

    assertar_exato(resultado, dinheiro(0))
    assert resultado is not DESCONHECIDO, "0 legítimo não é o mesmo estado que DESCONHECIDO"


@pytest.mark.regra
def test_inventario_vazio_e_zero() -> None:
    """§14.1: inventário vazio → `0`, estado legitimamente distinto de
    incompletude (`EC-45`) — soma sobre zero parcelas é o elemento neutro."""
    particao = particionar_elegibilidade(())
    resultado = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
        particao=particao, acoes_por_divida=SEM_ACOES
    )
    assertar_exato(resultado, dinheiro(0))
