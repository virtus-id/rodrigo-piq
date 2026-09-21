"""Testes de `derivar_RESERVA_MOBILIZAVEL` (T-102) — RF-43, RF-49 · §13.1 · §13.9.

Cobre os critérios comportamentais de `T-102`: a ORDEM das três regras da
§13.1 e o que cada uma produz. A ordem é o coração da função — as três regras
são individualmente triviais, e todo o risco de implementação está em qual
delas vence quando duas se aplicam ao mesmo tempo:

- `EC-23` — Regra 1 vence Regra 2: sem reserva ou sem disposição de uso, o
  valor informado é IGNORADO, não somado, mesmo preenchido.
- `EC-25` — Regra 3 vence Regra 2: total desconhecido devolve o estado
  desconhecido, não o valor informado.
- `AC-73` — o desconhecido nunca vira `0`: zero é uma decisão que o usuário
  não tomou, e a §13.1 proíbe convertê-lo "silenciosamente em zero como
  informação".
- `EC-24` — `MAX(0, ...)` zera o negativo ANTES do `MIN`; o resultado nunca é
  negativo.

`AC-70`/`AC-71` (os números literais de `GAB-AI-01` e `GAB-AI-02`) aparecem
aqui como testes de regra do caminho feliz da Regra 2 — o gabarito formal
`GAB-AI` marcado `@pytest.mark.gabarito_ataque_imediato`, em
`tests/gabaritos_ataque_imediato/`, é escopo de `T-110`, não desta tarefa.

Tolerância ZERO em toda asserção (spec §5, "Tolerância dos `GAB-AI`: zero";
`RESERVA_MOBILIZAVEL` está na lista de `SIMBOLOS_TOLERANCIA_ZERO` desde
`T-109`): `assertar_exato`, nunca `assertar_monetario`.
"""

from decimal import Decimal

import pytest

from engine.ataque_imediato import derivar_RESERVA_MOBILIZAVEL
from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO, Dinheiro
from tests.conftest import assertar_exato


@pytest.mark.regra
def test_regra_2_limita_pelo_valor_informado() -> None:
    """`AC-70` (`GAB-AI-01`): total `20.000`, usuário aceita analisar `5.000`
    — o `MIN` devolve o informado, que é o menor dos dois."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(5000),
    )

    assertar_exato(obtido, dinheiro(5000))


@pytest.mark.regra
def test_regra_2_limita_pelo_total_quando_informado_excede() -> None:
    """`AC-71` (`GAB-AI-02`): total `20.000`, usuário informa máximo de
    `30.000` — o `MIN` corta pelo total. Nunca `30.000`: o motor "apenas
    valida e limita" (§13.1), e ninguém mobiliza mais do que tem."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(30000),
    )

    assertar_exato(obtido, dinheiro(20000))


@pytest.mark.regra
def test_regra_1_disposicao_nao_zera_ignorando_valor_informado() -> None:
    """`AC-72` (`GAB-AI-03`) e `EC-23`: `DISPOSICAO_USO_RESERVA = NAO`
    devolve `0` mesmo com total e valor informado preenchidos e altos — a
    Regra 1 é avaliada ANTES da Regra 2 e vence; o informado é ignorado,
    não somado."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(9000),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_regra_1_reserva_inexistente_zera_ignorando_valor_informado() -> None:
    """`EC-23`: `RESERVA_EXISTE = NAO` com `VALOR_MAXIMO_...` preenchido
    (entrada inconsistente) resulta `0`, não `9.000` — o outro lado do `OU`
    da Regra 1, provado separadamente para que uma implementação que
    esqueça um dos dois ramos não passe."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(9000),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_regra_1_vence_ate_o_desconhecido() -> None:
    """`EC-23` no limite: `RESERVA_EXISTE = NAO` com AMBOS os monetários
    desconhecidos resulta `0`, não `DESCONHECIDO`. Prova que a Regra 1 é a
    PRIMEIRA guarda do pseudocódigo da §13.9, antes até dos testes de
    desconhecido — sem reserva, não há pendência a registrar."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        RESERVA_TOTAL=DESCONHECIDO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_regra_3_total_desconhecido_vence_valor_informado_conhecido() -> None:
    """`EC-25`: total desconhecido COM valor máximo informado conhecido
    devolve o estado desconhecido — não `5.000`. A Regra 3 tem precedência
    sobre a Regra 2 quando o total é desconhecido: sem saber o teto, o `MIN`
    não é calculável."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=DESCONHECIDO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(5000),
    )

    assertar_exato(obtido, DESCONHECIDO)


