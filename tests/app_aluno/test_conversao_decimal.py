"""Fronteira `Decimal` por Hypothesis — RF-13, AC-09, AC-10, EC-01 (T-39).

`tests/app_aluno/test_conversao.py` (T-38) já cobre os 22 casos exatos e
pontuais da fronteira. Este arquivo prova a mesma fronteira por PROPRIEDADE:
para todo universo de string ACEITA, o resultado é sempre `Decimal` e nunca
`float`; para todo universo de string RECUSADA, `ErroConversaoInvalida` é
sempre levantado e nada é coagido a `0`. Mais o caso exato de `AC-10` e o
caso de `AC-09` (um `EstadoFinanceiro` montado com valores convertidos não
dispara `_recusar_float`).

`derandomize=True` em todo `@settings`/`@given` — mesmo padrão de
`tests/invariantes/test_propriedades.py` (slug `motor-calculo`): Hypothesis
usa uma semente FIXA derivada do próprio corpo do teste, então a mesma versão
do teste sempre gera a mesma sequência de exemplos e a CI permanece
determinística.

REGRAS: RF-13, AC-09, AC-10, EC-01
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
    converter_para_taxa,
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
    TIPO_DIVIDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.estado import TIPO_RENDA as _TIPO_RENDA
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from engine.tipos import STATUS_DIVIDA as _STATUS_DIVIDA

# Mesma configuração determinística de `tests/invariantes/test_propriedades.py`
# (slug `motor-calculo`): semente fixa derivada do corpo do teste, nunca de
# `random` — duas execuções seguidas produzem exatamente os mesmos exemplos.
_SETTINGS_DETERMINISTICO = settings(
    derandomize=True,
    max_examples=300,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


# ---------------------------------------------------------------------------
# Estratégias — universo ACEITO: strings que a regra de normalização do
# módulo (documentada em `app/montagem/conversao.py`) aceita de fato.
# ---------------------------------------------------------------------------


def _formatar_br_com_milhar(valor: Decimal) -> str:
    """Formata um `Decimal` não-negativo com separador de milhar `.` e
    decimal `,` — o formato brasileiro completo (regra 2 do módulo)."""
    sinal, digitos, expoente = valor.as_tuple()
    # `allow_nan=False, allow_infinity=False` na estratégia garante que
    # `expoente` nunca é um dos literais especiais ('n'/'N'/'F') do
    # `Decimal.as_tuple()` — sempre `int` neste ponto.
    assert isinstance(expoente, int)
    texto_inteiro = "".join(str(d) for d in digitos)
    casas = -expoente if expoente < 0 else 0
    if casas:
        parte_inteira = texto_inteiro[:-casas] or "0"
        parte_decimal = texto_inteiro[-casas:].rjust(casas, "0")
    else:
        parte_inteira, parte_decimal = texto_inteiro, ""

    # Agrupa a parte inteira em blocos de 3 a partir da direita — o mesmo
    # agrupamento que `_milhar_valido` do módulo aceita.
    grupos: list[str] = []
    resto = parte_inteira
    while len(resto) > 3:
        grupos.insert(0, resto[-3:])
        resto = resto[:-3]
    grupos.insert(0, resto)
    com_milhar = ".".join(grupos)

    texto = f"{com_milhar},{parte_decimal}" if parte_decimal else com_milhar
    return f"-{texto}" if sinal else texto


def _formatar_so_virgula(valor: Decimal) -> str:
    """`"1234,56"` — só vírgula decimal, sem separador de milhar (regra 3,
    AC-10)."""
    return str(valor).replace(".", ",")


def _formatar_so_digitos(valor: Decimal) -> str:
    """Sem separador algum — inteiro puro (regra 5)."""
    return str(int(valor))


# Decimal finito, não-negativo ou negativo, com até 2 casas — domínio
# realista de valor monetário/percentual de formulário (mesmo padrão de
# `_st_saldo_decimal` em `tests/invariantes/test_propriedades.py`).
_st_decimal_aceitavel = st.decimals(
    min_value=Decimal("-999999.99"),
    max_value=Decimal("999999.99"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

# Formato "americano" ambíguo mas aceito pela regra 4: um único ponto com 1
# ou 2 dígitos depois — interpretado como decimal. `places` do Hypothesis
# exige um `int` literal, não uma estratégia — por isso a união de duas
# estratégias fixas em vez de sortear `places` dinamicamente.
_st_decimal_um_ou_dois_decimais = st.one_of(
    st.decimals(
        min_value=Decimal("-999999.9"),
        max_value=Decimal("999999.9"),
        allow_nan=False,
        allow_infinity=False,
        places=1,
    ),
    st.decimals(
        min_value=Decimal("-999999.99"),
        max_value=Decimal("999999.99"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)

_st_formato_aceito = st.sampled_from(
    [_formatar_br_com_milhar, _formatar_so_virgula, _formatar_so_digitos]
)


@st.composite
def _st_string_aceita(draw: st.DrawFn) -> str:
    """Gera uma string de entrada que a regra de normalização documentada em
    `app/montagem/conversao.py` DEVE aceitar: formato brasileiro completo
    (milhar `.` + decimal `,`), só vírgula decimal, só dígitos, ou o caso
    ambíguo de ponto único com 1-2 dígitos decimais (regra 4). Espaços nas
    bordas são incluídos como variação válida (regra 1)."""
    formatador = draw(_st_formato_aceito)
    valor = draw(_st_decimal_aceitavel)
    texto = formatador(valor)
    com_espacos = draw(st.booleans())
    if com_espacos:
        texto = f"  {texto}  "
    return texto


@st.composite
def _st_string_aceita_ponto_decimal_ambiguo(draw: st.DrawFn) -> str:
    """Só ponto, com 1 ou 2 dígitos depois — regra 4, decimal (ex.:
    `"12.5"`, `"1234.56"`)."""
    valor = draw(_st_decimal_um_ou_dois_decimais)
    return str(valor)


# ---------------------------------------------------------------------------
# Estratégias — universo RECUSADO: strings que devem produzir
# `ErroConversaoInvalida`, nunca um `Decimal` nem uma coerção a `0`.
# ---------------------------------------------------------------------------

_st_letras = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Lt", "Lm", "Lo")),
    min_size=1,
    max_size=20,
)

_st_string_vazia_ou_espacos = st.sampled_from(["", " ", "   ", "\t", "\n "])

_st_caractere_invalido = st.text(
    alphabet=st.characters(
        blacklist_categories=["Cs"], blacklist_characters="0123456789.,- \t\n"
    ),
    min_size=1,
    max_size=10,
).filter(lambda s: s.strip() != "")


@st.composite
def _st_multiplas_virgulas(draw: st.DrawFn) -> str:
    """Duas ou mais vírgulas — sempre ambíguo e recusado (regras 2 e 3)."""
    partes = draw(
        st.lists(st.text(alphabet="0123456789", min_size=1, max_size=4), min_size=3, max_size=5)
    )
    return ",".join(partes)


@st.composite
def _st_pontos_ambiguos(draw: st.DrawFn) -> str:
    """Dois ou mais pontos (nunca só um) onde pelo menos um grupo após o
    primeiro não tem exatamente 3 dígitos — viola `_milhar_valido` do módulo
    (ex.: `"1.2.3"`, `"12.3.456"`). Por ter mais de um `.`, também não se
    encaixa na regra 4 (decimal só é aceito com exatamente 1 ponto). Sempre
    recusado."""
    primeiro = draw(st.text(alphabet="0123456789", min_size=1, max_size=3))
    grupo_invalido = draw(
        st.text(alphabet="0123456789", min_size=1, max_size=2)
    )  # nunca 3 dígitos — garante violação do agrupamento de milhar
    grupo_extra_obrigatorio = draw(
        st.text(alphabet="0123456789", min_size=1, max_size=4)
    )  # garante >= 2 pontos no total — nunca decimal válido da regra 4
    grupos_extras = draw(
        st.lists(st.text(alphabet="0123456789", min_size=1, max_size=4), min_size=0, max_size=1)
    )
    return ".".join([primeiro, grupo_invalido, grupo_extra_obrigatorio, *grupos_extras])


_st_string_recusada = st.one_of(
    _st_letras,
    _st_string_vazia_ou_espacos,
    _st_caractere_invalido,
    _st_multiplas_virgulas(),
    _st_pontos_ambiguos(),
)


# ---------------------------------------------------------------------------
# AC-10 — caso exato: "1234,56" produz exatamente Decimal("1234.56"),
# comparado com igualdade exata, nunca com tolerância.
# ---------------------------------------------------------------------------
class TestAC10CasoExato:
    def test_ac_10_virgula_decimal_produz_decimal_exato(self) -> None:
        resultado = converter_para_dinheiro("1234,56")
        assert resultado == Decimal("1234.56")
        assert str(resultado) == "1234.56"  # igualdade exata, nunca tolerância


# ---------------------------------------------------------------------------
# AC-09 — um EstadoFinanceiro montado a partir de valores convertidos não
# levanta o TypeError de `_recusar_float`.
# ---------------------------------------------------------------------------
class TestAC09EstadoFinanceiroComValoresConvertidos:
    def _estado_com(
        self, *, renda: Decimal, despesas: Decimal, capacidade: Decimal
    ) -> EstadoFinanceiro:
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
        divida = Divida(
            DIVIDA_ID="D-01",
            TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
            STATUS_DIVIDA=_STATUS_DIVIDA.ATIVA,
            SALDO_DEVEDOR_ATUAL=renda,  # reaproveita valor convertido só p/ exercitar o campo
            VALOR_QUITACAO_HOJE=renda,
            QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
            STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
            TAXA_EFETIVA_MENSAL_NORMALIZADA=DESCONHECIDO,
            CET=DESCONHECIDO,
            PARCELA_CONTRATUAL=despesas,
            PAGAMENTO_MENSAL_EFETIVO=despesas,
            SEGURO_INCLUIDO_PARCELA=False,
            CUSTO_SEGURO=capacidade,
            PESO_EMOCIONAL=0,
            RENEGOCIACAO_PENDENTE=False,
            TROCA_PENDENTE=False,
            RISCO_MATERIAL_IMINENTE=False,
            OPORTUNIDADE_VIGENTE=None,
        )
        return EstadoFinanceiro(
            DATA_REFERENCIA=date(2026, 1, 1),
            RENDA_TOTAL_RECORRENTE=renda,
            TIPO_RENDA=_TIPO_RENDA.FIXA,
            DESPESAS_OPERACIONAIS_ATUAIS=despesas,
            DESPESAS_NAO_MENSAIS_NORMALIZADAS=despesas,
            CAPACIDADE_ATAQUE_DECLARADA=capacidade,
            ECONOMIA_POTENCIAL_IMEDIATA=capacidade,
            INVENTARIO_COMPLETO=True,
            dividas=(divida,),
            perfil_comportamental=perfil,
            sinais_comportamentais=sinais,
            CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
            AUTOPERCEPCAO_CONTROLE=0,
            # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
            # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
            # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
            # `Decimal(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
            # §13.1 vencer antes da Regra 3 (`EC-23`). `Decimal` direto, e não
            # `dinheiro(...)`: é o idioma deste módulo, que testa a fronteira
            # de conversão e nunca importou `engine.precisao`.
            RESERVA_EXISTE=RESERVA_EXISTE.NAO,
            RESERVA_TOTAL=Decimal(0),
            DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
            VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=Decimal(0),
            DINHEIRO_DISPONIVEL=Decimal(0),
            investimentos=(),
            ativos=(),
            recursos_extraordinarios=(),
        )

    def test_ac_09_estado_financeiro_com_valores_convertidos_nao_levanta_typeerror(self) -> None:
        renda = converter_para_dinheiro("5.432,10")
        despesas = converter_para_dinheiro("1234,56")
        capacidade = converter_para_taxa("4,5")

        # Não levanta: `_recusar_float` (engine/estado.py) só dispara sobre
        # `float` de fato, e a fronteira desta feature nunca produz `float`.
        estado = self._estado_com(renda=renda, despesas=despesas, capacidade=capacidade)

        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("5432.10")
        assert estado.dividas[0].SALDO_DEVEDOR_ATUAL == Decimal("5432.10")


# ---------------------------------------------------------------------------
# Propriedade Hypothesis — para toda string ACEITA, o resultado é sempre
# Decimal e nenhum float aparece no caminho.
# ---------------------------------------------------------------------------
@_SETTINGS_DETERMINISTICO
@given(_st_string_aceita())
def test_propriedade_string_aceita_produz_sempre_decimal_nunca_float_dinheiro(texto: str) -> None:
    resultado = converter_para_dinheiro(texto)
    assert isinstance(resultado, Decimal)
    assert not isinstance(resultado, float)


@_SETTINGS_DETERMINISTICO
@given(_st_string_aceita_ponto_decimal_ambiguo())
def test_propriedade_ponto_decimal_ambiguo_produz_sempre_decimal_nunca_float(texto: str) -> None:
    resultado = converter_para_dinheiro(texto)
    assert isinstance(resultado, Decimal)
    assert not isinstance(resultado, float)


@_SETTINGS_DETERMINISTICO
@given(_st_string_aceita())
def test_propriedade_string_aceita_produz_sempre_decimal_nunca_float_taxa(texto: str) -> None:
    resultado = converter_para_taxa(texto)
    assert isinstance(resultado, Decimal)
    assert not isinstance(resultado, float)


@_SETTINGS_DETERMINISTICO
@given(_st_string_aceita())
def test_propriedade_nenhum_float_aparece_no_estado_montado_do_convertido(texto: str) -> None:
    """Fecha o laço com `AC-09`: para toda string aceita, o `Dinheiro`
    resultante, usado para montar um `EstadoFinanceiro` mínimo, nunca faz
    `_recusar_float` disparar — nenhum `float` está no caminho."""
    convertido = converter_para_dinheiro(texto)
    estado = TestAC09EstadoFinanceiroComValoresConvertidos()._estado_com(
        renda=convertido, despesas=convertido, capacidade=convertido
    )
    for campo in fields(estado):
        assert not isinstance(getattr(estado, campo.name), float)


# ---------------------------------------------------------------------------
# EC-01 — para toda string RECUSADA, nenhuma gravação ocorre (nenhum
# Decimal é produzido) e o valor não é coagido a 0.
# ---------------------------------------------------------------------------
@_SETTINGS_DETERMINISTICO
@given(_st_string_recusada)
def test_propriedade_string_recusada_levanta_erro_tipado_nunca_coage_a_zero_dinheiro(
    texto: str,
) -> None:
    with pytest.raises(ErroConversaoInvalida) as excecao:
        converter_para_dinheiro(texto)
    assert excecao.value.valor_recusado == texto
    assert excecao.value.motivo  # motivo sempre nomeado, nunca mensagem vazia/genérica


@_SETTINGS_DETERMINISTICO
@given(_st_string_recusada)
def test_propriedade_string_recusada_levanta_erro_tipado_nunca_coage_a_zero_taxa(
    texto: str,
) -> None:
    with pytest.raises(ErroConversaoInvalida) as excecao:
        converter_para_taxa(texto)
    assert excecao.value.valor_recusado == texto
    assert excecao.value.motivo
