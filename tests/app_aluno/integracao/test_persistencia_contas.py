"""Testes de `persistencia/app_aluno/contas.py` — `RF-02` (T-28), estendido
com `e_revisor`/`buscar_por_id`/`promover_a_revisor` (`RF-23`, `RF-25`,
T-100).

Todos os testes exigem Postgres real (`@pytest.mark.requer_banco`), pulados
com mensagem explícita sem `DATABASE_URL` (hook de `tests/app_aluno/
conftest.py`), mesmo padrão de `tests/app_aluno/integracao/
test_persistencia_casos.py` (T-23). Os testes de `e_revisor` validam a
migração `003_papel_revisor.sql` (T-100) contra a coluna real: `NOT NULL
DEFAULT false`, o provisionamento manual via `promover_a_revisor`, e a
consulta `buscar_por_id` que a guarda `app/http/isolamento.py::
exigir_papel_revisor` usa a cada requisição.

REGRAS: RF-02, RF-23, RF-25
"""

from __future__ import annotations

import uuid

import pytest

from persistencia.app_aluno.contas import (
    ErroContaInexistente,
    ErroEmailDuplicado,
    RepositorioContasSupabase,
    listar_revisores,
    promover_a_revisor,
    revogar_revisor,
)

pytestmark = pytest.mark.requer_banco


def _database_url() -> str:
    from persistencia.supabase.conexao import obter_database_url

    return obter_database_url()


def _email_novo() -> str:
    return f"teste-t28-{uuid.uuid4().hex}@teste.invalido"


# ---------------------------------------------------------------------------
# Critério 1 — senha em texto claro não aparece em coluna, log ou erro.
# ---------------------------------------------------------------------------


def test_senha_em_texto_claro_nao_e_gravada_na_coluna_senha_hash() -> None:
    """A coluna `senha_hash` nunca contém a senha em texto claro — só o hash
    Argon2id produzido por `app.http.senhas.hashear_senha`."""
    repositorio = RepositorioContasSupabase()
    conta_id = f"TESTE_T28_CONTA_{uuid.uuid4().hex}"
    email = _email_novo()
    senha_em_texto_claro = "SenhaSecretaDoAluno123"

    repositorio.criar(conta_id, email, senha_em_texto_claro)

    conta = repositorio.buscar_por_email(email)
    assert conta is not None
    # `criar` sempre define senha (o caminho sem senha é `provisionar`,
    # `T-179`), então aqui o hash nunca é `None`.
    assert conta.senha_hash is not None
    assert conta.senha_hash != senha_em_texto_claro
    assert senha_em_texto_claro not in conta.senha_hash
    assert conta.senha_hash.startswith("$argon2id$")


def test_email_duplicado_levanta_erro_sem_mencionar_senha() -> None:
    """`UNIQUE` de `email` é respeitado; a exceção nomeia o e-mail, nunca a
    senha (nenhuma das duas tentativas de senha aparece na mensagem)."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    repositorio.criar(f"TESTE_T28_CONTA_{uuid.uuid4().hex}", email, "primeiraSenha")

    with pytest.raises(ErroEmailDuplicado) as excecao:
        repositorio.criar(f"TESTE_T28_CONTA_{uuid.uuid4().hex}", email, "segundaSenhaDiferente")

    mensagem = str(excecao.value)
    assert "primeiraSenha" not in mensagem
    assert "segundaSenhaDiferente" not in mensagem
    assert email in mensagem


# ---------------------------------------------------------------------------
# Critério 2 — dois hashes da mesma senha diferem; ambos autenticam.
# ---------------------------------------------------------------------------


def test_duas_contas_com_a_mesma_senha_tem_hashes_diferentes_e_ambas_autenticam() -> None:
    """Salt aleatório por conta: duas contas com a MESMA senha têm
    `senha_hash` diferentes no banco, e `autenticar` aceita as duas."""
    repositorio = RepositorioContasSupabase()
    senha_compartilhada = "senhaComumEntreDoisAlunos"
    email_1, email_2 = _email_novo(), _email_novo()

    repositorio.criar(f"TESTE_T28_CONTA_{uuid.uuid4().hex}", email_1, senha_compartilhada)
    repositorio.criar(f"TESTE_T28_CONTA_{uuid.uuid4().hex}", email_2, senha_compartilhada)

    conta_1 = repositorio.buscar_por_email(email_1)
    conta_2 = repositorio.buscar_por_email(email_2)
    assert conta_1 is not None and conta_2 is not None
    assert conta_1.senha_hash != conta_2.senha_hash

    assert repositorio.autenticar(email_1, senha_compartilhada) is not None
    assert repositorio.autenticar(email_2, senha_compartilhada) is not None


# ---------------------------------------------------------------------------
# Critério 3 — conta inexistente e senha errada são indistinguíveis.
# ---------------------------------------------------------------------------


def test_autenticar_com_conta_inexistente_e_senha_errada_devolve_o_mesmo_resultado() -> None:
    """`RF-02`: `autenticar` devolve `None` tanto para e-mail que não existe
    quanto para e-mail existente com senha errada — o MESMO valor de
    retorno, sem exceção que permita ao chamador diferenciar os dois casos."""
    repositorio = RepositorioContasSupabase()
    email_existente = _email_novo()
    repositorio.criar(f"TESTE_T28_CONTA_{uuid.uuid4().hex}", email_existente, "senhaCorreta")

    resultado_conta_inexistente = repositorio.autenticar(
        "email-que-nunca-foi-cadastrado@teste.invalido", "qualquer-coisa"
    )
    resultado_senha_errada = repositorio.autenticar(email_existente, "senhaErrada")

    assert resultado_conta_inexistente is None
    assert resultado_senha_errada is None
    assert resultado_conta_inexistente == resultado_senha_errada


def test_autenticar_com_email_e_senha_corretos_devolve_a_conta() -> None:
    """Caminho feliz: credenciais corretas devolvem a `Conta`."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T28_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaCorretaAqui")

    conta = repositorio.autenticar(email, "senhaCorretaAqui")

    assert conta is not None
    assert conta.conta_id == conta_id
    assert conta.email == email


