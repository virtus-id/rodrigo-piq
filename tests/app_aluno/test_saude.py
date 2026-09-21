"""Testes de `app/http/saude.py` — `RF-10`, `EC-05` (T-94).

**Escopo desta tarefa vs. `T-25`/`T-42`.** `EC-05` já está provado, para a
gravação de resposta, em `tests/app_aluno/integracao/test_persistencia_app_
aluno.py` (T-25, fim a fim) e para a rota de coleta em
`tests/app_aluno/test_rotas_coleta.py` (T-42) — este módulo não repete
aquela prova. Aqui o que se prova é específico do keep-alive: (1) a rota
`GET /saude/banco` responde `200` quando a query mínima tem sucesso e `503`
quando falha, sem jamais reportar sucesso sobre uma falha (mesma disciplina
de `EC-05`); (2) a query de keep-alive é `SELECT 1` puro — nenhuma tabela de
dado do aluno é tocada.

`test_ec05_...` roda sempre, com um dublê de `tocar_banco` (mesmo padrão de
`app/http/rotas_consentimento.py`/`isolamento.py`: dependência sobrescrita
via `app.dependency_overrides`), sem exigir `DATABASE_URL`. Os dois testes
`requer_banco` confirmam contra Postgres real que a query de fato só usa
`SELECT 1`, sem qualquer tabela de `app_aluno`.

REGRAS: RF-10, EC-05
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.http.aplicacao import criar_aplicacao
from app.http.saude import (
    ErroTocarBanco,
    obter_funcao_tocar_banco,
    tocar_banco,
)
from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — teste requer banco real (marcador requer_banco)"

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    return TestClient(aplicacao, base_url="https://teste.local")


# ---------------------------------------------------------------------------
# Comportamento HTTP da rota — dublê de `tocar_banco`, roda sempre.
# ---------------------------------------------------------------------------


def test_saude_banco_devolve_200_quando_a_query_minima_funciona(cliente: TestClient) -> None:
    cliente.app.dependency_overrides[obter_funcao_tocar_banco] = lambda: (lambda: None)  # type: ignore[attr-defined]

    resposta = cliente.get("/saude/banco")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_saude_banco_devolve_503_quando_a_query_minima_falha_ec05(cliente: TestClient) -> None:
    """`EC-05`, aplicado ao keep-alive: banco indisponível nunca é reportado
    como `200` — a rota devolve `503` explícito para o agendador externo."""

    def _tocar_banco_que_falha() -> None:
        raise ErroTocarBanco("dublê de teste: conexão recusada")

    cliente.app.dependency_overrides[obter_funcao_tocar_banco] = (  # type: ignore[attr-defined]
        lambda: _tocar_banco_que_falha
    )

    resposta = cliente.get("/saude/banco")

    assert resposta.status_code == 503
    assert resposta.json()["status"] == "erro"


def test_saude_banco_devolve_503_quando_database_url_ausente(cliente: TestClient) -> None:
    """`EC-05`: `DATABASE_URL` ausente é uma forma de banco indisponível —
    também nunca reportada como sucesso."""

    def _tocar_banco_sem_database_url() -> None:
        raise ErroConexaoAusente("dublê de teste: DATABASE_URL ausente")

    cliente.app.dependency_overrides[obter_funcao_tocar_banco] = (  # type: ignore[attr-defined]
        lambda: _tocar_banco_sem_database_url
    )

    resposta = cliente.get("/saude/banco")

    assert resposta.status_code == 503


def test_rota_saude_original_nao_e_afetada(cliente: TestClient) -> None:
    """`/saude` (T-29, liveness) continua respondendo `200` sem tocar banco —
    a rota nova é adicional, não uma substituição."""
    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# A query em si nunca referencia tabela de dado do aluno — auditoria estática.
# ---------------------------------------------------------------------------


def test_tocar_banco_nao_referencia_nenhuma_tabela_de_dado_do_aluno() -> None:
    """Critério de aceite: "o keep-alive não grava nada em tabela de dado do
    aluno". Auditoria por AST sobre `app/http/saude.py`: nenhum literal de
    string FORA DE DOCSTRING (a docstring do módulo cita os nomes das
    tabelas só para EXPLICAR que elas não são tocadas — mesma isenção de
    docstring de `tests/app_aluno/estatica/test_sem_conteudo_de_
    questionario_no_codigo.py`) contém o nome de uma tabela de `app_aluno`
    (`contas`, `casos`, `respostas`, `itens_repetidos`, `revisoes`,
    `consentimentos`, `eventos_caso`) nem um verbo de mutação SQL
    (`INSERT`/`UPDATE`/`DELETE`). A única string de query tolerada é
    `SELECT 1` (mais variações triviais de espaço), sem `FROM` nenhum."""
    codigo_fonte = Path("app/http/saude.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)
    docstrings = {ast.get_docstring(arvore, clean=False) or ""}
    for no_interno in ast.walk(arvore):
        if isinstance(no_interno, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstrings.add(ast.get_docstring(no_interno, clean=False) or "")

    tabelas_de_dado_do_aluno = (
        "contas",
        "casos",
        "respostas",
        "itens_repetidos",
        "revisoes",
        "consentimentos",
        "eventos_caso",
    )
    verbos_de_mutacao = ("insert", "update", "delete")

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        if no.value in docstrings:
            continue  # docstring de módulo/função: cita as tabelas para EXPLICAR que não as toca
        texto = no.value.lower()
        for tabela in tabelas_de_dado_do_aluno:
            assert tabela not in texto, (
                f"literal referencia tabela de dado do aluno {tabela!r}: {no.value!r}"
            )
        for verbo in verbos_de_mutacao:
            assert verbo not in texto, f"literal contém verbo de mutação {verbo!r}: {no.value!r}"


# ---------------------------------------------------------------------------
# Contra Postgres real — a query mínima de fato funciona e não lê dado algum.
# ---------------------------------------------------------------------------


@pytest.mark.requer_banco
def test_tocar_banco_tem_sucesso_contra_postgres_real() -> None:
    """`tocar_banco()` não levanta exceção contra um Postgres real e
    acessível — prova que a query mínima (`SELECT 1`) de fato executa."""
    tocar_banco()


@pytest.mark.requer_banco
def test_saude_banco_devolve_200_contra_postgres_real(cliente: TestClient) -> None:
    """Fim a fim: com `DATABASE_URL` real e acessível, `GET /saude/banco`
    devolve `200` sem dublê nenhum — a dependência real (`tocar_banco`) é
    usada, não a sobrescrita de teste."""
    resposta = cliente.get("/saude/banco")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_ec05_banco_indisponivel_tocar_banco_propaga_erro_e_nunca_finge_sucesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-05`, cenário fim a fim de indisponibilidade: `DATABASE_URL` aponta
    para uma porta que não responde — mesmo padrão de `tests/app_aluno/
    integracao/test_persistencia_app_aluno.py::
    test_ec05_banco_indisponivel_gravacao_levanta_erro_e_nada_e_reportado_
    salvo`. `tocar_banco()` deve propagar exceção, nunca retornar
    silenciosamente. Não exige `DATABASE_URL` real — roda sempre."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:1/piq_inexistente"
    )
    monkeypatch.setenv("PGCONNECT_TIMEOUT", "2")

    with pytest.raises((ErroTocarBanco, psycopg.OperationalError)):
        tocar_banco()


def test_obter_database_url_e_reaproveitado_sem_search_path_proprio() -> None:
    """Reforço de que `saude.py` não define um schema próprio: nenhum
    `cursor.execute(...)` do módulo contém `SET search_path` (a docstring
    MENCIONA o termo só para explicar a ausência dele — por isso a
    comparação é feita sobre as chamadas de `execute`, não sobre o arquivo
    inteiro), e a única dependência de config é `obter_database_url`/
    `ErroConexaoAusente` — os mesmos de `persistencia.supabase.conexao`,
    módulo congelado (`AC-44`), reaproveitados sem modificação."""
    codigo_fonte = Path("app/http/saude.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)

    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "execute"
        ):
            for argumento in no.args:
                if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
                    assert "search_path" not in argumento.value.lower()

    assert obter_database_url.__module__ == "persistencia.supabase.conexao"
