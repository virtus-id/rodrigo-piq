"""Gabarito `GAB-C` ponta a ponta — recomendação final do motor.

T-65 · RF-08 · RF-09 · RF-19 · `AC-04` · `AC-28` (`specs/motor-calculo.spec.md`)
· `piq-app-spec.md` §10.1 (linhas 419-427), §10.2 (linhas 453-464) · `Definições
§1` (`BURACO-05`, exemplo `NECESSIDADE_VITORIA=8` + `HISTORICO_ABANDONO=SIM`).

Este é o teste de INTEGRAÇÃO PONTA A PONTA que une toda a cadeia já validada
pelos gabaritos anteriores: roda os três métodos REAIS sobre `GAB-C`
(`tests/fixtures/gab_c.json`, via `tests/fixtures/carregar.py::carregar_gab_c`),
compara os cenários (`engine/comparacao.py::comparar_cenarios`, T-57/T-58),
deriva `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` a partir dos sinais
comportamentais do próprio gabarito (`engine/comportamento.py`, T-18, já
carregados por `carregar_gab_c` — `NECESSIDADE_VITORIA=8`,
`HISTORICO_ABANDONO=SIM`, ambos dado normativo da canônica linha 457, não
preenchimento de fixture), deriva `METODO_RECOMENDADO_PIQ`
(`engine/status_metodo.py::derivar_METODO_RECOMENDADO_PIQ`, T-61) e publica a
`ORDEM_QUITACAO` (`engine/ordem.py::publicar_ORDEM_QUITACAO`, T-63) sobre o
cenário do método recomendado.

`dg` (o `Diagnostico`) é produzido de verdade por `calcular_diagnostico`
(`engine/diagnostico.py`, T-24) — mesmo padrão dos três gabaritos de método
(`test_gabarito_c_avalanche.py`/`test_gabarito_c_bola_de_neve.py`/
`test_gabarito_c_hibrido.py`) — porque `NIVEL_CONTROLE`, `RISCO_RECAIDA` e
`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` já saem prontos dele, na mesma cadeia
de derivação (§11.10) que o motor usaria em produção: nada é recalculado à
parte nem fabricado à mão neste teste.

Resultado esperado (`AC-04`):

```
METODO_RECOMENDADO_PIQ              = HIBRIDO
INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE = SIM
ECONOMICAMENTE_PROXIMO(HIBRIDO)     = SIM
VITORIA_RAPIDA(HIBRIDO)             = SIM
```

— mesmo o superior econômico (`AC-28`) continuando a ser a Avalanche NO MESMO
teste: a recomendação diverge do superior puro por causa da camada
comportamental (`S-04`/`S-05`, `Definições §1`), não por engano de cálculo.

`ATAQUE_IMEDIATO_RECOMENDADO` (T-147, RF-66, AC-116) — cálculo à mão a partir
de `tests/fixtures/gab_c.json`: `DINHEIRO_DISPONIVEL=0`, `investimentos`,
`ativos` e `recursos_extraordinarios` são coleções vazias, e
`RESERVA_EXISTE=NAO` zera `RESERVA_MOBILIZAVEL` pela Regra 1 da §13.1 — os
cinco recursos estrategicamente recomendados somam `0`, então
`ATAQUE_IMEDIATO_RECOMENDADO = MIN(elegível, 0) = 0`, mesmo com as três
dívidas de `GAB-C` elegíveis e saldo positivo. Confirmado batendo com a
leitura real via `calcular_plano`.

REGRAS: RF-08, RF-09, RF-19, AC-04, AC-28
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.ciclo_mensal import simular_cenario
from engine.comparacao import comparar_cenarios
from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.gates import particionar_elegibilidade
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido
from engine.motor import calcular_plano
from engine.ordem import publicar_ORDEM_QUITACAO
from engine.precisao import dinheiro
from engine.status_metodo import derivar_METODO_RECOMENDADO_PIQ
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO, METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/gabaritos/test_gabarito_c_*.py`/
    `tests/regras/test_comparacao.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


@pytest.mark.gabarito
def test_gabarito_c_recomendacao() -> None:
    """AC-04/AC-28: a recomendação final do motor sobre `GAB-C`.

    ```
    METODO_RECOMENDADO_PIQ                 = HIBRIDO
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE = SIM
    ECONOMICAMENTE_PROXIMO(HIBRIDO)        = SIM
    VITORIA_RAPIDA(HIBRIDO)                = SIM
    CENARIO_ECONOMICAMENTE_SUPERIOR        = AVALANCHE (AC-28, no MESMO teste)
    ```
    """
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    dividas = _inventario(estado)

    diagnostico = calcular_diagnostico(estado, parametros)

    # Sinais normativos de GAB-C (canônica linha 457, Definições §1) já
    # carregados por carregar_gab_c — confirma que a fixture não regrediu
    # antes de usá-los via Diagnostico abaixo.
    assertar_exato(estado.sinais_comportamentais.NECESSIDADE_VITORIA, 8)
    assertar_exato(estado.sinais_comportamentais.HISTORICO_ABANDONO.value, "SIM")

    # Os três métodos REAIS sobre GAB-C — nenhum valor hardcoded (mesmo
    # padrão de test_comparacao.py::test_AC28_gabc_superior_e_avalanche).
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

    cenarios_rotulados = (
        dataclasses.replace(cenario_avalanche, metodo=METODO.AVALANCHE),
        dataclasses.replace(cenario_bola_de_neve, metodo=METODO.BOLA_DE_NEVE),
        dataclasses.replace(cenario_hibrido, metodo=METODO.HIBRIDO),
    )
    cenarios_por_metodo = {c.metodo: c for c in cenarios_rotulados if c.metodo is not None}

    comparacao = comparar_cenarios(cenarios_rotulados, parametros)

    # AC-28 (verificação cruzada, NO MESMO teste): o superior econômico
    # continua sendo a Avalanche — a recomendação final vai divergir dele
    # por causa da camada comportamental, não por erro de cálculo.
    assertar_exato(comparacao.CENARIO_ECONOMICAMENTE_SUPERIOR, METODO.AVALANCHE)

    # INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE (T-18) — derivada de verdade
    # pelo Diagnostico real de GAB-C (NECESSIDADE_VITORIA=8 >= limiar E
    # HISTORICO_ABANDONO=SIM), não fabricada à mão neste teste.
    assertar_exato(diagnostico.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE, True)

    resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
        cenarios_por_metodo,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=diagnostico.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
        INVENTARIO_COMPLETO=estado.INVENTARIO_COMPLETO,
        parametros=parametros,
    )

    # As quatro saídas de AC-04.
    assertar_exato(resultado_recomendacao.METODO_RECOMENDADO_PIQ, METODO.HIBRIDO)
    assertar_exato(comparacao.ECONOMICAMENTE_PROXIMO[METODO.HIBRIDO], True)

    teto_vitoria_rapida = parametros.numero("P_MESES_VITORIA_RAPIDA")
    meses_primeira_vitoria_hibrido = cenario_hibrido.MESES_PRIMEIRA_VITORIA
    assert meses_primeira_vitoria_hibrido is not None, (
        "Híbrido de GAB-C deveria quitar ao menos uma dívida dentro do horizonte "
        "simulado — ver tests/gabaritos/test_gabarito_c_hibrido.py"
    )
    assert meses_primeira_vitoria_hibrido <= teto_vitoria_rapida, (
        f"VITORIA_RAPIDA(HIBRIDO) deveria ser SIM: MESES_PRIMEIRA_VITORIA="
        f"{meses_primeira_vitoria_hibrido} <= P_MESES_VITORIA_RAPIDA={teto_vitoria_rapida}"
    )

    # Publica a ORDEM_QUITACAO sobre o cenário do método RECOMENDADO
    # (Híbrido) — reusa publicar_ORDEM_QUITACAO de T-63, nenhum
    # ranqueamento recalculado à parte (Q-04).
    particao = particionar_elegibilidade(estado.dividas)
    resultado_ordem = publicar_ORDEM_QUITACAO(
        cenario_hibrido, resultado_recomendacao.METODO_RECOMENDADO_PIQ, dividas, particao
    )

    assert resultado_ordem.ORDEM_QUITACAO, "ORDEM_QUITACAO publicada não pode ser vazia em GAB-C"
    for posicao in resultado_ordem.ORDEM_QUITACAO:
        assert posicao.JUSTIFICATIVA_POSICAO.strip() != "", (
            f"posição {posicao.posicao} ({posicao.DIVIDA_ID}) com "
            "JUSTIFICATIVA_POSICAO vazia — viola Q-05."
        )
        assert METODO.HIBRIDO.value in posicao.JUSTIFICATIVA_POSICAO

    # T-147/RF-66/AC-116 — asserção nova: ATAQUE_IMEDIATO_RECOMENDADO é o
    # valor REAL (composto na segunda passada de calcular_plano, T-142),
    # não o placeholder que `diagnostico` (calcular_diagnostico isolada,
    # acima) sempre carrega. Cálculo à mão: 0 (ver docstring do módulo).
    snapshot = calcular_plano(estado, parametros)
    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
