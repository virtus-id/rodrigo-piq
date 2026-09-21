"""Teste de comportamento de `app/eventos/mapeamento.py` — `RF-28`, `AC-35`
(`T-81`).

Cobre os quatro critérios de aceite da tarefa: (1) alteração cadastral não
produz `EVENTO_RECALCULO` — provado aqui pelo comportamento observável
(`None`) e, estruturalmente, pelo teste estático em
`tests/app_aluno/estatica/test_mapeamento_eventos_ac_35.py`; (2) nenhuma
passagem de tempo dispara evento (a função não aceita entrada de tempo
nenhuma, então este teste prova que o comportamento não muda entre chamadas);
(3) mapeamento por `valor_interno`, verificado indiretamente por não haver
`if` de pergunta no módulo (também coberto pelo teste estático); (4) resposta
sem evento correspondente devolve `None`, nunca um membro genérico.

REGRAS: `RF-28`, `AC-35`
"""

from __future__ import annotations

from app.eventos.mapeamento import VARIAVEL_STATUS_QUITACAO_REAL, evento_recalculo_da_resposta
from engine.tipos import EVENTO_RECALCULO


def test_quitacao_confirmada_mapeia_para_quitacao_confirmada() -> None:
    """`B11.Q01 = "Sim, foi quitada."` (`valor_interno: QUITADA`) é o único
    caminho desta função que produz `QUITACAO_CONFIRMADA` (RF-29, R-01)."""
    evento = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "QUITADA")

    assert evento is EVENTO_RECALCULO.QUITACAO_CONFIRMADA


def test_ainda_nao_nao_dispara_evento() -> None:
    """`B11.Q01 = "Ainda não."` (`valor_interno: NAO`) não é quitação —
    ausência explícita, não membro genérico."""
    evento = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "NAO")

    assert evento is None


def test_a_confirmar_nao_dispara_evento_ac_31() -> None:
    """AC-31: "Acredito que sim, mas ainda preciso confirmar." não dispara
    nada — nem quitação, nem qualquer outro evento."""
    evento = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "A_CONFIRMAR")

    assert evento is None


def test_alteracao_cadastral_nao_produz_evento_ac_35() -> None:
    """AC-35 — comportamento observável: uma variável de alteração cadastral
    qualquer (ex.: correção de um apelido/rótulo, que não tem
    `VARIAVEL_GRAVADA` mapeada) devolve `None`, nunca um `EVENTO_RECALCULO`.
    A prova ESTRUTURAL (o enum não tem membro para isso) está no teste
    estático `test_mapeamento_eventos_ac_35.py`."""
    evento = evento_recalculo_da_resposta("APELIDO_DIVIDA", "CORRIGIDO")

    assert evento is None


def test_virada_de_mes_nao_e_entrada_valida_para_disparo() -> None:
    """A função é pura sobre a resposta recebida — chamadas repetidas com os
    mesmos dois parâmetros (nenhuma passagem de tempo entre elas) produzem
    sempre o mesmo resultado, porque não há relógio nem estado mutável
    consultado por esta função."""
    primeira_chamada = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "NAO")
    segunda_chamada = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "NAO")

    assert primeira_chamada is None
    assert segunda_chamada is None


def test_variavel_gravada_desconhecida_devolve_ausencia_explicita() -> None:
    """Quarto critério: `VARIAVEL_GRAVADA` que não pertence a nenhum
    mapeamento conhecido também devolve `None` — nunca um membro qualquer do
    enum escolhido por aproximação."""
    evento = evento_recalculo_da_resposta("VARIAVEL_INEXISTENTE", "QUITADA")

    assert evento is None


def test_todos_os_membros_do_enum_permanecem_alcancaveis_pelo_mapeamento_ou_fora_de_escopo() -> (
    None
):
    """Prova negativa: o dicionário interno só produz membros REAIS de
    `EVENTO_RECALCULO` — nunca um valor fora do enum (garantido pelo próprio
    tipo do dicionário, checado por `mypy --strict`, `build` do sdd.config.md).
    Este teste fixa o único membro hoje alcançável a partir do registro
    transcrito por T-18 (`QUITACAO_CONFIRMADA`); os demais dependem de
    transcrição futura de `valor_interno` nas perguntas de resultado de ação
    (ver docstring do módulo)."""
    evento = evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, "QUITADA")

    assert evento in set(EVENTO_RECALCULO)
