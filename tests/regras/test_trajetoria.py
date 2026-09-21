"""Testes de `simular_trajetoria_isolada` — RF-05, AC-47, EC-13, §11.1, T-38.

Formaliza a verificação ad-hoc que T-36 (implementação) e T-37 (memoização) já
fizeram e descartaram, cobrindo os quatro critérios de aceite de T-38:

1. `test_AC47_cada_trajetoria_ate_seu_proprio_saldo_zero` — duas trajetórias
   com prazos bem diferentes, provando que cada uma soma até seu PRÓPRIO
   `SALDO = 0`, sem truncar no menor prazo (`AC-47`, `BURACO-07`).
2. `test_cache_e_sem_cache_produzem_resultado_identico_campo_a_campo` — uma
   carteira sintética de `ChaveTrajetoria` variadas, provando que ligar o
   cache é indistinguível de não ligá-lo (§7/§10 do plano).
3. `test_horizonte_comum_com_desembolso_zero_apos_quitacao_e_equivalente` —
   prova, por simulação alternativa escrita no próprio teste (sem tocar
   `engine/trajetoria.py`), que "parar na quitação" (o que a implementação
   faz) é matematicamente equivalente a "continuar até um horizonte comum,
   somando 0 após a quitação" (a alternativa permitida por `BURACO-07`).
4. `test_EC13_horizonte_estourado_sinaliza` — dívida cujo pagamento não cobre
   nem os juros do mês: nunca amortiza, estoura `HORIZONTE` e sinaliza.
"""

from decimal import Decimal, localcontext

import pytest

from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.trajetoria import (
    ChaveTrajetoria,
    Trajetoria,
    _simular_trajetoria_isolada_sem_cache,
    limpar_cache_trajetoria,
    simular_trajetoria_isolada,
)
from tests.conftest import assertar_exato, assertar_monetario


@pytest.fixture(autouse=True)
def _cache_limpo() -> None:
    """Isola cada teste: o cache de `simular_trajetoria_isolada` é global
    module-level (T-37) e não pode vazar resultado de um teste para outro."""
    limpar_cache_trajetoria()


