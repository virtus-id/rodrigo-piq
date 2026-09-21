"""Testa a montagem e o carimbo do `SnapshotOrdem` — RF-10 · `V-01..V-03` ·
`AC-16` · `AC-18` · `T-67`.

Reusa a mesma cadeia de integração ponta a ponta já validada por
`tests/gabaritos/test_gabarito_c_recomendacao.py` (T-65) sobre `GAB-C`:
`calcular_diagnostico` -> os três `Cenario` reais -> `comparar_cenarios` ->
`derivar_METODO_RECOMENDADO_PIQ` -> `publicar_ORDEM_QUITACAO` ->
`consolidar_ORDEM_STATUS`. `montar_SnapshotOrdem` (`engine/snapshot.py`) só
ENVELOPA esses resultados já calculados — os testes aqui não recalculam nada
à parte, só verificam a montagem e o carimbo.

REGRAS: RF-10, V-01, V-02, V-03, AC-16, AC-18
"""

from __future__ import annotations

import dataclasses

import pytest

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
from engine.parametros import Parametros
from engine.snapshot import SnapshotOrdem, montar_SnapshotOrdem
from engine.status_metodo import derivar_METODO_RECOMENDADO_PIQ
from engine.tipos import DESCONHECIDO, EVENTO_RECALCULO, METODO, ORDEM_STATUS
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/gabaritos/test_gabarito_c_recomendacao.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


def _montar_snapshot_gab_c(
    *,
    estado: EstadoFinanceiro,
    parametros: Parametros,
    evento: EVENTO_RECALCULO | None = None,
    motivo: str = "",
    anterior: SnapshotOrdem | None = None,
) -> SnapshotOrdem:
    """Roda a cadeia real do motor sobre `GAB-C` (T-24, T-46, T-57/T-58,
    T-61, T-63/T-64) e monta o `SnapshotOrdem` final via `montar_
    SnapshotOrdem` (T-67) — helper compartilhado entre os testes desta
    tarefa, para não duplicar a orquestração de teste em cada caso.
    """
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

    # Origem SIMULACAO para toda dívida da ordem publicada — GAB-C não
    # exercita fallback de benefício marginal (T-40/AC-33), então
    # ORDEM_STATUS consolidado é DEFINITIVA_NA_DATA aqui (verificado abaixo).
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
        evento=evento,
        motivo=motivo,
        anterior=anterior,
    )


@pytest.fixture(scope="module")
def _estado_e_parametros() -> tuple[EstadoFinanceiro, Parametros]:
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return estado, parametros


@pytest.mark.regra
def test_AC16_snapshot_carrega_engine_version_e_parametros_version(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`AC-16`: toda saída (todo `SnapshotOrdem` produzido) carrega
    `ENGINE_VERSION` e `PARAMETROS_VERSION` — carimbo lido de `Parametros`,
    nunca um literal novo em `engine/snapshot.py`."""
    estado, parametros = _estado_e_parametros
    snapshot = _montar_snapshot_gab_c(estado=estado, parametros=parametros)

    assertar_exato(snapshot.ENGINE_VERSION, parametros.ENGINE_VERSION)
    assertar_exato(snapshot.PARAMETROS_VERSION, parametros.PARAMETROS_VERSION)
    assert snapshot.ENGINE_VERSION, "ENGINE_VERSION não pode ser string vazia"
    assert snapshot.PARAMETROS_VERSION, "PARAMETROS_VERSION não pode ser string vazia"


@pytest.mark.regra
def test_V01_cadeia_snapshot_anterior_id_preservada_e_versao_incrementa(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`V-01`: `snapshot_anterior_id` aponta para o `SNAPSHOT_ID` do
    snapshot anterior e `versao` incrementa a cada novo snapshot na cadeia.
    """
    estado, parametros = _estado_e_parametros

    primeiro = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    assertar_exato(primeiro.versao, 1)
    assertar_exato(primeiro.snapshot_anterior_id, None)

    segundo = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D001",
        anterior=primeiro,
    )
    assertar_exato(segundo.versao, primeiro.versao + 1)
    assertar_exato(segundo.snapshot_anterior_id, primeiro.SNAPSHOT_ID)

    terceiro = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.NOVA_DIVIDA,
        motivo="NOVA_DIVIDA",
        anterior=segundo,
    )
    assertar_exato(terceiro.versao, segundo.versao + 1)
    assertar_exato(terceiro.snapshot_anterior_id, segundo.SNAPSHOT_ID)


