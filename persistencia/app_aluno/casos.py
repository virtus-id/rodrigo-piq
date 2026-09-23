"""Adaptador Supabase/Postgres de `Caso` — `RF-01`, `RF-04`, `RF-31`
(`EC-10`, `EC-14`).

Grava e lê `Caso` em `app_aluno.casos` (`persistencia/supabase/migracoes/
002_app_aluno.sql`, T-21), schema dedicado desta feature. Mesmo padrão de
conexão/transação/commit/rollback de `persistencia/app_aluno/respostas.py`
(T-22): reaproveita `obter_pool`/`ErroConexaoAusente` de
`persistencia.supabase.conexao` (genéricos, não amarrados a um schema) — o
MESMO pool do processo inteiro, `T-187`, nunca uma conexão própria — com
`search_path=app_aluno` fixado a cada checkout (a conexão física pode ter
servido `motor_calculo` no checkout anterior).

**`ESTADO_CASO`/`Caso` nascem em `app/casos/maquina.py` (T-33), não aqui.**
T-23 originalmente definiu os dois tipos provisoriamente aqui, antes de a
máquina de transições existir, com a nota de que T-33 deveria importá-los
deste módulo. T-33 inverteu essa direção: a máquina de estados é regra de
domínio (`app/`) e este adaptador é infraestrutura (`persistencia/`) — o
mesmo princípio da Lei nº 3 do backlog (`app/` importa de `persistencia/`,
nunca o contrário) exige que a definição canônica fique do lado do domínio,
para que não haja duas fontes de verdade sobre o que é um estado de caso.
Este módulo agora IMPORTA `ESTADO_CASO`/`Caso` de `app.casos.maquina` e só
os reexporta, para não quebrar quem já importa daqui (`tests/app_aluno/
integracao/test_persistencia_casos.py`, T-23). `Transicao` e a tabela de
transições nomeadas (a MÁQUINA em si, com suas guardas) vivem exclusivamente
em `app/casos/maquina.py` e não aparecem aqui: este módulo só persiste o
valor corrente de `estado`, nunca decide se uma mudança de `estado` é uma
transição válida.

**Divergência de nome com o plano §4.3, alinhada ao SQL real de T-21.** O
plano desenha `Caso.snapshot_corrente_id` (um único campo); a migração
`002_app_aluno.sql` (T-21, já concluída, fonte de verdade do schema real)
tem DOIS campos — `snapshot_raiz_id` e `snapshot_liberado_id` — exatamente
para resolver `OQ-11` (identidade do caso anterior ao primeiro snapshot,
distinta do snapshot liberado mais recente que a tela mostra, `OQ-09`).
Esta tarefa segue o SQL real (T-21 já está concluída e não é desta tarefa
revisar), não a prosa do plano: `Caso` tem os dois campos.

**Transição de estado usa `SELECT ... FOR UPDATE` (plano §6).** `FOR UPDATE`
é SQL puro dentro da query — não é sintaxe especial do driver `psycopg`
(confirmado: a lib só executa a string enviada; o bloqueio é inteiramente do
lado do Postgres). A trava é adquirida sobre a LINHA do caso, dentro da
MESMA transação que grava o novo estado: uma segunda transição concorrente
sobre o mesmo `CASO_ID` bloqueia no `SELECT ... FOR UPDATE` até a primeira
committar (ou fazer rollback) — nunca lê um `estado` "no meio" de outra
transição. Isso basta para impedir dois Bloco 6 simultâneos (§6 do plano):
não é lock otimista nem CAS em aplicação, é a garantia nativa do MVCC do
Postgres para `SELECT FOR UPDATE`.

**`ultima_interacao_em` (RF-31, EC-14).** Toda gravação de estado atualiza
`ultima_interacao_em` para o instante da chamada (`datetime.now(UTC)`) — é
o carimbo que a trilha de acompanhamento lê para saber há quanto tempo o
caso está parado (`EC-14`: abandono é observável, nunca silencioso).

**`pertence_a_conta` (RF-02, AC-03, T-31).** Extensão pequena e necessária
desta tarefa: o método que `app/http/isolamento.py` chama, a cada
requisição, para verificar no servidor se a sessão realmente possui o
`CASO_ID` recebido — nunca no cookie nem na interface. Devolve um único
booleano que não distingue "caso inexistente" de "caso de outra conta",
para que a dependência de isolamento sempre responda `404` (nunca `403`)
sem vazar qual das duas situações ocorreu.

**`listar_por_estado` (RF-23, RF-25, T-69).** Extensão pequena e necessária
desta tarefa: `app/revisao/fila.py::listar_fila_de_revisao` (T-66/T-68) já
recebia `casos_ids` como parâmetro do CHAMADOR — este método é a fonte real
desse parâmetro para a tela de revisão (`app/http/rotas_revisao.py`, T-69):
todos os `CASO_ID` com `estado = AGUARDANDO_REVISAO`. Não decide nada sobre
fila; só enumera.

**`listar_todos` (RF-35, T-102).** Extensão pequena e necessária desta
tarefa: o painel do operador (`app/http/rotas_operador.py`) precisa de TODOS
os `CASO_ID` do piloto, não só os de um `estado` específico — `listar_por_
estado` exigiria doze chamadas (uma por membro de `ESTADO_CASO`) para o
mesmo resultado. Mesmo precedente de `listar_por_estado`: só enumera
`CASO_ID`s, em qualquer ordem estável, sem decidir nada sobre o painel.

Direção de dependência: este módulo importa de `psycopg`/stdlib e de
`persistencia.supabase.conexao` — nunca de `engine/` (escopo desta feature
não toca o motor).

REGRAS: `RF-01`, `RF-02`, `RF-04`, `RF-31`, `AC-03`, `EC-10`, `EC-14`
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import psycopg

from app.casos.maquina import ESTADO_CASO, Caso
from persistencia.supabase.conexao import ErroConexaoAusente, obter_pool

REGRAS: Final[tuple[str, ...]] = (
    "RF-01",
    "RF-02",
    "RF-04",
    "RF-31",
    "AC-03",
    "EC-10",
    "EC-14",
)

_SCHEMA: Final[str] = "app_aluno"

# Reexportados para quem já importa `ESTADO_CASO`/`Caso` deste módulo
# (T-23) — a definição canônica agora vive em `app/casos/maquina.py` (T-33).
__all__ = [
    "ESTADO_CASO",
    "Caso",
    "ErroCasoInexistente",
    "ErroGravacaoCaso",
    "RepositorioCasos",
    "RepositorioCasosSupabase",
]


class ErroCasoInexistente(Exception):
    """Levantado quando uma operação referencia um `CASO_ID` que não existe
    em `app_aluno.casos` — nunca silenciosamente ignorado."""


class ErroGravacaoCaso(Exception):
    """Levantado quando a gravação/transição de um `Caso` falha antes do
    commit — nunca engolida: o chamador vê exatamente esta exceção (ou a
    original do driver, propagada), mesma disciplina de `EC-05` aplicada em
    `persistencia/app_aluno/respostas.py` (T-22)."""


@contextmanager
def _conectar() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Mesmo padrão de `persistencia/app_aluno/respostas.py::_conectar`:
    `search_path` fixado em `app_aluno`, commit ao sair sem exceção,
    rollback e propagação ao sair com exceção. `conectar()` daquele módulo
    não serve aqui mesmo com o pool compartilhado (`T-187`): fixa
    `search_path=motor_calculo`, o schema errado para este adaptador."""
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


