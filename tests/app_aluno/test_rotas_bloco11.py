"""Testes de `POST /caso/{CASO_ID}/bloco-11/resposta` e de `app/casos/
acompanhamento.py` — `RF-29`, `AC-05`, `AC-30`, `AC-31` (`T-82`).

Cobre os quatro critérios de aceite da tarefa:

1. `AC-31`: `A_CONFIRMAR` não dispara recálculo e não altera o status da
   dívida — provado pela resposta HTTP (`evento_recalculo: null`) depois de
   uma gravação bem-sucedida de `B11.Q01="A_CONFIRMAR"`.
2. `B11.Q01 = Sim` marca `QUITADA` e identifica o evento de recálculo —
   provado pela resposta HTTP (`evento_recalculo: "QUITACAO_CONFIRMADA"`) e
   pela leitura do valor gravado (`STATUS_QUITACAO_REAL = "QUITADA"`).
3. `AC-05`: o enunciado de `B11.Q01` exibe o `DIVIDA_ID` da ficha corrente no
   lugar de `[Dxxx]` — provado pelo campo `enunciado` da resposta HTTP.
4. `B11.Q02`–`B11.Q06` são coletadas na sequência declarada no registro —
   provado sobre `app/casos/acompanhamento.py::
   perguntas_do_bloco_11_confirmacao_quitacao`, sem subir a aplicação HTTP.

Mesmo padrão de dublê em memória de `tests/app_aluno/test_rotas_coleta_
dirigida.py` (`_RepositorioCasosDublê`) e do adaptador de arquivo já
existente `persistencia/app_aluno/arquivo.py::RepositorioRespostasArquivo`
(T-24) para rodar sem `DATABASE_URL` — nenhum destes testes é `requer_banco`.

REGRAS: `RF-29`, `AC-05`, `AC-30`, `AC-31`
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.acompanhamento import (
    evento_da_resposta_b11_q01,
    perguntas_do_bloco_11_confirmacao_quitacao,
)
from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_bloco11 import obter_colecao_de_registros, obter_repositorio_respostas
from app.http.rotas_bloco11 import roteador as roteador_bloco11
from app.http.sessao import iniciar_sessao_conta
from collection.carga import carregar_registros
from engine.tipos import EVENTO_RECALCULO
from persistencia.app_aluno.arquivo import RepositorioRespostasArquivo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID = "CONTA-BLOCO11-1"
_DIVIDA_ID_D003 = "D003"


class _RepositorioCasosDublê:
    """Restrito aos métodos que `exigir_caso_da_sessao` usa — mesmo padrão
    de `tests/app_aluno/test_rotas_coleta_dirigida.py::
    _RepositorioCasosDublê`."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _caso_em_acompanhamento(caso_id: str = "CASO-BLOCO11-1") -> Caso:
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


# ---------------------------------------------------------------------------
# AC-31 — A_CONFIRMAR não dispara recálculo e não altera o status da dívida.
# ---------------------------------------------------------------------------


def test_ac31_a_confirmar_nao_dispara_recalculo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`B11.Q01 = "Acredito que sim, mas ainda preciso confirmar."`
    (`valor_interno: A_CONFIRMAR`) é gravado normalmente, mas a resposta HTTP
    não identifica nenhum evento de recálculo."""
    caso = _caso_em_acompanhamento()
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID_D003, "valor": "A_CONFIRMAR"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["evento_recalculo"] is None

    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    assert valores["STATUS_QUITACAO_REAL"] == "A_CONFIRMAR"


def test_ac31_nao_tambem_nao_dispara_recalculo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`B11.Q01 = "Ainda não."` (`valor_interno: NAO`) — mesma ausência de
    evento que `A_CONFIRMAR`, ambos cobertos pelo mesmo critério `AC-31`."""
    caso = _caso_em_acompanhamento()
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID_D003, "valor": "NAO"},
    )

    assert resposta.status_code == 200
    assert resposta.json()["evento_recalculo"] is None


# ---------------------------------------------------------------------------
# B11.Q01 = Sim marca QUITADA e identifica o evento de recálculo.
# ---------------------------------------------------------------------------


