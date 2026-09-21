"""Testa o filtro de evento futuro previsto — RF-22, AC-30 · §11.6.

Formaliza como teste real (commitado) a verificação ad-hoc feita em T-34: dois
`EstadoFinanceiro` idênticos exceto por `sinais_comportamentais.
NOVA_DIVIDA_PREVISTA` (`NAO` vs `SIM`/`TALVEZ`) produzem `Diagnostico`
IDÊNTICO em todos os campos de saldo/resultado — a única diferença observável
é `RISCO_RECAIDA` (via `classificar_RISCO_RECAIDA`, `engine/risco.py`) e o
alerta que `gerar_alerta_evento_futuro` (`engine/eventos.py`) produz.

Base: `carregar_gab_a()` (`tests/fixtures/gab_a.json`), que já traz
`NOVA_DIVIDA_PREVISTA = NAO` e contagem 0 de sinais da regra D.4 — trocar
só esse campo para `SIM`/`TALVEZ` isola exatamente a variável sob teste e
move a contagem de 0 para 1 sinal (BAIXO → MODERADO), tornando a mudança de
`RISCO_RECAIDA` observável sem tocar em nenhum outro sinal da fixture.

`dataclasses.replace` constrói as variações porque `EstadoFinanceiro` e
`SinaisComportamentais` são `frozen=True` (`engine/estado.py`, T-08) — não há
outro jeito de "editar um campo" sem reconstruir o objeto.
"""

from dataclasses import replace

import pytest

from engine.diagnostico import calcular_diagnostico
from engine.estado import JANELA_NOVA_DIVIDA, EstadoFinanceiro
from engine.eventos import AlertaEventoFuturo, gerar_alerta_evento_futuro
from engine.risco import classificar_RISCO_RECAIDA
from engine.tipos import NIVEL_RISCO, SimNaoTalvez
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a


def _parametros_reais() -> FonteParametrosArquivo:
    return FonteParametrosArquivo()


def _com_previsao(estado: EstadoFinanceiro, previsao: SimNaoTalvez) -> EstadoFinanceiro:
    """Devolve uma cópia de `estado` com `NOVA_DIVIDA_PREVISTA` trocado — e,
    quando SIM/TALVEZ, `JANELA_NOVA_DIVIDA` preenchida (campo COND, B1.02 →
    B1.05, `engine/estado.py`), replicando um estado coletado coerente."""
    sinais = estado.sinais_comportamentais
    janela = JANELA_NOVA_DIVIDA.QUATRO_A_SEIS_MESES if previsao is not SimNaoTalvez.NAO else None
    novos_sinais = replace(sinais, NOVA_DIVIDA_PREVISTA=previsao, JANELA_NOVA_DIVIDA=janela)
    return replace(estado, sinais_comportamentais=novos_sinais)


@pytest.mark.regra
def test_RF22_nova_divida_prevista_fora_da_projecao() -> None:
    """AC-30: `NOVA_DIVIDA_PREVISTA = SIM` (com `JANELA_NOVA_DIVIDA` definida)
    não altera NENHUM saldo/resultado do diagnóstico frente ao mesmo estado
    com `NAO` — só entra como sinal de risco e alerta (verificado nos testes
    seguintes deste módulo), nunca como dívida do inventário/projeção-base.
    """
    parametros = _parametros_reais().carregar("1.0.1")
    base = carregar_gab_a()

    estado_nao = _com_previsao(base, SimNaoTalvez.NAO)
    estado_sim = _com_previsao(base, SimNaoTalvez.SIM)

    diagnostico_nao = calcular_diagnostico(estado_nao, parametros)
    diagnostico_sim = calcular_diagnostico(estado_sim, parametros)

    # Os dez campos de saldo/resultado — tolerância ZERO (RF-22/AC-30: o
    # evento é apenas provável, não pode mover um único centavo do
    # diagnóstico determinístico).
    assertar_exato(
        diagnostico_sim.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES,
        diagnostico_nao.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES,
    )
    assertar_exato(
        diagnostico_sim.PAGAMENTOS_EFETIVOS_DIVIDAS, diagnostico_nao.PAGAMENTOS_EFETIVOS_DIVIDAS
    )
    assertar_exato(
        diagnostico_sim.RESULTADO_CAIXA_OBSERVADO, diagnostico_nao.RESULTADO_CAIXA_OBSERVADO
    )
    assertar_exato(diagnostico_sim.RESULTADO_MENSAL_ATUAL, diagnostico_nao.RESULTADO_MENSAL_ATUAL)
    assertar_exato(
        diagnostico_sim.GAP_CAIXA_VS_ESTRUTURAL, diagnostico_nao.GAP_CAIXA_VS_ESTRUTURAL
    )
    assertar_exato(diagnostico_sim.DEFICIT_MENSAL, diagnostico_nao.DEFICIT_MENSAL)
    assertar_exato(diagnostico_sim.PISO_CAPACIDADE, diagnostico_nao.PISO_CAPACIDADE)
    assertar_exato(
        diagnostico_sim.CAPACIDADE_ATAQUE_ATUAL, diagnostico_nao.CAPACIDADE_ATAQUE_ATUAL
    )
    assertar_exato(
        diagnostico_sim.CAPACIDADE_ATAQUE_CONSERVADORA,
        diagnostico_nao.CAPACIDADE_ATAQUE_CONSERVADORA,
    )
    assertar_exato(
        diagnostico_sim.CAPACIDADE_ATAQUE_POTENCIAL, diagnostico_nao.CAPACIDADE_ATAQUE_POTENCIAL
    )


