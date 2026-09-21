"""Prova estrutural de `AC-35` para `app/eventos/mapeamento.py` — `RF-28`
(`T-81`).

`AC-35` não é um comportamento a testar chamando a função com um caso de
alteração cadastral (isso já está coberto, como comportamento observável, em
`tests/app_aluno/test_mapeamento_eventos.py`): é uma propriedade do TIPO —
"não existe caminho de código que produza um `EVENTO_RECALCULO` a partir de
alteração cadastral porque o enum não tem membro para isso" (R-04). Este
arquivo prova isso por inspeção estática de dois jeitos:

1. `engine.tipos.EVENTO_RECALCULO` (a fonte real, importada — não uma cópia)
   não tem, entre seus membros, nenhum que represente "alteração cadastral"
   ou "mudança cosmética" — nem por `name`, nem por `value`.
2. `app/eventos/mapeamento.py` não tem chamada a `date.today()`/
   `datetime.now()`/`datetime.utcnow()` — nenhuma leitura de relógio (segundo
   critério de aceite de `T-81`), mesma técnica AST de
   `test_sem_relogio_em_montagem.py` (T-51), restrita a `app/eventos/`.

Técnica igual à dos demais testes estáticos do backlog (`test_fronteira_
import_engine.py`, T-06; `test_sem_relogio_em_montagem.py`, T-51):
`ast.parse` sobre o texto do arquivo, nunca `importlib`/exec para a checagem
de relógio; para a checagem do enum, importar `EVENTO_RECALCULO` é seguro e
não um `exec` de código de aplicação — é o próprio tipo consumido por
`engine/eventos.py::avaliar_gatilho_recalculo`.

REGRAS: `RF-28`, `AC-35`
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

from engine.tipos import EVENTO_RECALCULO

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
ARQUIVO_MAPEAMENTO = RAIZ_PROJETO / "app" / "eventos" / "mapeamento.py"

# Fragmentos que, se aparecessem em `name` ou `value` de um membro do enum,
# indicariam que alguém adicionou um membro para alteração cadastral/cosmética
# — o que violaria R-04. Usados só para auditar o enum REAL importado acima,
# nunca para construir um enum sintético.
_FRAGMENTOS_DE_ALTERACAO_CADASTRAL: Final[tuple[str, ...]] = (
    "CADASTRAL",
    "COSMETIC",
    "RENOMEA",
    "APELIDO",
    "ROTULO",
    "CORRECAO_TEXTUAL",
)

NOMES_DE_CHAMADA_DE_RELOGIO: Final[frozenset[str]] = frozenset({"today", "now", "utcnow"})
NOMES_DE_CLASSE_DE_RELOGIO: Final[frozenset[str]] = frozenset({"date", "datetime"})


def test_evento_recalculo_nao_tem_membro_para_alteracao_cadastral_ac_35() -> None:
    """Prova estrutural central de `AC-35`: nenhum `name`/`value` de
    `EVENTO_RECALCULO` (o enum REAL de `engine/tipos.py`, T-05) contém um
    fragmento que indicaria "alteração cadastral" ou "mudança cosmética" —
    a ausência é do próprio tipo, não de uma checagem de runtime."""
    for membro in EVENTO_RECALCULO:
        nome_e_valor = f"{membro.name} {membro.value}".upper()
        for fragmento in _FRAGMENTOS_DE_ALTERACAO_CADASTRAL:
            assert fragmento not in nome_e_valor, (
                f"EVENTO_RECALCULO.{membro.name} parece representar alteração "
                f"cadastral/cosmética — violaria R-04/AC-35 (o enum não pode "
                f"ter esse membro)"
            )


def test_evento_recalculo_so_tem_os_membros_esperados_da_canonica() -> None:
    """Segunda camada da mesma prova: fixa a lista EXATA de membros
    esperados (quitação confirmada + os dez eventos materiais externos da
    canônica, `piq-app-spec.md` linha 94) — qualquer membro NOVO precisa ser
    revisado deliberadamente contra a canônica antes deste teste ser
    atualizado, o que impede uma "alteração cadastral" de entrar disfarçada
    de nome genérico no futuro."""
    nomes_esperados = {
        "QUITACAO_CONFIRMADA",
        "ALTERACAO_RENDA",
        "ALTERACAO_DESPESAS",
        "NOVA_DIVIDA",
        "RENEGOCIACAO_EXECUTADA",
        "TROCA_EXECUTADA",
        "RECURSO_EXTRAORDINARIO",
        "INFORMACAO_MATERIAL_CONHECIDA",
        "MUDANCA_PATRIMONIAL",
        "PROPOSTA_TEMPORARIA",
        "ALTERACAO_RISCO",
        "OUTRO_MATERIAL",
    }
    nomes_reais = {membro.name for membro in EVENTO_RECALCULO}

    assert nomes_reais == nomes_esperados


def test_sem_relogio_em_app_eventos_mapeamento_t_81() -> None:
    """Segundo critério de aceite de `T-81`: nenhuma chamada a
    `date.today()`/`datetime.now()`/`datetime.utcnow()` em
    `app/eventos/mapeamento.py` — a função é pura sobre a resposta recebida,
    e "virada de mês" não pode disparar nada porque o módulo nem lê o
    relógio."""
    assert ARQUIVO_MAPEAMENTO.is_file(), f"arquivo esperado não encontrado: {ARQUIVO_MAPEAMENTO}"
    codigo_fonte = ARQUIVO_MAPEAMENTO.read_text(encoding="utf-8")
    violacoes = _chamadas_de_relogio(codigo_fonte, str(ARQUIVO_MAPEAMENTO))

    assert not violacoes, (
        "leitura de relógio em app/eventos/mapeamento.py (T-81, segundo "
        f"critério): {violacoes}"
    )


def test_detector_pega_relogio_sintetico_em_mapeamento_de_eventos() -> None:
    """Prova negativa da técnica de detecção: um caso SINTÉTICO com
    `date.today()` é pego pelo mesmo detector usado no teste real acima —
    garante que `test_sem_relogio_em_app_eventos_mapeamento_t_81` não passa
    só porque o detector está incapaz de encontrar violação nenhuma."""
    codigo_com_violacao = """
from datetime import date

def evento_por_virada_de_mes():
    return date.today()
"""
    violacoes = _chamadas_de_relogio(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse date.today()"


def _chamadas_de_relogio(codigo_fonte: str, nome_arquivo: str) -> list[int]:
    """Mesma técnica de `tests/app_aluno/estatica/test_sem_relogio_em_
    montagem.py` (T-51): `ast.parse`, nunca `importlib`/exec. Devolve as
    linhas onde `date`/`datetime` importados de `datetime` chamam
    `today`/`now`/`utcnow`."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    linhas: list[int] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr not in NOMES_DE_CHAMADA_DE_RELOGIO:
            continue
        dono = no.func.value
        if isinstance(dono, ast.Name) and dono.id in NOMES_DE_CLASSE_DE_RELOGIO:
            linhas.append(no.lineno)
        elif isinstance(dono, ast.Name) and dono.id == "datetime":
            linhas.append(no.lineno)

    return linhas
