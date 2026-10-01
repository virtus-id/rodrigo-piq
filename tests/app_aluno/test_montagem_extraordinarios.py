"""Recursos extraordinários item a item — `RF-98`, `RF-81` (`T-270`,
`T-273`, `T-274`, `T-275`).

`AC-04`, `AC-123`, `AC-150`, `AC-151`, `EC-38`, `DE-02`, `DE-03`, sobre os
registros REAIS e a aplicação real com repositórios de arquivo (mesmos
auxiliares de `test_ficha_repetivel.py`). A montagem entrega ao motor um
`RecursoExtraordinario` por item `EXT`, nunca um total; a regra de projeção
é do motor (`motor-calculo` `RF-70`–`RF-76`) e não é asserida aqui.

REGRAS: `RF-98`, `RF-81`, `AC-04`, `AC-123`, `AC-150`, `AC-151`, `EC-38`
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.http.rotas_calculo import _respostas_do_calculo
from app.montagem.estado import ErroRespostaAusente, _recursos_extraordinarios
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.estado import CERTEZA_RECURSO_EXTRAORDINARIO, JANELA_RECURSO_EXTRAORDINARIO
from engine.tipos import DESCONHECIDO
from persistencia.app_aluno.arquivo import RepositorioItensArquivo, RepositorioRespostasArquivo
from tests.app_aluno.test_ficha_repetivel import (
    _CASO_ID,
    _cliente_real,
    _criar_em,
    _fichas,
    _responder,
)

_ESCOPO = EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID.value


@cache
def _registros() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _registro(ID: str) -> RegistroPergunta:
    (registro,) = [r for r in _registros() if r.ID == ID]
    return registro


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-EXT",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def _ficha(
    item_id: str, tipo: str, valor: object, janela: str, certeza: str
) -> tuple[Resposta, ...]:
    return (
        _resposta("TIPO_RECURSO_EXTRAORDINARIO", tipo, item_id),
        _resposta("VALOR_RECURSO_EXTRAORDINARIO", valor, item_id),
        _resposta("JANELA_RECURSO_EXTRAORDINARIO", janela, item_id),
        _resposta("CERTEZA_RECURSO_EXTRAORDINARIO", certeza, item_id),
    )


def _proxima_do_item(cliente: TestClient, item_id: str) -> str:
    corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta", params={"item_id": item_id}).json()
    ID: str = corpo["pergunta"]["ID"]
    return ID


def _respostas_gravadas(tmp_path: Path) -> tuple[Resposta, ...]:
    return RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl",
        repositorio_itens=RepositorioItensArquivo(caminho_arquivo=tmp_path / "itens.jsonl"),
    ).listar_do_caso(_CASO_ID)


# ---------------------------------------------------------------------------
# T-270 — escopo `RECURSO_EXTRAORDINARIO_ID` e `B3.05BF`.
# ---------------------------------------------------------------------------


def test_t270_b305a_d_sao_ficha_do_escopo_novo() -> None:
    for ID in ("B3.05A", "B3.05B", "B3.05BF", "B3.05C", "B3.05D"):
        assert _registro(ID).escopo_repeticao is EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID
    assert _registro("B3.05BF").VARIAVEL_GRAVADA == _registro("B3.05B").VARIAVEL_GRAVADA


def test_t270_sim_em_b305_aponta_a_ficha_e_dois_itens_sao_independentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-04` — cada item `EXT` tem as suas respostas; nada vaza entre eles."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    # `T-311`: o "Sim" cria o primeiro item e leva à primeira pergunta dele.
    proxima = _responder(cliente, "B3.05", "SIM").json()["proxima"]["pergunta"]
    primeiro = proxima["item_id"]
    segundo = _criar_em(cliente, _ESCOPO).json()["ficha"]["item_id"]
    assert (primeiro, segundo) == ("EXT001", "EXT002")

    assert _responder(cliente, "B3.05A", "13O_SALARIO", primeiro).status_code == 200
    assert _responder(cliente, "B3.05A", "VENDA_JA_PREVISTA", segundo).status_code == 200
    assert _responder(cliente, "B3.05B", "1500", primeiro).status_code == 200

    assert _proxima_do_item(cliente, primeiro) == "B3.05C"
    assert _proxima_do_item(cliente, segundo) == "B3.05B"


def test_ac151_ferias_abono_exibe_b305bf_e_grava_o_valor_informado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-151` — em Férias/abono a pergunta é a do acréscimo (`B3.05BF`),
    `B3.05B` não abre, e o valor gravado é o informado: nada de 1/3
    calculado pela aplicação."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    item = _responder(cliente, "B3.05", "SIM").json()["proxima"]["pergunta"]["item_id"]
    _responder(cliente, "B3.05A", "FERIAS_ABONO", item)

    assert _proxima_do_item(cliente, item) == "B3.05BF"
    fechada = cliente.get(f"/caso/{_CASO_ID}/pergunta/B3.05B", params={"item_id": item})
    assert fechada.status_code == 404
    campos = [c["ID"] for c in _fichas(cliente, _ESCOPO)[0]["campos"]]
    assert "B3.05BF" in campos
    assert "B3.05B" not in campos

    assert _responder(cliente, "B3.05BF", "1000", item).status_code == 200
    (valor,) = [
        r.valor
        for r in _respostas_gravadas(tmp_path)
        if r.ID_PERGUNTA == "VALOR_RECURSO_EXTRAORDINARIO" and r.item_id == item
    ]
    assert valor == Decimal("1000")
    assert _proxima_do_item(cliente, item) == "B3.05C"


def test_ac151_outro_tipo_exibe_b305b_e_nao_b305bf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "TALVEZ")
    item = _criar_em(cliente, _ESCOPO).json()["ficha"]["item_id"]
    _responder(cliente, "B3.05A", "13O_SALARIO", item)

    assert _proxima_do_item(cliente, item) == "B3.05B"
    fechada = cliente.get(f"/caso/{_CASO_ID}/pergunta/B3.05BF", params={"item_id": item})
    assert fechada.status_code == 404


# ---------------------------------------------------------------------------
# T-273/T-275 — montagem item a item (`AC-150`, `EC-38`).
# ---------------------------------------------------------------------------


def test_ac150_tres_recursos_viram_tres_itens_distintos_sem_total() -> None:
    respostas = RespostasCaso(
        respostas=(
            _resposta("RECURSOS_EXTRAORDINARIOS_EXISTE", "SIM"),
            *_ficha("EXT001", "13O_SALARIO", Decimal("3000"), "4_6M", "CONFIRMADO"),
            *_ficha("EXT002", "RESTITUICAO_DE_IMPOSTO", Decimal("800"), "1_3M", "PROVAVEL"),
            *_ficha("EXT003", "VENDA_JA_PREVISTA", Decimal("5000"), "7_12M", "POSSIVEL"),
        )
    )

    recursos = _recursos_extraordinarios(respostas)

    assert [
        (
            r.ITEM_ID,
            r.VALOR_RECURSO_EXTRAORDINARIO,
            r.JANELA_RECURSO_EXTRAORDINARIO,
            r.CERTEZA_RECURSO_EXTRAORDINARIO,
        )
        for r in recursos
    ] == [
        (
            "EXT001",
            Decimal("3000"),
            JANELA_RECURSO_EXTRAORDINARIO.QUATRO_A_SEIS_MESES,
            CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
        ),
        (
            "EXT002",
            Decimal("800"),
            JANELA_RECURSO_EXTRAORDINARIO.UM_A_TRES_MESES,
            CERTEZA_RECURSO_EXTRAORDINARIO.PROVAVEL,
        ),
        (
            "EXT003",
            Decimal("5000"),
            JANELA_RECURSO_EXTRAORDINARIO.SETE_A_DOZE_MESES,
            CERTEZA_RECURSO_EXTRAORDINARIO.POSSIVEL,
        ),
    ]
    # Nenhum total: nenhum item carrega a soma dos três.
    assert Decimal("8800") not in {r.VALOR_RECURSO_EXTRAORDINARIO for r in recursos}


@pytest.mark.parametrize(
    ("valor", "janela", "valor_esperado", "janela_esperada"),
    [
        (NAO_SEI, "ATE_30D", DESCONHECIDO, JANELA_RECURSO_EXTRAORDINARIO.ATE_30D),
        (Decimal("2000"), "NAO_SEI", Decimal("2000"), JANELA_RECURSO_EXTRAORDINARIO.NAO_SEI),
    ],
)
def test_ec38_confirmado_com_nao_sei_fica_presente_e_nunca_vira_zero(
    valor: object, janela: str, valor_esperado: object, janela_esperada: object
) -> None:
    respostas = RespostasCaso(
        respostas=_ficha("EXT001", "13O_SALARIO", valor, janela, "CONFIRMADO")
    )

    (recurso,) = _recursos_extraordinarios(respostas)

    assert recurso.VALOR_RECURSO_EXTRAORDINARIO is valor_esperado or (
        recurso.VALOR_RECURSO_EXTRAORDINARIO == valor_esperado
    )
    assert recurso.VALOR_RECURSO_EXTRAORDINARIO != Decimal("0")
    assert recurso.JANELA_RECURSO_EXTRAORDINARIO is janela_esperada


def test_t273_sem_item_ext_e_tupla_vazia() -> None:
    respostas = RespostasCaso(
        respostas=(
            _resposta("RECURSOS_EXTRAORDINARIOS_EXISTE", "NAO"),
            # Legado não migrado (`item_id=''`) não é item.
            _resposta("VALOR_RECURSO_EXTRAORDINARIO", Decimal("50000")),
        )
    )
    assert _recursos_extraordinarios(respostas) == ()


@pytest.mark.parametrize(
    ("ausente", "ID_PERGUNTA"),
    [
        ("TIPO_RECURSO_EXTRAORDINARIO", "B3.05A"),
        ("VALOR_RECURSO_EXTRAORDINARIO", "B3.05B"),
        ("JANELA_RECURSO_EXTRAORDINARIO", "B3.05C"),
        ("CERTEZA_RECURSO_EXTRAORDINARIO", "B3.05D"),
    ],
)
def test_t273_ficha_incompleta_nomeia_a_pergunta(ausente: str, ID_PERGUNTA: str) -> None:
    respostas = RespostasCaso(
        respostas=tuple(
            r
            for r in _ficha("EXT001", "13O_SALARIO", Decimal("3000"), "1_3M", "CONFIRMADO")
            if r.ID_PERGUNTA != ausente
        )
    )

    with pytest.raises(ErroRespostaAusente) as erro:
        _recursos_extraordinarios(respostas)

    assert (erro.value.DIVIDA_ID, erro.value.ID_PERGUNTA) == ("EXT001", ID_PERGUNTA)


def test_t273_ferias_sem_valor_nomeia_a_pergunta_do_acrescimo() -> None:
    respostas = RespostasCaso(
        respostas=tuple(
            r
            for r in _ficha("EXT001", "FERIAS_ABONO", Decimal("1"), "1_3M", "CONFIRMADO")
            if r.ID_PERGUNTA != "VALOR_RECURSO_EXTRAORDINARIO"
        )
    )

    with pytest.raises(ErroRespostaAusente) as erro:
        _recursos_extraordinarios(respostas)

    assert erro.value.ID_PERGUNTA == "B3.05BF"


def test_t275_caso_legado_migrado_pela_008_monta_um_item() -> None:
    """O que `008_extraordinarios_por_item.sql` faz com um caso legado: as
    quatro respostas de `item_id=''` passam a `EXT001`. Montado, é UM item."""
    legado = _ficha("", "13O_SALARIO", Decimal("3000"), "1_3M", "CONFIRMADO")
    migrado = RespostasCaso(
        respostas=tuple(
            Resposta(
                CASO_ID=r.CASO_ID,
                ID_PERGUNTA=r.ID_PERGUNTA,
                item_id="EXT001",
                valor=r.valor,
                QUESTIONARIO_VERSION=r.QUESTIONARIO_VERSION,
                respondida_em=r.respondida_em,
            )
            for r in legado
        )
    )

    (recurso,) = _recursos_extraordinarios(migrado)

    assert recurso.ITEM_ID == "EXT001"
    assert recurso.VALOR_RECURSO_EXTRAORDINARIO == Decimal("3000")


# ---------------------------------------------------------------------------
# T-274/T-275 — restituição de seguro confirmada (`AC-123`, `DE-03`).
# ---------------------------------------------------------------------------


def _divida_com_seguro_cancelado(cliente: TestClient) -> str:
    divida: str = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]
    assert _responder(cliente, "B5.D05", "SIM", divida).status_code == 200
    resposta = _responder(cliente, "B5.D05S", "CANCELADO_COM_RESTITUICAO", divida)
    assert resposta.status_code == 200, resposta.text
    return divida


def _itens_ext(tmp_path: Path) -> list[Any]:
    return [
        item
        for item in RepositorioItensArquivo(
            caminho_arquivo=tmp_path / "itens.jsonl"
        ).listar_do_caso(_CASO_ID, incluir_removidos=False)
        if item.escopo is EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID
    ]


def test_ac123_restituicao_nao_confirmada_nao_cria_recurso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    divida = _divida_com_seguro_cancelado(cliente)

    assert _responder(cliente, "B5.D05R", "NAO_SEI", divida).status_code == 200

    assert _itens_ext(tmp_path) == []
    assert _recursos_extraordinarios(RespostasCaso(respostas=_respostas_gravadas(tmp_path))) == ()


def test_ac123_restituicao_confirmada_cria_um_item_ligado_a_origem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "SIM")
    divida = _divida_com_seguro_cancelado(cliente)

    assert _responder(cliente, "B5.D05R", "300", divida).status_code == 200
    # Reconfirmar (inclusive com outro valor) não duplica: atualiza o item.
    assert _responder(cliente, "B5.D05R", "320", divida).status_code == 200

    # `T-311`: o "Sim" em `B3.05` já criou `EXT001`, sem origem.
    (item,) = [i for i in _itens_ext(tmp_path) if i.origem is not None]
    assert item.origem == f"B5.D05R:{divida}"
    gravadas = {
        r.ID_PERGUNTA: r.valor for r in _respostas_gravadas(tmp_path) if r.item_id == item.item_id
    }
    assert gravadas == {
        "VALOR_RECURSO_EXTRAORDINARIO": Decimal("320"),
        "CERTEZA_RECURSO_EXTRAORDINARIO": "CONFIRMADO",
        "ORIGEM_RECURSO_EXTRAORDINARIO": "B5.D05R",
    }
    # A janela é do aluno, nunca presumida (`R9-10`): a ficha pede o tipo e a
    # janela; valor e certeza já estão lá.
    assert _proxima_do_item(cliente, item.item_id) == "B3.05A"
    _responder(cliente, "B3.05A", "OUTRO", item.item_id)
    # `T-315`: "Outro" pede a descrição.
    assert _proxima_do_item(cliente, item.item_id) == "B3.05AO"
    _responder(cliente, "B3.05AO", "Restituição do seguro", item.item_id)
    assert _proxima_do_item(cliente, item.item_id) == "B3.05C"
    _responder(cliente, "B3.05C", "1_3M", item.item_id)

    (recurso,) = _recursos_extraordinarios(
        RespostasCaso(respostas=_respostas_gravadas(tmp_path))
    )
    assert recurso.ITEM_ID == item.item_id
    assert recurso.VALOR_RECURSO_EXTRAORDINARIO == Decimal("320")
    assert recurso.CERTEZA_RECURSO_EXTRAORDINARIO is CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO


def test_t274_uma_ficha_por_divida_de_origem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    primeira = _divida_com_seguro_cancelado(cliente)
    segunda = _divida_com_seguro_cancelado(cliente)

    _responder(cliente, "B5.D05R", "300", primeira)
    _responder(cliente, "B5.D05R", "150", segunda)
    _responder(cliente, "B5.D05R", "300", primeira)

    assert sorted(item.origem for item in _itens_ext(tmp_path)) == [
        f"B5.D05R:{primeira}",
        f"B5.D05R:{segunda}",
    ]


def test_t286_restituicao_confirmada_conta_mesmo_com_b305_nao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`T-286` (`DE-03`/q3_1): a restituição efetiva é recurso extraordinário
    mesmo que o aluno tenha dito "Não" em `B3.05` — as perguntas do item
    criado por ela abrem e as respostas chegam ao cálculo."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", "NAO")
    divida = _divida_com_seguro_cancelado(cliente)
    _responder(cliente, "B5.D05R", "300", divida)
    (item,) = _itens_ext(tmp_path)

    assert _proxima_do_item(cliente, item.item_id) == "B3.05A"
    assert _responder(cliente, "B3.05A", "OUTRO", item.item_id).status_code == 200
    # `T-315`: "Outro" pede a descrição.
    assert _responder(cliente, "B3.05AO", "Seguro", item.item_id).status_code == 200
    assert _proxima_do_item(cliente, item.item_id) == "B3.05C"
    assert _responder(cliente, "B3.05C", "1_3M", item.item_id).status_code == 200

    do_calculo = _respostas_do_calculo(
        _registros(), RespostasCaso(respostas=_respostas_gravadas(tmp_path))
    )
    (recurso,) = _recursos_extraordinarios(do_calculo)
    assert recurso.ITEM_ID == item.item_id
    assert recurso.VALOR_RECURSO_EXTRAORDINARIO == Decimal("300")


def test_t286_b305_nao_segue_fechando_o_item_declarado_pelo_aluno() -> None:
    """A regra de `B3.05` não muda para os demais itens: "Não" fecha a ficha
    e as respostas dela não chegam ao cálculo."""
    respostas = RespostasCaso(
        respostas=(
            _resposta("RECURSOS_EXTRAORDINARIOS_EXISTE", "NAO"),
            *_ficha("EXT001", "13O_SALARIO", Decimal("1000"), "1_3M", "CONFIRMADO"),
        )
    )

    assert _recursos_extraordinarios(_respostas_do_calculo(_registros(), respostas)) == ()


@pytest.mark.parametrize(("b305", "avisa"), [("NAO", True), ("SIM", False), ("TALVEZ", False)])
def test_t288_restituicao_com_b305_nao_avisa_por_que_a_ficha_apareceu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, b305: str, avisa: bool
) -> None:
    """`T-288` (decisão do produto, 2026-09-30): com `B3.05 = Não`, a
    restituição confirmada cria a ficha do recurso e o aluno lê, ao
    confirmar, por que ela apareceu. Com `Sim`/`Talvez` a ficha já era
    esperada — nenhum aviso."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.05", b305)
    divida = _divida_com_seguro_cancelado(cliente)

    avisos = _responder(cliente, "B5.D05R", "300", divida).json()["avisos"]

    codigos = [aviso["codigo"] for aviso in avisos]
    assert codigos == (["RESTITUICAO_SEGURO_EXTRAORDINARIO"] if avisa else [])
    # "Ainda não foi confirmada" não cria ficha — nada a explicar.
    nao_confirmada = _responder(cliente, "B5.D05R", "NAO_SEI", divida).json()["avisos"]
    assert nao_confirmada == []
