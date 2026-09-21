"""Lint estático: nenhuma das três fórmulas proibidas pela §13.1 existe em
`engine/` — AC-81, RF-49, US-15 · plano R3.9.5, T-113.

**TRAVA CANÔNICA (§13.1 da spec canônica, v1.0.1, congelada em 2026-09-07).**
"Nunca calcular `RESERVA_MOBILIZAVEL` mediante percentual automático de
`RESERVA_TOTAL`. Fórmulas **expressamente proibidas** na v1.0.1:"

```
RESERVA_MOBILIZAVEL = 30% × RESERVA_TOTAL                     ← PROIBIDA
RESERVA_MOBILIZAVEL = 50% × RESERVA_TOTAL                     ← PROIBIDA
RESERVA_MOBILIZAVEL = RESERVA_TOTAL - RESERVA_MINIMA_PADRAO   ← PROIBIDA
```

A razão é de método, não de estilo. `RESERVA_MOBILIZAVEL` é "o valor máximo da
reserva que o usuário aceita submeter à análise, declarado no Bloco 4 — o
motor apenas valida e limita" (§13.1). A reserva é recurso PROTETIVO do
usuário; derivá-la por percentual automático converteria "quanto o usuário
aceita analisar" em "quanto o motor decidiu tomar", que é decisão de
metodologia tomada no código (`sdd.config.md` §6: "Metodologia não se decide
implementando"). Este teste é a rede que impede as três formas de reaparecerem
por descuido em qualquer rodada futura.

Heurística de detecção e suas limitações
-----------------------------------------------------------------------------
Detecção por AST, mesma família de `tests/estatica/test_sem_float_no_motor.py`,
`test_uso_de_tolerancia.py` e `test_nenhum_parametro_no_codigo.py`. Três
padrões, cada um ancorado em uma das três formas proibidas:

1. **`RESERVA_TOTAL` como operando de multiplicação ou divisão** — `BinOp`
   com `Mult`, `Div` ou `FloorDiv`. Cobre as duas primeiras formas em
   qualquer escrita: `Decimal("0.30") * RESERVA_TOTAL`,
   `RESERVA_TOTAL * Decimal("0.5")`, `RESERVA_TOTAL * 30 / 100`,
   `RESERVA_TOTAL / 2`. O percentual é ARITMÉTICA, não um literal específico
   — travar em "0.3" e "0.5" deixaria passar `* 40 / 100` e seria uma trava
   contra o exemplo, não contra a regra.

2. **`RESERVA_TOTAL` como operando de subtração** — `BinOp` com `Sub`, dos
   dois lados. Cobre a terceira forma (`RESERVA_TOTAL - <qualquer piso>`),
   independentemente de como o subtraendo seja nomeado: o que a §13.1 proíbe
   é descontar automaticamente um piso da reserva total, e trocar o nome
   `RESERVA_MINIMA_PADRAO` por `PISO_DE_SEGURANCA` não tornaria a fórmula
   permitida.

3. **Qualquer identificador contendo `RESERVA_MINIMA_PADRAO`** — nome,
   atributo, parâmetro, alvo de atribuição, argumento nomeado de chamada,
   nome importado, função ou classe. Essa variável **não existe** na spec e
   não deve passar a existir: ela só teria uso se alguém fosse subtraí-la de
   `RESERVA_TOTAL`, que é exatamente a terceira forma proibida. Detectá-la
   como identificador pega a fórmula um passo antes de ela ser escrita.

**Por que MENÇÃO a `RESERVA_TOTAL` não é violação.** A §13.1 Regra 2 é
`MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))` — ela
menciona `RESERVA_TOTAL` e é OBRIGATÓRIA (`RF-43`, `T-102`). O mesmo vale para
a guarda `if RESERVA_TOTAL is DESCONHECIDO` da Regra 3 e para o campo
`EstadoFinanceiro.RESERVA_TOTAL: DinheiroTalvez` (`RF-36`). Um lint que
reprovasse qualquer aparição do nome tornaria a própria §13.1 inimplementável.
O alvo, portanto, é a OPERAÇÃO (`BinOp` de multiplicação, divisão ou
subtração), nunca a menção — `min`, `max`, comparação e passagem de argumento
são livres, e `test_detector_nao_reporta_regra_2_legitima` fixa essa fronteira.

**Por que a DOCSTRING que transcreve as fórmulas não é violação.**
`engine/ataque_imediato.py` cita literalmente as três formas proibidas na
docstring de `derivar_RESERVA_MOBILIZAVEL`, para que quem lê a função saiba o
que não pode escrever. Isso é texto (`ast.Constant` do tipo `str`), não
identificador nem operação — e citar a trava é o oposto de violá-la. Por isso
o padrão (3) inspeciona identificadores da AST, jamais o texto bruto do
arquivo: um `grep` por `RESERVA_MINIMA_PADRAO` reprovaria a documentação da
própria trava.

**Limitação documentada.** Como os demais lints desta suíte, é varredura
estrutural, não prova semântica. Não pega um percentual montado por reflexão
(`getattr`), nem uma multiplicação escrita sobre uma CÓPIA já renomeada
(`total = RESERVA_TOTAL` seguido de `total * Decimal("0.3")`) — rastrear
aliases exigiria análise de fluxo de dados, e o custo/benefício não se
sustenta contra a camada que já cobre isso: `T-112` verifica o COMPORTAMENTO
de `derivar_RESERVA_MOBILIZAVEL` sobre `AC-70`–`AC-73` e `EC-23`–`EC-26`, e
nenhum percentual passa por aqueles gabaritos sem quebrar um número. Este lint
cobre a forma sintática, que é como as três fórmulas apareceriam se alguém as
reintroduzisse copiando-as da spec.

O escopo é `engine/**/*.py` — `AC-81` fala do "código-fonte de `engine/`", que
é onde a fórmula teria efeito sobre o valor recomendado ao usuário.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

# As duas variáveis da §13.1 vigiadas por este lint, com o nome canônico da
# spec, caractere por caractere (`sdd.config.md` §7).
RESERVA_TOTAL = "RESERVA_TOTAL"
RESERVA_MINIMA_PADRAO = "RESERVA_MINIMA_PADRAO"

# Os operadores que produzem as três formas proibidas. `Mult`/`Div`/`FloorDiv`
# cobrem o percentual (formas 1 e 2, escritas como fator ou como razão);
# `Sub` cobre o desconto de piso (forma 3). `Add` fica de fora de propósito:
# somar algo a `RESERVA_TOTAL` não é nenhuma das três, e proibi-lo seria
# inventar uma quarta trava que a §13.1 não escreveu.
_OPERADORES_DE_PERCENTUAL = (ast.Mult, ast.Div, ast.FloorDiv)
_OPERADOR_DE_DESCONTO = (ast.Sub,)


@dataclass(frozen=True, slots=True)
class FormulaProibida:
    arquivo: str
    linha: int
    forma: str
    trecho: str


def _menciona_reserva_total(no: ast.expr) -> bool:
    """`True` se a sub-árvore de `no` referenciar `RESERVA_TOTAL` como nome
    simples (`RESERVA_TOTAL`) ou como atributo (`estado.RESERVA_TOTAL`) — as
    duas formas pelas quais a variável pode chegar a um operando."""
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name) and filho.id == RESERVA_TOTAL:
            return True
        if isinstance(filho, ast.Attribute) and filho.attr == RESERVA_TOTAL:
            return True
    return False


def _identificadores_reserva_minima_padrao(
    no: ast.AST, nome_arquivo: str
) -> list[FormulaProibida]:
    """Identificadores que contenham `RESERVA_MINIMA_PADRAO`, em qualquer das
    posições em que um nome pode aparecer na AST. A variável não existe na
    spec e não deve passar a existir — ver padrão (3) na docstring do módulo."""
    achados: list[FormulaProibida] = []

    def registrar(linha: int, posicao: str, identificador: str) -> None:
        achados.append(
            FormulaProibida(
                arquivo=nome_arquivo,
                linha=linha,
                forma="identificador RESERVA_MINIMA_PADRAO",
                trecho=f"{posicao} `{identificador}`",
            )
        )

    if isinstance(no, ast.Name) and RESERVA_MINIMA_PADRAO in no.id:
        registrar(no.lineno, "nome", no.id)
    elif isinstance(no, ast.Attribute) and RESERVA_MINIMA_PADRAO in no.attr:
        registrar(no.lineno, "atributo", no.attr)
    elif isinstance(no, ast.arg) and RESERVA_MINIMA_PADRAO in no.arg:
        registrar(no.lineno, "parâmetro", no.arg)
    elif isinstance(no, ast.keyword) and no.arg and RESERVA_MINIMA_PADRAO in no.arg:
        registrar(getattr(no, "lineno", 0), "argumento nomeado", no.arg)
    elif isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        if RESERVA_MINIMA_PADRAO in no.name:
            registrar(no.lineno, "definição", no.name)
    elif isinstance(no, ast.alias):
        nome_importado = no.asname or no.name
        if RESERVA_MINIMA_PADRAO in nome_importado:
            registrar(getattr(no, "lineno", 0), "import", nome_importado)

    return achados


def _detectar_formulas_proibidas(codigo_fonte: str, nome_arquivo: str) -> list[FormulaProibida]:
    """Percorre a AST de `codigo_fonte` e devolve toda ocorrência das três
    formas proibidas pela TRAVA CANÔNICA da §13.1, com arquivo e linha."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    achados: list[FormulaProibida] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.BinOp):
            envolve_reserva_total = _menciona_reserva_total(no.left) or _menciona_reserva_total(
                no.right
            )
            if envolve_reserva_total and isinstance(no.op, _OPERADORES_DE_PERCENTUAL):
                achados.append(
                    FormulaProibida(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        forma="percentual automático de RESERVA_TOTAL",
                        trecho=ast.unparse(no),
                    )
                )
            elif envolve_reserva_total and isinstance(no.op, _OPERADOR_DE_DESCONTO):
                achados.append(
                    FormulaProibida(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        forma="subtração sobre RESERVA_TOTAL",
                        trecho=ast.unparse(no),
                    )
                )

        achados.extend(_identificadores_reserva_minima_padrao(no, nome_arquivo))

    return achados


