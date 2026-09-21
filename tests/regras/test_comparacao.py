"""Testes de `engine/comparacao.py::comparar_cenarios` — `T-57`, `T-58`, `T-59`,
`T-78`.

`RF-19`/`AC-27`/`AC-28`/`EC-19` — empate material de 1% e eleição de
`CENARIO_ECONOMICAMENTE_SUPERIOR` (`T-57`).
`RF-20`/`AC-29` — proximidade econômica (`PENALIDADE_CUSTO`, `ATRASO_PRAZO`,
`ECONOMICAMENTE_PROXIMO`), medida contra o `CENARIO_ECONOMICAMENTE_SUPERIOR`
eleito, nunca contra a Avalanche fixa (`T-58`).

`T-59` não introduz cenário novo: reafirma `test_AC28_gabc_superior_e_
avalanche`, `test_AC27_empate_material_desempata_por_prazo` e `test_EC19_
empate_triplo` (de `T-57`) e acrescenta `test_AC29_proximidade_exige_
custo_e_prazo`, parametrizado sobre os quatro quadrantes já cobertos
individualmente pelos `test_AC29_*` de `T-58` — nome exigido literalmente
pelo critério de aceite, sem substituir a cobertura granular existente.

`T-78` (bug de `T-68`, corrigido aqui): `test_T78_*` cobrem o caso
`CUSTO_FUTURO_TOTAL = 0` em todos os cenários — `decimal.InvalidOperation`
antes da correção — via `Cenario`s sintéticos E via `calcular_plano` sobre
`GAB-A` real (déficit puro).

`test_AC27_*`/`test_EC19_*`/`test_AC29_*`/`test_T78_*` usam `Cenario`s
sintéticos construídos direto pelo dataclass (nenhum teste em `tests/`
ainda instancia `Cenario` fora de `simular_cenario`, mas `comparar_cenarios`
só lê `metodo`/`CUSTO_FUTURO_TOTAL`/`PRAZO_TOTAL` — os demais campos recebem
valores neutros mínimos, `meses=()` incluso, porque a função sob teste não
os inspeciona).
`test_AC28_*` roda os três métodos REAIS sobre `GAB-C` via `simular_cenario`,
conforme exigido pelo critério de aceite ("não com valores fixos
hardcoded").

REGRAS: RF-19, RF-20, AC-27, AC-28, AC-29, EC-19
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from engine.ciclo_mensal import Cenario, simular_cenario
from engine.comparacao import comparar_cenarios
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO, METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_c


def _cenario(metodo: METODO, custo: str, prazo: int) -> Cenario:
    """Constrói um `Cenario` sintético mínimo — só os três campos que
    `comparar_cenarios` de fato lê (`metodo`, `CUSTO_FUTURO_TOTAL`,
    `PRAZO_TOTAL`) recebem valor significativo; o resto é neutro."""
    return Cenario(
        metodo=metodo,
        classificacao=None,
        ORDEM_QUITACAO=(),
        PRAZO_TOTAL=prazo,
        CUSTO_FUTURO_TOTAL=dinheiro(custo),
        MESES_PRIMEIRA_VITORIA=None,
        meses=(),
        ESTOUROU_HORIZONTE=False,
        MESES_ATE_ALERTA_HORIZONTE=None,
    )


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/gabaritos/test_gabarito_c_*.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.fixture
def parametros() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def test_AC27_empate_material_desempata_por_prazo(parametros: Parametros) -> None:
    """`AC-27`: dois cenários cujos custos diferem em menos de 1% (P_DIFERENCA_
    ECONOMICA_MATERIAL) estão em empate material — vence o de menor
    PRAZO_TOTAL, mesmo que seu custo não seja o menor dos dois.

    Avalanche: custo 10.000,00, prazo 8 meses.
    Bola de Neve: custo 10.050,00 (+0,5%, dentro de 1%), prazo 6 meses.
    Empate material entre os dois ⇒ vence Bola de Neve (menor prazo), embora
    seu custo seja maior.
    """
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 8)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10050.00", 6)

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.BOLA_DE_NEVE)
    assertar_exato(
        set(resultado.empatados_materialmente), {METODO.AVALANCHE, METODO.BOLA_DE_NEVE}
    )


def test_AC27_fora_do_empate_vence_menor_custo(parametros: Parametros) -> None:
    """Contraprova de `AC-27`: diferença ACIMA de 1% não é empate material —
    vence o menor custo mesmo que seu prazo seja maior."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 6)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10200.00", 3)  # +2%, fora do empate

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.empatados_materialmente, (METODO.AVALANCHE,))


