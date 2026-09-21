"""Seleção de alvo do método Avalanche — RF-05 · §5.1, §11.1 · O-01..O-03 ·
AC-19 · T-49.

`O-01..O-03` (`piq-app-spec.md` §5.1, citada por `specs/motor-calculo.spec.md`
RF-05): a Avalanche ordena as dívidas elegíveis por
`BENEFICIO_MARGINAL_AMORTIZACAO` decrescente e ataca a de maior benefício
(`O-01`). O alvo permanece fixo até ser quitado ou até ocorrer um evento
externo (`O-02`) — reranquear "por hábito" a cada mês é proibido (`R-02`,
`AC-13`). Havendo resíduo dentro do próprio mês, o reranqueamento usa o mesmo
critério de ordenação, com o delta do resíduo em vez da capacidade cheia
(`O-03`, `AC-14`).

**Divisão de responsabilidade — quem decide QUANDO chamar, quem decide QUEM
escolher.** `engine/ciclo_mensal.py::executar_mes` (T-42/T-43) já implementa
o "quando": `sel()` só é invocada no bootstrap (`DIVIDA_ALVO_ATUAL is None`,
delta = capacidade cheia) e a cada rodada do laço de cascata do resíduo
(delta = resíduo restante) — ver docstring daquele módulo, "`SelecionarAlvo`
— quando é chamada". Em QUALQUER outro caso (alvo já definido e ainda não
quitado, `M-05`), `executar_mes` sequer chama `sel()`: o alvo atravessa o mês
sem reranqueamento. Este módulo NÃO duplica essa decisão — implementa apenas
o "quem": dada uma carteira e um delta, qual é a melhor dívida elegível AGORA.

A fixação do alvo (`O-02`) é, portanto, garantida por DOIS mecanismos
complementares, não um só: (a) estruturalmente, porque `executar_mes` não
chama `sel()` quando o alvo já está definido e não foi quitado (`M-05`); e
(b) defensivamente, dentro desta própria função — se ela FOR chamada com
`estado.DIVIDA_ALVO_ATUAL` apontando para uma dívida que ainda não está em
`estado.quitadas`, devolve essa mesma dívida sem recalcular a ordenação do
zero. Essa segunda camada existe porque o tipo `SelecionarAlvo` (`Callable
[[EstadoSimulacao, Dinheiro], Divida | None]`) não impede, por si só, que um
chamador futuro invoque a função com um alvo ainda vigente — a função pura
não deve depender silenciosamente de uma garantia externa que não pode
verificar. Hoje, `executar_mes` sempre passa `DIVIDA_ALVO_ATUAL=None` nas
duas ocasiões em que chama `sel()` (bootstrap e cascata), então este ramo é
defensivo, não exercitado pelo fluxo atual — mas faz parte do contrato de
"alvo fixo" que a função pura sozinha também deve honrar.

**Fábrica, não função direta — por que.** `SelecionarAlvo` é exatamente
`Callable[[EstadoSimulacao, Dinheiro], Divida | None]` (`engine/
ciclo_mensal.py`) — sem `Mapping[str, Divida]` nem `Parametros` na
assinatura. `EstadoSimulacao.saldos` é só `Mapping[str, Dinheiro]`: não
carrega `TAXA_EFETIVA_MENSAL_NORMALIZADA`, `PAGAMENTO_MENSAL_EFETIVO`,
`VALOR_QUITACAO_HOJE` nem os demais campos de `Divida` que
`calcular_beneficio_marginal`/`compor_VALOR_RELEVANTE_PARA_QUITACAO`
exigem — só o inventário completo (`Mapping[str, Divida]`, mesma extensão já
documentada em `executar_mes`) e `Parametros` (para
`P_HORIZONTE_MAXIMO_SIMULACAO`) têm esse dado. Não há como satisfazer o tipo
exato de `SelecionarAlvo` com uma função de módulo que também precise desses
dois parâmetros extras. `criar_selecionar_alvo_avalanche(dividas, p)` resolve
isso devolvendo um `Callable` fechado sobre `dividas`/`p` via closure — a
função devolvida É `SelecionarAlvo`, sem nenhuma mudança de assinatura, sem
duplicar o inventário dentro de `EstadoSimulacao`.

REGRAS: RF-05, O-01, O-02, O-03, AC-19, §5.1, §11.1
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from engine.beneficio_marginal import calcular_beneficio_marginal
from engine.ciclo_mensal import EstadoSimulacao, SelecionarAlvo
from engine.estado import Divida
from engine.parametros import Parametros
from engine.tipos import DESCONHECIDO, Dinheiro
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO

REGRAS: Final[tuple[str, ...]] = ("RF-05", "O-01", "O-02", "O-03", "AC-19", "§5.1", "§11.1")


def _ordenar_por_beneficio(
    beneficios: Mapping[str, Decimal],
) -> list[str]:
    """`O-01` + desempate: ordena os `DIVIDA_ID` elegíveis por benefício
    marginal decrescente; quando dois benefícios empatam exatamente, o
    desempate final é `DIVIDA_ID` em ordem alfabética/lexicográfica
    crescente (critério 2 da tarefa). `sorted` do Python é estável, então
    ordenar primeiro por `DIVIDA_ID` crescente e depois por benefício
    decrescente (com `key` negando só o benefício) produz exatamente essa
    ordem total determinística em uma única passada.
    """
    candidatos = sorted(beneficios.keys())
    return sorted(candidatos, key=lambda divida_id: -beneficios[divida_id])


def criar_selecionar_alvo_avalanche(
    dividas: Mapping[str, Divida], p: Parametros
) -> SelecionarAlvo:
    """Fábrica de `SelecionarAlvo` para a Avalanche — `O-01..O-03`, `AC-19`.

    `dividas` é o inventário completo indexado por `DIVIDA_ID` (mesmo padrão
    de `executar_mes`/`simular_cenario`); `p` é usado por
    `calcular_beneficio_marginal` para o horizonte de simulação
    (`P_HORIZONTE_MAXIMO_SIMULACAO`). A função devolvida é pura em relação a
    `estado`/`delta` — `dividas`/`p` são fixos para toda a simulação, nunca
    mutados.
    """

    def selecionar_alvo_avalanche(
        estado: EstadoSimulacao, delta: Dinheiro
    ) -> Divida | None:
        """`SelecionarAlvo` da Avalanche — `Callable[[EstadoSimulacao,
        Dinheiro], Divida | None]`, exatamente o tipo de `engine/
        ciclo_mensal.py`.

        `O-02` (defensivo — ver docstring do módulo): se o alvo corrente já
        aponta para uma dívida ainda não quitada, devolve-a sem recalcular
        a ordenação — o alvo é fixo até quitação ou evento, e um alvo ainda
        elegível já É a melhor escolha vigente por definição (foi
        escolhido, ou herdado, e não perdeu elegibilidade).

        Caso contrário (bootstrap ou reranqueamento intramês — os dois
        únicos casos em que `executar_mes` de fato chama esta função,
        sempre com `DIVIDA_ALVO_ATUAL=None`), recalcula a ordenação do
        zero: para cada dívida elegível (ainda não quitada), calcula
        `BENEFICIO_MARGINAL_AMORTIZACAO` com `delta_disponivel =
        MIN(delta, VALOR_RELEVANTE_PARA_QUITACAO)` — `AC-19` no
        ranqueamento normal (`delta` = capacidade), `O-03`/`AC-14` no
        reranqueamento de resíduo (`delta` = resíduo restante); o `MIN`
        contra `VALOR_RELEVANTE_PARA_QUITACAO` de CADA candidata é
        justamente a responsabilidade que `engine/ciclo_mensal.py` deixa
        explicitamente para quem implementa a Avalanche de verdade (ver
        docstring daquele módulo). Ordena por benefício decrescente,
        desempate por `DIVIDA_ID` (`O-01`), devolve a primeira — ou `None`
        se não houver candidata elegível.
        """
        alvo_atual_id = estado.DIVIDA_ALVO_ATUAL
        if alvo_atual_id is not None and alvo_atual_id not in estado.quitadas:
            # O-02: alvo fixo até quitação (ou evento — decidido pelo
            # chamador, fora desta função). Nenhuma ordenação nova.
            return dividas[alvo_atual_id]

        elegiveis = {
            divida_id: divida
            for divida_id, divida in dividas.items()
            if divida_id not in estado.quitadas
        }
        if not elegiveis:
            return None

        beneficios: dict[str, Decimal] = {}
        for divida_id, divida in elegiveis.items():
            resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
            valor_relevante = resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO
            if valor_relevante is DESCONHECIDO:
                # RF-16: sem VALOR_RELEVANTE_PARA_QUITACAO não há como
                # compor o delta de teste (MIN exige os dois operandos
                # conhecidos) — a dívida fica fora do ranqueamento desta
                # rodada, sem inventar um benefício marginal fabricado. A
                # triagem formal desse dado ausente (Gate 1,
                # INFORMACAO_PENDENTE) é responsabilidade de quem monta
                # `dividas` antes de chegar aqui, não desta função.
                continue
            delta_teste = min(delta, valor_relevante)
            resultado = calcular_beneficio_marginal(divida, delta_teste, p)
            if resultado.BENEFICIO_MARGINAL_AMORTIZACAO is DESCONHECIDO:
                # RF-16/§11.1 "Não criar benefício marginal artificial": sem
                # número algum (nem simulação, nem fallback de taxa/CET —
                # origem="INDISPONIVEL", ou divisão por zero sem divisor
                # válido), a dívida não pode ser comparada nesta rodada.
                continue
            beneficios[divida_id] = resultado.BENEFICIO_MARGINAL_AMORTIZACAO

        if not beneficios:
            return None

        ordenados = _ordenar_por_beneficio(beneficios)
        return dividas[ordenados[0]]

    return selecionar_alvo_avalanche
