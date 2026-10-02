"""Plano e conferência em linguagem humana — `RF-111`, `AC-174` (`T-326`,
absorve `T-306`).

Relato do produto (2026-10-02): a conferência mostrava "D011" como título
da dívida, "método HIBRIDO … D_ESTRELA … (H-05, H-06, H-07)", dados de
entrada crus (`TIPO_DIVIDA = CONSIGNADO`, `CET = DESCONHECIDO`, `0.01`) e
até a representação Python de `RecursoExtraordinario(...)`.

O caso deste teste é o de `AC-174`: um cheque especial da CAIXA (`D011`),
um consignado com `CET` desconhecido (`D001`) e um valor extraordinário —
`SnapshotOrdem` REAL de `calcular_plano`, servido pelas rotas reais
(`/api/revisao/caso/{id}`, `/api/revisao/fila`, `/caso/{id}/api/plano`).

REGRAS: `RF-111`, `AC-174`
"""

from __future__ import annotations

import dataclasses
import enum
import re
import typing
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_papel_revisor, obter_repositorio_casos
from app.http.rotas_coleta import obter_repositorio_itens, obter_repositorio_respostas
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_snapshots_da_fila,
)
from app.http.serializacao_plano import serializar_plano
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import carregar_registros
from collection.respostas import Resposta, RespostasCaso
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    JANELA_RECURSO_EXTRAORDINARIO,
    EstadoFinanceiro,
    RecursoExtraordinario,
)
from engine.gates import TIPO_ACAO_VALORES
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO, EVENTO_RECALCULO, METODO, ORDEM_STATUS, STATUS_METODO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.plano import (
    CENARIO_APRESENTACAO,
    VocabularioDoCaso,
    carregar_textos_canonicos,
    montar_contexto_plano,
)
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    caso_completo_com_divida_gab03,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CASO_ID = "CASO-T326"
_CONTA_ID = "CONTA-T326"
_CAIXA = "CAIXA ECONOMICA FEDERAL"

# Varredura de `AC-174`: nome de variável em CAIXA_ALTA, código `D0nn` e
# representação de dataclass do motor.
_IDENTIFICADOR = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_CODIGO_DE_DIVIDA = re.compile(r"\bD0\d\d\b")
_REPR = re.compile(
    r"\b(?:RecursoExtraordinario|ItemInvestimento|ItemAtivo|Oportunidade|Divida|Decimal)\("
)

# Campos que são IDENTIFICADOR ou DETALHE técnico ao revisor — os únicos em
# que um código pode aparecer. Todo o resto é texto principal.
_CHAVES_DE_DETALHE = frozenset(
    {
        "CASO_ID",
        "SNAPSHOT_ID",
        "DIVIDA_ID",
        "ITEM_ID",
        "codigo",
        "JUSTIFICATIVA_POSICAO",
        "motivo",  # ação: motivo do gate (revisor); `nao_projetados`: código (T-305)
        "METODO_RECOMENDADO_PIQ",
        "STATUS_METODO",
        "EVENTO_RECALCULO",
        "MOTIVO_RECALCULO",
        "ENGINE_VERSION",
        "PARAMETROS_VERSION",
    }
)


def _codigos_no_texto_principal(valor: object, chave: str = "") -> list[str]:
    if isinstance(valor, dict):
        return [a for k, v in valor.items() for a in _codigos_no_texto_principal(v, k)]
    if isinstance(valor, list):
        return [a for v in valor for a in _codigos_no_texto_principal(v, chave)]
    if isinstance(valor, str) and chave not in _CHAVES_DE_DETALHE:
        return [
            f"{chave}: {achado}"
            for padrao in (_IDENTIFICADOR, _CODIGO_DE_DIVIDA, _REPR)
            for achado in padrao.findall(valor)
        ]
    return []


def test_detector_pega_os_tres_tipos_de_codigo() -> None:
    payload = {
        "ordem": [{"nome": "D011", "DIVIDA_ID": "D011"}],
        "campos": [{"valor": "HIBRIDO_X", "codigo": "CET"}],
        "x": "(RecursoExtraordinario(VALOR=1",
    }

    assert _codigos_no_texto_principal(payload) == [
        "nome: D011",
        "valor: HIBRIDO_X",
        "x: RecursoExtraordinario(",
    ]


# ---------------------------------------------------------------------------
# O caso de `AC-174`.
# ---------------------------------------------------------------------------


