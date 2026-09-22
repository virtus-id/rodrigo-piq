"""Testes da guarda de papel de revisor — `RF-23`, `RF-25` (T-100).

Cobre os cinco critérios de aceite de T-100 pelo comportamento observável,
SEM Postgres real: `RepositorioContas` é substituído por um dublê em
memória via `app.dependency_overrides` (mesmo mecanismo de injeção que a
produção usa, `Depends(obter_repositorio_contas_para_papel)`), na mesma
disciplina de `tests/app_aluno/test_rotas_conta.py` (T-30) e `tests/
app_aluno/e2e/test_mecanismo_isolamento.py` (T-31). A validação da migração
e da coluna `e_revisor` contra Postgres real está em `tests/app_aluno/
integracao/test_persistencia_contas.py` (`requer_banco`).

1. sem sessão nenhuma ⇒ `401`, antes de qualquer leitura de caso;
2. sessão de aluno comum (`e_revisor=False`) ⇒ `403`, nunca `404`;
3. sessão de conta com `e_revisor=True` ⇒ acesso concedido (`200`);
4. a guarda consulta o repositório a cada requisição, sem cache — revogar
   `e_revisor` entre duas chamadas muda o resultado na PRÓXIMA, sem qualquer
   alteração na sessão;
5. teste complementar à auditoria de isolamento por `CASO_ID` (`T-31`/`T-32`):
   prova que a NOVA guarda de papel existe e funciona sobre a rota REAL
   `GET /revisao/fila`, registrada na aplicação de produção — sem substituir
   nem estender aquela auditoria (que continua vazia e fora do escopo de
   `/revisao/*`, motivo já registrado em T-69/T-100).

REGRAS: `RF-23`, `RF-25`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_contas_para_papel
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_snapshots_da_fila,
)
from app.http.sessao import iniciar_sessao_conta
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo
from persistencia.app_aluno.contas import Conta, RepositorioContas
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


class _RepositorioContasDublê(RepositorioContas):
    """Dublê em memória — cada chamada a `buscar_por_id` é contada, para
    provar o critério 4 (consulta a cada requisição, sem cache)."""

    def __init__(self, contas: dict[str, Conta]) -> None:
        self._contas = contas
        self.chamadas_buscar_por_id = 0

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
        self.chamadas_buscar_por_id += 1
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


@pytest.fixture
def aplicacao_e_dublê(
    monkeypatch: pytest.MonkeyPatch,
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
    # Nos cenários de recusa (sem sessão / sem papel), a fila não deve chegar
    # a consultar casos — um repositório que levanta em qualquer chamada
    # prova, por si só, que a guarda de papel recusou ANTES de qualquer
    # leitura de caso (critério 1). Nos cenários de acesso CONCEDIDO
    # (critérios 3/4), o handler segue e de fato lista casos — por isso este
    # dublê é substituído por um repositório de arquivo real (vazio) DENTRO
    # de cada teste que precisa de acesso concedido.
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = (
        lambda: _RepositorioCasosQueNuncaDeveSerChamado()
    )
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = (
        lambda: _RepositorioCasosQueNuncaDeveSerChamado()
    )

    @aplicacao.post("/_teste/login")
    def login(request: Request, conta_id: str) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"status": "ok"}

    return aplicacao, dublê


@pytest.fixture
def cliente_e_repositorio(
    aplicacao_e_dublê: tuple[FastAPI, _RepositorioContasDublê],
) -> tuple[TestClient, _RepositorioContasDublê]:
    aplicacao, dublê = aplicacao_e_dublê
    return TestClient(aplicacao, base_url="https://teste.local"), dublê


def _permitir_fila_vazia(aplicacao: FastAPI, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Substitui os repositórios "que nunca deveriam ser chamados" por
    adaptadores de arquivo reais e vazios — usado nos cenários em que o
    acesso É concedido e o handler de fato precisa listar casos (nenhum
    caso em `AGUARDANDO_REVISAO`, fila vazia, caminho já coberto por
    `tests/app_aluno/test_rotas_revisao.py::
    test_fila_vazia_quando_nenhum_caso_esta_em_aguardando_revisao`)."""
    diretorio = tmp_path_factory.mktemp("guarda-papel-revisor")
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = (
        lambda: RepositorioCasosArquivo(diretorio / "casos.jsonl")
    )
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = (
        lambda: RepositorioSnapshotsArquivo(diretorio / "snapshots.jsonl")
    )


class _RepositorioCasosQueNuncaDeveSerChamado:
    """Qualquer chamada a qualquer método levanta — usado para provar que a
    guarda de papel recusa a requisição ANTES de `RepositorioCasos.
    listar_por_estado` (ou qualquer outra leitura de caso) ser invocado."""

    def __getattr__(self, nome: str) -> object:
        def _levantar(*args: object, **kwargs: object) -> object:
            raise AssertionError(
                f"RepositorioCasos.{nome} não deveria ter sido chamado: a guarda de "
                "papel deve recusar ANTES de qualquer leitura de caso"
            )

        return _levantar


# ---------------------------------------------------------------------------
# Critério 1 — sem sessão ⇒ 401, antes de qualquer leitura de caso.
# ---------------------------------------------------------------------------


