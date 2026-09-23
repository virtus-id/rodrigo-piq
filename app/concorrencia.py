"""Paralelização de consultas independentes ao banco — `T-191`.

**O custo real, medido em produção (2026-09-23).** O pool de conexões
(`T-187`) resolveu o custo de ABRIR conexão; não resolve o custo de cada
CONSULTA: o servidor da aplicação fica em Boston, o Postgres em São Paulo, e
mesmo um `SELECT 1` numa conexão já aberta e aquecida custa ~484ms — é a
distância física, não overhead de driver. Uma rota que faz três consultas em
SEQUÊNCIA (nenhuma delas usando o resultado da anterior) paga ~1450ms por
nada: as três não têm por que esperar uma pela outra.

**`executar_em_paralelo` não é otimização especulativa.** É o mesmo padrão
já documentado em `persistencia/supabase/conexao.py::obter_pool` — cada
chamada pega SUA PRÓPRIA conexão do pool compartilhado (`getconn`/`putconn`
já são thread-safe por desenho do `psycopg_pool`), roda numa thread, e o
tempo de parede da rota vira o MAIOR dos tempos individuais, não a SOMA.

**Só para consultas de LEITURA sem dependência entre si.** Nunca para
gravação: a ordem de escrita costuma carregar garantia de correção (ex.:
`app/http/rotas_consentimento.py` grava o registro de consentimento só
DEPOIS de validar a transição, de propósito) — paralelizar escrita
reordenaria isso. Cada chamador decide quais das suas consultas são
independentes; esta função não adivinha.

**`ThreadPoolExecutor`, não um segundo pool de conexões.** Os chamadores
(rotas HTTP em `app/http/*`, ou `app/revisao/fila.py`, que monta a fila
como CONSULTA) já rodam em thread — rota `def` síncrona na threadpool do
Starlette (T-187), ou a própria thread da chamadora. Este módulo só abre um
`ThreadPoolExecutor` PEQUENO e de vida curta, por chamada, para as poucas
consultas daquela operação. Ele não compete com o pool de conexões do banco
(`_TAMANHO_MAXIMO_POOL`, 20) nem o substitui.

**Módulo de topo (`app/`), não `app/http/`.** Paralelizar consultas
independentes não é assunto exclusivo de rota HTTP — `app/revisao/
fila.py::listar_fila_de_revisao` monta a fila de revisão fora de qualquer
rota, e precisa do mesmo tratamento. Morar em `app/http/` inverteria a
direção de dependência (domínio importando de HTTP) só por causa de onde
o primeiro uso aconteceu.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

REGRAS: tuple[str, ...] = ()

# Teto de threads de `mapear_em_paralelo`, abaixo — nunca uma thread por item
# sem limite (uma fila com centenas de casos não deveria abrir centenas de
# threads de uma vez). O mesmo teto do pool de conexões
# (`persistencia/supabase/conexao.py::_TAMANHO_MAXIMO_POOL`) — acima disso as
# threads extras só fariam fila esperando conexão, sem ganho nenhum.
_TETO_DE_THREADS: int = 20


def duas_em_paralelo[T1, T2](
    chamada1: Callable[[], T1], chamada2: Callable[[], T2]
) -> tuple[T1, T2]:
    """Executa duas consultas independentes em paralelo — ~1 round trip de
    parede em vez de 2 (`T-191`)."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro1 = executor.submit(chamada1)
        futuro2 = executor.submit(chamada2)
        return futuro1.result(), futuro2.result()


def tres_em_paralelo[T1, T2, T3](
    chamada1: Callable[[], T1], chamada2: Callable[[], T2], chamada3: Callable[[], T3]
) -> tuple[T1, T2, T3]:
    """A mesma ideia de `duas_em_paralelo`, para três consultas
    independentes — ~1 round trip de parede em vez de 3."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futuro1 = executor.submit(chamada1)
        futuro2 = executor.submit(chamada2)
        futuro3 = executor.submit(chamada3)
        return futuro1.result(), futuro2.result(), futuro3.result()


def mapear_em_paralelo[T1, T2](chamada: Callable[[T1], T2], itens: Sequence[T1]) -> tuple[T2, ...]:
    """`duas_em_paralelo`/`tres_em_paralelo` são para um número FIXO de
    consultas de tipos diferentes; esta é para N consultas independentes da
    MESMA chamada — ex.: o histórico de snapshot de cada caso de uma fila,
    onde N é o tamanho da fila, não uma constante. A ordem do resultado é a
    de `itens`, como `map()`."""
    if not itens:
        return ()
    with ThreadPoolExecutor(max_workers=min(len(itens), _TETO_DE_THREADS)) as executor:
        return tuple(executor.map(chamada, itens))
