"""Perguntas complementares na mesma tela — `RF-99`, `AC-157` (`T-307`).

Aplicação real, registros REAIS, repositórios em memória por
`app.dependency_overrides` (sem banco): a pergunta-mãe sai com
`complementares` por opção, decidido no servidor (`RF-45`); a mãe gravada
abre as filhas, cada uma validada como sempre; a próxima pula as já
respondidas.
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
_CONTA = "CONTA-THREAD-1"
_CASO = "CASO-THREAD-1"
_AGORA = datetime(2026, 10, 1, tzinfo=UTC)


class _Respostas:
    def __init__(self) -> None:
        self.respostas: list[Resposta] = []

    def gravar(self, resposta: Resposta) -> None:
        self.respostas = [
            r
            for r in self.respostas
            if not (r.ID_PERGUNTA == resposta.ID_PERGUNTA and r.item_id == resposta.item_id)
        ] + [resposta]

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(self.respostas)


class _Itens:
    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        return (
            ItemRepetido(
                item_id="D001",
                CASO_ID=_CASO,
                escopo=EscopoRepeticao.DIVIDA_ID,
                removido_em=None,
                criado_em=_AGORA,
                origem=None,
            ),
        )


class _Casos:
    def buscar(self, caso_id: str) -> Caso | None:
        return Caso(
            CASO_ID=_CASO,
            conta_id=_CONTA,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=date(2026, 10, 1),
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


def _cliente(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _Respostas]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    respostas = _Respostas()
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = _Casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = _colecao_real
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = _Itens

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA}")
    return cliente, respostas


def _ids(complementares: dict[str, list[dict[str, object]]]) -> dict[str, list[object]]:
    return {valor: [f["ID"] for f in filhas] for valor, filhas in complementares.items()}


@pytest.mark.parametrize(
    ("mae", "item_id", "esperado"),
    [
        ("B3.02", None, {"VARIAVEL": ["B3.02A", "B3.02B"]}),
        ("B2.09", None, {"SIM": ["B2.10", "B2.10A"]}),
        ("B5.D05", "D001", {"SIM": ["B5.D05A", "B5.D05B", "B5.D05S"]}),
        (
            "B5.C01",
            "D001",
            {"SIM": ["B5.C02", "B5.C03", "B5.C04"], "NAO": ["B5.C05"], "NAO_SEI": ["B5.C05"]},
        ),
    ],
)
def test_ac157_mae_traz_as_filhas_de_cada_opcao(
    monkeypatch: pytest.MonkeyPatch,
    mae: str,
    item_id: str | None,
    esperado: dict[str, list[str]],
) -> None:
    cliente, _ = _cliente(monkeypatch)
    sufixo = f"?item_id={item_id}" if item_id else ""

    pergunta = cliente.get(f"/caso/{_CASO}/pergunta/{mae}{sufixo}").json()["pergunta"]

    assert _ids(pergunta["complementares"]) == esperado
    for filhas in pergunta["complementares"].values():
        for filha in filhas:
            # Serializada como as demais, no mesmo item, e sem thread própria
            # (profundidade 1).
            assert filha["item_id"] == item_id
            assert "complementares" not in filha


def test_ac157_filha_longe_da_mae_nao_entra_na_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """`B5.G03` lê o tipo da dívida (`B5.A02`) mas está em outro grupo da
    ficha: puxá-la para a tela de `B5.A02` mudaria a ordem da coleta."""
    cliente, _ = _cliente(monkeypatch)

    pergunta = cliente.get(f"/caso/{_CASO}/pergunta/B5.A02?item_id=D001").json()["pergunta"]

    assert "complementares" not in pergunta


def test_ac157_pergunta_sem_filhas_mantem_o_contrato(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _cliente(monkeypatch)

    pergunta = cliente.get(f"/caso/{_CASO}/pergunta/B3.01").json()["pergunta"]

    assert "complementares" not in pergunta


def test_ac157_mae_e_filhas_gravadas_em_ordem_e_proxima_pula_as_respondidas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, respostas = _cliente(monkeypatch)

    # Antes da mãe, a filha está fechada — a ordem mãe → filhas importa.
    fechada = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B3.02A", "valor": "1.000,00"}
    )
    assert fechada.status_code == 400

    mae = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B3.02", "valor": "VARIAVEL"}
    )
    assert mae.status_code == 200, mae.text

    recusada = cliente.post(
        f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": "B3.02A", "valor": "abc"}
    )
    assert recusada.status_code == 400
    # A mãe continua gravada; a filha recusada não.
    gravadas = {r.ID_PERGUNTA: r.valor for r in respostas.respostas}
    assert gravadas["TIPO_RENDA"] == "VARIAVEL"
    assert len(gravadas) == 1

    for filha, valor in (("B3.02A", "1.000,00"), ("B3.02B", "3.000,00")):
        gravada = cliente.post(
            f"/caso/{_CASO}/resposta", data={"ID_PERGUNTA": filha, "valor": valor}
        )
        assert gravada.status_code == 200, gravada.text

    proxima = gravada.json()["proxima"]["pergunta"]
    assert proxima["ID"] not in {"B3.02", "B3.02A", "B3.02B"}
