"""Tipos e domínios fechados do motor — RF-12, RF-16, RF-17, RF-26, RF-40.

`DESCONHECIDO` é o único jeito válido de representar dado de negócio ausente:
`None` significaria "não perguntado", que é outra coisa — RF-16. Todo
campo monetário ou de taxa que pode chegar como valor desconhecido usa
`DinheiroTalvez`/`TaxaTalvez`, nunca `Optional[Decimal]`.

Com `mypy --strict`, um `match`/`if isinstance` sobre `DinheiroTalvez` (ou
`TaxaTalvez`) que trata `Dinheiro`/`Taxa` mas esquece o ramo `Desconhecido`
falha a checagem de exaustividade quando o `else`/`case _` termina em
`assert_never` — ver verificação ad-hoc de T-04.

Os enums abaixo são os domínios fechados citados em §11.3 e §11.11 da spec
do slug e em Definições §4–§8 da canônica. Valores idênticos à spec,
caractere por caractere (§7 do sdd.config.md).
"""

from decimal import Decimal
from enum import Enum
from typing import Final

# RF-12/G-01: sempre exato; nunca float. `Dinheiro` é alias transparente de
# `Decimal` — só `engine/precisao.dinheiro()` está autorizado a construí-lo.
type Dinheiro = Decimal

# fração mensal: 4% a.m. == Decimal("0.04")
type Taxa = Decimal

type Meses = int


class Desconhecido(Enum):
    """RF-16: dado desconhecido é VALOR, não ausência. Único membro —
    existe para compor tipo-soma com `Dinheiro`/`Taxa`, nunca para ser
    instanciado fora de `DESCONHECIDO`."""

    DESCONHECIDO = "DESCONHECIDO"


DESCONHECIDO: Final = Desconhecido.DESCONHECIDO

# `None` é proibido para dado de negócio: ele significaria "não perguntado",
# que é outra coisa. Todo campo monetário/taxa potencialmente ausente usa
# um destes dois tipos-soma em vez de `Optional`.
type DinheiroTalvez = Dinheiro | Desconhecido
type TaxaTalvez = Taxa | Desconhecido


class SimNaoTalvez(Enum):
    """Domínio de resposta ternária usado em várias variáveis da canônica
    (ex. `NOVA_DIVIDA_PREVISTA`, `NOVO_PARCELAMENTO_PREVISTO`,
    `HISTORICO_RECAIDA` — `piq-app-spec.md`: "SIM · TALVEZ · NAO").

    Colocado em `engine/tipos.py` em vez de `engine/estado.py` por coesão:
    é tipo de domínio geral, não específico de dívida ou de estado
    financeiro — a regra D.4 (§11.4, T-15/T-16) e outras variáveis
    booleanas-com-incerteza vão reutilizá-lo.
    """

    SIM = "SIM"
    NAO = "NAO"
    TALVEZ = "TALVEZ"


class DIVIDA_STATUS_ESTRATEGICO(Enum):
    """RF-17 · §11.3 · Definições §6, §7 — cinco estados, não quatro."""

    INFORMACAO_PENDENTE = "INFORMACAO_PENDENTE"  # Gate 1 · QUITADA_A_CONFIRMAR
    INTERVENCAO_PENDENTE = "INTERVENCAO_PENDENTE"  # Gates 2 e 3 — GATE_PENDENTE distingue
    EM_ANALISE = "EM_ANALISE"  # STATUS_DIVIDA = OUTRA
    PRONTA_PARA_ORDENACAO = "PRONTA_PARA_ORDENACAO"
    EM_ATAQUE = "EM_ATAQUE"


class GATE_PENDENTE(Enum):
    """RF-17 · AC-43, AC-44 · Definições §7.1.

    Separa *o que a dívida é* (`DIVIDA_STATUS_ESTRATEGICO`) de *o que a
    trava*. Interno ao motor — nunca é pergunta ao usuário. Gates 2 e 3
    compartilham `INTERVENCAO_PENDENTE` e só se distinguem aqui.
    """

    INFORMACAO = "INFORMACAO"  # Gate 1
    CONTENCAO_RISCO = "CONTENCAO_RISCO"  # Gate 2
    TRANSFORMACAO = "TRANSFORMACAO"  # Gate 3
    OPORTUNIDADE = "OPORTUNIDADE"  # Gate 4
    NENHUM = "NENHUM"


class STATUS_DIVIDA(Enum):
    """RF-17 · Definições §6.

    Estado operacional declarado no cadastro. NÃO decide elegibilidade —
    quem decide são os gates (§11.3).
    """

    ATIVA = "ATIVA"
    EM_ACORDO = "EM_ACORDO"
    COBRANCA_SEM_PAGAMENTO = "COBRANCA_SEM_PAGAMENTO"
    QUITADA_A_CONFIRMAR = "QUITADA_A_CONFIRMAR"
    OUTRA = "OUTRA"


class NIVEL_CONTROLE(Enum):
    """RF-23 · Definições §4."""

    FORTE = "FORTE"
    PARCIAL = "PARCIAL"
    FRAGIL = "FRAGIL"


