"""Carga da redação canônica do plano e montagem do contexto de renderização
— `RF-21`, `RF-20`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-42`
(T-59, T-60); `EC-07`, `EC-08`, `EC-09` (T-62); `RF-26`, `AC-29` (T-70).

Ponto de apoio para `report/templates/plano/plano.html`: lê o título e o
corpo de `Q-03` de `report/templates/plano/textos-canonicos.yaml` — o ÚNICO
arquivo onde essa redação vive (mesma disciplina de `app/consentimento/
registro.py::carregar_texto_vigente` para o texto de consentimento e de
`collection/carga.py` para os registros de pergunta: redação é dado em YAML,
nunca literal em `.py` nem duplicada em template).

Diferença deliberada em relação a `app/consentimento/registro.py`: ali o
texto é insumo pendente (`PEND-01`) e a ausência de arquivo BLOQUEIA o fluxo
com um erro dedicado. Aqui a redação de `Q-03` já é canônica e definitiva —
`textos-canonicos.yaml` é versionado junto com este módulo, então a ausência
do arquivo é um erro de instalação/empacotamento, não uma política em
aberto: propaga como `FileNotFoundError`/erro de parsing do YAML, sem
necessidade de uma exceção própria.

`carregar_textos_canonicos` é o único carregador — tela (via
`Jinja2Templates`) e PDF (`report/pdf.py`, futuro, WeasyPrint) chamam o
MESMO `plano.html`, que recebe `titulo`/`corpo` já resolvidos por aqui,
nunca lendo o YAML por si.

**T-60 — `montar_contexto_plano`.** Lei nº 3 (`plans/app-aluno.plan.md` §1):
"a aplicação não calcula". Esta função só LÊ campos de `SnapshotOrdem` — por
`getattr`/indexação/iteração sobre `ORDEM_QUITACAO` — e nunca soma, subtrai,
multiplica ou divide um valor do snapshot (`AC-42`). A ÚNICA exceção é a
CONTAGEM de itens de `ORDEM_QUITACAO` para produzir "posição N de M": isso
não é aritmética SOBRE um valor financeiro, é `len()` de uma sequência para
exibição — a mesma distinção que `AC-42`/T-61 documentam como permitida
(contagem de itens de uma sequência, nunca soma/multiplicação de campo
monetário). Todo valor `Decimal` (monetário ou não) passa por
`engine.precisao.quantizar_exibicao` antes de virar texto — mesmo padrão já
usado por `collection/interpolacao.py::_formatar_valor` (T-12).

**T-62 — `EC-07`, `EC-08`, `EC-09`.** Os três cenários de apresentação que
divergem do plano "normal" (ordem publicada com posições) são decididos por
`decidir_cenario_apresentacao`, um `if`/`match` sobre campos JÁ EXISTENTES do
snapshot — nunca uma fórmula nova (mesma Lei nº 3 de T-60):

- `EC-07` (`ordem_vazia.html`) — `DIVIDA_ALVO_ATUAL is None`: `ORDEM_QUITACAO`
  veio vazia (nenhuma dívida elegível após os gates). A `ORDEM_ACOES` — já
  lida por `montar_contexto_plano` para o plano normal (AC-17 não muda) —
  vira o conteúdo PRINCIPAL: o que precisa ser resolvido antes de existir
  ataque, nunca uma ordem vazia sem explicação.
- `EC-09` (`estabilizacao.html`) — `snapshot.diagnostico.MODO_ESTABILIZACAO`:
  `RESULTADO_CAIXA_OBSERVADO` positivo (`Diagnostico.
  RESULTADO_CAIXA_OBSERVADO`, `engine/diagnostico.py`) NUNCA é chamado de
  "sobra" — auditado por `GAB-04`/`AC-11` no próprio motor
  (`tests/invariantes/test_gab04_estabilizacao.py`) e reforçado aqui por
  redação de template (nenhuma ocorrência da palavra em
  `estabilizacao.html`). Checado ANTES de `EC-07`/`EC-08` porque, em modo
  estabilização, método/ordem/cronograma inteiros passam a ser "fase 2
  condicional" — a condição mais abrangente das três, que subsume a
  apresentação de uma eventual `ORDEM_QUITACAO` vazia ou `PROVISORIA`
  decorrente do mesmo déficit estrutural.
- `EC-08` (`pendencias.html`, incluído dentro do plano normal, não um
  cenário exclusivo) — `snapshot.ORDEM_STATUS == ORDEM_STATUS.PROVISORIA`:
  lista as informações faltantes **lidas** do snapshot — nunca recomputadas.
  A única fonte legítima de "o que falta", sem inventar/recalcular
  (`RF-16`), é iterar `snapshot.estado_inputs.dividas` por campo `is
  DESCONHECIDO` (`Divida.SALDO_DEVEDOR_ATUAL`, `VALOR_QUITACAO_HOJE`,
  `TAXA_EFETIVA_MENSAL_NORMALIZADA`, `CET`, `PARCELA_CONTRATUAL`,
  `PAGAMENTO_MENSAL_EFETIVO`, `CUSTO_SEGURO`) mais a leitura direta de
  `snapshot.estado_inputs.INVENTARIO_COMPLETO` (`B5.FIM02`, `AC-09`/`AC-07`)
  — `motivos_rebaixamento` (`engine/ordem.py::ResultadoConsolidacaoOrdemStatus`)
  não é campo de `SnapshotOrdem` (só `ORDEM_STATUS` chega ao snapshot,
  ver `engine/snapshot.py::montar_SnapshotOrdem`), então a auditoria por
  campo `DESCONHECIDO`/`INVENTARIO_COMPLETO` é a única leitura possível sem
  recomputar a decisão do motor.

Os três estados não se excluem estruturalmente (uma carteira em modo
estabilização também pode ter `ORDEM_QUITACAO` vazia e `ORDEM_STATUS =
PROVISORIA` ao mesmo tempo), por isso `decidir_cenario_apresentacao` aplica
prioridade determinística e documentada: estabilização > ordem vazia > plano
normal (com bloco de pendências, quando `PROVISORIA`, dentro do mesmo
template).

**T-70 — `montar_contexto_estado_inputs`.** A tela de comparação do revisor
(`report/templates/revisao/comparacao.html`, `RF-26`/`AC-29`) mostra, ao lado
do plano, os `estado_inputs` (`EstadoFinanceiro`) que o produziram — TODOS os
campos, inclusive `Divida`, `PerfilComportamental` e `SinaisComportamentais`
por inteiro (contexto obrigatório da tarefa), nunca um recorte. Mesma Lei
nº 3 de `montar_contexto_plano`: esta função só LÊ campos de
`EstadoFinanceiro` por `getattr`, nunca calcula nada novo. A única
formatação aplicada é `_formatar_valor_ou_desconhecido` (abaixo), que:

- passa todo `Decimal` por `quantizar_exibicao` (mesma disciplina de
  `_formatar_valor_de_apoio`/`AC-42`);
- renderiza `Desconhecido`/`DESCONHECIDO` como o texto literal
  `"DESCONHECIDO"` — nunca `str(Desconhecido.DESCONHECIDO)` (que produziria
  `"Desconhecido.DESCONHECIDO"`) e, principalmente, nunca `0` ou string
  vazia. É a regra mais importante desta tarefa: um campo `DinheiroTalvez`/
  `TaxaTalvez`/`int | Desconhecido` marcado como desconhecido pelo motor
  precisa continuar visivelmente desconhecido para o revisor, do contrário
  ele julgaria o caso por um dado que nunca existiu (`RF-16`).

**T-115 — `_reserva_mobilizavel` (`RF-43`, `AC-70`, `EC-18`).** Quando o aluno
responde que prefere decidir depois quanto da reserva quer usar, a §13.1
(Regra 3) faz `Diagnostico.RESERVA_MOBILIZAVEL` valer `DESCONHECIDO` — e é
enfática: *"o estado DESCONHECIDA não é convertido silenciosamente em zero
como informação. A engine registra a pendência."* Exibir `R$ 0,00` aí seria
mentir para o aluno: "não decidi ainda" e "não tenho nada" são coisas
diferentes, e a segunda leitura o levaria a achar que não tem reserva alguma.

A convenção seguida é a de `_pendencias`/`ContextoPendencias`/
`pendencias.html` — a da tela do **ALUNO** —, não a de
`_formatar_valor_ou_desconhecido`, que renderiza o rótulo técnico
`"DESCONHECIDO"` e é a convenção da tela do **REVISOR** (`RF-26`/`AC-29`):
adequada lá, inadequada aqui. Como em `_pendencias`, o `.py` faz apenas a
leitura pura (`is DESCONHECIDO`, sem aritmética e sem inferência) e o texto
em português vive no template. Esta camada não reimplementa nenhuma das três
regras da §13.1: o valor chega DERIVADO do motor
(`engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`, invocado por
`engine/diagnostico.py`), e aqui só se decide COMO mostrá-lo.

REGRAS: `RF-20`, `RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-42`,
`EC-07`, `EC-08`, `EC-09`, `RF-26`, `AC-29`, `RF-43`, `AC-70`, `EC-18`
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Final

import yaml

from engine.estado import Divida, EstadoFinanceiro
from engine.precisao import quantizar_exibicao
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO, ORDEM_STATUS, Desconhecido

REGRAS: Final[tuple[str, ...]] = (
    "RF-20",
    "RF-21",
    "RF-22",
    "AC-14",
    "AC-15",
    "AC-16",
    "AC-17",
    "AC-42",
    "EC-07",
    "EC-08",
    "EC-09",
    "RF-26",
    "AC-29",
    "RF-43",
    "AC-70",
    "EC-18",
)

CAMINHO_TEXTOS_CANONICOS: Final[Path] = (
    Path(__file__).resolve().parent / "templates" / "plano" / "textos-canonicos.yaml"
)


@dataclass(frozen=True, slots=True)
class TextosCanonicosPlano:
    """O título e o corpo de `Q-03`, tais como lidos de
    `textos-canonicos.yaml` — nenhum outro texto normativo é acrescentado
    aqui além do que a canônica já define.

    `rotulos_de_apoio` (T-177) NÃO é redação normativa de `Q-03`: é a
    tradução dos nomes de variável do motor para o vocabulário do aluno.
    Vive no mesmo arquivo pela mesma disciplina — texto ao aluno é dado,
    nunca literal em `.py` (`AC-37`)."""

    titulo: str
    corpo: str
    rotulos_de_apoio: Mapping[str, str] = field(default_factory=dict)
    #: Por método (`METODO.value`) → `{"primeira": …, "seguintes": …}` — a
    #: explicação que o ALUNO lê, ao lado da `JUSTIFICATIVA_POSICAO`
    #: técnica, que segue para o revisor (`T-177`).
    #:
    #: Duas redações porque a primeira posição é a dívida em ataque AGORA, e
    #: o motivo dela estar ali ("é a de menor valor") seria falso da segunda
    #: em diante.
    explicacao_da_posicao: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: Por campo — o que falta, dito ao aluno (`T-177`).
    rotulos_de_pendencia: Mapping[str, str] = field(default_factory=dict)


def carregar_textos_canonicos(
    caminho: Path | None = None,
) -> TextosCanonicosPlano:
    """Lê `titulo`/`corpo` de `textos-canonicos.yaml` — a única leitura da
    redação de `Q-03` em todo o projeto. `plano.html` (tela e PDF) recebe o
    resultado desta função como contexto Jinja2; nenhum HTML contém a
    redação como literal."""
    alvo = caminho if caminho is not None else CAMINHO_TEXTOS_CANONICOS
    bruto = yaml.safe_load(alvo.read_text(encoding="utf-8"))

    # `T-177`: a chave é opcional para que um YAML antigo (ou um de teste
    # que só declare título e corpo) continue carregando. Sem ela, os
    # valores de apoio aparecem com o nome técnico — visível, nunca um
    # rótulo inventado aqui.
    def _mapa(chave: str) -> dict[str, str]:
        bloco = bruto.get(chave) or {}
        return {str(k): str(v) for k, v in bloco.items()}

    # `explicacao_da_posicao` é aninhado: método → {"primeira", "seguintes"}.
    explicacoes = {
        str(metodo): {str(quando): str(texto) for quando, texto in (redacoes or {}).items()}
        for metodo, redacoes in (bruto.get("explicacao_da_posicao") or {}).items()
    }

    return TextosCanonicosPlano(
        titulo=str(bruto["titulo"]),
        corpo=str(bruto["corpo"]),
        rotulos_de_apoio=_mapa("rotulos_de_apoio"),
        explicacao_da_posicao=explicacoes,
        rotulos_de_pendencia=_mapa("rotulos_de_pendencia"),
    )


def _formatar_valor_de_apoio(valor: Decimal | object) -> str:
    """Mesmo padrão de `collection/interpolacao.py::_formatar_valor` (T-12):
    todo `Decimal` (monetário ou taxa) passa por `quantizar_exibicao` antes
    de virar texto — nunca uma formatação numérica própria deste módulo."""
    if isinstance(valor, Decimal):
        return str(quantizar_exibicao(valor))
    return str(valor)


def _agrupar_milhar(inteiro: str) -> str:
    """`1234567` → `1.234.567`. Mesma regra de
    `frontend/src/mascaras.ts::agruparMilhar` — as duas pontas escrevem
    dinheiro do mesmo jeito, senão o aluno vê um formato ao digitar e outro
    ao ler o plano."""
    digitos = inteiro.lstrip("-")
    sinal = "-" if inteiro.startswith("-") else ""
    partes: list[str] = []
    while len(digitos) > 3:
        partes.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    partes.insert(0, digitos)
    return sinal + ".".join(partes)


def formatar_dinheiro_br(valor: Decimal) -> str:
    """`Decimal('73640.56')` → `R$ 73.640,56` — `T-177`.

    **Por que o servidor formata, e não a tela.** `RF-13` fixa a fronteira
    de dinheiro no servidor: o cliente recebe texto pronto e o exibe
    verbatim (`AC-14`). Deixar a formatação para o React significaria duas
    implementações da mesma regra — e a do PDF (WeasyPrint, sem JavaScript)
    ficaria de fora.

    **Por que isto não viola a Lei nº 3.** Não há aritmética: o valor já vem
    quantizado por `quantizar_exibicao`, e esta função só troca o separador
    decimal e agrupa milhar. Nenhum número muda de valor.
    """
    texto = str(quantizar_exibicao(valor))
    inteiro, _, centavos = texto.partition(".")
    centavos = (centavos + "00")[:2]
    return f"R$ {_agrupar_milhar(inteiro)},{centavos}"


def formatar_taxa_br(valor: Decimal) -> str:
    """`Decimal('0.042')` → `4,2% a.m.` — `T-177`.

    **A multiplicação por 100 é conversão de unidade, não cálculo.** O motor
    guarda taxa como fração (`0.042`), que é a unidade em que a matemática
    financeira opera; `4,2%` é a MESMA grandeza na unidade em que uma pessoa
    lê. `converter_para_taxa` faz a viagem inversa na entrada (divide por
    100), pela mesma razão. Mostrar `0.04` ao aluno é mostrar a unidade
    interna do motor — foi o que `T-177` encontrou na tela do primeiro plano
    liberado.

    `a.m.` porque a variável é `TAXA_EFETIVA_MENSAL_NORMALIZADA`: uma taxa
    sem período não informa, e "4,2%" sozinho seria lido como anual por
    muita gente.

    O `normalize()` tira zeros à direita (`4,20` → `4,2`) sem mexer no
    valor; `quantize` a duas casas evita a dízima que a multiplicação pode
    produzir.
    """
    # `quantizar_exibicao` no lugar de `Decimal("0.01")`: `RF-13` fixa a
    # fronteira única de construção de `Decimal` em
    # `app/montagem/conversao.py`, e `tests/app_aluno/estatica/
    # test_fronteira_decimal_unica.py` audita isso. Multiplicar por um
    # `int` não constrói `Decimal` novo — só muda a unidade.
    percentual = quantizar_exibicao(valor * 100)
    # `:f` em vez de `normalize()`: `normalize` devolve notação científica
    # para alguns valores (`1E+1`), que ninguém quer ler num plano.
    texto = f"{percentual:f}"
    inteiro, _, decimais = texto.partition(".")
    decimais = decimais.rstrip("0")
    virgula = f",{decimais}" if decimais else ""
    return f"{_agrupar_milhar(inteiro)}{virgula}% a.m."


#: Como cada valor de apoio é escrito — `T-177`.
#:
#: As chaves são as que `engine/ordem.py::_valores_de_apoio` emite. O motor
#: guarda todas como `Decimal` (inclusive `PESO_EMOCIONAL`, para caber no
#: mesmo mapa), então o tipo Python não distingue dinheiro de taxa de escala:
#: quem distingue é o SIGNIFICADO da variável, e ele está aqui.
#:
#: Uma chave nova sem entrada aqui cai no formato monetário? **Não** — cai em
#: `_formatar_valor_de_apoio`, o formato cru de antes. É deliberado: inventar
#: "R$" para uma variável cujo significado ninguém declarou seria afirmar que
#: ela é dinheiro sem saber.
_FORMATO_DE_APOIO: Final[Mapping[str, str]] = {
    "SALDO_DEVEDOR_ATUAL": "dinheiro",
    "VALOR_RELEVANTE_PARA_QUITACAO": "dinheiro",
    "PAGAMENTO_MENSAL_EFETIVO": "dinheiro",
    "TAXA_EFETIVA_MENSAL_NORMALIZADA": "taxa",
    "CET": "taxa",
    "PESO_EMOCIONAL": "escala",
}


def _apresentar_valor_de_apoio(nome: str, valor: Decimal | object) -> str:
    """O valor de apoio como o aluno lê — `T-177`.

    Despacha por `_FORMATO_DE_APOIO`; o que não está lá mantém o formato
    anterior, sem unidade inventada."""
    if not isinstance(valor, Decimal):
        return _formatar_valor_de_apoio(valor)

    formato = _FORMATO_DE_APOIO.get(nome)
    if formato == "dinheiro":
        return formatar_dinheiro_br(valor)
    if formato == "taxa":
        return formatar_taxa_br(valor)
    if formato == "escala":
        return formatar_escala_br(valor)
    return _formatar_valor_de_apoio(valor)


def _formatar_meses(prazo: int) -> str:
    """`33` → `33 meses`; `1` → `1 mês` — `T-177`.

    O singular não é firula: "1 meses" na tela do plano de alguém que
    terminou o esforço em um mês é o tipo de detalhe que faz a entrega
    parecer não revisada."""
    return f"{prazo} mês" if prazo == 1 else f"{prazo} meses"


def formatar_escala_br(valor: Decimal) -> str:
    """`Decimal('6.00')` → `6 de 10` — `T-177`.

    `PESO_EMOCIONAL` é `ESCALA_0_10`, e o motor o carrega como `Decimal`
    para caber no mesmo mapa dos valores monetários. Exibi-lo como `6.00`
    sugere precisão decimal que a escala não tem; `6 de 10` diz o que o
    número é.
    """
    return f"{int(valor)} de 10"


# T-70 — o texto exibido para qualquer campo cujo valor seja `DESCONHECIDO`.
# Literal e explícito: nunca "0", nunca string vazia (RF-16, regra mais
# importante desta tarefa — ver docstring do módulo).
_TEXTO_DESCONHECIDO: Final[str] = "DESCONHECIDO"


def _formatar_valor_ou_desconhecido(valor: object) -> str:
    """T-70 (`RF-26`, `AC-29`) — formata QUALQUER campo de `EstadoFinanceiro`/
    `Divida`/`PerfilComportamental`/`SinaisComportamentais` para exibição ao
    revisor, tratando `Desconhecido` (`engine.tipos.DESCONHECIDO`) de forma
    VISÍVEL, nunca como `0` ou vazio.

    Ordem de checagem, cada uma exaustiva para o tipo que trata:

    - `Desconhecido` (comparação `isinstance`, equivalente a `is DESCONHECIDO`
      já que o enum tem um único membro) -> `"DESCONHECIDO"` literal — nunca
      `str(valor)`, que produziria `"Desconhecido.DESCONHECIDO"` (ilegível) e
      nunca um valor numérico substituto.
    - `None` -> `"—"`: `None` é ausência ESTRUTURAL (campo condicional que
      nem chega a ser perguntado, ex. `JANELA_NOVA_DIVIDA`,
      `OPORTUNIDADE_VIGENTE`), semanticamente distinta de `DESCONHECIDO`
      (RF-16: "`None` significaria 'não perguntado', que é outra coisa") —
      as duas ausências recebem rótulos DIFERENTES para que o revisor não as
      confunda.
    - `Decimal` -> `quantizar_exibicao` (mesma disciplina de
      `_formatar_valor_de_apoio`/`AC-42`: todo monetário/taxa exibido passa
      por ali, nunca uma formatação numérica própria).
    - `Enum` -> `.value` (o identificador canônico, nunca `str(enum)`, que
      incluiria o nome da classe).
    - `frozenset`/`set` -> os elementos ordenados e unidos por vírgula, para
      exibição estável (`MECANISMO_DEFICIT`, B1.09).
    - `bool`/demais tipos -> `str(valor)`.
    """
    if isinstance(valor, Desconhecido):
        return _TEXTO_DESCONHECIDO
    if valor is None:
        return "—"
    if isinstance(valor, Decimal):
        return str(quantizar_exibicao(valor))
    if isinstance(valor, Enum):
        return str(valor.value)
    if isinstance(valor, (frozenset, set)):
        return ", ".join(sorted(str(item) for item in valor))
    return str(valor)


@dataclass(frozen=True, slots=True)
class ContextoCampo:
    """Um campo de `EstadoFinanceiro`/`Divida`/`PerfilComportamental`/
    `SinaisComportamentais`, já formatado para exibição ao revisor — nome do
    campo (idêntico ao da spec canônica, `sdd.config.md` §7) e valor tal
    como `_formatar_valor_ou_desconhecido` o resolveu."""

    nome: str
    valor: str


def _campos_de_apoio(instancia: object) -> tuple[ContextoCampo, ...]:
    """T-70 — todos os campos de uma dataclass `frozen` do motor
    (`EstadoFinanceiro`, `Divida`, `PerfilComportamental`,
    `SinaisComportamentais`), na ordem declarada, cada um formatado por
    `_formatar_valor_ou_desconhecido`. Leitura genérica por `dataclasses.
    fields`/`getattr` — nenhum campo é escolhido a dedo, nenhum é omitido
    (contexto obrigatório da tarefa: "TODOS os campos que precisam ser
    exibidos ao revisor, incluindo os que são `Desconhecido`")."""
    return tuple(
        ContextoCampo(
            nome=campo.name,
            valor=_formatar_valor_ou_desconhecido(getattr(instancia, campo.name)),
        )
        for campo in fields(instancia)  # type: ignore[arg-type]
    )


@dataclass(frozen=True, slots=True)
class ContextoDivida:
    """Uma `Divida` de `estado_inputs.dividas`, com TODOS os seus campos
    formatados para exibição ao revisor (`RF-26`, `AC-29`) — inclusive os
    que são `Desconhecido` (`GAB-03`/`AC-08`: saldo e pagamento
    desconhecidos, reproduzidos pelo teste desta tarefa)."""

    DIVIDA_ID: str
    campos: tuple[ContextoCampo, ...]


@dataclass(frozen=True, slots=True)
class ContextoEstadoInputs:
    """T-70 (`RF-26`, `AC-29`) — os `estado_inputs` (`EstadoFinanceiro`)
    completos que produziram o snapshot, prontos para
    `report/templates/revisao/comparacao.html`. `campos` cobre os campos
    escalares de `EstadoFinanceiro` (exceto `dividas`, `perfil_
    comportamental` e `sinais_comportamentais`, que ganham seções próprias
    abaixo, e não são duplicados aqui); `perfil_comportamental` e
    `sinais_comportamentais` cobrem, cada um, TODOS os campos de
    `PerfilComportamental`/`SinaisComportamentais`; `dividas` cobre, para
    CADA dívida, TODOS os campos de `Divida`."""

    campos: tuple[ContextoCampo, ...]
    perfil_comportamental: tuple[ContextoCampo, ...]
    sinais_comportamentais: tuple[ContextoCampo, ...]
    dividas: tuple[ContextoDivida, ...]


# Campos de `EstadoFinanceiro` que ganham seção própria em
# `montar_contexto_estado_inputs` — excluídos de `campos` para não duplicar
# a mesma informação em dois lugares do contexto.
_CAMPOS_ESTADO_COM_SECAO_PROPRIA: Final[frozenset[str]] = frozenset(
    {"dividas", "perfil_comportamental", "sinais_comportamentais"}
)


def montar_contexto_estado_inputs(estado: EstadoFinanceiro) -> ContextoEstadoInputs:
    """T-70 (`RF-26`, `AC-29`) — monta o contexto de exibição de
    `estado_inputs` para o revisor, a partir de um `EstadoFinanceiro` REAL
    (`SnapshotOrdem.estado_inputs`). Lei nº 3: só LÊ campos por `getattr`,
    nunca calcula nada — cada valor passa por `_formatar_valor_ou_
    desconhecido`, que é quem decide a formatação (nunca este função).

    Todo campo de `EstadoFinanceiro`, `Divida`, `PerfilComportamental` e
    `SinaisComportamentais` aparece no contexto resultante — nenhum é
    omitido, e nenhum campo `DESCONHECIDO` vira `0` ou string vazia (ver
    `_formatar_valor_ou_desconhecido`)."""
    campos = tuple(
        ContextoCampo(
            nome=campo.name,
            valor=_formatar_valor_ou_desconhecido(getattr(estado, campo.name)),
        )
        for campo in fields(estado)
        if campo.name not in _CAMPOS_ESTADO_COM_SECAO_PROPRIA
    )

    dividas = tuple(
        ContextoDivida(DIVIDA_ID=divida.DIVIDA_ID, campos=_campos_de_apoio(divida))
        for divida in estado.dividas
    )

    return ContextoEstadoInputs(
        campos=campos,
        perfil_comportamental=_campos_de_apoio(estado.perfil_comportamental),
        sinais_comportamentais=_campos_de_apoio(estado.sinais_comportamentais),
        dividas=dividas,
    )


class CENARIO_APRESENTACAO(Enum):
    """T-62 — os cenários de apresentação do plano, decididos por LEITURA de
    campo do snapshot (nunca por cálculo — ver `decidir_cenario_apresentacao`
    e a docstring do módulo). Domínio interno de `report/`, não do motor: a
    própria tarefa que fecha esta lacuna registra que "quem os apresenta como
    fase 2 é o `report/`" (`tests/invariantes/test_gab04_estabilizacao.py`).
    """

    NORMAL = "NORMAL"  # ORDEM_QUITACAO publicada — plano.html/posicao.html
    ORDEM_VAZIA = "ORDEM_VAZIA"  # EC-07 — DIVIDA_ALVO_ATUAL is None
    ESTABILIZACAO = "ESTABILIZACAO"  # EC-09 — MODO_ESTABILIZACAO


def decidir_cenario_apresentacao(snapshot: SnapshotOrdem) -> CENARIO_APRESENTACAO:
    """`EC-07`, `EC-09` (T-62) — decide qual template principal é incluído
    por `plano.html`, por leitura direta de dois campos JÁ EXISTENTES do
    snapshot — nenhuma fórmula nova, nenhum recálculo (Lei nº 3).

    Prioridade determinística (ver docstring do módulo, "Os três estados não
    se excluem estruturalmente"): `MODO_ESTABILIZACAO` primeiro, porque em
    modo estabilização método/ordem/cronograma inteiros passam a ser "fase 2
    condicional" — a condição mais abrangente, que subsume qualquer
    `ORDEM_QUITACAO` vazia decorrente do mesmo déficit estrutural. Só então
    `DIVIDA_ALVO_ATUAL is None` (`EC-07`). Fora desses dois, o plano é
    `NORMAL` — que ainda pode trazer o bloco de pendências de `EC-08`
    (`ORDEM_STATUS == PROVISORIA`), mas SEM trocar de template principal.
    """
    if snapshot.diagnostico.MODO_ESTABILIZACAO:
        return CENARIO_APRESENTACAO.ESTABILIZACAO
    if snapshot.DIVIDA_ALVO_ATUAL is None:
        return CENARIO_APRESENTACAO.ORDEM_VAZIA
    return CENARIO_APRESENTACAO.NORMAL


@dataclass(frozen=True, slots=True)
class ContextoAcaoRequerida:
    """Uma ação de `ORDEM_ACOES`, já pronta para exibição — só campos LIDOS
    de `AcaoRequerida` (`engine/gates.py`), sem nenhum cálculo (`AC-42`).
    Usada tanto pelo bloco de fila paralela do plano normal quanto, em
    primeiro plano, por `ordem_vazia.html` (`EC-07`).

    **T-92 — `DIVIDA_ID: str | None`.** `AcaoRequerida.DIVIDA_ID` (`engine/
    gates.py`, T-79/RF-31) relaxou para `str | None`: a ação de economia
    (`TIPO_ACAO="ECONOMIA"`, `RF-33`, `T-88`) não tem dívida associada. Este
    contexto propaga o mesmo relaxamento, em vez de forçar `str` — decidir
    aqui um `DIVIDA_ID` fictício para a ação de economia inventaria dado
    (`RF-16`). A exibição de `None` é resolvida em `_contexto_acoes`
    (abaixo), reaproveitando o texto `"—"` já usado por `_formatar_valor_ou_
    desconhecido` para ausência ESTRUTURAL (campo que não se aplica) — a
    mesma convenção já estabelecida neste módulo para `None`, não um texto
    novo inventado para este caso."""

    DIVIDA_ID: str | None
    descricao: str
    prioridade_excepcional: bool


def _contexto_acoes(snapshot: SnapshotOrdem) -> tuple[ContextoAcaoRequerida, ...]:
    """`EC-07` — `ORDEM_ACOES` tal como o snapshot a devolveu, sem
    reordenar nem filtrar: leitura direta, campo a campo.

    T-92: `DIVIDA_ID` é repassado tal como veio de `AcaoRequerida` (`str |
    None`) — a decisão de texto de exibição para `None` fica em
    `ContextoAcaoRequerida`/nos templates, não aqui (esta função continua
    sendo pura leitura, sem decidir apresentação)."""
    return tuple(
        ContextoAcaoRequerida(
            DIVIDA_ID=acao.DIVIDA_ID,
            descricao=acao.descricao,
            prioridade_excepcional=acao.prioridade_excepcional,
        )
        for acao in snapshot.ORDEM_ACOES
    )


# Nome do campo -> rótulo de exibição do dado material que falta (EC-08).
# Só os campos `DinheiroTalvez`/`TaxaTalvez` de `Divida` que RF-16 permite
# marcar `DESCONHECIDO` — mesmo conjunto citado em `engine/estado.py::Divida`.
# Declarado aqui, não descoberto por introspecção: a tarefa pede leitura de
# campo, não uma varredura genérica de dataclass que inventaria rótulo.
_CAMPOS_MATERIAIS_DA_DIVIDA: Final[tuple[str, ...]] = (
    "SALDO_DEVEDOR_ATUAL",
    "VALOR_QUITACAO_HOJE",
    "TAXA_EFETIVA_MENSAL_NORMALIZADA",
    "CET",
    "PARCELA_CONTRATUAL",
    "PAGAMENTO_MENSAL_EFETIVO",
    "CUSTO_SEGURO",
)


@dataclass(frozen=True, slots=True)
class ContextoPendencias:
    """`EC-08` — as informações faltantes que mantêm o plano `PROVISORIA`,
    lidas do snapshot: nenhuma delas é recomputada, apenas relatada
    (`snapshot.estado_inputs`, `RF-16`)."""

    inventario_incompleto: bool  # estado_inputs.INVENTARIO_COMPLETO is False (B5.FIM02)
    campos_faltantes_por_divida: tuple[tuple[str, tuple[str, ...]], ...]  # (DIVIDA_ID, campos)


def _campos_desconhecidos_da_divida(divida: Divida) -> tuple[str, ...]:
    """`EC-08` — os nomes dos campos materiais desta `Divida` cujo valor é
    `DESCONHECIDO`, na ordem declarada em `_CAMPOS_MATERIAIS_DA_DIVIDA`.
    Comparação `is DESCONHECIDO` pura — nenhuma aritmética, nenhuma
    inferência sobre o valor (`RF-16`)."""
    return tuple(
        campo
        for campo in _CAMPOS_MATERIAIS_DA_DIVIDA
        if getattr(divida, campo) is DESCONHECIDO
    )


def _pendencias(
    snapshot: SnapshotOrdem, rotulos: Mapping[str, str] | None = None
) -> ContextoPendencias | None:
    """`EC-08` — monta o relato de pendências quando `ORDEM_STATUS =
    PROVISORIA`, por LEITURA de `snapshot.estado_inputs` — nunca recomputando
    a decisão do motor (`motivos_rebaixamento` de `consolidar_ORDEM_STATUS`
    não é campo de `SnapshotOrdem`; a única fonte sem recálculo é o campo
    `INVENTARIO_COMPLETO` mais a comparação `is DESCONHECIDO` de cada campo
    material de cada `Divida` de `estado_inputs.dividas` — ver docstring do
    módulo). `None` quando o plano não está `PROVISORIA`: nada a relatar."""
    if snapshot.ORDEM_STATUS is not ORDEM_STATUS.PROVISORIA:
        return None

    # `T-177`: o aluno lê "quanto precisaria pagar para quitar hoje", não
    # `VALOR_QUITACAO_HOJE`. Campo sem rótulo cadastrado mantém o nome
    # técnico — visível, nunca um rótulo inventado aqui.
    traduzir = rotulos or {}

    campos_faltantes_por_divida = tuple(
        (divida.DIVIDA_ID, tuple(traduzir.get(campo, campo) for campo in campos_da_divida))
        for divida in snapshot.estado_inputs.dividas
        for campos_da_divida in (_campos_desconhecidos_da_divida(divida),)
        if campos_da_divida
    )

    return ContextoPendencias(
        inventario_incompleto=snapshot.estado_inputs.INVENTARIO_COMPLETO is False,
        campos_faltantes_por_divida=campos_faltantes_por_divida,
    )


@dataclass(frozen=True, slots=True)
class ContextoReservaMobilizavel:
    """`RF-43`, `AC-70`, `EC-18` (T-115) — `Diagnostico.RESERVA_MOBILIZAVEL`
    (`DinheiroTalvez`, `engine/diagnostico.py`) pronto para exibição ao
    ALUNO. Os dois estados são campos SEPARADOS, não um texto que o template
    precise interpretar: `pendente_de_decisao` decide QUAL bloco de
    `reserva_mobilizavel.html` aparece, e `valor` só é lido quando ele é
    `False`.

    A separação existe porque os dois estados NÃO são o mesmo tipo de
    informação: "ainda não decidi quanto da minha reserva quero usar"
    (§13.1, Regra 3) e "tenho R$ 0,00 de reserva mobilizável" (§13.1,
    Regra 1) levariam o aluno a conclusões diferentes sobre a própria
    situação. Um `valor: str` sozinho obrigaria o template a distinguir os
    dois por inspeção de texto — exatamente a conversão silenciosa que a
    §13.1 proíbe."""

    pendente_de_decisao: bool  # RESERVA_MOBILIZAVEL is DESCONHECIDO
    valor: str  # "" quando pendente de decisão; formatado quando não


def _reserva_mobilizavel(snapshot: SnapshotOrdem) -> ContextoReservaMobilizavel:
    """`RF-43`, `AC-70`, `EC-18` — lê `snapshot.diagnostico.
    RESERVA_MOBILIZAVEL` para exibição ao aluno.

    Leitura PURA, na mesma disciplina de `_campos_desconhecidos_da_divida`:
    uma comparação `is DESCONHECIDO` e nada mais — nenhuma aritmética,
    nenhuma inferência, nenhuma reimplementação das três regras da §13.1
    (`engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL` já as aplicou;
    o valor chega aqui DERIVADO, e esta camada só decide COMO mostrá-lo).

    O ramo desconhecido NUNCA passa por `_formatar_valor_de_apoio`: aquela
    função cai em `str(valor)` para o que não é `Decimal` e produziria
    `"Desconhecido.DESCONHECIDO"`. E também não usa
    `_formatar_valor_ou_desconhecido`, que é a convenção da tela do REVISOR
    (rótulo técnico `"DESCONHECIDO"`, `RF-26`/`AC-29`) — adequada lá,
    inadequada aqui. `valor` fica `""` e a decisão de o que o aluno LÊ é do
    template (`reserva_mobilizavel.html`, redação pendente de `OQ-21`),
    mesma divisão de trabalho de `_pendencias`/`pendencias.html`.

    Nenhum caminho levanta exceção ao encontrar `DESCONHECIDO` (`EC-18`), e
    nenhum o converte em zero — a §13.1 é explícita: "o estado DESCONHECIDA
    não é convertido silenciosamente em zero como informação"."""
    RESERVA_MOBILIZAVEL = snapshot.diagnostico.RESERVA_MOBILIZAVEL

    if RESERVA_MOBILIZAVEL is DESCONHECIDO:
        return ContextoReservaMobilizavel(pendente_de_decisao=True, valor="")

    return ContextoReservaMobilizavel(
        pendente_de_decisao=False,
        # `T-177`: `R$ 3.000,00`, não `3000.00`.
        valor=formatar_dinheiro_br(RESERVA_MOBILIZAVEL),
    )


@dataclass(frozen=True, slots=True)
class ContextoPosicao:
    """Uma posição de `ORDEM_QUITACAO`, já pronta para `posicao.html` — só
    campos LIDOS de `PosicaoOrdem` (`engine/ordem.py`), formatados por
    `_formatar_valor_de_apoio` (`AC-42`). `indice`/`total` são contagem de
    itens da sequência para exibição ("posição N de M"), não aritmética
    sobre valor financeiro — ver docstring do módulo."""

    posicao: int  # PosicaoOrdem.posicao — LIDO, nunca recalculado
    indice: int  # 1-based: ordem de exibição na sequência (contagem, não valor financeiro)
    total: int  # len(ORDEM_QUITACAO) — contagem de itens, não valor financeiro (AC-42)
    DIVIDA_ID: str
    #: Texto de AUDITORIA, do motor — vai ao revisor (`RF-26`/`AC-29`) e ao
    #: PDF. O próprio `engine/ordem.py` o declara "não prosa de usuário
    #: final".
    JUSTIFICATIVA_POSICAO: str
    valores_de_apoio: tuple[tuple[str, str], ...]  # (rótulo ao aluno, valor formatado)
    #: `T-177` — por que esta dívida vem nesta posição, dito ao ALUNO. Vazia
    #: quando o método não tem redação cadastrada: aí a tela cai na
    #: justificativa técnica, que é visível, em vez de não explicar nada.
    explicacao: str = ""


@dataclass(frozen=True, slots=True)
class ContextoPlano:
    """Contexto completo de `plano.html`: a redação canônica de `Q-03`
    (T-59), a ordem e o carimbo de versão lidos do snapshot (T-60), mais o
    cenário de apresentação e seus dados de apoio (`EC-07`, `EC-08`, `EC-09`,
    T-62). `cenario` decide, dentro de `plano.html`, qual dos três blocos —
    ordem normal, `ordem_vazia.html` ou `estabilizacao.html` — é incluído;
    `pendencias` (pode ser `None`) alimenta `pendencias.html` quando o plano
    está `PROVISORIA`, independentemente do `cenario`;
    `reserva_mobilizavel` (T-115, `RF-43`) alimenta
    `reserva_mobilizavel.html` sempre — o estado desconhecido é exibido
    como pendência de decisão, nunca omitido nem convertido em zero."""

    titulo: str
    corpo: str
    ordem: tuple[ContextoPosicao, ...]
    PRAZO_TOTAL: str
    CUSTO_FUTURO_TOTAL: str
    ENGINE_VERSION: str
    PARAMETROS_VERSION: str
    cenario: CENARIO_APRESENTACAO
    acoes: tuple[ContextoAcaoRequerida, ...]
    pendencias: ContextoPendencias | None
    MODO_ESTABILIZACAO: bool
    RESULTADO_CAIXA_OBSERVADO: str
    reserva_mobilizavel: ContextoReservaMobilizavel


def montar_contexto_plano(
    snapshot: SnapshotOrdem, textos: TextosCanonicosPlano
) -> ContextoPlano:
    """RF-20, RF-22, AC-16, AC-17, AC-42 (T-60); EC-07, EC-08, EC-09 (T-62) —
    monta o contexto Jinja2 de `plano.html` a partir de um `SnapshotOrdem`
    REAL.

    Lei nº 3 (`plans/app-aluno.plan.md` §1): esta função só LÊ campos do
    snapshot — `getattr`/indexação/iteração sobre `snapshot.ORDEM_QUITACAO` e
    `snapshot.cenarios` — nunca soma, subtrai, multiplica ou divide um valor
    do snapshot. `PRAZO_TOTAL`/`CUSTO_FUTURO_TOTAL` vêm do `Cenario` do
    método RECOMENDADO (`snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]`
    — a mesma leitura por chave que `report/` já faria para qualquer outro
    campo do cenário escolhido, nunca um recálculo de prazo/custo por conta
    própria). A única contagem feita aqui é `len(ORDEM_QUITACAO)`, para
    "posição N de M" — contagem de itens de uma sequência para exibição,
    não aritmética sobre campo financeiro (`AC-42`, ver docstring do
    módulo).

    `cenario` (`EC-07`/`EC-09`), `acoes` (`ORDEM_ACOES`, `EC-07`) e
    `pendencias` (`EC-08`) são decididos/lidos sem cálculo — ver
    `decidir_cenario_apresentacao` e `_pendencias`. `RESULTADO_CAIXA_
    OBSERVADO` é repassado como TEXTO neutro (via `_formatar_valor_de_apoio`)
    — nenhuma palavra de rótulo é atribuída a ele aqui; a redação de
    `estabilizacao.html` é quem garante que "sobra" nunca o qualifica
    (`EC-09`).
    """
    cenario_recomendado = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]
    total_de_posicoes = len(snapshot.ORDEM_QUITACAO)  # contagem de itens, não valor financeiro

    ordem = tuple(
        ContextoPosicao(
            posicao=posicao_do_snapshot.posicao,
            indice=indice,
            total=total_de_posicoes,
            DIVIDA_ID=posicao_do_snapshot.DIVIDA_ID,
            JUSTIFICATIVA_POSICAO=posicao_do_snapshot.JUSTIFICATIVA_POSICAO,
            # `T-177`: rótulo em português do aluno (de
            # `textos-canonicos.yaml`) e valor com unidade. Sem rótulo
            # cadastrado, o nome técnico aparece — visível, nunca um
            # rótulo inventado aqui.
            valores_de_apoio=tuple(
                (
                    textos.rotulos_de_apoio.get(nome, nome),
                    _apresentar_valor_de_apoio(nome, valor),
                )
                for nome, valor in posicao_do_snapshot.valores_de_apoio.items()
            ),
            # `T-177`: a redação ao aluno depende do MÉTODO recomendado (é
            # ele que define o critério de ordenação) e de a posição ser a
            # PRIMEIRA — a dívida em ataque agora — ou uma das seguintes.
            explicacao=textos.explicacao_da_posicao.get(
                snapshot.METODO_RECOMENDADO_PIQ.value, {}
            ).get("primeira" if indice == 1 else "seguintes", ""),
        )
        for indice, posicao_do_snapshot in enumerate(snapshot.ORDEM_QUITACAO, start=1)
    )

    return ContextoPlano(
        titulo=textos.titulo,
        corpo=textos.corpo,
        ordem=ordem,
        # `T-177`: com unidade. `PRAZO_TOTAL` é contagem de meses (`int`),
        # não `Decimal` — não passa por formatação monetária.
        PRAZO_TOTAL=_formatar_meses(cenario_recomendado.PRAZO_TOTAL),
        CUSTO_FUTURO_TOTAL=formatar_dinheiro_br(cenario_recomendado.CUSTO_FUTURO_TOTAL),
        ENGINE_VERSION=snapshot.ENGINE_VERSION,
        PARAMETROS_VERSION=snapshot.PARAMETROS_VERSION,
        cenario=decidir_cenario_apresentacao(snapshot),
        acoes=_contexto_acoes(snapshot),
        pendencias=_pendencias(snapshot, textos.rotulos_de_pendencia),
        MODO_ESTABILIZACAO=snapshot.diagnostico.MODO_ESTABILIZACAO,
        # `T-177`: com `R$`. O template de estabilização deixou de
        # prefixá-lo — o valor chega pronto.
        RESULTADO_CAIXA_OBSERVADO=formatar_dinheiro_br(
            snapshot.diagnostico.RESULTADO_CAIXA_OBSERVADO
        ),
        reserva_mobilizavel=_reserva_mobilizavel(snapshot),
    )
