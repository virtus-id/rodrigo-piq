"""Testes de `engine/status_metodo.py` — `T-60`/`T-61`/`T-62`.

Cobre a família `S` completa (`S-01`..`S-05`), `AC-09` e `AC-04`:

- `S-01`/`S-02` (`specs/piq-app-spec.md`, Devolutiva final §6.1): somente
  `CLASSIFICACAO_CENARIO.NAO_CALCULAVEL` rebaixa `STATUS_METODO`;
  `NAO_APLICAVEL` (dados completos, regra metodológica não produz aquele
  cenário — ex. Híbrido sem candidata, `H-08`/`EC-03`) não rebaixa.
  Distinção com tolerância ZERO — comparada aqui com `assertar_exato`.
- `S-03`: `STATUS_METODO = DEFINITIVO_NA_DATA` exige TODOS os cenários
  aplicáveis calculáveis e nenhum bloqueio material (inventário completo).
- `AC-09`/`GAB-02`: `INVENTARIO_COMPLETO = False` ⇒ `STATUS_METODO` no
  máximo `PROVISORIO`, mesmo com todos os cenários `CALCULAVEL`.
- `S-04`/`EC-05` (`T-61`): `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` com o
  `CENARIO_ECONOMICAMENTE_SUPERIOR` E nenhuma alternativa `ECONOMICAMENTE_
  PROXIMA` ⇒ `STATUS_METODO = PROVISORIO` e `REVISAO_HUMANA_OBRIGATORIA =
  SIM` — `test_S04_incompatibilidade_sem_alternativa_aciona_revisao`
  (nome exigido literalmente pelo critério de aceite de `T-62`; já
  implementado aqui, `T-62` não precisa recriá-lo, mesma situação de
  `T-59`/`test_comparacao.py`).
- `S-05`/`EC-04` (`T-61`): Híbrido `NAO_APLICAVEL` com Bola de Neve
  `ECONOMICAMENTE_PROXIMA` NÃO aciona revisão —
  `test_S05_hibrido_nao_aplicavel_nao_aciona_revisao` (idem, nome exato de
  `T-62`, já implementado).
- `AC-04`/`GAB-C` (`T-61`): `METODO_RECOMENDADO_PIQ` combina superioridade
  econômica, proximidade, incompatibilidade comportamental e vitória
  rápida — determinístico e sempre `CALCULAVEL`.
- `T-62`: confirma S-01..S-05 e acrescenta `test_S02_nao_aplicavel_nao_
  rebaixa_status` — nome exigido literalmente pelo critério de aceite de
  `T-62`, distinto de `test_S02_nao_aplicavel_nao_rebaixa_status_metodo`
  (`T-60`, mantido). Mesma lógica, mesmo cenário sintético; ambos coexistem
  porque este projeto trata nome de teste como citação literal obrigatória
  de critério de aceite (ver `T-59`). Toda asserção de valor/status/
  classificação da família `S` usa `assertar_exato` — tolerância zero para
  `NAO_APLICAVEL` vs `PROVISORIO` (`sdd.config.md` §5).

REGRAS: RF-08, S-01, S-02, S-03, S-04, S-05, AC-04, AC-09
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.ciclo_mensal import Cenario
from engine.comparacao import ComparacaoCenarios
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.status_metodo import (
    derivar_METODO_RECOMENDADO_PIQ,
    derivar_STATUS_METODO,
)
from engine.tipos import CLASSIFICACAO_CENARIO, METODO, STATUS_METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


@pytest.fixture
def parametros() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _cenario(
    metodo: METODO,
    classificacao: CLASSIFICACAO_CENARIO | None,
    *,
    MESES_PRIMEIRA_VITORIA: int | None = None,
    CUSTO_FUTURO_TOTAL: str = "0",
    PRAZO_TOTAL: int = 0,
) -> Cenario:
    """Constrói um `Cenario` sintético mínimo — só os campos significativos
    para `derivar_STATUS_METODO`/`derivar_METODO_RECOMENDADO_PIQ` recebem
    valor; o resto é neutro. Mesmo padrão de
    `tests/regras/test_comparacao.py::_cenario`."""
    return Cenario(
        metodo=metodo,
        classificacao=classificacao,
        ORDEM_QUITACAO=(),
        PRAZO_TOTAL=PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=dinheiro(CUSTO_FUTURO_TOTAL),
        MESES_PRIMEIRA_VITORIA=MESES_PRIMEIRA_VITORIA,
        meses=(),
        ESTOUROU_HORIZONTE=False,
        MESES_ATE_ALERTA_HORIZONTE=None,
    )


def _comparacao(
    superior: METODO,
    economicamente_proximo: dict[METODO, bool],
) -> ComparacaoCenarios:
    """Constrói uma `ComparacaoCenarios` sintética mínima — só
    `CENARIO_ECONOMICAMENTE_SUPERIOR`/`ECONOMICAMENTE_PROXIMO` são
    significativos para `derivar_METODO_RECOMENDADO_PIQ`; os demais campos
    recebem valores neutros (a função sob teste não os inspeciona)."""
    return ComparacaoCenarios(
        CENARIO_ECONOMICAMENTE_SUPERIOR=superior,
        empatados_materialmente=(superior,),
        DIFERENCA_PERCENTUAL={superior: Decimal("0")},
        PENALIDADE_CUSTO={m: Decimal("0") for m in economicamente_proximo},
        ATRASO_PRAZO={m: 0 for m in economicamente_proximo},
        ECONOMICAMENTE_PROXIMO=economicamente_proximo,
    )


@pytest.mark.regra
def test_S01_nao_calculavel_rebaixa_status_metodo() -> None:
    """`S-01`: um cenário `NAO_CALCULAVEL` — falta dado material — rebaixa
    `STATUS_METODO` para `PROVISORIO`, mesmo com inventário completo e os
    demais cenários `CALCULAVEL`."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.NAO_CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=True)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.PROVISORIO)
    assert resultado.motivos, (
        "rebaixamento por NAO_CALCULAVEL precisa registrar motivo (AC de auditoria)"
    )
    assert any("NAO_CALCULAVEL" in motivo for motivo in resultado.motivos)


