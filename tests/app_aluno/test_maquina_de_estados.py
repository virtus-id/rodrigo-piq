"""Testes de comportamento de `app/casos/maquina.py` — `RF-01` (T-34).

Suíte DIFERENTE de `tests/app_aluno/test_maquina_estados_construcao.py`
(T-33): aquela prova o que a máquina PROMETE CONSTRUIR (doze estados, forma
de `Transicao`, um par recusado como amostra, ausência de estado
"reaberto"). Esta prova o COMPORTAMENTO da máquina ao longo do tempo:

1. o caminho completo do plano §7.1 é percorrível só por transições
   declaradas (`gatilho` nomeado a cada passo, nunca uma transição
   inventada pelo teste);
2. o produto cartesiano DOS DOZE ESTADOS — 12×12 = 144 pares, EXAUSTIVO,
   não amostrado — separa os 17 pares declarados (sucesso) dos 127
   restantes (recusa por `ErroTransicaoNaoDeclarada`, nomeando origem e
   destino);
3. `ERRO_DE_CALCULO` volta a CADA UM dos quatro estados de origem de
   `CALCULANDO` por transição nomeada (`EC-06`);
4. `REPROVADO_EM_REVISAO` é alcançável só a partir de `AGUARDANDO_REVISAO`,
   nunca a partir de `PLANO_LIBERADO` (`EC-12`).

REGRAS: `RF-01`
"""

from __future__ import annotations

import itertools

import pytest

from app.casos.maquina import (
    ESTADO_CASO,
    TABELA_TRANSICOES,
    ErroTransicaoNaoDeclarada,
    transicionar,
)

# Os 17 pares declarados na tabela — usados para a exaustão do produto
# cartesiano. Não é uma cópia solta: é derivado da própria TABELA_TRANSICOES,
# para que o teste nunca divirja do módulo por edição manual desatualizada.
_PARES_DECLARADOS: frozenset[tuple[ESTADO_CASO, ESTADO_CASO]] = frozenset(
    (t.de, t.para) for t in TABELA_TRANSICOES
)


def test_tabela_declara_exatamente_dezessete_transicoes() -> None:
    """Pré-condição da exaustão: a tabela citada pela tarefa (17 linhas)
    ainda tem 17 pares distintos. Se este número mudar, os testes abaixo
    continuam corretos (derivam de `TABELA_TRANSICOES`), mas este teste
    avisa explicitamente que a superfície declarada mudou."""
    assert len(TABELA_TRANSICOES) == 17
    assert len(_PARES_DECLARADOS) == 17


def test_caminho_completo_do_plano_e_percorrivel_so_por_transicoes_declaradas() -> None:
    """Critério 1 — o caminho `CADASTRADO → ... → ACOMPANHAMENTO →
    CALCULANDO` do plano §7.1 é percorrido passo a passo, cada um por
    `transicionar(de, para)`. Se um par do caminho não estivesse na tabela,
    `transicionar` levantaria `ErroTransicaoNaoDeclarada` e o teste falharia
    — não há atalho nem transição inventada pelo teste."""
    caminho = (
        ESTADO_CASO.CADASTRADO,
        ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        ESTADO_CASO.COLETA_INICIAL,
        ESTADO_CASO.CALCULANDO,
        ESTADO_CASO.AGUARDANDO_REVISAO,
        ESTADO_CASO.PLANO_LIBERADO,
        ESTADO_CASO.ACOMPANHAMENTO,
        ESTADO_CASO.CALCULANDO,
    )

    gatilhos_esperados = (
        "registra_consentimento",
        "inicia_coleta",
        "bloco_6_executa",
        "snapshot_anexado",
        "libera",
        "abre_bloco_11",
        "recalcula",
    )

    assert len(caminho) - 1 == len(gatilhos_esperados)

    for (de, para), gatilho_esperado in zip(
        itertools.pairwise(caminho), gatilhos_esperados, strict=True
    ):
        transicao = transicionar(de, para)
        assert transicao.gatilho == gatilho_esperado, (
            f"{de} → {para} deveria disparar {gatilho_esperado!r}, "
            f"disparou {transicao.gatilho!r}"
        )


