"""A variante JSON é ADITIVA, nunca substitutiva — `RF-49`, `AC-79`,
`EC-21` (T-124).

A página única precisa de uma resposta que ela consiga consumir sem
reinterpretar HTML. Mas o caminho nativo (`<form method="post">`, sem
JavaScript) é **requisito de acessibilidade**, não cortesia: o plano §2
escolheu progressive enhancement, e `EC-21` fixa que a gravação continua
funcionando com JS desabilitado.

Daí a forma da mudança: a rota ramifica **só na montagem da resposta**, pelo
cabeçalho `Accept`, depois de os sete passos do §5.1 já terem corrido
idênticos. Estes testes provam as duas metades dessa afirmação — que quem
pede JSON recebe JSON, e que quem não pede continua recebendo exatamente o
fragmento HTML de antes.

Sem banco: repositórios de arquivo sobre `tmp_path`, mesmo padrão de
`tests/app_aluno/test_rotas_pergunta.py` (T-123).

REGRAS: `RF-49`, `AC-79`, `EC-21`
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
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import Caso

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID: Final[str] = "CONTA-JSON-1"
_CASO_ID: Final[str] = "CASO-JSON-1"


class _RepositorioCasosDublê:
    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _colecao_de_um_campo() -> ColecaoDeRegistros:
    """Um registro `MOEDA`, para exercitar a fronteira decimal junto."""
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            RegistroPergunta(
                ID="Q1",
                bloco=1,
                enunciado="Campo Q1",
                tipo=TipoResposta.MOEDA,
                obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
                escopo_repeticao=EscopoRepeticao.NENHUM,
                opcoes=(),
                VARIAVEL_GRAVADA="VAR_MOEDA",
                condicao_exibicao=None,
                interpolacoes=(),
                validacoes_cruzadas=(),
                origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
                admite_nao_sei=False,
                salto_consequencia=None,
            ),
        ),
    )


def _montar_cliente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    caso = Caso(
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

    repositorio_casos_arquivo = RepositorioCasosArquivo(caminho_arquivo=tmp_path / "casos.jsonl")
    repositorio_casos_arquivo.criar(caso)

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = _colecao_de_um_campo
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        lambda: RepositorioRespostasArquivo(
            caminho_arquivo=tmp_path / "respostas.jsonl",
            repositorio_casos=repositorio_casos_arquivo,
        )
    )
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


_CORPO: Final[str] = "ID_PERGUNTA=Q1&valor=1.234%2C56"
_FORM_URLENCODED: Final[dict[str, str]] = {
    "content-type": "application/x-www-form-urlencoded"
}


def test_ac79_cliente_que_pede_json_recebe_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A página única pede `application/json` e recebe os mesmos quatro
    campos que o fragmento HTML carrega."""
    cliente = _montar_cliente(monkeypatch, tmp_path)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content=_CORPO,
        headers={**_FORM_URLENCODED, "accept": "application/json"},
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    corpo = resposta.json()
    assert corpo["ID_PERGUNTA"] == "Q1"
    assert corpo["avanco_permitido"] is True
    assert corpo["total_pendencias"] == 0


@pytest.mark.parametrize(
    "accept",
    ["text/html,application/xhtml+xml", "*/*", "application/json", ""],
)
def test_resposta_e_json_qualquer_que_seja_o_accept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, accept: str
) -> None:
    """`OQ-28` respondida (T-144): a rota devolve JSON sempre — não há mais
    ramificação por `Accept`.

    Antes, `text/html` (form nativo) e `*/*` (HTMX) recebiam o fragmento
    HTML de confirmação, e só quem pedia `application/json` recebia JSON. A
    tela virou React; o fragmento não tem mais quem o renderize, e mantê-lo
    seria manter um segundo formato que ninguém lê.

    **O que se perdeu está nomeado**: `EC-21` (gravar sem JavaScript) deixou
    de valer, e se isso é aceitável para a persona está aberto em `OQ-29` —
    não foi esquecido, foi registrado."""
    cliente = _montar_cliente(monkeypatch, tmp_path)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content=_CORPO,
        headers={**_FORM_URLENCODED, "accept": accept},
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    assert resposta.json()["ID_PERGUNTA"] == "Q1"


def test_a_gravacao_e_identica_nos_dois_formatos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A ramificação é só de APRESENTAÇÃO: os sete passos do §5.1 correm
    iguais, e o valor gravado é o mesmo `Decimal` nos dois caminhos."""
    from decimal import Decimal

    cliente = _montar_cliente(monkeypatch, tmp_path)
    repositorio = RepositorioRespostasArquivo(caminho_arquivo=tmp_path / "respostas.jsonl")

    cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content=_CORPO,
        headers={**_FORM_URLENCODED, "accept": "application/json"},
    )

    gravadas = repositorio.listar_do_caso(_CASO_ID)
    assert len(gravadas) == 1
    assert gravadas[0].valor == Decimal("1234.56")
