"""Desconto do credor — `RF-83`, `RF-84`, `AC-125`–`AC-129`, `EC-30`,
`EC-31` (`T-238`, `T-239`, `T-240`, `T-241`).

A conferência é agregação de entrada (`app/montagem/entrada.py::
conferir_desconto`); as travas são da gravação (`POST /resposta`: `faixa` e
validação cruzada, `400`, nada gravado); a divergência R$ × % é AVISO — a
resposta fica gravada.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem import entrada
from app.montagem.conversao import converter_para_dinheiro, converter_para_taxa
from app.montagem.entrada import conferir_desconto
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.tipos import DESCONHECIDO
from tests.app_aluno.test_rotas_coleta_fotografia import (
    _CASO,
    _CHAVE_TESTE,
    _CONTA,
    _Casos,
    _colecao_real,
    _resposta,
    _Respostas,
)

_D = "D001"


class _ItensComDivida:
    def listar_do_caso(self, caso_id: str, *, incluir_removidos: bool = True) -> tuple[object, ...]:
        from datetime import UTC, datetime

        from collection.registro import EscopoRepeticao
        from persistencia.app_aluno.itens import ItemRepetido

        return (
            ItemRepetido(
                item_id=_D,
                CASO_ID=_CASO,
                escopo=EscopoRepeticao.DIVIDA_ID,
                removido_em=None,
                criado_em=datetime(2026, 9, 30, tzinfo=UTC),
            ),
        )


def _r(texto: str) -> Decimal:
    return converter_para_dinheiro(texto)


def _pct(texto: str) -> Decimal:
    return converter_para_taxa(texto)


def _caso(tipo: object, **valores: object) -> RespostasCaso:
    base = {
        "PROPOSTA_DESCONTO_EXISTE": "SIM",
        "PROPOSTA_DESCONTO": tipo,
        "SALDO_DEVEDOR_ATUAL": _r("99.999,00"),  # nunca a base (AC-126)
        **valores,
    }
    return RespostasCaso(respostas=tuple(_resposta(v, x, _D) for v, x in base.items()))


# ---------------------------------------------------------------------------
# conferir_desconto — AC-125..AC-127, EC-30, EC-31.
# ---------------------------------------------------------------------------


def test_ac125_desconto_em_reais_referencia_8000() -> None:
    conf = conferir_desconto(
        _caso(
            "VALOR",
            VALOR_QUITACAO_ANTES_DESCONTO=_r("10.000"),
            PROPOSTA_DESCONTO_VALOR=_r("2.000"),
        ),
        _D,
    )
    assert (conf.VALOR_REFERENCIA, conf.VALOR_CALCULADO) == (_r("8000"), _r("8000"))


def test_ac126_percentual_sobre_o_bruto_nunca_sobre_o_saldo() -> None:
    conf = conferir_desconto(
        _caso(
            "PERCENTUAL",
            VALOR_QUITACAO_ANTES_DESCONTO=_r("10.000"),
            PROPOSTA_DESCONTO_PERCENTUAL=_pct("15"),
        ),
        _D,
    )
    assert conf.VALOR_REFERENCIA == _r("8500")


def test_ac127_valor_final_do_credor_prevalece() -> None:
    conf = conferir_desconto(
        _caso(
            "PERCENTUAL",
            VALOR_QUITACAO_ANTES_DESCONTO=_r("10.000"),
            PROPOSTA_DESCONTO_PERCENTUAL=_pct("20"),
            PROPOSTA_VALOR_FINAL_QUITACAO=_r("7.900"),
        ),
        _D,
    )
    assert (conf.VALOR_REFERENCIA, conf.VALOR_CALCULADO) == (_r("7900"), _r("8000"))


@pytest.mark.parametrize(
    ("bruto", "reais", "pct", "divergente"),
    [
        ("10.000", "2.000", "20", False),
        ("10.000,20", "1.500,03", "15", False),
        ("10.000,20", "1.500,05", "15", True),
        ("10.000", "2.000", "15", True),
    ],
)
def test_ac129_conferencia_ao_centavo_nunca_soma(
    bruto: str, reais: str, pct: str, divergente: bool
) -> None:
    conf = conferir_desconto(
        _caso(
            "VALOR_E_PERCENTUAL",
            VALOR_QUITACAO_ANTES_DESCONTO=_r(bruto),
            PROPOSTA_DESCONTO_VALOR=_r(reais),
            PROPOSTA_DESCONTO_PERCENTUAL=_pct(pct),
        ),
        _D,
    )
    assert conf.divergencia_rs_pct is divergente
    # Aplicado uma vez: 10.000 − 2.000 = 8.000, nunca 6.000.
    assert conf.VALOR_CALCULADO == _r(bruto) - _r(reais)


def test_ec30_sem_detalhe_referencia_desconhecida_e_bruto_registrado() -> None:
    respostas = _caso("SEM_DETALHE", VALOR_QUITACAO_ANTES_DESCONTO=_r("10.000"))
    conf = conferir_desconto(respostas, _D)

    assert conf.VALOR_REFERENCIA is DESCONHECIDO
    assert respostas.valor_no_item(_D, "VALOR_QUITACAO_ANTES_DESCONTO") == _r("10000")


def test_ec31_bruto_nao_sei_com_percentual_nada_calculado() -> None:
    conf = conferir_desconto(
        _caso(
            "PERCENTUAL",
            VALOR_QUITACAO_ANTES_DESCONTO=NAO_SEI,
            PROPOSTA_DESCONTO_PERCENTUAL=_pct("15"),
        ),
        _D,
    )
    assert conf.VALOR_REFERENCIA is DESCONHECIDO and conf.VALOR_CALCULADO is DESCONHECIDO


def test_t239_conferir_desconto_nao_le_saldo_contrato_nem_parcelas() -> None:
    """Estático: a função não nomeia saldo, valor contratado nem parcelas."""
    fonte = inspect.getsource(entrada.conferir_desconto)
    literais = {
        no.value
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
    }
    proibidos = ("SALDO", "CONTRATADO", "PARCELA")
    assert not [s for s in literais if any(p in s for p in proibidos)]


# ---------------------------------------------------------------------------
# Pela rota — AC-128 (travas) e AC-129 (aviso, dois valores gravados).
# ---------------------------------------------------------------------------


def _cliente(
    monkeypatch: pytest.MonkeyPatch, *respostas: Resposta
) -> tuple[TestClient, _Respostas]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    repositorio = _Respostas(
        (
            _resposta("EXISTE_PROPOSTA_RENEGOCIACAO", "VIGENTE", _D),
            _resposta("TIPO_PROPOSTA", "A_VISTA", _D),
            _resposta("PROPOSTA_DESCONTO_EXISTE", "SIM", _D),
            *respostas,
        )
    )
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = _Casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = _colecao_real
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: repositorio
    aplicacao.dependency_overrides[obter_repositorio_itens] = _ItensComDivida

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA}")
    return cliente, repositorio


def _gravar(cliente: TestClient, ID: str, valor: str) -> object:
    return cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": ID, "item_id": _D, "valor": valor}
    )


def _gravado(repositorio: _Respostas, variavel: str) -> object:
    return RespostasCaso(respostas=tuple(repositorio.respostas)).valor_no_item(_D, variavel)


@pytest.mark.parametrize("percentual", ["120", "-5"])
def test_ac128_percentual_fora_de_0_a_100_recusado_sem_gravar(
    monkeypatch: pytest.MonkeyPatch, percentual: str
) -> None:
    cliente, repositorio = _cliente(monkeypatch, _resposta("PROPOSTA_DESCONTO", "PERCENTUAL", _D))

    resposta = _gravar(cliente, "B7.13D", percentual)

    assert resposta.status_code == 400  # type: ignore[attr-defined]
    texto = resposta.text  # type: ignore[attr-defined]
    assert "entre 0% e 100%" in texto
    assert "PROPOSTA_DESCONTO_PERCENTUAL" not in texto
    assert _gravado(repositorio, "PROPOSTA_DESCONTO_PERCENTUAL") is None


@pytest.mark.parametrize("percentual", ["0", "100"])
def test_t238_limites_da_faixa_sao_aceitos(
    monkeypatch: pytest.MonkeyPatch, percentual: str
) -> None:
    cliente, repositorio = _cliente(monkeypatch, _resposta("PROPOSTA_DESCONTO", "PERCENTUAL", _D))

    assert _gravar(cliente, "B7.13D", percentual).status_code == 200  # type: ignore[attr-defined]
    assert _gravado(repositorio, "PROPOSTA_DESCONTO_PERCENTUAL") == _pct(percentual)


def test_ac128_desconto_em_reais_acima_do_bruto_recusado(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, repositorio = _cliente(
        monkeypatch,
        _resposta("PROPOSTA_DESCONTO", "VALOR", _D),
        _resposta("VALOR_QUITACAO_ANTES_DESCONTO", _r("10.000"), _D),
    )

    resposta = _gravar(cliente, "B7.13C", "12.000,00")

    assert resposta.status_code == 400  # type: ignore[attr-defined]
    assert "VALOR_QUITACAO" not in resposta.text  # type: ignore[attr-defined]
    assert _gravado(repositorio, "PROPOSTA_DESCONTO_VALOR") is None


def test_t241_desconto_em_reais_com_bruto_nao_sei_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bruto "não sei" não quebra a validação cruzada (`NAO_SEI` não se
    compara com dinheiro) — nada a conferir, a resposta grava."""
    cliente, _ = _cliente(
        monkeypatch,
        _resposta("PROPOSTA_DESCONTO", "VALOR", _D),
        _resposta("VALOR_QUITACAO_ANTES_DESCONTO", NAO_SEI, _D),
    )

    assert _gravar(cliente, "B7.13C", "2.000,00").status_code == 200  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("reais", "pct", "avisos"),
    [("2.000,00", "20", 0), ("2.000,00", "15", 1)],
)
def test_ac129_divergencia_e_aviso_e_os_dois_valores_ficam_gravados(
    monkeypatch: pytest.MonkeyPatch, reais: str, pct: str, avisos: int
) -> None:
    cliente, repositorio = _cliente(
        monkeypatch,
        _resposta("PROPOSTA_DESCONTO", "VALOR_E_PERCENTUAL", _D),
        _resposta("VALOR_QUITACAO_ANTES_DESCONTO", _r("10.000"), _D),
        _resposta("PROPOSTA_DESCONTO_VALOR", _r(reais), _D),
    )

    resposta = _gravar(cliente, "B7.13D", pct)

    assert resposta.status_code == 200  # type: ignore[attr-defined]
    corpo = resposta.json()  # type: ignore[attr-defined]
    assert len(corpo["avisos"]) == avisos
    if avisos:
        (aviso,) = corpo["avisos"]
        assert (aviso["codigo"], aviso["ID_PERGUNTA"]) == ("DIVERGENCIA_DESCONTO", "B7.13D")
        assert aviso["mensagem"]
    assert _gravado(repositorio, "PROPOSTA_DESCONTO_VALOR") == _r(reais)
    assert _gravado(repositorio, "PROPOSTA_DESCONTO_PERCENTUAL") == _pct(pct)


def test_t240_sem_aviso_o_contrato_traz_lista_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _cliente(monkeypatch)

    resposta = _gravar(cliente, "B7.13A", "VALOR")

    assert resposta.json()["avisos"] == []  # type: ignore[attr-defined]


def test_t237_registros_do_desconto_carregam_e_nunca_dizem_saldo_devedor() -> None:
    registros = {r.ID: r for r in _colecao_real().registros}
    novos = ("B7.13A", "B7.13B", "B7.13C", "B7.13D", "B7.13E")

    assert all(ID in registros for ID in novos)
    assert [o.valor_interno for o in registros["B7.13A"].opcoes] == [
        "VALOR",
        "PERCENTUAL",
        "VALOR_E_PERCENTUAL",
        "SEM_DETALHE",
        "NAO_SEI",
    ]
    for ID in novos:
        assert "saldo devedor" not in registros[ID].enunciado.lower(), ID
