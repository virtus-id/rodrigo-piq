"""Testes do Bloco 10 — `RF-17`, `RF-18`, `AC-19`, `AC-22`, `AC-23`, `AC-24`
(T-79).

Cobre `app/casos/confirmacao_ataque.py` (T-77/T-78) e `POST /caso/{CASO_ID}/
bloco-10/resposta` (`app/http/rotas_bloco10.py`, T-77/T-78). `AC-19` (Bloco
7/8) já está integralmente coberto por `tests/app_aluno/
test_coleta_dirigida.py` (T-75/T-76) — este módulo não o duplica, só cita a
rastreabilidade no cabeçalho conforme `T-79` exige.

Mesma técnica de fixture de `tests/regras/test_ataque_imediato_recomendado_
diagnostico.py`: um `SnapshotOrdem` REAL, produzido por `calcular_plano`
sobre a fixture de caso completo (`tests/app_aluno/fixtures/caso_completo.py`,
T-53), com `ATAQUE_IMEDIATO_RECOMENDADO` CONTROLADO via `dataclasses.replace`
sobre `snapshot.diagnostico` — o mesmo mecanismo já usado por
`tests/regras/test_repositorio_snapshots.py`/`test_reserva_recomendada.py`
para forçar o campo em teste, sem precisar reproduzir um cenário completo de
gates/necessidade-elegível só para obter um valor positivo.

REGRAS: `RF-17`, `RF-18`, `AC-19`, `AC-22`, `AC-23`, `AC-24`
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.confirmacao_ataque import (
    RespostasDoBloco10,
    ataque_imediato_recomendado_de,
    bloco_10_alcancavel,
    perguntas_do_bloco_10,
)
from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_bloco10 import (
    obter_colecao_de_registros,
    obter_repositorio_respostas,
    obter_repositorio_snapshots,
)
from app.http.rotas_bloco10 import roteador as roteador_bloco10
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import RespostasCaso
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioRespostasArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_PARAMETROS_VERSAO = "1.0.1"
_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID = "CONTA-BLOCO10-1"
_DIVIDA_ID = "D001"


def _montar_snapshot_base() -> SnapshotOrdem:
    """Um `SnapshotOrdem` REAL, uma única dívida elegível — mesma técnica de
    `tests/app_aluno/test_coleta_dirigida.py::_montar_snapshot`.
    `ATAQUE_IMEDIATO_RECOMENDADO` sai `dinheiro(0)` deste cálculo (nenhuma
    necessidade financeira imediata elegível no caso completo padrão); os
    testes que precisam de um valor positivo o sobrescrevem via
    `_com_ataque_imediato_recomendado`."""
    respostas = caso_completo(DIVIDA_ID=_DIVIDA_ID).respostas
    divida = montar_divida(respostas, _DIVIDA_ID)
    caso = caso_completo(DIVIDA_ID=_DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def _com_ataque_imediato_recomendado(
    snapshot: SnapshotOrdem, valor: str
) -> SnapshotOrdem:
    """Sobrescreve `snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` via
    `dataclasses.replace` — o campo é `Dinheiro` (`Decimal`), controlado sem
    precisar montar um cenário completo de gates/necessidade-elegível.
    Mesma técnica de `tests/regras/test_repositorio_snapshots.py`."""
    diagnostico = dataclasses.replace(
        snapshot.diagnostico, ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(valor)
    )
    return dataclasses.replace(snapshot, diagnostico=diagnostico)


# ---------------------------------------------------------------------------
# app/casos/confirmacao_ataque.py — camada de domínio (T-77, T-78)
# ---------------------------------------------------------------------------


def test_ataque_imediato_recomendado_de_le_o_campo_sem_recomputar() -> None:
    """Terceiro critério de `T-77`: leitura direta do campo do snapshot."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")

    assert ataque_imediato_recomendado_de(snapshot) == dinheiro("1000.00")


