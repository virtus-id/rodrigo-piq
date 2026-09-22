"""Testes e2e de `app/http/rotas_operador.py` — o painel dedicado do
operador (`RF-35`, `OQ-07` respondida, T-102).

Cobre os quatro critérios de aceite de T-102:

1. `GET /operador/painel` lista todos os casos com `estado`,
   `aguardando_revisao` e tempo desde `ultima_interacao_em`, cada campo lido
   diretamente de `RelatoDeProgresso` (`app/casos/progresso.py`, T-92) —
   nada recalculado nesta tarefa.
2. A rota recusa com `401`/`403` uma sessão sem `e_revisor = true`, antes de
   qualquer leitura de caso (mesmo mecanismo de `T-100`).
3. Nenhum dado financeiro do aluno aparece na tela.
4. Conta de aluno comum recebe `403`; conta revisora vê os casos de todos os
   alunos do piloto, cada um com seu estado e tempo de inatividade corretos.

`RepositorioCasosArquivo` (persistência real de arquivo, T-24) e um dublê de
`RepositorioContas` em memória (mesmo padrão de `tests/app_aluno/
test_guarda_papel_revisor.py`, T-100) — sem Postgres real.

REGRAS: `RF-35`, `RF-31`
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_contas_para_papel
from app.http.rotas_operador import (
    obter_colecao_de_registros_do_painel,
    obter_repositorio_casos_do_painel,
    obter_repositorio_itens_do_painel,
    obter_repositorio_respostas_do_painel,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.contas import Conta, RepositorioContas

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_DATA_REFERENCIA = datetime(2026, 1, 1, tzinfo=UTC).date()

# Coleção vazia de registros: o painel só exibe estado/aguardando_revisao/
# tempo de inatividade (nenhum destes três depende de `registros` não vazio);
# `proxima_pergunta` de `RelatoDeProgresso` não é exibida no template desta
# tarefa. Evita depender dos 245 registros reais só para este teste.
_COLECAO_VAZIA = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.0", registros=())


class _RepositorioContasDublê(RepositorioContas):
    """Mesmo dublê de `tests/app_aluno/test_guarda_papel_revisor.py`."""

    def __init__(self, contas: dict[str, Conta]) -> None:
        self._contas = contas

    def criar(self, conta_id: str, email: str, senha: str) -> None:  # pragma: no cover
        raise NotImplementedError("não usado por estes testes")

    # `T-179`: estes dois nascem do provisionamento pela Hotmart, que
    # nenhum destes testes exercita — o `Protocol` os exige, o dublê os
    # recusa explicitamente em vez de fingir comportamento.
    def provisionar(self, conta_id: str, email: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def definir_senha(self, conta_id: str, senha: str) -> None:  # pragma: no cover
        raise NotImplementedError

    # `005`: bloqueio por reembolso da Hotmart, que nenhum destes testes
    # exercita — o `Protocol` o exige, o dublê o recusa explicitamente em
    # vez de fingir comportamento.
    def bloquear(self, conta_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def buscar_por_email(self, email: str) -> Conta | None:  # pragma: no cover
        raise NotImplementedError("não usado por estes testes")

    def buscar_por_id(self, conta_id: str) -> Conta | None:
        return self._contas.get(conta_id)

    def autenticar(self, email: str, senha: str) -> Conta | None:  # pragma: no cover
        raise NotImplementedError("não usado por estes testes")


def _conta(conta_id: str, *, e_revisor: bool) -> Conta:
    return Conta(
        conta_id=conta_id,
        email=f"{conta_id}@teste.invalido",
        senha_hash="hash-nao-usado-neste-teste",
        criado_em=datetime.now(UTC),
        e_revisor=e_revisor,
    )


def _criar_caso(
    repositorio_casos: RepositorioCasosArquivo,
    caso_id: str,
    conta_id: str,
    *,
    estado: ESTADO_CASO,
    ultima_interacao_em: datetime,
) -> None:
    repositorio_casos.criar(
        Caso(
            CASO_ID=caso_id,
            conta_id=conta_id,
            estado=ESTADO_CASO.CADASTRADO,
            DATA_REFERENCIA=_DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=ultima_interacao_em,
            criado_em=ultima_interacao_em,
        )
    )
    if estado is not ESTADO_CASO.CADASTRADO:
        repositorio_casos.transicionar_estado(caso_id, estado, ultima_interacao_em)


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    return RepositorioCasosArquivo(tmp_path / "casos.jsonl")


@pytest.fixture
def aplicacao_e_dublê(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    tmp_path: Path,
) -> tuple[FastAPI, _RepositorioContasDublê]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    dublê = _RepositorioContasDublê(
        {
            "CONTA_ALUNO": _conta("CONTA_ALUNO", e_revisor=False),
            "CONTA_REVISOR": _conta("CONTA_REVISOR", e_revisor=True),
        }
    )
    aplicacao.dependency_overrides[obter_repositorio_contas_para_papel] = lambda: dublê
    aplicacao.dependency_overrides[obter_repositorio_casos_do_painel] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_colecao_de_registros_do_painel] = lambda: _COLECAO_VAZIA
    aplicacao.dependency_overrides[obter_repositorio_respostas_do_painel] = (
        lambda: RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_do_painel] = (
        lambda: RepositorioItensArquivo(tmp_path / "itens_repetidos.jsonl")
    )

    @aplicacao.post("/_teste/login")
    def login(request: Request, conta_id: str) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"status": "ok"}

    return aplicacao, dublê


@pytest.fixture
def cliente(
    aplicacao_e_dublê: tuple[FastAPI, _RepositorioContasDublê],
) -> TestClient:
    aplicacao, _dublê = aplicacao_e_dublê
    return TestClient(aplicacao, base_url="https://teste.local")


# ---------------------------------------------------------------------------
# Critério 2 — recusa com 401/403 uma sessão sem e_revisor=true, antes de
# qualquer leitura de caso.
# ---------------------------------------------------------------------------


def test_sem_sessao_recebe_401(cliente: TestClient) -> None:
    resposta = cliente.get("/api/operador/painel")

    assert resposta.status_code == 401


def test_conta_de_aluno_comum_recebe_403(cliente: TestClient) -> None:
    cliente.post("/_teste/login", params={"conta_id": "CONTA_ALUNO"})

    resposta = cliente.get("/api/operador/painel")

    assert resposta.status_code == 403
    assert resposta.status_code != 404


# ---------------------------------------------------------------------------
# Critérios 1, 3 e 4 — conta revisora vê todos os casos do piloto, cada um
# com estado e tempo de inatividade corretos; nenhum dado financeiro.
# ---------------------------------------------------------------------------


def test_conta_revisora_ve_todos_os_casos_com_estado_e_tempo_de_inatividade(
    cliente: TestClient,
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    agora = datetime.now(UTC)
    _criar_caso(
        repositorio_casos,
        "CASO-OPERADOR-1",
        "conta-aluno-1",
        estado=ESTADO_CASO.COLETA_INICIAL,
        ultima_interacao_em=agora - timedelta(days=3),
    )
    _criar_caso(
        repositorio_casos,
        "CASO-OPERADOR-2",
        "conta-aluno-2",
        estado=ESTADO_CASO.AGUARDANDO_REVISAO,
        ultima_interacao_em=agora - timedelta(hours=2),
    )

    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})
    resposta = cliente.get("/api/operador/painel")
    corpo = resposta.text

    assert resposta.status_code == 200
    # Os dois casos, de contas diferentes, aparecem os dois — o painel não
    # filtra por conta, é tela de operador.
    assert "CASO-OPERADOR-1" in corpo
    assert "CASO-OPERADOR-2" in corpo
    # Estado corrente de cada um, lido direto de RelatoDeProgresso.
    assert ESTADO_CASO.COLETA_INICIAL.value in corpo
    assert ESTADO_CASO.AGUARDANDO_REVISAO.value in corpo
    # Tempo de inatividade — cada caso com o texto correspondente ao seu
    # ultima_interacao_em (3 dias vs. 2 horas).
    assert "há 3 dias" in corpo
    assert "há 2 horas" in corpo
    # O caso 2, em AGUARDANDO_REVISAO, é sinalizado como aguardando revisão.
    # Antes (Jinja) o sinal era o texto "Sim" na célula; agora é o booleano
    # do JSON, e a tela decide como dizê-lo.
    linhas_por_caso = {linha["CASO_ID"]: linha for linha in resposta.json()["linhas"]}
    assert linhas_por_caso["CASO-OPERADOR-2"]["aguardando_revisao"] is True
    assert linhas_por_caso["CASO-OPERADOR-1"]["aguardando_revisao"] is False


def test_painel_nao_expoe_nenhum_dado_financeiro_do_aluno(
    cliente: TestClient,
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """Só os quatro campos estruturais de `RelatoDeProgresso` aparecem —
    nenhum valor de resposta (renda, dívida, saldo) é lido por esta rota."""
    agora = datetime.now(UTC)
    _criar_caso(
        repositorio_casos,
        "CASO-SEM-DADO-FINANCEIRO",
        "conta-aluno-3",
        estado=ESTADO_CASO.COLETA_INICIAL,
        ultima_interacao_em=agora,
    )

    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})
    resposta = cliente.get("/api/operador/painel")

    assert resposta.status_code == 200
    # Nenhum termo financeiro aparece na resposta — a rota nunca lê Resposta/
    # ValorResposta nem EstadoFinanceiro/SnapshotOrdem. A garantia vale igual
    # sobre JSON: o que não é servido não pode vazar para tela nenhuma.
    for termo_financeiro in ("R$", "Decimal", "SALDO_DEVEDOR", "RENDA_"):
        assert termo_financeiro not in resposta.text


def test_painel_vazio_quando_nenhum_caso_cadastrado(cliente: TestClient) -> None:
    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})

    resposta = cliente.get("/api/operador/painel")

    assert resposta.status_code == 200
    assert resposta.json()["linhas"] == []
