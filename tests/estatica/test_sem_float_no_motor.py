"""Lint estático: nenhum `float`/ponto flutuante binário em `engine/` — RF-12.

NFR "Precisão" (`specs/motor-calculo.spec.md` §5): "Ponto flutuante binário é
proibido para valores monetários — a tolerância de `± R$ 0,05` da seção 10.3
existe para arredondamento de exibição, não para absorver erro de
representação." `engine/precisao.py::dinheiro()` já recusa `float` em tempo de
execução (T-03); este teste garante que o próprio texto-fonte de `engine/`
nunca contém o padrão em primeiro lugar — defesa em profundidade, e a única
forma de pegar `float`/`math` usado fora do caminho de `dinheiro()` (ex.: uma
variável não-monetária, ou um cálculo que nunca passa pelo construtor).

Heurística de detecção e suas limitações
-----------------------------------------------------------------------------
Três padrões, cada um por AST:

1. **`float` como nome usado** — `ast.Name(id="float")` em qualquer posição
   (chamada `float(x)`, anotação de tipo `x: float`, alias `f = float`).
   Cobre o caso mais comum e mais perigoso: alguém convertendo um `Decimal`
   para `float` "só para imprimir" ou "só para comparar", que reintroduz erro
   de representação binária exatamente onde `RF-12` proíbe.

2. **Literal de ponto flutuante Python** — `ast.Constant` cujo `value` é
   `isinstance(value, float)` (ex.: `0.05`, `1.0`, `3.14`). Este é o único
   jeito de um número decimal aparecer como float SEM passar pelo nome
   `float`: o próprio parser do Python já produz um `float` para qualquer
   literal com ponto decimal fora de uma string — `Decimal("0.05")` está bem
   (a `Decimal` recebe uma STRING, `ast.Constant(value="0.05")`, que é
   `str`, não `float`), mas `Decimal(0.05)` já reintroduziria o float ANTES
   da conversão, e esse literal `0.05` sozinho já é pego por este item,
   independente do que o envolve.

3. **`import math` / `from math import ...`** — qualquer forma de trazer o
   módulo `math` para o namespace. `math` opera inteiramente em `float`
   IEEE-754; não há uso legítimo dele em `engine/` sob a NFR de precisão.

**Exceção deliberada — `isinstance(x, float)`.** `engine/precisao.py::dinheiro()`
e `engine/estado.py::_recusar_float()` citam o nome `float` justamente para
RECUSÁ-LO em tempo de execução (`if isinstance(valor, float): raise
TypeError(...)`) — é a implementação da própria trava de RF-12, o oposto de
"usar float". Sinalizar esse padrão como violação penalizaria o código que
IMPEDE a violação. Por isso `float` como segundo argumento de uma chamada
`isinstance(...)` é a única forma de uso do nome que este lint isenta
explicitamente — qualquer outro uso do nome `float` (conversão, anotação,
alias) continua proibido.

**Limitação documentada.** Assim como os demais lints de AST desta suíte
(`test_uso_de_tolerancia.py`), esta é uma varredura textual/estrutural, não
uma prova de tipo. Não pega: `float` alcançado por reflexão dinâmica
(`getattr(builtins, "flo" + "at")`), nem um valor `float` que chegue de uma
fonte externa não tipada e escape para dentro de `engine/` via `Any` sem
nunca aparecer como literal ou nome `float` no texto-fonte. Esses casos são
cobertos por outra camada (a recusa em tempo de execução de
`engine/precisao.py::dinheiro()` e a checagem de tipo do `mypy --strict`
sobre `Dinheiro = Decimal`), não por este lint.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"


@dataclass(frozen=True, slots=True)
class ViolacaoFloat:
    arquivo: str
    linha: int
    descricao: str


def _nomes_float_isentos_por_isinstance(arvore: ast.AST) -> set[ast.Name]:
    """Coleta os nós `ast.Name(id="float")` que aparecem como SEGUNDO
    argumento de uma chamada `isinstance(x, float)` — a forma canônica de
    RECUSAR float (`engine/precisao.py::dinheiro()`,
    `engine/estado.py::_recusar_float()`), não de usá-lo. Ver exceção
    deliberada na docstring do módulo."""
    isentos: set[ast.Name] = set()
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "isinstance"
            and len(no.args) >= 2
        ):
            segundo_argumento = no.args[1]
            if isinstance(segundo_argumento, ast.Name) and segundo_argumento.id == "float":
                isentos.add(segundo_argumento)
            elif isinstance(segundo_argumento, ast.Tuple):
                # isinstance(x, (float, int)) — mesma isenção por elemento.
                for elemento in segundo_argumento.elts:
                    if isinstance(elemento, ast.Name) and elemento.id == "float":
                        isentos.add(elemento)
    return isentos


def _detectar_violacoes(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoFloat]:
    """Percorre a AST de `codigo_fonte` e devolve toda ocorrência de `float`
    como nome, literal de ponto flutuante, ou import de `math`."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoFloat] = []
    nomes_isentos = _nomes_float_isentos_por_isinstance(arvore)

    for no in ast.walk(arvore):
        # (1) `float` usado como nome — chamada, anotação, alias. Isento:
        # segundo argumento de isinstance(x, float) — ver docstring.
        if isinstance(no, ast.Name) and no.id == "float":
            if no in nomes_isentos:
                continue
            violacoes.append(
                ViolacaoFloat(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao="nome `float` referenciado",
                )
            )
        elif isinstance(no, ast.Attribute) and no.attr == "float":
            # ex.: `numpy.float` — mesmo padrão, coberto por generalidade.
            violacoes.append(
                ViolacaoFloat(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao="atributo `.float` referenciado",
                )
            )
        # (2) literal de ponto flutuante Python.
        elif isinstance(no, ast.Constant) and isinstance(no.value, float):
            violacoes.append(
                ViolacaoFloat(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao=f"literal de ponto flutuante: {no.value!r}",
                )
            )
        # (3) import de math, de qualquer forma.
        elif isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name == "math" or alias.name.startswith("math."):
                    violacoes.append(
                        ViolacaoFloat(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=f"`import {alias.name}`",
                        )
                    )
        elif isinstance(no, ast.ImportFrom):
            if no.module == "math" or (no.module or "").startswith("math."):
                violacoes.append(
                    ViolacaoFloat(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=f"`from {no.module} import ...`",
                    )
                )

    return violacoes


