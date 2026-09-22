"""Testes de `app/http/rotas_conta.py` — RF-02, AC-03 (T-30).

Cobre os quatro critérios de aceite pelo comportamento observável, SEM
Postgres real: `CadastroConta`/`RepositorioContas` são substituídos por
dublês em memória via `app.dependency_overrides` — o mesmo mecanismo de
injeção que a produção usa (`Depends(obter_cadastro_conta)`/
`Depends(obter_repositorio_contas)`), sem duplicar SQL num mock de cursor.
A validação contra Postgres real (transação atômica de verdade, `UNIQUE`
de e-mail) está em `tests/app_aluno/integracao/test_rotas_conta.py`
(`requer_banco`).

1. cadastro cria conta e caso, caso nasce em `CADASTRADO`;
2. login correto abre sessão; login errado não abre, mesma mensagem para
   conta inexistente e senha errada;
3. logout invalida a sessão: rota autenticada seguinte perde `conta_id`;
4. os três formulários submetem com `TestClient` (equivalente a JS
   desabilitado: POST direto ao endpoint, sem `fetch`) e o HTML não depende
   de `onsubmit`/JavaScript para funcionar.

REGRAS: RF-02, AC-03
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import NOME_COOKIE_SESSAO, criar_aplicacao
from app.http.rotas_api_conta import obter_casos_da_conta
from app.http.rotas_conta import (
    obter_cadastro_conta,
    obter_repositorio_contas,
)
from app.http.sessao import obter_conta_id
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado, RepositorioContas

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


class _CadastroContaDublê:
    """Dublê em memória de `CadastroConta` — grava em dicionários, nunca
    toca banco. `emails_existentes` simula a restrição `UNIQUE` de
    `app_aluno.contas` sem precisar de Postgres."""

    def __init__(self) -> None:
        self.contas: dict[str, Conta] = {}
        self.casos: dict[str, Caso] = {}
        self._proximo_id = 0

    def __call__(self, email: str, senha: str) -> tuple[Conta, Caso]:
        for conta_existente in self.contas.values():
            if conta_existente.email == email:
                raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}")

        self._proximo_id += 1
        conta_id = f"CONTA_TESTE_{self._proximo_id}"
        caso_id = f"CASO_TESTE_{self._proximo_id}"
        agora = datetime.now(UTC)

        conta = Conta(
            conta_id=conta_id, email=email, senha_hash=f"hash-de-{senha}", criado_em=agora
        )
        caso = Caso(
            CASO_ID=caso_id,
            conta_id=conta_id,
            estado=ESTADO_CASO.CADASTRADO,
            DATA_REFERENCIA=date.today(),
            QUESTIONARIO_VERSION="PENDENTE",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
        self.contas[conta_id] = conta
        self.casos[caso_id] = caso
        self._registrar_senha(conta_id, senha)
        return conta, caso

    def _registrar_senha(self, conta_id: str, senha: str) -> None:
        self._senhas = getattr(self, "_senhas", {})
        self._senhas[conta_id] = senha


class _RepositorioContasDublê(RepositorioContas):
    """Dublê em memória de `RepositorioContas` — `autenticar` reproduz a
    MESMA garantia de T-28 (mesmo resultado para conta inexistente e senha
    errada), sem tocar banco."""

    def __init__(self, cadastro: _CadastroContaDublê) -> None:
        self._cadastro = cadastro

    def criar(self, conta_id: str, email: str, senha: str) -> None:  # pragma: no cover
        raise NotImplementedError("não usado por estas rotas")

    # `T-179`: estes dois nascem do provisionamento pela Hotmart, que
    # nenhum destes testes exercita — o `Protocol` os exige, o dublê os
    # recusa explicitamente em vez de fingir comportamento.
    def provisionar(self, conta_id: str, email: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def definir_senha(self, conta_id: str, senha: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def buscar_por_email(self, email: str) -> Conta | None:
        for conta in self._cadastro.contas.values():
            if conta.email == email:
                return conta
        return None

    def buscar_por_id(self, conta_id: str) -> Conta | None:
        return self._cadastro.contas.get(conta_id)

    def autenticar(self, email: str, senha: str) -> Conta | None:
        conta = self.buscar_por_email(email)
        if conta is None:
            return None
        senhas = getattr(self._cadastro, "_senhas", {})
        if senhas.get(conta.conta_id) != senha:
            return None
        return conta


class _RepositorioCasosDaConta:
    """Dublê de `RepositorioCasos` restrito ao que `GET /api/conta/eu` usa —
    `T-154`.

    Sem ele a rota constrói `RepositorioCasosSupabase` e exige `DATABASE_URL`,
    que é exatamente o defeito que `T-157` corrigiu noutro arquivo: teste de
    rota não deve precisar de banco para provar comportamento de rota."""

    def __init__(self, cadastro: _CadastroContaDublê) -> None:
        self._cadastro = cadastro

    def listar_da_conta(self, conta_id: str) -> tuple[str, ...]:
        return tuple(
            caso.CASO_ID
            for caso in self._cadastro.casos.values()
            if caso.conta_id == conta_id
        )


@pytest.fixture
def cadastro_dublê() -> _CadastroContaDublê:
    return _CadastroContaDublê()


@pytest.fixture
def cliente(
    monkeypatch: pytest.MonkeyPatch, cadastro_dublê: _CadastroContaDublê
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_cadastro_conta] = lambda: cadastro_dublê
    aplicacao.dependency_overrides[obter_repositorio_contas] = lambda: (
        _RepositorioContasDublê(cadastro_dublê)
    )
    # `T-154`: `GET /api/conta/eu` enumera os casos da conta autenticada.
    aplicacao.dependency_overrides[obter_casos_da_conta] = lambda: (
        _RepositorioCasosDaConta(cadastro_dublê)
    )

    @aplicacao.get("/_teste/quem-sou")
    def quem_sou(request: Request) -> dict[str, str | None]:
        return {"conta_id": obter_conta_id(request)}

    return TestClient(aplicacao, base_url="https://teste.local")


# ---------------------------------------------------------------------------
# Critério 1 — cadastro cria conta e caso; caso nasce em CADASTRADO.
# ---------------------------------------------------------------------------


def test_cadastro_cria_conta_e_caso_em_cadastrado(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    resposta = cliente.post(
        "/api/conta/cadastro", data={"email": "aluno@teste.invalido", "senha": "senhaForte123"}
    )

    assert resposta.status_code == 201  # `201 Created`: o POST cria conta e caso
    assert len(cadastro_dublê.contas) == 1
    assert len(cadastro_dublê.casos) == 1

    (caso,) = cadastro_dublê.casos.values()
    assert caso.estado == ESTADO_CASO.CADASTRADO

    (conta,) = cadastro_dublê.contas.values()
    assert caso.conta_id == conta.conta_id


def test_cadastro_com_email_duplicado_nao_cria_conta_nem_caso_extra(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    cliente.post(
        "/api/conta/cadastro", data={"email": "duplicado@teste.invalido", "senha": "primeira"}
    )

    resposta = cliente.post(
        "/api/conta/cadastro", data={"email": "duplicado@teste.invalido", "senha": "segunda"}
    )

    assert resposta.status_code == 400
    assert len(cadastro_dublê.contas) == 1
    assert len(cadastro_dublê.casos) == 1


def test_cadastro_abre_sessao_da_conta_criada(cliente: TestClient) -> None:
    cliente.post(
        "/api/conta/cadastro", data={"email": "sessao@teste.invalido", "senha": "senhaForte123"}
    )

    resposta = cliente.get("/_teste/quem-sou")

    assert resposta.json()["conta_id"] is not None


# ---------------------------------------------------------------------------
# Critério 2 — login correto abre sessão; errado não abre, mesma mensagem.
# ---------------------------------------------------------------------------


def test_login_com_senha_correta_abre_sessao(cliente: TestClient) -> None:
    cliente.post(
        "/api/conta/cadastro", data={"email": "login@teste.invalido", "senha": "senhaCorreta"}
    )
    cliente.post("/api/conta/logout")

    resposta = cliente.post(
        "/api/conta/login", data={"email": "login@teste.invalido", "senha": "senhaCorreta"}
    )

    assert resposta.status_code == 200
    assert cliente.get("/_teste/quem-sou").json()["conta_id"] is not None


def test_login_com_senha_errada_nao_abre_sessao(cliente: TestClient) -> None:
    cliente.post(
        "/api/conta/cadastro", data={"email": "senhaerrada@teste.invalido", "senha": "correta"}
    )
    cliente.post("/api/conta/logout")

    resposta = cliente.post(
        "/api/conta/login", data={"email": "senhaerrada@teste.invalido", "senha": "errada"}
    )

    assert resposta.status_code == 401
    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": None}


def test_mensagem_de_erro_de_login_nao_distingue_conta_inexistente_de_senha_errada(
    cliente: TestClient,
) -> None:
    """RF-02: a mesma mensagem para os dois casos — o HTML de erro é
    idêntico byte a byte."""
    cliente.post(
        "/api/conta/cadastro", data={"email": "existente@teste.invalido", "senha": "correta"}
    )
    cliente.post("/api/conta/logout")

    resposta_senha_errada = cliente.post(
        "/api/conta/login", data={"email": "existente@teste.invalido", "senha": "errada"}
    )
    resposta_conta_inexistente = cliente.post(
        "/api/conta/login", data={"email": "nunca-existiu@teste.invalido", "senha": "qualquer"}
    )

    assert resposta_senha_errada.status_code == resposta_conta_inexistente.status_code == 401
    assert resposta_senha_errada.text == resposta_conta_inexistente.text


# ---------------------------------------------------------------------------
# Critério 3 — logout invalida a sessão.
# ---------------------------------------------------------------------------


def test_logout_invalida_a_sessao(cliente: TestClient) -> None:
    cliente.post(
        "/api/conta/cadastro", data={"email": "logout@teste.invalido", "senha": "senhaForte123"}
    )
    assert cliente.get("/_teste/quem-sou").json()["conta_id"] is not None

    # `TestClient` segue o redirect por padrão (equivalente ao que um
    # navegador sem JS faz nativamente): `resposta.history` prova que a rota
    # respondeu com um redirect, e o destino final (`/conta/login`) já é
    # servido sem sessão.
    resposta = cliente.post("/api/conta/logout")

    # A rota JSON não redireciona — quem decide o destino é o cliente.
    assert resposta.history == []
    assert resposta.json() == {"encerrada": True}
    assert cliente.get("/_teste/quem-sou").json() == {"conta_id": None}


# ---------------------------------------------------------------------------
# Critério 4 — REESCRITO em T-144: o contrato agora é JSON, não formulário.
#
# **O que se perdeu, dito com todas as letras.** Até a Rodada 4 estes quatro
# testes provavam que cadastro, login e logout funcionavam com JavaScript
# DESABILITADO: eram `<form method="post">` nativos, sem `<script>`. Isso era
# `RF-49`/`EC-21` — progressive enhancement, que é requisito de
# acessibilidade, não conforto.
#
# A adoção de React (decisão do especialista, `plans/app-aluno.plan.md` §2,
# revisão de 2026-09-15) **revogou** essa garantia: uma SPA não funciona sem
# JavaScript. Está registrado como `OQ-29`, aberta.
#
# Estes testes passam a provar o que de fato existe hoje — o contrato JSON —
# em vez de continuarem afirmando uma propriedade que o sistema deixou de
# ter. Apagá-los sem substituto esconderia a perda; mantê-los como estavam
# seria mentir sobre o que o sistema faz.
# ---------------------------------------------------------------------------


def test_cadastro_devolve_json_com_conta_e_caso(cliente: TestClient) -> None:
    """O cadastro cria conta E caso atomicamente, e o JSON devolve os dois —
    é o dado que o cliente React precisa para navegar ao caso recém-criado."""
    resposta = cliente.post(
        "/api/conta/cadastro",
        data={"email": "jsoncadastro@teste.invalido", "senha": "senhaForte123"},
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["email"] == "jsoncadastro@teste.invalido"
    assert corpo["conta_id"]
    assert corpo["CASO_ID"]


def test_login_devolve_json_e_abre_sessao(cliente: TestClient) -> None:
    cliente.post(
        "/api/conta/cadastro",
        data={"email": "jsonlogin@teste.invalido", "senha": "senhaForte123"},
    )
    cliente.post("/api/conta/logout")

    resposta = cliente.post(
        "/api/conta/login",
        data={"email": "jsonlogin@teste.invalido", "senha": "senhaForte123"},
    )

    assert resposta.status_code == 200
    assert resposta.json()["email"] == "jsonlogin@teste.invalido"
    assert cliente.get("/_teste/quem-sou").json()["conta_id"] is not None


def test_logout_devolve_json_sem_redirect(cliente: TestClient) -> None:
    """A rota JSON não redireciona: quem decide para onde ir é o cliente.
    O redirect existia porque um `<form>` nativo precisa de destino."""
    cliente.post(
        "/api/conta/cadastro",
        data={"email": "jsonlogout@teste.invalido", "senha": "senhaForte123"},
    )

    resposta = cliente.post("/api/conta/logout")

    assert resposta.status_code == 200
    assert resposta.json() == {"encerrada": True}
    assert resposta.history == []
    assert cliente.get("/_teste/quem-sou").json()["conta_id"] is None


def test_o_corpo_continua_form_urlencoded_sem_python_multipart(cliente: TestClient) -> None:
    """A RESPOSTA virou JSON, mas o CORPO da requisição continua
    `form-urlencoded`: `python-multipart` segue fora do plano, e as rotas
    leem com `parse_qsl` da stdlib."""
    resposta = cliente.post(
        "/api/conta/cadastro",
        content="email=urlencoded@teste.invalido&senha=senhaForte123",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 201


def test_nenhuma_rota_de_conta_usa_form_ou_request_form_do_starlette() -> None:
    """Reforço estático: `app/http/rotas_conta.py` não usa `fastapi.Form`
    nem `Request.form()` — ambos exigem `python-multipart`, dependência
    fora do plano (`pyproject.toml` extra `app` não a declara)."""
    codigo_fonte = Path("app/http/rotas_conta.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)

    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr == "form":
            raise AssertionError("Request.form() não deve ser usado (exige python-multipart)")
        if isinstance(no, ast.Name) and no.id == "Form":
            raise AssertionError("fastapi.Form não deve ser usado (exige python-multipart)")


# ---------------------------------------------------------------------------
# `RF-59`, `AC-80` — `e_revisor` no payload de login e de cadastro (T-148).
#
# É DICA DE INTERFACE, não autorização. Serve para a interface não oferecer ao
# aluno o caminho para a fila e o painel — quem vê "Fila", clica e recebe
# `403` conclui que o sistema está quebrado. Quem autoriza é
# `exigir_papel_revisor`, que reconsulta o banco a cada requisição.
# ---------------------------------------------------------------------------


def test_rf59_cadastro_devolve_e_revisor_falso(cliente: TestClient) -> None:
    """Conta nova nunca nasce revisora — `Conta.e_revisor` é `False` por
    default, e nenhuma rota promove ninguém."""
    resposta = cliente.post(
        "/api/conta/cadastro",
        data={"email": "novo@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    assert resposta.status_code == 201
    assert resposta.json()["e_revisor"] is False


def test_rf59_login_devolve_e_revisor_da_conta(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """`RF-59` — o login informa o papel para a interface decidir o que
    oferecer. Sem este campo, a interface não tem como esconder a área da
    equipe, e o aluno bate numa porta que o servidor fecha."""
    conta, _caso = cadastro_dublê("revisor@exemplo.gov.br", "senha-de-teste-123")
    # Promoção como no mundo real: manual, fora de qualquer rota HTTP.
    cadastro_dublê.contas[conta.conta_id] = replace(conta, e_revisor=True)

    resposta = cliente.post(
        "/api/conta/login",
        data={"email": "revisor@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    assert resposta.status_code == 200
    assert resposta.json()["e_revisor"] is True


def test_rf59_login_de_aluno_devolve_e_revisor_falso(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """A recíproca: conta de aluno reporta `False`, e a interface esconde as
    telas de equipe (`AC-80`)."""
    cadastro_dublê("aluna@exemplo.gov.br", "senha-de-teste-123")

    resposta = cliente.post(
        "/api/conta/login",
        data={"email": "aluna@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    assert resposta.status_code == 200
    assert resposta.json()["e_revisor"] is False


def test_rf59_e_revisor_nao_e_gravado_na_sessao(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """**A trava que impede o campo de virar autorização cacheada.**

    `app/http/sessao.py` grava só `conta_id`, por design: `exigir_papel_revisor`
    reconsulta o banco a cada requisição (`isolamento.py`). Se o papel entrasse
    na sessão, revogar alguém deixaria de ter efeito até o cookie expirar — e o
    campo do login deixaria de ser dica para virar credencial."""
    conta, _caso = cadastro_dublê("revisor2@exemplo.gov.br", "senha-de-teste-123")
    cadastro_dublê.contas[conta.conta_id] = replace(conta, e_revisor=True)

    cliente.post(
        "/api/conta/login",
        data={"email": "revisor2@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    cookie = cliente.cookies.get(NOME_COOKIE_SESSAO)
    assert cookie is not None
    # O cookie é assinado, não cifrado: o payload é legível. Se `e_revisor`
    # estivesse lá, apareceria — é justamente por isso que a asserção funciona.
    assert "e_revisor" not in cookie


def test_rf59_o_payload_de_login_nao_ganhou_campo_a_mais(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """O campo é ADITIVO: as chaves de antes seguem lá, e nenhuma outra entrou.

    Payload de login é superfície pública; campo a mais é campo que alguém vai
    consumir sem contrato."""
    cadastro_dublê("aluna2@exemplo.gov.br", "senha-de-teste-123")

    resposta = cliente.post(
        "/api/conta/login",
        data={"email": "aluna2@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    assert set(resposta.json()) == {"email", "conta_id", "e_revisor"}


# ---------------------------------------------------------------------------
# `RF-02`, `RF-59` — `GET /api/conta/eu` (T-154).
#
# A rota que fecha o buraco da descoberta: até ela existir, quem fizesse login
# sem `?caso=` na URL ficava preso na tela de entrada com a sessão instalada —
# credencial aceita, aplicação inalcançável. E o revisor perdia o papel a cada
# recarga da página.
# ---------------------------------------------------------------------------


def test_t154_eu_devolve_conta_e_caso_da_sessao(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """`RF-02` — depois de entrar, o cliente descobre o próprio caso pela
    SESSÃO, sem precisar do `?caso=` na URL."""
    _conta, caso = cadastro_dublê("aluna3@exemplo.gov.br", "senha-de-teste-123")
    cliente.post(
        "/api/conta/login",
        data={"email": "aluna3@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    resposta = cliente.get("/api/conta/eu")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["CASO_ID"] == caso.CASO_ID
    assert corpo["email"] == "aluna3@exemplo.gov.br"
    assert corpo["casos"] == [caso.CASO_ID]


def test_t154_eu_devolve_o_papel_lido_do_banco(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """`RF-59` — **o papel sobrevive a uma recarga da página.**

    O campo sai de `RepositorioContas.buscar_por_id`, não da sessão: é isso
    que faz revogar um revisor ter efeito na requisição seguinte, em vez de
    quando o cookie expirar."""
    conta, _caso = cadastro_dublê("revisor3@exemplo.gov.br", "senha-de-teste-123")
    cadastro_dublê.contas[conta.conta_id] = replace(conta, e_revisor=True)
    cliente.post(
        "/api/conta/login",
        data={"email": "revisor3@exemplo.gov.br", "senha": "senha-de-teste-123"},
    )

    assert cliente.get("/api/conta/eu").json()["e_revisor"] is True

    # Revogação SEM tocar na sessão: o cookie segue o mesmo, e a resposta muda.
    cadastro_dublê.contas[conta.conta_id] = replace(conta, e_revisor=False)

    assert cliente.get("/api/conta/eu").json()["e_revisor"] is False


def test_t154_eu_sem_sessao_responde_401(cliente: TestClient) -> None:
    """Sem sessão, `401` — o caminho normal de quem ainda não entrou. É o que
    permite o cliente perguntar "quem sou eu?" na carga da página sem tratar a
    ausência de login como falha."""
    resposta = cliente.get("/api/conta/eu")

    assert resposta.status_code == 401


def test_t154_eu_nao_aceita_identificador_do_cliente(
    cliente: TestClient, cadastro_dublê: _CadastroContaDublê
) -> None:
    """**A pergunta é "quem sou eu", nunca "posso ver o caso X".**

    A rota não tem parâmetro nenhum: a sessão é a única entrada, então não há
    identificador a forjar. Passar `conta_id` de outra conta na query não muda
    o que ela devolve."""
    _conta_a, caso_a = cadastro_dublê("a@exemplo.gov.br", "senha-de-teste-123")
    conta_b, _caso_b = cadastro_dublê("b@exemplo.gov.br", "senha-de-teste-123")
    cliente.post(
        "/api/conta/login", data={"email": "a@exemplo.gov.br", "senha": "senha-de-teste-123"}
    )

    resposta = cliente.get(f"/api/conta/eu?conta_id={conta_b.conta_id}")

    assert resposta.json()["CASO_ID"] == caso_a.CASO_ID
    assert resposta.json()["conta_id"] != conta_b.conta_id