def _linha_para_caso(linha: tuple[Any, ...]) -> Caso:
    (
        caso_id,
        conta_id,
        estado,
        data_referencia,
        questionario_version,
        snapshot_raiz_id,
        snapshot_liberado_id,
        ultima_interacao_em,
        criado_em,
    ) = linha
    return Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=ESTADO_CASO(estado),
        DATA_REFERENCIA=data_referencia,
        QUESTIONARIO_VERSION=questionario_version,
        snapshot_raiz_id=snapshot_raiz_id,
        snapshot_liberado_id=snapshot_liberado_id,
        ultima_interacao_em=_como_utc(ultima_interacao_em),
        criado_em=_como_utc(criado_em),
    )


def _como_utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


class RepositorioCasos(Protocol):
    """Contrato do adaptador de casos — `RepositorioCasosSupabase` (abaixo) é
    a implementação Postgres; `persistencia/app_aluno/arquivo.py` (T-24) é a
    implementação de arquivo sobre o MESMO `Protocol`."""

    def criar(self, caso: Caso) -> None:
        """Cadastra um novo `Caso`. `CASO_ID` é identidade própria de
        `app_aluno`, gerada pelo chamador antes desta chamada (`OQ-11`) —
        este método não gera identificador, só persiste o que recebe."""
        ...

    def buscar(self, caso_id: str) -> Caso | None:
        """`None` se `caso_id` não existir — nunca lança para "não
        encontrado", só para falha de acesso ao banco."""
        ...

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        """`RF-02`/`AC-03` (T-31) — verificação de isolamento por `CASO_ID`.
        `False` tanto para `caso_id` inexistente quanto para `caso_id`
        existente mas pertencente a OUTRA conta — o chamador (`app/http/
        isolamento.py`) nunca distingue os dois casos, exatamente para que a
        existência do caso de terceiro não vaze (404 uniforme, nunca 403).
        Consulta o banco a cada chamada, sem cache: quem depende deste
        método (a dependência de isolamento) é reexecutado a cada
        requisição, nunca lendo um valor gravado em sessão."""
        ...

    def transicionar_estado(
        self, caso_id: str, novo_estado: ESTADO_CASO, agora: datetime | None = None
    ) -> Caso:
        """Grava `novo_estado` e atualiza `ultima_interacao_em` para `agora`
        (ou `datetime.now(UTC)` se omitido), adquirindo `SELECT ... FOR
        UPDATE` sobre a linha do caso ANTES de gravar — impede que duas
        transições concorrentes sobre o MESMO caso produzam estados
        divergentes (§6 do plano). Levanta `ErroCasoInexistente` se
        `caso_id` não existir."""
        ...

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        """`T-56` (`AC-12`, disparo do Bloco 6): variante CONDICIONAL de
        `transicionar_estado` — grava `novo_estado` **somente se** o
        `estado` corrente da linha for exatamente `estado_esperado`, dentro
        da MESMA seção `SELECT ... FOR UPDATE` + `UPDATE` (mesma transação).
        Devolve o `Caso` atualizado quando a condição valia (e a gravação
        ocorreu); devolve `None`, sem gravar nada, quando o `estado`
        corrente já era outro — nunca sobrescreve silenciosamente.

        **Por que `transicionar_estado` (incondicional) não basta para
        disparo do Bloco 6.** Duas requisições concorrentes que leem
        `Caso.estado == COLETA_INICIAL` FORA da seção crítica (ex.: por
        `buscar()`, antes de chamar `transicionar_estado`) e SÓ DEPOIS
        chamam `transicionar_estado(caso_id, CALCULANDO)` correm uma
        condição de corrida clássica: a primeira grava, libera o lock; a
        segunda adquire o lock em seguida e GRAVARIA O MESMO VALOR de novo,
        sem erro — `transicionar_estado` nunca verifica o estado atual
        contra um esperado, só o `caso_id` existir. Isso disparia DOIS
        agendamentos de `calcular_plano` (violando o critério de aceite de
        `T-56`: "duas execuções concorrentes resultam em uma única
        execução"). Ler o estado esperado e escrevê-lo condicionalmente
        DENTRO da mesma seção `FOR UPDATE` (este método) é o que faz a
        segunda chamada, ao adquirir o lock depois da primeira já ter
        commitado, ENCONTRAR o estado já diferente do esperado e devolver
        `None` sem gravar — só a chamada vencedora dispara a execução."""
        ...

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        """Atualiza só `ultima_interacao_em`, sem mudar `estado` — para
        interações que não são transição (ex.: gravar uma resposta dentro do
        mesmo estado). `RF-31`/`EC-14`: toda interação atualiza a trilha."""
        ...

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        """Preenche `snapshot_raiz_id` — só deve ser chamado quando o
        PRIMEIRO snapshot do caso nasce (`OQ-11`). Idempotente: chamar de
        novo com o mesmo valor não é erro, mas sobrescrever com um valor
        DIFERENTE de um `snapshot_raiz_id` já preenchido é um uso indevido
        do chamador — este método não impede isso (não é sua
        responsabilidade decidir quando o primeiro snapshot "de fato" nasceu,
        isso é do fluxo do Bloco 6, `app/motor/`, fora desta tarefa)."""
        ...

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        """Atualiza `snapshot_liberado_id` para o snapshot mais recentemente
        LIBERADO em revisão (`OQ-09`) — chamado a cada liberação, nunca só
        na primeira."""
        ...

    def listar_por_estado(self, estado: ESTADO_CASO) -> tuple[str, ...]:
        """`RF-23`/`RF-25` (T-69) — extensão pequena e necessária desta
        tarefa: todos os `CASO_ID` cujo `estado` corrente é exatamente
        `estado`, em qualquer ordem estável. Único consumidor hoje: a tela
        da fila de revisão (`app/http/rotas_revisao.py`), que passa
        `ESTADO_CASO.AGUARDANDO_REVISAO` e entrega o resultado a
        `app.revisao.fila.listar_fila_de_revisao` — este método só enumera
        `CASO_ID`s, nunca decide o que é "fila" (essa decisão já pertence a
        `app/revisao/fila.py`, T-66/T-68)."""
        ...

    def listar_todos(self) -> tuple[str, ...]:
        """`RF-35` (T-102): todos os `CASO_ID` cadastrados no piloto,
        qualquer que seja o `estado`, em qualquer ordem estável. Único
        consumidor hoje: o painel do operador (`app/http/rotas_operador.py`),
        que monta o `RelatoDeProgresso` (`app/casos/progresso.py`, T-92) de
        cada um — este método só enumera, nunca decide o que exibir."""
        ...


