"""Testes dos quatro componentes não protetivos da §13.3 (T-104) —
RF-45, RF-37 · §13.3 · §13.7 (ordens 1 a 4).

Cobre os critérios comportamentais de `T-104`. Os quatro componentes são somas
triviais; todo o risco está no FILTRO de cada um, e cada filtro é mais estrito
que o do potencial (§13.2):

- `AC-78` — só `MOBILIZACAO_RECOMENDAVEL` compõe automaticamente. O item
  `MOBILIZACAO_POSSIVEL` fica **só no potencial**; `MOBILIZACAO_COM_RESSALVAS`
  e `NAO_MOBILIZAR` não entram automaticamente (`EC-30`).
- `INVESTIMENTOS_RECOMENDADOS` exige DUAS condições (liquidez E classificação);
  `ATIVOS_RECOMENDADOS` exige UMA (classificação), porque `ItemAtivo` não tem
  campo de liquidez — "com liquidez" é exigência que a §13.3 impõe apenas aos
  investimentos.
- `AC-79` — recurso extraordinário só compõe se `CONFIRMADO` **e** `ATE_30D`;
  o futuro/não confirmado fica no potencial. O lado do potencial está em
  `test_ataque_imediato_potencial.py` (`T-103`).
- `RF-37`/`AC-63`/`OQ-28` — `CAIXA_RECOMENDADO` é identidade sobre
  `DINHEIRO_DISPONIVEL`, sem revalidação.
- `EC-27` — coleção vazia devolve `dinheiro(0)` nas quatro.

Tolerância ZERO em toda asserção (spec §5, `OQ-34` respondida): `assertar_exato`,
nunca `assertar_monetario`. Os gabaritos `GAB-AI` formais são `T-110`+ — não
estão aqui.
"""

import pytest

from engine.ataque_imediato import (
    calcular_ATIVOS_RECOMENDADOS,
    calcular_CAIXA_RECOMENDADO,
    calcular_EXTRAORDINARIOS_RECOMENDADOS,
    calcular_INVESTIMENTOS_RECOMENDADOS,
)
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    DISPOSICAO_USO_INVESTIMENTO,
    ESSENCIALIDADE,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
    ItemInvestimento,
    RecursoExtraordinario,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, Dinheiro
from tests.conftest import assertar_exato

CLASSES_NAO_RECOMENDAVEIS: tuple[CLASSIFICACAO_MOBILIZACAO, ...] = (
    CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
    CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
    CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
)


def _ativo(item_id: str, valor: int, classe: CLASSIFICACAO_MOBILIZACAO) -> ItemAtivo:
    """RF-54, RF-59, T-125 — `CLASSIFICACAO_MOBILIZACAO` não é mais campo do
    construtor: `classe` continua o parâmetro da fixture, mas escolhe os
    campos BRUTOS canônicos (§14.4-§14.9) que fazem `classificar_ativo_fisico`
    DERIVAR exatamente `classe`, de trás para frente a partir da regra —
    nunca valor aleatório. `VALOR_ESTIMADO_ATIVO=valor`, sem passivo/custo
    (`POSSUI_PASSIVO_VINCULADO=POSSUI_CUSTO_DESMOBILIZACAO=False`), faz
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` derivado ser `valor` (assume
    `valor > 0`, único caso exercitado por este arquivo — `valor=0` cairia
    sempre em `MOBILIZACAO_COM_RESSALVAS` pelo ramo 3, ver `classificacao_
    ativos.py`):
      NAO_MOBILIZAR          -> POSSIBILIDADE_VENDA=NAO (ramo 1)
      MOBILIZACAO_COM_RESSALVAS -> ESSENCIAL, venda SIM (ramo 4, nunca
        RECOMENDAVEL mesmo com venda aceita)
      MOBILIZACAO_POSSIVEL   -> NAO_ESSENCIAL, venda TALVEZ (ramo 7)
      MOBILIZACAO_RECOMENDAVEL -> NAO_ESSENCIAL, venda SIM, outro-ativo
        (não veículo), fluxo recorrente 0<=0 (ramo 8c)
    """
    if classe == CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR:
        possibilidade_venda = POSSIBILIDADE_VENDA.NAO
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS:
        possibilidade_venda = POSSIBILIDADE_VENDA.SIM
        essencialidade = ESSENCIALIDADE.ESSENCIAL
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL:
        possibilidade_venda = POSSIBILIDADE_VENDA.TALVEZ
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL
    else:
        assert classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        possibilidade_venda = POSSIBILIDADE_VENDA.SIM
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL

    return ItemAtivo(
        ITEM_ID=item_id,
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
        POSSIBILIDADE_VENDA=possibilidade_venda,
        ESSENCIALIDADE=essencialidade,
        VALOR_ESTIMADO_ATIVO=dinheiro(valor),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=dinheiro(0),
        CUSTO_RECORRENTE_ATIVO=dinheiro(0),
    )


