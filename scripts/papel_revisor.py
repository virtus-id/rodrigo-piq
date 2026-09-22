"""Concede, revoga e lista o papel de revisor — `T-183`.

**O problema que resolve: o primeiro revisor.** O papel de revisor
(`e_revisor`, migração `003`) nasce `false` para toda conta — nenhuma vira
revisora por acidente. Mas até `T-183` não havia NENHUMA forma operacional
de conceder o papel: `promover_a_revisor` existia em
`persistencia/app_aluno/contas.py` e era chamada só pelos testes. Numa
instalação nova, a fila de revisão ficava inalcançável para todo mundo —
os alunos terminariam a coleta e o plano nunca seria liberado, porque não
existe revisor para liberá-lo e não há como criar o primeiro.

**Por que um comando, e não uma rota HTTP.** É um problema de origem: não
há revisor para autorizar a promoção do primeiro revisor. Uma rota teria de
aceitar um segredo de ambiente como autoridade — e seria, para sempre, uma
porta pública que dá acesso de leitura ao caso de TODOS os alunos a quem
tiver o segredo. Este comando exige acesso ao servidor e à `DATABASE_URL`:
superfície de ataque zero pela internet. A operação acontece uma vez na
instalação e quase nunca depois; essa raridade não paga o risco permanente
de manter a porta aberta.

**Três verbos, não um.** `promover` sozinho é irreversível pela via normal:
promover o e-mail errado — um caractere trocado que bata com outra conta
real — daria a um aluno acesso aos casos de todos os outros, e desfazer
exigiria SQL direto em produção, no susto. `revogar` fecha isso. `listar`
existe porque conferir é parte da operação: promover às cegas, sem ver o
resultado, deixa quem administra sem saber se acertou o e-mail.

Uso:

    DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \\
        scripts/papel_revisor.py listar

    DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \\
        scripts/papel_revisor.py promover revisor@exemplo.br

    DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \\
        scripts/papel_revisor.py revogar revisor@exemplo.br

**A conta precisa existir antes.** A promoção pressupõe uma conta já
cadastrada pelo fluxo normal (`T-179`) — este comando nunca cria conta.
Promover um e-mail inexistente falha nomeando o e-mail, em vez de criar
silenciosamente uma conta revisora que ninguém pediu.

REGRAS: `RF-23`, `RF-25`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persistencia.app_aluno.contas import (  # noqa: E402
    ErroContaInexistente,
    ErroGravacaoConta,
    listar_revisores,
    promover_a_revisor,
    revogar_revisor,
)
from persistencia.supabase.conexao import ErroConexaoAusente  # noqa: E402


def _forcar_utf8() -> None:
    """Garante acento legível na saída, em qualquer console.

    **Verificado, não suposto:** rodando este comando no console do Windows,
    a mensagem de erro saiu `promo��o recusada` — o console usa cp1252 por
    padrão e `print` escreve no encoding dele. Num servidor, essas
    mensagens são a ÚNICA orientação de quem está operando, e uma
    orientação ilegível equivale a nenhuma.

    `errors="replace"` porque um caractere que não passe vale menos que o
    comando inteiro morrer com `UnicodeEncodeError` no meio de uma
    promoção."""
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:  # pragma: no branch — sempre em py3.7+
            reconfigurar(encoding="utf-8", errors="replace")


def _normalizar(email: str) -> str:
    """Mesma normalização do cadastro e do login (`.strip().lower()`).

    Sem isto, `Revisor@Exemplo.BR` digitado no terminal não encontraria a
    conta gravada como `revisor@exemplo.br`, e o comando diria "não existe"
    sobre uma conta que existe — mandando quem administra procurar um
    problema que não está no banco."""
    return email.strip().lower()


def _listar() -> int:
    revisores = listar_revisores()
    if not revisores:
        # Estado legítimo (instalação nova), não erro — mas a fila de
        # revisão está inalcançável enquanto durar, e quem roda `listar`
        # precisa saber disso sem ter que deduzir.
        print("Nenhum revisor. A fila de revisão está inalcançável.")
        return 0

    print(f"{len(revisores)} revisor(es):")
    for conta in revisores:
        print(f"  {conta.email}  (conta_id={conta.conta_id}, desde {conta.criado_em:%Y-%m-%d})")
    return 0


def _promover(email: str) -> int:
    promover_a_revisor(email)
    print(f"{email}: agora é revisor.")
    # O aviso não é decorativo. Quem concede o papel precisa saber, no
    # momento em que concede, que acabou de dar acesso aos dados
    # financeiros de todos os alunos — não descobrir depois.
    print("Esta conta passa a ver o caso de TODOS os alunos.")
    return 0


def _revogar(email: str) -> int:
    revogar_revisor(email)
    print(f"{email}: não é mais revisor. A conta e o caso dela seguem intactos.")
    return 0


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="papel_revisor.py",
        description="Concede, revoga e lista o papel de revisor (T-183).",
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    subcomandos.add_parser("listar", help="mostra quem tem o papel de revisor")

    promover = subcomandos.add_parser("promover", help="concede o papel a uma conta existente")
    promover.add_argument("email", help="e-mail da conta já cadastrada")

    revogar = subcomandos.add_parser("revogar", help="tira o papel de uma conta")
    revogar.add_argument("email", help="e-mail da conta revisora")

    return parser


def main(argv: list[str] | None = None) -> int:
    _forcar_utf8()
    argumentos = _construir_parser().parse_args(argv)

    try:
        if argumentos.comando == "listar":
            return _listar()
        if argumentos.comando == "promover":
            return _promover(_normalizar(argumentos.email))
        return _revogar(_normalizar(argumentos.email))
    except ErroConexaoAusente as erro:
        # As três falhas abaixo são de OPERAÇÃO, não defeito de programa: a
        # variável esquecida, o e-mail digitado errado, o banco fora do ar.
        # Um traceback aqui esconderia a causa real no meio do ruído, para
        # alguém que está administrando um servidor, não depurando código.
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    except ErroContaInexistente as erro:
        print(f"erro: {erro}", file=sys.stderr)
        print("A conta precisa existir antes — este comando nunca cria conta.", file=sys.stderr)
        return 3
    except ErroGravacaoConta as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
