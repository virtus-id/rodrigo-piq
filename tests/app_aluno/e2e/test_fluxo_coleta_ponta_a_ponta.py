"""O fluxo da coleta ponta a ponta — `RF-45` a `RF-49` (Rodada 3).

**O que este teste prova, e por que ele não existia antes.** Até `T-123`, o
aluno cadastrava, consentia e **não alcançava pergunta nenhuma**: não havia
rota `GET` que dissesse qual pergunta responder. Este teste percorre o
caminho inteiro numa única sessão HTTP:

    abrir sessão → GET pergunta → responder (máscara) → GET próxima
                 → responder "não sei" → GET → coleta completa

Cada passo afirma sobre a resposta HTTP REAL da aplicação montada por
`criar_aplicacao()`, com os roteadores de produção — não sobre funções
isoladas.

**Por que `TestClient` e não um navegador.** Não há Playwright, Selenium nem
Chromium neste projeto, e o plano fechou a rodada em zero dependência nova
(`plans/app-aluno.plan.md` §2). `docs/checklist-acessibilidade.md` já
registra essa limitação para `T-48`/`T-97` e reserva a verificação visual
(zoom real, leitor de tela, 360 px num navegador de verdade) para a revisão
manual. Este teste cobre o que dá para cobrir sem navegador: o contrato
HTTP, a gravação, o estado do caso e o HTML produzido. O que ele **não**
cobre, e continua pendente de verificação manual: a execução de
`mascaras.js` dentro de um navegador.

REGRAS: `RF-45`, `RF-46`, `RF-47`, `RF-48`, `RF-49`
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
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
from collection.respostas import NAO_SEI
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import Caso

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID: Final[str] = "CONTA-E2E-1"
_CASO_ID: Final[str] = "CASO-E2E-1"
_FORM: Final[dict[str, str]] = {"content-type": "application/x-www-form-urlencoded"}


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


def _campo(
    identificador: str,
    variavel: str,
    tipo: TipoResposta,
    *,
    admite_nao_sei: bool = False,
) -> RegistroPergunta:
    return RegistroPergunta(
        ID=identificador,
        bloco=5,
        enunciado=f"Campo {identificador}",
        tipo=tipo,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=(),
        VARIAVEL_GRAVADA=variavel,
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=admite_nao_sei,
        salto_consequencia=None,
    )


def _colecao() -> ColecaoDeRegistros:
    """Dois campos: um `MOEDA` (máscara) e um que admite "não sei"."""
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _campo("Q_SALDO", "SALDO_DEVEDOR_ATUAL", TipoResposta.MOEDA),
            _campo("Q_TAXA", "TAXA_JUROS", TipoResposta.TAXA, admite_nao_sei=True),
        ),
    )


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
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
    casos_arquivo = RepositorioCasosArquivo(caminho_arquivo=tmp_path / "casos.jsonl")
    casos_arquivo.criar(caso)
    respostas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl", repositorio_casos=casos_arquivo
    )

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        caso, _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = _colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: RepositorioItensArquivo(
        caminho_arquivo=tmp_path / "itens.jsonl"
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    http = TestClient(aplicacao, base_url="https://teste.local")
    http.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    http.respostas = respostas  # type: ignore[attr-defined]
    return http


def test_fluxo_completo_da_coleta(cliente: TestClient) -> None:
    """O percurso inteiro, na ordem em que o aluno o vive."""
    # 1. O aluno abre o app e ALCANÇA uma pergunta — o passo que não existia.
    primeira = cliente.get(f"/caso/{_CASO_ID}/pergunta")
    assert primeira.status_code == 200
    assert primeira.json()["pergunta"]["ID"] == "Q_SALDO"

    # 2. O tipo chega ao cliente, que é o que decide a máscara a aplicar.
    #    A casca de página e os estáticos saíram daqui com T-144: quem serve
    #    a tela é o React, e o carregamento do bundle/máscara é auditado em
    #    `frontend/tests/` (unitário) e `frontend/tests/e2e/` (navegador
    #    real). O que continua sendo responsabilidade DESTA rota é dizer o
    #    tipo — sem ele o cliente não teria como escolher a máscara.
    assert primeira.json()["pergunta"]["tipo"] == "MOEDA"

    # 4. Responde no formato que a máscara emite — "1.234,56" (AC-75).
    gravou = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content="ID_PERGUNTA=Q_SALDO&valor=1.234%2C56",
        headers=_FORM,
    )
    assert gravou.status_code == 200

    respostas = cliente.respostas  # type: ignore[attr-defined]
    saldo = respostas.listar_do_caso(_CASO_ID)[0]
    assert saldo.valor == Decimal("1234.56")

    # 5. A próxima pergunta é a seguinte — nada já respondido reaparece.
    segunda = cliente.get(f"/caso/{_CASO_ID}/pergunta")
    assert segunda.json()["pergunta"]["ID"] == "Q_TAXA"
    assert "Q_SALDO" not in segunda.text

    # 6. "não sei" é resposta de primeira classe (RF-11/RF-48).
    nao_sei = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content="ID_PERGUNTA=Q_TAXA&nao_sei=on",
        headers=_FORM,
    )
    assert nao_sei.status_code == 200

    gravadas = {r.ID_PERGUNTA: r.valor for r in respostas.listar_do_caso(_CASO_ID)}
    assert gravadas["TAXA_JUROS"] is NAO_SEI
    assert gravadas["TAXA_JUROS"] != Decimal(0)

    # 7. Sem pendência, a coleta se declara completa — nunca uma pergunta
    #    arbitrária, nunca 500 (EC-23).
    fim = cliente.get(f"/caso/{_CASO_ID}/pergunta")
    assert fim.status_code == 200
    assert fim.json()["coleta_completa"] is True


def test_entrada_ambigua_nao_grava_nada(cliente: TestClient) -> None:
    """`AC-77`/`EC-01`: a máscara não "salva" o ambíguo — ele chega como
    digitado, o servidor recusa e **nada** é gravado. Nenhuma coerção a 0."""
    recusada = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        content="ID_PERGUNTA=Q_SALDO&valor=1.2%2C3",
        headers=_FORM,
    )

    assert recusada.status_code == 400
    respostas = cliente.respostas  # type: ignore[attr-defined]
    assert respostas.listar_do_caso(_CASO_ID) == ()


def test_o_cliente_nunca_recebe_o_grafo_condicional(cliente: TestClient) -> None:
    """`RF-45`/`RF-52`: o que o cliente recebe não carrega `condicao_exibicao`
    nem meio de avaliá-la — quem decide qual pergunta exibir é o servidor.

    `VARIAVEL_GRAVADA` (o nome interno do campo gravado) também não vai: o
    cliente identifica a pergunta por `ID` e manda `ID_PERGUNTA` de volta;
    quem resolve para qual variável aquilo grava é o servidor."""
    pagina = cliente.get(f"/caso/{_CASO_ID}/pergunta")

    assert "condicao_exibicao" not in pagina.text
    assert "VARIAVEL_GRAVADA" not in pagina.text
