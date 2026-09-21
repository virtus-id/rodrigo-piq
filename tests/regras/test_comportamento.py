"""Testes de `derivar_NIVEL_CONTROLE` (T-12), `derivar_CONFIABILIDADE_DADOS`
(T-13/T-14) e de `derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` (T-19) —
RF-23, RF-24, RF-27, Definições §4, Definições §5, Definições §1.

O primeiro bloco cobre os três ramos do domínio de `NIVEL_CONTROLE`
(`FRAGIL`, `FORTE`, `PARCIAL`) e, em particular, a ordem de avaliação
obrigatória `FRAGIL → FORTE → PARCIAL`: um perfil que tecnicamente
satisfaria todas as cinco condições de `FORTE` mas também dispara uma
condição de `FRAGIL` deve classificar `FRAGIL` — nunca `FORTE` — provando
que `FRAGIL` é testado primeiro.

O segundo bloco (T-14) cobre `derivar_CONFIABILIDADE_DADOS` (`AC-46`,
Definições §5): os três ramos do domínio (`BAIXA`, `ALTA`, `MEDIA`) e a
ordem de avaliação obrigatória `BAIXA → ALTA → MEDIA` — invertida em
relação à de `NIVEL_CONTROLE`. `AC-46` em particular prova que
`NIVEL_CONTROLE = FRAGIL` já basta para `BAIXA`, mesmo quando as outras três
condições de `BAIXA` não disparam sozinhas.

O terceiro bloco (T-19) cobre `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`
(`AC-34`, `AC-35`): os dois lados da conjunção — `NECESSIDADE_VITORIA` alta
sozinha não basta, sinal comportamental isolado sozinho não basta — e a
fronteira exata do limiar `P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA`.
`NIVEL_CONTROLE` e `RISCO_RECAIDA` são passados diretamente como enums já
derivados (`NIVEL_CONTROLE.FORTE`/`FRAGIL`, `NIVEL_RISCO.BAIXO`/`ALTO`) em
vez de recompostos via `derivar_NIVEL_CONTROLE`/`classificar_RISCO_RECAIDA`
— a função sob teste (`derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`)
recebe os dois já derivados como parâmetros obrigatórios (mesma trava de
assinatura documentada em `engine/comportamento.py`), e T-19 testa esta
função, não as que produzem seus parâmetros — testar por perfil/sinais D.4
completos aqui só acrescentaria acoplamento a T-12/T-16 sem cobrir nada a
mais da regra sob teste.
"""

import pytest

from engine.comportamento import (
    derivar_CONFIABILIDADE_DADOS,
    derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
    derivar_NIVEL_CONTROLE,
)
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    REVISAO_SEMANAL,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.tipos import CONFIABILIDADE_DADOS, NIVEL_CONTROLE, NIVEL_RISCO, SimNaoTalvez
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato

# T-19: parâmetros reais, carregados de `parameters/parametros-1.0.1.json` —
# mesma fonte que o motor usa em execução (AC-17: nunca literal no teste
# como se fosse o valor do parâmetro; lê-se a fonte externa de verdade).
_PARAMETROS = FonteParametrosArquivo().carregar("1.0.1")
_LIMIAR_NECESSIDADE_VITORIA = int(
    _PARAMETROS.numero("P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA")
)


def _sinais_comportamentais(
    *, necessidade_vitoria: int, historico_abandono: SimNaoTalvez
) -> SinaisComportamentais:
    """Monta `SinaisComportamentais` completo e válido para os testes de
    T-19, variando apenas `NECESSIDADE_VITORIA`/`HISTORICO_ABANDONO` — os
    dois campos que `derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` lê
    diretamente de `sinais` (Definições §1). Os demais campos recebem
    valores neutros: não alimentam esta função (só `RISCO_RECAIDA`/
    `RISCO_COMPORTAMENTAL_GERAL`, D.4, fora do escopo de T-19) e por isso
    são irrelevantes ao resultado — mantidos "sem risco" para não sugerir,
    por acidente de fixture, nenhum sinal que não o que o teste declara.
    """
    return SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
        MECANISMO_DEFICIT=frozenset(),
        HISTORICO_RECAIDA=SimNaoTalvez.NAO,
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
        PACTO="ESTABELECIDO",
        RISCO_IMPULSO="NENHUMA",
        LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
        NECESSIDADE_VITORIA=necessidade_vitoria,
        HISTORICO_ABANDONO=historico_abandono,
        JANELA_NOVA_DIVIDA=None,  # T-34: NOVA_DIVIDA_PREVISTA=NAO acima, ausência estrutural
    )

