"""Ataque imediato e reserva — §13 da spec do slug (documento canônico
PIQ v1.0.1, congelado em 2026-09-07) · RF-43, RF-49.

Fonte normativa: `specs/motor-calculo.spec.md` §13 ("Definições incorporadas
— Rodada 3"), cuja regra de precedência transcrita é explícita: para os temas
tratados naquela seção, estas definições prevalecem sobre qualquer redação
anterior. "Nenhuma dessas decisões fica a critério do desenvolvedor."

TODA função deste módulo é PURA no sentido forte da NFR "Pureza (Rodada 3)"
(spec §5): recebe todas as suas entradas por parâmetro, não consulta
`EstadoFinanceiro`, não consulta `Diagnostico`, não lê relógio, arquivo nem
variável global. É essa propriedade — e não uma fórmula adivinhada — que
torna `GAB-AI-01` a `GAB-AI-07` verificáveis com `OQ-26` e `OQ-29` ainda
abertas. Por isso toda assinatura começa com `*`: chamada posicional é
recusada em tempo de checagem estática, e a origem de cada entrada fica
legível no ponto de chamada.

**Zero parâmetro calibrável.** Nenhuma fórmula da §13 usa um `P_*` da seção 8
da canônica — não há limiar, percentual nem piso ajustável em `MIN`, `MAX` ou
soma. Este módulo, portanto, não recebe `Parametros` em nenhuma assinatura, e
essa ausência é normativa, não esquecimento (`sdd.config.md` §4, "Zero
parâmetro no código").

Escopo deste arquivo hoje (`T-102`..`T-107`): `RESERVA_MOBILIZAVEL` (§13.1),
`ATAQUE_IMEDIATO_POTENCIAL` (§13.2), os QUATRO componentes não protetivos da
§13.3 — ordens 1 a 4 da §13.7 —, `NECESSIDADE_RESIDUAL` e
`RESERVA_RECOMENDADA` (§13.4, ordem 5), `ATAQUE_IMEDIATO_RECOMENDADO`
(§13.3/§13.5) e a parte da hierarquia da §13.6 verificável sem a fatia 3C.
`REGRAS` abaixo cita só o que este arquivo já implementa: `ATAQUE_IMEDIATO_APROVADO`
e o ramo `>= APROVADO >= 0` da §13.6 dependem de confirmação do usuário
(`OQ-30`, fatia 3C) e **não** existem aqui — nem a variável, nem parâmetro,
nem menção em código executável.

**Potencial (§13.2) × recomendado (§13.3) — a distinção que este módulo
sustenta.** `MOBILIZACAO_POSSIVEL` compõe o POTENCIAL e **não** compõe o
RECOMENDADO; só `MOBILIZACAO_RECOMENDAVEL` compõe os dois. Nenhum dos dois
admite `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR`: as ressalvas não são
resolvidas automaticamente pelo motor (`EC-30`). Confundir as duas listas é o
erro que `AC-77` e `AC-78` existem para pegar.

REGRAS: Final[tuple[str, ...]] = ("RF-43", "RF-44", "RF-45", "RF-46", "RF-47",
                                  "RF-48", "RF-49", "RF-50", "§13.1", "§13.2",
                                  "§13.3", "§13.4", "§13.5", "§13.6", "§13.7",
                                  "§13.9")
"""

from __future__ import annotations

from typing import Final

from engine.ciclo_mensal import ErroInvariante
from engine.classificacao_ativos import (
    classificar_ativo_fisico,
    classificar_investimento,
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO,
    derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL,
)
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    DISPOSICAO_USO_RESERVA,
    JANELA_RECURSO_EXTRAORDINARIO,
    RESERVA_EXISTE,
    ItemAtivo,
    ItemInvestimento,
    RecursoExtraordinario,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO, Dinheiro, DinheiroTalvez

# Aliases dos dois enums. A assinatura do plano R3.4.5 dá ao PARÂMETRO o
# mesmo nome canônico da CLASSE (`RESERVA_EXISTE: RESERVA_EXISTE`) — exigência
# do `sdd.config.md` §7 (o nome no código é o nome na spec, caractere por
# caractere). Dentro do corpo, esse nome passa a designar o valor recebido, e
# os membros do domínio (`.NAO`) precisam ser alcançados por outro caminho:
# ler `.NAO` a partir da instância funciona no CPython 3.12 mas é acesso
# depreciado a membro por instância, ilegível e sem garantia futura. Os
# aliases resolvem sem tocar na assinatura nem renomear parâmetro.
_RESERVA_EXISTE = RESERVA_EXISTE
_DISPOSICAO_USO_RESERVA = DISPOSICAO_USO_RESERVA

# `CLASSIFICACAO_MOBILIZACAO` não é nome de parâmetro em nenhuma assinatura
# deste módulo (a classificação chega DENTRO de cada item), então não há
# colisão a resolver — o alias abaixo existe só por simetria de leitura com os
# dois de cima e para encurtar as comparações de classe no corpo das funções.
_CLASSIFICACAO = CLASSIFICACAO_MOBILIZACAO

