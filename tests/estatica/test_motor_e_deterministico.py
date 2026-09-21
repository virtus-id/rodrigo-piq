"""Lint estático: nenhuma fonte de não-determinismo importada em `engine/` —
NFR "Determinismo" (`specs/motor-calculo.spec.md` §5).

"Mesma entrada e mesma versão de parâmetros produzem exatamente a mesma
saída. Nenhuma dependência de relógio, ordem de iteração não especificada ou
aleatoriedade." `engine/estado.py::EstadoFinanceiro.DATA_REFERENCIA` já
modela a data como INPUT explícito (nunca `date.today()`) — este teste
garante que o texto-fonte de `engine/` nunca importa as fontes de
não-determinismo mais comuns em Python: relógio (`datetime.now`,
`date.today`), aleatoriedade (`random`) e identificador não-reprodutível
(`uuid4`).

Heurística de detecção e sua limitação DECLARADA (a tarefa pede para cobrir
"pelo menos os imports diretos, que é o caso mais comum e mais fácil de
detectar estaticamente")
-----------------------------------------------------------------------------
Cobertos, por AST:

- `from datetime import now` / `from datetime import date` **seguido de uso**
  `date.today()` seria o padrão mais comum para chegar à data corrente sem
  importar `now` diretamente — mas `date` também é o tipo legítimo do campo
  `DATA_REFERENCIA` (`engine/estado.py`), então proibir `from datetime import
  date` INTEIRO derrubaria código correto. A heurística adotada, portanto, é
  mais cirúrgica: proíbe `from datetime import now` (o método `now` de
  `datetime.datetime`, sempre não-determinístico) e QUALQUER uso do atributo
  `.now(` ou `.today(` em uma chamada (`ast.Call` cujo `func` é
  `ast.Attribute` com `attr` em `{"now", "today"}`) — isso pega tanto
  `datetime.now()` quanto `date.today()`, sem proibir a IMPORTAÇÃO do tipo
  `date` em si (que é legítima e já usada em `engine/estado.py`).
- `import random` / `from random import ...` — qualquer forma.
- `from uuid import uuid4` (ou `import uuid` seguido de `uuid.uuid4()`) —
  cobertos via `ast.ImportFrom`/`ast.Import` para o nome `uuid4`/módulo
  `uuid`, mais o mesmo padrão de chamada de atributo (`.uuid4(`) usado para
  `now`/`today`.

**Limitação documentada, citada explicitamente pelo enunciado da tarefa**:
"uso indireto via alias complexo pode escapar da heurística". Exemplos que
este lint NÃO pega: `import datetime as dt; agora = getattr(dt, "no" + "w")`
(reflexão dinâmica), reexportar `now` sob outro nome em um módulo fora de
`engine/` e importar esse wrapper (a violação real estaria no módulo
intermediário, fora do escopo desta varredura, que só cobre `engine/`), ou
qualquer chamada de função de terceiro que internamente use relógio/
aleatoriedade sem que `engine/` importe `datetime`/`random`/`uuid` diretamente
(esse caso é fora do alcance de qualquer lint estático de import — exigiria
análise transitiva de todo o grafo de dependências, não coberta aqui).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

_ATRIBUTOS_NAO_DETERMINISTICOS: Final[frozenset[str]] = frozenset({"now", "today", "uuid4"})


@dataclass(frozen=True, slots=True)
class ViolacaoDeterminismo:
    arquivo: str
    linha: int
    descricao: str


def _detectar_violacoes(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoDeterminismo]:
    """Percorre a AST de `codigo_fonte` e devolve toda ocorrência de import
    direto de fonte de não-determinismo, ou de chamada `.now(`/`.today(`/
    `.uuid4(`."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoDeterminismo] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            modulo = no.module or ""
            for alias in no.names:
                nome_importado = alias.name
                if modulo == "datetime" and nome_importado == "now":
                    violacoes.append(
                        ViolacaoDeterminismo(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao="`from datetime import now`",
                        )
                    )
                elif modulo == "random":
                    violacoes.append(
                        ViolacaoDeterminismo(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=f"`from random import {nome_importado}`",
                        )
                    )
                elif modulo == "uuid" and nome_importado in ("uuid4", "UUID"):
                    violacoes.append(
                        ViolacaoDeterminismo(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=f"`from uuid import {nome_importado}`",
                        )
                    )
        elif isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name == "random" or alias.name.startswith("random."):
                    violacoes.append(
                        ViolacaoDeterminismo(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=f"`import {alias.name}`",
                        )
                    )
                elif alias.name == "uuid":
                    violacoes.append(
                        ViolacaoDeterminismo(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao="`import uuid`",
                        )
                    )
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            if no.func.attr in _ATRIBUTOS_NAO_DETERMINISTICOS:
                violacoes.append(
                    ViolacaoDeterminismo(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=f"chamada `.{no.func.attr}(...)`: `{ast.unparse(no)}`",
                    )
                )

    return violacoes


