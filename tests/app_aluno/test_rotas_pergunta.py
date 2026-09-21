"""`GET /caso/{CASO_ID}/pergunta` — a rota que faltava (`RF-45`, `RF-46`,
`AC-72`, `AC-74`, `EC-23`, `EC-24`, T-123).

Sem banco: os repositórios são os adaptadores de arquivo (`persistencia/
app_aluno/arquivo.py`, T-24) sobre `tmp_path`, e o de casos é um dublê
restrito ao que `exigir_caso_da_sessao` usa — mesmo padrão de
`tests/app_aluno/test_bloco10.py::_montar_cliente`.

A coleção de registros é FABRICADA aqui, não a real: estes testes são sobre
o comportamento da ROTA (qual pergunta ela escolhe, o que faz quando a
condição é falsa, o que faz quando não há mais pendência), e amarrá-los aos
247 registros reais tornaria cada asserção refém de qualquer edição de YAML
— o mesmo motivo pelo qual `obter_colecao_de_registros` existe como ponto de
injeção (`rotas_coleta.py`).

REGRAS: `RF-45`, `RF-46`, `AC-72`, `AC-74`, `EC-23`, `EC-24`
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros
from collection.condicoes import Condicao, CondicaoIgual
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import Resposta
from persistencia.app_aluno.arquivo import (
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import Caso

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID: Final[str] = "CONTA-PERGUNTA-1"
_CASO_ID: Final[str] = "CASO-PERGUNTA-1"


class _RepositorioCasosDublê:
    """Restrito ao que `exigir_caso_da_sessao` usa — mesmo padrão de
    `tests/app_aluno/test_bloco10.py::_RepositorioCasosDublê`."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _registro(
    identificador: str,
    *,
    variavel: str,
    condicao: Condicao | None = None,
    tipo: TipoResposta = TipoResposta.TEXTO_CURTO,
) -> RegistroPergunta:
    """Registro fabricado — enunciado curto de propósito (`AC-37`: nenhum
    conteúdo real de questionário em `.py`)."""
    return RegistroPergunta(
        ID=identificador,
        bloco=1,
        enunciado=f"Campo {identificador}",
        tipo=tipo,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=(),
        VARIAVEL_GRAVADA=variavel,
        condicao_exibicao=condicao,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=False,
        salto_consequencia=None,
    )


def _caso_em_coleta() -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    colecao: ColecaoDeRegistros,
    respostas_iniciais: tuple[Resposta, ...] = (),
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    repositorio_respostas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    )
    for resposta in respostas_iniciais:
        repositorio_respostas.gravar(resposta)

    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        _caso_em_coleta(), _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: repositorio_respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: RepositorioItensArquivo(
        caminho_arquivo=tmp_path / "itens.jsonl"
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def _resposta(variavel: str, valor: str) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=variavel,
        item_id=None,
        valor=valor,
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# AC-72 — a primeira pergunta não respondida e exibível
# ---------------------------------------------------------------------------


def test_ac72_devolve_a_primeira_pergunta_nao_respondida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O aluno abre o app e recebe a pergunta que falta — o caminho que
    simplesmente não existia antes desta rota."""
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _registro("Q1", variavel="VAR_UM"),
            _registro("Q2", variavel="VAR_DOIS"),
        ),
    )
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=colecao)

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert resposta.status_code == 200
    assert resposta.json()["pergunta"]["ID"] == "Q1"


def test_ac72_pula_a_pergunta_ja_respondida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nada já respondido é pedido de novo (`RF-10`, `AC-01`)."""
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _registro("Q1", variavel="VAR_UM"),
            _registro("Q2", variavel="VAR_DOIS"),
        ),
    )
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=colecao,
        respostas_iniciais=(_resposta("VAR_UM", "ja respondida"),),
    )

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert resposta.status_code == 200
    assert resposta.json()["pergunta"]["ID"] == "Q2"


# ---------------------------------------------------------------------------
# EC-24 — condicional falsa nunca atravessa a fronteira
# ---------------------------------------------------------------------------


def test_ec24_pergunta_com_condicao_falsa_nao_e_devolvida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`RF-45`: quem avalia a condicional é o servidor. A pergunta fechada
    não aparece na resposta, e o cliente não recebe meio de descobrir que
    ela existe."""
    condicao_falsa = CondicaoIgual(variavel="VAR_UM", valor="NUNCA")
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _registro("Q1", variavel="VAR_UM"),
            _registro("Q_FECHADA", variavel="VAR_FECHADA", condicao=condicao_falsa),
        ),
    )
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=colecao,
        respostas_iniciais=(_resposta("VAR_UM", "outra coisa"),),
    )

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert "Q_FECHADA" not in resposta.text
    assert "condicao_exibicao" not in resposta.text


# ---------------------------------------------------------------------------
# EC-23 — coleta completa
# ---------------------------------------------------------------------------


def test_ec23_coleta_completa_nao_devolve_pergunta_arbitraria(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem pendência, a rota devolve a tela de conclusão — nunca `500`,
    nunca uma pergunta qualquer."""
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(_registro("Q1", variavel="VAR_UM"),),
    )
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=colecao,
        respostas_iniciais=(_resposta("VAR_UM", "respondida"),),
    )

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert resposta.status_code == 200
    assert resposta.json()["coleta_completa"] is True


# ---------------------------------------------------------------------------
# AC-74 — isolamento
# ---------------------------------------------------------------------------


def test_ac74_sem_sessao_e_recusado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem sessão ⇒ `401`, antes de qualquer leitura de dado do caso."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0", registros=(_registro("Q1", variavel="VAR_UM"),)
    )
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=colecao)
    cliente.cookies.clear()

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert resposta.status_code == 401


def test_ac74_caso_de_outra_conta_devolve_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Caso que não é da sessão ⇒ `404`, indistinguível de inexistente."""
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0", registros=(_registro("Q1", variavel="VAR_UM"),)
    )
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=colecao)

    resposta = cliente.get("/caso/CASO-DE-OUTRA-CONTA/pergunta")

    assert resposta.status_code == 404


def test_ac74_a_rota_nova_passa_na_auditoria_de_isolamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A auditoria que enumera toda `APIRoute` registrada não acusa a rota
    nova — ela declara `CASO_ID` com `exigir_caso_da_sessao`."""
    from tests.app_aluno.e2e.test_mecanismo_isolamento import (
        rotas_sem_isolamento_por_caso,
    )

    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    assert rotas_sem_isolamento_por_caso(aplicacao) == []


# ---------------------------------------------------------------------------
# A pergunta específica
# ---------------------------------------------------------------------------


def test_pergunta_especifica_devolve_o_campo_pedido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-33`: reabrir um campo isolado sem varrer a coleta inteira."""
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _registro("Q1", variavel="VAR_UM"),
            _registro("Q2", variavel="VAR_DOIS"),
        ),
    )
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=colecao)

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta/Q2")

    assert resposta.status_code == 200
    assert resposta.json()["pergunta"]["ID"] == "Q2"


def test_pergunta_inexistente_devolve_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    colecao = ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0", registros=(_registro("Q1", variavel="VAR_UM"),)
    )
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=colecao)

    resposta = cliente.get(f"/caso/{_CASO_ID}/pergunta/NAO_EXISTE")

    assert resposta.status_code == 404
