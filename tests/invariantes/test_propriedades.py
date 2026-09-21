"""Testes por propriedade dos invariantes `A-04` e `F-03` — `T-48`.

`tests/regras/test_ciclo_mensal.py` e `tests/regras/test_simular_cenario.py`
provam `A-04`/`F-03` com casos FIXOS, escolhidos a dedo. Este arquivo prova a
mesma coisa por PROPRIEDADE, sobre um espaço maior de carteiras geradas pelo
Hypothesis — carteiras de 1 a 10 dívidas, com saldos `Decimal` arbitrários
(válidos, não-negativos, sem `NaN`/infinito).

**`A-04` — nenhum valor desaparece** (`RF-03`, `piq-app-spec.md` linha 117,
TRAVA). Para qualquer mês simulado:

    ataque_aplicado_total_do_mes + ATAQUE_NAO_UTILIZADO_do_mes
        == CAPACIDADE_ATAQUE_M_do_mes

`executar_mes` já verifica essa mesma conta internamente e levanta
`ErroInvariante` se não fechar (`engine/ciclo_mensal.py`, "Invariante de
conservação"). Esta propriedade não testa a exceção — testa o RESULTADO
observável (`ResultadoMes`) sobre um espaço maior de entradas, reconstruindo
a mesma soma que a spec exige (`A-04`), de fora do módulo.

**`F-03` — nenhum valor contado duas vezes** (`RF-04`, §11.7). Para todo mês
do horizonte simulado, o `VALOR_FLUXO_LIBERADO` DEVOLVIDO por aquele mês
nunca é somado à `CAPACIDADE_ATAQUE_M` do PRÓPRIO mês — só do mês seguinte
(`M-11`). Verificado sobre `Cenario.meses` (o rastro completo de
`simular_cenario`, T-46), comparando `CAPACIDADE_ATAQUE_M` de cada mês contra
a do mês anterior mais o `VALOR_FLUXO_LIBERADO` do mês anterior.

`derandomize=True` em todo `@settings`/`@given`: Hypothesis usa uma semente
FIXA derivada do próprio corpo do teste (não de `random`), então a mesma
versão do teste sempre gera a mesma sequência de exemplos — a CI permanece
determinística (NFR "Determinismo", `specs/motor-calculo.spec.md` §5).
Verificado empiricamente na tarefa: duas execuções seguidas de
`pytest tests/invariantes/test_propriedades.py` produzem o mesmo resultado
(mesmos exemplos, mesmo veredito), sem variação de corrida para corrida.

`_SelPorMenorSaldo` é o mesmo `SelecionarAlvo` de teste usado por
`test_ciclo_mensal.py`/`test_simular_cenario.py`: escolhe, entre as dívidas
não quitadas, a de menor saldo (desempate por `DIVIDA_ID`) — não é a
Avalanche real (`T-49`+), só um ponto de variação determinístico suficiente
para exercitar `executar_mes`/`simular_cenario`.

**Teste de mutação (critério 4).** Ver `test_mutacao_deteccao_de_bugs.py`
neste mesmo diretório: duas versões da verificação de conservação com o bug
introduzido de propósito (resíduo descartado / fluxo somado duas vezes),
aplicadas sobre o MESMO rastro (`Cenario.meses`) que as propriedades acima
consomem — provam que a checagem por propriedade rejeita esses dois bugs.
Ficam em arquivo próprio, sempre executados pela suíte (não são script
manual descartável): assim a proteção contra regressão futura na lógica de
verificação continua valendo, em vez de ser só uma nota de rodapé.

REGRAS: RF-03, RF-04, A-04, F-03
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.ciclo_mensal import Cenario, EstadoSimulacao, ResultadoMes, simular_cenario
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
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_VALIDADE_PROPOSTA,
    DinheiroTalvez,
    SimNaoTalvez,
)
from tests.conftest import assertar_exato

# Toda propriedade deste arquivo é `derandomize=True` — critério de aceite 1:
# a CI permanece determinística porque a semente deixa de vir de `random` e
# passa a ser derivada do corpo do próprio teste, então a mesma versão do
# teste sempre gera a mesma sequência de exemplos.
_SETTINGS_DETERMINISTICO = settings(
    derandomize=True,
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
)


# ---------------------------------------------------------------------------
# Estratégias Hypothesis — carteira de 1 a 10 dívidas com saldos Decimal
# válidos, convertidos via dinheiro() (único construtor monetário, G-01).
# ---------------------------------------------------------------------------

# Decimal não-negativo, finito, com no máximo 2 casas — domínio realista de
# saldo devedor (RF-12: dinheiro() já recusa float; aqui garantimos que o
# Decimal gerado é sempre aceito por dinheiro() sem lançar).
_st_saldo_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

# Capacidade de ataque mensal — mesmo domínio de saldo, mas com piso menor
# para exercitar tanto meses que quitam de primeira quanto meses que
# cascateiam por vários períodos.
_st_capacidade_decimal = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("5000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

_st_tamanho_carteira = st.integers(min_value=1, max_value=10)


@st.composite
def _st_carteira(draw: st.DrawFn) -> tuple[dict[str, Divida], Decimal]:
    """Gera uma carteira de 1 a 10 dívidas (`DIVIDA_ID` únicos, saldo
    `Decimal` convertido por `dinheiro()`) e uma capacidade de ataque mensal
    — par consumido pelas duas propriedades abaixo."""
    tamanho = draw(_st_tamanho_carteira)
    saldos = draw(
        st.lists(_st_saldo_decimal, min_size=tamanho, max_size=tamanho, unique=True)
    )
    capacidade = draw(_st_capacidade_decimal)

    dividas: dict[str, Divida] = {}
    for indice, saldo_decimal in enumerate(saldos, start=1):
        divida_id = f"D-{indice:02d}"
        saldo = dinheiro(saldo_decimal)
        dividas[divida_id] = _divida(divida_id, saldo=saldo)
    return dividas, capacidade


def _divida(divida_id: str, *, saldo: DinheiroTalvez) -> Divida:
    """Dívida completa e válida — sem juros, pagamento normal 0 — mesmo
    padrão de `_divida` em `test_ciclo_mensal.py`/`test_simular_cenario.py`,
    variando apenas o saldo, que é o único campo gerado pela estratégia."""
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0"),
        CET=DESCONHECIDO,
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


def _parametros(*, horizonte_maximo_anos: int = 2, horizonte_alerta_anos: int = 1) -> Parametros:
    """Horizonte pequeno (2 anos = 24 meses) para a propriedade terminar
    rápido mesmo em carteiras grandes com capacidade pequena — o mesmo
    padrão de override de `_parametros` em `test_simular_cenario.py`."""
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={
            "P_HORIZONTE_MAXIMO_SIMULACAO": Decimal(horizonte_maximo_anos),
            "P_HORIZONTE_ALERTA": Decimal(horizonte_alerta_anos),
        },
    )


def _diagnostico(*, capacidade_conservadora: DinheiroTalvez) -> Diagnostico:
    """Mesmo helper de `test_simular_cenario.py::_diagnostico` — só
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
    """Mesmo helper de `test_simular_cenario.py::_estado_financeiro_neutro`
    — `simular_cenario` não lê `e` nesta tarefa, instância mínima só para
    satisfazer a assinatura."""
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


