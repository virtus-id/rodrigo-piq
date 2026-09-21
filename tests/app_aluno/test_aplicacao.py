"""Testes de `app/http/aplicacao.py` e `app/http/sessao.py` — RF-02, AC-03
(T-29).

Cobre os quatro critérios de aceite pelo comportamento observável:
1. o cookie de sessão é assinado e traz `HttpOnly`, `Secure`, `SameSite=Lax`;
2. a sessão carrega só `conta_id` — nada financeiro, nenhum `CASO_ID` de
   terceiros, nenhum papel autorizador;
3. a chave de assinatura vem de `CHAVE_ASSINATURA_SESSAO` (variável de
   ambiente), nunca de literal — subir sem ela é recusado;
4. a aplicação sobe e responde `/saude` sem tocar `persistencia/`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.http.aplicacao import (
    NOME_COOKIE_SESSAO,
    ErroConfiguracaoSessao,
    criar_aplicacao,
)
from app.http.sessao import encerrar_sessao, iniciar_sessao_conta, obter_conta_id

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


@pytest.fixture
def chave_assinatura_sessao(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    return _CHAVE_TESTE


def test_cookie_de_sessao_e_assinado_e_traz_as_tres_flags(
    chave_assinatura_sessao: str,
) -> None:
    """Critério 1: `HttpOnly`, `Secure`, `SameSite=Lax` no `Set-Cookie`, e o
    valor do cookie é opaco (assinado por `itsdangerous`), nunca um
    `conta_id` em texto claro."""
    aplicacao = criar_aplicacao()

    @aplicacao.post("/_teste/abrir-sessao")
    def abrir_sessao(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id="CONTA-123")
        return {"status": "ok"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    resposta = cliente.post("/_teste/abrir-sessao")

    assert resposta.status_code == 200
    set_cookie = resposta.headers.get("set-cookie", "")
    assert NOME_COOKIE_SESSAO in set_cookie

    set_cookie_normalizado = set_cookie.lower()
    assert "httponly" in set_cookie_normalizado
    assert "secure" in set_cookie_normalizado
    assert "samesite=lax" in set_cookie_normalizado

    # O cookie nunca traz "CONTA-123" em texto claro: é assinado/serializado
    # pelo itsdangerous, não um valor legível diretamente.
    assert "CONTA-123" not in set_cookie


def test_sessao_carrega_apenas_identificador_da_conta(
    chave_assinatura_sessao: str,
) -> None:
    """Critério 2: a sessão só expõe `conta_id` pelos helpers de
    `app/http/sessao.py` — nenhum valor monetário, `CASO_ID` de terceiros ou
    papel autorizador é gravável/lido por este módulo."""
    aplicacao = criar_aplicacao()

    @aplicacao.post("/_teste/login")
    def login(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id="CONTA-XYZ")
        return {"status": "ok"}

    @aplicacao.get("/_teste/quem-sou")
    def quem_sou(request: Request) -> dict[str, str | None]:
        return {"conta_id": obter_conta_id(request)}

    @aplicacao.post("/_teste/logout")
    def logout(request: Request) -> dict[str, str]:
        encerrar_sessao(request)
        return {"status": "ok"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")

    # Sem sessão aberta: nenhuma identidade.
    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": None}

    cliente.post("/_teste/login")
    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": "CONTA-XYZ"}

    cliente.post("/_teste/logout")
    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": None}


def test_modulo_sessao_declara_uma_unica_chave_gravavel() -> None:
    """Reforço estático do critério 2: `app/http/sessao.py` acessa
    `request.session[...]`/`request.session.get(...)` sempre pela MESMA
    variável de módulo (a chave é indireta, não repetida como literal em
    cada ponto de uso) — e essa variável vale `"conta_id"`. Não há segunda
    chave, literal ou não, lida/escrita neste módulo que pudesse carregar
    outro dado (dinheiro, `CASO_ID`, papel) por fora dos helpers públicos."""
    import app.http.sessao as modulo_sessao

    codigo_fonte = Path("app/http/sessao.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)

    def _e_acesso_a_session(alvo: ast.expr) -> bool:
        return isinstance(alvo, ast.Attribute) and alvo.attr == "session"

    nomes_de_variavel_usados_como_chave: set[str] = set()
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Subscript)
            and _e_acesso_a_session(no.value)
            and isinstance(no.slice, ast.Name)
        ):
            nomes_de_variavel_usados_como_chave.add(no.slice.id)
        elif (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "get"
            and _e_acesso_a_session(no.func.value)
            and no.args
            and isinstance(no.args[0], ast.Name)
        ):
            nomes_de_variavel_usados_como_chave.add(no.args[0].id)

    # Toda leitura/escrita de sessão usa exatamente uma variável de módulo
    # como chave, e essa variável resolve para "conta_id".
    assert nomes_de_variavel_usados_como_chave == {"_CHAVE_CONTA_ID"}
    assert modulo_sessao._CHAVE_CONTA_ID == "conta_id"


def test_chave_de_assinatura_vem_de_variavel_de_ambiente(
    chave_assinatura_sessao: str,
) -> None:
    """Critério 3, parte positiva: com `CHAVE_ASSINATURA_SESSAO` definida, a
    aplicação sobe e a sessão é assinada com aquela chave (round-trip: o
    cookie emitido é aceito de volta pela mesma aplicação)."""
    aplicacao = criar_aplicacao()

    @aplicacao.post("/_teste/login")
    def login(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id="CONTA-ABC")
        return {"status": "ok"}

    @aplicacao.get("/_teste/quem-sou")
    def quem_sou(request: Request) -> dict[str, str | None]:
        return {"conta_id": obter_conta_id(request)}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/login")

    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": "CONTA-ABC"}


def test_chave_de_assinatura_ausente_impede_a_aplicacao_de_subir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Critério 3, parte negativa: sem `CHAVE_ASSINATURA_SESSAO` no
    ambiente, `criar_aplicacao()` recusa — nunca um fallback inseguro
    silencioso (ex.: chave fixa ou gerada em memória sem avisar)."""
    monkeypatch.delenv("CHAVE_ASSINATURA_SESSAO", raising=False)

    with pytest.raises(ErroConfiguracaoSessao):
        criar_aplicacao()


