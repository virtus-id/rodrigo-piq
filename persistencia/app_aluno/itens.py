"""Adaptador Supabase/Postgres de itens repetidos — `RF-04` (`EC-10`).

Grava e lê `app_aluno.itens_repetidos` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21). Mesmo padrão de conexão/transação/commit/rollback
de `persistencia/app_aluno/respostas.py` (T-22) e `persistencia/app_aluno/
casos.py` (T-23): reaproveita `obter_database_url`/`ErroConexaoAusente` de
`persistencia.supabase.conexao`, com `search_path=app_aluno` fixado por
conexão própria deste adaptador.

**Este módulo fornece a implementação REAL de
`collection.repeticao.GeradorDeIdentificadorDeItem`** (T-15) sobre a
persistência — `GeradorDeIdentificadorEmMemoria` daquele módulo permanece
existindo só para teste e para contexto sem banco (mesmo precedente de
`persistencia/arquivo/` no motor); esta classe é o adaptador Postgres do
MESMO `Protocol`, sem alterar `collection/repeticao.py`.

**Mecanismo de não-reaproveitamento de `item_id` (decisão desta tarefa).**
O schema real de `itens_repetidos` (T-21) usa `item_id text PRIMARY KEY` —
**globalmente única na tabela, não composta com `CASO_ID`**. Não há coluna
de contador nem `SERIAL`/`IDENTITY` nativa do Postgres para gerar o número
sequencial (`Dnnn`, `Mnnn`, ...): "não reaproveitar" precisa ser garantido
pela LÓGICA de geração, não por uma sequência SQL nativa amarrada à PK
textual.

Duas camadas de identificador, deliberadamente distintas:

1. **Identificador LEGÍVEL** (`Dnnn`, `Mnnn`, ...) — o que
   `proximo_identificador` DEVOLVE ao chamador, o que aparece como `[Dxxx]`
   em `collection/interpolacao.py::Marcador` (`B11.Q01`) e o que um revisor
   humano lê na tela. É sequencial e monotônico por `(CASO_ID, escopo)`.
2. **Chave PERSISTIDA** (`f"{CASO_ID}:{identificador_legível}"`) — o valor
   que de fato ocupa a coluna `item_id text PRIMARY KEY`. Como a PK é
   global (nenhuma FK composta com `CASO_ID` na migração), dois casos
   diferentes gerando cada um o seu `D001` colidiriam se a chave persistida
   fosse só `D001`; prefixar com `CASO_ID` torna a chave global
   inequivocamente única sem exigir alterar a migração (T-21, já
   concluída, fora do escopo desta tarefa) nem mudar a assinatura de
   `GeradorDeIdentificadorDeItem.proximo_identificador` (que continua
   devolvendo só o identificador legível, o contrato de T-15 intocado).

Geração do PRÓXIMO NÚMERO: `SELECT COUNT(*) ... FOR UPDATE` sobre TODAS as
linhas já existentes (incluindo as já removidas, `removido_em IS NOT NULL`)
de `(CASO_ID, escopo)`, dentro da MESMA transação que faz o `INSERT` da
nova linha. O próximo número é `COUNT(*) + 1`. Como a contagem NUNCA exclui
linhas removidas, o número já usado por um item removido nunca volta a ser
gerado — a garantia de não-reaproveitamento vem de a tabela ser append-only
do ponto de vista desta rotina (o item "removido" é um `UPDATE` de
`removido_em`, nunca um `DELETE`; ver `remover`, abaixo, que não apaga
linha). `FOR UPDATE` sobre as linhas do par serializa duas chamadas
concorrentes de `proximo_identificador` para o MESMO `(CASO_ID, escopo)` —
sem isso, duas transações lendo `COUNT(*)` ao mesmo tempo poderiam calcular
o mesmo próximo número e colidir na PK (a colisão na PK, se ocorresse, seria
capturada e reportada como erro, nunca mascarada — mas o lock evita que ela
aconteça no caminho normal).

Alternativas descartadas e por quê: (1) `GENERATED ALWAYS AS IDENTITY`/
`SERIAL` de banco — não se aplica porque a PK é `item_id text` (texto
formatado), não um contador auxiliar; adicionar uma coluna de contador só
para isso duplicaria a fonte de verdade do número sem necessidade. (2) UUID
— descartado no design de T-15 (`collection/repeticao.py`) por não ser o
formato `[Dxxx]` que o plano usa como marcador de interpolação (`B11.Q01`)
e por ser ilegível numa tela de revisão humana; esta tarefa não reabre essa
decisão. (3) Alterar a migração para PK composta `(CASO_ID, item_id)` —
descartado porque T-21 já está concluída e revisar seu schema está fora do
escopo desta tarefa; o prefixo de chave persistida resolve o mesmo problema
sem tocar em `002_app_aluno.sql`.

Direção de dependência: este módulo importa de `collection.registro`
(`EscopoRepeticao`) e `collection.repeticao` (o `Protocol`), e de
`psycopg`/stdlib — nunca de `engine/`.

**`RepositorioItens` (`Protocol`, T-24).** `collection.repeticao.
GeradorDeIdentificadorDeItem` só declara `proximo_identificador` — o
suficiente para T-15, mas não o bastante para o adaptador de arquivo
(`persistencia/app_aluno/arquivo.py`) provar, sob `mypy --strict`, que
implementa o MESMO contrato do adaptador Postgres também para `remover` e
`listar_do_caso`, que `RepositorioItensSupabase` já expõe desde T-23 sem um
`Protocol` formal por cima. Extraído aqui (não em `collection/repeticao.py`,
que é congelado por T-23 concluída e não é desta tarefa revisitar) como
extensão estrita da interface já implícita na classe existente — nenhum
método novo de comportamento, só o nome formal do contrato que já existia de
fato.

REGRAS: `RF-04`, `EC-10`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from collection.registro import EscopoRepeticao
from collection.repeticao import PREFIXO_POR_ESCOPO, erro_escopo_sem_item
from persistencia.supabase.conexao import ErroConexaoAusente, obter_database_url

REGRAS: Final[tuple[str, ...]] = ("RF-04", "EC-10")

_SCHEMA: Final[str] = "app_aluno"

# Separador entre CASO_ID e o identificador legível na CHAVE PERSISTIDA
# (coluna item_id, PK global) — nunca aparece no identificador LEGÍVEL
# devolvido por `proximo_identificador` (ver nota do módulo). ':' não é um
# caractere usado pelos prefixos de escopo (D/V/M/DESP/A/REND/NM) nem por
# CASO_ID, então a divisão de volta ao identificador legível é inambígua.
_SEPARADOR_CHAVE: Final[str] = ":"


class ErroGravacaoItem(Exception):
    """Levantado quando a gravação de um item repetido falha antes do
    commit — nunca engolida, mesma disciplina de `EC-05` aplicada nos
    demais adaptadores desta feature."""


@dataclass(frozen=True, slots=True)
class ItemRepetido:
    """Uma linha de `app_aluno.itens_repetidos` — a identidade estável de
    uma ficha (dívida, vínculo, margem, item de despesa, ação, renda
    adicional ou despesa não-mensal) por caso (`RF-04`, T-15). `item_id` aqui
    é sempre o identificador LEGÍVEL
    (`D001`, `M002`, ...) — a chave persistida com prefixo de `CASO_ID` é
    um detalhe interno deste adaptador, nunca exposto fora dele."""

    item_id: str
    CASO_ID: str
    escopo: EscopoRepeticao
    removido_em: datetime | None
    criado_em: datetime


def _chave_persistida(caso_id: str, identificador_legivel: str) -> str:
    """Monta a chave global da PK a partir do `CASO_ID` e do identificador
    legível — ver a nota do módulo sobre por que a PK de `item_id` não pode
    ser só o identificador legível."""
    return f"{caso_id}{_SEPARADOR_CHAVE}{identificador_legivel}"


def _identificador_legivel(chave_persistida: str, caso_id: str) -> str:
    """Inverso de `_chave_persistida`: remove o prefixo `f"{caso_id}:"`."""
    prefixo = f"{caso_id}{_SEPARADOR_CHAVE}"
    if not chave_persistida.startswith(prefixo):
        raise ErroGravacaoItem(
            f"chave persistida {chave_persistida!r} não tem o prefixo esperado {prefixo!r}"
        )
    return chave_persistida[len(prefixo) :]


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `_conectar` em `persistencia/app_aluno/respostas.py`
    e `persistencia/app_aluno/casos.py`: `search_path=app_aluno`, commit ao
    sair sem exceção, rollback e propagação ao sair com exceção."""
    conexao = psycopg.connect(obter_database_url())
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _como_utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


