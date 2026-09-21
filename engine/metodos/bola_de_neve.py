"""Seleção de alvo do método Bola de Neve — RF-06 · §5.2, §11.2 · O-04, O-05 ·
AC-02 · T-51.

`O-04`/`O-05` (`piq-app-spec.md` §5.2, citada por `specs/motor-calculo.spec.md`
RF-06): a Bola de Neve ordena as dívidas elegíveis por
`VALOR_RELEVANTE_PARA_QUITACAO` CRESCENTE — a menor primeiro — e ataca a de
menor valor (`O-04`). O alvo permanece fixo até ser quitado ou até ocorrer um
evento externo, sem reranqueamento por mera passagem de mês (mesmo `O-02` da
Avalanche, aplicado aqui pelo enunciado de `O-04`: "Alvo fixo até quitação ou
evento; não é reranqueada mensalmente").

**Cadeia de desempate — `O-05`, ordem EXATA (`piq-app-spec.md` linha 147/356,
citada caractere por caractere):**

```
Desempates, nesta ordem: maior VALOR_FLUXO_LIBERADO; maior custo financeiro;
maior PESO_EMOCIONAL; DIVIDA_ID como desempate técnico final.
```

Os quatro níveis, na ordem em que são aplicados quando o nível anterior
empata:

1. Maior `VALOR_FLUXO_LIBERADO` — o quanto a dívida libera de orçamento
   quando quitada.
2. Maior custo financeiro.
3. Maior `PESO_EMOCIONAL`.
4. `DIVIDA_ID` — desempate técnico final, garante determinismo total mesmo
   com os três níveis anteriores empatados (mesmo papel de `O-01`/`H-04` na
   Avalanche e no Híbrido — `engine/metodos/avalanche.py`,
   `plans/motor-calculo.plan.md` linha 785).

**Nível 1 — `VALOR_FLUXO_LIBERADO` por dívida, decisão de leitura.**
`VALOR_FLUXO_LIBERADO` como CAMPO nomeado só existe hoje em
`ResultadoMes` (`engine/ciclo_mensal.py`) — a soma agregada do MÊS inteiro,
não um valor por dívida candidata. `O-05` compara dívidas individuais entre
si ("maior `VALOR_FLUXO_LIBERADO`" de uma candidata contra outra), então a
grandeza precisa existir por dívida. `engine/ciclo_mensal.py::executar_mes`
(`M-10`, `F-01`, `AC-32`, `EC-18`, comentário "libera o
`PAGAMENTO_MENSAL_EFETIVO` que de fato saía do orçamento por ela") já
resolveu essa mesma pergunta para o agregado do mês: o que UMA dívida
quitada libera é exatamente `PAGAMENTO_MENSAL_EFETIVO`, nunca a parcela
contratual. Reaproveitada aqui a mesma leitura — "`VALOR_FLUXO_LIBERADO` da
dívida" no desempate é `Divida.PAGAMENTO_MENSAL_EFETIVO` — em vez de inventar
uma segunda noção de fluxo liberado por dívida que a canônica não nomeia.
`DESCONHECIDO` não é comparável: tratado como o menor valor possível deste
nível (perde o desempate), nunca estimado (RF-16) — mesmo critério do nível
2 abaixo.

**Nível 2 — "maior custo financeiro", decisão de leitura, fonte ambígua.**
Nenhum campo do esquema (`engine/estado.py::Divida`) se chama literalmente
"custo financeiro" — não é uma variável nomeada da canônica, ao contrário de
`VALOR_FLUXO_LIBERADO` e `PESO_EMOCIONAL`, que são. `engine/
beneficio_marginal.py` já enfrentou a mesma ambiguidade de leitura para a
Avalanche (ver docstring daquele módulo, "Uso da taxa como substituto do
benefício marginal") e resolveu adotando `TAXA_EFETIVA_MENSAL_NORMALIZADA`
como a grandeza que representa o custo financeiro de uma dívida — é
literalmente a taxa de juros efetiva mensal que a dívida cobra, a leitura
mais direta de "custo financeiro" disponível no esquema sem inventar um
cálculo novo. A mesma leitura é adotada aqui, pelo mesmo motivo: preserva a
mesma variável já usada com esse papel em outro método, sem introduzir uma
segunda noção de "custo" que a canônica não nomeia. Se esta leitura divergir
da intenção do especialista, é uma decisão registrada aqui, não definitiva —
reportar para confirmação segue a trava da §6 do `sdd.config.md`
("metodologia não se decide implementando"). `DESCONHECIDO` também perde
este nível de desempate (mesmo tratamento do nível 1: RF-16 proíbe estimar).

**Nível 3 — `PESO_EMOCIONAL`.** Campo já modelado em `Divida.PESO_EMOCIONAL:
int | Desconhecido` (escala 0–10, comentário `# 0–10 · O-05/H-04` em
`engine/estado.py`). `DESCONHECIDO` perde o nível, mesmo tratamento dos dois
anteriores.

**Nível 4 — `DIVIDA_ID`.** Desempate final absoluto — sempre um `str`
concreto (`Divida.DIVIDA_ID: str`, nunca `DinheiroTalvez`/`Desconhecido`),
então este nível SEMPRE resolve qualquer empate remanescente: determinismo
total garantido mesmo que os três níveis anteriores empatem exatamente
(comentário `# O-05/H-04: desempate final` em `engine/estado.py`).

**`VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` — não entra na ordenação
normal.** Dívida cujo `compor_VALOR_RELEVANTE_PARA_QUITACAO` (T-27/T-28,
`engine/valor_quitacao.py`) devolve `DESCONHECIDO` fica de fora da
ordenação por `O-04` inteiramente — não é comparável a nenhuma outra
candidata, e RF-16 proíbe estimar um substituto. A triagem FORMAL desse caso
já existe: `engine/gates.py::aplicar_gate_1_informacao` (T-29, já
implementado) desvia exatamente esta situação para
`DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE` +
`GATE_PENDENTE.INFORMACAO` antes que a dívida chegue à ordenação (mesmo
comentário em `aplicar_gate_1_informacao`: "`VALOR_RELEVANTE_PARA_QUITACAO =
DESCONHECIDO`... `AC-44`: inelegível, `INFORMACAO_PENDENTE`... não ordenada
nem atacada até a confirmação"). Esta função não duplica essa triagem — ela
só garante, defensivamente, que uma dívida nesse estado nunca é escolhida
como alvo aqui (mesmo padrão de `engine/metodos/avalanche.py`, `continue` ao
encontrar `VALOR_RELEVANTE_PARA_QUITACAO is DESCONHECIDO`): fica de fora da
ordenação normal, exposta separadamente em
`ResultadoOrdenacaoBolaDeNeve.informacao_pendente` para quem for montar a
fila completa (`ORDEM_ACOES`, fora do escopo desta tarefa) — auditável, sem
inventar uma segunda modelagem de `INFORMACAO_PENDENTE`.

**Fábrica, não função direta — mesmo motivo de `avalanche.py`.**
`SelecionarAlvo` é exatamente `Callable[[EstadoSimulacao, Dinheiro], Divida |
None]` (`engine/ciclo_mensal.py`) — sem `Mapping[str, Divida]` na
assinatura. `criar_selecionar_alvo_bola_de_neve(dividas, p)` devolve um
`Callable` fechado sobre `dividas`/`p` via closure, exatamente como
`criar_selecionar_alvo_avalanche` — a função devolvida É `SelecionarAlvo`,
sem mudança de assinatura. `p` (`Parametros`) não é consumido pela Bola de
Neve hoje (nenhuma fórmula desta tarefa lê um `P_*`) — mantido na assinatura
só por simetria de fábrica com a Avalanche e para não fechar a porta a um
parâmetro futuro sem quebrar o contrato de todas as fábricas de método.

REGRAS: RF-06, O-04, O-05, AC-02, §5.2, §11.2
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.ciclo_mensal import EstadoSimulacao, SelecionarAlvo
from engine.estado import Divida
from engine.parametros import Parametros
from engine.tipos import DESCONHECIDO, Dinheiro
from engine.valor_quitacao import compor_VALOR_RELEVANTE_PARA_QUITACAO

REGRAS: Final[tuple[str, ...]] = ("RF-06", "O-04", "O-05", "AC-02", "§5.2", "§11.2")


@dataclass(frozen=True, slots=True)
class ResultadoOrdenacaoBolaDeNeve:
    """Saída auxiliar de `_ordenar_por_valor_relevante` — auditoria da
    ordenação `O-04`/`O-05` e da triagem de `INFORMACAO_PENDENTE` (ver
    docstring do módulo).

    `ordem` é a lista de `DIVIDA_ID` elegíveis, já na ordem final de ataque
    (`O-04` crescente + cadeia `O-05`). `informacao_pendente` é o
    subconjunto que NÃO participou da ordenação por
    `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` — exposto separadamente,
    nunca descartado em silêncio (RF-16).
    """

    ordem: tuple[str, ...]
    informacao_pendente: tuple[str, ...]


def _chave_desempate_O05(
    divida_id: str,
    divida: Divida,
) -> tuple[Decimal, Decimal, int, str]:
    """`O-05`, os quatro níveis nesta ordem EXATA — ver docstring do módulo:

    1. maior `VALOR_FLUXO_LIBERADO` (lido como `PAGAMENTO_MENSAL_EFETIVO`);
    2. maior custo financeiro (lido como `TAXA_EFETIVA_MENSAL_NORMALIZADA`);
    3. maior `PESO_EMOCIONAL`;
    4. `DIVIDA_ID` — desempate técnico final.

    `sorted` do Python é estável e compara tuplas posição a posição — uma
    única chave, com os três primeiros níveis NEGADOS (`O-05` pede "maior"
    em todos os três, mas a ordenação externa por `VALOR_RELEVANTE_PARA_
    QUITACAO` é crescente) resolve os quatro níveis em uma única
    comparação, sem sub-ordenações em cascata. `DESCONHECIDO` em qualquer um
    dos três primeiros níveis vira o pior valor possível daquele nível
    (perde o desempate) — nunca um número estimado (RF-16).
    """
    fluxo_liberado = divida.PAGAMENTO_MENSAL_EFETIVO
    fluxo_liberado_chave = (
        -fluxo_liberado if fluxo_liberado is not DESCONHECIDO else Decimal("Infinity")
    )

    custo_financeiro = divida.TAXA_EFETIVA_MENSAL_NORMALIZADA
    custo_financeiro_chave = (
        -custo_financeiro if custo_financeiro is not DESCONHECIDO else Decimal("Infinity")
    )

    peso_emocional = divida.PESO_EMOCIONAL
    peso_emocional_chave = (
        -peso_emocional if peso_emocional is not DESCONHECIDO else 1  # pior: 0..10 negado é -10..0
    )

    return (fluxo_liberado_chave, custo_financeiro_chave, peso_emocional_chave, divida_id)


def _ordenar_por_valor_relevante(
    elegiveis: Mapping[str, Divida],
) -> ResultadoOrdenacaoBolaDeNeve:
    """`O-04` + `O-05`: ordena os `DIVIDA_ID` elegíveis por
    `VALOR_RELEVANTE_PARA_QUITACAO` CRESCENTE (`compor_
    VALOR_RELEVANTE_PARA_QUITACAO`, T-27/T-28 — NUNCA `SALDO_DEVEDOR_ATUAL`
    direto), com a cadeia de desempate `O-05` aplicada em cada empate. Uma
    única chave por dívida (valor relevante + os quatro níveis de `O-05`) —
    `sorted` estável resolve tudo em uma passada, sem sub-ordenações.

    Dívida com `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` não entra na
    ordenação — vai para `informacao_pendente` (ver docstring do módulo).
    """
    valores_relevantes: dict[str, Dinheiro] = {}
    informacao_pendente: list[str] = []
    for divida_id, divida in elegiveis.items():
        resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
        valor_relevante = resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO
        if valor_relevante is DESCONHECIDO:
            # RF-16/AC-44: sem VALOR_RELEVANTE_PARA_QUITACAO não há como
            # comparar esta dívida a nenhuma outra por O-04 — desviada para
            # INFORMACAO_PENDENTE (triagem formal é Gate 1, engine/gates.py,
            # fora do escopo desta função; aqui só a exclusão defensiva).
            informacao_pendente.append(divida_id)
            continue
        valores_relevantes[divida_id] = valor_relevante

    ordenados = sorted(
        valores_relevantes.keys(),
        key=lambda divida_id: (
            valores_relevantes[divida_id],
            _chave_desempate_O05(divida_id, elegiveis[divida_id]),
        ),
    )

    return ResultadoOrdenacaoBolaDeNeve(
        ordem=tuple(ordenados),
        informacao_pendente=tuple(sorted(informacao_pendente)),
    )


def criar_selecionar_alvo_bola_de_neve(
    dividas: Mapping[str, Divida], p: Parametros  # noqa: ARG001 — simetria com avalanche.py
) -> SelecionarAlvo:
    """Fábrica de `SelecionarAlvo` para a Bola de Neve — `O-04`, `O-05`, `AC-02`.

    `dividas` é o inventário completo indexado por `DIVIDA_ID` (mesmo padrão
    de `criar_selecionar_alvo_avalanche`); `p` não é consumido por nenhuma
    fórmula desta tarefa (ver docstring do módulo, "Fábrica, não função
    direta"). A função devolvida é pura em relação a `estado`/`delta` —
    `dividas` é fixo para toda a simulação, nunca mutado. `delta` (a segunda
    posição do tipo `SelecionarAlvo`) não influencia a escolha da Bola de
    Neve: `O-04`/`O-05` ordenam só por `VALOR_RELEVANTE_PARA_QUITACAO` e a
    cadeia de desempate, nunca por capacidade de ataque disponível — ao
    contrário da Avalanche, que testa `BENEFICIO_MARGINAL_AMORTIZACAO` com
    `MIN(delta, VALOR_RELEVANTE_PARA_QUITACAO)`.
    """

    def selecionar_alvo_bola_de_neve(
        estado: EstadoSimulacao, delta: Dinheiro  # noqa: ARG001 — não usado por O-04/O-05
    ) -> Divida | None:
        """`SelecionarAlvo` da Bola de Neve — `Callable[[EstadoSimulacao,
        Dinheiro], Divida | None]`, exatamente o tipo de `engine/
        ciclo_mensal.py`.

        Alvo fixo (`O-04`, mesmo mecanismo de `O-02` na Avalanche — ver
        `engine/metodos/avalanche.py`): se o alvo corrente já aponta para
        uma dívida ainda não quitada, devolve-a sem recalcular a ordenação.

        Caso contrário (bootstrap ou reranqueamento intramês — os únicos
        casos em que `executar_mes` de fato chama esta função, sempre com
        `DIVIDA_ALVO_ATUAL=None`), recalcula a ordenação do zero por
        `VALOR_RELEVANTE_PARA_QUITACAO` crescente com a cadeia `O-05`,
        devolve a primeira — ou `None` se não houver candidata elegível
        (carteira vazia, todas quitadas, ou todas com valor relevante
        `DESCONHECIDO`).
        """
        alvo_atual_id = estado.DIVIDA_ALVO_ATUAL
        if alvo_atual_id is not None and alvo_atual_id not in estado.quitadas:
            # O-04: alvo fixo até quitação (ou evento — decidido pelo
            # chamador, fora desta função). Nenhuma ordenação nova.
            return dividas[alvo_atual_id]

        elegiveis = {
            divida_id: divida
            for divida_id, divida in dividas.items()
            if divida_id not in estado.quitadas
        }
        if not elegiveis:
            return None

        resultado_ordenacao = _ordenar_por_valor_relevante(elegiveis)
        if not resultado_ordenacao.ordem:
            return None

        return dividas[resultado_ordenacao.ordem[0]]

    return selecionar_alvo_bola_de_neve