def test_sem_percentual_automatico_de_reserva() -> None:
    """`AC-81` (`RF-49`, `US-15`): nenhum arquivo real de `engine/**/*.py`
    contém qualquer das três fórmulas expressamente proibidas pela TRAVA
    CANÔNICA da §13.1 — `30% × RESERVA_TOTAL`, `50% × RESERVA_TOTAL` e
    `RESERVA_TOTAL - RESERVA_MINIMA_PADRAO`. A mensagem de falha nomeia
    arquivo, linha e o trecho culpado."""
    achados: list[FormulaProibida] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        achados.extend(_detectar_formulas_proibidas(codigo_fonte, str(arquivo)))

    mensagem = (
        "AC-81 violado — fórmula proibida pela TRAVA CANÔNICA da §13.1 "
        "encontrada em engine/ (RESERVA_MOBILIZAVEL nunca é percentual "
        "automático de RESERVA_TOTAL; o usuário declara o valor máximo em "
        "B4.03A e o motor apenas valida e limita):\n"
    ) + "\n".join(f"  {a.arquivo}:{a.linha} — {a.forma}: `{a.trecho}`" for a in achados)
    assert not achados, mensagem


@pytest.mark.parametrize(
    ("forma", "codigo"),
    [
        (
            "30% × RESERVA_TOTAL",
            'RESERVA_MOBILIZAVEL = Decimal("0.30") * RESERVA_TOTAL\n',
        ),
        (
            "50% × RESERVA_TOTAL",
            'RESERVA_MOBILIZAVEL = Decimal("0.50") * RESERVA_TOTAL\n',
        ),
        (
            "RESERVA_TOTAL - RESERVA_MINIMA_PADRAO",
            "RESERVA_MOBILIZAVEL = RESERVA_TOTAL - RESERVA_MINIMA_PADRAO\n",
        ),
    ],
)
def test_detector_pega_cada_uma_das_tres_formulas_proibidas(forma: str, codigo: str) -> None:
    """Prova negativa, mesmo padrão de
    `tests/estatica/test_tipo_acao_apenas_quatro_valores.py::
    test_verificador_pega_quinto_literal_proposital` e de
    `test_sem_derivacao_de_classificacao_mobilizacao.py::
    test_detector_pega_derivacao_proposital`: alimenta o PRÓPRIO detector usado
    por `test_sem_percentual_automatico_de_reserva` com cada uma das três
    fórmulas da §13.1 construída como STRING — nunca escrita em `engine/`
    real, nunca executada — e confirma que cada uma é pega.

    Sem esta prova, o teste acima passaria igualmente bem com o detector
    quebrado: hoje ele varre um conjunto em que a resposta correta é "nenhuma",
    e verificação vácua não distingue "não há violação" de "não sei detectar
    violação". As três strings abaixo são transcrição literal das três linhas
    marcadas `← PROIBIDA` na §13.1."""
    achados = _detectar_formulas_proibidas(codigo, "caso_proposital.py")

    assert achados, f"o detector não pegou a fórmula proibida {forma!r}: `{codigo.strip()}`"
    assert achados[0].linha == 1, f"esperava a violação na linha 1, obteve: {achados!r}"