def _respostas_e_estado() -> tuple[RespostasCaso, EstadoFinanceiro]:
    cheque = caso_completo(
        DIVIDA_ID="D011",
        valores_divida={
            "TIPO_DIVIDA": "CHEQUE_ESPECIAL",
            "CREDOR": _CAIXA,
            # Fração, como `converter_para_taxa` grava: 1,47% a.m.
            "TAXA_INFORMADA": Decimal("0.0147"),
            "PERIODICIDADE_TAXA": "MENSAL",
        },
    )
    consignado = caso_completo(
        DIVIDA_ID="D001",
        valores_divida={"TIPO_DIVIDA": "CONSIGNADO", "CREDOR": "BANCO DO BRASIL"},
    )
    respostas = RespostasCaso(
        respostas=cheque.respostas.respostas
        + tuple(r for r in consignado.respostas.respostas if r.item_id == "D001")
    )
    estado = montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(respostas, "D011"), montar_divida(respostas, "D001")),
        **cheque.parametros_externos,  # type: ignore[arg-type]
    )
    extraordinario = RecursoExtraordinario(
        ITEM_ID="EXT001",
        VALOR_RECURSO_EXTRAORDINARIO=Decimal("15000.00"),
        JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO.UM_A_TRES_MESES,
        CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
    )
    return respostas, replace(estado, recursos_extraordinarios=(extraordinario,))


def _snapshot() -> tuple[RespostasCaso, SnapshotOrdem]:
    respostas, estado = _respostas_e_estado()
    parametros = FonteParametrosArquivo().carregar("1.0.1")
    return respostas, calcular_plano(estado, parametros)


class _Casos:
    def __init__(self, caso: Caso) -> None:
        self._caso = caso

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == _CONTA_ID

    def buscar_varios(self, caso_ids: tuple[str, ...]) -> dict[str, Caso]:
        return {i: self._caso for i in caso_ids if i == self._caso.CASO_ID}

    def listar_por_estado(self, estado: ESTADO_CASO) -> tuple[str, ...]:
        return (self._caso.CASO_ID,)


class _Snapshots:
    def __init__(self, snapshot: SnapshotOrdem) -> None:
        self._snapshot = snapshot

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        return self._snapshot

    def historico(self, raiz_id: str) -> tuple[SnapshotOrdem, ...]:
        return (self._snapshot,)


class _Respostas:
    def __init__(self, respostas: tuple[Resposta, ...]) -> None:
        self._respostas = respostas

    def listar_do_caso(self, *_args: object, **_kwargs: object) -> tuple[Resposta, ...]:
        return self._respostas


class _SemItens:
    def listar_do_caso(self, *_args: object, **_kwargs: object) -> tuple[()]:
        return ()


def _cliente(
    monkeypatch: pytest.MonkeyPatch, estado: ESTADO_CASO
) -> tuple[TestClient, SnapshotOrdem]:
    respostas, snapshot = _snapshot()
    caso = Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=estado,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot.SNAPSHOT_ID,
        snapshot_liberado_id=snapshot.SNAPSHOT_ID,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao: FastAPI = criar_aplicacao()
    casos, snapshots = _Casos(caso), _Snapshots(snapshot)
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: casos
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = lambda: casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: snapshots
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = lambda: snapshots
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: _Respostas(
        respostas.respostas
    )
    aplicacao.dependency_overrides[obter_repositorio_itens] = _SemItens
    aplicacao.dependency_overrides[exigir_papel_revisor] = lambda: "conta-revisor-teste"

    @aplicacao.post("/_teste/abrir-sessao")
    def abrir_sessao(request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=_CONTA_ID)
        return {}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post("/_teste/abrir-sessao")
    return cliente, snapshot


def _conferencia(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], SnapshotOrdem]:
    cliente, snapshot = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)
    resposta = cliente.get(f"/api/revisao/caso/{_CASO_ID}")
    assert resposta.status_code == 200
    corpo: dict[str, Any] = resposta.json()
    return corpo, snapshot


def _campo(campos: list[dict[str, str]], codigo: str) -> dict[str, str]:
    return next(c for c in campos if c["codigo"] == codigo)


def test_ac174_premissas_do_caso(monkeypatch: pytest.MonkeyPatch) -> None:
    _, snapshot = _snapshot()

    assert {d.DIVIDA_ID for d in snapshot.estado_inputs.dividas} == {"D011", "D001"}
    assert "D011" in {p.DIVIDA_ID for p in snapshot.ORDEM_QUITACAO}
    assert all(d.CET is DESCONHECIDO for d in snapshot.estado_inputs.dividas)