def test_ac22_bloco_10_nao_alcancavel_com_recomendado_zero() -> None:
    """`AC-22` — `ATAQUE_IMEDIATO_RECOMENDADO = 0` ⇒ `bloco_10_alcancavel`
    devolve `False`: o caso não entra em `CONFIRMACAO_ATAQUE`, `B10.C01` não
    é exibida."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "0")

    assert bloco_10_alcancavel(snapshot) is False


def test_bloco_10_alcancavel_com_recomendado_positivo() -> None:
    """Contraprova de `AC-22`: com `ATAQUE_IMEDIATO_RECOMENDADO > 0`, o
    Bloco 10 é alcançável."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")

    assert bloco_10_alcancavel(snapshot) is True


def test_ac24_perguntas_do_bloco_10_nao_tem_escolha_de_divida() -> None:
    """`AC-24` — auditoria das perguntas exibidas no Bloco 10: nenhuma delas
    tem `escopo_repeticao` por dívida, nem opção cujo `valor_interno` ou
    `rotulo` referencie um `DIVIDA_ID` — a ordem é do motor, nunca do
    aluno."""
    colecao = carregar_registros()

    perguntas = perguntas_do_bloco_10(colecao.registros)

    assert len(perguntas) > 0
    assert all(registro.bloco == 10 for registro in perguntas)
    for registro in perguntas:
        assert registro.escopo_repeticao is not EscopoRepeticao.DIVIDA_ID
        for opcao in registro.opcoes:
            texto = f"{opcao.rotulo} {opcao.valor_interno or ''}".upper()
            assert "DIVIDA" not in texto and "DÍVIDA" not in texto


def test_perguntas_do_bloco_10_inclui_b10_c01_e_b10_c01a() -> None:
    colecao = carregar_registros()

    ids = {registro.ID for registro in perguntas_do_bloco_10(colecao.registros)}

    assert "B10.C01" in ids
    assert "B10.C01A" in ids


def test_respostas_do_bloco10_resolve_zero_e_recomendado_do_snapshot() -> None:
    """`T-78` — `RespostasDoBloco10` resolve `ZERO`/`ATAQUE_IMEDIATO_
    RECOMENDADO` a partir do snapshot, e delega qualquer outra variável para
    a `RespostasCaso` recebida."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    adaptador = RespostasDoBloco10(
        respostas=RespostasCaso(respostas=()), snapshot=snapshot
    )

    assert adaptador.valor_no_item("", "ZERO") == dinheiro("0")
    assert adaptador.valor_no_item("", "ATAQUE_IMEDIATO_RECOMENDADO") == dinheiro("1000.00")
    # Variável comum: ausência de resposta gravada continua None (delegado).
    assert adaptador.valor_no_item("", "ATAQUE_IMEDIATO_APROVADO") is None


# ---------------------------------------------------------------------------
# POST /caso/{CASO_ID}/bloco-10/resposta — rota HTTP (T-77, T-78)
# ---------------------------------------------------------------------------


class _RepositorioCasosDublê:
    """Restrito aos métodos que `exigir_caso_da_sessao` usa — mesmo padrão
    de `tests/app_aluno/test_rotas_bloco11.py::_RepositorioCasosDublê`."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


class _RepositorioSnapshotsDublê:
    """Um único snapshot em memória — mesmo padrão de `tests/app_aluno/
    test_rotas_coleta_dirigida.py::_RepositorioSnapshotsDublê`."""

    def __init__(self, snapshot: SnapshotOrdem) -> None:
        self._snapshot = snapshot

    def anexar(self, s: SnapshotOrdem) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        if snapshot_id != self._snapshot.SNAPSHOT_ID:
            raise ErroSnapshotNaoEncontrado(f"sem snapshot com SNAPSHOT_ID={snapshot_id!r}")
        return self._snapshot

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


