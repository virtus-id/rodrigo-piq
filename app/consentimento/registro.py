"""Pontos de encaixe de consentimento — `RF-30`, `AC-39` (`PEND-01`).

Este módulo entrega o ENCAIXE de consentimento, nunca a redação. Os textos de
consentimento, o prazo de retenção e o procedimento de exclusão são insumo
externo de `PEND-01` (jurídico + especialista, `EC-13`) — nenhum deles está
escrito aqui. Três peças:

1. `carregar_texto_vigente` — lê a versão vigente do texto de
   `app/consentimento/textos/*.yaml` (dado, análogo a `collection/registros/`,
   nunca `.py`). **Sem arquivo externo, o carregamento BLOQUEIA** com
   `ErroTextoConsentimentoAusente` — o módulo não decide política (não existe
   texto padrão, não existe "aceite implícito"): a ausência do insumo de
   `PEND-01` impede o fluxo, nunca é contornada com um padrão inventado.
2. `RegistroConsentimento`/`registrar_consentimento` — a estrutura gravável
   (versão do texto, aceite, data), consultável por caso via
   `persistencia/app_aluno/consentimentos.py` (T-35, par desta tarefa).
3. `agendar_retencao`/`executar_exclusao` — os pontos de encaixe de retenção e
   exclusão (`EC-13`). Ambos declaram a INTENÇÃO da operação (assinatura,
   docstring) mas o comportamento real (prazo exato, cascata de exclusão) é
   política que `PEND-01` ainda não define — chamá-los levanta
   `ErroPoliticaPendente`, nunca uma suposição silenciosa do desenvolvedor.

Direção de dependência: este módulo usa só stdlib e `yaml` (já dependência do
gerador, `collection/carga.py`) — nunca `engine/` (escopo desta feature não
toca o motor).

REGRAS: `RF-30`, `AC-39`, `EC-13`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

import yaml

REGRAS: Final[tuple[str, ...]] = ("RF-30", "AC-39", "EC-13")

_DIRETORIO_TEXTOS_PADRAO: Final[Path] = Path(__file__).resolve().parent / "textos"

# Campos obrigatórios do formato declarado em `textos/README.md` — validados
# na carga, nunca assumidos presentes.
_CAMPOS_OBRIGATORIOS: Final[tuple[str, ...]] = ("QUESTIONARIO_VERSION", "titulo", "corpo")


class ErroTextoConsentimentoAusente(Exception):
    """`PEND-01` ainda está aberta: não existe arquivo de texto de
    consentimento em `app/consentimento/textos/`. Este é o bloqueio
    explícito exigido pelo critério de aceite — o fluxo de consentimento não
    prossegue sem o insumo externo, e nenhum texto padrão é assumido."""


class ErroTextoConsentimentoInvalido(Exception):
    """O arquivo de texto existe mas não tem a forma esperada (campo
    obrigatório ausente) — nomeia o arquivo e o campo culpado, na mesma
    disciplina de `collection.carga.ErroDeCarga`."""


class ErroPoliticaPendente(NotImplementedError):
    """Levantado por `agendar_retencao`/`executar_exclusao`: a POLÍTICA real
    (prazo exato de retenção, cascata de exclusão) é insumo de `PEND-01` e
    ainda não existe. Este módulo declara o ENCAIXE, não decide a política —
    chamar qualquer uma das duas funções antes de `PEND-01` ser respondida é
    sempre um bloqueio, nunca um padrão silencioso."""


@dataclass(frozen=True, slots=True)
class TextoConsentimento:
    """A versão vigente do texto de consentimento, lida de
    `app/consentimento/textos/` — nunca escrita em `.py` (`AC-37`)."""

    QUESTIONARIO_VERSION: str
    titulo: str
    corpo: str


@dataclass(frozen=True, slots=True)
class RegistroConsentimento:
    """Um registro de consentimento gravável — versão do texto aceito,
    aceite e data (`RF-30`, `AC-39`). `CASO_ID` é a chave de consulta."""

    CASO_ID: str
    versao_texto: str
    aceite: bool
    aceito_em: datetime


def _texto_mais_recente(arquivos: tuple[Path, ...]) -> Path:
    """Entre os arquivos de texto carregáveis, a versão vigente é a de nome
    lexicograficamente maior — mesma convenção de versionamento por nome de
    arquivo já usada por outros diretórios de dado do projeto. Determinístico
    e sem depender de data do sistema de arquivos."""
    return max(arquivos, key=lambda caminho: caminho.name)


def carregar_texto_vigente(diretorio: Path | None = None) -> TextoConsentimento:
    """Lê a versão vigente do texto de consentimento a partir de
    `app/consentimento/textos/*.yaml`.

    **Bloqueio explícito, nunca padrão assumido**: se o diretório não existe,
    ou existe vazio de `.yaml`, levanta `ErroTextoConsentimentoAusente` — o
    chamador (guarda de `T-36`) trata isso como impedimento ao fluxo, nunca
    como "sem consentimento = ok, prossiga". Arquivo presente mas incompleto
    levanta `ErroTextoConsentimentoInvalido` nomeando o campo ausente.
    """
    pasta = diretorio if diretorio is not None else _DIRETORIO_TEXTOS_PADRAO
    arquivos = tuple(sorted(pasta.glob("*.yaml"))) if pasta.is_dir() else ()

    if not arquivos:
        raise ErroTextoConsentimentoAusente(f"PEND-01 em aberto, sem texto em {pasta}")

    caminho = _texto_mais_recente(arquivos)
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))

    if not isinstance(bruto, dict):
        raise ErroTextoConsentimentoInvalido(f"{caminho}: conteúdo não é um mapeamento YAML")

    for campo in _CAMPOS_OBRIGATORIOS:
        if campo not in bruto:
            raise ErroTextoConsentimentoInvalido(f"{caminho}: campo ausente {campo!r}")

    return TextoConsentimento(
        QUESTIONARIO_VERSION=str(bruto["QUESTIONARIO_VERSION"]),
        titulo=str(bruto["titulo"]),
        corpo=str(bruto["corpo"]),
    )


def registrar_consentimento(
    caso_id: str, texto: TextoConsentimento, aceite: bool, agora: datetime
) -> RegistroConsentimento:
    """Monta o `RegistroConsentimento` a partir do texto vigente já
    carregado por `carregar_texto_vigente` — este módulo nunca decide QUAL
    versão é a vigente sem antes ter passado pelo bloqueio de ausência
    acima. A persistência (`persistencia/app_aluno/consentimentos.py`) é
    quem grava o resultado desta função."""
    return RegistroConsentimento(
        CASO_ID=caso_id,
        versao_texto=texto.QUESTIONARIO_VERSION,
        aceite=aceite,
        aceito_em=agora,
    )


def agendar_retencao(caso_id: str, prazo: object) -> None:
    """Ponto de encaixe de RETENÇÃO (`EC-13`). O prazo exato de retenção é
    texto/política de `PEND-01`, ainda não publicado — esta função declara
    a INTENÇÃO (existe um procedimento de agendamento de retenção por caso)
    sem implementar a política real. Chamá-la hoje é sempre um bloqueio.
    """
    raise ErroPoliticaPendente(
        f"agendar_retencao(caso_id={caso_id!r}): prazo de retenção é PEND-01"
    )


def executar_exclusao(caso_id: str) -> None:
    """Ponto de encaixe de EXCLUSÃO (`EC-13`). A cascata de exclusão (quais
    tabelas, em que ordem, o que é anonimizado versus removido) é texto/
    política de `PEND-01`, ainda não publicado — esta função declara a
    INTENÇÃO (existe um procedimento de exclusão por caso) sem implementar a
    cascata real. Chamá-la hoje é sempre um bloqueio, nunca uma exclusão
    parcial silenciosa.
    """
    raise ErroPoliticaPendente(f"executar_exclusao(caso_id={caso_id!r}): PEND-01 em aberto")
