"""`AC-181`, `AC-182`, `AC-183` — o aluno pede um plano novo depois da
liberação (`RF-118`, `RF-119`, `T-341`).

O fluxo inteiro pelas rotas reais (a mesma montagem de `test_correcao_pedida.py`,
`AC-175`): cálculo → liberação → pedido de plano novo → correção de uma taxa →
reenvio → v2 na fila, com a v1 intacta.

REGRAS: `RF-118`, `RF-119`, `AC-181`, `AC-182`, `AC-183`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.casos.maquina import ESTADO_CASO
from app.http.rotas_calculo import (
    obter_colecao_de_registros as calculo_colecao,
)
from app.http.rotas_calculo import (
    obter_repositorio_eventos,
)
from app.http.rotas_calculo import (
    obter_repositorio_itens as calculo_itens,
)
from app.http.rotas_calculo import (
    obter_repositorio_respostas as calculo_respostas,
)
from app.http.rotas_coleta import (
    obter_colecao_de_registros as coleta_colecao,
)
from app.http.rotas_coleta import (
    obter_repositorio_itens as coleta_itens,
)
from app.http.rotas_coleta import (
    obter_repositorio_respostas as coleta_respostas,
)
from app.http.rotas_plano import obter_contas_dos_casos
from app.http.rotas_respostas import obter_repositorio_eventos_da_retomada
from app.montagem.conversao import converter_para_taxa
from app.revisao.fila import liberar
from engine.estado import Divida
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo
from tests.app_aluno.fixtures.caso_completo import CASO_ID
from tests.app_aluno.test_correcao_pedida import (
    Cenario,
    _caso,
    _esperar_sair_de_calculando,
    cenario,  # noqa: F401 — fixture reutilizada
)

_MENSAGEM_NAO_LIBERADO = "Seu plano ainda não foi liberado."


class _SemContas:
    def contas_dos_casos(self, caso_ids: tuple[str, ...]) -> dict[str, Any]:
        return {}


@pytest.fixture(autouse=True)
def _trilha_da_retomada(cenario: Cenario) -> None:  # noqa: F811
    """A rota grava o evento pela dependência da retomada; aqui ela aponta para a
    MESMA trilha em arquivo que o resto do cenário usa."""
    aplicacao: Any = cenario[0].app
    sobrescritas = aplicacao.dependency_overrides
    sobrescritas[obter_repositorio_eventos_da_retomada] = sobrescritas[obter_repositorio_eventos]
    # `GET /respostas` lê pelas dependências de `rotas_coleta`; o cenário sobrescreve
    # as de `rotas_calculo` — as mesmas instâncias, com outro nome de injeção.
    # O plano chama o aluno pelo nome (conta); aqui não há banco — sem nome.
    sobrescritas[obter_contas_dos_casos] = lambda: _SemContas()
    for da_coleta, do_calculo in (
        (coleta_respostas, calculo_respostas),
        (coleta_itens, calculo_itens),
        (coleta_colecao, calculo_colecao),
    ):
        sobrescritas[da_coleta] = sobrescritas[do_calculo]


def _liberar_v1(cliente: Any, casos: RepositorioCasosArquivo, cenario_: Cenario) -> None:
    """Calcula a v1 e a libera pela função de domínio (sem pendência de homologação:
    o que se prova aqui é o fluxo do aluno, não a homologação — `T-264`)."""
    _, _, snapshots, _, revisoes = cenario_
    aplicacao: Any = cliente.app
    assert cliente.post(f"/caso/{CASO_ID}/calculo").status_code == 200
    caso = _esperar_sair_de_calculando(casos)
    assert caso.snapshot_raiz_id is not None
    (v1,) = snapshots.historico(caso.snapshot_raiz_id)
    liberar(
        revisao_id="REVISAO-T341",
        caso_id=CASO_ID,
        snapshot=v1,
        autor="revisor-t341",
        decidido_em=datetime(2026, 10, 5, tzinfo=UTC),
        repositorio_revisoes=revisoes,
        repositorio_casos=casos,
        repositorio_eventos=aplicacao.dependency_overrides[obter_repositorio_eventos](),
        pendencias_homologacao=(),
    )


def _taxa_da_divida(snapshot: Any, divida_id: str) -> Any:
    divida: Divida = next(d for d in snapshot.estado_inputs.dividas if d.DIVIDA_ID == divida_id)
    return divida.TAXA_EFETIVA_MENSAL_NORMALIZADA


def test_ac181_e_ac183_plano_novo_depois_da_liberacao_reflete_a_resposta_editada(
    cenario: Cenario,  # noqa: F811
) -> None:
    cliente, casos, snapshots, respostas, _ = cenario
    with cliente:
        _liberar_v1(cliente, casos, cenario)
        liberado = _caso(casos)
        assert liberado.estado is ESTADO_CASO.PLANO_LIBERADO
        assert liberado.snapshot_liberado_id is not None
        raiz = liberado.snapshot_raiz_id
        assert raiz is not None
        (v1,) = snapshots.historico(raiz)
        taxa_v1 = _taxa_da_divida(v1, "D001")

        # `AC-181`: a lista diz que dá para pedir o plano novo.
        assert cliente.get(f"/caso/{CASO_ID}/respostas").json()["pode_refazer_plano"] is True

        # O aluno corrige a taxa DEPOIS da liberação: o dado muda, o plano não.
        respostas.corrigir_no_item(
            "D001",
            {
                "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
                "TAXA_INFORMADA": converter_para_taxa("8"),
                "PERIODICIDADE_TAXA": "MENSAL",
            },
        )
        assert snapshots.historico(raiz) == (v1,), "editar a resposta não gera plano"

        # Pede o plano novo: coleta, plano liberado intacto e ainda servido.
        pedido = cliente.post(f"/caso/{CASO_ID}/refazer-plano")
        assert pedido.status_code == 200
        assert pedido.json()["estado"] == "COLETA_INICIAL"
        caso = _caso(casos)
        assert caso.estado is ESTADO_CASO.COLETA_INICIAL
        assert caso.snapshot_liberado_id == liberado.snapshot_liberado_id
        assert caso.snapshot_raiz_id == raiz
        inicio = cliente.get(f"/caso/{CASO_ID}/inicio").json()
        assert inicio["plano_liberado"] is True, "o aluno segue vendo o plano atual"
        assert cliente.get(f"/caso/{CASO_ID}/api/plano").status_code == 200

        # `AC-183`: o reenvio é o cálculo de sempre; a v2 nasce encadeada, com a taxa nova.
        assert cliente.post(f"/caso/{CASO_ID}/calculo").status_code == 200
        caso = _esperar_sair_de_calculando(casos)
        assert caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO
        historico = snapshots.historico(raiz)
        assert [s.versao for s in historico] == [1, 2]
        assert historico[0] == v1, "a v1 continua exatamente como estava"
        assert historico[1].snapshot_anterior_id == v1.SNAPSHOT_ID
        assert _taxa_da_divida(historico[0], "D001") == taxa_v1
        assert _taxa_da_divida(historico[1], "D001") == converter_para_taxa("8")
        assert _taxa_da_divida(historico[1], "D001") != taxa_v1
        # A v1 segue sendo o plano liberado até a v2 ser liberada (`OQ-09`).
        assert caso.snapshot_liberado_id == liberado.snapshot_liberado_id


@pytest.mark.parametrize(
    "estado", [ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.CALCULANDO, ESTADO_CASO.AGUARDANDO_REVISAO]
)
def test_ac182_antes_da_liberacao_pedir_plano_novo_e_recusado(
    cenario: Cenario,  # noqa: F811
    estado: ESTADO_CASO,
) -> None:
    cliente, casos, _, _, _ = cenario
    with cliente:
        if estado is not ESTADO_CASO.COLETA_INICIAL:
            casos.transicionar_estado(CASO_ID, ESTADO_CASO.CALCULANDO)
            if estado is ESTADO_CASO.AGUARDANDO_REVISAO:
                casos.transicionar_estado(CASO_ID, ESTADO_CASO.AGUARDANDO_REVISAO)

        resposta = cliente.post(f"/caso/{CASO_ID}/refazer-plano")

        assert resposta.status_code == 409
        assert resposta.json()["erro"] == _MENSAGEM_NAO_LIBERADO
        assert _caso(casos).estado is estado
        assert cliente.get(f"/caso/{CASO_ID}/respostas").json()["pode_refazer_plano"] is False


def test_ac181_de_acompanhamento_tambem_pode_refazer(cenario: Cenario) -> None:  # noqa: F811
    cliente, casos, _, _, _ = cenario
    with cliente:
        for destino in (
            ESTADO_CASO.CALCULANDO,
            ESTADO_CASO.AGUARDANDO_REVISAO,
            ESTADO_CASO.PLANO_LIBERADO,
            ESTADO_CASO.ACOMPANHAMENTO,
        ):
            casos.transicionar_estado(CASO_ID, destino)

        assert cliente.get(f"/caso/{CASO_ID}/respostas").json()["pode_refazer_plano"] is True
        assert cliente.post(f"/caso/{CASO_ID}/refazer-plano").status_code == 200
        assert _caso(casos).estado is ESTADO_CASO.COLETA_INICIAL
