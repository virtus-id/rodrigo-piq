"""Lint estático: nenhum valor `P_*` escrito em `engine/` — RF-13, AC-17 (lado A).

`AC-17`: "Dado o código-fonte do motor, quando for auditado, então nenhum
valor `P_*` aparece escrito nele, e alterar o valor na fonte externa muda o
resultado sem recompilar regra." Este teste cobre o lado estático da
auditoria (o lado dinâmico — "alterar o valor externo muda o resultado" — é
`test_parametro_externo_muda_resultado`, fora do escopo de T-10, ver
`plans/motor-calculo.plan.md` §9).

Heurística de detecção (decisão de implementação desta tarefa) e suas LIMITAÇÕES
-----------------------------------------------------------------------------
A varredura por AST cobre dois alvos, de robustez muito diferente. Documentado
aqui em vez de prometido implicitamente — nenhuma heurística de análise
estática "prova ausência de parâmetro embutido" em sentido absoluto; ela prova
a AUSÊNCIA DOS PADRÕES QUE PROCURA.

**(a) Identificador `P_*` recebendo literal — robusta.** Qualquer nome que
comece com `P_` (convenção fixada na §8 da canônica para os 38 parâmetros
ativos) e que apareça:
  - do lado esquerdo de uma atribuição (`ast.Assign`/`ast.AnnAssign`) cujo
    lado direito é um literal (`ast.Constant` numérico/string, ou uma
    expressão composta só por literais, ex. tupla de literais); ou
  - como valor default de parâmetro de função (`ast.arguments.defaults`/
    `kw_defaults`) que seja um literal;
é reportado como violação. Esse padrão cobre exatamente o caso do critério de
aceite ("`P_PISO_CAPACIDADE_ABSOLUTO = 300` faz o teste falhar") e qualquer
variante estrutural equivalente (anotação de tipo presente ou não, tupla de
vários `P_*=literal` na mesma linha, default de argumento). É robusta porque
não depende de adivinhar QUAL literal é "de parâmetro" — qualquer literal
atribuído a um nome `P_*` é suspeito por definição, já que todo parâmetro
real do projeto só deveria chegar via `Parametros.numero(...)` (ver item
correlato abaixo), nunca por atribuição direta em `engine/`.

**(b) Número da tabela da §8 aparecendo como literal solto — deliberadamente
LIMITADA, e por quê.** Generalizar "nenhum número da tabela de valores da §8
aparece como literal" sem falso positivo é impraticável: números pequenos
(`0`, `1`, `2`, `100`) aparecem legitimamente em código por motivos que nada
têm a ver com parâmetro — índices, bases de conversão (`_CEM = Decimal(100)`
em `engine/diagnostico.py`), contagens de sinais da regra D.4, arredondamento
(`Decimal("0.01")` em `engine/precisao.py`). Uma checagem "todo `0.05` é
proibido" quebraria o próprio `TOLERANCIA_MONETARIA = Decimal("0.05")` de
`tests/conftest.py` (fora de `engine/`, mas ilustra o risco de falso
positivo) e qualquer `ROUND_HALF_UP`/precisão que cite `0.01` incidentalmente.

Por isso a decisão de implementação (autorizada pela própria tarefa) restringe
o item (b) a dois sub-testes, cada um com objetivo estreito e declarado:

  (b.1) **Toda chamada a `Parametros.numero(...)` usa uma STRING que começa
        com `P_`.** Isto é o INVERSO do que a redação ingênua pediria — em
        vez de caçar todo número mágico, garante que o único portal de leitura
        de parâmetro (`numero`, `engine/parametros.py`) nunca é chamado com
        algo que não seja um nome de parâmetro válido. Não prova ausência de
        número mágico em outro lugar do código, mas prova que o PRÓPRIO
        mecanismo de leitura de parâmetro não é usado incorretamente (ex.:
        `parametros.numero("piso")` sem o prefixo `P_`, um erro de digitação
        que mascararia silenciosamente uma leitura errada).

  (b.2) **Os valores decimais "sabidamente de parâmetro" da lista fechada
        abaixo — `0.05`, `0.10`, `0.15`, `0.20`, `0.60`, `0.80` (as reduções
        de `REDUCAO_*` e o piso `P_FATOR_SEGURANCA_MINIMO`, ver
        `parameters/parametros-1.0.1.json`) — não aparecem como literal
        Python solto em `engine/` fora de `tests/`.** É uma lista curada, não
        uma varredura geral: cobre exatamente os valores citados no enunciado
        desta tarefa (que por sua vez cita `AC-36`: "reduções 0,20 + 0,15 +
        0,10 e piso 0,60"). Um literal `0.05` usado por outro motivo
        legítimo em `engine/` (não há caso conhecido hoje) geraria falso
        positivo — aceitável pela mesma lógica de `test_uso_de_tolerancia.py`:
        o projeto prefere falso positivo raro a deixar passar parâmetro
        embutido.

O que este teste **não** garante: um parâmetro embutido como `Decimal("300")`
sem estar atribuído a um nome `P_*` (ex.: usado direto numa fórmula) só é
pego se o valor numérico específico estiver na lista curada de (b.2). Isso é
uma lacuna conhecida e documentada, não uma promessa quebrada — ver nota de
escopo no início desta seção.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

# (b.2): valores decimais sabidamente ligados a um P_* de redução/piso — ver
# docstring do módulo. Lista curada, não uma varredura geral de "todo número
# mágico". Strings, comparadas ao texto literal do nó (ast.Constant.value
# convertido para str, e também a representação "0,20"→"0.20" não é
# necessária pois o Python só aceita ponto decimal em literal fonte).
VALORES_DECIMAIS_SUSPEITOS: Final[frozenset[str]] = frozenset(
    {"0.05", "0.10", "0.15", "0.20", "0.60", "0.80"}
)


@dataclass(frozen=True, slots=True)
class ViolacaoParametro:
    arquivo: str
    linha: int
    descricao: str


def _e_literal_puro(no: ast.expr) -> bool:
    """Um `ast.Constant`, ou uma `Tuple`/`List` cujos elementos são todos
    literais puros (cobre `P_PRESSAO_INDIVIDUAL = (5, 10, 20, 30)`-like)."""
    if isinstance(no, ast.Constant):
        return True
    if isinstance(no, (ast.Tuple, ast.List)):
        return all(_e_literal_puro(elemento) for elemento in no.elts)
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
        return _e_literal_puro(no.operand)
    return False


def _nomes_alvo_de_atribuicao(alvo: ast.expr) -> list[str]:
    """Extrai nomes simples de um alvo de atribuição — cobre `P_X = ...` e
    `P_X, P_Y = ...` (atribuição múltipla/tupla)."""
    if isinstance(alvo, ast.Name):
        return [alvo.id]
    if isinstance(alvo, (ast.Tuple, ast.List)):
        nomes: list[str] = []
        for elemento in alvo.elts:
            nomes.extend(_nomes_alvo_de_atribuicao(elemento))
        return nomes
    return []


def _detectar_parametro_atribuido(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoParametro]:
    """(a) — nome `P_*` recebendo literal via `Assign`/`AnnAssign`, ou como
    default de argumento de função."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoParametro] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign):
            nomes = [
                nome
                for alvo in no.targets
                for nome in _nomes_alvo_de_atribuicao(alvo)
            ]
            if any(nome.startswith("P_") for nome in nomes) and _e_literal_puro(no.value):
                violacoes.append(
                    ViolacaoParametro(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=f"atribuição literal a {nomes!r}: `{ast.unparse(no)}`",
                    )
                )
        elif isinstance(no, ast.AnnAssign):
            nomes = _nomes_alvo_de_atribuicao(no.target)
            if (
                any(nome.startswith("P_") for nome in nomes)
                and no.value is not None
                and _e_literal_puro(no.value)
            ):
                violacoes.append(
                    ViolacaoParametro(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=f"atribuição literal a {nomes!r}: `{ast.unparse(no)}`",
                    )
                )
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = no.args
            # Argumentos posicionais/keyword-only com default literal, cujo
            # NOME do parâmetro começa com P_.
            parametros_posicionais = args.posonlyargs + args.args
            defaults_alinhados = list(
                zip(
                    parametros_posicionais[len(parametros_posicionais) - len(args.defaults) :],
                    args.defaults,
                    strict=True,
                )
            )
            for arg, default in defaults_alinhados:
                if arg.arg.startswith("P_") and _e_literal_puro(default):
                    violacoes.append(
                        ViolacaoParametro(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=(
                                f"default literal em parâmetro de função "
                                f"{arg.arg!r}: `{ast.unparse(default)}`"
                            ),
                        )
                    )
            for arg, default_talvez in zip(args.kwonlyargs, args.kw_defaults, strict=True):
                if default_talvez is None:
                    continue
                default = default_talvez
                if arg.arg.startswith("P_") and _e_literal_puro(default):
                    violacoes.append(
                        ViolacaoParametro(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=(
                                f"default literal em parâmetro de função "
                                f"{arg.arg!r}: `{ast.unparse(default)}`"
                            ),
                        )
                    )

    return violacoes


