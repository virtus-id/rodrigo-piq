"""`GAB-NFI-09` — imóvel essencial (`T-129`).

Gabarito oficial de homologação da §14.16, transcrito do documento canônico
PIQ v1.0.1 (Fechamento Canônico — Necessidade Financeira Imediata e
Classificação de Ativos, congelado em 2026-09-09).

    `GAB-NFI-09`
      Cenário .......... `ESSENCIALIDADE=ESSENCIAL`,
                         `POSSIBILIDADE_VENDA=SIM`
      Resultado ........ `MOBILIZACAO_COM_RESSALVAS` (nunca RECOMENDAVEL)

Âncora: `AC-91` (`US-19`), `RF-54`, §14.5 REGRA CANÔNICA, §14.16.

**Tolerância ZERO** (spec §5, mesma régua dos `GAB-AI`, `T-129`):
`assertar_exato` — comparação de `Enum`, não de valor monetário.

Este é o gabarito FORMAL, com marcador `gabarito_classificacao_ativos`, que
compõe o portão de homologação `pytest -m "gabarito or invariante or
gabarito_ataque_imediato or gabarito_classificacao_ativos"`. O mesmo cenário
aparece como teste de REGRA em `tests/regras/test_classificacao_ativos.py`
(`T-127`) — os dois lugares são deliberados e devem concordar: divergência
entre eles é erro real, não duplicação.
"""

import pytest

from engine.classificacao_ativos import classificar_ativo_fisico
from engine.estado import ESSENCIALIDADE, POSSIBILIDADE_VENDA, TIPO_ATIVO_FISICO, ItemAtivo
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO
from tests.conftest import assertar_exato


@pytest.mark.gabarito_classificacao_ativos
def test_gab_nfi_09_imovel_essencial() -> None:
    """`GAB-NFI-09` · `AC-91` · §14.16: `ESSENCIALIDADE=ESSENCIAL`,
    `POSSIBILIDADE_VENDA=SIM` → `MOBILIZACAO_COM_RESSALVAS` — **nunca**
    `MOBILIZACAO_RECOMENDAVEL`, por mais favorável que seja
    `POSSIBILIDADE_VENDA` (§14.5, REGRA CANÔNICA: essencialidade prevalece
    sobre disposição de venda).
    """
    item = ItemAtivo(
        ITEM_ID="ATV-GAB-NFI-09",
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
        ESSENCIALIDADE=ESSENCIALIDADE.ESSENCIAL,
        VALOR_ESTIMADO_ATIVO=dinheiro(30000),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=dinheiro(0),
        CUSTO_RECORRENTE_ATIVO=dinheiro(0),
    )

    obtido = classificar_ativo_fisico(item)

    assertar_exato(obtido, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS)
    assert obtido != CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