def test_EC19_empate_triplo(parametros: Parametros) -> None:
    """`EC-19`: três cenários empatados materialmente concorrem TODOS
    simultaneamente (não par a par) — vence o de menor PRAZO_TOTAL entre os
    três, e todos os três aparecem em `empatados_materialmente`.

    Avalanche: custo 10.000,00 (mínimo), prazo 8.
    Bola de Neve: custo 10.090,00 (+0,9%, dentro de 1%), prazo 5.
    Híbrido: custo 10.050,00 (+0,5%, dentro de 1%), prazo 6.
    Os três empatam contra o MÍNIMO (10.000,00) — vence Bola de Neve, o de
    menor prazo entre os três, mesmo não sendo o de menor custo.
    """
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 8)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10090.00", 5)
    hibrido = _cenario(METODO.HIBRIDO, "10050.00", 6)

    resultado = comparar_cenarios((avalanche, bola_de_neve, hibrido), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.BOLA_DE_NEVE)
    assertar_exato(
        set(resultado.empatados_materialmente),
        {METODO.AVALANCHE, METODO.BOLA_DE_NEVE, METODO.HIBRIDO},
    )


def test_AC28_gabc_superior_e_avalanche(parametros: Parametros) -> None:
    """`AC-28`: em `GAB-C`, rodando os três métodos REAIS via `simular_
    cenario` (nenhum valor hardcoded), o cenário economicamente superior é a
    Avalanche — Híbrido a 1,6347% de diferença e Bola de Neve a 3,1388%,
    ambos fora do empate material de 1%.
    """
    estado = carregar_gab_c()
    dividas = _inventario(estado)
    diagnostico = calcular_diagnostico(estado, parametros)

    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, parametros)
    cenario_avalanche = simular_cenario(estado, diagnostico, dividas, sel_avalanche, parametros)

    sel_bola_de_neve = criar_selecionar_alvo_bola_de_neve(dividas, parametros)
    cenario_bola_de_neve = simular_cenario(
        estado, diagnostico, dividas, sel_bola_de_neve, parametros
    )

    resultado_hibrido = criar_selecionar_alvo_hibrido(estado, dividas, diagnostico, parametros)
    assertar_exato(resultado_hibrido.classificacao, CLASSIFICACAO_CENARIO.CALCULAVEL)
    assert resultado_hibrido.selecionar_alvo is not None, (
        "GAB-C deveria ter Híbrido aplicável — ver tests/gabaritos/test_gabarito_c_hibrido.py"
    )
    cenario_hibrido = simular_cenario(
        estado, diagnostico, dividas, resultado_hibrido.selecionar_alvo, parametros
    )

    cenarios = (
        dataclasses.replace(cenario_avalanche, metodo=METODO.AVALANCHE),
        dataclasses.replace(cenario_bola_de_neve, metodo=METODO.BOLA_DE_NEVE),
        dataclasses.replace(cenario_hibrido, metodo=METODO.HIBRIDO),
    )

    resultado = comparar_cenarios(cenarios, parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.empatados_materialmente, (METODO.AVALANCHE,))

    diferenca_hibrido = (resultado.DIFERENCA_PERCENTUAL[METODO.HIBRIDO] * 100).quantize(
        Decimal("0.0001")
    )
    diferenca_bola_de_neve = (
        resultado.DIFERENCA_PERCENTUAL[METODO.BOLA_DE_NEVE] * 100
    ).quantize(Decimal("0.0001"))

    assertar_exato(diferenca_hibrido, Decimal("1.6347"))
    assertar_exato(diferenca_bola_de_neve, Decimal("3.1388"))


def test_parametro_1_por_cento_nunca_e_confundido_com_5_por_cento(parametros: Parametros) -> None:
    """Critério de aceite 4: `P_DIFERENCA_ECONOMICA_MATERIAL` (1%) é o único
    parâmetro percentual lido por `comparar_cenarios` nesta tarefa — uma
    diferença de exatamente 3% (dentro dos 5% de `P_DIFERENCA_CUSTO_
    EQUIVALENTE`, que é assunto de T-58) NÃO é tratada como empate aqui."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 6)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10300.00", 3)  # +3%: dentro de 5%, fora de 1%

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.empatados_materialmente, (METODO.AVALANCHE,))


def test_AC29_custo_ok_prazo_ok_e_proximo(parametros: Parametros) -> None:
    """`AC-29`, quadrante 1: penalidade de custo dentro de 5% E atraso de
    prazo dentro de 2 meses ⇒ `ECONOMICAMENTE_PROXIMO` = SIM.

    Avalanche (superior): custo 10.000,00, prazo 10.
    Bola de Neve: custo 10.300,00 (+3%, dentro de 5%; fora do empate
    material de 1%, então não concorre pelo posto de superior), prazo 11
    (+1 mês, dentro de 2 meses)."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10300.00", 11)

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], Decimal("0.03"))
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], 1)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], True)