# §13.2 — as DUAS classes que compõem o POTENCIAL, "MOBILIZACAO_POSSIVEL OU
# MOBILIZACAO_RECOMENDAVEL" (`AC-77`). As outras duas não entram nem aqui
# (`EC-30`): o potencial já é filtrado, não é "tudo que existe".
_CLASSES_MOBILIZAVEIS_POTENCIAL: Final[frozenset[CLASSIFICACAO_MOBILIZACAO]] = frozenset(
    {_CLASSIFICACAO.MOBILIZACAO_POSSIVEL, _CLASSIFICACAO.MOBILIZACAO_RECOMENDAVEL}
)


REGRAS: Final[tuple[str, ...]] = (
    "RF-43",
    "RF-44",
    "RF-45",
    "RF-46",
    "RF-47",
    "RF-48",
    "RF-49",
    "RF-50",
    "§13.1",
    "§13.2",
    "§13.3",
    "§13.4",
    "§13.5",
    "§13.6",
    "§13.7",
    "§13.9",
)


def _valor_liquido_realizavel_ativo_disponivel(item: ItemAtivo) -> DinheiroTalvez:
    """`T-124` (`RF-53`, `RF-59`) — `ItemAtivo.VALOR_LIQUIDO_REALIZAVEL_ATIVO_
    DISPONIVEL` (Rodada 3) deixou de ser campo de entrada (`T-121`, §14.12):
    passa a ser DERIVADO chamando as duas funções de `engine/classificacao_
    ativos.py` sobre os campos brutos do item, na mesma composição que
    `classificar_ativo_fisico` já usa internamente para os ramos 2/3 (§14.4.2,
    §14.4.3). Devolve `DinheiroTalvez`: propaga `DESCONHECIDO` sem forçar
    zero (`RF-58`) — quem soma decide o que fazer com o desconhecido.
    """
    return derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
        VALOR_LIQUIDO_REALIZAVEL_ATIVO=derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
            VALOR_ESTIMADO_ATIVO=item.VALOR_ESTIMADO_ATIVO,
            POSSUI_PASSIVO_VINCULADO=item.POSSUI_PASSIVO_VINCULADO,
            SALDO_PASSIVO_VINCULADO=item.SALDO_PASSIVO_VINCULADO,
            POSSUI_CUSTO_DESMOBILIZACAO=item.POSSUI_CUSTO_DESMOBILIZACAO,
            CUSTOS_ESTIMADOS_DESMOBILIZACAO=item.CUSTOS_ESTIMADOS_DESMOBILIZACAO,
        )
    )


def derivar_RESERVA_MOBILIZAVEL(
    *,
    # Os quatro nomes são os nomes canônicos da §13.1, em maiúsculas, caractere
    # por caractere (`sdd.config.md` §7) — são variáveis da spec, não parâmetros
    # inventados aqui. O `*` inicial força chamada por argumento nomeado.
    RESERVA_EXISTE: RESERVA_EXISTE,
    DISPOSICAO_USO_RESERVA: DISPOSICAO_USO_RESERVA,
    RESERVA_TOTAL: DinheiroTalvez,
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez,
) -> DinheiroTalvez:
    """RF-43 · §13.1 · §13.9 `deriveReservaMobilizavel`.

    `RESERVA_MOBILIZAVEL` NÃO é percentual calculado pelo motor: é o valor
    máximo da reserva que o usuário aceita submeter à análise, declarado no
    Bloco 4 — "o motor apenas valida e limita" (§13.1). Esta função é essa
    validação e esse limite, nada mais.

    As três regras da §13.1 aplicadas NA ORDEM REGISTRADA, na mesma sequência
    de guardas do pseudocódigo da §13.9:

      Regra 1 vence Regra 2 (EC-23): `RESERVA_EXISTE = NAO` ou
              `DISPOSICAO_USO_RESERVA = NAO` -> `dinheiro(0)`, ignorando o
              valor informado — nunca somando-o, mesmo que ele esteja
              preenchido (entrada inconsistente). Vem antes até do teste de
              desconhecido: sem reserva ou sem disposição, o total é
              irrelevante e o resultado é `0`, não `DESCONHECIDO`.
      Regra 3 vence Regra 2 (EC-25, AC-73): `RESERVA_TOTAL` desconhecida ou
              `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` desconhecido ->
              `DESCONHECIDO`. Nunca `0`: o estado desconhecido "não é
              convertido silenciosamente em zero como informação" (§13.1) —
              zero seria uma decisão que o usuário não tomou. Quem consome
              registra a pendência (`EC-26`, `T-105`).
      Regra 2: `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO...))` — o `MAX(0, ...)`
              zera valor negativo ANTES do `MIN` (EC-24), então o resultado
              nunca é negativo; e o `MIN` garante que o informado jamais
              ultrapasse o total (AC-71, `GAB-AI-02`).

    TRAVA CANÔNICA (§13.1, RF-49): NUNCA percentual automático de
    `RESERVA_TOTAL`. As três formas expressamente proibidas na v1.0.1 —
    `30% x RESERVA_TOTAL`, `50% x RESERVA_TOTAL` e
    `RESERVA_TOTAL - RESERVA_MINIMA_PADRAO` — não existem em lugar nenhum
    deste módulo, em nenhuma forma (AC-81; prova estática em `T-113`).
    `RESERVA_TOTAL` só aparece abaixo como o TETO de um `min`, jamais como
    operando de multiplicação ou de subtração.

    Pureza (spec §5): as quatro entradas chegam por parâmetro; nada é lido de
    `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou global.
    """
    # Regra 1 (§13.1) — ausência de reserva ou de disposição de uso. Avaliada
    # PRIMEIRO: vence a Regra 2 (EC-23) e também a Regra 3, exatamente como
    # as duas primeiras guardas de `deriveReservaMobilizavel` (§13.9).
    if RESERVA_EXISTE is _RESERVA_EXISTE.NAO:
        return dinheiro(0)
    if DISPOSICAO_USO_RESERVA is _DISPOSICAO_USO_RESERVA.NAO:
        return dinheiro(0)

    # Regra 3 (§13.1) — decisão adiada, "não sei" ou reserva total
    # desconhecida. Avaliada ANTES da aritmética: vence a Regra 2 (EC-25) e
    # devolve o estado desconhecido, nunca `0` (AC-73).
    if RESERVA_TOTAL is DESCONHECIDO:
        return DESCONHECIDO
    if VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO:
        return DESCONHECIDO

    # Regra 2 (§13.1) — valor numérico conhecido em B4.03A:
    # MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO)).
    # O MAX(0, ...) zera o negativo ANTES do MIN (EC-24) — invertê-los faria
    # um total menor que zero vazar para o resultado.
    informado_nao_negativo = max(dinheiro(0), VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO)
    return min(RESERVA_TOTAL, informado_nao_negativo)


