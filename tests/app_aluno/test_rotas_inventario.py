"""`GET /caso/{CASO_ID}/inventario` e a etapa do Início — `RF-86`,
`AC-133`, `AC-03` (`T-250`, `T-251`).

Mesmos dublês de `tests/app_aluno/test_rotas_inicio.py`, pela mesma
aplicação real e os mesmos pontos de injeção (`app.dependency_overrides`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_inventario import (
    obter_colecao_de_registros_do_inventario,
    obter_repositorio_itens_do_inventario,
    obter_repositorio_respostas_do_inventario,
)
from app.http.sessao import iniciar_sessao_conta
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta
from persistencia.app_aluno.itens import ItemRepetido
from tests.app_aluno.test_rotas_inicio import (
    _CASO_ALHEIO,
    _CASO_ID,
    _CHAVE_TESTE,
    _CONTA_ALHEIA,
    _CONTA_DONA,
    _caso,
    _colecao_real,
    _RepositorioCasosDublê,
    _RepositorioItensDublê,
    _RepositorioRespostasDublê,
)


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def _cliente(
    monkeypatch: pytest.MonkeyPatch,
    respostas: tuple[Resposta, ...],
    itens: tuple[ItemRepetido, ...] = (),
    conta: str | None = _CONTA_DONA,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    casos = (
        _caso(ESTADO_CASO.COLETA_INICIAL),
        _caso(ESTADO_CASO.COLETA_INICIAL, CASO_ID=_CASO_ALHEIO, conta_id=_CONTA_ALHEIA),
    )
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(casos)
    aplicacao.dependency_overrides[obter_colecao_de_registros_do_inventario] = _colecao_real
    aplicacao.dependency_overrides[obter_repositorio_respostas_do_inventario] = (
        lambda: _RepositorioRespostasDublê(respostas)
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_do_inventario] = (
        lambda: _RepositorioItensDublê(itens)
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    if conta is not None:
        cliente.post(f"/_teste/abrir-sessao/{conta}")
    return cliente


def _ficha(item_id: str) -> ItemRepetido:
    return ItemRepetido(
        item_id=item_id,
        CASO_ID=_CASO_ID,
        escopo=EscopoRepeticao.DIVIDA_ID,
        removido_em=None,
        criado_em=datetime(2026, 9, 30, tzinfo=UTC),
    )


def test_t250_ac133_devolve_a_pendencia_com_a_mensagem_exata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fichas = tuple(_ficha(f"D00{i}") for i in range(1, 6))
    respostas = (
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 7),
        *(_resposta("TIPO_DIVIDA", "PESSOAL", item_id=f.item_id) for f in fichas),
    )

    resposta = _cliente(monkeypatch, respostas, fichas).get(f"/caso/{_CASO_ID}/inventario")

    assert resposta.status_code == 200
    (pendencia,) = resposta.json()["pendencias"]
    assert pendencia["mensagem"] == "Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas."
    assert pendencia["ID_PARA_CORRIGIR"] == "B5.00"
    assert pendencia["tipo"] == "INVENTARIO"


def test_t250_inventario_completo_devolve_lista_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    respostas = (_resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 0),)

    resposta = _cliente(monkeypatch, respostas).get(f"/caso/{_CASO_ID}/inventario")

    assert resposta.json() == {"pendencias": []}


def test_t250_ac03_isolamento_por_caso(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _cliente(monkeypatch, (), conta=None).get(
        f"/caso/{_CASO_ID}/inventario"
    ).status_code == 401
    assert _cliente(monkeypatch, ()).get(f"/caso/{_CASO_ALHEIO}/inventario").status_code == 404


def test_t251_inicio_troca_montar_o_plano_pela_pendencia() -> None:
    """`/inicio` (`T-251`): coleta completa com inventário incompleto → a
    etapa é `inventario`, apontando a declaração a corrigir; completo →
    `calculando`, como antes."""
    from app.casos.fases import FASE_INICIO
    from app.http.rotas_inicio import DESTINO_DA_ETAPA, _proxima_etapa
    from collection.carga import ColecaoDeRegistros
    from collection.respostas import RespostasCaso

    b5_00 = next(r for r in _colecao_real().registros if r.ID == "B5.00")
    colecao = ColecaoDeRegistros(QUESTIONARIO_VERSION="1.0.3", registros=(b5_00,))
    caso = _caso(ESTADO_CASO.COLETA_INICIAL)

    def etapa(declaradas: int) -> tuple[DESTINO_DA_ETAPA, str | None]:
        respostas = RespostasCaso(
            respostas=(_resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", declaradas),)
        )
        proxima = _proxima_etapa(caso, FASE_INICIO.COLETA, colecao, respostas, {})
        return proxima.destino, proxima.ID_PERGUNTA

    assert etapa(3) == (DESTINO_DA_ETAPA.INVENTARIO, "B5.00")
    assert etapa(0) == (DESTINO_DA_ETAPA.CALCULANDO, None)


def test_t324_dividas_faltando_diz_quais_tipos_e_quais_fichas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T-324` (`AC-173`): 12 declaradas, 2 cadastradas e uma criada vazia →
    a mensagem de `RF-87` segue literal e o payload relaciona os tipos
    marcados com os tipos das fichas — sem contagem por tipo."""
    fichas = (_ficha("D001"), _ficha("D002"), _ficha("D003"))
    respostas = (
        _resposta("QUANTIDADE_DIVIDAS_DECLARADA_INICIAL", 12),
        _resposta(
            "TIPOS_DIVIDA_DECLARADOS", frozenset({"CONSIGNADO", "PESSOAL", "CARTAO_ROTATIVO"})
        ),
        _resposta("TIPO_DIVIDA", "PESSOAL", item_id="D001"),
        _resposta("CREDOR", "Banco X", item_id="D001"),
        _resposta("CREDOR", "Loja Y", item_id="D002"),
    )

    resposta = _cliente(monkeypatch, respostas, fichas).get(f"/caso/{_CASO_ID}/inventario")

    (pendencia,) = resposta.json()["pendencias"]
    assert pendencia["mensagem"] == "Você declarou 12 dívidas e cadastrou 2. Faltam 10 fichas."
    assert pendencia["dividas"] == {
        "tipos_sem_ficha": ["Empréstimo consignado", "Cartão com saldo rotativo"],
        "fichas": [
            {"item_id": "D001", "credor": "Banco X", "tipo": "Empréstimo pessoal"},
            {"item_id": "D002", "credor": "Loja Y", "tipo": None},
        ],
        "ficha_vazia": "D003",
    }


def test_t324_tipos_da_declaracao_e_da_ficha_sao_os_mesmos_codigos() -> None:
    """`T-324`/`T-208`: todo tipo declarável (exceto "não tenho certeza") é
    um tipo de ficha — senão o tipo nunca sairia de "sem ficha"."""
    registros = _colecao_real().registros

    def codigos(variavel: str) -> set[str]:
        registro = next(r for r in registros if r.VARIAVEL_GRAVADA == variavel)
        return {
            o.valor_interno
            for o in registro.opcoes
            if o.valor_interno is not None and not o.admite_nao_sei
        }

    assert codigos("TIPOS_DIVIDA_DECLARADOS") == codigos("TIPO_DIVIDA")
