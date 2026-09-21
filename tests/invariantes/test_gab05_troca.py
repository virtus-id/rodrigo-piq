"""Invariante `GAB-05` da troca — RF-11 · `T-01`/`T-02` (nomenclatura da
spec) · `AC-12` · `T-72` (tarefa do backlog).

`GAB-05` (backlog, descrição de `T-72`): quitação de uma dívida antiga de
R$ 30.000 por uma nova operação de R$ 40.000. O invariante a provar:

    - o `CENARIO_SUBSTITUICAO_EQUIVALENTE` é calculado SÓ sobre os
      R$ 30.000 (a parte substituída) — nunca sobre os R$ 40.000 totais;
    - os R$ 10.000 restantes (`DINHEIRO_NOVO`) são tratados como NOVO
      ENDIVIDAMENTO — nunca como redução de custo/economia da troca.

**Por que este arquivo não fixa números de saída.** `RF-11` e `AC-12`
(`specs/motor-calculo.spec.md`) descrevem `GAB-05` só pelo CONCEITO — a
separação 30.000 substituído / 10.000 novo endividamento — sem publicar taxa,
prazo ou custo futuro exatos, ao contrário de `GAB-A`/`GAB-B`/`GAB-C`, que
têm todos os números do cenário canônico escritos na spec. Não há gabarito
numérico a reproduzir aqui: este é um teste de INVARIANTE ESTRUTURAL — prova
a PROPRIEDADE (separação entre os dois cenários, nunca soma nem mistura)
sobre dados sintéticos representativos do cenário 30k/40k, mesma abordagem
de `tests/regras/test_troca.py` (`T-71`), mas consolidando os três ângulos
do invariante em um único teste nomeado por `GAB-05`, no diretório correto
(`tests/invariantes/`, marcador `invariante` — `pyproject.toml`), como pede
o critério de aceite de `T-72`.

`_diagnostico`/`_estado_financeiro_neutro`/`_parametros`/`_sel_trivial`:
mesmos helpers de `tests/regras/test_troca.py` — `calcular_
CENARIO_SUBSTITUICAO_EQUIVALENTE` delega a `simular_cenario` internamente
sobre uma dívida sintética isolada, então a montagem mínima de
`EstadoFinanceiro`/`Diagnostico`/`Parametros`/`SelecionarAlvo` é idêntica.

REGRAS: RF-11, T-01, T-02
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao
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
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.estado import TIPO_RENDA as _TIPO_RENDA
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
    DinheiroTalvez,
    SimNaoTalvez,
)
from engine.troca import OperacaoTroca, calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE
from tests.conftest import assertar_exato, assertar_monetario


def _diagnostico(*, capacidade_conservadora: DinheiroTalvez) -> Diagnostico:
    """Mesmo helper de `tests/regras/test_troca.py::_diagnostico` — só
    `CAPACIDADE_ATAQUE_CONSERVADORA` é lido por `simular_cenario`."""
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
        BASE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_POTENCIAL=capacidade_conservadora,  # type: ignore[arg-type]
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


def _estado_financeiro_neutro() -> EstadoFinanceiro:
    """Mesmo helper de `tests/regras/test_troca.py::_estado_financeiro_neutro`
    — `simular_cenario` não lê `e` nesta cadeia de tarefas."""
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


def _parametros(*, horizonte_maximo_anos: int = 10, horizonte_alerta_anos: int = 5) -> Parametros:
    """Mesmo helper de `tests/regras/test_troca.py::_parametros`."""
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={
            "P_HORIZONTE_MAXIMO_SIMULACAO": Decimal(horizonte_maximo_anos),
            "P_HORIZONTE_ALERTA": Decimal(horizonte_alerta_anos),
        },
    )


def _sel_trivial(estado: EstadoSimulacao, _delta: DinheiroTalvez) -> Divida | None:
    """Mesmo `SelecionarAlvo` de `tests/regras/test_troca.py::_sel_trivial`:
    devolve a única candidata não quitada — cada simulação de `GAB-05` tem
    sempre uma única dívida sintética isolada, sem ranqueamento real a fazer."""
    candidatos = tuple(
        divida_id for divida_id in estado.saldos if divida_id not in estado.quitadas
    )
    if not candidatos:
        return None
    (unica_id,) = candidatos
    return Divida(
        DIVIDA_ID=unica_id,
        TIPO_DIVIDA=TIPO_DIVIDA.OUTRA,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=estado.saldos[unica_id],
        VALOR_QUITACAO_HOJE=estado.saldos[unica_id],
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        CET=dinheiro("0"),
        PARCELA_CONTRATUAL=dinheiro("0"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


# `GAB-05`: quitação de dívida antiga de R$ 30.000 por nova operação de
# R$ 40.000 (10.000 de dinheiro novo). Taxa mensal de 1% sobre o saldo,
# pagamento de R$ 5.000/mês na nova operação — valores sintéticos
# representativos, escolhidos apenas para exercitar a separação estrutural
# (não há gabarito numérico publicado na spec para reproduzir).
_OPERACAO_GAB05 = OperacaoTroca(
    SALDO_NOVA_OPERACAO=dinheiro("40000"),
    VALOR_SUBSTITUIDO=dinheiro("30000"),
    TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.01"),
    PAGAMENTO_MENSAL_EFETIVO=dinheiro("5000"),
)


@pytest.mark.invariante
def test_invariante_gab05_troca() -> None:
    """`AC-12`/`GAB-05`: quitação de R$ 30.000 por nova operação de
    R$ 40.000 — o cenário de substituição equivalente é calculado apenas
    sobre os R$ 30.000, e os R$ 10.000 são tratados como novo endividamento,
    jamais como economia.

    Três ângulos do mesmo invariante, no mesmo teste:

    1. O saldo de abertura simulado no `cenario_equivalente` é exatamente
       `VALOR_SUBSTITUIDO` (30.000) — nunca `SALDO_NOVA_OPERACAO` (40.000).
    2. `DINHEIRO_NOVO` é identificado (10.000) e simulado em cenário
       SEPARADO, nunca somado/subtraído/combinado ao `cenario_equivalente`:
       provado por controle — o `CUSTO_FUTURO_TOTAL` e o `PRAZO_TOTAL` do
       `cenario_equivalente` são IDÊNTICOS entre uma troca com dinheiro novo
       e uma troca "limpa" (sem dinheiro novo) sobre a MESMA parte
       substituída, nas mesmas condições de taxa/pagamento proporcional.
    3. Nenhum campo do resultado rotula os 10.000 como economia: o único
       total que "descontaria" o dinheiro novo do custo da troca seria uma
       subtração entre os dois cenários — nunca calculada pelo motor
       (`ResultadoSubstituicaoEquivalente` devolve os dois `Cenario`s
       inteiros e separados, sem nenhum campo agregado que os combine).
    """
    dg = _diagnostico(capacidade_conservadora=dinheiro("0"))
    p = _parametros()
    estado = _estado_financeiro_neutro()

    resultado = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-GAB05", _OPERACAO_GAB05, estado, dg, _sel_trivial, p
    )

    # --- Ângulo 1: cenário equivalente simula SÓ os 30.000 ---------------
    # M-02: juros (1%) aplicados sobre o saldo de ABERTURA antes do
    # pagamento — 30.000 * 1,01 = 30.300 — só então abate o pagamento
    # proporcional (5.000 * 30.000/40.000 = 3.750).
    pagamento_proporcional_equivalente = (
        dinheiro("30000") * dinheiro("5000") / dinheiro("40000")
    )
    saldo_com_juros = dinheiro("30000") * dinheiro("1.01")
    primeiro_mes = resultado.cenario_equivalente.meses[0]
    (saldo_apos_mes_1,) = primeiro_mes.estado_final.saldos.values()
    saldo_esperado_apos_mes_1 = saldo_com_juros - pagamento_proporcional_equivalente
    assertar_monetario(saldo_apos_mes_1, saldo_esperado_apos_mes_1)
    # Se o motor tivesse simulado os 40.000 totais como saldo de abertura em
    # vez de só os 30.000 substituídos, o saldo do primeiro mês divergiria
    # muito além da tolerância de homologação — a asserção acima já reprova
    # esse bug; a linha abaixo torna a distância explícita e legível.
    saldo_se_usasse_total_errado = (
        dinheiro("40000") * dinheiro("1.01") - pagamento_proporcional_equivalente
    )
    assert saldo_apos_mes_1 != saldo_se_usasse_total_errado, (
        "cenário equivalente parece ter simulado SALDO_NOVA_OPERACAO (40.000) "
        "em vez de VALOR_SUBSTITUIDO (30.000)"
    )

    # --- Ângulo 2: DINHEIRO_NOVO identificado, separado, e nunca ---------
    # --- contamina o custo/prazo do cenário equivalente -------------------
    assertar_monetario(resultado.DINHEIRO_NOVO, dinheiro("10000"))
    assert resultado.cenario_dinheiro_novo is not None, (
        "DINHEIRO_NOVO > 0 (10.000) deve produzir um cenário separado e identificável"
    )

    operacao_controle_sem_dinheiro_novo = OperacaoTroca(
        SALDO_NOVA_OPERACAO=dinheiro("30000"),
        VALOR_SUBSTITUIDO=dinheiro("30000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.01"),
        PAGAMENTO_MENSAL_EFETIVO=pagamento_proporcional_equivalente,
    )
    resultado_controle = calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE(
        "D-GAB05", operacao_controle_sem_dinheiro_novo, estado, dg, _sel_trivial, p
    )
    assertar_exato(resultado_controle.cenario_dinheiro_novo, None)

    # Mesma taxa e mesmo pagamento proporcional sobre a MESMA parte
    # substituída (30.000): com ou sem dinheiro novo na operação, o custo e
    # o prazo do cenário equivalente têm que ser EXATAMENTE os mesmos — se o
    # dinheiro novo estivesse "reduzindo" o custo comparado (ex.: sendo
    # somado ao pagamento e acelerando a quitação da parte substituída), os
    # dois resultados divergiriam.
    assertar_monetario(
        resultado.cenario_equivalente.CUSTO_FUTURO_TOTAL,
        resultado_controle.cenario_equivalente.CUSTO_FUTURO_TOTAL,
    )
    assertar_exato(
        resultado.cenario_equivalente.PRAZO_TOTAL,
        resultado_controle.cenario_equivalente.PRAZO_TOTAL,
    )

    # --- Ângulo 3: nenhum caminho classifica os 10.000 como economia -----
    # `ResultadoSubstituicaoEquivalente` só tem os dois cenários separados
    # (`cenario_equivalente`/`cenario_dinheiro_novo`) e o valor identificado
    # do dinheiro novo (`DINHEIRO_NOVO`) — nenhum campo agregado "soma" ou
    # "desconta" um do outro. Provado por introspecção de campos: o dataclass
    # não expõe nenhum atributo de economia/redução/desconto que combinaria
    # os dois cenários.
    campos_do_resultado = tuple(type(resultado).__dataclass_fields__)
    assertar_exato(
        campos_do_resultado, ("DINHEIRO_NOVO", "cenario_equivalente", "cenario_dinheiro_novo")
    )
    for termo_proibido in ("ECONOMIA", "REDUCAO", "DESCONTO", "VANTAGEM"):
        assert not any(termo_proibido in campo.upper() for campo in campos_do_resultado), (
            f"campo de {termo_proibido!r} encontrado em ResultadoSubstituicaoEquivalente — "
            "R$ 10.000 (DINHEIRO_NOVO) não pode ser classificado como economia da troca"
        )

    # O cenário isolado do dinheiro novo é, ele mesmo, um endividamento novo
    # com custo futuro próprio — nunca zero/negativo, que seria o único jeito
    # de ele funcionar como "economia" dentro da própria simulação dele.
    assert resultado.cenario_dinheiro_novo.CUSTO_FUTURO_TOTAL > dinheiro("0"), (
        "cenário do dinheiro novo deveria representar custo de NOVO "
        "endividamento (> 0), nunca economia"
    )