@pytest.mark.parametrize(
    ("descricao", "codigo"),
    [
        ("fator à esquerda", 'RESERVA_MOBILIZAVEL = Decimal("0.3") * RESERVA_TOTAL\n'),
        ("fator à direita", 'RESERVA_MOBILIZAVEL = RESERVA_TOTAL * Decimal("0.3")\n'),
        ("percentual como razão", "RESERVA_MOBILIZAVEL = RESERVA_TOTAL * 30 / 100\n"),
        ("divisão simples", "RESERVA_MOBILIZAVEL = RESERVA_TOTAL / 2\n"),
        ("divisão inteira", "RESERVA_MOBILIZAVEL = RESERVA_TOTAL // 3\n"),
        ("subtraendo renomeado", "RESERVA_MOBILIZAVEL = RESERVA_TOTAL - PISO_DE_SEGURANCA\n"),
        ("subtração invertida", "RESERVA_MOBILIZAVEL = PISO_DE_SEGURANCA - RESERVA_TOTAL\n"),
        ("via atributo do estado", 'RESERVA_MOBILIZAVEL = estado.RESERVA_TOTAL * Decimal("0.5")\n'),
        ("aninhado em chamada", 'return min(teto, RESERVA_TOTAL * Decimal("0.3"))\n'),
    ],
)
def test_detector_pega_cada_variacao_de_escrita(descricao: str, codigo: str) -> None:
    """`AC-81`, "as três fórmulas proibidas não existem **em nenhuma forma**":
    o percentual é ARITMÉTICA, não um literal específico. Uma trava que
    reconhecesse apenas `0.3` e `0.5` deixaria passar `* 40 / 100` e seria uma
    trava contra o exemplo, não contra a regra."""
    achados = _detectar_formulas_proibidas(codigo, "caso_proposital.py")

    assert achados, f"o detector não pegou a variação {descricao!r}: `{codigo.strip()}`"