def test_sem_float_no_motor() -> None:
    """RF-12 — nenhuma ocorrência de `float`, literal de ponto flutuante, ou
    `math.*` em nenhum arquivo real de `engine/`."""
    violacoes: list[ViolacaoFloat] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_violacoes(codigo_fonte, str(arquivo)))

    mensagem = "float/math detectado em engine/ (RF-12):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_sem_float_no_motor_detecta_literal_proposital() -> None:
    """Prova que o detector de AST pega uma violação, sem precisar commitar
    um trecho quebrado em `engine/` real. O trecho é construído como
    STRING, parseado isoladamente, e nunca executado como código do projeto.

    É exatamente o caso do critério de aceite de T-10: introduzir `0.05`
    solto em `engine/` deve fazer o teste falhar.
    """
    codigo_com_violacao = """
def calcular_algo() -> float:
    fator = 0.05
    return fator
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    # Duas violações esperadas nesta linha de anotação + a linha do literal:
    # `float` como nome de anotação de retorno, e `0.05` como literal.
    assert violacoes, "esperava ao menos 1 violação detectada no caso proposital, obteve 0"
    descricoes = " | ".join(v.descricao for v in violacoes)
    assert "0.05" in descricoes, f"esperava detectar o literal 0.05, obteve: {descricoes}"


def test_sem_float_no_motor_detecta_nome_float() -> None:
    """`float` usado como nome (chamada de conversão) é detectado, mesmo sem
    literal de ponto flutuante na mesma linha."""
    codigo_com_violacao = """
def converter(valor: str) -> None:
    resultado = float(valor)
    print(resultado)
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse o nome `float` usado como conversão"
    assert any("float" in v.descricao for v in violacoes)


def test_sem_float_no_motor_detecta_import_math() -> None:
    """`import math` e `from math import ...` são detectados."""
    codigo_import = "import math\n"
    codigo_from_import = "from math import sqrt\n"

    violacoes_import = _detectar_violacoes(codigo_import, "caso_proposital.py")
    violacoes_from_import = _detectar_violacoes(codigo_from_import, "caso_proposital.py")

    assert violacoes_import, "esperava detectar `import math`"
    assert violacoes_from_import, "esperava detectar `from math import ...`"


def test_sem_float_no_motor_nao_reporta_isinstance_float() -> None:
    """Contraprova da exceção deliberada: `isinstance(valor, float)` — o
    padrão real usado por `engine/precisao.py::dinheiro()` e
    `engine/estado.py::_recusar_float()` para RECUSAR float em tempo de
    execução — não é reportado como violação."""
    codigo_correto = """
def recusar_float(valor: object) -> None:
    if isinstance(valor, float):
        raise TypeError("float proibido")
"""
    violacoes = _detectar_violacoes(codigo_correto, "caso_correto.py")

    assert not violacoes, (
        f"não esperava violação em isinstance(valor, float) (guarda RF-12), obteve: {violacoes}"
    )


def test_sem_float_no_motor_ainda_detecta_float_fora_de_isinstance() -> None:
    """A isenção é estreita: `float` usado em QUALQUER outro contexto na
    mesma função continua sendo pego, mesmo coexistindo com um
    `isinstance(..., float)` legítimo."""
    codigo_com_violacao = """
def funcao(valor: object) -> None:
    if isinstance(valor, float):
        raise TypeError("float proibido")
    convertido: float = 1.5
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava detectar o `float` de anotação fora do isinstance"


def test_sem_float_no_motor_nao_reporta_decimal_de_string() -> None:
    """Contraprova: `Decimal("0.05")` — literal de STRING, não de float —
    não deve ser reportado. Isola que o lint pega o TIPO `float`, não o
    dígito "0.05" em qualquer contexto textual."""
    codigo_correto = """
from decimal import Decimal

def calcular_algo() -> Decimal:
    fator = Decimal("0.05")
    return fator
"""
    violacoes = _detectar_violacoes(codigo_correto, "caso_correto.py")

    assert not violacoes, (
        f"não esperava violação em Decimal('0.05') (string, não float), obteve: {violacoes}"
    )
