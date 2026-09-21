"""Testes de `calcular_ATAQUE_IMEDIATO_POTENCIAL` (T-103) — RF-44 · §13.2.

Cobre os critérios comportamentais de `T-103`. O risco de implementação desta
função não está na soma — está em QUEM entra nela:

- `AC-77` — as cinco parcelas somam, e o filtro de classificação do potencial
  admite `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL`. Nenhum item
  `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra.
- `EC-30` — e não entra nem com valor líquido alto: as ressalvas não são
  resolvidas automaticamente pelo motor.
- `EC-27` — coleções vazias com `DINHEIRO_DISPONIVEL = 0` dão `0`; nenhum erro,
  nenhum desconhecido fabricado.
- `RESERVA_MOBILIZAVEL` desconhecida contribui `0` para a soma — contribuição
  ARITMÉTICA. A pendência continua legível em `Diagnostico.RESERVA_MOBILIZAVEL`
  (`RF-41`, plano R3.8), que não é tocada aqui.

O contraste com `AC-79` (recurso extraordinário futuro compõe o POTENCIAL e
não compõe o recomendado) é testado dos dois lados: o lado do potencial está
aqui; o lado do recomendado, em `test_componentes_recomendados.py` (`T-104`).

Tolerância ZERO em toda asserção (spec §5, `OQ-34` respondida): `assertar_exato`,
nunca `assertar_monetario`. Os gabaritos `GAB-AI` formais são `T-110`+, em
`tests/gabaritos_ataque_imediato/` — não estão aqui.
"""

from decimal import Decimal

import pytest

from engine.ataque_imediato import calcular_ATAQUE_IMEDIATO_POTENCIAL
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
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO
from tests.conftest import assertar_exato


def _ativo(item_id: str, valor: int, classe: CLASSIFICACAO_MOBILIZACAO) -> ItemAtivo:
    """RF-54, RF-59, T-125 — mesma fixture canônica de
    `tests/regras/test_componentes_recomendados.py::_ativo`: `classe` escolhe
    os campos BRUTOS de §14.4-§14.9 que fazem `classificar_ativo_fisico`
    DERIVAR exatamente `classe` (assume `valor > 0`, único caso deste
    arquivo)."""
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
    """RF-53, RF-59, T-125 — mesma fixture canônica de
    `tests/regras/test_componentes_recomendados.py::_investimento`: `classe`
    escolhe os campos BRUTOS de §14.3.1 que fazem `classificar_investimento`
    DERIVAR exatamente `classe` (assume `valor > 0`, único caso deste
    arquivo)."""
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


@pytest.mark.regra
def test_soma_as_cinco_parcelas_da_secao_13_2() -> None:
    """`AC-77`: com as quatro classificações presentes, o potencial soma
    `DINHEIRO_DISPONIVEL` + `RESERVA_MOBILIZAVEL` + investimentos líquidos
    mobilizáveis + recursos extraordinários potenciais + ativos
    `POSSIVEL`/`RECOMENDAVEL` — e nada além disso.

    Números escolhidos para que cada parcela seja identificável no total:
    1.000 caixa + 2.000 reserva + 4.000 investimento líquido recomendável
    + 8.000 recurso extraordinário + 16.000 ativo possível + 32.000 ativo
    recomendável = 63.000. Os itens `COM_RESSALVAS` (64.000) e
    `NAO_MOBILIZAR` (128.000) ficam de fora — se algum entrasse, o total
    denunciaria exatamente qual.
    """
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(1000),
        RESERVA_MOBILIZAVEL=dinheiro(2000),
        investimentos=(
            _investimento(
                "I1",
                4000,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
            _investimento(
                "I2",
                64000,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
            ),
        ),
        recursos_extraordinarios=(
            _recurso(
                "R1",
                8000,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
        ),
        ativos=(
            _ativo("A1", 16000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL),
            _ativo("A2", 32000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
            _ativo("A3", 128000, CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR),
        ),
    )

    assertar_exato(obtido, dinheiro(63000))


@pytest.mark.regra
def test_ativo_possivel_e_ativo_recomendavel_entram_no_potencial() -> None:
    """`AC-77`: as DUAS classes mobilizáveis entram — provado sem nenhuma
    outra parcela para que o resultado seja a soma dos dois ativos e nada
    mais. Uma implementação que aceitasse só `MOBILIZACAO_RECOMENDAVEL`
    (o filtro do RECOMENDADO, §13.3) daria 300, não 800."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=(
            _ativo("A1", 500, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL),
            _ativo("A2", 300, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
        ),
    )

    assertar_exato(obtido, dinheiro(800))


@pytest.mark.regra
@pytest.mark.parametrize(
    "classe_excluida",
    [
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
        CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
    ],
)
def test_ativo_com_ressalvas_ou_nao_mobilizar_nao_entra_nem_com_valor_alto(
    classe_excluida: CLASSIFICACAO_MOBILIZACAO,
) -> None:
    """`EC-30` e `AC-77`: ativo `MOBILIZACAO_COM_RESSALVAS` (ou
    `NAO_MOBILIZAR`) com valor líquido realizável ALTO não entra no
    potencial. O valor é alto de propósito: é justamente o item caro que
    tenta o motor a "resolver a ressalva sozinho" — e a §13 proíbe."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(100),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=(_ativo("A1", 999999, classe_excluida),),
    )

    assertar_exato(obtido, dinheiro(100))


@pytest.mark.regra
@pytest.mark.parametrize(
    "classe_excluida",
    [
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
        CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
    ],
)
def test_investimento_com_ressalvas_ou_nao_mobilizar_nao_entra_no_potencial(
    classe_excluida: CLASSIFICACAO_MOBILIZACAO,
) -> None:
    """`AC-77` é sobre ITEM, não só sobre ativo: "nenhum item
    `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra na soma". O
    investimento líquido dessas duas classes não é "líquido mobilizável" —
    liquidez não promove classificação."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(100),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(_investimento("I1", 50000, liquidez=True, classe=classe_excluida),),
        recursos_extraordinarios=(),
        ativos=(),
    )

    assertar_exato(obtido, dinheiro(100))


@pytest.mark.regra
def test_recurso_extraordinario_futuro_e_nao_confirmado_compoe_o_potencial() -> None:
    """`AC-79`, lado do POTENCIAL: a §13.2 chama a parcela de
    `RECURSOS_EXTRAORDINARIOS_POTENCIAIS` e não lhe impõe filtro de janela
    nem de certeza. O recurso apenas previsto e não confirmado entra aqui —
    e é por isso que `AC-79` pode dizer que ele não compõe
    `EXTRAORDINARIOS_RECOMENDADOS` "ainda que componha" os potenciais.
    Filtrar por `ATE_30D`/`CONFIRMADO` nesta função apagaria a diferença
    entre §13.2 e §13.3."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(
            _recurso(
                "R1",
                7000,
                janela=JANELA_RECURSO_EXTRAORDINARIO.SETE_A_DOZE_MESES,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.POSSIVEL,
            ),
        ),
        ativos=(),
    )

    assertar_exato(obtido, dinheiro(7000))


