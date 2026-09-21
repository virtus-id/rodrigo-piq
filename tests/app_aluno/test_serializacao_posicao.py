"""`RF-63`, `AC-92` — a posição da pergunta dentro da ficha (T-148).

O localizador do `.top` diz *"Dívida 3 · pergunta 4 de 12"* no protótipo
validado. Estes testes provam os dois campos que o sustentam — `posicao` e
`total_na_ficha` — e, principalmente, **provam o denominador**, que foi onde a
primeira implementação errou.

**O defeito que estes testes existem para impedir.** `posicao_na_ficha` filtrava
só por `escopo_repeticao`, e `DIVIDA_ID` tem 88 registros espalhados por três
blocos: 55 no Bloco 5 (inventário de dívidas), 13 no Bloco 7 (renegociação) e 20
no Bloco 8 (troca). O resultado era *"pergunta 4 de 37"* para quem estava
cadastrando a primeira dívida — somando ao denominador a coleta dirigida
pós-plano, que o aluno só vê meses depois, e só para as dívidas que o motor
sinalizar. O critério `AC-92` foi marcado concluído sem nenhum teste, e foi
assim que passou.
"""

from __future__ import annotations

from collections import Counter
from functools import cache

import pytest

from app.casos.progresso import PosicaoNaFicha, posicao_na_ficha
from app.http.renderizacao import montar_contexto_pergunta
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import RespostasCaso

CASO_ID = "CASO-POSICAO"


@cache
def _colecao() -> ColecaoDeRegistros:
    return carregar_registros()


def _sem_respostas() -> RespostasCaso:
    return RespostasCaso(respostas=())


def _registros_do_escopo(
    escopo: EscopoRepeticao, bloco: int | None = None
) -> tuple[RegistroPergunta, ...]:
    return tuple(
        registro
        for registro in _colecao().registros
        if registro.escopo_repeticao == escopo
        and (bloco is None or registro.bloco == bloco)
    )


# ---------------------------------------------------------------------------
# `AC-92` — o denominador é por escopo E por bloco.
# ---------------------------------------------------------------------------


def test_ac92_o_escopo_divida_id_atravessa_tres_blocos() -> None:
    """A premissa do teste seguinte, medida na coleção REAL.

    Se um dia os Blocos 7 e 8 deixarem de compartilhar `DIVIDA_ID` com o
    Bloco 5, este teste falha e avisa que o risco desapareceu — em vez de
    deixar os testes abaixo passando por vacuidade."""
    por_bloco = Counter(r.bloco for r in _registros_do_escopo(EscopoRepeticao.DIVIDA_ID))

    assert por_bloco[5] > 0, "Bloco 5 deveria ter perguntas por DIVIDA_ID"
    assert por_bloco[7] > 0, "Bloco 7 deveria ter perguntas por DIVIDA_ID"
    assert len(por_bloco) >= 3, (
        f"o escopo DIVIDA_ID deveria atravessar ao menos 3 blocos, tem {dict(por_bloco)}"
    )


def test_ac92_o_denominador_nao_soma_blocos_diferentes() -> None:
    """`AC-92` — o total da ficha é do BLOCO, nunca a soma dos três.

    É a asserção central: o Bloco 7 é coleta dirigida pós-plano, e contar suas
    perguntas contra quem está no inventário mentiria sobre o trabalho
    restante."""
    do_bloco_5 = _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5)
    de_todos_os_blocos = _registros_do_escopo(EscopoRepeticao.DIVIDA_ID)

    posicao = posicao_na_ficha(do_bloco_5[0], _colecao().registros, _sem_respostas())

    assert posicao is not None
    assert posicao.total_na_ficha <= len(do_bloco_5), (
        f"total_na_ficha={posicao.total_na_ficha} passou das "
        f"{len(do_bloco_5)} perguntas do Bloco 5 — está somando outro bloco"
    )
    assert posicao.total_na_ficha < len(de_todos_os_blocos), (
        "total_na_ficha alcançou o total dos três blocos: o filtro por bloco "
        "não está sendo aplicado (era o defeito de T-148)"
    )


def test_ac92_a_posicao_acompanha_a_ordem_das_perguntas_abertas() -> None:
    """`AC-92` — a 4ª pergunta aberta da ficha devolve `posicao = 4`.

    1-indexada, como o aluno conta: ele lê "pergunta 4 de 35", não "3 de 35"."""
    abertas = [
        registro
        for registro in _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5)
        if posicao_na_ficha(registro, _colecao().registros, _sem_respostas()) is not None
    ]

    quarta = posicao_na_ficha(abertas[3], _colecao().registros, _sem_respostas())

    assert quarta is not None
    assert quarta.posicao == 4


