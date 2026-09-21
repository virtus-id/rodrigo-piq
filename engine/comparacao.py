"""Comparação de cenários — `RF-19`, `RF-20` · §11.5 (dois conceitos DISTINTOS).

`§11.5` da spec canônica define dois conceitos que usam parâmetros diferentes
e não são concorrentes:

1. **Empate material** (`P_DIFERENCA_ECONOMICA_MATERIAL` = 1%, `RF-19`) —
   elege `CENARIO_ECONOMICAMENTE_SUPERIOR`. Implementado por `T-57`.
2. **Proximidade econômica** (`P_DIFERENCA_CUSTO_EQUIVALENTE` = 5% **e**
   `P_DIFERENCA_PRAZO_EQUIVALENTE` = 2 meses, `RF-20`) — classifica
   `ECONOMICAMENTE_PROXIMO` de cada cenário alternativo contra o superior.
   Implementado por esta tarefa (`T-58`), ver `PENALIDADE_CUSTO`/
   `ATRASO_PRAZO`/`ECONOMICAMENTE_PROXIMO` abaixo.

**Risco explícito da §8 da spec** (linha "Confundir `P_DIFERENCA_ECONOMICA_
MATERIAL` (1%) com `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%)"): o trecho do
empate material em `comparar_cenarios` (`RF-19`) só lê o primeiro parâmetro;
`_avaliar_proximidade_economica` (passo da proximidade, `RF-20`, `T-58`) só
lê o segundo e o terceiro (`P_DIFERENCA_PRAZO_EQUIVALENTE`, em meses, sem
conversão). Os dois nunca aparecem na mesma expressão.

**Empate material — `eleger_CENARIO_ECONOMICAMENTE_SUPERIOR` (`RF-19`,
`AC-27`, `AC-28`, `EC-19`).** Acha o menor `CUSTO_FUTURO_TOTAL` entre os
cenários calculáveis recebidos. Todo cenário cujo `CUSTO_FUTURO_TOTAL` esteja
a MENOS de `P_DIFERENCA_ECONOMICA_MATERIAL` (1%) desse mínimo está em empate
material — `EC-19` exige que TODOS os empatados concorram simultaneamente
(não só par a par: um cenário a 0,9% do mínimo e outro a 0,95% do mesmo
mínimo empatam entre si mesmo que a diferença ENTRE os dois seja maior que
1%, porque o critério é sempre "distância até o mínimo", nunca "distância
entre pares"). Entre os empatados, vence o de menor `PRAZO_TOTAL`. Se ainda
houver empate de prazo, o desempate final é por `METODO.value` em ordem
alfabética (`AVALANCHE` < `BOLA_DE_NEVE` < `HIBRIDO`) — a spec não define um
critério adicional para este caso (não observado em nenhum gabarito: `GAB-C`
resolve por prazo, `AC-27`/`EC-19` testam apenas o corte de 1%), então a
escolha aqui é puramente para determinismo (nenhum cenário depende de sorte
de iteração) e está documentada, não escondida — ver `_desempatar` abaixo.

**Proximidade econômica — `_avaliar_proximidade_economica` (`RF-20`,
`AC-29`).** Para cada `Cenario` de `cs` que NÃO é o `CENARIO_ECONOMICAMENTE_
SUPERIOR` já eleito (passo anterior), mede-se, sempre contra o SUPERIOR (nunca
contra a Avalanche fixa — diferente de `PENALIDADE_CUSTO_VS_AVALANCHE`/
`ATRASO_PRAZO_VS_AVALANCHE` do Híbrido, que são métricas específicas da
construção do Híbrido, ver `engine/metodos/hibrido.py` e §11.5 in fine):

```
PENALIDADE_CUSTO(X) = (CUSTO_X − CUSTO_SUPERIOR) ÷ CUSTO_SUPERIOR
ATRASO_PRAZO(X)     =  PRAZO_X − PRAZO_SUPERIOR
ECONOMICAMENTE_PROXIMO(X) = PENALIDADE_CUSTO(X) ≤ P_DIFERENCA_CUSTO_EQUIVALENTE
                          E ATRASO_PRAZO(X)     ≤ P_DIFERENCA_PRAZO_EQUIVALENTE
```

`E` é conjunção cumulativa (`AC-29`): falhar qualquer um dos dois eixos basta
para `NAO`, nunca uma disjunção. O próprio `CENARIO_ECONOMICAMENTE_SUPERIOR`
não entra nos três mapas — comparar o superior contra si mesmo (penalidade
0, atraso 0, sempre `SIM`) não é um "cenário alternativo" no sentido de
`AC-29`, e incluí-lo inventaria estrutura sem consumidor normativo.

**Convenção de parâmetro percentual (ver `engine/diagnostico.py`, mesma
nota; e `engine/metodos/hibrido.py::_horizonte_penalidade_custo`, mesma
leitura para `P_DIFERENCA_CUSTO_EQUIVALENTE`).** `P_DIFERENCA_ECONOMICA_
MATERIAL` e `P_DIFERENCA_CUSTO_EQUIVALENTE` são armazenados em pontos
percentuais no JSON (`1` == "1%", `5` == "5%"), não em fração —
`Parametros.numero()` devolve o `Decimal` cru. Este módulo converte
explicitamente para fração dividindo por `Decimal(100)` no ponto de uso
(`_fracao_percentual`), nunca embutindo o `100` implicitamente na conta.
`P_DIFERENCA_PRAZO_EQUIVALENTE` já está em MESES (mesma unidade de
`ATRASO_PRAZO`), sem conversão.

REGRAS: RF-19, RF-20, AC-27, AC-28, AC-29, EC-19
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.ciclo_mensal import Cenario
from engine.parametros import Parametros
from engine.tipos import METODO, Meses

REGRAS: Final[tuple[str, ...]] = ("RF-19", "RF-20", "AC-27", "AC-28", "AC-29", "EC-19")

_CEM: Final[Decimal] = Decimal(100)


def _fracao_percentual(pontos_percentuais: Decimal) -> Decimal:
    """Converte um `P_*` percentual (pontos, ex. `1` == "1%") em fração
    (`Decimal("0.01")`). Mesma convenção de `engine/diagnostico.py::
    _fracao_percentual` — duplicada aqui (não importada) porque é privada
    daquele módulo e cada consumidor de um `P_*` percentual converte no
    próprio ponto de uso, sem embutir o `100` implicitamente."""
    return pontos_percentuais / _CEM


@dataclass(frozen=True, slots=True)
class ComparacaoCenarios:
    """§4 do plano técnico (`plans/motor-calculo.plan.md`, linhas 540-553) —
    saída de `comparar_cenarios`.

    **Campos do empate material (`T-57`, `RF-19`):**
    `CENARIO_ECONOMICAMENTE_SUPERIOR`, `empatados_materialmente`,
    `DIFERENCA_PERCENTUAL` (este último não está no snippet literal do
    plano, mas é exigido pela descrição de `T-57`: "expor... a diferença
    percentual de cada cenário perdedor, necessário para T-58/T-59" — mesma
    fração de `PENALIDADE_CUSTO`/`PENALIDADE_CUSTO_VS_AVALANCHE`, mas medida
    contra `CENARIO_ECONOMICAMENTE_SUPERIOR`, não contra a Avalanche).

    **Campos da proximidade econômica (`T-58`, `RF-20`, `AC-29`):**
    `PENALIDADE_CUSTO`, `ATRASO_PRAZO`, `ECONOMICAMENTE_PROXIMO` — exatamente
    o contrato do snippet do plano, um `Mapping[METODO, ...]` por eixo (não
    um dataclass auxiliar por método: o plano já fixa a forma "um mapa por
    métrica", e mantê-la evita duplicar `METODO` como chave em três lugares
    diferentes). As chaves dos três mapas são os métodos de `cs` MENOS o
    `CENARIO_ECONOMICAMENTE_SUPERIOR` (comparar o superior contra si mesmo
    não é um "cenário alternativo", `AC-29`). `PENALIDADE_CUSTO`/
    `ATRASO_PRAZO` ficam expostos como valores numéricos brutos (não só o
    booleano agregado) para auditoria/relatório futuro — critério de aceite
    4 de `T-58`.
    """

    CENARIO_ECONOMICAMENTE_SUPERIOR: METODO
    empatados_materialmente: tuple[METODO, ...]  # < P_DIFERENCA_ECONOMICA_MATERIAL (1%)
    DIFERENCA_PERCENTUAL: Mapping[METODO, Decimal]  # fração; vencedor mapeia para 0
    PENALIDADE_CUSTO: Mapping[METODO, Decimal]  # fração; exclui o SUPERIOR
    ATRASO_PRAZO: Mapping[METODO, Meses]  # exclui o SUPERIOR
    ECONOMICAMENTE_PROXIMO: Mapping[METODO, bool]  # <=5% E <=2 meses, cumulativo; exclui o SUPERIOR


def comparar_cenarios(cs: Sequence[Cenario], p: Parametros) -> ComparacaoCenarios:
    """`RF-19`/`RF-20`/`AC-27`/`AC-28`/`AC-29`/`EC-19` — elege `CENARIO_
    ECONOMICAMENTE_SUPERIOR` e avalia `ECONOMICAMENTE_PROXIMO` de cada
    cenário alternativo contra ele (§11.5, ambos os parágrafos).

    Pré-condição: todo `Cenario` de `cs` tem `metodo` preenchido (não
    `None`) — esta função compara MÉTODOS, não simulações anônimas, e
    `ComparacaoCenarios.CENARIO_ECONOMICAMENTE_SUPERIOR` é tipado `METODO`,
    não `Cenario`. `simular_cenario` (`T-46`) ainda não preenche `Cenario.
    metodo` (fica `None` na pipeline atual — ver `engine/ciclo_mensal.py`,
    comentário "T-49+: nenhum método real ainda implementado"); quem chama
    `comparar_cenarios` é responsável por rotular cada `Cenario` com seu
    `METODO` (`dataclasses.replace(cenario, metodo=...)`) antes de passar a
    sequência aqui — mesmo padrão já usado pelos três gabaritos de `GAB-C`
    (`tests/gabaritos/test_gabarito_c_*.py`), que sabem qual `sel` produziu
    qual `Cenario`. `ValueError` ruidoso se a pré-condição falhar, nunca um
    `METODO` inventado.

    `cs` tem 2 ou 3 elementos, dependendo de o Híbrido ser calculável ou
    `NAO_APLICAVEL` para a carteira (`H-08`, `EC-03`, `T-54`) — o chamador
    filtra para calculáveis antes de montar `cs`; esta função não decide
    elegibilidade, apenas compara custos e prazos do que recebeu.

    Passos (§11.5):
    1. Menor `CUSTO_FUTURO_TOTAL` entre os cenários de `cs`.
    2. Empate material: todo cenário com `(CUSTO_X - CUSTO_MINIMO) /
       CUSTO_MINIMO < P_DIFERENCA_ECONOMICA_MATERIAL` (`EC-19`: TODOS os
       que satisfazem, não só o par mais próximo).
    3. Vence, entre os empatados, o de menor `PRAZO_TOTAL`; empate residual
       de prazo desempata por `METODO.value` alfabético (ver docstring do
       módulo — decisão documentada, não normativa).
    4. Proximidade econômica (`RF-20`, `AC-29`): para cada cenário de `cs`
       diferente do vencedor do passo 3, `PENALIDADE_CUSTO`/`ATRASO_PRAZO`
       contra o vencedor, e `ECONOMICAMENTE_PROXIMO` pela conjunção
       cumulativa dos dois tetos (`_avaliar_proximidade_economica`).

    **`T-78` — `CUSTO_FUTURO_TOTAL` zero em todos os cenários.** Achado por
    `T-68` (fora do escopo lá): quando NENHUM cenário de `cs` desembolsou
    nada (`CUSTO_FUTURO_TOTAL = 0` para todos — carteiras como `GAB-A`,
    déficit puro sem `CAPACIDADE_ATAQUE_ATUAL` sobrando, ou `GAB-B`, única
    dívida com `SALDO_DEVEDOR_ATUAL = DESCONHECIDO`, nenhum método consegue
    simular quitação real), o passo 1 acima produz `CUSTO_MINIMO = 0` e o
    passo 2 divide por ele — antes desta correção, `decimal.InvalidOperation`
    (`DivisionUndefined`).

    Semântica adotada, decidida explicitamente (não é normativa da spec:
    §11.5 não prevê este caso extremo, ver `specs/motor-calculo.spec.md`):
    "está a menos de 1% do mínimo?" com mínimo zero só tem resposta exata
    quando o próprio custo também é zero — zero está a 0% de zero, "nenhuma
    diferença", não um erro. Todo cenário com `CUSTO_FUTURO_TOTAL = 0`
    empata materialmente com o mínimo zero exatamente como empataria contra
    qualquer outro mínimo igual ao seu; o desempate cai no passo 3
    (`PRAZO_TOTAL`) como no caminho normal — nenhum tratamento especial além
    da eleição do `CENARIO_ECONOMICAMENTE_SUPERIOR`. Mesmo raciocínio se
    aplica a `PENALIDADE_CUSTO` em `_avaliar_proximidade_economica` quando
    `superior.CUSTO_FUTURO_TOTAL = 0`. A pertença ao empate/proximidade é
    sempre decidida por COMPARAÇÃO DE CUSTO direta nesse ramo (nunca por uma
    fração numérica fabricada para representar "custo positivo sobre base
    zero", que não tem valor finito correto) — `DIFERENCA_PERCENTUAL`/
    `PENALIDADE_CUSTO` expostos ficam em `Decimal(0)` como valor neutro de
    auditoria nesse ramo residual (não observado em `GAB-A`/`GAB-B`, onde
    TODOS os cenários zeram simultaneamente, mas estruturalmente possível se
    um método desembolsasse algo e outro não).
    """
    if not cs:
        raise ValueError(
            "comparar_cenarios exige ao menos um Cenario calculável — "
            "lista vazia não tem cenário superior a eleger."
        )

    metodos: list[METODO] = []
    for cenario in cs:
        if cenario.metodo is None:
            raise ValueError(
                "comparar_cenarios exige Cenario.metodo preenchido — "
                "rotule cada Cenario com dataclasses.replace(cenario, "
                "metodo=...) antes de comparar (ver docstring da função)."
            )
        metodos.append(cenario.metodo)
    if len(metodos) != len(set(metodos)):
        raise ValueError(
            f"comparar_cenarios recebeu METODO repetido em cs: {metodos!r} — "
            "cada método concorre com no máximo um Cenario."
        )

    limiar_material = _fracao_percentual(p.numero("P_DIFERENCA_ECONOMICA_MATERIAL"))

    custo_minimo = min(cenario.CUSTO_FUTURO_TOTAL for cenario in cs)

    diferenca_percentual: dict[METODO, Decimal] = {}
    empatados: list[Cenario] = []
    for cenario in cs:
        assert cenario.metodo is not None  # já validado acima; só para mypy --strict
        # T-78 (bug achado por T-68): CUSTO_FUTURO_TOTAL (= DESEMBOLSO_
        # ACUMULADO, engine/ciclo_mensal.py) nunca é negativo, mas PODE ser
        # zero em TODOS os cenários simultaneamente — carteiras sem nenhuma
        # quitação real em nenhum método (GAB-A, déficit puro: sem
        # CAPACIDADE_ATAQUE_ATUAL sobrando; GAB-B, saldo devedor
        # DESCONHECIDO: nenhum cenário consegue simular quitação). Nesse
        # caso `custo_minimo == 0` e `(CUSTO_X - 0) / 0` é indefinido —
        # tratado explicitamente ANTES da divisão, nunca via try/except.
        #
        # Semântica decidida (RF-19/AC-27, §11.5): "está a menos de 1% do
        # mínimo?" quando o mínimo é zero só tem resposta exata para
        # CUSTO_X == 0 — zero está a 0% de zero ("nenhuma diferença", não
        # erro), mesmo patamar do mínimo, entra no empate igual entraria se
        # custo_minimo fosse qualquer outro valor igual ao seu. A pertença
        # ao empate é decidida por essa comparação de custo diretamente
        # (nunca por uma fração fabricada). Não é o cenário coberto pelos
        # gabaritos GAB-A/GAB-B desta tarefa (lá TODOS os cenários zeram
        # simultaneamente), mas o mesmo `custo_minimo == 0` também cobre o
        # caso residual CUSTO_X > 0: sem fração finita correta para "custo
        # positivo sobre base zero", DIFERENCA_PERCENTUAL fica em 0 (mesmo
        # valor "neutro" do ramo empatado) e a exclusão do empate é
        # garantida pela comparação de custo abaixo, não por essa fração.
        if custo_minimo == 0:
            diferenca = Decimal(0)
            no_empate = cenario.CUSTO_FUTURO_TOTAL == custo_minimo
        else:
            diferenca = (cenario.CUSTO_FUTURO_TOTAL - custo_minimo) / custo_minimo
            no_empate = diferenca < limiar_material
        diferenca_percentual[cenario.metodo] = diferenca
        if no_empate:
            empatados.append(cenario)

    empatados_metodos = tuple(
        cenario.metodo for cenario in empatados if cenario.metodo is not None
    )
    vencedor = _desempatar(empatados)

    cenario_superior = next(cenario for cenario in cs if cenario.metodo == vencedor)
    penalidade_custo, atraso_prazo, economicamente_proximo = _avaliar_proximidade_economica(
        cs, cenario_superior, p
    )

    return ComparacaoCenarios(
        CENARIO_ECONOMICAMENTE_SUPERIOR=vencedor,
        empatados_materialmente=empatados_metodos,
        DIFERENCA_PERCENTUAL=diferenca_percentual,
        PENALIDADE_CUSTO=penalidade_custo,
        ATRASO_PRAZO=atraso_prazo,
        ECONOMICAMENTE_PROXIMO=economicamente_proximo,
    )


def _avaliar_proximidade_economica(
    cs: Sequence[Cenario], superior: Cenario, p: Parametros
) -> tuple[dict[METODO, Decimal], dict[METODO, Meses], dict[METODO, bool]]:
    """`RF-20`/`AC-29` — `PENALIDADE_CUSTO`, `ATRASO_PRAZO` e
    `ECONOMICAMENTE_PROXIMO` de cada cenário de `cs` diferente de `superior`,
    sempre medidos contra `superior` (nunca contra a Avalanche fixa — ver
    docstring do módulo).

    Lê exclusivamente `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%, convertido para
    fração como `_fracao_percentual`) e `P_DIFERENCA_PRAZO_EQUIVALENTE`
    (2 meses, já na unidade de `ATRASO_PRAZO`, sem conversão) —
    `P_DIFERENCA_ECONOMICA_MATERIAL` (1%, usado só no empate material acima)
    nunca entra aqui (risco explícito da §8 da spec, ver docstring do
    módulo).

    `ECONOMICAMENTE_PROXIMO(X)` é `SIM` (`True`) apenas quando os DOIS eixos
    passam cumulativamente (`AC-29`: um único `and`, nunca um `or` nem dois
    filtros independentes) — `PENALIDADE_CUSTO(X) <= P_DIFERENCA_CUSTO_
    EQUIVALENTE` E `ATRASO_PRAZO(X) <= P_DIFERENCA_PRAZO_EQUIVALENTE`.
    """
    teto_penalidade_custo = _fracao_percentual(p.numero("P_DIFERENCA_CUSTO_EQUIVALENTE"))
    teto_atraso_prazo = p.numero("P_DIFERENCA_PRAZO_EQUIVALENTE")

    penalidade_custo: dict[METODO, Decimal] = {}
    atraso_prazo: dict[METODO, Meses] = {}
    economicamente_proximo: dict[METODO, bool] = {}
    for cenario in cs:
        assert cenario.metodo is not None  # já validado em comparar_cenarios
        if cenario.metodo == superior.metodo:
            continue  # o superior não concorre contra si mesmo (AC-29)

        # T-78 — mesmo tratamento explícito de `comparar_cenarios` para
        # CUSTO_FUTURO_TOTAL == 0 (ver comentário lá): se o SUPERIOR custa
        # zero, `(CUSTO_X - 0) / 0` é indefinido — tratado ANTES da divisão.
        # Um cenário com custo também zero está no mesmo patamar do
        # superior (PENALIDADE_CUSTO = 0, exato, "nenhuma diferença"); um
        # cenário com custo > 0 comparado a uma base zero não tem fração
        # finita correta, mas a pergunta de `ECONOMICAMENTE_PROXIMO` (`<=
        # P_DIFERENCA_CUSTO_EQUIVALENTE`) é decidida diretamente pela
        # comparação de custo, sem fabricar um número para representar
        # "infinitamente pior": custo estritamente maior que uma base zero
        # nunca passa no teto de proximidade de custo.
        if superior.CUSTO_FUTURO_TOTAL == 0:
            penalidade = Decimal(0)
            custo_dentro_do_teto = cenario.CUSTO_FUTURO_TOTAL == superior.CUSTO_FUTURO_TOTAL
        else:
            penalidade = (
                cenario.CUSTO_FUTURO_TOTAL - superior.CUSTO_FUTURO_TOTAL
            ) / superior.CUSTO_FUTURO_TOTAL
            custo_dentro_do_teto = penalidade <= teto_penalidade_custo
        atraso = cenario.PRAZO_TOTAL - superior.PRAZO_TOTAL

        penalidade_custo[cenario.metodo] = penalidade
        atraso_prazo[cenario.metodo] = atraso
        economicamente_proximo[cenario.metodo] = (
            custo_dentro_do_teto and Decimal(atraso) <= teto_atraso_prazo
        )

    return penalidade_custo, atraso_prazo, economicamente_proximo


def _desempatar(empatados: Sequence[Cenario]) -> METODO:
    """Vence o menor `PRAZO_TOTAL` entre os empatados materialmente
    (`AC-27`). Resíduo de empate de prazo (não coberto por nenhum gabarito
    normativo) desempata por `METODO.value` alfabético — decisão
    documentada no módulo, não normativa, apenas para garantir
    determinismo."""
    chaves: list[tuple[int, str, METODO]] = []
    for cenario in empatados:
        assert cenario.metodo is not None  # já validado em comparar_cenarios
        chaves.append((cenario.PRAZO_TOTAL, cenario.metodo.value, cenario.metodo))
    return min(chaves)[2]
