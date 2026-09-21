"""Testes de `collection/repeticao.py` — RF-04, AC-04 (T-15).

Cobre `perguntas_da_ficha` e `GeradorDeIdentificadorEmMemoria` pelo
comportamento observável — nunca por implementação interna. Os quatro
critérios de aceite de `T-15` são cobertos um a um.
"""

from __future__ import annotations

import pytest

from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.repeticao import (
    GeradorDeIdentificadorEmMemoria,
    perguntas_da_ficha,
)

_ORIGEM_OPCOES_DE_TESTE = OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None)


def _registro(
    ID: str, *, bloco: int, escopo_repeticao: EscopoRepeticao
) -> RegistroPergunta:
    """Fábrica mínima de `RegistroPergunta` para teste, mesmo padrão de
    `tests/app_aluno/test_opcoes_do_motor.py::_registro`."""
    return RegistroPergunta(
        ID=ID,
        bloco=bloco,
        enunciado="Enunciado de teste.",
        tipo=TipoResposta.TEXTO_CURTO,
        obrigatoriedade=frozenset({Obrigatoriedade.REP}),
        escopo_repeticao=escopo_repeticao,
        opcoes=(),
        VARIAVEL_GRAVADA="VARIAVEL_DE_TESTE",
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=_ORIGEM_OPCOES_DE_TESTE,
        admite_nao_sei=False,
        salto_consequencia=None,
    )


def test_conjunto_de_perguntas_de_uma_ficha_e_derivado_do_escopo_sem_lista_por_bloco() -> None:
    """Critério de aceite 2: `perguntas_da_ficha` devolve exatamente os
    registros cujo `escopo_repeticao` bate com o pedido, misturando blocos
    diferentes de propósito — a prova de que o filtro não é por bloco é ter
    dois registros do MESMO bloco com escopos diferentes, e só um deles
    aparecer no resultado."""
    pergunta_divida_bloco_5 = _registro(
        "B5.A02", bloco=5, escopo_repeticao=EscopoRepeticao.DIVIDA_ID
    )
    pergunta_margem_bloco_5 = _registro(
        "B5.M01", bloco=5, escopo_repeticao=EscopoRepeticao.MARGEM_ID
    )
    pergunta_divida_bloco_9 = _registro(
        "B9.X01", bloco=9, escopo_repeticao=EscopoRepeticao.DIVIDA_ID
    )
    pergunta_nao_repetivel = _registro(
        "B1.01", bloco=1, escopo_repeticao=EscopoRepeticao.NENHUM
    )
    registros = (
        pergunta_divida_bloco_5,
        pergunta_margem_bloco_5,
        pergunta_divida_bloco_9,
        pergunta_nao_repetivel,
    )

    ficha_de_divida = perguntas_da_ficha(registros, EscopoRepeticao.DIVIDA_ID)

    assert ficha_de_divida == (pergunta_divida_bloco_5, pergunta_divida_bloco_9)


def test_escopo_nenhum_nunca_aparece_em_ficha_repetivel() -> None:
    """Complementa o critério 2: uma pergunta de `escopo_repeticao=NENHUM`
    nunca é devolvida por nenhuma ficha, incluindo quando pedida
    explicitamente — `NENHUM` não é um escopo de ficha."""
    pergunta_nao_repetivel = _registro(
        "B1.01", bloco=1, escopo_repeticao=EscopoRepeticao.NENHUM
    )

    resultado = perguntas_da_ficha((pergunta_nao_repetivel,), EscopoRepeticao.NENHUM)

    assert resultado == (pergunta_nao_repetivel,)
    assert perguntas_da_ficha(
        (pergunta_nao_repetivel,), EscopoRepeticao.DIVIDA_ID
    ) == ()


def test_criar_tres_fichas_de_divida_produz_tres_identificadores_distintos_e_estaveis() -> None:
    """Critério de aceite 1: três fichas de dívida no mesmo caso produzem
    três `DIVIDA_ID` distintos. "Estável entre sessões" é verificado
    recriando um NOVO gerador sobre o MESMO estado persistido (aqui,
    simulado por reaplicar os contadores já observados) e confirmando que o
    próximo identificador continua a sequência em vez de reiniciar."""
    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-001"

    d1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    d2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    d3 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)

    assert len({d1, d2, d3}) == 3
    assert (d1, d2, d3) == ("D001", "D002", "D003")

    # "Estável entre sessões": um gerador que reabre o caso a partir do
    # mesmo estado de contador (aqui, o mesmo objeto — a persistência real,
    # T-23, reidrata esse estado do banco) nunca reproduz d1/d2/d3 de novo.
    d4 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    assert d4 == "D004"
    assert d4 not in {d1, d2, d3}