def calcular_ATAQUE_IMEDIATO_POTENCIAL(
    *,
    # Os dois primeiros nomes são os nomes canônicos da §13.2, em maiúsculas
    # (`sdd.config.md` §7); as três coleções usam o nome dos campos de
    # `EstadoFinanceiro` que as alimentam (plano R3.4.5).
    DINHEIRO_DISPONIVEL: Dinheiro,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,
    investimentos: tuple[ItemInvestimento, ...],
    recursos_extraordinarios: tuple[RecursoExtraordinario, ...],
    ativos: tuple[ItemAtivo, ...],
) -> Dinheiro:
    """RF-44 · §13.2 — soma das CINCO parcelas, na ordem em que a §13.2 as
    escreve: `DINHEIRO_DISPONIVEL` + `RESERVA_MOBILIZAVEL` +
    `INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS` + `RECURSOS_EXTRAORDINARIOS_POTENCIAIS`
    + ativos líquidos `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL`.

    É **apenas potencial** (§13.2): não entra no cronograma, não é recomendação,
    não é aprovação, e não significa que todos os recursos devam ser utilizados
    (§13.6, §13.11 — coluna "Entra no cronograma?" = NÃO).

    **Quem entra em cada parcela, transcrito:**

      - Investimentos: os "líquidos mobilizáveis". As DUAS condições vêm da
        letra da parcela — `POSSUI_LIQUIDEZ` (líquidos) e classificação em
        {`MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`} (mobilizáveis).
        `AC-77` é explícito e vale para ITEM, não só para ativo: "nenhum item
        `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra na soma".
      - Recursos extraordinários: os "potenciais" — TODOS os itens da coleção.
        A §13.2 não lhes impõe filtro nenhum, e é justamente por isso que
        `AC-79` pode dizer que o recurso futuro e não confirmado "não compõe
        `EXTRAORDINARIOS_RECOMENDADOS` **ainda que componha**
        `RECURSOS_EXTRAORDINARIOS_POTENCIAIS`". Filtrar aqui por
        janela/certeza apagaria essa diferença e tornaria `AC-79` vazio.
      - Ativos: `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL`
        (`AC-77`). `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` NÃO entram
        nem aqui, por mais alto que seja o valor líquido (`EC-30`) — as
        ressalvas não são resolvidas automaticamente pelo motor.

    **`RESERVA_MOBILIZAVEL` desconhecida contribui `0` para a soma** — e
    apenas para a soma. A §13.1 é explícita: "nenhum valor da reserva entra
    numericamente no recomendado ou aprovado até existir decisão válida". É
    contribuição ARITMÉTICA, nunca conversão de informação: o `DESCONHECIDO`
    original continua legível na saída, porque quem o carrega é
    `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`), e a pendência
    permanece registrada ali (plano R3.8, `EC-26`). Esta função devolve
    `Dinheiro`, nunca `DinheiroTalvez`: fabricar um desconhecido de saída a
    partir de uma parcela desconhecida contrariaria `EC-27` e deixaria o
    potencial inexprimível sempre que a decisão de reserva fosse adiada.

    `ECONOMIA_POTENCIAL_IMEDIATA` NÃO entra nesta soma, e não é parâmetro:
    `OQ-31` (relação entre ela e o potencial) está **aberta** e a §13.2 não a
    menciona (spec §9). Incluí-la seria decidir metodologia no código.

    `EC-27`: coleções vazias com `DINHEIRO_DISPONIVEL = 0` devolvem
    `dinheiro(0)` — nenhum erro, nenhum desconhecido fabricado.

    Pureza (spec §5): as cinco entradas chegam por parâmetro; nada é lido de
    `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou global.
    """
    total = DINHEIRO_DISPONIVEL

    # Parcela 2 — a reserva. `is DESCONHECIDO`, nunca "é falsy": `dinheiro(0)`
    # é valor legítimo e soma normalmente (mesmo padrão de `_somar_pagamentos`,
    # `engine/diagnostico.py`).
    if RESERVA_MOBILIZAVEL is not DESCONHECIDO:
        total += RESERVA_MOBILIZAVEL

    # Parcela 3 — INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS (§13.2). `T-124`:
    # classificação chega DERIVADA de `classificar_investimento(item)`
    # (`RF-59`), nunca mais lida de `item.CLASSIFICACAO_MOBILIZACAO`.
    for investimento in investimentos:
        classificacao_investimento = classificar_investimento(investimento)
        if (
            investimento.POSSUI_LIQUIDEZ
            and classificacao_investimento in _CLASSES_MOBILIZAVEIS_POTENCIAL
        ):
            total += investimento.VALOR_LIQUIDO_REALIZAVEL

    # Parcela 4 — RECURSOS_EXTRAORDINARIOS_POTENCIAIS (§13.2): sem filtro de
    # janela nem de certeza. O filtro é da §13.3, e vive em
    # `calcular_EXTRAORDINARIOS_RECOMENDADOS` (`AC-79`).
    for recurso in recursos_extraordinarios:
        total += recurso.VALOR_RECURSO_EXTRAORDINARIO

    # Parcela 5 — ativos MOBILIZACAO_POSSIVEL OU MOBILIZACAO_RECOMENDAVEL
    # (`AC-77`); as outras duas classes não entram (`EC-30`). `T-124`:
    # classificação chega DERIVADA de `classificar_ativo_fisico(item)`
    # (`RF-59`); `None` (bloqueio de veículo, `RF-56`) é tratado como "não
    # soma, não erro" — mesma disciplina de filtro das outras classes que
    # não mobilizam (plano R4.5, passo 4). O `is None` vem PRIMEIRO no `and`
    # para que o `mypy --strict` faça o narrowing antes de qualquer uso do
    # valor como `CLASSIFICACAO_MOBILIZACAO` puro.
    for ativo in ativos:
        classificacao_ativo = classificar_ativo_fisico(ativo)
        if (
            classificacao_ativo is not None
            and classificacao_ativo in _CLASSES_MOBILIZAVEIS_POTENCIAL
        ):
            valor_liquido_disponivel = _valor_liquido_realizavel_ativo_disponivel(ativo)
            # Estruturalmente inalcançável com valor DESCONHECIDO: se o valor
            # líquido fosse desconhecido, `classificar_ativo_fisico` teria
            # retornado MOBILIZACAO_COM_RESSALVAS (§14.4.2), fora do filtro
            # acima. `is not DESCONHECIDO` explícito é o que permite ao
            # `mypy --strict` provar a soma sem erro de tipo `Dinheiro`/
            # `Desconhecido` neste ponto (mesma disciplina de `RESERVA_
            # MOBILIZAVEL`, parcela 2 acima).
            if valor_liquido_disponivel is not DESCONHECIDO:
                total += valor_liquido_disponivel

    return total


