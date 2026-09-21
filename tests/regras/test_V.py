"""Testes da família `V` — versionamento, carimbo e cadeia de snapshot,
combinando o ponto de entrada único do motor (`calcular_plano`, T-68) com o
repositório de arquivo (T-69) — RF-02, RF-10, AC-16, AC-18, AC-31, EC-08,
EC-09 · `T-70`.

**Por que este arquivo, e por que não duplica `test_snapshot.py`/
`test_gatilho_recalculo.py`/`test_repositorio_snapshots.py`.** `T-67`,
`T-66` e `T-69` já cobrem, isoladamente, a MONTAGEM do snapshot
(`montar_SnapshotOrdem`), a DECISÃO de recalcular (`avaliar_gatilho_
recalculo`) e a PERSISTÊNCIA (`RepositorioSnapshotsArquivo`). O que faltava
— e é o que esta tarefa acrescenta — é a prova de INTEGRAÇÃO ponta a ponta
através do ponto de entrada único (`engine/motor.py::calcular_plano`,
T-68): que o carimbo de versão aparece em QUALQUER saída do motor (não só
quando `montar_SnapshotOrdem` é chamado manualmente em teste), que a cadeia
de snapshots preserva o anterior intacto quando um novo é produzido, e que
um evento material realmente incrementa `.versao` no snapshot RESULTANTE
mesmo quando método/D* não mudam — não só que o GATILHO decide recalcular
(isso já é `test_EC09_evento_material_com_resultado_identico_ainda_assim_
recalcula`, `tests/regras/test_gatilho_recalculo.py`, T-66).

Reusa a mesma fixture `GAB-C` real (`carregar_gab_c`, T-11) e a mesma cadeia
de integração já validada por `tests/gabaritos/test_gabarito_c_recomendacao.py`
(T-65) — agora através de `calcular_plano`, não da orquestração manual de
`_montar_snapshot_gab_c` (`tests/regras/test_snapshot.py`, T-67).

REGRAS: RF-02, RF-10, V-01, V-02, V-03, AC-16, AC-18, AC-31, EC-08, EC-09
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from engine.estado import EstadoFinanceiro
from engine.motor import calcular_plano
from engine.parametros import Parametros
from engine.tipos import EVENTO_RECALCULO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c


@pytest.fixture(scope="module")
def _estado_e_parametros() -> tuple[EstadoFinanceiro, Parametros]:
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return estado, parametros


@pytest.mark.regra
def test_V03_carimbo_em_toda_saida(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`V-03`/`AC-16`: toda saída do motor — passando pelo ponto de entrada
    único `calcular_plano` (T-68), não só a montagem manual de `T-67` —
    carrega `ENGINE_VERSION` e `PARAMETROS_VERSION` lidos de `Parametros`,
    nunca um literal novo. Roda `calcular_plano` duas vezes, com e sem
    evento, para provar que o carimbo não depende do caminho percorrido."""
    estado, parametros = _estado_e_parametros

    snapshot_sem_evento = calcular_plano(estado, parametros)
    assertar_exato(snapshot_sem_evento.ENGINE_VERSION, parametros.ENGINE_VERSION)
    assertar_exato(snapshot_sem_evento.PARAMETROS_VERSION, parametros.PARAMETROS_VERSION)
    assert snapshot_sem_evento.ENGINE_VERSION, "ENGINE_VERSION não pode ser string vazia"
    assert snapshot_sem_evento.PARAMETROS_VERSION, "PARAMETROS_VERSION não pode ser string vazia"

    snapshot_com_evento = calcular_plano(
        estado,
        parametros,
        anterior=snapshot_sem_evento,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D001",
    )
    assertar_exato(snapshot_com_evento.ENGINE_VERSION, parametros.ENGINE_VERSION)
    assertar_exato(snapshot_com_evento.PARAMETROS_VERSION, parametros.PARAMETROS_VERSION)