@pytest.mark.regra
def test_regra_3_decisao_adiada_devolve_desconhecido_nunca_zero() -> None:
    """`AC-73` (`GAB-AI-04`): "prefiro decidir depois de ver a análise"
    chega como `VALOR_MAXIMO_...` desconhecido e devolve o estado
    desconhecido — explicitamente NÃO `0`. A §13.1 é normativa: o estado
    desconhecido "não é convertido silenciosamente em zero como
    informação"."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )

    assertar_exato(obtido, DESCONHECIDO)
    # A afirmação forte de `AC-73`: não é só "é DESCONHECIDO", é "NÃO é zero"
    # — o `DESCONHECIDO` é um `Enum`, então não é sequer comparável por
    # igualdade a `dinheiro(0)`, e é exatamente essa incomparabilidade que
    # impede um consumidor de tratá-lo como valor numérico por descuido.
    assert obtido != dinheiro(0), "desconhecido nunca pode ser lido como zero (§13.1)"
    assert not isinstance(obtido, Decimal), "desconhecido não é valor monetário (§13.1)"


@pytest.mark.regra
def test_regra_2_valor_informado_negativo_e_zerado_antes_do_min() -> None:
    """`EC-24`: informado negativo (`-500`) é zerado pelo `MAX(0, ...)`
    ANTES do `MIN`, resultando `0`. Se a ordem fosse `MAX(0, MIN(total,
    informado))` o resultado seria o mesmo aqui, mas `MIN(total, informado)`
    sem o `MAX` devolveria `-500` — o teste seguinte fecha o outro lado."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=dinheiro(20000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(-500),
    )

    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
@pytest.mark.parametrize(
    ("reserva_total", "valor_informado"),
    [
        (dinheiro(20000), dinheiro(-500)),
        (dinheiro(0), dinheiro(-1)),
        (dinheiro("0.01"), dinheiro("-0.01")),
        (dinheiro(20000), dinheiro(-20000)),
    ],
)
def test_resultado_nunca_e_negativo(reserva_total: Dinheiro, valor_informado: Dinheiro) -> None:
    """`EC-24`: sob qualquer combinação de informado negativo, o resultado
    nunca é negativo — a garantia que a §13.1 dá ao usuário é que uma
    entrada absurda não vira reserva negativa a mobilizar."""
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=reserva_total,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=valor_informado,
    )

    assert obtido is not DESCONHECIDO
    assert obtido >= dinheiro(0), f"resultado negativo viola EC-24: {obtido!r}"


@pytest.mark.regra
def test_funcao_e_pura_recusa_chamada_posicional() -> None:
    """NFR "Pureza (Rodada 3)" (spec §5) e `AC-80`: as quatro entradas
    chegam por argumento NOMEADO — o `*` da assinatura recusa a chamada
    posicional em tempo de execução, e `mypy --strict` a recusa antes disso.
    Provar isso aqui é provar que a função não tem canal de entrada implícito
    (`EstadoFinanceiro`, `Diagnostico`, relógio, global)."""
    with pytest.raises(TypeError):
        derivar_RESERVA_MOBILIZAVEL(  # type: ignore[call-arg]
            RESERVA_EXISTE.SIM,
            DISPOSICAO_USO_RESERVA.PARTE,
            dinheiro(20000),
            dinheiro(5000),
        )