@pytest.mark.regra
def test_investimento_sem_liquidez_nao_e_liquido_mobilizavel() -> None:
    """§13.2: a parcela é `INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS` — líquidos E
    mobilizáveis. O investimento recomendável SEM liquidez não é líquido, e
    portanto não compõe o potencial; só o líquido compõe."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(
            _investimento(
                "I_SEM_LIQUIDEZ",
                9000,
                liquidez=False,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
            _investimento(
                "I_COM_LIQUIDEZ",
                1500,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
            ),
        ),
        recursos_extraordinarios=(),
        ativos=(),
    )

    assertar_exato(obtido, dinheiro(1500))


@pytest.mark.regra
def test_reserva_desconhecida_contribui_zero_para_a_soma() -> None:
    """`RESERVA_MOBILIZAVEL = DESCONHECIDO` (`GAB-AI-04`) contribui `0` para
    a soma: o potencial vale exatamente o que valeria com a reserva em zero,
    e a função devolve um `Dinheiro` — nunca propaga o desconhecido para a
    saída, o que tornaria o potencial inexprimível sempre que a decisão de
    reserva fosse adiada (`EC-27`).

    É contribuição ARITMÉTICA, não conversão de informação: quem mantém a
    pendência legível é `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez`
    (`RF-41`, plano R3.8), fora desta função."""
    parcelas_sem_reserva = {
        "DINHEIRO_DISPONIVEL": dinheiro(1000),
        "investimentos": (),
        "recursos_extraordinarios": (),
        "ativos": (_ativo("A1", 400, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),),
    }

    com_desconhecido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        **parcelas_sem_reserva,  # type: ignore[arg-type]
    )
    com_zero = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        RESERVA_MOBILIZAVEL=dinheiro(0),
        **parcelas_sem_reserva,  # type: ignore[arg-type]
    )

    assertar_exato(com_desconhecido, dinheiro(1400))
    assertar_exato(com_desconhecido, com_zero)
    # Que a saída nunca é `DESCONHECIDO` já é provado ANTES do runtime: o tipo
    # de retorno é `Dinheiro`, e `mypy --strict` recusa (`comparison-overlap`)
    # até escrever `is not DESCONHECIDO` aqui. Em runtime resta a evidência
    # direta de que é valor monetário somável.
    assert isinstance(com_desconhecido, Decimal)


@pytest.mark.regra
def test_reserva_zero_conhecida_soma_normalmente() -> None:
    """`dinheiro(0)` é valor legítimo e soma normalmente — a checagem da
    função é `is DESCONHECIDO`, nunca "é falsy" (mesmo padrão de `AC-32` em
    `_somar_pagamentos`). O teste existe para que uma implementação que use
    `if RESERVA_MOBILIZAVEL:` continue passando por acidente aqui e falhe no
    caso conhecido positivo abaixo."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(5000),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=(),
    )

    assertar_exato(obtido, dinheiro(5000))


@pytest.mark.regra
def test_colecoes_vazias_e_dinheiro_zero_devolvem_zero() -> None:
    """`EC-27`: as três coleções vazias e `DINHEIRO_DISPONIVEL = 0` devolvem
    `dinheiro(0)` — nenhum erro, nenhum estado desconhecido fabricado. Soma
    de coleção vazia é `0`, não pendência."""
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=(),
    )

    assertar_exato(obtido, dinheiro(0))
    # "Nenhum desconhecido fabricado" (`EC-27`) é garantido pelo tipo de
    # retorno `Dinheiro`, verificado no comando `build` — em runtime, a
    # evidência é que o resultado é um valor monetário, não um `Enum`.
    assert isinstance(obtido, Decimal)


@pytest.mark.regra
def test_funcao_e_pura_recusa_chamada_posicional() -> None:
    """NFR "Pureza (Rodada 3)" (spec §5) e `AC-80`: as cinco entradas chegam
    por argumento NOMEADO — o `*` recusa a chamada posicional. Provar isso é
    provar que a função não tem canal de entrada implícito
    (`EstadoFinanceiro`, `Diagnostico`, relógio, global)."""
    with pytest.raises(TypeError):
        calcular_ATAQUE_IMEDIATO_POTENCIAL(  # type: ignore[call-arg]
            dinheiro(1000),
            dinheiro(0),
            (),
            (),
            (),
        )
