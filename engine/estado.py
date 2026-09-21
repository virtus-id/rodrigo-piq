"""Estado financeiro de entrada do motor — RF-14, RF-16, RF-17 · §11.11.

`Divida` e `EstadoFinanceiro` são o contrato de entrada do motor (§4 do plano
técnico). São `frozen=True, slots=True`: imutáveis e hasheáveis por valor —
condição para `RF-10`/`V-01` (snapshot nunca sobrescrito) e para memoização
segura de simulação (§10 da spec, custo do Híbrido).

Todo campo monetário ou de taxa que pode chegar como valor desconhecido usa
`DinheiroTalvez`/`TaxaTalvez` — nunca `Optional[Decimal]` (RF-16). `float` é
proibido em qualquer campo: `__post_init__` valida e nomeia o campo culpado,
já que `frozen=True` impede corrigir o valor, só recusar (mesmo padrão de
rejeição de `engine/precisao.py::dinheiro()`, adaptado para validar o objeto
inteiro em vez de um valor isolado).

REGRAS: Final[tuple[str, ...]] = ("RF-14", "RF-16", "RF-17", "§11.11")
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date
from enum import Enum
from typing import Final

from engine.tipos import (
    CONFIABILIDADE_DADOS,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    Desconhecido,
    Dinheiro,
    DinheiroTalvez,
    SimNaoTalvez,
    TaxaTalvez,
)

REGRAS: Final[tuple[str, ...]] = ("RF-14", "RF-16", "RF-17", "§11.11")


# ---------------------------------------------------------------------------
# TIPO_DIVIDA — B5.A02 da canônica (`piq-app-spec.md`). Domínio FECHADO,
# transcrito caractere por caractere da linha "Valor interno / mapeamento"
# de B5.A02: CONSIGNADO · PESSOAL · FIN_VEICULO · FIN_IMOBILIARIO ·
# CARTAO_ROTATIVO · CARTAO_PARCELADO · CHEQUE_ESPECIAL ·
# PARCELAMENTO_COMPRA · TRIBUTARIA · PESSOA_FISICA · ACORDO · OUTRA.
# Não é decisão desta tarefa: é o domínio normativo da canônica.
# ---------------------------------------------------------------------------
class TIPO_DIVIDA(Enum):
    """RF-17 · `piq-app-spec.md` B5.A02 — tipo de dívida declarado."""

    CONSIGNADO = "CONSIGNADO"
    PESSOAL = "PESSOAL"
    FIN_VEICULO = "FIN_VEICULO"
    FIN_IMOBILIARIO = "FIN_IMOBILIARIO"
    CARTAO_ROTATIVO = "CARTAO_ROTATIVO"
    CARTAO_PARCELADO = "CARTAO_PARCELADO"
    CHEQUE_ESPECIAL = "CHEQUE_ESPECIAL"
    PARCELAMENTO_COMPRA = "PARCELAMENTO_COMPRA"
    TRIBUTARIA = "TRIBUTARIA"
    PESSOA_FISICA = "PESSOA_FISICA"
    ACORDO = "ACORDO"
    OUTRA = "OUTRA"


# ---------------------------------------------------------------------------
# TIPO_RENDA — B3.02 da canônica. Domínio FECHADO, três valores.
# ---------------------------------------------------------------------------
class TIPO_RENDA(Enum):
    """RF-14 · `piq-app-spec.md` B3.02 — estabilidade da renda total."""

    FIXA = "FIXA"
    RELATIVAMENTE_ESTAVEL = "RELATIVAMENTE_ESTAVEL"
    VARIAVEL = "VARIAVEL"


@dataclass(frozen=True, slots=True)
class Oportunidade:
    """Gate 4 — §11.3: `OPORTUNIDADE_EXECUTAVEL = benefício + recurso
    disponível + prazo + sustentabilidade`.

    Placeholder mínimo: só o suficiente para `Divida.OPORTUNIDADE_VIGENTE`
    existir e tipar corretamente. A avaliação completa do gate (regra de
    executabilidade, prioridade, não-bloqueio automático) é escopo de
    T-29/T-30 (`engine/gates.py`), que vão consumir estes campos.
    """

    beneficio: DinheiroTalvez
    recurso_disponivel: bool
    prazo: date | None
    sustentavel: bool


@dataclass(frozen=True, slots=True)
class SinaisComportamentais:
    """Entradas coletadas da regra D.4 — §11.4 da spec do slug.

    Somente os sinais de ENTRADA (coletados). `NIVEL_CONTROLE = FRAGIL` é
    DERIVADO (Definições §4, a partir de `PerfilComportamental`) — não entra
    aqui; é calculado por `engine/comportamento.py` (T-12, fora do escopo
    desta tarefa) e injetado como parâmetro obrigatório em
    `classificar_RISCO_COMPORTAMENTAL_GERAL` (T-16).

    `MECANISMO_DEFICIT` cobre tanto o sinal 2 de `RISCO_RECAIDA` ("cartão,
    cheque especial, empréstimo ou parcelamento para fechar o mês") quanto o
    sinal 1 de `RISCO_COMPORTAMENTAL_GERAL` ("crédito usado para fechar o
    mês") — é a mesma variável coletada (`MECANISMO_DEFICIT`, B1.09),
    reaproveitada pelas duas contagens; não há duas variáveis distintas na
    canônica para os dois enunciados.

    `NECESSIDADE_VITORIA` e `HISTORICO_ABANDONO` (T-18, Definições §1,
    `BURACO-05` do plano) entram aqui pelo mesmo motivo de
    `HISTORICO_RECAIDA`: são entradas comportamentais coletadas, não
    derivadas, e alimentam exclusivamente fórmulas próximas da regra D.4
    (`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`) — nunca o diagnóstico
    financeiro (`EstadoFinanceiro` direto). `HISTORICO_ABANDONO` é
    estruturalmente análogo a `HISTORICO_RECAIDA` (mesmo domínio
    `SimNaoTalvez`, mesma natureza de "histórico declarado"); agrupá-los
    evita espalhar sinais comportamentais correlatos em dois lugares do
    estado. `NECESSIDADE_VITORIA` é escala 0–10 (mesmo padrão de
    `Divida.PESO_EMOCIONAL`, O-05/H-04), aqui com `int | Desconhecido`.

    `JANELA_NOVA_DIVIDA` (T-34, RF-22, §11.6, B1.05) entra aqui pelo mesmo
    motivo de `NOVA_DIVIDA_PREVISTA`: é entrada coletada, condicional a
    `NOVA_DIVIDA_PREVISTA ∈ {SIM, TALVEZ}` (B1.02 → B1.05 na canônica).
    `JANELA_NOVA_DIVIDA | None`, não `Desconhecido`: `None` é ausência
    ESTRUTURAL (a pergunta B1.05 nem é exibida quando `NOVA_DIVIDA_PREVISTA
    = NAO`), diferente de um dado que foi perguntado e não respondido.
    Puramente informativa — nunca insumo de projeção-base (RF-22): não
    entra em nenhuma fórmula de saldo, dívida ou ordem, só compõe o alerta
    de sustentabilidade em `engine/eventos.py`.
    """

    NOVA_DIVIDA_PREVISTA: SimNaoTalvez
    MECANISMO_DEFICIT: frozenset[str] | Desconhecido  # B1.09: checklist múltipla
    HISTORICO_RECAIDA: SimNaoTalvez
    NOVO_PARCELAMENTO_PREVISTO: SimNaoTalvez
    PACTO: str  # ESTABELECIDO · EM_CONSTRUCAO · NAO_ESTABELECIDO (B1.01)
    RISCO_IMPULSO: str | Desconhecido  # NENHUMA·UMA·DUAS_TRES·QUATRO_MAIS·NAO_SEI (B2.11)
    LINHA_CONTINUA_SENDO_UTILIZADA: str | Desconhecido  # SIM·AS_VEZES·NAO·NAO_APLICA (B5.C07)
    NECESSIDADE_VITORIA: int | Desconhecido  # 0–10 · Definições §1 · T-18
    HISTORICO_ABANDONO: SimNaoTalvez  # Definições §1 · T-18
    JANELA_NOVA_DIVIDA: JANELA_NOVA_DIVIDA | None  # B1.05 · RF-22 · T-34


# ---------------------------------------------------------------------------
# JANELA_NOVA_DIVIDA — B1.05 da canônica (`piq-app-spec.md`, linha 4967).
# Domínio FECHADO, transcrito caractere por caractere: "ATE_30D · 1_3M ·
# 4_6M · 7_12M · APOS_12M · NAO_SEI". Campo COND: só é exibido/coletado
# quando B1.02 (NOVA_DIVIDA_PREVISTA) = SIM ou TALVEZ (linha 641 da
# canônica) — daí `SinaisComportamentais.JANELA_NOVA_DIVIDA` ser
# `JANELA_NOVA_DIVIDA | None`, e não usar `Desconhecido`: `None` aqui é
# ausência ESTRUTURAL (a pergunta nem chega a ser feita quando
# NOVA_DIVIDA_PREVISTA = NAO), não dado não-respondido — mesmo padrão já
# usado por `Divida.OPORTUNIDADE_VIGENTE: Oportunidade | None` (Gate 4,
# T-08) para campo condicional por estrutura. "Uso pelo motor: Calendário
# de risco" (canônica) — nunca insumo de projeção-base (RF-22, §11.6).
# ---------------------------------------------------------------------------
class JANELA_NOVA_DIVIDA(Enum):
    """RF-22 · `piq-app-spec.md` B1.05 — janela de tempo estimada para a
    nova dívida prevista (`NOVA_DIVIDA_PREVISTA`) ocorrer. Puramente
    informativo/alerta — nunca insumo de evento determinístico (§11.6)."""

    ATE_30D = "ATE_30D"
    UM_A_TRES_MESES = "1_3M"
    QUATRO_A_SEIS_MESES = "4_6M"
    SETE_A_DOZE_MESES = "7_12M"
    APOS_12M = "APOS_12M"
    NAO_SEI = "NAO_SEI"


# ---------------------------------------------------------------------------
# Domínios de reserva e de recurso extraordinário — Rodada 3 (T-94, plano
# R3.4.2). São os domínios de COLETA da §13.1 e da §13.3 traduzidos para
# domínio de MOTOR: o motor conhece variável de domínio, nunca pergunta —
# `engine/` não importa nada de `collection/`. Os IDs de pergunta (`B4.02`,
# `B4.03`, `B3.05C`, `B3.05D`) aparecem apenas como rastreabilidade
# DOCUMENTAL nas docstrings, no mesmo padrão já usado por `TIPO_DIVIDA`
# (B5.A02) e `JANELA_NOVA_DIVIDA` (B1.05). Domínios FECHADOS, transcritos
# caractere por caractere.
# ---------------------------------------------------------------------------
class RESERVA_EXISTE(Enum):
    """RF-36 · §13.1 Regra 1 · B4.02. Ternário: a §13.1 só distingue
    `NAO` de não-`NAO`, mas `SIM` e `INFORMAL` são estados de coleta
    distintos e colapsá-los aqui perderia informação que a devolutiva usa
    (`OQ-25`, aberta — não bloqueia: a aritmética só olha `NAO`)."""

    SIM = "SIM"
    INFORMAL = "INFORMAL"
    NAO = "NAO"


class DISPOSICAO_USO_RESERVA(Enum):
    """RF-36 · §13.1 Regra 1 · B4.03. Quatro valores; a §13.1 reduz a
    `NAO`/não-`NAO`. Os outros três são preservados no estado pelo mesmo
    motivo de `RESERVA_EXISTE` (`OQ-25`)."""

    PARTE = "PARTE"
    GRANDE_PARTE = "GRANDE_PARTE"
    TALVEZ = "TALVEZ"
    NAO = "NAO"


class JANELA_RECURSO_EXTRAORDINARIO(Enum):
    """RF-39 · §13.3 (`EXTRAORDINARIOS_RECOMENDADOS`) · B3.05C — janela de
    recebimento. `ATE_30D` é a única janela do "momento atual"; as demais
    são futuro, e recurso apenas previsto para o futuro NÃO compõe o
    recomendado (§13.3)."""

    ATE_30D = "ATE_30D"  # §13.3: ÚNICO membro qualificado como "momento atual"
    UM_A_TRES_MESES = "1_3M"
    QUATRO_A_SEIS_MESES = "4_6M"
    SETE_A_DOZE_MESES = "7_12M"
    NAO_SEI = "NAO_SEI"


class CERTEZA_RECURSO_EXTRAORDINARIO(Enum):
    """RF-39 · §13.3 · B3.05D — grau de certeza. Só `CONFIRMADO` satisfaz
    "confirmados, disponíveis e aptos no momento atual" (§13.3)."""

    CONFIRMADO = "CONFIRMADO"  # §13.3: ÚNICO membro qualificado como "confirmado"
    PROVAVEL = "PROVAVEL"
    POSSIVEL = "POSSIVEL"


# ---------------------------------------------------------------------------
# PerfilComportamental — Bloco 2 (8 variáveis), §11.11. Domínios internos
# fechados, transcritos caractere por caractere da tabela da spec.
# ---------------------------------------------------------------------------
class REGISTRO_GASTOS(Enum):
    TUDO = "TUDO"
    MAIORIA = "MAIORIA"
    PARTE = "PARTE"
    RARAMENTE = "RARAMENTE"
    NAO_REGISTRA = "NAO_REGISTRA"


class FREQUENCIA_REGISTRO(Enum):
    DIARIA = "DIARIA"
    VARIAS_SEMANA = "VARIAS_SEMANA"
    SEMANAL = "SEMANAL"
    VARIAS_MES = "VARIAS_MES"
    SOB_DEMANDA = "SOB_DEMANDA"
    INDEFINIDA = "INDEFINIDA"


class DEFASAGEM_REGISTRO(Enum):
    NA_HORA = "NA_HORA"
    MESMO_DIA = "MESMO_DIA"
    DIAS_DEPOIS = "DIAS_DEPOIS"
    FIM_SEMANA = "FIM_SEMANA"
    FIM_MES = "FIM_MES"
    SEM_PADRAO = "SEM_PADRAO"


class COBERTURA_PEQUENOS_GASTOS(Enum):
    TODOS = "TODOS"
    MAIORIA = "MAIORIA"
    ALGUNS = "ALGUNS"
    QUASE_NENHUM = "QUASE_NENHUM"
    NAO_ENTRAM = "NAO_ENTRAM"


class COBERTURA_MEIOS_PAGAMENTO(Enum):
    TOTAL = "TOTAL"
    QUASE_TOTAL = "QUASE_TOTAL"
    PARCIAL = "PARCIAL"
    NAO_SEI = "NAO_SEI"


class CONHECIMENTO_GASTO(Enum):
    BOA_APROXIMACAO = "BOA_APROXIMACAO"
    RAZOAVEL = "RAZOAVEL"
    NOCAO_GERAL = "NOCAO_GERAL"
    NAO_SEI = "NAO_SEI"


class GASTOS_NAO_IDENTIFICADOS(Enum):
    NUNCA = "NUNCA"
    RARAMENTE = "RARAMENTE"
    ALGUMAS_MES = "ALGUMAS_MES"
    FREQUENTE = "FREQUENTE"
    NAO_CONFERE = "NAO_CONFERE"


class REVISAO_SEMANAL(Enum):
    SEMPRE = "SEMPRE"
    MAIORIA = "MAIORIA"
    ALGUMAS = "ALGUMAS"
    RARAMENTE = "RARAMENTE"
    NUNCA = "NUNCA"


@dataclass(frozen=True, slots=True)
class PerfilComportamental:
    """RF-23 · §11.11 — as 8 entradas do Bloco 2 que o motor exige.

    Domínios fechados: não criar valores novos. Raiz do grafo de derivação
    da §11.10 (`NIVEL_CONTROLE` depende só destas 8 variáveis).
    """

    REGISTRO_GASTOS: REGISTRO_GASTOS
    FREQUENCIA_REGISTRO: FREQUENCIA_REGISTRO
    DEFASAGEM_REGISTRO: DEFASAGEM_REGISTRO
    COBERTURA_PEQUENOS_GASTOS: COBERTURA_PEQUENOS_GASTOS
    COBERTURA_MEIOS_PAGAMENTO: COBERTURA_MEIOS_PAGAMENTO
    CONHECIMENTO_GASTO: CONHECIMENTO_GASTO
    GASTOS_NAO_IDENTIFICADOS: GASTOS_NAO_IDENTIFICADOS
    REVISAO_SEMANAL: REVISAO_SEMANAL


def _recusar_float(instancia: object) -> None:
    """Percorre os campos de uma dataclass e recusa `float`, nomeando o
    campo culpado. `frozen=True` impede corrigir o valor em
    `__post_init__` — só resta VALIDAR e levantar. Mesmo padrão de recusa
    de `engine/precisao.py::dinheiro()`, adaptado para um objeto inteiro.
    `bool` é subclasse de `int`, não de `float` — não é afetado.
    """
    for campo in fields(instancia):  # type: ignore[arg-type]
        valor = getattr(instancia, campo.name)
        if isinstance(valor, float):
            raise TypeError(
                f"{type(instancia).__name__}.{campo.name} recebeu float "
                f"({valor!r}) — RF-12 proíbe ponto flutuante binário em "
                f"campo monetário/taxa. Use Decimal (engine/precisao.dinheiro)."
            )


# ---------------------------------------------------------------------------
# LIQUIDEZ_INVESTIMENTOS / DISPOSICAO_USO_INVESTIMENTO — Rodada 4 (T-117,
# plano R4.4.1). Domínios FECHADOS que a §14.3.1 exige para
# `classificar_investimento` (T-122, fora do escopo desta tarefa): só o
# domínio nasce aqui, nenhuma função de classificação. `value` igual ao
# nome, mesmo padrão de `TIPO_DIVIDA`/`JANELA_NOVA_DIVIDA`.
# ---------------------------------------------------------------------------
class LIQUIDEZ_INVESTIMENTOS(Enum):
    """RF-53 · §14.3.1 — domínio FECHADO de seis valores que a §14.3.1
    Regras 1, 4, 5 e 6 exigem para classificar investimento. Não substitui
    `ItemInvestimento.POSSUI_LIQUIDEZ: bool` (Rodada 3): `POSSUI_LIQUIDEZ`
    continua existindo e servindo a outro propósito (§13.3 — "com liquidez"
    é condição de `INVESTIMENTOS_RECOMENDADOS`), sem relação de substituição
    com este enum, que é insumo exclusivo da classificação da §14.3.1."""

    D0 = "D0"
    D1 = "D1"
    D7 = "D7"
    D30 = "D30"
    MAIS_30 = "MAIS_30"
    BLOQUEADO = "BLOQUEADO"


class DISPOSICAO_USO_INVESTIMENTO(Enum):
    """RF-53 · §14.3.1 Regras 1, 3, 4, 5 — domínio FECHADO de três valores:
    disposição do usuário em usar o investimento para quitação de dívida."""

    NAO = "NAO"
    TALVEZ = "TALVEZ"
    SIM = "SIM"


# ---------------------------------------------------------------------------
# TIPO_ATIVO_FISICO / POSSIBILIDADE_VENDA / ESSENCIALIDADE — Rodada 4
# (T-118, plano R4.4.2). Domínios FECHADOS que `classificar_ativo_fisico`
# (T-123, fora do escopo desta tarefa) exige — só o domínio nasce aqui.
# ---------------------------------------------------------------------------
class TIPO_ATIVO_FISICO(Enum):
    """RF-54, RF-56 · §14.4 — os três tipos de ativo físico que a §14
    distingue por nome de variável de coleta (`IMOVEL_*`, `VEICULO_*`,
    `OUTRO_ATIVO_*`). É o único jeito de `classificar_ativo_fisico` saber
    que está diante de veículo para aplicar o bloqueio de `OQ-38`
    (`RF-56`, §14.8: `RENDA_RECORRENTE_ATIVO = None` estrutural)."""

    IMOVEL = "IMOVEL"
    VEICULO = "VEICULO"
    OUTRO_ATIVO = "OUTRO_ATIVO"


class POSSIBILIDADE_VENDA(Enum):
    """RF-54 · §14.4 — domínio FECHADO de cinco valores, idêntico entre os
    três tipos de ativo físico na coleta."""

    NAO = "NAO"
    EXTREMO = "EXTREMO"
    TALVEZ = "TALVEZ"
    SIM = "SIM"
    JA_PRETENDE = "JA_PRETENDE"


class ESSENCIALIDADE(Enum):
    """RF-54 · §14.5, §14.6 — domínio FECHADO de QUATRO valores, não três:
    inclui `PARCIAL` mesmo que a coleta hoje não produza esse valor por
    nenhum caminho. A §14.6 trata `IMPORTANTE` e `PARCIAL` com a MESMA
    regra ("SE ESSENCIALIDADE em {IMPORTANTE, PARCIAL}"), então `PARCIAL`
    nunca exercitado por dado real não quebra `classificar_ativo_fisico` —
    só fica um valor do domínio sem caminho de coleta ainda."""

    ESSENCIAL = "ESSENCIAL"
    IMPORTANTE = "IMPORTANTE"
    PARCIAL = "PARCIAL"
    NAO_ESSENCIAL = "NAO_ESSENCIAL"


# ---------------------------------------------------------------------------
# Itens de patrimônio — Rodada 3 (T-95, plano R3.4.3). Cada dataclass abaixo
# representa UM item, nunca um total agregado (`AC-64`): a §13.3 exige
# `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` *dos ativos
# MOBILIZACAO_RECOMENDAVEL*, soma que é inexprimível sobre um escalar já
# somado. Nomenclatura fixada pelo plano R3.4.3: PascalCase para a dataclass
# que agrupa (como `Divida`, `Oportunidade`), nome de campo caractere por
# caractere como na §13 (`sdd.config.md` §7).
#
# `ITEM_ID` é campo do PLANO, não da §13, justificado contra requisito:
# `RF-52`/`AC-83` exigem que cada item componha no máximo um componente do
# recomendado, e a §13.8 exige "origem econômica única". Sem identidade por
# item, "este item apareceu em dois componentes" seria inexprimível como
# asserção de teste. É o mínimo que satisfaz `RF-52` — nenhum campo além dele.
#
# As três chamam `_recusar_float(self)` no PRÓPRIO `__post_init__`: a função
# percorre os campos do objeto que recebe e NÃO desce em `tuple` aninhada, de
# modo que a chamada em `EstadoFinanceiro` não alcançaria um `float` escondido
# dentro de `EstadoFinanceiro.investimentos[0].VALOR_LIQUIDO_REALIZAVEL`.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ItemInvestimento:
    """RF-38 (Rodada 3) · RF-53, RF-59, EC-32 (Rodada 4) — UM investimento,
    nunca um total agregado (`AC-64`).

    Ficha repetível `B4.04A`–`B4.06B` da coleta (`[COND, REP]`). O valor
    líquido realizável (`VALOR_LIQUIDO_REALIZAVEL`) chega JÁ APURADO
    (`OQ-27`, aberta — a fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_
    DISPONIVEL` não está publicada por nenhuma fonte). Por isso continua
    campo de ENTRADA aqui: o motor recebe, nunca deriva.

    `CLASSIFICACAO_MOBILIZACAO` NÃO é mais campo do construtor (`RF-59`,
    decisão (a) de R4.1.1 do plano): chega DERIVADA por
    `classificar_investimento(item)` (`T-122`, fora do escopo desta tarefa),
    nunca armazenada. `EC-31` (Rodada 3 — "item sem classificação é erro de
    contrato") está REVOGADO: o novo erro de contrato é `EC-32` — item que
    chega sem os campos BRUTOS abaixo, que a §14.3.1 exige para a
    classificação.

    `VALOR_LIQUIDO_REALIZAVEL` (Rodada 3) e `VALOR_LIQUIDO_REALIZAVEL_
    ATIVO_DISPONIVEL` (§14.3.1, Rodada 4, nome literal da spec) COEXISTEM
    sem reconciliação (plano R4.4.1, nota; R4.10): o segundo não é
    recalculado a partir do primeiro nem o substitui — são dois valores de
    entrada distintos, decisão deliberada para não ampliar o escopo desta
    fatia reconciliando dois campos já existentes sob nomes próximos.
    """

    ITEM_ID: str  # identidade estável do item — origem econômica única (§13.8)
    VALOR_LIQUIDO_REALIZAVEL: Dinheiro
    POSSUI_LIQUIDEZ: bool  # §13.3: "com liquidez" é condição do recomendado
    LIQUIDEZ_INVESTIMENTOS: LIQUIDEZ_INVESTIMENTOS  # §14.3.1 Regras 1, 4, 5
    DISPOSICAO_USO_INVESTIMENTO: DISPOSICAO_USO_INVESTIMENTO  # §14.3.1 Regras 1, 3, 4, 5
    VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL: Dinheiro  # §14.3.1 Regra 4 — nome literal §14
    TEM_CUSTO_CONHECIDO: bool  # §14.3.1 Regra 5 — "existe custo conhecido de saída"
    SEM_CUSTO_PERDA_RELEVANTE: bool  # §14.3.1 Regra 4 — "sem custo/perda relevante conhecida"

    def __post_init__(self) -> None:
        _recusar_float(self)


@dataclass(frozen=True, slots=True)
class ItemAtivo:
    """RF-38 (Rodada 3) · RF-54, RF-56, RF-57, RF-58, RF-59, EC-32 (Rodada 4)
    — UM ativo (ficha de imóvel `B4.I01`–`B4.I04A` e demais bens), nunca um
    total agregado (`AC-64`).

    `CLASSIFICACAO_MOBILIZACAO` NÃO é mais campo do construtor (`RF-59`,
    decisão (a) de R4.1.1 do plano): chega DERIVADA por
    `classificar_ativo_fisico(item)` (`T-123`, fora do escopo desta tarefa).
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (Rodada 3) TAMBÉM deixa de
    ser campo de entrada pronto — a §14.12 fecha a fórmula (`RF-57`), então
    o valor passa a ser DERIVADO por `derivar_VALOR_LIQUIDO_REALIZAVEL_
    ATIVO`/`_DISPONIVEL` (`T-121`, fora do escopo desta tarefa), nunca
    recebido diretamente. `EC-31` (Rodada 3 — "item sem classificação é erro
    de contrato") está REVOGADO: o novo erro de contrato é `EC-32` — item
    que chega sem os campos BRUTOS abaixo, que as §14.4–§14.9/§14.12 exigem
    para classificação e derivação de valor líquido.

    Não há `POSSUI_LIQUIDEZ` aqui: "com liquidez" é condição que a §13.3
    impõe apenas a `INVESTIMENTOS_RECOMENDADOS`; `ATIVOS_RECOMENDADOS`
    qualifica-se só pela classificação.
    """

    ITEM_ID: str
    TIPO_ATIVO_FISICO: TIPO_ATIVO_FISICO  # §14.8, RF-56
    POSSIBILIDADE_VENDA: POSSIBILIDADE_VENDA  # §14.4.1, §14.5-14.9
    ESSENCIALIDADE: ESSENCIALIDADE  # §14.5, §14.6, §14.7
    VALOR_ESTIMADO_ATIVO: DinheiroTalvez  # §14.12.1 — pode ser desconhecido (EC-36)
    POSSUI_PASSIVO_VINCULADO: bool  # §14.12.4 — "não existe" → 0
    SALDO_PASSIVO_VINCULADO: DinheiroTalvez  # §14.12.4 — só relevante se acima=True
    POSSUI_CUSTO_DESMOBILIZACAO: bool  # §14.12.5 — "não existe" → 0
    # §14.12.5 — já resolvido (percentual→monetário na fronteira de montagem)
    CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez
    # §14.8 — None = ausência ESTRUTURAL (veículo, OQ-38, RF-56, EC-39), nunca
    # DESCONHECIDO — mesmo precedente de `SinaisComportamentais.JANELA_NOVA_DIVIDA:
    # JANELA_NOVA_DIVIDA | None`
    RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None
    CUSTO_RECORRENTE_ATIVO: DinheiroTalvez  # §14.8

    def __post_init__(self) -> None:
        _recusar_float(self)


@dataclass(frozen=True, slots=True)
class RecursoExtraordinario:
    """RF-39 · §13.2 (`RECURSOS_EXTRAORDINARIOS_POTENCIAIS`) · §13.3
    (`EXTRAORDINARIOS_RECOMENDADOS`) — UM recebimento previsto
    (`B3.05A`–`B3.05D`, `[COND, REP]`), nunca um total agregado.

    `AC-65`: os três campos abaixo bastam para decidir, POR ITEM e sem
    consultar nenhum outro campo, se o recurso é "confirmado, disponível e
    apto no momento atual" (§13.3):
      confirmado    = CERTEZA_RECURSO_EXTRAORDINARIO is CONFIRMADO
      momento atual = JANELA_RECURSO_EXTRAORDINARIO is ATE_30D

    `VALOR_RECURSO_EXTRAORDINARIO` chega JÁ APURADO, pelo mesmo motivo que
    o valor líquido de `ItemInvestimento`/`ItemAtivo` (`OQ-27`, aberta).
    Não há `CLASSIFICACAO_MOBILIZACAO` aqui: a §13 não classifica recurso
    extraordinário por mobilização — quem o qualifica são janela e certeza.
    """

    ITEM_ID: str
    VALOR_RECURSO_EXTRAORDINARIO: Dinheiro
    JANELA_RECURSO_EXTRAORDINARIO: JANELA_RECURSO_EXTRAORDINARIO
    CERTEZA_RECURSO_EXTRAORDINARIO: CERTEZA_RECURSO_EXTRAORDINARIO

    def __post_init__(self) -> None:
        _recusar_float(self)


@dataclass(frozen=True, slots=True)
class Divida:
    """RF-14, RF-16, RF-17 · §4 do plano técnico."""

    DIVIDA_ID: str  # O-05/H-04: desempate final
    TIPO_DIVIDA: TIPO_DIVIDA
    STATUS_DIVIDA: STATUS_DIVIDA  # ciclo de vida (B5.A04)
    SALDO_DEVEDOR_ATUAL: DinheiroTalvez
    VALOR_QUITACAO_HOJE: DinheiroTalvez
    QUITACAO_CONSULTADA: SimNaoTalvez
    STATUS_VALIDADE_PROPOSTA: STATUS_VALIDADE_PROPOSTA
    TAXA_EFETIVA_MENSAL_NORMALIZADA: TaxaTalvez  # fallback 1º de RF-21
    CET: TaxaTalvez  # fallback 2º de RF-21
    PARCELA_CONTRATUAL: DinheiroTalvez
    PAGAMENTO_MENSAL_EFETIVO: DinheiroTalvez  # AC-32/GAB-A: pode ser 0
    SEGURO_INCLUIDO_PARCELA: bool  # GAB-01: informacional
    CUSTO_SEGURO: DinheiroTalvez  # GAB-01: NUNCA somado à parcela
    PESO_EMOCIONAL: int | Desconhecido  # 0–10 · O-05/H-04
    RENEGOCIACAO_PENDENTE: bool  # Gate 3
    TROCA_PENDENTE: bool  # Gate 3
    RISCO_MATERIAL_IMINENTE: bool  # Gate 2
    OPORTUNIDADE_VIGENTE: Oportunidade | None  # Gate 4

    def __post_init__(self) -> None:
        _recusar_float(self)


@dataclass(frozen=True, slots=True)
class EstadoFinanceiro:
    """RF-14, RF-16 · §4 do plano técnico.

    `CONFIABILIDADE_DADOS` aqui é tipado com o enum `CONFIABILIDADE_DADOS`
    já existente em `engine/tipos.py` (`ALTA`/`MEDIA`/`BAIXA`, RF-23,
    Definições §5) — o plano usa o mesmo nome para o campo e para o enum
    porque é a MESMA variável semântica (§11.10: `CONFIABILIDADE_DADOS` é
    derivada de `NIVEL_CONTROLE`). Não é coincidência de nome a resolver:
    é o valor derivado sendo carregado no estado para consumo por etapas
    posteriores do motor (`FATOR_SEGURANCA`, §11.8). A derivação em si
    (T-13, `engine/comportamento.py`) fica fora do escopo desta tarefa —
    aqui só o campo é modelado, tipado com o enum correto.

    `perfil_comportamental` foi incluído mesmo não aparecendo no snippet
    literal do plano: a T-08 é responsável por modelar `PerfilComportamental`
    (§11.11) e o único lugar coerente para ele viver é dentro do estado
    financeiro completo, já que `NIVEL_CONTROLE`/`CONFIABILIDADE_DADOS`
    (T-12/T-13) o consomem a partir daqui — sem este campo, o Bloco 2
    ficaria modelado mas inacessível ao motor.

    `AUTOPERCEPCAO_CONTROLE` (T-23, `engine/diagnostico.py::GAP_AUTOPERCEPCAO`)
    é a variável `B2.13` da canônica (`piq-app-spec.md` linha 4880): escala
    0–10, obrigatória, "quanto você sente que sabe para onde o seu dinheiro
    está indo?". É entrada COLETADA do Bloco 2, assim como as 8 variáveis de
    `PerfilComportamental` — mas §11.11 desta spec do slug fecha
    `PerfilComportamental` nomeando exatamente essas 8, sem incluir
    `AUTOPERCEPCAO_CONTROLE`. Por isso o campo vive solto em
    `EstadoFinanceiro`, não dentro de `PerfilComportamental`: adicioná-lo lá
    alteraria um contrato que a spec já fechou por nome. Mesmo padrão de
    domínio de `Divida.PESO_EMOCIONAL`/`SinaisComportamentais.
    NECESSIDADE_VITORIA` (`int | Desconhecido`, escala 0–10).

    **Rodada 3 (T-96, plano R3.4.4).** Os nove campos da §13 entraram numa
    LEVA SÓ, e não campo a campo, por decisão de mitigação de risco (§8 da
    spec): `EstadoFinanceiro` compõe `SnapshotOrdem.estado_inputs`, que
    alimenta `hash_inputs` (`engine/snapshot.py`) — cada campo acrescentado
    muda o hash de TODO snapshot. Uma leva, uma mudança de hash.
    """

    DATA_REFERENCIA: date  # INPUT, nunca date.today() — NFR determinismo
    RENDA_TOTAL_RECORRENTE: Dinheiro
    TIPO_RENDA: TIPO_RENDA
    DESPESAS_OPERACIONAIS_ATUAIS: Dinheiro
    DESPESAS_NAO_MENSAIS_NORMALIZADAS: Dinheiro
    CAPACIDADE_ATAQUE_DECLARADA: DinheiroTalvez
    ECONOMIA_POTENCIAL_IMEDIATA: Dinheiro  # GAB-B/EC-11: potencial ≠ base
    INVENTARIO_COMPLETO: bool  # GAB-02/AC-09
    dividas: tuple[Divida, ...]
    perfil_comportamental: PerfilComportamental
    sinais_comportamentais: SinaisComportamentais  # entradas da regra D.4
    CONFIABILIDADE_DADOS: CONFIABILIDADE_DADOS
    AUTOPERCEPCAO_CONTROLE: int | Desconhecido  # B2.13 · §11.8 GAP_AUTOPERCEPCAO

    # --- Rodada 3 · reserva (RF-36 · §13.1) — T-96, plano R3.4.4 ---
    # `RESERVA_TOTAL` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` são
    # `DinheiroTalvez` porque a Regra 3 da §13.1 EXIGE o estado desconhecido
    # ("decisão adiada", "não sei", "reserva total desconhecida" ->
    # RESERVA_MOBILIZAVEL = DESCONHECIDA, nunca zero silencioso) — `AC-62`.
    RESERVA_EXISTE: RESERVA_EXISTE  # B4.02
    RESERVA_TOTAL: DinheiroTalvez  # B4.02A · Regra 3
    DISPOSICAO_USO_RESERVA: DISPOSICAO_USO_RESERVA  # B4.03
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez  # B4.03A · RF-42

    # --- Rodada 3 · caixa (RF-37 · §13.2, §13.3 CAIXA_RECOMENDADO) ---
    DINHEIRO_DISPONIVEL: Dinheiro
    # ↑ SEMPRE presente, nunca `DinheiroTalvez` (`AC-63`). O enunciado de
    # B4.01 já qualifica "que não esteja comprometido com as despesas
    # normais": a garantia é de COLETA e o motor NÃO revalida "livre / não
    # comprometido" em lugar nenhum (`RF-37`, `AC-63`, `OQ-28` encaminhada).
    # Valor comprometido não integra — quem exclui é a coleta, não o motor;
    # `calcular_CAIXA_RECOMENDADO` (T-104) é identidade, não validação.

    # --- Rodada 3 · patrimônio por item (RF-38, RF-39) ---
    investimentos: tuple[ItemInvestimento, ...]
    ativos: tuple[ItemAtivo, ...]
    recursos_extraordinarios: tuple[RecursoExtraordinario, ...]
    # ↑ `AC-64`: NÃO existe, e não deve existir, nenhum campo escalar de
    # total agregado de investimentos ou de ativos aqui — a §13.3 exige
    # `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` *dos ativos
    # MOBILIZACAO_RECOMENDAVEL*, soma inexprimível sobre um escalar já
    # somado. Nome de coleção em minúscula seguindo `dividas` (`RF-38`).

    def __post_init__(self) -> None:
        _recusar_float(self)
