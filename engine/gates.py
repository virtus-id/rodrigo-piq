"""Gates de elegibilidade — RF-17, RF-16 · §11.3 · AC-22, AC-23, AC-41, AC-42,
AC-43, AC-44, AC-45, EC-15, EC-16, EC-17, RF-32, AC-56, AC-57, AC-58, AC-59,
AC-60, EC-22.

Os quatro gates são aplicados **antes** da ordem-base, na sequência fixa
Informação → Contenção de Risco → Transformação → Oportunidade com Prazo
(§11.3). `T-29` implementou os Gates 1 e 2. `T-30` acrescentou os Gates 3 e 4
e a orquestração completa dos quatro (`aplicar_gates_1_a_4`). `T-31` fechou o
mapeamento completo de `STATUS_DIVIDA` → `DIVIDA_STATUS_ESTRATEGICO`
(Definições §6, tabela inteira de §11.3) com `determinar_status_estrategico`.
Esta tarefa (`T-32`) consolida os resultados de todo o inventário em
`ParticaoElegibilidade` (`elegiveis`, `ORDEM_ACOES`, `bloqueadas`) via
`particionar_elegibilidade`.

**Nota sobre `EM_ATAQUE` (§4.1 do plano, Eixo 2).** A fórmula normativa de
`DIVIDA_ELEGIVEL_ORDEM` (§4.1) inclui `status ∈ {PRONTA_PARA_ORDENACAO,
EM_ATAQUE}`. `determinar_status_estrategico` (`T-31`) NUNCA produz
`EM_ATAQUE` — a própria docstring daquela função é explícita: "`EM_ATAQUE`
... não é decidido aqui; ... é responsabilidade de quem monta o ciclo
mensal". `EM_ATAQUE` é a promoção de `PRONTA_PARA_ORDENACAO` para "já é
`DIVIDA_ALVO_ATUAL`", decidida pelo ciclo mensal (`engine/ciclo_mensal.py`,
T-42+), que ainda não existe. Por isso `particionar_elegibilidade` classifica
como `elegiveis` toda dívida cujo `ResultadoGates.DIVIDA_ELEGIVEL_ORDEM` for
`True` — o próprio booleano já resolvido por `T-31`/`T-29`/`T-30` a partir do
`DIVIDA_STATUS_ESTRATEGICO` real (hoje sempre `PRONTA_PARA_ORDENACAO` quando
`True`), sem reimplementar a fórmula nem hardcodar o enum aqui: quando o
ciclo mensal (T-42+) passar a produzir `EM_ATAQUE` para a dívida que já é o
alvo corrente, `DIVIDA_ELEGIVEL_ORDEM` continuará `True` para ela e esta
função não precisa mudar.

**Decisão de `T-31` sobre os dois sabores de `EM_ACORDO`** (§11.3, tabela
`STATUS_DIVIDA` → Efeito). A tabela distingue "acordo executado, estrutura
vigente conhecida, nada pendente" (não bloqueia) de "negociação aberta ou
estrutura sujeita a mudança material" (`INTERVENCAO_PENDENTE` +
`TRANSFORMACAO`). `engine/estado.py` não modela um campo dedicado a
"negociação aberta" para `EM_ACORDO` — mas já modela exatamente essa noção
para o Gate 3 inteiro: `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE`
(`Divida`, campos comentados "# Gate 3"), que representam "intervenção
pendente que pode alterar materialmente saldo, parcela, taxa, prazo ou
custo" — a MESMA descrição textual do sub-caso "negociação aberta ou
estrutura sujeita a mudança material" de `EM_ACORDO`. Não é coincidência:
"negociação aberta" É uma renegociação pendente; "estrutura sujeita a
mudança material" É o que `TROCA_PENDENTE` cobre. Por isso `EM_ACORDO` não
recebe tratamento especial nesta função — ele simplesmente atravessa os
quatro gates como `ATIVA`/`COBRANCA_SEM_PAGAMENTO`: se
`RENEGOCIACAO_PENDENTE` ou `TROCA_PENDENTE` forem `True`, o Gate 3 já
produz `INTERVENCAO_PENDENTE` + `GATE_PENDENTE = TRANSFORMACAO` (mesmo
resultado exigido pela tabela); se ambos forem `False` ("acordo executado,
estrutura vigente conhecida, nada pendente"), nenhum gate bloqueia e a
função consolida `PRONTA_PARA_ORDENACAO`. Nenhum campo novo foi criado —
um já existente serve, e usá-lo evita duplicar em `Divida` uma variável que
já existe com outro nome, e evita que `determinar_status_estrategico` decida
elegibilidade a partir de `STATUS_DIVIDA` sozinho (o que a tabela proíbe
explicitamente).

**Decisão de interface.** O plano (`§4`) desenha uma função pública única
`aplicar_gates(d, ctx, p) -> ResultadoGates`, que encadeia os quatro gates em
sequência fixa. Como `ContextoGates` e `Parametros` ainda não existem nesta
tarefa (não há parâmetro `P_*` consumido por nenhum dos quatro gates), a
função completa desenhada no plano é adiada para quando esses tipos forem
modelados; esta tarefa expõe, em vez disso, `aplicar_gates_1_a_4`, com a
mesma assinatura de dados (`Divida` + os mesmos parâmetros já usados pelos
gates individuais) e o mesmo contrato de retorno (`ResultadoGates | None`,
`None` = nenhum gate bloqueou). Trocar por `aplicar_gates(d, ctx, p)` mais
tarde é mudança de assinatura, não de comportamento.

- `aplicar_gate_1_informacao(divida, resultado_valor_relevante)
   -> ResultadoGates | None`
- `aplicar_gate_2_contencao_risco(divida, quitacao_e_a_propria_contencao=False)
   -> ResultadoGates | None`
- `aplicar_gate_3_transformacao(divida) -> ResultadoGates | None`
- `aplicar_gate_4_oportunidade(divida) -> ResultadoGates | None` — **sempre**
  `None` (ver docstring da função: por que este gate estruturalmente não
  bloqueia)
- `avaliar_oportunidade_executavel(divida) -> bool` — auxiliar que calcula
  `OPORTUNIDADE_EXECUTAVEL` (§11.3), para uso futuro por `T-32`
- `aplicar_gates_1_e_2(...)` (`T-29`) e `aplicar_gates_1_a_4(...)` (`T-30`),
  que encadeiam os gates em sequência fixa, curto-circuitando no primeiro que
  bloquear
- `determinar_status_estrategico(divida, resultado_valor_relevante)
   -> ResultadoGates` (`T-31`) — mapeamento completo de `STATUS_DIVIDA` para
  `DIVIDA_STATUS_ESTRATEGICO`, incluindo o desvio `OUTRA` (antes dos gates) e
  a montagem do `ResultadoGates` de sucesso (`PRONTA_PARA_ORDENACAO`) quando
  nenhum gate bloqueia — as funções de gate individuais só devolvem algo
  quando bloqueiam, então é aqui que o caso positivo é consolidado
- `particionar_elegibilidade(dividas, resolver_valor_relevante=...)
   -> ParticaoElegibilidade` (`T-32`) — roda `determinar_status_estrategico`
  para cada dívida do inventário e agrega os resultados em `elegiveis`,
  `ORDEM_ACOES` e `bloqueadas`. Não reimplementa a fórmula de
  `DIVIDA_ELEGIVEL_ORDEM`: apenas consome o booleano já correto de cada
  `ResultadoGates`

Cada gate individual devolve `None` quando NÃO bloqueia (dívida passa), para
que a orquestração encadeie sem precisar desembrulhar o resultado.

REGRAS: RF-17, RF-16, AC-22, AC-23, AC-41, AC-42, AC-43, AC-44, AC-45, EC-15,
EC-16, EC-17, §11.3
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

import engine.tipos as tipos
from engine.estado import Divida
from engine.precisao import dinheiro
from engine.tipos import (
    DESCONHECIDO,
    DIVIDA_STATUS_ESTRATEGICO,
    GATE_PENDENTE,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    DinheiroTalvez,
)
from engine.valor_quitacao import ResultadoValorRelevante, compor_VALOR_RELEVANTE_PARA_QUITACAO

# `NECESSIDADE_IMEDIATA_DIVIDA` (T-134) nomeia seus parâmetros keyword-only
# `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` — assinatura exata do plano
# R4B.4.2 — o que faz sombra, DENTRO do corpo dessa função, aos tipos
# `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` importados acima. `import
# engine.tipos as tipos` dá acesso aos mesmos enums por um nome que o
# parâmetro nunca sombreia, sem remover os imports diretos já em uso pelo
# resto do módulo.

REGRAS: Final[tuple[str, ...]] = (
    "RF-17",
    "RF-16",
    "AC-22",
    "AC-23",
    "AC-41",
    "AC-42",
    "AC-43",
    "AC-44",
    "AC-45",
    "EC-15",
    "EC-16",
    "EC-17",
    "RF-32",
    "AC-56",
    "AC-57",
    "AC-58",
    "AC-59",
    "AC-60",
    "EC-22",
    "§11.3",
    "§14.1",
    "§14.1.1",
    "§14.2.1",
    "§14.2.2",
)


TIPO_ACAO_VALORES: Final[frozenset[str]] = frozenset(
    {"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}
)
# RF-29 · AC-49: domínio fechado, ASCII, sem parênteses, exatamente estes
# quatro literais. Usado por teste estático (Rodada 2) para recusar um
# quinto valor introduzido por engano em runtime.


@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    """Item da fila paralela `ORDEM_ACOES` (§11.3) — dívida desviada de um
    gate que exige ação anterior ao ataque ordinário, em vez de bloqueio
    silencioso.

    Modelagem mínima e deliberadamente pequena na Rodada 1: só o suficiente
    para que os Gates 2 e 3 tivessem o que devolver. A estrutura completa de
    `ORDEM_ACOES` — agregação por plano, prioridade entre ações concorrentes,
    exibição no relatório — é consolidada em `T-32`.

    Rodada 2 (`RF-28`, `RF-29`, `RF-31`, `RF-34` · plano §R2.4) estende o
    contrato com `ACAO_ID` (identidade estável entre snapshots, `T-80`),
    `TIPO_ACAO` (domínio fechado `TIPO_ACAO_VALORES`) e `CAMPO_PENDENTE`
    (só para `TIPO_ACAO="INFORMACAO"`, Gate 1), e relaxa `DIVIDA_ID` para
    `str | None` (a ação de economia, `RF-33`, não tem dívida associada).
    `gate_origem` amplia para incluir `1` (Gate 1 passa a emitir
    `AcaoRequerida`, `RF-32`) e `None` (ação de economia, `RF-33`, não vem
    de gate algum). Nenhuma lógica de derivação de `TIPO_ACAO`/`ACAO_ID`
    nesta tarefa (`T-79`) — só o shape; a derivação real é `T-80`/`T-83`/
    `T-84`.

    Rodada 4 — fatia 4B (`RF-61`, §14.2.1/§14.2.2, `OQ-39` — decisão R4B.1.1):
    ganha `VALOR_ACAO_FINANCEIRA_IMEDIATA`, campo OBRIGATÓRIO sem default —
    quebra de contrato, não adição (mesmo padrão de `RF-31`/`RF-41`/`RF-59`).
    Representa o valor monetário necessário à execução desta ação: `0`
    quando não há desembolso; o valor conhecido quando há desembolso e o
    valor é conhecido; `DESCONHECIDO` quando há desembolso e o valor não é
    conhecido. Nunca `None` — a variável sempre se aplica a toda ação,
    mesmo quando o valor é `0`.
    """

    ACAO_ID: str
    DIVIDA_ID: str | None  # RF-31: None só para TIPO_ACAO="ECONOMIA"
    TIPO_ACAO: str  # RF-29: domínio fechado, ver TIPO_ACAO_VALORES
    descricao: str  # motivo/ação necessária, texto auditável (Q-05)
    gate_origem: Literal[1, 2, 3] | None  # RF-32/RF-33 ampliam o domínio
    VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez  # RF-61/RF-62/RF-63 · §14.2.1/§14.2.2
    prioridade_excepcional: bool = False  # EC-15: quitação é a própria contenção
    CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"] | None = None
    # RF-34: só preenchido quando TIPO_ACAO="INFORMACAO" (Gate 1). None nos
    # demais TIPO_ACAO.


def _derivar_TIPO_ACAO(gate_pendente: GATE_PENDENTE) -> str:
    """RF-30 · AC-50, `AMB-R2-02` (resolvida) — deriva `TIPO_ACAO` a partir de
    `GATE_PENDENTE`, **nunca** de `gate_origem` (`Literal[1, 2, 3] | None`,
    insuficiente por si só — Gates 2 e 3 compartilham `INTERVENCAO_PENDENTE`
    e só `GATE_PENDENTE` os distingue, conforme a própria docstring de
    `GATE_PENDENTE` em `engine/tipos.py`).

    Mapeamento coberto nesta tarefa (`T-83`, plano §R2.5):
        GATE_PENDENTE.INFORMACAO       -> "INFORMACAO"        (Gate 1)
        GATE_PENDENTE.CONTENCAO_RISCO  -> "RENEGOCIACAO"       (Gate 2,
            `AMB-R2-02`: contenção de risco não tem valor próprio no domínio
            fechado de quatro — é semanticamente mais próxima de
            renegociação do que dos outros três)

    `GATE_PENDENTE.TRANSFORMACAO` (Gate 3) tem mapeamento condicionado a
    `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE` da dívida (não decidível a
    partir só de `GATE_PENDENTE`) — coberto por `_derivar_TIPO_ACAO_gate_3`
    (`T-84`), função irmã desta, não por esta função (que segue recusando
    `TRANSFORMACAO` propositalmente: não há como decidir "RENEGOCIACAO" vs
    "TROCA" sem o par de campos da dívida, que esta assinatura não recebe).
    `GATE_PENDENTE.OPORTUNIDADE` e `GATE_PENDENTE.NENHUM` nunca chegam a
    precisar de `TIPO_ACAO` (Gate 4 nunca bloqueia; `NENHUM` é o caso em que
    nenhuma `AcaoRequerida` é emitida).
    """
    if gate_pendente is GATE_PENDENTE.INFORMACAO:
        return "INFORMACAO"
    if gate_pendente is GATE_PENDENTE.CONTENCAO_RISCO:
        return "RENEGOCIACAO"
    raise NotImplementedError(
        f"_derivar_TIPO_ACAO: {gate_pendente!r} fora do escopo desta função "
        "(TRANSFORMACAO é _derivar_TIPO_ACAO_gate_3, T-84; OPORTUNIDADE/"
        "NENHUM nunca emitem AcaoRequerida)."
    )


def _derivar_TIPO_ACAO_gate_3(*, renegociacao_pendente: bool, troca_pendente: bool) -> str:
    """RF-30 · AC-51, AC-52, `AMB-R2-03` (resolvida) — deriva `TIPO_ACAO` para
    `GATE_PENDENTE.TRANSFORMACAO` (Gate 3), caso não coberto por
    `_derivar_TIPO_ACAO` (T-83): `GATE_PENDENTE` sozinho não basta para
    diferenciar `"RENEGOCIACAO"` de `"TROCA"` no Gate 3 — é preciso também o
    discriminador `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE` da própria dívida
    (o mesmo par de campos que `aplicar_gate_3_transformacao` já usa para
    compor `origem`, hoje só em texto livre).

    Função irmã dedicada, em vez de estender a assinatura de
    `_derivar_TIPO_ACAO`: aquela função já tem contrato fechado e verificado
    por introspecção (`test_derivar_tipo_acao_le_gate_pendente_nunca_gate_
    origem`, T-83) — recebe exclusivamente `gate_pendente`, um parâmetro.
    Adicionar parâmetros opcionais a ela quebraria esse contrato sem
    necessidade real, já que Gate 1 e Gate 2 nunca precisam do par
    renegociação/troca.

    Mapeamento (T-84, plano §R2.5 item 2):
        RENEGOCIACAO_PENDENTE=True,  TROCA_PENDENTE=False -> "RENEGOCIACAO"
        RENEGOCIACAO_PENDENTE=False, TROCA_PENDENTE=True  -> "TROCA"
        RENEGOCIACAO_PENDENTE=True,  TROCA_PENDENTE=True  -> "RENEGOCIACAO"
            (`AMB-R2-03`: prioridade fixa, "RENEGOCIACAO" prevalece — "TROCA"
            só é emitido quando TROCA_PENDENTE=True e RENEGOCIACAO_PENDENTE=
            False)

    Chamar com os dois campos `False` é erro de uso do chamador — esta
    função só é chamada depois que `aplicar_gate_3_transformacao` já
    confirmou que ao menos um dos dois é `True` (é o próprio motivo do Gate 3
    ter bloqueado).
    """
    if renegociacao_pendente:
        # AMB-R2-03: RENEGOCIACAO prevalece mesmo quando TROCA_PENDENTE
        # também é True — nenhum quinto valor é introduzido.
        return "RENEGOCIACAO"
    return "TROCA"


def _compor_ACAO_ID(*, divida_id: str | None, tipo_acao: str) -> str:
    """RF-28 · OQ-21/OQ-22 (respondida) — ACAO_ID determinístico por
    composição, sem contador, sem UUID, sem estado externo.

    Ações ligadas a gate (INFORMACAO, RENEGOCIACAO, TROCA):
        ACAO_ID = f"{divida_id}:{tipo_acao}"
    Ação de economia (ECONOMIA, sem DIVIDA_ID):
        ACAO_ID = f"ACAO:{tipo_acao}"     # ex.: "ACAO:ECONOMIA"

    Mesmos dois insumos sempre produzem o mesmo `ACAO_ID` — reaproveitada
    pelos três pontos de emissão (Gate 1, Gate 3, ação de economia em
    `engine/motor.py`, `T-83`/`T-84`).
    """
    if divida_id is None:
        return f"ACAO:{tipo_acao}"
    return f"{divida_id}:{tipo_acao}"


@dataclass(frozen=True, slots=True)
class ResultadoGates:
    """Saída de cada gate — §4 do plano técnico.

    `gate_bloqueador` é `None` quando a dívida passa pelo(s) gate(s)
    avaliado(s) nesta chamada — ver `aplicar_gate_1_informacao` e
    `aplicar_gate_2_contencao_risco`, que devolvem `None` (não
    `ResultadoGates` com `gate_bloqueador=None`) nesse caso, para que a
    orquestração encadeie sem precisar desembrulhar o resultado. Quando ESTE
    tipo é de fato instanciado, é porque um gate bloqueou — `gate_bloqueador`
    sempre tem valor.
    """

    DIVIDA_ID: str
    DIVIDA_STATUS_ESTRATEGICO: DIVIDA_STATUS_ESTRATEGICO
    GATE_PENDENTE: GATE_PENDENTE
    DIVIDA_ELEGIVEL_ORDEM: bool
    gate_bloqueador: Literal[1, 2, 3, 4] | None
    motivo: str  # entra na JUSTIFICATIVA_POSICAO (Q-05)
    acao: AcaoRequerida | None  # alimenta ORDEM_ACOES


def aplicar_gate_1_informacao(
    divida: Divida,
    resultado_valor_relevante: ResultadoValorRelevante,
) -> ResultadoGates | None:
    """Gate 1 — Informação (§11.3, primeira linha da tabela).

    Bloqueia quando dado material impede saber: (a) o valor sobre o qual o
    ataque será aplicado — `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO`,
    já composto por `compor_VALOR_RELEVANTE_PARA_QUITACAO` (T-27) e recebido
    aqui como `resultado_valor_relevante`; ou (b) se a dívida está confirmada
    como quitada — `STATUS_DIVIDA = QUITADA_A_CONFIRMAR` (Definições §6,
    adiantado aqui por ser fundamentalmente falta de confirmação/informação;
    o mapeamento COMPLETO de `STATUS_DIVIDA` é `T-31`).

    CRÍTICO (§11.3): a falta APENAS da simulação marginal
    (`BENEFICIO_MARGINAL_AMORTIZACAO`, calculada em `T-39`, ainda não
    implementada) NÃO bloqueia por si só, se o fallback do §11.1 for
    possível. Esta função não lê nem depende de benefício marginal algum —
    ela só verifica dado ESTRUTURAL (valor relevante, status da dívida), o
    que já garante a trava por construção: não há caminho aqui que trave por
    ausência de um cálculo derivado.

    `T-87` (`RF-32`) — os dois ramos de bloqueio constroem `AcaoRequerida`
    (`TIPO_ACAO="INFORMACAO"`), em vez de `acao=None`: o ramo (b) marca
    `CAMPO_PENDENTE="STATUS_DIVIDA"` (`AC-56`); o ramo (a) marca
    `CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"` (`AC-57`). Os dois `if` seguem
    sequenciais — o segundo só é avaliado quando o primeiro não retornou —
    o que garante por construção que os dois ramos são mutuamente
    exclusivos e `CAMPO_PENDENTE` nunca é ambíguo (`EC-22`).

    Devolve `None` quando o Gate 1 NÃO bloqueia (dívida segue para o Gate 2).
    """
    if divida.STATUS_DIVIDA == STATUS_DIVIDA.QUITADA_A_CONFIRMAR:
        # AC-44/AC-56: inelegível, INFORMACAO_PENDENTE + GATE_PENDENTE =
        # INFORMACAO, não ordenada nem atacada até a confirmação. RF-32:
        # emite AcaoRequerida (CAMPO_PENDENTE="STATUS_DIVIDA"), em vez de
        # acao=None — a confirmação do status É o dado que falta.
        motivo = (
            f"{divida.DIVIDA_ID}: STATUS_DIVIDA = QUITADA_A_CONFIRMAR — quitação "
            "ainda não confirmada, dívida inelegível até a confirmação (AC-44)."
        )
        tipo_acao = _derivar_TIPO_ACAO(GATE_PENDENTE.INFORMACAO)
        acao = AcaoRequerida(
            # T-87: TIPO_ACAO derivado de GATE_PENDENTE (T-83) e ACAO_ID
            # composto por _compor_ACAO_ID (T-80) — mesmo padrão dos Gates
            # 2/3. CAMPO_PENDENTE nomeia o campo de Divida ainda incerto
            # (RF-34): aqui, o próprio STATUS_DIVIDA.
            ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao=tipo_acao),
            DIVIDA_ID=divida.DIVIDA_ID,
            TIPO_ACAO=tipo_acao,
            descricao=motivo,
            gate_origem=1,
            # T-133 (RF-61/RF-62 · §14.2.1): TIPO_ACAO="INFORMACAO" nunca
            # exige desembolso — sem valor de ação financeira imediata.
            VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
            CAMPO_PENDENTE="STATUS_DIVIDA",
        )
        return ResultadoGates(
            DIVIDA_ID=divida.DIVIDA_ID,
            DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
            GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
            DIVIDA_ELEGIVEL_ORDEM=False,
            gate_bloqueador=1,
            motivo=motivo,
            acao=acao,
        )

    if resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO is DESCONHECIDO:
        # Dado material ausente: não se sabe o valor sobre o qual o ataque
        # seria aplicado. Bloqueio estrutural — não é a falta de simulação
        # marginal (essa não é sequer consultada aqui). AC-57/RF-32: emite
        # AcaoRequerida (CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"). Este `if` só
        # é avaliado quando o ramo acima não bloqueou — EC-22: os dois ramos
        # são mutuamente exclusivos por construção, CAMPO_PENDENTE nunca é
        # ambíguo.
        motivo = (
            f"{divida.DIVIDA_ID}: VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO — "
            "falta dado material sobre o valor a atacar."
        )
        tipo_acao = _derivar_TIPO_ACAO(GATE_PENDENTE.INFORMACAO)
        acao = AcaoRequerida(
            ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao=tipo_acao),
            DIVIDA_ID=divida.DIVIDA_ID,
            TIPO_ACAO=tipo_acao,
            descricao=motivo,
            gate_origem=1,
            # T-133 (RF-61/RF-62 · §14.2.1): TIPO_ACAO="INFORMACAO" nunca
            # exige desembolso — sem valor de ação financeira imediata.
            VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
            CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL",
        )
        return ResultadoGates(
            DIVIDA_ID=divida.DIVIDA_ID,
            DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
            GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
            DIVIDA_ELEGIVEL_ORDEM=False,
            gate_bloqueador=1,
            motivo=motivo,
            acao=acao,
        )

    return None


def aplicar_gate_2_contencao_risco(
    divida: Divida,
    *,
    quitacao_e_a_propria_contencao: bool = False,
) -> ResultadoGates | None:
    """Gate 2 — Contenção de risco (§11.3, segunda linha da tabela).

    Risco que exija ação anterior ao ataque ordinário — especialmente
    patrimonial crítico ou consequência material iminente
    (`Divida.RISCO_MATERIAL_IMINENTE`) — desvia a dívida temporariamente da
    ordem-base para `ORDEM_ACOES`: `DIVIDA_STATUS_ESTRATEGICO =
    INTERVENCAO_PENDENTE`, `GATE_PENDENTE = CONTENCAO_RISCO` (AC-43).

    CRÍTICO (AC-23): risco alto, por si só, NUNCA torna a dívida
    automaticamente a primeira. Este gate só decide DESVIAR (inelegível para
    a ordem ordinária) — nunca promove nem prioriza a dívida na ordem-base.
    A única forma de prioridade aqui é a EXCEÇÃO expressa abaixo, e mesmo
    essa é sinalizada como excepcional, não como "primeiro lugar automático".

    EXCEÇÃO (EC-15): se a própria quitação for a ação que contém o risco e
    for executável, pode receber prioridade excepcional com justificativa
    expressa. Modelada como o parâmetro booleano
    `quitacao_e_a_propria_contencao`: a decisão de SE a quitação é a própria
    contenção e SE é executável não é dado bruto de `Divida` (não há campo
    para isso em `engine/estado.py` — `RISCO_MATERIAL_IMINENTE` só marca que
    existe risco, não que a quitação o resolve) nem cálculo derivável só a
    partir dela; é avaliação de negócio que depende de contexto externo à
    dívida (ex.: se há recurso disponível para quitar agora — Gate 4 trata
    de "recurso disponível" para OUTRA finalidade, `OPORTUNIDADE_VIGENTE`,
    que não é o mesmo conceito). Por isso fica explícito como parâmetro do
    chamador, documentado aqui, em vez de inferido silenciosamente — mantém
    a trava de "não inventar dado" (RF-16) e a trava de "risco alto não
    promove sozinho" (AC-23): o booleano precisa vir de fora, com
    justificativa, nunca ser derivado automaticamente de `RISCO_MATERIAL_
    IMINENTE = True`.

    Devolve `None` quando o Gate 2 NÃO bloqueia (dívida segue para o Gate 3,
    fora do escopo desta tarefa).
    """
    if not divida.RISCO_MATERIAL_IMINENTE:
        return None

    if quitacao_e_a_propria_contencao:
        # EC-15: prioridade excepcional, com justificativa expressa — a
        # dívida AINDA sai da ordem-base e vai para ORDEM_ACOES (AC-23:
        # risco alto não promove sozinho); a exceção está em `acao.
        # prioridade_excepcional = True` e no motivo, não em tornar a
        # dívida elegível para a ordem ordinária.
        motivo = (
            f"{divida.DIVIDA_ID}: RISCO_MATERIAL_IMINENTE = True e a própria "
            "quitação é a ação que contém o risco e é executável — prioridade "
            "excepcional em ORDEM_ACOES, com justificativa expressa (EC-15). "
            "Não implica primeiro lugar automático na ordem-base (AC-23)."
        )
        tipo_acao = _derivar_TIPO_ACAO(GATE_PENDENTE.CONTENCAO_RISCO)
        acao = AcaoRequerida(
            # T-83: TIPO_ACAO derivado de GATE_PENDENTE (AMB-R2-02) e ACAO_ID
            # composto por _compor_ACAO_ID (T-80) — nada mais provisório.
            ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao=tipo_acao),
            DIVIDA_ID=divida.DIVIDA_ID,
            TIPO_ACAO=tipo_acao,
            descricao=motivo,
            gate_origem=2,
            # T-133 (RF-61/RF-62 · §14.2.1): nenhum valor de contenção é
            # modelado hoje em Divida/ResultadoGates para este ponto —
            # dinheiro(0) explícito, ambiguidade registrada em R4B.10.1, não
            # resolvida por esta tarefa.
            VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
            prioridade_excepcional=True,
        )
    else:
        motivo = (
            f"{divida.DIVIDA_ID}: RISCO_MATERIAL_IMINENTE = True — risco que exige "
            "ação anterior ao ataque ordinário. Desviada para ORDEM_ACOES; risco "
            "alto não a torna automaticamente a primeira dívida (AC-23)."
        )
        tipo_acao = _derivar_TIPO_ACAO(GATE_PENDENTE.CONTENCAO_RISCO)
        acao = AcaoRequerida(
            # T-83: TIPO_ACAO derivado de GATE_PENDENTE (AMB-R2-02) e ACAO_ID
            # composto por _compor_ACAO_ID (T-80) — nada mais provisório.
            ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao=tipo_acao),
            DIVIDA_ID=divida.DIVIDA_ID,
            TIPO_ACAO=tipo_acao,
            descricao=motivo,
            gate_origem=2,
            # T-133 (RF-61/RF-62 · §14.2.1): mesmo raciocínio do ramo acima
            # — sem oferta de valor conhecida neste ponto.
            VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
            prioridade_excepcional=False,
        )

    return ResultadoGates(
        DIVIDA_ID=divida.DIVIDA_ID,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE,
        GATE_PENDENTE=GATE_PENDENTE.CONTENCAO_RISCO,
        DIVIDA_ELEGIVEL_ORDEM=False,
        gate_bloqueador=2,
        motivo=motivo,
        acao=acao,
    )


def aplicar_gates_1_e_2(
    divida: Divida,
    resultado_valor_relevante: ResultadoValorRelevante,
    *,
    quitacao_e_a_propria_contencao: bool = False,
) -> ResultadoGates | None:
    """Orquestra Gate 1 → Gate 2, na sequência fixa de §11.3. Curto-circuita
    no primeiro que bloquear. Devolve `None` quando NENHUM dos dois bloqueia
    — a dívida segue candidata ao Gate 3.

    Mantida (em vez de absorvida por `aplicar_gates_1_a_4`) porque `T-27`/
    `T-28` e os testes de `T-29` já dependem desta assinatura reduzida (sem
    os parâmetros de Gate 3/4); `aplicar_gates_1_a_4` reaproveita esta função
    internamente para os dois primeiros gates, sem duplicar a lógica.
    """
    resultado_gate_1 = aplicar_gate_1_informacao(divida, resultado_valor_relevante)
    if resultado_gate_1 is not None:
        return resultado_gate_1

    resultado_gate_2 = aplicar_gate_2_contencao_risco(
        divida, quitacao_e_a_propria_contencao=quitacao_e_a_propria_contencao
    )
    if resultado_gate_2 is not None:
        return resultado_gate_2

    return None


def aplicar_gate_3_transformacao(divida: Divida) -> ResultadoGates | None:
    """Gate 3 — Transformação (§11.3, terceira linha da tabela).

    Renegociação, troca ou outra intervenção pendente que possa alterar
    materialmente saldo, parcela, taxa, prazo ou custo desvia a dívida da
    ordem ordinária: `DIVIDA_STATUS_ESTRATEGICO = INTERVENCAO_PENDENTE`,
    `GATE_PENDENTE = TRANSFORMACAO`. Verifica `divida.RENEGOCIACAO_PENDENTE`
    OU `divida.TROCA_PENDENTE` — os dois únicos campos de intervenção
    pendente modelados em `Divida` (`engine/estado.py`, ambos comentados
    "# Gate 3"); não há terceiro campo de intervenção no esquema atual.

    **AC-22 — "volta a ser elegível quando a intervenção for executada,
    rejeitada ou encerrada" NÃO é uma máquina de estados própria desta
    função.** Este gate é uma função pura que reflete o estado ATUAL de
    `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE`: se `True`, bloqueia agora; a
    "volta a ser elegível" é propriedade natural de reavaliar o MESMO gate
    sobre um NOVO estado da dívida — quando o chamador (o motor, num ciclo
    de recálculo disparado por `EVENTO_RECALCULO.RENEGOCIACAO_EXECUTADA` ou
    `TROCA_EXECUTADA`, `R-01`) atualizar esses campos para `False`, uma nova
    chamada a este gate simplesmente devolve `None` — nenhum histórico de
    transição precisa ser mantido AQUI para que AC-22 se cumpra. A
    responsabilidade de disparar o recálculo quando a intervenção muda de
    estado pertence ao motor (§3.2/RF-22), não a este gate.

    Devolve `None` quando o Gate 3 NÃO bloqueia (dívida segue para o Gate 4).
    """
    if not (divida.RENEGOCIACAO_PENDENTE or divida.TROCA_PENDENTE):
        return None

    if divida.RENEGOCIACAO_PENDENTE and divida.TROCA_PENDENTE:
        origem = "RENEGOCIACAO_PENDENTE e TROCA_PENDENTE"
    elif divida.RENEGOCIACAO_PENDENTE:
        origem = "RENEGOCIACAO_PENDENTE"
    else:
        origem = "TROCA_PENDENTE"

    motivo = (
        f"{divida.DIVIDA_ID}: {origem} = True — intervenção pendente que pode "
        "alterar materialmente saldo, parcela, taxa, prazo ou custo. Fora da "
        "ordem ordinária até a intervenção ser executada, rejeitada ou "
        "encerrada (AC-22)."
    )
    tipo_acao = _derivar_TIPO_ACAO_gate_3(
        renegociacao_pendente=divida.RENEGOCIACAO_PENDENTE,
        troca_pendente=divida.TROCA_PENDENTE,
    )
    # T-133 (RF-61/RF-62 · §14.2.1): único dos cinco pontos de gates.py com
    # candidato real em Divida a consultar — quando há proposta VIGENTE, o
    # valor de quitação hoje É o valor de ação financeira imediata desta
    # transformação; sem proposta vigente, a ação é só negociar/formalizar,
    # sem desembolso (dinheiro(0)).
    if divida.STATUS_VALIDADE_PROPOSTA is STATUS_VALIDADE_PROPOSTA.VIGENTE:
        valor_acao_financeira_imediata = divida.VALOR_QUITACAO_HOJE
    else:
        valor_acao_financeira_imediata = dinheiro(0)
    acao = AcaoRequerida(
        # T-84: TIPO_ACAO derivado de RENEGOCIACAO_PENDENTE/TROCA_PENDENTE
        # (AMB-R2-03) e ACAO_ID composto por _compor_ACAO_ID (T-80) — nada
        # mais provisório.
        ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao=tipo_acao),
        DIVIDA_ID=divida.DIVIDA_ID,
        TIPO_ACAO=tipo_acao,
        descricao=motivo,
        gate_origem=3,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=valor_acao_financeira_imediata,
        prioridade_excepcional=False,
    )

    return ResultadoGates(
        DIVIDA_ID=divida.DIVIDA_ID,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE,
        GATE_PENDENTE=GATE_PENDENTE.TRANSFORMACAO,
        DIVIDA_ELEGIVEL_ORDEM=False,
        gate_bloqueador=3,
        motivo=motivo,
        acao=acao,
    )


def avaliar_oportunidade_executavel(divida: Divida) -> bool:
    """`OPORTUNIDADE_EXECUTAVEL` (§11.3) — auxiliar separada do Gate 4.

    `OPORTUNIDADE_EXECUTAVEL = benefício + recurso disponível + prazo +
    sustentabilidade`: só é `True` se `divida.OPORTUNIDADE_VIGENTE` existir E
    todos os quatro componentes de `Oportunidade` (T-08) estiverem
    presentes/positivos — `beneficio` conhecido (não `DESCONHECIDO`),
    `recurso_disponivel = True`, `prazo` definido (não `None`) e
    `sustentavel = True`. Falta de qualquer um dos quatro torna a
    oportunidade não executável (RF-16: não inventar dado — nenhum
    componente ausente é tratado como presente).

    Esta função existe separada de `aplicar_gate_4_oportunidade` porque o
    Gate 4 em si NUNCA bloqueia (ver docstring daquela função) — é a
    consolidação futura de `ParticaoElegibilidade` (`T-32`) que vai usar este
    resultado para eventualmente sinalizar prioridade específica na ordem,
    sem que a elegibilidade da dívida dependa disso.
    """
    oportunidade = divida.OPORTUNIDADE_VIGENTE
    if oportunidade is None:
        return False

    beneficio_presente = oportunidade.beneficio is not DESCONHECIDO
    prazo_presente = oportunidade.prazo is not None

    return (
        beneficio_presente
        and oportunidade.recurso_disponivel
        and prazo_presente
        and oportunidade.sustentavel
    )


def aplicar_gate_4_oportunidade(divida: Divida) -> ResultadoGates | None:
    """Gate 4 — Oportunidade com prazo (§11.3, quarta linha da tabela).

    **CRÍTICO (EC-16) — este é o único dos quatro gates que estruturalmente
    NÃO bloqueia.** Os Gates 1–3 desviam a dívida da ordem-base quando a
    condição deles se verifica; o Gate 4 é diferente por desenho normativo:
    "Avaliada antes da ordem-base [...]. **Não** é bloqueio automático, e
    desconto não implica primeiro lugar" (§11.3, quarta linha). Uma
    oportunidade vigente — mesmo quando `OPORTUNIDADE_EXECUTAVEL = True` — é
    informação que PODE gerar prioridade específica dentro da ordem-base
    (consolidada em `T-32`), nunca um motivo para tirar a dívida da ordem
    ordinária nem para promovê-la automaticamente ao primeiro lugar (mesma
    trava estrutural de `AC-23` para o Gate 2, agora aplicada ao Gate 4).

    Por isso esta função devolve **sempre** `None`: a dívida segue elegível
    para a ordem-base independentemente de `OPORTUNIDADE_VIGENTE`. A
    avaliação de `OPORTUNIDADE_EXECUTAVEL` em si vive em
    `avaliar_oportunidade_executavel`, separada desta função — não porque o
    dado seja irrelevante, mas porque ele não é insumo de BLOQUEIO, e sim de
    PRIORIDADE (papel distinto, consumido por outra camada). Manter a função
    com a mesma forma `Divida -> ResultadoGates | None` dos outros três gates
    preserva a uniformidade da sequência em `aplicar_gates_1_a_4`, mesmo que
    o valor de retorno seja sempre o mesmo aqui.
    """
    return None


def aplicar_gates_1_a_4(
    divida: Divida,
    resultado_valor_relevante: ResultadoValorRelevante,
    *,
    quitacao_e_a_propria_contencao: bool = False,
) -> ResultadoGates | None:
    """Orquestra os quatro gates na sequência fixa de §11.3: Informação →
    Contenção de Risco → Transformação → Oportunidade com Prazo.
    Curto-circuita no primeiro que bloquear — Gates 1, 2 e 3 podem bloquear;
    o Gate 4 nunca bloqueia sozinho (EC-16), então só "roda" depois que os
    três primeiros passaram, e sempre devolve `None` da perspectiva de
    bloqueio (ver `aplicar_gate_4_oportunidade`).

    Devolve `None` quando NENHUM gate bloqueia — a dívida está
    `DIVIDA_ELEGIVEL_ORDEM = True`, pronta para a ordem-base. Devolve
    `ResultadoGates` do primeiro gate que bloquear, com `gate_bloqueador`
    registrado (`1`, `2` ou `3`) e `motivo` reaproveitável por
    `JUSTIFICATIVA_POSICAO` (Q-05).

    Substitui, para efeito de uso pelo chamador, a função `aplicar_gates`
    desenhada no plano §4 — ver nota de interface no topo do módulo sobre
    por que a assinatura completa (`ContextoGates`, `Parametros`) é adiada.
    """
    resultado_gates_1_e_2 = aplicar_gates_1_e_2(
        divida,
        resultado_valor_relevante,
        quitacao_e_a_propria_contencao=quitacao_e_a_propria_contencao,
    )
    if resultado_gates_1_e_2 is not None:
        return resultado_gates_1_e_2

    resultado_gate_3 = aplicar_gate_3_transformacao(divida)
    if resultado_gate_3 is not None:
        return resultado_gate_3

    # Gate 4 nunca bloqueia (EC-16) — sempre None. Chamado por completude e
    # uniformidade da sequência fixa; `avaliar_oportunidade_executavel` é o
    # ponto de entrada para quem precisar do dado de OPORTUNIDADE_EXECUTAVEL.
    return aplicar_gate_4_oportunidade(divida)


def determinar_status_estrategico(
    divida: Divida,
    resultado_valor_relevante: ResultadoValorRelevante,
    *,
    quitacao_e_a_propria_contencao: bool = False,
) -> ResultadoGates:
    """Mapeamento completo `STATUS_DIVIDA` → `DIVIDA_STATUS_ESTRATEGICO`
    (`T-31`, Definições §6, tabela inteira de §11.3).

    **`STATUS_DIVIDA` não decide elegibilidade sozinho** — quem decide são
    os gates (§11.3). Esta função só usa `STATUS_DIVIDA` para UM desvio
    estrutural que precede os próprios gates (`OUTRA`, item 1 abaixo); todo
    o resto da tabela é resolvido deixando a dívida atravessar
    `aplicar_gates_1_a_4` normalmente:

    1. `OUTRA` → `EM_ANALISE`, sem ataque, **sem passar pelos gates 1–4**
       (AC-45). A tabela descreve isso como "sem ataque até a situação ser
       normalizada" — é um desvio ANTES da avaliação de elegibilidade, não
       um resultado que um gate produz; por isso é tratado aqui, fora de
       `aplicar_gates_1_a_4`.
    2. `QUITADA_A_CONFIRMAR` → já coberto pelo Gate 1
       (`aplicar_gate_1_informacao`, `T-29`): falta de confirmação é falta
       de informação estrutural, então basta deixar a dívida atravessar os
       gates normalmente (AC-44).
    3. `EM_ACORDO` → sem tratamento especial: os dois sub-casos da tabela
       ("acordo executado, estrutura conhecida, nada pendente" vs.
       "negociação aberta ou estrutura sujeita a mudança material") são
       exatamente o que `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE` já
       distinguem para QUALQUER dívida via Gate 3 — ver decisão documentada
       no cabeçalho do módulo. Atravessa os gates como as demais.
    4. `ATIVA` / `COBRANCA_SEM_PAGAMENTO` → atravessam os quatro gates
       normalmente. Para `COBRANCA_SEM_PAGAMENTO` especificamente, "elegível
       se a existência for confirmada e houver `VALOR_RELEVANTE_PARA_
       QUITACAO` conhecido" (AC-42) já é coberto pelo Gate 1, que bloqueia
       quando `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO`
       (`aplicar_gate_1_informacao`) — nenhuma lógica extra é necessária, e
       nenhum caminho lê ou inventa `PAGAMENTO_MENSAL_DEVIDO_VIGENTE`: este
       campo não existe em `Divida` (`engine/estado.py`) e esta função nunca
       o referencia, preservando RF-16.

    Quando os quatro gates atravessam sem bloquear, as funções de gate
    individuais devolvem `None` (contrato de `aplicar_gates_1_a_4`) — não há
    `ResultadoGates` de sucesso pronto para devolver. É esta função que
    monta esse resultado positivo: `DIVIDA_STATUS_ESTRATEGICO =
    PRONTA_PARA_ORDENACAO`, `GATE_PENDENTE = NENHUM`, `DIVIDA_ELEGIVEL_ORDEM
    = True`, `gate_bloqueador = None`.

    Diferente das funções de gate individuais (que devolvem `None` quando
    não bloqueiam, para permitir encadeamento), esta função SEMPRE devolve
    um `ResultadoGates` — ela é o ponto de consolidação final, não um elo de
    uma cadeia. `EM_ATAQUE` (a dívida já é o alvo corrente) não é decidido
    aqui: esta função só distingue elegibilidade estrutural; a promoção de
    `PRONTA_PARA_ORDENACAO` para `EM_ATAQUE` quando a dívida já é
    `DIVIDA_ALVO_ATUAL` é responsabilidade de quem monta o ciclo mensal
    (fora do escopo desta tarefa, que é só o mapeamento de `STATUS_DIVIDA`).
    """
    if divida.STATUS_DIVIDA == STATUS_DIVIDA.OUTRA:
        # AC-45: desvio ANTES dos gates — "sem ataque até a situação ser
        # normalizada" não é um bloqueio de gate, é uma condição prévia.
        return ResultadoGates(
            DIVIDA_ID=divida.DIVIDA_ID,
            DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.EM_ANALISE,
            GATE_PENDENTE=GATE_PENDENTE.NENHUM,
            DIVIDA_ELEGIVEL_ORDEM=False,
            gate_bloqueador=None,
            motivo=(
                f"{divida.DIVIDA_ID}: STATUS_DIVIDA = OUTRA — situação fora dos "
                "demais status conhecidos, em análise; sem ataque até ser "
                "normalizada (AC-45)."
            ),
            acao=None,
        )

    resultado_bloqueio = aplicar_gates_1_a_4(
        divida,
        resultado_valor_relevante,
        quitacao_e_a_propria_contencao=quitacao_e_a_propria_contencao,
    )
    if resultado_bloqueio is not None:
        # QUITADA_A_CONFIRMAR (Gate 1), risco (Gate 2) ou transformação
        # pendente (Gate 3, cobre também EM_ACORDO com negociação aberta ou
        # estrutura sujeita a mudança material) — já plenamente resolvido
        # pelos gates individuais.
        return resultado_bloqueio

    # Nenhum gate bloqueou: ATIVA, EM_ACORDO (acordo executado/estrutura
    # conhecida) ou COBRANCA_SEM_PAGAMENTO (existência confirmada e valor
    # relevante conhecido, garantido pelo Gate 1) chegam aqui elegíveis.
    return ResultadoGates(
        DIVIDA_ID=divida.DIVIDA_ID,
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        GATE_PENDENTE=GATE_PENDENTE.NENHUM,
        DIVIDA_ELEGIVEL_ORDEM=True,
        gate_bloqueador=None,
        motivo=(
            f"{divida.DIVIDA_ID}: os quatro gates resolvidos — elegível para a "
            "ordem-base (PRONTA_PARA_ORDENACAO)."
        ),
        acao=None,
    )


@dataclass(frozen=True, slots=True)
class ParticaoElegibilidade:
    """Consolidação do inventário inteiro pelos gates — `T-32`, §4 do plano
    técnico, §11.3, RF-17, EC-17.

    Agrega, para todas as dívidas de um `EstadoFinanceiro.dividas`, os três
    grupos que `determinar_status_estrategico` (`T-31`) já resolve dívida a
    dívida:

    - `elegiveis`: as com `DIVIDA_ELEGIVEL_ORDEM = True` — candidatas à
      ordem-base dos três métodos (Avalanche/Bola de Neve/Híbrido). Ordem
      TOTAL e DETERMINÍSTICA (ver `particionar_elegibilidade`), mas **não** é
      o ranking final: o ranqueamento real pelos métodos é escopo de `T-49+`.
    - `ORDEM_ACOES`: fila PARALELA — nunca `ORDEM_QUITACAO` — com os itens
      `acao` de todo `ResultadoGates` que gerou um. `T-87` (`RF-32`) faz o
      Gate 1 passar a gerar `acao` nos dois ramos de bloqueio, assim como os
      Gates 2 e 3 (`T-29`/`T-30`) — só o desvio `OUTRA`/`EM_ANALISE`
      continua nunca preenchendo `acao` (situação prévia aos próprios
      gates, ver `ResultadoGates.acao` e `determinar_status_estrategico`).
    - `bloqueadas`: todo `ResultadoGates` com `DIVIDA_ELEGIVEL_ORDEM = False`
      — inclui tanto as que geraram `acao` (Gates 1/2/3) quanto as que não
      geraram (desvio `OUTRA`/`EM_ANALISE`). Toda dívida bloqueada aparece
      aqui com seu `gate_bloqueador` e `motivo`, mesmo que também tenha
      gerado uma `AcaoRequerida`.

    **EC-17 — `elegiveis == ()` é estado VÁLIDO**, não uma falha: sinaliza
    que não há alvo para a ordem-base neste snapshot (todas bloqueadas, ou
    inventário vazio). Não existe `DIVIDA_ALVO_ATUAL` nesse caso — o
    consumidor (o motor, ao montar `SnapshotOrdem`) deve tratar isso sem
    quebrar: o plano vira ação (`ORDEM_ACOES` como saída principal) e o
    cronograma fica condicional (§5, passo 6, do plano técnico).
    """

    elegiveis: tuple[Divida, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]  # fila PARALELA, não é ordem de ataque
    bloqueadas: tuple[ResultadoGates, ...]
    # EC-17: elegiveis == () → não há alvo; o plano vira ação.


def particionar_elegibilidade(dividas: tuple[Divida, ...]) -> ParticaoElegibilidade:
    """Produz `ParticaoElegibilidade` a partir do inventário completo —
    `T-32`, RF-17, EC-17.

    Para cada dívida: compõe `ResultadoValorRelevante` (`T-27`,
    `compor_VALOR_RELEVANTE_PARA_QUITACAO`) e roda `determinar_status_
    estrategico` (`T-31`) para obter o `ResultadoGates` correspondente. Esta
    função **agrega** — não reimplementa a fórmula de `DIVIDA_ELEGIVEL_ORDEM`
    nem decide gate algum; ela só classifica o `ResultadoGates` já correto de
    cada dívida em `elegiveis`, `ORDEM_ACOES` e `bloqueadas`.

    `quitacao_e_a_propria_contencao` (EC-15, Gate 2) não é parâmetro aqui:
    nenhum campo de `Divida` (`engine/estado.py`) determina automaticamente
    se a quitação é a própria contenção do risco — é avaliação de negócio
    externa à dívida (ver docstring de `aplicar_gate_2_contencao_risco`).
    Como este particionamento opera sobre o inventário inteiro sem contexto
    de negócio adicional, cada dívida usa o padrão conservador
    (`quitacao_e_a_propria_contencao=False`): a EXCEÇÃO de prioridade
    excepcional continua disponível para quem chamar
    `determinar_status_estrategico`/`aplicar_gate_2_contencao_risco`
    diretamente, com o contexto de negócio em mãos.

    **Ordenação de `elegiveis` — total e determinística (O-05/H-04).** Nesta
    tarefa a ordenação é a mais simples que satisfaz o critério: preserva a
    ordem de entrada de `dividas` (que já é uma tupla, portanto
    determinística por construção), com `DIVIDA_ID` como critério de
    desempate final explícito — não há dois elementos com o mesmo
    `DIVIDA_ID` no domínio (identificador único por dívida), então o
    desempate nunca é de fato exercitado, mas a chave de ordenação inclui
    `DIVIDA_ID` para deixar a garantia explícita e estável mesmo se a ordem
    de entrada não vier previamente estável. O ranqueamento REAL por
    Avalanche/Bola de Neve/Híbrido (`RF-01`..`RF-03`) é escopo de `T-49+` e
    substitui esta ordenação, não a estende.
    """
    elegiveis: list[Divida] = []
    ordem_acoes: list[AcaoRequerida] = []
    bloqueadas: list[ResultadoGates] = []

    for divida in dividas:
        resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
        resultado_gates = determinar_status_estrategico(divida, resultado_valor_relevante)

        if resultado_gates.acao is not None:
            ordem_acoes.append(resultado_gates.acao)

        if resultado_gates.DIVIDA_ELEGIVEL_ORDEM:
            elegiveis.append(divida)
        else:
            bloqueadas.append(resultado_gates)

    # O-05/H-04: ordem total e determinística, DIVIDA_ID como desempate
    # final. `dividas` já é tupla (ordem de entrada preservada e estável);
    # a chave explícita torna a garantia auditável independente da ordem de
    # entrada.
    elegiveis_ordenadas = tuple(sorted(elegiveis, key=lambda d: d.DIVIDA_ID))

    return ParticaoElegibilidade(
        elegiveis=elegiveis_ordenadas,
        ORDEM_ACOES=tuple(ordem_acoes),
        bloqueadas=tuple(bloqueadas),
    )


def NECESSIDADE_IMEDIATA_DIVIDA(
    *,
    GATE_PENDENTE: tipos.GATE_PENDENTE,
    DIVIDA_STATUS_ESTRATEGICO: tipos.DIVIDA_STATUS_ESTRATEGICO,
    acao_financeira_imediata_executavel: AcaoRequerida | None,
    VALOR_RELEVANTE_PARA_QUITACAO: DinheiroTalvez,
) -> DinheiroTalvez:
    """`NECESSIDADE_IMEDIATA_DIVIDA` — `RF-64`, `RF-65` · §14.1.1 · `T-134`.

    Quanto do saldo desta dívida pode receber aplicação imediata de
    recursos, avaliado em ordem ESTRITA de cinco ramos (§14.1.1) — cadeia
    `if`/`elif` única, nunca funções auxiliares que calculam mais de um
    ramo antes de decidir:

    1. Gate 1 pendente (`GATE_PENDENTE.INFORMACAO`) → `0`.
    2. Gate 3 pendente (`GATE_PENDENTE.TRANSFORMACAO`) → `0`.
    3. Existe ação financeira imediata executável agora (Gate 2/4,
       `acao_financeira_imediata_executavel is not None`) com
       `VALOR_ACAO_FINANCEIRA_IMEDIATA` conhecido → esse valor. Se a ação
       existe mas o valor é `DESCONHECIDO`, este ramo AINDA decide — o
       retorno é `DESCONHECIDO`, propagado (`RF-63`, `AC-109`), e a função
       não cai para o ramo 4/5. Ação que não é executável agora
       (`acao_financeira_imediata_executavel is None`) nunca entra aqui.
    4. `DIVIDA_STATUS_ESTRATEGICO` em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}`
       → `VALOR_RELEVANTE_PARA_QUITACAO` **integral**, sem multiplicação,
       `MIN`/`MAX` ou fração (`AC-107`) — passado adiante tal como recebido.
    5. Senão → `0`.

    `RF-65` (`AC-104`, `AC-111`) — TRAVA DE DUPLA CONTAGEM: os ramos 3 e 4
    são mutuamente exclusivos por CONSTRUÇÃO da cadeia `if`/`elif` — uma
    mesma chamada nunca avalia os dois. Não há verificação separada de
    dupla contagem porque a ordem estrita já a torna estruturalmente
    impossível (plano R4B.10).

    Função pura: só lê os quatro parâmetros recebidos — nenhum acesso a
    `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou variável global.
    """
    # §14.1.1 · RF-64/RF-65: cadeia if/elif/…/else ÚNICA, cinco ramos, nesta
    # ordem exata — nenhum return antecipado fora da cadeia.
    if GATE_PENDENTE is tipos.GATE_PENDENTE.INFORMACAO:
        # Ramo 1 — Gate 1 pendente.
        resultado: DinheiroTalvez = dinheiro(0)
    elif GATE_PENDENTE is tipos.GATE_PENDENTE.TRANSFORMACAO:
        # Ramo 2 — Gate 3 pendente.
        resultado = dinheiro(0)
    elif acao_financeira_imediata_executavel is not None:
        # Ramo 3 — ação financeira imediata executável agora (Gate 2/4):
        # RF-63/AC-109, propaga o valor tal como está, incluindo
        # DESCONHECIDO quando o valor da ação não é conhecido — nunca cai
        # para o ramo 4/5 por causa disso.
        resultado = acao_financeira_imediata_executavel.VALOR_ACAO_FINANCEIRA_IMEDIATA
    elif DIVIDA_STATUS_ESTRATEGICO in (
        tipos.DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
        tipos.DIVIDA_STATUS_ESTRATEGICO.EM_ATAQUE,
    ):
        # Ramo 4 — dívida ordinariamente elegível: VALOR_RELEVANTE_PARA_
        # QUITACAO integral (AC-107), sem multiplicação, MIN/MAX ou fração.
        resultado = VALOR_RELEVANTE_PARA_QUITACAO
    else:
        # Ramo 5 — nenhum dos anteriores se aplica.
        resultado = dinheiro(0)

    return resultado


def NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
    *,
    particao: ParticaoElegibilidade,
    acoes_por_divida: Mapping[str, AcaoRequerida],
) -> DinheiroTalvez:
    """`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` — `RF-64` · §14.1 · `T-135`.

    Teto monetário objetivo do valor que pode receber aplicação imediata de
    recursos, após os gates: soma `NECESSIDADE_IMEDIATA_DIVIDA(d)` (`T-134`)
    sobre TODAS as dívidas do inventário — `elegiveis` e `bloqueadas` de
    `particao` (`RF-64` não restringe a soma às elegíveis; dívidas
    bloqueadas por Gate 1/3 já contribuem `0` pela própria fórmula dos
    ramos 1/2 de `NECESSIDADE_IMEDIATA_DIVIDA`, então somar o inventário
    inteiro e somar só elegíveis+demais produzem o mesmo resultado
    numérico). `acoes_por_divida` fornece, por `DIVIDA_ID`, a ação
    financeira imediata associada quando existir (ramo 3 de
    `NECESSIDADE_IMEDIATA_DIVIDA`) — ausência de entrada no mapa equivale a
    "nenhuma ação financeira imediata executável agora para esta dívida".

    Para `elegiveis` (`Divida`, sem `GATE_PENDENTE`/`DIVIDA_STATUS_
    ESTRATEGICO` próprios — ordem-base sem bloqueio), os dois primeiros
    ramos nunca se aplicam: usa-se `GATE_PENDENTE.NENHUM` e
    `DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO` (o resultado que
    `determinar_status_estrategico` já atribuiu para chegar a `elegiveis`),
    com `VALOR_RELEVANTE_PARA_QUITACAO` recomposto por
    `compor_VALOR_RELEVANTE_PARA_QUITACAO`. Para `bloqueadas`
    (`ResultadoGates`), os três primeiros insumos já vêm resolvidos pelo
    próprio `ResultadoGates` — dívida bloqueada pelo Gate 1/3 contribui `0`
    pela própria fórmula, então `VALOR_RELEVANTE_PARA_QUITACAO` não precisa
    ser recomposto para o ramo 4 (nunca alcançado por essas dívidas).

    Inventário vazio → `0`, estado legitimamente distinto de incompletude
    (`EC-45`).

    `AC-108` (`EC-46`) — se QUALQUER parcela for `DESCONHECIDO`, o
    resultado inteiro é `DESCONHECIDO`: propagação, nunca fallback — jamais
    soma parcial das dívidas conhecidas apresentada como total definitivo,
    mesmo com as demais parcelas conhecidas e somáveis.

    Soma em `Decimal` exato, sem arredondamento intermediário (tolerância
    zero desta fatia). Função pura: só lê `particao`/`acoes_por_divida` —
    nenhum acesso a `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou
    variável global.
    """
    total = dinheiro(0)

    for divida in particao.elegiveis:
        resultado_valor_relevante = compor_VALOR_RELEVANTE_PARA_QUITACAO(divida)
        parcela = NECESSIDADE_IMEDIATA_DIVIDA(
            GATE_PENDENTE=tipos.GATE_PENDENTE.NENHUM,
            DIVIDA_STATUS_ESTRATEGICO=tipos.DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO,
            acao_financeira_imediata_executavel=acoes_por_divida.get(divida.DIVIDA_ID),
            VALOR_RELEVANTE_PARA_QUITACAO=resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO,
        )
        if parcela is DESCONHECIDO:
            return DESCONHECIDO
        total += parcela

    for resultado_gates in particao.bloqueadas:
        parcela = NECESSIDADE_IMEDIATA_DIVIDA(
            GATE_PENDENTE=resultado_gates.GATE_PENDENTE,
            DIVIDA_STATUS_ESTRATEGICO=resultado_gates.DIVIDA_STATUS_ESTRATEGICO,
            acao_financeira_imediata_executavel=acoes_por_divida.get(resultado_gates.DIVIDA_ID),
            # `bloqueadas` é, por definição, toda dívida com DIVIDA_ELEGIVEL_
            # ORDEM=False (particionar_elegibilidade) — logo seu DIVIDA_
            # STATUS_ESTRATEGICO NUNCA é PRONTA_PARA_ORDENACAO/EM_ATAQUE (só
            # dívida elegível recebe um desses dois). O ramo 4 de
            # NECESSIDADE_IMEDIATA_DIVIDA, o único que lê VALOR_RELEVANTE_
            # PARA_QUITACAO, portanto nunca é alcançado por uma dívida
            # bloqueada — dinheiro(0) é valor neutro nunca de fato lido.
            VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(0),
        )
        if parcela is DESCONHECIDO:
            return DESCONHECIDO
        total += parcela

    return total
