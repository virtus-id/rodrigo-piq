"""Adaptador Supabase/Postgres de `FonteParametros` — RF-13, RF-12, AC-17.

Lê a linha de `motor_calculo.parametros` cuja `PARAMETROS_VERSION` combina
com a versão pedida e constrói um `Parametros` — mesma interface pública de
`persistencia/arquivo/fonte_parametros.py::FonteParametrosArquivo`, trocando
JSON+jsonschema por uma consulta `numeric` ↔ `Decimal` nativa do `psycopg 3`
(RF-12: nenhuma conversão passa por `float`, nem na ida nem na volta).

Direção de dependência: este módulo importa de `engine/` — nunca o
contrário (mesma lei nº 1 de `persistencia/arquivo/fonte_parametros.py`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from engine.parametros import ErroParametros, Parametros
from engine.portas import FonteParametros
from persistencia.supabase.conexao import conectar

REGRAS: Final[tuple[str, ...]] = ("RF-13", "RF-12", "AC-17")

# Nomes de coluna que não são parâmetros numéricos escalares — carimbo
# (Parametros.PARAMETROS_VERSION/ENGINE_VERSION/DATA_VIGENCIA), as três
# REGRA_* de comportamento (texto, não número) e as colunas técnicas da
# tabela. Espelha _CHAVES_CARIMBO do adaptador de arquivo.
_CHAVES_CARIMBO: Final[frozenset[str]] = frozenset(
    {"PARAMETROS_VERSION", "ENGINE_VERSION", "DATA_VIGENCIA", "criado_em"}
)
_CHAVES_REGRA: Final[frozenset[str]] = frozenset(
    {"REGRA_RESIDUO_ATAQUE", "REGRA_RANQUEAMENTO", "REGRA_DELTA_RESIDUO"}
)


class FonteParametrosSupabase(FonteParametros):
    """Lê parâmetros de `motor_calculo.parametros` (Supabase/Postgres).

    Mesmo contrato público de `FonteParametrosArquivo`: `carregar(versao)`
    devolve um `Parametros` validado e carimbado, ou levanta `ErroParametros`
    — nunca um valor embutido no motor como fallback (AC-17). A validação de
    esquema aqui é a própria coluna `numeric NOT NULL`/tipo da tabela (ver
    `migracoes/001_inicial.sql`): o banco recusa a gravação de um parâmetro
    fora do formato antes mesmo da leitura, papel que `jsonschema` cumpre no
    adaptador de arquivo.
    """

    def carregar(self, versao: str) -> Parametros:
        """RF-13/AC-17: busca a linha de `PARAMETROS_VERSION = versao` em
        `motor_calculo.parametros` e constrói um `Parametros`. `ErroParametros`
        se a versão não existir na tabela — nunca `None`/objeto fabricado.
        """
        with conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                'SELECT * FROM motor_calculo.parametros WHERE "PARAMETROS_VERSION" = %s',
                (versao,),
            )
            linha = cursor.fetchone()
            if linha is None:
                raise ErroParametros(
                    f"Nenhuma linha em motor_calculo.parametros para "
                    f"PARAMETROS_VERSION={versao!r}"
                )
            colunas = [descricao.name for descricao in cursor.description or ()]
            bruto = dict(zip(colunas, linha, strict=True))

        return _construir_parametros(bruto)


def _construir_parametros(bruto: dict[str, object]) -> Parametros:
    """Monta `_valores` a partir da linha lida do Postgres: `numeric` chega
    do `psycopg 3` já como `Decimal` nativo (RF-12 — nenhuma conversão por
    `float` na fronteira do driver), `numeric[]` chega como `list[Decimal]`
    e vira `tuple[Decimal, ...]` (mesma forma de array que o adaptador de
    arquivo produz a partir de um array JSON)."""
    valores: dict[str, Decimal | str | tuple[Decimal, ...]] = {}
    for chave, valor in bruto.items():
        if chave in _CHAVES_CARIMBO:
            continue
        if chave in _CHAVES_REGRA:
            if not isinstance(valor, str):
                raise ErroParametros(f"{chave!r} deveria ser texto, recebido {valor!r}")
            valores[chave] = valor
        elif isinstance(valor, list):
            if not all(isinstance(item, Decimal) for item in valor):
                raise ErroParametros(f"{chave!r} deveria ser array numeric, recebido {valor!r}")
            valores[chave] = tuple(valor)
        elif isinstance(valor, Decimal):
            valores[chave] = valor
        else:
            raise ErroParametros(
                f"Parâmetro {chave!r} tem tipo inesperado após a carga: "
                f"{type(valor).__name__}"
            )

    return Parametros(
        PARAMETROS_VERSION=_string_obrigatoria(bruto, "PARAMETROS_VERSION"),
        ENGINE_VERSION=_string_obrigatoria(bruto, "ENGINE_VERSION"),
        DATA_VIGENCIA=_data_vigencia(bruto["DATA_VIGENCIA"]),
        _valores=valores,
    )


def _string_obrigatoria(bruto: dict[str, object], chave: str) -> str:
    valor = bruto[chave]
    if not isinstance(valor, str):
        raise ErroParametros(f"{chave} deve ser string, recebido {valor!r}")
    return valor


def _data_vigencia(valor: object) -> date:
    # psycopg 3 já devolve `date` nativo para coluna `date` — nenhuma
    # conversão de string é necessária aqui (diferente do adaptador de
    # arquivo, que parte de um literal JSON ISO 8601).
    if not isinstance(valor, date):
        raise ErroParametros(f"DATA_VIGENCIA deveria ser date, recebido {valor!r}")
    return valor
