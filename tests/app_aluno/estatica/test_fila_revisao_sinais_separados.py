"""Separação sintática dos dois sinais de `RF-25` — `AC-25`, `AC-28`, T-66.

**O risco alto que este teste neutraliza (spec §8):** confundir
`REVISAO_HUMANA_OBRIGATORIA` (campo do motor, `S-04`) com
`POLITICA_REVISAO_INTEGRAL_PILOTO` (política de processo do piloto)
produziria um sistema que revisa só uma fração dos casos, violando `PEND-06`
sem ninguém perceber. `AC-25`/`AC-28` testam o COMPORTAMENTO (ver
`tests/app_aluno/test_fila_de_revisao.py`); este teste prova a causa
ESTRUTURAL que garante esse comportamento: os dois identificadores nunca
aparecem juntos numa mesma expressão booleana (`and`/`or`/comparação
combinada) em `app/revisao/fila.py` — nem hoje, nem numa edição futura
descuidada, porque este teste falharia primeiro.

Mesma técnica AST de `test_fronteira_import_engine.py` (T-06) e
`test_fronteira_decimal_unica.py` (RF-13): `ast.parse` sobre o texto do
arquivo, nunca `importlib`/exec. O detector é testado tanto contra o arquivo
REAL do repositório (que deve dar zero violações) quanto contra casos
SINTÉTICOS de violação, parseados isoladamente — para provar que o detector
de fato pegaria a mistura se alguém a introduzisse.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
ARQUIVO_FILA: Final[Path] = RAIZ_PROJETO / "app" / "revisao" / "fila.py"

# Os dois identificadores que NUNCA podem coexistir numa mesma expressão
# booleana — nomes exatos da spec e do código (`sdd.config.md` §7).
POLITICA: Final[str] = "POLITICA_REVISAO_INTEGRAL_PILOTO"
CAMPO_DO_MOTOR: Final[str] = "REVISAO_HUMANA_OBRIGATORIA"


@dataclass(frozen=True, slots=True)
class ViolacaoSinaisMisturados:
    linha: int
    trecho: str


def _nomes_referenciados(no: ast.AST) -> set[str]:
    """Todos os `ast.Name`/`ast.Attribute` (por atributo final, ex.:
    `snapshot.REVISAO_HUMANA_OBRIGATORIA` -> `REVISAO_HUMANA_OBRIGATORIA`)
    dentro da subárvore `no`."""
    nomes: set[str] = set()
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name):
            nomes.add(filho.id)
        elif isinstance(filho, ast.Attribute):
            nomes.add(filho.attr)
    return nomes


def verificar_codigo(codigo_fonte: str) -> list[ViolacaoSinaisMisturados]:
    """Percorre a AST de `codigo_fonte` e devolve toda expressão booleana ou
    comparação combinada (`ast.BoolOp`/`ast.Compare`) cuja subárvore
    referencie SIMULTANEAMENTE `POLITICA_REVISAO_INTEGRAL_PILOTO` e
    `REVISAO_HUMANA_OBRIGATORIA` — a mistura que o critério de aceite
    proíbe."""
    arvore = ast.parse(codigo_fonte)
    violacoes: list[ViolacaoSinaisMisturados] = []

    for no in ast.walk(arvore):
        if not isinstance(no, (ast.BoolOp, ast.Compare)):
            continue

        nomes = _nomes_referenciados(no)
        if POLITICA in nomes and CAMPO_DO_MOTOR in nomes:
            violacoes.append(
                ViolacaoSinaisMisturados(
                    linha=no.lineno,
                    trecho=ast.dump(no),
                )
            )

    return violacoes


def _mensagem(violacoes: list[ViolacaoSinaisMisturados]) -> str:
    return (
        f"{POLITICA!r} e {CAMPO_DO_MOTOR!r} aparecem na mesma expressão booleana "
        "(RF-25 — risco alto da spec §8):\n"
        + "\n".join(f"  linha {v.linha}: {v.trecho}" for v in violacoes)
    )


def test_fila_revisao_nunca_mistura_os_dois_sinais_na_mesma_expressao() -> None:
    """`AC-25`/`AC-28`: sobre o arquivo REAL `app/revisao/fila.py`, nenhuma
    expressão booleana ou comparação combinada referencia
    `POLITICA_REVISAO_INTEGRAL_PILOTO` e `REVISAO_HUMANA_OBRIGATORIA` ao
    mesmo tempo."""
    assert ARQUIVO_FILA.is_file(), f"arquivo esperado não encontrado: {ARQUIVO_FILA}"
    codigo_fonte = ARQUIVO_FILA.read_text(encoding="utf-8")

    violacoes = verificar_codigo(codigo_fonte)

    assert not violacoes, _mensagem(violacoes)


def test_fila_revisao_referencia_os_dois_identificadores_em_algum_lugar() -> None:
    """Prova negativa da prova negativa: os dois identificadores REALMENTE
    aparecem no arquivo (um em cada função dedicada) — senão o teste acima
    passaria trivialmente por ausência total dos nomes, o que não provaria
    nada sobre separação."""
    codigo_fonte = ARQUIVO_FILA.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte)
    nomes_do_modulo = _nomes_referenciados(arvore)

    assert POLITICA in nomes_do_modulo
    assert CAMPO_DO_MOTOR in nomes_do_modulo


def test_detector_pega_and_misturando_os_dois_sinais() -> None:
    """Caso sintético: `and` combinando os dois identificadores diretamente —
    exatamente a mistura proibida."""
    codigo_com_violacao = """
