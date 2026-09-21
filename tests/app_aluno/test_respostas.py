"""Testes de `collection/respostas.py` — RF-10, RF-11, RF-13 (T-22).

Cobre `NaoSei`/`NAO_SEI`, `ValorResposta`, `Resposta` e `RespostasCaso` pelo
comportamento observável. O critério "`ValorResposta` não admite `float`,
verificado por `mypy --strict`" é uma checagem ESTÁTICA, não exercitável em
runtime por `pytest` — está coberta pela verificação ad-hoc de mypy relatada
na entrega desta tarefa (uma atribuição `float` a `ValorResposta` falha a
checagem de tipos) e reforçada aqui em runtime: `NaoSei`/`NAO_SEI` nunca é
confundido com um `float`/`int`/`None`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from collection.registro import EscopoRepeticao
from collection.respostas import NAO_SEI, NaoSei, Resposta, RespostasCaso


def _resposta(
    ID_PERGUNTA: str,
    valor: object,
    item_id: str | None = None,
) -> Resposta:
    return Resposta(
        CASO_ID="CASO-1",
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 1, 1, 12, 0, 0),
    )


def test_nao_sei_e_membro_unico_e_distinto_de_none_e_de_valor_concreto() -> None:
    """RF-11: `NAO_SEI` é resposta de primeira classe — nunca igual a `None`
    (que significa "não perguntado") nem a nenhum valor concreto."""
    valor_qualquer: object = NAO_SEI
    assert NAO_SEI is NaoSei.NAO_SEI
    assert valor_qualquer is not None
    assert valor_qualquer != 0
    assert valor_qualquer != ""
    assert list(NaoSei) == [NaoSei.NAO_SEI]


def test_resposta_none_em_item_id_significa_nao_repetivel_nao_nao_sei() -> None:
    """`item_id=None` é "pergunta não repetível" — um conceito totalmente
    diferente de `NAO_SEI` (que vive em `valor`, nunca em `item_id`)."""
    r = _resposta("B1.01", "sim")
    assert r.item_id is None
    assert r.valor != NAO_SEI


def test_respostas_caso_valor_ausente_e_none_nao_sei_e_valor_dedicado() -> None:
    """`RespostasCaso.valor` distingue as três situações: variável nunca
    respondida (`None`), respondida como `NAO_SEI`, e respondida com um
    valor concreto — nenhuma delas se confunde com a outra."""
    respostas = RespostasCaso(
        respostas=(
            _resposta("B1.01", Decimal("1500.00")),
            _resposta("B1.02", NAO_SEI),
        )
    )
    assert respostas.valor("B1.01") == Decimal("1500.00")
    assert respostas.valor("B1.02") is NAO_SEI
    assert respostas.valor("B1.99") is None


def test_respostas_caso_valor_no_item_isola_por_item(  # AC-04 (via T-22)
) -> None:
    """Duas fichas de dívida (`item_id` distintos) não vazam valor uma para
    a outra — mesma garantia de isolamento por item que `T-15` exige do
    gerador, agora também na leitura pela persistência."""
    respostas = RespostasCaso(
        respostas=(
            _resposta("B5.VALOR", Decimal("100.00"), item_id="D001"),
            _resposta("B5.VALOR", Decimal("200.00"), item_id="D002"),
        )
    )
    assert respostas.valor_no_item("D001", "B5.VALOR") == Decimal("100.00")
    assert respostas.valor_no_item("D002", "B5.VALOR") == Decimal("200.00")
    assert respostas.valor_no_item("D003", "B5.VALOR") is None


def test_respostas_caso_valores_do_escopo_ignora_nao_repetiveis_e_escopo_vazio() -> None:
    """`valores_do_escopo` devolve só os valores gravados EM ALGUM item
    (nunca a variável escalar de `item_id=""`), e tupla vazia — nunca erro —
    quando nenhum item respondeu."""
    respostas = RespostasCaso(
        respostas=(
            _resposta("B5.EXISTE_CARTAO", "sim", item_id="D001"),
            _resposta("B5.EXISTE_CARTAO", "nao", item_id="D002"),
            _resposta("B5.EXISTE_CARTAO", "sim"),  # escalar — não deve aparecer
        )
    )
    valores = respostas.valores_do_escopo(EscopoRepeticao.DIVIDA_ID, "B5.EXISTE_CARTAO")
    assert sorted(str(v) for v in valores) == ["nao", "sim"]  # só os dois dos itens

    vazio = respostas.valores_do_escopo(EscopoRepeticao.MARGEM_ID, "B5.INEXISTENTE")
    assert vazio == ()


def test_respostas_caso_valores_do_escopo_renda_adicional_id_0_1_e_n_itens() -> None:
    """T-105 (`OQ-19`): `RENDA_ADICIONAL_ID` funciona por
    `valores_do_escopo` exatamente como `DIVIDA_ID`/`MARGEM_ID` já funcionam
    — 0, 1 e N fichas de `RENDA_RECORRENTE_ADICIONAL` (B3.03B) são lidas sem
    nenhum código especial por escopo. `variavel` de `valores_do_escopo` é o
    `VARIAVEL_GRAVADA` do registro: `Resposta.ID_PERGUNTA` grava exatamente
    `RegistroPergunta.VARIAVEL_GRAVADA`, não `RegistroPergunta.ID`
    (`app/http/rotas_coleta.py::ID_PERGUNTA=registro.VARIAVEL_GRAVADA`,
    T-42) — daí `_resposta` abaixo receber `"RENDA_RECORRENTE_ADICIONAL"`
    como primeiro argumento, não `"B3.03B"`."""
    vazio = RespostasCaso(respostas=()).valores_do_escopo(
        EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL"
    )
    assert vazio == ()

    uma_ficha = RespostasCaso(
        respostas=(
            _resposta("RENDA_RECORRENTE_ADICIONAL", Decimal("300.00"), item_id="REND001"),
        )
    )
    assert uma_ficha.valores_do_escopo(
        EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL"
    ) == (Decimal("300.00"),)

    tres_fichas = RespostasCaso(
        respostas=(
            _resposta("RENDA_RECORRENTE_ADICIONAL", Decimal("300.00"), item_id="REND001"),
            _resposta("RENDA_RECORRENTE_ADICIONAL", Decimal("450.50"), item_id="REND002"),
            _resposta("RENDA_RECORRENTE_ADICIONAL", Decimal("120.00"), item_id="REND003"),
        )
    )
    valores = tres_fichas.valores_do_escopo(
        EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL"
    )
    assert set(valores) == {Decimal("120.00"), Decimal("300.00"), Decimal("450.50")}


def test_respostas_caso_valores_do_escopo_despesa_nao_mensal_id_0_1_e_n_itens() -> None:
    """T-105 (`OQ-19`): `DESPESA_NAO_MENSAL_ID` funciona por
    `valores_do_escopo` exatamente como `DIVIDA_ID`/`MARGEM_ID` já funcionam
    — 0, 1 e N fichas de `VALOR_DESPESA_NAO_MENSAL` (B3.NM02B) são lidas sem
    nenhum código especial por escopo (mesma convenção `VARIAVEL_GRAVADA`
    do teste acima)."""
    vazio = RespostasCaso(respostas=()).valores_do_escopo(
        EscopoRepeticao.DESPESA_NAO_MENSAL_ID, "VALOR_DESPESA_NAO_MENSAL"
    )
    assert vazio == ()

    uma_ficha = RespostasCaso(
        respostas=(
            _resposta("VALOR_DESPESA_NAO_MENSAL", Decimal("1200.00"), item_id="NM001"),
        )
    )
    assert uma_ficha.valores_do_escopo(
        EscopoRepeticao.DESPESA_NAO_MENSAL_ID, "VALOR_DESPESA_NAO_MENSAL"
    ) == (Decimal("1200.00"),)

    quatro_fichas = RespostasCaso(
        respostas=(
            _resposta("VALOR_DESPESA_NAO_MENSAL", Decimal("1200.00"), item_id="NM001"),
            _resposta("VALOR_DESPESA_NAO_MENSAL", Decimal("300.00"), item_id="NM002"),
            _resposta("VALOR_DESPESA_NAO_MENSAL", Decimal("80.00"), item_id="NM003"),
            _resposta("VALOR_DESPESA_NAO_MENSAL", Decimal("500.00"), item_id="NM004"),
        )
    )
    valores = quatro_fichas.valores_do_escopo(
        EscopoRepeticao.DESPESA_NAO_MENSAL_ID, "VALOR_DESPESA_NAO_MENSAL"
    )
    assert set(valores) == {
        Decimal("80.00"),
        Decimal("300.00"),
        Decimal("500.00"),
        Decimal("1200.00"),
    }
