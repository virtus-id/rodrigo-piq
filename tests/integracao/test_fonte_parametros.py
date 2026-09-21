"""Paridade arquivo x Postgres de `FonteParametros` — `RF-10`, `RF-12`,
`RF-13`, `T-76`.

Critério de aceite 1 de `T-76`: `FonteParametrosArquivo` e
`FonteParametrosSupabase` carregam `Parametros` IDÊNTICOS campo a campo para
`PARAMETROS_VERSION="1.0.1"` — todos os 38 `P_*` (35 escalares + os 3 arrays
`P_PRESSAO_INDIVIDUAL`/`P_PRESSAO_TOTAL`/`P_ESCALA_0_10`), as 3 `REGRA_*`, e o
carimbo `ENGINE_VERSION`/`PARAMETROS_VERSION`/`DATA_VIGENCIA`. Comparação
sempre com `Decimal` exato — nunca aproximado por conversão `float` no meio
do caminho (RF-12).

Critério de aceite 4: sem `DATABASE_URL`, todo teste deste módulo é pulado
com mensagem explícita — mesmo padrão `@pytest.mark.skipif` de
`tests/regras/test_supabase_adaptadores.py` (T-75).

REGRAS: RF-10, RF-12, RF-13
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.regra

_DATABASE_URL_AUSENTE = not os.environ.get("DATABASE_URL")
_MOTIVO_SKIP = "DATABASE_URL não definida — adaptador Supabase é opcional (plano §2.1)"

_VERSAO: Final[str] = "1.0.1"
_CAMINHO_PARAMETROS: Final[Path] = (
    Path(__file__).resolve().parents[2] / "parameters" / f"parametros-{_VERSAO}.json"
)

# Chaves de carimbo/comportamento — não passam por `numero()` (ver
# `_CHAVES_CARIMBO`/`_CHAVES_REGRA` nos dois adaptadores, mesma partição).
_CHAVES_CARIMBO: Final[frozenset[str]] = frozenset(
    {"ENGINE_VERSION", "PARAMETROS_VERSION", "DATA_VIGENCIA"}
)
_CHAVES_REGRA: Final[frozenset[str]] = frozenset(
    {"REGRA_RESIDUO_ATAQUE", "REGRA_RANQUEAMENTO", "REGRA_DELTA_RESIDUO"}
)


def _nomes_p_estrela() -> tuple[tuple[str, bool], ...]:
    """Lê `parameters/parametros-1.0.1.json` (a fonte canônica) e devolve
    cada chave `P_*` com um marcador `e_array` — nunca uma lista fixada à
    mão no teste, para que a paridade continue válida se a canônica ganhar/
    perder um parâmetro em versão futura (o teste então cobriria o conjunto
    real, não um instantâneo desatualizado)."""
    with _CAMINHO_PARAMETROS.open(encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)
    nomes = []
    for chave, valor in bruto.items():
        if chave.startswith("P_"):
            nomes.append((chave, isinstance(valor, list)))
    return tuple(nomes)


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_paridade_campo_a_campo_arquivo_x_postgres_todos_os_P_estrela() -> None:
    """Critério de aceite 1 de `T-76`: todo `P_*` (35 escalares + 3 arrays)
    carregado por `FonteParametrosArquivo` é IDÊNTICO, com `Decimal` exato,
    ao mesmo `P_*` carregado por `FonteParametrosSupabase`."""
    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.fonte_parametros import FonteParametrosSupabase

    esperado = FonteParametrosArquivo().carregar(_VERSAO)
    obtido = FonteParametrosSupabase().carregar(_VERSAO)

    nomes_p_estrela = _nomes_p_estrela()
    assert len(nomes_p_estrela) == 38, (
        f"esperava 38 P_* na fonte canônica (35 escalares + 3 arrays), "
        f"encontrou {len(nomes_p_estrela)}"
    )

    for nome, e_array in nomes_p_estrela:
        if e_array:
            valor_esperado = esperado._valores[nome]  # noqa: SLF001 — comparação direta de array
            valor_obtido = obtido._valores[nome]  # noqa: SLF001
            assert isinstance(valor_esperado, tuple), f"{nome} deveria ser tuple no arquivo"
            assert isinstance(valor_obtido, tuple), f"{nome} deveria ser tuple no Postgres"
            assert len(valor_obtido) == len(valor_esperado), (
                f"{nome}: tamanho de array diverge — "
                f"arquivo={len(valor_esperado)} postgres={len(valor_obtido)}"
            )
            for indice, (item_esperado, item_obtido) in enumerate(
                zip(valor_esperado, valor_obtido, strict=True)
            ):
                assert isinstance(item_esperado, Decimal), f"{nome}[{indice}] arquivo não é Decimal"
                assert isinstance(item_obtido, Decimal), f"{nome}[{indice}] postgres não é Decimal"
                assert item_obtido == item_esperado, (
                    f"{nome}[{indice}] diverge: arquivo={item_esperado!r} postgres={item_obtido!r}"
                )
        else:
            valor_esperado = esperado.numero(nome)
            valor_obtido = obtido.numero(nome)
            assert isinstance(valor_esperado, Decimal), f"{nome} arquivo não é Decimal"
            assert isinstance(valor_obtido, Decimal), f"{nome} postgres não é Decimal"
            assert valor_obtido == valor_esperado, (
                f"{nome} diverge: arquivo={valor_esperado!r} postgres={valor_obtido!r}"
            )


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_paridade_campo_a_campo_arquivo_x_postgres_REGRA_estrela() -> None:
    """Critério de aceite 1 de `T-76`: as 3 `REGRA_*` (comportamento, não
    número) são idênticas entre os dois adaptadores."""
    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.fonte_parametros import FonteParametrosSupabase

    esperado = FonteParametrosArquivo().carregar(_VERSAO)
    obtido = FonteParametrosSupabase().carregar(_VERSAO)

    for nome in sorted(_CHAVES_REGRA):
        valor_esperado = esperado._valores[nome]  # noqa: SLF001
        valor_obtido = obtido._valores[nome]  # noqa: SLF001
        assert isinstance(valor_esperado, str), f"{nome} arquivo não é str"
        assert isinstance(valor_obtido, str), f"{nome} postgres não é str"
        assert valor_obtido == valor_esperado, (
            f"{nome} diverge: arquivo={valor_esperado!r} postgres={valor_obtido!r}"
        )


@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)
def test_paridade_campo_a_campo_arquivo_x_postgres_carimbo() -> None:
    """Critério de aceite 1 de `T-76`: `ENGINE_VERSION`, `PARAMETROS_VERSION`
    e `DATA_VIGENCIA` são idênticos entre os dois adaptadores."""
    from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
    from persistencia.supabase.fonte_parametros import FonteParametrosSupabase

    esperado = FonteParametrosArquivo().carregar(_VERSAO)
    obtido = FonteParametrosSupabase().carregar(_VERSAO)

    assert obtido.ENGINE_VERSION == esperado.ENGINE_VERSION
    assert obtido.PARAMETROS_VERSION == esperado.PARAMETROS_VERSION
    assert obtido.DATA_VIGENCIA == esperado.DATA_VIGENCIA


def test_skip_gracioso_sem_database_url_nao_e_erro_nem_falha() -> None:
    """Critério de aceite 4 de `T-76`: sem `DATABASE_URL` no ambiente, os
    testes deste módulo aparecem como `skipped` — nunca `failed`/`error`.
    Este teste roda SEMPRE (não é `skipif`) e apenas documenta o motivo
    esperado do skip, para que a suíte padrão continue provando a ausência
    de dependência obrigatória do Supabase mesmo sem rodar o pytest com
    `-rs`."""
    if _DATABASE_URL_AUSENTE:
        assert _MOTIVO_SKIP  # mensagem explícita, não um skip silencioso
    else:
        assert os.environ.get("DATABASE_URL")