# Perfil-base que satisfaz integralmente as 5 condições de FORTE (Definições
# §4), usado como ponto de partida e alterado campo a campo pelos testes.
_PERFIL_FORTE_BASE = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)


@pytest.mark.regra
def test_fragil_por_registro_gastos_raramente() -> None:
    """Definições §4: `REGISTRO_GASTOS ∈ {RARAMENTE, NAO_REGISTRA}` basta."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.RARAMENTE,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.SOB_DEMANDA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.SEM_PADRAO,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.ALGUNS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.PARCIAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.NOCAO_GERAL,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.ALGUMAS_MES,
        REVISAO_SEMANAL=REVISAO_SEMANAL.ALGUMAS,
    )
    assertar_exato(derivar_NIVEL_CONTROLE(perfil), NIVEL_CONTROLE.FRAGIL)


@pytest.mark.regra
def test_forte_quando_todas_as_cinco_condicoes_satisfeitas() -> None:
    """Definições §4: as 5 condições (E) satisfeitas classificam FORTE."""
    assertar_exato(derivar_NIVEL_CONTROLE(_PERFIL_FORTE_BASE), NIVEL_CONTROLE.FORTE)


@pytest.mark.regra
def test_parcial_e_o_fallback_dos_demais_casos() -> None:
    """Nem FRAGIL nem FORTE integralmente satisfeito → PARCIAL (default)."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.PARTE,  # não é FRAGIL nem entra em FORTE
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.VARIAS_MES,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.DIAS_DEPOIS,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.MAIORIA,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.QUASE_TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.RAZOAVEL,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.RARAMENTE,
        REVISAO_SEMANAL=REVISAO_SEMANAL.RARAMENTE,
    )
    assertar_exato(derivar_NIVEL_CONTROLE(perfil), NIVEL_CONTROLE.PARCIAL)


@pytest.mark.regra
def test_ordem_de_avaliacao_fragil_vence_forte() -> None:
    """RF-27, Definições §4: ordem obrigatória FRAGIL → FORTE → PARCIAL.

    Perfil satisfaz as 5 condições de FORTE mas também dispara
    `REVISAO_SEMANAL = NUNCA` (uma condição de FRAGIL). Se a ordem fosse
    invertida ou paralela, um bug poderia devolver FORTE; a ordem correta
    devolve FRAGIL, provando que FRAGIL é testado — e vence — primeiro.
    """
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.NUNCA,  # dispara FRAGIL
    )
    assertar_exato(derivar_NIVEL_CONTROLE(perfil), NIVEL_CONTROLE.FRAGIL)


