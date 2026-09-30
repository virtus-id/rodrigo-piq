"""`B3.C00` por integração — `RF-79`, `RF-80`, `AC-119`, `AC-120`
(`T-227`, `T-229`).

Aplicação real, registros REAIS, repositórios em memória por
`app.dependency_overrides` (sem banco): `GET /pergunta/B3.C00` devolve o
painel; qualquer outra pergunta mantém o contrato de hoje; `NAO_SEI` na
`B3.C00` segue o fluxo; a correção pela rota de `RF-69` reflete no painel.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import cache

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.inventario import pendencias_de_inventario
from app.casos.maquina import ESTADO_CASO, Caso
from app.casos.progresso import pendencias_obrigatorias
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem.conversao import converter_para_dinheiro
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta, RespostasCaso

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA = "CONTA-FOTO-1"
_CASO = "CASO-FOTO-1"
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
    def __init__(self) -> None:
        def item(item_id: str, escopo: EscopoRepeticao, origem: str | None) -> object:
            from persistencia.app_aluno.itens import ItemRepetido

            return ItemRepetido(
                item_id=item_id,
                CASO_ID=_CASO,
                escopo=escopo,
                removido_em=None,
                criado_em=_AGORA,
                origem=origem,
            )

        self.itens = (
            item("I001", EscopoRepeticao.ITEM_DESPESA, "B3.D01:ALUGUEL"),
            item("I002", EscopoRepeticao.ITEM_DESPESA, None),
            item("NM001", EscopoRepeticao.DESPESA_NAO_MENSAL_ID, None),
        )

    def listar_do_caso(self, caso_id: str, *, incluir_removidos: bool = True) -> tuple[object, ...]:
        return self.itens


class _Casos:
    def __init__(self) -> None:
        self.caso = Caso(
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

    def buscar(self, caso_id: str) -> Caso | None:
        return self.caso if caso_id == _CASO else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == _CASO and conta_id == _CONTA


@cache
def _colecao_real() -> ColecaoDeRegistros:
    return carregar_registros()


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID=_CASO,
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=_AGORA,
    )


def _respostas_iniciais() -> tuple[Resposta, ...]:
    return (
        _resposta("RENDA_PRINCIPAL", converter_para_dinheiro("8.000,00")),
        _resposta("VALOR_DESPESA", converter_para_dinheiro("3.000,00"), "I001"),
        _resposta("VALOR_DESPESA", converter_para_dinheiro("2.000,00"), "I002"),
        _resposta("DESPESAS_NAO_MENSAIS_EXISTE", "SIM"),
        _resposta("VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("6.000,00"), "NM001"),
    )


def _cliente(
    monkeypatch: pytest.MonkeyPatch, colecao: ColecaoDeRegistros | None = None
) -> tuple[TestClient, _Respostas]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    respostas = _Respostas(_respostas_iniciais())
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = _Casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao or _colecao_real()
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = _Itens

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA}")
    return cliente, respostas


def test_t227_b3_c00_devolve_o_painel_com_os_destinos_de_correcao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, _ = _cliente(monkeypatch)

    painel = cliente.get(f"/caso/{_CASO}/pergunta/B3.C00").json()["pergunta"]["painel"]

    numeros = ("renda_total", "despesas_totais", "sobra_antes_das_dividas")
    assert tuple(painel[n] for n in numeros) == ("8000.00", "5500.00", "2500.00")
    assert painel["parcial"] == {"renda": False, "despesas": False, "sobra": False}
    primeira = painel["despesas_por_item"][0]
    assert primeira["rotulo"] == "Aluguel"
    assert primeira["corrigir"] == {"ID_PERGUNTA": "B3.DF01", "item_id": "I001"}
    assert painel["nao_mensais_por_item"][0]["corrigir"] == {
        "ID_PERGUNTA": "B3.NM02B",
        "item_id": "NM001",
    }


def test_t227_pergunta_sem_painel_mantem_o_contrato(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _cliente(monkeypatch)

    pergunta = cliente.get(f"/caso/{_CASO}/pergunta/B3.01").json()["pergunta"]

    assert "painel" not in pergunta


def test_t229_ac119_correcao_pela_rota_de_rf69_reflete_no_painel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, _ = _cliente(monkeypatch)

    gravada = cliente.post(
        f"/caso/{_CASO}/resposta",
        data={"ID_PERGUNTA": "B3.DF01", "item_id": "I001", "valor": "4.000,00"},
    )
    assert gravada.status_code == 200, gravada.text

    painel = cliente.get(f"/caso/{_CASO}/pergunta/B3.C00").json()["pergunta"]["painel"]
    assert painel["despesas_totais"] == "6500.00"
    assert painel["sobra_antes_das_dividas"] == "1500.00"


def test_t229_ac120_nao_sei_segue_para_b3_c01_sem_acao_nem_pendencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-120`: sobre o trecho real do fluxo (`B3.C00` → `B3.C01`), a
    resposta "Ainda não consigo avaliar" grava e a próxima é `B3.C01`; nenhuma
    ficha é aberta, nenhuma pendência de cálculo nasce dela."""
    reais = {r.ID: r for r in _colecao_real().registros}
    trecho = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.3", registros=(reais["B3.C00"], reais["B3.C01"])
    )
    cliente, respostas = _cliente(monkeypatch, trecho)

    gravada = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B3.C00", "nao_sei": "on"}
    )

    assert gravada.status_code == 200, gravada.text
    corpo = gravada.json()
    assert corpo["proxima"]["pergunta"]["ID"] == "B3.C01"
    assert corpo["abrir_fichas"] == []
    gravadas = RespostasCaso(respostas=tuple(respostas.respostas))
    ids_pendentes = {p.ID for p in pendencias_obrigatorias(trecho.registros, gravadas, {})}
    assert "B3.C00" not in ids_pendentes
    itens = {EscopoRepeticao.DESPESA_NAO_MENSAL_ID: ("NM001",)}
    assert pendencias_de_inventario(_colecao_real().registros, gravadas, itens) == ()