def _investimento(
    item_id: str, valor: int, *, liquidez: bool, classe: CLASSIFICACAO_MOBILIZACAO
) -> ItemInvestimento:
    """RF-53, RF-59, T-125 — mesmo espírito de `_ativo` acima: `classe`
    escolhe os campos BRUTOS canônicos (§14.3.1) que fazem
    `classificar_investimento` DERIVAR exatamente `classe`:
      NAO_MOBILIZAR             -> DISPOSICAO_USO_INVESTIMENTO=NAO (Regra 1)
      MOBILIZACAO_POSSIVEL      -> TALVEZ, liquidez não bloqueada (Regra 3)
      MOBILIZACAO_COM_RESSALVAS -> SIM, liquidez MAIS_30 (Regra 6, fallback)
      MOBILIZACAO_RECOMENDAVEL  -> SIM, D0, sem custo/perda relevante,
        `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=valor>0` (Regra 4)
    `POSSUI_LIQUIDEZ` continua parâmetro nomeado independente: §13.3 o exige
    só para `INVESTIMENTOS_RECOMENDADOS`, sem relação com a classificação."""
    if classe == CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.NAO
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D0
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.TALVEZ
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D1
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.SIM
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.MAIS_30
        tem_custo_conhecido = False
        sem_custo_perda_relevante = False
    else:
        assert classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        disposicao = DISPOSICAO_USO_INVESTIMENTO.SIM
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D0
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True

    return ItemInvestimento(
        ITEM_ID=item_id,
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(valor),
        POSSUI_LIQUIDEZ=liquidez,
        LIQUIDEZ_INVESTIMENTOS=liquidez_investimentos,
        DISPOSICAO_USO_INVESTIMENTO=disposicao,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(valor),
        TEM_CUSTO_CONHECIDO=tem_custo_conhecido,
        SEM_CUSTO_PERDA_RELEVANTE=sem_custo_perda_relevante,
    )


def _recurso(
    item_id: str,
    valor: int,
    *,
    janela: JANELA_RECURSO_EXTRAORDINARIO,
    certeza: CERTEZA_RECURSO_EXTRAORDINARIO,
) -> RecursoExtraordinario:
    return RecursoExtraordinario(
        ITEM_ID=item_id,
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(valor),
        JANELA_RECURSO_EXTRAORDINARIO=janela,
        CERTEZA_RECURSO_EXTRAORDINARIO=certeza,
    )


# ---------------------------------------------------------------------------
# Ordem 1 (§13.7) — CAIXA_RECOMENDADO
# ---------------------------------------------------------------------------
@pytest.mark.regra
@pytest.mark.parametrize("valor", [dinheiro(0), dinheiro(1), dinheiro("1234.56"), dinheiro(99999)])
def test_caixa_recomendado_e_identidade_sem_transformacao(valor: Dinheiro) -> None:
    """`RF-37`/`AC-63`/`OQ-28`: `CAIXA_RECOMENDADO = DINHEIRO_DISPONIVEL`,
    caractere por caractere do valor recebido — sem arredondar, sem piso, sem
    revalidar "livre / não comprometido" (garantia de coleta, não do motor).
    A igualdade é EXATA, inclusive nos centavos."""
    assertar_exato(calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=valor), valor)


@pytest.mark.regra
def test_caixa_recomendado_devolve_o_proprio_objeto_recebido() -> None:
    """A identidade da §13.3 é literal: o `Decimal` que sai é o MESMO objeto
    que entrou. Qualquer transformação — `+valor`, `dinheiro(valor)`,
    `quantize` — construiria um objeto novo e faria este `is` falhar, que é
    a forma mais forte de provar "sem transformação"."""
    entrada = dinheiro("7000.005")

    assert calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=entrada) is entrada


