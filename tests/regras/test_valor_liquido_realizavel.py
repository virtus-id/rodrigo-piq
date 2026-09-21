"""Testes de `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL` (T-121) —
RF-57, RF-58 · §14.12 · §14.14 `deriveValorLiquidoRealizavelAtivo`/
`_Disponivel`.

Cobre as DUAS funções de `engine/classificacao_ativos.py` isoladamente, com
os valores literais do exemplo positivo/negativo de §14.12.3 (o negativo é o
gabarito formal `GAB-NFI-12`, §14.16) e a prova explícita de que `DESCONHECIDO`
nunca vira zero silenciosamente (RF-58) — pedido explícito de `T-126`, não
implícito no valor final bater.

Duas funções, nunca compostas: `VALOR_LIQUIDO_REALIZAVEL_ATIVO` PODE ser
negativo (§14.12.1); `_DISPONIVEL = MAX(0, ...)` NUNCA pode (§14.12.2,
REGRA CANÔNICA). Tolerância ZERO em toda asserção monetária (spec §5,
gabaritos de homologação): `assertar_exato`, nunca `assertar_monetario`.
"""

from unittest.mock import sentinel

import pytest

from engine.classificacao_ativos import (
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO,
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL,
)
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO
from tests.conftest import assertar_exato


@pytest.mark.regra
def test_GAB_NFI_12_valor_liquido_negativo() -> None:
    """`GAB-NFI-12` (`AC-94`), literal de §14.16/§14.12.3 coluna "Exemplo
    negativo": `VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=
    105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_
    REALIZAVEL_ATIVO=-10.000` (negativo, REGRA CANÔNICA §14.12.2 — nenhum
    MAX aplicado nesta função) e `_DISPONIVEL=0` (MAX zera o negativo).
    Tolerância zero — gabarito de homologação."""
    valor_liquido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=True,
        SALDO_PASSIVO_VINCULADO=dinheiro(105000),
        POSSUI_CUSTO_DESMOBILIZACAO=True,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(5000),
    )
    assertar_exato(valor_liquido, dinheiro(-10000))

    disponivel = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=valor_liquido
    )
    assertar_exato(disponivel, dinheiro(0))


@pytest.mark.regra
def test_exemplo_positivo_14_12_3() -> None:
    """Exemplo positivo da tabela §14.12.3, literal: `VALOR_ESTIMADO_ATIVO=
    100.000`, `SALDO_PASSIVO_VINCULADO=70.000`, `CUSTOS_ESTIMADOS_
    DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=25.000` e
    `_DISPONIVEL=25.000` (MAX não altera valor já positivo). RF-57."""
    valor_liquido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=True,
        SALDO_PASSIVO_VINCULADO=dinheiro(70000),
        POSSUI_CUSTO_DESMOBILIZACAO=True,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(5000),
    )
    assertar_exato(valor_liquido, dinheiro(25000))

    disponivel = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=valor_liquido
    )
    assertar_exato(disponivel, dinheiro(25000))


@pytest.mark.regra
def test_passivo_existe_mas_desconhecido_propaga_desconhecido_nunca_zero() -> None:
    """`RF-58`, `AC-99`, `EC-36`(normalização): `SALDO_PASSIVO_VINCULADO`
    EXISTE (`POSSUI_PASSIVO_VINCULADO=True`) mas é `DESCONHECIDO` →
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO is DESCONHECIDO`, nunca `0` como se o
    passivo não existisse. Teste dedicado, separado do de custo, para que
    uma implementação que trate só um dos dois campos não passe por
    coincidência."""
    obtido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=True,
        SALDO_PASSIVO_VINCULADO=DESCONHECIDO,
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
    )
    assert obtido is DESCONHECIDO, "passivo existente e desconhecido nunca vira 0 (RF-58)"