@pytest.mark.regra
def test_AC18_snapshot_preserva_anterior(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """`AC-18`: dada uma quitação real ou evento de recálculo, quando a
    ordem muda (novo snapshot produzido), então o snapshot ANTERIOR é
    preservado — nunca sobrescrito, nunca mutado, ainda acessível com seus
    próprios campos (data, `MOTIVO_RECALCULO`, inputs, método, `D*`,
    justificativas) intactos, e referenciado pela cadeia (`snapshot_
    anterior_id`) do novo snapshot (`V-01`)."""
    estado, parametros = _estado_e_parametros

    anterior = calcular_plano(estado, parametros)
    campos_anterior_antes = dataclasses.replace(anterior)  # cópia para comparar depois

    novo = calcular_plano(
        estado,
        parametros,
        anterior=anterior,
        evento=EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
        motivo="QUITACAO_D003",
    )

    # A cadeia referencia o anterior — nunca um objeto novo desvinculado.
    assertar_exato(novo.snapshot_anterior_id, anterior.SNAPSHOT_ID)
    assertar_exato(novo.versao, anterior.versao + 1)

    # O objeto ANTERIOR, em si, não foi mutado pela produção do novo —
    # mesmos campos de antes, ainda frozen.
    assertar_exato(anterior.SNAPSHOT_ID, campos_anterior_antes.SNAPSHOT_ID)
    assertar_exato(anterior.versao, campos_anterior_antes.versao)
    assertar_exato(anterior.DATA_REFERENCIA, campos_anterior_antes.DATA_REFERENCIA)
    assertar_exato(anterior.MOTIVO_RECALCULO, campos_anterior_antes.MOTIVO_RECALCULO)
    assertar_exato(anterior.estado_inputs, campos_anterior_antes.estado_inputs)
    assertar_exato(
        anterior.METODO_RECOMENDADO_PIQ, campos_anterior_antes.METODO_RECOMENDADO_PIQ
    )
    assertar_exato(anterior.DIVIDA_ALVO_ATUAL, campos_anterior_antes.DIVIDA_ALVO_ATUAL)
    assertar_exato(anterior.ORDEM_QUITACAO, campos_anterior_antes.ORDEM_QUITACAO)
    with pytest.raises(dataclasses.FrozenInstanceError):
        anterior.MOTIVO_RECALCULO = "tentativa de sobrescrita"  # type: ignore[misc]


@pytest.mark.regra
def test_EC09_evento_material_versiona_mesmo_sem_mudanca(
    _estado_e_parametros: tuple[EstadoFinanceiro, Parametros],
) -> None:
    """RF-02 · EC-09: um evento material sempre gera novo snapshot mesmo que
    o resultado calculado seja idêntico ao anterior. Diferente de
    `test_EC09_evento_material_com_resultado_identico_ainda_assim_recalcula`
    (`tests/regras/test_gatilho_recalculo.py`, T-66), que prova só a
    DECISÃO do gatilho (`deve_recalcular = True`) isoladamente — este teste
    prova o VERSIONAMENTO EFETIVO do snapshot RESULTANTE: chama
    `calcular_plano` (T-68) duas vezes com o MESMO `EstadoFinanceiro` (nada
    muda no estado, então `METODO_RECOMENDADO_PIQ`/D* do segundo cálculo são
    idênticos ao primeiro), a segunda vez informando um `EVENTO_RECALCULO`
    material, e verifica que `.versao` incrementa mesmo assim (`R-05`)."""
    estado, parametros = _estado_e_parametros

    primeiro = calcular_plano(estado, parametros)
    segundo = calcular_plano(
        estado,
        parametros,
        anterior=primeiro,
        evento=EVENTO_RECALCULO.RENEGOCIACAO_EXECUTADA,
        motivo="RENEGOCIACAO_D002",
    )

    # Resultado IDÊNTICO — mesmo estado de entrada, mesma cadeia decisória.
    assertar_exato(segundo.METODO_RECOMENDADO_PIQ, primeiro.METODO_RECOMENDADO_PIQ)
    assertar_exato(segundo.DIVIDA_ALVO_ATUAL, primeiro.DIVIDA_ALVO_ATUAL)
    assertar_exato(segundo.ORDEM_QUITACAO, primeiro.ORDEM_QUITACAO)
    assertar_exato(segundo.hash_inputs, primeiro.hash_inputs)

    # Mesmo assim, um NOVO snapshot foi produzido, versionado na cadeia.
    assertar_exato(segundo.versao, primeiro.versao + 1)
    assertar_exato(segundo.snapshot_anterior_id, primeiro.SNAPSHOT_ID)
    assert segundo.SNAPSHOT_ID != primeiro.SNAPSHOT_ID, (
        "evento material precisa produzir um SNAPSHOT_ID novo mesmo com "
        "resultado idêntico ao anterior — R-05/EC-09."
    )


@pytest.mark.regra
def test_round_trip_snapshot_jsonl_preserva_decimal_exato(
    tmp_path: Path, _estado_e_parametros: tuple[EstadoFinanceiro, Parametros]
) -> None:
    """Round-trip snapshot -> JSONL -> snapshot com igualdade EXATA de todo
    `Decimal` — através do ponto de entrada único (`calcular_plano`, T-68) e
    do repositório de arquivo (`RepositorioSnapshotsArquivo`, T-69). Já
    coberto em profundidade por `test_criterio3_decimal_vira_string_e_
    volta_exato_round_trip` (`tests/regras/test_repositorio_snapshots.py`,
    T-69, critério de aceite 3, campo a campo, inclusive `valores_de_apoio`
    de cada posição publicada) — este teste é a citação equivalente exigida
    por `T-70`, agora a partir de um `SnapshotOrdem` produzido por
    `calcular_plano`, não da montagem manual `_montar_snapshot_gab_c`."""
    estado, parametros = _estado_e_parametros
    caminho = tmp_path / "snapshots.jsonl"
    repositorio = RepositorioSnapshotsArquivo(caminho)

    original = calcular_plano(estado, parametros)
    repositorio.anexar(original)
    reconstruido = repositorio.obter(original.SNAPSHOT_ID)

    assert type(reconstruido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA) is type(
        original.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    )
    assertar_exato(
        reconstruido.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
        original.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
    )
    assertar_exato(reconstruido.diagnostico, original.diagnostico)
    assertar_exato(reconstruido.cenarios, original.cenarios)
    assertar_exato(reconstruido.ORDEM_QUITACAO, original.ORDEM_QUITACAO)
    assertar_exato(reconstruido.SNAPSHOT_ID, original.SNAPSHOT_ID)
    assertar_exato(reconstruido.hash_inputs, original.hash_inputs)
