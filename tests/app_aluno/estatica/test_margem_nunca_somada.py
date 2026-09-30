"""Margens nunca somadas; renda líquida do vínculo fora do motor — `AC-138`,
`AC-156` (`T-260`, `RF-89`, `RF-90`, `DE-05`).

**`AC-138`.** A margem aparece sob o seu vínculo pela serialização genérica
da ficha — que não precisa nomear a variável. Então nenhum código de `app/`,
`report/` nem `frontend/src/` lê `VALOR_LIVRE_MARGEM`/`VALOR_TOTAL_MARGEM` pelo
nome: quem os lesse seria quem os somasse. Docstrings e comentários não
contam. E `EstadoFinanceiro` (o estado entregue ao motor) não tem campo de
margem.

**`AC-156`.** `RENDA_LIQUIDA_VINCULO` só existe para a conferência
(`app/montagem/entrada.py`); a montagem do estado nunca a lê.

REGRAS: `AC-138`, `AC-156`
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import Final

from engine.estado import EstadoFinanceiro

_RAIZ: Final[Path] = Path(__file__).resolve().parents[3]
_VALORES_DE_MARGEM: Final[frozenset[str]] = frozenset({"VALOR_LIVRE_MARGEM", "VALOR_TOTAL_MARGEM"})


def _constantes_de_codigo(caminho: Path) -> set[str]:
    """Strings do código Python, sem docstrings."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
    }
    return {
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docstrings
    }


def test_ac138_nenhum_codigo_python_le_o_valor_da_margem() -> None:
    violacoes = [
        str(arquivo.relative_to(_RAIZ))
        for pasta in ("app", "report")
        for arquivo in (_RAIZ / pasta).rglob("*.py")
        if _VALORES_DE_MARGEM & {
            nome
            for constante in _constantes_de_codigo(arquivo)
            for nome in _VALORES_DE_MARGEM
            if nome in constante
        }
    ]
    assert violacoes == []


def test_ac138_nenhum_codigo_do_cliente_le_o_valor_da_margem() -> None:
    violacoes = [
        str(arquivo.relative_to(_RAIZ))
        for extensao in ("*.ts", "*.tsx")
        for arquivo in (_RAIZ / "frontend" / "src").rglob(extensao)
        if any(nome in arquivo.read_text(encoding="utf-8") for nome in _VALORES_DE_MARGEM)
    ]
    assert violacoes == []


def test_ac138_estado_entregue_ao_motor_sem_campo_de_margem() -> None:
    assert [c.name for c in dataclasses.fields(EstadoFinanceiro) if "MARGEM" in c.name] == []


def test_ac156_montagem_do_estado_nunca_le_a_renda_liquida_do_vinculo() -> None:
    estado = _RAIZ / "app" / "montagem" / "estado.py"
    assert "RENDA_LIQUIDA_VINCULO" not in _constantes_de_codigo(estado)
    assert "RENDA_LIQUIDA_VINCULO" in _constantes_de_codigo(
        _RAIZ / "app" / "montagem" / "entrada.py"
    )