def calcular_CAIXA_RECOMENDADO(*, DINHEIRO_DISPONIVEL: Dinheiro) -> Dinheiro:
    """RF-45 · RF-37 · §13.3 — `CAIXA_RECOMENDADO = DINHEIRO_DISPONIVEL`.
    §13.7, **ordem 1**: "usar se realmente livre e não comprometido".

    Identidade, não cálculo — e a ausência de cálculo é a norma, não uma
    simplificação. A qualificação da §13.3 ("realmente livre, não
    correspondente a obrigação já contabilizada, não comprometido com despesa
    conhecida e não contado em outra variável") é garantia de COLETA: `B4.01`
    já a impõe no enunciado, `RF-37`/`AC-63` fixam que o motor consome o valor
    **sem revalidá-lo**, e `OQ-28` ("quem valida livre/não comprometido?")
    segue **aberta**, encaminhada como garantia de coleta. Revalidar aqui
    seria decidir `OQ-28` no código; se o especialista decidir que cabe
    validação no motor, ela é acréscimo a esta função, não reescrita dela.

    A função existe para dar NOME NORMATIVO à parcela — para que a ordem de
    utilização da §13.7 e a soma da §13.3 sejam legíveis no código com os
    nomes da spec — e é também o que impede a dupla contagem da §13.8
    ("dinheiro de venda de ativo contado como ativo e como dinheiro"):
    `CAIXA_RECOMENDADO` é escalar de origem econômica única, nunca derivado de
    item de coleção (plano R3.5, `AC-83`).

    Pureza (spec §5): a única entrada chega por parâmetro.
    """
    return DINHEIRO_DISPONIVEL


