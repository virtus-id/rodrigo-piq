"""Adaptador Supabase/Postgres de respostas de coleta — `RF-10`, `RF-11`,
`RF-13` (`AC-02`, `EC-05`, `EC-10`).

Grava e lê `collection.respostas.Resposta` em `app_aluno.respostas`
(`persistencia/supabase/migracoes/002_app_aluno.sql`, T-21), schema dedicado
desta feature — nunca `motor_calculo` (NFR de segurança). Reaproveita
`obter_pool`/`ErroConexaoAusente` de `persistencia.supabase.conexao`
(genéricos, não amarrados a um schema) — o MESMO pool do processo inteiro,
`T-187`, nunca uma conexão própria — mas `search_path=app_aluno` é fixado
por este módulo a cada checkout, nunca pela função `conectar()` daquele
módulo, que continua fixando `search_path=motor_calculo` para o adaptador
do motor. `engine/` e a lógica de `fonte_parametros.py`/
`repositorio_snapshots.py` (os outros dois módulos Supabase do motor)
seguem intocados por esta tarefa.

**Exatamente um valor por resposta (EC-10, sem merge).** `RegravarResposta`
grava por `INSERT ... ON CONFLICT ("CASO_ID", "ID_PERGUNTA", item_id) DO
UPDATE` — a MESMA linha da PK é SUBSTITUÍDA inteira (`valor_texto`,
`valor_numerico`, `valor_nao_sei`, `QUESTIONARIO_VERSION`, `respondida_em`
são todos reescritos pela última chamada), nunca um `COALESCE`/merge parcial
entre a linha antiga e a nova. Duas sessões simultâneas gravando a mesma
`(CASO_ID, ID_PERGUNTA, item_id)`: a última transação a commitar vence
inteira — nunca uma combinação dos dois valores.

**Exatamente uma das três colunas de valor é preenchida por resposta**
(mesma regra documentada na migração): `NAO_SEI` grava `valor_nao_sei=true`
com `valor_texto`/`valor_numerico` `NULL`; um valor numérico (`Decimal`)
grava `valor_numerico` com os outros dois `NULL`/`false`; qualquer outro
`ValorResposta` (str, int, date, frozenset[str]) é serializado como texto em
`valor_texto`. `int`/`date`/`frozenset[str]` viram texto porque a tabela não
tem coluna dedicada para eles (a migração só distingue numérico/texto/não
sei) — a extensão de esquema para tipos adicionais fica fora desta tarefa;
o round-trip abaixo cobre os cinco ramos do tipo-soma.

**`Decimal` nunca perde precisão (`RF-13`).** `valor_numerico` é `numeric`
(não `double precision`): a escrita passa o `Decimal` direto ao driver
(`psycopg` serializa `Decimal` para `numeric` sem conversão binária
intermediária) e a leitura reconstrói via `Decimal(str(...))` — nunca
`float(...)` em nenhum ponto do caminho de ida ou volta.

**Falha nunca reporta sucesso sem commit (`EC-05`).** `gravar`/`regravar`
abrem uma transação explícita (`with conexao:` do `psycopg`, que comita ao
sair sem exceção e reverte ao sair COM exceção) — qualquer exceção levantada
pelo cursor (antes do commit) propaga para o chamador; a função nunca engole
o erro nem devolve um valor de sucesso por outro caminho.

**Guarda "sem consentimento, nenhuma resposta é gravada" (`RF-30`, `AC-39`,
T-36).** `gravar` lê o `estado` corrente do caso, DENTRO da mesma transação
do `INSERT`, e chama `app.casos.maquina.exigir_estado_permite_resposta` ANTES
de qualquer gravação. Se o caso estiver em `CADASTRADO` ou
`CONSENTIMENTO_REGISTRADO`, a guarda levanta `ErroConsentimentoNaoRegistrado`,
a transação é revertida (`rollback`, mesmo caminho de `EC-05`) e nenhuma
linha é escrita — a checagem mora AQUI, no adaptador que qualquer rota
presente ou futura precisa chamar para persistir uma resposta, e não em
`app/http/`, para que nenhuma rota nova possa contornar a guarda chamando
este repositório diretamente.

Direção de dependência: este módulo importa de `collection/` (o tipo
`Resposta`/`ValorResposta`), de `app.casos.maquina` (a guarda e
`ErroCasoInexistente`, tipos de domínio) e de `psycopg`/stdlib — nunca de
`engine/` (escopo desta feature não toca o motor).

REGRAS: `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-05`, `EC-10`, `RF-30`, `AC-39`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final, Protocol

import psycopg

from app.casos.maquina import (
    ESTADO_CASO,
    ErroConsentimentoNaoRegistrado,
    exigir_estado_permite_resposta,
)
from collection.respostas import NAO_SEI, NaoSei, Resposta, ValorResposta
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

REGRAS: Final[tuple[str, ...]] = (
    "RF-10",
    "RF-11",
    "RF-13",
    "AC-02",
    "EC-05",
    "EC-10",
    "RF-30",
    "AC-39",
)

_SCHEMA: Final[str] = "app_aluno"

# Prefixo de serialização textual por tipo concreto de `ValorResposta`, para
# que a leitura saiba desserializar sem ambiguidade (ex.: distinguir uma
# `str` literal "2024-01-01" de uma `date`). Cada prefixo é curto o
# suficiente para não ser confundido com conteúdo do questionário (AC-37):
# são chaves técnicas de formato, não enunciado nem opção.
_PREFIXO_DATA: Final[str] = "DATA:"
_PREFIXO_FROZENSET: Final[str] = "CONJUNTO:"
_PREFIXO_INT: Final[str] = "INTEIRO:"
_SEPARADOR_FROZENSET: Final[str] = "\x1f"  # unit separator — nunca digitável pelo aluno


class ErroGravacaoResposta(Exception):
    """Levantado quando a gravação de uma resposta falha antes do commit —
    nunca engolida: o chamador vê exatamente esta exceção (ou a original do
    driver, propagada) e nenhuma resposta é reportada como salva sem
    transação confirmada (`EC-05`)."""


class ErroCasoInexistenteParaResposta(Exception):
    """Levantado quando `gravar` é chamado com um `CASO_ID` que não existe em
    `app_aluno.casos` — a guarda de consentimento (`RF-30`, `AC-39`) precisa
    de um `estado` real para decidir; um caso inexistente nunca é tratado
    como "estado que permite resposta" por omissão."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Retira uma conexão do pool compartilhado (`T-187`), com
    `search_path` fixado em `app_aluno` — nunca `motor_calculo` nem
    `public`. Mesmo padrão de `persistencia.supabase.conexao.conectar`
    (commit ao sair sem exceção, rollback e propagação ao sair com
    exceção), reescrito aqui porque aquele módulo fixa `search_path` para
    o schema do motor, o errado para este adaptador."""
    pool = obter_pool()
    conexao = pool.getconn()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"SET search_path TO {_SCHEMA}, public")
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        pool.putconn(conexao)


def _serializar_valor(
    valor: ValorResposta,
) -> tuple[str | None, Decimal | None, bool]:
    """`ValorResposta` -> `(valor_texto, valor_numerico, valor_nao_sei)`.
    Exatamente um dos três carrega o dado; os outros dois são `None`/`False`
    — nunca os dois preenchidos ao mesmo tempo (regra documentada na
    migração `002_app_aluno.sql`)."""
    if isinstance(valor, NaoSei):
        return None, None, True
    if isinstance(valor, Decimal):
        # RF-13: Decimal vai direto para `numeric`, sem passar por float.
        return None, valor, False
    if isinstance(valor, bool):
        # bool é subtipo de int em Python — checado ANTES de int para não
        # cair no ramo `_PREFIXO_INT` por engano.
        return (f"{_PREFIXO_INT}{int(valor)}", None, False)
    if isinstance(valor, int):
        return f"{_PREFIXO_INT}{valor}", None, False
    if isinstance(valor, date):
        return f"{_PREFIXO_DATA}{valor.isoformat()}", None, False
    if isinstance(valor, frozenset):
        return (
            f"{_PREFIXO_FROZENSET}{_SEPARADOR_FROZENSET.join(sorted(valor))}",
            None,
            False,
        )
    # str — nenhum prefixo: é o caso mais comum e o único sem marcação.
    return valor, None, False


def _desserializar_valor(
    valor_texto: str | None, valor_numerico: Decimal | None, valor_nao_sei: bool
) -> ValorResposta:
    """Inverso de `_serializar_valor`. `valor_numerico` chega do driver já
    como `Decimal` (coluna `numeric`) — nunca `float` (RF-13); o round-trip
    de alta precisão depende só do driver preservar essa conversão, o que
    `psycopg 3` faz nativamente para `numeric`."""
    if valor_nao_sei:
        return NAO_SEI
    if valor_numerico is not None:
        return valor_numerico
    if valor_texto is None:
        raise ErroGravacaoResposta(
            "linha de resposta sem valor_texto, valor_numerico nem "
            "valor_nao_sei — violação da exclusividade da migração"
        )
    if valor_texto.startswith(_PREFIXO_DATA):
        return date.fromisoformat(valor_texto[len(_PREFIXO_DATA) :])
    if valor_texto.startswith(_PREFIXO_FROZENSET):
        resto = valor_texto[len(_PREFIXO_FROZENSET) :]
        return frozenset(resto.split(_SEPARADOR_FROZENSET)) if resto else frozenset()
    if valor_texto.startswith(_PREFIXO_INT):
        return int(valor_texto[len(_PREFIXO_INT) :])
    return valor_texto


class RepositorioRespostas(Protocol):
    """Contrato do adaptador de respostas — `RepositorioRespostasSupabase`
    (abaixo) é a implementação Postgres; `persistencia/app_aluno/arquivo.py`
    (T-24) é a implementação de arquivo sobre o MESMO `Protocol`."""

    def gravar(self, resposta: Resposta) -> None:
        """Grava `resposta`. Regrava a mesma `(CASO_ID, ID_PERGUNTA,
        item_id)` sobrescrevendo com a última confirmada, sem merge
        (`EC-10`). Propaga qualquer exceção de gravação — nunca reporta
        sucesso sem transação confirmada (`EC-05`). RECUSA a gravação, sem
        persistir nada, se o caso ainda não tiver consentimento registrado
        (`RF-30`, `AC-39`) — ver `app.casos.maquina.
        exigir_estado_permite_resposta`."""
        ...

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        """Todas as respostas gravadas para `caso_id`, uma por
        `(ID_PERGUNTA, item_id)` — a linha mais recente confirmada de cada
        chave, nunca duas por chave (a própria PK do banco já garante isso;
        o adaptador de arquivo precisa reproduzir a mesma garantia)."""
        ...


class RepositorioRespostasSupabase:
    """Implementa `RepositorioRespostas` sobre `app_aluno.respostas`."""

    def gravar(self, resposta: Resposta) -> None:
        """`RF-30`/`AC-39`: ANTES de qualquer `INSERT`, lê o `estado` corrente
        do caso e chama `exigir_estado_permite_resposta` — se o caso ainda
        estiver em `CADASTRADO` ou `CONSENTIMENTO_REGISTRADO`,
        `ErroConsentimentoNaoRegistrado` é levantada, a transação sofre
        `rollback` (mesmo `except BaseException` de `_conectar`) e nenhuma
        linha é escrita. `EC-10`: `INSERT ... ON CONFLICT (...) DO UPDATE` — a
        linha da PK é inteiramente substituída pelos valores de `resposta`,
        nunca mesclada com a linha anterior. `EC-05`: a gravação ocorre
        dentro do `with _conectar()`, que só comita se o bloco terminar sem
        exceção; qualquer erro do cursor propaga como `psycopg.Error` (ou é
        envolvido, ver bloco `except` abaixo) antes de qualquer commit.

        `T-91` (`RF-31`, `EC-14`): depois do `INSERT`/`UPDATE` da resposta,
        NA MESMA TRANSAÇÃO, `casos.ultima_interacao_em` é atualizada para
        `resposta.respondida_em` — o carimbo real da interação, não
        `datetime.now()` no momento em que este método roda (os dois quase
        sempre coincidem, mas `respondida_em` é o valor que o chamador já
        decidiu ser "quando a resposta ocorreu", a mesma fonte que a
        própria linha de `app_aluno.respostas` grava). Toda gravação de
        resposta atualiza a trilha do caso — não só transições de estado."""
        item_id = resposta.item_id or ""
        valor_texto, valor_numerico, valor_nao_sei = _serializar_valor(resposta.valor)

        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT estado FROM app_aluno.casos WHERE "CASO_ID" = %s
                    """,
                    (resposta.CASO_ID,),
                )
                linha_caso = cursor.fetchone()
                if linha_caso is None:
                    raise ErroCasoInexistenteParaResposta(
                        f"gravação de resposta recusada: CASO_ID={resposta.CASO_ID!r} não existe"
                    )
                (estado_bruto,) = linha_caso
                # A guarda mora em app.casos.maquina (domínio) — este
                # adaptador só lê o estado e delega a decisão a ela, nunca
                # reimplementando a regra aqui.
                exigir_estado_permite_resposta(resposta.CASO_ID, ESTADO_CASO(estado_bruto))

                cursor.execute(
                    """
                    INSERT INTO app_aluno.respostas (
                        "CASO_ID", "ID_PERGUNTA", item_id,
                        valor_texto, valor_numerico, valor_nao_sei,
                        "QUESTIONARIO_VERSION", respondida_em
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT ("CASO_ID", "ID_PERGUNTA", item_id) DO UPDATE SET
                        valor_texto = EXCLUDED.valor_texto,
                        valor_numerico = EXCLUDED.valor_numerico,
                        valor_nao_sei = EXCLUDED.valor_nao_sei,
                        "QUESTIONARIO_VERSION" = EXCLUDED."QUESTIONARIO_VERSION",
                        respondida_em = EXCLUDED.respondida_em
                    """,
                    (
                        resposta.CASO_ID,
                        resposta.ID_PERGUNTA,
                        item_id,
                        valor_texto,
                        valor_numerico,
                        valor_nao_sei,
                        resposta.QUESTIONARIO_VERSION,
                        resposta.respondida_em,
                    ),
                )

                # T-91 (RF-31/EC-14): mesma transação da gravação acima —
                # nunca um segundo commit separado que pudesse deixar a
                # resposta gravada sem a trilha atualizada (ou vice-versa).
                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET ultima_interacao_em = %s
                    WHERE "CASO_ID" = %s
                    """,
                    (resposta.respondida_em, resposta.CASO_ID),
                )
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistenteParaResposta:
            raise
        except ErroConsentimentoNaoRegistrado:
            # RF-30/AC-39: propagada tal como levantada pela guarda de
            # domínio — o `with _conectar()` já reverteu a transação antes de
            # esta exceção chegar aqui (rollback do `except BaseException`
            # do context manager). Nunca reempacotada em `ErroGravacaoResposta`
            # para que o chamador distinga "falha técnica" de "sem
            # consentimento" sem inspecionar a causa.
            raise
        except psycopg.Error as erro:
            # EC-05: nunca engolida — reempacotada só para nomear a chave
            # afetada, com a exceção original preservada como causa.
            raise ErroGravacaoResposta(
                f"falha ao gravar resposta CASO_ID={resposta.CASO_ID!r} "
                f"ID_PERGUNTA={resposta.ID_PERGUNTA!r} item_id={item_id!r}: {erro}"
            ) from erro

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT "CASO_ID", "ID_PERGUNTA", item_id,
                       valor_texto, valor_numerico, valor_nao_sei,
                       "QUESTIONARIO_VERSION", respondida_em
                FROM app_aluno.respostas
                WHERE "CASO_ID" = %s
                """,
                (caso_id,),
            )
            linhas = cursor.fetchall()

        return tuple(_linha_para_resposta(linha) for linha in linhas)

    def listar_de_varios_casos(
        self, caso_ids: tuple[str, ...]
    ) -> dict[str, tuple[Resposta, ...]]:
        """`T-187` — as respostas de vários casos, numa consulta só. Único
        consumidor: o painel do operador, que precisava de `RespostasCaso`
        por caso só para montar `RelatoDeProgresso` (`consultar_trilha_
        de_progresso`) — ver a nota de `RepositorioCasosSupabase.
        buscar_varios` sobre por que uma consulta por caso não escala.

        `CASO_ID` sem nenhuma resposta ainda não aparece no dict — quem
        consome trata a ausência como tupla vazia (`.get(caso_id, ())`),
        igual a `listar_do_caso` para um caso novo."""
        if not caso_ids:
            return {}
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT "CASO_ID", "ID_PERGUNTA", item_id,
                       valor_texto, valor_numerico, valor_nao_sei,
                       "QUESTIONARIO_VERSION", respondida_em
                FROM app_aluno.respostas
                WHERE "CASO_ID" = ANY(%s)
                """,
                (list(caso_ids),),
            )
            linhas = cursor.fetchall()

        agrupado: dict[str, list[Resposta]] = {}
        for linha in linhas:
            resposta = _linha_para_resposta(linha)
            agrupado.setdefault(resposta.CASO_ID, []).append(resposta)
        return {caso_id: tuple(respostas) for caso_id, respostas in agrupado.items()}


def _linha_para_resposta(linha: tuple[Any, ...]) -> Resposta:
    (
        caso_id,
        id_pergunta,
        item_id,
        valor_texto,
        valor_numerico,
        valor_nao_sei,
        questionario_version,
        respondida_em,
    ) = linha
    respondida_em_utc: datetime = (
        respondida_em
        if respondida_em.tzinfo is not None
        else respondida_em.replace(tzinfo=UTC)
    )
    return Resposta(
        CASO_ID=caso_id,
        ID_PERGUNTA=id_pergunta,
        item_id=item_id or None,
        valor=_desserializar_valor(valor_texto, valor_numerico, valor_nao_sei),
        QUESTIONARIO_VERSION=questionario_version,
        respondida_em=respondida_em_utc,
    )
