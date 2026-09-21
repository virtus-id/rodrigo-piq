"""Nenhuma aritmética sobre campo de `SnapshotOrdem` — RF-34, AC-42.

Lei nº 3 (`plans/app-aluno.plan.md` §1): *a aplicação não calcula*. `AC-42`
torna essa lei uma propriedade verificável por AST, não uma convenção de code
review: operação aritmética (`+`, `-`, `*`, `/`) cujo operando venha de um
campo de `SnapshotOrdem` só é permitida DENTRO de `engine.precisao.
quantizar_exibicao` (`engine/precisao.py`) — código do motor, congelado,
fora do escopo desta auditoria de qualquer forma (a auditoria é só sobre
`app/`, `collection/` e `report/`, nunca `engine/`).

**Esta suíte GENERALIZA o teste ad-hoc de `T-60`**
(`tests/app_aluno/test_plano.py::
test_ac42_nenhuma_aritmetica_sobre_campo_do_snapshot_em_report_plano`), que
audita só `report/plano.py`. Aqui a mesma técnica varre TODA `app/`,
`collection/` e `report/` — qualquer arquivo novo dessas pastas já nasce
coberto, sem precisar de um teste ad-hoc por módulo. O teste ad-hoc de T-60
continua existindo (redundante com esta suíte, não incorreto — cobre o
mesmo caso real com um detector menos genérico) porque a tarefa não pede
removê-lo e "escopo é lei": `T-61` só cria o arquivo listado nela.

Mesmo estilo de auditoria de `test_fronteira_import_engine.py` (T-06),
`test_sem_conteudo_de_questionario_no_codigo.py` (T-08) e
`test_fronteira_decimal_unica.py` (T-27): `ast.parse` sobre o texto de cada
`.py`, nunca `importlib`/exec; a lógica de detecção (`verificar_arquivo`) é
separada do teste que a aplica sobre o repositório real (zero violações
hoje) dos testes que a exercitam com casos SINTÉTICOS de violação
(`tmp_path`).

## A heurística de detecção e sua limitação declarada

Detectar por AST puro que uma variável "vem de campo de `SnapshotOrdem`" é
mais sutil que os testes irmãos (que reconhecem um padrão sintático direto,
como `Decimal(...)` ou `import engine.gates`): o AST não carrega informação
de tipo, então não há como provar, sem executar o código, que uma expressão
qualquer é *de fato* tipada como `SnapshotOrdem`, `PosicaoOrdem` ou
`Cenario`. A operacionalização adotada — a mesma decisão já registrada no
teste ad-hoc de `T-60` — é **sintática/por convenção de nome**, não
semântica:

- **Um `ast.BinOp` (`+`, `-`, `*`, `/`) é reportado quando um de seus dois
  operandos deriva de um NOME DE VARIÁVEL que sugere snapshot/posição/
  cenário do motor.** "Derivar" significa: o próprio operando é um
  `ast.Name` com esse nome, OU contém em sua sub-árvore (`ast.walk`) um
  `ast.Name` com esse nome — cobre tanto `snapshot.CUSTO_FUTURO_TOTAL + x`
  quanto `(snapshot.CUSTO_FUTURO_TOTAL) + x` quanto
  `soma_parcial + posicao_do_snapshot.valor`.
- **Nomes reconhecidos** (`NOMES_QUE_INDICAM_SNAPSHOT` abaixo): `snapshot`,
  `posicao_do_snapshot`, `cenario`, `cenario_recomendado`, mais qualquer
  nome que **comece ou termine** com `_do_snapshot`/`snapshot_` (cobre
  variações razoáveis como `campo_do_snapshot`, `snapshot_corrente`) —
  mesmo espírito das exceções por nome de função já usadas em `T-27`
  (`desserializar_*`), só que aqui é o inverso: o nome aciona a suspeita,
  não a isenta.
- **Limitação DECLARADA (não é 100% semântica):** este detector não sabe
  que `snapshot` é de fato um `SnapshotOrdem` — ele reage ao NOME da
  variável. Duas consequências, aceitas deliberadamente:
  1. Falso negativo possível: uma variável batizada com um nome fora da
     lista (ex.: `s = snapshot; s.CUSTO_FUTURO_TOTAL + 1`) escaparia da
     detecção. Mitigação: a convenção de nomear a variável que carrega o
     snapshot como `snapshot`/`*_do_snapshot`/`cenario*` já é a que o
     código real do projeto usa (`report/plano.py`,
     `collection/interpolacao.py`, `collection/opcoes_do_motor.py`) — é o
     mesmo argumento de T-60.
  2. Falso positivo possível: uma variável chamada `cenario` que não vem do
     motor (ex.: um "cenário de teste" de outro domínio) seria acusada
     mesmo sem relação com `SnapshotOrdem`. Mitigação: os nomes escolhidos
     são específicos o bastante (nenhum deles é uma palavra genérica como
     `valor` ou `total`) para que essa colisão seja rara e, quando
     acontecer, o remédio é renomear a variável — não afrouxar a regra.

## Exceções permitidas, declaradas explicitamente

1. **Dentro de `quantizar_exibicao`.** A própria função (identificada pelo
   NOME da função que envolve a linha da operação, `ast.FunctionDef.name ==
   "quantizar_exibicao"`) é a exceção normativa da tarefa: "só é permitida
   dentro de `quantizar_exibicao`". Cobre tanto a definição real em
   `engine/precisao.py` (fora do escopo desta auditoria, que só varre
   `app/`, `collection/`, `report/`) quanto qualquer função LOCAL dessas
   três pastas que se chame literalmente `quantizar_exibicao` — não há uma
   hoje, mas o nome da função é o critério, não o módulo em que vive.
2. **Contagem de itens de uma sequência (`len(...)`).** "Contagem de itens
   de uma sequência para exibição" (critério de aceite da tarefa) não é
   aritmética SOBRE VALOR — é sobre uma COLEÇÃO. `len(sequencia)` nunca é
   reportado, mesmo quando `sequencia` deriva de um nome de snapshot (ex.:
   `len(snapshot.ORDEM_QUITACAO)`, o padrão real de
   `report/plano.py::montar_contexto_plano`). Esta exceção é sobre a
   CHAMADA `len(...)` em si — o teste nem entra na sub-árvore de uma
   chamada a `len` ao procurar operandos suspeitos de `BinOp`. Ela NÃO
   isenta um `BinOp` que use o RESULTADO de `len(...)` como operando (ex.:
   `len(snapshot.ORDEM_QUITACAO) + 1` continua violação: ali a aritmética é
   sobre um valor derivado do snapshot, não mais uma contagem pura).

## Segundo alvo: total exibido produzido por `sum(...)`

O critério de aceite "o teste falha se um total exibido for produzido por
`sum(...)` sobre campos do snapshot" é um alvo distinto de `BinOp`: uma
chamada a `sum(...)` cujo argumento deriva de um nome de snapshot é sempre
violação, sem exceção de `quantizar_exibicao` (não há caso legítimo de somar
uma coleção de campos do snapshot em `app/`/`collection/`/`report/` — Lei
nº 3 exige que qualquer total já exista como campo do próprio snapshot,
nunca seja produzido por soma na camada de aplicação).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
PASTAS_VERIFICADAS: Final[tuple[Path, ...]] = (
    RAIZ_PROJETO / "app",
    RAIZ_PROJETO / "collection",
    RAIZ_PROJETO / "report",
)

# Nome da função cujo CORPO é a única exceção normativa a `BinOp` sobre
# campo do snapshot (critério de aceite: "só é permitida dentro de
# quantizar_exibicao"). Critério por NOME de função — mesmo mecanismo de
# `T-27` (`desserializar_*`), aplicado aqui a um nome exato, não a prefixo.
NOME_FUNCAO_EXCECAO: Final[str] = "quantizar_exibicao"

# Nomes de variável que, por convenção do projeto (ver docstring, "a
# heurística e sua limitação"), indicam que a expressão deriva de
# `SnapshotOrdem`/`PosicaoOrdem`/`Cenario`. Lista curada e explícita — nunca
# "qualquer nome com jeito de snapshot".
NOMES_QUE_INDICAM_SNAPSHOT: Final[frozenset[str]] = frozenset(
    {
        "snapshot",
        "posicao_do_snapshot",
        "cenario",
        "cenario_recomendado",
    }
)

# Sufixos/prefixos de nome adicionais que também indicam snapshot — cobre
# variações razoáveis (`campo_do_snapshot`, `snapshot_corrente`) sem exigir
# enumerar cada uma.
SUFIXO_QUE_INDICA_SNAPSHOT: Final[str] = "_do_snapshot"
PREFIXO_QUE_INDICA_SNAPSHOT: Final[str] = "snapshot_"


@dataclass(frozen=True, slots=True)
class ViolacaoAritmeticaSnapshot:
    arquivo: str
    linha: int
    descricao: str


def _nome_indica_snapshot(nome: str) -> bool:
    return (
        nome in NOMES_QUE_INDICAM_SNAPSHOT
        or nome.endswith(SUFIXO_QUE_INDICA_SNAPSHOT)
        or nome.startswith(PREFIXO_QUE_INDICA_SNAPSHOT)
    )


def _deriva_de_snapshot(no: ast.expr) -> bool:
    """`no` é o próprio nome suspeito, ou contém em sua sub-árvore um
    `ast.Name` cujo nome indica snapshot (`snapshot.CAMPO`,
    `posicao_do_snapshot.valores_de_apoio[0]`, `(cenario.PRAZO_TOTAL)` etc.).
    Não desce dentro de uma chamada `len(...)` — essa é a exceção de
    contagem de itens (ver docstring do módulo)."""
    for sub in ast.walk(no):
        if isinstance(sub, ast.Call) and _nome_da_chamada(sub.func) == "len":
            continue
        if isinstance(sub, ast.Name) and _nome_indica_snapshot(sub.id):
            return True
    return False


def _nome_da_chamada(no_func: ast.expr) -> str | None:
    if isinstance(no_func, ast.Name):
        return no_func.id
    if isinstance(no_func, ast.Attribute):
        return no_func.attr
    return None


def _funcoes_que_envolvem_linha(
    arvore: ast.Module,
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]]:
    """Faixa de linhas (`lineno`..`end_lineno`) de cada função/método do
    módulo — usado para decidir se uma operação cai dentro do corpo de
    `quantizar_exibicao` (a exceção normativa)."""
    funcoes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]] = []
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fim = no.end_lineno if no.end_lineno is not None else no.lineno
            funcoes.append((no, no.lineno, fim))
    return funcoes


def _dentro_de_quantizar_exibicao(
    linha: int, funcoes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]]
) -> bool:
    """A `linha` está dentro do corpo de alguma função cujo nome é
    literalmente `quantizar_exibicao`? Usa a função mais interna (menor
    extensão) que contém a linha, para lidar com funções aninhadas."""
    candidatas = [
        (no, inicio, fim) for (no, inicio, fim) in funcoes if inicio <= linha <= fim
    ]
    if not candidatas:
        return False
    mais_interna = min(candidatas, key=lambda item: item[2] - item[1])
    return mais_interna[0].name == NOME_FUNCAO_EXCECAO


def verificar_arquivo(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoAritmeticaSnapshot]:
    """Percorre a AST de `codigo_fonte` e devolve toda violação de `AC-42`:
    aritmética (`+`, `-`, `*`, `/`) sobre campo de snapshot fora de
    `quantizar_exibicao`, e `sum(...)` sobre campos do snapshot. Nunca
    importa o arquivo — só o parseia.
    """
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    funcoes = _funcoes_que_envolvem_linha(arvore)
    violacoes: list[ViolacaoAritmeticaSnapshot] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.BinOp) and isinstance(
            no.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            if _dentro_de_quantizar_exibicao(no.lineno, funcoes):
                continue
            if _deriva_de_snapshot(no.left) or _deriva_de_snapshot(no.right):
                violacoes.append(
                    ViolacaoAritmeticaSnapshot(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=(
                            "operação aritmética sobre campo de SnapshotOrdem "
                            "fora de quantizar_exibicao (AC-42)"
                        ),
                    )
                )
        elif isinstance(no, ast.Call) and _nome_da_chamada(no.func) == "sum":
            if any(_deriva_de_snapshot(argumento) for argumento in no.args):
                violacoes.append(
                    ViolacaoAritmeticaSnapshot(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=(
                            "total produzido por sum(...) sobre campos de "
                            "SnapshotOrdem — Lei nº 3, todo total exibido já "
                            "é campo do próprio snapshot (AC-42)"
                        ),
                    )
                )

    return violacoes


def _mensagem(violacoes: list[ViolacaoAritmeticaSnapshot]) -> str:
    return (
        "aritmética sobre campo de SnapshotOrdem fora de quantizar_exibicao (AC-42):\n"
        + "\n".join(f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes)
    )


def _arquivos_py_das_pastas_verificadas() -> list[Path]:
    arquivos: list[Path] = []
    for pasta in PASTAS_VERIFICADAS:
        if pasta.is_dir():
            arquivos.extend(sorted(pasta.rglob("*.py")))
    return arquivos


def test_ac42_nenhuma_aritmetica_sobre_campo_de_snapshot_no_repositorio_real() -> None:
    """AC-42: `app/`, `collection/` e `report/` — hoje, sobre o repositório
    real — não contêm nenhuma operação aritmética sobre campo de
    `SnapshotOrdem` fora de `quantizar_exibicao`, nem `sum(...)` sobre
    campos do snapshot. `T-60` (`report/plano.py`) e as demais tarefas já
    concluídas seguiram a regra: zero violações esperadas."""
    violacoes: list[ViolacaoAritmeticaSnapshot] = []
    for arquivo in _arquivos_py_das_pastas_verificadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(verificar_arquivo(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_soma_direta_sobre_campo_de_snapshot(tmp_path: Path) -> None:
    """Caso sintético: `snapshot.CUSTO_FUTURO_TOTAL + 1` fora de qualquer
    função de exceção — critério de aceite "o teste falha se qualquer
    arquivo somar ... um campo de SnapshotOrdem"."""
    codigo_com_violacao = """
def exibir_custo_mais_taxa(snapshot):
    return snapshot.CUSTO_FUTURO_TOTAL + 1
"""
    arquivo_temporario = tmp_path / "report" / "caso_proposital_soma.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse a soma sobre snapshot.CUSTO_FUTURO_TOTAL"
    assert violacoes[0].linha == 3
    assert "AC-42" in violacoes[0].descricao