def test_AC29_custo_ok_prazo_estourado_nao_e_proximo(parametros: Parametros) -> None:
    """`AC-29`, quadrante 2: penalidade de custo dentro de 5% mas atraso de
    prazo ACIMA de 2 meses ⇒ `ECONOMICAMENTE_PROXIMO` = NAO, mesmo o custo
    tendo passado. A conjunção cumulativa (`E`) exige os dois eixos."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10300.00", 13)  # +3 meses

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], Decimal("0.03"))
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], 3)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], False)


def test_AC29_custo_estourado_prazo_ok_nao_e_proximo(parametros: Parametros) -> None:
    """`AC-29`, quadrante 3: penalidade de custo ACIMA de 5% mas atraso de
    prazo dentro de 2 meses ⇒ `ECONOMICAMENTE_PROXIMO` = NAO."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10800.00", 11)  # +8%

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], Decimal("0.08"))
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], 1)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], False)


def test_AC29_custo_estourado_prazo_estourado_nao_e_proximo(parametros: Parametros) -> None:
    """`AC-29`, quadrante 4: os dois eixos ACIMA do teto ⇒
    `ECONOMICAMENTE_PROXIMO` = NAO."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10800.00", 13)  # +8%, +3 meses

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], Decimal("0.08"))
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], 3)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], False)


@pytest.mark.parametrize(
    (
        "custo_alternativo",
        "prazo_alternativo",
        "penalidade_custo_esperada",
        "atraso_prazo_esperado",
        "proximo_esperado",
    ),
    (
        pytest.param("10300.00", 11, Decimal("0.03"), 1, True, id="custo_ok_prazo_ok"),
        pytest.param("10300.00", 13, Decimal("0.03"), 3, False, id="custo_ok_prazo_estourado"),
        pytest.param("10800.00", 11, Decimal("0.08"), 1, False, id="custo_estourado_prazo_ok"),
        pytest.param(
            "10800.00", 13, Decimal("0.08"), 3, False, id="custo_estourado_prazo_estourado"
        ),
    ),
)
def test_AC29_proximidade_exige_custo_e_prazo(
    parametros: Parametros,
    custo_alternativo: str,
    prazo_alternativo: int,
    penalidade_custo_esperada: Decimal,
    atraso_prazo_esperado: int,
    proximo_esperado: bool,
) -> None:
    """`AC-29`, nome exato exigido pelo critério de aceite de `T-59`: a
    conjunção cumulativa (`E`) entre `PENALIDADE_CUSTO` (≤ `P_DIFERENCA_
    CUSTO_EQUIVALENTE`, 5%) e `ATRASO_PRAZO` (≤ `P_DIFERENCA_PRAZO_
    EQUIVALENTE`, 2 meses) — os quatro quadrantes reunidos num único teste
    parametrizado. Mesmos casos numéricos de `T-58`
    (`test_AC29_custo_ok_prazo_ok_e_proximo` e as três contraprovas), que
    permanecem intactos como cobertura direta e granular; este teste é a
    evidência sob o nome literal do critério de aceite de `T-59`:

    Avalanche (superior): custo 10.000,00, prazo 10.
    - custo OK (+3%, ≤5%) / prazo OK (+1 mês, ≤2) ⇒ SIM
    - custo OK (+3%, ≤5%) / prazo estourado (+3 meses, >2) ⇒ NAO
    - custo estourado (+8%, >5%) / prazo OK (+1 mês, ≤2) ⇒ NAO
    - custo estourado (+8%, >5%) / prazo estourado (+3 meses, >2) ⇒ NAO
    """
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, custo_alternativo, prazo_alternativo)

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], penalidade_custo_esperada)
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], atraso_prazo_esperado)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], proximo_esperado)


def test_AC29_tetos_exatos_sao_proximos(parametros: Parametros) -> None:
    """Fronteira: `<=`, não `<` — penalidade EXATAMENTE 5% e atraso
    EXATAMENTE 2 meses ainda contam como `ECONOMICAMENTE_PROXIMO` = SIM
    (§11.5 usa `≤` nos dois eixos, não `<`)."""
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 10)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "10500.00", 12)  # exatamente +5%, +2 meses

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.BOLA_DE_NEVE], Decimal("0.05"))
    assertar_exato(resultado.ATRASO_PRAZO[METODO.BOLA_DE_NEVE], 2)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], True)


def test_AC29_referencia_e_o_superior_nao_a_avalanche(parametros: Parametros) -> None:
    """Critério de aceite 2 de `T-58`: a referência de `PENALIDADE_CUSTO`/
    `ATRASO_PRAZO` é sempre `CENARIO_ECONOMICAMENTE_SUPERIOR`, nunca a
    Avalanche por definição fixa. `Cenario`s sintéticos forçam um caso onde o
    superior NÃO é a Avalanche (em `GAB-C` real o superior é sempre a
    Avalanche, `AC-28` — este teste usa custos artificiais só para provar
    que a função não hardcoda `METODO.AVALANCHE` como referência).

    Bola de Neve (menor custo, vence): custo 9.000,00, prazo 10.
    Avalanche: custo 10.000,00 (+11,11...%, bem fora do empate de 1%), prazo
    9 (prazo MENOR que o do superior, então ATRASO_PRAZO é negativo).
    Se a referência fosse a Avalanche (incorreto), a penalidade da Avalanche
    contra si mesma seria 0 — mas a Avalanche não é o superior aqui, então
    ela também é avaliada como alternativa, contra a Bola de Neve."""
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "9000.00", 10)
    avalanche = _cenario(METODO.AVALANCHE, "10000.00", 9)

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.BOLA_DE_NEVE)
    # penalidade da Avalanche medida contra a Bola de Neve (9.000,00), não contra si mesma:
    # (10.000,00 - 9.000,00) / 9.000,00 = 0,1111...
    assertar_exato(
        resultado.PENALIDADE_CUSTO[METODO.AVALANCHE].quantize(Decimal("0.0001")),
        Decimal("0.1111"),
    )
    assertar_exato(resultado.ATRASO_PRAZO[METODO.AVALANCHE], -1)  # prazo menor que o superior
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.AVALANCHE], False)
    # o superior (Bola de Neve) não aparece nos mapas de proximidade — não concorre consigo mesmo
    assert METODO.BOLA_DE_NEVE not in resultado.PENALIDADE_CUSTO
    assert METODO.BOLA_DE_NEVE not in resultado.ATRASO_PRAZO
    assert METODO.BOLA_DE_NEVE not in resultado.ECONOMICAMENTE_PROXIMO


def test_AC29_parametro_5_por_cento_nao_e_confundido_com_1_por_cento(
    parametros: Parametros,
) -> None:
    """Critério de aceite 3 de `T-58`: `P_DIFERENCA_ECONOMICA_MATERIAL` (1%,
    de `T-57`) e `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%, desta tarefa) nunca se
    cruzam. Prova por leitura de código: `_avaliar_proximidade_economica`
    (função que produz `PENALIDADE_CUSTO`/`ATRASO_PRAZO`/`ECONOMICAMENTE_
    PROXIMO`) não CHAMA `p.numero("P_DIFERENCA_ECONOMICA_MATERIAL")` em seu
    texto-fonte — só o empate material (trecho diferente, em
    `comparar_cenarios`) lê esse parâmetro. (A docstring da função MENCIONA
    o nome só para explicar a exclusão — por isso a asserção busca a chamada
    `p.numero(...)`, não a string crua.)"""
    import inspect

    from engine import comparacao

    codigo_fonte = inspect.getsource(comparacao._avaliar_proximidade_economica)
    assert 'p.numero("P_DIFERENCA_ECONOMICA_MATERIAL")' not in codigo_fonte
    assert 'p.numero("P_DIFERENCA_CUSTO_EQUIVALENTE")' in codigo_fonte
    assert 'p.numero("P_DIFERENCA_PRAZO_EQUIVALENTE")' in codigo_fonte


def test_lista_vazia_levanta_erro(parametros: Parametros) -> None:
    """Sem cenário calculável, não há o que eleger — erro ruidoso, nunca um
    `METODO` inventado (mesmo espírito de `ErroParametros`/`ErroInvariante`
    do restante do motor)."""
    with pytest.raises(ValueError):
        comparar_cenarios((), parametros)


def test_metodo_ausente_levanta_erro(parametros: Parametros) -> None:
    """`Cenario.metodo is None` (estado atual de `simular_cenario`, T-46) não
    pode ser comparado silenciosamente — a função exige rotulagem prévia."""
    sem_metodo = Cenario(
        metodo=None,
        classificacao=None,
        ORDEM_QUITACAO=(),
        PRAZO_TOTAL=6,
        CUSTO_FUTURO_TOTAL=dinheiro("10000.00"),
        MESES_PRIMEIRA_VITORIA=None,
        meses=(),
        ESTOUROU_HORIZONTE=False,
        MESES_ATE_ALERTA_HORIZONTE=None,
    )

    with pytest.raises(ValueError):
        comparar_cenarios((sem_metodo,), parametros)


def test_T78_custo_zero_em_todos_nao_levanta_invalid_operation(parametros: Parametros) -> None:
    """`T-78` (bug achado por `T-68`, não corrigido lá por estar fora de
    escopo): quando TODOS os cenários têm `CUSTO_FUTURO_TOTAL = 0` (nenhuma
    dívida quitada em nenhum método — `GAB-A`/`GAB-B` reais), `CUSTO_MINIMO`
    é zero e a divisão de `DIFERENCA_PERCENTUAL` não pode mais quebrar com
    `decimal.InvalidOperation`.

    Semântica adotada (ver docstring de `comparar_cenarios`): zero contra
    mínimo zero é "mesmo patamar" (0% de diferença, não erro) — todos os
    três cenários empatam materialmente entre si e o desempate cai no
    `PRAZO_TOTAL`, como no caminho normal (`AC-27`). Prazos dentro de
    `P_DIFERENCA_PRAZO_EQUIVALENTE` (2 meses) do superior, para que o eixo
    de prazo de `ECONOMICAMENTE_PROXIMO` também passe — o foco deste teste é
    o eixo de custo (zero), não o de prazo."""
    avalanche = _cenario(METODO.AVALANCHE, "0.00", 11)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "0.00", 10)
    hibrido = _cenario(METODO.HIBRIDO, "0.00", 12)

    resultado = comparar_cenarios((avalanche, bola_de_neve, hibrido), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.BOLA_DE_NEVE)
    assertar_exato(
        set(resultado.empatados_materialmente),
        {METODO.AVALANCHE, METODO.BOLA_DE_NEVE, METODO.HIBRIDO},
    )
    for metodo in (METODO.AVALANCHE, METODO.BOLA_DE_NEVE, METODO.HIBRIDO):
        assertar_exato(resultado.DIFERENCA_PERCENTUAL[metodo], Decimal(0))

    # proximidade econômica também não quebra: os dois alternativos, com
    # custo igual ao superior (zero) e prazo dentro do teto, são
    # ECONOMICAMENTE_PROXIMO = SIM.
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.AVALANCHE], Decimal(0))
    assertar_exato(resultado.PENALIDADE_CUSTO[METODO.HIBRIDO], Decimal(0))
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.AVALANCHE], True)
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.HIBRIDO], True)


def test_T78_custo_zero_no_minimo_mas_alternativo_positivo_nao_empata(
    parametros: Parametros,
) -> None:
    """Contraprova de `T-78`: quando o `CUSTO_MINIMO` é zero mas um cenário
    alternativo tem custo estritamente positivo, esse cenário NÃO empata
    materialmente (custo positivo não pode estar "a menos de 1% de zero")
    nem é `ECONOMICAMENTE_PROXIMO` do superior de custo zero — decidido por
    comparação de custo direta, sem dividir por zero."""
    avalanche = _cenario(METODO.AVALANCHE, "0.00", 12)
    bola_de_neve = _cenario(METODO.BOLA_DE_NEVE, "500.00", 10)

    resultado = comparar_cenarios((avalanche, bola_de_neve), parametros)

    assertar_exato(resultado.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)
    assertar_exato(resultado.empatados_materialmente, (METODO.AVALANCHE,))
    assertar_exato(resultado.ECONOMICAMENTE_PROXIMO[METODO.BOLA_DE_NEVE], False)


def test_T78_gab_a_calcular_plano_nao_levanta_invalid_operation() -> None:
    """`T-78`, critério de aceite 3: prova via pipeline completo
    (`calcular_plano`) de que `GAB-A` (déficit puro — nenhuma dívida quitada
    em nenhum método, `CAPACIDADE_ATAQUE_ATUAL = 0`) não quebra mais. Antes
    da correção, esta chamada levantava `decimal.InvalidOperation` dentro de
    `comparar_cenarios` (passo 9 de `calcular_plano`, `engine/motor.py`)."""
    from engine.motor import calcular_plano

    estado = carregar_gab_a()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    assert snapshot.METODO_RECOMENDADO_PIQ in (METODO.AVALANCHE, METODO.BOLA_DE_NEVE)