def test_b11q01_sim_marca_quitada_e_identifica_evento_de_recalculo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`B11.Q01 = "Sim, foi quitada."` (`valor_interno: QUITADA`) grava
    `STATUS_QUITACAO_REAL = QUITADA` e a resposta HTTP identifica
    `EVENTO_RECALCULO.QUITACAO_CONFIRMADA` — sem que esta rota dispare
    nenhum executor (`T-86`, fora de escopo; ver docstring de `app/http/
    rotas_bloco11.py`)."""
    caso = _caso_em_acompanhamento()
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID_D003, "valor": "QUITADA"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["evento_recalculo"] == EVENTO_RECALCULO.QUITACAO_CONFIRMADA.name

    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    assert valores["STATUS_QUITACAO_REAL"] == "QUITADA"


def test_evento_da_resposta_b11_q01_e_chamada_fina_sobre_o_mapeamento_t81() -> None:
    """Prova unitária (sem HTTP) de que `app/casos/acompanhamento.py::
    evento_da_resposta_b11_q01` é exatamente `evento_recalculo_da_resposta`
    fixando `STATUS_QUITACAO_REAL` — os três valores possíveis de `B11.Q01`
    produzem o mesmo resultado que `app/eventos/mapeamento.py` (T-81) já
    documenta e testa."""
    assert evento_da_resposta_b11_q01("QUITADA") is EVENTO_RECALCULO.QUITACAO_CONFIRMADA
    assert evento_da_resposta_b11_q01("NAO") is None
    assert evento_da_resposta_b11_q01("A_CONFIRMAR") is None


# ---------------------------------------------------------------------------
# AC-05 — o enunciado exibe o DIVIDA_ID da ficha corrente no lugar de [Dxxx].
# ---------------------------------------------------------------------------


def test_ac05_enunciado_de_b11q01_exibe_o_divida_id_da_ficha_corrente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-05` — para `item_id="D003"`, o enunciado devolvido contém `D003`
    no lugar de `[Dxxx]`, e não contém mais o marcador literal."""
    caso = _caso_em_acompanhamento()
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID_D003, "valor": "NAO"},
    )

    assert resposta.status_code == 200
    enunciado = resposta.json()["enunciado"]
    assert _DIVIDA_ID_D003 in enunciado
    assert "[Dxxx]" not in enunciado


# ---------------------------------------------------------------------------
# B11.Q02–Q06 são coletadas na sequência declarada no registro.
# ---------------------------------------------------------------------------


def test_perguntas_do_bloco_11_confirmacao_quitacao_preserva_a_sequencia_do_registro() -> None:
    """Quarto critério de aceite: a ordem devolvida é exatamente a ordem em
    que `collection/registros/bloco-11.yaml` (T-18) lista as perguntas —
    nenhuma reordenação por conta deste módulo. `B11.Q04A` é condicional a
    `B11.Q04` e está incluída na mesma sequência (imediatamente após
    `B11.Q04`, como o YAML já declara)."""
    colecao = carregar_registros()

    perguntas = perguntas_do_bloco_11_confirmacao_quitacao(colecao.registros)

    ids = [p.ID for p in perguntas]
    assert ids == ["B11.Q01", "B11.Q02", "B11.Q03", "B11.Q04", "B11.Q04A", "B11.Q05", "B11.Q06"]


def test_perguntas_do_bloco_11_confirmacao_quitacao_nao_inclui_outras_fichas_por_acao_id() -> None:
    """As demais perguntas do Bloco 11 por `ACAO_ID` (`B11.01`,
    `B11.03-INF`/`-REN`/`-TRO`/`-ECO`) não fazem parte desta ficha de
    confirmação de quitação — a rota especializada de `T-82` não as aceita."""
    colecao = carregar_registros()

    perguntas = perguntas_do_bloco_11_confirmacao_quitacao(colecao.registros)

    ids = {p.ID for p in perguntas}
    assert "B11.01" not in ids
    assert "B11.03-INF" not in ids


# ---------------------------------------------------------------------------
# Isolamento por CASO_ID — mesma disciplina de qualquer outra rota da feature.
# ---------------------------------------------------------------------------


def test_isolamento_recusa_sessao_de_outra_conta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`RF-02`/`AC-03`: uma sessão de outra conta recebe `404`, nunca grava
    resposta num caso alheio."""
    caso = _caso_em_acompanhamento()
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco11)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, "CONTA-DONA-DO-CASO"
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

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID_D003, "valor": "QUITADA"},
    )

    assert resposta.status_code == 404
