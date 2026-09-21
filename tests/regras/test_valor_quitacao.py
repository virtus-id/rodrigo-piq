"""Testes de `compor_VALOR_RELEVANTE_PARA_QUITACAO` — RF-06, AC-20, AC-21,
EC-14, §11.2.

Um teste por linha da tabela da §11.2 da spec do slug:

| Situação                   | Comportamento                                    |
| --------------------------- | ------------------------------------------------ |
| Proposta expirada           | Fallback para `SALDO_DEVEDOR_ATUAL`               |
| Quitação nunca consultada   | Fallback para `SALDO_DEVEDOR_ATUAL`               |
| Validade desconhecida       | Fallback para saldo; `PRIORIDADE_INFORMACAO` se   |
|                              | a diferença for materialmente relevante           |
| Saldo também desconhecido   | `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO`    |

Mais o caso positivo (quitação confirmada + validade vigente, o "SE" da
fórmula), o negativo de EC-14 (validade desconhecida mas sem diferença
relevante) e AC-21 isolado (sem quitação vigente E saldo desconhecido).

`_divida_base` monta uma `Divida` completa e válida com valores neutros em
todos os campos que `compor_VALOR_RELEVANTE_PARA_QUITACAO` não lê — o mesmo
padrão de `_sinais_comportamentais`/`_PERFIL_FORTE_BASE` em
`tests/regras/test_comportamento.py`: variar só o que o teste declara.
"""

import pytest

from engine.estado import TIPO_DIVIDA, Divida
from engine.precisao import dinheiro
from engine.tipos import (
    DESCONHECIDO,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    DinheiroTalvez,
    SimNaoTalvez,
)
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO
from tests.conftest import assertar_exato


def _divida_base(
    *,
    saldo_devedor_atual: DinheiroTalvez,
    valor_quitacao_hoje: DinheiroTalvez,
    quitacao_consultada: SimNaoTalvez,
    status_validade_proposta: STATUS_VALIDADE_PROPOSTA,
) -> Divida:
    """Monta uma `Divida` completa e válida, variando apenas os quatro campos
    que a fórmula de §11.2 lê. Os demais recebem valores neutros — nenhum é
    consumido por `compor_VALOR_RELEVANTE_PARA_QUITACAO`."""
    return Divida(
        DIVIDA_ID="D001",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo_devedor_atual,
        VALOR_QUITACAO_HOJE=valor_quitacao_hoje,
        QUITACAO_CONSULTADA=quitacao_consultada,
        STATUS_VALIDADE_PROPOSTA=status_validade_proposta,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=DESCONHECIDO,
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=dinheiro("500"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("500"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=DESCONHECIDO,
        PESO_EMOCIONAL=DESCONHECIDO,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


@pytest.mark.regra
def test_quitacao_confirmada_e_vigente_usa_valor_de_quitacao() -> None:
    """§11.2 — ramo "SE": `QUITACAO_CONSULTADA = SIM`, `VALOR_QUITACAO_HOJE`
    conhecido e `STATUS_VALIDADE_PROPOSTA = VIGENTE` ⇒ usa
    `VALOR_QUITACAO_HOJE`, nunca o saldo."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=dinheiro("8500"),
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VIGENTE,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("8500"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)


@pytest.mark.regra
def test_proposta_expirada_usa_fallback_para_saldo() -> None:
    """Tabela §11.2, linha "Proposta expirada": `STATUS_VALIDADE_PROPOSTA =
    EXPIRADA` ⇒ não usa `VALOR_QUITACAO_HOJE`; fallback para
    `SALDO_DEVEDOR_ATUAL` (`AC-20`)."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=dinheiro("8500"),
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.EXPIRADA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)


@pytest.mark.regra
def test_quitacao_nunca_consultada_usa_fallback_para_saldo() -> None:
    """Tabela §11.2, linha "Quitação nunca consultada": `QUITACAO_CONSULTADA
    = NAO` ⇒ fallback para `SALDO_DEVEDOR_ATUAL`, independentemente do que
    `VALOR_QUITACAO_HOJE`/`STATUS_VALIDADE_PROPOSTA` digam (`AC-20`)."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=DESCONHECIDO,
        quitacao_consultada=SimNaoTalvez.NAO,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)


@pytest.mark.regra
def test_EC14_validade_desconhecida_gera_prioridade_informacao() -> None:
    """EC-14 — caso positivo: `STATUS_VALIDADE_PROPOSTA =
    VALIDADE_DESCONHECIDA`, com `VALOR_QUITACAO_HOJE` e `SALDO_DEVEDOR_ATUAL`
    conhecidos e DIFERENTES. Não trata como vigente (fallback para saldo) e
    sinaliza `PRIORIDADE_INFORMACAO`, pois a diferença pode alterar
    materialmente a decisão."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=dinheiro("8500"),
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, True)
    assert resultado.motivo is not None
    assert "D001" in resultado.motivo


@pytest.mark.regra
def test_validade_desconhecida_com_valores_iguais_nao_gera_prioridade() -> None:
    """Caso negativo de EC-14: `STATUS_VALIDADE_PROPOSTA =
    VALIDADE_DESCONHECIDA`, mas `VALOR_QUITACAO_HOJE` e `SALDO_DEVEDOR_ATUAL`
    são IGUAIS — a diferença não pode alterar materialmente a decisão, então
    não gera `PRIORIDADE_INFORMACAO`. Ainda assim usa o saldo (fallback)."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=dinheiro("10000"),
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)
    assertar_exato(resultado.motivo, None)


@pytest.mark.regra
def test_validade_desconhecida_com_valor_quitacao_tambem_desconhecido_nao_gera_prioridade() -> (
    None
):
    """Segunda variante do caso negativo de EC-14: `VALOR_QUITACAO_HOJE` é o
    próprio `DESCONHECIDO` (nunca consultado com sucesso) — não há diferença
    a comparar, então não gera `PRIORIDADE_INFORMACAO`. Fallback para saldo
    normalmente."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=DESCONHECIDO,
        quitacao_consultada=SimNaoTalvez.TALVEZ,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)