def calcular_INVESTIMENTOS_RECOMENDADOS(
    *, investimentos: tuple[ItemInvestimento, ...]
) -> Dinheiro:
    """RF-45 · §13.3 — soma do `VALOR_LIQUIDO_REALIZAVEL` dos investimentos
    **com liquidez** E classificados `MOBILIZACAO_RECOMENDAVEL`. §13.7,
    **ordem 2**: "somente líquidos e classificados como recomendáveis".

    As DUAS condições, conjuntas — a §13.3 escreve "com liquidez **E**
    classificados `MOBILIZACAO_RECOMENDAVEL`". Investimento recomendável mas
    sem liquidez não entra; investimento líquido mas apenas
    `MOBILIZACAO_POSSIVEL` também não: "apenas `MOBILIZACAO_POSSIVEL` fica no
    potencial, não entra automaticamente no recomendado" (§13.3, `AC-78`) —
    ele continua contando em `ATAQUE_IMEDIATO_POTENCIAL` (§13.2), e é essa
    diferença entre as duas somas que a §13.6 chama de hierarquia.
    `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` não entram em nenhuma das
    duas (`EC-30`).

    `EC-27`: coleção vazia devolve `dinheiro(0)` — nenhum erro, nenhum
    desconhecido fabricado. Não há ramo de `DESCONHECIDO` a tratar:
    `ItemInvestimento.VALOR_LIQUIDO_REALIZAVEL` é `Dinheiro` puro, já apurado
    na entrada (`RF-38`, `OQ-27` aberta). `T-124`, `RF-59`: a classificação
    não é mais campo do item — é DERIVADA por `classificar_investimento(item)`
    a cada chamada, sempre um dos quatro valores do domínio, nunca omitida
    por default (`OQ-26` aberta, `AC-67`).

    Pureza (spec §5): a única entrada chega por parâmetro.
    """
    total = dinheiro(0)
    # `T-124`: classificação chega DERIVADA de `classificar_investimento(item)`
    # (`RF-59`), nunca mais lida de `item.CLASSIFICACAO_MOBILIZACAO`.
    for investimento in investimentos:
        classificacao_investimento = classificar_investimento(investimento)
        if (
            investimento.POSSUI_LIQUIDEZ
            and classificacao_investimento is _CLASSIFICACAO.MOBILIZACAO_RECOMENDAVEL
        ):
            total += investimento.VALOR_LIQUIDO_REALIZAVEL
    return total


def calcular_EXTRAORDINARIOS_RECOMENDADOS(
    *, recursos_extraordinarios: tuple[RecursoExtraordinario, ...]
) -> Dinheiro:
    """RF-45 · §13.3 — soma do `VALOR_RECURSO_EXTRAORDINARIO` dos recursos
    "confirmados, disponíveis, não comprometidos e aptos **no momento
    atual**". §13.7, **ordem 3**: "somente confirmados e disponíveis".

    As duas condições, conjuntas, decidíveis POR ITEM e sem consultar nenhum
    outro campo (`AC-65`, `engine/estado.py`):

      confirmado    = `CERTEZA_RECURSO_EXTRAORDINARIO is CONFIRMADO`
      momento atual = `JANELA_RECURSO_EXTRAORDINARIO is ATE_30D`

    `CONFIRMADO` é o único membro do domínio que satisfaz "confirmado";
    `ATE_30D` é a única janela do "momento atual" — as demais (`1_3M`,
    `4_6M`, `7_12M`, `NAO_SEI`) são futuro ou incerteza. "Recurso apenas
    previsto para o futuro não compõe o recomendado atual" (§13.3): ele
    continua compondo `RECURSOS_EXTRAORDINARIOS_POTENCIAIS` na §13.2, e é
    exatamente esse contraste que `AC-79` verifica.

    `EC-27`: coleção vazia devolve `dinheiro(0)`.

    Pureza (spec §5): a única entrada chega por parâmetro.
    """
    total = dinheiro(0)
    for recurso in recursos_extraordinarios:
        if (
            recurso.CERTEZA_RECURSO_EXTRAORDINARIO is CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO
            and recurso.JANELA_RECURSO_EXTRAORDINARIO is JANELA_RECURSO_EXTRAORDINARIO.ATE_30D
        ):
            total += recurso.VALOR_RECURSO_EXTRAORDINARIO
    return total


def calcular_ATIVOS_RECOMENDADOS(*, ativos: tuple[ItemAtivo, ...]) -> Dinheiro:
    """RF-45 · §13.3 — `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` dos
    ativos `MOBILIZACAO_RECOMENDAVEL`. §13.7, **ordem 4**: "somente
    `MOBILIZACAO_RECOMENDAVEL`".

    UMA condição, não duas: não há `POSSUI_LIQUIDEZ` em `ItemAtivo`, porque
    "com liquidez" é exigência que a §13.3 impõe apenas a
    `INVESTIMENTOS_RECOMENDADOS`; `ATIVOS_RECOMENDADOS` qualifica-se só pela
    classificação (`engine/estado.py`, `ItemAtivo`).

    `MOBILIZACAO_POSSIVEL` fica **só no potencial** (`AC-78`): o ativo
    possível continua somando em `ATAQUE_IMEDIATO_POTENCIAL` (§13.2) e não
    entra aqui. `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` "não entram
    automaticamente" (§13.3, `AC-78`, `EC-30`) — e "automaticamente" é a
    palavra da norma: o que os traria para dentro é decisão humana sobre a
    ressalva, jamais uma regra deste módulo. Não existe aqui, e não deve
    existir enquanto `OQ-26` estiver aberta, nenhum ramo que promova uma
    classe a outra (`AC-67`).

    `EC-27`: coleção vazia devolve `dinheiro(0)`.

    Pureza (spec §5): a única entrada chega por parâmetro.
    """
    total = dinheiro(0)
    # `T-124`: classificação chega DERIVADA de `classificar_ativo_fisico(item)`
    # (`RF-59`); `None` (bloqueio de veículo, `RF-56`) é tratado como "não
    # soma, não erro" — o item simplesmente não é `MOBILIZACAO_RECOMENDAVEL`
    # (plano R4.5, passo 4). `is` contra o enum funciona mesmo com `None` de
    # um lado (comparação de identidade aceita qualquer tipo, não é "uso"
    # do valor como `CLASSIFICACAO_MOBILIZACAO` puro) — o que `mypy --strict`
    # exigiria narrowing explícito é USAR o valor como se fosse garantidamente
    # o enum (ex.: passá-lo para algo tipado só `CLASSIFICACAO_MOBILIZACAO`),
    # não compará-lo.
    for ativo in ativos:
        classificacao_ativo = classificar_ativo_fisico(ativo)
        if classificacao_ativo is _CLASSIFICACAO.MOBILIZACAO_RECOMENDAVEL:
            valor_liquido_disponivel = _valor_liquido_realizavel_ativo_disponivel(ativo)
            # Estruturalmente inalcançável com valor DESCONHECIDO: ver
            # `calcular_ATAQUE_IMEDIATO_POTENCIAL` acima, mesma disciplina.
            if valor_liquido_disponivel is not DESCONHECIDO:
                total += valor_liquido_disponivel
    return total


