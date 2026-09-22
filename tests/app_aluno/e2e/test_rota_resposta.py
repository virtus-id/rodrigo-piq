"""`POST /caso/{CASO_ID}/resposta` fim-a-fim — os sete passos do plano
`plans/app-aluno.plan.md` §5.1 (`RF-05`, `RF-07`, `RF-10`, `RF-11`, `RF-13`,
`AC-02`, `EC-01`, `EC-02`, `EC-05`, T-42).

Cobre os cinco critérios de aceite da tarefa, cada um contra Postgres real
(`requer_banco`, pulado com mensagem explícita sem `DATABASE_URL`, hook de
`tests/app_aluno/conftest.py`), com um caso nascido de um fluxo HTTP real
(cadastro T-30 → consentimento T-36 → `inicia_coleta` disparada diretamente
sobre o repositório, mesmo ângulo já usado por `tests/app_aluno/test_rotas_
consentimento.py`/T-37 para a transição que ainda não tem rota própria):

1. `AC-02`: a resposta está persistida ANTES de a rota devolver a resposta
   HTTP — provado por uma NOVA consulta ao repositório, sem reaproveitar
   nenhum estado da chamada HTTP, imediatamente após o `TestClient.post`
   retornar (mesmo ângulo de `tests/app_aluno/integracao/
   test_persistencia_app_aluno.py::test_ac02_...`, agora atrás da rota).
2. Responder pergunta cuja condição de exibição é falsa é recusado (`400`),
   sem gravação — usa `B3.S06A`, real, condicionada a
   `VINCULO_CONSIGNAVEL != NAO`.
3. `NAO_SEI` grava sem passar pela conversão decimal — usa `B3.S06B`
   (`MOEDA`), com `nao_sei=on`; se a rota tentasse converter, uma string
   vazia seria recusada por `EC-01` e o teste falharia por status errado.
4. `EC-01`/`EC-02` recusam sem gravar, com a mensagem apontando o(s)
   campo(s): `EC-01` sobre `B3.S06B` (`MOEDA`) com entrada não numérica;
   `EC-02` sobre `B3.S06B`/`B3.S06C` (validação cruzada normativa
   `VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`, real, por `MARGEM_ID`).
5. `EC-05`: falha de banco devolve a mensagem fixa de falha de gravação e a
   linha nunca chega a existir — via `app.dependency_overrides` sobre
   `obter_repositorio_respostas`, com um dublê que sempre levanta
   `ErroGravacaoResposta` (mesmo padrão de dublê de `EC-05` já usado por
   T-22/T-25 no nível do repositório, aqui reaproveitado no nível da rota
   para provar que a rota REAGE corretamente à falha, sem reimplementar o
   cenário de conexão indisponível já coberto por T-25).

REGRAS: `RF-05`, `RF-07`, `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-01`,
`EC-02`, `EC-05`
"""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.consentimento.registro import TextoConsentimento
from app.http.aplicacao import criar_aplicacao
from app.http.rotas_coleta import obter_repositorio_respostas
from collection.respostas import Resposta
from persistencia.app_aluno.casos import RepositorioCasosSupabase
from persistencia.app_aluno.respostas import (
    ErroGravacaoResposta,
    RepositorioRespostasSupabase,
)
from persistencia.supabase.conexao import obter_database_url

pytestmark = pytest.mark.requer_banco

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


@pytest.fixture
def diretorio_textos_fabricado(tmp_path: Path) -> Path:
    """Mesmo papel da fixture homônima de `test_rotas_consentimento.py`/
    `test_consentimento.py` (T-37): um `.yaml` de texto de consentimento
    FABRICADO só para exercitar o mecanismo de carga, nunca a redação real
    de `PEND-01`."""
    (tmp_path / "v1.yaml").write_text(
        "QUESTIONARIO_VERSION: 'T42-1.0.0'\ntitulo: fabricado\ncorpo: fabricado\n",
        encoding="utf-8",
    )
    return tmp_path


def _carregar_texto_fabricado(diretorio: Path) -> TextoConsentimento:
    from app.consentimento.registro import carregar_texto_vigente as original

    return original(diretorio)


