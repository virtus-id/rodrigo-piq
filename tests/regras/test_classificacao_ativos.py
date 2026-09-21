"""Testes de `classificar_investimento`/`classificar_ativo_fisico` (T-122,
T-123) — RF-53, RF-54, RF-55, RF-56 · §14.3, §14.3.1, §14.4-§14.9 · §14.14
`classifyInvestment`/`classifyPhysicalAsset`.

Cobre `classificar_investimento` (seis regras + precedência forçada) e
`classificar_ativo_fisico` (oito ramos + precedência forçada + bloqueio de
veículo) com os cenários literais de `GAB-NFI-06` a `GAB-NFI-11` (§14.16) e
os dois casos de precedência de `AC-95`/`AC-96`. Estes são os testes de
comportamento que substituem a "verificação manual" registrada em
`T-122`/`T-123` — pedido explícito de `T-127`.

`assertar_exato` em toda asserção: `CLASSIFICACAO_MOBILIZACAO`/`None` é
tolerância zero por natureza (enum e sentinela, não valor acumulado).
"""

import pytest

from engine.classificacao_ativos import classificar_ativo_fisico, classificar_investimento
from engine.estado import (
    DISPOSICAO_USO_INVESTIMENTO,
    ESSENCIALIDADE,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
    ItemInvestimento,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO
from tests.conftest import assertar_exato


def _investimento(
    *,
    disposicao: DISPOSICAO_USO_INVESTIMENTO,
    liquidez: LIQUIDEZ_INVESTIMENTOS,
    valor_liquido_disponivel: int,
    sem_custo_perda_relevante: bool = True,
    tem_custo_conhecido: bool = False,
) -> ItemInvestimento:
    """Fixture local — monta `ItemInvestimento` a partir dos campos BRUTOS
    de §14.3.1 que os cenários deste arquivo variam. `VALOR_LIQUIDO_
    REALIZAVEL`/`POSSUI_LIQUIDEZ` são irrelevantes para `classificar_
    investimento` (não lidos pela função) e recebem valores neutros."""
    return ItemInvestimento(
        ITEM_ID="INV-TESTE",
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(valor_liquido_disponivel),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=liquidez,
        DISPOSICAO_USO_INVESTIMENTO=disposicao,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(valor_liquido_disponivel),
        TEM_CUSTO_CONHECIDO=tem_custo_conhecido,
        SEM_CUSTO_PERDA_RELEVANTE=sem_custo_perda_relevante,
    )


def _ativo(
    *,
    tipo: TIPO_ATIVO_FISICO = TIPO_ATIVO_FISICO.OUTRO_ATIVO,
    possibilidade_venda: POSSIBILIDADE_VENDA,
    essencialidade: ESSENCIALIDADE,
    valor_estimado: int = 30000,
    possui_passivo_vinculado: bool = False,
    saldo_passivo_vinculado: int | None = None,
    possui_custo_desmobilizacao: bool = False,
    custos_estimados_desmobilizacao: int | None = None,
    renda_recorrente_ativo: int | None = 0,
    custo_recorrente_ativo: int = 0,
) -> ItemAtivo:
    """Fixture local — monta `ItemAtivo` a partir dos campos BRUTOS de
    §14.4-§14.9/§14.12 que os cenários deste arquivo variam.
    `renda_recorrente_ativo=None` propaga o sentinela ESTRUTURAL de
    `RF-56`/`OQ-38` (`RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None`)."""
    return ItemAtivo(
        ITEM_ID="ATV-TESTE",
        TIPO_ATIVO_FISICO=tipo,
        POSSIBILIDADE_VENDA=possibilidade_venda,
        ESSENCIALIDADE=essencialidade,
        VALOR_ESTIMADO_ATIVO=dinheiro(valor_estimado),
        POSSUI_PASSIVO_VINCULADO=possui_passivo_vinculado,
        SALDO_PASSIVO_VINCULADO=(
            dinheiro(saldo_passivo_vinculado)
            if saldo_passivo_vinculado is not None
            else dinheiro(0)
        ),
        POSSUI_CUSTO_DESMOBILIZACAO=possui_custo_desmobilizacao,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=(
            dinheiro(custos_estimados_desmobilizacao)
            if custos_estimados_desmobilizacao is not None
            else dinheiro(0)
        ),
        RENDA_RECORRENTE_ATIVO=(
            dinheiro(renda_recorrente_ativo) if renda_recorrente_ativo is not None else None
        ),
        CUSTO_RECORRENTE_ATIVO=dinheiro(custo_recorrente_ativo),
    )


# ---------------------------------------------------------------------------
# classificar_investimento — RF-53, §14.3.1
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_GAB_NFI_06_investimento_bloqueado() -> None:
    """`GAB-NFI-06` (`AC-88`): `DISPOSICAO_USO_INVESTIMENTO=SIM`,
    `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO` → `NAO_MOBILIZAR` — a Regra 1
    (bloqueio) vence independentemente da disposição ser `SIM`."""
    item = _investimento(
        disposicao=DISPOSICAO_USO_INVESTIMENTO.SIM,
        liquidez=LIQUIDEZ_INVESTIMENTOS.BLOQUEADO,
        valor_liquido_disponivel=10000,
    )
    assertar_exato(classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR)


@pytest.mark.regra
def test_GAB_NFI_07_investimento_liquido_e_disponivel() -> None:
    """`GAB-NFI-07` (`AC-89`): `DISPOSICAO_USO_INVESTIMENTO=SIM`,
    `LIQUIDEZ_INVESTIMENTOS=D1`, sem custo relevante conhecido,
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=10.000` →
    `MOBILIZACAO_RECOMENDAVEL` (Regra 4)."""
    item = _investimento(
        disposicao=DISPOSICAO_USO_INVESTIMENTO.SIM,
        liquidez=LIQUIDEZ_INVESTIMENTOS.D1,
        valor_liquido_disponivel=10000,
        sem_custo_perda_relevante=True,
    )
    assertar_exato(
        classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    )


@pytest.mark.regra
def test_GAB_NFI_08_disposicao_talvez() -> None:
    """`GAB-NFI-08` (`AC-90`): `DISPOSICAO_USO_INVESTIMENTO=TALVEZ`,
    investimento efetivamente resgatável (liquidez não `BLOQUEADO`, Regra 1
    não dispara) → `MOBILIZACAO_POSSIVEL` (Regra 3)."""
    item = _investimento(
        disposicao=DISPOSICAO_USO_INVESTIMENTO.TALVEZ,
        liquidez=LIQUIDEZ_INVESTIMENTOS.D7,
        valor_liquido_disponivel=10000,
    )
    assertar_exato(classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL)


@pytest.mark.regra
def test_regra_1_vence_regra_4_quando_ambas_se_aplicam() -> None:
    """`AC-95`, `EC-33`: investimento que satisfaz simultaneamente a Regra 1
    (`LIQUIDEZ_INVESTIMENTOS=BLOQUEADO`) e, não fosse o bloqueio, também
    satisfaria a Regra 4 (`DISPOSICAO_USO_INVESTIMENTO=SIM`, liquidez em
    `{D0,D1,D7}`, sem custo, valor líquido positivo) → `NAO_MOBILIZAR`, a
    PRIMEIRA regra da ordem de precedência, nunca a Regra 4 mesmo sendo
    satisfeita isoladamente."""
    item = _investimento(
        disposicao=DISPOSICAO_USO_INVESTIMENTO.SIM,
        liquidez=LIQUIDEZ_INVESTIMENTOS.BLOQUEADO,
        valor_liquido_disponivel=10000,
        sem_custo_perda_relevante=True,
    )
    assertar_exato(classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR)


@pytest.mark.regra
def test_investimento_tipo_poupanca_liquidez_longa_e_ressalvas_nao_recomendavel() -> None:
    """`EC-37`, §14.3.1.1: investimento do tipo comumente associado a alta
    liquidez (ex.: poupança) com `LIQUIDEZ_INVESTIMENTOS=MAIS_30` na entrada
    → `MOBILIZACAO_COM_RESSALVAS` (Regra 6), contrariando a presunção
    "poupança = recomendável" que a função é proibida de fazer — nenhum
    parâmetro de "tipo" existe na assinatura, só `LIQUIDEZ_INVESTIMENTOS`
    real decide."""
    item = _investimento(
        disposicao=DISPOSICAO_USO_INVESTIMENTO.SIM,
        liquidez=LIQUIDEZ_INVESTIMENTOS.MAIS_30,
        valor_liquido_disponivel=10000,
        sem_custo_perda_relevante=True,
        tem_custo_conhecido=False,
    )
    assertar_exato(
        classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    )


# ---------------------------------------------------------------------------
# classificar_ativo_fisico — RF-54, RF-55, RF-56, §14.4-§14.9
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_GAB_NFI_09_imovel_essencial_nunca_recomendavel() -> None:
    """`GAB-NFI-09` (`AC-91`, `EC-34`): `ESSENCIALIDADE=ESSENCIAL`,
    `POSSIBILIDADE_VENDA=SIM` → `MOBILIZACAO_COM_RESSALVAS`. O mesmo
    cenário trocando `POSSIBILIDADE_VENDA` para `JA_PRETENDE` (a disposição
    de venda mais favorável do domínio) TAMBÉM produz `MOBILIZACAO_COM_
    RESSALVAS` — essencialidade prevalece sobre qualquer disposição de
    venda (§14.5, REGRA CANÔNICA), nunca `MOBILIZACAO_RECOMENDAVEL` em
    nenhum dos dois."""
    item_sim = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.ESSENCIAL,
        valor_estimado=30000,
    )
    item_ja_pretende = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.JA_PRETENDE,
        essencialidade=ESSENCIALIDADE.ESSENCIAL,
        valor_estimado=30000,
    )

    assertar_exato(
        classificar_ativo_fisico(item_sim), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    )
    assertar_exato(
        classificar_ativo_fisico(item_ja_pretende),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
    )
    assert classificar_ativo_fisico(item_sim) != CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    assert (
        classificar_ativo_fisico(item_ja_pretende)
        != CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    )


