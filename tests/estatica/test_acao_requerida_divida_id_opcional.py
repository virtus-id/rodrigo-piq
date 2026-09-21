"""`AcaoRequerida.DIVIDA_ID` relaxado para `str | None` — RF-31, AC-55, EC-21
· plano §R2.9 (procedimento de auditoria), T-86.

`AcaoRequerida.DIVIDA_ID` deixou de ser sempre `str` (`T-79`): a ação de
economia (`TIPO_ACAO="ECONOMIA"`, `RF-33`) não tem dívida associada e usa
`DIVIDA_ID=None`. `EC-21` exige que qualquer consumidor interno do motor que
volte a presumir `str` sem checar `None` primeiro seja pego pelo `mypy
--strict` (comando `build`, `sdd.config.md` §2) — falha visível de tipagem,
nunca comportamento silencioso em runtime.

Mesmo padrão de `tests/estatica/test_ordem_de_derivacao.py` (T-25): a prova de
que a trava é real — e não uma leitura otimista do código — é executar `mypy
--strict` como subprocess sobre um trecho escrito como STRING, sintetizado num
arquivo `.py` temporário FORA da árvore do projeto (nunca importado pela
suíte, para não quebrar a coleta do pytest nem o `build` real), e exigir
`exit code != 0` com o erro de tipagem esperado (`union-attr`, já que `acao.
DIVIDA_ID.upper()` sobre `str | None` sem checagem é um acesso de atributo
sobre `None`).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent

# Trecho SEM checagem: lê `acao.DIVIDA_ID` como se fosse sempre `str`, sem
# `is None`/`is not None` antes — exatamente o consumo que `AC-55`/`EC-21`
# proíbem depois do relaxamento de `RF-31`.
_TRECHO_SEM_CHECAGEM = """
from __future__ import annotations

from engine.gates import AcaoRequerida


def usa_divida_id_sem_checar(acao: AcaoRequerida) -> str:
    # Uso proposital, sem checar None antes — é o que AC-55/EC-21 proíbem.
    return acao.DIVIDA_ID.upper()
"""

# Trecho de controle: o MESMO consumo, mas checando `None` antes — prova que o
# snippet em si é válido e que a falha do trecho acima é da ausência de
# checagem, não de um erro incidental de sintaxe/import.
_TRECHO_COM_CHECAGEM = """
from __future__ import annotations

from engine.gates import AcaoRequerida


def usa_divida_id_com_checagem(acao: AcaoRequerida) -> str:
    if acao.DIVIDA_ID is None:
        return "ACAO:SEM_DIVIDA"
    return acao.DIVIDA_ID.upper()
"""

# `union-attr`: código de erro do mypy para "atributo/método chamado sobre um
# membro `None` de um tipo união" — exatamente o que `acao.DIVIDA_ID.upper()`
# produz quando `DIVIDA_ID: str | None` não é checado antes.
_CODIGO_DE_ERRO_ESPERADO = "union-attr"


def _rodar_mypy_strict(codigo_fonte: str) -> subprocess.CompletedProcess[str]:
    """Escreve `codigo_fonte` num `.py` temporário FORA da árvore do projeto
    e roda `mypy --strict` contra ele como subprocess, com `cwd` na raiz do
    projeto — para que `engine.*` resolva exatamente como resolve para a
    suíte real (mesmo `pyproject.toml`, mesmo ambiente).

    O arquivo nunca é gravado dentro de `tests/` nem de `engine/`: se fosse,
    o pytest o coletaria (ou o `mypy` real do projeto o incluiria via `files
    = [...]` do `pyproject.toml`) e um trecho propositalmente quebrado
    quebraria a suíte/o `build` inteiros — exatamente o que esta tarefa pede
    para evitar.
    """
    diretorio_temporario = tempfile.mkdtemp(prefix="piq_divida_id_opcional_")
    try:
        arquivo_temporario = Path(diretorio_temporario) / "trecho_sob_teste.py"
        arquivo_temporario.write_text(codigo_fonte, encoding="utf-8")

        return subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", str(arquivo_temporario)],
            cwd=RAIZ_PROJETO,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        for arquivo in Path(diretorio_temporario).glob("*"):
            arquivo.unlink()
        Path(diretorio_temporario).rmdir()


@pytest.mark.regra
def test_AC55_divida_id_sem_checagem_falha_no_mypy_strict() -> None:
    """AC-55/EC-21: consumir `AcaoRequerida.DIVIDA_ID` como `str` sem checar
    `None` antes é recusado pelo `mypy --strict` (`union-attr`) — prova que a
    rede de segurança da varredura de `RF-31` (plano §R2.9) funciona de
    verdade, não é só leitura otimista do código."""
    resultado = _rodar_mypy_strict(_TRECHO_SEM_CHECAGEM)

    assert resultado.returncode != 0, (
        "esperava que o mypy recusasse o uso de DIVIDA_ID sem checagem "
        f"(exit != 0), mas obteve exit={resultado.returncode}\n"
        f"stdout:\n{resultado.stdout}"
    )
    assert _CODIGO_DE_ERRO_ESPERADO in resultado.stdout, (
        f"esperava um erro '{_CODIGO_DE_ERRO_ESPERADO}' ao consumir "
        f"DIVIDA_ID sem checagem, obteve:\n{resultado.stdout}"
    )


@pytest.mark.regra
def test_AC55_divida_id_com_checagem_compila() -> None:
    """Contraprova: o MESMO consumo, checando `is None` antes, passa limpo no
    `mypy --strict` — isola que a falha do teste acima é da AUSÊNCIA de
    checagem, não de um erro incidental de sintaxe/import no snippet."""
    resultado = _rodar_mypy_strict(_TRECHO_COM_CHECAGEM)

    assert resultado.returncode == 0, (
        "esperava que o trecho COM checagem passasse limpo no mypy --strict, "
        f"mas obteve exit={resultado.returncode}\nstdout:\n{resultado.stdout}"
    )
