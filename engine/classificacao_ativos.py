"""Classificação de ativos e valor líquido realizável — §14 da spec do slug
(documento canônico PIQ v1.0.1, "Fechamento Canônico — Necessidade Financeira
Imediata e Classificação de Ativos", congelado em 2026-09-09) · RF-53..RF-58.

Fonte normativa: `specs/motor-calculo.spec.md` §14 ("Definições incorporadas
— Rodada 4"), cuja regra de precedência transcrita é explícita: para os temas
tratados naquela seção, estas definições prevalecem sobre qualquer redação
anterior conflitante, incompleta ou menos específica. "Nenhuma dessas
decisões fica a critério do desenvolvedor."

TODA função deste módulo é PURA no sentido forte da NFR "Pureza (Rodada 3)"
(spec §5), preservada na Rodada 4 (plano R4.2, R4.7): recebe todas as suas
entradas por parâmetro nomeado (`*`), não consulta `EstadoFinanceiro`, não
consulta `Diagnostico`, não lê relógio, arquivo nem variável global.

Escopo deste arquivo: as duas funções de valor líquido realizável de ativo
(§14.12.1/§14.12.4/§14.12.5/§14.12.2, `RF-57`, `RF-58`, `T-121`) e as duas
funções de classificação determinística (`classificar_investimento`, §14.3.1,
`RF-53`, `T-122`; `classificar_ativo_fisico`, §14.4-§14.9, `RF-54`..`RF-56`,
`T-123`).

REGRAS: Final[tuple[str, ...]] = ("RF-53", "RF-54", "RF-55", "RF-56", "RF-57",
                                  "RF-58", "§14.3", "§14.3.1", "§14.4", "§14.5",
                                  "§14.6", "§14.7", "§14.8", "§14.9", "§14.12")
"""

from __future__ import annotations

from typing import Final

from engine.estado import (
    DISPOSICAO_USO_INVESTIMENTO,
    ESSENCIALIDADE,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
    ItemInvestimento,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO, DinheiroTalvez

REGRAS: Final[tuple[str, ...]] = (
    "RF-53",
    "RF-54",
    "RF-55",
    "RF-56",
    "RF-57",
    "RF-58",
    "§14.3",
    "§14.3.1",
    "§14.4",
    "§14.5",
    "§14.6",
    "§14.7",
    "§14.8",
    "§14.9",
    "§14.12",
)


def derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
    *,
    VALOR_ESTIMADO_ATIVO: DinheiroTalvez,
    POSSUI_PASSIVO_VINCULADO: bool,
    SALDO_PASSIVO_VINCULADO: DinheiroTalvez,
    POSSUI_CUSTO_DESMOBILIZACAO: bool,
    CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez,
) -> DinheiroTalvez:
    """RF-57 · §14.12.1, §14.12.4, §14.12.5 · §14.14
    `deriveValorLiquidoRealizavelAtivo`.

    `VALOR_ESTIMADO_ATIVO − SALDO_PASSIVO_VINCULADO −
    CUSTOS_ESTIMADOS_DESMOBILIZACAO`. PODE ser negativo (§14.12.2, REGRA
    CANÔNICA) — nenhum MAX/MIN aqui: esta função é deliberadamente
    independente de `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
    (RF-57, restrição dura do plano R4.4.3/R4.10).

    Ordem de avaliação NORMATIVA (§14.14), cada guarda vence a seguinte:
      1. `VALOR_ESTIMADO_ATIVO is DESCONHECIDO` -> `DESCONHECIDO`, sem sequer
         avaliar passivo/custo (`EC-36`) — nada abaixo é lido.
      2. Passivo (§14.12.4): `POSSUI_PASSIVO_VINCULADO=False` -> 0; `True` E
         `SALDO_PASSIVO_VINCULADO is DESCONHECIDO` -> `DESCONHECIDO` (`RF-58`,
         `AC-99`, nunca assumir zero); `True` e conhecido -> usa o valor.
      3. Custo (§14.12.5): mesma lógica de `POSSUI_CUSTO_DESMOBILIZACAO` sobre
         `CUSTOS_ESTIMADOS_DESMOBILIZACAO`.
      4. Só então a subtração — pode resultar em valor negativo.
    """
    # Guarda 1 (§14.12.1, EC-36) — valor estimado desconhecido vence tudo,
    # sem tocar passivo/custo.
    if VALOR_ESTIMADO_ATIVO is DESCONHECIDO:
        return DESCONHECIDO

    # Guarda 2 (§14.12.4) — normalização do passivo vinculado. "Não existe"
    # vira 0; "existe e desconhecido" propaga DESCONHECIDO (RF-58, AC-99),
    # nunca assumido como zero.
    if not POSSUI_PASSIVO_VINCULADO:
        saldo_passivo = dinheiro(0)
    elif SALDO_PASSIVO_VINCULADO is DESCONHECIDO:
        return DESCONHECIDO
    else:
        saldo_passivo = SALDO_PASSIVO_VINCULADO

    # Guarda 3 (§14.12.5) — normalização do custo de desmobilização, mesma
    # lógica de "não existe" -> 0 / "existe e desconhecido" -> DESCONHECIDO.
    if not POSSUI_CUSTO_DESMOBILIZACAO:
        custo = dinheiro(0)
    elif CUSTOS_ESTIMADOS_DESMOBILIZACAO is DESCONHECIDO:
        return DESCONHECIDO
    else:
        custo = CUSTOS_ESTIMADOS_DESMOBILIZACAO

    # §14.12.1 — subtração final. PODE ser negativo (REGRA CANÔNICA §14.12.2).
    return VALOR_ESTIMADO_ATIVO - saldo_passivo - custo


def derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
    *, VALOR_LIQUIDO_REALIZAVEL_ATIVO: DinheiroTalvez
) -> DinheiroTalvez:
    """RF-57 · §14.12.2 · §14.14 `deriveValorLiquidoRealizavelAtivoDisponivel`
    — `MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)`. NUNCA negativo (REGRA
    CANÔNICA §14.12.2). Propaga DESCONHECIDO sem aplicar MAX sobre um
    desconhecido (`GAB-NFI-12`, `AC-94`).

    Função SEPARADA da anterior — não uma composta que já aplica MAX
    internamente — porque a spec exige as DUAS variáveis expostas e
    testáveis independentemente (RF-57, restrição dura do pedido desta
    fatia; plano R4.10).
    """
    if VALOR_LIQUIDO_REALIZAVEL_ATIVO is DESCONHECIDO:
        return DESCONHECIDO
    return max(dinheiro(0), VALOR_LIQUIDO_REALIZAVEL_ATIVO)


def classificar_investimento(item: ItemInvestimento) -> CLASSIFICACAO_MOBILIZACAO:
    """RF-53 · §14.3, §14.3.1, §14.3.1.1 · §14.14 `classifyInvestment`.

    SEIS regras em cadeia `if`/`elif` ESTRITA, ORDEM EXATA (NFR "Ordem de
    precedência é normativa"; `AC-88`-`AC-90`, `AC-95`, `EC-33`) — cada
    ramo abaixo é um `elif`, nunca condição paralela; um investimento que
    satisfaz duas regras cai sempre na primeira que se aplica:

      Regra 1 — bloqueio: `DISPOSICAO_USO_INVESTIMENTO=NAO` OU
        `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO` -> `NAO_MOBILIZAR`. Avaliada
        ANTES de qualquer outra regra (`EC-33`).
      Regra 2 — dado desconhecido: valor/liquidez/custo p/ apurar valor
        líquido desconhecidos -> `MOBILIZACAO_COM_RESSALVAS`. Em
        `ItemInvestimento` (`T-119`), `VALOR_LIQUIDO_REALIZAVEL_ATIVO_
        DISPONIVEL` é tipado `Dinheiro` puro, não `DinheiroTalvez` — a
        própria construção do item já exige o valor conhecido (`EC-32`),
        então este ramo é estruturalmente inalcançável por este campo
        neste construtor; preservado na numeração/docstring por
        fidelidade à ordem normativa de `classifyInvestment` (§14.14), sem
        ramo `elif` correspondente no código, já que nenhuma condição em
        `Dinheiro` puro pode ser `is DESCONHECIDO` (checado por
        `mypy --strict`, `comparison-overlap`).
      Regra 3 — disposição condicional: `DISPOSICAO_USO_INVESTIMENTO=TALVEZ`
        E o investimento pode efetivamente ser resgatado (`LIQUIDEZ_
        INVESTIMENTOS != BLOQUEADO`, já garantido pela Regra 1 não ter
        disparado) -> `MOBILIZACAO_POSSIVEL`.
      Regra 4 — líquido/disponível/sem custo: `DISPOSICAO_USO_INVESTIMENTO=
        SIM` E `LIQUIDEZ_INVESTIMENTOS em {D0,D1,D7}` E
        `SEM_CUSTO_PERDA_RELEVANTE` E `VALOR_LIQUIDO_REALIZAVEL_ATIVO_
        DISPONIVEL > 0` -> `MOBILIZACAO_RECOMENDAVEL`.
      Regra 5 — custo conhecido ou D30: `DISPOSICAO_USO_INVESTIMENTO=SIM`
        E (`TEM_CUSTO_CONHECIDO` OU `LIQUIDEZ_INVESTIMENTOS=D30`) ->
        `MOBILIZACAO_POSSIVEL`.
      Regra 6 — liquidez longa/indeterminado: `LIQUIDEZ_INVESTIMENTOS=
        MAIS_30` OU custo/perda indeterminado OU consequência material não
        quantificada -> `MOBILIZACAO_COM_RESSALVAS`. Guarda-final: qualquer
        combinação de `DISPOSICAO_USO_INVESTIMENTO=SIM` que não caiu nas
        Regras 4/5 (ex.: liquidez longa sem custo conhecido) também recai
        aqui, mesma leitura de `classifyInvestment` (§14.14, fallback final
        `return MOBILIZACAO_COM_RESSALVAS`).

    Nenhum ramo lê ou distingue por TIPO de investimento (§14.3.1.1,
    `EC-37`): nenhuma variável de "tipo" (CDB/previdência/ação/poupança) é
    parâmetro desta função — não presumir que todo CDB é recomendável, toda
    previdência não mobilizar, toda ação possível, toda poupança
    recomendável.
    """
    # Regra 1 (§14.3.1, EC-33) — bloqueio, avaliada antes de qualquer outra.
    if (
        item.DISPOSICAO_USO_INVESTIMENTO == DISPOSICAO_USO_INVESTIMENTO.NAO
        or item.LIQUIDEZ_INVESTIMENTOS == LIQUIDEZ_INVESTIMENTOS.BLOQUEADO
    ):
        return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
    # Regra 2 (§14.3.1, §14.14) — dado desconhecido para apurar o valor
    # líquido disponível. Sem ramo `elif` correspondente: em
    # `ItemInvestimento` (T-119) o campo é tipado `Dinheiro` puro, não
    # `DinheiroTalvez` — a construção do item já garante valor conhecido
    # (EC-32), então esta condição é estruturalmente inalcançável aqui
    # (ver docstring). Numeração das regras preservada nos comentários
    # abaixo por fidelidade à ordem normativa de `classifyInvestment`.
    # Regra 3 — disposição condicional, investimento efetivamente resgatável
    # (liquidez BLOQUEADO já descartada pela Regra 1 não ter disparado).
    elif item.DISPOSICAO_USO_INVESTIMENTO == DISPOSICAO_USO_INVESTIMENTO.TALVEZ:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    # Regra 4 — líquido/disponível/sem custo relevante.
    elif (
        item.DISPOSICAO_USO_INVESTIMENTO == DISPOSICAO_USO_INVESTIMENTO.SIM
        and item.LIQUIDEZ_INVESTIMENTOS
        in {
            LIQUIDEZ_INVESTIMENTOS.D0,
            LIQUIDEZ_INVESTIMENTOS.D1,
            LIQUIDEZ_INVESTIMENTOS.D7,
        }
        and item.SEM_CUSTO_PERDA_RELEVANTE
        and item.VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL > dinheiro(0)
    ):
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    # Regra 5 — custo conhecido de saída ou liquidez D30.
    elif item.DISPOSICAO_USO_INVESTIMENTO == DISPOSICAO_USO_INVESTIMENTO.SIM and (
        item.TEM_CUSTO_CONHECIDO
        or item.LIQUIDEZ_INVESTIMENTOS == LIQUIDEZ_INVESTIMENTOS.D30
    ):
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    # Regra 6 — liquidez longa/indeterminado (fallback final de §14.14).
    else:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS


