"""Decisão da conferência sem siglas e dívidas com nome único — `RF-111`
(a)/(b), `AC-174` (`T-328`).

Relato do produto (2026-10-02): "D001 · B5.I02: Comprovado…", "Ordem final
de ataque D011 → D008 → …", "Mês de quitação D011: mês 2 · …" e nove
consignados CAIXA com o mesmo nome. O caso é o de `T-326`
(`test_t326_linguagem_humana.py`), servido por `GET /revisao/caso/{id}/
decisao`.

REGRAS: `RF-111`, `AC-174`
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.casos.maquina import ESTADO_CASO
from app.http.rotas_revisao import (
    obter_repositorio_itens_da_revisao,
    obter_repositorio_respostas_da_revisao,
)
from collection.registro import EscopoRepeticao
from engine.tipos import DESCONHECIDO
from persistencia.app_aluno.itens import ItemRepetido
from report.plano import VocabularioDoCaso, carregar_textos_canonicos, nomear_dividas
from tests.app_aluno.test_t326_linguagem_humana import (
    _CAIXA,
    _CASO_ID,
    _cliente,
    _codigos_no_texto_principal,
    _Respostas,
    _snapshot,
)

_CHEQUE = f"Cheque especial ({_CAIXA})"
_CONSIGNADO = "Empréstimo consignado (BANCO DO BRASIL)"


class _Itens:
    def listar_do_caso(self, *_args: object, **_kwargs: object) -> tuple[ItemRepetido, ...]:
        agora = datetime(2026, 1, 1, tzinfo=UTC)
        return tuple(
            ItemRepetido(
                item_id=item_id,
                CASO_ID=_CASO_ID,
                escopo=EscopoRepeticao.DIVIDA_ID,
                removido_em=None,
                criado_em=agora,
            )
            for item_id in ("D011", "D001")
        )


def _decisao(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    cliente, _ = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)
    respostas, _ = _snapshot()
    aplicacao: Any = cliente.app
    aplicacao.dependency_overrides[obter_repositorio_respostas_da_revisao] = lambda: _Respostas(
        respostas.respostas
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_da_revisao] = _Itens
    resposta = cliente.get(f"/revisao/caso/{_CASO_ID}/decisao")
    assert resposta.status_code == 200
    corpo: dict[str, Any] = resposta.json()
    return corpo


def test_ac174_decisao_sem_codigo_no_texto_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    corpo = _decisao(monkeypatch)

    assert corpo["fontes"], "premissa: o caso tem fontes de comprovação"
    assert _codigos_no_texto_principal(corpo) == []


def test_t328_fontes_pela_divida_e_pelo_dado(monkeypatch: pytest.MonkeyPatch) -> None:
    fontes = _decisao(monkeypatch)["fontes"]

    fonte = next(f for f in fontes if f["item_id"] == "D011" and f["origem"] == "B5.I02")
    assert fonte["nome"] == _CHEQUE
    assert fonte["dado"] == "Fonte das informações"


def test_t328_ordem_e_meses_de_quitacao_por_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    _, snapshot = _snapshot()
    itens = _decisao(monkeypatch)["homologacao"]["itens"]
    nomes = {"D011": _CHEQUE, "D001": _CONSIGNADO}

    assert itens["ordem_final_de_ataque"]["valor"] == [
        f"{i}º {nomes[p.DIVIDA_ID]}" for i, p in enumerate(snapshot.ORDEM_QUITACAO, start=1)
    ]
    meses = itens["mes_de_quitacao_por_divida"]["valor"]
    assert set(meses) <= {_CHEQUE, _CONSIGNADO}


# ---------------------------------------------------------------------------
# Nomes repetidos — `nomear_dividas`, que plano, PDF e conferência usam.
# ---------------------------------------------------------------------------


def _nomes(*parcelas: Decimal | None) -> dict[str, str]:
    _, snapshot = _snapshot()
    base = next(d for d in snapshot.estado_inputs.dividas if d.DIVIDA_ID == "D001")
    dividas = [
        replace(
            base,
            DIVIDA_ID=f"D10{i}",
            PARCELA_CONTRATUAL=parcela if parcela is not None else DESCONHECIDO,
        )
        for i, parcela in enumerate(parcelas, start=1)
    ]
    vocabulario = VocabularioDoCaso(credores={d.DIVIDA_ID: _CAIXA for d in dividas})
    return nomear_dividas(dividas, carregar_textos_canonicos(), vocabulario)


def test_t328_nome_unico_fica_como_esta() -> None:
    assert _nomes(Decimal("292.55"))["D101"].endswith(f" ({_CAIXA})")


def test_t328_repetidos_ganham_a_parcela() -> None:
    nome = _nomes(None)["D101"]
    assert _nomes(Decimal("292.55"), Decimal("1000.00")) == {
        "D101": f"{nome} · parcela R$ 292,55",
        "D102": f"{nome} · parcela R$ 1.000,00",
    }


def test_t328_sem_parcela_ou_parcela_igual_ganham_ordinal() -> None:
    nome = _nomes(None)["D101"]
    assert _nomes(None, None, Decimal("50.00"), Decimal("50.00"), Decimal("70.00")) == {
        "D101": f"{nome} · 1",
        "D102": f"{nome} · 2",
        "D103": f"{nome} · parcela R$ 50,00 · 1",
        "D104": f"{nome} · parcela R$ 50,00 · 2",
        "D105": f"{nome} · parcela R$ 70,00",
    }