POLITICA_REVISAO_INTEGRAL_PILOTO = True

def entra(snapshot):
    return POLITICA_REVISAO_INTEGRAL_PILOTO and snapshot.REVISAO_HUMANA_OBRIGATORIA
"""
    violacoes = verificar_codigo(codigo_com_violacao)

    assert violacoes, "esperava que o detector pegasse `and` misturando os dois sinais"
    assert violacoes[0].linha == 5


def test_detector_pega_or_misturando_os_dois_sinais() -> None:
    """Caso sintético: `or` — a mistura é proibida em qualquer operador
    booleano, não só `and`."""
    codigo_com_violacao = """
POLITICA_REVISAO_INTEGRAL_PILOTO = True

def entra(snapshot):
    return POLITICA_REVISAO_INTEGRAL_PILOTO or snapshot.REVISAO_HUMANA_OBRIGATORIA
"""
    violacoes = verificar_codigo(codigo_com_violacao)

    assert violacoes, "esperava que o detector pegasse `or` misturando os dois sinais"


def test_detector_pega_comparacao_combinada_misturando_os_dois_sinais() -> None:
    """Caso sintético: comparação encadeada (`ast.Compare`) misturando os
    dois sinais — o critério de aceite cita explicitamente "comparação
    combinada" além de `and`/`or`."""
    codigo_com_violacao = """
POLITICA_REVISAO_INTEGRAL_PILOTO = True

def entra(snapshot):
    return POLITICA_REVISAO_INTEGRAL_PILOTO == snapshot.REVISAO_HUMANA_OBRIGATORIA
"""
    violacoes = verificar_codigo(codigo_com_violacao)

    assert violacoes, "esperava que o detector pegasse comparação combinando os dois sinais"


def test_detector_aceita_os_dois_sinais_em_funcoes_separadas() -> None:
    """Prova negativa: os dois identificadores usados em funções DIFERENTES,
    cada expressão booleana só com um deles — o padrão real adotado por
    `app/revisao/fila.py` (`entra_na_fila_de_revisao`/`e_caso_metodologico_
    S04`) não é uma violação."""
    codigo_permitido = """
POLITICA_REVISAO_INTEGRAL_PILOTO = True

def entra_na_fila_de_revisao(snapshot):
    return POLITICA_REVISAO_INTEGRAL_PILOTO

def e_caso_metodologico_S04(snapshot):
    return snapshot.REVISAO_HUMANA_OBRIGATORIA
"""
    violacoes = verificar_codigo(codigo_permitido)

    assert not violacoes, _mensagem(violacoes)


def test_detector_aceita_expressao_booleana_com_apenas_um_dos_sinais() -> None:
    """Prova negativa: uma expressão `and`/`or` que combine
    `REVISAO_HUMANA_OBRIGATORIA` com QUALQUER OUTRA coisa que não seja
    `POLITICA_REVISAO_INTEGRAL_PILOTO` não é uma violação — o que é proibido
    é a combinação específica dos dois nomes, não `and`/`or` em si."""
    codigo_permitido = """
def e_metodologico_e_algo_mais(snapshot, outra_condicao):
    return snapshot.REVISAO_HUMANA_OBRIGATORIA and outra_condicao
"""
    violacoes = verificar_codigo(codigo_permitido)

    assert not violacoes, _mensagem(violacoes)