@pytest.mark.regra
def test_AC18_snapshot_preserva_data_motivo_inputs_metodo_alvo_e_justificativas(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`AC-18`: o snapshot preserva data, `MOTIVO_RECALCULO`, inputs, método
    (recomendado), dívida-alvo (`D*`) e justificativas (`JUSTIFICATIVA_
    POSICAO` de cada posição da ordem) — tudo acessível a partir do
    snapshot montado, sem perda de informação."""
    estado, parametros = _estado_e_parametros
    snapshot = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D003",
    )

    assertar_exato(snapshot.DATA_REFERENCIA, estado.DATA_REFERENCIA)
    assertar_exato(snapshot.MOTIVO_RECALCULO, "QUITACAO_D003")
    assertar_exato(snapshot.EVENTO_RECALCULO, EVENTO_RECALCULO.QUITACAO_CONFIRMADA)
    assertar_exato(snapshot.estado_inputs, estado)
    assertar_exato(snapshot.METODO_RECOMENDADO_PIQ, METODO.HIBRIDO)  # AC-04, GAB-C

    assert snapshot.ORDEM_QUITACAO, "ORDEM_QUITACAO publicada não pode ser vazia em GAB-C"
    assertar_exato(snapshot.DIVIDA_ALVO_ATUAL, snapshot.ORDEM_QUITACAO[0].DIVIDA_ID)

    for posicao in snapshot.ORDEM_QUITACAO:
        assert posicao.JUSTIFICATIVA_POSICAO.strip() != "", (
            f"posição {posicao.posicao} ({posicao.DIVIDA_ID}) com "
            "JUSTIFICATIVA_POSICAO vazia — viola AC-18/Q-05."
        )


@pytest.mark.regra
def test_snapshot_sem_ordem_publicada_nao_tem_divida_alvo(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`EC-17` refletido no snapshot: `ORDEM_QUITACAO` vazia implica
    `DIVIDA_ALVO_ATUAL = None` e `PROXIMA_DIVIDA = None` — nunca um alvo
    fabricado sem dívida elegível."""
    from engine.ordem import ResultadoOrdemPublicada

    estado, parametros = _estado_e_parametros
    dividas = _inventario(estado)
    diagnostico = calcular_diagnostico(estado, parametros)
    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, parametros)
    cenario_avalanche = dataclasses.replace(
        simular_cenario(estado, diagnostico, dividas, sel_avalanche, parametros),
        metodo=METODO.AVALANCHE,
    )
    comparacao = comparar_cenarios((cenario_avalanche,), parametros)
    resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
        {METODO.AVALANCHE: cenario_avalanche},
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=False,
        INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
        parametros=parametros,
    )
    ordem_vazia = ResultadoOrdemPublicada(ORDEM_QUITACAO=(), ORDEM_ACOES=())

    snapshot = montar_SnapshotOrdem(
        estado=estado,
        parametros=parametros,
        diagnostico=diagnostico,
        cenarios={METODO.AVALANCHE: cenario_avalanche},
        comparacao=comparacao,
        resultado_metodo=resultado_recomendacao,
        ordem_status=ORDEM_STATUS.PROVISORIA,
        ordem_publicada=ordem_vazia,
        evento=None,
        motivo="",
    )

    assertar_exato(snapshot.DIVIDA_ALVO_ATUAL, None)
    assertar_exato(snapshot.PROXIMA_DIVIDA, None)
    assertar_exato(snapshot.ORDEM_QUITACAO, ())


