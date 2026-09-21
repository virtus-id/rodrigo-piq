"""Testes de `criar_selecionar_alvo_bola_de_neve` — RF-06 · O-04, O-05 ·
AC-02 · T-51.

Cobre:

1. `test_O04_ordena_por_valor_relevante_crescente` — entre duas dívidas
   elegíveis com `VALOR_RELEVANTE_PARA_QUITACAO` diferentes, a de MENOR
   valor relevante é escolhida (não a de menor `SALDO_DEVEDOR_ATUAL` bruto:
   o valor relevante usado é o composto por
   `compor_VALOR_RELEVANTE_PARA_QUITACAO`, que pode divergir do saldo — ver
   `test_O04_usa_valor_relevante_nao_saldo_bruto`).
2. `test_O04_usa_valor_relevante_nao_saldo_bruto` — dívida com
   `VALOR_QUITACAO_HOJE` confirmado e vigente (menor que o saldo bruto de
   outra) vence mesmo quando seu `SALDO_DEVEDOR_ATUAL` bruto é maior que o
   da concorrente — prova de que a ordenação usa
   `VALOR_RELEVANTE_PARA_QUITACAO`, não `SALDO_DEVEDOR_ATUAL` direto.
3. `test_O05_nivel1_maior_valor_fluxo_liberado` — valor relevante empatado:
   desempate pelo maior `VALOR_FLUXO_LIBERADO` (lido como
   `PAGAMENTO_MENSAL_EFETIVO`, ver docstring do módulo).
4. `test_O05_nivel2_maior_custo_financeiro` — nível 1 também empatado:
   desempate pelo maior custo financeiro (`TAXA_EFETIVA_MENSAL_NORMALIZADA`).
5. `test_O05_nivel3_maior_peso_emocional` — níveis 1 e 2 também empatados:
   desempate pelo maior `PESO_EMOCIONAL`.
6. `test_O05_nivel4_desempate_final_por_divida_id` — todos os níveis
   anteriores empatados: `DIVIDA_ID` decide, de forma estável.
7. `test_desconhecido_vai_para_informacao_pendente` — dívida com
   `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` não entra na ordenação
   normal (não é escolhida mesmo sendo a única "candidata" restante).
8. `test_devolve_none_sem_divida_elegivel` — carteira vazia e carteira
   inteiramente quitada devolvem `None`, sem levantar exceção.
9. `test_O04_alvo_fixo_devolvido_sem_recalcular` — com
   `EstadoSimulacao.DIVIDA_ALVO_ATUAL` apontando para uma dívida ainda não
   quitada, a função devolve essa mesma dívida mesmo que outra tivesse
   valor relevante menor.
10. `test_integracao_minima_via_simular_cenario` — a fábrica usada como
    `sel` de `simular_cenario` (T-46) produz um cenário coerente: a dívida
    de menor valor relevante é atacada primeiro.

`_divida` segue o padrão de `tests/regras/test_avalanche.py::_divida` —
`QUITACAO_CONSULTADA=SIM`/`STATUS_VALIDADE_PROPOSTA=VIGENTE` para que
`VALOR_RELEVANTE_PARA_QUITACAO` seja determinístico (`= SALDO_DEVEDOR_ATUAL`
quando igual a `VALOR_QUITACAO_HOJE`, sem cair no fallback de §11.2).

REGRAS: RF-06, O-04, O-05, AC-02, §5.2, §11.2
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import TIPO_DIVIDA, Divida, EstadoFinanceiro
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
    """Mesmo padrão de `test_avalanche.py::_divida` — dívida completa e
    válida, `VALOR_RELEVANTE_PARA_QUITACAO` determinístico
    (`QUITACAO_CONSULTADA=SIM`, `STATUS_VALIDADE_PROPOSTA=VIGENTE`,
    `VALOR_QUITACAO_HOJE == SALDO_DEVEDOR_ATUAL`)."""
    base: dict[str, object] = dict(
        DIVIDA_ID="D-01",
        TIPO_DIVIDA=TIPO_DIVIDA.CONSIGNADO,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        CET=Decimal("0.05"),
        PARCELA_CONTRATUAL=dinheiro("600"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("600"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
    base.update(overrides)
    return Divida(**base)  # type: ignore[arg-type]


def _estado(
    *,
    saldos: dict[str, Decimal],
    quitadas: frozenset[str] = frozenset(),
    alvo: str | None = None,
) -> EstadoSimulacao:
    return EstadoSimulacao(
        mes=1,
        saldos=saldos,
        quitadas=quitadas,
        DIVIDA_ALVO_ATUAL=alvo,
        CAPACIDADE_ATAQUE_M=dinheiro("100"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )


@pytest.mark.regra
def test_O04_ordena_por_valor_relevante_crescente() -> None:
    """`O-04`: entre duas dívidas elegíveis, a Bola de Neve escolhe a de
    MENOR `VALOR_RELEVANTE_PARA_QUITACAO` — D-PEQUENA tem saldo bem menor
    que D-GRANDE."""
    d_pequena = _divida(
        DIVIDA_ID="D-PEQUENA",
        SALDO_DEVEDOR_ATUAL=dinheiro("200"),
        VALOR_QUITACAO_HOJE=dinheiro("200"),
    )
    d_grande = _divida(
        DIVIDA_ID="D-GRANDE",
        SALDO_DEVEDOR_ATUAL=dinheiro("5000"),
        VALOR_QUITACAO_HOJE=dinheiro("5000"),
    )
    dividas = {"D-GRANDE": d_grande, "D-PEQUENA": d_pequena}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-GRANDE": dinheiro("5000"), "D-PEQUENA": dinheiro("200")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-PEQUENA")


@pytest.mark.regra
def test_O04_usa_valor_relevante_nao_saldo_bruto() -> None:
    """Critério de aceite 1: a ordenação usa `VALOR_RELEVANTE_PARA_QUITACAO`
    (via `compor_VALOR_RELEVANTE_PARA_QUITACAO`), nunca `SALDO_DEVEDOR_ATUAL`
    direto. D-PROPOSTA tem saldo bruto MAIOR que D-SEM-PROPOSTA, mas uma
    quitação à vista confirmada e vigente bem menor — o valor RELEVANTE é
    menor, então D-PROPOSTA deve vencer, invertendo a ordem que o saldo
    bruto sozinho produziria."""
    d_proposta = _divida(
        DIVIDA_ID="D-PROPOSTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("9000"),  # saldo bruto MAIOR
        VALOR_QUITACAO_HOJE=dinheiro("300"),  # valor relevante MENOR (confirmado e vigente)
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
    )
    d_sem_proposta = _divida(
        DIVIDA_ID="D-SEM-PROPOSTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),  # saldo bruto menor, mas é o valor relevante aqui
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,  # sem quitação confirmada — cai no fallback (saldo)
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    dividas = {"D-PROPOSTA": d_proposta, "D-SEM-PROPOSTA": d_sem_proposta}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-PROPOSTA": dinheiro("9000"), "D-SEM-PROPOSTA": dinheiro("1000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    # D-PROPOSTA vence: valor relevante 300 < 1000, mesmo com saldo bruto
    # 9000 > 1000 — prova de que a ordenação não usa SALDO_DEVEDOR_ATUAL.
    assertar_exato(escolhido.DIVIDA_ID, "D-PROPOSTA")


@pytest.mark.regra
def test_O05_nivel1_maior_valor_fluxo_liberado() -> None:
    """`O-05`, nível 1: valor relevante EMPATADO (mesmo saldo) — desempate
    pelo maior `VALOR_FLUXO_LIBERADO` (lido como `PAGAMENTO_MENSAL_EFETIVO`,
    ver docstring de `engine/metodos/bola_de_neve.py`). D-LIBERA-MAIS tem
    pagamento mensal maior — vence o desempate."""
    comuns = dict(SALDO_DEVEDOR_ATUAL=dinheiro("1000"), VALOR_QUITACAO_HOJE=dinheiro("1000"))
    d_libera_mais = _divida(
        DIVIDA_ID="D-LIBERA-MAIS", PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"), **comuns
    )
    d_libera_menos = _divida(
        DIVIDA_ID="D-LIBERA-MENOS", PAGAMENTO_MENSAL_EFETIVO=dinheiro("100"), **comuns
    )
    dividas = {"D-LIBERA-MENOS": d_libera_menos, "D-LIBERA-MAIS": d_libera_mais}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-LIBERA-MENOS": dinheiro("1000"), "D-LIBERA-MAIS": dinheiro("1000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-LIBERA-MAIS")


@pytest.mark.regra
def test_O05_nivel2_maior_custo_financeiro() -> None:
    """`O-05`, nível 2: valor relevante E `VALOR_FLUXO_LIBERADO` (nível 1)
    empatados — desempate pelo maior custo financeiro
    (`TAXA_EFETIVA_MENSAL_NORMALIZADA`, ver docstring do módulo).
    D-TAXA-ALTA tem taxa maior — vence o desempate."""
    comuns = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("300"),  # nível 1 empatado
    )
    d_taxa_alta = _divida(
        DIVIDA_ID="D-TAXA-ALTA", TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.10"), **comuns
    )
    d_taxa_baixa = _divida(
        DIVIDA_ID="D-TAXA-BAIXA", TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.02"), **comuns
    )
    dividas = {"D-TAXA-BAIXA": d_taxa_baixa, "D-TAXA-ALTA": d_taxa_alta}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-TAXA-BAIXA": dinheiro("1000"), "D-TAXA-ALTA": dinheiro("1000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-TAXA-ALTA")


@pytest.mark.regra
def test_O05_nivel3_maior_peso_emocional() -> None:
    """`O-05`, nível 3: valor relevante, `VALOR_FLUXO_LIBERADO` (nível 1) e
    custo financeiro (nível 2) todos empatados — desempate pelo maior
    `PESO_EMOCIONAL`. D-PESO-ALTO tem peso emocional maior — vence."""
    comuns = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("300"),  # nível 1 empatado
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),  # nível 2 empatado
    )
    d_peso_alto = _divida(DIVIDA_ID="D-PESO-ALTO", PESO_EMOCIONAL=9, **comuns)
    d_peso_baixo = _divida(DIVIDA_ID="D-PESO-BAIXO", PESO_EMOCIONAL=1, **comuns)
    dividas = {"D-PESO-BAIXO": d_peso_baixo, "D-PESO-ALTO": d_peso_alto}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-PESO-BAIXO": dinheiro("1000"), "D-PESO-ALTO": dinheiro("1000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-PESO-ALTO")


@pytest.mark.regra
def test_O05_nivel4_desempate_final_por_divida_id() -> None:
    """`O-05`, nível 4/critério de aceite 3: valor relevante,
    `VALOR_FLUXO_LIBERADO`, custo financeiro E `PESO_EMOCIONAL` TODOS
    empatados — `DIVIDA_ID` é o desempate técnico final e garante
    determinismo total. "D-A" < "D-B" ⇒ "D-A" escolhida, independentemente
    da ordem de inserção no dicionário."""
    comuns = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("300"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        PESO_EMOCIONAL=5,
    )
    d_b = _divida(DIVIDA_ID="D-B", **comuns)
    d_a = _divida(DIVIDA_ID="D-A", **comuns)
    # Inserção proposital em ordem "errada" (D-B antes de D-A) — a função
    # não pode depender da ordem de iteração do dict para desempatar.
    dividas = {"D-B": d_b, "D-A": d_a}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(saldos={"D-B": dinheiro("1000"), "D-A": dinheiro("1000")}, alvo=None)
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-A")


@pytest.mark.regra
def test_desconhecido_vai_para_informacao_pendente() -> None:
    """Critério de aceite 4: dívida com `VALOR_RELEVANTE_PARA_QUITACAO`
    `DESCONHECIDO` NÃO entra na ordenação normal. D-DESCONHECIDA tem
    `SALDO_DEVEDOR_ATUAL = DESCONHECIDO` e nenhuma quitação confirmada
    vigente — `compor_VALOR_RELEVANTE_PARA_QUITACAO` devolve `DESCONHECIDO`
    (AC-21). Mesmo sendo a "melhor" candidata em qualquer outro critério, ela
    nunca é escolhida; D-CONHECIDA (a única com valor relevante) é."""
    d_desconhecida = _divida(
        DIVIDA_ID="D-DESCONHECIDA",
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
    )
    d_conhecida = _divida(
        DIVIDA_ID="D-CONHECIDA",
        SALDO_DEVEDOR_ATUAL=dinheiro("5000"),
        VALOR_QUITACAO_HOJE=dinheiro("5000"),
    )
    dividas = {"D-DESCONHECIDA": d_desconhecida, "D-CONHECIDA": d_conhecida}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-DESCONHECIDA": dinheiro("0"), "D-CONHECIDA": dinheiro("5000")}, alvo=None
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-CONHECIDA")

    # Com SOMENTE a dívida DESCONHECIDA elegível, não há candidata alguma
    # para O-04 — a função devolve None, nunca inventa uma escolha.
    sel_so_desconhecida = criar_selecionar_alvo_bola_de_neve(
        {"D-DESCONHECIDA": d_desconhecida}, _parametros_reais()
    )
    estado_so_desconhecida = _estado(saldos={"D-DESCONHECIDA": dinheiro("0")}, alvo=None)
    assertar_exato(sel_so_desconhecida(estado_so_desconhecida, dinheiro("100")), None)


@pytest.mark.regra
def test_devolve_none_sem_divida_elegivel() -> None:
    """Sem candidata elegível — carteira vazia OU todas quitadas — `sel`
    devolve `None`, nunca levanta exceção."""
    d1 = _divida(DIVIDA_ID="D-01")
    parametros = _parametros_reais()

    sel_vazia = criar_selecionar_alvo_bola_de_neve({}, parametros)
    estado_vazio = _estado(saldos={}, alvo=None)
    assertar_exato(sel_vazia(estado_vazio, dinheiro("100")), None)

    sel_quitada = criar_selecionar_alvo_bola_de_neve({"D-01": d1}, parametros)
    estado_quitado = _estado(
        saldos={"D-01": dinheiro("0")}, quitadas=frozenset({"D-01"}), alvo=None
    )
    assertar_exato(sel_quitada(estado_quitado, dinheiro("100")), None)


@pytest.mark.regra
def test_O04_alvo_fixo_devolvido_sem_recalcular(monkeypatch: pytest.MonkeyPatch) -> None:
    """`O-04` (alvo fixo até quitação ou evento): com `DIVIDA_ALVO_ATUAL`
    apontando para uma dívida ainda não quitada, a função devolve essa mesma
    dívida sem recalcular a ordenação — mesmo que outra candidata tivesse
    valor relevante menor. Prova reforçada com monkeypatch: se
    `compor_VALOR_RELEVANTE_PARA_QUITACAO` fosse chamada, o teste falharia."""
    import engine.metodos.bola_de_neve as bola_de_neve_mod

    def _falha_se_chamado(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "compor_VALOR_RELEVANTE_PARA_QUITACAO não deveria ser chamada quando "
            "o alvo corrente ainda é elegível (O-04: alvo fixo)."
        )

    monkeypatch.setattr(
        bola_de_neve_mod, "compor_VALOR_RELEVANTE_PARA_QUITACAO", _falha_se_chamado
    )

    d_alvo = _divida(
        DIVIDA_ID="D-ALVO",
        SALDO_DEVEDOR_ATUAL=dinheiro("5000"),  # valor relevante alto
        VALOR_QUITACAO_HOJE=dinheiro("5000"),
    )
    d_melhor = _divida(
        DIVIDA_ID="D-MELHOR",
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),  # valor relevante bem menor
        VALOR_QUITACAO_HOJE=dinheiro("50"),
    )
    dividas = {"D-ALVO": d_alvo, "D-MELHOR": d_melhor}
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())

    estado = _estado(
        saldos={"D-ALVO": dinheiro("5000"), "D-MELHOR": dinheiro("50")},
        alvo="D-ALVO",
    )
    escolhido = sel(estado, dinheiro("100"))

    assert escolhido is not None
    assertar_exato(escolhido.DIVIDA_ID, "D-ALVO")


@pytest.mark.regra
def test_integracao_minima_via_simular_cenario() -> None:
    """Integração mínima: a fábrica usada como `sel` de `simular_cenario`
    (T-46) ataca primeiro a dívida de MENOR valor relevante — `ORDEM_
    QUITACAO` reflete essa prioridade (`O-04`)."""
    d_pequena = _divida(
        DIVIDA_ID="D-PEQUENA",
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_grande = _divida(
        DIVIDA_ID="D-GRANDE",
        SALDO_DEVEDOR_ATUAL=dinheiro("900"),
        VALOR_QUITACAO_HOJE=dinheiro("900"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-GRANDE": d_grande, "D-PEQUENA": d_pequena}
    parametros = _parametros_reais()
    sel = criar_selecionar_alvo_bola_de_neve(dividas, parametros)

    classificacao_neutra = ClassificacaoRisco(sinais=(), contagem=0, nivel=NIVEL_RISCO.BAIXO)
    dg = Diagnostico(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=dinheiro("0"),
        PAGAMENTOS_EFETIVOS_DIVIDAS=dinheiro("0"),
        RESULTADO_CAIXA_OBSERVADO=dinheiro("0"),
        RESULTADO_MENSAL_ATUAL=dinheiro("0"),
        GAP_CAIXA_VS_ESTRUTURAL=dinheiro("0"),
        DEFICIT_MENSAL=dinheiro("0"),
        PISO_CAPACIDADE=dinheiro("0"),
        STATUS_FINANCEIRO=STATUS_FINANCEIRO.CAPACIDADE_POSITIVA,
        MODO_ESTABILIZACAO=False,
        GAP_AUTOPERCEPCAO=False,
        BASE_CONSERVADORA=dinheiro("100"),
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=dinheiro("100"),
        CAPACIDADE_ATAQUE_CONSERVADORA=dinheiro("100"),
        CAPACIDADE_ATAQUE_POTENCIAL=dinheiro("100"),
        NIVEL_CONTROLE=NIVEL_CONTROLE.FORTE,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=False,
        classificacao_risco_recaida=classificacao_neutra,
        classificacao_risco_comportamental_geral=classificacao_neutra,
        # T-90/OQ-23: contrato de tipo/posição, sem valor de negócio real.
        RESERVA_MOBILIZAVEL=dinheiro("0"),
        ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("0"),
    )

    from engine.estado import (
        COBERTURA_MEIOS_PAGAMENTO,
        COBERTURA_PEQUENOS_GASTOS,
        CONHECIMENTO_GASTO,
        DEFASAGEM_REGISTRO,
        DISPOSICAO_USO_RESERVA,
        FREQUENCIA_REGISTRO,
        GASTOS_NAO_IDENTIFICADOS,
        REGISTRO_GASTOS,
        RESERVA_EXISTE,
        REVISAO_SEMANAL,
        PerfilComportamental,
        SinaisComportamentais,
    )
    from engine.estado import TIPO_RENDA as _TIPO_RENDA

    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    sinais = SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
        MECANISMO_DEFICIT=frozenset(),
        HISTORICO_RECAIDA=SimNaoTalvez.NAO,
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
        PACTO="ESTABELECIDO",
        RISCO_IMPULSO="NENHUMA",
        LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
        NECESSIDADE_VITORIA=0,
        HISTORICO_ABANDONO=SimNaoTalvez.NAO,
        JANELA_NOVA_DIVIDA=None,
    )
    e = EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 1, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("0"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("0"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("0"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("0"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(),
        perfil_comportamental=perfil,
        sinais_comportamentais=sinais,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=0,
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro("0"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro("0"),
        DINHEIRO_DISPONIVEL=dinheiro("0"),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )

    cenario = simular_cenario(e, dg, dividas, sel, parametros)

    # D-PEQUENA (menor VALOR_RELEVANTE_PARA_QUITACAO) é atacada primeiro e
    # quita antes de D-GRANDE — a Bola de Neve prioriza a menor dívida.
    assertar_exato(cenario.ORDEM_QUITACAO[0], "D-PEQUENA")
    assertar_exato(set(cenario.ORDEM_QUITACAO), {"D-PEQUENA", "D-GRANDE"})
