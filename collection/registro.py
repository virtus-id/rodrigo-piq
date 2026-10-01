"""Esquema do registro de pergunta — o núcleo do gerador (`RF-03`..`RF-08`).

`plans/app-aluno.plan.md` §4.1. Este módulo define o ESQUEMA das 291 perguntas
da §11 da canônica: os domínios (`Obrigatoriedade`, `TipoResposta`,
`EscopoRepeticao`) e os dataclasses de registro (`OpcaoRegistro`,
`RegistroPergunta`). NENHUM enunciado, opção ou condição de pergunta aparece
aqui — o conteúdo vive em `collection/registros/*.yaml` (T-16, T-17..T-19);
este arquivo é auditado por `AC-37` (`tests/app_aluno/estatica/
test_sem_conteudo_de_questionario_no_codigo.py`) e precisa passar vazio de
conteúdo.

Os quatro tipos referenciados por `RegistroPergunta` — `Condicao` (T-10,
`collection/condicoes.py`), `Marcador` (T-12, `collection/interpolacao.py`),
`ValidacaoCruzada` (T-13, `collection/validacao.py`) e `OrigemOpcoes` (T-14,
`collection/opcoes_do_motor.py`) — já existem e são importados diretamente
abaixo.

REGRAS: `RF-03`, `AC-36`, `AC-37`
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Final, Literal

from collection.condicoes import Condicao
from collection.interpolacao import Marcador
from collection.opcoes_do_motor import OrigemOpcoes
from collection.validacao import ValidacaoCruzada

REGRAS: Final[tuple[str, ...]] = ("RF-03", "AC-36", "AC-37")


class Obrigatoriedade(Enum):
    """§11 da canônica, coluna de obrigatoriedade. Domínio FECHADO: exatamente
    quatro membros. `RegistroPergunta.obrigatoriedade` é `frozenset` — não um
    único membro — porque `COND` e `REP` coexistem no mesmo registro (caso de
    `B5.A05A`: condicional E repetível ao mesmo tempo)."""

    OBR = "OBR"
    COND = "COND"
    OPT = "OPT"
    REP = "REP"


class TipoResposta(Enum):
    """§11 da canônica — tipo de resposta de cada registro. Os nove membros
    fecham o domínio dos tipos de entrada usados nas 291 perguntas."""

    SELECAO_UNICA = "SELECAO_UNICA"
    SELECAO_MULTIPLA = "SELECAO_MULTIPLA"
    NUMERO = "NUMERO"
    MOEDA = "MOEDA"
    TAXA = "TAXA"
    DATA = "DATA"
    TEXTO_CURTO = "TEXTO_CURTO"
    SIM_NAO_TALVEZ = "SIM_NAO_TALVEZ"
    ESCALA_0_10 = "ESCALA_0_10"


class EscopoRepeticao(Enum):
    """RF-04 — 115 das 291 perguntas são `REP`, repetíveis por item. Os oito
    membros fecham o domínio de escopos de repetição, um por tipo de item que
    o aluno pode cadastrar mais de uma vez (dívida, vínculo, margem, despesa,
    ação, renda adicional, despesa não-mensal) mais `NENHUM` para pergunta
    não repetível. `RENDA_ADICIONAL_ID` e `DESPESA_NAO_MENSAL_ID` fecham
    `OQ-19` (T-105): as fichas REP de `B3.03A-C` e `B3.NM02A-D`, transcritas
    por `T-17` com `NENHUM`, ganham escopo real — sem limite de quantidade
    codificado, mesmo tratamento dos seis membros já existentes."""

    NENHUM = "NENHUM"
    DIVIDA_ID = "DIVIDA_ID"
    VINCULO_ID = "VINCULO_ID"
    MARGEM_ID = "MARGEM_ID"
    ITEM_DESPESA = "ITEM_DESPESA"
    ACAO_ID = "ACAO_ID"
    RENDA_ADICIONAL_ID = "RENDA_ADICIONAL_ID"
    DESPESA_NAO_MENSAL_ID = "DESPESA_NAO_MENSAL_ID"
    # `T-270` (RF-98, DE-02): `B3.05A`–`D` — vários recursos extraordinários,
    # cada um com tipo, valor, janela e certeza, nunca somados.
    RECURSO_EXTRAORDINARIO_ID = "RECURSO_EXTRAORDINARIO_ID"


class NIVEL_COMPROVACAO(Enum):
    """RF-91 — "Fonte de comprovação" em três níveis (`DE-06`). Nomes
    técnicos a critério do plano (`E-14`, `R9.5`). O nível é atributo da
    OPÇÃO no YAML (`OpcaoRegistro.nivel_comprovacao`) — mapear
    `valor_interno → nível` em código seria conteúdo de questionário em
    `.py`."""

    COMPROVADO = "COMPROVADO"  # nível 1
    INFORMADO = "INFORMADO"  # nível 2
    PENDENTE_DE_CONFIRMACAO = "PENDENTE_DE_CONFIRMACAO"  # nível 3 — só informação verbal


@dataclass(frozen=True, slots=True)
class NivelCondicional:
    """RF-91 — nível alternativo de uma opção quando `condicao` vale no item
    da ficha (ex.: "Outra" sobe a `COMPROVADO` com documento associado)."""

    condicao: Condicao
    nivel: NIVEL_COMPROVACAO


@dataclass(frozen=True, slots=True)
class OpcaoRegistro:
    """Uma opção de resposta. `rotulo` é a redação canônica ao usuário;
    `valor_interno` é a coluna "Valor interno / mapeamento" da §11 (ex.:
    B5.A02 → CONSIGNADO · PESSOAL · ...). Traduzir qualquer um dos dois é
    proibido — ambos vêm do YAML de registro, nunca deste módulo.

    `abre_campo` (`T-213`): a opção pede um valor digitado (ex.: "Data" de
    `B5.B05B`), gravado na `VARIAVEL_GRAVADA` da pergunta no lugar do
    `valor_interno`. Só `DATA` e `MOEDA` — o esquema recusa qualquer outro.

    `variavel_do_campo` (`T-294`): com ela, o valor digitado vai para ESTA
    variável, no mesmo item, e a opção grava seu `valor_interno` na
    `VARIAVEL_GRAVADA` como sempre (ex.: `B5.B01` "Sim." → `CONFIRMADA` +
    `VALOR_ORIGINAL`). O esquema a exige com `abre_campo: MOEDA`."""

    rotulo: str
    valor_interno: str | None
    admite_nao_sei: bool = False
    abre_campo: TipoResposta | None = None
    variavel_do_campo: str | None = None
    # RF-91 (`T-222`): padrão neutro — opção sem nível declarado não tem nível.
    nivel_comprovacao: NIVEL_COMPROVACAO | None = None
    nivel_comprovacao_se: NivelCondicional | None = None


@dataclass(frozen=True, slots=True)
class RegistroPergunta:
    """RF-03 — uma pergunta da §11, como DADO. Editar o YAML e reiniciar troca
    o enunciado sem tocar em código (`AC-36`)."""

    ID: str
    bloco: int
    enunciado: str
    tipo: TipoResposta
    obrigatoriedade: frozenset[Obrigatoriedade]
    escopo_repeticao: EscopoRepeticao
    opcoes: tuple[OpcaoRegistro, ...]
    VARIAVEL_GRAVADA: str | None
    condicao_exibicao: Condicao | None
    interpolacoes: tuple[Marcador, ...]
    validacoes_cruzadas: tuple[ValidacaoCruzada, ...]
    origem_opcoes: OrigemOpcoes
    admite_nao_sei: bool
    salto_consequencia: str | None
    # Rodada 9 (`T-222`, `R9.5`) — campos opcionais com padrão neutro: os
    # registros sem eles carregam sem edição. Quem USA cada um é tarefa
    # própria. `painel` (RF-79): a serialização anexa a fotografia do mês.
    # `indispensavel` (RF-93): dado cuja ausência bloqueia a liberação.
    # `faixa` (RF-84): intervalo FECHADO aceito na gravação (EC-01).
    painel: Literal["FOTOGRAFIA_DO_MES"] | None = None
    indispensavel: bool = False
    faixa: tuple[Decimal, Decimal] | None = None
    # Redação ao aluno quando o valor sai da `faixa` (`T-238`) — do YAML.
    mensagem_faixa: str | None = None
    # `T-254` (RF-90, `E-09`): a ficha deste registro existe DENTRO de um
    # item de outro escopo — a margem dentro do vínculo. O pai é gravado na
    # criação do item (`item_pai_id`), nunca perguntado.
    escopo_pai: EscopoRepeticao | None = None