def _caso_fabricado(*, snapshot_liberado_id: str | None, caso_id: str = "CASO-BLOCO10-1") -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.CONFIRMACAO_ATAQUE,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot_liberado_id,
        snapshot_liberado_id=snapshot_liberado_id,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    caso: Caso,
    snapshot: SnapshotOrdem,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco10)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = (
        lambda: _RepositorioSnapshotsDublê(snapshot)
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


def test_ac22_rota_recusa_resposta_com_recomendado_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-22` — com `ATAQUE_IMEDIATO_RECOMENDADO = 0`, a rota recusa
    `B10.C01`, e nada é gravado."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "0")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "TODO"},
    )

    assert resposta.status_code == 400
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    assert gravadas == ()


def test_aceite_total_e_gravado_quando_bloco_alcancavel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Quarto critério de `T-77`: aceite TOTAL é um dos três caminhos
    possíveis, registrado como resposta."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "TODO"},
    )

    assert resposta.status_code == 200
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    assert valores["ATAQUE_IMEDIATO_APROVADO"] == "TODO"


def test_aceite_nenhum_e_gravado_quando_bloco_alcancavel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Quarto critério de `T-77`: aceite NENHUM é um dos três caminhos
    possíveis, registrado como resposta."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "NAO"},
    )

    assert resposta.status_code == 200
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    assert valores["ATAQUE_IMEDIATO_APROVADO"] == "NAO"


def test_ac23_valor_parcial_maior_que_recomendado_e_recusado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-23` — recomendado `1000`, `B10.C01A = 1500`: recusado, nada
    gravado. Tolerância ZERO: `1000,01` já seria suficiente para recusar,
    mas o critério de aceite usa `1500` explicitamente. `B10.C01A` só abre
    depois de `B10.C01 = PARTE` (`condicao_exibicao` do registro) — a
    resposta que a abre é gravada primeiro."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)
    cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "PARTE"},
    )

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01A", "valor": "1500,00"},
    )

    assert resposta.status_code == 400
    corpo = resposta.json()
    assert "ATAQUE_IMEDIATO_APROVADO" in corpo["erro"]
    assert "ATAQUE_IMEDIATO_RECOMENDADO" in corpo["erro"]
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    # B10.C01=PARTE foi gravado (abriu B10.C01A); B10.C01A em si NÃO foi.
    assert valores == {"ATAQUE_IMEDIATO_APROVADO": "PARTE"}


def test_ac23_valor_parcial_igual_ao_recomendado_e_aceito(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Tolerância ZERO na fronteira: `1000,00` sobre recomendado `1000,00` é
    aceito (`<=`, não `<`) — prova de que a validação não é conservadora
    demais."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)
    cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "PARTE"},
    )

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01A", "valor": "1000,00"},
    )

    assert resposta.status_code == 200


def test_ac23_valor_negativo_e_recusado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-23` (limite inferior, `0 <= ATAQUE_IMEDIATO_APROVADO`) — valor
    negativo é recusado pelo mesmo caminho de validação cruzada."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    cliente = _montar_cliente(monkeypatch, tmp_path, caso=caso, snapshot=snapshot)
    cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "PARTE"},
    )

    resposta = cliente.post(
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01A", "valor": "-100,00"},
    )

    assert resposta.status_code == 400
    gravadas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    ).listar_do_caso(caso.CASO_ID)
    valores = {r.ID_PERGUNTA: r.valor for r in gravadas}
    # B10.C01=PARTE foi gravado (abriu B10.C01A); B10.C01A em si NÃO foi.
    assert valores == {"ATAQUE_IMEDIATO_APROVADO": "PARTE"}


def test_isolamento_recusa_sessao_de_outra_conta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`RF-02`/`AC-03`: sessão de outra conta recebe `404`."""
    snapshot = _com_ataque_imediato_recomendado(_montar_snapshot_base(), "1000.00")
    caso = _caso_fabricado(snapshot_liberado_id=snapshot.SNAPSHOT_ID)
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco10)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, "CONTA-DONA-DO-CASO"
    )
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = (
        lambda: _RepositorioSnapshotsDublê(snapshot)
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
        f"/caso/{caso.CASO_ID}/bloco-10/resposta",
        data={"ID_PERGUNTA": "B10.C01", "valor": "TODO"},
    )

    assert resposta.status_code == 404