def test_sem_sessao_recebe_401_antes_de_qualquer_leitura_de_caso(
    cliente_e_repositorio: tuple[TestClient, _RepositorioContasDublê],
) -> None:
    cliente, dublê = cliente_e_repositorio
    # Nenhum login realizado.

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 401
    # O repositório de contas nunca foi consultado — a recusa por ausência de
    # sessão ocorre antes até de perguntar ao banco quem é o dono da sessão.
    assert dublê.chamadas_buscar_por_id == 0


# ---------------------------------------------------------------------------
# Critério 2 — conta autenticada sem papel de revisor ⇒ 403, nunca 404.
# ---------------------------------------------------------------------------


def test_conta_de_aluno_comum_recebe_403_nunca_404(
    cliente_e_repositorio: tuple[TestClient, _RepositorioContasDublê],
) -> None:
    cliente, _dublê = cliente_e_repositorio
    cliente.post("/_teste/login", params={"conta_id": "CONTA_ALUNO"})

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 403
    assert resposta.status_code != 404


def test_conta_inexistente_na_sessao_tambem_recebe_403(
    cliente_e_repositorio: tuple[TestClient, _RepositorioContasDublê],
) -> None:
    """Sessão com um `conta_id` que não corresponde a nenhuma conta (dado
    inconsistente, ex.: conta apagada após o login) é tratada como "sem
    papel de revisor" — `403`, mesma disciplina de "ausência de e_revisor",
    nunca um erro interno nem um `404`."""
    cliente, _dublê = cliente_e_repositorio
    cliente.post("/_teste/login", params={"conta_id": "CONTA_QUE_NAO_EXISTE"})

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 403


# ---------------------------------------------------------------------------
# Critério 3 — sessão de conta com e_revisor=True ⇒ acesso concedido.
# ---------------------------------------------------------------------------


def test_conta_revisora_acessa_a_fila(
    aplicacao_e_dublê: tuple[FastAPI, _RepositorioContasDublê],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    aplicacao, _dublê = aplicacao_e_dublê
    _permitir_fila_vazia(aplicacao, tmp_path_factory)
    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# Critério 4 — a guarda consulta o repositório a cada requisição, sem cache.
# ---------------------------------------------------------------------------


def test_guarda_consulta_o_repositorio_a_cada_requisicao_sem_cache(
    aplicacao_e_dublê: tuple[FastAPI, _RepositorioContasDublê],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    aplicacao, dublê = aplicacao_e_dublê
    _permitir_fila_vazia(aplicacao, tmp_path_factory)
    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})

    cliente.get("/api/revisao/fila")
    cliente.get("/api/revisao/fila")
    cliente.get("/api/revisao/fila")

    # Três requisições na MESMA sessão: três consultas reais ao repositório —
    # nenhuma foi respondida por um valor lido/cacheado da sessão.
    assert dublê.chamadas_buscar_por_id == 3


def test_revogar_e_revisor_entre_chamadas_muda_o_resultado_sem_tocar_a_sessao(
    aplicacao_e_dublê: tuple[FastAPI, _RepositorioContasDublê],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Reforço do critério 4 pelo lado do dado: revogar `e_revisor`
    diretamente no "banco" (dublê), sem tocar a sessão, muda o resultado na
    PRÓXIMA requisição — prova que nada do papel ficou cacheado no cookie."""
    aplicacao, dublê = aplicacao_e_dublê
    _permitir_fila_vazia(aplicacao, tmp_path_factory)
    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/login", params={"conta_id": "CONTA_REVISOR"})

    assert cliente.get("/api/revisao/fila").status_code == 200

    # Revoga o papel diretamente no "banco" — a sessão (cookie) não muda.
    dublê._contas["CONTA_REVISOR"] = _conta("CONTA_REVISOR", e_revisor=False)

    assert cliente.get("/api/revisao/fila").status_code == 403


# ---------------------------------------------------------------------------
# Critério 5 — complementa (não substitui) a auditoria de isolamento por
# CASO_ID: prova que a NOVA guarda de papel existe sobre a rota real
# GET /revisao/fila, registrada na aplicação de produção.
# ---------------------------------------------------------------------------


def test_guarda_de_papel_protege_a_rota_real_de_producao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`GET /revisao/fila`, exatamente como registrada em `criar_aplicacao()`
    (sem nenhum router sintético/de exemplo), recusa sem sessão — prova, na
    aplicação REAL, que a guarda foi de fato ligada à rota (não apenas
    declarada em algum módulo sem uso). Este teste é o complemento explícito
    à auditoria de isolamento por `CASO_ID` (`tests/app_aluno/e2e/
    test_mecanismo_isolamento.py`, T-31/T-32): aquela auditoria continua sem
    cobrir `/revisao/*` (rota multi-caso, nunca recebe `CASO_ID`, motivo já
    registrado em T-69) — este teste cobre o que ela não cobre, sem fingir
    substituí-la."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 401


def test_guarda_de_papel_nao_e_a_mesma_dependencia_de_isolamento_por_caso() -> None:
    """`exigir_papel_revisor` é uma dependência DISTINTA de `exigir_caso_
    da_sessao` — a auditoria de isolamento por `CASO_ID` (T-31/T-32)
    reconhece especificamente o nome/módulo de `exigir_caso_da_sessao`
    (`app/http/isolamento.py::dependencia`); `exigir_papel_revisor` não usa
    esse nome e não é, portanto, contabilizada por aquela auditoria — o que
    é correto, pois ela audita um domínio diferente (posse de CASO_ID de
    aluno, não papel de revisor)."""
    from app.http.isolamento import exigir_papel_revisor

    assert exigir_papel_revisor.__name__ != "dependencia"
