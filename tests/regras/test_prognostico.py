"""Testa o prognóstico "sem ação" — `RF-77` · `AC-132`..`AC-134` · `EC-57` · T-169.

REGRAS: RF-77
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import _serializar_canonico
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import _desserializar_snapshot
from tests.fixtures.carregar import carregar_gab_c


@pytest.fixture(scope="module")
def _snapshot():  # type: ignore[no-untyped-def]
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return calcular_plano(carregar_gab_c(), parametros)


@pytest.mark.regra
def test_AC132_prognostico_sem_acao_coerente(_snapshot) -> None:  # type: ignore[no-untyped-def]
    p = _snapshot.prognostico
    assert p is not None
    s = p.sem_acao
    assert s.HORIZONTE_MESES >= 1
    assert s.SALDO_INICIAL_TOTAL > dinheiro(0)
    assert s.SALDO_NO_HORIZONTE >= dinheiro(0)
    assert 0 <= s.DIVIDAS_QUE_CRESCEM
    assert s.DEFICIT_ACUMULADO >= dinheiro(0)
    if s.DEFICIT_MENSAL == dinheiro(0):
        assert s.DEFICIT_ACUMULADO == dinheiro(0)


@pytest.mark.regra
def test_AC133_horizonte_e_o_prazo_do_plano(_snapshot) -> None:  # type: ignore[no-untyped-def]
    recomendado = _snapshot.cenarios[_snapshot.METODO_RECOMENDADO_PIQ]
    assert _snapshot.prognostico is not None
    assert _snapshot.prognostico.sem_acao.HORIZONTE_MESES == max(1, recomendado.PRAZO_TOTAL)


@pytest.mark.regra
def test_AC134_ida_e_volta_na_persistencia(_snapshot) -> None:  # type: ignore[no-untyped-def]
    bruto = json.loads(json.dumps(_serializar_canonico(_snapshot)))
    assert _desserializar_snapshot(bruto).prognostico == _snapshot.prognostico


@pytest.mark.regra
def test_EC57_snapshot_antigo_sem_chave_fica_sem_prognostico(_snapshot) -> None:  # type: ignore[no-untyped-def]
    bruto = json.loads(json.dumps(_serializar_canonico(_snapshot)))
    bruto.pop("prognostico")
    assert _desserializar_snapshot(bruto).prognostico is None


@pytest.mark.regra
def test_prognostico_nao_altera_o_plano(_snapshot) -> None:  # type: ignore[no-untyped-def]
    sem = dataclasses.replace(_snapshot, prognostico=None)
    assert sem.ORDEM_QUITACAO == _snapshot.ORDEM_QUITACAO


@pytest.mark.regra
def test_RF78_verde_so_com_contribuicao_extra_e_nunca_pior_que_o_plano(_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert _snapshot.prognostico is not None and _snapshot.prognostico.com_extra is None
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    novo = calcular_plano(estado, parametros)
    verde = novo.prognostico.com_extra  # type: ignore[union-attr]
    assert verde is not None
    assert verde.CONTRIBUICAO_EXTRA_MENSAL == dinheiro(500)
    azul = novo.cenarios[novo.METODO_RECOMENDADO_PIQ]
    assert verde.PRAZO_TOTAL <= azul.PRAZO_TOTAL
    assert verde.CUSTO_FUTURO_TOTAL <= azul.CUSTO_FUTURO_TOTAL
    ataque = novo.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    assert verde.ATAQUE_MENSAL_TOTAL == ataque + dinheiro(500)
    vermelho = novo.prognostico.sem_acao  # type: ignore[union-attr]
    assert vermelho.MESES_PRIMEIRA_VITORIA is None or vermelho.MESES_PRIMEIRA_VITORIA >= 1
    assert verde.MESES_ANTECIPADOS == azul.PRAZO_TOTAL - verde.PRAZO_TOTAL >= 0
    assert verde.ECONOMIA_CUSTO == azul.CUSTO_FUTURO_TOTAL - verde.CUSTO_FUTURO_TOTAL >= 0
    assert verde.MESES_ANTECIPADOS > 0 or verde.ECONOMIA_CUSTO > 0
    assert novo.ORDEM_QUITACAO == _snapshot.ORDEM_QUITACAO or novo.ORDEM_QUITACAO
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    assert _desserializar_snapshot(bruto).prognostico == novo.prognostico
    assert _desserializar_snapshot(bruto).estado_inputs == estado


@pytest.mark.regra
def test_RF78_extra_zero_nao_gera_verde() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(0))
    p = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1")).prognostico
    assert p is not None and p.com_extra is None


@pytest.mark.regra
def test_AC136_snapshot_anterior_sem_os_campos_de_diferenca_volta_com_zero() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    for chave in ("MESES_ANTECIPADOS", "ECONOMIA_CUSTO"):
        bruto["prognostico"]["com_extra"].pop(chave)
    antigo = _desserializar_snapshot(bruto).prognostico.com_extra  # type: ignore[union-attr]
    assert antigo is not None
    assert antigo.MESES_ANTECIPADOS == 0 and antigo.ECONOMIA_CUSTO == dinheiro(0)


@pytest.mark.regra
def test_T174_snapshot_anterior_sem_os_campos_novos_volta_com_none() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    bruto["prognostico"]["sem_acao"].pop("MESES_PRIMEIRA_VITORIA")
    bruto["prognostico"]["com_extra"].pop("ATAQUE_MENSAL_TOTAL")
    antigo = _desserializar_snapshot(bruto).prognostico
    assert antigo is not None and antigo.com_extra is not None
    assert antigo.sem_acao.MESES_PRIMEIRA_VITORIA is None
    assert antigo.com_extra.ATAQUE_MENSAL_TOTAL is None


@pytest.mark.regra
def test_AC138_quitacoes_por_caminho() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    p = novo.prognostico
    assert p is not None and p.com_extra is not None
    verde = p.com_extra
    # Verde: toda dívida do plano quita, cada uma uma vez, até o prazo.
    assert sorted(d for d, _ in verde.QUITACOES) == sorted(x.DIVIDA_ID for x in novo.ORDEM_QUITACAO)
    assert all(1 <= mes <= verde.PRAZO_TOTAL for _, mes in verde.QUITACOES)
    if verde.MESES_PRIMEIRA_VITORIA is not None:
        assert min(mes for _, mes in verde.QUITACOES) == verde.MESES_PRIMEIRA_VITORIA
    # Vermelho: só o que quita no horizonte.
    assert len(p.sem_acao.QUITACOES) == p.sem_acao.DIVIDAS_QUITADAS_SOZINHAS
    assert all(mes <= p.sem_acao.HORIZONTE_MESES for _, mes in p.sem_acao.QUITACOES)
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    assert _desserializar_snapshot(bruto).prognostico == p
    bruto["prognostico"]["sem_acao"].pop("QUITACOES")
    bruto["prognostico"]["com_extra"].pop("QUITACOES")
    antigo = _desserializar_snapshot(bruto).prognostico
    assert antigo is not None and antigo.sem_acao.QUITACOES == ()


@pytest.mark.regra
def test_AC139_mes_a_mes_dos_planos_com_saldo_total_do_motor() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    p = novo.prognostico
    assert p is not None and p.com_extra is not None
    azul = novo.cenarios[novo.METODO_RECOMENDADO_PIQ]
    for meses, prazo, quitacoes in (
        (p.MESES_DO_PLANO, azul.PRAZO_TOTAL, None),
        (p.com_extra.MESES, p.com_extra.PRAZO_TOTAL, p.com_extra.QUITACOES),
    ):
        assert [m.MES for m in meses] == list(range(1, prazo + 1))
        assert meses[-1].SALDO_TOTAL == dinheiro(0)
        saldos = [m.SALDO_TOTAL for m in meses]
        assert saldos == sorted(saldos, reverse=True)  # sem déficit: só desce
        if quitacoes is not None:
            assert sorted((d, m.MES) for m in meses for d in m.QUITACOES) == sorted(quitacoes)
    assert p.com_extra.MESES[0].VALOR_EXTRA >= p.MESES_DO_PLANO[0].VALOR_EXTRA
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    assert _desserializar_snapshot(bruto).prognostico == p
    bruto["prognostico"].pop("MESES_DO_PLANO")
    bruto["prognostico"]["com_extra"].pop("MESES")
    antigo = _desserializar_snapshot(bruto).prognostico
    assert antigo is not None and antigo.MESES_DO_PLANO == ()
    assert antigo.com_extra is not None and antigo.com_extra.MESES == ()


@pytest.mark.regra
def test_T380_pagamento_mensal_total_de_cada_plano() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    p = novo.prognostico
    assert p is not None and p.com_extra is not None
    devido = novo.diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES
    ataque = novo.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    assert p.PAGAMENTO_MENSAL_PLANO == devido + ataque
    assert p.com_extra.PAGAMENTO_MENSAL_TOTAL == devido + ataque + dinheiro(500)
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    assert _desserializar_snapshot(bruto).prognostico == p
    bruto["prognostico"].pop("PAGAMENTO_MENSAL_PLANO")
    bruto["prognostico"]["com_extra"].pop("PAGAMENTO_MENSAL_TOTAL")
    antigo = _desserializar_snapshot(bruto).prognostico
    assert antigo is not None and antigo.PAGAMENTO_MENSAL_PLANO is None
    assert antigo.com_extra is not None and antigo.com_extra.PAGAMENTO_MENSAL_TOTAL is None


@pytest.mark.regra
def test_AC141_detalhe_por_divida_fecha_a_conta_de_cada_mes() -> None:
    estado = dataclasses.replace(carregar_gab_c(), CONTRIBUICAO_EXTRA_MENSAL=dinheiro(500))
    novo = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    p = novo.prognostico
    assert p is not None and p.com_extra is not None
    for meses in (p.MESES_DO_PLANO, p.com_extra.MESES):
        anterior = None
        for mes in meses:
            assert mes.DIVIDAS and mes.TOTAL_PAGAR is not None
            # Início + juros − pago = saldo ao fim do mês, no total e por dívida.
            assert mes.SALDO_INICIAL_TOTAL + mes.JUROS_TOTAL - mes.TOTAL_PAGAR == mes.SALDO_TOTAL  # type: ignore[operator]
            assert mes.HABITUAL_TOTAL + mes.EXTRA_TOTAL == mes.TOTAL_PAGAR  # type: ignore[operator]
            for d in mes.DIVIDAS:
                assert d.SALDO_ANTES + d.JUROS - d.TOTAL_PAGAR == d.SALDO_DEPOIS
                assert d.HABITUAL + d.EXTRA == d.TOTAL_PAGAR
                assert d.EXTRA >= dinheiro(0) and d.HABITUAL >= dinheiro(0)
            if anterior is not None:  # o saldo de um mês abre o seguinte
                assert mes.SALDO_INICIAL_TOTAL == anterior.SALDO_TOTAL
            anterior = mes
    # Sem déficit, o total pago por mês é constante (a parcela liberada é reaplicada)
    # até o penúltimo mês e é o "Até R$ … por mês" do capítulo 5.
    assert p.MESES_DO_PLANO[0].TOTAL_PAGAR == p.PAGAMENTO_MENSAL_PLANO
    assert p.com_extra.MESES[0].TOTAL_PAGAR == p.com_extra.PAGAMENTO_MENSAL_TOTAL
    bruto = json.loads(json.dumps(_serializar_canonico(novo)))
    assert _desserializar_snapshot(bruto).prognostico == p
    antigo = json.loads(json.dumps(bruto))
    for m in antigo["prognostico"]["MESES_DO_PLANO"]:
        for chave in (
            "DIVIDAS",
            "SALDO_INICIAL_TOTAL",
            "JUROS_TOTAL",
            "HABITUAL_TOTAL",
            "EXTRA_TOTAL",
            "TOTAL_PAGAR",
        ):
            m.pop(chave)
    lido = _desserializar_snapshot(antigo).prognostico
    assert lido is not None and lido.MESES_DO_PLANO[0].DIVIDAS == ()
    assert lido.MESES_DO_PLANO[0].TOTAL_PAGAR is None