@pytest.mark.parametrize("indice", [0, 3, 10])
def test_ac92_o_denominador_e_o_mesmo_para_toda_a_ficha(indice: int) -> None:
    """O total não pode variar entre perguntas da MESMA ficha — senão a barra
    de progresso do `.top` andaria para trás sozinha."""
    do_bloco_5 = _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5)
    primeira = posicao_na_ficha(do_bloco_5[0], _colecao().registros, _sem_respostas())
    outra = posicao_na_ficha(
        do_bloco_5[indice], _colecao().registros, _sem_respostas()
    )

    assert primeira is not None
    assert outra is not None
    assert outra.total_na_ficha == primeira.total_na_ficha


def test_ac92_posicao_e_sempre_menor_ou_igual_ao_total() -> None:
    """Invariante: nenhuma pergunta é a "36 de 35"."""
    for registro in _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5):
        posicao = posicao_na_ficha(registro, _colecao().registros, _sem_respostas())
        if posicao is None:
            continue
        assert 1 <= posicao.posicao <= posicao.total_na_ficha, (
            f"{registro.ID}: posicao={posicao.posicao} fora de "
            f"[1, {posicao.total_na_ficha}]"
        )


# ---------------------------------------------------------------------------
# `AC-92` — pergunta fora de ficha devolve nulo, não um número inventado.
# ---------------------------------------------------------------------------


def test_ac92_pergunta_fora_de_ficha_devolve_nulo() -> None:
    """`AC-92` — sem escopo de repetição, não existe "pergunta 4 de 12": a
    pergunta não pertence a ficha nenhuma. `None` é o caso honesto, e o
    cliente cai no rótulo do bloco."""
    sem_escopo = _registros_do_escopo(EscopoRepeticao.NENHUM)

    assert sem_escopo, "a coleção deveria ter perguntas sem escopo de repetição"
    assert posicao_na_ficha(sem_escopo[0], _colecao().registros, _sem_respostas()) is None


# ---------------------------------------------------------------------------
# `RF-63` — os dois campos atravessam a fronteira HTTP.
# ---------------------------------------------------------------------------


def test_rf63_o_payload_expoe_posicao_e_total_na_ficha() -> None:
    """`RF-63` — os dois campos chegam ao cliente. Sem isso o localizador não
    tem como dizer "pergunta 4 de 35", e o `.top` do protótipo fica vazio."""
    registro = _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5)[3]
    contexto = montar_contexto_pergunta(registro, _sem_respostas(), item_id="D003")
    posicao = posicao_na_ficha(registro, _colecao().registros, _sem_respostas())

    assert posicao is not None
    payload = serializar_pergunta(
        contexto,
        CASO_ID=CASO_ID,
        item_id="D003",
        posicao=posicao.posicao,
        total_na_ficha=posicao.total_na_ficha,
    )

    assert payload["posicao"] == posicao.posicao
    assert payload["total_na_ficha"] == posicao.total_na_ficha


def test_rf63_o_payload_traz_os_campos_como_nulos_fora_de_ficha() -> None:
    """Os campos existem SEMPRE no payload, nulos quando não se aplicam — o
    cliente não precisa checar presença de chave, só o valor."""
    registro = _registros_do_escopo(EscopoRepeticao.NENHUM)[0]
    contexto = montar_contexto_pergunta(registro, _sem_respostas())

    payload = serializar_pergunta(contexto, CASO_ID=CASO_ID)

    assert payload["posicao"] is None
    assert payload["total_na_ficha"] is None


def test_rf63_os_campos_novos_nao_abriram_a_fronteira_de_ac73() -> None:
    """`AC-73` — acrescentar campo ao payload não pode ter deixado passar
    regra de exibição. A lista de proibidos é a mesma de sempre."""
    registro = _registros_do_escopo(EscopoRepeticao.DIVIDA_ID, bloco=5)[0]
    contexto = montar_contexto_pergunta(registro, _sem_respostas(), item_id="D001")

    payload = serializar_pergunta(
        contexto, CASO_ID=CASO_ID, item_id="D001", posicao=1, total_na_ficha=35
    )

    for proibido in (
        "condicao_exibicao",
        "validacoes_cruzadas",
        "obrigatoriedade",
        "interpolacoes",
        "VARIAVEL_GRAVADA",
    ):
        assert proibido not in payload, f"{proibido} atravessou a fronteira"


def test_rf63_dataclass_de_posicao_e_imutavel() -> None:
    """`PosicaoNaFicha` é `frozen`: o localizador não é recalculado a meio
    caminho por ninguém."""
    posicao = PosicaoNaFicha(posicao=4, total_na_ficha=35)

    with pytest.raises(AttributeError):
        posicao.posicao = 5  # type: ignore[misc]
