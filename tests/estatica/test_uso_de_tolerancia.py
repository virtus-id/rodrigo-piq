"""Lint estático: `assertar_monetario` nunca pode ser aplicado a símbolo de
tolerância zero.

RF-12, NFR "Tolerância de homologação" (specs/motor-calculo.spec.md §5;
plans/motor-calculo.plan.md §9): `± R$ 0,05` é exclusivo de valor monetário
ACUMULADO. A lista abaixo — método recomendado, ordem de quitação, gates,
status de dívida estratégico, status do método, status da ordem, número de
meses, mês da primeira vitória, `D*`, aplicação de resíduo, gatilho de
recálculo, `NAO_APLICAVEL`/`PROVISORIO` e, desde a Rodada 3,
`RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_RECOMENDADO` e `NECESSIDADE_RESIDUAL`
— exige `assertar_exato`.

Heurística de detecção (decisão de implementação desta tarefa)
----------------------------------------------------------------
Este é um lint por AST, não uma checagem de tipos: percorremos toda chamada
`assertar_monetario(obtido, esperado)` encontrada em `tests/**/*.py` e
inspecionamos, para CADA argumento posicional, o(s) identificador(es) textuais
que compõem a expressão (nome de variável simples, atributo `.NOME`, ou
subscrição `["NOME"]`/['NOME']). Se qualquer um desses identificadores casar
(por igualdade de string, não por valor em runtime) com um símbolo da lista
proibida — incluindo casamento parcial para os símbolos compostos como "D*"
(convertido para o padrão de nome `D_ESTRELA`/"D asterisco" tratado à parte, ver
`_menciona_simbolo_proibido`) — a chamada é reportada como violação, citando
arquivo e linha.

Isso é uma heurística por nome de identificador, não uma prova por tipo: uma
variável chamada `total_pago` que por acaso guardasse um `STATUS_METODO` não
seria pega, e uma variável chamada `status_metodo_texto_livre` seria pega por
falso positivo controlado (o projeto prefere falso positivo raro a deixar
passar tolerância errada). Uma abordagem 100% robusta exigiria rastrear tipos
declarados/inferidos até a chamada, o que é overkill para um lint de suíte de
testes — a varredura por nome de identificador é o que a tarefa T-09 pede e é
suficiente para o objetivo: impedir que a tolerância errada vaze por descuido
de quem escreve o teste.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ_TESTES = Path(__file__).resolve().parent.parent

# Símbolos que exigem tolerância zero (plans/motor-calculo.plan.md §9,
# specs/motor-calculo.spec.md §5). Cada entrada é um padrão de identificador —
# comparado por igualdade ou por substring contra os nomes extraídos da AST.
SIMBOLOS_TOLERANCIA_ZERO: tuple[str, ...] = (
    "METODO_RECOMENDADO_PIQ",
    "ORDEM_QUITACAO",
    "GATE_PENDENTE",
    "DIVIDA_STATUS_ESTRATEGICO",
    "STATUS_METODO",
    "ORDEM_STATUS",
    "MESES_ATE_QUITACAO",
    "NUMERO_DE_MESES",
    "MESES_PRIMEIRA_VITORIA",
    "APLICACAO_DE_RESIDUO",
    "APLICACAO_RESIDUO",
    "GATILHO_DE_RECALCULO",
    "GATILHO_RECALCULO",
    "NAO_APLICAVEL",
    "PROVISORIO",
    # Rodada 3 — NFR "Tolerância dos `GAB-AI`: zero" (spec §5, `OQ-34`
    # respondida) e plano R3.9.2: os `GAB-AI-01`..`GAB-AI-07` (`AC-70`–`AC-76`)
    # são `MIN`/`MAX`/soma sem acumulação de arredondamento, então
    # `assertar_monetario` (± R$ 0,05) é proibido sobre estes três nomes —
    # a régua é `assertar_exato`, a mesma de `AC-82` (hierarquia com
    # tolerância zero).
    "RESERVA_MOBILIZAVEL",
    "ATAQUE_IMEDIATO_RECOMENDADO",
    "NECESSIDADE_RESIDUAL",
)

# "D*" (D-estrela) é o nome normativo da dívida-alvo do Híbrido; em
# identificador Python vira `D_ESTRELA` (ou variações com underscore/asterisco
# textual). Tratado à parte porque "*" não é caractere válido de identificador.
PADRAO_D_ESTRELA = re.compile(r"^D[_ ]?ESTRELA$|^D\*$")


def _menciona_simbolo_proibido(identificador: str) -> str | None:
    """Devolve o símbolo proibido casado, ou None."""
    nome = identificador.upper()
    for simbolo in SIMBOLOS_TOLERANCIA_ZERO:
        if simbolo in nome:
            return simbolo
    if PADRAO_D_ESTRELA.match(nome):
        return "D*"
    return None


def _identificadores_da_expressao(no: ast.expr) -> list[str]:
    """Extrai todo nome textual (Name, atributo, chave de subscrição string)
    presente na sub-árvore de um argumento de chamada."""
    identificadores: list[str] = []
    for sub in ast.walk(no):
        if isinstance(sub, ast.Name):
            identificadores.append(sub.id)
        elif isinstance(sub, ast.Attribute):
            identificadores.append(sub.attr)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            identificadores.append(sub.value)
    return identificadores


@dataclass(frozen=True, slots=True)
class ViolacaoTolerancia:
    arquivo: str
    linha: int
    simbolo: str
    trecho: str


def _detectar_violacoes(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoTolerancia]:
    """Percorre a AST de `codigo_fonte` e devolve toda chamada a
    `assertar_monetario` cujos argumentos mencionem um símbolo de tolerância
    zero."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoTolerancia] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome_chamada = alvo.id if isinstance(alvo, ast.Name) else (
            alvo.attr if isinstance(alvo, ast.Attribute) else None
        )
        if nome_chamada != "assertar_monetario":
            continue

        for argumento in list(no.args) + [kw.value for kw in no.keywords]:
            for identificador in _identificadores_da_expressao(argumento):
                simbolo = _menciona_simbolo_proibido(identificador)
                if simbolo is not None:
                    violacoes.append(
                        ViolacaoTolerancia(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            simbolo=simbolo,
                            trecho=ast.unparse(no),
                        )
                    )

    return violacoes


