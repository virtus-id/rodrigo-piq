"""Visibilidade do Bloco 7 por tipo de proposta — `RF-94`, `RF-95`,
`AC-143`–`AC-146`, `EC-37` (`T-242`, `T-244`).

Sobre o registro REAL (`collection/registros/bloco-07.yaml`): cada pergunta
aberta/fechada pela `condicao_exibicao` avaliada no item da dívida — a
mesma avaliação da coleta e do cálculo (`_respostas_do_calculo`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

import pytest

from app.casos.progresso import pendencias_obrigatorias
from app.http.rotas_calculo import _respostas_do_calculo
from collection.carga import carregar_registros
from collection.condicoes import avaliar
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import Resposta, RespostasCaso

_D = "D001"
_PARCELAMENTO = {"B7.07", "B7.08", "B7.09"}


@cache
def _bloco_7() -> tuple[RegistroPergunta, ...]:
    return tuple(r for r in carregar_registros().registros if r.bloco == 7)


def _resposta(variavel: str, valor: object) -> Resposta:
    return Resposta(
        CASO_ID="CASO-B7",
        ID_PERGUNTA=variavel,
        item_id=_D,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def _abertas(**respostas: object) -> set[str]:
    caso = RespostasCaso(respostas=tuple(_resposta(v, x) for v, x in respostas.items()))
    return {
        r.ID
        for r in _bloco_7()
        if r.condicao_exibicao is None or avaliar(r.condicao_exibicao, caso, _D)
    }


def test_ac143_sem_proposta_nada_da_proposta_aparece() -> None:
    assert _abertas(EXISTE_PROPOSTA_RENEGOCIACAO="NAO") == {"B7.04"}


def test_ac144_a_vista_valor_desconto_validade_e_fonte() -> None:
    abertas = _abertas(
        EXISTE_PROPOSTA_RENEGOCIACAO="VIGENTE",
        TIPO_PROPOSTA="A_VISTA",
        PROPOSTA_DESCONTO_EXISTE="SIM",
        PROPOSTA_DESCONTO="VALOR_E_PERCENTUAL",
    )

    assert abertas == {
        "B7.04",
        "B7.04A",
        "B7.07V",
        "B7.13",
        "B7.13A",
        "B7.13B",
        "B7.13C",
        "B7.13D",
        "B7.13E",
        "B7.15",
        "B7.16",
    }
    assert abertas.isdisjoint(_PARCELAMENTO)


@pytest.mark.parametrize("tipo", ["PARCELADA", "AMBAS"])
def test_ac145_parcelada_e_ambas(tipo: str) -> None:
    abertas = _abertas(EXISTE_PROPOSTA_RENEGOCIACAO="VALIDADE_DESCONHECIDA", TIPO_PROPOSTA=tipo)

    parcelamento = _PARCELAMENTO | {"B7.05", "B7.06", "B7.10", "B7.11", "B7.12", "B7.14"}
    assert parcelamento | {"B7.15"} <= abertas
    assert ("B7.07V" in abertas) is (tipo == "AMBAS")


def test_ac146_ec37_troca_de_parcelada_para_a_vista() -> None:
    """As respostas do parcelamento continuam gravadas, mas deixam de ser
    exibidas, de pendurar pendência e de chegar ao cálculo."""
    registros = carregar_registros().registros
    gravadas = (
        _resposta("EXISTE_PROPOSTA_RENEGOCIACAO", "VIGENTE"),
        _resposta("PROPOSTA_PARCELA", "500"),
        _resposta("PROPOSTA_QTD_PARCELAS", 12),
        _resposta("PROPOSTA_PRAZO", "NAO"),
    )
    antes = RespostasCaso(respostas=(*gravadas, _resposta("TIPO_PROPOSTA", "PARCELADA")))
    depois = RespostasCaso(respostas=(*gravadas, _resposta("TIPO_PROPOSTA", "A_VISTA")))
    variaveis = {"PROPOSTA_PARCELA", "PROPOSTA_QTD_PARCELAS", "PROPOSTA_PRAZO"}

    ao_calculo_antes = {r.ID_PERGUNTA for r in _respostas_do_calculo(registros, antes).respostas}
    ao_calculo = {r.ID_PERGUNTA for r in _respostas_do_calculo(registros, depois).respostas}

    assert variaveis <= ao_calculo_antes
    assert ao_calculo.isdisjoint(variaveis)
    pendentes = {
        p.ID
        for p in pendencias_obrigatorias(registros, depois, {EscopoRepeticao.DIVIDA_ID: (_D,)})
    }
    assert pendentes.isdisjoint(_PARCELAMENTO)


def test_t242_b7_16_toda_opcao_tem_valor_interno() -> None:
    b7_16 = next(r for r in _bloco_7() if r.ID == "B7.16")
    assert all(o.valor_interno for o in b7_16.opcoes)
