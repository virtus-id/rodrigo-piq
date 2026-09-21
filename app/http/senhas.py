"""Hash e verificação de senha com Argon2id — `RF-02` (NFR de segurança: senha
nunca armazenada em texto claro nem registrada em log).

`plans/app-aluno.plan.md` §2 escolhe Argon2id (`argon2-cffi`) como algoritmo de
hash, mas não fixa os parâmetros de custo (memory cost, time cost,
parallelism) — decisão de implementação desta tarefa (T-28).

**Parâmetros de custo escolhidos.** `_PARAMETROS_ARGON2` usa exatamente os
valores recomendados hoje pelo próprio `argon2-cffi` (2ª recomendação da RFC
9106 para ambiente sem hardware dedicado, também o piso que a OWASP Password
Storage Cheat Sheet lista para Argon2id): `time_cost=3`, `memory_cost=65536`
(64 MiB), `parallelism=4`, `hash_len=32`, `salt_len=16`, `type=Argon2id`. São
robustos para qualquer volume — inclusive muito além do piloto de 1 a 3
alunos (`OQ-06`) — e são declarados explicitamente aqui, nesta única
constante, em vez de depender implicitamente do default da lib: se uma versão
futura do `argon2-cffi` mudar seus defaults, o custo efetivo deste módulo não
muda com ela.

**Sem mitigação de timing attack nesta tarefa.** Verificar login contra uma
conta inexistente é mais rápido (nenhum hash Argon2id é computado) do que
contra uma conta existente com senha errada (um hash completo é computado e
comparado). Isso é uma diferença de tempo observável em tese, mas decidimos
NÃO mitigá-la nesta tarefa (YAGNI declarado): o piloto tem 1 a 3 alunos
(`OQ-06`), o vetor exige medir latência de rede com precisão de milissegundos
para inferir a única informação que vazaria ("este e-mail tem conta"; nenhuma
senha), e a defesa (hash contra um "hash dummy" fixo quando a conta não
existe) tem custo de manutenção (fixar um hash de referência, mantê-lo
sincronizado com `_PARAMETROS_ARGON2` se estes mudarem) desproporcional ao
risco real neste estágio. O que ESTA tarefa garante, e que é o critério de
aceite: a MENSAGEM de erro de login nunca distingue os dois casos — ver
`persistencia/app_aluno/contas.py::autenticar`, que devolve o mesmo resultado
(`None`) e não expõe qual dos dois casos ocorreu. Se o piloto crescer e o
vetor deixar de ser desprezível, a mitigação (verificar contra hash dummy
quando a conta não existe) é um acréscimo pontual a `autenticar`, sem mudar
este módulo.

Este módulo é PURO: nenhuma chamada a banco, nenhum log. `persistencia/
app_aluno/contas.py` é quem grava/lê `senha_hash` e usa estas duas funções.

REGRAS: `RF-02`
"""

from __future__ import annotations

from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

REGRAS: Final[tuple[str, ...]] = ("RF-02",)

# Parâmetros de custo do Argon2id, declarados numa ÚNICA constante do módulo —
# ver justificativa na docstring acima. Nenhuma outra chamada a
# `PasswordHasher(...)` neste módulo usa valor diferente destes.
_TIME_COST: Final[int] = 3
_MEMORY_COST: Final[int] = 65536  # 64 MiB
_PARALLELISM: Final[int] = 4
_HASH_LEN: Final[int] = 32
_SALT_LEN: Final[int] = 16

_PARAMETROS_ARGON2: Final[dict[str, int]] = {
    "time_cost": _TIME_COST,
    "memory_cost": _MEMORY_COST,
    "parallelism": _PARALLELISM,
    "hash_len": _HASH_LEN,
    "salt_len": _SALT_LEN,
}

_hasher: Final = PasswordHasher(
    time_cost=_TIME_COST,
    memory_cost=_MEMORY_COST,
    parallelism=_PARALLELISM,
    hash_len=_HASH_LEN,
    salt_len=_SALT_LEN,
)


def hashear_senha(senha: str) -> str:
    """Produz o hash Argon2id de `senha`, com salt aleatório novo a cada
    chamada — duas chamadas com a MESMA senha produzem hashes DIFERENTES
    (salt), e ambos são aceitos por `verificar_senha`. O valor devolvido é a
    string autodescritiva do Argon2id (`$argon2id$v=...$m=...,t=...,p=...$
    <salt>$<hash>`) pronta para a coluna `senha_hash` — nunca a senha em
    texto claro é retida em nenhum lugar além do parâmetro desta função."""
    return _hasher.hash(senha)


def verificar_senha(hash_armazenado: str, senha: str) -> bool:
    """`True` se `senha` corresponde a `hash_armazenado`, `False` caso
    contrário — NUNCA levanta exceção para senha errada nem para hash
    malformado: os três casos (`VerifyMismatchError` — senha errada;
    `VerificationError` — falha de verificação do driver; `InvalidHashError`
    — `hash_armazenado` não é um hash Argon2id válido) viram `False`, para
    que o chamador não precise (e não possa, por acidente) distinguir "hash
    corrompido" de "senha errada" a partir de uma exceção. Nenhuma das três
    carrega a senha em texto claro em sua mensagem — apenas o hash e
    metadados do algoritmo."""
    try:
        return _hasher.verify(hash_armazenado, senha)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
