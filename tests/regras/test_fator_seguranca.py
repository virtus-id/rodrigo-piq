"""Testes de `calcular_fator_seguranca` — RF-25, AC-36, AC-26.

`FATOR_SEGURANCA` é composto de forma **subtrativa**: soma as quatro
reduções, subtrai de 1 e só então aplica o piso `P_FATOR_SEGURANCA_MINIMO`.
Composição multiplicativa é proibida. AC-36 fecha o exemplo canônico da
§11.8/Definições §3 (0,20 + 0,15 + 0,10 com piso 0,60 ⇒ 0,60); AC-26 garante
que `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO` e `P_REDUCAO_HISTORICO_RECAIDA` são
somadas separadamente, sem que uma absorva a outra.
"""

from decimal import Decimal

import pytest

from engine.diagnostico import calcular_fator_seguranca
from engine.estado import TIPO_RENDA
from engine.parametros import Parametros
from engine.tipos import CONFIABILIDADE_DADOS, NIVEL_RISCO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


@pytest.mark.gabarito
def test_AC36_soma_primeiro_piso_depois() -> None:
    """AC-36: reduções 0,20 (renda variável) + 0,15 (risco comportamental
    alto) + 0,10 (recaída) com piso 0,60 ⇒ `FATOR_SEGURANCA` = 0,60.

    Confiabilidade ALTA não contribui (redução 0). Bruto = 1 - 0,45 = 0,55;
    `MAX(0,60; 0,55) = 0,60`.
    """
    parametros = _parametros_reais()
    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.VARIAVEL,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.ALTA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.ALTO,
        RISCO_RECAIDA=NIVEL_RISCO.ALTO,
        parametros=parametros,
    )
    assertar_exato(resultado.REDUCAO_RENDA_VARIAVEL, Decimal("0.20"))
    assertar_exato(resultado.REDUCAO_CONFIABILIDADE, Decimal("0"))
    assertar_exato(resultado.REDUCAO_RISCO_COMPORTAMENTAL, Decimal("0.15"))
    assertar_exato(resultado.REDUCAO_RECAIDA, Decimal("0.10"))
    assertar_exato(resultado.REDUCAO_SEGURANCA_TOTAL, Decimal("0.45"))
    assertar_exato(resultado.FATOR_SEGURANCA, Decimal("0.60"))


@pytest.mark.regra
def test_AC26_risco_comportamental_e_recaida_nao_se_absorvem() -> None:
    """AC-26: `RISCO_COMPORTAMENTAL_GERAL` = ALTO e `RISCO_RECAIDA` = ALTO
    (histórico de recaída) aplicam as duas reduções somadas, não a maior
    das duas nem uma única redução combinada."""
    parametros = _parametros_reais()
    reducao_comportamental = parametros.numero("P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO")
    reducao_recaida = parametros.numero("P_REDUCAO_HISTORICO_RECAIDA")

    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.FIXA,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.ALTA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.ALTO,
        RISCO_RECAIDA=NIVEL_RISCO.ALTO,
        parametros=parametros,
    )

    assertar_exato(resultado.REDUCAO_RISCO_COMPORTAMENTAL, reducao_comportamental)
    assertar_exato(resultado.REDUCAO_RECAIDA, reducao_recaida)
    assertar_exato(
        resultado.REDUCAO_SEGURANCA_TOTAL, reducao_comportamental + reducao_recaida
    )
    assertar_exato(
        resultado.FATOR_SEGURANCA,
        max(
            parametros.numero("P_FATOR_SEGURANCA_MINIMO"),
            Decimal(1) - (reducao_comportamental + reducao_recaida),
        ),
    )


@pytest.mark.regra
def test_moderado_nao_aciona_reducao_comportamental() -> None:
    """§11.4/AC-26: somente ALTO aciona `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO`
    — MODERADO não tem redução parcial."""
    parametros = _parametros_reais()
    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.FIXA,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.ALTA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.MODERADO,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        parametros=parametros,
    )
    assertar_exato(resultado.REDUCAO_RISCO_COMPORTAMENTAL, Decimal("0"))
    assertar_exato(resultado.REDUCAO_RECAIDA, Decimal("0"))
    assertar_exato(resultado.FATOR_SEGURANCA, Decimal("1"))


@pytest.mark.regra
def test_tipo_renda_fixa_nao_aciona_reducao_renda_variavel() -> None:
    """`TIPO_RENDA` = FIXA ⇒ `REDUCAO_RENDA_VARIAVEL` = 0."""
    parametros = _parametros_reais()
    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.FIXA,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.ALTA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        parametros=parametros,
    )
    assertar_exato(resultado.REDUCAO_RENDA_VARIAVEL, Decimal("0"))
    assertar_exato(resultado.FATOR_SEGURANCA, Decimal("1"))


@pytest.mark.regra
def test_tipo_renda_relativamente_estavel_nao_aciona_reducao() -> None:
    """`TIPO_RENDA` = RELATIVAMENTE_ESTAVEL não aciona `REDUCAO_RENDA_VARIAVEL`
    — só `VARIAVEL` aciona (interpretação documentada, ver docstring de
    `calcular_fator_seguranca`)."""
    parametros = _parametros_reais()
    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.RELATIVAMENTE_ESTAVEL,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.ALTA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        parametros=parametros,
    )
    assertar_exato(resultado.REDUCAO_RENDA_VARIAVEL, Decimal("0"))


@pytest.mark.regra
def test_confiabilidade_media_e_baixa() -> None:
    """`CONFIABILIDADE_DADOS` MEDIA e BAIXA acionam suas próprias reduções."""
    parametros = _parametros_reais()

    media = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.FIXA,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.MEDIA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        parametros=parametros,
    )
    assertar_exato(
        media.REDUCAO_CONFIABILIDADE, parametros.numero("P_REDUCAO_CONFIABILIDADE_MEDIA")
    )

    baixa = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.FIXA,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.BAIXA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        parametros=parametros,
    )
    assertar_exato(
        baixa.REDUCAO_CONFIABILIDADE, parametros.numero("P_REDUCAO_CONFIABILIDADE_BAIXA")
    )


@pytest.mark.regra
def test_piso_nao_deixa_fator_seguranca_abaixo_do_minimo() -> None:
    """Todas as quatro reduções ativas ao mesmo tempo — soma ultrapassa
    largamente 1, mas o piso `P_FATOR_SEGURANCA_MINIMO` impede que
    `FATOR_SEGURANCA` fique abaixo dele."""
    parametros = _parametros_reais()
    resultado = calcular_fator_seguranca(
        TIPO_RENDA_ATUAL=TIPO_RENDA.VARIAVEL,
        CONFIABILIDADE_DADOS_ATUAL=CONFIABILIDADE_DADOS.BAIXA,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.ALTO,
        RISCO_RECAIDA=NIVEL_RISCO.ALTO,
        parametros=parametros,
    )
    assertar_exato(resultado.FATOR_SEGURANCA, parametros.numero("P_FATOR_SEGURANCA_MINIMO"))
