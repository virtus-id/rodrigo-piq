"""Seguro prestamista na montagem e rateio analítico — `RF-81`, `RF-82`,
`RF-85`, `AC-121`, `AC-122`, `AC-124`, `AC-130`, `AC-131` (2ª metade),
`AC-132`, `AC-155`, `EC-39` (`T-230`, `T-231`, `T-232`, `T-233`, `T-234`).

Decisão do produto `R9-1` (2026-09-30): o seguro cobrado mensalmente à
parte entra nas DESPESAS MENSAIS OPERACIONAIS entregues ao motor, uma vez
por dívida — nunca na parcela, nunca na `B3.C00`.
"""

from __future__ import annotations

import ast
import inspect
from functools import cache

from app.montagem import estado as modulo_estado
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.entrada import fotografia_do_mes, rateio_mensal
from app.montagem.estado import montar_divida
from collection.carga import carregar_registros
from collection.condicoes import avaliar
from collection.registro import RegistroPergunta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.tipos import DESCONHECIDO
from tests.app_aluno.test_montagem_estado_financeiro import (
    _montar,
    _respostas_minimas_completas,
)

_BASE = "CUSTO_SEGURO (+ base MENSAL/TOTAL)"
_D = "D001"


@cache
def _registros() -> dict[str, RegistroPergunta]:
    return {r.ID: r for r in carregar_registros().registros}


def _r(texto: str) -> object:
    return converter_para_dinheiro(texto)


def _no_item(variavel: str, valor: object) -> Resposta:
    return Resposta(
        CASO_ID="CASO-SEGURO",
        ID_PERGUNTA=variavel,
        item_id=_D,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=_respostas_minimas_completas().respostas[0].respondida_em,
    )


def _caso(**seguro: object) -> RespostasCaso:
    """Caso mínimo completo + uma ficha de dívida com parcela de R$ 500 e as
    respostas de seguro dadas (variável → valor)."""
    ficha = {
        "TIPO_DIVIDA": "PESSOAL",
        "STATUS_DIVIDA": "ATIVA",
        "SALDO_DEVEDOR_ATUAL": _r("5.000,00"),
        "PAGAMENTO_MENSAL_EFETIVO": _r("500,00"),
        "PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)": _r("500,00"),
        "PESO_EMOCIONAL": 5,
        "SEGURO_PRESTAMISTA": "SIM",
        **seguro,
    }
    base = _respostas_minimas_completas()
    return RespostasCaso(
        respostas=base.respostas + tuple(_no_item(v, valor) for v, valor in ficha.items())
    )


def _estado(respostas: RespostasCaso):  # type: ignore[no-untyped-def]
    return _montar(respostas, dividas=(montar_divida(respostas, _D),))


_SEM_SEGURO = _caso(SEGURO_PRESTAMISTA="NAO")


# ---------------------------------------------------------------------------
# T-230 — registros novos, visibilidade sobre o registro real.
# ---------------------------------------------------------------------------


def _aberta(ID: str, respostas: RespostasCaso) -> bool:
    condicao = _registros()[ID].condicao_exibicao
    return condicao is None or avaliar(condicao, respostas, _D)


def test_t230_visibilidade_das_perguntas_do_seguro() -> None:
    assert not _aberta("B5.D05S", _SEM_SEGURO)
    assert _aberta("B5.D05S", _caso())
    for ID in ("B5.D05V", "B5.D05P"):
        assert not _aberta(ID, _caso())
        assert not _aberta(ID, _caso(**{_BASE: NAO_SEI}))
        assert _aberta(ID, _caso(**{_BASE: "MENSAL"}))
        assert _aberta(ID, _caso(**{_BASE: "TOTAL"}))
    assert not _aberta("B5.D05R", _caso(SITUACAO_SEGURO="COBRADO_MENSAL_A_PARTE"))
    assert _aberta("B5.D05R", _caso(SITUACAO_SEGURO="CANCELADO_COM_RESTITUICAO"))