def classificar_ativo_fisico(item: ItemAtivo) -> CLASSIFICACAO_MOBILIZACAO | None:
    """RF-54, RF-55, RF-56 · §14.4-§14.9 · §14.14 `classifyPhysicalAsset`.

    OITO ramos em cadeia `if`/`elif` ESTRITA, ORDEM EXATA do pseudocódigo
    `classifyPhysicalAsset` (§14.14) — guardas de §14.4 (bloqueio, dado
    desconhecido, valor líquido zero) ANTES da ramificação por
    essencialidade de §14.5-§14.9 (`AC-96`, `EC-34`, `EC-35`; ver nota de
    ordem do plano R4.4.3, que concilia o pseudocódigo com a prosa das
    §14.4-14.9):

      1. `POSSIBILIDADE_VENDA=NAO` -> `NAO_MOBILIZAR` (§14.4.1). Avaliado
         ANTES de qualquer outra condição, inclusive quando o item também
         satisfaz a condição de dado desconhecido do ramo 2 (`AC-96`,
         `EC-35`) — bloqueio de venda sempre vence.
      2. Dado material desconhecido para apurar o valor líquido disponível
         (`VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL is DESCONHECIDO`) ->
         `MOBILIZACAO_COM_RESSALVAS` (§14.4.2). Não assume zero.
      3. Valor líquido disponível = 0 -> `MOBILIZACAO_COM_RESSALVAS`
         (§14.4.3) — ativo não gera liquidez imediata, mas a venda ainda
         pode trazer benefício relevante (ex.: redução de custo mensal).
      4. `ESSENCIALIDADE=ESSENCIAL` -> `MOBILIZACAO_COM_RESSALVAS`, NUNCA
         `MOBILIZACAO_RECOMENDAVEL`, em nenhuma combinação de
         `POSSIBILIDADE_VENDA`, incluindo `JA_PRETENDE` (`AC-91`, `EC-34`,
         §14.5 "REGRA CANÔNICA": essencialidade prevalece sobre disposição
         de venda). `POSSIBILIDADE_VENDA=NAO` já foi descartada pelo ramo
         1 — aqui só restam `EXTREMO`/`TALVEZ`/`SIM`/`JA_PRETENDE`, e a
         §14.5 trata todos eles com a MESMA classificação.
      5. `ESSENCIALIDADE em {IMPORTANTE, PARCIAL}` (§14.6):
         `POSSIBILIDADE_VENDA em {EXTREMO,TALVEZ}` ->
         `MOBILIZACAO_COM_RESSALVAS`; `{SIM,JA_PRETENDE}` ->
         `MOBILIZACAO_POSSIVEL`. `POSSIBILIDADE_VENDA=NAO` já bloqueada no
         ramo 1 (`EC-35`) — nunca chega a este ramo por essa via.
      6. `NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA=EXTREMO` ->
         `MOBILIZACAO_COM_RESSALVAS` (§14.7).
      7. `NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA=TALVEZ` ->
         `MOBILIZACAO_POSSIVEL` (§14.7).
      8. `NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA em {SIM,JA_PRETENDE}` ->
         avalia `FLUXO_LIQUIDO_RECORRENTE_ATIVO` (§14.8, §14.9):
           a. `TIPO_ATIVO_FISICO=VEICULO` E `RENDA_RECORRENTE_ATIVO is
              None` -> retorna `None` (RF-56, bloqueio `OQ-38`) — checado
              explicitamente com `is None`, ANTES de qualquer aritmética
              de fluxo, para nunca subtrair `CUSTO_RECORRENTE_ATIVO` de um
              `None` (o que levantaria `TypeError`, não é o comportamento
              desejado).
           b. Fluxo desconhecido (`RENDA_RECORRENTE_ATIVO is None` fora do
              bloqueio de veículo — defensivo, não esperado por contrato
              de `ItemAtivo` — ou `RENDA_RECORRENTE_ATIVO`/
              `CUSTO_RECORRENTE_ATIVO is DESCONHECIDO`) ->
              `MOBILIZACAO_POSSIVEL` (nunca `MOBILIZACAO_RECOMENDAVEL`
              enquanto desconhecido, §14.9).
           c. `FLUXO_LIQUIDO_RECORRENTE_ATIVO <= 0` ->
              `MOBILIZACAO_RECOMENDAVEL` (venda produz liquidez e não
              elimina fluxo recorrente positivo).
           d. `FLUXO_LIQUIDO_RECORRENTE_ATIVO > 0` ->
              `MOBILIZACAO_POSSIVEL` (venda eliminaria fluxo recorrente
              positivo).

    Assinatura de retorno `CLASSIFICACAO_MOBILIZACAO | None`: o `None` é o
    sentinela ESTRUTURAL de "bloqueado por ausência estrutural de
    `RENDA_RECORRENTE_ATIVO` de veículo" (`OQ-38`) — nunca confundido com
    `DESCONHECIDO` do domínio de dado, nunca um valor do domínio de
    `CLASSIFICACAO_MOBILIZACAO`, nunca levantado como exceção. Todo
    CONSUMIDOR desta função (`T-124`) precisa tratar o ramo `None`
    explicitamente — `mypy --strict` recusa ignorá-lo.
    """
    # Ramo 1 (§14.4.1, EC-35) — bloqueio de venda, antes de qualquer outra
    # condição, inclusive dado desconhecido (AC-96).
    if item.POSSIBILIDADE_VENDA == POSSIBILIDADE_VENDA.NAO:
        return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR

    valor_liquido_disponivel = derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
            VALOR_ESTIMADO_ATIVO=item.VALOR_ESTIMADO_ATIVO,
            POSSUI_PASSIVO_VINCULADO=item.POSSUI_PASSIVO_VINCULADO,
            SALDO_PASSIVO_VINCULADO=item.SALDO_PASSIVO_VINCULADO,
            POSSUI_CUSTO_DESMOBILIZACAO=item.POSSUI_CUSTO_DESMOBILIZACAO,
            CUSTOS_ESTIMADOS_DESMOBILIZACAO=item.CUSTOS_ESTIMADOS_DESMOBILIZACAO,
        )
    )

    # Ramo 2 (§14.4.2) — dado material desconhecido, não assume zero.
    if valor_liquido_disponivel is DESCONHECIDO:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    # Ramo 3 (§14.4.3) — valor líquido disponível = 0, sem liquidez imediata.
    elif valor_liquido_disponivel == dinheiro(0):
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    # Ramo 4 (§14.5, REGRA CANÔNICA, AC-91, EC-34) — essencial NUNCA
    # RECOMENDAVEL, em nenhuma combinação de POSSIBILIDADE_VENDA restante.
    elif item.ESSENCIALIDADE == ESSENCIALIDADE.ESSENCIAL:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    # Ramo 5 (§14.6) — importante/parcialmente essencial.
    elif item.ESSENCIALIDADE in {ESSENCIALIDADE.IMPORTANTE, ESSENCIALIDADE.PARCIAL}:
        if item.POSSIBILIDADE_VENDA in {
            POSSIBILIDADE_VENDA.EXTREMO,
            POSSIBILIDADE_VENDA.TALVEZ,
        }:
            return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
        else:
            return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    # Ramo 6 (§14.7) — não essencial, venda extrema.
    elif (
        item.ESSENCIALIDADE == ESSENCIALIDADE.NAO_ESSENCIAL
        and item.POSSIBILIDADE_VENDA == POSSIBILIDADE_VENDA.EXTREMO
    ):
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
    # Ramo 7 (§14.7) — não essencial, venda talvez.
    elif (
        item.ESSENCIALIDADE == ESSENCIALIDADE.NAO_ESSENCIAL
        and item.POSSIBILIDADE_VENDA == POSSIBILIDADE_VENDA.TALVEZ
    ):
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    # Ramo 8 (§14.8, §14.9, RF-55, RF-56) — não essencial, venda aceita.
    elif item.ESSENCIALIDADE == ESSENCIALIDADE.NAO_ESSENCIAL and item.POSSIBILIDADE_VENDA in {
        POSSIBILIDADE_VENDA.SIM,
        POSSIBILIDADE_VENDA.JA_PRETENDE,
    }:
        # Bloqueio de veículo (RF-56, OQ-38): checado com `is None` ANTES de
        # qualquer aritmética de fluxo — nunca subtrai CUSTO_RECORRENTE_ATIVO
        # de um None (levantaria TypeError, não é o comportamento desejado).
        if (
            item.TIPO_ATIVO_FISICO == TIPO_ATIVO_FISICO.VEICULO
            and item.RENDA_RECORRENTE_ATIVO is None
        ):
            return None
        # Fluxo desconhecido (tipo != veículo bloqueado, já descartado
        # acima) OU RENDA_RECORRENTE_ATIVO estruturalmente ausente fora do
        # bloqueio de veículo (não deveria ocorrer por contrato de
        # ItemAtivo, mas a checagem `is None` aqui, ANTES de qualquer
        # aritmética, é o que permite a `mypy --strict` provar que a
        # subtração abaixo nunca opera sobre `None`): nunca
        # MOBILIZACAO_RECOMENDAVEL enquanto desconhecido.
        elif (
            item.RENDA_RECORRENTE_ATIVO is None
            or item.RENDA_RECORRENTE_ATIVO is DESCONHECIDO
            or item.CUSTO_RECORRENTE_ATIVO is DESCONHECIDO
        ):
            return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
        else:
            # A esta altura RENDA_RECORRENTE_ATIVO não é None nem
            # DESCONHECIDO, e CUSTO_RECORRENTE_ATIVO não é DESCONHECIDO —
            # a subtração é segura (§14.8).
            fluxo_liquido_recorrente = (
                item.RENDA_RECORRENTE_ATIVO - item.CUSTO_RECORRENTE_ATIVO
            )
            if fluxo_liquido_recorrente <= dinheiro(0):
                return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
            else:
                return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    # Fallback final de §14.14 — nenhuma combinação normativa deveria
    # alcançar este ponto (os oito ramos acima cobrem o produto cartesiano
    # de ESSENCIALIDADE × POSSIBILIDADE_VENDA restante após o ramo 1).
    else:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