def _linha_para_item(linha: tuple[Any, ...]) -> ItemRepetido:
    chave_persistida, caso_id, escopo, removido_em, criado_em = linha
    return ItemRepetido(
        item_id=_identificador_legivel(chave_persistida, caso_id),
        CASO_ID=caso_id,
        escopo=EscopoRepeticao(escopo),
        removido_em=_como_utc(removido_em) if removido_em is not None else None,
        criado_em=_como_utc(criado_em),
    )


class RepositorioItens(Protocol):
    """Contrato do adaptador de itens repetidos — `RepositorioItensSupabase`
    (abaixo) é a implementação Postgres; `persistencia/app_aluno/arquivo.py`
    (T-24) é a implementação de arquivo sobre o MESMO `Protocol`. Estende
    `collection.repeticao.GeradorDeIdentificadorDeItem` (mesma assinatura de
    `proximo_identificador`, verificado por `mypy --strict` como
    subtipagem estrutural) com as operações de leitura/remoção que a
    persistência real precisa."""

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        """Ver `collection.repeticao.GeradorDeIdentificadorDeItem`: devolve
        um novo identificador de item, estável e nunca reaproveitado, para o
        par `(CASO_ID, escopo)`."""
        ...

    def remover(self, caso_id: str, item_id: str, agora: datetime | None = None) -> None:
        """Marca o item como removido (`removido_em`) — NUNCA apaga a linha:
        é essa memória que impede o reaproveitamento do identificador
        (`AC-04`, critério 4)."""
        ...

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        """Todos os itens de `caso_id`, em ordem de criação.
        `incluir_removidos=True` (padrão) devolve a trilha completa."""
        ...