def test_motor_e_deterministico() -> None:
    """NFR Determinismo — nenhum import direto de `datetime.now`, `random`,
    `uuid4`, nem chamada `.now()`/`.today()`/`.uuid4()` em `engine/`."""
    violacoes: list[ViolacaoDeterminismo] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_violacoes(codigo_fonte, str(arquivo)))

    mensagem = "fonte de não-determinismo detectada em engine/ (NFR Determinismo):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_motor_e_deterministico_detecta_caso_proposital() -> None:
    """Prova que o detector de AST pega uma violação, sem precisar commitar um
    trecho quebrado em `engine/` real. O trecho é construído como STRING,
    parseado isoladamente, e nunca executado como código do projeto.

    É exatamente o caso do critério de aceite de T-10 (adaptado ao NFR de
    determinismo): `from datetime import date` seguido de uso `date.today()`.
    """
    codigo_com_violacao = """
from datetime import date

def obter_data_referencia() -> date:
    return date.today()
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava ao menos 1 violação detectada no caso proposital, obteve 0"
    assert any("today" in v.descricao for v in violacoes)


def test_motor_e_deterministico_detecta_random() -> None:
    """`import random` e `from random import ...` são detectados."""
    codigo_import = "import random\n"
    codigo_from_import = "from random import choice\n"

    violacoes_import = _detectar_violacoes(codigo_import, "caso_proposital.py")
    violacoes_from_import = _detectar_violacoes(codigo_from_import, "caso_proposital.py")

    assert violacoes_import, "esperava detectar `import random`"
    assert violacoes_from_import, "esperava detectar `from random import choice`"


def test_motor_e_deterministico_detecta_uuid4() -> None:
    """`from uuid import uuid4` e a chamada `uuid.uuid4()` são detectados."""
    codigo_from_import = "from uuid import uuid4\n"
    codigo_chamada = """
import uuid

def gerar_id() -> str:
    return str(uuid.uuid4())
"""

    violacoes_from_import = _detectar_violacoes(codigo_from_import, "caso_proposital.py")
    violacoes_chamada = _detectar_violacoes(codigo_chamada, "caso_proposital.py")

    assert violacoes_from_import, "esperava detectar `from uuid import uuid4`"
    assert violacoes_chamada, "esperava detectar `import uuid` + `uuid.uuid4()`"


def test_motor_e_deterministico_nao_reporta_import_de_date_isolado() -> None:
    """Contraprova: `from datetime import date` SOZINHO (sem uso de
    `.today()`) não é reportado — `date` é o tipo legítimo de
    `EstadoFinanceiro.DATA_REFERENCIA` (`engine/estado.py`)."""
    codigo_correto = """
from datetime import date

def usar_data(d: date) -> date:
    return d
"""
    violacoes = _detectar_violacoes(codigo_correto, "caso_correto.py")

    assert not violacoes, (
        f"não esperava violação em `from datetime import date` isolado, obteve: {violacoes}"
    )
