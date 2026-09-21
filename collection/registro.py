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
from enum import Enum
from typing import Final

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


@dataclass(frozen=True, slots=True)
class OpcaoRegistro:
    """Uma opção de resposta. `rotulo` é a redação canônica ao usuário;
    `valor_interno` é a coluna "Valor interno / mapeamento" da §11 (ex.:
    B5.A02 → CONSIGNADO · PESSOAL · ...). Traduzir qualquer um dos dois é
    proibido — ambos vêm do YAML de registro, nunca deste módulo."""

    rotulo: str
    valor_interno: str | None
    admite_nao_sei: bool = False


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
