"""Fotografia do mês (`B3.C00`) — `RF-79`, `RF-80`, `AC-117`, `AC-118`,
`AC-119`, `EC-28`, `EC-29` (`T-226`).

Pela função pura `app/montagem/entrada.py::fotografia_do_mes` e, para o
motor, pela montagem real (`montar_estado_financeiro`).
"""

from __future__ import annotations

from decimal import Decimal

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.entrada import fotografia_do_mes
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.tipos import DESCONHECIDO
from tests.app_aluno.test_montagem_estado_financeiro import (
    _montar,
    _resposta,
    _respostas_minimas_completas,
)


def _r(valor: str) -> Decimal:
    return converter_para_dinheiro(valor)


def _caso(*extras: Resposta, renda: object | None = None) -> RespostasCaso:
    """AC-117: renda 8.000; despesas 3.000 + 2.000; não mensal 6.000/ano
    (500/mês)."""
    base = _respostas_minimas_completas(
        **({"RENDA_PRINCIPAL": renda} if renda is not None else {})
    )
    return RespostasCaso(
        respostas=base.respostas
        + (
            _resposta("VALOR_DESPESA", _r("3.000,00"), item_id="I001"),
            _resposta("VALOR_DESPESA", _r("2.000,00"), item_id="I002"),
            _resposta("VALOR_DESPESA_NAO_MENSAL", _r("6.000,00"), item_id="NM001"),
            *extras,
        )
    )


def test_ac117_tres_valores_exatos() -> None:
    foto = fotografia_do_mes(_caso())

    assert (foto.RENDA_TOTAL, foto.DESPESAS_TOTAIS, foto.SOBRA_ANTES_DAS_DIVIDAS) == (
        _r("8000"),
        _r("5500"),
        _r("2500"),
    )
    assert (foto.parcial_renda, foto.parcial_despesas, foto.parcial_sobra) == (False, False, False)


def test_ac118_ec29_parcelas_de_divida_nunca_entram() -> None:
    com_dividas = _caso(
        _resposta("PARCELA_CONTRATUAL", _r("300"), item_id="D001"),
        _resposta("PARCELA_CONTRATUAL", _r("700"), item_id="D002"),
        _resposta("CUSTO_SEGURO_VALOR", _r("40"), item_id="D001"),
    )

    assert fotografia_do_mes(com_dividas) == fotografia_do_mes(_caso())


def test_ac119_decomposicoes_somam_exatamente_as_despesas_totais() -> None:
    foto = fotografia_do_mes(
        _caso(_resposta("VALOR_DESPESA_NAO_MENSAL", _r("1.000,00"), item_id="NM002"))
    )
    linhas = foto.despesas_por_item + foto.nao_mensais_por_item

    assert [linha.item_id for linha in linhas] == ["I001", "I002", "NM001", "NM002"]
    valores = [linha.valor_mensal for linha in linhas]
    assert all(isinstance(v, Decimal) for v in valores)
    assert sum((v for v in valores if isinstance(v, Decimal)), _r("0")) == foto.DESPESAS_TOTAIS


def test_ec28_despesa_nao_sei_total_parcial_com_os_informados() -> None:
    """Decisão `R9-2` e decisão da sobra (2026-09-30): o total leva os
    informados e a marca "parcial"; a sobra recebe o mesmo tratamento."""
    foto = fotografia_do_mes(_caso(_resposta("VALOR_DESPESA", NAO_SEI, item_id="I003")))

    assert foto.DESPESAS_TOTAIS == _r("5500")
    assert foto.parcial_despesas is True
    assert foto.SOBRA_ANTES_DAS_DIVIDAS == _r("2500")
    assert foto.parcial_sobra is True
    assert foto.despesas_por_item[-1].valor_mensal is DESCONHECIDO


def test_ec28_renda_adicional_nao_sei_marca_a_renda_parcial() -> None:
    foto = fotografia_do_mes(
        _caso(_resposta("RENDA_RECORRENTE_ADICIONAL", NAO_SEI, item_id="R001"))
    )

    assert (foto.RENDA_TOTAL, foto.parcial_renda, foto.parcial_sobra) == (_r("8000"), True, True)


def test_ec28_renda_principal_nao_sei_e_nao_informado() -> None:
    foto = fotografia_do_mes(_caso(renda=NAO_SEI))

    assert foto.RENDA_TOTAL is DESCONHECIDO
    assert foto.SOBRA_ANTES_DAS_DIVIDAS is DESCONHECIDO
    assert foto.DESPESAS_TOTAIS == _r("5500")


def test_motor_recebe_a_soma_dos_informados() -> None:
    """OQ-16 inalterado: a montagem entrega ao motor a soma dos informados."""
    respostas = _caso(_resposta("VALOR_DESPESA", NAO_SEI, item_id="I003"))

    estado = _montar(respostas)

    assert estado.DESPESAS_OPERACIONAIS_ATUAIS == _r("5000")
    assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == _r("500")


def test_resposta_repetida_do_mesmo_item_conta_uma_vez() -> None:
    """A última resposta de `(variável, item)` vence — mesma chave de
    `RespostasCaso`; a decomposição nunca soma o item duas vezes."""
    repetida = _caso(_resposta("VALOR_DESPESA", _r("3.000,00"), item_id="I001"))

    assert fotografia_do_mes(repetida).DESPESAS_TOTAIS == _r("5500")
    assert _montar(repetida).DESPESAS_OPERACIONAIS_ATUAIS == _r("5000")
