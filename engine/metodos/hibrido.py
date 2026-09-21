"""Seleção de alvo do método Híbrido — RF-07, RF-08 · §5.3, §11.5 · H-01..H-08 ·
AC-03, EC-03 · T-53, T-54.

Fonte normativa das seis etapas (`piq-app-spec.md` §5.3, linhas 149-181,
tabela "Etapa"/"Regra" + blocos "Etapa 3"/"Etapa 4"/"Fases em execução";
citada por `specs/motor-calculo.spec.md` RF-07 como `H-01..H-08`):

```
Etapa 1 (H-01)  Calcular ORDEM_AVALANCHE como referência de eficiência
                financeira.
Etapa 2 (H-02)  Para cada dívida elegível D diferente da primeira da
                ORDEM_AVALANCHE, simular CENARIO_HIBRIDO_D = D primeiro +
                Avalanche para as restantes, respeitados os gates.
Etapa 3 (H-03)  D é candidata válida se, CUMULATIVAMENTE:
                    MESES_PRIMEIRA_VITORIA(CENARIO_HIBRIDO_D) <= P_MESES_VITORIA_RAPIDA
                E   PENALIDADE_CUSTO_VS_AVALANCHE             <= P_DIFERENCA_CUSTO_EQUIVALENTE
                E   ATRASO_PRAZO_VS_AVALANCHE                 <= P_DIFERENCA_PRAZO_EQUIVALENTE
Etapa 4 (H-04)  Havendo várias candidatas, escolher lexicograficamente:
                    1º menor MESES_PRIMEIRA_VITORIA
                    2º menor PENALIDADE_CUSTO_VS_AVALANCHE
                    3º maior VALOR_FLUXO_LIBERADO
                    4º maior PESO_EMOCIONAL
                    5º maior BENEFICIO_MARGINAL_AMORTIZACAO
                    6º menor DIVIDA_ID
Etapa 5 (H-05)  ORDEM_HIBRIDA = D* seguida da Avalanche event-driven das
                restantes.
                    FASE_HIBRIDA_1 (H-06): DIVIDA_ALVO_ATUAL = D* até
                    QUITACAO_D* ou EVENTO_RECALCULO_EXTERNO — D* não pode
                    ser substituída pela evolução mensal dos saldos.
                    FASE_HIBRIDA_2 (H-07): Avalanche event-driven das
                    restantes — recalcular após cada quitação, nunca por
                    passagem de mês.
Etapa 6 (H-08)  Não havendo candidata: CENARIO_HIBRIDO = NAO_APLICAVEL e
                ORDEM_HIBRIDA = NAO_APLICAVEL. Não se fabrica um Híbrido.
```

**H-01 a H-07 (`T-53`) + H-08 (`T-54`).** `escolher_D_ESTRELA` executa as
Etapas 1-4: quando nenhuma dívida sobrevive às três tolerâncias cumulativas
da Etapa 3, devolve `D* = None` — nunca uma exceção, nunca uma candidata
fabricada por aproximação (mesma trava de `RF-16`/`§6` do `sdd.config.md`,
"metodologia não se decide implementando"). `criar_selecionar_alvo_hibrido`
(Etapa 5, motor real do Híbrido) conecta esse `None` à classificação formal
de `H-08`/`EC-03`: devolve `ResultadoHibrido(classificacao=NAO_APLICAVEL,
selecionar_alvo=None)` — nunca `NAO_CALCULAVEL` (que significaria "faltam
dados", `DESCONHECIDO` em cascata; aqui os dados existem e o cálculo É
possível, apenas não existe Híbrido aplicável a esta carteira, `S-01`/`S-02`
em `engine/tipos.py::CLASSIFICACAO_CENARIO`).

**As três tolerâncias — nomes exatos, fonte `parameters/parametros-1.0.1.json`
(confirmados presentes, nenhum hardcode, `AC-17`):**

- `P_MESES_VITORIA_RAPIDA` = 3 (meses) — teto para `MESES_PRIMEIRA_VITORIA`.
- `P_DIFERENCA_CUSTO_EQUIVALENTE` = 5 (unidade "%" na tabela §8 da canônica)
  — teto para `PENALIDADE_CUSTO_VS_AVALANCHE`.
- `P_DIFERENCA_PRAZO_EQUIVALENTE` = 2 (meses) — teto para
  `ATRASO_PRAZO_VS_AVALANCHE`.

**Cumulativas, não independentes (critério de aceite 2 da tarefa).** `H-03`
usa "E" maiúsculo entre as três condições — um `and` lógico único, avaliado
sobre a MESMA candidata D, nunca três filtros unidos por `or`/aplicados a
conjuntos diferentes. `_e_candidata_valida` abaixo é a função que testa essa
conjunção; `escolher_D_ESTRELA` a aplica uma vez por candidata, então
filtra: o conjunto de sobreviventes de uma tolerância nunca é maior que o
de todas juntas, porque `and` de curto-circuito nunca amplia o resultado —
é estruturalmente impossível expressar "cumulativo" com uma única expressão
booleana `and` de outra forma.

**Conversão de `P_DIFERENCA_CUSTO_EQUIVALENTE` (%) para fração — decisão de
implementação, fonte ambígua.** `PENALIDADE_CUSTO_VS_AVALANCHE` (§11.5,
mesma fórmula de `PENALIDADE_CUSTO(X)`) é uma FRAÇÃO decimal: `AC-03` fecha
o gabarito em "penalidade econômica 1,635%", ou seja
`PENALIDADE_CUSTO_VS_AVALANCHE = Decimal("0.01635")` como número interno
(arredondamento só na exibição, `G-01`). `P_DIFERENCA_CUSTO_EQUIVALENTE` é
lido de `Parametros.numero()` como `Decimal("5")` — o valor "5" da coluna
"Valor" da tabela §8, na unidade "%" da coluna ao lado. Comparar
`Decimal("0.01635") <= Decimal("5")` sem dividir por 100 sempre seria
verdadeiro e a tolerância nunca filtraria nada — não é a intenção normativa
("teto de 5%"). Adotada aqui a mesma leitura já usada por `P_DIFERENCA_
ECONOMICA_MATERIAL` (1%) em `specs/motor-calculo.spec.md` §11.5 ("Cenário a
MENOS DE 1% desse menor custo") — o número da tabela é um percentual
inteiro, dividido por 100 antes de comparar com uma fração. `engine/
comparacao.py` (RF-19/RF-20, T-6x, ainda não implementado nesta árvore) vai
enfrentar a MESMA conversão para `P_DIFERENCA_ECONOMICA_MATERIAL` e
`P_DIFERENCA_CUSTO_EQUIVALENTE` de novo (reaproveitado ali para
`ECONOMICAMENTE_PROXIMO`, §11.5, "Métricas do Híbrido... na comparação
geral entre métodos, a referência é `CENARIO_ECONOMICAMENTE_SUPERIOR`") —
se aquela tarefa resolver de outra forma, é uma segunda leitura, não uma
contradição desta: os dois módulos comparam grandezas conceitualmente
análogas (penalidade de custo vs. referência) contra o MESMO parâmetro
nomeado, então a conversão deveria ser idêntica; caso divirja, reportar
para confirmação segue a trava do `sdd.config.md` §6.
`P_DIFERENCA_PRAZO_EQUIVALENTE` já está em MESES (mesma unidade de
`ATRASO_PRAZO_VS_AVALANCHE = PRAZO_X - PRAZO_SUPERIOR`), sem conversão.

**Etapa 2 (H-02) — "D primeiro + Avalanche para as restantes", como
`SelecionarAlvo`.** `criar_selecionar_alvo_forcar_depois_avalanche` é o
`SelecionarAlvo` auxiliar que representa exatamente essa frase normativa:
no bootstrap (`DIVIDA_ALVO_ATUAL is None`, `estado.quitadas` ainda sem `D`),
força `D` como alvo, ignorando o benefício marginal; em qualquer chamada
POSTERIOR (D já quitada, ou reranqueamento de resíduo antes da quitação de
D) delega inteiramente à Avalanche real
(`criar_selecionar_alvo_avalanche`, T-49, reaproveitada — nunca duplicada,
ver instrução da tarefa "não duplicar código de ordenação por benefício
marginal"). Esta MESMA função serve dois papéis: (a) dentro de
`_avaliar_candidata`, para produzir `CENARIO_HIBRIDO_D` de cada candidata
na Etapa 2; (b) — com `D = D*` — como o motor real de
`criar_selecionar_alvo_hibrido`, a `SelecionarAlvo` pública deste módulo
(Etapa 5/H-05, fases H-06/H-07). Não há dois códigos fazendo a mesma coisa.

**Parâmetro `e: EstadoFinanceiro` — mesma extensão documentada já usada por
`executar_mes`/`simular_cenario` (`engine/ciclo_mensal.py`, "Parâmetro
adicional... extensão documentada do contrato do plano").**
`escolher_D_ESTRELA`/`criar_selecionar_alvo_hibrido` precisam simular
`CENARIO_HIBRIDO_D` (H-02) e a Avalanche de referência (H-01) via
`simular_cenario(e, dg, dividas, sel, p)`, cuja assinatura já exige `e`
(mesmo sem uso direto por aquela função hoje — `noqa: ARG001` em
`ciclo_mensal.py`). Este módulo apenas repassa o `EstadoFinanceiro` real do
chamador — nunca constrói um objeto vazio/inválido só para satisfazer o
tipo.

**H-06 — "D* não pode ser substituída pela evolução mensal dos saldos".**
Garantido pela MESMA dupla camada já documentada em `engine/metodos/
avalanche.py` (`O-02`): estruturalmente, `executar_mes` só chama `sel()`
quando `DIVIDA_ALVO_ATUAL is None` (alvo ainda não definido, ou acabou de
ser quitado) — nunca por mera passagem de mês (`M-05`); e defensivamente,
dentro da própria função devolvida aqui, que devolve o alvo corrente sem
recalcular se ele ainda não foi quitado. O parâmetro `EVENTO_RECALCULO_
EXTERNO` de H-06 é decidido por QUEM ORQUESTRA vários snapshots
(`engine/motor.py`, fora do escopo desta tarefa) — este módulo não vê
eventos externos, só o que `EstadoSimulacao`/`SelecionarAlvo` expõem.

**H-07 — "Avalanche event-driven — recalcular após cada quitação, nunca por
passagem de mês".** É exatamente o comportamento de `criar_selecionar_alvo_
avalanche` (T-49, `O-02`) reaproveitado sem modificação: reranqueia apenas
quando chamada (bootstrap ou cascata de resíduo), nunca por hábito mensal.

**Elegibilidade — mesmo padrão de `avalanche.py`/`bola_de_neve.py`.** Este
módulo recebe `dividas: Mapping[str, Divida]` já resolvido pelo chamador
(inventário elegível — gates aplicados fora daqui, `T-53` não depende de
`engine/gates.py`, mesma decisão de T-49/T-51). "Respeitados os gates" (H-02)
é responsabilidade de quem monta esse `Mapping` antes de chamar as funções
deste módulo, não deste módulo.

**`VALOR_FLUXO_LIBERADO` no desempate (H-04, nível 3) — mesma leitura de
`O-05`.** `engine/metodos/bola_de_neve.py` já resolveu a mesma ambiguidade
("`VALOR_FLUXO_LIBERADO` da dívida" não é campo nomeado em `Divida`) lendo
`PAGAMENTO_MENSAL_EFETIVO` — o que a dívida de fato libera de orçamento
quando quitada (`F-01`, `AC-32`, `EC-18`). Reaproveitada aqui a mesma
leitura, pelo mesmo motivo (ver docstring daquele módulo).

**`BENEFICIO_MARGINAL_AMORTIZACAO` no desempate (H-04, nível 5).** Calculado
com `calcular_beneficio_marginal` (T-39, `engine/beneficio_marginal.py`),
`delta_disponivel = MIN(CAPACIDADE_ATAQUE_CONSERVADORA, VALOR_RELEVANTE_
PARA_QUITACAO)` — mesmo `DELTA_TESTE_AVALANCHE` de `§11.1`/`AC-19`, já que
H-04 não prescreve um delta diferente para este nível de desempate.
`CAPACIDADE_ATAQUE_CONSERVADORA` chega como parâmetro explícito de
`escolher_D_ESTRELA` (o mesmo valor usado para simular os cenários da
Etapa 2 — `Cenario`/`simular_cenario` já a recebem via `Diagnostico`).
`DESCONHECIDO` perde este nível de desempate (pior valor possível), mesmo
tratamento já usado em `_chave_desempate_O05` de `bola_de_neve.py` —
nunca um número estimado (RF-16).

REGRAS: RF-07, RF-08, H-01, H-02, H-03, H-04, H-05, H-06, H-07, H-08, AC-03,
EC-03, §5.3, §11.5
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final

from engine.beneficio_marginal import calcular_beneficio_marginal
from engine.ciclo_mensal import Cenario, EstadoSimulacao, SelecionarAlvo, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.metodos.avalanche import criar_selecionar_alvo_avalanche
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO, Dinheiro, Meses
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO

REGRAS: Final[tuple[str, ...]] = (
    "RF-07",
    "RF-08",
    "H-01",
    "H-02",
    "H-03",
    "H-04",
    "H-05",
    "H-06",
    "H-07",
    "H-08",
    "AC-03",
    "EC-03",
    "§5.3",
    "§11.5",
)


@dataclass(frozen=True, slots=True)
class MetricasHibridoD:
    """Saída intermediária de `_avaliar_candidata` — as três grandezas de
    `H-03`/`H-04` para UMA candidata D, mais os desempates de `H-04`,
    reunidas para auditoria (o revisor refaz a conta sem rodar de novo,
    mesmo princípio de `BeneficioMarginal`/`ComparacaoCenarios`).
    """

    DIVIDA_ID: str
    cenario: Cenario  # CENARIO_HIBRIDO_D completo (H-02) — rastro de auditoria
    MESES_PRIMEIRA_VITORIA: Meses | None
    PENALIDADE_CUSTO_VS_AVALANCHE: Decimal
    ATRASO_PRAZO_VS_AVALANCHE: Meses
    VALOR_FLUXO_LIBERADO: Dinheiro  # H-04 nível 3 — lido como PAGAMENTO_MENSAL_EFETIVO
    PESO_EMOCIONAL: int  # H-04 nível 4 — DESCONHECIDO já resolvido para o pior valor
    BENEFICIO_MARGINAL_AMORTIZACAO: Decimal  # H-04 nível 5 — idem


def criar_selecionar_alvo_forcar_depois_avalanche(
    divida_forcada_id: str, dividas: Mapping[str, Divida], p: Parametros
) -> SelecionarAlvo:
    """`H-02`/`H-05`/`H-06`/`H-07` — "D primeiro + Avalanche para as
    restantes", como `SelecionarAlvo`. Ver docstring do módulo, "Etapa 2".

    No bootstrap (`DIVIDA_ALVO_ATUAL is None` e `divida_forcada_id` ainda
    não quitada), força `divida_forcada_id` como alvo — ignora
    completamente o benefício marginal, a força é o próprio significado de
    "D primeiro" (H-02) e de "FASE_HIBRIDA_1: `DIVIDA_ALVO_ATUAL = D*`"
    (H-06). Uma vez que `divida_forcada_id` já está em `estado.quitadas` —
    ou nunca existiu no inventário (defensivo) — delega inteiramente à
    Avalanche real (`criar_selecionar_alvo_avalanche`, T-49) sobre o
    inventário INTEIRO recebido; a Avalanche já ignora, por construção,
    qualquer `DIVIDA_ID` presente em `estado.quitadas` (ver `avalanche.py`,
    filtro `elegiveis`), então não é preciso remover `divida_forcada_id` de
    `dividas` manualmente — ela nunca volta a ser escolhida depois de
    quitada (H-07: "event-driven", nunca reescolhe o que já foi).
    """
    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, p)

    def selecionar_alvo_hibrido_fase(
        estado: EstadoSimulacao, delta: Dinheiro
    ) -> Divida | None:
        alvo_atual_id = estado.DIVIDA_ALVO_ATUAL
        if alvo_atual_id is not None and alvo_atual_id not in estado.quitadas:
            # H-06: alvo (D* ou herdado da Avalanche pós-D*) fixo até
            # quitação — nenhuma decisão nova aqui, mesmo mecanismo de
            # O-02/O-04 já usado por avalanche.py/bola_de_neve.py.
            return dividas[alvo_atual_id]

        if (
            divida_forcada_id in dividas
            and divida_forcada_id not in estado.quitadas
        ):
            # H-02/H-06: "D primeiro" — força, sem consultar benefício
            # marginal algum. Só ocorre no bootstrap (primeira chamada,
            # DIVIDA_ALVO_ATUAL is None) porque em qualquer chamada
            # subsequente `divida_forcada_id` OU já está em `quitadas`
            # (ramo abaixo) OU o ramo acima já devolveu o alvo herdado sem
            # chegar aqui.
            return dividas[divida_forcada_id]

        # H-07: D* (ou D, na simulação da Etapa 2) já quitada — Avalanche
        # event-driven pura sobre o restante, reranqueando só quando
        # chamada (bootstrap ou cascata de resíduo), nunca por passagem de
        # mês (mesmo comportamento de O-02, reaproveitado sem duplicação).
        return sel_avalanche(estado, delta)

    return selecionar_alvo_hibrido_fase


def _horizonte_penalidade_custo(
    custo_d: Dinheiro, custo_avalanche: Dinheiro
) -> Decimal:
    """`PENALIDADE_CUSTO_VS_AVALANCHE = (CUSTO_D − CUSTO_AVALANCHE) ÷
    CUSTO_AVALANCHE` — mesma fórmula de `PENALIDADE_CUSTO(X)` (§11.5),
    aplicada aqui com a Avalanche como referência (em vez do cenário
    economicamente superior — §11.5 é explícito: "`PENALIDADE_CUSTO_VS_
    AVALANCHE`... são específicas da construção... do Híbrido", a
    referência aqui é sempre a Avalanche, nunca o superior geral).

    `CUSTO_AVALANCHE == 0` é um caso extremo sem fonte normativa (carteira
    de custo zero não existe em nenhum gabarito) — tratado defensivamente
    como penalidade `0` quando os dois custos também são `0` (nenhuma
    diferença: nem penalidade), e como o PIOR valor possível (`Decimal`
    positivo grande) quando `CUSTO_D` é maior que zero sobre uma base zero
    — para nunca dividir por zero silenciosamente, mas também sem inventar
    uma "aprovação" indevida de uma candidata sobre uma base inválida.
    """
    with localcontext(CONTEXTO_MOTOR):
        if custo_avalanche == dinheiro(0):
            if custo_d == dinheiro(0):
                return Decimal(0)
            return Decimal("Infinity")
        return (custo_d - custo_avalanche) / custo_avalanche


def _avaliar_candidata(
    divida_id: str,
    e: EstadoFinanceiro,
    dividas: Mapping[str, Divida],
    cenario_avalanche: Cenario,
    dg: Diagnostico,
    p: Parametros,
) -> MetricasHibridoD:
    """`H-02`/`H-03` para UMA candidata: simula `CENARIO_HIBRIDO_D` (D
    primeiro + Avalanche para o resto) e deriva as três grandezas de
    tolerância mais os campos de desempate de `H-04`.
    """
    sel_d = criar_selecionar_alvo_forcar_depois_avalanche(divida_id, dividas, p)
    cenario_d = simular_cenario(e, dg, dividas, sel_d, p)

    penalidade_custo = _horizonte_penalidade_custo(
        cenario_d.CUSTO_FUTURO_TOTAL, cenario_avalanche.CUSTO_FUTURO_TOTAL
    )
    atraso_prazo = cenario_d.PRAZO_TOTAL - cenario_avalanche.PRAZO_TOTAL

    divida = dividas[divida_id]
    valor_fluxo_liberado = divida.PAGAMENTO_MENSAL_EFETIVO
    valor_fluxo_liberado_chave = (
        valor_fluxo_liberado if valor_fluxo_liberado is not DESCONHECIDO else dinheiro(0)
    )

    peso_emocional = divida.PESO_EMOCIONAL
    peso_emocional_chave = peso_emocional if peso_emocional is not DESCONHECIDO else -1

    resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
    valor_relevante = resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO
    beneficio_marginal_chave = Decimal("-Infinity")  # pior valor: perde o nível 5
    if valor_relevante is not DESCONHECIDO:
        delta_teste = min(dg.CAPACIDADE_ATAQUE_CONSERVADORA, valor_relevante)
        resultado_beneficio = calcular_beneficio_marginal(divida, delta_teste, p)
        if resultado_beneficio.BENEFICIO_MARGINAL_AMORTIZACAO is not DESCONHECIDO:
            beneficio_marginal_chave = resultado_beneficio.BENEFICIO_MARGINAL_AMORTIZACAO

    return MetricasHibridoD(
        DIVIDA_ID=divida_id,
        cenario=cenario_d,
        MESES_PRIMEIRA_VITORIA=cenario_d.MESES_PRIMEIRA_VITORIA,
        PENALIDADE_CUSTO_VS_AVALANCHE=penalidade_custo,
        ATRASO_PRAZO_VS_AVALANCHE=atraso_prazo,
        VALOR_FLUXO_LIBERADO=valor_fluxo_liberado_chave,
        PESO_EMOCIONAL=peso_emocional_chave,
        BENEFICIO_MARGINAL_AMORTIZACAO=beneficio_marginal_chave,
    )


def _e_candidata_valida(metricas: MetricasHibridoD, p: Parametros) -> bool:
    """`H-03` — as três tolerâncias CUMULATIVAS, um único `and`: nenhuma é
    testada isoladamente, todas têm que valer para a MESMA candidata (ver
    docstring do módulo, "Cumulativas, não independentes"). Valores lidos
    de `Parametros.numero()`, nunca hardcoded (critério de aceite 2).

    `MESES_PRIMEIRA_VITORIA is None` (a candidata nunca quita nenhuma
    dívida dentro do horizonte simulado — cenário estourou o horizonte
    antes da primeira vitória) reprova de imediato: não há como comparar
    `None <= P_MESES_VITORIA_RAPIDA`, e RF-16 proíbe inventar um número.
    """
    if metricas.MESES_PRIMEIRA_VITORIA is None:
        return False

    teto_meses_vitoria = p.numero("P_MESES_VITORIA_RAPIDA")
    teto_penalidade_custo = p.numero("P_DIFERENCA_CUSTO_EQUIVALENTE") / dinheiro(100)
    teto_atraso_prazo = p.numero("P_DIFERENCA_PRAZO_EQUIVALENTE")

    return (
        Decimal(metricas.MESES_PRIMEIRA_VITORIA) <= teto_meses_vitoria
        and metricas.PENALIDADE_CUSTO_VS_AVALANCHE <= teto_penalidade_custo
        and Decimal(metricas.ATRASO_PRAZO_VS_AVALANCHE) <= teto_atraso_prazo
    )


def _chave_desempate_H04(
    metricas: MetricasHibridoD,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, str]:
    """`H-04` — os seis níveis, nesta ordem EXATA (ver docstring do módulo):

    1. menor `MESES_PRIMEIRA_VITORIA`
    2. menor `PENALIDADE_CUSTO_VS_AVALANCHE`
    3. maior `VALOR_FLUXO_LIBERADO`
    4. maior `PESO_EMOCIONAL`
    5. maior `BENEFICIO_MARGINAL_AMORTIZACAO`
    6. menor `DIVIDA_ID`

    `sorted` é estável e compara tuplas posição a posição — os níveis 3, 4
    e 5 ("maior") são NEGADOS na chave para que uma única ordenação
    CRESCENTE resolva os seis níveis em uma passada, mesmo padrão de
    `_chave_desempate_O05` (`bola_de_neve.py`). `MESES_PRIMEIRA_VITORIA`
    nunca é `None` aqui: `_e_candidata_valida` já reprovou esse caso antes
    de a candidata chegar a este desempate.
    """
    assert metricas.MESES_PRIMEIRA_VITORIA is not None  # noqa: S101 — invariante de _e_candidata_valida
    return (
        Decimal(metricas.MESES_PRIMEIRA_VITORIA),
        metricas.PENALIDADE_CUSTO_VS_AVALANCHE,
        -metricas.VALOR_FLUXO_LIBERADO,
        Decimal(-metricas.PESO_EMOCIONAL),
        -metricas.BENEFICIO_MARGINAL_AMORTIZACAO,
        metricas.DIVIDA_ID,
    )


def escolher_D_ESTRELA(
    e: EstadoFinanceiro, dividas: Mapping[str, Divida], dg: Diagnostico, p: Parametros
) -> tuple[str | None, tuple[MetricasHibridoD, ...]]:
    """Etapas 1 a 4 (`H-01..H-04`) — determina `D*`, a "dívida especial" do
    Híbrido, e devolve também o rastro completo de métricas de toda
    candidata avaliada (auditoria — o revisor refaz a conta de qualquer
    candidata, escolhida ou não).

    Devolve `(None, metricas)` quando NENHUMA candidata sobrevive às três
    tolerâncias cumulativas de `H-03` — `H-08`/`EC-03`
    (`CENARIO_HIBRIDO = NAO_APLICAVEL`) é `T-54`, fora do escopo desta
    tarefa; aqui o sinal é apenas `D* = None`, nunca uma exceção, nunca uma
    candidata fabricada por aproximação. Ver `# TODO T-54` em
    `criar_selecionar_alvo_hibrido` abaixo, onde este `None` é consumido.

    `dividas` vazio devolve `(None, ())` de imediato — sem candidata
    possível, sem sequer uma Avalanche de referência para calcular.
    """
    if not dividas:
        return None, ()

    # H-01: ORDEM_AVALANCHE como referência de eficiência.
    sel_avalanche = criar_selecionar_alvo_avalanche(dividas, p)
    cenario_avalanche = simular_cenario(e, dg, dividas, sel_avalanche, p)

    if not cenario_avalanche.ORDEM_QUITACAO:
        # Avalanche não conseguiu quitar nenhuma dívida (sem capacidade,
        # sem candidata simulável) — sem referência válida, não há como
        # calcular H-02/H-03 para ninguém. Nenhuma candidata possível.
        return None, ()

    primeira_da_avalanche = cenario_avalanche.ORDEM_QUITACAO[0]

    # H-02: para cada dívida elegível D DIFERENTE da primeira da Avalanche.
    candidatas_ids = sorted(
        divida_id for divida_id in dividas if divida_id != primeira_da_avalanche
    )

    metricas_todas: list[MetricasHibridoD] = []
    for divida_id in candidatas_ids:
        metricas_todas.append(
            _avaliar_candidata(divida_id, e, dividas, cenario_avalanche, dg, p)
        )

    # H-03: filtro cumulativo — cada candidata testada pelas três
    # tolerâncias na mesma expressão `and` (ver `_e_candidata_valida`).
    candidatas_validas = [m for m in metricas_todas if _e_candidata_valida(m, p)]

    if not candidatas_validas:
        return None, tuple(metricas_todas)

    # H-04: desempate lexicográfico de seis níveis, terminando em DIVIDA_ID.
    candidatas_validas.sort(key=_chave_desempate_H04)
    d_estrela = candidatas_validas[0].DIVIDA_ID

    return d_estrela, tuple(metricas_todas)


@dataclass(frozen=True, slots=True)
class ResultadoHibrido:
    """Saída de `criar_selecionar_alvo_hibrido` — `H-05`/`H-08`, `RF-08`,
    `EC-03`. Carrega a classificação formal do cenário Híbrido junto com o
    `SelecionarAlvo`, mesmo padrão de `BeneficioMarginal`
    (`engine/beneficio_marginal.py`), onde o payload nunca aparece
    desacompanhado de uma classificação nomeada — aqui o payload é a
    própria função de seleção, não um número.

    `classificacao` é `CLASSIFICACAO_CENARIO.CALCULAVEL` com
    `selecionar_alvo` presente quando `D*` foi encontrada (H-01..H-05), ou
    `CLASSIFICACAO_CENARIO.NAO_APLICAVEL` com `selecionar_alvo = None`
    quando nenhuma candidata sobrevive às três tolerâncias cumulativas de
    `H-03` (H-08/EC-03). `CLASSIFICACAO_CENARIO.NAO_CALCULAVEL` nunca é
    produzida por este módulo: ela significaria "faltam dados para
    calcular" (`DESCONHECIDO` em cascata, `S-01`), o que é uma categoria
    diferente de "o cálculo foi feito e a regra de negócio concluiu que não
    existe Híbrido aplicável" — as duas jamais se confundem (`S-02`,
    tolerância zero, `tests/conftest.py::assertar_exato`).
    """

    classificacao: CLASSIFICACAO_CENARIO
    selecionar_alvo: SelecionarAlvo | None


def criar_selecionar_alvo_hibrido(
    e: EstadoFinanceiro, dividas: Mapping[str, Divida], dg: Diagnostico, p: Parametros
) -> ResultadoHibrido:
    """Fábrica de `SelecionarAlvo` para o Híbrido — `H-01..H-08`, `EC-03`.

    Executa as Etapas 1-4 (`escolher_D_ESTRELA`) para determinar `D*` e, se
    encontrada, devolve `ResultadoHibrido(CALCULAVEL, sel)` com a
    `SelecionarAlvo` da Etapa 5 (`H-05`): `D*` seguida da Avalanche
    event-driven das restantes (`H-06`/`H-07`, via
    `criar_selecionar_alvo_forcar_depois_avalanche`).

    Devolve `ResultadoHibrido(NAO_APLICAVEL, None)` quando nenhuma
    candidata sobrevive às três tolerâncias — `H-08`/`EC-03`: `CENARIO_
    HIBRIDO = NAO_APLICAVEL` e `ORDEM_HIBRIDA = NAO_APLICAVEL`. Não se
    fabrica um `D*` por aproximação (ex.: a "quase candidata" mais próxima
    do limite) nem se força uma escolha — `escolher_D_ESTRELA` já garante
    isso devolvendo `D* = None`, este ponto apenas traduz esse `None` para
    a classificação formal, sem tocar a decisão em si.

    Diferente de `criar_selecionar_alvo_avalanche`/`criar_selecionar_alvo_
    bola_de_neve` (T-49/T-51), que sempre devolvem uma `SelecionarAlvo`
    válida — o Híbrido pode legitimamente NÃO EXISTIR (H-08), então o tipo
    de retorno reflete essa possibilidade em vez de devolver uma função que
    sempre escolhe `None` silenciosamente.
    """
    d_estrela, _metricas = escolher_D_ESTRELA(e, dividas, dg, p)
    if d_estrela is None:
        # H-08/EC-03: sem candidata válida, o Híbrido é NAO_APLICAVEL — não
        # NAO_CALCULAVEL (que exigiria dado faltante, não é o caso aqui: os
        # dados existem, a conjunção das três tolerâncias de H-03 apenas
        # não foi satisfeita por nenhuma dívida).
        return ResultadoHibrido(
            classificacao=CLASSIFICACAO_CENARIO.NAO_APLICAVEL, selecionar_alvo=None
        )

    # H-05/H-06/H-07: D* primeiro, Avalanche event-driven depois — mesma
    # função auxiliar da Etapa 2, agora com D* como alvo forçado.
    sel = criar_selecionar_alvo_forcar_depois_avalanche(d_estrela, dividas, p)
    return ResultadoHibrido(classificacao=CLASSIFICACAO_CENARIO.CALCULAVEL, selecionar_alvo=sel)
