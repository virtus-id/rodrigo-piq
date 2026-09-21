"""Isolamento por `CASO_ID` fim-a-fim, com DUAS SESSÕES REAIS — `RF-02`,
`AC-03` (T-32; ampliado por T-64 com a rota real de plano).

**Ângulo deste arquivo, e por que ele não duplica `test_mecanismo_isolamento.py`
(T-31).** T-31 prova a AUDITORIA ESTÁTICA (`rotas_sem_isolamento_por_caso`
percorre `app.routes` e detecta, por introspecção de `dependant`, uma rota
com `CASO_ID` sem a dependência de isolamento) e o comportamento 401/404 com
UMA sessão sobre um router sintético e um dublê de repositório. Este arquivo
cobre o ângulo que falta: o COMPORTAMENTO OBSERVADO fim-a-fim com **duas
sessões reais** (caso A e caso B), cada uma nascida de um cadastro de verdade
via `TestClient` contra `app/http/rotas_conta.py` (T-30) — não um dublê de
sessão, e não uma chamada direta à dependência.

**Atualização de T-64: a rota real de plano substitui o placeholder
`/exemplo-plano`.** Quando este arquivo nasceu (T-32), nenhuma rota real de
plano existia — `/exemplo-plano/{CASO_ID}` era um placeholder nomeado só
para ler como o domínio futuro (ver nota histórica abaixo). T-64 implementou
`GET /caso/{CASO_ID}/plano` (`app/http/rotas_plano.py`) de verdade, protegida
pela MESMA `exigir_caso_da_sessao` — este arquivo agora testa a ROTA REAL
para o ângulo "plano", exatamente como a nota histórica previa
("`test_nenhuma_rota_real_escapa_da_auditoria_de_isolamento` passa a testar
diretamente essas rotas"). Respostas, PDF e fila continuam sem rota real
(Entregas 5b/7/8 restantes) e permanecem cobertas pelos placeholders
`/exemplo-respostas`, `/exemplo-pdf` e `/exemplo-fila` — a MESMA fábrica de
isolamento que a rota real de plano usa.

**Nota histórica da decisão original de T-32 (ainda válida para os
placeholders remanescentes).** Os critérios de aceite de T-32 falam em "toda
rota do caso B: respostas, plano, PDF e fila" — na época, nenhuma dessas
rotas de domínio existia; hoje "plano" já é real (T-64), e as demais seguem
como placeholders nomeados para ler como os domínios futuros, montados com a
MESMA fábrica `exigir_caso_da_sessao` que qualquer rota real terá que usar.

**O que este teste garante hoje vs. o que garantirá quando as rotas de
domínio restantes existirem:**
- HOJE: (1) a auditoria por enumeração de `app.routes` roda sobre a
  aplicação REAL e não acusa nenhuma rota real (a rota real de plano, T-64,
  declara `exigir_caso_da_sessao`, por isso não aparece como violação); (2)
  com duas sessões reais de cadastro, a rota REAL de plano e um cenário
  fim-a-fim sintético para os domínios ainda não implementados (respostas,
  PDF, fila) provam que a sessão do caso A recebe 404 em toda rota do caso
  B, inclusive por `DIVIDA_ID`/`MARGEM_ID`.
- QUANDO as rotas reais de respostas/PDF/fila (Entregas 5b/7/8) forem
  implementadas: os testes parametrizados abaixo passam a apontar para elas
  também (nenhuma rota nova pode ser registrada em `app.routes` com
  `CASO_ID` sem `exigir_caso_da_sessao` — a auditoria falha
  automaticamente, nomeando a rota, no dia em que isso ocorrer).

REGRAS: `RF-02`, `AC-03`
"""

from __future__ import annotations

from typing import Final

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.casos.maquina import Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.rotas_conta import obter_cadastro_conta, obter_repositorio_contas
from persistencia.app_aluno.casos import RepositorioCasos
from tests.app_aluno.e2e.test_mecanismo_isolamento import rotas_sem_isolamento_por_caso
from tests.app_aluno.test_rotas_conta import _CadastroContaDublê, _RepositorioContasDublê

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


