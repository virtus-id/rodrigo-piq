"""Testes de `collection/interpolacao.py` — RF-06, AC-05, AC-42 (T-12).

Cobre `interpolar` pelo comportamento observável (o texto final do
enunciado), nunca por implementação interna. A origem `CAMPO_DO_SNAPSHOT` é
testada contra um `SnapshotOrdem` REAL, produzido pela mesma cadeia do motor
já validada por `tests/regras/test_snapshot.py` (T-67) sobre `GAB-C` — nunca
um `SnapshotOrdem` fabricado à mão, para que o teste prove que a origem lê o
snapshot de verdade, e não um dublê que finge sua forma.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from collection.interpolacao import (
    ContextoItem,
    ErroInterpolacao,
    Marcador,
    interpolar,
)
from engine.beneficio_marginal import BeneficioMarginal
from engine.ciclo_mensal import simular_cenario
from engine.comparacao import comparar_cenarios
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.gates import particionar_elegibilidade
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido
from engine.ordem import consolidar_ORDEM_STATUS, publicar_ORDEM_QUITACAO
from engine.precisao import quantizar_exibicao
from engine.snapshot import SnapshotOrdem, montar_SnapshotOrdem
from engine.status_metodo import derivar_METODO_RECOMENDADO_PIQ
from engine.tipos import DESCONHECIDO, METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/regras/test_snapshot.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.fixture(scope="module")
def _snapshot_gab_c() -> SnapshotOrdem:
    """Roda a cadeia real do motor sobre `GAB-C` e monta o `SnapshotOrdem`
    final — mesma orquestração de `tests/regras/test_snapshot.py::
    _montar_snapshot_gab_c`, reproduzida aqui para não acoplar este teste a
    um módulo de outra suíte."""
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    dividas = _inventario(estado)
    diagnostico = calcular_diagnostico(estado, parametros)

    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, parametros)
    cenario_avalanche = simular_cenario(estado, diagnostico, dividas, sel_avalanche, parametros)

    sel_bola_de_neve = criar_selecionar_alvo_bola_de_neve(dividas, parametros)
    cenario_bola_de_neve = simular_cenario(
        estado, diagnostico, dividas, sel_bola_de_neve, parametros
    )

    resultado_hibrido = criar_selecionar_alvo_hibrido(estado, dividas, diagnostico, parametros)
    assert resultado_hibrido.selecionar_alvo is not None
    cenario_hibrido = simular_cenario(
        estado, diagnostico, dividas, resultado_hibrido.selecionar_alvo, parametros
    )

    cenarios_rotulados = (
        dataclasses.replace(cenario_avalanche, metodo=METODO.AVALANCHE),
        dataclasses.replace(cenario_bola_de_neve, metodo=METODO.BOLA_DE_NEVE),
        dataclasses.replace(cenario_hibrido, metodo=METODO.HIBRIDO),
    )
    cenarios_por_metodo = {c.metodo: c for c in cenarios_rotulados if c.metodo is not None}

    comparacao = comparar_cenarios(cenarios_rotulados, parametros)

    resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
        cenarios_por_metodo,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=diagnostico.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
        INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
        parametros=parametros,
    )

    cenario_recomendado = cenarios_por_metodo[resultado_recomendacao.METODO_RECOMENDADO_PIQ]
    particao = particionar_elegibilidade(estado.dividas)
    ordem_publicada = publicar_ORDEM_QUITACAO(
        cenario_recomendado, resultado_recomendacao.METODO_RECOMENDADO_PIQ, dividas, particao
    )

    beneficios_marginais = {
        posicao.DIVIDA_ID: BeneficioMarginal(
            DIVIDA_ID=posicao.DIVIDA_ID,
            DELTA_TESTE_AVALANCHE=dividas[posicao.DIVIDA_ID].SALDO_DEVEDOR_ATUAL,  # type: ignore[arg-type]
            DELTA_REALMENTE_APLICADO=dividas[posicao.DIVIDA_ID].SALDO_DEVEDOR_ATUAL,  # type: ignore[arg-type]
            DESEMBOLSO_FUTURO_SEM_DELTA=dividas[posicao.DIVIDA_ID].SALDO_DEVEDOR_ATUAL,  # type: ignore[arg-type]
            DESEMBOLSO_FUTURO_COM_DELTA=dividas[posicao.DIVIDA_ID].SALDO_DEVEDOR_ATUAL,  # type: ignore[arg-type]
            BENEFICIO_MARGINAL_AMORTIZACAO=dividas[posicao.DIVIDA_ID].SALDO_DEVEDOR_ATUAL,
            origem="SIMULACAO",
        )
        for posicao in ordem_publicada.ORDEM_QUITACAO
    }
    resultado_status = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
        beneficios_marginais=beneficios_marginais,
    )

    return montar_SnapshotOrdem(
        estado=estado,
        parametros=parametros,
        diagnostico=diagnostico,
        cenarios=cenarios_por_metodo,
        comparacao=comparacao,
        resultado_metodo=resultado_recomendacao,
        ordem_status=resultado_status.ORDEM_STATUS,
        ordem_publicada=ordem_publicada,
        evento=None,
        motivo="",
    )


class _RespostasDeTeste:
    """Dublê mínimo de `Respostas` (`Protocol`), sem depender de
    `collection/respostas.py` (T-22, ainda não implementada) — mesmo padrão
    de `tests/app_aluno/test_condicoes.py::_RespostasDeTeste`."""

    def __init__(self, valores: dict[str, object] | None = None) -> None:
        self._valores = valores or {}

    def valor(self, variavel: str) -> object | None:
        return self._valores.get(variavel)


def _contexto(
    *,
    item_id: str | None = None,
    respostas: _RespostasDeTeste | None = None,
    snapshot: SnapshotOrdem | None = None,
) -> ContextoItem:
    return ContextoItem(
        item_id=item_id, respostas=respostas or _RespostasDeTeste(), snapshot=snapshot
    )


def test_ac05_id_do_item_substitui_marcador_pelo_identificador_do_item_corrente() -> None:
    """AC-05: `B11.Q01` para a dívida `D003` exibe `D003` no lugar de
    `[Dxxx]`."""
    marcador = Marcador(marcador="[Dxxx]", origem="ID_DO_ITEM", referencia="")
    enunciado = "A dívida [Dxxx] foi efetivamente quitada?"

    resultado = interpolar(enunciado, (marcador,), _contexto(item_id="D003"))

    assert resultado == "A dívida D003 foi efetivamente quitada?"


def test_id_do_item_sem_item_corrente_levanta_erro_explicito() -> None:
    marcador = Marcador(marcador="[Dxxx]", origem="ID_DO_ITEM", referencia="")

    with pytest.raises(ErroInterpolacao):
        interpolar("A dívida [Dxxx] foi quitada?", (marcador,), _contexto(item_id=None))


def test_variavel_coletada_substitui_pelo_valor_ja_respondido() -> None:
    marcador = Marcador(
        marcador="[PAGAMENTO]", origem="VARIAVEL_COLETADA", referencia="PAGAMENTO_MENSAL_EFETIVO"
    )
    respostas = _RespostasDeTeste({"PAGAMENTO_MENSAL_EFETIVO": "350,00"})

    resultado = interpolar(
        "Seu pagamento atual é [PAGAMENTO].", (marcador,), _contexto(respostas=respostas)
    )

    assert resultado == "Seu pagamento atual é 350,00."


def test_variavel_coletada_ausente_produz_erro_explicito_nunca_string_vazia() -> None:
    """Critério de aceite 4: marcador sem valor disponível produz erro
    explícito, nunca string vazia silenciosa."""
    marcador = Marcador(
        marcador="[PAGAMENTO]", origem="VARIAVEL_COLETADA", referencia="PAGAMENTO_MENSAL_EFETIVO"
    )

    with pytest.raises(ErroInterpolacao):
        interpolar("Seu pagamento é [PAGAMENTO].", (marcador,), _contexto())


def test_campo_do_snapshot_le_campo_direto_do_snapshot_sem_aritmetica(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    """Critério de aceite 2: origem `CAMPO_DO_SNAPSHOT` acessa o campo por
    NOME (aqui, um campo direto de `SnapshotOrdem`) — nunca aritmética."""
    marcador = Marcador(
        marcador="[METODO]", origem="CAMPO_DO_SNAPSHOT", referencia="METODO_RECOMENDADO_PIQ"
    )

    resultado = interpolar(
        "O método recomendado é [METODO].", (marcador,), _contexto(snapshot=_snapshot_gab_c)
    )

    assert resultado == f"O método recomendado é {_snapshot_gab_c.METODO_RECOMENDADO_PIQ}."


def test_campo_do_snapshot_navega_ate_o_campo_do_item_corrente_sem_recalcular(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    """`B11.Q06` mostra o `PAGAMENTO_MENSAL_EFETIVO` vigente (RF-06): o
    valor é LIDO da dívida do item corrente dentro de `estado_inputs`,
    nunca recomputado (AC-42)."""
    dividas_do_snapshot = {d.DIVIDA_ID: d for d in _snapshot_gab_c.estado_inputs.dividas}
    divida_id_qualquer = next(iter(dividas_do_snapshot))
    pagamento_esperado = dividas_do_snapshot[divida_id_qualquer].PAGAMENTO_MENSAL_EFETIVO
    assert pagamento_esperado is not DESCONHECIDO
    assert isinstance(pagamento_esperado, Decimal)

    marcador = Marcador(
        marcador="[PAGAMENTO]",
        origem="CAMPO_DO_SNAPSHOT",
        referencia="estado_inputs.dividas.PAGAMENTO_MENSAL_EFETIVO",
    )

    resultado = interpolar(
        "Pagamento vigente: [PAGAMENTO].",
        (marcador,),
        _contexto(item_id=divida_id_qualquer, snapshot=_snapshot_gab_c),
    )

    assert resultado == f"Pagamento vigente: {quantizar_exibicao(pagamento_esperado)}."


def test_campo_do_snapshot_monetario_passa_por_quantizar_exibicao(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    """Critério de aceite 3: valor monetário interpolado passa por
    `quantizar_exibicao` antes de virar texto (G-01) — o texto produzido
    pela interpolação é comparado com o resultado exato da própria função,
    nunca com uma conta reimplementada aqui.

    O caminho exercitado é o mesmo do teste de navegação por item corrente
    (`estado_inputs.dividas.PAGAMENTO_MENSAL_EFETIVO`), que já atravessa um
    `Decimal` real do snapshot — aqui o foco é a igualdade exata com
    `quantizar_exibicao`, não a navegação em si."""
    dividas_do_snapshot = {d.DIVIDA_ID: d for d in _snapshot_gab_c.estado_inputs.dividas}
    divida_id = next(iter(dividas_do_snapshot))
    saldo_devedor = dividas_do_snapshot[divida_id].SALDO_DEVEDOR_ATUAL
    assert saldo_devedor is not DESCONHECIDO
    assert isinstance(saldo_devedor, Decimal)

    marcador = Marcador(
        marcador="[SALDO]",
        origem="CAMPO_DO_SNAPSHOT",
        referencia="estado_inputs.dividas.SALDO_DEVEDOR_ATUAL",
    )

    resultado = interpolar(
        "Saldo devedor: [SALDO].",
        (marcador,),
        _contexto(item_id=divida_id, snapshot=_snapshot_gab_c),
    )

    assert resultado == f"Saldo devedor: {quantizar_exibicao(saldo_devedor)}."


def test_campo_do_snapshot_sem_snapshot_disponivel_produz_erro_explicito() -> None:
    """Critério de aceite 4: sem snapshot, nenhuma string vazia — erro."""
    marcador = Marcador(
        marcador="[METODO]", origem="CAMPO_DO_SNAPSHOT", referencia="METODO_RECOMENDADO_PIQ"
    )

    with pytest.raises(ErroInterpolacao):
        interpolar("Método: [METODO].", (marcador,), _contexto(snapshot=None))


def test_campo_do_snapshot_campo_inexistente_produz_erro_explicito(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    marcador = Marcador(
        marcador="[X]", origem="CAMPO_DO_SNAPSHOT", referencia="CAMPO_QUE_NAO_EXISTE"
    )

    with pytest.raises(ErroInterpolacao):
        interpolar("[X]", (marcador,), _contexto(snapshot=_snapshot_gab_c))
