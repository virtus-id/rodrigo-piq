"""`POST /api/provisionamento/{conta,senha}` — `RF-02`, `RF-30` (T-179).

**Por que estes testes existem, e por que ninguém os escreveria por
acidente.** A auditoria de isolamento (`tests/app_aluno/e2e/
test_isolamento_por_caso.py`) enumera as rotas reais e exige
`exigir_caso_da_sessao` em toda que receba `CASO_ID` — mas estas duas NÃO
recebem `CASO_ID`: a de provisionamento é chamada por máquina, antes de
qualquer sessão, e a de senha é chamada por quem ainda não consegue
autenticar. As duas passam naquela auditoria por VACUIDADE.

Ou seja: a porta que cria conta no sistema não tinha nenhum teste guardando
quem pode abri-la. É o que este arquivo cobre.

REGRAS: `RF-02`, `RF-30`
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest
from fastapi.testclient import TestClient

from app.http.aplicacao import criar_aplicacao
from app.http.rotas_provisionamento import (
    TAMANHO_MINIMO_SENHA,
    obter_provisionamento,
    obter_repositorio_contas_provisionamento,
    obter_repositorio_tokens,
)
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado
from persistencia.app_aluno.tokens_acesso import ErroTokenInvalido, TokenEmitido

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_SEGREDO: Final[str] = "segredo-de-teste-do-provisionamento"
_NOME_HEADER: Final[str] = "X-PIQ-Provisionamento"
_EMAIL: Final[str] = "comprador@exemplo.gov.br"

#: O que a fixture `ambiente` entrega a cada teste.
type Ambiente = tuple[
    TestClient, "_ProvisionamentoDublê", "_RepositorioContasDublê", "_RepositorioTokensDublê"
]


class _ProvisionamentoDublê:
    """Cria conta+caso em memória. `ErroEmailDuplicado` no segundo e-mail
    igual, como o `UNIQUE` do banco faria."""

    def __init__(self) -> None:
        self.emails: list[str] = []

    def __call__(self, email: str) -> tuple[Conta, object]:
        if email in self.emails:
            raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}")
        self.emails.append(email)
        conta = Conta(
            conta_id=f"CONTA_{len(self.emails)}",
            email=email,
            senha_hash=None,
            criado_em=datetime.now(UTC),
        )
        return conta, object()


class _RepositorioContasDublê:
    def __init__(self, provisionamento: _ProvisionamentoDublê) -> None:
        self._provisionamento = provisionamento
        self.senhas_definidas: list[tuple[str, str]] = []

    def criar(self, conta_id: str, email: str, senha: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def provisionar(self, conta_id: str, email: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def definir_senha(self, conta_id: str, senha: str) -> None:
        self.senhas_definidas.append((conta_id, senha))

    def buscar_por_email(self, email: str) -> Conta | None:
        if email not in self._provisionamento.emails:
            return None
        indice = self._provisionamento.emails.index(email) + 1
        return Conta(
            conta_id=f"CONTA_{indice}",
            email=email,
            senha_hash=None,
            criado_em=datetime.now(UTC),
        )

    def buscar_por_id(self, conta_id: str) -> Conta | None:  # pragma: no cover
        raise NotImplementedError

    def autenticar(self, email: str, senha: str) -> Conta | None:  # pragma: no cover
        raise NotImplementedError


class _RepositorioTokensDublê:
    def __init__(self) -> None:
        self.emitidos: list[str] = []
        self.consumidos: list[str] = []
        self.valido = True

    def emitir(self, conta_id: str, validade: timedelta | None = None) -> TokenEmitido:
        self.emitidos.append(conta_id)
        return TokenEmitido(
            valor=f"token-de-{conta_id}",
            conta_id=conta_id,
            expira_em=datetime.now(UTC) + timedelta(hours=48),
        )

    def consumir(self, valor: str) -> str:
        if not self.valido:
            raise ErroTokenInvalido("token de acesso inválido")
        self.consumidos.append(valor)
        return "CONTA_1"


@pytest.fixture
def ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Ambiente]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("SEGREDO_PROVISIONAMENTO", _SEGREDO)

    provisionamento = _ProvisionamentoDublê()
    contas = _RepositorioContasDublê(provisionamento)
    tokens = _RepositorioTokensDublê()

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_provisionamento] = lambda: provisionamento
    aplicacao.dependency_overrides[obter_repositorio_contas_provisionamento] = lambda: contas
    aplicacao.dependency_overrides[obter_repositorio_tokens] = lambda: tokens

    with TestClient(aplicacao) as cliente:
        yield cliente, provisionamento, contas, tokens


# ---------------------------------------------------------------------------
# A porta: quem pode criar conta
# ---------------------------------------------------------------------------


def test_sem_segredo_a_rota_recusa(ambiente: Ambiente) -> None:
    """Sem o header, ninguém cria conta. É a única barreira desta rota —
    ela não tem sessão nem `CASO_ID` que a auditoria de isolamento cubra."""
    cliente, provisionamento, _contas, _tokens = ambiente

    resposta = cliente.post("/api/provisionamento/conta", data={"email": _EMAIL})

    assert resposta.status_code == 401
    assert provisionamento.emails == []


def test_segredo_errado_recusa(ambiente: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/conta",
        data={"email": _EMAIL},
        headers={_NOME_HEADER: "segredo-errado"},
    )

    assert resposta.status_code == 401
    assert provisionamento.emails == []


def test_sem_variavel_de_ambiente_a_rota_fica_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**`503`, nunca "aceita qualquer um".**

    Um esquecimento de deploy não pode virar porta aberta para criar contas
    — que é o que aconteceria se a ausência do segredo fosse tratada como
    "não precisa de segredo"."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.delenv("SEGREDO_PROVISIONAMENTO", raising=False)

    provisionamento = _ProvisionamentoDublê()
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_provisionamento] = lambda: provisionamento

    with TestClient(aplicacao) as cliente:
        resposta = cliente.post(
            "/api/provisionamento/conta",
            data={"email": _EMAIL},
            headers={_NOME_HEADER: "qualquer-coisa"},
        )

    assert resposta.status_code == 503
    assert provisionamento.emails == []


# ---------------------------------------------------------------------------
# O caminho feliz e a compra repetida
# ---------------------------------------------------------------------------


def test_provisiona_conta_e_devolve_token(ambiente: Ambiente) -> None:
    cliente, provisionamento, _contas, tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/conta",
        data={"email": _EMAIL},
        headers={_NOME_HEADER: _SEGREDO},
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["token"]
    assert corpo["expira_em"]
    assert provisionamento.emails == [_EMAIL]
    assert tokens.emitidos == ["CONTA_1"]


def test_a_rota_nao_instala_sessao(ambiente: Ambiente) -> None:
    """Quem chama é máquina. Uma sessão instalada no servidor da Hotmart
    não serve a ninguém — e seria uma credencial viva onde não deve."""
    cliente, _provisionamento, _contas, _tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/conta",
        data={"email": _EMAIL},
        headers={_NOME_HEADER: _SEGREDO},
    )

    assert resposta.status_code == 201
    assert "set-cookie" not in {chave.lower() for chave in resposta.headers}


def test_compra_repetida_reenvia_link_sem_revelar_que_ja_existia(
    ambiente: Ambiente,
) -> None:
    """**Decisão do especialista (2026-09-21).** Comprar de novo é normal —
    o aluno perdeu o link, renovou. A rota emite token novo e responde
    IGUAL ao caso novo: o chamador não distingue "criei" de "já existia",
    mesma disciplina do login (`RF-02`)."""
    cliente, _provisionamento, _contas, tokens = ambiente

    primeira = cliente.post(
        "/api/provisionamento/conta",
        data={"email": _EMAIL},
        headers={_NOME_HEADER: _SEGREDO},
    )
    segunda = cliente.post(
        "/api/provisionamento/conta",
        data={"email": _EMAIL},
        headers={_NOME_HEADER: _SEGREDO},
    )

    assert primeira.status_code == segunda.status_code == 201
    assert set(primeira.json()) == set(segunda.json())
    # Dois tokens emitidos para a MESMA conta — o segundo revoga o primeiro
    # (garantia do repositório real, `emitir`).
    assert tokens.emitidos == ["CONTA_1", "CONTA_1"]


def test_email_ausente_recusa(ambiente: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/conta",
        data={},
        headers={_NOME_HEADER: _SEGREDO},
    )

    assert resposta.status_code == 400
    assert provisionamento.emails == []


# ---------------------------------------------------------------------------
# Definir senha
# ---------------------------------------------------------------------------


def test_define_senha_com_token_valido(ambiente: Ambiente) -> None:
    cliente, _provisionamento, contas, tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/senha",
        data={"token": "token-de-CONTA_1", "senha": "senha-bem-comprida"},
    )

    assert resposta.status_code == 200
    assert contas.senhas_definidas == [("CONTA_1", "senha-bem-comprida")]
    assert tokens.consumidos == ["token-de-CONTA_1"]


def test_senha_curta_recusa_e_nao_queima_o_token(ambiente: Ambiente) -> None:
    """**A ordem importa.** A senha é validada ANTES de o token ser
    consumido: um erro de digitação não pode obrigar o aluno a pedir outro
    link."""
    cliente, _provisionamento, contas, tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/senha",
        data={"token": "token-de-CONTA_1", "senha": "a" * (TAMANHO_MINIMO_SENHA - 1)},
    )

    assert resposta.status_code == 400
    assert contas.senhas_definidas == []
    assert tokens.consumidos == []


def test_token_invalido_recusa(ambiente: Ambiente) -> None:
    cliente, _provisionamento, contas, tokens = ambiente
    tokens.valido = False

    resposta = cliente.post(
        "/api/provisionamento/senha",
        data={"token": "token-que-nao-existe", "senha": "senha-bem-comprida"},
    )

    assert resposta.status_code == 400
    assert contas.senhas_definidas == []


def test_definir_senha_nao_instala_sessao(ambiente: Ambiente) -> None:
    """Depois de definir a senha, o aluno entra pelo login normal — assim o
    fluxo de autenticação é um só, e a senha recém-escolhida é exercitada
    na hora."""
    cliente, _provisionamento, _contas, _tokens = ambiente

    resposta = cliente.post(
        "/api/provisionamento/senha",
        data={"token": "token-de-CONTA_1", "senha": "senha-bem-comprida"},
    )

    assert resposta.status_code == 200
    assert "set-cookie" not in {chave.lower() for chave in resposta.headers}


# ---------------------------------------------------------------------------
# Webhook da Hotmart
# ---------------------------------------------------------------------------

_HOTTOK: Final[str] = "hottok-de-teste"
_NOME_HEADER_HOTTOK: Final[str] = "X-HOTMART-HOTTOK"
_PRODUTO_ID: Final[str] = "7079006"


def _payload_hotmart(
    *, evento: str = "PURCHASE_APPROVED", produto_id: str = _PRODUTO_ID, email: str = _EMAIL
) -> dict[str, object]:
    """Só os campos que a rota lê — a Hotmart manda muito mais, mas o
    restante do payload real (`purchase`, `producer`, `commissions`...)
    é irrelevante para este teste."""
    return {
        "event": evento,
        "data": {"product": {"id": produto_id}, "buyer": {"email": email}},
    }


@pytest.fixture
def ambiente_hotmart(monkeypatch: pytest.MonkeyPatch) -> Iterator[Ambiente]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("HOTMART_HOTTOK", _HOTTOK)
    monkeypatch.setenv("HOTMART_PRODUTO_ID", _PRODUTO_ID)

    provisionamento = _ProvisionamentoDublê()
    contas = _RepositorioContasDublê(provisionamento)
    tokens = _RepositorioTokensDublê()

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_provisionamento] = lambda: provisionamento
    aplicacao.dependency_overrides[obter_repositorio_contas_provisionamento] = lambda: contas
    aplicacao.dependency_overrides[obter_repositorio_tokens] = lambda: tokens

    with TestClient(aplicacao) as cliente:
        yield cliente, provisionamento, contas, tokens


def test_hotmart_sem_hottok_recusa(ambiente_hotmart: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    resposta = cliente.post("/api/provisionamento/hotmart", json=_payload_hotmart())

    assert resposta.status_code == 401
    assert provisionamento.emails == []


def test_hotmart_hottok_errado_recusa(ambiente_hotmart: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    resposta = cliente.post(
        "/api/provisionamento/hotmart",
        json=_payload_hotmart(),
        headers={_NOME_HEADER_HOTTOK: "token-errado"},
    )

    assert resposta.status_code == 401
    assert provisionamento.emails == []


def test_hotmart_sem_variavel_de_ambiente_fica_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.delenv("HOTMART_HOTTOK", raising=False)

    provisionamento = _ProvisionamentoDublê()
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_provisionamento] = lambda: provisionamento

    with TestClient(aplicacao) as cliente:
        resposta = cliente.post(
            "/api/provisionamento/hotmart",
            json=_payload_hotmart(),
            headers={_NOME_HEADER_HOTTOK: "qualquer-coisa"},
        )

    assert resposta.status_code == 503
    assert provisionamento.emails == []


def test_hotmart_token_no_corpo_tambem_autentica(ambiente_hotmart: Ambiente) -> None:
    """A Hotmart documenta o token tanto no header quanto no campo
    `hottok` do corpo, conforme a versão — a rota aceita as duas formas."""
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    corpo = _payload_hotmart()
    corpo["hottok"] = _HOTTOK
    resposta = cliente.post("/api/provisionamento/hotmart", json=corpo)

    assert resposta.status_code == 200
    assert provisionamento.emails == [_EMAIL]


def test_hotmart_evento_diferente_de_aprovada_e_ignorado(
    ambiente_hotmart: Ambiente,
) -> None:
    """Reembolso, cancelamento etc. não são erro — só não criam conta. `200`
    para a Hotmart não reenviar o mesmo evento pra sempre."""
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    resposta = cliente.post(
        "/api/provisionamento/hotmart",
        json=_payload_hotmart(evento="PURCHASE_REFUNDED"),
        headers={_NOME_HEADER_HOTTOK: _HOTTOK},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"ignorado": "evento"}
    assert provisionamento.emails == []


def test_hotmart_produto_diferente_e_ignorado(ambiente_hotmart: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    resposta = cliente.post(
        "/api/provisionamento/hotmart",
        json=_payload_hotmart(produto_id="999999"),
        headers={_NOME_HEADER_HOTTOK: _HOTTOK},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"ignorado": "produto"}
    assert provisionamento.emails == []


def test_hotmart_compra_aprovada_provisiona_e_nao_devolve_token(
    ambiente_hotmart: Ambiente,
) -> None:
    """Diferente de `/conta`: o token não volta no corpo — quem chama é a
    Hotmart, o único caminho de entrega ao aluno é o e-mail."""
    cliente, provisionamento, _contas, tokens = ambiente_hotmart

    resposta = cliente.post(
        "/api/provisionamento/hotmart",
        json=_payload_hotmart(),
        headers={_NOME_HEADER_HOTTOK: _HOTTOK},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["provisionado"] is True
    assert "token" not in corpo
    assert provisionamento.emails == [_EMAIL]
    assert tokens.emitidos == ["CONTA_1"]


def test_hotmart_compra_repetida_reprovisiona_sem_erro(ambiente_hotmart: Ambiente) -> None:
    cliente, _provisionamento, _contas, tokens = ambiente_hotmart

    for _ in range(2):
        resposta = cliente.post(
            "/api/provisionamento/hotmart",
            json=_payload_hotmart(),
            headers={_NOME_HEADER_HOTTOK: _HOTTOK},
        )
        assert resposta.status_code == 200

    assert tokens.emitidos == ["CONTA_1", "CONTA_1"]


def test_hotmart_sem_email_no_payload_recusa(ambiente_hotmart: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    corpo = _payload_hotmart()
    corpo["data"] = {"product": {"id": _PRODUTO_ID}, "buyer": {}}
    resposta = cliente.post(
        "/api/provisionamento/hotmart", json=corpo, headers={_NOME_HEADER_HOTTOK: _HOTTOK}
    )

    assert resposta.status_code == 400
    assert provisionamento.emails == []


def test_hotmart_corpo_nao_json_recusa(ambiente_hotmart: Ambiente) -> None:
    cliente, provisionamento, _contas, _tokens = ambiente_hotmart

    resposta = cliente.post(
        "/api/provisionamento/hotmart",
        content=b"isto nao e json",
        headers={_NOME_HEADER_HOTTOK: _HOTTOK, "Content-Type": "application/json"},
    )

    assert resposta.status_code == 400
    assert provisionamento.emails == []
