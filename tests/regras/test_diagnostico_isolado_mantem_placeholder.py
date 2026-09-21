"""Prova de que `calcular_diagnostico` chamada ISOLADAMENTE — sem passar por
`calcular_plano` — continua devolvendo o placeholder `dinheiro(0)` em
`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` — `RF-68` · `RF-69` · `AC-112` ·
`US-26` · `T-146`.

Esta é a garantia central de que a decisão `OQ-44`/(2) (plano R4C.1.1) — "não
dar a `calcular_diagnostico` acesso a `ParticaoElegibilidade`/
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`" — **não vazou comportamento** para
fora da segunda passada de `engine/motor.py::_compor_ATAQUE_IMEDIATO_
RECOMENDADO` (`T-141`/`T-142`). A varredura de 22 chamadores de teste do plano
R4C.1.3 identificou que boa parte deles chama `calcular_diagnostico` de forma
isolada, ESPERANDO que `ATAQUE_IMEDIATO_RECOMENDADO` continue `0` — se esta
função passasse a produzir o valor real por conta própria (ex.: importando
`particionar_elegibilidade` internamente), aqueles 22 chamadores quebrariam ou,
pior, silenciosamente passariam a exercitar um caminho de cálculo diferente do
que testam. Este teste é a prova única e dedicada de que isso não acontece —
`T-144` (`test_ataque_imediato_recomendado_diagnostico.py`) cobre o lado
oposto (`calcular_plano` ponta a ponta produz o valor real) e não substitui
esta prova.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.diagnostico import calcular_diagnostico
from engine.parametros import Parametros
from engine.precisao import dinheiro
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c


@pytest.mark.regra
def test_calcular_diagnostico_isolado_mantem_ataque_imediato_recomendado_zero() -> None:
    """`AC-112`/`RF-68`/`RF-69` · `OQ-44` decisão (2) · plano R4C.1.3.

    Mesmo perfil de `AC-112` (`T-144`): `EstadoFinanceiro` com dívida
    elegível com `VALOR_RELEVANTE_PARA_QUITACAO > 0` (as três dívidas de
    `GAB-C`, saldos `12.000`/`7.000`/`3.000`, nenhuma bloqueada pelos gates)
    e recursos positivos (`DINHEIRO_DISPONIVEL` elevado de `0`, valor da
    fixture, para um valor positivo). A diferença deliberada em relação a
    `AC-112` é a chamada: aqui é **apenas** `calcular_diagnostico(estado,
    parametros)` — `calcular_plano` nunca é invocada, em nenhum ponto deste
    teste.

    Se o cenário fosse "vazio" (sem dívida elegível, sem recurso algum), um
    `ATAQUE_IMEDIATO_RECOMENDADO=0` não provaria nada — poderia ser
    coincidência do cenário trivial. Usar o MESMO perfil positivo de `AC-112`
    é o que torna esta prova honesta: mesmo com todos os insumos que
    produziriam um valor real diferente de zero via `calcular_plano`
    (confirmado por `T-144`), a chamada isolada a `calcular_diagnostico`
    CONTINUA devolvendo o placeholder — porque esta função nunca teve, e por
    desenho (`OQ-44`/R4C.1.1) não tem, acesso a `ParticaoElegibilidade`/
    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, que só existem depois dos
    gates rodarem dentro de `calcular_plano`.
    """
    estado = dataclasses.replace(carregar_gab_c(), DINHEIRO_DISPONIVEL=dinheiro("1000"))
    parametros: Parametros = FonteParametrosArquivo().carregar("1.0.1")

    diagnostico = calcular_diagnostico(estado, parametros)

    assertar_exato(diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
