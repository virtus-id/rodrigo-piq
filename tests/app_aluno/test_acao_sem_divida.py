"""Teste de `AC-50` (ação sem dívida) sobre o vínculo por `ACAO_ID` — T-89.

`AC-50` é testável hoje porque depende só de a CHAVE de vínculo da resposta
do Bloco 11 ser `ACAO_ID`, nunca `DIVIDA_ID` (`collection/registros/
bloco-11.yaml` já declara `escopo_repeticao: ACAO_ID` para `B11.Q01`–`B11.Q06`,
T-18) — independe de `OQ-15` (a ação de economia real) e das três mudanças
pendentes em `engine/gates.py::AcaoRequerida` (slug `motor-calculo`).

Este teste prova o caminho HTTP PONTA A PONTA (`POST /caso/{CASO_ID}/
bloco-11/resposta`, `app/http/rotas_bloco11.py`, T-82) para uma ação SEM
`DIVIDA_ID` associado: a pergunta é exibida (o enunciado é devolvido) e a
resposta é gravada com `item_id = ACAO_ID` — nunca com um `DIVIDA_ID`
inventado como substituto.

`B11.Q01` (confirmação de quitação) é a pergunta escolhida para este teste:
`condicao_exibicao: null` (sempre aberta, sem depender de `TIPO_ACAO`) e
`escopo_repeticao: ACAO_ID`. Isso permite construir a fixture de ação sem
dívida com um `ACAO_ID` (identificador de INSTÂNCIA, ex. `"A001"`) e SEM
`TIPO_ACAO` — `AC-50` é sobre `DIVIDA_ID` ausente, não sobre tipo de ação
(`OQ-13`, que seria necessário só para perguntas condicionadas a `TIPO_ACAO`,
como `B11.03-ECO`, fora do escopo desta tarefa).

Mesmo padrão de dublê em memória e mesmo `RepositorioRespostasArquivo`
(T-24) de `tests/app_aluno/test_rotas_bloco11.py` (T-82) — sem `xfail`,
sem `DATABASE_URL`.

REGRAS: RF-33, AC-50
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_bloco11 import obter_colecao_de_registros, obter_repositorio_respostas
from app.http.rotas_bloco11 import roteador as roteador_bloco11
from app.http.sessao import iniciar_sessao_conta
from collection.carga import carregar_registros
from persistencia.app_aluno.arquivo import RepositorioRespostasArquivo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID = "CONTA-ACAO-SEM-DIVIDA-1"

# Identificador de INSTÂNCIA de uma ação SEM dívida associada (a futura ação
# de economia, `OQ-15`) — nunca um `TIPO_ACAO` (`OQ-13`, fora do escopo deste
# teste). Nenhum `DIVIDA_ID` correspondente existe em lugar nenhum do teste.
_ACAO_ID_SEM_DIVIDA = "A001"


class _RepositorioCasosDublê:
    """Restrito aos métodos que `exigir_caso_da_sessao` usa — mesmo padrão
    de `tests/app_aluno/test_rotas_bloco11.py::_RepositorioCasosDublê`
    (T-82)."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _caso_em_acompanhamento(caso_id: str = "CASO-ACAO-SEM-DIVIDA-1") -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.ACOMPANHAMENTO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id="SNAP-1",
        snapshot_liberado_id="SNAP-1",
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    caso: Caso,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco11)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = carregar_registros
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        lambda: RepositorioRespostasArquivo(caminho_arquivo=tmp_path / "respostas.jsonl")
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def test_ac50_acao_sem_divida_e_exibida_no_bloco_11_e_sua_resposta_e_gravada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-50` — uma ação sem `DIVIDA_ID` associado (identificada apenas por
    `ACAO_ID`) é exibida no Bloco 11: `B11.Q01` é aceita normalmente com
    `item_id=ACAO_ID` (a rota nunca exige um `DIVIDA_ID` correspondente) e o
    enunciado é devolvido na resposta HTTP. A resposta é então gravada com
    `item_id = ACAO_ID` — nunca com um `DIVIDA_ID` inventado."""
    caso = _caso_em_acompanhamento()
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _ACAO_ID_SEM_DIVIDA, "valor": "QUITADA"},
    )

    # Exibição: a rota aceita a pergunta e devolve o enunciado — nenhum
    # `DIVIDA_ID` foi exigido para que B11.Q01 fosse considerada aberta.
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ID_PERGUNTA"] == "B11.Q01"
    assert corpo["enunciado"]  # enunciado interpolado e não vazio

    # Gravação: a resposta persistida carrega item_id = ACAO_ID, a chave de
    # vínculo real (RF-33) — nunca um DIVIDA_ID substituto.
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    respostas_da_acao = [r for r in gravadas if r.ID_PERGUNTA == "STATUS_QUITACAO_REAL"]
    assert len(respostas_da_acao) == 1
    assert respostas_da_acao[0].item_id == _ACAO_ID_SEM_DIVIDA
    assert respostas_da_acao[0].valor == "QUITADA"
