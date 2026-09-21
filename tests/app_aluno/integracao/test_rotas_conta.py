"""Testes de `app/http/rotas_conta.py` contra Postgres real — RF-02, AC-03
(T-30).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`), mesmo padrão de `tests/app_aluno/integracao/
test_persistencia_contas.py` (T-28) e `test_persistencia_casos.py` (T-23).

Cobre o que `tests/app_aluno/test_rotas_conta.py` (dublês em memória) não
pode provar: a transação ÚNICA de `_cadastrar_conta_e_caso_supabase` —
`UNIQUE` real de `email` recusando o `INSERT` de `contas` e, com ele, o
`INSERT` de `casos` na MESMA transação (nenhuma conta órfã sem caso, nenhum
caso órfão sem conta).

REGRAS: RF-02, AC-03
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.http.aplicacao import criar_aplicacao

pytestmark = pytest.mark.requer_banco

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _email_novo() -> str:
    return f"teste-t30-{uuid.uuid4().hex}@teste.invalido"


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    return TestClient(aplicacao, base_url="https://teste.local")


def _contar_contas_por_email(email: str) -> int:
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM app_aluno.contas WHERE email = %s", (email,))
        linha = cursor.fetchone()
        assert linha is not None
        return int(linha[0])


def _contar_casos_por_conta_email(email: str) -> int:
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM app_aluno.casos c
            JOIN app_aluno.contas a ON a.conta_id = c.conta_id
            WHERE a.email = %s
            """,
            (email,),
        )
        linha = cursor.fetchone()
        assert linha is not None
        return int(linha[0])


# ---------------------------------------------------------------------------
# Critério 1 — cadastro cria conta e caso, atomicamente, contra banco real.
# ---------------------------------------------------------------------------


def test_cadastro_cria_conta_e_caso_em_cadastrado_no_banco_real(cliente: TestClient) -> None:
    email = _email_novo()

    resposta = cliente.post("/api/conta/cadastro", data={"email": email, "senha": "senhaForte123"})

    assert resposta.status_code == 201  # `201 Created` — o POST cria conta e caso
    assert _contar_contas_por_email(email) == 1
    assert _contar_casos_por_conta_email(email) == 1

    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.estado FROM app_aluno.casos c
            JOIN app_aluno.contas a ON a.conta_id = c.conta_id
            WHERE a.email = %s
            """,
            (email,),
        )
        linha = cursor.fetchone()
        assert linha is not None
    assert linha[0] == "CADASTRADO"


def test_cadastro_com_email_duplicado_nao_deixa_conta_orfa_nem_caso_extra(
    cliente: TestClient,
) -> None:
    """A transação ÚNICA garante que a segunda tentativa (e-mail já
    existente) não grava NEM conta NEM caso extra — a violação de `UNIQUE`
    em `contas` faz `ROLLBACK` da transação inteira."""
    email = _email_novo()
    cliente.post("/api/conta/cadastro", data={"email": email, "senha": "primeiraSenha"})
    assert _contar_contas_por_email(email) == 1
    assert _contar_casos_por_conta_email(email) == 1

    resposta = cliente.post("/api/conta/cadastro", data={"email": email, "senha": "segundaSenha"})

    assert resposta.status_code == 400
    assert _contar_contas_por_email(email) == 1
    assert _contar_casos_por_conta_email(email) == 1


# ---------------------------------------------------------------------------
# Critérios 2 e 3 — login/logout ponta a ponta contra banco real.
# ---------------------------------------------------------------------------


def test_login_e_logout_ponta_a_ponta_contra_banco_real(cliente: TestClient) -> None:
    email = _email_novo()
    cliente.post("/api/conta/cadastro", data={"email": email, "senha": "senhaCorreta"})
    cliente.post("/api/conta/logout")

    resposta_senha_errada = cliente.post(
        "/api/conta/login", data={"email": email, "senha": "errada"}
    )
    assert resposta_senha_errada.status_code == 401

    resposta_login = cliente.post(
        "/api/conta/login", data={"email": email, "senha": "senhaCorreta"}
    )
    assert resposta_login.status_code == 200

    resposta_logout = cliente.post("/api/conta/logout")
    # A rota JSON não redireciona: o destino é decisão do cliente.
    assert resposta_logout.history == []