class CONFIABILIDADE_DADOS(Enum):
    """RF-23 · Definições §5."""

    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAIXA = "BAIXA"


class STATUS_FINANCEIRO(Enum):
    """RF-26 · AC-37..AC-39 · §11.8 · Definições §8."""

    DEFICIT = "DEFICIT"  # RESULTADO_MENSAL_ATUAL < 0 · vermelho
    EQUILIBRIO_FRAGIL = "EQUILIBRIO_FRAGIL"  # 0 <= RMA < PISO_CAPACIDADE · amarelo
    CAPACIDADE_POSITIVA = "CAPACIDADE_POSITIVA"  # RMA >= PISO · verde


class STATUS_VALIDADE_PROPOSTA(Enum):
    """RF-06."""

    VIGENTE = "VIGENTE"
    EXPIRADA = "EXPIRADA"
    VALIDADE_DESCONHECIDA = "VALIDADE_DESCONHECIDA"


class ORDEM_STATUS(Enum):
    """RF-21 · AC-09 · AC-33."""

    DEFINITIVA_NA_DATA = "DEFINITIVA_NA_DATA"
    PROVISORIA = "PROVISORIA"


class STATUS_METODO(Enum):
    """RF-08 · S-01..S-05."""

    DEFINITIVO_NA_DATA = "DEFINITIVO_NA_DATA"
    PROVISORIO = "PROVISORIO"


class CLASSIFICACAO_CENARIO(Enum):
    """S-01, S-02 — tolerância ZERO entre `NAO_CALCULAVEL` e `NAO_APLICAVEL`:
    o primeiro rebaixa o método, o segundo não."""

    CALCULAVEL = "CALCULAVEL"
    NAO_CALCULAVEL = "NAO_CALCULAVEL"  # rebaixa
    NAO_APLICAVEL = "NAO_APLICAVEL"  # não rebaixa


class METODO(Enum):
    AVALANCHE = "AVALANCHE"
    BOLA_DE_NEVE = "BOLA_DE_NEVE"
    HIBRIDO = "HIBRIDO"


class NIVEL_RISCO(Enum):
    """RF-18 · §11.4 (regra D.4)."""

    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ALTO = "ALTO"


class CLASSIFICACAO_MOBILIZACAO(Enum):
    """RF-40 · §13 (§13.2, §13.3, §13.7) · `piq-app-spec.md:2614` — domínio
    FECHADO de exatamente quatro valores.

    A canônica fecha que a classificação é DERIVADA pelo motor e PROÍBE
    perguntá-la. A *regra* de derivação não está publicada por nenhuma fonte
    (`OQ-26`, aberta). Esta rodada entrega o DOMÍNIO e recebe a classificação
    já feita, por item — nunca a deriva.

    Não existe, e não deve existir enquanto `OQ-26` estiver aberta, nenhuma
    função neste projeto que PRODUZA um destes quatro valores a partir de
    `LIQUIDEZ_INVESTIMENTOS`, `CUSTO_DESMOBILIZACAO_INVESTIMENTOS`,
    `DISPOSICAO_USO_INVESTIMENTO`, `IMOVEL_POSSUI_PASSIVO` ou tipo de ativo
    (`AC-67`).
    """

    MOBILIZACAO_POSSIVEL = "MOBILIZACAO_POSSIVEL"  # §13.3: fica no potencial
    MOBILIZACAO_RECOMENDAVEL = "MOBILIZACAO_RECOMENDAVEL"  # §13.3: único automático
    MOBILIZACAO_COM_RESSALVAS = "MOBILIZACAO_COM_RESSALVAS"
    NAO_MOBILIZAR = "NAO_MOBILIZAR"


class EVENTO_RECALCULO(Enum):
    """RF-02 · §3.2 · RF-22.

    R-04/EC-08: alteração meramente cadastral ou cosmética NÃO tem membro
    aqui — é proposital que seja inexprimível neste enum.
    """

    QUITACAO_CONFIRMADA = "QUITACAO_CONFIRMADA"
    ALTERACAO_RENDA = "ALTERACAO_RENDA"
    ALTERACAO_DESPESAS = "ALTERACAO_DESPESAS"
    NOVA_DIVIDA = "NOVA_DIVIDA"
    RENEGOCIACAO_EXECUTADA = "RENEGOCIACAO_EXECUTADA"
    TROCA_EXECUTADA = "TROCA_EXECUTADA"
    RECURSO_EXTRAORDINARIO = "RECURSO_EXTRAORDINARIO"
    INFORMACAO_MATERIAL_CONHECIDA = "INFORMACAO_MATERIAL_CONHECIDA"
    MUDANCA_PATRIMONIAL = "MUDANCA_PATRIMONIAL"
    PROPOSTA_TEMPORARIA = "PROPOSTA_TEMPORARIA"
    ALTERACAO_RISCO = "ALTERACAO_RISCO"
    OUTRO_MATERIAL = "OUTRO_MATERIAL"
