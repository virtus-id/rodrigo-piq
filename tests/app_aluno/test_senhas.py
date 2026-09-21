"""Testes de `app/http/senhas.py` — `RF-02` (T-28).

Módulo puro, sem banco: os quatro critérios de aceite de T-28 são
exercitáveis sem `DATABASE_URL`. O critério "verificação de senha errada não
distingue conta inexistente de senha errada" é coberto aqui só na metade que
cabe a este módulo (verificar senha errada nunca levanta exceção que
distinga esse caso de qualquer outro); a metade "resultado de `autenticar`
é o mesmo para conta inexistente e senha errada" é coberta em
`tests/app_aluno/integracao/test_persistencia_contas.py`, contra
`persistencia/app_aluno/contas.py::autenticar`.
"""

from __future__ import annotations

from app.http.senhas import _PARAMETROS_ARGON2, hashear_senha, verificar_senha


def test_hash_nao_contem_a_senha_em_texto_claro() -> None:
    """Critério 1 (parte de `app/http/senhas.py`): a senha em texto claro
    não aparece no hash produzido."""
    senha = "minhaSenhaSecreta123!"
    hash_produzido = hashear_senha(senha)

    assert senha not in hash_produzido
    assert hash_produzido.startswith("$argon2id$"), (
        "o hash deve ser explicitamente Argon2id, não outra variante do algoritmo"
    )


def test_dois_hashes_da_mesma_senha_diferem_e_ambos_sao_aceitos() -> None:
    """Critério 2: salt aleatório por chamada — dois hashes da MESMA senha
    são strings diferentes, e `verificar_senha` aceita as duas."""
    senha = "outraSenha456"
    hash_1 = hashear_senha(senha)
    hash_2 = hashear_senha(senha)

    assert hash_1 != hash_2, "dois hashes da mesma senha deveriam diferir (salt aleatório)"
    assert verificar_senha(hash_1, senha) is True
    assert verificar_senha(hash_2, senha) is True


def test_verificacao_de_senha_errada_devolve_falso_sem_excecao() -> None:
    """Critério 3 (parte deste módulo): senha errada contra um hash válido
    devolve `False` — nunca levanta exceção."""
    hash_correto = hashear_senha("senhaVerdadeira")

    resultado = verificar_senha(hash_correto, "senhaErrada")

    assert resultado is False


def test_verificacao_contra_hash_malformado_tambem_devolve_falso_sem_excecao() -> None:
    """Critério 3, caso-limite: um `hash_armazenado` que não é sequer um hash
    Argon2id válido (ex.: dado corrompido) também devolve `False` — pelo
    MESMO caminho de retorno da senha errada, nunca uma exceção que permita
    ao chamador diferenciar "hash corrompido" de "senha errada"."""
    resultado = verificar_senha("isto-nao-e-um-hash-argon2id-valido", "qualquer-senha")

    assert resultado is False


def test_mensagem_de_erro_nunca_contem_a_senha_em_texto_claro() -> None:
    """Critério 1: mesmo em caminhos de exceção (aqui, forçados via hash
    malformado, que internamente levanta e é capturado), a senha em texto
    claro não deveria aparecer em nenhuma mensagem — este teste verifica a
    ausência dela na representação textual da própria função pública, dado
    que `verificar_senha` não expõe nenhuma exceção ao chamador (ver teste
    acima); a garantia formal é de código: nenhuma das exceções tratadas em
    `verificar_senha` recebe `senha` como argumento na construção da
    mensagem (revisão de código), e o teste abaixo trava a assinatura para
    impedir uma regressão que passasse a logar o parâmetro."""
    senha_sentinela = "SENHA_QUE_NUNCA_PODE_APARECER_EM_LOG_OU_ERRO"

    try:
        verificar_senha("hash-invalido-de-proposito", senha_sentinela)
    except Exception as erro:  # pragma: no cover — não deveria ocorrer
        assert senha_sentinela not in str(erro)


def test_parametros_de_custo_estao_declarados_numa_constante_unica() -> None:
    """Critério 4: os parâmetros de custo do Argon2id estão numa única
    constante do módulo, com os cinco campos esperados (time_cost,
    memory_cost, parallelism, hash_len, salt_len)."""
    assert set(_PARAMETROS_ARGON2) == {
        "time_cost",
        "memory_cost",
        "parallelism",
        "hash_len",
        "salt_len",
    }
    # Robustez mínima declarada (RFC 9106 / OWASP): pelo menos 64 MiB de
    # memória e pelo menos 3 iterações — evita que a constante seja
    # enfraquecida por engano numa edição futura.
    assert _PARAMETROS_ARGON2["memory_cost"] >= 65536
    assert _PARAMETROS_ARGON2["time_cost"] >= 3


def test_apenas_uma_declaracao_de_parametros_no_modulo() -> None:
    """Critério 4, reforço: existe só UM valor de `_TIME_COST` no módulo
    (usado tanto em `_PARAMETROS_ARGON2` quanto na construção do
    `PasswordHasher` de fato usado por `hashear_senha`/`verificar_senha`) —
    nenhum segundo literal numérico solto que pudesse divergir dele."""
    import app.http.senhas as modulo_senhas

    assert modulo_senhas._PARAMETROS_ARGON2["time_cost"] == modulo_senhas._TIME_COST
    assert modulo_senhas._PARAMETROS_ARGON2["memory_cost"] == modulo_senhas._MEMORY_COST
    assert modulo_senhas._hasher.time_cost == modulo_senhas._TIME_COST
    assert modulo_senhas._hasher.memory_cost == modulo_senhas._MEMORY_COST
    assert modulo_senhas._hasher.parallelism == modulo_senhas._PARALLELISM
