"""Fonte de comprovação e pendências de homologação — `RF-91`, `RF-93`
(`T-261`, `T-263`).

`AC-140`, `EC-36`, `EC-39` sobre os registros REAIS: o nível é atributo da
opção no YAML, e o teste lê o YAML carregado — nunca uma cópia do mapa.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

import pytest

from app.revisao.comprovacao import (
    NivelDaFicha,
    PendenciaHomologacao,
    niveis_por_ficha,
    pendencias_de_homologacao,
)
from collection.carga import carregar_registros
from collection.registro import NIVEL_COMPROVACAO, EscopoRepeticao, RegistroPergunta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso

_N = NIVEL_COMPROVACAO

# `AC-140` / `EC-36` — `valor_interno` → nível esperado, por pergunta de fonte.
_NIVEIS_ESPERADOS: dict[str, dict[str, NIVEL_COMPROVACAO]] = {
    "B5.I02": {
        "DOCUMENTO_CONTRATO": _N.COMPROVADO,
        "APLICATIVO": _N.COMPROVADO,
        "CONTRACHEQUE": _N.COMPROVADO,
        "MEMORIA": _N.INFORMADO,
        "COMBINACAO": _N.INFORMADO,
        "OUTRA": _N.INFORMADO,
        "ATENDIMENTO_CREDOR": _N.PENDENTE_DE_CONFIRMACAO,
    },
    "B7.16": {
        "DOCUMENTO_CONTRATO": _N.COMPROVADO,
        "APLICATIVO": _N.COMPROVADO,
        "MENSAGEM_EMAIL": _N.COMPROVADO,
        "SEM_REGISTRO": _N.INFORMADO,
        "ATENDIMENTO": _N.PENDENTE_DE_CONFIRMACAO,
    },
    "B8.15": {
        "DOCUMENTO_FORMAL": _N.COMPROVADO,
        "APLICATIVO_INTERNET_BANKING": _N.COMPROVADO,
        "SIMULACAO_FORNECIDA_PELA_INSTITUICAO": _N.COMPROVADO,
        "OUTRA_FONTE": _N.INFORMADO,
        "ATENDIMENTO": _N.PENDENTE_DE_CONFIRMACAO,
        "CORRESPONDENTE": _N.PENDENTE_DE_CONFIRMACAO,
    },
}

_AGORA = datetime(2026, 9, 30, tzinfo=UTC)


@cache
def _registros() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _registro(ID: str) -> RegistroPergunta:
    return next(r for r in _registros() if r.ID == ID)


# ---------------------------------------------------------------------------
# T-261 — os níveis e `indispensavel` estão no YAML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ID", sorted(_NIVEIS_ESPERADOS))
def test_t261_toda_opcao_das_perguntas_de_fonte_tem_nivel(ID: str) -> None:
    registro = _registro(ID)

    obtidos = {o.valor_interno: o.nivel_comprovacao for o in registro.opcoes}

    assert obtidos == _NIVEIS_ESPERADOS[ID]


def test_t261_outra_sobe_a_comprovado_so_com_documento_em_b5_i01() -> None:
    (outra,) = [o for o in _registro("B5.I02").opcoes if o.valor_interno == "OUTRA"]

    assert outra.nivel_comprovacao_se is not None
    assert outra.nivel_comprovacao_se.nivel is _N.COMPROVADO


def test_t261_classificacao_de_t218_segue_igual_nas_seis_opcoes() -> None:
    """`T-218`: os seis códigos de `B5.I02` não mudam — só "Outra" ganha o seu."""
    codigos = {o.valor_interno for o in _registro("B5.I02").opcoes}

    assert codigos == {
        "DOCUMENTO_CONTRATO",
        "APLICATIVO",
        "ATENDIMENTO_CREDOR",
        "CONTRACHEQUE",
        "MEMORIA",
        "COMBINACAO",
        "OUTRA",
    }


def test_t261_indispensaveis_sao_os_que_o_motor_le() -> None:
    """`R9-8`: saldo, parcela, taxa (e sua periodicidade, `T-287`) e renda —
    o motor não lê prazo."""
    indispensaveis = {r.ID for r in _registros() if r.indispensavel}

    assert indispensaveis == {"B3.01", "B5.B03", "B5.C02", "B5.D01", "B5.D01A", "B5.D01B"}


# ---------------------------------------------------------------------------
# T-263 — `niveis_por_ficha` e `pendencias_de_homologacao` sobre o YAML real
# ---------------------------------------------------------------------------

_D = "D001"
_ITENS = {EscopoRepeticao.DIVIDA_ID: (_D,)}

# O que abre a pergunta de fonte de cada bloco no item.
_ABRE_FONTE: dict[str, dict[str, object]] = {
    "B5.I02": {},
    "B7.16": {"EXISTE_PROPOSTA_RENEGOCIACAO": "VIGENTE"},
    "B8.15": {"STATUS_TROCA": "PROPOSTA_RECEBIDA"},
}

# Uma dívida com os quatro dados que o motor lê, todos respondidos.
_DIVIDA_COMPLETA: dict[str, object] = {
    "SALDO_DEVEDOR_ATUAL": "1000",
    "POSSUI_PARCELA_DEFINIDA": "SIM",
    "PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)": "100",
    "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
    "TAXA_INFORMADA": "2",
    "PERIODICIDADE_TAXA": "MENSAL",
}


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-COMPROVACAO",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.3",
        respondida_em=_AGORA,
    )


def _caso(no_item: dict[str, object], renda: object = "5000") -> RespostasCaso:
    respostas = [_resposta(v, x, _D) for v, x in no_item.items()]
    if renda is not None:
        respostas.append(_resposta("RENDA_PRINCIPAL", renda))
    return RespostasCaso(respostas=tuple(respostas))


def _nivel_de(ID: str, no_item: dict[str, object]) -> NIVEL_COMPROVACAO | None:
    niveis = niveis_por_ficha(_registros(), _caso(no_item), _ITENS)
    (nivel,) = [n for n in niveis if n.origem_fonte == ID]
    return nivel.nivel


def _pendencias(no_item: dict[str, object], renda: object = "5000") -> set[tuple[str, str]]:
    return {
        (p.ID_PERGUNTA, p.motivo)
        for p in pendencias_de_homologacao(_registros(), _caso(no_item, renda), _ITENS)
    }


@pytest.mark.parametrize(
    ("ID", "valor", "esperado"),
    [(ID, valor, nivel) for ID, mapa in _NIVEIS_ESPERADOS.items() for valor, nivel in mapa.items()],
)
def test_ac140_cada_opcao_no_nivel_esperado(
    ID: str, valor: str, esperado: NIVEL_COMPROVACAO
) -> None:
    variavel = _registro(ID).VARIAVEL_GRAVADA
    assert variavel is not None

    assert _nivel_de(ID, {**_ABRE_FONTE[ID], variavel: valor}) is esperado


def test_ac140_outra_com_documento_associado_e_comprovado() -> None:
    no_item: dict[str, object] = {
        "FONTE_DADO": "OUTRA",
        "DOCUMENTACAO_DISPONIVEL": frozenset({"FATURA"}),
    }

    assert _nivel_de("B5.I02", no_item) is _N.COMPROVADO


def test_ac140_outra_sem_documento_e_informado() -> None:
    no_item: dict[str, object] = {
        "FONTE_DADO": "OUTRA",
        "DOCUMENTACAO_DISPONIVEL": frozenset({"NAO_TENHO_NENHUM_DOCUMENTO_AGORA"}),
    }

    assert _nivel_de("B5.I02", no_item) is _N.INFORMADO


def test_ec36_simulacao_e_nivel_1_e_correspondente_nivel_3() -> None:
    abre = _ABRE_FONTE["B8.15"]
    variavel = "FONTE_DADO (troca)"

    assert _nivel_de("B8.15", {**abre, variavel: "SIMULACAO_FORNECIDA_PELA_INSTITUICAO"}) is (
        _N.COMPROVADO
    )
    assert _nivel_de("B8.15", {**abre, variavel: "CORRESPONDENTE"}) is (
        _N.PENDENTE_DE_CONFIRMACAO
    )


def test_fonte_fechada_pela_condicao_nao_aparece_e_nao_respondida_e_none() -> None:
    niveis = niveis_por_ficha(_registros(), _caso({}), _ITENS)

    assert niveis == (NivelDaFicha(item_id=_D, origem_fonte="B5.I02", nivel=None),)


def test_ec39_seguro_nao_sei_e_nao_informado_nunca_nivel_3() -> None:
    no_item = {**_DIVIDA_COMPLETA, "SEGURO_PRESTAMISTA": "SIM", "SITUACAO_SEGURO": NAO_SEI}

    niveis = niveis_por_ficha(_registros(), _caso(no_item), _ITENS)

    assert all(n.nivel is not _N.PENDENTE_DE_CONFIRMACAO for n in niveis)
    assert _pendencias(no_item) == set()


def test_rf93_dados_completos_e_fonte_comprovada_nenhuma_pendencia() -> None:
    assert _pendencias({**_DIVIDA_COMPLETA, "FONTE_DADO": "DOCUMENTO_CONTRATO"}) == set()


def test_rf93_indispensavel_em_branco_ou_nao_sei_e_ausente() -> None:
    no_item = {**_DIVIDA_COMPLETA, "SALDO_DEVEDOR_ATUAL": NAO_SEI}
    del no_item["TAXA_INFORMADA"]

    assert _pendencias(no_item, renda=None) == {
        ("B3.01", "AUSENTE"),
        ("B5.B03", "AUSENTE"),
        ("B5.D01A", "AUSENTE"),
    }


def test_rf93_fonte_em_nivel_3_pende_todo_indispensavel_da_ficha() -> None:
    no_item = {**_DIVIDA_COMPLETA, "FONTE_DADO": "ATENDIMENTO_CREDOR"}

    assert pendencias_de_homologacao(_registros(), _caso(no_item), _ITENS) == (
        PendenciaHomologacao(_D, "B5.B03", "PENDENTE_DE_CONFIRMACAO"),
        PendenciaHomologacao(_D, "B5.C02", "PENDENTE_DE_CONFIRMACAO"),
        PendenciaHomologacao(_D, "B5.D01A", "PENDENTE_DE_CONFIRMACAO"),
    )


def test_rf93_fonte_de_outro_bloco_em_nivel_3_nao_pende_dado_da_divida() -> None:
    """`B7.16` "atendimento" é a fonte da PROPOSTA, não do saldo/taxa/parcela."""
    no_item = {
        **_DIVIDA_COMPLETA,
        "FONTE_DADO": "DOCUMENTO_CONTRATO",
        "EXISTE_PROPOSTA_RENEGOCIACAO": "VIGENTE",
        "FONTE_DADO (proposta)": "ATENDIMENTO",
    }

    assert _pendencias(no_item) == set()


def test_gab03_parcela_fechada_pela_condicao_rotativo_nunca_pende() -> None:
    no_item = {**_DIVIDA_COMPLETA, "POSSUI_PARCELA_DEFINIDA": "NAO"}
    del no_item["PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)"]

    assert _pendencias(no_item) == set()


def test_r9_9_taxa_anual_respondida_nao_pende() -> None:
    assert _pendencias({**_DIVIDA_COMPLETA, "PERIODICIDADE_TAXA": "ANUAL"}) == set()


def test_t283_taxa_nao_sei_em_b5_d01_e_ausente() -> None:
    """`T-283`/`DE-06`: "Não." em `B5.D01` fecha `B5.D01A`, mas a taxa segue
    indispensável — o próprio `B5.D01` pende como `AUSENTE`."""
    no_item = {**_DIVIDA_COMPLETA, "QUALIDADE_TAXA_INFORMADA": "DESCONHECIDA"}
    del no_item["TAXA_INFORMADA"]

    assert _pendencias(no_item) == {("B5.D01", "AUSENTE")}


def test_t283_b5_d01_em_branco_e_ausente_e_nao_duplica_confirmacao() -> None:
    sem_qualidade = {**_DIVIDA_COMPLETA}
    del sem_qualidade["QUALIDADE_TAXA_INFORMADA"]
    nivel_3 = {**_DIVIDA_COMPLETA, "FONTE_DADO": "ATENDIMENTO_CREDOR"}

    assert _pendencias(sem_qualidade) == {("B5.D01", "AUSENTE")}
    assert ("B5.D01", "PENDENTE_DE_CONFIRMACAO") not in _pendencias(nivel_3)


def test_t287_periodicidade_nao_sei_e_ausente_e_taxa_estimada_nao_pende() -> None:
    """`T-287`/`DE-06` (Rodrigo, 2026-09-30)."""
    assert _pendencias({**_DIVIDA_COMPLETA, "PERIODICIDADE_TAXA": "NAO_SEI"}) == {
        ("B5.D01B", "AUSENTE")
    }
    assert _pendencias({**_DIVIDA_COMPLETA, "QUALIDADE_TAXA_INFORMADA": "ESTIMADA"}) == set()
