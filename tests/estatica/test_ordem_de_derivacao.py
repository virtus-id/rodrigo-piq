"""A ordem de derivação do grafo (§11.10) é imposta por TIPO, não por
convenção — RF-27, T-24, T-25.

`calcular_diagnostico` (`engine/diagnostico.py`) compõe o grafo `NIVEL_CONTROLE
→ CONFIABILIDADE_DADOS → D.4 → INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE →
FATOR_SEGURANCA → capacidades` chamando cada sub-função com o resultado da
etapa anterior como parâmetro **obrigatório e posicional**
(`derivar_CONFIABILIDADE_DADOS` exige `nivel_controle`,
`derivar_INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` exige `nivel_controle` e
`risco_recaida`, `calcular_fator_seguranca` exige `CONFIABILIDADE_DADOS_ATUAL`
+ as duas classificações de risco). A prova de que essa trava é real — e não
apenas uma leitura otimista do código — é que uma chamada FORA de ordem não
compila. Este módulo prova isso executando `mypy --strict` como subprocess
sobre um trecho de código escrito como STRING, gerado num arquivo `.py`
temporário fora da árvore do projeto (nunca importado pela suíte, para não
quebrar a coleta do pytest) e exigindo `exit code != 0` com um erro do tipo
esperado (`call-arg`/`arg-type`).

Diferente de `tests/estatica/test_uso_de_tolerancia.py` (lint por AST, sem
executar ferramenta externa) e dos quatro testes de `T-10` (ainda pendente,
que varrem `engine/` real por AST): aqui o "arquivo sob teste" não existe no
projeto — é sintetizado em tempo de teste porque o próprio objetivo é provar
uma FALHA de compilação que não pode, por definição, viver em `engine/` real.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent

# Trecho fora de ordem: chama `derivar_CONFIABILIDADE_DADOS` (T-13) passando o
# `PerfilComportamental` no lugar de `NIVEL_CONTROLE` — ou seja, pulando a
# etapa anterior do grafo (`derivar_NIVEL_CONTROLE`, T-12) e tentando usar o
# dado bruto de entrada onde o valor já derivado é exigido. É o mesmo tipo de
# erro que a ordem de derivação da §11.10 precisa impedir silenciosamente
# (RF-27): "a fórmula parece rodar, mas o resultado está errado" — só que
# aqui nem chega a rodar, porque o mypy recusa antes.
_TRECHO_FORA_DE_ORDEM = """
from __future__ import annotations

from engine.comportamento import derivar_CONFIABILIDADE_DADOS
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    REVISAO_SEMANAL,
    PerfilComportamental,
)

perfil = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)

# FORA DE ORDEM: NIVEL_CONTROLE nunca foi derivado (derivar_NIVEL_CONTROLE,
# T-12) — o `perfil` bruto é passado no lugar do NIVEL_CONTROLE exigido.
resultado = derivar_CONFIABILIDADE_DADOS(perfil)
"""

# Trecho de controle: o MESMO fluxo, na ordem correta — prova que o snippet em
# si é válido (a falha do trecho acima é da ORDEM, não de um erro de sintaxe
# ou de import incidental que inflaria falsamente o resultado).
_TRECHO_EM_ORDEM = """
from __future__ import annotations

from engine.comportamento import derivar_CONFIABILIDADE_DADOS, derivar_NIVEL_CONTROLE
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    REVISAO_SEMANAL,
    PerfilComportamental,
)

perfil = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)

# EM ORDEM: NIVEL_CONTROLE é derivado primeiro (T-12) e passado à etapa
# seguinte (T-13), respeitando o grafo da §11.10.
nivel_controle = derivar_NIVEL_CONTROLE(perfil)
resultado = derivar_CONFIABILIDADE_DADOS(nivel_controle, perfil)
"""

# Códigos de erro do mypy que RF-27 espera ver quando a ordem é violada por
# tipo: `call-arg` (faltou o argumento posicional `NIVEL_CONTROLE`) e/ou
# `arg-type` (o `perfil` passado na posição de `NIVEL_CONTROLE` tem tipo
# incompatível). Qualquer um dos dois já prova a trava — não é preciso que os
# dois apareçam juntos, mas nesse trecho específico ambos aparecem.
_CODIGOS_DE_ERRO_ESPERADOS = ("call-arg", "arg-type")


def _rodar_mypy_strict(codigo_fonte: str) -> subprocess.CompletedProcess[str]:
    """Escreve `codigo_fonte` num `.py` temporário FORA da árvore do projeto
    e roda `mypy --strict` contra ele como subprocess, com `cwd` na raiz do
    projeto — para que `engine.*`/`persistencia.*` resolvam exatamente como
    resolvem para a suíte real (mesmo `pyproject.toml`, mesmo ambiente).

    O arquivo nunca é gravado dentro de `tests/`: se fosse, o pytest o
    coletaria (ou o mypy real do projeto o incluiria via `files =
    ["engine", "persistencia", "tests"]` do `pyproject.toml`) e um trecho
    propositalmente quebrado quebraria a suíte inteira — exatamente o que a
    tarefa pede para evitar.
    """
    diretorio_temporario = tempfile.mkdtemp(prefix="piq_ordem_derivacao_")
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
def test_ordem_de_derivacao() -> None:
    """RF-27/§11.10 — chamar `derivar_CONFIABILIDADE_DADOS` fora de ordem
    (sem `NIVEL_CONTROLE` já derivado) é recusado pelo `mypy --strict`, com
    um erro do tipo esperado (`call-arg` e/ou `arg-type`) — prova que a
    ordem de derivação é garantida por tipo, não por convenção."""
    resultado = _rodar_mypy_strict(_TRECHO_FORA_DE_ORDEM)

    assert resultado.returncode != 0, (
        "esperava que o mypy recusasse o trecho fora de ordem (exit != 0), "
        f"mas obteve exit={resultado.returncode}\nstdout:\n{resultado.stdout}"
    )
    assert any(codigo in resultado.stdout for codigo in _CODIGOS_DE_ERRO_ESPERADOS), (
        "esperava um erro do tipo call-arg/arg-type no trecho fora de ordem, "
        f"obteve:\n{resultado.stdout}"
    )


@pytest.mark.regra
def test_ordem_de_derivacao_trecho_de_controle_compila() -> None:
    """Contraprova: o MESMO fluxo, na ordem correta, passa limpo no
    `mypy --strict` — isola que a falha do teste acima é da ORDEM das
    chamadas, não de um erro incidental de sintaxe/import no snippet."""
    resultado = _rodar_mypy_strict(_TRECHO_EM_ORDEM)

    assert resultado.returncode == 0, (
        "esperava que o trecho EM ordem passasse limpo no mypy --strict, "
        f"mas obteve exit={resultado.returncode}\nstdout:\n{resultado.stdout}"
    )
