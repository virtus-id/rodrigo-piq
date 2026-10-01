"""Suíte de homologação — `RF-96`, `RF-97` (`app-aluno` T-269, `DE-08`).

`AC-147`: `GAB-A/B/C` produzem o registro dos cinco itens, e os itens com
valor no gabarito (§10 da canônica) são comparados a ele com as tolerâncias
de `sdd.config.md` §5. Item "não disponível" aparece como tal — nunca é
comparado a uma estimativa. `AC-148`: caso que não é gabarito — só
invariantes, nenhum valor esperado. `AC-149`: dado indispensável ausente →
o cálculo roda, `homologavel=False` e o dado é nomeado.

REGRAS: `RF-96`, `RF-97`, `AC-147`, `AC-148`, `AC-149`
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.revisao.comprovacao import PendenciaHomologacao, pendencias_de_homologacao
from app.revisao.homologacao import NAO_DISPONIVEL, RegistroHomologacao, registrar_homologacao
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import NAO_SEI
from engine.estado import EstadoFinanceiro
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, CasoCompleto, caso_completo
from tests.conftest import assertar_exato, assertar_monetario
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_b, carregar_gab_c
from tests.homologacao.registro import emitir

type Registrar = Callable[[str, object], None]

_ITENS = (
    "ordem_final_de_ataque",
    "mes_de_quitacao_por_divida",
    "valor_mensal_destinado",
    "custo_total_de_juros",
    "uso_da_reserva",
)


def _snapshot(estado: EstadoFinanceiro) -> SnapshotOrdem:
    return calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))


def _registro_do_caso(caso: CasoCompleto) -> tuple[SnapshotOrdem, RegistroHomologacao]:
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    snapshot = _snapshot(estado)
    pendencias = pendencias_de_homologacao(
        carregar_registros().registros,
        caso.respostas,
        {EscopoRepeticao.DIVIDA_ID: (caso.DIVIDA_ID,)},
    )
    return snapshot, registrar_homologacao(snapshot, pendencias)


def _assert_cinco_itens(registro: RegistroHomologacao) -> None:
    for nome in _ITENS:
        item = getattr(registro, nome)
        if item.disponivel:
            assert item.origem, f"{nome}: valor sem campo de origem"
        else:
            assert item.valor == NAO_DISPONIVEL and item.motivo, f"{nome}: sem motivo"


@pytest.mark.gabarito
@pytest.mark.parametrize("carregar", [carregar_gab_a, carregar_gab_b, carregar_gab_c])
def test_ac147_gabaritos_produzem_o_registro_dos_cinco_itens(
    carregar: Callable[[], EstadoFinanceiro], record_property: Registrar
) -> None:
    registro = registrar_homologacao(_snapshot(carregar()), ())

    emitir(record_property, registro)

    _assert_cinco_itens(registro)
    assert registro.homologavel is True
    # Uso da reserva: nunca comparado a estimativa (`R9-6`).
    assert registro.uso_da_reserva.valor == NAO_DISPONIVEL


@pytest.mark.gabarito
def test_ac147_gab_c_comparado_ao_gabarito(record_property: Registrar) -> None:
    """§10.1/§10.2: Híbrido, 6 meses, R$ 24.107,20, 1ª vitória no mês 1,
    D003 → D001 → D002, `CAPACIDADE_ATAQUE_CONSERVADORA = 3.000`. Juros =
    custo futuro total do gabarito − saldos de entrada (12.000 + 7.000 +
    3.000), a mesma identidade de `registro.py`."""
    registro = registrar_homologacao(_snapshot(carregar_gab_c()), ())
    emitir(record_property, registro)

    assertar_exato(registro.ordem_final_de_ataque.valor, ("D003", "D001", "D002"))
    meses = registro.mes_de_quitacao_por_divida.valor
    assert isinstance(meses, dict)
    assertar_exato(meses["D003"], 1)  # 1ª vitória
    assertar_exato(max(meses.values()), 6)  # prazo
    assertar_exato(registro.valor_mensal_destinado.valor, dinheiro("3000"))
    juros = registro.custo_total_de_juros.valor
    assert isinstance(juros, Decimal)
    assertar_monetario(juros, dinheiro("24107.20") - dinheiro("22000"))


@pytest.mark.gabarito
def test_ac147_gab_b_valor_mensal_e_a_capacidade_conservadora(record_property: Registrar) -> None:
    """§10.2: `CAPACIDADE_ATAQUE_CONSERVADORA = 200` — nunca os 600 do
    potencial."""
    registro = registrar_homologacao(_snapshot(carregar_gab_b()), ())
    emitir(record_property, registro)

    assertar_exato(registro.valor_mensal_destinado.valor, dinheiro("200"))


def test_ac148_caso_livre_so_invariantes(record_property: Registrar) -> None:
    """Nenhum valor esperado de ordem, prazo, juros ou reserva: o motor
    apura; o teste só confere coerência interna do registro."""
    snapshot, registro = _registro_do_caso(caso_completo())
    emitir(record_property, registro)

    _assert_cinco_itens(registro)
    ordem = registro.ordem_final_de_ataque.valor
    meses = registro.mes_de_quitacao_por_divida.valor
    assert isinstance(ordem, tuple) and isinstance(meses, dict)
    dividas = {d.DIVIDA_ID for d in snapshot.estado_inputs.dividas}
    assert set(ordem) <= dividas
    assert set(meses) <= dividas
    assert all(isinstance(m, int) and m >= 1 for m in meses.values())
    juros = registro.custo_total_de_juros
    if juros.disponivel:
        assert isinstance(juros.valor, Decimal) and juros.valor >= 0


def test_ac149_indispensavel_ausente_calcula_e_nao_homologa(record_property: Registrar) -> None:
    caso = caso_completo(valores_divida={"SALDO_DEVEDOR_ATUAL": NAO_SEI})

    snapshot, registro = _registro_do_caso(caso)
    emitir(record_property, registro)

    assert snapshot.SNAPSHOT_ID  # o cálculo rodou
    assert registro.homologavel is False
    assert PendenciaHomologacao(caso.DIVIDA_ID, "B5.B03", "AUSENTE") in registro.pendencias
    # Nenhum valor presumido no lugar do saldo.
    assert registro.custo_total_de_juros.valor == NAO_DISPONIVEL
