"""Testa os gatilhos de recálculo externo — RF-02, RF-22 · AC-13, AC-31 ·
EC-02, EC-08, EC-09 · `T-66`.

**Desambiguação de nomenclatura `R-*` (ver docstring de `engine/eventos.py`
para o detalhe completo).** A spec canônica usa o prefixo `R-01`..`R-05`
para DUAS famílias de regra distintas:

1. Reranqueamento *intramês*, dentro do laço de `simular_cenario`/
   `executar_mes` (`engine/ciclo_mensal.py`) — já testado em
   `tests/regras/test_R.py` (T-47), que NÃO é tocado por este arquivo.
2. Gatilho de recálculo *externo*, que decide se o mundo real (quitação
   confirmada, evento material) justifica produzir um novo
   `SnapshotOrdem` fora do laço de simulação de um cenário — objeto de
   `T-66`/`avaliar_gatilho_recalculo` (`engine/eventos.py`), testado aqui.

Por isso os testes deste arquivo citam RF/AC/EC no nome, não o ID `R-*`
isolado — evita reaproveitar um ID já usado por `test_R.py` com outro
significado.
"""

from __future__ import annotations

import pytest

from engine.eventos import ResultadoGatilhoRecalculo, avaliar_gatilho_recalculo
from engine.tipos import EVENTO_RECALCULO
from tests.conftest import assertar_exato


@pytest.mark.regra
def test_RF02_quitacao_confirmada_dispara_recalculo() -> None:
    """RF-02 · EC-02: quitação confirmada de qualquer dívida — inclusive a
    que se encerra apenas pelo pagamento normal, sem ataque — dispara
    recálculo."""
    resultado = avaliar_gatilho_recalculo(EVENTO_RECALCULO.QUITACAO_CONFIRMADA)

    assert isinstance(resultado, ResultadoGatilhoRecalculo)
    assertar_exato(resultado.deve_recalcular, True)
    assertar_exato(resultado.evento, EVENTO_RECALCULO.QUITACAO_CONFIRMADA)
    assert resultado.motivo  # motivo auditável nunca vazio


@pytest.mark.regra
def test_AC13_virada_de_mes_sozinha_nao_dispara_recalculo() -> None:
    """RF-02 · AC-13: ausência de `EVENTO_RECALCULO` (nenhuma quitação,
    nenhum evento externo material — inclui a mera passagem de mês) NÃO
    justifica recálculo."""
    resultado = avaliar_gatilho_recalculo(None)

    assertar_exato(resultado.deve_recalcular, False)
    assertar_exato(resultado.evento, None)
    assert resultado.motivo  # motivo auditável nunca vazio


@pytest.mark.regra
def test_EC08_alteracao_cosmetica_e_inexprimivel_no_enum() -> None:
    """RF-02 · EC-08: não existe forma de expressar um evento cadastral/
    cosmético em `EVENTO_RECALCULO` — a garantia é estrutural (ausência de
    membro), não uma checagem em runtime.

    Prova por inspeção: nenhum membro do enum corresponde a alteração de
    nome, apelido, telefone ou qualquer dado cosmético/cadastral — os únicos
    membros existentes são eventos materiais (quitação, renda, despesas,
    nova dívida, renegociação, troca, recurso extraordinário, informação
    material, patrimônio, proposta temporária, risco, outro material).
    """
    nomes_membros = {membro.name for membro in EVENTO_RECALCULO}

    termos_cosmeticos = {
        "CADASTRO",
        "CADASTRAL",
        "COSMETICO",
        "COSMETICA",
        "NOME",
        "APELIDO",
        "TELEFONE",
        "CORRECAO",
        "CORRECAO_TEXTUAL",
    }
    assertar_exato(nomes_membros & termos_cosmeticos, set())

    # Todo membro existente é material — nenhum enum "vazio"/neutro que um
    # chamador pudesse usar para representar uma mudança cosmética.
    assertar_exato(
        nomes_membros,
        {
            "QUITACAO_CONFIRMADA",
            "ALTERACAO_RENDA",
            "ALTERACAO_DESPESAS",
            "NOVA_DIVIDA",
            "RENEGOCIACAO_EXECUTADA",
            "TROCA_EXECUTADA",
            "RECURSO_EXTRAORDINARIO",
            "INFORMACAO_MATERIAL_CONHECIDA",
            "MUDANCA_PATRIMONIAL",
            "PROPOSTA_TEMPORARIA",
            "ALTERACAO_RISCO",
            "OUTRO_MATERIAL",
        },
    )