@pytest.fixture
def aplicacao_real(
    monkeypatch: pytest.MonkeyPatch, diretorio_textos_fabricado: Path
) -> FastAPI:
    """A `FastAPI` de produção, sem `dependency_overrides` de isolamento/
    repositório de casos/consentimento — cadastro e consentimento correm
    pelo caminho de produção contra o Postgres de `DATABASE_URL`, mesmo
    padrão de `test_consentimento.py::cliente_http_real` (T-37). A coleção
    de registros também é a REAL (`collection/carga.py::
    carregar_registros()`, sem override), para exercitar `B3.S06A`/`B3.S06B`/
    `B3.S06C` como o questionário de verdade os declara. Exposta separada do
    `TestClient` para que o teste de `EC-05` possa aplicar seu próprio
    `dependency_overrides` sobre a MESMA instância antes de instanciar o
    cliente (mesmo padrão de `tests/app_aluno/test_rotas_conta.py::cliente`)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setattr(
        "app.http.rotas_consentimento.carregar_texto_vigente",
        lambda diretorio=None: _carregar_texto_fabricado(diretorio_textos_fabricado),
    )
    return criar_aplicacao()


@pytest.fixture
def cliente_http_real(aplicacao_real: FastAPI) -> TestClient:
    """`TestClient` sobre `aplicacao_real`, sem nenhum override — o caminho
    de produção completo para os quatro primeiros critérios de aceite."""
    return TestClient(aplicacao_real, base_url="https://teste.local")


def _database_url() -> str:
    return obter_database_url()


def _caso_pronto_para_coleta(cliente_http_real: TestClient) -> str:
    """Cadastro real (T-30) + consentimento real (T-36) + `inicia_coleta`
    disparada diretamente sobre o repositório (a mesma transição ainda sem
    rota HTTP própria, T-42/T-45) — devolve o `CASO_ID` já em
    `COLETA_INICIAL`, pronto para receber respostas por esta rota."""
    email = f"t42-{uuid.uuid4().hex}@teste.invalido"
    resposta_cadastro = cliente_http_real.post(
        "/api/conta/cadastro", data={"email": email, "senha": "senha-de-teste-t42"}
    )
    assert resposta_cadastro.status_code == 201  # `201 Created` (T-144)

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            'SELECT "CASO_ID" FROM app_aluno.casos WHERE conta_id = ('
            "SELECT conta_id FROM app_aluno.contas WHERE email = %s)",
            (email,),
        )
        (caso_id,) = cursor.fetchone()  # type: ignore[misc]

    resposta_consentimento = cliente_http_real.post(
        f"/caso/{caso_id}/consentimento", data={"aceite": "on"}
    )
    assert resposta_consentimento.status_code == 200

    RepositorioCasosSupabase().transicionar_estado(caso_id, ESTADO_CASO.COLETA_INICIAL)
    return str(caso_id)


def _total_de_respostas(caso_id: str, id_pergunta: str | None = None) -> int:
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        if id_pergunta is None:
            cursor.execute(
                'SELECT count(*) FROM app_aluno.respostas WHERE "CASO_ID" = %s',
                (caso_id,),
            )
        else:
            cursor.execute(
                'SELECT count(*) FROM app_aluno.respostas '
                'WHERE "CASO_ID" = %s AND "ID_PERGUNTA" = %s',
                (caso_id, id_pergunta),
            )
        (total,) = cursor.fetchone()  # type: ignore[misc]
        return int(total)


# ---------------------------------------------------------------------------
# AC-02 — a resposta está persistida ANTES de a rota devolver a resposta
# HTTP: encerrar o processo imediatamente depois não perde a resposta.
# ---------------------------------------------------------------------------


def test_ac02_resposta_persistida_antes_do_retorno_http(cliente_http_real: TestClient) -> None:
    """Grava `B1.01` (SELECAO_UNICA, sempre aberta, sem validação cruzada) e,
    com uma NOVA consulta via repositório (instância nova, sem reaproveitar
    nada da chamada HTTP), confirma que o valor já está no banco — a leitura
    ocorre DEPOIS do `TestClient.post` já ter retornado, provando que o
    commit aconteceu antes da resposta HTTP chegar ao cliente."""
    caso_id = _caso_pronto_para_coleta(cliente_http_real)

    resposta = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B1.01", "valor": "ESTABELECIDO"},
    )
    assert resposta.status_code == 200

    leitura_nova = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    valores = {r.ID_PERGUNTA: r.valor for r in leitura_nova}
    # B1.01 real declara VARIAVEL_GRAVADA=PACTO — a chave gravada é a
    # variável, não o ID do registro (ver app/http/rotas_coleta.py,
    # ErroRegistroSemVariavelGravada).
    assert valores.get("PACTO") == "ESTABELECIDO", (
        "AC-02: a resposta deveria estar legível do banco imediatamente após "
        f"a rota retornar; valores gravados: {valores}"
    )


# ---------------------------------------------------------------------------
# Responder pergunta cuja condição de exibição é falsa é recusado, sem
# gravação.
# ---------------------------------------------------------------------------


def test_pergunta_com_condicao_de_exibicao_falsa_e_recusada_sem_gravacao(
    cliente_http_real: TestClient,
) -> None:
    """`B3.S06A` real só está aberta quando `VINCULO_CONSIGNAVEL != NAO`
    (`condicao_exibicao: {tipo: NAO, termo: {tipo: IGUAL, ...}}`). Sem
    nenhuma resposta prévia de `VINCULO_CONSIGNAVEL`, a condição avalia como
    falsa (variável ausente ⇒ `avaliar` devolve falso para `CondicaoIgual`,
    logo `CondicaoNao` do falso é verdadeiro... — usamos aqui o caso em que
    `VINCULO_CONSIGNAVEL=NAO` é respondido antes, fechando explicitamente a
    condição, para testar exatamente a recusa, não a ambiguidade da
    ausência)."""
    caso_id = _caso_pronto_para_coleta(cliente_http_real)

    # Fecha a condição explicitamente: B3.S01 grava VINCULO_CONSIGNAVEL=NAO,
    # o que faz CondicaoNao(CondicaoIgual(VINCULO_CONSIGNAVEL, NAO)) avaliar
    # falso — B3.S06A não está aberta.
    resposta_fechamento = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S01", "valor": "NAO"},
    )
    assert resposta_fechamento.status_code == 200

    resposta = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S06A", "valor": "EMPRESTIMO"},
    )
    assert resposta.status_code == 400
    assert _total_de_respostas(caso_id, "TIPO_MARGEM") == 0


# ---------------------------------------------------------------------------
# NAO_SEI grava sem passar pela conversão decimal.
# ---------------------------------------------------------------------------


def test_nao_sei_grava_sem_passar_pela_conversao_decimal(cliente_http_real: TestClient) -> None:
    """`B3.S06B` é `MOEDA` — se a rota tentasse converter antes de checar
    `nao_sei`, uma string vazia de `valor` seria recusada por `EC-01`
    (`ErroConversaoInvalida`) e a resposta HTTP seria `400`, não `200`. O
    `200` aqui, combinado com a leitura de `NAO_SEI` de volta, prova que o
    passo 3 (NAO_SEI pula a conversão) roda antes do passo 4."""
    caso_id = _caso_pronto_para_coleta(cliente_http_real)

    resposta = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S06B", "item_id": "M001", "nao_sei": "on"},
    )
    assert resposta.status_code == 200

    leitura = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    from collection.respostas import NAO_SEI

    valores_margem = {
        (r.ID_PERGUNTA, r.item_id): r.valor for r in leitura if r.item_id == "M001"
    }
    assert valores_margem.get(("VALOR_TOTAL_MARGEM", "M001")) is NAO_SEI


# ---------------------------------------------------------------------------
# EC-01 — conversão decimal inválida recusa sem gravar, apontando o campo.
# ---------------------------------------------------------------------------


def test_ec01_entrada_monetaria_invalida_recusa_sem_gravar_apontando_o_campo(
    cliente_http_real: TestClient,
) -> None:
    """`B3.S06B` (`MOEDA`) com `"mil reais"` — `app/montagem/conversao.py`
    recusa (`EC-01`) antes de qualquer gravação; a mensagem devolvida cita a
    variável do campo (`VALOR_TOTAL_MARGEM`)."""
    caso_id = _caso_pronto_para_coleta(cliente_http_real)

    resposta = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S06B", "item_id": "M002", "valor": "mil reais"},
    )

    assert resposta.status_code == 400
    assert "VALOR_TOTAL_MARGEM" in resposta.text
    assert _total_de_respostas(caso_id, "VALOR_TOTAL_MARGEM") == 0


# ---------------------------------------------------------------------------
# EC-02 — validação cruzada falha recusa sem gravar, apontando os DOIS
# campos.
# ---------------------------------------------------------------------------


def test_ec02_validacao_cruzada_falha_recusa_sem_gravar_apontando_os_dois_campos(
    cliente_http_real: TestClient,
) -> None:
    """`VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`, validação cruzada
    normativa real de `B3.S06B`/`B3.S06C`, por `MARGEM_ID`: grava
    `VALOR_TOTAL_MARGEM=1000` primeiro, depois tenta
    `VALOR_UTILIZADO_MARGEM=1200` no MESMO item — a segunda gravação é
    recusada (`EC-02`), com a mensagem do próprio registro, e NENHUMA das
    duas variáveis fica com o valor da tentativa recusada."""
    caso_id = _caso_pronto_para_coleta(cliente_http_real)
    item_id = "M003"

    resposta_total = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S06B", "item_id": item_id, "valor": "1000,00"},
    )
    assert resposta_total.status_code == 200

    resposta_utilizado = cliente_http_real.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B3.S06C", "item_id": item_id, "valor": "1200,00"},
    )

    assert resposta_utilizado.status_code == 400
    assert "VALOR_UTILIZADO_MARGEM" in resposta_utilizado.text
    assert "VALOR_TOTAL_MARGEM" in resposta_utilizado.text
    # A resposta recusada nunca chegou a ser gravada — só a primeira
    # (VALOR_TOTAL_MARGEM=1000) está no banco para este item.
    assert _total_de_respostas(caso_id, "VALOR_UTILIZADO_MARGEM") == 0


# ---------------------------------------------------------------------------
# EC-05 — falha de banco devolve "Não foi possível salvar." e NÃO avança.
# ---------------------------------------------------------------------------


class _RepositorioRespostasSempreFalha:
    """Dublê que simula `EC-05` no nível da rota: qualquer `gravar` levanta
    `ErroGravacaoResposta`, como uma falha de commit real faria — mas sem
    depender de derrubar a conexão de banco (já coberto no nível do
    repositório por `tests/app_aluno/integracao/
    test_persistencia_app_aluno.py::test_ec05_...`, T-25). `listar_do_caso`
    delega ao repositório real, para que os passos 2/5 (que leem o estado
    atual do caso) continuem funcionando normalmente até a gravação."""

    def __init__(self) -> None:
        self._real = RepositorioRespostasSupabase()

    def gravar(self, resposta: Resposta) -> None:
        raise ErroGravacaoResposta("EC-05: falha simulada de gravação para o teste da rota")

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return self._real.listar_do_caso(caso_id)


def test_ec05_falha_de_gravacao_devolve_mensagem_fixa_e_nao_grava(
    aplicacao_real: FastAPI,
) -> None:
    """Com o repositório de respostas substituído por um dublê que sempre
    falha (`app.dependency_overrides`, aplicado na MESMA `FastAPI` antes de
    o `TestClient` ser criado — mesmo padrão de `tests/app_aluno/
    test_rotas_conta.py::cliente`), a rota devolve `503` com a mensagem fixa
    "Não foi possível salvar." — e a linha nunca chega a existir no banco
    real (conferido pelo repositório real, fora do override). O caso é
    preparado por um cliente SEM o override (cadastro/consentimento reais
    não devem falhar), e a chamada que falha usa um cliente separado sobre a
    MESMA `aplicacao_real` já com o override aplicado."""
    cliente = TestClient(aplicacao_real, base_url="https://teste.local")
    caso_id = _caso_pronto_para_coleta(cliente)

    # O override é aplicado DEPOIS de o caso já estar pronto (cadastro e
    # consentimento reais não devem falhar) — mesmo `TestClient`, para
    # preservar o cookie de sessão já aberto pelo cadastro acima.
    aplicacao_real.dependency_overrides[obter_repositorio_respostas] = (
        _RepositorioRespostasSempreFalha
    )
    resposta = cliente.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B1.01", "valor": "ESTABELECIDO"},
    )

    assert resposta.status_code == 503
    assert "Não foi possível salvar." in resposta.text
    assert _total_de_respostas(caso_id) == 0