def test_uso_de_tolerancia() -> None:
    """`assertar_monetario` nunca pode ser chamado sobre símbolo de tolerância
    zero em nenhum arquivo real de `tests/`."""
    violacoes: list[ViolacaoTolerancia] = []
    for arquivo in sorted(RAIZ_TESTES.rglob("*.py")):
        if arquivo.name == "test_uso_de_tolerancia.py":
            continue  # o próprio lint contém os símbolos proibidos como dados
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_violacoes(codigo_fonte, str(arquivo)))

    mensagem = "uso de assertar_monetario sobre símbolo de tolerância zero:\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — símbolo {v.simbolo!r} em `{v.trecho}`" for v in violacoes
    )
    assert not violacoes, mensagem


def test_uso_de_tolerancia_detecta_caso_proposital() -> None:
    """Prova que o detector de AST pega uma violação, sem precisar commitar um
    teste propositalmente errado no projeto real (que ficaria quebrado).

    O trecho abaixo é construído como string, parseado isoladamente, e nunca
    executado como teste de verdade — só alimenta `_detectar_violacoes`.
    """
    codigo_com_violacao = """
def test_exemplo_proposital_invalido():
    assertar_monetario(obtido.STATUS_METODO, esperado.STATUS_METODO)
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    # Uma violação é registrada por argumento que mencione o símbolo proibido;
    # a chamada acima tem dois argumentos (obtido.STATUS_METODO e
    # esperado.STATUS_METODO), então o detector reporta duas — ambas sobre o
    # mesmo símbolo e a mesma linha, o que já prova que "o lint pega".
    assert violacoes, "esperava ao menos 1 violação detectada no caso proposital, obteve 0"
    assert all(v.simbolo == "STATUS_METODO" for v in violacoes)
    assert all(v.linha == 3 for v in violacoes)


@pytest.mark.parametrize("simbolo_proibido", SIMBOLOS_TOLERANCIA_ZERO)
def test_uso_de_tolerancia_detecta_cada_simbolo_da_lista(simbolo_proibido: str) -> None:
    """Cada símbolo da lista de tolerância zero, se usado como argumento de
    `assertar_monetario`, é detectado — prova item a item da lista do
    critério de aceite de T-09."""
    codigo_com_violacao = (
        "def test_exemplo():\n"
        f"    assertar_monetario(obtido.{simbolo_proibido}, esperado.{simbolo_proibido})\n"
    )
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, f"o detector não pegou o símbolo proibido {simbolo_proibido!r}"


def test_uso_de_tolerancia_detecta_d_estrela() -> None:
    """`D*` (dívida-alvo do Híbrido) vira `D_ESTRELA` em identificador Python."""
    codigo_com_violacao = """
def test_exemplo():
    assertar_monetario(resultado.D_ESTRELA, esperado.D_ESTRELA)
"""
    violacoes = _detectar_violacoes(codigo_com_violacao, "caso_proposital.py")

    assert violacoes
    assert violacoes[0].simbolo == "D*"
