"""O comando de papel de revisor — `T-183`.

**Por que testar um script operacional.** Este comando é a única forma de
criar o primeiro revisor de uma instalação: sem ele, a fila de revisão fica
inalcançável e nenhum plano é liberado. Ele roda uma vez, em produção, por
alguém que não vai depurá-lo — se falhar ali, falha no pior momento
possível e sem ninguém com contexto para consertar.

**Sem banco.** As três funções de `contas.py` são substituídas: o que se
testa aqui é o COMANDO (qual verbo chama qual função, com qual argumento,
e que código de saída devolve), não o SQL — esse é o escopo de
`tests/app_aluno/integracao/test_persistencia_contas.py`, que exige
Postgres real.

REGRAS: `RF-23`, `RF-25`
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import papel_revisor  # noqa: E402

from persistencia.app_aluno.contas import (  # noqa: E402
    Conta,
    ErroContaInexistente,
    ErroGravacaoConta,
)
from persistencia.supabase.conexao import ErroConexaoAusente  # noqa: E402

_EMAIL = "revisor@exemplo.invalido"


def _conta(email: str = _EMAIL, conta_id: str = "CONTA_1") -> Conta:
    return Conta(
        conta_id=conta_id,
        email=email,
        senha_hash="$argon2id$dummy",
        criado_em=datetime(2026, 9, 21, tzinfo=UTC),
        e_revisor=True,
    )


# ---------------------------------------------------------------------------
# Cada verbo chama a função certa, com o argumento certo.
# ---------------------------------------------------------------------------


def test_promover_chama_promover_a_revisor_e_sai_com_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamados: list[str] = []
    monkeypatch.setattr(papel_revisor, "promover_a_revisor", chamados.append)

    assert papel_revisor.main(["promover", _EMAIL]) == 0
    assert chamados == [_EMAIL]


def test_revogar_chama_revogar_revisor_e_sai_com_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamados: list[str] = []
    monkeypatch.setattr(papel_revisor, "revogar_revisor", chamados.append)

    assert papel_revisor.main(["revogar", _EMAIL]) == 0
    assert chamados == [_EMAIL]


def test_promover_nunca_e_chamado_pelo_verbo_revogar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A troca mais cara possível.** Se `revogar` promovesse, quem
    tentasse tirar o acesso de alguém estaria concedendo — e o comando
    diria que deu certo."""

    def _nunca(email: str) -> None:
        raise AssertionError(f"promover_a_revisor não deveria ser chamado: {email!r}")

    monkeypatch.setattr(papel_revisor, "promover_a_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "revogar_revisor", lambda email: None)

    assert papel_revisor.main(["revogar", _EMAIL]) == 0


def test_revogar_nunca_e_chamado_pelo_verbo_promover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _nunca(email: str) -> None:
        raise AssertionError(f"revogar_revisor não deveria ser chamado: {email!r}")

    monkeypatch.setattr(papel_revisor, "revogar_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "promover_a_revisor", lambda email: None)

    assert papel_revisor.main(["promover", _EMAIL]) == 0


def test_listar_nao_grava_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """`listar` é leitura pura: nenhum caminho dele pode alterar papel."""

    def _nunca(email: str) -> None:
        raise AssertionError(f"escrita indevida em listar: {email!r}")

    monkeypatch.setattr(papel_revisor, "promover_a_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "revogar_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "listar_revisores", lambda: (_conta(),))

    assert papel_revisor.main(["listar"]) == 0


# ---------------------------------------------------------------------------
# Normalização do e-mail.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "digitado",
    ["  revisor@exemplo.invalido  ", "Revisor@Exemplo.INVALIDO", "\tREVISOR@exemplo.invalido\n"],
)
def test_email_e_normalizado_como_no_cadastro(
    monkeypatch: pytest.MonkeyPatch, digitado: str
) -> None:
    """Sem isto, `Revisor@Exemplo.BR` digitado no terminal não encontraria a
    conta gravada como `revisor@exemplo.br`: o comando diria "não existe"
    sobre uma conta que existe, mandando quem administra procurar um
    problema que não está no banco."""
    chamados: list[str] = []
    monkeypatch.setattr(papel_revisor, "promover_a_revisor", chamados.append)

    assert papel_revisor.main(["promover", digitado]) == 0
    assert chamados == [_EMAIL]


def test_normalizacao_vale_tambem_para_revogar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A revogação precisa encontrar a mesma conta que a promoção
    encontrou — normalizar só num lado deixaria o acesso concedido."""
    chamados: list[str] = []
    monkeypatch.setattr(papel_revisor, "revogar_revisor", chamados.append)

    assert papel_revisor.main(["revogar", "  Revisor@Exemplo.INVALIDO "]) == 0
    assert chamados == [_EMAIL]


# ---------------------------------------------------------------------------
# A saída — quem roda isto está num terminal, não lendo um traceback.
# ---------------------------------------------------------------------------


def test_listar_sem_revisores_avisa_que_a_fila_esta_inalcancavel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lista vazia é estado legítimo (instalação nova), não erro — mas a
    fila de revisão está inalcançável enquanto durar, e quem roda `listar`
    precisa saber disso sem ter que deduzir."""
    monkeypatch.setattr(papel_revisor, "listar_revisores", tuple)

    assert papel_revisor.main(["listar"]) == 0
    assert "inalcançável" in capsys.readouterr().out


def test_listar_mostra_email_e_conta_id_de_cada_revisor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        papel_revisor,
        "listar_revisores",
        lambda: (_conta(), _conta("outro@exemplo.invalido", "CONTA_2")),
    )

    assert papel_revisor.main(["listar"]) == 0

    saida = capsys.readouterr().out
    assert _EMAIL in saida
    assert "outro@exemplo.invalido" in saida
    assert "CONTA_2" in saida