@pytest.mark.regra
def test_S02_nao_aplicavel_nao_rebaixa_status_metodo() -> None:
    """`S-02`/`EC-03`: Híbrido `NAO_APLICAVEL` (sem candidata, `H-08`) é um
    resultado válido — dados completos, a regra de negócio decidiu que não
    há cenário aplicável. NÃO rebaixa `STATUS_METODO`, distinção com
    tolerância ZERO frente a `NAO_CALCULAVEL` (`test_S01_*`)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.HIBRIDO: _cenario(METODO.HIBRIDO, CLASSIFICACAO_CENARIO.NAO_APLICAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=True)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.DEFINITIVO_NA_DATA)
    assertar_exato(resultado.motivos, ())


@pytest.mark.regra
def test_S02_nao_aplicavel_nao_rebaixa_status() -> None:
    """`S-02`/`EC-03`, nome exigido literalmente pelo critério de aceite de
    `T-62` (sem o sufixo `_metodo` de `test_S02_nao_aplicavel_nao_rebaixa_
    status_metodo`, criado em `T-60`). Mesma regra, mesmo cenário sintético:
    Híbrido `NAO_APLICAVEL` (sem candidata, `H-08`) é resultado válido de
    dados completos e NÃO rebaixa `STATUS_METODO` — distinção com
    tolerância ZERO frente a `NAO_CALCULAVEL` (`test_S01_*`). Preservado o
    teste original acima; este é um teste equivalente com o nome exato do
    backlog, não um alias — nomes de teste são citação literal obrigatória
    neste projeto (ver `T-59`)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.HIBRIDO: _cenario(METODO.HIBRIDO, CLASSIFICACAO_CENARIO.NAO_APLICAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=True)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.DEFINITIVO_NA_DATA)
    assertar_exato(resultado.motivos, ())


