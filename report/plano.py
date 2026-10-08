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
formatação aplicada é `_apresentar_dado` (abaixo; reescrita em `T-326`,
`RF-111`: rótulo em português, R$, %, dd/mm/aaaa, opção pelo rótulo do
registro, item composto descrito campo a campo). Regra mais importante:
um campo `DinheiroTalvez`/`TaxaTalvez`/`int | Desconhecido` marcado como
desconhecido pelo motor continua visivelmente desconhecido para o revisor
("Não informado") — nunca `0` ou vazio —, do contrário ele julgaria o caso
por um dado que nunca existiu (`RF-16`).

**T-115 — `_reserva_mobilizavel` (`RF-43`, `AC-70`, `EC-18`).** Quando o aluno
responde que prefere decidir depois quanto da reserva quer usar, a §13.1
(Regra 3) faz `Diagnostico.RESERVA_MOBILIZAVEL` valer `DESCONHECIDO` — e é
enfática: *"o estado DESCONHECIDA não é convertido silenciosamente em zero
como informação. A engine registra a pendência."* Exibir `R$ 0,00` aí seria
mentir para o aluno: "não decidi ainda" e "não tenho nada" são coisas
diferentes, e a segunda leitura o levaria a achar que não tem reserva alguma.

A convenção seguida é a de `_pendencias`/`ContextoPendencias`/
`pendencias.html` — a da tela do **ALUNO** —, não a de
`_apresentar_dado`, que é a convenção da tela do **REVISOR** (`RF-26`/
`AC-29`): adequada lá, inadequada aqui. Como em `_pendencias`, o `.py` faz apenas a
leitura pura (`is DESCONHECIDO`, sem aritmética e sem inferência) e o texto
em português vive no template. Esta camada não reimplementa nenhuma das três
regras da §13.1: o valor chega DERIVADO do motor
(`engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`, invocado por
`engine/diagnostico.py`), e aqui só se decide COMO mostrá-lo.

REGRAS: `RF-20`, `RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-42`,
`EC-07`, `EC-08`, `EC-09`, `RF-26`, `AC-29`, `RF-43`, `AC-70`, `EC-18`
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Final

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
    #: Por `NIVEL_COMPROVACAO` (+ `NAO_INFORMADO`) — `RF-91`, `T-267`.
    rotulos_de_comprovacao: Mapping[str, str] = field(default_factory=dict)
    #: `titulo`/`explicacao` da seção do cenário adicional — `RF-98`,
    #: `T-276`; aplicada, pendente de validação do especialista (`T-289`).
    cenario_adicional: Mapping[str, str] = field(default_factory=dict)
    #: `RF-82` (`T-245`) — orientação por dívida com seguro prestamista;
    #: aplicada, pendente de validação do especialista (`T-289`).
    orientacao_seguro_prestamista: str = ""
    #: `RF-111` (`T-326`) — "{tipo} — {credor}": como a dívida é chamada no
    #: plano e na conferência, no lugar do `DIVIDA_ID`.
    nome_da_divida: str = ""
    #: `RF-111` (`T-328`) — o diferencial de nomes repetidos: "{nome} ·
    #: parcela {parcela}" e, sem parcela, "{nome} · {ordinal}".
    nome_com_parcela: str = ""
    nome_com_ordinal: str = ""
    #: `RF-111` (`T-306`) — por `TIPO_ACAO`, o que o aluno precisa fazer. A
    #: `descricao` do motor (motivo do gate) fica para o revisor.
    descricao_da_acao: Mapping[str, str] = field(default_factory=dict)
    #: `RF-111` (`T-326`) — campo de `EstadoFinanceiro` (e do que ele
    #: contém) → rótulo curto na conferência.
    rotulos_de_dados: Mapping[str, str] = field(default_factory=dict)
    #: `RF-111` (`T-326`) — código sem opção no registro (método, status,
    #: cenário, evento de recálculo, domínios do motor) → rótulo.
    rotulos_de_codigos: Mapping[str, str] = field(default_factory=dict)
    #: `T-330` (`RF-111`) — por `METODO`, o critério da ordem em uma frase,
    #: mostrado uma vez no destaque do método (não por posição).
    criterio_do_metodo: Mapping[str, str] = field(default_factory=dict)
    #: Plano amigável (2026-10-03) — frase de apoio a cada número do resumo
    #: do topo ("prazo", "valor_mensal", "custo_futuro"). Sugestão, a
    #: validar pelo especialista.
    resumo: Mapping[str, str] = field(default_factory=dict)
    #: Plano amigável — explica que "Mês 1" é relativo ao início do
    #: acompanhamento do aluno, nunca um mês do calendário.
    explicacao_mes_1: str = ""
    #: Plano amigável — "Como o seu plano funciona": titulo + por `METODO`,
    #: uma lista de passos em português. Sugestão, a validar.
    como_funciona_titulo: str = ""
    como_funciona: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: Rótulos curtos ("Mês"…), usados no plano e no cenário adicional.
    grade_meses: Mapping[str, str] = field(default_factory=dict)
    #: Revisão de redação e design (2026-10-03) — cabeçalho personalizado,
    #: títulos das seções do documento, "Seu ponto de partida", títulos
    #: curtos dos quadros de "Como funciona", textos do cartão de cada
    #: dívida.
    cabecalho: Mapping[str, str] = field(default_factory=dict)
    secoes: Mapping[str, str] = field(default_factory=dict)
    ponto_de_partida: Mapping[str, str] = field(default_factory=dict)
    como_funciona_rotulos: tuple[str, ...] = ()
    textos_das_dividas: Mapping[str, str] = field(default_factory=dict)
    #: Nome curto do tipo de dívida no plano, por `TIPO_DIVIDA` — tem
    #: prioridade sobre o rótulo da opção de `B5.A02` (texto de pergunta).
    rotulo_do_tipo_no_plano: Mapping[str, str] = field(default_factory=dict)
    #: `T-379` — nome ainda mais curto do tipo ("Cheque", "Cartão") e do credor
    #: sem o "Banco", para o quadro de cada bloco do capítulo 5.
    nome_curto_do_tipo: Mapping[str, str] = field(default_factory=dict)
    prefixos_do_credor: tuple[str, ...] = ()
    nome_curto: str = ""
    #: Plano amigável — frase de apoio ao valor da reserva mobilizável.
    #: Sugestão, a validar.
    reserva_explicacao: str = ""
    #: Plano amigável (`RF-92`-adjacente) — por campo material da dívida,
    #: onde o aluno encontra o dado que falta, e o `ID_PERGUNTA` do Bloco 5
    #: que grava esse campo (para o link "Responder agora").
    onde_achar: Mapping[str, str] = field(default_factory=dict)
    pergunta_do_campo: Mapping[str, str] = field(default_factory=dict)
    #: Plano amigável — lista fixa de (pergunta, resposta). Sugestão, a
    #: validar.
    duvidas: tuple[tuple[str, str], ...] = ()
    #: Plano amigável — nota de rodapé "Sobre este plano". Sugestão, a
    #: validar.
    sobre_este_plano: str = ""
    #: Plano amigável — "titulo"/"texto" do bloco de estabilização
    #: (`{valor}` é `RESULTADO_CAIXA_OBSERVADO` já formatado). Sugestão, a
    #: validar; nunca usa a palavra "sobra" (GAB-04).
    estabilizacao: Mapping[str, str] = field(default_factory=dict)
    #: T-352 a T-354 — introdução e quadro de aulas do curso de entrada
    #: (Servidor Sem Dívidas), a nota de incômodo e o aviso de "sem valor
    #: extra". Aninhado como vem do YAML; lido por `_contexto_do_curso`.
    curso_ssd: Mapping[str, Any] = field(default_factory=dict)
    prognostico: Mapping[str, str] = field(default_factory=dict)
    incomodo: Mapping[str, str] = field(default_factory=dict)
    sem_valor_extra: str = ""


@dataclass(frozen=True, slots=True)
class VocabularioDoCaso:
    """`RF-111` (`T-326`) — o que o relatório precisa, além do snapshot,
    para falar a língua de quem lê: o rótulo de cada opção do registro
    (`VARIAVEL_GRAVADA` → `valor_interno` → `rotulo`) e o credor de cada
    ficha de dívida. Montado pela aplicação (`report/` não lê registro nem
    resposta); vazio, os nomes caem no rótulo gerado do código."""

    rotulos_de_opcao: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    credores: Mapping[str, str] = field(default_factory=dict)


