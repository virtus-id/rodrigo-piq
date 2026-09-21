"""Gabarito `GAB-B` ponta a ponta — Equilíbrio frágil / potencial não é capacidade.

T-26 · RF-14, RF-15 · `AC-06`, `AC-07` (`specs/motor-calculo.spec.md`) ·
`piq-app-spec.md` §10.2, linhas 443-451.

Formaliza no local correto (`tests/gabaritos/`, marcador `gabarito`) o que
T-21/T-23 já verificaram ad-hoc em `tests/regras/test_status_financeiro.py`
(`test_gab_b_piso_status_e_capacidade`) durante o próprio desenvolvimento: que
`calcular_diagnostico(carregar_gab_b(), parametros)` reproduz as 7 saídas de
`AC-06`.

`GAB-B`: renda 10.000, despesas operacionais 7.600, despesas não-mensais 400,
D001 agregada com devido = efetivo = 1.800 (nada de falso superávit aqui,
ao contrário de `GAB-A`). `RESULTADO_MENSAL_ATUAL` = 200; piso = MAX(100,
10.000 × 3%) = 300 ⇒ 200 < 300 ⇒ `EQUILIBRIO_FRAGIL` (o resultado positivo
não basta para `CAPACIDADE_POSITIVA`, mas também não é `DEFICIT`).
`FATOR_SEGURANCA` = 1,00 porque o perfil da fixture é neutro/forte (nenhuma
das quatro reduções é acionada). `ECONOMIA_POTENCIAL_IMEDIATA` = 400 alimenta
somente `CAPACIDADE_ATAQUE_POTENCIAL` (600), nunca a capacidade conservadora
(200) que de fato alimenta o cronograma-base — `AC-07`/`EC-11`.

**Tolerância.** Mesma justificativa de `test_gabarito_a_deficit.py`: os sete
valores de `AC-06` resultam de um único mês calculado deterministicamente,
sem acumulação de arredondamento entre meses de simulação — `assertar_exato`
é aplicável e é a convenção já usada por T-21/T-23 para os mesmos campos
(`test_gab_b_piso_status_e_capacidade`). `STATUS_FINANCEIRO` é categórico e
usa `assertar_exato` por definição (§9 do plano).

`ATAQUE_IMEDIATO_RECOMENDADO` (T-147, RF-66, AC-116) — cálculo à mão a partir
de `tests/fixtures/gab_b.json`: `DINHEIRO_DISPONIVEL=0`, `investimentos`,
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
from engine.tipos import STATUS_FINANCEIRO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_b


@pytest.mark.gabarito
def test_gabarito_b_equilibrio_fragil() -> None:
    """AC-06: as 7 saídas de `GAB-B`.

    ```
    PISO_CAPACIDADE                = 300
    STATUS_FINANCEIRO              = EQUILIBRIO_FRAGIL
    CAPACIDADE_ATAQUE_ATUAL        = 200
    BASE_CONSERVADORA              = 200
    FATOR_SEGURANCA                = 1,00
    CAPACIDADE_ATAQUE_CONSERVADORA = 200
    CAPACIDADE_ATAQUE_POTENCIAL    = 600
    ```
    """
    estado = carregar_gab_b()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    diagnostico = calcular_diagnostico(estado, parametros)

    assertar_exato(diagnostico.PISO_CAPACIDADE, dinheiro(Decimal("300")))
    assertar_exato(diagnostico.STATUS_FINANCEIRO, STATUS_FINANCEIRO.EQUILIBRIO_FRAGIL)
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_ATUAL, dinheiro(Decimal("200")))
    assertar_exato(diagnostico.BASE_CONSERVADORA, dinheiro(Decimal("200")))
    assertar_exato(diagnostico.FATOR_SEGURANCA, Decimal("1.00"))
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA, dinheiro(Decimal("200")))
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_POTENCIAL, dinheiro(Decimal("600")))

    # T-147/RF-66/AC-116 — asserção nova: ATAQUE_IMEDIATO_RECOMENDADO é o
    # valor REAL (composto na segunda passada de calcular_plano, T-142),
    # não o placeholder que `diagnostico` (calcular_diagnostico isolada,
    # acima) sempre carrega. Cálculo à mão: 0 (ver docstring do módulo).
    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro(Decimal("0")))


@pytest.mark.gabarito
def test_gabarito_b_ac07_cronograma_base_usa_no_maximo_conservadora() -> None:
    """AC-07/EC-11: trava de intenção arquitetural.

    O cronograma-base real (`engine/ciclo_mensal.py`, Entrega 4 em diante)
    ainda não existe neste backlog — não há consumidor concreto para exercitar
    diretamente. O que este caso prova, com o diagnóstico já implementado, é a
    condição estrutural que torna a regra `AC-07`/`EC-11` verificável: que
    `CAPACIDADE_ATAQUE_POTENCIAL` (600) é **diferente** de
    `CAPACIDADE_ATAQUE_CONSERVADORA` (200) em `GAB-B` — ou seja, a economia de
    R$ 400 (`ECONOMIA_POTENCIAL_IMEDIATA`) de fato infla apenas a capacidade
    potencial, nunca a conservadora.

    Registro explícito para qualquer consumidor futuro de cronograma-base:
    **use sempre `CAPACIDADE_ATAQUE_CONSERVADORA`, nunca
    `CAPACIDADE_ATAQUE_POTENCIAL`**, para determinar `CAPACIDADE_ATAQUE_M` ou
    qualquer valor de ataque real (ver aviso já reforçado na docstring do
    campo `Capacidades.CAPACIDADE_ATAQUE_POTENCIAL`, `engine/diagnostico.py`).
    Se as duas capacidades um dia colidirem por coincidência numérica em outro
    cenário, esta trava deixa de distinguir a violação — por isso o teste
    também falha explicitamente se elas deixarem de divergir em `GAB-B`,
    sinalizando que o gabarito precisa ser revisto antes que a regra possa ser
    considerada coberta.
    """
    estado = carregar_gab_b()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    diagnostico = calcular_diagnostico(estado, parametros)

    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA, dinheiro(Decimal("200")))
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_POTENCIAL, dinheiro(Decimal("600")))
    assert diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA != diagnostico.CAPACIDADE_ATAQUE_POTENCIAL, (
        "GAB-B precisa manter CAPACIDADE_ATAQUE_CONSERVADORA != "
        "CAPACIDADE_ATAQUE_POTENCIAL para que este teste continue provando "
        "AC-07/EC-11 — os R$ 400 de ECONOMIA_POTENCIAL_IMEDIATA só podem "
        "aparecer na potencial, nunca na conservadora que alimenta o "
        "cronograma-base"
    )