def test_t230_opcoes_de_escolha_novas_tem_valor_interno() -> None:
    assert all(o.valor_interno for o in _registros()["B5.D05S"].opcoes)


# ---------------------------------------------------------------------------
# T-231 — CUSTO_SEGURO montado pela situação; fim do AssertionError.
# ---------------------------------------------------------------------------


def test_t231_base_mensal_respondida_nao_quebra_a_montagem() -> None:
    """Reproduz o defeito de `R9.5`: `B5.D05A = MENSAL` fazia o `assert` de
    `_dinheiro_estrutural_ou_desconhecido` estourar."""
    divida = montar_divida(_caso(**{_BASE: "MENSAL"}), _D)

    assert divida.CUSTO_SEGURO is DESCONHECIDO  # sem situação nem valor


def test_t231_custo_seguro_so_com_cobranca_mensal_a_parte() -> None:
    cobrado = _caso(
        SITUACAO_SEGURO="COBRADO_MENSAL_A_PARTE",
        **{_BASE: "MENSAL"},
        CUSTO_SEGURO_VALOR=_r("40,00"),
    )
    assert montar_divida(cobrado, _D).CUSTO_SEGURO == _r("40,00")

    for situacao in ("PREMIO_UNICO_FINANCIADO", "CANCELADO_COM_RESTITUICAO", NAO_SEI):
        outra = _caso(
            SITUACAO_SEGURO=situacao, **{_BASE: "MENSAL"}, CUSTO_SEGURO_VALOR=_r("40,00")
        )
        assert montar_divida(outra, _D).CUSTO_SEGURO is DESCONHECIDO, situacao
    total = _caso(
        SITUACAO_SEGURO="COBRADO_MENSAL_A_PARTE",
        **{_BASE: "TOTAL"},
        CUSTO_SEGURO_VALOR=_r("1.200,00"),
    )
    assert montar_divida(total, _D).CUSTO_SEGURO is DESCONHECIDO


# ---------------------------------------------------------------------------
# T-232/T-234 — AC-121, AC-122, AC-132, AC-155/EC-39.
# ---------------------------------------------------------------------------


def test_ac122_seguro_mensal_a_parte_soma_uma_vez_as_despesas_operacionais() -> None:
    respostas = _caso(
        SITUACAO_SEGURO="COBRADO_MENSAL_A_PARTE",
        SEGURO_INCLUIDO_PARCELA="NAO",
        **{_BASE: "MENSAL"},
        CUSTO_SEGURO_VALOR=_r("40,00"),
    )

    com, sem = _estado(respostas), _estado(_SEM_SEGURO)

    assert com.DESPESAS_OPERACIONAIS_ATUAIS == sem.DESPESAS_OPERACIONAIS_ATUAIS + _r("40")
    assert com.dividas[0].PARCELA_CONTRATUAL == sem.dividas[0].PARCELA_CONTRATUAL
    assert fotografia_do_mes(respostas) == fotografia_do_mes(_SEM_SEGURO)


def test_ac132_seguro_ja_incluido_na_parcela_nao_soma() -> None:
    respostas = _caso(
        SITUACAO_SEGURO="COBRADO_MENSAL_A_PARTE",
        SEGURO_INCLUIDO_PARCELA="SIM",
        **{_BASE: "MENSAL"},
        CUSTO_SEGURO_VALOR=_r("40,00"),
    )

    assert _estado(respostas).DESPESAS_OPERACIONAIS_ATUAIS == (
        _estado(_SEM_SEGURO).DESPESAS_OPERACIONAIS_ATUAIS
    )


def test_ac121_premio_unico_nada_soma_e_o_total_fica_registrado() -> None:
    respostas = _caso(
        SITUACAO_SEGURO="PREMIO_UNICO_FINANCIADO",
        **{_BASE: "TOTAL"},
        CUSTO_SEGURO_VALOR=_r("1.200,00"),
    )

    com, sem = _estado(respostas), _estado(_SEM_SEGURO)

    assert com.DESPESAS_OPERACIONAIS_ATUAIS == sem.DESPESAS_OPERACIONAIS_ATUAIS
    assert com.dividas[0].SALDO_DEVEDOR_ATUAL == sem.dividas[0].SALDO_DEVEDOR_ATUAL
    assert com.dividas[0].PARCELA_CONTRATUAL == sem.dividas[0].PARCELA_CONTRATUAL
    assert respostas.valor_no_item(_D, "CUSTO_SEGURO_VALOR") == _r("1200")