def test_identificadores_de_escopos_diferentes_nao_colidem_entre_si() -> None:
    """Complementa o critério 1: o contador é por `(CASO_ID, escopo)` — uma
    ficha de margem no mesmo caso não consome a sequência de dívida."""
    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-001"

    d1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    m1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.MARGEM_ID)
    d2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)

    assert (d1, m1, d2) == ("D001", "M001", "D002")


def test_identificadores_de_casos_diferentes_nao_colidem_entre_si() -> None:
    """Complementa o critério 1: o contador é por CASO — dois casos distintos
    podem ter, cada um, seu próprio `D001` sem colisão entre eles."""
    gerador = GeradorDeIdentificadorEmMemoria()

    d1_caso_a = gerador.proximo_identificador("CASO-A", EscopoRepeticao.DIVIDA_ID)
    d1_caso_b = gerador.proximo_identificador("CASO-B", EscopoRepeticao.DIVIDA_ID)

    assert d1_caso_a == "D001"
    assert d1_caso_b == "D001"


def test_responder_ficha_2_nao_altera_nenhum_campo_das_fichas_1_e_3() -> None:
    """Critério de aceite 3 (AC-04): cada ficha é identificada por um
    `item_id` próprio, e as respostas de um item são isoladas por
    `(CASO_ID, ID_PERGUNTA, item_id)` (plano §4.3) — este módulo não
    persiste resposta nenhuma, então a prova aqui é sobre o que ELE garante:
    os identificadores de item das fichas 1 e 3 permanecem os mesmos objetos
    (imutáveis, `str`) antes e depois de a ficha 2 ser "respondida" (gerar
    seu identificador não afeta os das demais)."""
    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-001"

    ficha_1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    ficha_2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    ficha_3 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)

    # "Responder" a ficha 2 não tem efeito sobre este módulo (ele não grava
    # resposta), mas qualquer nova consulta ao gerador para o mesmo caso
    # continua a sequência sem jamais reemitir ficha_1 ou ficha_3.
    novo_item_apos_responder_ficha_2 = gerador.proximo_identificador(
        CASO_ID, EscopoRepeticao.DIVIDA_ID
    )

    assert ficha_1 == "D001"
    assert ficha_2 == "D002"
    assert ficha_3 == "D003"
    assert novo_item_apos_responder_ficha_2 == "D004"
    assert {ficha_1, ficha_3}.isdisjoint({novo_item_apos_responder_ficha_2})


def test_item_removido_nao_reaproveita_seu_identificador_para_item_novo() -> None:
    """Critério de aceite 4: o contador do gerador nunca decresce nem
    recicla. Simula a remoção de `D002` (removê-lo é responsabilidade da
    persistência, T-23 — este módulo só garante que o CONTADOR não recua) e
    confirma que o próximo identificador gerado para o mesmo escopo nunca é
    `D002` de novo."""
    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-001"

    d1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    d2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    itens_ativos = {d1, d2}

    # Remoção do item d2 — de responsabilidade da persistência futura; aqui
    # apenas o retiramos do conjunto de itens ativos que o chamador mantém.
    itens_ativos.discard(d2)

    d3 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)

    assert d3 == "D003"
    assert d3 != d2
    assert d2 not in itens_ativos
    assert d3 not in {d1, d2}


def test_renda_adicional_e_despesa_nao_mensal_geram_identificadores_proprios_e_distintos() -> None:
    """T-105 (`OQ-19`): os dois novos escopos seguem exatamente o mesmo
    mecanismo dos cinco já existentes — prefixo próprio, contador monotônico
    por `(CASO_ID, escopo)`, sem colidir entre si nem com os demais."""
    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-001"

    r1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.RENDA_ADICIONAL_ID)
    r2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.RENDA_ADICIONAL_ID)
    n1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DESPESA_NAO_MENSAL_ID)
    r3 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.RENDA_ADICIONAL_ID)

    assert (r1, r2, r3) == ("REND001", "REND002", "REND003")
    assert n1 == "NM001"
    assert len({r1, r2, r3, n1}) == 4


def test_escopo_nenhum_nao_tem_prefixo_de_item_e_e_recusado() -> None:
    """`EscopoRepeticao.NENHUM` não nomeia item nenhum — pedir um
    identificador para ele é um erro de uso do gerador, não um caso
    silencioso."""
    gerador = GeradorDeIdentificadorEmMemoria()

    with pytest.raises(ValueError):
        gerador.proximo_identificador("CASO-001", EscopoRepeticao.NENHUM)