@pytest.mark.regra
def test_custo_desmobilizacao_existe_mas_desconhecido_propaga_desconhecido() -> None:
    """`RF-58`, `AC-99`: mesma regra do teste anterior, mas para
    `CUSTOS_ESTIMADOS_DESMOBILIZACAO` — teste SEPARADO, como a `AC-99`
    exige ("a mesma regra vale para `CUSTOS_ESTIMADOS_DESMOBILIZACAO`
    desconhecido"). `POSSUI_CUSTO_DESMOBILIZACAO=True` com valor
    `DESCONHECIDO` → resultado desconhecido, nunca `0`."""
    obtido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=True,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=DESCONHECIDO,
    )
    assert obtido is DESCONHECIDO, "custo existente e desconhecido nunca vira 0 (RF-58)"


@pytest.mark.regra
def test_valor_estimado_desconhecido_vence_sem_avaliar_passivo_e_custo() -> None:
    """`EC-36`: `VALOR_ESTIMADO_ATIVO is DESCONHECIDO` → `DESCONHECIDO` por
    propagação direta (§14.14, primeira guarda) — "nem passivo nem custo
    chegam a ser avaliados". Prova por construção de dado: `sentinel.NUNCA_
    LIDO` no lugar de `SALDO_PASSIVO_VINCULADO`/`CUSTOS_ESTIMADOS_
    DESMOBILIZACAO` não é `Dinheiro` nem `Desconhecido` — se a função
    chegasse a comparar/subtrair esse valor, levantaria `TypeError` antes
    de retornar; como o teste passa sem exceção, a guarda 1 realmente
    retorna sem tocar nos parâmetros seguintes."""
    obtido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=DESCONHECIDO,
        POSSUI_PASSIVO_VINCULADO=True,
        SALDO_PASSIVO_VINCULADO=sentinel.NUNCA_LIDO,
        POSSUI_CUSTO_DESMOBILIZACAO=True,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=sentinel.NUNCA_LIDO,
    )
    assert obtido is DESCONHECIDO


@pytest.mark.regra
def test_nao_possui_passivo_nem_custo_e_tratado_como_zero_nao_desconhecido() -> None:
    """`RF-58`, distinção das duas pontas: `POSSUI_PASSIVO_VINCULADO=False`
    e `POSSUI_CUSTO_DESMOBILIZACAO=False` (§14.12.4/§14.12.5, "não existe" →
    0) resultam em `VALOR_LIQUIDO_REALIZAVEL_ATIVO = VALOR_ESTIMADO_ATIVO`
    exato, DISTINTO de "existe e desconhecido" (`DESCONHECIDO`, testado
    acima). Os valores desconhecidos passados abaixo não são lidos porque
    `POSSUI_*=False` normaliza para 0 antes de qualquer checagem de
    desconhecido — se fossem lidos, o resultado seria `DESCONHECIDO`, não
    `100.000`."""
    obtido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
        VALOR_ESTIMADO_ATIVO=dinheiro(100000),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=DESCONHECIDO,
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=DESCONHECIDO,
    )
    assertar_exato(obtido, dinheiro(100000))


@pytest.mark.regra
def test_disponivel_nunca_negativo_mesmo_alimentado_com_resultado_negativo() -> None:
    """`RF-57`, REGRA CANÔNICA §14.12.2: `_DISPONIVEL` NUNCA é negativo,
    mesmo recebendo diretamente o resultado negativo do teste de
    `GAB-NFI-12` acima como entrada. `Decimal` exato, tolerância zero —
    nenhuma margem para um `MAX` mal aplicado devolver o negativo intacto."""
    disponivel = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=dinheiro(-10000)
    )
    assertar_exato(disponivel, dinheiro(0))
    assert disponivel is not DESCONHECIDO
    assert disponivel >= dinheiro(0), "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL nunca negativo"


@pytest.mark.regra
def test_disponivel_propaga_desconhecido_sem_aplicar_max() -> None:
    """`AC-94`, `GAB-NFI-12`: `_DISPONIVEL` propaga `DESCONHECIDO` sem
    aplicar `MAX` sobre um desconhecido — `MAX(0, DESCONHECIDO)` não é uma
    operação válida, e a função nunca tenta computá-la."""
    obtido = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=DESCONHECIDO
    )
    assert obtido is DESCONHECIDO