def test_nenhum_literal_de_chave_de_assinatura_no_codigo() -> None:
    """Reforço estático do critério 3: `app/http/aplicacao.py` não contém
    nenhuma chamada a `SessionMiddleware`/`add_middleware` cujo `secret_key`
    seja uma string literal — o valor só pode vir de `os.environ`."""
    codigo_fonte = Path("app/http/aplicacao.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)

    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            for palavra_chave in no.keywords:
                if palavra_chave.arg == "secret_key":
                    assert not isinstance(palavra_chave.value, ast.Constant), (
                        "secret_key não pode ser literal — deve vir de os.environ"
                    )


def test_aplicacao_sobe_e_responde_rota_de_saude(chave_assinatura_sessao: str) -> None:
    """Critério 4: `/saude` responde sem exigir banco (nenhum `DATABASE_URL`
    definido neste teste, e ainda assim a rota responde 200)."""
    aplicacao = criar_aplicacao()
    cliente = TestClient(aplicacao, base_url="https://teste.local")

    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_rota_de_saude_nao_importa_persistencia() -> None:
    """Reforço estático do critério 4: `app/http/aplicacao.py` não importa
    nada de `persistencia/` — a rota de saúde não pode depender de banco
    nem por acaso, via import de módulo vizinho."""
    codigo_fonte = Path("app/http/aplicacao.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                assert not alias.name.startswith("persistencia"), (
                    f"import de persistencia/ encontrado: {alias.name}"
                )
        elif isinstance(no, ast.ImportFrom):
            modulo = no.module or ""
            assert not modulo.startswith("persistencia"), (
                f"import de persistencia/ encontrado: {modulo}"
            )