# ---------------------------------------------------------------------------
# Ordem 2 (§13.7) — INVESTIMENTOS_RECOMENDADOS
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_investimentos_recomendados_exige_liquidez_e_classificacao() -> None:
    """`AC-78` · §13.3: "com liquidez **E** classificados
    `MOBILIZACAO_RECOMENDAVEL`" — as duas condições, conjuntas. Dos quatro
    itens, só o primeiro satisfaz ambas; o total é 2.000, não 2.000+400 (que
    ignoraria a liquidez), não 2.000+800 (que ignoraria a classificação) e
    não 3.200 (que ignoraria as duas)."""
    obtido = calcular_INVESTIMENTOS_RECOMENDADOS(
        investimentos=(
            _investimento(
                "OK",
                2000,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
            _investimento(
                "SEM_LIQUIDEZ",
                400,
                liquidez=False,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
            _investimento(
                "SO_POSSIVEL",
                800,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
            ),
            _investimento(
                "NENHUMA_DAS_DUAS",
                1600,
                liquidez=False,
                classe=CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
            ),
        )
    )

    assertar_exato(obtido, dinheiro(2000))


@pytest.mark.regra
@pytest.mark.parametrize("classe", CLASSES_NAO_RECOMENDAVEIS)
def test_investimento_nao_recomendavel_nao_compoe_ainda_que_liquido(
    classe: CLASSIFICACAO_MOBILIZACAO,
) -> None:
    """`AC-78` e `EC-30`: nenhuma das três outras classes compõe
    `INVESTIMENTOS_RECOMENDADOS`, mesmo com liquidez e valor alto.
    `MOBILIZACAO_POSSIVEL` "fica no potencial, não entra automaticamente no
    recomendado" (§13.3); `COM_RESSALVAS` e `NAO_MOBILIZAR` também não."""
    obtido = calcular_INVESTIMENTOS_RECOMENDADOS(
        investimentos=(_investimento("I1", 500000, liquidez=True, classe=classe),)
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_investimento_recomendavel_sem_liquidez_nao_compoe() -> None:
    """§13.3, o outro lado do `E`: recomendável mas ILÍQUIDO não compõe.
    `POSSUI_LIQUIDEZ` é campo de entrada por item (`RF-38`), e a §13.3 o
    exige explicitamente para esta parcela — só para esta."""
    obtido = calcular_INVESTIMENTOS_RECOMENDADOS(
        investimentos=(
            _investimento(
                "I1",
                12000,
                liquidez=False,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
        )
    )

    assertar_exato(obtido, dinheiro(0))


# ---------------------------------------------------------------------------
# Ordem 3 (§13.7) — EXTRAORDINARIOS_RECOMENDADOS
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_extraordinarios_recomendados_exige_confirmado_e_ate_30d() -> None:
    """`AC-79` · §13.3: "confirmados, disponíveis, não comprometidos e aptos
    no momento atual". Só o item `CONFIRMADO` + `ATE_30D` compõe: 3.000, não
    3.000+900 (que ignoraria a certeza) nem 3.000+1.700 (que ignoraria a
    janela)."""
    obtido = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=(
            _recurso(
                "OK",
                3000,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
            _recurso(
                "PROVAVEL_AGORA",
                900,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.PROVAVEL,
            ),
            _recurso(
                "CONFIRMADO_FUTURO",
                1700,
                janela=JANELA_RECURSO_EXTRAORDINARIO.UM_A_TRES_MESES,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
        )
    )

    assertar_exato(obtido, dinheiro(3000))


@pytest.mark.regra
@pytest.mark.parametrize(
    "janela_futura",
    [
        JANELA_RECURSO_EXTRAORDINARIO.UM_A_TRES_MESES,
        JANELA_RECURSO_EXTRAORDINARIO.QUATRO_A_SEIS_MESES,
        JANELA_RECURSO_EXTRAORDINARIO.SETE_A_DOZE_MESES,
        JANELA_RECURSO_EXTRAORDINARIO.NAO_SEI,
    ],
)
def test_recurso_com_janela_futura_nao_compoe_o_recomendado(
    janela_futura: JANELA_RECURSO_EXTRAORDINARIO,
) -> None:
    """`AC-79`: "recurso apenas previsto para o futuro não compõe o
    recomendado atual" (§13.3), ainda que CONFIRMADO. `ATE_30D` é a ÚNICA
    janela do "momento atual"; as outras quatro — inclusive `NAO_SEI`, que é
    ausência de janela conhecida — ficam de fora."""
    obtido = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=(
            _recurso(
                "R1",
                6000,
                janela=janela_futura,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
        )
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
@pytest.mark.parametrize(
    "certeza_insuficiente",
    [CERTEZA_RECURSO_EXTRAORDINARIO.PROVAVEL, CERTEZA_RECURSO_EXTRAORDINARIO.POSSIVEL],
)
def test_recurso_nao_confirmado_nao_compoe_o_recomendado(
    certeza_insuficiente: CERTEZA_RECURSO_EXTRAORDINARIO,
) -> None:
    """`AC-79`, o outro lado do `E`: mesmo chegando em `ATE_30D`, o recurso
    `PROVAVEL` ou `POSSIVEL` não compõe. `CONFIRMADO` é o único membro do
    domínio que satisfaz "confirmados" (§13.3) — provável não é confirmado,
    e recomendar sobre provável seria recomendar dinheiro que pode não
    existir."""
    obtido = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=(
            _recurso(
                "R1",
                6000,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=certeza_insuficiente,
            ),
        )
    )

    assertar_exato(obtido, dinheiro(0))


# ---------------------------------------------------------------------------
# Ordem 4 (§13.7) — ATIVOS_RECOMENDADOS
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_ativo_possivel_fica_so_no_potencial() -> None:
    """`AC-78` literal: "dado um ativo classificado `MOBILIZACAO_POSSIVEL` e
    outro `MOBILIZACAO_RECOMENDAVEL`, apenas o `MOBILIZACAO_RECOMENDAVEL`
    compõe a soma — e o `MOBILIZACAO_POSSIVEL` permanece contando apenas em
    `ATAQUE_IMEDIATO_POTENCIAL`". O total é 300, não 800; que os 500 do
    possível continuam no potencial é provado em
    `test_ataque_imediato_potencial.py`."""
    obtido = calcular_ATIVOS_RECOMENDADOS(
        ativos=(
            _ativo("A_POSSIVEL", 500, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL),
            _ativo("A_RECOMENDAVEL", 300, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
        )
    )

    assertar_exato(obtido, dinheiro(300))


@pytest.mark.regra
@pytest.mark.parametrize("classe", CLASSES_NAO_RECOMENDAVEIS)
def test_ativo_nao_recomendavel_nao_entra_automaticamente(
    classe: CLASSIFICACAO_MOBILIZACAO,
) -> None:
    """`AC-78`, `EC-30`: `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` "não
    entram automaticamente" (§13.3), e `MOBILIZACAO_POSSIVEL` também não —
    nem com valor líquido realizável alto. "Automaticamente" é a palavra da
    norma: o que traria um item com ressalva para dentro é decisão humana
    sobre a ressalva, jamais uma regra deste módulo."""
    obtido = calcular_ATIVOS_RECOMENDADOS(ativos=(_ativo("A1", 750000, classe),))

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_ativos_recomendados_somam_todos_os_recomendaveis() -> None:
    """§13.3: `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` — é soma sobre
    TODOS os ativos recomendáveis, não o maior nem o primeiro. Sem condição
    de liquidez: `ItemAtivo` não tem esse campo, porque "com liquidez" é
    exigência que a §13.3 impõe apenas aos investimentos."""
    obtido = calcular_ATIVOS_RECOMENDADOS(
        ativos=(
            _ativo("A1", 1200, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
            _ativo("A2", 800, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
            _ativo("A3", 25, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
        )
    )

    assertar_exato(obtido, dinheiro(2025))


# ---------------------------------------------------------------------------
# Comum às quatro — EC-27 e pureza
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_colecao_vazia_devolve_zero_nas_quatro() -> None:
    """`EC-27`: coleção vazia (e `DINHEIRO_DISPONIVEL = 0`) devolve
    `dinheiro(0)` em cada um dos quatro componentes — nenhum erro, nenhum
    estado desconhecido fabricado."""
    assertar_exato(calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=dinheiro(0)), dinheiro(0))
    assertar_exato(calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=()), dinheiro(0))
    assertar_exato(
        calcular_EXTRAORDINARIOS_RECOMENDADOS(recursos_extraordinarios=()), dinheiro(0)
    )
    assertar_exato(calcular_ATIVOS_RECOMENDADOS(ativos=()), dinheiro(0))


@pytest.mark.regra
def test_as_quatro_recusam_chamada_posicional() -> None:
    """NFR "Pureza (Rodada 3)" (spec §5) e `AC-80`: as quatro assinaturas
    começam com `*`, então toda entrada chega por argumento NOMEADO e nenhuma
    função tem canal de entrada implícito (`EstadoFinanceiro`, `Diagnostico`,
    relógio, global)."""
    with pytest.raises(TypeError):
        calcular_CAIXA_RECOMENDADO(dinheiro(1000))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        calcular_INVESTIMENTOS_RECOMENDADOS(())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        calcular_EXTRAORDINARIOS_RECOMENDADOS(())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        calcular_ATIVOS_RECOMENDADOS(())  # type: ignore[call-arg]
