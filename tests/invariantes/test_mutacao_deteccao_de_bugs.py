"""Teste de mutação — prova que as propriedades de `test_propriedades.py`
REJEITAM os dois bugs que `A-04`/`F-03` existem para prevenir — `T-48`,
critério de aceite 4.

Não editam `engine/ciclo_mensal.py`. Cada teste abaixo reimplementa, em uma
função LOCAL a este arquivo, uma cópia mutada da conta de verificação usada
pela propriedade real (`ataque_aplicado_total_do_mes` para `A-04`, a soma de
capacidades para `F-03`), com o bug introduzido de propósito, e aplica essa
cópia mutada sobre o MESMO rastro (`Cenario.meses`) que `simular_cenario`
(motor real, sem alteração) produz. Se a asserção da versão mutada nunca
falhasse, a propriedade não estaria testando nada — este arquivo prova o
contrário: a versão mutada FALHA de forma confiável, o que significa que a
versão real (em `test_propriedades.py`) tem poder de detecção sobre esses
dois bugs.

Decisão de onde documentar (critério de aceite 4, redação da tarefa): mantido
como teste automatizado permanente, não como script manual descartável — a
suíte já roda em CI (`sdd.config.md` §2, comando `test`), e um teste que
prova "a propriedade rejeita o bug" é, por si, uma proteção contra regressão
futura na lógica de verificação (se algum dia `assertar_exato` for trocado
por `assertar_monetario` aqui por engano, por exemplo, este arquivo pega).
Cada teste abaixo é marcado com `pytest.raises`/`assert` explícito sobre a
FALHA esperada da versão mutada — nunca `xfail` silencioso.

REGRAS: RF-03, RF-04, A-04, F-03
"""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from engine.ciclo_mensal import ResultadoMes
from engine.estado import TIPO_DIVIDA, Divida
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import DESCONHECIDO, STATUS_DIVIDA, STATUS_VALIDADE_PROPOSTA, SimNaoTalvez
from tests.conftest import assertar_exato
from tests.invariantes.test_propriedades import _divida, _simular


def _ataque_aplicado_total_do_mes_com_bug_descarta_residuo(resultado_mes: ResultadoMes) -> Decimal:
    """Mutação proposital de `ataque_aplicado_total_do_mes`
    (`test_propriedades.py`): descarta o resíduo aplicado na cascata —
    como se `A-02` nunca tivesse acontecido. Simula o bug real que `A-04`
    existe para prevenir: dinheiro cascateado desaparecendo da conta de
    conservação."""
    capacidade = resultado_mes.estado_final.CAPACIDADE_ATAQUE_M
    with localcontext(CONTEXTO_MOTOR):
        aplicado_no_alvo_original = capacidade - resultado_mes.RESIDUO_ATAQUE_M
        # BUG PROPOSITAL: `aplicacoes_residuo` (a cascata inteira) é
        # ignorada — o resíduo que efetivamente coube em outras dívidas some
        # da soma de conservação.
        return aplicado_no_alvo_original


def test_A04_mutacao_residuo_descartado_e_rejeitada_pela_propriedade() -> None:
    """Prova que `A-04` (via `assertar_exato`) DETECTA o bug de resíduo
    descartado: usa uma carteira de duas dívidas construída para forçar
    cascata (a primeira quita com folga e sobra resíduo para a segunda), e
    mostra que a conta MUTADA (sem a cascata) não fecha contra
    `CAPACIDADE_ATAQUE_M`, enquanto a conta REAL (mesma usada pela
    propriedade) fecha."""
    d1 = _divida("D-01", saldo=dinheiro("40"))
    d2 = _divida("D-02", saldo=dinheiro("1000"))
    dividas = {"D-01": d1, "D-02": d2}

    cenario = _simular(dividas, Decimal("100"))

    mes_com_cascata = next(
        (m for m in cenario.meses if m.aplicacoes_residuo), None
    )
    assert mes_com_cascata is not None, (
        "cenário de teste não produziu cascata — ajuste os saldos/capacidade "
        "para que este teste de mutação continue exercitando o bug"
    )

    # Conta REAL (mesma lógica de test_propriedades.py): fecha exatamente.
    with localcontext(CONTEXTO_MOTOR):
        aplicado_real = (
            mes_com_cascata.estado_final.CAPACIDADE_ATAQUE_M - mes_com_cascata.RESIDUO_ATAQUE_M
        ) + sum(
            (a.valor_aplicado for a in mes_com_cascata.aplicacoes_residuo), start=dinheiro("0")
        )
    assertar_exato(
        aplicado_real + mes_com_cascata.ATAQUE_NAO_UTILIZADO,
        mes_com_cascata.estado_final.CAPACIDADE_ATAQUE_M,
    )

    # Conta MUTADA (bug: descarta a cascata): NÃO fecha — a propriedade A-04
    # rejeitaria este resultado se ele fosse o valor de fato produzido pelo
    # motor.
    aplicado_mutado = _ataque_aplicado_total_do_mes_com_bug_descarta_residuo(mes_com_cascata)
    soma_mutada = aplicado_mutado + mes_com_cascata.ATAQUE_NAO_UTILIZADO
    with pytest.raises(AssertionError):
        assertar_exato(soma_mutada, mes_com_cascata.estado_final.CAPACIDADE_ATAQUE_M)