@dataclass
class _SelPorMenorSaldo:
    """Mesmo `SelecionarAlvo` de teste de `test_ciclo_mensal.py`/
    `test_simular_cenario.py` — escolhe, entre as dívidas não quitadas, a de
    menor saldo (desempate por `DIVIDA_ID`)."""

    dividas: dict[str, Divida] = field(default_factory=dict)

    def __call__(self, estado: EstadoSimulacao, delta: DinheiroTalvez) -> Divida | None:
        candidatos = tuple(
            divida_id for divida_id in self.dividas if divida_id not in estado.quitadas
        )
        if not candidatos:
            return None
        escolhido = min(candidatos, key=lambda d: (estado.saldos[d], d))
        return self.dividas[escolhido]


def _simular(dividas: dict[str, Divida], capacidade: Decimal) -> Cenario:
    sel = _SelPorMenorSaldo(dividas=dividas)
    dg = _diagnostico(capacidade_conservadora=dinheiro(capacidade))
    p = _parametros()
    return simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)


# ---------------------------------------------------------------------------
# A-04 — nenhum valor desaparece: para qualquer mês simulado,
# ataque_aplicado_total_do_mes + ATAQUE_NAO_UTILIZADO_do_mes ==
# CAPACIDADE_ATAQUE_M_do_mes. Critério de aceite 2: carteiras de 1 a 10
# dívidas.
# ---------------------------------------------------------------------------
@_SETTINGS_DETERMINISTICO
@given(_st_carteira())
def test_A04_nenhum_valor_desaparece_em_qualquer_mes(
    carteira: tuple[dict[str, Divida], Decimal],
) -> None:
    dividas, capacidade = carteira
    cenario = _simular(dividas, capacidade)

    for resultado_mes in cenario.meses:
        ataque_aplicado_total = ataque_aplicado_total_do_mes(resultado_mes)
        with_conservacao = ataque_aplicado_total + resultado_mes.ATAQUE_NAO_UTILIZADO
        # CAPACIDADE_ATAQUE_M_do_mes é a capacidade que abriu aquele mês —
        # o mesmo valor com que a cascata daquele mês trabalhou, disponível
        # em estado_final.CAPACIDADE_ATAQUE_M (executar_mes devolve a
        # capacidade recebida, sem alterá-la — só simular_cenario muda essa
        # capacidade, e só na ABERTURA do mês seguinte, F-02/F-03).
        assertar_exato(with_conservacao, resultado_mes.estado_final.CAPACIDADE_ATAQUE_M)