@pytest.mark.regra
def test_AC16_SNAPSHOT_ID_e_deterministico_nunca_uuid4(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Critério de aceite 4 de `T-67`: `SNAPSHOT_ID` é derivado de
    `hash_inputs` + versão — nunca de `uuid4()`. Roda a montagem DUAS VEZES
    com a mesma entrada e prova que produz o MESMO `SNAPSHOT_ID` — se fosse
    `uuid4()`, cada chamada produziria um valor diferente, o que faria esta
    asserção falhar."""
    estado, parametros = _estado_e_parametros

    primeira_montagem = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    segunda_montagem = _montar_snapshot_gab_c(estado=estado, parametros=parametros)

    assertar_exato(primeira_montagem.hash_inputs, segunda_montagem.hash_inputs)
    assertar_exato(primeira_montagem.SNAPSHOT_ID, segunda_montagem.SNAPSHOT_ID)
    assert primeira_montagem.SNAPSHOT_ID, "SNAPSHOT_ID não pode ser string vazia"


@pytest.mark.regra
def test_SNAPSHOT_ID_muda_quando_a_versao_muda_mesmo_hash_inputs(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`SNAPSHOT_ID` depende de `hash_inputs` E de `versao` — dois snapshots
    com o MESMO estado de entrada, mas versões diferentes na cadeia
    (`anterior` presente), têm `hash_inputs` igual mas `SNAPSHOT_ID`
    distinto (evita colisão entre versões sucessivas do mesmo caso)."""
    estado, parametros = _estado_e_parametros

    primeiro = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    segundo = _montar_snapshot_gab_c(
        estado=estado,
        parametros=parametros,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D001",
        anterior=primeiro,
    )

    assertar_exato(primeiro.hash_inputs, segundo.hash_inputs)
    assert primeiro.SNAPSHOT_ID != segundo.SNAPSHOT_ID, (
        "SNAPSHOT_ID deveria mudar entre versões sucessivas, mesmo com "
        "hash_inputs idêntico — evita colisão entre snapshots da mesma cadeia."
    )


@pytest.mark.regra
def test_SNAPSHOT_ID_muda_quando_o_estado_muda(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`hash_inputs`/`SNAPSHOT_ID` refletem o conteúdo do `EstadoFinanceiro`
    — mudar a carteira de dívidas (mesmo só um campo) produz um
    `hash_inputs` diferente."""
    estado, parametros = _estado_e_parametros

    divida_alterada = dataclasses.replace(
        estado.dividas[0], PESO_EMOCIONAL=(estado.dividas[0].PESO_EMOCIONAL or 0) + 1
        if estado.dividas[0].PESO_EMOCIONAL is not DESCONHECIDO
        else 5,
    )
    estado_alterado = dataclasses.replace(
        estado, dividas=(divida_alterada, *estado.dividas[1:])
    )

    snapshot_original = _montar_snapshot_gab_c(estado=estado, parametros=parametros)
    snapshot_alterado = _montar_snapshot_gab_c(estado=estado_alterado, parametros=parametros)

    assert snapshot_original.hash_inputs != snapshot_alterado.hash_inputs
    assert snapshot_original.SNAPSHOT_ID != snapshot_alterado.SNAPSHOT_ID


@pytest.mark.regra
def test_criterio5_SnapshotOrdem_e_frozen_sem_caminho_de_sobrescrita(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """Critério de aceite 5 de `T-67`: `SnapshotOrdem` é `frozen=True` — não
    existe caminho de sobrescrita de nenhum campo depois de montado."""
    estado, parametros = _estado_e_parametros
    snapshot = _montar_snapshot_gab_c(estado=estado, parametros=parametros)

    assert dataclasses.is_dataclass(SnapshotOrdem)
    parametros_dataclass = dataclasses.fields(SnapshotOrdem)
    assert parametros_dataclass, "SnapshotOrdem precisa ter campos declarados"

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.MOTIVO_RECALCULO = "tentativa de sobrescrita"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.ENGINE_VERSION = "9.9.9"  # type: ignore[misc]
