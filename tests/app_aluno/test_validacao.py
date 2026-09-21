"""Testes de `collection/validacao.py` — RF-07, AC-06, EC-02 (T-13).

Cobre `validar_cruzada` pelo comportamento observável (o `ResultadoValidacao`
devolvido), nunca por implementação interna. O caso normativo é
`VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`, por `MARGEM_ID` (§15.1,
canônica linha 5167).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from collection.registro import EscopoRepeticao
from collection.validacao import ResultadoValidacao, ValidacaoCruzada, validar_cruzada


class _RespostasDeTeste:
    """Dublê mínimo de `Respostas` (`Protocol`), sem depender de
    `collection/respostas.py` (T-22, ainda não implementada) — mesmo padrão
    de `tests/app_aluno/test_condicoes.py::_RespostasDeTeste` e
    `tests/app_aluno/test_interpolacao.py::_RespostasDeTeste`. As chaves são
    `(item_id, variavel)`, para permitir valores distintos por item."""

    def __init__(self, valores: dict[tuple[str, str], object] | None = None) -> None:
        self._valores = valores or {}

    def valor_no_item(self, item_id: str, variavel: str) -> object | None:
        return self._valores.get((item_id, variavel))


_VALIDACAO_MARGEM = ValidacaoCruzada(
    variavel_esquerda="VALOR_UTILIZADO_MARGEM",
    operador="<=",
    variavel_direita="VALOR_TOTAL_MARGEM",
    escopo=EscopoRepeticao.MARGEM_ID,
    mensagem="O valor utilizado não pode superar o valor total da margem.",
)


def test_ac06_caso_normativo_margem_utilizada_maior_que_total_e_recusada() -> None:
    """AC-06/EC-02: `VALOR_UTILIZADO_MARGEM = 1200` com `VALOR_TOTAL_MARGEM =
    1000` é recusado, com mensagem, e nenhum dos dois é gravado (a não
    gravação é responsabilidade de quem CHAMA `validar_cruzada`; aqui se
    prova que o resultado sinaliza a falha de forma inequívoca)."""
    respostas = _RespostasDeTeste(
        {
            ("M001", "VALOR_UTILIZADO_MARGEM"): Decimal("1200"),
            ("M001", "VALOR_TOTAL_MARGEM"): Decimal("1000"),
        }
    )

    resultado = validar_cruzada(_VALIDACAO_MARGEM, "M001", respostas)

    assert resultado == ResultadoValidacao(
        valida=False,
        variavel_esquerda="VALOR_UTILIZADO_MARGEM",
        variavel_direita="VALOR_TOTAL_MARGEM",
        mensagem=_VALIDACAO_MARGEM.mensagem,
    )


def test_caso_normativo_margem_utilizada_dentro_do_total_e_aceito() -> None:
    respostas = _RespostasDeTeste(
        {
            ("M001", "VALOR_UTILIZADO_MARGEM"): Decimal("800"),
            ("M001", "VALOR_TOTAL_MARGEM"): Decimal("1000"),
        }
    )

    resultado = validar_cruzada(_VALIDACAO_MARGEM, "M001", respostas)

    assert resultado == ResultadoValidacao(valida=True)


@pytest.mark.parametrize(
    ("operador", "esquerdo", "direito", "esperado"),
    [
        ("<=", 5, 5, True),
        ("<=", 6, 5, False),
        (">=", 5, 5, True),
        (">=", 4, 5, False),
        ("<", 4, 5, True),
        ("<", 5, 5, False),
        (">", 6, 5, True),
        (">", 5, 5, False),
        ("==", 5, 5, True),
        ("==", 5, 6, False),
    ],
)
def test_os_cinco_operadores_sao_suportados_por_um_unico_comparador(
    operador: str, esquerdo: int, direito: int, esperado: bool
) -> None:
    """Critério de aceite 1: os cinco operadores (`<=`, `>=`, `<`, `>`,
    `==`) são suportados — todos exercitados pela mesma função
    `validar_cruzada`, sem caminho de código diferente por operador."""
    validacao = ValidacaoCruzada(
        variavel_esquerda="A",
        operador=operador,
        variavel_direita="B",
        escopo=EscopoRepeticao.MARGEM_ID,
        mensagem="Mensagem de teste do registro.",
    )
    respostas = _RespostasDeTeste({("ITEM", "A"): esquerdo, ("ITEM", "B"): direito})

    resultado = validar_cruzada(validacao, "ITEM", respostas)

    assert resultado.valida is esperado


def test_comparacao_ocorre_estritamente_dentro_do_mesmo_item() -> None:
    """Critério de aceite 2: itens diferentes do mesmo escopo nunca se
    comparam — o valor de `M002` não interfere na validação de `M001`."""
    respostas = _RespostasDeTeste(
        {
            ("M001", "VALOR_UTILIZADO_MARGEM"): Decimal("500"),
            ("M001", "VALOR_TOTAL_MARGEM"): Decimal("1000"),
            # Item diferente, que isoladamente violaria a regra — não pode
            # vazar para a validação de M001.
            ("M002", "VALOR_UTILIZADO_MARGEM"): Decimal("9999"),
            ("M002", "VALOR_TOTAL_MARGEM"): Decimal("1"),
        }
    )

    resultado_m001 = validar_cruzada(_VALIDACAO_MARGEM, "M001", respostas)

    assert resultado_m001 == ResultadoValidacao(valida=True)


def test_falha_nomeia_os_dois_campos_envolvidos() -> None:
    """Critério de aceite 3: o `ResultadoValidacao` de falha nomeia OS DOIS
    campos, não apenas um."""
    respostas = _RespostasDeTeste(
        {
            ("M003", "VALOR_UTILIZADO_MARGEM"): Decimal("2000"),
            ("M003", "VALOR_TOTAL_MARGEM"): Decimal("1500"),
        }
    )

    resultado = validar_cruzada(_VALIDACAO_MARGEM, "M003", respostas)

    assert resultado.variavel_esquerda == "VALOR_UTILIZADO_MARGEM"
    assert resultado.variavel_direita == "VALOR_TOTAL_MARGEM"


def test_mensagem_exibida_vem_do_registro_nao_e_composta_pelo_modulo() -> None:
    """Critério de aceite 4: a mensagem do `ResultadoValidacao` é
    exatamente `ValidacaoCruzada.mensagem` — o módulo não escreve redação
    própria."""
    mensagem_do_registro = "Texto de mensagem definido inteiramente no registro YAML."
    validacao = ValidacaoCruzada(
        variavel_esquerda="X",
        operador="<=",
        variavel_direita="Y",
        escopo=EscopoRepeticao.MARGEM_ID,
        mensagem=mensagem_do_registro,
    )
    respostas = _RespostasDeTeste({("ITEM", "X"): 10, ("ITEM", "Y"): 5})

    resultado = validar_cruzada(validacao, "ITEM", respostas)

    assert resultado.mensagem == mensagem_do_registro


def test_variavel_ainda_nao_respondida_no_item_e_tratada_como_valida() -> None:
    """Sem os dois valores presentes no item, não há o que comparar ainda —
    a obrigatoriedade da resposta é assunto de `Obrigatoriedade`, não deste
    comparador."""
    respostas = _RespostasDeTeste({("M004", "VALOR_UTILIZADO_MARGEM"): Decimal("100")})

    resultado = validar_cruzada(_VALIDACAO_MARGEM, "M004", respostas)

    assert resultado == ResultadoValidacao(valida=True)


def test_operador_desconhecido_levanta_erro() -> None:
    validacao = ValidacaoCruzada(
        variavel_esquerda="A",
        operador="!=",  # fora do domínio suportado
        variavel_direita="B",
        escopo=EscopoRepeticao.MARGEM_ID,
        mensagem="Mensagem de teste do registro.",
    )
    respostas = _RespostasDeTeste({("ITEM", "A"): 1, ("ITEM", "B"): 2})

    with pytest.raises(ValueError):
        validar_cruzada(validacao, "ITEM", respostas)
