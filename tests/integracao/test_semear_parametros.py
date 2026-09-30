"""`scripts/semear_parametros.py` escolhe a versão a semear — `T-168`
(`RF-70`, `V-03`).

Sem banco: só a resolução do arquivo canônico. A versão vem do argumento;
sem ele, da versão vigente do piloto (`PARAMETROS_VERSION_VIGENTE`, a mesma
variável que `app/http/rotas_calculo.py` carimba no cálculo); sem as duas,
continua `1.0.1`.

REGRAS: `V-03`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import semear_parametros  # noqa: E402


def test_sem_argumento_nem_vigente_o_padrao_continua_1_0_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PARAMETROS_VERSION_VIGENTE", raising=False)
    assert semear_parametros.arquivo_da_versao(None).name == "parametros-1.0.1.json"


def test_sem_argumento_semeia_a_versao_vigente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", "1.0.2")
    arquivo = semear_parametros.arquivo_da_versao(None)
    assert arquivo.name == "parametros-1.0.2.json"
    assert semear_parametros.carregar_canonico(arquivo)["PARAMETROS_VERSION"] == "1.0.2"


def test_argumento_vence_a_vigente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", "1.0.2")
    assert semear_parametros.arquivo_da_versao("1.0.1").name == "parametros-1.0.1.json"


def test_versao_sem_arquivo_falha_antes_do_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PARAMETROS_VERSION_VIGENTE", raising=False)
    with pytest.raises(SystemExit):
        semear_parametros.arquivo_da_versao("9.9.9")