@pytest.mark.parametrize(
    "de_para_gatilho",
    [
        pytest.param(
            (ESTADO_CASO.PLANO_LIBERADO, ESTADO_CASO.COLETA_DIRIGIDA, "abre_blocos_7_8"),
            id="plano_liberado_para_coleta_dirigida",
        ),
        pytest.param(
            (
                ESTADO_CASO.PLANO_LIBERADO,
                ESTADO_CASO.CONFIRMACAO_ATAQUE,
                "abre_bloco_10",
            ),
            id="plano_liberado_para_confirmacao_ataque",
        ),
    ],
)
def test_os_outros_dois_ramos_de_plano_liberado_tambem_sao_transicoes_declaradas(
    de_para_gatilho: tuple[ESTADO_CASO, ESTADO_CASO, str],
) -> None:
    """Complemento ao caminho principal: o plano §7.1 desenha TRÊS ramos a
    partir de `PLANO_LIBERADO` (`COLETA_DIRIGIDA`, `CONFIRMACAO_ATAQUE`,
    `ACOMPANHAMENTO` — este último já coberto no caminho principal). Os
    outros dois também são transições nomeadas, não bifurcações implícitas."""
    de, para, gatilho_esperado = de_para_gatilho
    transicao = transicionar(de, para)
    assert transicao.gatilho == gatilho_esperado


@pytest.mark.parametrize(
    "de_para_gatilho",
    [
        pytest.param(
            (ESTADO_CASO.COLETA_DIRIGIDA, ESTADO_CASO.CALCULANDO, "recalcula"),
            id="coleta_dirigida_para_calculando",
        ),
        pytest.param(
            (ESTADO_CASO.CONFIRMACAO_ATAQUE, ESTADO_CASO.CALCULANDO, "recalcula"),
            id="confirmacao_ataque_para_calculando",
        ),
    ],
)
def test_coleta_dirigida_e_confirmacao_ataque_tambem_convergem_para_calculando(
    de_para_gatilho: tuple[ESTADO_CASO, ESTADO_CASO, str],
) -> None:
    """Fecha o ciclo dos três ramos de `PLANO_LIBERADO`: os três convergem de
    volta a `CALCULANDO` por `recalcula`, tal como `ACOMPANHAMENTO` no
    caminho principal — nenhum dos três tem um destino de recálculo
    diferente inventado."""
    de, para, gatilho_esperado = de_para_gatilho
    transicao = transicionar(de, para)
    assert transicao.gatilho == gatilho_esperado


def test_produto_cartesiano_completo_dos_doze_estados_e_exaustivo() -> None:
    """Critério 2 — EXAUSTIVO sobre os 12×12 = 144 pares (de, para), nenhuma
    amostra: os 17 pares declarados sucedem e devolvem a `Transicao`
    correta; os 127 restantes são recusados com `ErroTransicaoNaoDeclarada`
    nomeando origem e destino."""
    todos_os_pares = list(itertools.product(ESTADO_CASO, ESTADO_CASO))
    assert len(todos_os_pares) == 144  # 12 x 12, produto cartesiano completo

    pares_declarados_vistos = 0
    pares_recusados_vistos = 0

    for de, para in todos_os_pares:
        if (de, para) in _PARES_DECLARADOS:
            transicao = transicionar(de, para)
            assert transicao.de is de
            assert transicao.para is para
            pares_declarados_vistos += 1
        else:
            with pytest.raises(ErroTransicaoNaoDeclarada) as capturado:
                transicionar(de, para)
            erro = capturado.value
            assert erro.de is de
            assert erro.para is para
            pares_recusados_vistos += 1

    assert pares_declarados_vistos == 17
    assert pares_recusados_vistos == 127
    assert pares_declarados_vistos + pares_recusados_vistos == 144