def test_detector_pega_subtracao_multiplicacao_e_divisao(tmp_path: Path) -> None:
    """Critério de aceite: subtrair, multiplicar ou dividir um campo de
    snapshot também é violação — não só somar."""
    codigo_com_violacao = """
def tres_operacoes(cenario, posicao_do_snapshot):
    a = cenario.PRAZO_TOTAL - 1
    b = posicao_do_snapshot.posicao * 2
    c = cenario.CUSTO_FUTURO_TOTAL / 2
    return a, b, c
"""
    arquivo_temporario = tmp_path / "app" / "caso_proposital_tres_operacoes.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert len(violacoes) == 3, _mensagem(violacoes)
    assert {v.linha for v in violacoes} == {3, 4, 5}


def test_detector_pega_total_produzido_por_sum_sobre_campos_do_snapshot(tmp_path: Path) -> None:
    """Critério de aceite: "o teste falha se um total exibido for produzido
    por sum(...) sobre campos do snapshot"."""
    codigo_com_violacao = """
def total_das_posicoes(snapshot):
    return sum(p.valor for p in snapshot.ORDEM_QUITACAO)
"""
    arquivo_temporario = tmp_path / "collection" / "caso_proposital_sum.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse sum(...) sobre snapshot.ORDEM_QUITACAO"
    assert "sum(...)" in violacoes[0].descricao


