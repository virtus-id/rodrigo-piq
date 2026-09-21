"""`Diagnostico.RESERVA_MOBILIZAVEL` retipado para `DinheiroTalvez` — RF-41,
AC-68, US-15 · §13.1 Regra 3 · plano R3.10.2, T-98.

`Diagnostico.RESERVA_MOBILIZAVEL` deixou de ser `Dinheiro` (placeholder de
`T-90`): a §13.1 Regra 3 admite o estado **DESCONHECIDA** — o usuário
respondeu "prefiro decidir somente depois de ver a análise" ou "não sei", ou
a própria `RESERVA_TOTAL` é desconhecida. A §13.1 é enfática em que esse
estado **não** é convertido silenciosamente em zero: "não sei quanto o
usuário aceita mobilizar" e "o usuário não aceita mobilizar nada" são fatos
diferentes, e só o primeiro é pendência a registrar.

`AC-68` exige que qualquer consumidor que volte a tratar apenas o ramo
`Dinheiro` — somando, comparando ou passando o campo onde se espera
`Decimal` — sem cobrir o ramo `Desconhecido` seja pego pelo `mypy --strict`
(comando `build`, `sdd.config.md` §2): falha visível de tipagem, nunca um
`TypeError` em runtime nem, pior, um zero silencioso.

Mesmo padrão de `tests/estatica/test_acao_requerida_divida_id_opcional.py`
(T-86): a prova de que a trava é real — e não uma leitura otimista do código
— é executar `mypy --strict` como subprocess sobre um trecho escrito como
STRING, sintetizado num arquivo `.py` temporário FORA da árvore do projeto
(nunca importado pela suíte, para não quebrar a coleta do pytest nem o
`build` real), e exigir `exit code != 0` com o erro de tipagem esperado.

Nota de escopo: este teste prova o **tipo**, não o valor. Ligar
`derivar_RESERVA_MOBILIZAVEL` ao `calcular_diagnostico` é `T-114`.
`ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro` e por isso aparece aqui
como contraprova — não existe caminho da §13 em que ele seja desconhecido
(plano R3.4.6).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent

# Trecho SEM checagem: lê `diagnostico.RESERVA_MOBILIZAVEL` como se fosse
# sempre `Dinheiro`, somando-o a um `Decimal` sem distinguir o ramo
# `Desconhecido` antes — exatamente o consumo que `AC-68` proíbe depois do
# retipamento de `RF-41`.
_TRECHO_SEM_CHECAGEM = """
from __future__ import annotations

from decimal import Decimal

from engine.diagnostico import Diagnostico


def usa_reserva_mobilizavel_sem_checar(diagnostico: Diagnostico) -> Decimal:
    # Uso proposital, sem distinguir DESCONHECIDO antes — é o que AC-68
    # proíbe: trataria "não sei" como se fosse um número.
    return diagnostico.RESERVA_MOBILIZAVEL + Decimal("1")
"""

# Trecho de controle: o MESMO consumo, mas checando `is DESCONHECIDO` antes —
# prova que o snippet em si é válido e que a falha do trecho acima é da
# ausência de checagem, não de um erro incidental de sintaxe/import.
_TRECHO_COM_CHECAGEM = """
from __future__ import annotations

from decimal import Decimal

from engine.diagnostico import Diagnostico
from engine.tipos import DESCONHECIDO


def usa_reserva_mobilizavel_com_checagem(diagnostico: Diagnostico) -> Decimal:
    # `is DESCONHECIDO`, nunca "é falsy": `dinheiro(0)` é valor legítimo e
    # soma normalmente (mesmo padrão de `somar_ATAQUE_IMEDIATO_POTENCIAL`).
    if diagnostico.RESERVA_MOBILIZAVEL is DESCONHECIDO:
        return Decimal("1")
    return diagnostico.RESERVA_MOBILIZAVEL + Decimal("1")