@pytest.mark.regra
def test_GAB_NFI_10_nao_essencial_fluxo_negativo_recomendavel() -> None:
    """`GAB-NFI-10` (`AC-92`): `ESSENCIALIDADE=NAO_ESSENCIAL`,
    `POSSIBILIDADE_VENDA=SIM`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=
    30.000`, `FLUXO_LIQUIDO_RECORRENTE_ATIVO=-500` → `MOBILIZACAO_
    RECOMENDAVEL` (ramo 8c, `FLUXO <= 0`). `FLUXO=-500` construído com
    `RENDA_RECORRENTE_ATIVO=0`, `CUSTO_RECORRENTE_ATIVO=500`."""
    item = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.NAO_ESSENCIAL,
        valor_estimado=30000,
        renda_recorrente_ativo=0,
        custo_recorrente_ativo=500,
    )
    assertar_exato(
        classificar_ativo_fisico(item), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    )


@pytest.mark.regra
def test_GAB_NFI_11_nao_essencial_fluxo_positivo_possivel() -> None:
    """`GAB-NFI-11` (`AC-93`): mesmo cenário de `GAB-NFI-10` exceto
    `FLUXO_LIQUIDO_RECORRENTE_ATIVO=+700` → `MOBILIZACAO_POSSIVEL` (ramo
    8d, `FLUXO > 0`) — fluxo recorrente positivo impede `MOBILIZACAO_
    RECOMENDAVEL` mesmo com o mesmo valor líquido disponível de
    `GAB-NFI-10`. `FLUXO=+700` construído com `RENDA_RECORRENTE_ATIVO=700`,
    `CUSTO_RECORRENTE_ATIVO=0`."""
    item = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.NAO_ESSENCIAL,
        valor_estimado=30000,
        renda_recorrente_ativo=700,
        custo_recorrente_ativo=0,
    )
    assertar_exato(classificar_ativo_fisico(item), CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL)