def _detectar_numero_chamada_sem_prefixo_p(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoParametro]:
    """(b.1) — toda chamada `algo.numero(...)` cujo primeiro argumento é uma
    string literal que NÃO começa com "P_" é suspeita: o único portal
    legítimo de leitura de parâmetro (`Parametros.numero`) só deveria ser
    chamado com nomes de parâmetro reais."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoParametro] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "numero"):
            continue
        if not no.args:
            continue
        primeiro = no.args[0]
        if isinstance(primeiro, ast.Constant) and isinstance(primeiro.value, str):
            if not primeiro.value.startswith("P_"):
                violacoes.append(
                    ViolacaoParametro(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=(
                            f"Parametros.numero() chamado com string sem prefixo "
                            f"P_: {primeiro.value!r} em `{ast.unparse(no)}`"
                        ),
                    )
                )

    return violacoes


def _detectar_valor_decimal_suspeito(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoParametro]:
    """(b.2) — valor decimal sabidamente de parâmetro (lista curada) aparecendo
    como literal Python solto em `engine/` (fora de string, fora de
    docstring — `ast.Constant` numérico ou string convertível diretamente)."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoParametro] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant):
            continue
        valor = no.value
        texto: str | None = None
        if isinstance(valor, (int, float)):
            texto = str(valor)
        elif isinstance(valor, str):
            texto = valor
        if texto is not None and texto in VALORES_DECIMAIS_SUSPEITOS:
            violacoes.append(
                ViolacaoParametro(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao=f"literal decimal suspeito de parâmetro: {valor!r}",
                )
            )

    return violacoes