def test_buscar_por_email_inexistente_devolve_none_sem_excecao() -> None:
    """`buscar_por_email` nunca lança para "não encontrado" — só `None`."""
    repositorio = RepositorioContasSupabase()

    resultado = repositorio.buscar_por_email("nao-existe-mesmo@teste.invalido")

    assert resultado is None


# ---------------------------------------------------------------------------
# T-100 — migração `003_papel_revisor.sql` contra Postgres real: `e_revisor`
# nasce `false`, `promover_a_revisor` grava `true`, `buscar_por_id` lê
# fresco do banco a cada chamada.
# ---------------------------------------------------------------------------


def test_conta_nova_nasce_com_e_revisor_false_por_padrao() -> None:
    """Migração `003_papel_revisor.sql`: `e_revisor boolean NOT NULL DEFAULT
    false` — nenhuma conta vira revisora por acidente, nem mesmo uma criada
    DEPOIS da migração (o `DEFAULT` da coluna, não uma decisão do adaptador,
    é quem garante isso)."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    repositorio.criar(f"TESTE_T100_CONTA_{uuid.uuid4().hex}", email, "senhaQualquer")

    conta = repositorio.buscar_por_email(email)

    assert conta is not None
    assert conta.e_revisor is False


def test_promover_a_revisor_grava_e_revisor_true_e_e_lido_por_buscar_por_id() -> None:
    """`promover_a_revisor` (o único mecanismo de provisionamento desta
    feature, fora de UI) grava `e_revisor = true` — `buscar_por_id` (o
    método que `app/http/isolamento.py::exigir_papel_revisor` usa a cada
    requisição) lê o valor promovido, fresco do banco."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T100_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaQualquer")

    antes = repositorio.buscar_por_id(conta_id)
    assert antes is not None
    assert antes.e_revisor is False

    promover_a_revisor(email)

    depois = repositorio.buscar_por_id(conta_id)
    assert depois is not None
    assert depois.e_revisor is True


def test_promover_a_revisor_com_email_inexistente_levanta_erro_sem_criar_conta() -> None:
    """`promover_a_revisor` nunca cria uma conta nova — presume uma conta já
    cadastrada; e-mail inexistente é um erro nomeado, nunca um `UPDATE`
    silencioso de zero linhas."""
    with pytest.raises(ErroContaInexistente) as excecao:
        promover_a_revisor("nunca-foi-cadastrado-t100@teste.invalido")

    assert "nunca-foi-cadastrado-t100@teste.invalido" in str(excecao.value)


def test_buscar_por_id_inexistente_devolve_none_sem_excecao() -> None:
    """`buscar_por_id` nunca lança para "não encontrado" — só `None`, mesma
    disciplina de `buscar_por_email`."""
    repositorio = RepositorioContasSupabase()

    resultado = repositorio.buscar_por_id("CONTA_QUE_NUNCA_EXISTIU_T100")

    assert resultado is None