@pytest.mark.regra
def test_AC47_cada_trajetoria_ate_seu_proprio_saldo_zero() -> None:
    """AC-47/BURACO-07: dadas duas trajetórias com prazos bem diferentes —
    uma quita em 3 meses, outra em 24 —, cada uma é somada até seu PRÓPRIO
    `SALDO = 0`, nunca truncada no menor prazo nem em um horizonte fixo.

    `MESES_ATE_QUITACAO` usa `assertar_exato` (RF-12/§5 do config: número de
    meses é tolerância zero). `DESEMBOLSO_FUTURO` usa `assertar_monetario`
    porque é um valor monetário ACUMULADO ao longo de meses de simulação —
    mesma categoria de "valor monetário acumulado" da tolerância de
    homologação (± R$ 0,05), ainda que o cálculo aqui seja determinístico e
    não envolva soma de parcelas arredondadas de fato: o helper correto para
    a NATUREZA do dado (dinheiro somado mês a mês) é `assertar_monetario`,
    não o tipo do dado em si — usar `assertar_exato` misturaria o critério
    "monetário acumulado" com "coincidiu por não haver arredondamento no
    caminho", o que quebraria na primeira mudança de parâmetro que introduza
    fração não-exata.
    """
    curta = ChaveTrajetoria(
        DIVIDA_ID="D-CURTA",
        SALDO_DEVEDOR_ATUAL=dinheiro("1000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.02"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("400"),
        DELTA=dinheiro("0"),
        HORIZONTE=120,
    )
    longa = ChaveTrajetoria(
        DIVIDA_ID="D-LONGA",
        SALDO_DEVEDOR_ATUAL=dinheiro("9000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.015"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("450"),
        DELTA=dinheiro("0"),
        HORIZONTE=120,
    )

    resultado_curta = simular_trajetoria_isolada(curta)
    resultado_longa = simular_trajetoria_isolada(longa)

    # Prazos bem diferentes — a longa NÃO é truncada no prazo da curta.
    assertar_exato(resultado_curta.MESES_ATE_QUITACAO, 3)
    assertar_exato(resultado_longa.MESES_ATE_QUITACAO, 24)
    assertar_exato(resultado_curta.ESTOUROU_HORIZONTE, False)
    assertar_exato(resultado_longa.ESTOUROU_HORIZONTE, False)

    # Desembolsos calculados fora da função sob teste — aritmética decimal
    # direta, mês a mês, replicando §11.1 sem reutilizar a implementação.
    assertar_monetario(resultado_curta.DESEMBOLSO_FUTURO, dinheiro("1037.048"))
    assertar_monetario(
        resultado_longa.DESEMBOLSO_FUTURO, dinheiro("10780.44094949047273492983787030420")
    )


@pytest.mark.regra
def test_cache_e_sem_cache_produzem_resultado_identico_campo_a_campo() -> None:
    """§7/§10 do plano: ligar o cache (`simular_trajetoria_isolada`) precisa
    ser indistinguível de não ligá-lo (`_simular_trajetoria_isolada_sem_cache`).
    Carteira sintética de 8 `ChaveTrajetoria` distintas, cobrindo taxa zero,
    `DELTA` não-nulo, prazos curtos/longos e o caso de horizonte estourado
    (EC-13) — comparação `Trajetoria` completa (`==` de dataclass frozen
    compara os três campos: `DESEMBOLSO_FUTURO`, `MESES_ATE_QUITACAO`,
    `ESTOUROU_HORIZONTE`)."""
    carteira = [
        # taxa zero — amortização puramente linear
        ChaveTrajetoria(
            "D01", dinheiro("1200"), Decimal("0"), dinheiro("300"), dinheiro("0"), 60
        ),
        # DELTA não-nulo no primeiro mês
        ChaveTrajetoria(
            "D02", dinheiro("1000"), Decimal("0.02"), dinheiro("400"), dinheiro("200"), 120
        ),
        ChaveTrajetoria(
            "D03", dinheiro("9000"), Decimal("0.015"), dinheiro("450"), dinheiro("1000"), 120
        ),
        # prazo longo, sem delta
        ChaveTrajetoria(
            "D04", dinheiro("9000"), Decimal("0.015"), dinheiro("450"), dinheiro("0"), 120
        ),
        # prazo curtíssimo (quita instantaneamente: pagamento > saldo)
        ChaveTrajetoria(
            "D05", dinheiro("50"), Decimal("0.03"), dinheiro("500"), dinheiro("0"), 60
        ),
        # saldo já zerado na entrada — caso-limite de quitação instantânea
        ChaveTrajetoria(
            "D06", dinheiro("0"), Decimal("0.04"), dinheiro("300"), dinheiro("0"), 60
        ),
        # horizonte estourado (EC-13): pagamento não cobre os juros
        ChaveTrajetoria(
            "D07", dinheiro("5000"), Decimal("0.05"), dinheiro("100"), dinheiro("0"), 12
        ),
        # taxa alta, delta grande, horizonte apertado
        ChaveTrajetoria(
            "D08", dinheiro("20000"), Decimal("0.03"), dinheiro("600"), dinheiro("5000"), 240
        ),
    ]

    for chave in carteira:
        com_cache = simular_trajetoria_isolada(chave)
        sem_cache = _simular_trajetoria_isolada_sem_cache(chave)

        assertar_exato(com_cache, sem_cache)
        assertar_exato(com_cache.DESEMBOLSO_FUTURO, sem_cache.DESEMBOLSO_FUTURO)
        assertar_exato(com_cache.MESES_ATE_QUITACAO, sem_cache.MESES_ATE_QUITACAO)
        assertar_exato(com_cache.ESTOUROU_HORIZONTE, sem_cache.ESTOUROU_HORIZONTE)

    # Chamar de novo (agora vindo do cache, não recalculado) não muda nada.
    for chave in carteira:
        com_cache_repetido = simular_trajetoria_isolada(chave)
        sem_cache = _simular_trajetoria_isolada_sem_cache(chave)
        assertar_exato(com_cache_repetido, sem_cache)


def _simula_horizonte_comum(
    chave: ChaveTrajetoria, horizonte_comum: int
) -> Trajetoria:
    """Simulação ALTERNATIVA escrita só para este teste de verificação —
    NÃO faz parte de `engine/trajetoria.py`. Implementa a variante que
    BURACO-07/§11.1 permite como equivalente: continuar até um horizonte
    comum (maior que o necessário para esta dívida), somando
    `DESEMBOLSO_MENSAL = 0` em todo mês posterior à quitação, em vez de
    parar assim que `SALDO = 0` (que é o que a implementação de produção
    faz). Replica a mesma mecânica mês a mês de
    `_simular_trajetoria_isolada_sem_cache`, mas sem o `return` antecipado.
    """
    with localcontext(CONTEXTO_MOTOR):
        saldo = chave.SALDO_DEVEDOR_ATUAL
        if saldo <= dinheiro(0):
            return Trajetoria(dinheiro(0), 0, False)

        desembolso_futuro = dinheiro(0)
        meses_ate_quitacao: int | None = None
        um = dinheiro(1)
        quitada = False

        for mes in range(1, horizonte_comum + 1):
            if quitada:
                # Pós-quitação: DESEMBOLSO_MENSAL = 0 — a alternativa
                # permitida por BURACO-07, nunca aplicada na produção.
                continue

            saldo = saldo * (um + chave.TAXA_EFETIVA_MENSAL_NORMALIZADA)

            pagamento_nominal = chave.PAGAMENTO_MENSAL_EFETIVO
            if mes == 1:
                pagamento_nominal = pagamento_nominal + chave.DELTA

            pagamento_efetivo = min(pagamento_nominal, saldo)
            if pagamento_efetivo < dinheiro(0):
                pagamento_efetivo = dinheiro(0)

            saldo = saldo - pagamento_efetivo
            desembolso_futuro = desembolso_futuro + pagamento_efetivo

            if saldo <= dinheiro(0):
                quitada = True
                meses_ate_quitacao = mes

        return Trajetoria(
            DESEMBOLSO_FUTURO=desembolso_futuro,
            MESES_ATE_QUITACAO=meses_ate_quitacao,
            ESTOUROU_HORIZONTE=not quitada,
        )


@pytest.mark.regra
def test_horizonte_comum_com_desembolso_zero_apos_quitacao_e_equivalente() -> None:
    """BURACO-07/§11.1: "é permitido usar horizonte comum igual ao maior dos
    dois prazos, com DESEMBOLSO_MENSAL=0 após cada quitação, desde que o
    resultado seja matematicamente equivalente". `simular_trajetoria_isolada`
    (T-36) adota a abordagem de PARAR na quitação, sem simular meses vazios.
    Este teste prova a equivalência matemática entre as duas abordagens:
    roda a trajetória de produção (que para) e a alternativa de horizonte
    comum (`_simula_horizonte_comum`, definida só neste arquivo, que continua
    somando 0 após a quitação) para a MESMA `ChaveTrajetoria`, com o
    horizonte comum estritamente maior que `MESES_ATE_QUITACAO` — e confirma
    que `DESEMBOLSO_FUTURO` bate exatamente entre as duas.
    """
    chave = ChaveTrajetoria(
        DIVIDA_ID="D-EQUIVALENCIA",
        SALDO_DEVEDOR_ATUAL=dinheiro("9000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.015"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("450"),
        DELTA=dinheiro("1000"),
        HORIZONTE=120,
    )

    resultado_producao = simular_trajetoria_isolada(chave)
    assert resultado_producao.MESES_ATE_QUITACAO is not None
    assert not resultado_producao.ESTOUROU_HORIZONTE

    # Horizonte comum bem maior que o necessário — simula meses "vazios"
    # depois da quitação, como uma trajetória irmã mais longa exigiria.
    horizonte_comum = resultado_producao.MESES_ATE_QUITACAO + 36
    resultado_horizonte_comum = _simula_horizonte_comum(chave, horizonte_comum)

    # Equivalência matemática exigida por BURACO-07: mesmo desembolso e
    # mesmo mês de quitação, apesar das duas abordagens serem diferentes
    # (uma para no SALDO=0, a outra continua somando 0).
    assertar_exato(
        resultado_horizonte_comum.MESES_ATE_QUITACAO,
        resultado_producao.MESES_ATE_QUITACAO,
    )
    assertar_exato(
        resultado_horizonte_comum.ESTOUROU_HORIZONTE,
        resultado_producao.ESTOUROU_HORIZONTE,
    )
    assertar_monetario(
        resultado_horizonte_comum.DESEMBOLSO_FUTURO,
        resultado_producao.DESEMBOLSO_FUTURO,
    )
    # Aqui, sem nenhuma fonte de arredondamento fracionário no caminho, as
    # duas abordagens produzem o mesmo Decimal bit a bit — a equivalência é
    # exata, não apenas dentro da tolerância de homologação.
    assertar_exato(
        resultado_horizonte_comum.DESEMBOLSO_FUTURO,
        resultado_producao.DESEMBOLSO_FUTURO,
    )


@pytest.mark.regra
def test_EC13_horizonte_estourado_sinaliza() -> None:
    """EC-13: dívida cujo pagamento mensal (R$ 100) não cobre nem os juros do
    mês (5% sobre R$ 5.000 = R$ 250) — o saldo cresce a cada mês, nunca
    amortiza. Com `HORIZONTE` pequeno (12, para não gastar tempo de teste),
    a simulação encerra sem quitar e sinaliza `ESTOUROU_HORIZONTE = True`,
    `MESES_ATE_QUITACAO = None` — nunca um loop infinito, nunca uma
    estimativa do que faltaria além do horizonte."""
    chave = ChaveTrajetoria(
        DIVIDA_ID="D-NUNCA-AMORTIZA",
        SALDO_DEVEDOR_ATUAL=dinheiro("5000"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.05"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("100"),
        DELTA=dinheiro("0"),
        HORIZONTE=12,
    )

    resultado = simular_trajetoria_isolada(chave)

    assertar_exato(resultado.ESTOUROU_HORIZONTE, True)
    assertar_exato(resultado.MESES_ATE_QUITACAO, None)
    # DESEMBOLSO_FUTURO é a soma do que foi efetivamente pago nos 12 meses
    # (R$ 100 por mês, todo mês — o pagamento nunca chega a exceder o saldo
    # remanescente, que só cresce): 12 × R$ 100 = R$ 1.200.
    assertar_monetario(resultado.DESEMBOLSO_FUTURO, dinheiro("1200"))