def _capacidade_esperada_com_bug_soma_fluxo_no_proprio_mes(
    mes_anterior: ResultadoMes,
) -> Decimal:
    """Mutação proposital: soma o `VALOR_FLUXO_LIBERADO` do mês à
    `CAPACIDADE_ATAQUE_M` do MESMO mês, simulando o bug que `F-03` proíbe
    (fluxo liberado contado como pagamento normal E como capacidade
    adicional dentro do mesmo mês m, em vez de só em m+1)."""
    with localcontext(CONTEXTO_MOTOR):
        return (
            mes_anterior.estado_final.CAPACIDADE_ATAQUE_M
            + mes_anterior.VALOR_FLUXO_LIBERADO
            + mes_anterior.VALOR_FLUXO_LIBERADO  # BUG PROPOSITAL: soma DUAS vezes
        )


def test_F03_mutacao_fluxo_somado_duas_vezes_e_rejeitada_pela_propriedade() -> None:
    """Prova que `F-03` (via `assertar_exato`) DETECTA o bug de dupla
    contagem: dívida não-alvo quitada só com pagamento normal no mês 1
    libera fluxo > 0; a capacidade REAL do mês 2 incorpora esse fluxo uma
    única vez (M-11), enquanto a versão MUTADA (que soma duas vezes) diverge
    do valor real observado."""
    # D-01 (não-alvo) quita só com pagamento normal de 700 no mês 1,
    # liberando 700 (F-01/EC-18: efetivo, não contratual). D-02 (alvo, menor
    # saldo — escolhida no bootstrap) tem saldo grande e ataca aos poucos.
    d1 = _divida_com_pagamento_normal("D-01", saldo=dinheiro("700"))
    d2 = _divida("D-02", saldo=dinheiro("2000"))
    dividas = {"D-01": d1, "D-02": d2}

    cenario = _simular(dividas, Decimal("100"))
    assert len(cenario.meses) >= 2, (
        "cenário de teste não produziu ao menos dois meses — ajuste os "
        "saldos/capacidade para que este teste de mutação continue "
        "exercitando o bug"
    )

    mes_1 = cenario.meses[0]
    mes_2 = cenario.meses[1]
    assert mes_1.VALOR_FLUXO_LIBERADO != dinheiro("0"), (
        "cenário de teste não liberou fluxo no mês 1 — ajuste os saldos "
        "para que este teste de mutação continue exercitando o bug"
    )

    # Conta REAL: a capacidade do mês 2 é exatamente capacidade(mês 1) +
    # fluxo liberado(mês 1), uma única vez (M-11) — mesma verificação de
    # test_propriedades.py::test_F03_fluxo_liberado_nunca_soma_na_capacidade_do_proprio_mes.
    with localcontext(CONTEXTO_MOTOR):
        capacidade_esperada_real = (
            mes_1.estado_final.CAPACIDADE_ATAQUE_M + mes_1.VALOR_FLUXO_LIBERADO
        )
    assertar_exato(mes_2.estado_final.CAPACIDADE_ATAQUE_M, capacidade_esperada_real)

    # Conta MUTADA (bug: soma o fluxo duas vezes): diverge do valor real
    # observado — a propriedade F-03 rejeitaria este resultado.
    capacidade_mutada = _capacidade_esperada_com_bug_soma_fluxo_no_proprio_mes(mes_1)
    with pytest.raises(AssertionError):
        assertar_exato(mes_2.estado_final.CAPACIDADE_ATAQUE_M, capacidade_mutada)


def _divida_com_pagamento_normal(divida_id: str, *, saldo: Decimal) -> Divida:
    """Variante local de `_divida` (test_propriedades.py) com
    `PAGAMENTO_MENSAL_EFETIVO` igual ao saldo — quita só com o pagamento
    normal (`EC-02`), sem precisar de ataque, para liberar fluxo > 0 no
    próprio mês."""
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=saldo,
        PAGAMENTO_MENSAL_EFETIVO=saldo,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