"""

# Contraprova do escopo (plano R3.4.6): `ATAQUE_IMEDIATO_RECOMENDADO` NÃO foi
# retipado "por simetria" — continua `Dinheiro` e portanto soma direto, sem
# checagem alguma. Se alguém o retipar por engano, este trecho para de
# compilar e o teste falha.
_TRECHO_ATAQUE_IMEDIATO_RECOMENDADO = """
from __future__ import annotations

from decimal import Decimal

from engine.diagnostico import Diagnostico


def usa_ataque_imediato_recomendado(diagnostico: Diagnostico) -> Decimal:
    # Sem checagem de DESCONHECIDO: correto, porque o campo é `Dinheiro`.
    return diagnostico.ATAQUE_IMEDIATO_RECOMENDADO + Decimal("1")
"""

# `operator`: código de erro do mypy para "operador não suportado entre os
# tipos" — exatamente o que `diagnostico.RESERVA_MOBILIZAVEL + Decimal(...)`
# produz quando `RESERVA_MOBILIZAVEL: Dinheiro | Desconhecido` não é
# discriminado antes (não se soma um `Desconhecido` a um `Decimal`).
_CODIGO_DE_ERRO_ESPERADO = "operator"


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
    diretorio_temporario = tempfile.mkdtemp(prefix="piq_reserva_mobilizavel_talvez_")
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
def test_AC68_reserva_mobilizavel_sem_checagem_falha_no_mypy_strict() -> None:
    """AC-68/RF-41: consumir `Diagnostico.RESERVA_MOBILIZAVEL` como `Dinheiro`
    puro, sem distinguir `DESCONHECIDO` antes, é recusado pelo `mypy --strict`
    (`operator`) — prova que a rede de segurança da varredura de `RF-41`
    (plano §R3.10.2) funciona de verdade, não é só leitura otimista do
    código."""
    resultado = _rodar_mypy_strict(_TRECHO_SEM_CHECAGEM)

    assert resultado.returncode != 0, (
        "esperava que o mypy recusasse o uso de RESERVA_MOBILIZAVEL sem "
        f"checagem (exit != 0), mas obteve exit={resultado.returncode}\n"
        f"stdout:\n{resultado.stdout}"
    )
    assert _CODIGO_DE_ERRO_ESPERADO in resultado.stdout, (
        f"esperava um erro '{_CODIGO_DE_ERRO_ESPERADO}' ao consumir "
        f"RESERVA_MOBILIZAVEL sem checagem, obteve:\n{resultado.stdout}"
    )


@pytest.mark.regra
def test_AC68_reserva_mobilizavel_com_checagem_compila() -> None:
    """Contraprova: o MESMO consumo, checando `is DESCONHECIDO` antes, passa
    limpo no `mypy --strict` — isola que a falha do teste acima é da AUSÊNCIA
    de checagem, não de um erro incidental de sintaxe/import no snippet."""
    resultado = _rodar_mypy_strict(_TRECHO_COM_CHECAGEM)

    assert resultado.returncode == 0, (
        "esperava que o trecho COM checagem passasse limpo no mypy --strict, "
        f"mas obteve exit={resultado.returncode}\nstdout:\n{resultado.stdout}"
    )


@pytest.mark.regra
def test_AC68_ataque_imediato_recomendado_continua_dinheiro() -> None:
    """Plano R3.4.6: `ATAQUE_IMEDIATO_RECOMENDADO` NÃO foi retipado "por
    simetria" — não existe caminho da §13 em que ele seja desconhecido. Somá-lo
    a um `Decimal` SEM checagem alguma compila limpo; se alguém o retipar para
    `DinheiroTalvez` por engano, este teste falha e a divergência aparece."""
    resultado = _rodar_mypy_strict(_TRECHO_ATAQUE_IMEDIATO_RECOMENDADO)

    assert resultado.returncode == 0, (
        "ATAQUE_IMEDIATO_RECOMENDADO deve continuar `Dinheiro` (plano "
        "R3.4.6): somá-lo sem checar DESCONHECIDO tem de compilar, mas "
        f"obteve exit={resultado.returncode}\nstdout:\n{resultado.stdout}"
    )