@pytest.mark.regra
def test_bloqueio_de_venda_vence_dado_desconhecido_simultaneo() -> None:
    """`AC-96`: ativo físico que satisfaz simultaneamente `POSSIBILIDADE_
    VENDA=NAO` (bloqueio, ramo 1) E a condição de dado desconhecido para
    apurar o valor líquido disponível (ramo 2, `VALOR_ESTIMADO_ATIVO`
    desconhecido) → `NAO_MOBILIZAR` — a ordem de precedência da §14.4.1
    (bloqueio primeiro) prevalece sobre a §14.4.2, mesmo que o dado
    desconhecido também dispararia por si só."""
    item = ItemAtivo(
        ITEM_ID="ATV-BLOQUEIO-DESCONHECIDO",
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.NAO,
        ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
        VALOR_ESTIMADO_ATIVO=DESCONHECIDO,
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=dinheiro(0),
        CUSTO_RECORRENTE_ATIVO=dinheiro(0),
    )
    assertar_exato(classificar_ativo_fisico(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR)


@pytest.mark.regra
@pytest.mark.parametrize(
    "essencialidade", [ESSENCIALIDADE.IMPORTANTE, ESSENCIALIDADE.PARCIAL]
)
def test_importante_ou_parcial_com_venda_nao_e_bloqueado_nao_ramo_14_6(
    essencialidade: ESSENCIALIDADE,
) -> None:
    """`EC-35`: `ESSENCIALIDADE em {IMPORTANTE, PARCIAL}` com
    `POSSIBILIDADE_VENDA=NAO` → `NAO_MOBILIZAR` pelo bloqueio de §14.4.1
    (ramo 1, avaliado ANTES da ramificação por essencialidade), não um
    resultado de §14.6 (que só trata `EXTREMO`/`TALVEZ`/`SIM`/
    `JA_PRETENDE` — `POSSIBILIDADE_VENDA=NAO` nunca alcança aquele ramo por
    essa via)."""
    item = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.NAO,
        essencialidade=essencialidade,
        valor_estimado=30000,
    )
    assertar_exato(classificar_ativo_fisico(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR)


@pytest.mark.regra
def test_veiculo_nao_essencial_sem_renda_recorrente_retorna_none() -> None:
    """`AC-100`, `EC-39`: ativo físico do tipo VEÍCULO, `ESSENCIALIDADE=
    NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`, `RENDA_RECORRENTE_ATIVO=
    None` (ausência ESTRUTURAL, `OQ-38`) → retorno `is None`, nenhum valor
    do domínio de `CLASSIFICACAO_MOBILIZACAO` — não é `MOBILIZACAO_
    POSSIVEL`/`_RECOMENDAVEL`/`_COM_RESSALVAS`/`NAO_MOBILIZAR` por
    nenhuma via, inclusive a de "tratar como desconhecido" que `RF-56`
    proíbe explicitamente. Este é o teste da FUNÇÃO em si — comportamento
    de `classificar_ativo_fisico` isolada — separado do teste estrutural de
    `T-131` (`tests/estatica/test_veiculo_nao_essencial_bloqueado.py`), que
    prova a garantia no nível do código-fonte, não da chamada."""
    item = _ativo(
        tipo=TIPO_ATIVO_FISICO.VEICULO,
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.NAO_ESSENCIAL,
        valor_estimado=30000,
        renda_recorrente_ativo=None,
    )
    obtido = classificar_ativo_fisico(item)

    assert obtido is None
    assert not isinstance(obtido, CLASSIFICACAO_MOBILIZACAO)