def test_nenhum_parametro_atribuido_no_codigo() -> None:
    """(a) — nenhum nome `P_*` recebe literal diretamente em `engine/`."""
    violacoes: list[ViolacaoParametro] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_parametro_atribuido(codigo_fonte, str(arquivo)))

    mensagem = "parâmetro P_* atribuído por literal em engine/ (AC-17):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_toda_chamada_numero_usa_prefixo_p() -> None:
    """(b.1) — toda chamada a `Parametros.numero(...)` em `engine/` usa uma
    string que começa com "P_"."""
    violacoes: list[ViolacaoParametro] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_numero_chamada_sem_prefixo_p(codigo_fonte, str(arquivo)))

    mensagem = "chamada a .numero() sem prefixo P_ em engine/ (AC-17):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_nenhum_valor_decimal_suspeito_solto() -> None:
    """(b.2) — nenhum valor decimal da lista curada (reduções/piso de
    FATOR_SEGURANCA) aparece como literal solto em `engine/`."""
    violacoes: list[ViolacaoParametro] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_valor_decimal_suspeito(codigo_fonte, str(arquivo)))

    mensagem = "literal decimal sabidamente de parâmetro em engine/ (AC-17):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_detector_pega_caso_proposital_de_parametro_atribuido() -> None:
    """Prova que o detector de AST pega uma violação de verdade, sem precisar
    commitar um trecho quebrado em `engine/` real (que ficaria quebrado para
    sempre). O trecho é construído como STRING, parseado isoladamente, e
    nunca executado como código real do projeto — só alimenta
    `_detectar_parametro_atribuido`.

    É exatamente o caso do critério de aceite de T-10: introduzir
    `P_PISO_CAPACIDADE_ABSOLUTO = 300` em `engine/` deve fazer o teste falhar.
    """
    codigo_com_violacao = """
from decimal import Decimal

P_PISO_CAPACIDADE_ABSOLUTO = 300

def alguma_funcao() -> None:
    pass
"""
    violacoes = _detectar_parametro_atribuido(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, (
        "esperava que o detector pegasse `P_PISO_CAPACIDADE_ABSOLUTO = 300`, obteve 0 violações"
    )
    assert any("P_PISO_CAPACIDADE_ABSOLUTO" in v.descricao for v in violacoes)
    assert violacoes[0].linha == 4


def test_detector_pega_caso_proposital_de_default_de_argumento() -> None:
    """Mesma prova, para o sub-caso de `P_*` como default de argumento de
    função — também coberto pela heurística (a)."""
    codigo_com_violacao = """
def calcular(algo: int, P_FATOR_SEGURANCA_MINIMO: float = 0.6) -> int:
    return algo
"""
    violacoes = _detectar_parametro_atribuido(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse o default literal do parâmetro P_*"
    assert any("P_FATOR_SEGURANCA_MINIMO" in v.descricao for v in violacoes)


def test_detector_pega_chamada_numero_sem_prefixo() -> None:
    """Prova (b.1): `parametros.numero("PISO")` (sem prefixo `P_`) é pego."""
    codigo_com_violacao = """
def usar(parametros):
    return parametros.numero("PISO_SEM_PREFIXO")
"""
    violacoes = _detectar_numero_chamada_sem_prefixo_p(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse .numero() sem prefixo P_"


def test_detector_pega_valor_decimal_suspeito_solto() -> None:
    """Prova (b.2): `Decimal('0.20')` solto (fora de uma atribuição a nome
    P_*) é pego pela lista curada."""
    codigo_com_violacao = """
from decimal import Decimal

def calcular_algo() -> Decimal:
    return Decimal("0.20") + Decimal("1")
"""
    violacoes = _detectar_valor_decimal_suspeito(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse o literal '0.20' solto"
