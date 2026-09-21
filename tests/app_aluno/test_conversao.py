"""Testes de `app/montagem/conversao.py` — RF-13, AC-09, AC-10, EC-01 (T-38).

Cobre a fronteira `Decimal` única pelo comportamento observável: o `Decimal`
devolvido, ou o `ErroConversaoInvalida` levantado. Casos exatos e a estrutura
do erro tipado; a propriedade universal por Hypothesis (nenhuma entrada
aceita produz `float`) é `T-39`, tarefa separada.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
    converter_para_taxa,
)


class TestConverterParaDinheiro:
    """AC-10: `"1234,56"` produz exatamente `Decimal("1234.56")`."""

    def test_ac_10_virgula_decimal_simples(self) -> None:
        resultado = converter_para_dinheiro("1234,56")
        assert resultado == Decimal("1234.56")
        assert isinstance(resultado, Decimal)

    def test_formato_brasileiro_completo_milhar_e_decimal(self) -> None:
        # "." é milhar (removido), "," é decimal (vira ".") — regra 2.
        assert converter_para_dinheiro("1.234,56") == Decimal("1234.56")

    def test_formato_brasileiro_milhoes(self) -> None:
        assert converter_para_dinheiro("1.234.567,89") == Decimal("1234567.89")

    def test_apenas_digitos_sem_separador(self) -> None:
        assert converter_para_dinheiro("1234") == Decimal("1234")

    def test_ponto_ambiguo_como_decimal_um_digito(self) -> None:
        # Regra 4: um único ponto com 1 dígito após ele é decimal.
        assert converter_para_dinheiro("12.5") == Decimal("12.5")

    def test_ponto_ambiguo_como_decimal_dois_digitos(self) -> None:
        # Regra 4: um único ponto com 2 dígitos após ele é decimal.
        assert converter_para_dinheiro("1234.56") == Decimal("1234.56")

    def test_ponto_ambiguo_como_milhar_tres_digitos(self) -> None:
        # Regra 4: um único ponto seguido de exatamente 3 dígitos é milhar,
        # nunca decimal — "1.234" é mil duzentos e trinta e quatro.
        assert converter_para_dinheiro("1.234") == Decimal("1234")

    def test_multiplos_pontos_sao_sempre_milhar(self) -> None:
        assert converter_para_dinheiro("1.234.567") == Decimal("1234567")

    def test_espacos_nas_bordas_sao_descartados(self) -> None:
        assert converter_para_dinheiro("  1234,56  ") == Decimal("1234.56")

    def test_resultado_nunca_e_float(self) -> None:
        resultado = converter_para_dinheiro("1234,56")
        assert not isinstance(resultado, float)


class TestConverterParaTaxa:
    """A conversão de taxa é separada da de moeda: o mesmo texto normalizado
    de moeda, para taxa, é dividido por 100 (percentual → fração)."""

    def test_taxa_percentual_simples(self) -> None:
        # "4" no campo TAXA (____ %) representa 4% a.m. == Decimal("0.04").
        assert converter_para_taxa("4") == Decimal("0.04")

    def test_taxa_com_virgula_decimal(self) -> None:
        assert converter_para_taxa("4,5") == Decimal("0.045")

    def test_taxa_e_dinheiro_sao_conversoes_distintas_para_a_mesma_entrada(self) -> None:
        # O mesmo texto normalizado produz valores diferentes conforme a
        # função chamada — a divisão por 100 só ocorre na conversão de taxa.
        assert converter_para_dinheiro("4") == Decimal("4")
        assert converter_para_taxa("4") == Decimal("0.04")

    def test_resultado_de_taxa_nunca_e_float(self) -> None:
        resultado = converter_para_taxa("4,5")
        assert not isinstance(resultado, float)


class TestEntradaInvalidaRecusada:
    """EC-01: `"mil reais"`, `"1.2.3"` e string vazia são recusados com erro
    tipado, sem coerção a `0`."""

    def test_texto_nao_numerico_e_recusado(self) -> None:
        with pytest.raises(ErroConversaoInvalida) as excecao:
            converter_para_dinheiro("mil reais")
        assert excecao.value.valor_recusado == "mil reais"
        assert excecao.value.motivo  # motivo nomeado, nunca vazio

    def test_multiplos_pontos_decimais_ambiguos_e_recusado(self) -> None:
        with pytest.raises(ErroConversaoInvalida) as excecao:
            converter_para_dinheiro("1.2.3")
        assert excecao.value.valor_recusado == "1.2.3"

    def test_string_vazia_e_recusada(self) -> None:
        with pytest.raises(ErroConversaoInvalida) as excecao:
            converter_para_dinheiro("")
        assert excecao.value.motivo == "entrada vazia"

    def test_string_so_com_espacos_e_recusada(self) -> None:
        with pytest.raises(ErroConversaoInvalida):
            converter_para_dinheiro("   ")

    def test_multiplas_virgulas_e_recusado(self) -> None:
        with pytest.raises(ErroConversaoInvalida):
            converter_para_dinheiro("1,2,3")

    def test_erro_tipado_nunca_generico(self) -> None:
        # ErroConversaoInvalida é subclasse própria de Exception, não uma
        # ValueError/TypeError genérica sem contexto.
        with pytest.raises(ErroConversaoInvalida) as excecao:
            converter_para_dinheiro("abc")
        assert isinstance(excecao.value, ErroConversaoInvalida)
        assert "abc" in str(excecao.value)

    def test_recusa_tambem_vale_para_taxa(self) -> None:
        with pytest.raises(ErroConversaoInvalida):
            converter_para_taxa("um por cento")

    def test_nenhuma_coercao_a_zero(self) -> None:
        # Nunca existe um caminho em que entrada inválida devolva Decimal(0)
        # em vez de levantar — a única reação é a exceção.
        for entrada_invalida in ("mil reais", "1.2.3", "", "R$ 10", "10,,5"):
            with pytest.raises(ErroConversaoInvalida):
                converter_para_dinheiro(entrada_invalida)
