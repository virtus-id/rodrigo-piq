"""Diagnóstico financeiro — RF-14, RF-15, RF-25, RF-26 · §11.8 · GAB-A, GAB-B.

T-20: pagamentos devidos × efetivos, os dois resultados (caixa observado e
estrutural), o gap entre eles e o déficit mensal.

T-21: `PISO_CAPACIDADE`, `STATUS_FINANCEIRO` e `CAPACIDADE_ATAQUE_ATUAL`.

T-22: `FATOR_SEGURANCA`, composto de forma subtrativa a partir das quatro
reduções (`calcular_fator_seguranca`).

T-23 (esta tarefa): as três capacidades completas (`BASE_CONSERVADORA`,
`CAPACIDADE_ATAQUE_CONSERVADORA`, `CAPACIDADE_ATAQUE_POTENCIAL`) e
`MODO_ESTABILIZACAO` (`calcular_capacidades`). `GAP_AUTOPERCEPCAO`
(`calcular_gap_autopercepcao`) também é desta tarefa. O encadeamento em
`calcular_diagnostico` que produz o `Diagnostico` completo do plano (§4) é
escopo de T-24. Este módulo cresce nas tarefas seguintes.

**Ambiguidade registrada — fórmula de `CAPACIDADE_ATAQUE_POTENCIAL` (T-23).**
Nenhuma fonte do slug (`motor-calculo.spec.md` §11.8, `piq-app-spec.md`,
`piq-definicoes-engine.md`) escreve a fórmula completa de
`CAPACIDADE_ATAQUE_POTENCIAL` — só que ela "inclui `ECONOMIA_POTENCIAL_
IMEDIATA`" e "nunca entra no cronograma-base" (`EC-11`). `AC-06`/`GAB-B` dá
`CAPACIDADE_ATAQUE_POTENCIAL = 600` com `BASE_CONSERVADORA = 200`,
`CAPACIDADE_ATAQUE_CONSERVADORA = 200` e `ECONOMIA_POTENCIAL_IMEDIATA = 400`
— mas como `FATOR_SEGURANCA = 1,00` neste gabarito, os dois candidatos abaixo
produzem o MESMO resultado (600) e o gabarito, sozinho, não desambiguiza:

```
(1) CAPACIDADE_ATAQUE_CONSERVADORA + ECONOMIA_POTENCIAL_IMEDIATA = 200 + 400 = 600
(2) BASE_CONSERVADORA + ECONOMIA_POTENCIAL_IMEDIATA              = 200 + 400 = 600
```

Adotada a opção (1). Razão: `CAPACIDADE_ATAQUE_POTENCIAL` representa "a
capacidade que existiria se as economias identificadas fossem implementadas"
— ou seja, é a MESMA margem de segurança da capacidade conservadora
(`FATOR_SEGURANCA`) estendida pela economia adicional, não a base bruta sem
o fator aplicado. Aplicar o fator de segurança uniformemente a toda
capacidade projetada (conservadora e potencial) é mais coerente com o resto
do modelo do que ter uma capacidade "potencial" mais arriscada (sem fator)
do que a "conservadora" mesma variável de base. Se um cenário futuro tiver
`FATOR_SEGURANCA < 1` e uma segunda fonte de gabarito desambiguizar de forma
diferente, esta escolha deve ser revisitada — reportar ao especialista, não
corrigir silenciosamente (§6 do `sdd.config.md`).

**Gap caixa × estrutural é diagnóstico matemático, sem limiar** (§11.8):

```
GAP_CAIXA_VS_ESTRUTURAL = RESULTADO_CAIXA_OBSERVADO - RESULTADO_MENSAL_ATUAL
```

`P_CAIXA_VS_ESTRUTURAL` está `DEPRECATED` (§11.8/§11.9, `OQ-02`) e não é lido
em nenhum ponto deste módulo — nenhum limiar é aplicado sobre o gap.

**Decisão de design — diagnóstico parcial por dado desconhecido.** Somar
`DESCONHECIDO` como se fosse zero seria estimar, o que `RF-16`/GAB-03 proíbem.
Em vez de propagar `DinheiroTalvez` por todos os campos (o que obrigaria toda
tarefa futura consumidora a tratar `DESCONHECIDO` em cada soma intermediária,
mesmo quando só uma dívida entre várias tem dado faltante), a soma de
`PARCELA_CONTRATUAL`/`PAGAMENTO_MENSAL_EFETIVO` ignora as dívidas com dado
desconhecido no total parcial e registra **quais** dívidas ficaram de fora em
`dividas_com_devido_desconhecido`/`dividas_com_efetivo_desconhecido` — tuplas
de `DIVIDA_ID`. O total só é confiável quando a tupla correspondente está
vazia; por isso `PagamentosEResultados.completo` resume isso num único
booleano (`True` apenas quando as duas tuplas são vazias) para quem só
precisa saber "posso confiar nestes totais?" sem inspecionar as tuplas. Os
`Dinheiro` continuam sempre exatos (nunca `DinheiroTalvez`) — são somas
parciais explicitamente sinalizadas como tal, não estimativas.

**Convenção de parâmetro percentual (T-21, vale para toda tarefa futura que
leia um `P_*` percentual do JSON — ex. T-22, T-57, T-58).** Os parâmetros
`P_*` do JSON de `parameters/` que representam percentual são armazenados em
**pontos percentuais**, não em fração: `P_PISO_CAPACIDADE_PERCENTUAL = 3`
significa "3%", não "300%". Isso é visivelmente diferente de `Taxa` (alias de
`Decimal`, `engine/tipos.py`), que por convenção de domínio já circula como
fração (`4% a.m. == Decimal("0.04")`) — mas `Taxa` é o tipo de campo de
`EstadoFinanceiro`/`Divida` (dado coletado), não o de `Parametros.numero()`.
Não há conversão automática em `engine/parametros.py::numero()` — ele devolve
o `Decimal` cru do JSON, ponto percentual como está armazenado. Cada fórmula
que consome um `P_*` percentual converte explicitamente para fração dividindo
por `Decimal(100)` no ponto de uso (`_fracao_percentual`, abaixo), nunca
embutindo o `100` implicitamente na conta. Verificado contra `GAB-B`:
`RENDA_TOTAL_RECORRENTE = 10.000`, `P_PISO_CAPACIDADE_PERCENTUAL = 3` ⇒
`10.000 × (3 / 100) = 300`, que é o `PISO_CAPACIDADE` esperado por `AC-06`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.comportamento import (
    derivar_CONFIABILIDADE_DADOS,
    derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
    derivar_NIVEL_CONTROLE,
)
from engine.estado import TIPO_RENDA, Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import (
    ClassificacaoRisco,
    classificar_RISCO_COMPORTAMENTAL_GERAL,
    classificar_RISCO_RECAIDA,
)
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_FINANCEIRO,
    Dinheiro,
    DinheiroTalvez,
)

REGRAS: Final[tuple[str, ...]] = (
    "RF-14",
    "RF-15",
    "RF-16",
    "RF-25",
    "RF-26",
    "RF-27",
    "RF-35",
    "§11.8",
    "§11.10",
)

_CEM: Final[Decimal] = Decimal(100)


def _fracao_percentual(pontos_percentuais: Decimal) -> Decimal:
    """Converte um `P_*` percentual (pontos, ex. `3` == "3%") em fração
    (`Decimal("0.03")`) para uso em multiplicação. Ver nota de convenção no
    topo do módulo — vale para todo `P_*` percentual, não só o piso."""
    return pontos_percentuais / _CEM


@dataclass(frozen=True, slots=True)
class PagamentosEResultados:
    """Pagamentos devidos × efetivos e os dois resultados mensais — T-20.

    `completo = True` somente quando nenhuma dívida do inventário tem
    `PARCELA_CONTRATUAL` ou `PAGAMENTO_MENSAL_EFETIVO` desconhecidos; nesse
    caso as tuplas `dividas_com_*_desconhecido` estão vazias. Quando
    `completo = False`, os totais somam apenas as dívidas com dado
    conhecido — são parciais, não zero silencioso.
    """

    PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES: Dinheiro
    PAGAMENTOS_EFETIVOS_DIVIDAS: Dinheiro
    RESULTADO_CAIXA_OBSERVADO: Dinheiro
    RESULTADO_MENSAL_ATUAL: Dinheiro
    GAP_CAIXA_VS_ESTRUTURAL: Dinheiro  # §11.8: diagnóstico, SEM limiar
    DEFICIT_MENSAL: Dinheiro
    completo: bool
    dividas_com_devido_desconhecido: tuple[str, ...]
    dividas_com_efetivo_desconhecido: tuple[str, ...]


def _somar_pagamentos(
    dividas: tuple[Divida, ...],
) -> tuple[Dinheiro, Dinheiro, tuple[str, ...], tuple[str, ...]]:
    """Soma `PARCELA_CONTRATUAL` (devido) e `PAGAMENTO_MENSAL_EFETIVO`
    (efetivo) de todas as dívidas do inventário.

    RF-16/GAB-03: dívida com dado `DESCONHECIDO` não entra na soma — somar
    como zero seria estimar. Ela é registrada na tupla correspondente para
    que o chamador saiba que o total é parcial. AC-32: `PAGAMENTO_MENSAL_
    EFETIVO = 0` é um `Dinheiro` como outro qualquer, somado normalmente —
    a checagem é `is DESCONHECIDO`, nunca "é falsy" ou "é zero".
    """
    total_devido = dinheiro(0)
    total_efetivo = dinheiro(0)
    devido_desconhecido: list[str] = []
    efetivo_desconhecido: list[str] = []

    for divida in dividas:
        if divida.PARCELA_CONTRATUAL is DESCONHECIDO:
            devido_desconhecido.append(divida.DIVIDA_ID)
        else:
            total_devido += divida.PARCELA_CONTRATUAL

        if divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO:
            efetivo_desconhecido.append(divida.DIVIDA_ID)
        else:
            # AC-32/GAB-A: 0 é valor legítimo, somado normalmente.
            total_efetivo += divida.PAGAMENTO_MENSAL_EFETIVO

    return total_devido, total_efetivo, tuple(devido_desconhecido), tuple(efetivo_desconhecido)


def calcular_pagamentos_e_resultados(estado: EstadoFinanceiro) -> PagamentosEResultados:
    """RF-14 · §11.8 — pagamentos devidos/efetivos, os dois resultados,
    o gap caixa × estrutural (sem limiar) e o déficit mensal.

    `RESULTADO_CAIXA_OBSERVADO` usa os pagamentos EFETIVOS (o que
    efetivamente sai do caixa); `RESULTADO_MENSAL_ATUAL` usa os pagamentos
    DEVIDOS contratuais (o resultado estrutural). GAB-A: renda 8000, despesas
    operacionais 6500, despesas não-mensais 500, devidos 2000, efetivos 800
    ⇒ observado +200, estrutural -1000, gap 1200, déficit 1000.

    EC-12/AC-08: `SEGURO_INCLUIDO_PARCELA` não é lido aqui — `CUSTO_SEGURO`
    NUNCA é somado a `PARCELA_CONTRATUAL`/`PAGAMENTO_MENSAL_EFETIVO`, porque
    quando o seguro está incluído ele já compõe esses dois valores na
    origem (o dado coletado). Somar de novo duplicaria o custo.
    """
    (
        total_devido,
        total_efetivo,
        devido_desconhecido,
        efetivo_desconhecido,
    ) = _somar_pagamentos(estado.dividas)

    resultado_caixa_observado = (
        estado.RENDA_TOTAL_RECORRENTE
        - estado.DESPESAS_OPERACIONAIS_ATUAIS
        - estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS
        - total_efetivo
    )
    resultado_mensal_atual = (
        estado.RENDA_TOTAL_RECORRENTE
        - estado.DESPESAS_OPERACIONAIS_ATUAIS
        - estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS
        - total_devido
    )

    # §11.8: diagnóstico matemático, sem limiar — nenhum P_* é lido aqui.
    gap_caixa_vs_estrutural = resultado_caixa_observado - resultado_mensal_atual

    deficit_mensal = (
        -resultado_mensal_atual if resultado_mensal_atual < dinheiro(0) else dinheiro(0)
    )

    return PagamentosEResultados(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=total_devido,
        PAGAMENTOS_EFETIVOS_DIVIDAS=total_efetivo,
        RESULTADO_CAIXA_OBSERVADO=resultado_caixa_observado,
        RESULTADO_MENSAL_ATUAL=resultado_mensal_atual,
        GAP_CAIXA_VS_ESTRUTURAL=gap_caixa_vs_estrutural,
        DEFICIT_MENSAL=deficit_mensal,
        completo=not devido_desconhecido and not efetivo_desconhecido,
        dividas_com_devido_desconhecido=devido_desconhecido,
        dividas_com_efetivo_desconhecido=efetivo_desconhecido,
    )


@dataclass(frozen=True, slots=True)
class StatusFinanceiro:
    """`PISO_CAPACIDADE`, `STATUS_FINANCEIRO` e `CAPACIDADE_ATAQUE_ATUAL` — T-21.

    RF-26/AC-37..AC-39: o piso **classifica** em qual das três faixas o
    `RESULTADO_MENSAL_ATUAL` cai; ele nunca trunca, eleva ou substitui a
    capacidade. `CAPACIDADE_ATAQUE_ATUAL` deriva SOMENTE de
    `RESULTADO_MENSAL_ATUAL` — `PISO_CAPACIDADE` nunca entra nessa conta.
    """

    PISO_CAPACIDADE: Dinheiro
    STATUS_FINANCEIRO: STATUS_FINANCEIRO
    CAPACIDADE_ATAQUE_ATUAL: Dinheiro


def calcular_status_financeiro(
    pagamentos: PagamentosEResultados,
    estado: EstadoFinanceiro,
    parametros: Parametros,
) -> StatusFinanceiro:
    """RF-26 · AC-37..AC-39 · §11.8 — classifica `STATUS_FINANCEIRO` a partir
    do `PISO_CAPACIDADE` e deriva `CAPACIDADE_ATAQUE_ATUAL`.

    ```
    PISO_CAPACIDADE = MAX(P_PISO_CAPACIDADE_ABSOLUTO,
                          RENDA_TOTAL_RECORRENTE × P_PISO_CAPACIDADE_PERCENTUAL)
    CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)
    ```

    AC-38 é a trava normativa: resultado 200 com piso 300 dá
    `EQUILIBRIO_FRAGIL` (o resultado está abaixo do piso), mas a capacidade
    continua 200 — nem 0 (o piso não é um teto que zera abaixo dele), nem 300
    (o piso não é um mínimo garantido de ataque). `PISO_CAPACIDADE` só é lido
    para decidir a faixa de `STATUS_FINANCEIRO`; a expressão de
    `CAPACIDADE_ATAQUE_ATUAL` abaixo não referencia `piso` em nenhum ramo.
    """
    resultado = pagamentos.RESULTADO_MENSAL_ATUAL

    piso_absoluto = parametros.numero("P_PISO_CAPACIDADE_ABSOLUTO")
    piso_percentual = estado.RENDA_TOTAL_RECORRENTE * _fracao_percentual(
        parametros.numero("P_PISO_CAPACIDADE_PERCENTUAL")
    )
    piso_capacidade = dinheiro(max(piso_absoluto, piso_percentual))

    if resultado < dinheiro(0):
        status = STATUS_FINANCEIRO.DEFICIT
    elif resultado < piso_capacidade:
        status = STATUS_FINANCEIRO.EQUILIBRIO_FRAGIL
    else:
        status = STATUS_FINANCEIRO.CAPACIDADE_POSITIVA

    # RF-26: só RESULTADO_MENSAL_ATUAL entra aqui — PISO_CAPACIDADE
    # classifica acima, nunca participa desta conta.
    capacidade_ataque_atual = resultado if resultado > dinheiro(0) else dinheiro(0)

    return StatusFinanceiro(
        PISO_CAPACIDADE=piso_capacidade,
        STATUS_FINANCEIRO=status,
        CAPACIDADE_ATAQUE_ATUAL=capacidade_ataque_atual,
    )


@dataclass(frozen=True, slots=True)
class FatorSeguranca:
    """`FATOR_SEGURANCA` e as quatro parcelas de redução — T-22, RF-25.

    As quatro reduções ficam expostas individualmente (não só a soma) para
    que o revisor humano refaça a conta sem reexecutar o motor — mesmo
    princípio de auditabilidade de `SinalD4`/`ClassificacaoRisco`
    (`engine/risco.py`). `REDUCAO_SEGURANCA_TOTAL` é a soma das quatro;
    `FATOR_SEGURANCA` já é o valor final, com o piso aplicado.
    """

    REDUCAO_RENDA_VARIAVEL: Decimal
    REDUCAO_CONFIABILIDADE: Decimal
    REDUCAO_RISCO_COMPORTAMENTAL: Decimal
    REDUCAO_RECAIDA: Decimal
    REDUCAO_SEGURANCA_TOTAL: Decimal
    FATOR_SEGURANCA: Decimal


def calcular_fator_seguranca(
    TIPO_RENDA_ATUAL: TIPO_RENDA,
    CONFIABILIDADE_DADOS_ATUAL: CONFIABILIDADE_DADOS,
    RISCO_COMPORTAMENTAL_GERAL: NIVEL_RISCO,
    RISCO_RECAIDA: NIVEL_RISCO,
    parametros: Parametros,
) -> FatorSeguranca:
    """RF-25 · AC-36 · AC-26 · Definições §3 — compõe `FATOR_SEGURANCA` de
    forma **subtrativa**: soma as quatro reduções, subtrai de 1, e só então
    aplica o piso. Composição multiplicativa é proibida (`(1-r1)×(1-r2)×...`
    NUNCA).

    ```
    REDUCAO_SEGURANCA_TOTAL = REDUCAO_RENDA_VARIAVEL + REDUCAO_CONFIABILIDADE
                            + REDUCAO_RISCO_COMPORTAMENTAL + REDUCAO_RECAIDA

    FATOR_SEGURANCA = MAX(P_FATOR_SEGURANCA_MINIMO, 1 − REDUCAO_SEGURANCA_TOTAL)
    ```

    AC-36: reduções 0,20 + 0,15 + 0,10 com piso 0,60 ⇒ bruto 1 − 0,45 = 0,55,
    `MAX(0,60; 0,55) = 0,60` ⇒ `FATOR_SEGURANCA = 0,60`.

    Os quatro parâmetros de entrada são **obrigatórios e posicionais** — como
    em `derivar_CONFIABILIDADE_DADOS`/`classificar_RISCO_COMPORTAMENTAL_GERAL`
    (`engine/comportamento.py`, `engine/risco.py`), a assinatura reforça por
    tipo, não por convenção, a ordem de derivação da §11.10 (`RF-27`):
    `CONFIABILIDADE_DADOS_ATUAL`, `RISCO_COMPORTAMENTAL_GERAL` e
    `RISCO_RECAIDA` precisam já estar derivados antes desta chamada.

    Nota de unidade: diferente dos `P_*` "percentual" (`P_PISO_CAPACIDADE_
    PERCENTUAL`, ver `_fracao_percentual` acima), os `P_*` desta função têm
    unidade "fração" ou "fator" na §8 da canônica (`piq-app-spec.md`) — já
    armazenados no JSON como fração pronta (`P_REDUCAO_RENDA_VARIAVEL =
    0.20` == "0,20", não "20%"). Não há conversão por `_fracao_percentual`
    aqui; o valor de `Parametros.numero()` é usado direto.

    **`REDUCAO_RENDA_VARIAVEL`** — interpretação documentada (nenhuma das
    fontes do slug detalha uma fórmula além do valor único do parâmetro):
    `P_REDUCAO_RENDA_VARIAVEL` se `TIPO_RENDA_ATUAL == VARIAVEL`, senão 0.
    `RELATIVAMENTE_ESTAVEL` não aciona redução parcial — não há fonte
    normativa (`motor-calculo.spec.md`, `piq-definicoes-engine.md`) que
    combine `P_FATOR_RENDA_VARIAVEL` nesta fórmula; esse parâmetro é "fator
    aplicado sobre renda variável" e sua única menção na canônica
    (`piq-app-spec.md` B3.02A/B3.02B) é no cálculo de
    `RENDA_VARIAVEL_CONSIDERADA`, fora do escopo de `FATOR_SEGURANCA`/T-22.

    **`REDUCAO_RECAIDA`** — acionada por `RISCO_RECAIDA == ALTO`, a variável
    **derivada** pela regra D.4 (`classificar_RISCO_RECAIDA`,
    `engine/risco.py`, T-15), não pelo campo de entrada bruto
    `HISTORICO_RECAIDA` de `SinaisComportamentais` (que é só 1 dos 5 sinais
    que alimentam `RISCO_RECAIDA`). O grafo de derivação obrigatório
    (`motor-calculo.spec.md` §11.10) liga explicitamente `RISCO_RECAIDA
    (D.4) → REDUCAO_RECAIDA`, nunca `HISTORICO_RECAIDA → REDUCAO_RECAIDA`
    diretamente.

    **`REDUCAO_RISCO_COMPORTAMENTAL`** — AC-26/§11.4: somente
    `RISCO_COMPORTAMENTAL_GERAL == ALTO` aciona `P_REDUCAO_RISCO_
    COMPORTAMENTAL_ALTO`; `MODERADO` e `BAIXO` não têm redução parcial. Essa
    redução e `REDUCAO_RECAIDA` são somadas separadamente — nenhuma absorve
    a outra, mesmo quando ambas as condições estão ativas ao mesmo tempo.
    """
    reducao_renda_variavel = (
        parametros.numero("P_REDUCAO_RENDA_VARIAVEL")
        if TIPO_RENDA_ATUAL is TIPO_RENDA.VARIAVEL
        else Decimal(0)
    )

    if CONFIABILIDADE_DADOS_ATUAL is CONFIABILIDADE_DADOS.MEDIA:
        reducao_confiabilidade = parametros.numero("P_REDUCAO_CONFIABILIDADE_MEDIA")
    elif CONFIABILIDADE_DADOS_ATUAL is CONFIABILIDADE_DADOS.BAIXA:
        reducao_confiabilidade = parametros.numero("P_REDUCAO_CONFIABILIDADE_BAIXA")
    else:
        reducao_confiabilidade = Decimal(0)

    # AC-26/§11.4: SOMENTE ALTO aciona — sem redução parcial para MODERADO.
    reducao_risco_comportamental = (
        parametros.numero("P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO")
        if RISCO_COMPORTAMENTAL_GERAL is NIVEL_RISCO.ALTO
        else Decimal(0)
    )

    # §11.10: RISCO_RECAIDA (D.4 já derivado) → REDUCAO_RECAIDA — não o
    # campo de entrada HISTORICO_RECAIDA (ver docstring acima).
    reducao_recaida = (
        parametros.numero("P_REDUCAO_HISTORICO_RECAIDA")
        if RISCO_RECAIDA is NIVEL_RISCO.ALTO
        else Decimal(0)
    )

    # RF-25/AC-36: soma primeiro, piso depois — composição multiplicativa
    # é PROIBIDA em qualquer caminho.
    reducao_total = (
        reducao_renda_variavel
        + reducao_confiabilidade
        + reducao_risco_comportamental
        + reducao_recaida
    )
    fator_seguranca_bruto = Decimal(1) - reducao_total
    fator_seguranca = max(
        parametros.numero("P_FATOR_SEGURANCA_MINIMO"), fator_seguranca_bruto
    )

    return FatorSeguranca(
        REDUCAO_RENDA_VARIAVEL=reducao_renda_variavel,
        REDUCAO_CONFIABILIDADE=reducao_confiabilidade,
        REDUCAO_RISCO_COMPORTAMENTAL=reducao_risco_comportamental,
        REDUCAO_RECAIDA=reducao_recaida,
        REDUCAO_SEGURANCA_TOTAL=reducao_total,
        FATOR_SEGURANCA=fator_seguranca,
    )


@dataclass(frozen=True, slots=True)
class Capacidades:
    """As três capacidades de ataque e `MODO_ESTABILIZACAO` — T-23, RF-14,
    RF-15, §11.8, `AC-06`, `AC-07`, `EC-10`, `EC-11`.

    ```
    BASE_CONSERVADORA = MIN(RESULTADO_MENSAL_ATUAL, CAPACIDADE_ATAQUE_DECLARADA)
    CAPACIDADE_ATAQUE_CONSERVADORA = BASE_CONSERVADORA × FATOR_SEGURANCA
    CAPACIDADE_ATAQUE_POTENCIAL = CAPACIDADE_ATAQUE_CONSERVADORA
                                 + ECONOMIA_POTENCIAL_IMEDIATA
    ```

    `CAPACIDADE_ATAQUE_CONSERVADORA` é a ÚNICA capacidade que alimenta o
    cronograma-base (`AC-07`). `CAPACIDADE_ATAQUE_POTENCIAL` existe apenas
    como diagnóstico/alerta — nenhum consumidor de cronograma-base pode
    lê-la; ver aviso reforçado na docstring do campo, abaixo.

    RF-15/EC-10: `RESULTADO_MENSAL_ATUAL < 0` já produz `CAPACIDADE_ATAQUE_
    ATUAL = 0` em `calcular_status_financeiro` (T-21) — aqui apenas se
    espelha a mesma condição de déficit em `MODO_ESTABILIZACAO`, sem
    recalcular nada. Em modo estabilização o motor NÃO aborta: continua e
    devolve as três capacidades normalmente.

    **Nota sobre sinal em déficit.** A fórmula literal de `BASE_CONSERVADORA`
    (§11.8/`piq-app-spec.md` linha 449) é `MIN(RESULTADO_MENSAL_ATUAL,
    CAPACIDADE_ATAQUE_DECLARADA)`, sem `MAX(0, ...)` — diferente de
    `CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)`, que É
    definida com truncamento explícito na mesma seção. Em
    `MODO_ESTABILIZACAO`, `BASE_CONSERVADORA`/`CAPACIDADE_ATAQUE_CONSERVADORA`/
    `CAPACIDADE_ATAQUE_POTENCIAL` podem sair negativas — nenhum gabarito
    (`GAB-A`/`AC-05`) exercita essas três variáveis especificamente em
    déficit, só `CAPACIDADE_ATAQUE_ATUAL = 0`. Não se adiciona um `MAX(0,
    ...)` aqui por analogia: a metodologia não se decide implementando (§6
    do `sdd.config.md`) — fórmula que a fonte não escreveu não é inventada.
    Consumidores futuros de cronograma-base (Entrega 4+) devem checar
    `MODO_ESTABILIZACAO`/`CAPACIDADE_ATAQUE_ATUAL` antes de usar qualquer
    capacidade conservadora/potencial como valor de ataque real.
    """

    BASE_CONSERVADORA: Dinheiro
    CAPACIDADE_ATAQUE_CONSERVADORA: Dinheiro
    CAPACIDADE_ATAQUE_POTENCIAL: Dinheiro
    """EC-11: entra `ECONOMIA_POTENCIAL_IMEDIATA`, nunca o cronograma-base.
    NENHUM consumidor de `engine/ciclo_mensal.py`, `engine/metodos/*` ou de
    qualquer lógica de cronograma-base (tarefas futuras da Entrega 4 em
    diante) deve ler este campo para determinar `CAPACIDADE_ATAQUE_M` ou
    qualquer valor de ataque real. É estritamente diagnóstico/alerta
    (`AC-07`)."""
    MODO_ESTABILIZACAO: bool


def calcular_capacidades(
    pagamentos: PagamentosEResultados,
    estado: EstadoFinanceiro,
    fator_seguranca: FatorSeguranca,
) -> Capacidades:
    """RF-14, RF-15 · §11.8 · `AC-06`, `EC-10`, `EC-11` — as três capacidades
    de ataque e `MODO_ESTABILIZACAO`.

    `CAPACIDADE_ATAQUE_DECLARADA` pode ser `DESCONHECIDO` (`DinheiroTalvez`
    em `EstadoFinanceiro`) — RF-16 proíbe estimar. Quando desconhecida,
    `BASE_CONSERVADORA` usa só `RESULTADO_MENSAL_ATUAL` (não há outro termo
    determinístico para compor o `MIN`; inventar um substituto seria
    estimar). Isso NÃO é o mesmo que tratar `DESCONHECIDO` como zero: o
    `MIN` simplesmente perde um dos dois candidatos, e o resultado ainda é
    exato, não uma estimativa do valor ausente.

    Verificado contra `GAB-B` (`AC-06`): `RESULTADO_MENSAL_ATUAL = 200`,
    `CAPACIDADE_ATAQUE_DECLARADA = 500` ⇒ `BASE_CONSERVADORA = MIN(200, 500)
    = 200`; `FATOR_SEGURANCA = 1,00` ⇒ `CAPACIDADE_ATAQUE_CONSERVADORA =
    200 × 1,00 = 200`; `ECONOMIA_POTENCIAL_IMEDIATA = 400` ⇒
    `CAPACIDADE_ATAQUE_POTENCIAL = 200 + 400 = 600`.
    """
    resultado = pagamentos.RESULTADO_MENSAL_ATUAL
    declarada = estado.CAPACIDADE_ATAQUE_DECLARADA

    # RF-16: sem estimar o termo desconhecido — o MIN só compara os
    # candidatos determinísticos disponíveis.
    base_conservadora = (
        min(resultado, declarada) if declarada is not DESCONHECIDO else resultado
    )

    capacidade_conservadora = dinheiro(base_conservadora * fator_seguranca.FATOR_SEGURANCA)

    # Ambiguidade documentada na docstring do módulo (topo do arquivo):
    # adotada a soma sobre a capacidade JÁ seguranificada, não sobre a base
    # bruta — o fator de segurança se aplica uniformemente a toda capacidade
    # projetada, conservadora ou potencial.
    capacidade_potencial = dinheiro(
        capacidade_conservadora + estado.ECONOMIA_POTENCIAL_IMEDIATA
    )

    # RF-15/EC-10: espelha a mesma condição de déficit de
    # calcular_status_financeiro (T-21) — sem recalcular, sem abortar.
    modo_estabilizacao = resultado < dinheiro(0)

    return Capacidades(
        BASE_CONSERVADORA=dinheiro(base_conservadora),
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidade_conservadora,
        CAPACIDADE_ATAQUE_POTENCIAL=capacidade_potencial,
        MODO_ESTABILIZACAO=modo_estabilizacao,
    )


def calcular_gap_autopercepcao(
    estado: EstadoFinanceiro,
    nivel_controle: NIVEL_CONTROLE,
    parametros: Parametros,
) -> bool:
    """`GAP_AUTOPERCEPCAO` — §11.8, `OQ-03` (P_AUTOPERCEPCAO = 7).

    ```
    GAP_AUTOPERCEPCAO = AUTOPERCEPCAO_CONTROLE >= P_AUTOPERCEPCAO
                      E NIVEL_CONTROLE != FORTE
    ```

    `nivel_controle` é parâmetro obrigatório e já derivado — mesmo padrão de
    assinatura de `calcular_fator_seguranca`/`derivar_CONFIABILIDADE_DADOS`
    (`engine/comportamento.py`), reforçando por tipo a ordem de derivação da
    §11.10 (`RF-27`): `NIVEL_CONTROLE` precisa existir antes desta chamada.

    `AUTOPERCEPCAO_CONTROLE` é `int | Desconhecido` (`EstadoFinanceiro`,
    B2.13). RF-16: desconhecido não pode satisfazer `>=` o limiar — tratado
    como abaixo dele, nunca estimado (mesmo padrão de `NECESSIDADE_VITORIA`
    em `derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`).
    """
    autopercepcao = estado.AUTOPERCEPCAO_CONTROLE
    limiar = parametros.numero("P_AUTOPERCEPCAO")

    autopercepcao_alta = autopercepcao is not DESCONHECIDO and autopercepcao >= limiar

    return autopercepcao_alta and nivel_controle is not NIVEL_CONTROLE.FORTE


@dataclass(frozen=True, slots=True)
class Diagnostico:
    """Diagnóstico financeiro e comportamental completo — T-24, RF-14, RF-27,
    §4 do plano técnico, §11.10 (ordem de derivação obrigatória).

    Os catorze primeiros campos são cópia literal do bloco `Diagnostico` da
    §4 do plano (`plans/motor-calculo.plan.md`), nomes idênticos.

    **Decisão de design — campos comportamentais extras dentro de
    `Diagnostico`, não em objeto/tupla separado.** O snippet do plano não
    lista `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `RISCO_RECAIDA`,
    `RISCO_COMPORTAMENTAL_GERAL` nem `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`
    no bloco `Diagnostico` — mas são produtos derivados essenciais do mesmo
    fluxo (§11.10) e tarefas futuras precisam deles: T-61
    (`METODO_RECOMENDADO_PIQ` consome `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`
    via `S-04`/`AC-04`) e T-39 (`BENEFICIO_MARGINAL_AMORTIZACAO` consome
    `CAPACIDADE_ATAQUE_CONSERVADORA`, já presente no bloco literal). Optou-se
    por adicioná-los como campos extras de `Diagnostico`, em vez de devolver
    uma tupla/objeto maior (`Diagnostico` + extras) a partir de
    `calcular_diagnostico`, porque `SnapshotOrdem` (§4 do plano) já declara
    um único campo `diagnostico: Diagnostico` — não dois. Se
    `calcular_diagnostico` devolvesse uma tupla, todo consumidor futuro do
    snapshot (T-61, relatório) precisaria desempacotar e carregar dois
    objetos em vez de um, contrariando o contrato que o plano já fechou. Os
    campos extras vêm depois dos catorze do plano, claramente separados por
    comentário, para que a cópia literal do bloco original permaneça
    identificável.

    `classificacao_risco_recaida`/`classificacao_risco_comportamental_geral`
    carregam os `ClassificacaoRisco` completos (não só o `NIVEL_RISCO`) pelo
    mesmo motivo de auditabilidade documentado em `engine/risco.py`: o
    revisor humano precisa poder refazer a contagem de sinais a partir do
    diagnóstico consolidado, sem reexecutar o motor.
    """

    # --- bloco literal da §4 do plano (`plans/motor-calculo.plan.md`) ---
    PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES: Dinheiro
    PAGAMENTOS_EFETIVOS_DIVIDAS: Dinheiro
    RESULTADO_CAIXA_OBSERVADO: Dinheiro
    RESULTADO_MENSAL_ATUAL: Dinheiro
    GAP_CAIXA_VS_ESTRUTURAL: Dinheiro  # §11.8: diagnóstico, SEM limiar
    DEFICIT_MENSAL: Dinheiro
    PISO_CAPACIDADE: Dinheiro  # MAX(P_PISO_ABSOLUTO; P_PISO_PCT × renda)
    STATUS_FINANCEIRO: STATUS_FINANCEIRO
    MODO_ESTABILIZACAO: bool  # RF-15
    GAP_AUTOPERCEPCAO: bool  # §11.8, P_AUTOPERCEPCAO = 7
    BASE_CONSERVADORA: Dinheiro  # MIN(RESULTADO_MENSAL_ATUAL; DECLARADA)
    FATOR_SEGURANCA: Decimal  # piso P_FATOR_SEGURANCA_MINIMO
    CAPACIDADE_ATAQUE_ATUAL: Dinheiro  # RF-15: 0 em MODO_ESTABILIZACAO
    CAPACIDADE_ATAQUE_CONSERVADORA: Dinheiro  # a única que alimenta o cronograma
    CAPACIDADE_ATAQUE_POTENCIAL: Dinheiro  # EC-11: NUNCA entra no cronograma-base

    # --- campos comportamentais adicionais — ver docstring acima ---
    NIVEL_CONTROLE: NIVEL_CONTROLE
    CONFIABILIDADE_DADOS: CONFIABILIDADE_DADOS
    RISCO_RECAIDA: NIVEL_RISCO
    RISCO_COMPORTAMENTAL_GERAL: NIVEL_RISCO
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE: bool
    classificacao_risco_recaida: ClassificacaoRisco
    classificacao_risco_comportamental_geral: ClassificacaoRisco

    # --- Rodada 2 (RF-35, mesmo bloco) — nasceram em T-90 como contrato de
    # tipo/posição apenas. T-114 (RF-51) separou os dois estágios:
    # `RESERVA_MOBILIZAVEL` passou a receber o valor REAL da §13.1 (RF-43),
    # enquanto `ATAQUE_IMEDIATO_RECOMENDADO`, aqui em `calcular_diagnostico`,
    # continua `dinheiro(0)` — por design, não por pendência: a fórmula
    # exige o elegível, que só existe depois dos gates (RF-68). O valor real
    # é publicado por `calcular_plano` (T-141/T-142). Ver docstring de
    # `calcular_diagnostico` (bloco "T-114/RF-51/RF-69").
    #
    # T-98 (RF-41, AC-68) — `RESERVA_MOBILIZAVEL` é `DinheiroTalvez`, não
    # `Dinheiro`: a §13.1 Regra 3 admite o estado DESCONHECIDA (o usuário
    # respondeu "prefiro decidir somente depois de ver a análise" / "não
    # sei", ou a própria `RESERVA_TOTAL` é desconhecida). A §13.1 é
    # enfática em que esse estado NÃO vira zero silencioso: "não sei quanto
    # o usuário aceita mobilizar" e "o usuário não aceita mobilizar nada"
    # são fatos diferentes, e só o primeiro é pendência a registrar. O
    # `DinheiroTalvez` mantém a distinção legível até a camada de relatório.
    #
    # `ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro` — não existe
    # caminho na §13 em que ele seja desconhecido (plano R3.4.6): quando a
    # reserva é desconhecida ela contribui `0` para a soma
    # (`somar_ATAQUE_IMEDIATO_POTENCIAL`) e o recomendado permanece um
    # valor certo. Não retipar "por simetria".
    RESERVA_MOBILIZAVEL: DinheiroTalvez
    ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro


def calcular_diagnostico(estado: EstadoFinanceiro, parametros: Parametros) -> Diagnostico:
    """RF-14, RF-27 · §11.10 — orquestra o `Diagnostico` completo, respeitando
    a ordem de derivação obrigatória do grafo:

    ```
    Bloco 2 (8 variáveis)
       └→ NIVEL_CONTROLE
            ├→ CONFIABILIDADE_DADOS ──→ REDUCAO_CONFIABILIDADE ──┐
            ├→ RISCO_RECAIDA (D.4) ───→ REDUCAO_RECAIDA ─────────┤
            ├→ RISCO_COMPORTAMENTAL_GERAL (D.4)                  ├→ FATOR_SEGURANCA
            │     └→ REDUCAO_RISCO_COMPORTAMENTAL ───────────────┤
            │                          REDUCAO_RENDA_VARIAVEL ───┘
            │                                                          ↓
            └──── + NECESSIDADE_VITORIA + RISCO_RECAIDA    CAPACIDADE_ATAQUE_CONSERVADORA
                     └→ INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE
    ```

    Esta função apenas COMPÕE as sub-funções já puras de
    `engine/comportamento.py`, `engine/risco.py` e deste módulo — nenhuma
    lógica de derivação nova é introduzida aqui. A ordem de chamada não é
    convenção: cada sub-função já exige, por assinatura obrigatória e
    posicional, o resultado da etapa anterior (`derivar_CONFIABILIDADE_DADOS`
    exige `nivel_controle`; `classificar_RISCO_COMPORTAMENTAL_GERAL` exige
    `nivel_controle`; `derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` exige
    `nivel_controle` e `risco_recaida`; `calcular_fator_seguranca` exige
    `CONFIABILIDADE_DADOS_ATUAL`, `RISCO_COMPORTAMENTAL_GERAL` e
    `RISCO_RECAIDA`; `calcular_capacidades` exige `fator_seguranca`) — logo
    reordenar as chamadas abaixo não compila (`RF-27`, ver verificação
    ad-hoc de T-24 em `tests/estatica/`).

    Pura: nenhuma chamada de relógio, nenhum I/O, nenhum global mutável —
    somente composição de valores já calculados por funções puras.

    **T-114/RF-51 — `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`.**
    Esta função também povoa os dois campos de `RF-35` (§12.6 da spec deste
    slug). Os dois estão em estágios DIFERENTES, e a diferença é deliberada.

    `OQ-23` — a pergunta que bloqueava a derivação destes dois campos —
    **foi RESPONDIDA em 2026-09-07** pelo documento canônico do especialista
    do método, transcrito integralmente na **§13** de
    `specs/motor-calculo.spec.md` e marcado **congelado** ("nenhuma dessas
    decisões fica a critério do desenvolvedor"). Não há mais bloqueio por
    `OQ-23`, e nenhuma afirmação em contrário sobrevive nesta docstring
    (`AC-86`).

    `RESERVA_MOBILIZAVEL` é **valor real** (`RF-43`, `AC-85`): vem de
    `derivar_RESERVA_MOBILIZAVEL` (§13.1, três regras na ordem registrada),
    alimentada pelos quatro campos de reserva de `EstadoFinanceiro`
    (`RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA`, `RESERVA_TOTAL`,
    `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, `RF-36`). Não depende de
    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, então nada a impede aqui.
    Pode valer `DESCONHECIDO` (§13.1 Regra 3, `RF-41`): quem consome
    registra a pendência em vez de tratar como zero.

    `ATAQUE_IMEDIATO_RECOMENDADO`, chamada ISOLADA desta função, CONTINUA
    `dinheiro(0)` — por design, não por pendência. `calcular_diagnostico`
    não recebe (e não deve receber, decisão `OQ-44`/R4C.1.1 do plano)
    `ParticaoElegibilidade` nem `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` —
    a fórmula da §13.3/§14.2.4 exige o elegível, que só existe depois dos
    gates rodarem (`particionar_elegibilidade`), e esta função roda ANTES
    disso em `calcular_plano` (`engine/motor.py`, `RF-68`). O valor REAL só
    existe no `Diagnostico` que `calcular_plano` publica no
    `SnapshotOrdem` — lá, uma segunda passada (`dataclasses.replace`,
    `engine/motor.py::_compor_ATAQUE_IMEDIATO_RECOMENDADO`) substitui este
    placeholder pelo valor real, composto pelas mesmas nove funções de
    `engine/ataque_imediato.py` mais
    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA`
    (`engine/gates.py`, fatia 4B). Isto NÃO é mais placeholder por
    pendência de `OQ-29` (RESPONDIDA em 2026-09-09, §14) — é a consequência
    inevitável de `calcular_diagnostico` não ter, e não precisar ter,
    acesso aos gates: quem quer o valor real de
    `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` deve ler o `Diagnostico`
    dentro de um `SnapshotOrdem` publicado por `calcular_plano`, nunca o
    resultado de uma chamada isolada a esta função. `RF-66`/`RF-67`/
    §14.2.4 documentam a fórmula real e onde ela é aplicada.

    **`verificar_hierarquia_ataque_imediato` NÃO é chamada aqui** (`RF-50`,
    §13.6), por decisão registrada em `T-114`. A verificação exige os DOIS
    valores reais, e aqui nenhum dos dois está disponível: o recomendado é o
    placeholder acima, e `ATAQUE_IMEDIATO_POTENCIAL` (§13.2) sequer é campo
    de `Diagnostico` nesta rodada. Chamá-la com `0 >= 0` passaria sempre,
    afirmando uma cobertura de hierarquia que não existe — o oposto do que a
    função foi feita para pegar. A verificação de comportamento fica com os
    testes de `T-112`, sobre as funções puras e os gabaritos `GAB-AI`, onde
    os dois lados são valores de verdade.
    """
    # 1) NIVEL_CONTROLE — raiz do grafo, depende só do Bloco 2 (§11.11).
    nivel_controle = derivar_NIVEL_CONTROLE(estado.perfil_comportamental)

    # 2) CONFIABILIDADE_DADOS — depende de NIVEL_CONTROLE + Bloco 2.
    confiabilidade_dados = derivar_CONFIABILIDADE_DADOS(
        nivel_controle, estado.perfil_comportamental
    )

    # 3) RISCO_RECAIDA e RISCO_COMPORTAMENTAL_GERAL (D.4) — o segundo
    # também depende de NIVEL_CONTROLE (sexto sinal).
    classificacao_risco_recaida = classificar_RISCO_RECAIDA(estado.sinais_comportamentais)
    classificacao_risco_comportamental_geral = classificar_RISCO_COMPORTAMENTAL_GERAL(
        estado.sinais_comportamentais, nivel_controle
    )

    # 4) INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE — depende de NIVEL_CONTROLE
    # + RISCO_RECAIDA (já derivados) + sinais coletados + parâmetros.
    incompatibilidade_comportamental_grave = derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE(
        nivel_controle,
        classificacao_risco_recaida.nivel,
        estado.sinais_comportamentais,
        parametros,
    )

    # 5) Pagamentos devidos × efetivos e os dois resultados mensais (T-20).
    pagamentos = calcular_pagamentos_e_resultados(estado)

    # 6) STATUS_FINANCEIRO + PISO_CAPACIDADE + CAPACIDADE_ATAQUE_ATUAL (T-21)
    # — depende dos pagamentos já calculados.
    status_financeiro = calcular_status_financeiro(pagamentos, estado, parametros)

    # 7) FATOR_SEGURANCA — depende de TIPO_RENDA (do estado) +
    # CONFIABILIDADE_DADOS + RISCO_COMPORTAMENTAL_GERAL + RISCO_RECAIDA
    # (todos já derivados nos passos 1-3) + parâmetros (T-22).
    fator_seguranca = calcular_fator_seguranca(
        estado.TIPO_RENDA,
        confiabilidade_dados,
        classificacao_risco_comportamental_geral.nivel,
        classificacao_risco_recaida.nivel,
        parametros,
    )

    # 8) As três capacidades + MODO_ESTABILIZACAO — depende dos pagamentos
    # + estado + fator de segurança já calculado (T-23).
    capacidades = calcular_capacidades(pagamentos, estado, fator_seguranca)

    # 9) GAP_AUTOPERCEPCAO — depende de NIVEL_CONTROLE já derivado (T-23).
    gap_autopercepcao = calcular_gap_autopercepcao(estado, nivel_controle, parametros)

    # 10) RESERVA_MOBILIZAVEL (RF-43 · §13.1) — independente de todo o grafo
    # acima: depende apenas dos quatro campos de reserva do estado (RF-36).
    # Fica aqui, e não antes, só por legibilidade da ordem de montagem.
    #
    # IMPORT LOCAL, DELIBERADO — quebra de ciclo (T-114). No topo do módulo
    # ele fecharia um triângulo de importação em tempo de carga:
    # `engine.diagnostico` → `engine.ataque_imediato` (para esta função) →
    # `engine.ciclo_mensal` (para `ErroInvariante`, usado por
    # `verificar_hierarquia_ataque_imediato`) → `engine.diagnostico` (para o
    # tipo `Diagnostico`), e o interpretador falha com
    # `ImportError: cannot import name 'ErroInvariante' from partially
    # initialized module`. O import local resolve o nome em tempo de CHAMADA,
    # quando os três módulos já estão carregados. As alternativas exigiriam
    # editar arquivos de outra tarefa desta rodada (`engine/ataque_imediato.py`,
    # `engine/ciclo_mensal.py`), fora do escopo de `T-114` (`sdd.config.md` §4).
    # Não afeta a pureza (spec §5): é resolução de nome, não I/O.
    from engine.ataque_imediato import derivar_RESERVA_MOBILIZAVEL

    # Argumentos NOMEADOS: a função é keyword-only (`*`), e os quatro nomes
    # são os nomes canônicos da §13.1, caractere por caractere.
    RESERVA_MOBILIZAVEL = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=estado.RESERVA_EXISTE,
        DISPOSICAO_USO_RESERVA=estado.DISPOSICAO_USO_RESERVA,
        RESERVA_TOTAL=estado.RESERVA_TOTAL,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=(
            estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO
        ),
    )

    # 11) Monta o Diagnostico final, consolidando todos os resultados.
    return Diagnostico(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=pagamentos.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES,
        PAGAMENTOS_EFETIVOS_DIVIDAS=pagamentos.PAGAMENTOS_EFETIVOS_DIVIDAS,
        RESULTADO_CAIXA_OBSERVADO=pagamentos.RESULTADO_CAIXA_OBSERVADO,
        RESULTADO_MENSAL_ATUAL=pagamentos.RESULTADO_MENSAL_ATUAL,
        GAP_CAIXA_VS_ESTRUTURAL=pagamentos.GAP_CAIXA_VS_ESTRUTURAL,
        DEFICIT_MENSAL=pagamentos.DEFICIT_MENSAL,
        PISO_CAPACIDADE=status_financeiro.PISO_CAPACIDADE,
        STATUS_FINANCEIRO=status_financeiro.STATUS_FINANCEIRO,
        MODO_ESTABILIZACAO=capacidades.MODO_ESTABILIZACAO,
        GAP_AUTOPERCEPCAO=gap_autopercepcao,
        BASE_CONSERVADORA=capacidades.BASE_CONSERVADORA,
        FATOR_SEGURANCA=fator_seguranca.FATOR_SEGURANCA,
        CAPACIDADE_ATAQUE_ATUAL=status_financeiro.CAPACIDADE_ATAQUE_ATUAL,
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidades.CAPACIDADE_ATAQUE_CONSERVADORA,
        CAPACIDADE_ATAQUE_POTENCIAL=capacidades.CAPACIDADE_ATAQUE_POTENCIAL,
        NIVEL_CONTROLE=nivel_controle,
        CONFIABILIDADE_DADOS=confiabilidade_dados,
        RISCO_RECAIDA=classificacao_risco_recaida.nivel,
        RISCO_COMPORTAMENTAL_GERAL=classificacao_risco_comportamental_geral.nivel,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=incompatibilidade_comportamental_grave,
        classificacao_risco_recaida=classificacao_risco_recaida,
        classificacao_risco_comportamental_geral=classificacao_risco_comportamental_geral,
        # T-114/RF-43/AC-85: valor REAL da §13.1, não mais placeholder —
        # `derivar_RESERVA_MOBILIZAVEL` depende só dos quatro campos de
        # reserva do estado, nunca do elegível de OQ-29.
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        # T-114/RF-69: placeholder por design, não por pendência — ver
        # docstring desta função (bloco "T-114/RF-51/RF-69"). A fórmula da
        # §13.3/§14.2.4 exige NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, que
        # só existe depois dos gates (RF-68) e que esta função,
        # isoladamente, não tem como obter. O valor real é composto por
        # `calcular_plano` via `_compor_ATAQUE_IMEDIATO_RECOMENDADO`
        # (T-141/T-142), que substitui este placeholder no `Diagnostico`
        # publicado no `SnapshotOrdem`.
        ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0),
    )
