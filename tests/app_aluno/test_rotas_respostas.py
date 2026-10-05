"""`GET /caso/{CASO_ID}/respostas` — rever o que já foi respondido.

`RF-68`, `AC-100`, `AC-101` (T-160).

**Por que esta rota nasceu.** Dois relatos do mesmo teste de uso: *"as
perguntas que eu respondi não consigo editar"* e *"nem consigo ver o que foi
respondido, e se eu esquecer"*. O backend permitia as duas coisas desde
`T-42` — faltava superfície. `RF-10` promete retomada **sem redigitar**;
ninguém tinha escrito que promete **conferência**, e por isso nenhum critério
cobria o caso.

Sem `DATABASE_URL`: tudo por `app.dependency_overrides`, o mesmo mecanismo da
produção.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from typing import Any, Final

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta, ValorResposta
from persistencia.app_aluno.itens import ItemRepetido

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-producao"
_CONTA_DONA: Final[str] = "CONTA-RESPOSTAS"
_CASO: Final[str] = "CASO-RESPOSTAS"

# `B1.01` é a primeira pergunta do Bloco 1 — `SELECAO_UNICA`, sem condicional
# e sem escopo de repetição. Serve de âncora estável: se ela mudar de bloco ou
# de tipo, estes testes falham alto em vez de passar medindo outra coisa.
_PERGUNTA_B1: Final[str] = "B1.01"
_VALOR_B1: Final[str] = "ESTABELECIDO"


@cache
def _colecao_real() -> ColecaoDeRegistros:
    return carregar_registros()


class _RepositorioCasosDublê:
    """Só o que a dependência de isolamento usa."""

    def __init__(self, caso: Caso) -> None:
        self._caso = caso

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._caso.conta_id


class _RepositorioRespostasDublê:
    def __init__(self, respostas: tuple[Resposta, ...] = ()) -> None:
        self._respostas = respostas

    def gravar(self, resposta: Resposta) -> None:  # pragma: no cover — a rota só lê
        raise NotImplementedError("GET /respostas não grava")

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(r for r in self._respostas if r.CASO_ID == caso_id)


class _RepositorioItensDublê:
    def __init__(self, itens: tuple[ItemRepetido, ...] = ()) -> None:
        self._itens = itens

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = False
    ) -> tuple[ItemRepetido, ...]:
        return tuple(i for i in self._itens if i.CASO_ID == caso_id)


def _caso_fabricado() -> Caso:
    return Caso(
        CASO_ID=_CASO,
        conta_id=_CONTA_DONA,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _resposta(
    id_pergunta: str, valor: ValorResposta, item_id: str | None = None
) -> Resposta:
    """Uma resposta gravada, como a PRODUÇÃO a grava.

    ⚠️ **O campo se chama `ID_PERGUNTA` mas guarda a `VARIAVEL_GRAVADA`.**
    `rotas_coleta.py:497` faz `ID_PERGUNTA=registro.VARIAVEL_GRAVADA`, e
    `RespostasCaso._indice` indexa por esse campo enquanto `valor()` recebe a
    variável — o par só fecha porque quem grava já converteu.

    Fabricar com o `ID` real (`"B1.01"`) produz uma resposta que NENHUMA
    consulta encontra: o índice teria `B1.01` e a busca pediria `PACTO`. Este
    helper converte pelo registro, para o dublê ficar na mesma forma do banco.
    """
    registro = next(r for r in _colecao_real().registros if r.ID == id_pergunta)
    assert registro.VARIAVEL_GRAVADA is not None, f"{id_pergunta} sem variável"
    return Resposta(
        CASO_ID=_CASO,
        ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 3, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    respostas: tuple[Resposta, ...] = (),
    itens: tuple[ItemRepetido, ...] = (),
    conta_da_sessao: str | None = _CONTA_DONA,
) -> TestClient:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    caso = _caso_fabricado()

    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: (
        _RepositorioCasosDublê(caso)
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = _colecao_real
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: (
        _RepositorioRespostasDublê(respostas)
    )
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: (
        _RepositorioItensDublê(itens)
    )

    if conta_da_sessao is not None:

        conta = conta_da_sessao

        @aplicacao.post("/_teste/sessao")
        def abrir_sessao(request: Request) -> dict[str, str]:
            # `Request` explícito, não `Any`: é a anotação que faz o FastAPI
            # injetar o objeto real. Com `Any` ele trata o parâmetro como
            # corpo da requisição, a sessão nunca é instalada, e toda rota
            # protegida responde `401` — que foi exatamente o que aconteceu.
            iniciar_sessao_conta(request, conta_id=conta)
            return {"ok": "1"}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    if conta_da_sessao is not None:
        cliente.post("/_teste/sessao")
    return cliente


def _partes(cliente: TestClient) -> list[dict[str, Any]]:
    resposta = cliente.get(f"/caso/{_CASO}/respostas")
    assert resposta.status_code == 200
    partes: list[dict[str, Any]] = resposta.json()["partes"]
    return partes


# ---------------------------------------------------------------------------
# `AC-100` — a revisão mostra pergunta E valor respondido.
# ---------------------------------------------------------------------------


def test_ac100_a_revisao_traz_o_enunciado_e_o_valor_respondido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-100` — nunca só o identificador da pergunta.

    "B1.01 → ESTABELECIDO" não é conferência: o aluno não reconhece nem a
    pergunta nem a resposta. O que ele precisa reler é o que ele leu quando
    respondeu."""
    cliente = _montar_cliente(
        monkeypatch, respostas=(_resposta(_PERGUNTA_B1, _VALOR_B1),)
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 1)
    linha = next(r for r in parte["respondidas"] if r["ID"] == _PERGUNTA_B1)

    assert linha["enunciado"], "a pergunta precisa vir por extenso"
    assert len(linha["enunciado"]) > 20, "enunciado truncado não é conferência"
    assert linha["valores"], "a resposta dada precisa vir"
    # `T-335`: o tipo vai junto, para o cliente exibir `0.08` como "8%".
    assert linha["tipo"] == "SELECAO_UNICA"