@pytest.mark.regra
def test_S03_todos_calculaveis_e_inventario_completo_e_definitivo() -> None:
    """`S-03`: `STATUS_METODO = DEFINITIVO_NA_DATA` exige que todos os
    cenários aplicáveis sejam plenamente calculáveis e que não exista
    bloqueio material — aqui, os três métodos `CALCULAVEL` mais
    `INVENTARIO_COMPLETO = True` produzem o status mais confiante possível,
    sem nenhum motivo de rebaixamento."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.HIBRIDO: _cenario(METODO.HIBRIDO, CLASSIFICACAO_CENARIO.CALCULAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=True)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.DEFINITIVO_NA_DATA)
    assertar_exato(resultado.motivos, ())


@pytest.mark.regra
def test_AC09_inventario_incompleto_limita_a_provisorio() -> None:
    """`AC-09`/`GAB-02`: `INVENTARIO_COMPLETO = False` limita `STATUS_METODO`
    ao máximo `PROVISORIO`, mesmo que todos os cenários sejam `CALCULAVEL`
    — nunca alcança `DEFINITIVO_NA_DATA` nessa condição."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
        METODO.HIBRIDO: _cenario(METODO.HIBRIDO, CLASSIFICACAO_CENARIO.CALCULAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=False)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.PROVISORIO)
    assert resultado.motivos, "rebaixamento por INVENTARIO_COMPLETO=False precisa registrar motivo"
    assert any("INVENTARIO_COMPLETO" in motivo for motivo in resultado.motivos)


@pytest.mark.regra
def test_AC09_e_S01_acumulam_motivos_mas_status_continua_provisorio() -> None:
    """Inventário incompleto (`AC-09`) e cenário `NAO_CALCULAVEL` (`S-01`)
    simultâneos geram DOIS motivos distintos na tupla de auditoria, mas o
    `STATUS_METODO` final continua `PROVISORIO` — não há nível mais baixo
    nesta tarefa (`T-60`)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, CLASSIFICACAO_CENARIO.NAO_CALCULAVEL),
        METODO.BOLA_DE_NEVE: _cenario(METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=False)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.PROVISORIO)
    assertar_exato(len(resultado.motivos), 2)


@pytest.mark.regra
def test_cenario_nao_classificado_none_nao_rebaixa() -> None:
    """`Cenario.classificacao = None` ("preenchido por tarefa futura", ver
    `engine/ciclo_mensal.py::Cenario`) não é `NAO_CALCULAVEL` — não deve
    rebaixar por si só. Só `NAO_CALCULAVEL` explícito rebaixa (`S-01`)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(METODO.AVALANCHE, None),
    }

    resultado = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=True)

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.DEFINITIVO_NA_DATA)
    assertar_exato(resultado.motivos, ())


# ---------------------------------------------------------------------------
# S-04/S-05/AC-04 — engine/status_metodo.py::derivar_METODO_RECOMENDADO_PIQ
# (T-61). Nomes `test_S04_*`/`test_S05_*` exigidos literalmente pelos
# critérios de aceite de T-62 — já implementados aqui, T-62 não precisa
# recriá-los (mesma situação de T-59/test_comparacao.py, ver docstring do
# módulo).
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_S04_incompatibilidade_sem_alternativa_aciona_revisao(parametros: Parametros) -> None:
    """`S-04`/`EC-05`: `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` com o
    `CENARIO_ECONOMICAMENTE_SUPERIOR` (Avalanche) e NENHUM cenário
    alternativo é `ECONOMICAMENTE_PROXIMO` ⇒ `STATUS_METODO = PROVISORIO`
    e `REVISAO_HUMANA_OBRIGATORIA = SIM`. O motor não pode decidir sozinho
    — mantém a Avalanche como recomendação (não há alternativa calculável
    melhor a oferecer), mas sinaliza a revisão."""
    cenarios = {
        METODO.AVALANCHE: _cenario(
            METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=4
        ),
        METODO.BOLA_DE_NEVE: _cenario(
            METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=1
        ),
    }
    comparacao = _comparacao(
        superior=METODO.AVALANCHE,
        economicamente_proximo={METODO.BOLA_DE_NEVE: False},  # fora dos tetos de RF-20
    )

    resultado = derivar_METODO_RECOMENDADO_PIQ(
        cenarios,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=True,
        INVENTARIO_COMPLETO=True,
        parametros=parametros,
    )

    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.PROVISORIO)
    assertar_exato(resultado.REVISAO_HUMANA_OBRIGATORIA, True)
    assertar_exato(resultado.METODO_RECOMENDADO_PIQ, METODO.AVALANCHE)
    assert resultado.motivos, "S-04 precisa registrar motivo de auditoria do rebaixamento"
    assert any("S-04" in motivo for motivo in resultado.motivos)
    assert resultado.motivo_recomendacao