@pytest.mark.parametrize(
    ("posicao", "codigo"),
    [
        ("nome lido", "teto = RESERVA_MINIMA_PADRAO\n"),
        ("alvo de atribuição", "RESERVA_MINIMA_PADRAO = dinheiro(1000)\n"),
        ("parâmetro de função", "def derivar(*, RESERVA_MINIMA_PADRAO):\n    return None\n"),
        ("argumento nomeado", "derivar(RESERVA_MINIMA_PADRAO=dinheiro(0))\n"),
        ("atributo", "teto = parametros.RESERVA_MINIMA_PADRAO\n"),
        ("import", "from engine.parametros import RESERVA_MINIMA_PADRAO\n"),
        ("import com alias", "from engine.parametros import piso as RESERVA_MINIMA_PADRAO\n"),
        ("nome de função", "def calcular_RESERVA_MINIMA_PADRAO():\n    return None\n"),
    ],
)
def test_detector_pega_identificador_reserva_minima_padrao(posicao: str, codigo: str) -> None:
    """Terceiro critério de `T-113`: QUALQUER identificador contendo
    `RESERVA_MINIMA_PADRAO` em `engine/` é violação. A variável não existe na
    spec e não deve passar a existir — seu único uso concebível é ser
    subtraída de `RESERVA_TOTAL`, que é a terceira fórmula proibida. Pegá-la
    como identificador trava a fórmula um passo antes de ela ser escrita."""
    achados = _detectar_formulas_proibidas(codigo, "caso_proposital.py")

    assert achados, (
        f"o detector não pegou `RESERVA_MINIMA_PADRAO` na posição {posicao!r}: `{codigo.strip()}`"
    )
    assert any("RESERVA_MINIMA_PADRAO" in a.forma for a in achados), (
        f"esperava a forma 'identificador RESERVA_MINIMA_PADRAO', obteve: {achados!r}"
    )