def test_buscar_por_id_consulta_o_banco_a_cada_chamada_sem_cache() -> None:
    """Reforço direto do critério "sem cache de autorização": duas chamadas
    consecutivas de `buscar_por_id`, com uma promoção a revisor no meio,
    refletem o valor mais recente do BANCO — nenhum valor é memoizado pelo
    adaptador entre chamadas."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T100_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaQualquer")

    primeira_leitura = repositorio.buscar_por_id(conta_id)
    assert primeira_leitura is not None and primeira_leitura.e_revisor is False

    promover_a_revisor(email)

    segunda_leitura = repositorio.buscar_por_id(conta_id)
    assert segunda_leitura is not None and segunda_leitura.e_revisor is True


# ---------------------------------------------------------------------------
# `revogar_revisor` e `listar_revisores` — `T-183`.
#
# Concedido sem como desfazer nem como conferir, o papel de revisor vira uma
# decisão cega e permanente: promover o e-mail errado dá a um aluno acesso
# aos casos de todos os outros, e a única saída seria SQL direto em
# produção, no susto.
# ---------------------------------------------------------------------------


def test_revogar_revisor_tira_o_papel_e_e_lido_por_buscar_por_id() -> None:
    """A revogação é o par de `promover_a_revisor`: `buscar_por_id` — que a
    guarda `exigir_papel_revisor` chama a cada requisição — volta a ler
    `false`, então o acesso à fila fecha na requisição seguinte."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T183_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaQualquer")
    promover_a_revisor(email)

    antes = repositorio.buscar_por_id(conta_id)
    assert antes is not None and antes.e_revisor is True

    revogar_revisor(email)

    depois = repositorio.buscar_por_id(conta_id)
    assert depois is not None and depois.e_revisor is False


def test_revogar_revisor_preserva_a_conta_e_o_email() -> None:
    """**Revogar não é apagar.** A conta perde o papel e volta a ser conta
    comum — o caso e o histórico dela seguem intactos. Se a revogação
    removesse a conta, desfazer uma promoção errada destruiria os dados de
    um aluno real."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T183_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaQualquer")
    promover_a_revisor(email)

    revogar_revisor(email)

    conta = repositorio.buscar_por_id(conta_id)
    assert conta is not None
    assert conta.email == email
    assert conta.senha_hash is not None


def test_revogar_de_quem_nao_e_revisor_e_sucesso_silencioso() -> None:
    """O estado final pedido já é o estado atual. Falhar aqui faria quem
    administra hesitar diante de um comando que já fez o que devia."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    conta_id = f"TESTE_T183_CONTA_{uuid.uuid4().hex}"
    repositorio.criar(conta_id, email, "senhaQualquer")

    revogar_revisor(email)

    conta = repositorio.buscar_por_id(conta_id)
    assert conta is not None and conta.e_revisor is False


def test_revogar_revisor_com_email_inexistente_levanta_erro() -> None:
    """Mesma disciplina de `promover_a_revisor`: e-mail inexistente é erro
    nomeado, nunca um `UPDATE` silencioso de zero linhas que faria quem
    administra achar que revogou o acesso de alguém."""
    with pytest.raises(ErroContaInexistente) as excecao:
        revogar_revisor("nunca-foi-cadastrado-t183@teste.invalido")

    assert "nunca-foi-cadastrado-t183@teste.invalido" in str(excecao.value)


def test_listar_revisores_mostra_o_promovido_e_nao_o_aluno_comum() -> None:
    """A lista é o que permite conferir se a promoção acertou o e-mail —
    e auditar depois quem ficou com acesso aos casos de todos os alunos."""
    repositorio = RepositorioContasSupabase()
    email_revisor = _email_novo()
    email_aluno = _email_novo()
    repositorio.criar(f"TESTE_T183_CONTA_{uuid.uuid4().hex}", email_revisor, "senhaQualquer")
    repositorio.criar(f"TESTE_T183_CONTA_{uuid.uuid4().hex}", email_aluno, "senhaQualquer")
    promover_a_revisor(email_revisor)

    emails = {conta.email for conta in listar_revisores()}

    assert email_revisor in emails
    assert email_aluno not in emails


def test_listar_revisores_deixa_de_mostrar_quem_foi_revogado() -> None:
    """Fecha o ciclo: promover, conferir, revogar, conferir. Sem isto, a
    lista poderia estar lendo um estado velho e ninguém notaria."""
    repositorio = RepositorioContasSupabase()
    email = _email_novo()
    repositorio.criar(f"TESTE_T183_CONTA_{uuid.uuid4().hex}", email, "senhaQualquer")
    promover_a_revisor(email)
    assert email in {conta.email for conta in listar_revisores()}

    revogar_revisor(email)

    assert email not in {conta.email for conta in listar_revisores()}


def test_listar_revisores_devolve_tupla_ordenada_de_forma_estavel() -> None:
    """Ordem estável entre chamadas — uma lista que muda de ordem sozinha
    não serve para comparar antes e depois de uma promoção."""
    repositorio = RepositorioContasSupabase()
    for _ in range(2):
        email = _email_novo()
        repositorio.criar(f"TESTE_T183_CONTA_{uuid.uuid4().hex}", email, "senhaQualquer")
        promover_a_revisor(email)

    primeira = listar_revisores()
    segunda = listar_revisores()

    assert isinstance(primeira, tuple)
    assert [conta.conta_id for conta in primeira] == [conta.conta_id for conta in segunda]