@pytest.mark.parametrize(
    "estado_de_origem_de_calculando",
    [
        ESTADO_CASO.COLETA_INICIAL,
        ESTADO_CASO.COLETA_DIRIGIDA,
        ESTADO_CASO.CONFIRMACAO_ATAQUE,
        ESTADO_CASO.ACOMPANHAMENTO,
    ],
)
def test_erro_de_calculo_volta_a_cada_estado_de_origem_de_calculando_ec06(
    estado_de_origem_de_calculando: ESTADO_CASO,
) -> None:
    """Critério 3 (`EC-06`) — `ERRO_DE_CALCULO` retorna a CADA UM dos quatro
    estados que alcançam `CALCULANDO`, por transição nomeada
    (`operador_retoma_apos_erro`), nunca por um destino fixo único
    inventado. As quatro transições `CALCULANDO → estado` também existem
    (o caminho de ida), confirmando que o estado de origem é de fato uma
    origem real de `CALCULANDO` no grafo."""
    transicao_de_volta = transicionar(
        ESTADO_CASO.ERRO_DE_CALCULO, estado_de_origem_de_calculando
    )
    assert transicao_de_volta.gatilho == "operador_retoma_apos_erro"

    # A origem alegada de CALCULANDO precisa, de fato, alcançar CALCULANDO —
    # senão "EC-06 volta ao estado anterior" seria uma alegação vazia.
    transicao_de_ida = transicionar(estado_de_origem_de_calculando, ESTADO_CASO.CALCULANDO)
    assert transicao_de_ida.para is ESTADO_CASO.CALCULANDO


def test_erro_de_calculo_nao_tem_quinta_transicao_de_volta_declarada() -> None:
    """Reforço do critério 3: exatamente quatro transições partem de
    `ERRO_DE_CALCULO` — nenhuma quinta, nenhum destino fixo único inventado
    além dos quatro estados de origem reais de `CALCULANDO`."""
    origens_esperadas = {
        ESTADO_CASO.COLETA_INICIAL,
        ESTADO_CASO.COLETA_DIRIGIDA,
        ESTADO_CASO.CONFIRMACAO_ATAQUE,
        ESTADO_CASO.ACOMPANHAMENTO,
    }
    destinos_declarados = {
        t.para for t in TABELA_TRANSICOES if t.de is ESTADO_CASO.ERRO_DE_CALCULO
    }
    assert destinos_declarados == origens_esperadas
    assert len(destinos_declarados) == 4


def test_reprovado_em_revisao_e_alcancavel_a_partir_de_aguardando_revisao_ec12() -> None:
    """Critério 4, primeira metade (`EC-12`) — `AGUARDANDO_REVISAO →
    REPROVADO_EM_REVISAO` é uma transição nomeada e declarada."""
    transicao = transicionar(
        ESTADO_CASO.AGUARDANDO_REVISAO, ESTADO_CASO.REPROVADO_EM_REVISAO
    )
    assert transicao.gatilho == "reprova"


def test_reprovado_em_revisao_nao_e_alcancavel_a_partir_de_plano_liberado_ec12() -> None:
    """Critério 4, segunda metade (`EC-12`) — `PLANO_LIBERADO →
    REPROVADO_EM_REVISAO` NÃO está na tabela: uma vez liberado, o plano não
    pode ser reprovado por essa via. A tentativa é recusada."""
    par = (ESTADO_CASO.PLANO_LIBERADO, ESTADO_CASO.REPROVADO_EM_REVISAO)
    assert par not in _PARES_DECLARADOS

    with pytest.raises(ErroTransicaoNaoDeclarada) as capturado:
        transicionar(*par)

    erro = capturado.value
    assert erro.de is ESTADO_CASO.PLANO_LIBERADO
    assert erro.para is ESTADO_CASO.REPROVADO_EM_REVISAO


def test_reprovado_em_revisao_e_alcancavel_apenas_a_partir_de_aguardando_revisao() -> None:
    """Fecha o critério 4 de forma exaustiva: entre os DOZE estados
    possíveis de origem, `AGUARDANDO_REVISAO` é o ÚNICO que alcança
    `REPROVADO_EM_REVISAO` — nenhum outro estado, incluindo mas não se
    limitando a `PLANO_LIBERADO`, tem essa transição declarada."""
    origens_que_alcancam_reprovado = {
        estado
        for estado in ESTADO_CASO
        if (estado, ESTADO_CASO.REPROVADO_EM_REVISAO) in _PARES_DECLARADOS
    }
    assert origens_que_alcancam_reprovado == {ESTADO_CASO.AGUARDANDO_REVISAO}