def calcular_NECESSIDADE_RESIDUAL(
    *,
    # `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` entra POR PARÂMETRO (RF-48):
    # sua fórmula não existe na §13 — `OQ-29` está aberta com o especialista —
    # e é exatamente por chegar pronta de fora que esta função é escrevível e
    # verificável hoje. Derivá-la aqui seria inventar metodologia.
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: Dinheiro,
    CAIXA_RECOMENDADO: Dinheiro,
    INVESTIMENTOS_RECOMENDADOS: Dinheiro,
    EXTRAORDINARIOS_RECOMENDADOS: Dinheiro,
    ATIVOS_RECOMENDADOS: Dinheiro,
) -> Dinheiro:
    """RF-46 · RF-48 · §13.4 · §13.9 `deriveReservaRecomendada` (primeira
    metade) — `MAX(0, elegível − os QUATRO não protetivos)`.

    Quanto da necessidade elegível **sobra** depois de esgotados os recursos
    não protetivos recomendáveis (§13.7, ordens 1 a 4). É o teto que a §13.4
    impõe à reserva, e a razão de a reserva ser o ÚLTIMO componente: recurso
    protetivo só é considerado "depois dos recursos não protetivos
    recomendáveis" (§13.4).

    O `MAX(0, ...)` é a regra, não uma defesa: quando os não protetivos já
    cobrem a necessidade, o residual é `0` e a reserva não é mobilizada
    (`EC-29`). A subtração nunca vaza negativo para quem consome — um residual
    negativo, propagado, viraria um `MIN` que devolveria número negativo em
    `derivar_RESERVA_RECOMENDADA` e quebraria a hierarquia da §13.6.

    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` chega POR PARÂMETRO (`RF-48`,
    `AC-80`) e não é derivada aqui: a §13.5 a define em prosa ("valor máximo
    que faz sentido aplicar imediatamente, considerando o estado do plano após
    os gates") mas não publica fórmula, e `OQ-29` segue **aberta**. Esta
    função não a busca em `EstadoFinanceiro` nem em `Diagnostico`.

    Pureza (spec §5): as cinco entradas chegam por parâmetro; nada é lido de
    `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou global.
    """
    # A ordem das quatro subtrações é a da §13.4, que é a ordem de utilização
    # da §13.7 (caixa → investimentos → extraordinários → ativos). Em Decimal
    # a soma é exata, então a ordem não muda o número — ela mantém o código
    # legível contra o pseudocódigo, que é o que a §13.9 exige.
    residual = (
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL
        - CAIXA_RECOMENDADO
        - INVESTIMENTOS_RECOMENDADOS
        - EXTRAORDINARIOS_RECOMENDADOS
        - ATIVOS_RECOMENDADOS
    )
    return max(dinheiro(0), residual)