@pytest.mark.regra
def test_RF22_saida_completa_identica_com_e_sem_previsao() -> None:
    """Compara a saída completa com e sem a previsão: ordem (`dividas`, a
    tupla do inventário) e saldos idênticos — nenhuma dívida hipotética foi
    adicionada ao estado a partir de `NOVA_DIVIDA_PREVISTA` (§11.6, garantia
    negativa documentada em `engine/eventos.py`)."""
    parametros = _parametros_reais().carregar("1.0.1")
    base = carregar_gab_a()

    estado_nao = _com_previsao(base, SimNaoTalvez.NAO)
    estado_talvez = _com_previsao(base, SimNaoTalvez.TALVEZ)

    # A tupla de dívidas em si — mesma identidade de conteúdo, mesma ordem,
    # mesmo tamanho. Nenhuma `Divida` hipotética foi construída.
    assertar_exato(estado_talvez.dividas, estado_nao.dividas)
    assertar_exato(len(estado_talvez.dividas), len(estado_nao.dividas))

    diagnostico_nao = calcular_diagnostico(estado_nao, parametros)
    diagnostico_talvez = calcular_diagnostico(estado_talvez, parametros)

    assertar_exato(
        diagnostico_talvez.RESULTADO_MENSAL_ATUAL, diagnostico_nao.RESULTADO_MENSAL_ATUAL
    )
    assertar_exato(
        diagnostico_talvez.RESULTADO_CAIXA_OBSERVADO, diagnostico_nao.RESULTADO_CAIXA_OBSERVADO
    )
    assertar_exato(
        diagnostico_talvez.CAPACIDADE_ATAQUE_CONSERVADORA,
        diagnostico_nao.CAPACIDADE_ATAQUE_CONSERVADORA,
    )


@pytest.mark.regra
@pytest.mark.parametrize("previsao", [SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ])
def test_RF22_sinal_de_risco_recaida_muda_com_previsao(previsao: SimNaoTalvez) -> None:
    """O sinal `NOVA_DIVIDA_PREVISTA` da regra D.4 (`engine/risco.py`, T-15)
    é um dos 5 sinais de `RISCO_RECAIDA`. `GAB-A` tem contagem 0 (BAIXO) com
    `NAO`; ativar SIM/TALVEZ soma exatamente 1 sinal, subindo para MODERADO
    — a classificação de risco muda entre os dois casos."""
    base = carregar_gab_a()
    estado_nao = _com_previsao(base, SimNaoTalvez.NAO)
    estado_com_previsao = _com_previsao(base, previsao)

    classificacao_nao = classificar_RISCO_RECAIDA(estado_nao.sinais_comportamentais)
    classificacao_com_previsao = classificar_RISCO_RECAIDA(
        estado_com_previsao.sinais_comportamentais
    )

    assertar_exato(classificacao_nao.contagem, 0)
    assertar_exato(classificacao_nao.nivel, NIVEL_RISCO.BAIXO)

    assertar_exato(classificacao_com_previsao.contagem, 1)
    assertar_exato(classificacao_com_previsao.nivel, NIVEL_RISCO.MODERADO)

    # A contagem aumenta estritamente — o sinal NOVA_DIVIDA_PREVISTA está
    # ativo no segundo caso e não no primeiro.
    assert classificacao_com_previsao.contagem > classificacao_nao.contagem


@pytest.mark.regra
def test_RF22_alerta_evento_futuro_nao_gera_com_previsao_nao() -> None:
    """`NOVA_DIVIDA_PREVISTA = NAO` ⇒ `gerar_alerta_evento_futuro` devolve
    `None` — ausência de objeto, não um objeto com campos nulos."""
    base = carregar_gab_a()
    estado_nao = _com_previsao(base, SimNaoTalvez.NAO)

    assertar_exato(gerar_alerta_evento_futuro(estado_nao), None)


@pytest.mark.regra
@pytest.mark.parametrize("previsao", [SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ])
def test_RF22_alerta_evento_futuro_preenchido_com_janela_preservada(
    previsao: SimNaoTalvez,
) -> None:
    """`NOVA_DIVIDA_PREVISTA ∈ {SIM, TALVEZ}` ⇒ `AlertaEventoFuturo`
    preenchido, com `NOVA_DIVIDA_PREVISTA` reproduzido e `JANELA_NOVA_DIVIDA`
    (B1.05) preservada sem alteração — puramente informativo (§11.6)."""
    base = carregar_gab_a()
    estado_com_previsao = _com_previsao(base, previsao)

    alerta = gerar_alerta_evento_futuro(estado_com_previsao)

    assert alerta is not None
    assert isinstance(alerta, AlertaEventoFuturo)
    assertar_exato(alerta.NOVA_DIVIDA_PREVISTA, previsao)
    assertar_exato(alerta.JANELA_NOVA_DIVIDA, JANELA_NOVA_DIVIDA.QUATRO_A_SEIS_MESES)
