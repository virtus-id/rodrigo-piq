"""Semeia `motor_calculo.parametros` a partir do arquivo canônico.

As migrações (`persistencia/supabase/migracoes/001_inicial.sql`) criam a
tabela **vazia**, por decisão registrada lá: elas são só DDL. Mas quatro
testes de paridade comparam a linha do Postgres campo a campo com
`parameters/parametros-1.0.1.json` — sem a linha, falham.

**Por que ler do arquivo, e nunca digitar os valores aqui.** São 44 colunas
de parâmetros de um motor de cálculo financeiro. Um número errado digitado à
mão não quebra teste nenhum de tipo: ele vira silenciosamente um plano de
quitação errado para uma pessoa real. O arquivo canônico é a única fonte, e
este script é só transporte.

**Sem `float` em nenhum ponto** (`RF-12`/`RF-13`): o JSON é lido com
`parse_float=Decimal`/`parse_int=Decimal`, e o `psycopg 3` mapeia `Decimal`
→ `numeric` e `list[Decimal]` → `numeric[]` nativamente. O valor nunca
atravessa ponto flutuante entre o arquivo e o banco.

Uso:

    DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \\
        scripts/semear_parametros.py [--versao 1.0.2]

**Qual versão (`T-168`).** `--versao`; sem ele, a vigente do piloto
(`PARAMETROS_VERSION_VIGENTE`, a mesma variável que `app/http/
rotas_calculo.py` carimba no cálculo — `V-03`); sem as duas, `1.0.1`. Semear
uma versão não apaga a outra: cada `PARAMETROS_VERSION` é uma linha.

Idempotente: `ON CONFLICT DO NOTHING`. Rodar duas vezes não duplica nem
sobrescreve — para trocar a linha, apague-a explicitamente antes.

Ver `docs/banco-local.md` para o procedimento completo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persistencia.supabase.conexao import obter_database_url  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PARAMETROS = RAIZ / "parameters"
VERSAO_PADRAO = "1.0.1"
VARIAVEL_VERSAO_VIGENTE = "PARAMETROS_VERSION_VIGENTE"
TABELA = "motor_calculo.parametros"


def arquivo_da_versao(versao: str | None) -> Path:
    """`T-168` — o arquivo canônico da versão pedida, da vigente ou do
    padrão. Versão sem arquivo encerra aqui, antes de abrir conexão."""
    escolhida = versao or os.environ.get(VARIAVEL_VERSAO_VIGENTE) or VERSAO_PADRAO
    arquivo = PASTA_PARAMETROS / f"parametros-{escolhida}.json"
    if not arquivo.is_file():
        raise SystemExit(f"{arquivo.name} não existe em {PASTA_PARAMETROS}.")
    return arquivo


def carregar_canonico(arquivo: Path) -> dict[str, Any]:
    """Lê o arquivo canônico com `Decimal`, nunca `float`."""
    bruto: dict[str, Any] = json.loads(
        arquivo.read_text(encoding="utf-8"),
        parse_float=Decimal,
        parse_int=Decimal,
    )
    return bruto


def _converter(chave: str, valor: Any) -> Any:
    """`DATA_VIGENCIA` vira `date`; array JSON vira `list[Decimal]` (que o
    psycopg grava em `numeric[]`); o resto passa como está."""
    if chave == "DATA_VIGENCIA":
        return date.fromisoformat(valor)
    if isinstance(valor, list):
        return [Decimal(str(item)) for item in valor]
    return valor


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description="Semeia motor_calculo.parametros.")
    leitor.add_argument("--versao", help="PARAMETROS_VERSION a semear (ex.: 1.0.2)")
    arquivo = arquivo_da_versao(leitor.parse_args(argumentos).versao)
    bruto = carregar_canonico(arquivo)
    colunas = list(bruto)
    valores = [_converter(chave, bruto[chave]) for chave in colunas]

    lista_colunas = ", ".join(f'"{coluna}"' for coluna in colunas)
    marcadores = ", ".join(["%s"] * len(colunas))
    sql = f"INSERT INTO {TABELA} ({lista_colunas}) VALUES ({marcadores}) ON CONFLICT DO NOTHING"

    # `psycopg.connect()` SEM argumento não lê `DATABASE_URL` — a libpq lê
    # `PGHOST`/`PGDATABASE`/..., nunca esse nome. Quem lê `DATABASE_URL` é
    # `obter_database_url()`, que também levanta `ErroConexaoAusente` em vez
    # de ficar pendurado até dar timeout quando a variável não existe.
    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute(sql, valores)
        conexao.commit()
        cursor.execute(f"SELECT count(*) FROM {TABELA}")
        resultado = cursor.fetchone()
        total = resultado[0] if resultado else 0

    versao = bruto["PARAMETROS_VERSION"]
    print(f"{arquivo.name}: {len(colunas)} colunas, PARAMETROS_VERSION={versao}")
    print(f"{TABELA}: {total} linha(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
