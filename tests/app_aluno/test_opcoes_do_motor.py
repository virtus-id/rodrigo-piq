"""Testes de `collection/opcoes_do_motor.py` — RF-08, AC-20, AC-42 (T-14).

Cobre `opcoes_efetivas` pelo comportamento observável (a tupla de
`OpcaoRegistro` devolvida), nunca por implementação interna. `fonte=SNAPSHOT`
é exercitada tanto contra um `SnapshotOrdem` REAL (produzido pela mesma cadeia
do motor já validada por `tests/regras/test_snapshot.py` sobre `GAB-C`, mesmo
padrão de `tests/app_aluno/test_interpolacao.py`) quanto contra um dublê
estrutural mínimo: o motor real ainda não produz um campo no formato de
`OpcaoRegistro` (`B12.16` é caso de prova do gerador, coleta efetiva fora de
escopo — `OQ-12`), então o dublê é o único jeito de provar a leitura por nome
sem antecipar essa implementação do motor.
"""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass

import pytest

import collection.opcoes_do_motor as modulo_opcoes_do_motor
from collection.opcoes_do_motor import OrigemOpcoes, opcoes_efetivas
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    OpcaoRegistro,
    RegistroPergunta,
    TipoResposta,
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
from engine.snapshot import SnapshotOrdem, montar_SnapshotOrdem
from engine.status_metodo import derivar_METODO_RECOMENDADO_PIQ
from engine.tipos import DESCONHECIDO, METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/regras/test_snapshot.py` e
    `tests/app_aluno/test_interpolacao.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.fixture(scope="module")
def _snapshot_gab_c() -> SnapshotOrdem:
    """Roda a cadeia real do motor sobre `GAB-C` e monta o `SnapshotOrdem`
    final — reproduz `tests/app_aluno/test_interpolacao.py::_snapshot_gab_c`
    para não acoplar este teste a outra suíte."""
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


@dataclass(frozen=True, slots=True)
class _SnapshotComRegrasPropostas:
    """Dublê estrutural mínimo, com a forma de um `SnapshotOrdem` que já
    carregasse um campo de regras propostas por `OpcaoRegistro` (caso de
    prova de `B12.16` — o motor real ainda não produz esse campo, `OQ-12`).
    `opcoes_efetivas` só acessa por `getattr`, então não precisa do tipo
    concreto de `SnapshotOrdem` para provar a leitura por nome."""

    REGRAS_PROPOSTAS: tuple[OpcaoRegistro, ...]


_OPCOES_FIXAS_DO_REGISTRO = (
    OpcaoRegistro(rotulo="Sim", valor_interno="SIM"),
    OpcaoRegistro(rotulo="Não", valor_interno="NAO"),
)


def _registro(*, fonte: str, campo_do_snapshot: str | None) -> RegistroPergunta:
    return RegistroPergunta(
        ID="B99.TESTE",
        bloco=99,
        enunciado="Enunciado de teste.",
        tipo=TipoResposta.SELECAO_UNICA,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=_OPCOES_FIXAS_DO_REGISTRO,
        VARIAVEL_GRAVADA="VARIAVEL_DE_TESTE",
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte=fonte, campo_do_snapshot=campo_do_snapshot),  # type: ignore[arg-type]
        admite_nao_sei=False,
        salto_consequencia=None,
    )


def test_ac20_fonte_registro_devolve_as_opcoes_do_proprio_registro_sem_tocar_snapshot(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    """Critério de aceite 1: `fonte=REGISTRO` devolve as opções do próprio
    registro. Um `SnapshotOrdem` REAL é passado, mas não pode influenciar o
    resultado — a prova de que ele não é tocado é o próprio valor devolvido
    ser idêntico a `registro.opcoes`."""
    registro = _registro(fonte="REGISTRO", campo_do_snapshot=None)

    resultado = opcoes_efetivas(registro, _snapshot_gab_c)

    assert resultado == _OPCOES_FIXAS_DO_REGISTRO


def test_ac20_fonte_snapshot_ausente_devolve_lista_vazia_nunca_opcao_inventada() -> None:
    """Critério de aceite 2: `fonte=SNAPSHOT` com snapshot ausente devolve
    lista vazia — a pergunta não é exibível, nunca uma opção fixa aparece no
    lugar."""
    registro = _registro(fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS")

    resultado = opcoes_efetivas(registro, None)

    assert resultado == ()


def test_ac20_fonte_snapshot_com_campo_ausente_no_snapshot_real_devolve_lista_vazia(
    _snapshot_gab_c: SnapshotOrdem,
) -> None:
    """Um `SnapshotOrdem` REAL existe, mas não tem o campo de regras
    propostas (o motor ainda não o produz — caso de prova de `B12.16`,
    `OQ-12`): a leitura por nome não encontra o campo e devolve vazio, nunca
    inventa uma opção para preencher a lacuna."""
    registro = _registro(fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS")

    resultado = opcoes_efetivas(registro, _snapshot_gab_c)

    assert resultado == ()


def test_ac20_fonte_snapshot_devolve_exatamente_as_opcoes_do_campo_nomeado() -> None:
    """Critério de aceite 2 (caminho positivo) e AC-20: com o campo presente
    no snapshot, as opções efetivas são EXATAMENTE as do snapshot — nenhuma
    das opções fixas do registro aparece na lista."""
    opcoes_do_motor = (
        OpcaoRegistro(rotulo="Regra proposta 1", valor_interno="REGRA_1"),
        OpcaoRegistro(rotulo="Regra proposta 2", valor_interno="REGRA_2"),
    )
    snapshot_com_regras = _SnapshotComRegrasPropostas(REGRAS_PROPOSTAS=opcoes_do_motor)
    registro = _registro(fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS")

    resultado = opcoes_efetivas(registro, snapshot_com_regras)  # type: ignore[arg-type]

    assert resultado == opcoes_do_motor
    assert not any(opcao in resultado for opcao in _OPCOES_FIXAS_DO_REGISTRO)


def test_o_modulo_le_o_campo_do_snapshot_por_nome_sem_aritmetica() -> None:
    """Critério de aceite 4 (AC-42): a leitura navega por `getattr`/nome de
    campo — nenhuma soma, subtração ou comparação numérica é aplicada ao
    valor lido. Prova indireta: um campo cujo valor é um número puro (não uma
    tupla de opções) nunca vira opção nenhuma, porque o módulo não o
    interpreta numericamente para produzir nada — apenas o lê e descarta por
    não ter a forma esperada."""

    @dataclass(frozen=True, slots=True)
    class _SnapshotComCampoNumerico:
        REGRAS_PROPOSTAS: int

    registro = _registro(fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS")

    resultado = opcoes_efetivas(registro, _SnapshotComCampoNumerico(REGRAS_PROPOSTAS=42))  # type: ignore[arg-type]

    assert resultado == ()


def test_nenhum_rotulo_de_opcao_aparece_como_literal_no_modulo() -> None:
    """Critério de aceite 3: auditoria direta do código-fonte do módulo —
    nenhuma string de rótulo de opção está escrita nele. Complementa (não
    substitui) o teste estático `AC-37`
    (`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`)."""
    codigo_fonte = inspect.getsource(modulo_opcoes_do_motor)

    for rotulo_de_teste in ("Sim", "Não", "Regra proposta 1", "Regra proposta 2"):
        assert rotulo_de_teste not in codigo_fonte