def test_EC08_alteracao_cosmetica_falha_em_tempo_de_execucao_ao_tentar_construir() -> None:
    """RF-02 · EC-08 — segunda prova, agora tentando efetivamente construir
    o membro inexistente: `EVENTO_RECALCULO["COSMETICO"]` (acesso por nome)
    levanta `KeyError`, e `EVENTO_RECALCULO("COSMETICO")` (acesso por valor)
    levanta `ValueError`. Não há caminho, nem por nome nem por valor, capaz
    de produzir um `EVENTO_RECALCULO` cosmético."""
    with pytest.raises(KeyError):
        EVENTO_RECALCULO["COSMETICO"]

    with pytest.raises(ValueError):
        EVENTO_RECALCULO("COSMETICO")


@pytest.mark.regra
def test_AC31_nova_divida_contratada_gera_evento_recalculo_nova_divida() -> None:
    """AC-31: dada a contratação efetiva de nova dívida, quando registrada,
    então `EVENTO_RECALCULO = NOVA_DIVIDA` e o gatilho dispara recálculo
    (a montagem do novo snapshot em si é `T-67`/`T-70`, fora deste
    módulo)."""
    resultado = avaliar_gatilho_recalculo(EVENTO_RECALCULO.NOVA_DIVIDA)

    assertar_exato(resultado.evento, EVENTO_RECALCULO.NOVA_DIVIDA)
    assertar_exato(resultado.deve_recalcular, True)


@pytest.mark.regra
@pytest.mark.parametrize("evento", list(EVENTO_RECALCULO))
def test_RF02_todo_evento_material_dispara_recalculo_sempre(evento: EVENTO_RECALCULO) -> None:
    """RF-02: qualquer membro de `EVENTO_RECALCULO` — não só
    `QUITACAO_CONFIRMADA` e `NOVA_DIVIDA` — dispara recálculo. A decisão
    depende só de o evento existir, nunca de qual evento é."""
    resultado = avaliar_gatilho_recalculo(evento)

    assertar_exato(resultado.deve_recalcular, True)
    assertar_exato(resultado.evento, evento)


@pytest.mark.regra
def test_EC09_evento_material_com_resultado_identico_ainda_assim_recalcula() -> None:
    """RF-02 · EC-09: um evento material sempre gera novo snapshot mesmo que
    o resultado calculado seja idêntico ao anterior (mesmo método
    recomendado, mesmo D*) — o gatilho não compara resultados, só verifica
    se houve evento. Duas avaliações do MESMO evento produzem a MESMA
    decisão de recalcular — não há "otimização" que dependa de um resultado
    hipotético ainda não calculado."""
    primeira_avaliacao = avaliar_gatilho_recalculo(EVENTO_RECALCULO.RENEGOCIACAO_EXECUTADA)
    segunda_avaliacao = avaliar_gatilho_recalculo(EVENTO_RECALCULO.RENEGOCIACAO_EXECUTADA)

    # Nenhuma das duas avaliações recebe (ou poderia receber) o resultado do
    # cálculo anterior como argumento — a assinatura de avaliar_gatilho_
    # recalculo(evento) não aceita um "snapshot anterior" para comparar.
    assertar_exato(primeira_avaliacao.deve_recalcular, True)
    assertar_exato(segunda_avaliacao.deve_recalcular, True)
    assertar_exato(primeira_avaliacao.deve_recalcular, segunda_avaliacao.deve_recalcular)
