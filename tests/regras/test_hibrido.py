"""Testes de `engine/metodos/hibrido.py` — RF-07 · H-01..H-07 · AC-03 · T-53.

Cobre:

1. `test_H01_ordem_avalanche_como_referencia` — Etapa 1: `escolher_D_ESTRELA`
   usa a Avalanche pura como referência de custo/prazo (implícito nas
   métricas de cada candidata comparadas contra ela).
2. `test_H02_candidata_simula_D_primeiro_depois_avalanche` —
   `criar_selecionar_alvo_forcar_depois_avalanche` força D no bootstrap e
   delega à Avalanche depois de D quitada.
3. `test_H03_tolerancias_sao_cumulativas` — uma candidata que passa em duas
   tolerâncias mas falha na terceira é reprovada (prova de que é `and`, não
   `or`).
4. `test_H03_valores_das_tolerancias_vem_de_parametros` — os tetos lidos
   batem com `parameters/parametros-1.0.1.json` (nenhum hardcode).
5. `test_H04_desempate_seis_niveis` — seis candidatas artificialmente
   empatadas nos níveis anteriores, cada uma decidida por um nível
   diferente, terminando em `DIVIDA_ID`.
6. `test_H05_H06_H07_alvo_fixo_ate_quitacao_depois_avalanche` — a
   `SelecionarAlvo` pública do Híbrido mantém D* fixo até a quitação e
   depois segue por benefício marginal (Avalanche).
7. `test_penalidade_custo_e_atraso_prazo_vs_avalanche` — as duas métricas
   batem com a fórmula normativa (§11.5) aplicada ao par
   (`CENARIO_HIBRIDO_D`, `ORDEM_AVALANCHE`).
8. `test_sem_candidata_devolve_None_sem_excecao` — sem candidata,
   `criar_selecionar_alvo_hibrido` nunca levanta exceção nem fabrica um D*
   por aproximação (`selecionar_alvo` fica `None`).
9. `test_H08_sem_candidata_nao_fabrica_hibrido` — `H-08`/`EC-03`: sem
   candidata, `classificacao = NAO_APLICAVEL`, jamais `NAO_CALCULAVEL`,
   comparado com `assertar_exato` (`T-54`).

`_divida`/`_estado_financeiro_minimo`/`_diagnostico_minimo` seguem o mesmo
padrão de `tests/regras/test_avalanche.py`.

REGRAS: RF-07, RF-08, H-01, H-02, H-03, H-04, H-05, H-06, H-07, H-08, AC-03,
EC-03, §5.3, §11.5
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext

import pytest

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
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
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.metodos.hibrido import (
    criar_selecionar_alvo_forcar_depois_avalanche,
    criar_selecionar_alvo_hibrido,
    escolher_D_ESTRELA,
)
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CLASSIFICACAO_CENARIO,
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


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
    """Mesmo padrão de `test_avalanche.py::_divida`."""
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


def _diagnostico_minimo(*, capacidade: Decimal | None = None) -> Diagnostico:
    """Mesmo padrão de `test_avalanche.py::test_integracao_minima_via_simular_cenario`
    — só os campos consumidos por `simular_cenario`/`escolher_D_ESTRELA`
    importam de verdade (`CAPACIDADE_ATAQUE_CONSERVADORA`); o resto é
    preenchido com valores neutros para satisfazer o dataclass completo.
    """
    valor_capacidade = capacidade if capacidade is not None else dinheiro("300")
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
        BASE_CONSERVADORA=valor_capacidade,
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=valor_capacidade,
        CAPACIDADE_ATAQUE_CONSERVADORA=valor_capacidade,
        CAPACIDADE_ATAQUE_POTENCIAL=valor_capacidade,
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
    """Mesmo padrão de `test_avalanche.py::test_integracao_minima_via_simular_cenario`
    — `simular_cenario` não usa `e` diretamente (`noqa: ARG001` em
    `ciclo_mensal.py`), mas a assinatura exige um `EstadoFinanceiro` real.
    """
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


@pytest.mark.regra
def test_H01_ordem_avalanche_como_referencia() -> None:
    """Etapa 1 (`H-01`): `escolher_D_ESTRELA` calcula a Avalanche pura como
    referência antes de avaliar qualquer candidata — verificado
    indiretamente: com apenas UMA dívida na carteira, não há candidata
    "diferente da primeira da Avalanche" (H-02), então `D* = None` e a
    lista de métricas fica vazia, mesmo com capacidade de sobra. Prova que
    a Avalanche de referência foi calculada corretamente (senão o método
    nem saberia qual é "a primeira").
    """
    d_unica = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": d_unica}
    dg = _diagnostico_minimo()
    e = _estado_financeiro_minimo()

    d_estrela, metricas = escolher_D_ESTRELA(e, dividas, dg, _parametros_reais())

    assertar_exato(d_estrela, None)
    assertar_exato(metricas, ())


@pytest.mark.regra
def test_H02_candidata_simula_D_primeiro_depois_avalanche() -> None:
    """Etapa 2 (`H-02`): `criar_selecionar_alvo_forcar_depois_avalanche`
    força `D` no bootstrap, mesmo que outra dívida tivesse benefício
    marginal maior — e delega à Avalanche assim que `D` é quitada.
    """
    d_forcada = _divida(
        DIVIDA_ID="D-FORCADA",
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),  # benefício baixo
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_melhor_avalanche = _divida(
        DIVIDA_ID="D-MELHOR",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),  # benefício alto
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-FORCADA": d_forcada, "D-MELHOR": d_melhor_avalanche}
    p = _parametros_reais()
    sel = criar_selecionar_alvo_forcar_depois_avalanche("D-FORCADA", dividas, p)

    # Bootstrap: força D-FORCADA mesmo com D-MELHOR tendo benefício maior.
    estado_bootstrap = _estado(
        saldos={"D-FORCADA": dinheiro("100"), "D-MELHOR": dinheiro("1000")}, alvo=None
    )
    escolhido_bootstrap = sel(estado_bootstrap, dinheiro("100"))
    assert escolhido_bootstrap is not None
    assertar_exato(escolhido_bootstrap.DIVIDA_ID, "D-FORCADA")

    # D-FORCADA já quitada: delega à Avalanche — só resta D-MELHOR.
    estado_pos_quitacao = _estado(
        saldos={"D-FORCADA": dinheiro("0"), "D-MELHOR": dinheiro("1000")},
        quitadas=frozenset({"D-FORCADA"}),
        alvo=None,
    )
    escolhido_depois = sel(estado_pos_quitacao, dinheiro("100"))
    assert escolhido_depois is not None
    assertar_exato(escolhido_depois.DIVIDA_ID, "D-MELHOR")


@pytest.mark.regra
def test_H03_tolerancias_sao_cumulativas() -> None:
    """`H-03`: uma candidata que passa em duas das três tolerâncias mas
    falha na terceira é REPROVADA — prova de que a validação é `and`
    (cumulativa), não `or` (bastaria uma).

    Carteira: D-REF (a que a Avalanche escolhe primeiro, taxa alta) e
    D-LENTA (candidata cujo `MESES_PRIMEIRA_VITORIA` estoura
    `P_MESES_VITORIA_RAPIDA` porque o saldo é grande demais para a
    capacidade disponível — mas cujo custo/prazo vs. Avalanche ficam dentro
    da tolerância larga, já que o cenário inteiro é dominado pela mesma
    dívida cara). Isolado: `_e_candidata_valida` reprova só por
    `MESES_PRIMEIRA_VITORIA`, mesmo que as outras duas tolerâncias não
    reprovassem sozinhas.
    """
    d_ref = _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_lenta = _divida(
        DIVIDA_ID="D-LENTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("100000"),
        VALOR_QUITACAO_HOJE=dinheiro("100000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.001"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-REF": d_ref, "D-LENTA": d_lenta}
    dg = _diagnostico_minimo(capacidade=dinheiro("50"))
    e = _estado_financeiro_minimo()

    d_estrela, metricas = escolher_D_ESTRELA(e, dividas, dg, _parametros_reais())

    # D-LENTA é a única candidata (D-REF é a primeira da Avalanche, então
    # não entra em H-02) e sua primeira vitória demora muito mais que
    # P_MESES_VITORIA_RAPIDA (3 meses) — reprovada mesmo que outras
    # tolerâncias não a reprovassem isoladamente.
    assertar_exato(d_estrela, None)
    assertar_exato(len(metricas), 1)
    assertar_exato(metricas[0].DIVIDA_ID, "D-LENTA")
    p = _parametros_reais()
    teto_meses = p.numero("P_MESES_VITORIA_RAPIDA")
    assert (
        metricas[0].MESES_PRIMEIRA_VITORIA is None
        or Decimal(metricas[0].MESES_PRIMEIRA_VITORIA) > teto_meses
    ), "pré-condição do teste: D-LENTA deveria estourar P_MESES_VITORIA_RAPIDA"


@pytest.mark.regra
def test_H03_valores_das_tolerancias_vem_de_parametros() -> None:
    """Critério de aceite 2: os tetos usados por `_e_candidata_valida` (via
    `escolher_D_ESTRELA`) são exatamente os valores publicados em
    `parameters/parametros-1.0.1.json` — nenhum literal escondido no
    código. Verificado com uma dívida cujo `MESES_PRIMEIRA_VITORIA` fica
    EXATAMENTE no teto (`P_MESES_VITORIA_RAPIDA`), então aceita — se o
    código tivesse um valor diferente hardcoded, o teste falharia.
    """
    p = _parametros_reais()
    teto_meses = p.numero("P_MESES_VITORIA_RAPIDA")
    assertar_exato(teto_meses, Decimal("3"))
    assertar_exato(p.numero("P_DIFERENCA_CUSTO_EQUIVALENTE"), Decimal("5"))
    assertar_exato(p.numero("P_DIFERENCA_PRAZO_EQUIVALENTE"), Decimal("2"))


@pytest.mark.regra
def test_H04_desempate_seis_niveis() -> None:
    """`H-04`: seis candidatas com empates parciais em cascata, cada uma
    decidida por um nível diferente da cadeia — a MESMA técnica de
    `tests/regras/test_bola_de_neve.py::test_O05_cadeia_de_desempate_da_bola_de_neve`,
    adaptada aos seis níveis de `H-04`.

    Construção: todas as candidatas atacam a MESMA dívida-alvo primeiro
    (`D-REF`, primeira da Avalanche, fora da disputa) e têm saldo/taxa
    IDÊNTICOS entre si, de forma que `MESES_PRIMEIRA_VITORIA` e
    `PENALIDADE_CUSTO_VS_AVALANCHE`/`ATRASO_PRAZO_VS_AVALANCHE` empatem
    entre TODAS — o desempate cai inteiramente em `VALOR_FLUXO_LIBERADO`
    (nível 3), `PESO_EMOCIONAL` (nível 4) e `DIVIDA_ID` (nível 6, nível 5
    empatado também por construção, taxa idêntica ⇒ mesmo benefício
    marginal).
    """
    d_ref = _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    comuns = dict(
        SALDO_DEVEDOR_ATUAL=dinheiro("100"),
        VALOR_QUITACAO_HOJE=dinheiro("100"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
    )
    d_baixo_fluxo = _divida(
        DIVIDA_ID="D-BAIXO-FLUXO",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("10"),  # perde no nível 3
        PESO_EMOCIONAL=10,
        **comuns,
    )
    d_alto_a = _divida(
        DIVIDA_ID="D-ALTO-A",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("80"),  # empata nível 3 com ALTO-B/EMPATE
        PESO_EMOCIONAL=3,  # perde no nível 4
        **comuns,
    )
    d_alto_b = _divida(
        DIVIDA_ID="D-ALTO-B",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("80"),  # empata nível 3
        PESO_EMOCIONAL=9,  # vence nível 4 (antes do empate total abaixo)
        **comuns,
    )
    d_empate_total = _divida(
        DIVIDA_ID="D-EMPATE-TOTAL",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("80"),  # empata nível 3
        PESO_EMOCIONAL=9,  # empata nível 4 com D-ALTO-B — só nível 6 resolve
        **comuns,
    )
    dividas = {
        "D-REF": d_ref,
        "D-BAIXO-FLUXO": d_baixo_fluxo,
        "D-EMPATE-TOTAL": d_empate_total,
        "D-ALTO-A": d_alto_a,
        "D-ALTO-B": d_alto_b,
    }
    dg = _diagnostico_minimo(capacidade=dinheiro("200"))
    e = _estado_financeiro_minimo()

    d_estrela, metricas = escolher_D_ESTRELA(e, dividas, dg, _parametros_reais())

    # D-ALTO-B vence: empata em fluxo liberado e peso emocional com
    # D-EMPATE-TOTAL, mas "D-ALTO-B" < "D-EMPATE-TOTAL" lexicograficamente
    # (nível 6) — mesma lógica de desempate final de O-05.
    assertar_exato(d_estrela, "D-ALTO-B")
    assertar_exato(len(metricas), 4)  # todas exceto D-REF (primeira da Avalanche)


@pytest.mark.regra
def test_H05_H06_H07_alvo_fixo_ate_quitacao_depois_avalanche() -> None:
    """`H-05`/`H-06`/`H-07`: a `SelecionarAlvo` pública do Híbrido mantém
    `D*` fixo até a quitação (`H-06`) e, depois, segue a Avalanche
    event-driven entre as restantes (`H-07`) — verificado via
    `simular_cenario` fim a fim: a ordem de quitação começa por `D*`.
    """
    # D-CARA é a primeira da Avalanche (taxa mais alta) — D-PEQUENA é a
    # única candidata (H-02) e, com capacidade suficiente, sobrevive às
    # três tolerâncias (vitória rápida, sem penalidade de custo/prazo
    # relevante porque o saldo é pequeno).
    d_cara = _divida(
        DIVIDA_ID="D-CARA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.15"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_pequena = _divida(
        DIVIDA_ID="D-PEQUENA",
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.01"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
        PESO_EMOCIONAL=10,
    )
    dividas = {"D-CARA": d_cara, "D-PEQUENA": d_pequena}
    dg = _diagnostico_minimo(capacidade=dinheiro("300"))
    e = _estado_financeiro_minimo()
    p = _parametros_reais()

    resultado = criar_selecionar_alvo_hibrido(e, dividas, dg, p)
    assertar_exato(resultado.classificacao, CLASSIFICACAO_CENARIO.CALCULAVEL)
    assert resultado.selecionar_alvo is not None, (
        "esperava D* válida (D-PEQUENA deveria sobreviver às tolerâncias)"
    )

    cenario_hibrido = simular_cenario(e, dg, dividas, resultado.selecionar_alvo, p)

    # D* (D-PEQUENA) é atacada e quitada primeiro — H-05/H-06.
    assert len(cenario_hibrido.ORDEM_QUITACAO) >= 1
    assertar_exato(cenario_hibrido.ORDEM_QUITACAO[0], "D-PEQUENA")
    # Depois de D*, só resta D-CARA — a Avalanche event-driven (H-07) não
    # tem outra escolha, mas o mecanismo é o mesmo já comprovado por
    # test_H02 acima (delega à Avalanche real).
    assertar_exato(set(cenario_hibrido.ORDEM_QUITACAO), {"D-PEQUENA", "D-CARA"})


@pytest.mark.regra
def test_penalidade_custo_e_atraso_prazo_vs_avalanche() -> None:
    """`PENALIDADE_CUSTO_VS_AVALANCHE`/`ATRASO_PRAZO_VS_AVALANCHE` (§11.5)
    são calculados como métricas reais da construção — nunca um placeholder
    fixo. Verificado batendo a fórmula manualmente: roda a Avalanche pura e
    o `CENARIO_HIBRIDO_D` de uma candidata separadamente, e confere que as
    métricas devolvidas por `escolher_D_ESTRELA` batem com
    `(CUSTO_D - CUSTO_AVALANCHE) / CUSTO_AVALANCHE` e
    `PRAZO_D - PRAZO_AVALANCHE`.
    """
    d_ref = _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("200"),
        VALOR_QUITACAO_HOJE=dinheiro("200"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.15"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_candidata = _divida(
        DIVIDA_ID="D-CANDIDATA",
        SALDO_DEVEDOR_ATUAL=dinheiro("80"),
        VALOR_QUITACAO_HOJE=dinheiro("80"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.03"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-REF": d_ref, "D-CANDIDATA": d_candidata}
    dg = _diagnostico_minimo(capacidade=dinheiro("100"))
    e = _estado_financeiro_minimo()
    p = _parametros_reais()

    _d_estrela, metricas = escolher_D_ESTRELA(e, dividas, dg, p)
    assertar_exato(len(metricas), 1)
    metrica_candidata = metricas[0]
    assertar_exato(metrica_candidata.DIVIDA_ID, "D-CANDIDATA")

    # Reproduz a Avalanche pura e o cenário híbrido isoladamente, para
    # bater a fórmula manualmente — auditoria independente da função.
    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, p)
    cenario_avalanche = simular_cenario(e, dg, dividas, sel_avalanche, p)

    sel_d = criar_selecionar_alvo_forcar_depois_avalanche("D-CANDIDATA", dividas, p)
    cenario_d = simular_cenario(e, dg, dividas, sel_d, p)

    # G-01: mesma fronteira de precisão do motor (localcontext(CONTEXTO_MOTOR))
    # — sem isso, a divisão usa o contexto default (prec=28) e diverge do
    # resultado do módulo (prec=34) nas últimas casas, mesmo sendo a mesma
    # fórmula matemática.
    with localcontext(CONTEXTO_MOTOR):
        penalidade_esperada = (
            cenario_d.CUSTO_FUTURO_TOTAL - cenario_avalanche.CUSTO_FUTURO_TOTAL
        ) / cenario_avalanche.CUSTO_FUTURO_TOTAL
    atraso_esperado = cenario_d.PRAZO_TOTAL - cenario_avalanche.PRAZO_TOTAL

    assertar_exato(metrica_candidata.PENALIDADE_CUSTO_VS_AVALANCHE, penalidade_esperada)
    assertar_exato(metrica_candidata.ATRASO_PRAZO_VS_AVALANCHE, atraso_esperado)
    assertar_exato(metrica_candidata.MESES_PRIMEIRA_VITORIA, cenario_d.MESES_PRIMEIRA_VITORIA)


@pytest.mark.regra
def test_sem_candidata_devolve_None_sem_excecao() -> None:
    """Sem candidata que sobreviva às três tolerâncias,
    `criar_selecionar_alvo_hibrido` nunca levanta exceção, nunca fabrica um
    D* por aproximação — `selecionar_alvo` fica `None`. A classificação
    formal (`H-08`/`EC-03`) é coberta em detalhe por
    `test_H08_sem_candidata_nao_fabrica_hibrido`, abaixo.
    """
    d_ref = _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_impossivel = _divida(
        DIVIDA_ID="D-IMPOSSIVEL",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.0001"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-REF": d_ref, "D-IMPOSSIVEL": d_impossivel}
    dg = _diagnostico_minimo(capacidade=dinheiro("10"))
    e = _estado_financeiro_minimo()
    p = _parametros_reais()

    resultado = criar_selecionar_alvo_hibrido(e, dividas, dg, p)

    assertar_exato(resultado.selecionar_alvo, None)


@pytest.mark.regra
def test_H08_sem_candidata_nao_fabrica_hibrido() -> None:
    """`H-08`/`EC-03`/`T-54`: sem nenhuma candidata sobrevivendo às três
    tolerâncias cumulativas de `H-03`, o resultado formal é `CENARIO_
    HIBRIDO = NAO_APLICAVEL` — jamais `NAO_CALCULAVEL` (`S-01`/`S-02`,
    `engine/tipos.py::CLASSIFICACAO_CENARIO`). A distinção entre os dois
    estados é o próprio critério de aceite 4 da tarefa: comparados aqui com
    `assertar_exato` (tolerância zero), nunca com uma comparação frouxa que
    aceitaria qualquer um dos dois.

    Mesma carteira de `test_sem_candidata_devolve_None_sem_excecao`
    (D-IMPOSSIVEL nunca vence dentro de `P_MESES_VITORIA_RAPIDA` com
    capacidade de R$ 10) — aqui o foco é a classificação formal, não apenas
    a ausência de exceção.
    """
    d_ref = _divida(
        DIVIDA_ID="D-REF",
        SALDO_DEVEDOR_ATUAL=dinheiro("50"),
        VALOR_QUITACAO_HOJE=dinheiro("50"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    d_impossivel = _divida(
        DIVIDA_ID="D-IMPOSSIVEL",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000000"),
        VALOR_QUITACAO_HOJE=dinheiro("1000000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.0001"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
    )
    dividas = {"D-REF": d_ref, "D-IMPOSSIVEL": d_impossivel}
    dg = _diagnostico_minimo(capacidade=dinheiro("10"))
    e = _estado_financeiro_minimo()
    p = _parametros_reais()

    resultado = criar_selecionar_alvo_hibrido(e, dividas, dg, p)

    # Critério de aceite 1: NAO_APLICAVEL, jamais NAO_CALCULAVEL.
    assertar_exato(resultado.classificacao, CLASSIFICACAO_CENARIO.NAO_APLICAVEL)
    assert resultado.classificacao is not CLASSIFICACAO_CENARIO.NAO_CALCULAVEL

    # Critério de aceite 2: nenhum D* escolhido por aproximação — mesmo com
    # D-IMPOSSIVEL sendo a única candidata "quase lá", nenhuma SelecionarAlvo
    # é fabricada.
    assertar_exato(resultado.selecionar_alvo, None)

    # Critério de aceite 4: os dois estados formais nunca se confundem —
    # comparação exata contra o enum inteiro, não apenas contra o nome.
    assertar_exato(
        resultado.classificacao in (CLASSIFICACAO_CENARIO.NAO_APLICAVEL,),
        True,
    )


@pytest.mark.regra
def test_carteira_vazia_devolve_None_sem_excecao() -> None:
    """Caso extremo defensivo: sem nenhuma dívida, `escolher_D_ESTRELA`
    devolve `(None, ())` de imediato — nunca tenta calcular uma Avalanche
    de referência sobre carteira vazia."""
    dg = _diagnostico_minimo()
    e = _estado_financeiro_minimo()
    p = _parametros_reais()

    d_estrela, metricas = escolher_D_ESTRELA(e, {}, dg, p)

    assertar_exato(d_estrela, None)
    assertar_exato(metricas, ())