class RepositorioCasosSupabase:
    """Implementa `RepositorioCasos` sobre `app_aluno.casos`."""

    def criar(self, caso: Caso) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app_aluno.casos (
                        "CASO_ID", conta_id, estado, "DATA_REFERENCIA",
                        "QUESTIONARIO_VERSION", snapshot_raiz_id,
                        snapshot_liberado_id, ultima_interacao_em, criado_em
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        caso.CASO_ID,
                        caso.conta_id,
                        caso.estado.value,
                        caso.DATA_REFERENCIA,
                        caso.QUESTIONARIO_VERSION,
                        caso.snapshot_raiz_id,
                        caso.snapshot_liberado_id,
                        caso.ultima_interacao_em,
                        caso.criado_em,
                    ),
                )
        except ErroConexaoAusente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao criar caso CASO_ID={caso.CASO_ID!r}: {erro}"
            ) from erro

    def buscar(self, caso_id: str) -> Caso | None:
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT "CASO_ID", conta_id, estado, "DATA_REFERENCIA",
                       "QUESTIONARIO_VERSION", snapshot_raiz_id,
                       snapshot_liberado_id, ultima_interacao_em, criado_em
                FROM app_aluno.casos
                WHERE "CASO_ID" = %s
                """,
                (caso_id,),
            )
            linha = cursor.fetchone()

        return _linha_para_caso(linha) if linha is not None else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        """Uma única consulta que já compara `conta_id` no `WHERE` — o
        resultado não distingue "não existe" de "existe mas é de outra
        conta" (`RF-02`/`AC-03`, T-31): as duas situações produzem `False`
        pela mesma linha de código, sem ramo que pudesse vazar qual delas
        ocorreu."""
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM app_aluno.casos
                WHERE "CASO_ID" = %s AND conta_id = %s
                """,
                (caso_id, conta_id),
            )
            return cursor.fetchone() is not None

    def transicionar_estado(
        self, caso_id: str, novo_estado: ESTADO_CASO, agora: datetime | None = None
    ) -> Caso:
        """`SELECT ... FOR UPDATE` é SQL puro — `psycopg` não tem sintaxe
        própria para isso, a trava é do Postgres. A aquisição do lock e a
        gravação do novo estado ocorrem na MESMA transação (`with
        _conectar()`): uma segunda chamada concorrente para o mesmo
        `caso_id` bloqueia no `SELECT ... FOR UPDATE` abaixo até esta
        transação COMMIT/ROLLBACK — nunca lê a linha "no meio" da primeira
        transição (§6 do plano)."""
        instante = agora if agora is not None else datetime.now(UTC)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT "CASO_ID" FROM app_aluno.casos
                    WHERE "CASO_ID" = %s
                    FOR UPDATE
                    """,
                    (caso_id,),
                )
                if cursor.fetchone() is None:
                    raise ErroCasoInexistente(
                        f"transição de estado recusada: CASO_ID={caso_id!r} não existe"
                    )

                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET estado = %s, ultima_interacao_em = %s
                    WHERE "CASO_ID" = %s
                    """,
                    (novo_estado.value, instante, caso_id),
                )
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao transicionar CASO_ID={caso_id!r} para {novo_estado!r}: {erro}"
            ) from erro

        caso_atualizado = self.buscar(caso_id)
        if caso_atualizado is None:  # pragma: no cover — defensivo, não deveria ocorrer
            raise ErroCasoInexistente(
                f"CASO_ID={caso_id!r} desapareceu entre a transição e a releitura"
            )
        return caso_atualizado

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        """`T-56` — o `estado` corrente é lido DENTRO da mesma seção `FOR
        UPDATE` que o `UPDATE` condicional (`WHERE estado = %s`): a segunda
        chamada concorrente, ao adquirir o lock depois do commit da
        primeira, vê o `estado` já diferente de `estado_esperado` e o
        `UPDATE` afeta zero linhas (`cursor.rowcount == 0`) — devolve `None`
        sem gravar, nunca sobrescrevendo o que a primeira já gravou. Ver a
        nota extensa no `Protocol` (acima) sobre por que `transicionar_
        estado` (incondicional) não basta para este caso de uso."""
        instante = agora if agora is not None else datetime.now(UTC)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT "CASO_ID" FROM app_aluno.casos
                    WHERE "CASO_ID" = %s
                    FOR UPDATE
                    """,
                    (caso_id,),
                )
                if cursor.fetchone() is None:
                    raise ErroCasoInexistente(
                        f"transição condicional recusada: CASO_ID={caso_id!r} não existe"
                    )

                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET estado = %s, ultima_interacao_em = %s
                    WHERE "CASO_ID" = %s AND estado = %s
                    """,
                    (novo_estado.value, instante, caso_id, estado_esperado.value),
                )
                afetou_a_linha = cursor.rowcount > 0
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao transicionar condicionalmente CASO_ID={caso_id!r} "
                f"para {novo_estado!r}: {erro}"
            ) from erro

        if not afetou_a_linha:
            return None

        caso_atualizado = self.buscar(caso_id)
        if caso_atualizado is None:  # pragma: no cover — defensivo, não deveria ocorrer
            raise ErroCasoInexistente(
                f"CASO_ID={caso_id!r} desapareceu entre a transição e a releitura"
            )
        return caso_atualizado

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        instante = agora if agora is not None else datetime.now(UTC)
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET ultima_interacao_em = %s
                    WHERE "CASO_ID" = %s
                    """,
                    (instante, caso_id),
                )
                if cursor.rowcount == 0:
                    raise ErroCasoInexistente(
                        f"registro de interação recusado: CASO_ID={caso_id!r} não existe"
                    )
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao registrar interação de CASO_ID={caso_id!r}: {erro}"
            ) from erro

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET snapshot_raiz_id = %s
                    WHERE "CASO_ID" = %s
                    """,
                    (snapshot_raiz_id, caso_id),
                )
                if cursor.rowcount == 0:
                    raise ErroCasoInexistente(
                        f"registro de snapshot raiz recusado: CASO_ID={caso_id!r} não existe"
                    )
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao registrar snapshot_raiz_id de CASO_ID={caso_id!r}: {erro}"
            ) from erro

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        try:
            with _conectar() as conexao, conexao.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE app_aluno.casos
                    SET snapshot_liberado_id = %s
                    WHERE "CASO_ID" = %s
                    """,
                    (snapshot_liberado_id, caso_id),
                )
                if cursor.rowcount == 0:
                    raise ErroCasoInexistente(
                        f"registro de snapshot liberado recusado: CASO_ID={caso_id!r} não existe"
                    )
        except ErroConexaoAusente:
            raise
        except ErroCasoInexistente:
            raise
        except psycopg.Error as erro:
            raise ErroGravacaoCaso(
                f"falha ao registrar snapshot_liberado_id de CASO_ID={caso_id!r}: {erro}"
            ) from erro

    def listar_por_estado(self, estado: ESTADO_CASO) -> tuple[str, ...]:
        """`RF-23`/`RF-25` (T-69) — uma única consulta filtrando por
        `estado`; nenhuma lógica de fila aqui, só enumeração de `CASO_ID`."""
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT "CASO_ID" FROM app_aluno.casos
                WHERE estado = %s
                """,
                (estado.value,),
            )
            linhas = cursor.fetchall()
        return tuple(str(linha[0]) for linha in linhas)

    def listar_da_conta(self, conta_id: str) -> tuple[str, ...]:
        """`RF-02` (T-154) — filtro por `conta_id`, feito no BANCO.

        O filtro é da consulta, não de código que varre `listar_todos` e
        descarta o que não bate: carregar todos os casos do piloto para
        devolver um é desperdício, e é o tipo de laço em que um `!=` trocado
        vaza caso alheio.

        **Ordenado do mais RECENTE para o mais antigo, e isso é contrato, não
        detalhe.** Uma conta pode ter vários casos — o banco local de
        demonstração chegou a 14, porque cada execução de `scripts/
        subir_demo.py` cria um. `GET /api/conta/eu` usa o primeiro da lista
        como "o caso da sessão"; sem `ORDER BY` a ordem é a que o Postgres
        entregar, e o aluno cairia num caso arbitrário — possivelmente o mais
        antigo, abandonado meses antes. O mais recente é o único que ele
        reconhece como "o meu"."""
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT "CASO_ID"
                  FROM app_aluno.casos
                 WHERE conta_id = %s
                 ORDER BY criado_em DESC
                """,
                (conta_id,),
            )
            linhas = cursor.fetchall()
        return tuple(str(linha[0]) for linha in linhas)

    def listar_todos(self) -> tuple[str, ...]:
        """`RF-35` (T-102) — uma única consulta sem filtro de `estado`;
        nenhuma lógica de painel aqui, só enumeração de `CASO_ID`."""
        with _conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute("""SELECT "CASO_ID" FROM app_aluno.casos""")
            linhas = cursor.fetchall()
        return tuple(str(linha[0]) for linha in linhas)