# ---------------------------------------------------------------------------
# Critério 1 — enumera app.routes de verdade, sem lista escrita à mão.
# ---------------------------------------------------------------------------


def test_ac03_nenhuma_rota_real_registrada_hoje_escapa_da_auditoria_de_isolamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A auditoria de `rotas_sem_isolamento_por_caso` (mecanismo de T-31)
    roda sobre a aplicação REAL — `criar_aplicacao()`, sem router sintético
    incluído — e não acusa nenhuma violação. Além das rotas sem `CASO_ID`
    (`/saude`, `/conta/cadastro`, `/conta/login`, `/conta/logout`), a
    aplicação real já registra rotas com `CASO_ID` desde T-36/T-42/T-56/T-63
    (consentimento, resposta, cálculo, PDF do plano) — todas declaram
    `exigir_caso_da_sessao`, por isso a auditoria continua vazia. O dia em
    que uma rota nova (com `CASO_ID`) for adicionada sem essa dependência,
    esta mesma chamada passa a devolver o `path` dela e o teste quebra — SEM
    precisar editar este arquivo (`AC-03`, critério "rota nova sem
    isolamento quebra o teste automaticamente")."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    assert rotas_sem_isolamento_por_caso(aplicacao) == []


# ---------------------------------------------------------------------------
# Cenário fim-a-fim sintético — duas sessões reais (caso A e caso B).
#
# As quatro rotas abaixo são NOMEADAS como os domínios futuros que os
# critérios de aceite citam (respostas, plano, e leitura de item repetido
# por DIVIDA_ID/MARGEM_ID) e protegidas pela MESMA dependência real de T-31
# (`exigir_caso_da_sessao`) que as rotas de produto terão que declarar — a
# prova de comportamento, não a implementação de produto.
# ---------------------------------------------------------------------------


class _RepositorioCasosDeSessaoReal(RepositorioCasos):
    """Dublê de `RepositorioCasos` que respeita a POSSE real registrada no
    cadastro: cada `CASO_ID` criado por `/conta/cadastro` (via
    `_CadastroContaDublê`) pertence exatamente à `conta_id` que o cadastrou.
    Ao contrário do dublê de `test_mecanismo_isolamento.py` (posse fixada à
    mão), este lê a posse do MESMO dublê de cadastro usado pelas sessões
    reais — para que "sessão do caso A" e "caso A" sejam, de fato, o produto
    de um cadastro real, não dois literais combinando por coincidência."""

    def __init__(self, cadastro: _CadastroContaDublê) -> None:
        self._cadastro = cadastro

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._cadastro.casos.get(caso_id)

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        caso = self._cadastro.casos.get(caso_id)
        return caso is not None and caso.conta_id == conta_id

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


def _incluir_rotas_de_exemplo_de_dominio_futuro(aplicacao) -> None:  # type: ignore[no-untyped-def]
    """Registra, na aplicação de teste, as rotas placeholder que representam
    — pelo NOME, não pela implementação — os domínios futuros ainda não
    implementados: respostas, PDF, fila, e item repetido por
    `DIVIDA_ID`/`MARGEM_ID`. "Plano" NÃO é mais um placeholder aqui — a rota
    real `GET /caso/{CASO_ID}/plano` (`app/http/rotas_plano.py`, T-64) já
    está registrada por `criar_aplicacao()` e é testada diretamente, com o
    caminho `/caso/{CASO_ID}/plano` em vez de `/exemplo-plano/{CASO_ID}`.
    Todas as rotas abaixo declaram `exigir_caso_da_sessao`, o mecanismo real
    de T-31."""
    roteador = APIRouter()

    @roteador.get("/exemplo-respostas/{CASO_ID}")
    def respostas_do_caso(
        CASO_ID: str = Depends(exigir_caso_da_sessao("CASO_ID")),
    ) -> dict[str, str]:
        return {"CASO_ID": CASO_ID, "recurso": "respostas"}

    @roteador.get("/exemplo-pdf/{CASO_ID}")
    def pdf_do_caso(
        CASO_ID: str = Depends(exigir_caso_da_sessao("CASO_ID")),
    ) -> dict[str, str]:
        return {"CASO_ID": CASO_ID, "recurso": "pdf"}

    @roteador.get("/exemplo-fila/{CASO_ID}")
    def fila_do_caso(
        CASO_ID: str = Depends(exigir_caso_da_sessao("CASO_ID")),
    ) -> dict[str, str]:
        return {"CASO_ID": CASO_ID, "recurso": "fila"}

    # Leitura de item repetido por DIVIDA_ID e por MARGEM_ID — a mesma
    # fábrica, parametrizada com o nome do parâmetro da própria rota.
    @roteador.get("/exemplo-item-repetido/{DIVIDA_ID}")
    def divida_do_caso(
        DIVIDA_ID: str = Depends(exigir_caso_da_sessao("DIVIDA_ID")),
    ) -> dict[str, str]:
        return {"DIVIDA_ID": DIVIDA_ID, "recurso": "divida"}

    @roteador.get("/exemplo-item-margem/{MARGEM_ID}")
    def margem_do_caso(
        MARGEM_ID: str = Depends(exigir_caso_da_sessao("MARGEM_ID")),
    ) -> dict[str, str]:
        return {"MARGEM_ID": MARGEM_ID, "recurso": "margem"}

    aplicacao.include_router(roteador)


@pytest.fixture
def duas_sessoes_reais_caso_a_e_caso_b(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, TestClient, str, str]:
    """Monta a aplicação real (`criar_aplicacao()`) com as rotas de exemplo
    de domínio futuro incluídas, e abre DUAS SESSÕES REAIS por cadastro de
    verdade via `/conta/cadastro` (T-30) — `TestClient` distintos para caso A
    e caso B, cada um com seu próprio cookie de sessão assinado, exatamente
    como dois alunos em navegadores diferentes.

    Devolve `(cliente_a, cliente_b, caso_id_a, caso_id_b)`."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    cadastro_dublê = _CadastroContaDublê()
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_cadastro_conta] = lambda: cadastro_dublê
    aplicacao.dependency_overrides[obter_repositorio_contas] = lambda: (
        _RepositorioContasDublê(cadastro_dublê)
    )
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: (
        _RepositorioCasosDeSessaoReal(cadastro_dublê)
    )
    _incluir_rotas_de_exemplo_de_dominio_futuro(aplicacao)

    cliente_a = TestClient(aplicacao, base_url="https://teste.local")
    cliente_b = TestClient(aplicacao, base_url="https://teste.local")

    cliente_a.post(
        "/api/conta/cadastro", data={"email": "caso-a@teste.invalido", "senha": "senhaForte123"}
    )
    cliente_b.post(
        "/api/conta/cadastro", data={"email": "caso-b@teste.invalido", "senha": "senhaForte123"}
    )

    # O cadastro cria exatamente um caso por conta (T-30, critério 1) — o
    # dublê de cadastro é a única fonte dos CASO_ID reais desta fixture.
    caso_id_a = _caso_id_da_conta(cadastro_dublê, "caso-a@teste.invalido")
    caso_id_b = _caso_id_da_conta(cadastro_dublê, "caso-b@teste.invalido")

    return cliente_a, cliente_b, caso_id_a, caso_id_b


def _caso_id_da_conta(cadastro_dublê: _CadastroContaDublê, email: str) -> str:
    conta_id = next(c.conta_id for c in cadastro_dublê.contas.values() if c.email == email)
    caso_id = next(
        caso_id for caso_id, caso in cadastro_dublê.casos.items() if caso.conta_id == conta_id
    )
    return caso_id


# ---------------------------------------------------------------------------
# Critério 2 — sessão do caso A recebe 404 em toda rota do caso B:
# respostas, plano, PDF e fila (via rotas de exemplo nomeadas como os
# domínios futuros — ver nota do módulo sobre a tensão de escopo).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caminho_do_recurso",
    ["/exemplo-respostas", "/exemplo-pdf", "/exemplo-fila"],
)
def test_ac03_sessao_do_caso_a_recebe_404_em_toda_rota_do_caso_b(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
    caminho_do_recurso: str,
) -> None:
    cliente_a, _cliente_b, _caso_id_a, caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"{caminho_do_recurso}/{caso_id_b}")

    assert resposta.status_code == 404


@pytest.mark.parametrize(
    "caminho_do_recurso",
    ["/exemplo-respostas", "/exemplo-pdf", "/exemplo-fila"],
)
def test_ac03_sessao_do_caso_a_acessa_normalmente_sua_propria_rota(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
    caminho_do_recurso: str,
) -> None:
    """Contraprova: a mesma sessão, sobre o PRÓPRIO caso, é aceita — a 404
    do teste anterior é isolamento, não uma rota quebrada."""
    cliente_a, _cliente_b, caso_id_a, _caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"{caminho_do_recurso}/{caso_id_a}")

    assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# Critério 2 (T-64) — a rota REAL de plano (`GET /caso/{CASO_ID}/plano`,
# `app/http/rotas_plano.py`) segue a mesma garantia, testada diretamente em
# vez de via placeholder: sessão do caso A recebe 404 no plano do caso B, e
# acessa normalmente o próprio (o caso recém-cadastrado não tem snapshot
# liberado, então a resposta é 200 com `plano: null` e o estado do caso
# (T-145: a tela é React), não 404 —
# a distinção entre "isolamento" e "sem snapshot liberado" é exatamente o
# que este par de testes prova).
# ---------------------------------------------------------------------------


def test_ac03_sessao_do_caso_a_recebe_404_no_plano_real_do_caso_b(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
) -> None:
    cliente_a, _cliente_b, _caso_id_a, caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"/caso/{caso_id_b}/api/plano")

    assert resposta.status_code == 404


def test_ac03_sessao_do_caso_a_acessa_normalmente_o_plano_real_do_proprio_caso(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
) -> None:
    """Contraprova: a mesma sessão, sobre o PRÓPRIO caso, é aceita — a 404
    do teste anterior é isolamento, não uma rota quebrada. O caso recém
    cadastrado não tem snapshot liberado (`CADASTRADO`, `T-64`/`AC-25`), por
    isso a resposta é `200` com a tela de estado do caso, nunca `404`."""
    cliente_a, _cliente_b, caso_id_a, _caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"/caso/{caso_id_a}/api/plano")

    assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# Critério 3 — cobre também rotas de leitura de item repetido por
# DIVIDA_ID/MARGEM_ID.
# ---------------------------------------------------------------------------


def test_ac03_sessao_do_caso_a_recebe_404_ao_ler_divida_pelo_caso_id_do_caso_b(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
) -> None:
    cliente_a, _cliente_b, _caso_id_a, caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"/exemplo-item-repetido/{caso_id_b}")

    assert resposta.status_code == 404


def test_ac03_sessao_do_caso_a_recebe_404_ao_ler_margem_pelo_caso_id_do_caso_b(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
) -> None:
    cliente_a, _cliente_b, _caso_id_a, caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    resposta = cliente_a.get(f"/exemplo-item-margem/{caso_id_b}")

    assert resposta.status_code == 404


def test_ac03_sessao_do_caso_b_recebe_404_em_toda_rota_do_caso_a_reciproca(
    duas_sessoes_reais_caso_a_e_caso_b: tuple[TestClient, TestClient, str, str],
) -> None:
    """A garantia é simétrica: B também não alcança nada de A — não é um
    efeito colateral de qual sessão foi criada primeiro."""
    _cliente_a, cliente_b, caso_id_a, _caso_id_b = duas_sessoes_reais_caso_a_e_caso_b

    assert cliente_b.get(f"/exemplo-respostas/{caso_id_a}").status_code == 404
    assert cliente_b.get(f"/caso/{caso_id_a}/api/plano").status_code == 404
    assert cliente_b.get(f"/exemplo-pdf/{caso_id_a}").status_code == 404
    assert cliente_b.get(f"/exemplo-fila/{caso_id_a}").status_code == 404
    assert cliente_b.get(f"/exemplo-item-repetido/{caso_id_a}").status_code == 404
    assert cliente_b.get(f"/exemplo-item-margem/{caso_id_a}").status_code == 404
