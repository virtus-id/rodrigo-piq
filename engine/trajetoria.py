"""Trajetória isolada de uma única dívida — RF-05 · §11.1 · AC-47 · EC-13.

`simular_trajetoria_isolada(chave)` evolui uma dívida mês a mês, aplicando
juros e depois abatendo o pagamento do mês, até `SALDO = 0` ou até estourar
`ChaveTrajetoria.HORIZONTE`. É o bloco de simulação que sustenta o benefício
marginal da Avalanche (§11.1): comparar a trajetória **A** (sem ataque
extraordinário) contra a **B** (com `DELTA` aplicado agora) exige rodar esta
função duas vezes, uma por trajetória, cada uma com sua própria `DELTA`.

**Horizonte próprio de cada trajetória (`BURACO-07`, Definições §2, `AC-47`).**
A função soma o desembolso até o **próprio** `SALDO = 0` da trajetória que
recebeu — nunca até o menor prazo de uma trajetória irmã comparada em outro
lugar. É por isso que `simular_trajetoria_isolada` não conhece a existência de
uma segunda trajetória: cada chamada é unidimensional, e é o chamador (futuro
`engine/beneficio_marginal.py`, T-39) quem invoca a função duas vezes — uma
para A, outra para B — e compara os dois `DESEMBOLSO_FUTURO` resultantes.
Nenhum horizonte fixo (60, 120 meses) é aceitável: o único teto é
`ChaveTrajetoria.HORIZONTE`, que o CHAMADOR desta função deriva de
`P_HORIZONTE_MAXIMO_SIMULACAO` (em anos) × 12 — esta função em si não lê
`Parametros`, só o campo já pronto na chave, para permanecer pura (§1 do
plano: "engine/ não lê relógio, não lê rede").

**Delta só no primeiro mês — decisão de leitura da fonte.** A §11.1 descreve
duas trajetórias para o teste de benefício marginal: "A sem pagamento
extraordinário; B com DELTA_TESTE_AVALANCHE aplicado **agora**". "Agora" é o
mês em que a simulação começa — um evento pontual, não uma recorrência mensal.
Isso é reforçado pela "Exceção intramês" da mesma seção, que fala em aplicar
`DELTA_TESTE_AVALANCHE_RESIDUO` a cada reranqueamento — ou seja, cada
simulação de trajetória B testa o efeito de UM aporte extra no momento em que
é calculada, não de um aporte que se repete todo mês daquela trajetória (isso
inflaria artificialmente o benefício marginal e duplicaria o papel do ataque
mensal recorrente, que já é `PAGAMENTO_MENSAL_EFETIVO` recalculado a cada
ranqueamento pelo ciclo mensal real). Adotado: `DELTA` soma-se ao pagamento
apenas do primeiro mês simulado (`mes == 1`); nos meses seguintes, paga-se
só `PAGAMENTO_MENSAL_EFETIVO`. Nenhuma redação da fonte contradiz esta leitura
— não há ambiguidade a registrar em Open Questions.

**Horizonte próprio vs. horizonte comum (§11.1, permitido mas não usado
aqui).** A spec permite, como alternativa matematicamente equivalente, somar
as duas trajetórias no mesmo laço até o maior prazo, com
`DESEMBOLSO_MENSAL = 0` após cada quitação — mas essa é uma otimização de
CUSTO (ajuda o orçamento de desempenho da memoização, §10 do plano) que exige
comparar duas trajetórias ao mesmo tempo. Esta tarefa (T-36) modela só a
trajetória ISOLADA, sem o contexto de comparação: a versão mais direta é
parar assim que a própria dívida quitar, sem simular meses vazios adicionais.

**Memoização (T-37).** `simular_trajetoria_isolada`, exportada por este
módulo, é a versão pública memoizada (`functools.lru_cache`) de
`_simular_trajetoria_isolada_sem_cache`, que contém toda a lógica descrita
acima. Ver a docstring de `simular_trajetoria_isolada` para a justificativa
da separação e `limpar_cache_trajetoria()` para o mecanismo de limpeza entre
execuções do motor.

REGRAS: RF-05, AC-47, EC-13, §11.1
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import localcontext
from functools import cache
from typing import Final

from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import Dinheiro, Meses, Taxa

REGRAS: Final[tuple[str, ...]] = ("RF-05", "AC-47", "EC-13", "§11.1")


@dataclass(frozen=True, slots=True)
class ChaveTrajetoria:
    """Entrada de `simular_trajetoria_isolada` — hasheável por valor.

    `Decimal` compara exato (nunca por aproximação binária), então duas
    instâncias com os mesmos valores produzem o mesmo hash e são iguais —
    condição necessária para a memoização de `simular_trajetoria_isolada`
    (T-37), garantida aqui só pelo `frozen=True, slots=True` (RF-12, §4 do
    plano).

    `HORIZONTE` já vem pronto, calculado pelo CHAMADOR a partir de
    `P_HORIZONTE_MAXIMO_SIMULACAO` (anos) × 12 — esta função não lê
    `Parametros` para permanecer pura.
    """

    DIVIDA_ID: str
    SALDO_DEVEDOR_ATUAL: Dinheiro
    TAXA_EFETIVA_MENSAL_NORMALIZADA: Taxa
    PAGAMENTO_MENSAL_EFETIVO: Dinheiro
    DELTA: Dinheiro
    HORIZONTE: Meses


@dataclass(frozen=True, slots=True)
class Trajetoria:
    """Saída de `simular_trajetoria_isolada` — §11.1, EC-13."""

    DESEMBOLSO_FUTURO: Dinheiro
    MESES_ATE_QUITACAO: Meses | None  # None = estourou o horizonte (EC-13)
    ESTOUROU_HORIZONTE: bool


def _simular_trajetoria_isolada_sem_cache(chave: ChaveTrajetoria) -> Trajetoria:
    """Evolui a dívida de `chave` mês a mês até `SALDO = 0` ou até estourar
    `chave.HORIZONTE`. Pura e determinística: mesma `ChaveTrajetoria`, mesmo
    resultado (nenhum estado global, nenhum relógio, nenhum I/O).

    A cada mês: `saldo *= (1 + TAXA_EFETIVA_MENSAL_NORMALIZADA)`, depois
    abate-se o pagamento do mês. O pagamento do PRIMEIRO mês é
    `PAGAMENTO_MENSAL_EFETIVO + DELTA` (o ataque extraordinário "agora",
    §11.1 — ver decisão na docstring do módulo); dos meses seguintes, só
    `PAGAMENTO_MENSAL_EFETIVO`. O último pagamento nunca excede o saldo
    remanescente — `DESEMBOLSO_FUTURO` soma o que foi efetivamente pago, não
    o valor cheio da parcela (EC-13, "encerra... e sinaliza" pressupõe que o
    desembolso é sempre o realmente saído do bolso, nunca um valor teórico).

    AC-47/BURACO-07: esta função soma até o PRÓPRIO `SALDO = 0` da dívida
    recebida em `chave` — nunca trunca no prazo de uma trajetória irmã, e o
    único teto é `chave.HORIZONTE` (evitar loop infinito em dívida que nunca
    amortiza porque o pagamento não cobre nem os juros do mês).
    """
    with localcontext(CONTEXTO_MOTOR):
        saldo = chave.SALDO_DEVEDOR_ATUAL

        # Caso-limite: saldo já zerado ou negativo na entrada — quitação
        # instantânea, sem desembolso e sem simular nenhum mês.
        if saldo <= dinheiro(0):
            return Trajetoria(
                DESEMBOLSO_FUTURO=dinheiro(0),
                MESES_ATE_QUITACAO=0,
                ESTOUROU_HORIZONTE=False,
            )

        desembolso_futuro = dinheiro(0)
        um = dinheiro(1)

        for mes in range(1, chave.HORIZONTE + 1):
            saldo = saldo * (um + chave.TAXA_EFETIVA_MENSAL_NORMALIZADA)

            pagamento_nominal = chave.PAGAMENTO_MENSAL_EFETIVO
            if mes == 1:
                # §11.1: o DELTA é o ataque extraordinário aplicado "agora"
                # — evento único do primeiro mês, não recorrente (ver
                # decisão documentada na docstring do módulo).
                pagamento_nominal = pagamento_nominal + chave.DELTA

            # O pagamento efetivamente feito nunca excede o saldo
            # remanescente: o último pagamento só cobre o que falta, sem
            # pagar a mais (EC-13/§11.1: DESEMBOLSO_FUTURO é o que
            # realmente saiu, não o que "deveria" ter sido pago).
            pagamento_efetivo = min(pagamento_nominal, saldo)
            if pagamento_efetivo < dinheiro(0):
                pagamento_efetivo = dinheiro(0)

            saldo = saldo - pagamento_efetivo
            desembolso_futuro = desembolso_futuro + pagamento_efetivo

            if saldo <= dinheiro(0):
                return Trajetoria(
                    DESEMBOLSO_FUTURO=desembolso_futuro,
                    MESES_ATE_QUITACAO=mes,
                    ESTOUROU_HORIZONTE=False,
                )

        # EC-13: horizonte esgotado sem quitar. DESEMBOLSO_FUTURO é a soma
        # de tudo efetivamente pago até aqui — nunca uma estimativa do que
        # faltaria além do horizonte.
        return Trajetoria(
            DESEMBOLSO_FUTURO=desembolso_futuro,
            MESES_ATE_QUITACAO=None,
            ESTOUROU_HORIZONTE=True,
        )


@cache
def simular_trajetoria_isolada(chave: ChaveTrajetoria) -> Trajetoria:
    """API pública memoizada de `_simular_trajetoria_isolada_sem_cache` — T-37.

    **Por que `functools.cache` e não outro mecanismo.** `functools.cache` é
    `lru_cache(maxsize=None)` — cache sem limite de tamanho, forma preferida
    pelo lint do projeto (`ruff` UP033) desde Python 3.9. `ChaveTrajetoria` já
    é `frozen=True, slots=True` (T-36): hasheável por valor, com `Decimal`
    comparado exato (nunca por aproximação binária) — condição necessária e
    suficiente para chavear corretamente sem precisar de normalização
    adicional. É a solução mais simples e mais idiomática em Python para este
    formato de função pura unária; introduzir um dicionário manual só
    duplicaria o que a biblioteca padrão já garante.

    **Por que a função original foi renomeada para `_..._sem_cache`, em vez de
    o cache ficar embutido nela.** T-38 precisa comparar, campo a campo, o
    resultado COM cache contra o resultado SEM cache, para provar que a
    memoização não é observável (§7 e §10 do plano: "precisa ser
    indistinguível de sua ausência"). Se o `lru_cache` decorasse a única
    função existente, não haveria como chamar a versão pura isoladamente sem
    reconstruir a lógica em duplicata. Com o wrapper, `simular_trajetoria_isolada`
    continua sendo o único nome público e funcional que T-38/T-39
    (`calcular_beneficio_marginal`) consomem; `_simular_trajetoria_isolada_sem_cache`
    é detalhe de implementação (prefixo `_`), mas permanece importável de
    dentro do pacote `engine` — uso aceito em Python para teste interno, sem
    fazer parte da API pública oficial do módulo.

    **Escopo de execução.** O cache é module-level (`lru_cache` guarda estado
    no objeto função) e por isso pode vazar entre execuções distintas do
    motor se não for limpo. `limpar_cache_trajetoria()`, abaixo, existe para
    isso: o futuro `calcular_plano` (T-68) deve chamá-la no início de cada
    execução, garantindo que o cache nunca carregue resíduo de uma chamada
    anterior — mesmo requisito de determinismo do `decimal.localcontext()`
    (§7 do plano, "State Management").

    Pura no mesmo sentido da função interna: dado o mesmo `chave`, sempre
    produz o mesmo `Trajetoria` — cache "puro", o único global mutável restante
    permitido pelo plano ("Nenhum global mutável além do cache puro").
    """
    return _simular_trajetoria_isolada_sem_cache(chave)


def limpar_cache_trajetoria() -> None:
    """Zera o cache de `simular_trajetoria_isolada` — T-37.

    Deve ser chamada no início de cada execução do motor (`calcular_plano`,
    T-68) para que o cache não vaze entre execuções distintas: mesma garantia
    de isolamento que `decimal.localcontext()` dá ao contexto decimal (§7 do
    plano, tabela "State Management"). Sem esta chamada, uma segunda execução
    do motor no mesmo processo poderia reaproveitar silenciosamente resultados
    de uma carteira anterior — o cache deixaria de ser "indistinguível de sua
    ausência".
    """
    simular_trajetoria_isolada.cache_clear()
