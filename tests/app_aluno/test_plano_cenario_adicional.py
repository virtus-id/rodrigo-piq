"""Cenário adicional separado do plano principal — `RF-98`, `AC-152`,
`AC-42` (`T-276`, `T-278`, `DE-02`).

O snapshot vem de `engine.motor.calcular_plano` sobre a fixture de caso
completo com UM recurso extraordinário incerto — nunca um `SnapshotOrdem`
fabricado à mão. Nenhum valor esperado de prazo ou custo é escrito aqui: o
teste compara o que o plano exibe com os campos do próprio snapshot.

REGRAS: `RF-98`, `AC-152`, `AC-42`
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.http.serializacao_plano import serializar_plano
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import Resposta, RespostasCaso
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.plano import (
    VocabularioDoCaso,
    carregar_textos_canonicos,
    formatar_dinheiro_br,
    montar_contexto_plano,
    nomear_dividas,
)
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    DIVIDA_ID_UNICA,
    caso_completo,
)

_ITEM = "EXT001"


def _snapshot(certeza: str | None) -> SnapshotOrdem:
    caso = caso_completo()
    ficha = (
        ()
        if certeza is None
        else tuple(
            Resposta(
                CASO_ID="CASO-T278",
                ID_PERGUNTA=variavel,
                item_id=_ITEM,
                valor=valor,
                QUESTIONARIO_VERSION="1.0.3",
                respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
            )
            for variavel, valor in (
                ("TIPO_RECURSO_EXTRAORDINARIO", "RESTITUICAO_DE_IMPOSTO"),
                ("VALOR_RECURSO_EXTRAORDINARIO", Decimal("2000")),
                ("JANELA_RECURSO_EXTRAORDINARIO", "1_3M"),
                ("CERTEZA_RECURSO_EXTRAORDINARIO", certeza),
            )
        )
    )
    respostas = RespostasCaso(respostas=(*caso.respostas.respostas, *ficha))
    estado = montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(respostas, DIVIDA_ID_UNICA),),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    return calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))


def _plano(snapshot: SnapshotOrdem) -> dict[str, object]:
    return serializar_plano(montar_contexto_plano(snapshot, carregar_textos_canonicos()))


def test_t276_snapshot_sem_projecao_nao_tem_cenario_adicional() -> None:
    plano = _plano(_snapshot(None))

    assert plano["cenario_adicional"] is None
    assert plano["nao_projetados"] == []


@pytest.mark.parametrize("certeza", ["PROVAVEL", "POSSIVEL"])
def test_ac152_incerto_so_no_cenario_adicional_separado_e_rotulado(certeza: str) -> None:
    snapshot = _snapshot(certeza)
    adicional_do_snapshot = snapshot.projecao_extraordinarios.cenario_adicional
    assert adicional_do_snapshot is not None, "o motor não projetou o recurso incerto"
    base = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]

    plano = _plano(snapshot)

    # Plano principal: os campos da projeção-base, e nenhum rastro do item.
    assert [p["DIVIDA_ID"] for p in plano["ordem"]] == [  # type: ignore[attr-defined]
        p.DIVIDA_ID for p in snapshot.ORDEM_QUITACAO
    ]
    assert plano["CUSTO_FUTURO_TOTAL"] == formatar_dinheiro_br(base.CUSTO_FUTURO_TOTAL)
    assert str(base.PRAZO_TOTAL) in str(plano["PRAZO_TOTAL"])
    principal = {k: v for k, v in plano.items() if k not in ("cenario_adicional", "nao_projetados")}
    assert _ITEM not in json.dumps(principal, default=str)
    # Na projeção-base o item incerto fica de fora, com o motivo do motor.
    assert plano["nao_projetados"] == [{"ITEM_ID": _ITEM, "motivo": "CERTEZA_FORA_DO_CONJUNTO"}]

    # Cenário adicional: seção própria, rotulada, lida do snapshot.
    adicional = plano["cenario_adicional"]
    assert isinstance(adicional, dict)
    assert adicional["rotulo"]
    # `T-326` (`RF-111`): a ordem do cenário adicional também chama a
    # dívida pelo nome, não pelo `DIVIDA_ID`.
    nomes = nomear_dividas(
        snapshot.estado_inputs.dividas, carregar_textos_canonicos(), VocabularioDoCaso()
    )
    assert adicional["ordem"] == [nomes[d] for d in adicional_do_snapshot.ORDEM_QUITACAO]
    assert adicional["CUSTO_FUTURO_TOTAL"] == formatar_dinheiro_br(
        adicional_do_snapshot.CUSTO_FUTURO_TOTAL
    )
    assert str(adicional_do_snapshot.PRAZO_TOTAL) in adicional["PRAZO_TOTAL"]
    # Plano amigável (2026-10-03): ao ALUNO, `ITEM_ID` (`EXT001`) não
    # aparece — nenhum código chega ao texto principal (AC-174). Só `mes`/
    # `valor` seguem, na mesma ordem dos aportes do snapshot.
    assert "ITEM_ID" not in json.dumps(adicional["itens"], default=str)
    assert [i["mes"] for i in adicional["itens"]] == [
        a.mes for a in adicional_do_snapshot.aportes
    ]
    # Ao REVISOR (`para_revisor=True`), o `ITEM_ID` continua disponível
    # como detalhe de auditoria.
    plano_revisor = serializar_plano(
        montar_contexto_plano(snapshot, carregar_textos_canonicos()), para_revisor=True
    )
    adicional_revisor = plano_revisor["cenario_adicional"]
    assert isinstance(adicional_revisor, dict)
    assert [(i["ITEM_ID"], i["mes"]) for i in adicional_revisor["itens"]] == [
        (a.ITEM_ID, a.mes) for a in adicional_do_snapshot.aportes
    ]


def test_t276_confirmado_sem_valor_aparece_em_nao_projetados() -> None:
    """`EC-38` — o item fica visível com o motivo; nunca vira `0`."""
    caso = caso_completo()
    ficha = tuple(
        Resposta(
            CASO_ID="CASO-T278",
            ID_PERGUNTA=variavel,
            item_id=_ITEM,
            valor=valor,
            QUESTIONARIO_VERSION="1.0.3",
            respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
        )
        for variavel, valor in (
            ("TIPO_RECURSO_EXTRAORDINARIO", "13O_SALARIO"),
            ("VALOR_RECURSO_EXTRAORDINARIO", Decimal("1000")),
            ("JANELA_RECURSO_EXTRAORDINARIO", "NAO_SEI"),
            ("CERTEZA_RECURSO_EXTRAORDINARIO", "CONFIRMADO"),
        )
    )
    respostas = RespostasCaso(respostas=(*caso.respostas.respostas, *ficha))
    estado = montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(respostas, DIVIDA_ID_UNICA),),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )

    plano = _plano(calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1")))

    assert plano["nao_projetados"] == [{"ITEM_ID": _ITEM, "motivo": "JANELA_NAO_SEI"}]
    assert plano["cenario_adicional"] is None