class RepositorioItensSupabase:
    """Implementa `RepositorioItens` sobre `app_aluno.itens_repetidos`."""

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        """`GeradorDeIdentificadorDeItem.proximo_identificador` — ver a nota
        do módulo sobre o mecanismo de não-reaproveitamento
        (`COUNT(*) FOR UPDATE` sobre TODAS as linhas do par, removidas
        inclusive, dentro da mesma transação do `INSERT`)."""
        prefixo = PREFIXO_POR_ESCOPO.get(escopo)
        if prefixo is None:
            raise erro_escopo_sem_item(escopo)

        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT item_id FROM app_aluno.itens_repetidos
                    WHERE "CASO_ID" = %s AND escopo = %s
                    FOR UPDATE
                    """,
                    (CASO_ID, escopo.value),
                )
                total_existente = len(cursor.fetchall())
                proximo_numero = total_existente + 1
                identificador_legivel = f"{prefixo}{proximo_numero:03d}"
                chave_persistida = _chave_persistida(CASO_ID, identificador_legivel)

                cursor.execute(
                    """
                    INSERT INTO app_aluno.itens_repetidos (item_id, "CASO_ID", escopo)
                    VALUES (%s, %s, %s)
                    """,
                    (chave_persistida, CASO_ID, escopo.value),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoItem(
                f"falha ao gerar próximo item_id para CASO_ID={CASO_ID!r} "
                f"escopo={escopo!r}: {erro}"
            ) from erro

        return identificador_legivel

    def remover(self, caso_id: str, item_id: str, agora: datetime | None = None) -> None:
        """Marca `removido_em` — NUNCA um `DELETE`. Apagar a linha
        destruiria a memória de que aquele número já foi usado, e é
        exatamente essa memória que impede o reaproveitamento (ver a nota
        do módulo). `item_id` é o identificador LEGÍVEL (`D001`); `caso_id`
        é necessário para reconstruir a chave persistida (`_chave_persistida`)."""
        instante = agora if agora is not None else datetime.now(UTC)
        chave_persistida = _chave_persistida(caso_id, item_id)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.itens_repetidos
                    SET removido_em = %s
                    WHERE item_id = %s
                    """,
                    (instante, chave_persistida),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoItem(f"falha ao remover item_id={item_id!r}: {erro}") from erro

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        """Todos os itens de `caso_id`. `incluir_removidos=True` (padrão)
        devolve a trilha completa, inclusive itens já removidos — quem
        precisa só dos ativos filtra por `removido_em is None`."""
        filtro_removidos = "" if incluir_removidos else 'AND removido_em IS NULL'
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT item_id, "CASO_ID", escopo, removido_em, criado_em
                FROM app_aluno.itens_repetidos
                WHERE "CASO_ID" = %s {filtro_removidos}
                ORDER BY criado_em
                """,
                (caso_id,),
            )
            linhas = cursor.fetchall()

        return tuple(_linha_para_item(linha) for linha in linhas)