@pytest.mark.regra
def test_AC21_saldo_desconhecido_propaga_desconhecido() -> None:
    """AC-21: sem quitação vigente (aqui, nunca consultada) E
    `SALDO_DEVEDOR_ATUAL = DESCONHECIDO` ⇒
    `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` — nunca uma estimativa
    (RF-16)."""
    divida = _divida_base(
        saldo_devedor_atual=DESCONHECIDO,
        valor_quitacao_hoje=DESCONHECIDO,
        quitacao_consultada=SimNaoTalvez.NAO,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, DESCONHECIDO)


@pytest.mark.regra
def test_AC21_saldo_desconhecido_com_quitacao_expirada_propaga_desconhecido() -> None:
    """Variante de AC-21 com proposta EXPIRADA em vez de nunca consultada:
    mesmo com `VALOR_QUITACAO_HOJE` conhecido, a ausência de vigência e o
    saldo `DESCONHECIDO` ainda propagam `DESCONHECIDO` — o valor de quitação
    não vigente nunca substitui o saldo ausente."""
    divida = _divida_base(
        saldo_devedor_atual=DESCONHECIDO,
        valor_quitacao_hoje=dinheiro("8500"),
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.EXPIRADA,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, DESCONHECIDO)


@pytest.mark.regra
def test_valor_quitacao_desconhecido_com_validade_vigente_usa_fallback() -> None:
    """Fronteira da conjunção do "SE": `STATUS_VALIDADE_PROPOSTA = VIGENTE`
    sozinho não basta — se `VALOR_QUITACAO_HOJE` é `DESCONHECIDO` (não há
    valor "confirmado" para usar), cai no `SENÃO` e usa o saldo. Prova que a
    ponte T-08 (`QUITACAO_CONSULTADA == SIM E VALOR_QUITACAO_HOJE !=
    DESCONHECIDO`) é avaliada em conjunção, não isoladamente."""
    divida = _divida_base(
        saldo_devedor_atual=dinheiro("10000"),
        valor_quitacao_hoje=DESCONHECIDO,
        quitacao_consultada=SimNaoTalvez.SIM,
        status_validade_proposta=STATUS_VALIDADE_PROPOSTA.VIGENTE,
    )
    resultado = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    assertar_exato(resultado.VALOR_RELEVANTE_PARA_QUITACAO, dinheiro("10000"))
    assertar_exato(resultado.gerou_PRIORIDADE_INFORMACAO, False)