def test_ac155_ec39_situacao_nao_sei_nada_soma() -> None:
    respostas = _caso(
        SITUACAO_SEGURO=NAO_SEI, **{_BASE: "MENSAL"}, CUSTO_SEGURO_VALOR=_r("40,00")
    )

    com = _estado(respostas)

    assert com.DESPESAS_OPERACIONAIS_ATUAIS == _estado(_SEM_SEGURO).DESPESAS_OPERACIONAIS_ATUAIS
    assert com.dividas[0].CUSTO_SEGURO is DESCONHECIDO


# ---------------------------------------------------------------------------
# T-233/T-234 — rateio analítico (AC-124, AC-130, AC-131 2ª metade).
# ---------------------------------------------------------------------------


def test_ac124_rateio_com_periodo_e_sem_periodo() -> None:
    assert rateio_mensal(_r("1.200,00"), 24) == _r("50")  # type: ignore[arg-type]
    assert rateio_mensal(_r("1.200,00"), None) is None  # type: ignore[arg-type]
    assert rateio_mensal(_r("1.200,00"), DESCONHECIDO) is None  # type: ignore[arg-type]


def test_ac130_ac131_total_sem_prazo_nenhum_mensal_com_prazo_so_rateio() -> None:
    assert rateio_mensal(_r("1.200,00"), None) is None  # type: ignore[arg-type]
    assert rateio_mensal(_r("1.200,00"), 12) == _r("100")  # type: ignore[arg-type]
    assert rateio_mensal(DESCONHECIDO, 12) is None


def test_t233_rateio_nunca_chamado_pela_montagem_do_estado() -> None:
    """Estático: nenhuma função de `estado.py` chama `rateio_mensal`."""
    arvore = ast.parse(inspect.getsource(modulo_estado))
    chamados = {
        no.func.id
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }
    assert "rateio_mensal" not in chamados
    assert "rateio_mensal" not in inspect.getsource(modulo_estado)


# ---------------------------------------------------------------------------
# T-235 — B8.12V/B8.12P, condicionadas à base de B8.12A (registro real).
# ---------------------------------------------------------------------------


def test_t235_valor_e_meses_do_novo_seguro_abrem_pela_base() -> None:
    def respostas(base: object) -> RespostasCaso:
        return RespostasCaso(respostas=(_no_item("NOVO_SEGURO", base),))

    for ID in ("B8.12V", "B8.12P"):
        assert _registros()[ID].escopo_repeticao.value == "DIVIDA_ID"
        assert _aberta(ID, respostas("MENSAL"))
        assert _aberta(ID, respostas("TOTAL"))
        assert not _aberta(ID, respostas("NAO_SEI"))
        assert not _aberta(ID, RespostasCaso(respostas=()))
    assert _registros()["B8.12P"].admite_nao_sei


def test_t236_custo_da_troca_proposta_nunca_conta_antes_da_contratacao() -> None:
    """Decisão do produto (2026-09-30): o custo "por mês" de `B8.12A` só
    conta a partir da contratação da troca (recálculo pós-plano), nunca
    antes. Proposta recebida (Bloco 8) não altera as despesas entregues ao
    motor."""
    proposta = _caso(
        NOVO_SEGURO="MENSAL",
        NOVO_SEGURO_VALOR=_r("30,00"),
        NOVO_SEGURO_MESES=10,
        NOVO_SEGURO_INCLUIDO_PARCELA="NAO",
    )

    assert _estado(proposta).DESPESAS_OPERACIONAIS_ATUAIS == (
        _estado(_caso()).DESPESAS_OPERACIONAIS_ATUAIS
    )