@pytest.mark.regra
def test_forte_falha_por_uma_condicao_ausente_cai_em_parcial() -> None:
    """Definições §4: FORTE exige TODAS as 5 condições (E). Faltando uma
    condição — sem disparar nenhuma de FRAGIL — o resultado é PARCIAL, não
    FORTE."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.VARIAS_MES,  # fora do conjunto de FORTE
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    assertar_exato(derivar_NIVEL_CONTROLE(perfil), NIVEL_CONTROLE.PARCIAL)


# ---------------------------------------------------------------------------
# T-14 — `derivar_CONFIABILIDADE_DADOS` (RF-23, AC-46, Definições §5)
# ---------------------------------------------------------------------------

# Perfil-base cujas 4 variáveis usadas por CONFIABILIDADE_DADOS satisfazem
# integralmente ALTA (Definições §5) — usado como ponto de partida e alterado
# campo a campo pelos testes deste bloco. NIVEL_CONTROLE é passado à parte
# (parâmetro obrigatório da função sob teste), não recalculado do perfil.
_PERFIL_CONFIABILIDADE_ALTA_BASE = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)


@pytest.mark.regra
def test_AC46_fragil_implica_confiabilidade_baixa() -> None:
    """AC-46: `NIVEL_CONTROLE = FRAGIL` ⇒ `CONFIABILIDADE_DADOS = BAIXA` — a
    ordem de avaliação testa BAIXA antes de ALTA. Perfil satisfaz, à parte
    de `nivel_controle`, as três outras condições de BAIXA em NEGATIVO (não
    dispararia BAIXA por si só) para provar que é exclusivamente o
    `NIVEL_CONTROLE = FRAGIL` recebido como parâmetro que decide."""
    resultado = derivar_CONFIABILIDADE_DADOS(
        NIVEL_CONTROLE.FRAGIL, _PERFIL_CONFIABILIDADE_ALTA_BASE
    )
    assertar_exato(resultado, CONFIABILIDADE_DADOS.BAIXA)


@pytest.mark.regra
def test_confiabilidade_baixa_por_defasagem_registro_fim_de_mes() -> None:
    """Definições §5: `DEFASAGEM_REGISTRO ∈ {FIM_MES, SEM_PADRAO}` basta,
    mesmo com `NIVEL_CONTROLE = FORTE` — prova que BAIXA não depende só do
    controle."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.FIM_MES,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    resultado = derivar_CONFIABILIDADE_DADOS(NIVEL_CONTROLE.FORTE, perfil)
    assertar_exato(resultado, CONFIABILIDADE_DADOS.BAIXA)


@pytest.mark.regra
def test_confiabilidade_alta_quando_as_quatro_condicoes_satisfeitas() -> None:
    """Definições §5: `NIVEL_CONTROLE = FORTE` + as 3 condições (E) do Bloco
    2 satisfeitas classificam ALTA."""
    resultado = derivar_CONFIABILIDADE_DADOS(
        NIVEL_CONTROLE.FORTE, _PERFIL_CONFIABILIDADE_ALTA_BASE
    )
    assertar_exato(resultado, CONFIABILIDADE_DADOS.ALTA)


@pytest.mark.regra
def test_confiabilidade_media_e_o_fallback_dos_demais_casos() -> None:
    """Nem BAIXA nem ALTA integralmente satisfeita → MEDIA (default).
    `NIVEL_CONTROLE = PARCIAL` já impede BAIXA (que exige FRAGIL) e ALTA
    (que exige FORTE); as demais variáveis ficam fora dos dois conjuntos de
    condição."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.PARTE,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.VARIAS_MES,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.DIAS_DEPOIS,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.MAIORIA,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.QUASE_TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.RAZOAVEL,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.RARAMENTE,
        REVISAO_SEMANAL=REVISAO_SEMANAL.RARAMENTE,
    )
    resultado = derivar_CONFIABILIDADE_DADOS(NIVEL_CONTROLE.PARCIAL, perfil)
    assertar_exato(resultado, CONFIABILIDADE_DADOS.MEDIA)


@pytest.mark.regra
def test_ordem_de_avaliacao_confiabilidade_baixa_vence_alta() -> None:
    """RF-27, Definições §5: ordem obrigatória BAIXA → ALTA → MEDIA — mesma
    prova estrutural de `test_ordem_de_avaliacao_fragil_vence_forte`, agora
    para CONFIABILIDADE_DADOS. Perfil satisfaz as 3 condições de ALTA mas
    `COBERTURA_MEIOS_PAGAMENTO = NAO_SEI` também dispara uma condição de
    BAIXA. Se BAIXA não fosse testada primeiro, um bug poderia devolver
    ALTA; a ordem correta devolve BAIXA."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.NAO_SEI,  # dispara BAIXA
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    resultado = derivar_CONFIABILIDADE_DADOS(NIVEL_CONTROLE.FORTE, perfil)
    assertar_exato(resultado, CONFIABILIDADE_DADOS.BAIXA)


