"""Teste de integração fim a fim da cadeia de desempate de `H-04` — RF-07 ·
H-04 · AC-03 · T-55.

`test_H04_desempate_lexicografico_seis_niveis` exercita os SEIS níveis da
Etapa 4 (`H-04`, `engine/metodos/hibrido.py::_chave_desempate_H04`), nesta
ordem EXATA (lida diretamente da docstring/assinatura daquela função):

```
1. menor MESES_PRIMEIRA_VITORIA
2. menor PENALIDADE_CUSTO_VS_AVALANCHE
3. maior VALOR_FLUXO_LIBERADO
4. maior PESO_EMOCIONAL
5. maior BENEFICIO_MARGINAL_AMORTIZACAO
6. menor DIVIDA_ID
```

Mesmo espírito de `tests/regras/test_bola_de_neve.py::test_O05_nivel1_maior_
valor_fluxo_liberado`..`test_O05_nivel4_desempate_final_por_divida_id` (T-52)
— uma cascata de empates parciais em que cada par de candidatas empata em
TODOS os níveis anteriores e diverge exatamente no nível sob teste — mas
reunida em um único teste (conforme o nome pedido pela tarefa), com SEIS
sub-casos internos em vez de seis testes separados, porque o Híbrido não tem
uma única chamada testável por nível como a Bola de Neve (`criar_selecionar_
alvo_bola_de_neve` reordena instantaneamente): aqui cada nível exige uma
carteira e uma chamada a `escolher_D_ESTRELA` própria (Etapas 1-4 completas,
`H-01`..`H-04`, via `simular_cenario` internamente), porque `MESES_PRIMEIRA_
VITORIA`/`PENALIDADE_CUSTO_VS_AVALANCHE`/`ATRASO_PRAZO_VS_AVALANCHE` (níveis
1/2, mais a tolerância de `H-03`) só emergem de uma simulação completa de
`CENARIO_HIBRIDO_D`, não são atributos diretos de `Divida` como os campos que
decidem os níveis 3-6 do desempate de `O-05` (Bola de Neve).

**Por que os seis sub-casos usam carteiras diferentes, não uma cascata
única.** Uma única carteira com sete candidatas empatando nível a nível (como
`test_hibrido.py::test_H04_desempate_seis_niveis`, T-53) prova que os campos
de desempate TÉCNICO (níveis 3-6, atributos diretos de `Divida`) resolvem na
ordem certa, mas não isola os níveis 1/2 de forma determinística: `MESES_
PRIMEIRA_VITORIA` e `PENALIDADE_CUSTO_VS_AVALANCHE` emergem do MESMO par de
simulações (`CENARIO_HIBRIDO_D` vs `ORDEM_AVALANCHE`) e são fortemente
acoplados — mudar o saldo de uma candidata para adiar sua primeira vitória
também desloca sua penalidade de custo, então "isolar" cada nível nessa dupla
exige controlar a MAGNITUDE da diferença (não apenas a direção) para manter
os dois valores dentro das tolerâncias cumulativas de `H-03` sem que o nível 2
"vaze" para dentro do nível 1 ou vice-versa. Cada sub-caso abaixo foi
calibrado numericamente (saldo/capacidade) para produzir exatamente esse
empate parcial controlado — ver comentário de cada bloco.

REGRAS: RF-07, H-01, H-02, H-03, H-04, AC-03
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engine.diagnostico import Diagnostico
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
    TIPO_DIVIDA,
    TIPO_RENDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.metodos.hibrido import escolher_D_ESTRELA
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato

# Mesmo padrão de `_divida`/`_diagnostico_minimo`/`_estado_financeiro_minimo`
# de `tests/regras/test_hibrido.py` — reaproveitado aqui em vez de importado
# (helpers privados de módulo de teste não são API compartilhável entre
# arquivos de teste, mesma convenção já usada por `test_avalanche.py`/
# `test_bola_de_neve.py`, cada um com sua própria cópia local).


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
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


def _diagnostico_minimo(*, capacidade: Decimal) -> Diagnostico:
    classificacao_neutra = ClassificacaoRisco(sinais=(), contagem=0, nivel=NIVEL_RISCO.BAIXO)
    return Diagnostico(
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
        BASE_CONSERVADORA=capacidade,
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=capacidade,
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidade,
        CAPACIDADE_ATAQUE_POTENCIAL=capacidade,
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


def _estado_financeiro_minimo() -> EstadoFinanceiro:
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
    return EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 1, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("0"),
        TIPO_RENDA=TIPO_RENDA.FIXA,
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


def _d_ref() -> Divida:
    """A "primeira da Avalanche" comum a todos os sub-casos: taxa altíssima
    e saldo pequeno garantem que ela sempre vence a Avalanche de referência
    (`H-01`) e, por isso, NUNCA é candidata (`H-02`: "diferente da primeira
    da Avalanche") — mantém as carteiras de cada nível concentradas apenas
    nas duas candidatas que de fato disputam aquele nível.
    """
    return _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("10"),
        VALOR_QUITACAO_HOJE=dinheiro("10"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.90"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )


@pytest.mark.regra
def test_H04_desempate_lexicografico_seis_niveis() -> None:
    """`H-04`: os seis níveis de desempate, cada um decidido isoladamente por
    um par de candidatas empatadas em TODOS os níveis anteriores — cascata
    completa até o último nível (`DIVIDA_ID`), na ordem exata de `_chave_
    desempate_H04`.
    """
    e = _estado_financeiro_minimo()
    p = _parametros_reais()
    d_ref = _d_ref()

    # --- Nível 1: menor MESES_PRIMEIRA_VITORIA -----------------------------
    # C-N1-RAPIDA quita em 1 mês, C-N1-LENTA em 2 — ambas sobrevivem às três
    # tolerâncias de H-03 (penalidade/atraso ficam iguais entre as duas,
    # porque o "resto" simulado depois de cada uma é o mesmo D-REF), então o
    # desempate cai inteiramente no nível 1.
    c_n1_rapida = _divida(
        DIVIDA_ID="C-N1-RAPIDA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    c_n1_lenta = _divida(
        DIVIDA_ID="C-N1-LENTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1200"),
        VALOR_QUITACAO_HOJE=dinheiro("1200"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas_n1 = {"D-REF": d_ref, "C-N1-RAPIDA": c_n1_rapida, "C-N1-LENTA": c_n1_lenta}
    dg_n1 = _diagnostico_minimo(capacidade=dinheiro("1000"))
    d_estrela_n1, metricas_n1 = escolher_D_ESTRELA(e, dividas_n1, dg_n1, p)

    assertar_exato(d_estrela_n1, "C-N1-RAPIDA")
    metricas_por_id_n1 = {m.DIVIDA_ID: m for m in metricas_n1}
    assertar_exato(metricas_por_id_n1["C-N1-RAPIDA"].MESES_PRIMEIRA_VITORIA, 1)
    assertar_exato(metricas_por_id_n1["C-N1-LENTA"].MESES_PRIMEIRA_VITORIA, 2)
    # Pré-condição do sub-caso: níveis 2 e 3+ realmente empatados entre as
    # duas — senão o nível 1 não seria o que decide de fato.
    assertar_exato(
        metricas_por_id_n1["C-N1-RAPIDA"].PENALIDADE_CUSTO_VS_AVALANCHE,
        metricas_por_id_n1["C-N1-LENTA"].PENALIDADE_CUSTO_VS_AVALANCHE,
    )

    # --- Nível 2: MESES empatado (ambas em 1 mês) — menor PENALIDADE_CUSTO_
    # VS_AVALANCHE decide -----------------------------------------------
    # D-RESTO permanece na carteira como a dívida "restante" simulada por
    # cada CENARIO_HIBRIDO_D depois que a candidata quita — sua taxa alta é
    # o que faz a penalidade de custo divergir entre C-N2-MENOR (consome
    # menos capacidade, sobra mais para atacar D-RESTO mais cedo) e
    # C-N2-MAIOR (consome quase toda a capacidade, deixa D-RESTO acumular
    # mais juros) — ambas ainda dentro do teto de 5% (H-03).
    d_resto = _divida(
        DIVIDA_ID="D-RESTO",
        SALDO_DEVEDOR_ATUAL=dinheiro("2000"),
        VALOR_QUITACAO_HOJE=dinheiro("2000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.08"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("50"),
    )
    c_n2_menor = _divida(
        DIVIDA_ID="C-N2-MENOR",
        SALDO_DEVEDOR_ATUAL=dinheiro("200"),
        VALOR_QUITACAO_HOJE=dinheiro("200"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    c_n2_maior = _divida(
        DIVIDA_ID="C-N2-MAIOR",
        SALDO_DEVEDOR_ATUAL=dinheiro("350"),
        VALOR_QUITACAO_HOJE=dinheiro("350"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas_n2 = {
        "D-REF": d_ref,
        "D-RESTO": d_resto,
        "C-N2-MENOR": c_n2_menor,
        "C-N2-MAIOR": c_n2_maior,
    }
    dg_n2 = _diagnostico_minimo(capacidade=dinheiro("500"))
    d_estrela_n2, metricas_n2 = escolher_D_ESTRELA(e, dividas_n2, dg_n2, p)

    assertar_exato(d_estrela_n2, "C-N2-MENOR")
    metricas_por_id_n2 = {m.DIVIDA_ID: m for m in metricas_n2}
    assertar_exato(metricas_por_id_n2["C-N2-MENOR"].MESES_PRIMEIRA_VITORIA, 1)
    assertar_exato(metricas_por_id_n2["C-N2-MAIOR"].MESES_PRIMEIRA_VITORIA, 1)
    assert (
        metricas_por_id_n2["C-N2-MENOR"].PENALIDADE_CUSTO_VS_AVALANCHE
        < metricas_por_id_n2["C-N2-MAIOR"].PENALIDADE_CUSTO_VS_AVALANCHE
    ), "pré-condição do sub-caso: MENOR precisa ter penalidade estritamente menor"

    # --- Nível 3: MESES e PENALIDADE empatados — maior VALOR_FLUXO_LIBERADO
    # decide ----------------------------------------------------------------
    # Mesmo saldo/quitação/taxa (0, sem juros) entre as duas candidatas —
    # MESES_PRIMEIRA_VITORIA e PENALIDADE_CUSTO_VS_AVALANCHE saem idênticos
    # por construção; só o PAGAMENTO_MENSAL_EFETIVO (lido como VALOR_FLUXO_
    # LIBERADO, ver docstring de hibrido.py) diverge.
    comuns_n3 = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
    )
    c_n3_baixo = _divida(
        DIVIDA_ID="C-N3-BAIXO", PAGAMENTO_MENSAL_EFETIVO=dinheiro("10"), **comuns_n3
    )
    c_n3_alto = _divida(
        DIVIDA_ID="C-N3-ALTO", PAGAMENTO_MENSAL_EFETIVO=dinheiro("80"), **comuns_n3
    )
    dividas_n3 = {"D-REF": d_ref, "C-N3-BAIXO": c_n3_baixo, "C-N3-ALTO": c_n3_alto}
    dg_n3 = _diagnostico_minimo(capacidade=dinheiro("200"))
    d_estrela_n3, metricas_n3 = escolher_D_ESTRELA(e, dividas_n3, dg_n3, p)

    assertar_exato(d_estrela_n3, "C-N3-ALTO")
    metricas_por_id_n3 = {m.DIVIDA_ID: m for m in metricas_n3}
    assertar_exato(
        metricas_por_id_n3["C-N3-BAIXO"].MESES_PRIMEIRA_VITORIA,
        metricas_por_id_n3["C-N3-ALTO"].MESES_PRIMEIRA_VITORIA,
    )
    assertar_exato(
        metricas_por_id_n3["C-N3-BAIXO"].PENALIDADE_CUSTO_VS_AVALANCHE,
        metricas_por_id_n3["C-N3-ALTO"].PENALIDADE_CUSTO_VS_AVALANCHE,
    )
    assertar_exato(metricas_por_id_n3["C-N3-ALTO"].VALOR_FLUXO_LIBERADO, dinheiro("80"))
    assertar_exato(metricas_por_id_n3["C-N3-BAIXO"].VALOR_FLUXO_LIBERADO, dinheiro("10"))

    # --- Nível 4: MESES, PENALIDADE e VALOR_FLUXO_LIBERADO empatados — maior
    # PESO_EMOCIONAL decide ---------------------------------------------
    comuns_n4 = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("50"),
    )
    c_n4_baixo = _divida(DIVIDA_ID="C-N4-BAIXO", PESO_EMOCIONAL=1, **comuns_n4)
    c_n4_alto = _divida(DIVIDA_ID="C-N4-ALTO", PESO_EMOCIONAL=9, **comuns_n4)
    dividas_n4 = {"D-REF": d_ref, "C-N4-BAIXO": c_n4_baixo, "C-N4-ALTO": c_n4_alto}
    dg_n4 = _diagnostico_minimo(capacidade=dinheiro("200"))
    d_estrela_n4, metricas_n4 = escolher_D_ESTRELA(e, dividas_n4, dg_n4, p)

    assertar_exato(d_estrela_n4, "C-N4-ALTO")
    metricas_por_id_n4 = {m.DIVIDA_ID: m for m in metricas_n4}
    assertar_exato(
        metricas_por_id_n4["C-N4-BAIXO"].VALOR_FLUXO_LIBERADO,
        metricas_por_id_n4["C-N4-ALTO"].VALOR_FLUXO_LIBERADO,
    )
    assertar_exato(metricas_por_id_n4["C-N4-ALTO"].PESO_EMOCIONAL, 9)
    assertar_exato(metricas_por_id_n4["C-N4-BAIXO"].PESO_EMOCIONAL, 1)

    # --- Nível 5: MESES, PENALIDADE, VALOR_FLUXO_LIBERADO e PESO_EMOCIONAL
    # empatados — maior BENEFICIO_MARGINAL_AMORTIZACAO decide -----------
    # Saldo pequeno frente à capacidade garante MESES_PRIMEIRA_VITORIA=1 para
    # as duas mesmo com taxas diferentes (0,01 vs 0,02) — a taxa maior gera
    # mais economia de juros evitados (maior benefício marginal), mas a
    # penalidade de custo continua desprezível o suficiente para empatar
    # (ambas convergem para 0 dentro da precisão do motor).
    comuns_n5 = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("50"),
        PESO_EMOCIONAL=5,
    )
    c_n5_baixo = _divida(
        DIVIDA_ID="C-N5-BAIXO", TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"), **comuns_n5
    )
    c_n5_alto = _divida(
        DIVIDA_ID="C-N5-ALTO", TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.02"), **comuns_n5
    )
    dividas_n5 = {"D-REF": d_ref, "C-N5-BAIXO": c_n5_baixo, "C-N5-ALTO": c_n5_alto}
    dg_n5 = _diagnostico_minimo(capacidade=dinheiro("1000"))
    d_estrela_n5, metricas_n5 = escolher_D_ESTRELA(e, dividas_n5, dg_n5, p)

    assertar_exato(d_estrela_n5, "C-N5-ALTO")
    metricas_por_id_n5 = {m.DIVIDA_ID: m for m in metricas_n5}
    assertar_exato(
        metricas_por_id_n5["C-N5-BAIXO"].MESES_PRIMEIRA_VITORIA,
        metricas_por_id_n5["C-N5-ALTO"].MESES_PRIMEIRA_VITORIA,
    )
    assertar_exato(
        metricas_por_id_n5["C-N5-BAIXO"].PENALIDADE_CUSTO_VS_AVALANCHE,
        metricas_por_id_n5["C-N5-ALTO"].PENALIDADE_CUSTO_VS_AVALANCHE,
    )
    assertar_exato(
        metricas_por_id_n5["C-N5-BAIXO"].VALOR_FLUXO_LIBERADO,
        metricas_por_id_n5["C-N5-ALTO"].VALOR_FLUXO_LIBERADO,
    )
    assertar_exato(
        metricas_por_id_n5["C-N5-BAIXO"].PESO_EMOCIONAL,
        metricas_por_id_n5["C-N5-ALTO"].PESO_EMOCIONAL,
    )
    assert (
        metricas_por_id_n5["C-N5-ALTO"].BENEFICIO_MARGINAL_AMORTIZACAO
        > metricas_por_id_n5["C-N5-BAIXO"].BENEFICIO_MARGINAL_AMORTIZACAO
    ), "pré-condição do sub-caso: ALTO precisa ter benefício marginal estritamente maior"

    # --- Nível 6: TODOS os cinco níveis anteriores empatados — menor
    # DIVIDA_ID é o desempate técnico final ------------------------------
    comuns_n6 = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("50"),
        PESO_EMOCIONAL=5,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),
    )
    # Inserção proposital em ordem "errada" (C-N6-B antes de C-N6-A) — a
    # função não pode depender da ordem de iteração do dict (mesma
    # verificação de `test_O05_nivel4_desempate_final_por_divida_id`, T-52).
    c_n6_b = _divida(DIVIDA_ID="C-N6-B", **comuns_n6)
    c_n6_a = _divida(DIVIDA_ID="C-N6-A", **comuns_n6)
    dividas_n6 = {"D-REF": d_ref, "C-N6-B": c_n6_b, "C-N6-A": c_n6_a}
    dg_n6 = _diagnostico_minimo(capacidade=dinheiro("1000"))
    d_estrela_n6, metricas_n6 = escolher_D_ESTRELA(e, dividas_n6, dg_n6, p)

    assertar_exato(d_estrela_n6, "C-N6-A")
    metricas_por_id_n6 = {m.DIVIDA_ID: m for m in metricas_n6}
    assertar_exato(
        metricas_por_id_n6["C-N6-A"].MESES_PRIMEIRA_VITORIA,
        metricas_por_id_n6["C-N6-B"].MESES_PRIMEIRA_VITORIA,
    )
    assertar_exato(
        metricas_por_id_n6["C-N6-A"].PENALIDADE_CUSTO_VS_AVALANCHE,
        metricas_por_id_n6["C-N6-B"].PENALIDADE_CUSTO_VS_AVALANCHE,
    )
    assertar_exato(
        metricas_por_id_n6["C-N6-A"].VALOR_FLUXO_LIBERADO,
        metricas_por_id_n6["C-N6-B"].VALOR_FLUXO_LIBERADO,
    )
    assertar_exato(
        metricas_por_id_n6["C-N6-A"].PESO_EMOCIONAL, metricas_por_id_n6["C-N6-B"].PESO_EMOCIONAL
    )
    assertar_exato(
        metricas_por_id_n6["C-N6-A"].BENEFICIO_MARGINAL_AMORTIZACAO,
        metricas_por_id_n6["C-N6-B"].BENEFICIO_MARGINAL_AMORTIZACAO,
    )