def rotulo_de_codigo(rotulos: Mapping[str, str], codigo: str) -> str:
    """`RF-111` (`T-326`) — o rótulo cadastrado ou, sem ele, um legível
    gerado do código (`TAXA_EFETIVA_MENSAL_NORMALIZADA` → "Taxa efetiva
    mensal normalizada"). Nunca quebra; o teste de `AC-174` é quem cobra o
    rótulo que falta."""
    return rotulos.get(codigo) or codigo.replace("_", " ").strip().capitalize()


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

    # Plano amigável — `como_funciona` é aninhado: método → lista de passos.
    como_funciona_bruto = bruto.get("como_funciona") or {}
    como_funciona = {
        str(metodo): tuple(str(passo) for passo in passos)
        for metodo, passos in como_funciona_bruto.items()
        if metodo != "titulo"
    }

    duvidas_bruto = bruto.get("duvidas") or []
    duvidas = tuple((str(item["pergunta"]), str(item["resposta"])) for item in duvidas_bruto)

    estabilizacao_bruto = bruto.get("estabilizacao") or {}

    return TextosCanonicosPlano(
        titulo=str(bruto["titulo"]),
        corpo=str(bruto["corpo"]),
        rotulos_de_apoio=_mapa("rotulos_de_apoio"),
        explicacao_da_posicao=explicacoes,
        rotulos_de_pendencia=_mapa("rotulos_de_pendencia"),
        rotulos_de_comprovacao=_mapa("rotulos_de_comprovacao"),
        cenario_adicional=_mapa("cenario_adicional"),
        orientacao_seguro_prestamista=str(bruto.get("orientacao_seguro_prestamista") or ""),
        nome_da_divida=str(bruto.get("nome_da_divida") or ""),
        nome_com_parcela=str(bruto.get("nome_com_parcela") or ""),
        nome_com_ordinal=str(bruto.get("nome_com_ordinal") or ""),
        descricao_da_acao=_mapa("descricao_da_acao"),
        rotulos_de_dados=_mapa("rotulos_de_dados"),
        rotulos_de_codigos=_mapa("rotulos_de_codigos"),
        criterio_do_metodo=_mapa("criterio_do_metodo"),
        resumo=_mapa("resumo"),
        explicacao_mes_1=str(bruto.get("explicacao_mes_1") or ""),
        como_funciona_titulo=str((bruto.get("como_funciona") or {}).get("titulo") or ""),
        como_funciona=como_funciona,
        grade_meses=_mapa("grade_meses"),
        cabecalho=_mapa("cabecalho"),
        secoes=_mapa("secoes"),
        ponto_de_partida=_mapa("ponto_de_partida"),
        como_funciona_rotulos=tuple(
            str(rotulo) for rotulo in (bruto.get("como_funciona_rotulos") or [])
        ),
        textos_das_dividas=_mapa("dividas"),
        rotulo_do_tipo_no_plano=_mapa("rotulo_do_tipo_no_plano"),
        nome_curto_do_tipo=_mapa("nome_curto_do_tipo"),
        prefixos_do_credor=tuple(str(p) for p in (bruto.get("prefixos_do_credor") or [])),
        nome_curto=str(bruto.get("nome_curto") or ""),
        reserva_explicacao=str(bruto.get("reserva_explicacao") or ""),
        onde_achar=_mapa("onde_achar"),
        pergunta_do_campo=_mapa("pergunta_do_campo"),
        duvidas=duvidas,
        sobre_este_plano=str(bruto.get("sobre_este_plano") or ""),
        estabilizacao={str(k): str(v) for k, v in estabilizacao_bruto.items()},
        curso_ssd=dict(bruto.get("curso_ssd") or {}),
        prognostico=_mapa("prognostico"),
        incomodo=_mapa("incomodo"),
        sem_valor_extra=str(bruto.get("sem_valor_extra") or ""),
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


def formatar_escala_br(valor: Decimal | int) -> str:
    """`Decimal('6.00')` → `6 de 10` — `T-177`.

    `PESO_EMOCIONAL` é `ESCALA_0_10`, e o motor o carrega como `Decimal`
    para caber no mesmo mapa dos valores monetários. Exibi-lo como `6.00`
    sugere precisão decimal que a escala não tem; `6 de 10` diz o que o
    número é.
    """
    return f"{int(valor)} de 10"


#: `T-326` — dados inteiros que são `ESCALA_0_10`: "6 de 10", não "6".
_ESCALAS: Final[frozenset[str]] = frozenset(
    {"PESO_EMOCIONAL", "NECESSIDADE_VITORIA", "AUTOPERCEPCAO_CONTROLE"}
)

#: `T-326` — identificadores dos itens: vão ao revisor como detalhe
#: (`DIVIDA_ID` no cabeçalho da dívida), nunca como dado de entrada.
_CAMPOS_IDENTIFICADORES: Final[frozenset[str]] = frozenset({"DIVIDA_ID", "ITEM_ID"})


def _rotulo_de_opcao(
    nome: str, codigo: str, textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> str:
    """`RF-111` — o código de uma opção: primeiro o `rotulo` da opção no
    registro (a pergunta que grava `nome`); sem ela, o glossário."""
    return vocabulario.rotulos_de_opcao.get(nome, {}).get(codigo) or rotulo_de_codigo(
        textos.rotulos_de_codigos, codigo
    )


def _apresentar_dado(
    nome: str, valor: object, textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> str:
    """T-70 (`RF-26`, `AC-29`), reescrita em `T-326` (`RF-111`) — um campo
    de `EstadoFinanceiro` (ou do que ele contém) como o revisor o lê.

    - `Desconhecido` → "Não informado" — nunca `0` nem vazio (`RF-16`).
    - `None` → "—": ausência ESTRUTURAL (campo que nem se aplica), distinta
      de `DESCONHECIDO` — as duas ausências seguem com textos diferentes.
    - `Decimal` → taxa em % (`formatar_taxa_br`), escala ou dinheiro em R$:
      todo outro `Decimal` de `EstadoFinanceiro` é `Dinheiro`/`DinheiroTalvez`.
    - `date` → dd/mm/aaaa; `bool` → Sim/Não.
    - `Enum`/`str` → rótulo da opção do registro ou do glossário.
    - conjunto → rótulos separados por vírgula.
    - item composto (`RecursoExtraordinario`, `Oportunidade`…) → descrito
      campo a campo; tupla deles, item a item. Nunca a representação Python.
    """
    codigos = textos.rotulos_de_codigos
    if isinstance(valor, Desconhecido):
        return rotulo_de_codigo(codigos, "DESCONHECIDO")
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return rotulo_de_codigo(codigos, "SIM" if valor else "NAO")
    if isinstance(valor, Decimal):
        formato = _FORMATO_DE_APOIO.get(nome)
        if formato == "taxa":
            return formatar_taxa_br(valor)
        if formato == "escala":
            return formatar_escala_br(valor)
        return formatar_dinheiro_br(valor)
    if isinstance(valor, int):
        return formatar_escala_br(valor) if nome in _ESCALAS else str(valor)
    if isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    if isinstance(valor, Enum):
        return _rotulo_de_opcao(nome, str(valor.value), textos, vocabulario)
    if isinstance(valor, str):
        return _rotulo_de_opcao(nome, valor, textos, vocabulario)
    if isinstance(valor, (frozenset, set)):
        rotulos = sorted(_rotulo_de_opcao(nome, str(v), textos, vocabulario) for v in valor)
        return ", ".join(rotulos) or rotulo_de_codigo(codigos, "NENHUM")
    if isinstance(valor, tuple):
        itens = [_descrever_item(item, textos, vocabulario) for item in valor]
        return "; ".join(itens) or rotulo_de_codigo(codigos, "NENHUM")
    if is_dataclass(valor):
        return _descrever_item(valor, textos, vocabulario)
    return str(valor)


def _descrever_item(
    item: object, textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> str:
    """`T-326` — "Valor: R$ 15.000,00 · Quando: 1–3 meses · …": cada campo
    do item com rótulo e valor legível, sem o identificador."""
    return " · ".join(
        f"{rotulo_de_codigo(textos.rotulos_de_dados, campo.name)}: "
        f"{_apresentar_dado(campo.name, getattr(item, campo.name), textos, vocabulario)}"
        for campo in fields(item)  # type: ignore[arg-type]
        if campo.name not in _CAMPOS_IDENTIFICADORES
    )


@dataclass(frozen=True, slots=True)
class ContextoCampo:
    """Um campo de `EstadoFinanceiro`/`Divida`/`PerfilComportamental`/
    `SinaisComportamentais`, pronto para o revisor (`T-326`): `nome` é o
    rótulo em português, `valor` o texto legível e `codigo` o nome técnico
    (idêntico ao da spec canônica, `sdd.config.md` §7), mostrado só como
    detalhe."""

    nome: str
    valor: str
    codigo: str


def _campos_de_apoio(
    instancia: object, textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> tuple[ContextoCampo, ...]:
    """T-70 — todos os campos de uma dataclass `frozen` do motor
    (`EstadoFinanceiro`, `Divida`, `PerfilComportamental`,
    `SinaisComportamentais`), na ordem declarada. Leitura genérica por
    `dataclasses.fields`/`getattr` — nenhum campo é escolhido a dedo, nenhum
    é omitido além do identificador (`T-326`), que vai no cabeçalho."""
    return tuple(
        ContextoCampo(
            nome=rotulo_de_codigo(textos.rotulos_de_dados, campo.name),
            valor=_apresentar_dado(campo.name, getattr(instancia, campo.name), textos, vocabulario),
            codigo=campo.name,
        )
        for campo in fields(instancia)  # type: ignore[arg-type]
        if campo.name not in _CAMPOS_IDENTIFICADORES
        and campo.name not in _CAMPOS_ESTADO_COM_SECAO_PROPRIA
    )


@dataclass(frozen=True, slots=True)
class ContextoDivida:
    """Uma `Divida` de `estado_inputs.dividas`, com TODOS os seus campos
    formatados para exibição ao revisor (`RF-26`, `AC-29`) — inclusive os
    que são `Desconhecido` (`GAB-03`/`AC-08`). `nome` é "tipo — credor"
    (`T-326`); `DIVIDA_ID`, o detalhe."""

    DIVIDA_ID: str
    nome: str
    campos: tuple[ContextoCampo, ...]


@dataclass(frozen=True, slots=True)
class ContextoEstadoInputs:
    """T-70 (`RF-26`, `AC-29`) — os `estado_inputs` (`EstadoFinanceiro`)
    completos que produziram o snapshot. `campos` cobre os campos
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


def nomear_dividas(
    dividas: Iterable[Divida], textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> dict[str, str]:
    """`RF-111` (`T-326`) — `DIVIDA_ID` → "Cheque especial — CAIXA
    ECONOMICA FEDERAL". O tipo é o do snapshot, pelo rótulo da opção de
    `B5.A02`; o credor, a resposta de `CREDOR` — o mesmo par que o alerta de
    inventário mostra (`T-324`). Sem credor, só o tipo.

    `T-328`: nomes repetidos (9 consignados CAIXA) ganham a parcela
    ("· parcela R$ 292,55"); o que ainda repete (sem parcela, ou parcela
    igual) ganha o ordinal na ordem de `dividas` ("· 2"). Todo chamador
    passa `estado_inputs.dividas`, então o nome é o mesmo no plano, no PDF
    e na conferência."""
    dividas = tuple(dividas)
    nomes: dict[str, str] = {}
    for divida in dividas:
        # Revisão de redação (2026-10-03): o nome curto do plano vem antes
        # do rótulo da pergunta (`B5.A02`), que traz travessão ("Cartão de
        # crédito — saldo rotativo") e não deve ser editado para caber aqui.
        tipo = textos.rotulo_do_tipo_no_plano.get(divida.TIPO_DIVIDA.value) or _rotulo_de_opcao(
            "TIPO_DIVIDA", divida.TIPO_DIVIDA.value, textos, vocabulario
        )
        credor = vocabulario.credores.get(divida.DIVIDA_ID)
        nomes[divida.DIVIDA_ID] = (
            textos.nome_da_divida.format(tipo=tipo, credor=credor)
            if credor and textos.nome_da_divida
            else tipo
        )

    repetidos = Counter(nomes.values())
    for divida in dividas:
        nome = nomes[divida.DIVIDA_ID]
        parcela = divida.PARCELA_CONTRATUAL
        if repetidos[nome] > 1 and isinstance(parcela, Decimal) and textos.nome_com_parcela:
            nomes[divida.DIVIDA_ID] = textos.nome_com_parcela.format(
                nome=nome, parcela=formatar_dinheiro_br(parcela)
            )

    repetidos = Counter(nomes.values())
    ordinais: Counter[str] = Counter()
    for divida in dividas:
        nome = nomes[divida.DIVIDA_ID]
        if repetidos[nome] > 1 and textos.nome_com_ordinal:
            ordinais[nome] += 1
            nomes[divida.DIVIDA_ID] = textos.nome_com_ordinal.format(
                nome=nome, ordinal=ordinais[nome]
            )
    return nomes


def nomear_dividas_curtas(
    dividas: Iterable[Divida], textos: TextosCanonicosPlano, vocabulario: VocabularioDoCaso
) -> dict[str, str]:
    """`T-379` — `DIVIDA_ID` → "Cheque Itaú": tipo curto + credor sem o "Banco".
    Só para o quadro do capítulo 5, onde o número do círculo já distingue duas
    dívidas de mesmo nome curto. Tipo sem nome curto cai no nome do plano."""
    nomes: dict[str, str] = {}
    for divida in dividas:
        codigo = divida.TIPO_DIVIDA.value
        tipo = (
            textos.nome_curto_do_tipo.get(codigo)
            or textos.rotulo_do_tipo_no_plano.get(codigo)
            or _rotulo_de_opcao("TIPO_DIVIDA", codigo, textos, vocabulario)
        )
        credor = vocabulario.credores.get(divida.DIVIDA_ID)
        for prefixo in textos.prefixos_do_credor:
            if credor and credor.lower().startswith(prefixo.lower()):
                credor = credor[len(prefixo) :].strip()
                break
        nomes[divida.DIVIDA_ID] = (
            textos.nome_curto.format(tipo=tipo, credor=credor)
            if credor and textos.nome_curto
            else tipo
        )
    return nomes


def montar_contexto_estado_inputs(
    estado: EstadoFinanceiro,
    textos: TextosCanonicosPlano,
    vocabulario: VocabularioDoCaso | None = None,
) -> ContextoEstadoInputs:
    """T-70 (`RF-26`, `AC-29`) — monta o contexto de exibição de
    `estado_inputs` para o revisor, a partir de um `EstadoFinanceiro` REAL
    (`SnapshotOrdem.estado_inputs`). Lei nº 3: só LÊ campos por `getattr`,
    nunca calcula nada — cada valor passa por `_apresentar_dado`, que é
    quem decide a formatação (`T-326`: rótulo e valor legíveis)."""
    vocabulario = vocabulario or VocabularioDoCaso()
    nomes = nomear_dividas(estado.dividas, textos, vocabulario)

    return ContextoEstadoInputs(
        campos=_campos_de_apoio(estado, textos, vocabulario),
        perfil_comportamental=_campos_de_apoio(estado.perfil_comportamental, textos, vocabulario),
        sinais_comportamentais=_campos_de_apoio(estado.sinais_comportamentais, textos, vocabulario),
        dividas=tuple(
            ContextoDivida(
                DIVIDA_ID=divida.DIVIDA_ID,
                nome=nomes[divida.DIVIDA_ID],
                campos=_campos_de_apoio(divida, textos, vocabulario),
            )
            for divida in estado.dividas
        ),
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
    #: `T-306`: o que o aluno precisa fazer, por `TIPO_ACAO`.
    descricao: str
    prioridade_excepcional: bool
    #: `T-326`: "tipo — credor"; `None` na ação sem dívida (economia).
    nome_divida: str | None = None
    #: `T-306`: a `descricao` do motor (motivo do gate) — só ao revisor.
    motivo: str = ""


def _contexto_acoes(
    snapshot: SnapshotOrdem, textos: TextosCanonicosPlano, nomes: Mapping[str, str]
) -> tuple[ContextoAcaoRequerida, ...]:
    """`EC-07` — `ORDEM_ACOES` tal como o snapshot a devolveu, sem
    reordenar nem filtrar: leitura direta, campo a campo.

    T-92: `DIVIDA_ID` é repassado tal como veio de `AcaoRequerida` (`str |
    None`). `T-306`: a descrição ao aluno vem de `textos-canonicos.yaml` por
    `TIPO_ACAO`; o motivo técnico do gate segue em `motivo`."""
    return tuple(
        ContextoAcaoRequerida(
            DIVIDA_ID=acao.DIVIDA_ID,
            descricao=rotulo_de_codigo(textos.descricao_da_acao, acao.TIPO_ACAO),
            prioridade_excepcional=acao.prioridade_excepcional,
            nome_divida=None
            if acao.DIVIDA_ID is None
            else nomes.get(acao.DIVIDA_ID, acao.DIVIDA_ID),
            motivo=acao.descricao,
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
    #: (DIVIDA_ID, nome "tipo — credor" — `T-326`, campos)
    campos_faltantes_por_divida: tuple[tuple[str, str, tuple[str, ...]], ...]


def _campos_desconhecidos_da_divida(divida: Divida) -> tuple[str, ...]:
    """`EC-08` — os nomes dos campos materiais desta `Divida` cujo valor é
    `DESCONHECIDO`, na ordem declarada em `_CAMPOS_MATERIAIS_DA_DIVIDA`.
    Comparação `is DESCONHECIDO` pura — nenhuma aritmética, nenhuma
    inferência sobre o valor (`RF-16`)."""
    return tuple(
        campo for campo in _CAMPOS_MATERIAIS_DA_DIVIDA if getattr(divida, campo) is DESCONHECIDO
    )


def _pendencias(
    snapshot: SnapshotOrdem,
    rotulos: Mapping[str, str] | None = None,
    nomes: Mapping[str, str] | None = None,
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
    nomes = nomes or {}

    campos_faltantes_por_divida = tuple(
        (
            divida.DIVIDA_ID,
            nomes.get(divida.DIVIDA_ID, divida.DIVIDA_ID),
            tuple(traduzir.get(campo, campo) for campo in campos_da_divida),
        )
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
    `"Desconhecido.DESCONHECIDO"`. E também não usa `_apresentar_dado`,
    que é a convenção da tela do REVISOR (`RF-26`/`AC-29`) — adequada lá,
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
    #: `T-326`: "tipo — credor" — o título da posição; o código é detalhe.
    nome: str
    #: Texto de AUDITORIA, do motor — vai só ao revisor (`RF-26`/`AC-29`;
    #: `T-305`). O próprio `engine/ordem.py` o declara "não prosa de usuário
    #: final".
    JUSTIFICATIVA_POSICAO: str
    valores_de_apoio: tuple[tuple[str, str], ...]  # (rótulo ao aluno, valor formatado)
    #: `T-177` — por que esta dívida vem nesta posição, dito ao ALUNO. Todo
    #: método tem redação (`test_todo_metodo_do_motor_tem_explicacao_ao_
    #: aluno`); `T-305` tirou o fallback para a justificativa técnica.
    explicacao: str = ""
    #: `T-304` (`DE-08`) — mês previsto de quitação, LIDO do cronograma
    #: gravado (`meses_de_quitacao`); `None` = não disponível.
    mes_de_quitacao: int | None = None
    #: Revisão de design (2026-10-03) — os números que o aluno quer ver em
    #: TODA dívida, qualquer que seja o método: quanto deve hoje, a parcela
    #: que paga hoje e a taxa de juros. `valores_de_apoio` varia por método
    #: (é o que sustenta a POSIÇÃO, `AC-17`) e continua existindo; estes são
    #: lidos de `estado_inputs.dividas`, com "não informado" quando o dado é
    #: `DESCONHECIDO` (nunca zero, `RF-16`). (rótulo, valor formatado).
    fatos: tuple[tuple[str, str], ...] = ()
    #: T-354 — a nota de incômodo que o ALUNO deu a esta dívida, lida de
    #: `Divida.PESO_EMOCIONAL` (vazia se desconhecida) e, quando a nota é
    #: alta e a dívida não é a primeira, o aviso de que a ordem seguiu o
    #: critério do método. Texto, nunca regra de ordem.
    incomodo: str = ""
    aviso_incomodo: str = ""


@dataclass(frozen=True, slots=True)
class ContextoCursoSSD:
    """T-352/T-353 — introdução, quadro de aulas e orientações em texto, tudo
    de `textos-canonicos.yaml` (só o que consta nas legendas do curso). A
    escolha das aulas é um lookup por método/cenário: nenhuma conta."""

    #: Primeira página: como este documento se liga ao curso (T-355).
    apresentacao_titulo: str
    apresentacao: tuple[str, ...]
    introducao_titulo: str
    introducao: str
    quadro_titulo: str
    aulas: tuple[tuple[str, str, str], ...]  # (número, título, por que ajuda)
    melhorar_titulo: str
    melhorar_intro: str
    melhorar: tuple[tuple[str, str], ...]  # (orientação, aula)


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
    #: Plano amigável (2026-10-03) — o mesmo `Cenario.PRAZO_TOTAL` do
    #: método recomendado, como `int` cru: serve só à GEOMETRIA dos
    #: gráficos de `visuais.html` (posição relativa de uma barra/marca),
    #: nunca exibido como número — o texto que o aluno lê continua sendo
    #: `PRAZO_TOTAL` (acima), já formatado. Ver "Regra de geometria" no
    #: cabeçalho de `visuais.html`.
    PRAZO_TOTAL_INT: int
    ENGINE_VERSION: str
    PARAMETROS_VERSION: str
    cenario: CENARIO_APRESENTACAO
    acoes: tuple[ContextoAcaoRequerida, ...]
    pendencias: ContextoPendencias | None
    MODO_ESTABILIZACAO: bool
    RESULTADO_CAIXA_OBSERVADO: str
    reserva_mobilizavel: ContextoReservaMobilizavel
    #: `RF-98`/`AC-152` (`T-276`): seção à parte, NUNCA misturada aos campos
    #: acima — que continuam lidos só do cenário recomendado.
    cenario_adicional: ContextoCenarioAdicional | None = None
    nao_projetados: tuple[tuple[str, str], ...] = ()  # (ITEM_ID, motivo) — EC-38
    #: `T-304` (`DE-08`) — `diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA`, a
    #: capacidade que alimenta o cronograma (`AC-07`), formatada.
    valor_mensal_destinado: str = ""
    #: `T-326` (`RF-111`) — rótulos do método recomendado e do cenário de
    #: apresentação; o código continua em `cenario`, para os templates.
    metodo: str = ""
    rotulo_do_cenario: str = ""
    #: Revisão de design (2026-10-03) — personalização: o primeiro nome do
    #: aluno (`None` sem nome na conta) e os números do mês dele.
    nome_do_aluno: str | None = None
    ponto_de_partida: ContextoPontoDePartida | None = None
    #: Plano amigável — "Como o seu plano funciona", por método — lido de
    #: `textos.como_funciona`, uma lista de passos em português.
    como_funciona: tuple[str, ...] = ()
    #: Plano amigável (`RF-92`-adjacente) — pendências com "onde achar" e o
    #: `ID_PERGUNTA` do Bloco 5, para o botão "Responder agora".
    pendencias_acionaveis: tuple[ContextoPendenciaAcionavel, ...] = ()
    #: T-352/T-353 — o curso de entrada; `None` se o YAML não o declara.
    curso_ssd: ContextoCursoSSD | None = None
    #: `RF-77`/`RF-78` — "Seu prognóstico: três caminhos"; `None` sem prognóstico.
    prognostico: ContextoPrognostico | None = None
    #: `T-375` — "Quando cada dívida termina", dentro de "Seu plano em números".
    quando_termina: ContextoQuandoTermina | None = None
    #: T-352 — plano normal sem valor extra no mês (capacidade 0, sem
    #: estabilização): o aviso ao aluno; vazio nos demais casos.
    aviso_sem_valor_extra: str = ""


@dataclass(frozen=True, slots=True)
class ContextoAporte:
    """Um item projetado no cenário adicional — `mes` e valor LIDOS do
    `AporteProjetado` do snapshot."""

    ITEM_ID: str
    mes: int
    valor: str


@dataclass(frozen=True, slots=True)
class ContextoCenarioAdicional:
    """`RF-98`, `AC-152` (`T-276`) — a segunda projeção do motor
    (`CenarioAdicional`, com os `PROVAVEL` e `POSSIVEL`), só LIDA de
    `snapshot.projecao_extraordinarios` e formatada. Nenhuma aritmética
    (`AC-42`)."""

    rotulo: str
    explicacao: str
    PRAZO_TOTAL: str
    CUSTO_FUTURO_TOTAL: str
    ordem: tuple[str, ...]
    itens: tuple[ContextoAporte, ...]


def _cenario_adicional(
    snapshot: SnapshotOrdem, textos: TextosCanonicosPlano, nomes: Mapping[str, str]
) -> ContextoCenarioAdicional | None:
    """`None` quando o motor não projetou cenário adicional."""
    adicional_do_snapshot = snapshot.projecao_extraordinarios.cenario_adicional
    if adicional_do_snapshot is None:
        return None
    return ContextoCenarioAdicional(
        rotulo=textos.cenario_adicional.get("titulo", ""),
        explicacao=textos.cenario_adicional.get("explicacao", ""),
        PRAZO_TOTAL=_formatar_meses(adicional_do_snapshot.PRAZO_TOTAL),
        CUSTO_FUTURO_TOTAL=formatar_dinheiro_br(adicional_do_snapshot.CUSTO_FUTURO_TOTAL),
        ordem=tuple(nomes.get(d, d) for d in adicional_do_snapshot.ORDEM_QUITACAO),
        itens=tuple(
            ContextoAporte(
                ITEM_ID=aporte.ITEM_ID,
                mes=aporte.mes,
                valor=formatar_dinheiro_br(aporte.VALOR_DESTINADO),
            )
            for aporte in adicional_do_snapshot.aportes
        ),
    )


def meses_de_quitacao(snapshot: SnapshotOrdem) -> dict[str, int] | None:
    """`DE-08`, `RF-96` (`T-304`) — `DIVIDA_ID` → mês em que a dívida é
    quitada no cronograma GRAVADO do cenário recomendado: o
    `estado_final.mes` do mês em cuja `quitacoes` ela aparece. Só leitura
    (`AC-42`), nunca o motor de novo; `None` sem cenário recomendado, e a
    dívida que não quita dentro do horizonte não está no dicionário."""
    cenario = snapshot.cenarios.get(snapshot.METODO_RECOMENDADO_PIQ)
    if cenario is None:
        return None
    return {divida_id: mes.estado_final.mes for mes in cenario.meses for divida_id in mes.quitacoes}


@dataclass(frozen=True, slots=True)
class ContextoCaminho:
    """Uma linha do prognóstico; tudo já em texto (`RF-13`). `mes_fim`,
    `escala` são inteiros só para a GEOMETRIA da barra (razão de
    dois inteiros, como em `visuais.html`) — nunca exibidos como dado."""

    cor: str  # "vermelho" | "azul" | "verde"
    titulo: str
    veredito: str  # a frase que o aluno lê primeiro
    nota: str  # uma linha de explicação, em letra pequena
    marcador: str  # texto na ponta da barra ("dívida zero", "ainda deve R$ …")
    destaques: tuple[tuple[str, str], ...]  # até 3 (rótulo, valor)
    mes_fim: int
    escala: int
    #: `T-375` — (mês, número da dívida em "Suas dívidas") de cada quitação.
    #: Círculos desenhados na barra; vazio no vermelho (pedido do produto).
    marcos: tuple[tuple[int, int], ...] = ()
    #: Todas as quitações do caminho, para o mês a mês e a tabela.
    quitacoes: tuple[tuple[int, int], ...] = ()
    rotulo_curto: str = ""  # nome do caminho nas faixas e na tabela
    #: `T-378`/`T-379` — as dívidas que marcam a barra, em ordem de quitação:
    #: "M7 · Quita Cheque Itaú". Vazio no vermelho.
    itens: tuple[str, ...] = ()
    #: "Economia frente ao plano base: R$ …" — só no plano acelerado.
    economia: str = ""


@dataclass(frozen=True, slots=True)
class ContextoMesDetalhado:
    """`T-377` — um mês de um plano, para o mural e para o cartão do mês.
    `rotulo` é a referência ("Mês 01"), nunca uma data; `ancora` liga o bloco
    do mural ao cartão. Tudo já formatado: o app só lê (Lei nº 3)."""

    rotulo: str
    ancora: str
    divida_da_vez: tuple[int, str] | None  # (número em "Suas dívidas", nome)
    valor_extra: str
    saldo: str
    quitadas: tuple[tuple[int, str], ...]
    primeira_quitacao: bool
    ultimo: bool
    #: "Quita Cheque Itaú" por dívida quitada no mês (nome curto), para o mural.
    quitas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextoPlanoDetalhado:
    cor: str  # "azul" | "verde"
    titulo: str
    meses: tuple[ContextoMesDetalhado, ...]


@dataclass(frozen=True, slots=True)
class ContextoQuandoTermina:
    """`T-375` — "Quando cada dívida termina": uma linha por dívida (número,
    nome e o mês de quitação em cada caminho, já em texto)."""

    colunas: tuple[str, ...]
    linhas: tuple[tuple[int, str, tuple[str, ...]], ...]
    #: Cor de cada coluna, na ordem de `colunas` ("vermelho" | "azul" | "verde").
    cores: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextoPrognostico:
    titulo: str
    introducao: str
    caminhos: tuple[ContextoCaminho, ...]
    #: `T-377` — o plano seguido e (com valor extra) o acelerado, mês a mês.
    detalhes: tuple[ContextoPlanoDetalhado, ...] = ()


def _numeros_das_dividas(snapshot: SnapshotOrdem) -> dict[str, int]:
    """`DIVIDA_ID` → posição em "Suas dívidas" (a mesma de `ContextoPosicao.indice`)."""
    return {
        posicao.DIVIDA_ID: indice for indice, posicao in enumerate(snapshot.ORDEM_QUITACAO, start=1)
    }


def _marcos(
    quitacoes: Iterable[tuple[str, int]], numeros: Mapping[str, int]
) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((mes, numeros[d]) for d, mes in quitacoes if d in numeros))


def _com_marcos(
    caminho: ContextoCaminho,
    quitacoes: Iterable[tuple[str, int]],
    numeros: Mapping[str, int],
    nomes: Mapping[str, str],
    textos: Mapping[str, str],
) -> ContextoCaminho:
    """`T-375`/`T-379` — marcos da barra e o quadro de dívidas do bloco, uma linha
    por dívida ("M7 - Quita Cheque Itaú"), só no plano e no plano acelerado."""
    marcos = _marcos(quitacoes, numeros)
    nome_do = {numero: nomes.get(d, d) for d, numero in numeros.items()}
    modelo = textos.get("item_quita", "M{mes} · Quita {nome}")
    com_marcos = caminho.cor != "vermelho"
    return replace(
        caminho,
        marcos=marcos if com_marcos else (),
        quitacoes=marcos,
        rotulo_curto=textos.get(f"{caminho.cor}_curto", ""),
        itens=tuple(modelo.format(mes=mes, nome=nome_do[n]) for mes, n in marcos)
        if com_marcos
        else (),
    )


def _meses_detalhados(
    meses: Iterable[Any],
    cor: str,
    quitacoes_do_caminho: tuple[tuple[int, int], ...],
    numeros: Mapping[str, int],
    nomes: Mapping[str, str],
    textos: Mapping[str, str],
    nomes_curtos: Mapping[str, str],
) -> tuple[ContextoMesDetalhado, ...]:
    """`T-377` — um `ContextoMesDetalhado` por `MesDoPlano` do snapshot. Só
    formata e compara (rótulo "Mês 01" com zeros à esquerda, sem data)."""
    lista = tuple(meses)
    largura = max(2, len(str(len(lista))))
    mes_primeira = min((mes for mes, _ in quitacoes_do_caminho), default=None)
    palavra = textos.get("mes", "Mês")

    def _divida(divida_id: str) -> tuple[int, str]:
        return (numeros.get(divida_id, 0), nomes.get(divida_id, divida_id))

    return tuple(
        ContextoMesDetalhado(
            rotulo=f"{palavra} {item.MES:0{largura}d}",
            ancora=f"mes-{cor}-{item.MES:0{largura}d}",
            divida_da_vez=None if item.DIVIDA_ALVO is None else _divida(item.DIVIDA_ALVO),
            valor_extra=formatar_dinheiro_br(item.VALOR_EXTRA),
            saldo=formatar_dinheiro_br(item.SALDO_TOTAL),
            quitadas=tuple(_divida(d) for d in item.QUITACOES),
            primeira_quitacao=bool(item.QUITACOES) and item.MES == mes_primeira,
            ultimo=indice == len(lista),
            quitas=tuple(
                textos.get("texto_quita", "Quita {nome}").format(nome=nomes_curtos.get(d, d))
                for d in item.QUITACOES
            ),
        )
        for indice, item in enumerate(lista, start=1)
    )


def _quando_cada_divida_termina(
    snapshot: SnapshotOrdem,
    prognostico: ContextoPrognostico | None,
    nomes: Mapping[str, str],
    textos: TextosCanonicosPlano,
) -> ContextoQuandoTermina | None:
    """`T-375` — com prognóstico, uma coluna por caminho; sem ele (plano
    antigo), só a do plano, lida de `meses_de_quitacao`."""
    t = textos.prognostico
    if not snapshot.ORDEM_QUITACAO or snapshot.diagnostico.MODO_ESTABILIZACAO:
        return None
    numeros = _numeros_das_dividas(snapshot)
    if prognostico is not None:
        colunas = tuple((c.rotulo_curto, c.quitacoes, c.cor) for c in prognostico.caminhos)
    else:
        colunas = (
            (
                t.get("azul_curto", ""),
                _marcos((meses_de_quitacao(snapshot) or {}).items(), numeros),
                "azul",
            ),
        )
    mes = t.get("mes", "Mês")
    nao_acaba = t.get("nao_acaba", "")

    def _celula(marcos: tuple[tuple[int, int], ...], numero: int) -> str:
        quando = next((m for m, n in marcos if n == numero), None)
        return nao_acaba if quando is None else f"{mes} {quando}"

    return ContextoQuandoTermina(
        colunas=tuple(rotulo for rotulo, _, _ in colunas),
        cores=tuple(cor for _, _, cor in colunas),
        linhas=tuple(
            (
                numero,
                nomes.get(divida_id, divida_id),
                tuple(_celula(marcos, numero) for _, marcos, _ in colunas),
            )
            for divida_id, numero in numeros.items()
        ),
    )


def _prognostico(
    snapshot: Any,
    cenario_recomendado: Any,
    textos: TextosCanonicosPlano,
    nomes: Mapping[str, str],
    nomes_curtos: Mapping[str, str],
) -> ContextoPrognostico | None:
    """Monta as linhas (`_linhas_do_prognostico`) e acrescenta os marcos de
    quitação de cada caminho e o mês a mês (`T-375`)."""
    base = _linhas_do_prognostico(snapshot, cenario_recomendado, textos)
    if base is None:
        return None
    t = textos.prognostico
    prog = snapshot.prognostico
    numeros = _numeros_das_dividas(snapshot)
    quitacoes = {
        "vermelho": prog.sem_acao.QUITACOES,
        "azul": tuple((meses_de_quitacao(snapshot) or {}).items()),
        "verde": prog.com_extra.QUITACOES if prog.com_extra is not None else (),
    }
    caminhos = tuple(
        _com_marcos(c, quitacoes[c.cor], numeros, nomes_curtos, t) for c in base.caminhos
    )
    por_cor = {c.cor: c for c in caminhos}
    fontes = [("azul", prog.MESES_DO_PLANO)]
    if prog.com_extra is not None:
        fontes.append(("verde", prog.com_extra.MESES))
    detalhes = tuple(
        ContextoPlanoDetalhado(
            cor=cor,
            titulo=por_cor[cor].titulo,
            meses=_meses_detalhados(
                meses, cor, por_cor[cor].quitacoes, numeros, nomes, t, nomes_curtos
            ),
        )
        for cor, meses in fontes
        if meses
    )
    return replace(base, caminhos=caminhos, detalhes=detalhes)


def _sem_centavos(valor: str) -> str:
    """"R$ 600,00" → "R$ 600" (só formatação; com centavos, fica como está)."""
    return valor.removesuffix(",00")


def _linhas_do_prognostico(
    snapshot: Any, cenario_recomendado: Any, textos: TextosCanonicosPlano
) -> ContextoPrognostico | None:
    """`RF-77`/`RF-78` — LÊ `snapshot.prognostico` e o cenário recomendado; só
    formata e compara (nenhuma conta, `AC-42`: a diferença verde × azul vem
    pronta do motor). `None` sem prognóstico (snapshot antigo) ou em
    estabilização. Sem valor extra informado, só vermelho e azul."""
    t = textos.prognostico
    prog = snapshot.prognostico
    sem_ordem = snapshot.diagnostico.MODO_ESTABILIZACAO or not snapshot.ORDEM_QUITACAO
    if prog is None or not t or sem_ordem:
        return None
    sem = prog.sem_acao
    escala = max(1, sem.HORIZONTE_MESES)
    saldo = formatar_dinheiro_br(sem.SALDO_NO_HORIZONTE)

    def _mes(n: int) -> str:
        return f"{t.get('mes', 'Mês')} {n}"

    def _complemento(chave: str, valor: Any) -> str:
        """Frase "Até R$ … por mês"; ausente em snapshot anterior (sem o valor)."""
        return "" if valor is None else t.get(chave, "").format(total=formatar_dinheiro_br(valor))

    # Dívida inicial, primeira quitação prevista e, só com déficit, o que falta
    # por mês. A quitação só é afirmada quando é certa: nenhuma dívida quita
    # sozinha, ou o motor gravou o mês (snapshot anterior não grava).
    destaques_vermelho = [
        (t.get("rotulo_divida_inicial", ""), formatar_dinheiro_br(sem.SALDO_INICIAL_TOTAL))
    ]
    if sem.DIVIDAS_QUITADAS_SOZINHAS == 0:
        destaques_vermelho.append((t.get("rotulo_primeira_prevista", ""), t.get("nenhuma", "")))
    elif sem.MESES_PRIMEIRA_VITORIA is not None:
        destaques_vermelho.append(
            (t.get("rotulo_primeira_prevista", ""), _mes(sem.MESES_PRIMEIRA_VITORIA))
        )
    if sem.DEFICIT_MENSAL > 0:
        destaques_vermelho.append(
            (t.get("rotulo_falta_por_mes", ""), formatar_dinheiro_br(sem.DEFICIT_MENSAL))
        )
    elif sem.DIVIDAS_QUE_CRESCEM > 0:
        destaques_vermelho.append(
            (t.get("rotulo_dividas_crescem", ""), str(sem.DIVIDAS_QUE_CRESCEM))
        )
    zerado = sem.SALDO_NO_HORIZONTE == 0
    vermelho = ContextoCaminho(
        cor="vermelho",
        titulo=t.get("vermelho_titulo", ""),
        veredito=t.get("vermelho_veredito_zerado" if zerado else "vermelho_veredito", "").format(
            horizonte=sem.HORIZONTE_MESES, saldo=saldo
        ),
        nota=t.get("vermelho_nota", ""),
        marcador="",
        destaques=tuple(destaques_vermelho),
        mes_fim=escala,
        escala=escala,
    )

    estourou = cenario_recomendado.ESTOUROU_HORIZONTE
    azul_veredito = t.get("azul_veredito_nao_quita" if estourou else "azul_veredito", "").format(
        prazo=_formatar_meses(cenario_recomendado.PRAZO_TOTAL)
    )
    if not estourou:
        azul_veredito += _complemento("azul_complemento", prog.PAGAMENTO_MENSAL_PLANO)
    azul = ContextoCaminho(
        cor="azul",
        titulo=t.get("azul_titulo", ""),
        veredito=azul_veredito,
        nota=t.get("azul_nota", ""),
        marcador="",
        destaques=(
            (
                t.get("rotulo_aporte", ""),
                formatar_dinheiro_br(snapshot.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA),
            ),
            (
                t.get("rotulo_total_pagamentos", ""),
                formatar_dinheiro_br(cenario_recomendado.CUSTO_FUTURO_TOTAL),
            ),
        ),
        mes_fim=min(cenario_recomendado.PRAZO_TOTAL, escala) or escala,
        escala=escala,
    )
    caminhos = [vermelho, azul]

    extra = prog.com_extra
    if extra is not None:
        valor_extra = _sem_centavos(formatar_dinheiro_br(extra.CONTRIBUICAO_EXTRA_MENSAL))
        if extra.ESTOUROU_HORIZONTE:
            chave = "verde_veredito_nao_quita"
        elif extra.MESES_ANTECIPADOS > 0:
            chave = "verde_veredito"
        elif extra.ECONOMIA_CUSTO > 0:
            chave = "verde_veredito_mesmo_prazo"
        else:
            chave = "verde_veredito_sem_ganho"
        verde_veredito = t.get(chave, "").format(
            prazo=_formatar_meses(extra.PRAZO_TOTAL),
            antecipados=_formatar_meses(extra.MESES_ANTECIPADOS),
        )
        if not extra.ESTOUROU_HORIZONTE:
            verde_veredito += _complemento("verde_complemento", extra.PAGAMENTO_MENSAL_TOTAL)
        caminhos.append(
            ContextoCaminho(
                cor="verde",
                titulo=t.get("verde_titulo", ""),
                veredito=verde_veredito,
                nota=t.get("verde_nota", "").format(extra=valor_extra),
                marcador="",
                destaques=(
                    (
                        t.get("rotulo_aporte", ""),
                        formatar_dinheiro_br(extra.ATAQUE_MENSAL_TOTAL)
                        if extra.ATAQUE_MENSAL_TOTAL is not None
                        else valor_extra,
                    ),
                    (
                        t.get("rotulo_total_pagamentos", ""),
                        formatar_dinheiro_br(extra.CUSTO_FUTURO_TOTAL),
                    ),
                ),
                economia=(
                    f"{t.get('rotulo_economia_base', '')} "
                    f"{formatar_dinheiro_br(extra.ECONOMIA_CUSTO)}"
                    if extra.ECONOMIA_CUSTO > 0
                    else ""
                ),
                mes_fim=min(extra.PRAZO_TOTAL, escala) if extra.PRAZO_TOTAL else escala,
                escala=escala,
            )
        )
    return ContextoPrognostico(
        titulo=t.get("titulo", ""), introducao=t.get("introducao", ""), caminhos=tuple(caminhos)
    )


@dataclass(frozen=True, slots=True)
class ContextoPendenciaAcionavel:
    """Plano amigável — uma pendência de `_CAMPOS_MATERIAIS_DA_DIVIDA` com
    o "onde achar" e o `ID_PERGUNTA` do Bloco 5 que grava o campo, para o
    botão "Responder agora" (`frontend` navega para
    `#respostas/{ID_PERGUNTA}/{DIVIDA_ID}`, rota já existente). `id_pergunta`
    é `None` quando o campo não tem pergunta mapeada em `pergunta_do_campo`
    — o botão não aparece nesse caso, mas o item continua listado."""

    DIVIDA_ID: str
    nome_divida: str
    rotulo: str
    onde_achar: str
    id_pergunta: str | None


def _pendencias_acionaveis(
    snapshot: SnapshotOrdem, textos: TextosCanonicosPlano, nomes: Mapping[str, str]
) -> tuple[ContextoPendenciaAcionavel, ...]:
    """Mesma fonte de `_pendencias` (`_campos_desconhecidos_da_divida` sobre
    `snapshot.estado_inputs.dividas`), reformatada com "onde achar" e o ID
    da pergunta — nenhuma leitura nova além da já feita por `_pendencias`."""
    if snapshot.ORDEM_STATUS is not ORDEM_STATUS.PROVISORIA:
        return ()
    return tuple(
        ContextoPendenciaAcionavel(
            DIVIDA_ID=divida.DIVIDA_ID,
            nome_divida=nomes.get(divida.DIVIDA_ID, divida.DIVIDA_ID),
            rotulo=textos.rotulos_de_pendencia.get(campo, campo),
            onde_achar=textos.onde_achar.get(campo, ""),
            id_pergunta=textos.pergunta_do_campo.get(campo),
        )
        for divida in snapshot.estado_inputs.dividas
        for campo in _campos_desconhecidos_da_divida(divida)
    )


#: Revisão de design (2026-10-03) — os campos de `Divida` mostrados em todo
#: cartão de dívida, na ordem em que aparecem, e como cada um é escrito.
_FATOS_DA_DIVIDA: Final[tuple[tuple[str, str], ...]] = (
    ("SALDO_DEVEDOR_ATUAL", "dinheiro"),
    ("PAGAMENTO_MENSAL_EFETIVO", "dinheiro"),
    ("TAXA_EFETIVA_MENSAL_NORMALIZADA", "taxa"),
)


#: T-354 — a partir desta nota o aluno recebe o aviso de que a ordem seguiu
#: o critério do método. Faixa dita pelo especialista (9 e 10).
_NOTA_DE_INCOMODO_ALTA: Final[int] = 9


def _incomodo_da_divida(
    divida: Divida | None, indice: int, textos: TextosCanonicosPlano
) -> tuple[str, str]:
    """`(linha, aviso)` da nota de incômodo — LIDA de `Divida.PESO_EMOCIONAL`.
    Desconhecida ou sem texto cadastrado, não há nada a dizer (nunca zero)."""
    if divida is None or not isinstance(divida.PESO_EMOCIONAL, int | Decimal):
        return "", ""
    nota = int(divida.PESO_EMOCIONAL)
    linha = textos.incomodo.get("linha", "").replace("{nota}", str(nota))
    alto = nota >= _NOTA_DE_INCOMODO_ALTA and indice > 1
    return linha, textos.incomodo.get("aviso", "") if alto else ""


def _contexto_do_curso(
    textos: TextosCanonicosPlano, metodo: str, estabilizacao: bool
) -> ContextoCursoSSD | None:
    """T-352/T-353 — o quadro de aulas do plano. A escolha das aulas é um
    lookup no YAML por método (ou "estabilizacao"); o título e o motivo de
    cada aula também. Aula sem cadastro no YAML é ignorada."""
    bruto = textos.curso_ssd
    if not bruto:
        return None
    aulas = bruto.get("aulas") or {}
    quadros = bruto.get("quadro_por_cenario") or {}
    chave = "estabilizacao" if estabilizacao else metodo
    numeros = quadros.get(chave) or quadros.get("padrao") or []
    escolhidas = tuple(
        (str(n), str(aulas[n]["titulo"]), str(aulas[n]["motivo"])) for n in numeros if n in aulas
    )
    return ContextoCursoSSD(
        apresentacao_titulo=str(bruto.get("apresentacao_titulo") or ""),
        apresentacao=tuple(str(par) for par in (bruto.get("apresentacao") or [])),
        introducao_titulo=str(bruto.get("introducao_titulo") or ""),
        introducao=str(bruto.get("introducao") or ""),
        quadro_titulo=str(bruto.get("quadro_titulo") or ""),
        aulas=escolhidas,
        melhorar_titulo=str(bruto.get("melhorar_titulo") or ""),
        melhorar_intro=str(bruto.get("melhorar_intro") or ""),
        melhorar=tuple(
            (str(item["texto"]), str(item["aula"])) for item in (bruto.get("melhorar") or [])
        ),
    )


def _fatos_da_divida(
    divida: Divida | None, textos: TextosCanonicosPlano
) -> tuple[tuple[str, str], ...]:
    """Os números fixos do cartão de cada dívida, LIDOS de `Divida` —
    mesmos rótulos de `rotulos_de_apoio`, para que o documento possa omitir
    um valor de apoio que repita um destes. `DESCONHECIDO` vira "Não
    informado", nunca zero (`RF-16`). Vazio sem a dívida em
    `estado_inputs` (não deveria acontecer: a ordem só traz dívidas do
    inventário)."""
    if divida is None:
        return ()
    nao_informado = rotulo_de_codigo(textos.rotulos_de_codigos, "DESCONHECIDO")
    fatos: list[tuple[str, str]] = []
    for campo, formato in _FATOS_DA_DIVIDA:
        valor = getattr(divida, campo)
        if not isinstance(valor, Decimal):
            texto = nao_informado
        elif formato == "taxa":
            texto = formatar_taxa_br(valor)
        else:
            texto = formatar_dinheiro_br(valor)
        fatos.append((textos.rotulos_de_apoio.get(campo, campo), texto))
    return tuple(fatos)


@dataclass(frozen=True, slots=True)
class ContextoPontoDePartida:
    """ "Seu ponto de partida" — revisão de design (2026-10-03): os números do
    mês do aluno, para o plano parecer feito para ELE. Todos LIDOS do
    snapshot e só formatados (`AC-42`): renda e gastos de `estado_inputs`,
    parcelas e valor extra do `Diagnostico`. Nenhuma conta liga um número
    ao outro na tela; a relação entre eles é explicada em texto."""

    renda: str
    gastos: str
    gastos_ocasionais: str
    parcelas: str
    valor_extra: str
    quantidade_de_dividas: int  # len(estado_inputs.dividas): contagem, não valor


def _ponto_de_partida(snapshot: SnapshotOrdem) -> ContextoPontoDePartida:
    estado = snapshot.estado_inputs
    diagnostico = snapshot.diagnostico
    return ContextoPontoDePartida(
        renda=formatar_dinheiro_br(estado.RENDA_TOTAL_RECORRENTE),
        gastos=formatar_dinheiro_br(estado.DESPESAS_OPERACIONAIS_ATUAIS),
        gastos_ocasionais=formatar_dinheiro_br(estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS),
        parcelas=formatar_dinheiro_br(diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES),
        valor_extra=formatar_dinheiro_br(diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA),
        quantidade_de_dividas=len(estado.dividas),
    )


def primeiro_nome(nome_completo: str | None) -> str | None:
    """ "MARIA DA SILVA" → "Maria" — revisão de design (2026-10-03): o
    cabeçalho trata o aluno pelo primeiro nome. O nome vem da compra
    (Hotmart, migração `009`), muitas vezes em caixa alta; `None` ou vazio
    devolve `None` e o documento usa a versão sem nome."""
    if not nome_completo or not nome_completo.strip():
        return None
    return nome_completo.strip().split()[0].capitalize()


def rotulo_do_motivo_de_recalculo(snapshot: SnapshotOrdem, textos: TextosCanonicosPlano) -> str:
    """`RF-111` (`T-326`) — o motivo do recálculo por rótulo. O
    `MOTIVO_RECALCULO` do motor é texto de auditoria ("Nenhum
    EVENTO_RECALCULO observado — … (R-02, AC-13)"); aqui se lê o
    `EVENTO_RECALCULO` que o gerou. Sem evento, o primeiro snapshot da
    cadeia é o primeiro cálculo."""
    evento = snapshot.EVENTO_RECALCULO
    if evento is not None:
        chave = evento.value
    elif snapshot.versao == 1:
        chave = "SEM_EVENTO_PRIMEIRO_CALCULO"
    else:
        chave = "SEM_EVENTO"
    return rotulo_de_codigo(textos.rotulos_de_codigos, chave)


def montar_contexto_plano(
    snapshot: SnapshotOrdem,
    textos: TextosCanonicosPlano,
    vocabulario: VocabularioDoCaso | None = None,
    nome_do_aluno: str | None = None,
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
    quitacoes = meses_de_quitacao(snapshot) or {}
    # `T-326`: a dívida por "tipo — credor", não por `DIVIDA_ID`.
    nomes = nomear_dividas(
        snapshot.estado_inputs.dividas, textos, vocabulario or VocabularioDoCaso()
    )

    cenario = decidir_cenario_apresentacao(snapshot)
    # Revisão de design: cada cartão de dívida lê os próprios números da
    # `Divida` de origem, por `DIVIDA_ID` — leitura, nunca conta.
    dividas_por_id = {divida.DIVIDA_ID: divida for divida in snapshot.estado_inputs.dividas}
    ordem = tuple(
        ContextoPosicao(
            posicao=posicao_do_snapshot.posicao,
            indice=indice,
            total=total_de_posicoes,
            DIVIDA_ID=posicao_do_snapshot.DIVIDA_ID,
            nome=nomes.get(posicao_do_snapshot.DIVIDA_ID, posicao_do_snapshot.DIVIDA_ID),
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
            mes_de_quitacao=quitacoes.get(posicao_do_snapshot.DIVIDA_ID),
            fatos=_fatos_da_divida(dividas_por_id.get(posicao_do_snapshot.DIVIDA_ID), textos),
            incomodo=_incomodo_da_divida(
                dividas_por_id.get(posicao_do_snapshot.DIVIDA_ID), indice, textos
            )[0],
            aviso_incomodo=_incomodo_da_divida(
                dividas_por_id.get(posicao_do_snapshot.DIVIDA_ID), indice, textos
            )[1],
        )
        for indice, posicao_do_snapshot in enumerate(snapshot.ORDEM_QUITACAO, start=1)
    )
    nomes_curtos = nomear_dividas_curtas(
        snapshot.estado_inputs.dividas, textos, vocabulario or VocabularioDoCaso()
    )
    prognostico = _prognostico(snapshot, cenario_recomendado, textos, nomes, nomes_curtos)

    return ContextoPlano(
        titulo=textos.titulo,
        corpo=textos.corpo,
        ordem=ordem,
        # `T-177`: com unidade. `PRAZO_TOTAL` é contagem de meses (`int`),
        # não `Decimal` — não passa por formatação monetária.
        PRAZO_TOTAL=_formatar_meses(cenario_recomendado.PRAZO_TOTAL),
        PRAZO_TOTAL_INT=cenario_recomendado.PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=formatar_dinheiro_br(cenario_recomendado.CUSTO_FUTURO_TOTAL),
        ENGINE_VERSION=snapshot.ENGINE_VERSION,
        PARAMETROS_VERSION=snapshot.PARAMETROS_VERSION,
        cenario=cenario,
        acoes=_contexto_acoes(snapshot, textos, nomes),
        pendencias=_pendencias(snapshot, textos.rotulos_de_pendencia, nomes),
        MODO_ESTABILIZACAO=snapshot.diagnostico.MODO_ESTABILIZACAO,
        # `T-177`: com `R$`. O template de estabilização deixou de
        # prefixá-lo — o valor chega pronto.
        RESULTADO_CAIXA_OBSERVADO=formatar_dinheiro_br(
            snapshot.diagnostico.RESULTADO_CAIXA_OBSERVADO
        ),
        reserva_mobilizavel=_reserva_mobilizavel(snapshot),
        cenario_adicional=_cenario_adicional(snapshot, textos, nomes),
        nao_projetados=tuple(
            (item.ITEM_ID, item.motivo.value)
            for item in snapshot.projecao_extraordinarios.nao_projetados
        ),
        valor_mensal_destinado=formatar_dinheiro_br(
            snapshot.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
        ),
        metodo=rotulo_de_codigo(textos.rotulos_de_codigos, snapshot.METODO_RECOMENDADO_PIQ.value),
        rotulo_do_cenario=rotulo_de_codigo(textos.rotulos_de_codigos, cenario.value),
        # Plano amigável (2026-10-03) — leitura adicional do MESMO
        # `cenario_recomendado`/`snapshot` já obtidos acima; nenhum campo
        # novo é lido do motor, só reorganizado para a "consultoria".
        nome_do_aluno=primeiro_nome(nome_do_aluno),
        ponto_de_partida=_ponto_de_partida(snapshot),
        como_funciona=textos.como_funciona.get(snapshot.METODO_RECOMENDADO_PIQ.value, ()),
        pendencias_acionaveis=_pendencias_acionaveis(snapshot, textos, nomes),
        prognostico=prognostico,
        quando_termina=_quando_cada_divida_termina(snapshot, prognostico, nomes, textos),
        curso_ssd=_contexto_do_curso(
            textos,
            snapshot.METODO_RECOMENDADO_PIQ.value,
            snapshot.diagnostico.MODO_ESTABILIZACAO,
        ),
        aviso_sem_valor_extra=(
            textos.sem_valor_extra
            if not snapshot.diagnostico.MODO_ESTABILIZACAO
            and isinstance(snapshot.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA, Decimal)
            and snapshot.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA == 0
            else ""
        ),
    )
