"""Testes de `app/casos/maquina.py` — `RF-01` (`AC-33`, `AC-34`, T-33).

Cobre os quatro critérios de aceite de T-33. A suíte exaustiva sobre o
produto cartesiano de todos os pares de estado e o caminho completo do
plano §7.1 ficam para `T-34` (`tests/app_aluno/test_maquina_de_estados.py`);
aqui só se prova o que T-33 promete construir.
"""

from __future__ import annotations

import itertools

import pytest

from app.casos.maquina import (
    ESTADO_CASO,
    TABELA_TRANSICOES,
    ErroTransicaoNaoDeclarada,
    Transicao,
    transicionar,
)


def test_estado_caso_tem_exatamente_os_doze_membros_do_plano() -> None:
    """Critério 1: `ESTADO_CASO` tem exatamente os doze membros do plano
    §4.3, com os nomes caractere por caractere."""
    nomes_esperados = {
        "CADASTRADO",
        "CONSENTIMENTO_REGISTRADO",
        "COLETA_INICIAL",
        "CALCULANDO",
        "ERRO_DE_CALCULO",
        "AGUARDANDO_REVISAO",
        "REPROVADO_EM_REVISAO",
        "PLANO_LIBERADO",
        "COLETA_DIRIGIDA",
        "CONFIRMACAO_ATAQUE",
        "ACOMPANHAMENTO",
        "ENCERRADO",
    }
    nomes_reais = {membro.name for membro in ESTADO_CASO}

    assert nomes_reais == nomes_esperados
    assert len(ESTADO_CASO) == 12
    # Nome do membro e valor da string devem coincidir caractere por
    # caractere — nenhuma tradução entre o identificador Python e o valor
    # persistido na coluna `app_aluno.casos.estado`.
    for membro in ESTADO_CASO:
        assert membro.name == membro.value


def test_toda_transicao_declarada_tem_de_para_gatilho_e_guarda_opcional() -> None:
    """Critério 2: toda transição declarada tem `de`, `para`, `gatilho`
    nomeado (string não vazia) e `guarda` opcional (`str | None`)."""
    assert len(TABELA_TRANSICOES) > 0

    for transicao in TABELA_TRANSICOES:
        assert isinstance(transicao, Transicao)
        assert isinstance(transicao.de, ESTADO_CASO)
        assert isinstance(transicao.para, ESTADO_CASO)
        assert isinstance(transicao.gatilho, str) and transicao.gatilho.strip() != "", (
            f"transição {transicao.de} → {transicao.para} sem gatilho nomeado"
        )
        assert transicao.guarda is None or isinstance(transicao.guarda, str)


def test_transicao_nao_declarada_levanta_erro_nomeando_origem_e_destino() -> None:
    """Critério 3: um par `(de, para)` fora da tabela é recusado, nunca
    silenciosamente aceito, e o erro nomeia origem e destino."""
    declarados = {(t.de, t.para) for t in TABELA_TRANSICOES}

    # ENCERRADO -> CADASTRADO nunca é declarado em lugar nenhum do plano.
    par_nao_declarado = (ESTADO_CASO.ENCERRADO, ESTADO_CASO.CADASTRADO)
    assert par_nao_declarado not in declarados

    with pytest.raises(ErroTransicaoNaoDeclarada) as capturado:
        transicionar(*par_nao_declarado)

    erro = capturado.value
    assert erro.de is ESTADO_CASO.ENCERRADO
    assert erro.para is ESTADO_CASO.CADASTRADO
    assert "ENCERRADO" in str(erro)
    assert "CADASTRADO" in str(erro)


def test_nenhum_par_fora_da_tabela_e_tolerado_amostra_do_produto_cartesiano() -> None:
    """Reforço do critério 3, numa amostra do produto cartesiano completo
    (a exaustão total é responsabilidade de T-34): todo par não declarado
    levanta `ErroTransicaoNaoDeclarada`; todo par declarado devolve a
    `Transicao` correspondente, sem exceção."""
    declarados = {(t.de, t.para): t for t in TABELA_TRANSICOES}

    for de, para in itertools.product(ESTADO_CASO, ESTADO_CASO):
        if (de, para) in declarados:
            assert transicionar(de, para) == declarados[(de, para)]
        else:
            try:
                transicionar(de, para)
            except ErroTransicaoNaoDeclarada as erro:
                assert erro.de is de
                assert erro.para is para
            else:
                raise AssertionError(
                    f"par não declarado ({de}, {para}) foi silenciosamente aceito"
                )


def test_reabertura_de_pergunta_nao_e_estado() -> None:
    """Critério 4: não existe membro de `ESTADO_CASO` para "reaberto" — a
    reabertura de pergunta (`AC-33`, `AC-34`) vive na pergunta, nunca no
    estado do caso (plano §7.1, "por que reabertura não é estado")."""
    nomes = {membro.name for membro in ESTADO_CASO}
    valores = {membro.value for membro in ESTADO_CASO}

    for termo_proibido in ("REABERTO", "REABERTURA", "REOPEN", "REOPENED"):
        assert termo_proibido not in nomes
        assert termo_proibido not in valores