# ---------------------------------------------------------------------------
# T-19 — `derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` (RF-24, Definições §1)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC34_conjuncao_produz_incompatibilidade() -> None:
    """AC-34: NECESSIDADE_VITORIA=8 + HISTORICO_ABANDONO=SIM + RISCO_RECAIDA
    BAIXO + NIVEL_CONTROLE FORTE ⇒ SIM. Necessidade acima do limiar E um
    sinal comportamental presente (HISTORICO_ABANDONO) — os outros dois
    sinais (RISCO_RECAIDA, NIVEL_CONTROLE) deliberadamente ausentes, para
    provar que basta UM sinal, não os três."""
    sinais = _sinais_comportamentais(
        necessidade_vitoria=8, historico_abandono=SimNaoTalvez.SIM
    )
    resultado = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle=NIVEL_CONTROLE.FORTE,
        risco_recaida=NIVEL_RISCO.BAIXO,
        sinais=sinais,
        parametros=_PARAMETROS,
    )
    assertar_exato(resultado, True)


@pytest.mark.regra
def test_AC35_sinal_isolado_nao_basta() -> None:
    """AC-35: NECESSIDADE_VITORIA=6 + HISTORICO_ABANDONO=SIM ⇒ NAO. O sinal
    comportamental está presente, mas a necessidade de vitória (6) não
    atinge o limiar (7) — o sinal isolado não basta sem a conjunção."""
    sinais = _sinais_comportamentais(
        necessidade_vitoria=6, historico_abandono=SimNaoTalvez.SIM
    )
    resultado = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle=NIVEL_CONTROLE.FORTE,
        risco_recaida=NIVEL_RISCO.BAIXO,
        sinais=sinais,
        parametros=_PARAMETROS,
    )
    assertar_exato(resultado, False)


@pytest.mark.regra
def test_necessidade_alta_sem_nenhum_sinal_comportamental_nao_basta() -> None:
    """Definições §1: NECESSIDADE_VITORIA alta sozinha, sem nenhum dos três
    sinais comportamentais (HISTORICO_ABANDONO=NAO, RISCO_RECAIDA=BAIXO,
    NIVEL_CONTROLE≠FRAGIL) ⇒ NAO — prova o outro lado da conjunção: a
    necessidade de vitória isolada também não basta."""
    sinais = _sinais_comportamentais(
        necessidade_vitoria=10, historico_abandono=SimNaoTalvez.NAO
    )
    resultado = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle=NIVEL_CONTROLE.FORTE,
        risco_recaida=NIVEL_RISCO.BAIXO,
        sinais=sinais,
        parametros=_PARAMETROS,
    )
    assertar_exato(resultado, False)


@pytest.mark.regra
def test_fronteira_necessidade_vitoria_igual_ao_limiar_e_inclusiva() -> None:
    """Definições §1: `>=` é inclusivo. NECESSIDADE_VITORIA exatamente igual
    a `P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA` (lido de
    parameters/parametros-1.0.1.json, não literal) com um sinal
    comportamental presente ⇒ SIM."""
    sinais = _sinais_comportamentais(
        necessidade_vitoria=_LIMIAR_NECESSIDADE_VITORIA,
        historico_abandono=SimNaoTalvez.SIM,
    )
    resultado = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle=NIVEL_CONTROLE.FORTE,
        risco_recaida=NIVEL_RISCO.BAIXO,
        sinais=sinais,
        parametros=_PARAMETROS,
    )
    assertar_exato(resultado, True)


@pytest.mark.regra
def test_fronteira_necessidade_vitoria_um_a_menos_do_limiar_nao_basta() -> None:
    """Fronteira do outro lado: NECESSIDADE_VITORIA um a menos que o limiar
    ⇒ NAO, mesmo com sinal comportamental presente — prova que `>=` não é
    `>` nem arredonda para baixo."""
    sinais = _sinais_comportamentais(
        necessidade_vitoria=_LIMIAR_NECESSIDADE_VITORIA - 1,
        historico_abandono=SimNaoTalvez.SIM,
    )
    resultado = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle=NIVEL_CONTROLE.FORTE,
        risco_recaida=NIVEL_RISCO.BAIXO,
        sinais=sinais,
        parametros=_PARAMETROS,
    )
    assertar_exato(resultado, False)