def test_detector_aceita_a_mesma_soma_dentro_de_quantizar_exibicao(tmp_path: Path) -> None:
    """Prova negativa exigida pela tarefa: a MESMA soma que é violação fora
    de `quantizar_exibicao` é aceita quando o nome da função que a envolve é
    literalmente `quantizar_exibicao` — a exceção normativa desta auditoria
    ("só é permitida dentro de quantizar_exibicao")."""
    codigo_permitido = """
def quantizar_exibicao(snapshot):
    return snapshot.CUSTO_FUTURO_TOTAL + 1
"""
    arquivo_temporario = tmp_path / "report" / "caso_permitido_dentro_da_excecao.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_aceita_len_como_contagem_de_itens(tmp_path: Path) -> None:
    """Exceção explícita: `len(sequencia)` não é aritmética sobre VALOR, é
    contagem de uma COLEÇÃO — sempre permitido, mesmo sobre
    `snapshot.ORDEM_QUITACAO`. Mesmo padrão real de
    `report/plano.py::montar_contexto_plano`
    (`total_de_posicoes = len(snapshot.ORDEM_QUITACAO)`)."""
    codigo_permitido = """
def montar_total_de_posicoes(snapshot):
    total_de_posicoes = len(snapshot.ORDEM_QUITACAO)
    return total_de_posicoes
"""
    arquivo_temporario = tmp_path / "report" / "caso_permitido_len.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_binop_que_usa_resultado_de_len_como_operando(tmp_path: Path) -> None:
    """A exceção de `len(...)` cobre só a CONTAGEM em si — um `BinOp` que
    usa o resultado de `len(snapshot...)` como operando de uma soma
    continua violação: ali a aritmética já não é mais "contagem para
    exibição", é uma conta sobre um valor derivado do snapshot."""
    codigo_com_violacao = """
def total_mais_um(snapshot):
    return len(snapshot.ORDEM_QUITACAO) + 1
"""
    arquivo_temporario = tmp_path / "report" / "caso_proposital_len_mais_soma.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "len(snapshot...) + 1 deveria continuar sendo violação"


def test_detector_aceita_aritmetica_sem_relacao_com_snapshot(tmp_path: Path) -> None:
    """Prova negativa: uma soma comum, sem nenhum operando derivado de nome
    de snapshot, nunca é reportada — o teste não pode confundir toda
    aritmética do projeto com AC-42."""
    codigo_permitido = """
def somar_dois_inteiros(a, b):
    return a + b
"""
    arquivo_temporario = tmp_path / "app" / "caso_permitido_sem_snapshot.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_nomeia_arquivo_e_linha_da_violacao() -> None:
    """O critério de aceite exige (mesmo estilo de T-06/T-08/T-27) que a
    falha nomeie arquivo e linha — verificado diretamente nos campos de
    `ViolacaoAritmeticaSnapshot`."""
    codigo_com_violacao = """
def a():
    pass


def exibir(snapshot):
    return snapshot.CUSTO_FUTURO_TOTAL + 1
"""
    violacoes = verificar_arquivo(codigo_com_violacao, "report/exemplo.py")

    assert len(violacoes) == 1
    assert violacoes[0].arquivo == "report/exemplo.py"
    assert violacoes[0].linha == 7
