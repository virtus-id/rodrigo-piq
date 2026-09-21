"""Classificação de cenários e derivação de `STATUS_METODO` — `RF-08` ·
`S-01..S-05` · `AC-04` · `AC-09` · `T-60`/`T-61`.

`§6` da spec canônica e `specs/motor-calculo.spec.md` `RF-08` exigem que o
motor resuma a confiabilidade geral do resultado num único `STATUS_METODO`
(`engine/tipos.py::STATUS_METODO`, dois membros: `DEFINITIVO_NA_DATA` e
`PROVISORIO`). `T-60` cobriu as três primeiras regras da família `S`:

- `S-01`/`S-02` (tolerância ZERO, `engine/tipos.py::CLASSIFICACAO_CENARIO`):
  `NAO_CALCULAVEL` — faltam dados, `DESCONHECIDO` em cascata — REBAIXA
  `STATUS_METODO`; `NAO_APLICAVEL` — dados completos, mas a regra de
  negócio decidiu que não há resultado aplicável (ex.: Híbrido sem
  candidata via `H-08`, `EC-03`) — é um resultado válido e NÃO rebaixa.
- `AC-09` (`GAB-02`): `INVENTARIO_COMPLETO = False` limita `STATUS_METODO`
  a `PROVISORIO` no máximo, mesmo que todos os cenários sejam `CALCULAVEL`
  — nunca pode alcançar `DEFINITIVO_NA_DATA`.

`T-61` (esta extensão) cobre o restante da família `S` e `METODO_
RECOMENDADO_PIQ`:

- `S-04` (`specs/piq-app-spec.md` §6.1/§9, `EC-05`): SE
  `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` (T-18,
  `engine/comportamento.py::derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`)
  com o `CENARIO_ECONOMICAMENTE_SUPERIOR` (T-57, `engine/comparacao.py`) E
  nenhuma alternativa calculável for `ECONOMICAMENTE_PROXIMA` (T-58,
  `ComparacaoCenarios.ECONOMICAMENTE_PROXIMO`), ENTÃO `STATUS_METODO =
  PROVISORIO` e `REVISAO_HUMANA_OBRIGATORIA = SIM` — o motor não decide
  sozinho quando o comportamento do usuário é incompatível com a única
  saída disponível.
- `S-05` (`EC-04`): Híbrido `NAO_APLICAVEL` com Bola de Neve
  `ECONOMICAMENTE_PROXIMA` **não** aciona `REVISAO_HUMANA_OBRIGATORIA` — a
  Bola de Neve continua sendo uma alternativa comportamental aplicável, e
  `NAO_APLICAVEL` já é resultado de negócio válido (`S-02`), não falha.
  Consequência direta de `S-04` ler `ECONOMICAMENTE_PROXIMO` só sobre
  cenários efetivamente presentes em `cenarios` — um Híbrido `NAO_APLICAVEL`
  simplesmente não concorre como alternativa, mas não bloqueia as demais.
- `AC-04`/`GAB-C`: `METODO_RECOMENDADO_PIQ` — ver `derivar_
  METODO_RECOMENDADO_PIQ` abaixo pela fórmula completa de combinação.

**Estrutural (critério de aceite 3 de `T-60`, preservado por `T-61`).**
`STATUS_METODO` é sempre DERIVADO, nunca atribuído por um caminho
alternativo: não existe setter, não existe campo mutável, e
`ResultadoStatusMetodo` é `frozen`. `derivar_STATUS_METODO` continua
conhecendo apenas `S-01`/`S-02`/`AC-09` (não duplica `S-04`/`S-05`);
`derivar_METODO_RECOMENDADO_PIQ` (`T-61`) COMPÕE sobre o resultado dela —
parte de `ResultadoStatusMetodo.STATUS_METODO`/`motivos` e rebaixa ainda
mais quando `S-04` se aplicar — nunca recalcula `S-01`/`S-02`/`AC-09` do
zero. Mesmo padrão de função pura já usado por `engine/beneficio_
marginal.py::determinar_ordem_status_por_origem` para o `ORDEM_STATUS`
irmão.

**Motivo de auditoria (critério de aceite 4 de `T-60`; critério de aceite 3
de `T-61`).** Cada rebaixamento — por cenário `NAO_CALCULAVEL`, por
inventário incompleto, ou agora por `S-04` — é registrado como uma string
em `motivos`, mesmo padrão de `engine/gates.py::ResultadoGates.motivo`
(aqui uma tupla, porque podem existir vários motivos simultâneos).
`ResultadoMetodoRecomendado.motivo_recomendacao` documenta, à parte, POR
QUE aquele método específico (e não outro) foi escolhido — auditoria da
recomendação em si, distinta da auditoria do rebaixamento de status.

REGRAS: RF-08, S-01, S-02, S-03, S-04, S-05, AC-04, AC-09
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.ciclo_mensal import Cenario
from engine.comparacao import ComparacaoCenarios
from engine.parametros import Parametros
from engine.tipos import CLASSIFICACAO_CENARIO, METODO, STATUS_METODO

REGRAS: Final[tuple[str, ...]] = (
    "RF-08",
    "S-01",
    "S-02",
    "S-03",
    "S-04",
    "S-05",
    "AC-04",
    "AC-09",
)


@dataclass(frozen=True, slots=True)
class ResultadoStatusMetodo:
    """Saída de `derivar_STATUS_METODO` — `T-60`.

    `STATUS_METODO` é o resumo final; `motivos` é a lista de auditoria de
    todo rebaixamento aplicado, na ordem em que foi avaliado (cenários
    `NAO_CALCULAVEL` primeiro, inventário incompleto depois — ver
    `derivar_STATUS_METODO`). Vazio quando `STATUS_METODO =
    DEFINITIVO_NA_DATA`: nada rebaixou.

    Este dataclass permanece exatamente como `T-60` o definiu — sem
    `REVISAO_HUMANA_OBRIGATORIA`. `T-61` optou por NÃO estendê-lo (a
    alternativa mencionada na versão anterior desta docstring) e sim
    compor um dataclass novo, `ResultadoMetodoRecomendado` (abaixo), que
    envolve `STATUS_METODO`/`motivos` já rebaixados por `S-04` mais os
    campos novos (`METODO_RECOMENDADO_PIQ`, `REVISAO_HUMANA_OBRIGATORIA`,
    `motivo_recomendacao`). Razão: `derivar_STATUS_METODO` é chamada hoje
    só com `cenarios`/`INVENTARIO_COMPLETO` (ver `tests/regras/test_S.py`,
    `T-60`) — ela não tem, e não deveria precisar de, a `ComparacaoCenarios`
    nem a `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` que `S-04` exige. Mudar
    sua assinatura quebraria essa API já testada sem necessidade; um
    dataclass que a ENVOLVE é a extensão mínima.
    """

    STATUS_METODO: STATUS_METODO
    motivos: tuple[str, ...]


def derivar_STATUS_METODO(
    cenarios: Mapping[METODO, Cenario],
    *,
    INVENTARIO_COMPLETO: bool,
) -> ResultadoStatusMetodo:
    """`RF-08` · `S-01` · `S-02` · `AC-09` — deriva `STATUS_METODO` a partir
    da classificação de cada cenário calculado e da completude do
    inventário. Função pura: sempre recalcula do zero a partir das
    entradas, nunca um valor atribuído por fora.

    `cenarios` é o mapa de cenários efetivamente produzidos para este
    snapshot (tipicamente os três métodos — Avalanche, Bola de Neve,
    Híbrido — mas esta função não exige um conjunto fixo de chaves: ela só
    itera o que recebeu, então um Híbrido `NAO_APLICAVEL` que nem chegou a
    entrar no mapa também não rebaixaria, pelo mesmo motivo por que um que
    entra como `NAO_APLICAVEL` não rebaixa — `S-02`).

    Regras, em ordem de avaliação:

    1. `S-01`/`S-02` — tolerância ZERO entre `CLASSIFICACAO_CENARIO.
       NAO_CALCULAVEL` (rebaixa) e `CLASSIFICACAO_CENARIO.NAO_APLICAVEL`
       (não rebaixa). Cenário com `classificacao is None` (método ainda não
       rotulado, ver `Cenario.classificacao` — "preenchido por tarefa
       futura") ou `CLASSIFICACAO_CENARIO.CALCULAVEL` também não rebaixa.
    2. `AC-09` — `INVENTARIO_COMPLETO = False` limita o resultado a
       `PROVISORIO`, mesmo que nenhum cenário seja `NAO_CALCULAVEL`. Não é
       cumulativo com o motivo acima: um inventário incompleto e um
       cenário `NAO_CALCULAVEL` geram DOIS motivos distintos na tupla, mas
       o `STATUS_METODO` final continua sendo `PROVISORIO` (não há nível
       mais baixo que ele nesta tarefa).

    Sem qualquer rebaixamento, `STATUS_METODO = DEFINITIVO_NA_DATA` e
    `motivos = ()`.
    """
    motivos: list[str] = []

    for metodo, cenario in cenarios.items():
        if cenario.classificacao is CLASSIFICACAO_CENARIO.NAO_CALCULAVEL:
            # S-01/S-02: NAO_CALCULAVEL rebaixa — faltam dados, DESCONHECIDO
            # em cascata. NAO_APLICAVEL (Híbrido sem candidata, H-08/EC-03)
            # e CALCULAVEL nunca entram aqui.
            motivos.append(
                f"{metodo.value}: CLASSIFICACAO_CENARIO = NAO_CALCULAVEL — "
                "dados insuficientes para calcular o cenário, rebaixa "
                "STATUS_METODO (S-01, S-02)."
            )

    if not INVENTARIO_COMPLETO:
        # AC-09/GAB-02: inventário com informação faltante em algum ponto
        # limita o STATUS_METODO ao máximo PROVISORIO, mesmo que todos os
        # cenários sejam CALCULAVEL.
        motivos.append(
            "INVENTARIO_COMPLETO = False — carteira de dívidas com informação "
            "faltante em algum ponto; STATUS_METODO limitado a PROVISORIO no "
            "máximo (AC-09)."
        )

    if motivos:
        return ResultadoStatusMetodo(
            STATUS_METODO=STATUS_METODO.PROVISORIO,
            motivos=tuple(motivos),
        )

    return ResultadoStatusMetodo(
        STATUS_METODO=STATUS_METODO.DEFINITIVO_NA_DATA,
        motivos=(),
    )


@dataclass(frozen=True, slots=True)
class ResultadoMetodoRecomendado(ResultadoStatusMetodo):
    """Saída de `derivar_METODO_RECOMENDADO_PIQ` — `T-61`.

    Herda `STATUS_METODO`/`motivos` de `ResultadoStatusMetodo` (já
    rebaixados por `S-01`/`S-02`/`AC-09` via `derivar_STATUS_METODO`, e
    agora possivelmente também por `S-04`) e acrescenta:

    - `METODO_RECOMENDADO_PIQ` — o método escolhido, sempre `CALCULAVEL`
      (critério de aceite 4 de `T-61`: nunca `NAO_APLICAVEL`/`NAO_
      CALCULAVEL`).
    - `REVISAO_HUMANA_OBRIGATORIA` — `S-04`/`S-05`.
    - `motivo_recomendacao` — string de auditoria de POR QUE este método
      (e não outro) foi escolhido, mesmo espírito de `motivos`
      (`ResultadoStatusMetodo`), mas dedicado à recomendação em si, não ao
      rebaixamento de status.

    `frozen=True, slots=True` como toda saída derivada do motor — sem
    setter, sem campo mutável (mesma trava estrutural de
    `ResultadoStatusMetodo`, `T-60`, critério de aceite 3).
    """

    METODO_RECOMENDADO_PIQ: METODO
    REVISAO_HUMANA_OBRIGATORIA: bool
    motivo_recomendacao: str


def _vitoria_rapida(cenario: Cenario, p: Parametros) -> bool:
    """`VITORIA_RAPIDA(X)` — `AC-04`/`§11.5` (`P_MESES_VITORIA_RAPIDA`, o
    mesmo teto que `H-03` usa para a vitória estratégica do Híbrido, aqui
    generalizado para qualquer cenário candidato a substituir o superior
    sob `S-04`).

    `MESES_PRIMEIRA_VITORIA is None` (cenário nunca quita nenhuma dívida
    dentro do horizonte simulado) reprova de imediato — mesma trava de
    `engine/metodos/hibrido.py::_e_candidata_valida`: não há como comparar
    `None <= P_MESES_VITORIA_RAPIDA`, e RF-16 proíbe inventar um número.
    """
    if cenario.MESES_PRIMEIRA_VITORIA is None:
        return False
    teto = p.numero("P_MESES_VITORIA_RAPIDA")
    return cenario.MESES_PRIMEIRA_VITORIA <= teto


def derivar_METODO_RECOMENDADO_PIQ(
    cenarios: Mapping[METODO, Cenario],
    comparacao: ComparacaoCenarios,
    *,
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE: bool,
    INVENTARIO_COMPLETO: bool,
    parametros: Parametros,
) -> ResultadoMetodoRecomendado:
    """`RF-08` · `S-04` · `S-05` · `AC-04` · `EC-04` · `EC-05` — deriva
    `METODO_RECOMENDADO_PIQ` e `REVISAO_HUMANA_OBRIGATORIA`, compondo sobre
    `derivar_STATUS_METODO` (`T-60`) em vez de duplicar sua lógica de
    rebaixamento por `S-01`/`S-02`/`AC-09`. Função pura: sempre recalcula
    do zero a partir das entradas.

    `comparacao` é a saída de `engine/comparacao.py::comparar_cenarios`
    (`T-57`/`T-58`) sobre os MESMOS cenários calculáveis de `cenarios` —
    fonte de `CENARIO_ECONOMICAMENTE_SUPERIOR` (`RF-19`) e
    `ECONOMICAMENTE_PROXIMO` (`RF-20`). `cenarios` também é usado aqui para
    ler `MESES_PRIMEIRA_VITORIA` de cada candidato (`VITORIA_RAPIDA`) e
    para garantir, por construção, que a recomendação final aponta sempre
    para um `Cenario` com `classificacao is CLASSIFICACAO_CENARIO.
    CALCULAVEL` (critério de aceite 4): `comparacao` só enxerga métodos que
    o chamador já filtrou para calculáveis (contrato de
    `comparar_cenarios`), então qualquer `METODO` que sai desta função via
    `CENARIO_ECONOMICAMENTE_SUPERIOR` ou via `ECONOMICAMENTE_PROXIMO` já
    satisfaz essa garantia — nunca um `NAO_APLICAVEL`/`NAO_CALCULAVEL` é
    fabricado aqui.

    Passos:

    1. `derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=...)` (`T-60`)
       — ponto de partida de `STATUS_METODO`/`motivos`, cobrindo
       `S-01`/`S-02`/`AC-09` sem duplicar a lógica.
    2. Ponto de partida da recomendação: `comparacao.
       CENARIO_ECONOMICAMENTE_SUPERIOR` (`RF-19`) — o cenário mais
       econômico é a recomendação padrão quando não há incompatibilidade
       comportamental grave com ele.
    3. `S-04`/`S-05`: se `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` é `True`
       (a incompatibilidade é sempre avaliada "com o cenário mais
       econômico", `specs/piq-app-spec.md` §6.1 — nunca com a
       recomendação já trocada), busca-se entre os cenários alternativos
       `ECONOMICAMENTE_PROXIMO` (`comparacao.ECONOMICAMENTE_PROXIMO`) uma
       saída aceitável. Prioridade determinística, nesta ordem — nunca por
       ordem de iteração do mapa:
       a. Primeiro, entre os `ECONOMICAMENTE_PROXIMO` que também são
          `VITORIA_RAPIDA` (`MESES_PRIMEIRA_VITORIA <=
          P_MESES_VITORIA_RAPIDA`) — a "vitória rápida" é o que efetivamente
          resolve `NECESSIDADE_VITORIA` alta (a raiz de `INCOMPATIBILIDADE_
          COMPORTAMENTAL_GRAVE`, `Definições §1`). Entre vários, desempate
          lexicográfico de três níveis (`_chave`): 1º menor
          `MESES_PRIMEIRA_VITORIA`; 2º menor `comparacao.PENALIDADE_CUSTO`
          — mesmo padrão normativo do desempate da Etapa 4 do Híbrido
          ("1º menor `MESES_PRIMEIRA_VITORIA`; 2º menor
          `PENALIDADE_CUSTO_VS_AVALANCHE`", `specs/piq-app-spec.md` linha
          170), aqui aplicado entre MÉTODOS candidatos em vez de dívidas D
          — `GAB-C`/`AC-04` exercita exatamente este empate (Bola de Neve
          e Híbrido ambos `MESES_PRIMEIRA_VITORIA = 1`; só a menor
          `PENALIDADE_CUSTO` do Híbrido, 1,635% contra 3,139%, decide); 3º
          `METODO.value` alfabético como resíduo final determinístico
          (nunca observado em nenhum gabarito, mas mantido para o caso de
          penalidade também empatada).
       b. Não havendo nenhum com vitória rápida, mas havendo algum
          `ECONOMICAMENTE_PROXIMO` (ex.: Bola de Neve, `S-05`), recomenda-
          se pelo mesmo desempate de três níveis do item `a` entre eles
          (`MESES_PRIMEIRA_VITORIA = None` conta como pior, vai ao final).
          `S-05` é exatamente este ramo: Híbrido `NAO_APLICAVEL` (nem
          entra em `comparacao.ECONOMICAMENTE_PROXIMO`, que só cobre
          cenários calculáveis) com Bola de Neve `ECONOMICAMENTE_PROXIMA`
          cai aqui — recomendação = Bola de Neve, revisão NÃO acionada.
       c. Não havendo NENHUMA alternativa `ECONOMICAMENTE_PROXIMA` (`S-04`
          propriamente dito, `EC-05`): a recomendação permanece o
          `CENARIO_ECONOMICAMENTE_SUPERIOR` (não há outro candidato
          calculável melhor a oferecer), mas `STATUS_METODO` é rebaixado a
          `PROVISORIO` (se já não estiver) e `REVISAO_HUMANA_OBRIGATORIA =
          True` — o motor não decide sozinho.
    4. Sem incompatibilidade grave: `METODO_RECOMENDADO_PIQ =
       CENARIO_ECONOMICAMENTE_SUPERIOR`, `REVISAO_HUMANA_OBRIGATORIA =
       False`, `STATUS_METODO`/`motivos` inalterados do passo 1.
    """
    base = derivar_STATUS_METODO(cenarios, INVENTARIO_COMPLETO=INVENTARIO_COMPLETO)
    superior = comparacao.CENARIO_ECONOMICAMENTE_SUPERIOR

    if not INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE:
        return ResultadoMetodoRecomendado(
            STATUS_METODO=base.STATUS_METODO,
            motivos=base.motivos,
            METODO_RECOMENDADO_PIQ=superior,
            REVISAO_HUMANA_OBRIGATORIA=False,
            motivo_recomendacao=(
                f"{superior.value}: CENARIO_ECONOMICAMENTE_SUPERIOR, sem "
                "INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE — recomendação padrão "
                "(RF-19)."
            ),
        )

    # S-04/S-05: há incompatibilidade grave com o cenário mais econômico.
    # Procura alternativa ECONOMICAMENTE_PROXIMA — nunca contra a Avalanche
    # fixa, sempre contra o próprio superior (mesma referência de RF-20).
    proximos = [
        metodo
        for metodo, proximo in comparacao.ECONOMICAMENTE_PROXIMO.items()
        if proximo
    ]

    if not proximos:
        # S-04 propriamente dito (EC-05): nenhuma alternativa aplicável é
        # próxima — o motor não pode decidir sozinho.
        motivo_status = (
            f"INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE = SIM com o cenário mais "
            f"econômico ({superior.value}) e nenhuma alternativa aplicável é "
            "ECONOMICAMENTE_PROXIMA — STATUS_METODO limitado a PROVISORIO e "
            "REVISAO_HUMANA_OBRIGATORIA = SIM (S-04)."
        )
        motivos = (
            base.motivos if motivo_status in base.motivos else (*base.motivos, motivo_status)
        )
        return ResultadoMetodoRecomendado(
            STATUS_METODO=STATUS_METODO.PROVISORIO,
            motivos=motivos,
            METODO_RECOMENDADO_PIQ=superior,
            REVISAO_HUMANA_OBRIGATORIA=True,
            motivo_recomendacao=(
                f"{superior.value}: CENARIO_ECONOMICAMENTE_SUPERIOR mantido por "
                "falta de alternativa ECONOMICAMENTE_PROXIMA, apesar da "
                "INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE — REVISAO_HUMANA_"
                "OBRIGATORIA = SIM (S-04)."
            ),
        )

    # S-05: existe ao menos uma alternativa próxima — revisão NÃO é
    # acionada. Prioriza vitória rápida (resolve a raiz de NECESSIDADE_
    # VITORIA alta); na ausência, o melhor MESES_PRIMEIRA_VITORIA entre as
    # próximas (ex.: Bola de Neve com Híbrido NAO_APLICAVEL).
    candidatos_vitoria_rapida = [
        metodo for metodo in proximos if _vitoria_rapida(cenarios[metodo], parametros)
    ]
    grupo = candidatos_vitoria_rapida or proximos

    def _chave(metodo: METODO) -> tuple[int, Decimal, str]:
        meses = cenarios[metodo].MESES_PRIMEIRA_VITORIA
        # None (nunca quita dentro do horizonte) é o pior caso — vai ao
        # final da ordenação crescente.
        ordem_meses = meses if meses is not None else 10**9
        # 2º critério — menor PENALIDADE_CUSTO (comparacao.PENALIDADE_CUSTO,
        # T-58): mesmo padrão do desempate lexicográfico já normativo da
        # Etapa 4 do Híbrido ("1º menor MESES_PRIMEIRA_VITORIA; 2º menor
        # PENALIDADE_CUSTO_VS_AVALANCHE", `specs/piq-app-spec.md` linha 170)
        # — aqui aplicado entre MÉTODOS candidatos, não entre dívidas D,
        # mas a mesma lógica: entre vitórias igualmente rápidas, prefere-se
        # o mais barato. GAB-C (`AC-04`) exercita esta exata situação: Bola
        # de Neve e Híbrido empatam em MESES_PRIMEIRA_VITORIA = 1, e só a
        # PENALIDADE_CUSTO (1,635% × 3,139%) decide — sem este critério, o
        # `METODO.value` alfabético elegeria BOLA_DE_NEVE < HIBRIDO,
        # divergindo do gabarito normativo. `METODO.value` alfabético
        # permanece como resíduo final, para o caso (não observado em
        # nenhum gabarito) de penalidade também empatada.
        return (ordem_meses, comparacao.PENALIDADE_CUSTO[metodo], metodo.value)

    escolhido = min(grupo, key=_chave)

    if candidatos_vitoria_rapida:
        motivo_recomendacao = (
            f"{escolhido.value}: ECONOMICAMENTE_PROXIMO de {superior.value} E "
            "VITORIA_RAPIDA — resolve a INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE "
            "sem exigir revisão humana (S-04, AC-04)."
        )
    else:
        motivo_recomendacao = (
            f"{escolhido.value}: ECONOMICAMENTE_PROXIMO de {superior.value} — "
            "alternativa comportamental aplicável apesar da "
            "INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE (S-05)."
        )

    return ResultadoMetodoRecomendado(
        STATUS_METODO=base.STATUS_METODO,
        motivos=base.motivos,
        METODO_RECOMENDADO_PIQ=escolhido,
        REVISAO_HUMANA_OBRIGATORIA=False,
        motivo_recomendacao=motivo_recomendacao,
    )
