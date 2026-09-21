"""Portas do motor — interfaces que `engine/` define e `persistencia/` implementa.

Lei nº 1 da arquitetura (plans/motor-calculo.plan.md §1): `engine/` não conhece
persistência. Este módulo é o contrato do lado do motor; os adaptadores
concretos (arquivo, Supabase) vivem em `persistencia/` e importam daqui —
nunca o contrário.

`T-69` adiciona `RepositorioSnapshots` (RF-10, RF-12, V-01..V-03) sobre
`FonteParametros`, escopo de `T-07`.
"""

from collections.abc import Sequence
from typing import Final, Protocol

from engine.parametros import Parametros
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-13", "RF-10", "RF-12")


class FonteParametros(Protocol):
    """RF-13 — porta de carga de parâmetros. `engine/parametros.py` §4 do plano.

    `carregar(versao)` devolve um `Parametros` validado e carimbado com a
    versão pedida, ou levanta `ErroParametros` (`engine.parametros`).
    """

    def carregar(self, versao: str) -> Parametros: ...


class RepositorioSnapshots(Protocol):
    """RF-10 · RF-12 · `V-01..V-03` — porta de persistência do histórico de
    `SnapshotOrdem`. `plans/motor-calculo.plan.md` §4 (bloco literal,
    linhas 588-593), `T-69`.

    Expõe exatamente três métodos: `anexar` (grava um novo snapshot,
    append-only), `obter` (busca um snapshot específico pelo `SNAPSHOT_ID`)
    e `historico` (devolve a cadeia completa de um caso, em ordem
    determinística). **Não existe `atualizar` nem `remover`** — a violação
    de `V-01` (imutabilidade do histórico: ordem e estado nunca são
    sobrescritos) é estruturalmente INEXPRIMÍVEL nesta interface, não uma
    checagem em runtime: não há verbo de mutação no `Protocol` para chamar.
    """

    def anexar(self, s: SnapshotOrdem) -> None:
        """`V-01`: adiciona um novo snapshot ao histórico. Nunca sobrescreve
        um snapshot já anexado — cada chamada é uma nova linha no histórico,
        encadeada por `SnapshotOrdem.snapshot_anterior_id`."""
        ...

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        """Busca um snapshot específico pelo `SNAPSHOT_ID`. Levanta erro do
        adaptador concreto se não existir — nunca devolve `None` nem um
        `SnapshotOrdem` fabricado."""
        ...

    def historico(self, caso_id: str) -> Sequence[SnapshotOrdem]:
        """Devolve a cadeia completa de snapshots de um caso, em ordem
        determinística (ver adaptador concreto para a ordenação exata)."""
        ...