@pytest.mark.regra
def test_S05_hibrido_nao_aplicavel_nao_aciona_revisao(parametros: Parametros) -> None:
    """`S-05`/`EC-04`: Híbrido `NAO_APLICAVEL` (sem candidata, `H-08`) e
    Bola de Neve `ECONOMICAMENTE_PROXIMA` da Avalanche (superior) — cenário
    normal, NÃO aciona `REVISAO_HUMANA_OBRIGATORIA`, mesmo havendo
    `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` com a Avalanche. A recomendação
    passa a ser a Bola de Neve, alternativa comportamental aplicável.
    `NAO_APLICAVEL` não entra em `comparacao.ECONOMICAMENTE_PROXIMO` (T-58)
    nem precisa entrar em `cenarios` para este teste — a ausência do
    Híbrido é, em si, a prova de que ele não concorre."""
    cenarios = {
        METODO.AVALANCHE: _cenario(
            METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=4
        ),
        METODO.BOLA_DE_NEVE: _cenario(
            METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=1
        ),
    }
    comparacao = _comparacao(
        superior=METODO.AVALANCHE,
        economicamente_proximo={METODO.BOLA_DE_NEVE: True},
    )

    resultado = derivar_METODO_RECOMENDADO_PIQ(
        cenarios,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=True,
        INVENTARIO_COMPLETO=True,
        parametros=parametros,
    )

    assertar_exato(resultado.REVISAO_HUMANA_OBRIGATORIA, False)
    assertar_exato(resultado.METODO_RECOMENDADO_PIQ, METODO.BOLA_DE_NEVE)
    assert "S-04" not in " ".join(resultado.motivos), (
        "S-05 é o cenário normal — não deve registrar motivo de rebaixamento por S-04"
    )


