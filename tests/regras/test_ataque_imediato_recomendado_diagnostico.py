"""Testes de integração ponta a ponta de `Diagnostico.ATAQUE_IMEDIATO_
RECOMENDADO`, o campo REAL publicado por `calcular_plano` — `RF-66` · `AC-112`
a `AC-114` · `EC-48` · `EC-49` · `US-26` · `T-144`.

Todos os cinco casos chamam **exclusivamente** `calcular_plano` — nunca
`calcular_diagnostico` isolada (essa segunda prova, de que a chamada isolada
CONTINUA `dinheiro(0)`, é `T-146`, arquivo `test_diagnostico_isolado_mantem_
placeholder.py`). É a prova de que a segunda passada de `engine/motor.py`
(`_compor_ATAQUE_IMEDIATO_RECOMENDADO`, `T-141`/`T-142`) substitui de fato o
placeholder pelo valor real da §14.2.4/§13.3, sem vazar comportamento nem
inventar valor.

`GAB-C` (`tests/fixtures/carregar.py::carregar_gab_c`) é o ponto de partida
comum: três dívidas com `SALDO_DEVEDOR_ATUAL` conhecido, `QUITACAO_CONSULTADA
=NAO` (então `VALOR_RELEVANTE_PARA_QUITACAO` cai no fallback de
`compor_VALOR_RELEVANTE_PARA_QUITACAO` e vale o próprio saldo), nenhuma
travada pelos Gates 1-4 — as três chegam `PRONTA_PARA_ORDENACAO`, contribuindo
o saldo integral (ramo 4 de `NECESSIDADE_IMEDIATA_DIVIDA`) à soma de
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`. `dataclasses.replace` ajusta só o
necessário para cada cenário, preservando o resto da carteira homologada.

`GAB-A` (déficit puro, as duas dívidas com `SALDO_DEVEDOR_ATUAL=DESCONHECIDO`,
bloqueadas no Gate 1) é o ponto de partida de `EC-49` — ver docstring do
teste correspondente para a distinção do caminho lógico de `EC-48`.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.estado import (
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    LIQUIDEZ_INVESTIMENTOS,
    RESERVA_EXISTE,
    EstadoFinanceiro,
    ItemInvestimento,
)
from engine.gates import AcaoRequerida, ParticaoElegibilidade
from engine.motor import calcular_plano
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_c


@pytest.fixture(scope="module")
def _parametros() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _investimento_recomendavel(item_id: str, valor: int) -> ItemInvestimento:
    """`MOBILIZACAO_RECOMENDAVEL`, líquido — mesmo padrão canônico de
    `tests/regras/test_ataque_imediato_potencial.py::_investimento` (T-103),
    reduzido ao único ramo que `calcular_INVESTIMENTOS_RECOMENDADOS` exige:
    `POSSUI_LIQUIDEZ=True` e campos brutos que `classificar_investimento`
    deriva como `MOBILIZACAO_RECOMENDAVEL` (§14.3.1)."""
    return ItemInvestimento(
        ITEM_ID=item_id,
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(valor),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D0,
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.SIM,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(valor),
        TEM_CUSTO_CONHECIDO=False,
        SEM_CUSTO_PERDA_RELEVANTE=True,
    )


def _com_reserva_mobilizavel(estado: EstadoFinanceiro, valor: int) -> EstadoFinanceiro:
    """Ajusta os quatro campos de reserva (RF-36, §13.1) para que `derivar_
    RESERVA_MOBILIZAVEL` produza exatamente `valor` conhecido: Regra 1 não
    vence (`RESERVA_EXISTE=SIM`, `DISPOSICAO_USO_RESERVA` != `NAO`), Regra 3
    não vence (`RESERVA_TOTAL`/`VALOR_MAXIMO_...` conhecidos), Regra 2 dá
    `MIN(RESERVA_TOTAL, MAX(0, informado)) = valor` com os dois iguais a
    `valor`."""
    return dataclasses.replace(
        estado,
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=dinheiro(valor),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(valor),
    )


@pytest.mark.regra
def test_AC112_insumos_positivos_produzem_ataque_imediato_recomendado_nao_zero(
    _parametros: Parametros,
) -> None:
    """`AC-112` (prova negativa genérica): `EstadoFinanceiro` com
    `DINHEIRO_DISPONIVEL > 0` e ao menos uma dívida elegível com
    `VALOR_RELEVANTE_PARA_QUITACAO > 0` produz `ATAQUE_IMEDIATO_RECOMENDADO
    != dinheiro(0)` — o campo carrega o valor calculado por `MIN(elegível,
    recursos)` e não existe mais nenhum `dinheiro(0)` de placeholder no
    `Diagnostico` publicado por `calcular_plano` (§14.2.4).

    `GAB-C` já tem três dívidas elegíveis com saldo positivo; só
    `DINHEIRO_DISPONIVEL` precisa deixar de ser `0` (valor da fixture) para
    que `CAIXA_RECOMENDADO > 0` componha o `MIN` com um elegível também
    positivo."""
    estado = dataclasses.replace(carregar_gab_c(), DINHEIRO_DISPONIVEL=dinheiro("1000"))

    snapshot = calcular_plano(estado, _parametros)

    assert snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO != dinheiro(0), (
        "insumos positivos (caixa e dívida elegível com valor relevante > 0) "
        "deveriam produzir ATAQUE_IMEDIATO_RECOMENDADO real, não o placeholder 0"
    )


@pytest.mark.regra
def test_AC113_equivalente_a_GAB_AI_06_elegivel_20000_recursos_22000_resultado_20000(
    _parametros: Parametros,
) -> None:
    """`AC-113`, equivalente a `GAB-AI-06` (§13.10, §14.16): elegível
    `20.000`; `CAIXA_RECOMENDADO=5.000`; `INVESTIMENTOS_RECOMENDADOS=7.000`;
    `EXTRAORDINARIOS_RECOMENDADOS=0`; `ATIVOS_RECOMENDADOS=0`;
    `RESERVA_MOBILIZAVEL=10.000` ⇒ `NECESSIDADE_RESIDUAL=8.000`,
    `RESERVA_RECOMENDADA=MIN(10.000,8.000)=8.000`, recursos totais
    `5.000+7.000+0+0+8.000=20.000`, `ATAQUE_IMEDIATO_RECOMENDADO=
    MIN(20.000,20.000)=20.000` — reproduzindo, ponta a ponta via
    `calcular_plano`, o mesmo resultado que `GAB-AI-06` já provava como
    função pura isolada (Rodada 3, `T-145` confirma a equivalência).

    `GAB-C` tem três dívidas elegíveis somando `12.000+7.000+3.000=22.000`
    de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`; D001 é ajustada de
    `12.000` para `10.000` para que a soma feche exatamente em `20.000`
    (`10.000+7.000+3.000`)."""
    base = carregar_gab_c()
    d001_ajustada = dataclasses.replace(base.dividas[0], SALDO_DEVEDOR_ATUAL=dinheiro("10000"))
    estado = dataclasses.replace(
        base,
        dividas=(d001_ajustada, *base.dividas[1:]),
        DINHEIRO_DISPONIVEL=dinheiro("5000"),
        investimentos=(_investimento_recomendavel("I1", 7000),),
    )
    estado = _com_reserva_mobilizavel(estado, 10000)

    snapshot = calcular_plano(estado, _parametros)

    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("20000"))


@pytest.mark.regra
def test_AC114_equivalente_a_GAB_AI_07_elegivel_10000_recursos_25000_resultado_10000(
    _parametros: Parametros,
) -> None:
    """`AC-114`, equivalente a `GAB-AI-07` (§13.10, §14.16): elegível
    `10.000`, recursos estrategicamente recomendados somando `25.000` ⇒
    `ATAQUE_IMEDIATO_RECOMENDADO = MIN(10.000, 25.000) = 10.000` — **nunca**
    `25.000`. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é o TETO da
    recomendação, não uma parcela: ter recursos mobilizáveis muito acima da
    necessidade elegível não eleva o recomendado além do elegível (§13.5).

    Carteira reduzida a uma única dívida elegível de saldo `10.000` (a soma
    de todas as parcelas do inventário, ramo 4 de `NECESSIDADE_IMEDIATA_
    DIVIDA`, precisa fechar em `10.000` exato) com `DINHEIRO_DISPONIVEL=
    25.000` (todo o recurso concentrado em caixa, §13.7 ordem 1, para não
    depender de investimento/reserva adicionais nesta prova)."""
    base = carregar_gab_c()
    unica_divida = dataclasses.replace(base.dividas[0], SALDO_DEVEDOR_ATUAL=dinheiro("10000"))
    estado = dataclasses.replace(
        base,
        dividas=(unica_divida,),
        DINHEIRO_DISPONIVEL=dinheiro("25000"),
    )

    snapshot = calcular_plano(estado, _parametros)

    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("10000"))
    assert snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO != dinheiro("25000"), (
        "MIN(elegível, recursos) nunca pode devolver os recursos inteiros "
        "quando eles excedem o elegível (AC-114/AC-76/GAB-AI-07)"
    )


@pytest.mark.regra
def test_EC48_acao_gate_com_valor_financeiro_desconhecido_nao_fabrica_valor(
    _parametros: Parametros,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-48`: uma `AcaoRequerida` (Gate 2/4) associada a uma dívida
    elegível com `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` faz
    `NECESSIDADE_IMEDIATA_DIVIDA` (ramo 3, `RF-63`/`AC-109`) devolver
    `DESCONHECIDO` para aquela parcela, que propaga (`AC-108`/`EC-46`) para
    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=DESCONHECIDO` inteiro — e a
    trava de propagação de `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (`T-141`,
    primeiro ramo avaliado) devolve `ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)`,
    **sem levantar exceção** e sem fabricar um valor a partir dos recursos
    recomendados conhecidos.

    Nenhum dos quatro gates reais (`engine/gates.py`) produz hoje uma
    `AcaoRequerida` com `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` — Gate
    2 hardcoda `dinheiro(0)` nos dois ramos, e a única fonte real de valor
    (`VALOR_QUITACAO_HOJE` do Gate 3) cai no `GATE_PENDENTE.TRANSFORMACAO`
    (ramo 2, sempre `0`), nunca no ramo 3. Para exercitar ponta a ponta, via
    `calcular_plano`, o caminho aspiracional que `RF-63`/`AC-109` preveem
    (mesma técnica de `tests/regras/test_motor.py::
    test_criterio5_erro_invariante_propaga_sem_ser_capturado`, que também
    usa `monkeypatch` sobre um ponto interno de `engine.motor`), este teste
    substitui `particionar_elegibilidade` por um stub que devolve a MESMA
    partição real de `GAB-C`, exceto que a dívida `D001` (elegível, saldo
    conhecido) ganha uma `AcaoRequerida` de `ORDEM_ACOES` com valor
    desconhecido — tudo o mais no motor roda normalmente."""
    import engine.motor as motor_mod
    from engine.gates import particionar_elegibilidade as particionar_elegibilidade_real

    estado = dataclasses.replace(carregar_gab_c(), DINHEIRO_DISPONIVEL=dinheiro("1000"))

    def _particionar_com_acao_de_valor_desconhecido(
        dividas: tuple[object, ...],
    ) -> ParticaoElegibilidade:
        particao_real = particionar_elegibilidade_real(dividas)  # type: ignore[arg-type]
        acao_com_valor_desconhecido = AcaoRequerida(
            ACAO_ID="D001:RENEGOCIACAO",
            DIVIDA_ID="D001",
            TIPO_ACAO="RENEGOCIACAO",
            descricao=(
                "D001: ação financeira imediata executável agora (Gate 2), com "
                "valor ainda não apurado — EC-48, teste sintético."
            ),
            gate_origem=2,
            VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO,
        )
        return dataclasses.replace(
            particao_real,
            ORDEM_ACOES=(*particao_real.ORDEM_ACOES, acao_com_valor_desconhecido),
        )

    monkeypatch.setattr(
        motor_mod, "particionar_elegibilidade", _particionar_com_acao_de_valor_desconhecido
    )

    snapshot = calcular_plano(estado, _parametros)

    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))


@pytest.mark.regra
def test_EC49_todas_as_dividas_sem_necessidade_imediata_com_recursos_positivos(
    _parametros: Parametros,
) -> None:
    """`EC-49`: todas as dívidas do inventário contribuem `NECESSIDADE_
    IMEDIATA_DIVIDA=0` — aqui porque `GAB-A` bloqueia as duas no Gate 1
    (`SALDO_DEVEDOR_ATUAL=DESCONHECIDO`, ramo 1 de `NECESSIDADE_IMEDIATA_
    DIVIDA`, sempre `dinheiro(0)` CONHECIDO, nunca `DESCONHECIDO`) — mesmo
    com `DINHEIRO_DISPONIVEL > 0` (recursos recomendados positivos),
    `ATAQUE_IMEDIATO_RECOMENDADO = MIN(0, recursos) = 0`.

    **Distinção do caminho lógico de `EC-48` (mesmo resultado numérico,
    origem diferente).** Em `EC-48`, `NECESSIDADE_FINANCEIRA_IMEDIATA_
    ELEGIVEL` é `DESCONHECIDO` (decisão adiada, propagada) e a trava de
    `_compor_ATAQUE_IMEDIATO_RECOMENDADO` intercepta ANTES de qualquer
    função de `ataque_imediato.py` ser chamada. Aqui em `EC-49`, o elegível
    é `dinheiro(0)` CONHECIDO (soma de parcelas todas `0`, nenhuma
    `DESCONHECIDO` na cadeia) — a trava de propagação nunca é acionada; as
    sete funções rodam normalmente e é o próprio `MIN(0, recursos) = 0`
    (`calcular_ATAQUE_IMEDIATO_RECOMENDADO`, `EC-28`) que produz o zero.
    "Sei que é zero" (`EC-49`) é estruturalmente diferente de "não sei
    quanto é" (`EC-48`), mesmo que os dois cheguem no mesmo `dinheiro(0)`
    final."""
    estado = dataclasses.replace(carregar_gab_a(), DINHEIRO_DISPONIVEL=dinheiro("1500"))

    snapshot = calcular_plano(estado, _parametros)

    assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
