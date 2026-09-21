"""`GAB-AI-05` — modo estabilização zera a reserva recomendada (`T-111`).

Gabarito oficial de homologação da §13.10, transcrito do documento canônico
PIQ v1.0.1: "a implementação deve reproduzir **exatamente** estes resultados".

    `GAB-AI-05`
      Cenário .......... `RESULTADO_MENSAL_ATUAL = -1.000`;
                         `RESERVA_MOBILIZAVEL = 20.000`
      Resultado ........ `MODO_ESTABILIZACAO = SIM`; `RESERVA_RECOMENDADA = 0`

Âncora: `AC-74` (`US-16`), `RF-46`, TRAVA MODO ESTABILIZAÇÃO da §13.4, §13.10.

A norma é literal: "a reserva não pode ser usada para mascarar déficit
estrutural". Quem gasta mais do que ganha todo mês não tem problema de caixa
pontual a resolver com reserva — tem déficit a estabilizar primeiro. Por isso
`RESERVA_RECOMENDADA = 0` **mesmo havendo 20.000 mobilizáveis**.

`MODO_ESTABILIZACAO` é campo de `Diagnostico`, derivado em
`engine/diagnostico.py` (`calcular_capacidades`, `RF-15`) da MESMA condição de
déficit (`RESULTADO_MENSAL_ATUAL < 0`) que arma a trava da §13.4. As duas
derivações são deliberadamente separadas — `derivar_RESERVA_RECOMENDADA` é
função pura e **não** consulta `Diagnostico` (spec §5, `RF-48`/`AC-80`) —, e
este gabarito verifica os dois lados da mesma condição: o campo de
`Diagnostico` e a reserva zerada.

**Tolerância ZERO** (spec §5, `OQ-34` respondida): `assertar_exato`;
`assertar_monetario` não aparece neste arquivo.
"""

import pytest

from engine.ataque_imediato import derivar_RESERVA_RECOMENDADA
from engine.diagnostico import calcular_diagnostico
from engine.precisao import dinheiro
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a


@pytest.mark.gabarito_ataque_imediato
def test_gab_ai_05_modo_estabilizacao_zera_reserva() -> None:
    """`GAB-AI-05` · `AC-74` · §13.10: `RESULTADO_MENSAL_ATUAL = -1.000` com
    `RESERVA_MOBILIZAVEL = 20.000` → `MODO_ESTABILIZACAO = SIM` e
    `RESERVA_RECOMENDADA = 0`.

    `MODO_ESTABILIZACAO` é lido do `Diagnostico` real produzido sobre um
    estado cujo `RESULTADO_MENSAL_ATUAL` é exatamente os `-1.000` do
    enunciado (o cenário `GAB-A`, `AC-05`) — não de um booleano escrito à
    mão no teste. É o mesmo número que alimenta a trava da §13.4 logo
    abaixo, e é isso que torna "a condição é uma só, escrita em dois
    lugares" uma afirmação verificada, não uma promessa de docstring.

    `NECESSIDADE_RESIDUAL` entra com os mesmos 20.000 para fechar o cerco: o
    `MIN(20.000, 20.000)` devolveria 20.000 se a trava não existisse ou se
    fosse avaliada depois. O `0` obtido só pode vir da trava.
    """
    diagnostico = calcular_diagnostico(carregar_gab_a(), FonteParametrosArquivo().carregar("1.0.1"))

    # O elo entre o `Diagnostico` e o enunciado: o resultado mensal do estado
    # é literalmente os `-1.000` de `GAB-AI-05`.
    assertar_exato(diagnostico.RESULTADO_MENSAL_ATUAL, dinheiro(-1000))
    assertar_exato(diagnostico.MODO_ESTABILIZACAO, True)

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(20000),
        NECESSIDADE_RESIDUAL=dinheiro(20000),
        RESULTADO_MENSAL_ATUAL=diagnostico.RESULTADO_MENSAL_ATUAL,
    )

    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))
