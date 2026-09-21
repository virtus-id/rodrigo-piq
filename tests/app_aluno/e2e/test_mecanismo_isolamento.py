"""Prova prospectiva do mecanismo de isolamento por `CASO_ID` — `RF-02`,
`AC-03` (T-31).

Hoje NENHUMA rota real desta feature recebe `CASO_ID` como path/query
parameter (as rotas de coleta, plano e revisão só chegam na Entrega 5+). Os
quatro critérios de aceite de T-31 são cobertos aqui com um **router de
exemplo sintético**, declarado inline neste teste:

1. "toda rota que recebe `CASO_ID` declara a dependência de isolamento" —
   auditado por `rotas_sem_isolamento_por_caso`, que ENUMERA `app.routes`
   (nunca uma lista escrita à mão) e prova, com um caso proposital SEM a
   dependência, que a auditoria de fato falha ao detectá-lo. Esta função é
   o mesmo mecanismo que `tests/app_aluno/e2e/test_isolamento_por_caso.py`
   (T-32, futura) vai aplicar às rotas reais quando elas existirem — a
   tarefa aqui só prova que o mecanismo funciona, sem implementar rotas
   novas de produto.
2. caso de outra conta ⇒ `404`, nunca `403`.
3. a verificação consulta o banco a cada requisição — dublê de
   `RepositorioCasos` conta chamadas, sem cache em sessão.
4. sem sessão ⇒ recusada antes de qualquer leitura de dado do caso — o
   dublê de repositório nunca é consultado neste caminho.

REGRAS: `RF-02`, `AC-03`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.sessao import iniciar_sessao_conta
from persistencia.app_aluno.casos import Caso, RepositorioCasos

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"

# Nome canônico do path parameter usado pelas rotas de exemplo — literalmente
# "CASO_ID", o nome da spec (sdd.config.md §7): é este texto (normalizado
# para maiúsculas) que a auditoria de `rotas_sem_isolamento_por_caso`
# reconhece como "esta rota recebe um CASO_ID".
_NOME_PARAMETRO_CASO_ID: Final[str] = "CASO_ID"


class _RepositorioCasosDublê(RepositorioCasos):
    """Dublê em memória — cada chamada a `pertence_a_conta` é contada, para
    provar o critério 3 (consulta a cada requisição, sem cache)."""

    def __init__(self, posse: dict[str, str]) -> None:
        self._posse = posse  # CASO_ID -> conta_id dono
        self.chamadas_pertence_a_conta = 0

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        self.chamadas_pertence_a_conta += 1
        return self._posse.get(caso_id) == conta_id

    def transicionar_estado(self, caso_id, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def transicionar_estado_se(self, caso_id, estado_esperado, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui (T-56)

    def registrar_interacao(self, caso_id, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id, snapshot_raiz_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_liberado(self, caso_id, snapshot_liberado_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def listar_por_estado(self, estado):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui (T-69)

    def listar_todos(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui (T-102)


def _rotas_api_achatadas(rotas: Sequence[BaseRoute]) -> list[APIRoute]:
    """Achata `app.routes`, descendo em `_IncludedRouter` (a representação
    lazy do FastAPI para roteadores incluídos via `include_router`) —
    percorre a árvore REAL de rotas registradas, nunca uma lista à mão."""
    achatadas: list[APIRoute] = []
    for rota in rotas:
        if type(rota).__name__ == "_IncludedRouter":
            achatadas.extend(_rotas_api_achatadas(rota.original_router.routes))  # type: ignore[attr-defined]
        elif isinstance(rota, APIRoute):
            achatadas.append(rota)
    return achatadas


def rotas_sem_isolamento_por_caso(aplicacao: FastAPI) -> list[str]:
    """O MECANISMO DE AUDITORIA reutilizável (critério 1). Enumera toda
    `APIRoute` registrada em `aplicacao.routes` e, para cada uma, percorre a
    árvore de dependências (`dependant.dependencies`, recursivamente)
    procurando um path/query parameter cujo nome normalizado seja
    `CASO_ID`.

    A prova de que a checagem é real (não cosmética): quando a dependência
    de `exigir_caso_da_sessao` está presente, o parâmetro `CASO_ID` some do
    `path_params`/`query_params` do `dependant` DA PRÓPRIA ROTA e passa a
    aparecer no `dependant` da SUBDEPENDÊNCIA (a função interna que a
    fábrica devolve) — é essa migração que prova que a dependência
    efetivamente consome o parâmetro. Se `CASO_ID` aparece em QUALQUER
    dependant que não seja produzido por `exigir_caso_da_sessao`
    (reconhecido pelo nome interno `dependencia`, único produzido pela
    fábrica), a rota está desprotegida.

    Devolve a lista de `path`s de rota SEM a dependência — vazia significa
    "toda rota que recebe CASO_ID declara o isolamento"."""
    violacoes: list[str] = []
    for rota in _rotas_api_achatadas(aplicacao.routes):
        if _dependant_tem_caso_id_sem_isolamento(rota.dependant):
            violacoes.append(rota.path)
    return violacoes


def _dependant_tem_caso_id_sem_isolamento(dependant: object) -> bool:
    nomes_no_dependant = {
        parametro.name.upper()
        for parametro in [*dependant.path_params, *dependant.query_params]  # type: ignore[attr-defined]
    }
    se_e_a_propria_dependencia_de_isolamento = (
        getattr(dependant.call, "__name__", "") == "dependencia"  # type: ignore[attr-defined]
        and getattr(dependant.call, "__module__", "") == "app.http.isolamento"  # type: ignore[attr-defined]
    )
    tem_caso_id = _NOME_PARAMETRO_CASO_ID in nomes_no_dependant
    if tem_caso_id and not se_e_a_propria_dependencia_de_isolamento:
        return True
    return any(
        _dependant_tem_caso_id_sem_isolamento(sub)
        for sub in dependant.dependencies  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------------------------
# Critério 1 — toda rota que recebe CASO_ID declara a dependência.
# ---------------------------------------------------------------------------


def test_mecanismo_detecta_rota_protegida_como_conforme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma rota de exemplo que DECLARA `exigir_caso_da_sessao` não aparece
    na lista de violações."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    roteador = APIRouter()

    @roteador.get("/exemplo-protegido/{CASO_ID}")
    def rota_protegida(
        CASO_ID: str = Depends(exigir_caso_da_sessao(_NOME_PARAMETRO_CASO_ID)),
    ) -> dict[str, str]:
        return {"CASO_ID": CASO_ID}

    aplicacao.include_router(roteador)

    assert "/exemplo-protegido/{CASO_ID}" not in rotas_sem_isolamento_por_caso(aplicacao)


def test_mecanismo_detecta_rota_desprotegida_como_violacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PROVA PROSPECTIVA exigida pela tarefa: um router sintético com uma
    rota que usa `CASO_ID` SEM a dependência de isolamento é detectado pela
    auditoria — prova que o mecanismo que futuras tarefas (coleta, plano,
    revisão) vão reaproveitar de fato funciona, e não é cosmético."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    roteador = APIRouter()

    @roteador.get("/exemplo-desprotegido/{CASO_ID}")
    def rota_desprotegida(CASO_ID: str) -> dict[str, str]:
        # Handler lê o CASO_ID diretamente do path, sem passar pela
        # dependência de isolamento — exatamente o descuido que a auditoria
        # deve pegar.
        return {"CASO_ID": CASO_ID}

    aplicacao.include_router(roteador)

    violacoes = rotas_sem_isolamento_por_caso(aplicacao)

    assert "/exemplo-desprotegido/{CASO_ID}" in violacoes


def test_rotas_reais_de_conta_nao_recebem_caso_id_e_nao_violam_o_mecanismo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As rotas hoje registradas (`app/http/rotas_conta.py`, T-30) não
    recebem `CASO_ID` — não precisam da dependência, e a auditoria não as
    marca como violação (não há falso positivo)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    assert rotas_sem_isolamento_por_caso(aplicacao) == []


# ---------------------------------------------------------------------------
# Critério 2 — caso de outra conta devolve 404, nunca 403.
# ---------------------------------------------------------------------------


@pytest.fixture
def cliente_com_rota_de_exemplo(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, _RepositorioCasosDublê]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    roteador = APIRouter()

    @roteador.get("/exemplo/{CASO_ID}")
    def rota_exemplo(
        CASO_ID: str = Depends(exigir_caso_da_sessao(_NOME_PARAMETRO_CASO_ID)),
    ) -> dict[str, str]:
        return {"CASO_ID": CASO_ID}

    aplicacao.include_router(roteador)

    @aplicacao.post("/_teste/login")
    def login(request: Request, conta_id: str) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"status": "ok"}

    dublê = _RepositorioCasosDublê(posse={"CASO_A": "CONTA_1", "CASO_B": "CONTA_2"})
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: dublê

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    return cliente, dublê


def test_caso_de_outra_conta_devolve_404_nao_403(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    cliente, _dublê = cliente_com_rota_de_exemplo
    cliente.post("/_teste/login", params={"conta_id": "CONTA_1"})

    resposta = cliente.get("/exemplo/CASO_B")  # CASO_B pertence a CONTA_2

    assert resposta.status_code == 404


def test_caso_inexistente_devolve_404_identico_ao_de_outra_conta(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    """A existência do caso não vaza: a resposta para 'caso de outra conta'
    e para 'caso inexistente' é byte a byte idêntica."""
    cliente, _dublê = cliente_com_rota_de_exemplo
    cliente.post("/_teste/login", params={"conta_id": "CONTA_1"})

    resposta_outra_conta = cliente.get("/exemplo/CASO_B")
    resposta_inexistente = cliente.get("/exemplo/CASO_NUNCA_EXISTIU")

    assert resposta_outra_conta.status_code == resposta_inexistente.status_code == 404
    assert resposta_outra_conta.text == resposta_inexistente.text


def test_caso_da_propria_conta_e_aceito(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    cliente, _dublê = cliente_com_rota_de_exemplo
    cliente.post("/_teste/login", params={"conta_id": "CONTA_1"})

    resposta = cliente.get("/exemplo/CASO_A")

    assert resposta.status_code == 200
    assert resposta.json() == {"CASO_ID": "CASO_A"}


# ---------------------------------------------------------------------------
# Critério 3 — consulta o banco a cada requisição, sem cache em sessão.
# ---------------------------------------------------------------------------


def test_verificacao_consulta_o_repositorio_a_cada_requisicao_sem_cache(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    cliente, dublê = cliente_com_rota_de_exemplo
    cliente.post("/_teste/login", params={"conta_id": "CONTA_1"})

    cliente.get("/exemplo/CASO_A")
    cliente.get("/exemplo/CASO_A")
    cliente.get("/exemplo/CASO_A")

    # Três requisições ao MESMO caso, na MESMA sessão: três consultas reais
    # ao repositório — nenhuma foi respondida por um valor lido da sessão.
    assert dublê.chamadas_pertence_a_conta == 3


def test_sessao_nao_carrega_nenhum_dado_de_posse_de_caso(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    """Reforço do critério 3 pelo lado da sessão: revogar a posse no
    repositório (sem tocar a sessão) muda o resultado na PRÓXIMA
    requisição — prova que nada ficou cacheado do lado do cliente/sessão."""
    cliente, dublê = cliente_com_rota_de_exemplo
    cliente.post("/_teste/login", params={"conta_id": "CONTA_1"})

    assert cliente.get("/exemplo/CASO_A").status_code == 200

    # Revoga a posse diretamente no "banco" (dublê) — a sessão não muda.
    dublê._posse.pop("CASO_A")

    assert cliente.get("/exemplo/CASO_A").status_code == 404


# ---------------------------------------------------------------------------
# Critério 4 — sem sessão, recusa antes de qualquer leitura de dado do caso.
# ---------------------------------------------------------------------------


def test_sem_sessao_e_recusado_antes_de_qualquer_leitura_do_caso(
    cliente_com_rota_de_exemplo: tuple[TestClient, _RepositorioCasosDublê],
) -> None:
    cliente, dublê = cliente_com_rota_de_exemplo
    # Nenhum login realizado.

    resposta = cliente.get("/exemplo/CASO_A")

    assert resposta.status_code == 401
    # O repositório de casos NUNCA foi consultado — a recusa ocorre antes de
    # qualquer leitura de dado do caso.
    assert dublê.chamadas_pertence_a_conta == 0
