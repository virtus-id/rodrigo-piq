"""Gabarito `GAB-C` ponta a ponta — método Avalanche.

T-50 · RF-05 · `AC-01` (`specs/motor-calculo.spec.md`) · `piq-app-spec.md`
§10.1 (linhas 419-427), §10.2 (linhas 453-464).

Formaliza no local correto (`tests/gabaritos/`, marcador `gabarito`) a
reprodução ponta a ponta de `AC-01`: monta o cenário `GAB-C` (fixture
`tests/fixtures/gab_c.json`, carregada por `tests/fixtures/carregar.py::
carregar_gab_c`), roda `simular_cenario` (T-46, `engine/ciclo_mensal.py`)
usando `criar_selecionar_alvo_avalanche` (T-49, `engine/metodos/
avalanche.py`) como `sel`, e verifica as quatro saídas esperadas:

```
PRAZO_TOTAL            = 6 meses
CUSTO_FUTURO_TOTAL      = R$ 23.719,46
MESES_PRIMEIRA_VITORIA = mês 4
ORDEM_QUITACAO         = D001 → D002 → D003
```

`dg` (o `Diagnostico`) é produzido de verdade por `calcular_diagnostico`
(`engine/diagnostico.py`, T-24) a partir do mesmo `EstadoFinanceiro` de
`GAB-C` — não um `Diagnostico` fabricado à mão — porque
`CAPACIDADE_ATAQUE_CONSERVADORA = 3.000` é a entrada de `§10.2` (linha 457)
que efetivamente alimenta `CAPACIDADE_ATAQUE_M` do mês de abertura de
`simular_cenario`; usar o diagnóstico real garante que o teste exercite a
mesma cadeia de derivação (§11.10) que o motor usaria em produção, em vez de
injetar o número isoladamente.

**Tolerância.** `CUSTO_FUTURO_TOTAL` é valor monetário ACUMULADO ao longo de
6 meses simulados (soma de `DESEMBOLSO_ACUMULADO`, `engine/ciclo_mensal.py`)
— usa `assertar_monetario` (± R$ 0,05, RF-12/G-02), a única grandeza deste
teste sujeita a acúmulo de arredondamento entre meses. `PRAZO_TOTAL`,
`MESES_PRIMEIRA_VITORIA` e `ORDEM_QUITACAO` são valores exatos (número de
meses, mês de evento discreto, sequência de `DIVIDA_ID`) — tolerância zero
por definição (§9 do plano, `tests/conftest.py`), usam `assertar_exato`.

`ATAQUE_IMEDIATO_RECOMENDADO` (T-147, RF-66, AC-116) — cálculo à mão a partir
de `tests/fixtures/gab_c.json`: `DINHEIRO_DISPONIVEL=0`, `investimentos`,
`ativos` e `recursos_extraordinarios` são coleções vazias, e
`RESERVA_EXISTE=NAO` zera `RESERVA_MOBILIZAVEL` pela Regra 1 da §13.1 — os
cinco recursos estrategicamente recomendados somam `0`, então
`ATAQUE_IMEDIATO_RECOMENDADO = MIN(elegível, 0) = 0`, mesmo com as três
dívidas de `GAB-C` elegíveis e saldo positivo. Confirmado batendo com a
leitura real via `calcular_plano`.

REGRAS: RF-05, AC-01, §10.1, §10.2
"""

from __future__ import annotations

import pytest

from engine.ciclo_mensal import simular_cenario
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato, assertar_monetario
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Converte `EstadoFinanceiro.dividas` (tupla) no `Mapping[str, Divida]`
    indexado por `DIVIDA_ID` que `simular_cenario`/`criar_selecionar_alvo_
    avalanche` exigem — mesmo padrão de inventário já usado por `tests/
    regras/test_avalanche.py`/`test_simular_cenario.py`. `GAB-C` não tem
    nenhuma dívida com `SALDO_DEVEDOR_ATUAL` desconhecido (T-11), então a
    checagem abaixo é defensiva, não exercitada por este gabarito.
    """
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.mark.gabarito
def test_gabarito_c_avalanche() -> None:
    """AC-01: as quatro saídas de `GAB-C` no método Avalanche.

    ```
    PRAZO_TOTAL             = 6 meses
    CUSTO_FUTURO_TOTAL      = R$ 23.719,46
    MESES_PRIMEIRA_VITORIA  = mês 4
    ORDEM_QUITACAO          = D001 → D002 → D003
    ```
    """
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    dividas = _inventario(estado)

    diagnostico = calcular_diagnostico(estado, parametros)
    sel = criar_selecionar_alvo_avalanche(dividas, parametros)

    cenario = simular_cenario(estado, diagnostico, dividas, sel, parametros)

    assertar_exato(cenario.PRAZO_TOTAL, 6)
    assertar_monetario(cenario.CUSTO_FUTURO_TOTAL, dinheiro("23719.46"))
    assertar_exato(cenario.MESES_PRIMEIRA_VITORIA, 4)
    assertar_exato(cenario.ORDEM_QUITACAO, ("D001", "D002", "D003"))

    # T-147/RF-66/AC-116 — asserção nova: ATAQUE_IMEDIATO_RECOMENDADO é o
    # valor REAL (composto na segunda passada de calcular_plano, T-142),
    # não o placeholder que `diagnostico` (calcular_diagnostico isolada,
    # acima) sempre carrega. Cálculo à mão: 0 (ver docstring do módulo).
    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