def test_ac100_o_valor_vem_como_rotulo_nunca_como_valor_interno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-100` — **a asserção que carrega o requisito.**

    Quem respondeu "Estou disposto(a) a não assumir novas dívidas…" precisa
    reler isso, não `ESTABELECIDO`. O `valor_interno` é vocabulário do modelo
    de dados; devolvê-lo ao aluno seria o mesmo erro que `AC-37` proíbe na
    direção contrária."""
    cliente = _montar_cliente(
        monkeypatch, respostas=(_resposta(_PERGUNTA_B1, _VALOR_B1),)
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 1)
    linha = next(r for r in parte["respondidas"] if r["ID"] == _PERGUNTA_B1)

    assert _VALOR_B1 not in linha["valores"], (
        f"o payload devolveu o valor_interno {_VALOR_B1!r} — o aluno precisa "
        "do rótulo que leu quando respondeu"
    )
    assert len(linha["valores"][0]) > len(_VALOR_B1)


def test_ac100_pergunta_sem_resposta_nao_aparece_na_lista(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A revisão é do que FOI respondido. Listar as 247 perguntas com 244
    vazias transformaria a conferência noutro formulário."""
    cliente = _montar_cliente(
        monkeypatch, respostas=(_resposta(_PERGUNTA_B1, _VALOR_B1),)
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 1)

    assert len(parte["respondidas"]) == 1


# ---------------------------------------------------------------------------
# `AC-101` — parte sem resposta aparece assim mesmo.
# ---------------------------------------------------------------------------


def test_ac101_as_cinco_partes_vem_sempre(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AC-101` — mesmo sem nenhuma resposta gravada.

    Uma parte que some faz o aluno procurar onde ela foi parar; a lista das
    cinco é o mapa, e mapa com buraco não orienta."""
    cliente = _montar_cliente(monkeypatch)

    partes = _partes(cliente)

    assert [p["bloco"] for p in partes] == [1, 2, 3, 4, 5]
    assert all(p["respondidas"] == [] for p in partes)


def test_ac101_a_parte_informa_o_total_de_perguntas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-101` — o total é o que dá tamanho à parte vazia: "0 de 16" diz que
    há trabalho ali; "0" sozinho não diz nada."""
    cliente = _montar_cliente(monkeypatch)

    for parte in _partes(cliente):
        assert parte["total_de_perguntas"] > 0
        assert parte["rotulo"], "a parte precisa de nome em linguagem do aluno"