def test_detector_nao_reporta_regra_2_legitima() -> None:
    """Contraprova da fronteira, e a mais importante deste módulo: a Regra 2
    da §13.1 — `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))`
    — MENCIONA `RESERVA_TOTAL` e é OBRIGATÓRIA (`RF-43`, `T-102`,
    `engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`).

    Um detector que reprovasse qualquer menção ao nome tornaria a própria
    §13.1 inimplementável e quebraria `T-102`. O alvo é a OPERAÇÃO de
    multiplicação/divisão/subtração, nunca a menção: `min`, `max`, comparação
    e passagem de argumento são livres. O trecho abaixo é a transcrição do
    corpo real da função."""
    codigo_legitimo = """
def derivar_RESERVA_MOBILIZAVEL(*, RESERVA_TOTAL, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO):
    if RESERVA_TOTAL is DESCONHECIDO:
        return DESCONHECIDO
    informado_nao_negativo = max(dinheiro(0), VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO)
    return min(RESERVA_TOTAL, informado_nao_negativo)
"""
    achados = _detectar_formulas_proibidas(codigo_legitimo, "caso_correto.py")

    assert not achados, (
        "a Regra 2 legítima da §13.1 não pode ser reportada como fórmula "
        f"proibida — reprová-la tornaria a §13.1 inimplementável, obteve: {achados!r}"
    )


def test_detector_nao_reporta_docstring_que_transcreve_a_trava() -> None:
    """Contraprova do padrão (3): `engine/ataque_imediato.py` transcreve as
    três fórmulas proibidas na docstring de `derivar_RESERVA_MOBILIZAVEL`,
    para que quem lê a função saiba o que não pode escrever. Texto
    (`ast.Constant` do tipo `str`) não é identificador nem operação, e citar a
    trava é o oposto de violá-la.

    Isola por que este lint é por AST e não por `grep`: uma busca textual por
    `RESERVA_MINIMA_PADRAO` reprovaria a documentação da própria trava — e o
    caminho de menor esforço para "consertar" a falha seria apagar a
    documentação, deixando o motor menos protegido, não mais."""
    codigo_legitimo = '''
def derivar_RESERVA_MOBILIZAVEL(*, RESERVA_TOTAL):
    """TRAVA CANÔNICA (§13.1, RF-49): NUNCA percentual automático de
    `RESERVA_TOTAL`. As três formas expressamente proibidas na v1.0.1 —
    `30% x RESERVA_TOTAL`, `50% x RESERVA_TOTAL` e
    `RESERVA_TOTAL - RESERVA_MINIMA_PADRAO` — não existem neste módulo."""
    return RESERVA_TOTAL
'''
    achados = _detectar_formulas_proibidas(codigo_legitimo, "caso_correto.py")

    assert not achados, (
        "a docstring que TRANSCREVE a trava não pode ser reportada como "
        f"violação dela, obteve: {achados!r}"
    )


def test_mensagem_de_falha_nomeia_arquivo_e_linha() -> None:
    """`AC-81`/`T-113`, critério "nomeando arquivo e linha na mensagem de
    falha": o achado carrega o caminho do arquivo, a linha exata e o trecho
    reconstruído, para que o diagnóstico não exija reproduzir o caso."""
    codigo = 'x = 1\ny = 2\nRESERVA_MOBILIZAVEL = Decimal("0.30") * RESERVA_TOTAL\n'

    achados = _detectar_formulas_proibidas(codigo, "engine/ataque_imediato.py")

    assert len(achados) == 1, f"esperava exatamente 1 achado, obteve: {achados!r}"
    assert achados[0].arquivo == "engine/ataque_imediato.py"
    assert achados[0].linha == 3
    assert achados[0].forma == "percentual automático de RESERVA_TOTAL"
    assert "RESERVA_TOTAL" in achados[0].trecho
