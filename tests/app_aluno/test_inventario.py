"""Pendências de inventário — `RF-87`, `RF-88` (`T-247`).

`AC-133`, `AC-135`, `AC-153`, `AC-154`, `EC-32`, `EC-33`, `EC-34`, sobre os
registros REAIS (a pergunta a corrigir é resolvida pela variável no YAML).
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

import pytest

from app.casos.inventario import (
    TIPO_PENDENCIA_INVENTARIO,
    PendenciaInventario,
    mensagem_da_pendencia,
    pendencias_de_inventario,
)
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso

_T = TIPO_PENDENCIA_INVENTARIO


@cache
def _registros() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-INVENTARIO",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def _dividas(n: int) -> tuple[str, ...]:
    return tuple(f"D{i:03d}" for i in range(1, n + 1))


def _pendencias(
    *respostas: Resposta, itens: dict[EscopoRepeticao, tuple[str, ...]] | None = None
) -> tuple[PendenciaInventario, ...]:
    return pendencias_de_inventario(_registros(), RespostasCaso(respostas=respostas), itens or {})


def _fichas_preenchidas(ids: tuple[str, ...]) -> tuple[Resposta, ...]:
    return tuple(_resposta("TIPO_DIVIDA", "PESSOAL", item_id=i) for i in ids)


def test_ac133_sete_declaradas_cinco_fichas_mensagem_exata() -> None:
    fichas = _dividas(5)
    (pendencia,) = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 7),
        *_fichas_preenchidas(fichas),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )

    assert pendencia.tipo is _T.DIVIDAS_FALTANDO
    assert pendencia.ID_PARA_CORRIGIR == "B5.00"
    assert mensagem_da_pendencia(pendencia) == (
        "Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas."
    )


def test_ac134_setima_ficha_remove_a_pendencia() -> None:
    fichas = _dividas(7)
    assert (
        _pendencias(
            _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 7),
            *_fichas_preenchidas(fichas),
            itens={EscopoRepeticao.DIVIDA_ID: fichas},
        )
        == ()
    )


def test_ac154_ec33_seis_fichas_para_cinco_declaradas_pede_atualizar_b5_00() -> None:
    fichas = _dividas(6)
    (pendencia,) = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 5),
        *_fichas_preenchidas(fichas),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )

    assert pendencia.tipo is _T.DIVIDAS_ACIMA
    assert pendencia.ID_PARA_CORRIGIR == "B5.00"
    assert (pendencia.declaradas, pendencia.cadastradas) == (5, 6)

    igualado = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 6),
        *_fichas_preenchidas(fichas),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )
    assert igualado == ()


def test_ac153_ec32_nao_sei_quantas_bloqueia_ate_confirmar_a_ultima() -> None:
    fichas = _dividas(2)
    base = (
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", NAO_SEI),
        *_fichas_preenchidas(fichas),
    )

    (pendencia,) = _pendencias(*base, itens={EscopoRepeticao.DIVIDA_ID: fichas})
    assert pendencia.tipo is _T.DIVIDAS_SEM_CONFIRMACAO
    # A ação direta: cadastrar/confirmar nas fichas, ou dar um número em B5.00.
    assert (pendencia.ID_PARA_CORRIGIR, pendencia.escopo) == ("B5.00", EscopoRepeticao.DIVIDA_ID)
    assert "Faltam" not in mensagem_da_pendencia(pendencia)

    confirmado = _pendencias(
        *base,
        _resposta("SYS (loop)", "NAO_ESTA_FOI_A_ULTIMA", item_id="D002"),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )
    assert confirmado == ()


def test_ac153_nao_tenho_certeza_nao_confirma() -> None:
    fichas = _dividas(1)
    (pendencia,) = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", NAO_SEI),
        _resposta("SYS (loop)", NAO_SEI, item_id="D001"),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )
    assert pendencia.tipo is _T.DIVIDAS_SEM_CONFIRMACAO


@pytest.mark.parametrize(
    ("variavel", "escopo", "tipo", "ID", "mensagem"),
    [
        (
            "DESPESAS_NAO_MENSAIS_EXISTE",
            EscopoRepeticao.DESPESA_NAO_MENSAL_ID,
            _T.NAO_MENSAL_SEM_ITEM,
            "B3.NM01",
            "Você informou que possui despesa não mensal, mas ainda não cadastrou nenhuma",
        ),
        (
            "RENDA_RECORRENTE_ADICIONAL_EXISTE",
            EscopoRepeticao.RENDA_ADICIONAL_ID,
            _T.RENDA_EXTRA_SEM_ITEM,
            "B3.03",
            None,
        ),
        ("VINCULO_CONSIGNAVEL", EscopoRepeticao.VINCULO_ID, _T.VINCULO_SEM_ITEM, "B3.S01", None),
    ],
)
def test_ac135_sim_sem_item_bloqueia_e_nao_remove(
    variavel: str,
    escopo: EscopoRepeticao,
    tipo: TIPO_PENDENCIA_INVENTARIO,
    ID: str,
    mensagem: str | None,
) -> None:
    (pendencia,) = _pendencias(_resposta(variavel, "SIM"))
    assert (pendencia.tipo, pendencia.ID_PARA_CORRIGIR, pendencia.escopo) == (tipo, ID, escopo)
    texto = mensagem_da_pendencia(pendencia)
    assert texto.startswith("Você informou que possui")
    if mensagem is not None:
        assert texto == mensagem

    assert _pendencias(_resposta(variavel, "NAO")) == ()
    assert (
        _pendencias(
            _resposta(variavel, "SIM"),
            _resposta("QUALQUER", "X", item_id="X001"),
            itens={escopo: ("X001",)},
        )
        == ()
    )


def test_ec34_vinculo_nao_sei_sem_ficha_nao_e_pendencia() -> None:
    assert _pendencias(_resposta("VINCULO_CONSIGNAVEL", NAO_SEI)) == ()


def test_ficha_criada_e_vazia_nao_conta_como_cadastrada() -> None:
    fichas = _dividas(2)
    (pendencia,) = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 2),
        *_fichas_preenchidas(fichas[:1]),
        itens={EscopoRepeticao.DIVIDA_ID: fichas},
    )
    assert (pendencia.tipo, pendencia.cadastradas) == (_T.DIVIDAS_FALTANDO, 1)
    assert mensagem_da_pendencia(pendencia) == (
        "Você declarou 2 dívidas e cadastrou 1. Falta 1 ficha."
    )


def test_resposta_de_item_removido_nao_conta() -> None:
    """Item removido não está em `itens_por_escopo` (só ativos): mesmo com
    resposta gravada, não conta como cadastrado."""
    (pendencia,) = _pendencias(
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 1),
        *_fichas_preenchidas(("D001",)),
        itens={},
    )
    assert pendencia.tipo is _T.DIVIDAS_FALTANDO