def derivar_RESERVA_RECOMENDADA(
    *,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,
    NECESSIDADE_RESIDUAL: Dinheiro,
    # RF-48: POR PARÂMETRO, nunca de `Diagnostico` — ver a TRAVA na docstring.
    RESULTADO_MENSAL_ATUAL: Dinheiro,
) -> Dinheiro:
    """RF-46 · RF-48 · §13.4 · §13.9 `deriveReservaRecomendada` — a reserva é
    o ÚLTIMO componente (§13.7, **ordem 5**), "apenas necessidade residual e
    se estrategicamente justificado".

    **TRAVA — MODO ESTABILIZAÇÃO (§13.4).** Se `RESULTADO_MENSAL_ATUAL < 0`,
    então `RESERVA_RECOMENDADA = 0`, ponto — sem `MIN`, sem residual, por mais
    alta que seja a reserva mobilizável (`AC-74`, `GAB-AI-05`). A norma é
    literal: "a reserva não pode ser usada para mascarar déficit estrutural".
    Quem está gastando mais do que ganha todo mês não tem problema de caixa
    pontual a resolver com reserva; tem déficit a estabilizar primeiro.

    `RESULTADO_MENSAL_ATUAL` chega POR PARÂMETRO e a trava é avaliada AQUI,
    sobre o valor recebido. `Diagnostico.MODO_ESTABILIZACAO` deriva da MESMA
    condição de déficit (`engine/diagnostico.py`, §11 da spec) e é o campo que
    o teste de `AC-74` lê para confirmar `MODO_ESTABILIZACAO = SIM` — mas esta
    função **não o consulta**, porque consultá-lo quebraria a NFR de Pureza
    (spec §5) e amarraria a §13.4 a um objeto de estado que ela não menciona.
    A condição é uma só, escrita em dois lugares por design; se um dia
    divergirem, é bug de derivação, não de leitura.

    `RESERVA_MOBILIZAVEL` desconhecida devolve `0` — "0 até decisão válida"
    (§13.9, `EC-26`). NÃO é conversão silenciosa do desconhecido em zero como
    informação: é a §13.1 aplicada ("nenhum valor da reserva entra
    numericamente no recomendado ou aprovado até existir decisão válida",
    `AC-73`). A pendência continua registrada e legível onde a spec manda que
    ela fique — `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`,
    plano R3.8) —, e é de lá que o relatório a lê. O retorno desta função é
    `Dinheiro`, nunca `DinheiroTalvez`: a §13.9 devolve `0`, não
    `DESCONHECIDA`, e é o que sustenta `ATAQUE_IMEDIATO_RECOMENDADO` ser
    sempre numérico (plano R3.4.6).

    Nos demais casos: `MIN(RESERVA_MOBILIZAVEL, NECESSIDADE_RESIDUAL)` — a
    reserva nunca excede o que sobrou por cobrir (§13.4), nem o que o usuário
    aceitou submeter à análise (§13.1).

    **ORDEM DE AVALIAÇÃO (§13.9, "o resultado lógico não pode variar").**
    Trava do déficit PRIMEIRO — vence tudo, inclusive o desconhecido: com
    `RESULTADO_MENSAL_ATUAL < 0` o resultado é `0` sem sequer olhar a reserva.
    Depois a guarda de desconhecido, também devolvendo `0`. Só então o `MIN`.
    O pseudocódigo calcula `necessidadeResidual` entre as duas guardas, mas
    esse cálculo é aqui insumo do chamador (`calcular_NECESSIDADE_RESIDUAL`) e
    nenhum dos dois ramos anteriores o consome — o RESULTADO LÓGICO é
    idêntico, que é o que a nota de implementação da §13.9 exige.

    **REGRA CANÔNICA (§13.4), que esta função não viola nem supre.** "A
    existência de `RESERVA_MOBILIZAVEL`, isoladamente, nunca é justificativa
    suficiente para recomendar sua utilização" — exige finalidade concreta e
    justificável, tendo passado pelos gates aplicáveis. Este `MIN` é o TETO
    aritmético dessa recomendação, não a justificativa dela: a finalidade vem
    da `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` que entrou no residual, que
    por definição da §13.5 já é "o estado do plano APÓS os gates".

    Pureza (spec §5): as três entradas chegam por parâmetro; nada é lido de
    `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou global.
    """
    # TRAVA MODO_ESTABILIZACAO (§13.4) — primeira guarda de
    # `deriveReservaRecomendada` (§13.9). Estrito (`< 0`): resultado mensal
    # exatamente zero NÃO é déficit e não aciona a trava.
    if RESULTADO_MENSAL_ATUAL < dinheiro(0):
        return dinheiro(0)

    # Decisão de reserva adiada / desconhecida (§13.1 Regra 3, `EC-26`) —
    # `0` "até decisão válida" (§13.9). `is DESCONHECIDO`, nunca "é falsy":
    # `dinheiro(0)` conhecido é decisão válida e segue para o `MIN` abaixo.
    if RESERVA_MOBILIZAVEL is DESCONHECIDO:
        return dinheiro(0)

    # Demais casos (§13.4): MIN(RESERVA_MOBILIZAVEL, NECESSIDADE_RESIDUAL).
    return min(RESERVA_MOBILIZAVEL, NECESSIDADE_RESIDUAL)


