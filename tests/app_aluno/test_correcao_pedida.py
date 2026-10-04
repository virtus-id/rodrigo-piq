"""`AC-175` — "Pedir correção" devolve o plano ao aluno (`RF-113`, `T-333`,
revisa `EC-12`).

O fluxo inteiro pelas rotas reais, com a coleção real e dublês de
repositório (arquivo/memória): cálculo → conferência pede correção → Início
do aluno com a mensagem e os dados a conferir → reenvio → fila com a versão 2.
O perfil é o T02 de `test_plano_ponta_a_ponta.py`, com a primeira dívida
trocada por um cheque especial da CAIXA de taxa desconhecida — a pendência
de homologação de `RF-93` que o revisor pede para o aluno informar.

REGRAS: `RF-113`, `AC-175`, `EC-12`
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_papel_revisor, obter_repositorio_casos
from app.http.rotas_calculo import (
    obter_colecao_de_registros,
    obter_fonte_parametros,
    obter_parametros_externos_do_bloco6,
    obter_repositorio_eventos,
    obter_repositorio_itens,
    obter_repositorio_respostas,
    obter_repositorio_snapshots,
)
from app.http.rotas_inicio import (
    obter_colecao_de_registros_do_inicio,
    obter_repositorio_itens_do_inicio,
    obter_repositorio_respostas_do_inicio,
    obter_repositorio_revisoes_do_inicio,
)
from app.http.rotas_plano import obter_repositorio_snapshots as obter_repositorio_snapshots_do_aluno
from app.http.rotas_revisao import (
    obter_colecao_de_registros_da_revisao,
    obter_repositorio_casos_da_fila,
    obter_repositorio_eventos_da_decisao,
    obter_repositorio_itens_da_revisao,
    obter_repositorio_respostas_da_revisao,
    obter_repositorio_revisoes_da_decisao,
    obter_repositorio_snapshots_da_fila,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem.conversao import converter_para_dinheiro, converter_para_taxa
from app.revisao.fila import DECISAO_REVISAO, RegistroRevisao
from collection.carga import carregar_registros
from collection.respostas import Resposta, ValorResposta
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import (
    CASO_ID,
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)
from tests.app_aluno.test_plano_ponta_a_ponta import _T02_CASO, _T02_D001, _T02_D002, _itens
from tests.app_aluno.test_rotas_calculo import (
    _ParametrosExternosFabricados,
    _RepositorioItensDublê,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ALUNO = "CONTA-ALUNO-T333"
_REVISOR = "conta-revisor-t333"
_MENSAGEM = "Informe a taxa do cheque especial"
_OBSERVACAO = "OBS-INTERNA-taxa-zerada-no-motor"

_D001_CHEQUE_SEM_TAXA: dict[str, object] = {
    **{k: v for k, v in _T02_D001.items() if k not in ("TAXA_INFORMADA", "PERIODICIDADE_TAXA")},
    "TIPO_DIVIDA": "CHEQUE_ESPECIAL",
    "CREDOR": "CAIXA ECONOMICA FEDERAL",
    "LINHA_CONTINUA_SENDO_UTILIZADA": "NAO",
    "QUALIDADE_TAXA_INFORMADA": "DESCONHECIDA",
}


def _respostas() -> list[Resposta]:
    base = caso_completo(
        valores_caso={
            **_T02_CASO,
            "TIPOS_DIVIDA_DECLARADOS": frozenset({"CHEQUE_ESPECIAL", "PESSOAL"}),
        },
        valores_divida=_D001_CHEQUE_SEM_TAXA,
        valores_item_despesa={"VALOR_DESPESA": converter_para_dinheiro("3.500,00")},
        valores_despesa_nao_mensal={
            "VALOR_DESPESA_NAO_MENSAL": converter_para_dinheiro("1.200,00")
        },
        DIVIDA_ID="D001",
    ).respostas.respostas
    d002 = tuple(
        r
        for r in montar_respostas_caso(valores_divida=_T02_D002, DIVIDA_ID="D002").respostas
        if r.item_id == "D002"
    )
    return [*base, *d002]


class _Respostas:
    """Dublê mutável: o teste corrige a resposta entre a devolução e o
    reenvio, como o aluno faria pela rota de correção (`RF-69`)."""

    def __init__(self) -> None:
        self.respostas = _respostas()

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(self.respostas)

    def corrigir_no_item(self, item_id: str, valores: dict[str, ValorResposta]) -> None:
        mantidas = [
            r for r in self.respostas if not (r.item_id == item_id and r.ID_PERGUNTA in valores)
        ]
        modelo = next(r for r in self.respostas if r.item_id == item_id)
        self.respostas = mantidas + [
            Resposta(
                CASO_ID=modelo.CASO_ID,
                ID_PERGUNTA=variavel,
                item_id=item_id,
                valor=valor,
                QUESTIONARIO_VERSION=modelo.QUESTIONARIO_VERSION,
                respondida_em=modelo.respondida_em,
            )
            for variavel, valor in valores.items()
        ]


class _Revisoes:
    """Dublê em memória de `RepositorioRevisoes` — `gravar` e
    `listar_do_caso`, append-only."""

    def __init__(self) -> None:
        self.registros: list[RegistroRevisao] = []

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        self.registros.append(registro)

    def obter(self, revisao_id: str) -> RegistroRevisao | None:  # pragma: no cover
        return None

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroRevisao, ...]:
        return tuple(r for r in self.registros if r.CASO_ID == caso_id)


def _caso(casos: RepositorioCasosArquivo) -> Caso:
    caso = casos.buscar(CASO_ID)
    assert caso is not None
    return caso


def _esperar_sair_de_calculando(casos: RepositorioCasosArquivo) -> Caso:
    # ponytail: polling — o cálculo roda numa asyncio.Task do TestClient.
    prazo = time.monotonic() + 30
    while time.monotonic() < prazo:
        caso = casos.buscar(CASO_ID)
        assert caso is not None
        if caso.estado is not ESTADO_CASO.CALCULANDO:
            return caso
        time.sleep(0.05)
    raise AssertionError("caso ficou em CALCULANDO")


type Cenario = tuple[
    TestClient, RepositorioCasosArquivo, RepositorioSnapshotsArquivo, _Respostas, _Revisoes
]


@pytest.fixture
def cenario(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Cenario:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", "1.0.1")
    casos = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    casos.criar(
        Caso(
            CASO_ID=CASO_ID,
            conta_id=_CONTA_ALUNO,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    snapshots = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
    eventos = RepositorioEventosCasoArquivo(tmp_path / "eventos.jsonl")
    respostas = _Respostas()
    revisoes = _Revisoes()
    colecao = carregar_registros()

    def itens() -> _RepositorioItensDublê:
        return _RepositorioItensDublê(_itens(("D001", "D002")))

    aplicacao = criar_aplicacao()
    sobrescritas: dict[Callable[..., Any], Callable[..., Any]] = {
        obter_repositorio_casos: lambda: casos,
        obter_repositorio_casos_da_fila: lambda: casos,
        obter_colecao_de_registros: lambda: colecao,
        obter_colecao_de_registros_do_inicio: lambda: colecao,
        obter_colecao_de_registros_da_revisao: lambda: colecao,
        obter_repositorio_respostas: lambda: respostas,
        obter_repositorio_respostas_do_inicio: lambda: respostas,
        obter_repositorio_respostas_da_revisao: lambda: respostas,
        obter_repositorio_itens: itens,
        obter_repositorio_itens_do_inicio: itens,
        obter_repositorio_itens_da_revisao: itens,
        obter_repositorio_snapshots: lambda: snapshots,
        obter_repositorio_snapshots_do_aluno: lambda: snapshots,
        obter_repositorio_snapshots_da_fila: lambda: snapshots,
        obter_repositorio_eventos: lambda: eventos,
        obter_repositorio_eventos_da_decisao: lambda: eventos,
        obter_repositorio_revisoes_da_decisao: lambda: revisoes,
        obter_repositorio_revisoes_do_inicio: lambda: revisoes,
        obter_fonte_parametros: FonteParametrosArquivo,
        obter_parametros_externos_do_bloco6: _ParametrosExternosFabricados,
        exigir_papel_revisor: lambda: _REVISOR,
    }
    aplicacao.dependency_overrides.update(sobrescritas)

    @aplicacao.post("/_teste/abrir-sessao")
    def abrir_sessao(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=_CONTA_ALUNO)
        return {"ok": "ok"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/abrir-sessao")
    return cliente, casos, snapshots, respostas, revisoes


def _decidir(cliente: TestClient, corpo: str) -> Any:
    return cliente.post(
        f"/revisao/caso/{CASO_ID}/decisao",
        content=corpo,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


def test_ac175_pedir_correcao_devolve_ao_aluno_e_reenvio_volta_a_fila_como_v2(
    cenario: Cenario,
) -> None:
    cliente, casos, snapshots, respostas, revisoes = cenario
    with cliente:  # mantém o loop vivo para a asyncio.Task do cálculo
        assert cliente.post(f"/caso/{CASO_ID}/calculo").status_code == 200
        caso = _esperar_sair_de_calculando(casos)
        assert caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO
        assert caso.snapshot_raiz_id is not None
        (v1,) = snapshots.historico(caso.snapshot_raiz_id)

        # 1. Sem mensagem ao aluno: recusado, nada gravado, caso intacto.
        recusa = _decidir(cliente, f"decisao=REPROVAR&observacao={_OBSERVACAO}&mensagem_aluno=+")
        assert recusa.status_code == 422
        assert recusa.json()["detail"] == "Escreva a mensagem para o aluno."
        assert revisoes.registros == []
        assert _caso(casos).estado is ESTADO_CASO.AGUARDANDO_REVISAO

        # 2. Com a mensagem: reprovação registrada, snapshot intacto, coleta.
        resposta = _decidir(
            cliente,
            f"decisao=REPROVAR&observacao={_OBSERVACAO}"
            f"&mensagem_aluno={_MENSAGEM.replace(' ', '+')}",
        )
        assert resposta.status_code == 200
        (registro,) = revisoes.registros
        assert registro.decisao is DECISAO_REVISAO.REPROVADO
        assert registro.autor == _REVISOR
        assert registro.decidido_em is not None
        assert registro.mensagem_aluno == _MENSAGEM
        assert registro.observacao == _OBSERVACAO
        assert registro.SNAPSHOT_ID == v1.SNAPSHOT_ID
        caso = _caso(casos)
        assert caso.estado is ESTADO_CASO.COLETA_INICIAL
        assert caso.snapshot_liberado_id is None
        assert caso.snapshot_raiz_id is not None
        assert snapshots.historico(caso.snapshot_raiz_id) == (v1,)
        assert len(respostas.respostas) == len(_respostas())

        # 3. Início: mensagem, dados a conferir com nome e link, reenvio.
        inicio = cliente.get(f"/caso/{CASO_ID}/inicio")
        assert inicio.status_code == 200
        corpo = inicio.json()
        assert corpo["fase"] == "coleta"
        assert "revisão" not in corpo["mensagem"]
        assert corpo["correcao_pedida"] == {
            "mensagem": _MENSAGEM,
            "dados_a_conferir": [
                {
                    "nome": "Cheque especial (CAIXA ECONOMICA FEDERAL)",
                    "enunciado": "Você sabe qual é a taxa de juros desta operação?",
                    "ID_PERGUNTA": "B5.D01",
                    "item_id": "D001",
                }
            ],
        }
        # A observação interna nunca chega ao aluno.
        for rota in ("inicio", "calculo/progresso", "api/plano"):
            assert _OBSERVACAO not in cliente.get(f"/caso/{CASO_ID}/{rota}").text

        # 4. O aluno informa a taxa (RF-69): a lista esvazia, o aviso fica.
        respostas.corrigir_no_item(
            "D001",
            {
                "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
                "TAXA_INFORMADA": converter_para_taxa("8"),
                "PERIODICIDADE_TAXA": "MENSAL",
            },
        )
        corpo = cliente.get(f"/caso/{CASO_ID}/inicio").json()
        assert corpo["correcao_pedida"]["dados_a_conferir"] == []
        assert corpo["correcao_pedida"]["mensagem"] == _MENSAGEM

        # 5. "Enviar para nova conferência": recalcula e volta à fila em v2.
        assert cliente.post(f"/caso/{CASO_ID}/calculo").status_code == 200
        caso = _esperar_sair_de_calculando(casos)
        assert caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO
        assert caso.snapshot_raiz_id is not None
        historico = snapshots.historico(caso.snapshot_raiz_id)
        assert [s.versao for s in historico] == [1, 2]
        assert historico[0] == v1
        assert historico[1].snapshot_anterior_id == v1.SNAPSHOT_ID
        conferencia = cliente.get(f"/revisao/caso/{CASO_ID}/decisao").json()
        assert conferencia["versao"] == 2

        # Fora da correção pedida, o aviso some.
        assert cliente.get(f"/caso/{CASO_ID}/inicio").json()["correcao_pedida"] is None


def test_observacao_interna_nao_e_lida_por_nenhuma_rota_de_aluno() -> None:
    """`AC-175`: a `observacao` só é lida pela rota do revisor — nenhum outro
    módulo de `app/http/` acessa o atributo."""
    raiz = Path(__file__).resolve().parents[2] / "app" / "http"
    leitores = [
        caminho.name
        for caminho in raiz.glob("*.py")
        if re.search(r"\.observacao\b", caminho.read_text(encoding="utf-8"))
    ]
    assert leitores == []
