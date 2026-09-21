"""Gabarito `GAB-C` ponta a ponta — método Híbrido.

T-55 · RF-07 · `AC-03` (`specs/motor-calculo.spec.md`) · `piq-app-spec.md`
§10.1 (linhas 419-427), §10.2 (linhas 453-464).

Formaliza no local correto (`tests/gabaritos/`, marcador `gabarito`) a
reprodução ponta a ponta de `AC-03`: monta o cenário `GAB-C` (fixture
`tests/fixtures/gab_c.json`, carregada por `tests/fixtures/carregar.py::
carregar_gab_c`), determina `D*` e a `SelecionarAlvo` do Híbrido via
`criar_selecionar_alvo_hibrido` (T-53/T-54, `engine/metodos/hibrido.py`), roda
`simular_cenario` (T-46, `engine/ciclo_mensal.py`) com essa `SelecionarAlvo`, e
verifica as SETE saídas esperadas:

```
PRAZO_TOTAL                     = 6 meses
CUSTO_FUTURO_TOTAL              = R$ 24.107,20
MESES_PRIMEIRA_VITORIA          = mês 1
ORDEM_QUITACAO                  = D003 → D001 → D002
D*                              = D003
PENALIDADE_CUSTO_VS_AVALANCHE   = 1,635%
ATRASO_PRAZO_VS_AVALANCHE       = 0 mês
```

Mesmo padrão de montagem de cenário de `test_gabarito_c_avalanche.py` (T-50) e
`test_gabarito_c_bola_de_neve.py` (T-52), com duas diferenças estruturais
exigidas pelo contrato do Híbrido (`T-54`):

1. `criar_selecionar_alvo_hibrido` devolve `ResultadoHibrido`, não uma
   `SelecionarAlvo` pura — é preciso primeiro confirmar
   `classificacao is CLASSIFICACAO_CENARIO.CALCULAVEL` (nunca `NAO_APLICAVEL`,
   `H-08`/`EC-03`) e só então extrair `.selecionar_alvo` para simular. Simular
   com `selecionar_alvo = None` seria um erro de tipo silencioso — a checagem
   aqui é também a prova de que `GAB-C` tem um Híbrido aplicável, não apenas
   uma conveniência de tipo.
2. `D*` (o `DIVIDA_ID` escolhido por `escolher_D_ESTRELA`, Etapas 1-4 de
   `H-01`..`H-04`) e as métricas de tolerância (`PENALIDADE_CUSTO_VS_
   AVALANCHE`/`ATRASO_PRAZO_VS_AVALANCHE`) não aparecem em `Cenario` — são
   auditadas separadamente a partir do rastro de `escolher_D_ESTRELA`
   (`tuple[MetricasHibridoD, ...]`), filtrando a candidata cujo `DIVIDA_ID`
   é o próprio `D*`.

**Tolerâncias — decisão e justificativa (critério de aceite 2).**
`PRAZO_TOTAL`, `MESES_PRIMEIRA_VITORIA`, `ORDEM_QUITACAO`, `D*` e
`ATRASO_PRAZO_VS_AVALANCHE` (todos valores exatos por natureza — contagem de
meses, sequência de `DIVIDA_ID`, diferença inteira de prazos) usam
`assertar_exato` (tolerância zero), na lista explícita de
`tests/conftest.py::assertar_exato` ("D*", "número de meses",
"MESES_PRIMEIRA_VITORIA"). `CUSTO_FUTURO_TOTAL` é valor monetário ACUMULADO ao
longo de 6 meses simulados (soma de `DESEMBOLSO_ACUMULADO`) — usa
`assertar_monetario` (± R$ 0,05, RF-12/G-02), mesmo padrão dos outros dois
gabaritos de `GAB-C` (T-50/T-52).

`PENALIDADE_CUSTO_VS_AVALANCHE` é uma FRAÇÃO decimal mantida com precisão
interna integral (`§11.5`, mesma fórmula de `PENALIDADE_CUSTO(X)`) — não um
valor monetário, então `assertar_monetario` (tolerância em R$) não se aplica
por natureza. O gabarito normativo (`AC-03`) publica o valor já arredondado
para exibição ("penalidade econômica 1,635%", 3 casas percentuais = G-01: "o
arredondamento existe apenas na camada de exibição"). Como não há um dígito
"redondo" internamente (o valor calculado é
`0.016346812053870890...`, uma fração de divisão exata entre dois
`CUSTO_FUTURO_TOTAL`), comparar a fração de precisão total contra
`Decimal("0.01635")` com tolerância zero nunca bateria — mas comparar com
`assertar_monetario` (pensado para R$, não para uma fração adimensional)
seria emprestar uma tolerância de natureza errada. A escolha adotada aqui é
`assertar_exato` aplicado ao valor JÁ ARREDONDADO à mesma casa que o gabarito
publica (percentual com 3 casas, `Decimal.quantize(Decimal("0.001"))` sobre
`PENALIDADE_CUSTO_VS_AVALANCHE * 100`) — a mesma fronteira de arredondamento
de exibição que `G-01` já reserva para dinheiro, aplicada aqui à única outra
grandeza fracionária que o gabarito reporta arredondada, com tolerância ZERO
depois desse ponto de corte (nenhuma folga adicional).

**`ATAQUE_IMEDIATO_RECOMENDADO` (T-147, RF-66, AC-116).** Cálculo à mão a
partir de `tests/fixtures/gab_c.json`: `DINHEIRO_DISPONIVEL=0`,
`investimentos`, `ativos` e `recursos_extraordinarios` são coleções vazias, e
`RESERVA_EXISTE=NAO` zera `RESERVA_MOBILIZAVEL` pela Regra 1 da §13.1 — os
cinco recursos estrategicamente recomendados somam `0`, então
`ATAQUE_IMEDIATO_RECOMENDADO = MIN(elegível, 0) = 0`, mesmo com as três
dívidas de `GAB-C` elegíveis e saldo positivo. Confirmado batendo com a
leitura real via `calcular_plano`.

REGRAS: RF-07, AC-03, §10.1, §10.2, H-01, H-02, H-03, H-04, H-05, H-08, EC-03
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.ciclo_mensal import simular_cenario
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido, escolher_D_ESTRELA
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato, assertar_monetario
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Converte `EstadoFinanceiro.dividas` (tupla) no `Mapping[str, Divida]`
    indexado por `DIVIDA_ID` que `simular_cenario`/`escolher_D_ESTRELA`/
    `criar_selecionar_alvo_hibrido` exigem — mesmo padrão de inventário já
    usado por `tests/gabaritos/test_gabarito_c_avalanche.py`/
    `test_gabarito_c_bola_de_neve.py`. `GAB-C` não tem nenhuma dívida com
    `SALDO_DEVEDOR_ATUAL` desconhecido (T-11), então a checagem abaixo é
    defensiva, não exercitada por este gabarito.
    """
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.mark.gabarito
def test_gabarito_c_hibrido() -> None:
    """AC-03: as sete saídas de `GAB-C` no método Híbrido.

    ```
    PRAZO_TOTAL                    = 6 meses
    CUSTO_FUTURO_TOTAL             = R$ 24.107,20
    MESES_PRIMEIRA_VITORIA         = mês 1
    ORDEM_QUITACAO                 = D003 → D001 → D002
    D*                             = D003
    PENALIDADE_CUSTO_VS_AVALANCHE  = 1,635%
    ATRASO_PRAZO_VS_AVALANCHE      = 0 mês
    ```
    """
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    dividas = _inventario(estado)

    diagnostico = calcular_diagnostico(estado, parametros)

    # Etapas 1-4 (H-01..H-04): D* e o rastro de métricas de toda candidata
    # avaliada — fonte de auditoria para D*/PENALIDADE_CUSTO_VS_AVALANCHE/
    # ATRASO_PRAZO_VS_AVALANCHE, que não aparecem em `Cenario`.
    d_estrela, metricas = escolher_D_ESTRELA(estado, dividas, diagnostico, parametros)
    assertar_exato(d_estrela, "D003")

    metrica_d_estrela = next(m for m in metricas if m.DIVIDA_ID == d_estrela)
    assertar_exato(metrica_d_estrela.ATRASO_PRAZO_VS_AVALANCHE, 0)

    penalidade_percentual = (metrica_d_estrela.PENALIDADE_CUSTO_VS_AVALANCHE * 100).quantize(
        Decimal("0.001")
    )
    assertar_exato(penalidade_percentual, Decimal("1.635"))

    # Etapa 5 (H-05/H-06/H-07): ResultadoHibrido carrega a classificação
    # formal junto com a SelecionarAlvo — H-08/EC-03 exige confirmar
    # CALCULAVEL (nunca NAO_APLICAVEL) antes de simular; GAB-C tem Híbrido
    # aplicável, então esta asserção também é prova de que a classificação
    # não regrediu para NAO_APLICAVEL.
    resultado = criar_selecionar_alvo_hibrido(estado, dividas, diagnostico, parametros)
    assertar_exato(resultado.classificacao, CLASSIFICACAO_CENARIO.CALCULAVEL)
    assert resultado.selecionar_alvo is not None, (
        "GAB-C deveria ter Híbrido aplicável (D003 sobrevive às três "
        "tolerâncias de H-03) — ver escolher_D_ESTRELA acima"
    )

    cenario = simular_cenario(estado, diagnostico, dividas, resultado.selecionar_alvo, parametros)

    assertar_exato(cenario.PRAZO_TOTAL, 6)
    assertar_monetario(cenario.CUSTO_FUTURO_TOTAL, dinheiro("24107.20"))
    assertar_exato(cenario.MESES_PRIMEIRA_VITORIA, 1)
    assertar_exato(cenario.ORDEM_QUITACAO, ("D003", "D001", "D002"))

    # T-147/RF-66/AC-116 — asserção nova: ATAQUE_IMEDIATO_RECOMENDADO é o
    # valor REAL (composto na segunda passada de calcular_plano, T-142),
    # não o placeholder que `diagnostico` (calcular_diagnostico isolada,
    # acima) sempre carrega. Cálculo à mão: 0 (ver docstring do módulo).
    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