def calcular_ATAQUE_IMEDIATO_RECOMENDADO(
    *,
    # Seis parâmetros do MESMO tipo `Dinheiro`. O `*` não é estilo: em chamada
    # posicional, trocar elegível por caixa seria erro silencioso que nenhum
    # tipo pega e que os `GAB-AI` só detectariam por sorte (plano R3.4.5).
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: Dinheiro,  # RF-48: POR PARÂMETRO
    CAIXA_RECOMENDADO: Dinheiro,
    INVESTIMENTOS_RECOMENDADOS: Dinheiro,
    EXTRAORDINARIOS_RECOMENDADOS: Dinheiro,
    ATIVOS_RECOMENDADOS: Dinheiro,
    RESERVA_RECOMENDADA: Dinheiro,
) -> Dinheiro:
    """RF-47 · RF-48 · §13.3 · §13.5 · §13.9 `deriveAtaqueImediatoRecomendado`
    — `MIN(elegível, soma dos CINCO componentes recomendados)`.

    Os cinco componentes são os da §13.3, somados na ordem de utilização da
    §13.7 (1 caixa → 2 investimentos → 3 extraordinários → 4 ativos →
    5 reserva). O `MIN` contra a necessidade elegível é a §13.5 escrita como
    código: `ATAQUE_IMEDIATO_RECOMENDADO <= NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`.

    **"Nunca recomendar recurso sem destinação financeira elegível" (§13.5).**
    Por isso o elegível é TETO e não parcela: com elegível `= 0`, o resultado é
    `dinheiro(0)` mesmo com recursos recomendáveis altos (`EC-28`) — ter
    dinheiro mobilizável não é razão para mobilizá-lo. E com elegível de
    10.000 contra 25.000 de recursos, o resultado é 10.000, não 25.000
    (`AC-76`, `GAB-AI-07`).

    `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` chega POR ARGUMENTO EXPLÍCITO
    (`RF-48`, `AC-80`): esta função **não** a busca em `EstadoFinanceiro` nem
    em `Diagnostico`, e não a deriva — a §13.5 não publica fórmula e `OQ-29`
    está **aberta**. É o que torna esta função verificável hoje.

    Devolve `Dinheiro`, nunca `DinheiroTalvez`: não há caminho da §13 em que o
    recomendado seja desconhecido, porque a parcela desconhecida da reserva já
    entrou como `0` em `derivar_RESERVA_RECOMENDADA` (§13.9, plano R3.4.6).
    `AC-73` exige apenas que NENHUM valor da reserva entre nele, o que é
    satisfeito com `RESERVA_RECOMENDADA = 0`.

    Este valor **não entra no cronograma** (§13.6, §13.11): "o motor considera
    estrategicamente adequado" ainda não é "o usuário confirmou". Só
    `ATAQUE_IMEDIATO_APROVADO` entra, e ele não existe nesta rodada (`OQ-30`).

    Função pura (spec §5, NFR "Pureza"): as seis entradas chegam por
    parâmetro; nada é lido de `EstadoFinanceiro`, `Diagnostico`, relógio,
    arquivo ou global.
    """
    recursos_recomendados = (
        CAIXA_RECOMENDADO
        + INVESTIMENTOS_RECOMENDADOS
        + EXTRAORDINARIOS_RECOMENDADOS
        + ATIVOS_RECOMENDADOS
        + RESERVA_RECOMENDADA
    )
    return min(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, recursos_recomendados)


def verificar_hierarquia_ataque_imediato(
    *, ATAQUE_IMEDIATO_POTENCIAL: Dinheiro, ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro
) -> None:
    """RF-50 · §13.6 HIERARQUIA CANÔNICA, na parte verificável sem a fatia 3C:
    `ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO >= 0`.

    **Tolerância ZERO** (`AC-82`): a comparação é exata sobre `Decimal`, sem
    `± R$ 0,05`, sem `round`, sem `quantize`. A tolerância monetária da spec §5
    existe para valores acumulados ao longo de meses; aqui os dois lados saem
    da MESMA rodada de cálculo, sobre os mesmos itens, então qualquer
    divergência é erro de filtro (item recomendado que não está no potencial),
    não ruído de arredondamento — e um centavo de folga esconderia exatamente
    o bug que esta função existe para pegar.

    Levanta `ErroInvariante` (mesmo padrão de `engine/ciclo_mensal.py`, regra
    `A-04`) — **nunca corrige, nunca degrada silenciosamente, nunca rebaixa
    valor**. Violação de hierarquia é bug do motor, não dado do usuário:
    corrigir aqui produziria um número plausível e errado, e apagaria a prova
    de que o filtro da §13.3 divergiu do da §13.2. A mensagem nomeia os dois
    valores para que o diagnóstico não exija reproduzir o caso.

    **Função SEPARADA, chamada explicitamente** (plano R3.4.5/R3.10): embuti-la
    em `calcular_ATAQUE_IMEDIATO_RECOMENDADO` obrigaria aquela função a receber
    o potencial, que não é insumo da fórmula da §13.3 — um parâmetro que não
    participa do cálculo. O custo aceito é que a verificação depende de ser
    chamada; o benefício é que a §13.3 permanece a §13.3.

    **O ramo `>= ATAQUE_IMEDIATO_APROVADO >= 0` da §13.6 NÃO é verificado
    aqui.** A parcela confirmada pelo usuário é da fatia 3C (`OQ-30` aberta) e
    não existe nesta rodada — nem como variável, nem como parâmetro. Fingir
    verificá-la com um valor default seria afirmar uma cobertura inexistente.

    Pureza (spec §5): as duas entradas chegam por parâmetro. Não devolve valor:
    ou passa em silêncio, ou levanta.
    """
    if ATAQUE_IMEDIATO_POTENCIAL < ATAQUE_IMEDIATO_RECOMENDADO:
        raise ErroInvariante(
            "hierarquia do ataque imediato violada (RF-50/§13.6, A-04): "
            f"ATAQUE_IMEDIATO_POTENCIAL={ATAQUE_IMEDIATO_POTENCIAL!r} < "
            f"ATAQUE_IMEDIATO_RECOMENDADO={ATAQUE_IMEDIATO_RECOMENDADO!r} — "
            "o recomendado nunca pode exceder o potencial"
        )
    if ATAQUE_IMEDIATO_RECOMENDADO < dinheiro(0):
        raise ErroInvariante(
            "hierarquia do ataque imediato violada (RF-50/§13.6, A-04): "
            f"ATAQUE_IMEDIATO_RECOMENDADO={ATAQUE_IMEDIATO_RECOMENDADO!r} < 0 "
            f"(ATAQUE_IMEDIATO_POTENCIAL={ATAQUE_IMEDIATO_POTENCIAL!r}) — "
            "nenhum estágio da hierarquia admite valor negativo"
        )
