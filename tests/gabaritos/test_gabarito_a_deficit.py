"""Gabarito `GAB-A` ponta a ponta — Déficit / falso superávit observado.

T-26 · RF-14, RF-15 · `AC-05` (`specs/motor-calculo.spec.md`) ·
`piq-app-spec.md` §10.2, linhas 433-441.

Formaliza no local correto (`tests/gabaritos/`, marcador `gabarito`) o que
T-20/T-21/T-23/T-24 já verificaram ad-hoc em `tests/regras/test_diagnostico.py`
e `tests/regras/test_status_financeiro.py` durante o próprio desenvolvimento:
que `calcular_diagnostico(carregar_gab_a(), parametros)` reproduz as 8 saídas
de `AC-05`, incluindo `MODO_ESTABILIZACAO = SIM`.

`GAB-A`: renda 8.000, despesas operacionais 6.500, despesas não-mensais 500.
D001 tem devido 1.200 mas efetivo 0 (não estava sendo paga de fato — AC-32);
D002 tem devido 800 e efetivo 800. Daí devidos = 2.000, efetivos = 800,
observado = +200 (falso superávit: parece sobra, mas é dívida não paga
deixando de sair do caixa), estrutural = -1.000 (déficit real).

**Tolerância.** Todos os oito valores de `AC-05` são resultado de um único
mês, calculado deterministicamente a partir de somas e diferenças diretas de
`EstadoFinanceiro` — não há acumulação de arredondamento ao longo de meses de
simulação (que é a razão de existir de `assertar_monetario`, RF-12/G-02).
`test_gab_b_piso_status_e_capacidade` (`tests/regras/test_status_financeiro.py`,
T-21/T-23) já usa `assertar_exato` para os mesmos campos monetários de
diagnóstico de um único mês; este teste segue a mesma convenção para manter o
teste isolado e o teste de gabarito coerentes entre si. `MODO_ESTABILIZACAO`
é booleano/categórico e usa `assertar_exato` por definição (§9 do plano).

`ATAQUE_IMEDIATO_RECOMENDADO` (T-147, RF-66, AC-116) — cálculo à mão a partir
de `tests/fixtures/gab_a.json`: `DINHEIRO_DISPONIVEL=0`, `investimentos`,
`ativos` e `recursos_extraordinarios` são coleções vazias, e
`RESERVA_EXISTE=NAO` zera `RESERVA_MOBILIZAVEL` pela Regra 1 da §13.1 — os
cinco recursos estrategicamente recomendados somam `0`, então
`ATAQUE_IMEDIATO_RECOMENDADO = MIN(elegível, 0) = 0`, qualquer que seja o
elegível. Confirmado batendo com a leitura real via `calcular_plano`.
"""

from decimal import Decimal

import pytest

from engine.diagnostico import calcular_diagnostico
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a


@pytest.mark.gabarito
def test_gabarito_a_deficit() -> None:
    """AC-05: as 8 saídas de `GAB-A`, incluindo `MODO_ESTABILIZACAO = SIM`.

    ```
    PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES = 2.000
    PAGAMENTOS_EFETIVOS_DIVIDAS         =   800
    RESULTADO_CAIXA_OBSERVADO           =  +200
    RESULTADO_MENSAL_ATUAL              = -1.000
    GAP_CAIXA_VS_ESTRUTURAL             = 1.200
    DEFICIT_MENSAL                      = 1.000
    CAPACIDADE_ATAQUE_ATUAL             =     0
    MODO_ESTABILIZACAO                  =   SIM
    ```
    """
    estado = carregar_gab_a()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    diagnostico = calcular_diagnostico(estado, parametros)

    assertar_exato(
        diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES, dinheiro(Decimal("2000"))
    )
    assertar_exato(diagnostico.PAGAMENTOS_EFETIVOS_DIVIDAS, dinheiro(Decimal("800")))
    assertar_exato(diagnostico.RESULTADO_CAIXA_OBSERVADO, dinheiro(Decimal("200")))
    assertar_exato(diagnostico.RESULTADO_MENSAL_ATUAL, dinheiro(Decimal("-1000")))
    assertar_exato(diagnostico.GAP_CAIXA_VS_ESTRUTURAL, dinheiro(Decimal("1200")))
    assertar_exato(diagnostico.DEFICIT_MENSAL, dinheiro(Decimal("1000")))
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_ATUAL, dinheiro(Decimal("0")))
    assertar_exato(diagnostico.MODO_ESTABILIZACAO, True)

    # T-147/RF-66/AC-116 — asserção nova: ATAQUE_IMEDIATO_RECOMENDADO é o
    # valor REAL (composto na segunda passada de calcular_plano, T-142),
    # não o placeholder que `diagnostico` (calcular_diagnostico isolada,
    # acima) sempre carrega. Cálculo à mão: 0 (ver docstring do módulo).
    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro(Decimal("0")))
