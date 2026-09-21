"""A máscara e a fronteira de conversão concordam — `RF-47`, `AC-75`,
`AC-76`, `AC-77` (T-127).

**Por que este teste é em Python, e não num runner de JavaScript.** Não há
runner de JS neste projeto e o plano não autoriza um (`plans/app-aluno.
plan.md` §2: zero dependência nova nesta rodada; a mesma restrição que
manteve o HTMX como arquivo servido em vez de pacote). Testar a máscara
"por dentro" exigiria Node ou um browser headless.

Mas o que de fato importa não é o comportamento interno da máscara: é o
**contrato entre ela e `app/montagem/conversao.py`**. Se a máscara emitir
algo que a fronteira recusa, o aluno digita, vê o campo formatado e leva um
`400` — o pior dos mundos. Esse contrato é verificável aqui: a tabela abaixo
declara, para cada entrada de teclado, a saída que `mascaras.js` produz
(derivada das regras documentadas naquele arquivo), e cada saída é submetida
à conversão REAL para provar que é aceita e produz o `Decimal` certo.

A tabela é DADO deste teste — não enunciado de pergunta, não conteúdo de
questionário (`AC-37` segue verde).

**O que este teste não cobre**, e é honesto declarar: ele não executa
`mascaras.js`. Se a implementação em JS divergir das regras aqui declaradas,
este teste continua passando. O que ele garante é que **as regras
declaradas são compatíveis com o servidor** — a metade do risco que dá para
eliminar sem browser. A outra metade (a máscara implementa o que
documentou) fica para a verificação manual do checklist e para `T-128`.

REGRAS: `RF-47`, `AC-75`, `AC-76`, `AC-77`
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
    converter_para_taxa,
)

# (digitação do aluno, saída que `mascaras.js::formatarMoeda` produz,
#  Decimal que `converter_para_dinheiro` tem de devolver)
CASOS_MOEDA: Final[tuple[tuple[str, str, str], ...]] = (
    ("123456", "1.234,56", "1234.56"),
    ("100", "1,00", "1.00"),
    ("5", "0,05", "0.05"),
    ("50", "0,50", "0.50"),
    ("999", "9,99", "9.99"),
    ("100000", "1.000,00", "1000.00"),
    ("123456789", "1.234.567,89", "1234567.89"),
    ("820000", "8.200,00", "8200.00"),
)

# (digitação, saída de `formatarTaxa`, fração que `converter_para_taxa`
#  devolve — a divisão por 100 é do servidor, nunca da máscara)
CASOS_TAXA: Final[tuple[tuple[str, str, str], ...]] = (
    ("4,5", "4,5", "0.045"),
    ("12", "12", "0.12"),
    ("0,99", "0,99", "0.0099"),
    ("2,75", "2,75", "0.0275"),
)

# Entradas que a máscara NÃO "salva": seguem como digitadas e a fronteira
# recusa — `AC-77`, `EC-01`.
ENTRADAS_AMBIGUAS: Final[tuple[str, ...]] = (
    "1.2,3",
    "1.2.3",
    "mil reais",
    "",
    "1,2,3",
)


@pytest.mark.parametrize(("digitado", "formatado", "esperado"), CASOS_MOEDA)
def test_saida_da_mascara_de_moeda_e_aceita_pela_fronteira_ac_75(
    digitado: str, formatado: str, esperado: str
) -> None:
    """`AC-75`: o que a máscara exibe é exatamente o que a fronteira aceita,
    e o `Decimal` resultante é o valor que o aluno quis digitar.

    `digitado` entra na asserção para que a tabela não vire decoração: a
    formatação declarada tem de ser função SÓ dos dígitos teclados — é
    assim que `formatarMoeda` opera (descarta não-dígitos e reposiciona os
    centavos), e é isso que torna `EC-22` verdadeiro (colar `"R$ 1.234,56"`
    dá o mesmo resultado que teclar `"123456"`)."""
    assert "".join(caractere for caractere in formatado if caractere.isdigit()).lstrip(
        "0"
    ) == digitado.lstrip("0")
    assert converter_para_dinheiro(formatado) == Decimal(esperado)


@pytest.mark.parametrize(("digitado", "formatado", "esperado"), CASOS_TAXA)
def test_saida_da_mascara_de_taxa_e_aceita_pela_fronteira_ac_76(
    digitado: str, formatado: str, esperado: str
) -> None:
    """`AC-76`: taxa submete o percentual (`"4,5"`), e é o SERVIDOR que
    divide por 100. A máscara nunca envia a fração já dividida."""
    assert formatado == digitado
    assert converter_para_taxa(formatado) == Decimal(esperado)


def test_a_mascara_de_taxa_nunca_emite_o_caractere_por_cento_ac_76() -> None:
    """`AC-76`: `_CARACTERES_ACEITOS` recusa `%`. Se a máscara colocasse o
    símbolo dentro do `<input>`, toda taxa levaria `400` — por isso o `%` de
    `pergunta.html` é um `<span>` irmão, `aria-hidden`, fora do campo."""
    for _digitado, formatado, _esperado in CASOS_TAXA:
        assert "%" not in formatado

    with pytest.raises(ErroConversaoInvalida):
        converter_para_taxa("4,5%")


@pytest.mark.parametrize("ambigua", ENTRADAS_AMBIGUAS)
def test_entrada_ambigua_e_recusada_e_nada_e_gravado_ac_77(ambigua: str) -> None:
    """`AC-77`/`EC-01`: a máscara deixa passar o ambíguo em vez de adivinhar,
    e a fronteira recusa. Nenhuma coerção a `0` em nenhum caminho."""
    with pytest.raises(ErroConversaoInvalida):
        converter_para_dinheiro(ambigua)


def test_zero_continua_sendo_valor_legitimo() -> None:
    """Zero é resposta válida (`§11.7`, `PAGAMENTO_MENSAL_EFETIVO`): a
    máscara formatando `"0"` como `"0,00"` não pode virar recusa."""
    assert converter_para_dinheiro("0,00") == Decimal("0.00")
