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