def test_ac101_o_rotulo_e_do_aluno_nao_do_questionario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os rótulos são os do protótipo validado — "Seu compromisso", não
    "Bloco 1" nem "Pacto da Virada". O aluno não sabe o que é um Bloco 2, e
    não deveria precisar saber."""
    cliente = _montar_cliente(monkeypatch)

    rotulos = [p["rotulo"] for p in _partes(cliente)]

    assert rotulos[0] == "Seu compromisso"
    for rotulo in rotulos:
        assert "Bloco" not in rotulo, f"{rotulo!r} usa vocabulário do questionário"


# ---------------------------------------------------------------------------
# Repetíveis, "não sei" e isolamento.
# ---------------------------------------------------------------------------


def test_pergunta_repetivel_rende_uma_linha_por_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duas dívidas respondendo a mesma pergunta são duas respostas distintas.

    Juntá-las numa linha esconderia qual valor é de qual dívida — e é
    exatamente a confusão que a revisão existe para desfazer."""
    registro = next(
        r
        for r in _colecao_real().registros
        if r.bloco == 5
        and r.escopo_repeticao == EscopoRepeticao.DIVIDA_ID
        and r.VARIAVEL_GRAVADA is not None
    )

    cliente = _montar_cliente(
        monkeypatch,
        respostas=(
            _resposta(registro.ID, "CARTAO", item_id="D001"),
            _resposta(registro.ID, "CARTAO", item_id="D002"),
        ),
        itens=(
            ItemRepetido(
                CASO_ID=_CASO,
                escopo=EscopoRepeticao.DIVIDA_ID,
                item_id="D001",
                criado_em=datetime(2026, 1, 1, tzinfo=UTC),
                removido_em=None,
            ),
            ItemRepetido(
                CASO_ID=_CASO,
                escopo=EscopoRepeticao.DIVIDA_ID,
                item_id="D002",
                criado_em=datetime(2026, 1, 1, tzinfo=UTC),
                removido_em=None,
            ),
        ),
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 5)
    do_registro = [r for r in parte["respondidas"] if r["ID"] == registro.ID]

    assert len(do_registro) == 2
    assert {r["item_id"] for r in do_registro} == {"D001", "D002"}


def test_isolamento_caso_de_outra_conta_responde_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-03` — a rota recebe `CASO_ID` e entra na auditoria de isolamento
    como qualquer outra. Conta que não é dona vê `404`, nunca `403`: a
    existência do caso alheio não vaza."""
    cliente = _montar_cliente(monkeypatch, conta_da_sessao="OUTRA-CONTA")

    assert cliente.get(f"/caso/{_CASO}/respostas").status_code == 404


def test_isolamento_sem_sessao_responde_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem sessão, `401` — antes de qualquer leitura de dado do caso."""
    cliente = _montar_cliente(monkeypatch, conta_da_sessao=None)

    assert cliente.get(f"/caso/{_CASO}/respostas").status_code == 401


# ---------------------------------------------------------------------------
# `T-198` (achado C7) — resposta cuja condição fechou depois de uma correção.
# ---------------------------------------------------------------------------


def test_t198_resposta_cuja_condicao_fechou_nao_quebra_nem_e_listada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`B1.02=SIM` abre `B1.03`; corrigir para `NAO` fecha. A resposta de
    `B1.03` continua gravada, mas a revisão respondia `500` em toda carga —
    e o "‹ Pergunta anterior", que usa a mesma rota, sumia.

    A linha some da revisão (mesma disciplina das fichas); a parte fica."""
    b103 = _resposta("B1.03", "CONSUMO")
    respostas = (_resposta("B1.02", "NAO"), b103)
    cliente = _montar_cliente(monkeypatch, respostas=respostas)

    parte = next(p for p in _partes(cliente) if p["bloco"] == 1)

    assert [r["ID"] for r in parte["respondidas"]] == ["B1.02"]
    assert b103 in _RepositorioRespostasDublê(respostas).listar_do_caso(_CASO)


# ---------------------------------------------------------------------------
# `T-295` — checklist sem nada marcado.
# ---------------------------------------------------------------------------


def test_t295_checklist_sem_item_marcado_e_texto_legivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-100`: `B3.D04` respondida sem marcar nada grava `frozenset()`; a
    revisão mostrava `"[]"` — serialização técnica, não o que o aluno disse."""
    cliente = _montar_cliente(monkeypatch, respostas=(_resposta("B3.D04", frozenset()),))

    parte = next(p for p in _partes(cliente) if p["bloco"] == 3)
    linha = next(r for r in parte["respondidas"] if r["ID"] == "B3.D04")

    assert linha["valores"] == ["Nenhum item marcado."]


# ---------------------------------------------------------------------------
# `T-297` — total por ficha e o Bloco 9 na revisão.
# ---------------------------------------------------------------------------


def _dividas(*item_ids: str) -> tuple[ItemRepetido, ...]:
    return tuple(
        ItemRepetido(
            CASO_ID=_CASO,
            escopo=EscopoRepeticao.DIVIDA_ID,
            item_id=item_id,
            criado_em=datetime(2026, 1, 1, tzinfo=UTC),
            removido_em=None,
        )
        for item_id in item_ids
    )


def test_t297_total_conta_por_ficha_como_as_respondidas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com duas dívidas, cada pergunta da ficha conta duas vezes no total —
    a mesma unidade das respondidas (uma linha por item). Antes o total
    contava registros e a parte dizia "80 respondidas de 63"."""
    cliente = _montar_cliente(monkeypatch, itens=_dividas("D001", "D002"))
    do_bloco_5 = [r for r in _colecao_real().registros if r.bloco == 5]
    de_caso = sum(1 for r in do_bloco_5 if r.escopo_repeticao == EscopoRepeticao.NENHUM)
    de_ficha = len(do_bloco_5) - de_caso

    parte = next(p for p in _partes(cliente) if p["bloco"] == 5)

    assert parte["total_de_perguntas"] == de_caso + 2 * de_ficha


