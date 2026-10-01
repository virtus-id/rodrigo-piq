"""Ficha de dívida no `POST /resposta` — `T-291` (`RF-87`, `DE-04`) e
`T-292` (`RF-09`, `AC-11`).

Aplicação real, registros REAIS, repositórios em memória por
`app.dependency_overrides` (sem banco) — mesmo arranjo de
`test_rotas_coleta_fotografia.py`.

- `T-291`: `B5.00 = 2` e `B5.00A` respondidas sem ficha → `abrir_fichas`
  aponta `DIVIDA_ID` (antes vinha vazio e a próxima já era `B5.FIM02`).
- `T-292`: "Sim, salvar dívida." em `B5.CHECK` com `B5.D02` aberta (por
  `B5.I01 = CONTRATO`) e em branco no item é recusado com `400` que lista o
  que falta; nada é gravado.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import cache

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta
from persistencia.app_aluno.itens import ItemRepetido

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA = "CONTA-FICHA-1"
_CASO = "CASO-FICHA-1"
_AGORA = datetime(2026, 9, 30, tzinfo=UTC)


class _Respostas:
    def __init__(self, respostas: tuple[Resposta, ...]) -> None:
        self.respostas = list(respostas)

    def gravar(self, resposta: Resposta) -> None:
        self.respostas = [
            r
            for r in self.respostas
            if not (r.ID_PERGUNTA == resposta.ID_PERGUNTA and r.item_id == resposta.item_id)
        ] + [resposta]

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(self.respostas)


class _Itens:
    def __init__(self, item_ids: tuple[str, ...]) -> None:
        self.itens = tuple(
            ItemRepetido(
                item_id=item_id,
                CASO_ID=_CASO,
                escopo=EscopoRepeticao.DIVIDA_ID,
                removido_em=None,
                criado_em=_AGORA,
            )
            for item_id in item_ids
        )

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        return self.itens


class _Casos:
    def buscar(self, caso_id: str) -> Caso | None:
        if caso_id != _CASO:
            return None
        return Caso(
            CASO_ID=_CASO,
            conta_id=_CONTA,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=date(2026, 9, 30),
            QUESTIONARIO_VERSION="1.0.3",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=_AGORA,
            criado_em=_AGORA,
        )

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == _CASO and conta_id == _CONTA


@cache
def _colecao_real() -> ColecaoDeRegistros:
    return carregar_registros()


def _trecho(*ids: str) -> ColecaoDeRegistros:
    reais = {r.ID: r for r in _colecao_real().registros}
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.3", registros=tuple(reais[i] for i in ids)
    )


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID=_CASO,
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=_AGORA,
    )


def _cliente(
    monkeypatch: pytest.MonkeyPatch,
    respostas: tuple[Resposta, ...],
    item_ids: tuple[str, ...] = (),
    colecao: ColecaoDeRegistros | None = None,
) -> tuple[TestClient, _Respostas]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    repositorio = _Respostas(respostas)
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = _Casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao or _colecao_real()
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: repositorio
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: _Itens(item_ids)

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA}")
    return cliente, repositorio


def test_t291_b5_00a_com_duas_dividas_declaradas_abre_a_lista_de_dividas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, _ = _cliente(monkeypatch, (_resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 2),))

    gravada = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B5.00A", "valor": "PESSOAL"}
    )

    assert gravada.status_code == 200, gravada.text
    assert "DIVIDA_ID" in gravada.json()["abrir_fichas"]


def test_t291_b5_00_sozinha_nao_pula_a_b5_00a(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com `B5.00A` ainda em branco a lista não abre: a próxima é ela."""
    cliente, _ = _cliente(monkeypatch, ())

    gravada = cliente.post(f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B5.00", "valor": "2"})

    assert gravada.status_code == 200, gravada.text
    assert "DIVIDA_ID" not in gravada.json()["abrir_fichas"]


def test_t291_com_ficha_ja_criada_nao_reabre_a_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _cliente(
        monkeypatch, (_resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 2),), ("D001",)
    )

    gravada = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B5.00A", "valor": "PESSOAL"}
    )

    assert gravada.status_code == 200, gravada.text
    assert "DIVIDA_ID" not in gravada.json()["abrir_fichas"]


def test_t292_salvar_divida_com_b5_d02_aberta_e_em_branco_e_recusado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trecho = _trecho("B5.D02", "B5.I01", "B5.CHECK")
    contrato = _resposta("DOCUMENTACAO_DISPONIVEL", frozenset({"CONTRATO"}), "D002")
    cliente, repositorio = _cliente(monkeypatch, (contrato,), ("D002",), trecho)

    recusada = cliente.post(
        f"/caso/{_CASO}/resposta",
        data={"ID_PERGUNTA": "B5.CHECK", "item_id": "D002", "valor": "SIM_SALVAR_DIVIDA"},
    )

    assert recusada.status_code == 400
    erro = recusada.json()["erro"]
    assert erro.startswith("Antes de salvar, responda nesta ficha:")
    assert "efetiva ou nominal" in erro
    assert [r.ID_PERGUNTA for r in repositorio.respostas] == ["DOCUMENTACAO_DISPONIVEL"]

    corrigir = cliente.post(
        f"/caso/{_CASO}/resposta",
        data={
            "ID_PERGUNTA": "B5.CHECK",
            "item_id": "D002",
            "valor": "QUERO_CORRIGIR_ALGUMA_INFORMACAO",
        },
    )
    assert corrigir.status_code == 200, corrigir.text

    assert (
        cliente.post(
            f"/caso/{_CASO}/resposta",
            data={"ID_PERGUNTA": "B5.D02", "item_id": "D002", "valor": "EFETIVA"},
        ).status_code
        == 200
    )
    salva = cliente.post(
        f"/caso/{_CASO}/resposta",
        data={"ID_PERGUNTA": "B5.CHECK", "item_id": "D002", "valor": "SIM_SALVAR_DIVIDA"},
    )
    assert salva.status_code == 200, salva.text
