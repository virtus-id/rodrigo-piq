"""Teste isolado da cadeia de desempate `O-05` — RF-06 · AC-02 · T-52.

Complementa `tests/regras/test_bola_de_neve.py` (T-51), que já cobre cada
nível de `O-05` isoladamente (`test_O05_nivel1_maior_valor_fluxo_liberado`,
`test_O05_nivel2_maior_custo_financeiro`, `test_O05_nivel3_maior_peso_
emocional`, `test_O05_nivel4_desempate_final_por_divida_id`). Este módulo não
duplica essa cobertura nível a nível: é um teste de integração mais simples,
com várias dívidas empatando PARCIALMENTE nos primeiros critérios ao mesmo
tempo, demonstrando a cadeia completa (`O-05`, os quatro níveis) resolvendo
em uma única ordenação fim a fim via `criar_selecionar_alvo_bola_de_neve`.

REGRAS: RF-06, O-05, AC-02
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao
from engine.estado import TIPO_DIVIDA, Divida
from engine.metodos.bola_de_neve import criar_selecionar_alvo_bola_de_neve
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.tipos import STATUS_DIVIDA, STATUS_VALIDADE_PROPOSTA, SimNaoTalvez
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _parametros_reais() -> Parametros:
    return FonteParametrosArquivo().carregar("1.0.1")


def _divida(**overrides: object) -> Divida:
    """Mesmo padrão de `test_bola_de_neve.py::_divida` — dívida completa e
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


def _estado(*, saldos: dict[str, Decimal]) -> EstadoSimulacao:
    return EstadoSimulacao(
        mes=1,
        saldos=saldos,
        quitadas=frozenset(),
        DIVIDA_ALVO_ATUAL=None,
        CAPACIDADE_ATAQUE_M=dinheiro("100"),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
        DESEMBOLSO_ACUMULADO=dinheiro("0"),
    )


@pytest.mark.regra
def test_O05_cadeia_de_desempate_da_bola_de_neve() -> None:
    """`O-05`: cadeia completa de desempate fim a fim, com quatro dívidas de
    `VALOR_RELEVANTE_PARA_QUITACAO` IGUAL (mesmo saldo), empatando
    PARCIALMENTE nos primeiros níveis, na ordem exata da cadeia:

    ```
    Desempates, nesta ordem: maior VALOR_FLUXO_LIBERADO; maior custo
    financeiro; maior PESO_EMOCIONAL; DIVIDA_ID como desempate técnico final.
    ```

    - D-BAIXO: perde já no nível 1 (`VALOR_FLUXO_LIBERADO`/
      `PAGAMENTO_MENSAL_EFETIVO` menor que as outras três).
    - D-MEDIO: empata com D-BAIXO... não, empata nível 1 com D-ALTO-A/
      D-ALTO-B, mas perde no nível 2 (custo financeiro/
      `TAXA_EFETIVA_MENSAL_NORMALIZADA` menor).
    - D-ALTO-A e D-ALTO-B: empatam nos níveis 1 e 2 entre si — decidido no
      nível 3 (`PESO_EMOCIONAL`); D-ALTO-B tem peso maior e vence.
    - Uma quinta dívida, D-EMPATE-TOTAL, empata em TODOS os três primeiros
      níveis com D-ALTO-B — só o nível 4 (`DIVIDA_ID`) resolve, e
      "D-ALTO-B" < "D-EMPATE-TOTAL" lexicograficamente, então D-ALTO-B segue
      vencendo mesmo com o empate total.

    A ordem final esperada de ataque (`O-04` crescente, com `O-05` resolvendo
    o empate de valor relevante) é: D-ALTO-B primeiro, D-EMPATE-TOTAL em
    segundo (nível 4 os desempata entre si), D-ALTO-A em terceiro, D-MEDIO em
    quarto, D-BAIXO por último.
    """
    comuns = dict(SALDO_DEVEDOR_ATUAL=dinheiro("1000"), VALOR_QUITACAO_HOJE=dinheiro("1000"))

    d_baixo = _divida(
        DIVIDA_ID="D-BAIXO",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("50"),  # perde no nível 1
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.20"),
        PESO_EMOCIONAL=10,
        **comuns,
    )
    d_medio = _divida(
        DIVIDA_ID="D-MEDIO",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),  # empata nível 1 com os "ALTO"
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.03"),  # perde no nível 2
        PESO_EMOCIONAL=10,
        **comuns,
    )
    d_alto_a = _divida(
        DIVIDA_ID="D-ALTO-A",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),  # empata nível 1
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.10"),  # empata nível 2
        PESO_EMOCIONAL=3,  # perde no nível 3
        **comuns,
    )
    d_alto_b = _divida(
        DIVIDA_ID="D-ALTO-B",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),  # empata nível 1
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.10"),  # empata nível 2
        PESO_EMOCIONAL=9,  # vence no nível 3
        **comuns,
    )
    d_empate_total = _divida(
        DIVIDA_ID="D-EMPATE-TOTAL",
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),  # empata nível 1
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.10"),  # empata nível 2
        PESO_EMOCIONAL=9,  # empata nível 3 com D-ALTO-B — só o nível 4 resolve
        **comuns,
    )

    dividas = {
        "D-MEDIO": d_medio,
        "D-EMPATE-TOTAL": d_empate_total,
        "D-BAIXO": d_baixo,
        "D-ALTO-A": d_alto_a,
        "D-ALTO-B": d_alto_b,
    }
    sel = criar_selecionar_alvo_bola_de_neve(dividas, _parametros_reais())
    saldos = {divida_id: dinheiro("1000") for divida_id in dividas}

    ordem_esperada = ["D-ALTO-B", "D-EMPATE-TOTAL", "D-ALTO-A", "D-MEDIO", "D-BAIXO"]
    quitadas: set[str] = set()
    ordem_obtida: list[str] = []
    for _ in ordem_esperada:
        estado = EstadoSimulacao(
            mes=1,
            saldos=saldos,
            quitadas=frozenset(quitadas),
            DIVIDA_ALVO_ATUAL=None,
            CAPACIDADE_ATAQUE_M=dinheiro("100"),
            ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro("0"),
            DESEMBOLSO_ACUMULADO=dinheiro("0"),
        )
        escolhido = sel(estado, dinheiro("100"))
        assert escolhido is not None
        ordem_obtida.append(escolhido.DIVIDA_ID)
        quitadas.add(escolhido.DIVIDA_ID)

    assertar_exato(tuple(ordem_obtida), tuple(ordem_esperada))