def test_t297_respostas_do_bloco_9_aparecem_na_revisao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-100`: `B9.02`/`B9.04` são respondidas na coleta inicial e sumiam
    da revisão — nenhuma das cinco partes listava o Bloco 9. Ficam em "Seu
    compromisso" (perseverança no plano), sem criar sexta parte (`RF-68`)."""
    cliente = _montar_cliente(
        monkeypatch,
        respostas=(_resposta("B9.02", 7), _resposta("B9.04", "NAO")),
    )

    partes = _partes(cliente)
    ids = [r["ID"] for p in partes for r in p["respondidas"]]

    assert [p["bloco"] for p in partes] == [1, 2, 3, 4, 5]
    assert {"B9.02", "B9.04"} <= set(ids)
    parte_1 = next(p for p in partes if p["bloco"] == 1)
    assert {"B9.02", "B9.04"} <= {r["ID"] for r in parte_1["respondidas"]}


# ---------------------------------------------------------------------------
# `T-303` — opção que abre campo mostra o valor digitado.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("CONFIRMADA", "Sim. — R$ 8.000,00"), ("ESTIMADA", "Aproximadamente. — R$ 8.000,00")],
)
def test_t303_b5_b01_mostra_o_valor_original(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: str
) -> None:
    """Achado no teste ponta a ponta: a revisão mostrava só "Sim."."""
    valor_original = Resposta(
        CASO_ID=_CASO,
        ID_PERGUNTA="VALOR_ORIGINAL",
        item_id="D001",
        valor=Decimal("8000"),
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 3, 1, tzinfo=UTC),
    )
    cliente = _montar_cliente(
        monkeypatch,
        respostas=(_resposta("B5.B01", valor, "D001"), valor_original),
        itens=_dividas("D001"),
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 5)
    linha = next(r for r in parte["respondidas"] if r["ID"] == "B5.B01")

    assert linha["valores"] == [esperado]


def test_t303_data_digitada_aparece_formatada(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente = _montar_cliente(
        monkeypatch,
        respostas=(_resposta("B5.B04", date(2026, 1, 15), "D001"),),
        itens=_dividas("D001"),
    )

    parte = next(p for p in _partes(cliente) if p["bloco"] == 5)
    linha = next(r for r in parte["respondidas"] if r["ID"] == "B5.B04")

    assert linha["valores"] == ["Data (dd/mm/aaaa) — 15/01/2026"]