@pytest.mark.regra
def test_sem_incompatibilidade_recomenda_superior_sem_revisao(parametros: Parametros) -> None:
    """Caminho feliz: sem `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`, a
    recomendação é sempre `CENARIO_ECONOMICAMENTE_SUPERIOR` (`RF-19`), e
    `REVISAO_HUMANA_OBRIGATORIA` nunca é acionada por `S-04` (não há
    incompatibilidade a avaliar)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(
            METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=4
        ),
        METODO.BOLA_DE_NEVE: _cenario(
            METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=1
        ),
    }
    comparacao = _comparacao(
        superior=METODO.AVALANCHE,
        economicamente_proximo={METODO.BOLA_DE_NEVE: False},
    )

    resultado = derivar_METODO_RECOMENDADO_PIQ(
        cenarios,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=False,
        INVENTARIO_COMPLETO=True,
        parametros=parametros,
    )

    assertar_exato(resultado.METODO_RECOMENDADO_PIQ, METODO.AVALANCHE)
    assertar_exato(resultado.REVISAO_HUMANA_OBRIGATORIA, False)
    assertar_exato(resultado.STATUS_METODO, STATUS_METODO.DEFINITIVO_NA_DATA)


@pytest.mark.regra
def test_AC04_hibrido_proximo_e_vitoria_rapida_e_priorizado(parametros: Parametros) -> None:
    """`AC-04`/`GAB-C`: com incompatibilidade grave, entre várias
    alternativas `ECONOMICAMENTE_PROXIMA`, prioriza-se a que também é
    `VITORIA_RAPIDA` (`MESES_PRIMEIRA_VITORIA <= P_MESES_VITORIA_RAPIDA` =
    3, `parameters/parametros-1.0.1.json`) — o Híbrido (mês 1) vence sobre
    a Bola de Neve (mês 1 também, mas incluída só para provar que a
    presença de mais de um candidato não quebra o determinismo) quando
    ambas são candidatas, mesmo que a Bola de Neve não tenha vitória
    rápida neste cenário sintético (mês 5, fora do teto)."""
    cenarios = {
        METODO.AVALANCHE: _cenario(
            METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=4
        ),
        METODO.BOLA_DE_NEVE: _cenario(
            METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=5
        ),
        METODO.HIBRIDO: _cenario(
            METODO.HIBRIDO, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=1
        ),
    }
    comparacao = _comparacao(
        superior=METODO.AVALANCHE,
        economicamente_proximo={METODO.BOLA_DE_NEVE: True, METODO.HIBRIDO: True},
    )

    resultado = derivar_METODO_RECOMENDADO_PIQ(
        cenarios,
        comparacao,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=True,
        INVENTARIO_COMPLETO=True,
        parametros=parametros,
    )

    assertar_exato(resultado.METODO_RECOMENDADO_PIQ, METODO.HIBRIDO)
    assertar_exato(resultado.REVISAO_HUMANA_OBRIGATORIA, False)


@pytest.mark.regra
def test_recomendacao_nunca_e_nao_aplicavel_ou_nao_calculavel(parametros: Parametros) -> None:
    """Critério de aceite 4 de `T-61`: nenhum caminho de `derivar_METODO_
    RECOMENDADO_PIQ` recomenda um cenário `NAO_APLICAVEL`/`NAO_CALCULAVEL`
    — `comparacao` só enxerga métodos calculáveis (contrato de
    `comparar_cenarios`, `T-57`), e a recomendação final é sempre um
    `METODO` presente em `comparacao` (o superior ou um dos
    `ECONOMICAMENTE_PROXIMO`), nunca inventado. Testa os três ramos (sem
    incompatibilidade, S-04 sem alternativa, S-05 com alternativa) contra
    o mesmo `cenarios`, onde só Avalanche/Bola de Neve são `CALCULAVEL` —
    o Híbrido nem aparece, como um `NAO_APLICAVEL` real produziria."""
    cenarios = {
        METODO.AVALANCHE: _cenario(
            METODO.AVALANCHE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=4
        ),
        METODO.BOLA_DE_NEVE: _cenario(
            METODO.BOLA_DE_NEVE, CLASSIFICACAO_CENARIO.CALCULAVEL, MESES_PRIMEIRA_VITORIA=1
        ),
    }
    calculaveis = {METODO.AVALANCHE, METODO.BOLA_DE_NEVE}

    for incompatibilidade, proximo in (
        (False, False),
        (True, False),
        (True, True),
    ):
        comparacao = _comparacao(
            superior=METODO.AVALANCHE,
            economicamente_proximo={METODO.BOLA_DE_NEVE: proximo},
        )
        resultado = derivar_METODO_RECOMENDADO_PIQ(
            cenarios,
            comparacao,
            INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=incompatibilidade,
            INVENTARIO_COMPLETO=True,
            parametros=parametros,
        )
        assert resultado.METODO_RECOMENDADO_PIQ in calculaveis, (
            f"recomendação {resultado.METODO_RECOMENDADO_PIQ!r} fora dos métodos "
            "CALCULAVEL do cenário sintético"
        )