def test_ac174_conferencia_em_linguagem_humana(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AC-174`: dívida por "tipo — credor", `CET` "Não informado", valor
    extraordinário por item, método "Híbrido" (ou o rótulo do método do
    caso) e justificativa técnica só no detalhe."""
    corpo, snapshot = _conferencia(monkeypatch)
    plano, entradas, fila = corpo["plano"], corpo["estado_inputs"], corpo["fila"]

    cheque = next(p for p in plano["ordem"] if p["DIVIDA_ID"] == "D011")
    assert cheque["nome"] == f"Cheque especial — {_CAIXA}"
    assert cheque["explicacao"]
    assert cheque["JUSTIFICATIVA_POSICAO"]  # detalhe técnico, só ao revisor

    divida_entrada = next(d for d in entradas["dividas"] if d["DIVIDA_ID"] == "D001")
    assert divida_entrada["nome"] == "Empréstimo consignado — BANCO DO BRASIL"
    cet = _campo(divida_entrada["campos"], "CET")
    assert cet == {"nome": "Custo efetivo total (CET)", "valor": "Não informado", "codigo": "CET"}
    assert _campo(divida_entrada["campos"], "TIPO_DIVIDA")["valor"] == "Empréstimo consignado"

    extraordinarios = _campo(entradas["campos"], "recursos_extraordinarios")["valor"]
    assert "R$ 15.000,00" in extraordinarios
    assert "1–3 meses" in extraordinarios
    assert "RecursoExtraordinario(" not in extraordinarios

    assert _campo(entradas["campos"], "DATA_REFERENCIA")["valor"] == (
        f"{snapshot.estado_inputs.DATA_REFERENCIA:%d/%m/%Y}"
    )
    assert _campo(entradas["campos"], "RENDA_TOTAL_RECORRENTE")["valor"].startswith("R$ ")

    textos = carregar_textos_canonicos()
    assert fila["metodo"] == textos.rotulos_de_codigos[snapshot.METODO_RECOMENDADO_PIQ.value]
    assert plano["metodo"] == fila["metodo"]
    assert fila["status_metodo"] == textos.rotulos_de_codigos[snapshot.STATUS_METODO.value]
    assert fila["motivo"] == "Primeiro cálculo, sem evento de recálculo"

    assert _codigos_no_texto_principal(corpo) == []


def test_ac174_metodo_hibrido_vira_rotulo() -> None:
    assert carregar_textos_canonicos().rotulos_de_codigos["HIBRIDO"] == "Híbrido"


def test_ac174_taxa_com_precisao_util(monkeypatch: pytest.MonkeyPatch) -> None:
    """`0.0147` era exibido "0.01" (`quantizar_exibicao` direto sobre a
    fração); agora "1,47% a.m."."""
    corpo, snapshot = _conferencia(monkeypatch)
    cheque = next(d for d in snapshot.estado_inputs.dividas if d.DIVIDA_ID == "D011")
    assert cheque.TAXA_EFETIVA_MENSAL_NORMALIZADA == Decimal("0.0147")
    divida = next(d for d in corpo["estado_inputs"]["dividas"] if d["DIVIDA_ID"] == "D011")

    campo = _campo(divida["campos"], "TAXA_EFETIVA_MENSAL_NORMALIZADA")

    assert campo["valor"] == "1,47% a.m."
    assert campo["nome"] == "Taxa de juros mensal"


def test_ac174_fila_em_linguagem_humana(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, _ = _cliente(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)

    itens = cliente.get("/api/revisao/fila").json()["itens"]

    assert itens and itens[0]["motivo"] == "Primeiro cálculo, sem evento de recálculo"
    assert _codigos_no_texto_principal(itens) == []


def test_ac174_plano_do_aluno_sem_codigo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ao aluno, nenhum código: nem `D011`, nem o motivo técnico das ações,
    nem o código do cenário no carimbo (`T-306`)."""
    cliente, _ = _cliente(monkeypatch, ESTADO_CASO.PLANO_LIBERADO)

    plano = cliente.get(f"/caso/{_CASO_ID}/api/plano").json()["plano"]

    assert f"Cheque especial — {_CAIXA}" in [p["nome"] for p in plano["ordem"]]
    assert all("JUSTIFICATIVA_POSICAO" not in p for p in plano["ordem"])
    assert all("motivo" not in a for a in plano["acoes"])
    assert _codigos_no_texto_principal(plano) == []


def test_t306_acao_ao_aluno_vem_do_yaml_por_tipo_acao(monkeypatch: pytest.MonkeyPatch) -> None:
    """`T-306`: na ordem vazia (`EC-07`), a ação diz o que fazer em
    português, por `TIPO_ACAO`, e nomeia a dívida; o motivo do gate fica
    para o revisor."""
    caso = caso_completo_com_divida_gab03()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(caso.respostas, caso.DIVIDA_ID),),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    snapshot = calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))
    assert snapshot.ORDEM_ACOES, "premissa: o Gate 1 emite ação de informação"

    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos, VocabularioDoCaso())
    aluno = serializar_plano(contexto)
    revisor = serializar_plano(contexto, para_revisor=True)

    for acao, original in zip(aluno["acoes"], snapshot.ORDEM_ACOES, strict=True):
        assert acao["descricao"] == textos.descricao_da_acao[original.TIPO_ACAO]
        assert "motivo" not in acao
    assert [a["motivo"] for a in revisor["acoes"]] == [a.descricao for a in snapshot.ORDEM_ACOES]
    assert aluno["cenario"] == textos.rotulos_de_codigos["ORDEM_VAZIA"]
    assert _codigos_no_texto_principal(aluno) == []


def test_ac174_pendencias_nomeiam_a_divida(monkeypatch: pytest.MonkeyPatch) -> None:
    """O plano provisório diz QUAL dívida tem dado faltando pelo nome."""
    corpo, snapshot = _conferencia(monkeypatch)
    assert snapshot.ORDEM_STATUS is ORDEM_STATUS.PROVISORIA  # premissa: CET desconhecido

    nomes = {
        p["DIVIDA_ID"]: p["nome"]
        for p in corpo["plano"]["pendencias"]["campos_faltantes_por_divida"]
    }

    assert nomes == {
        "D011": f"Cheque especial — {_CAIXA}",
        "D001": "Empréstimo consignado — BANCO DO BRASIL",
    }


# ---------------------------------------------------------------------------
# Nenhuma variável sem rótulo: o glossário cobre TODO campo que um caso real
# pode produzir, e todo valor de domínio fechado tem rótulo (registro ou
# glossário). Falha listando o que falta.
# ---------------------------------------------------------------------------


def _dataclasses_do_estado() -> list[type]:
    vistos: list[type] = []

    def visitar(classe: type) -> None:
        if classe in vistos:
            return
        vistos.append(classe)
        for tipo in typing.get_type_hints(classe).values():
            for argumento in typing.get_args(tipo) or (tipo,):
                for interno in typing.get_args(argumento) or (argumento,):
                    if dataclasses.is_dataclass(interno) and isinstance(interno, type):
                        visitar(interno)

    visitar(EstadoFinanceiro)
    return vistos


def test_t326_todo_dado_de_entrada_tem_rotulo() -> None:
    rotulos = carregar_textos_canonicos().rotulos_de_dados
    sem_rotulo = [
        f"{classe.__name__}.{campo.name}"
        for classe in _dataclasses_do_estado()
        for campo in dataclasses.fields(classe)
        if campo.name
        not in {
            "DIVIDA_ID",
            "ITEM_ID",
            "dividas",
            "perfil_comportamental",
            "sinais_comportamentais",
        }
        and campo.name not in rotulos
    ]

    assert sem_rotulo == [], "sem rótulo em rotulos_de_dados:\n" + "\n".join(sem_rotulo)


def test_t326_todo_valor_de_dominio_tem_rotulo() -> None:
    codigos = carregar_textos_canonicos().rotulos_de_codigos
    opcoes: dict[str, set[str]] = {}
    for registro in carregar_registros().registros:
        if registro.VARIAVEL_GRAVADA is not None:
            opcoes.setdefault(registro.VARIAVEL_GRAVADA, set()).update(
                o.valor_interno for o in registro.opcoes if o.valor_interno is not None
            )

    sem_rotulo = [
        f"{classe.__name__}.{nome} = {membro.value}"
        for classe in _dataclasses_do_estado()
        for nome, tipo in typing.get_type_hints(classe).items()
        for dominio in typing.get_args(tipo) or (tipo,)
        if isinstance(dominio, type)
        and issubclass(dominio, enum.Enum)
        and dominio.__name__ != "Desconhecido"
        for membro in dominio
        if membro.value not in opcoes.get(nome, set()) and membro.value not in codigos
    ]

    assert sem_rotulo == [], "sem rótulo no registro nem em rotulos_de_codigos:\n" + "\n".join(
        sem_rotulo
    )


def test_t326_metodo_status_cenario_e_evento_tem_rotulo() -> None:
    codigos = carregar_textos_canonicos().rotulos_de_codigos
    todos = [
        m.value for e in (METODO, STATUS_METODO, EVENTO_RECALCULO, CENARIO_APRESENTACAO) for m in e
    ]

    assert [c for c in todos if c not in codigos] == []


def test_t306_toda_acao_tem_descricao_ao_aluno() -> None:
    descricoes = carregar_textos_canonicos().descricao_da_acao
    assert sorted(descricoes) == sorted(TIPO_ACAO_VALORES)