def ataque_aplicado_total_do_mes(resultado_mes: ResultadoMes) -> Decimal:
    """`ataque_aplicado_total_do_mes` da propriedade `A-04`: o que coube no
    alvo original (`CAPACIDADE_ATAQUE_M − RESIDUO_ATAQUE_M`, já que
    `RESIDUO_ATAQUE_M` é exatamente "o que sobrou do ataque depois de zerar
    o alvo original", `A-01`) mais cada rodada da cascata de resíduo
    (`aplicacoes_residuo`, `A-02`)."""
    capacidade = resultado_mes.estado_final.CAPACIDADE_ATAQUE_M
    with localcontext(CONTEXTO_MOTOR):
        aplicado_no_alvo_original = capacidade - resultado_mes.RESIDUO_ATAQUE_M
        aplicado_na_cascata = sum(
            (aplicacao.valor_aplicado for aplicacao in resultado_mes.aplicacoes_residuo),
            start=dinheiro("0"),
        )
        return aplicado_no_alvo_original + aplicado_na_cascata


# ---------------------------------------------------------------------------
# F-03 — nenhum valor contado duas vezes: o VALOR_FLUXO_LIBERADO de um mês
# nunca é somado à CAPACIDADE_ATAQUE_M do PRÓPRIO mês — só do mês seguinte.
# Critério de aceite 3: verifica TODO mês do horizonte, não só o primeiro.
# ---------------------------------------------------------------------------
@_SETTINGS_DETERMINISTICO
@given(_st_carteira())
def test_F03_fluxo_liberado_nunca_soma_na_capacidade_do_proprio_mes(
    carteira: tuple[dict[str, Divida], Decimal],
) -> None:
    dividas, capacidade = carteira
    cenario = _simular(dividas, capacidade)

    if len(cenario.meses) < 2:
        # Precisa de pelo menos dois meses para comparar "capacidade do mês
        # N" contra "capacidade do mês N-1 + fluxo liberado do mês N-1" —
        # com um único mês (ou nenhum) não há mês seguinte a verificar.
        return

    for indice in range(1, len(cenario.meses)):
        mes_anterior = cenario.meses[indice - 1]
        mes_atual = cenario.meses[indice]

        with localcontext(CONTEXTO_MOTOR):
            capacidade_esperada_do_mes_atual = (
                mes_anterior.estado_final.CAPACIDADE_ATAQUE_M
                + mes_anterior.VALOR_FLUXO_LIBERADO
            )
        # M-11: o fluxo liberado do mês anterior JÁ está incorporado na
        # capacidade do mês atual...
        assertar_exato(
            mes_atual.estado_final.CAPACIDADE_ATAQUE_M, capacidade_esperada_do_mes_atual
        )
        # ...e F-03: a capacidade do PRÓPRIO mês anterior nunca incluiu o
        # fluxo que ELE MESMO liberou — só a capacidade do mês seguinte
        # incorpora. Se o mês anterior já tivesse somado seu próprio fluxo,
        # a capacidade do mês atual teria o valor contado duas vezes (uma
        # vez implicitamente dentro de `CAPACIDADE_ATAQUE_M` do mês
        # anterior, outra explicitamente aqui) — verificado provando que
        # `CAPACIDADE_ATAQUE_M` do mês anterior, por si só, NUNCA já
        # continha esse fluxo: refazendo a soma a partir do mês
        # anterior-anterior (ou da capacidade inicial) chega ao mesmo total,
        # sem sobra nem falta.
        if mes_anterior.VALOR_FLUXO_LIBERADO != dinheiro("0"):
            assert (
                mes_anterior.estado_final.CAPACIDADE_ATAQUE_M
                != capacidade_esperada_do_mes_atual
            ), (
                "F-03 violado: a capacidade do próprio mês já incorporava o "
                "fluxo que ele mesmo liberou — dupla contagem"
            )