def test_promover_avisa_o_alcance_do_papel_concedido(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Quem concede precisa saber, no momento em que concede, que acabou de
    dar acesso aos dados financeiros de todos os alunos — não descobrir
    depois."""
    monkeypatch.setattr(papel_revisor, "promover_a_revisor", lambda email: None)

    papel_revisor.main(["promover", _EMAIL])

    assert "TODOS" in capsys.readouterr().out


def test_nenhuma_senha_aparece_na_saida(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Conta` carrega `senha_hash`. A listagem imprime e-mail, `conta_id` e
    data — nunca o hash, que não tem por que passar pelo terminal nem pelo
    histórico do shell."""
    monkeypatch.setattr(papel_revisor, "listar_revisores", lambda: (_conta(),))

    papel_revisor.main(["listar"])

    assert "argon2" not in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# Falhas de operação: código de saída distinto, mensagem em stderr,
# nunca traceback.
# ---------------------------------------------------------------------------


def _levantar(erro: Exception) -> Callable[..., None]:
    def _fn(*_args: object, **_kwargs: object) -> None:
        raise erro

    return _fn


@pytest.mark.parametrize(
    ("erro", "codigo"),
    [
        (ErroConexaoAusente("DATABASE_URL ausente"), 2),
        (ErroContaInexistente("email=x não existe"), 3),
        (ErroGravacaoConta("falha ao promover"), 4),
    ],
)
def test_falha_de_operacao_vira_codigo_de_saida_e_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    erro: Exception,
    codigo: int,
) -> None:
    """Códigos distintos por causa: quem automatiza o provisionamento
    precisa distinguir "esqueci a variável" de "digitei o e-mail errado"
    sem raspar texto de mensagem."""
    monkeypatch.setattr(papel_revisor, "promover_a_revisor", _levantar(erro))

    assert papel_revisor.main(["promover", _EMAIL]) == codigo

    capturado = capsys.readouterr()
    assert "erro:" in capturado.err
    assert capturado.out == ""


def test_conta_inexistente_explica_que_o_comando_nao_cria_conta(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A promoção pressupõe conta cadastrada pelo fluxo normal (`T-179`).
    Dizer só "não existe" deixaria quem administra tentando adivinhar se o
    comando deveria tê-la criado."""
    monkeypatch.setattr(
        papel_revisor, "promover_a_revisor", _levantar(ErroContaInexistente("não existe"))
    )

    papel_revisor.main(["promover", _EMAIL])

    assert "nunca cria conta" in capsys.readouterr().err


def test_saida_e_reconfigurada_para_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Regressão de um defeito observado, não hipotético.** Rodando o
    comando no console do Windows, a mensagem saiu `promo��o recusada`: o
    console usa cp1252 e `print` escreve no encoding dele. Num servidor,
    essas mensagens são a única orientação de quem opera — ilegíveis, não
    orientam nada.

    O teste confere que `main` reconfigura os dois fluxos, e que pede
    `errors="replace"`: um caractere perdido vale menos que o comando
    morrer com `UnicodeEncodeError` no meio de uma promoção."""
    pedidos: list[dict[str, object]] = []

    class _FluxoFalso:
        def reconfigure(self, **kwargs: object) -> None:
            pedidos.append(kwargs)

        def write(self, _texto: str) -> int:
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", _FluxoFalso())
    monkeypatch.setattr(sys, "stderr", _FluxoFalso())
    monkeypatch.setattr(papel_revisor, "listar_revisores", tuple)

    papel_revisor.main(["listar"])

    assert len(pedidos) == 2, "stdout e stderr precisam ser reconfigurados"
    for kwargs in pedidos:
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"


def test_fluxo_sem_reconfigure_nao_quebra_o_comando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nem todo fluxo tem `reconfigure` — um `StringIO` de captura, um pipe
    substituído por outra ferramenta. O comando precisa seguir funcionando:
    acento torto é incômodo, comando que não roda é bloqueio."""

    class _FluxoSemReconfigure:
        def write(self, _texto: str) -> int:
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", _FluxoSemReconfigure())
    monkeypatch.setattr(sys, "stderr", _FluxoSemReconfigure())
    monkeypatch.setattr(papel_revisor, "listar_revisores", tuple)

    assert papel_revisor.main(["listar"]) == 0


# ---------------------------------------------------------------------------
# Uso incorreto do comando.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [[], ["promover"], ["revogar"], ["verbo-que-nao-existe"]])
def test_uso_incorreto_nao_executa_nada(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    """Verbo ausente, e-mail ausente ou verbo inválido param no parser —
    `argparse` sai com `2`, e nenhuma função de papel é chamada. Um comando
    incompleto nunca pode virar uma promoção parcial."""

    def _nunca(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"nada deveria executar para argv={argv!r}")

    monkeypatch.setattr(papel_revisor, "promover_a_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "revogar_revisor", _nunca)
    monkeypatch.setattr(papel_revisor, "listar_revisores", _nunca)

    with pytest.raises(SystemExit) as saida:
        papel_revisor.main(argv)

    assert saida.value.code == 2
