"""Testes de `app/http/rotas_inicio.py` — `GET /caso/{CASO_ID}/inicio`
(`RF-58`, `RF-60`, `AC-74`, `AC-81`, `AC-88`, `EC-25`, T-147).

A tela Início lê a fase do caso e devolve **uma** próxima etapa. Este módulo
cobre os cinco compromissos da rota:

1. **`AC-81`** — um caso em cada uma das cinco fases devolve exatamente UMA
   `proxima_etapa`, e a `fase` corresponde ao `ESTADO_CASO` conforme o mapa
   de `RF-61`.
2. **`AC-88`** — na fase `plano`, o valor vem em `valor_em_destaque` como
   **string**, e o `rotulo` NÃO contém o número: nenhum dígito do valor
   aparece no rótulo. A composição da frase é do cliente.
3. **`AC-74`** — a rota aparece na auditoria de isolamento
   (`tests/app_aluno/e2e/test_mecanismo_isolamento.py::
   rotas_sem_isolamento_por_caso`) sem violação; sem sessão ⇒ `401`; caso de
   outra conta ⇒ `404`.
4. **`RF-13`** — todo valor monetário do payload é `str`, nunca `float`/`int`.
   Verificado por varredura recursiva do JSON.
5. **`EC-25`** — `CALCULANDO`, `ERRO_DE_CALCULO` e `ENCERRADO` devolvem
   payload íntegro com mensagem, e o de `ERRO_DE_CALCULO` não contém nenhuma
   palavra técnica de erro.

**Sem banco.** Dublês em memória para casos, respostas, itens e snapshots,
injetados por `app.dependency_overrides` — mesmo mecanismo que a produção usa,
mesmo padrão de `tests/app_aluno/test_rotas_plano.py`, `test_bloco10.py` e
`test_rotas_calculo.py`. Nenhum teste deste módulo toca Postgres nem exige
`DATABASE_URL`.

O `SnapshotOrdem` é REAL — produzido por `calcular_plano` sobre a fixture de
caso completo (T-53) —, com `ATAQUE_IMEDIATO_RECOMENDADO` controlado via
`dataclasses.replace`, exatamente a técnica de `test_bloco10.py`. Nunca um
snapshot fabricado à mão.

REGRAS: `RF-13`, `RF-58`, `RF-60`, `RF-61`, `RF-62`, `AC-74`, `AC-81`,
`AC-88`, `AC-90`, `EC-25`
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime
from functools import cache
from typing import Any, Final

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.fases import FASE_INICIO
from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.mensagens_de_estado import mensagem_do_estado_do_caso
from app.http.rotas_inicio import (
    obter_colecao_de_registros_do_inicio,
    obter_repositorio_itens_do_inicio,
    obter_repositorio_respostas_do_inicio,
)
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.itens import ItemRepetido
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from tests.app_aluno.e2e.test_mecanismo_isolamento import rotas_sem_isolamento_por_caso
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_CHAVE_TESTE: Final[str] = (
    "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
)
_PARAMETROS_VERSAO: Final[str] = "1.0.1"
_CONTA_DONA: Final[str] = "CONTA-INICIO-1"
_CONTA_ALHEIA: Final[str] = "CONTA-INICIO-2"
_CASO_ID: Final[str] = "CASO-INICIO-1"
_CASO_ALHEIO: Final[str] = "CASO-INICIO-ALHEIO"
_DIVIDA_ID: Final[str] = "D001"
_SNAPSHOT_ID_INEXISTENTE: Final[str] = "SNAP-QUE-NUNCA-EXISTIU"

# `EC-25`: nenhuma destas palavras pode aparecer no payload de
# `ERRO_DE_CALCULO`. O aluno endividado não pode agir sobre a falha técnica —
# saber dela só acrescenta medo. A falha é observável pelo operador.
_PALAVRAS_TECNICAS_DE_ERRO: Final[tuple[str, ...]] = (
    "traceback",
    "exception",
    "stack",
    "erro de cálculo",
    "erro de calculo",
    "erro_de_calculo",
    "falha",
    "500",
)

# Chaves do payload cujo valor é monetário — `RF-13`: viajam como `str`,
# nunca como número, porque `JSON.parse` transformaria um número em `double`
# silenciosamente.
_CHAVES_MONETARIAS: Final[frozenset[str]] = frozenset({"valor_em_destaque"})


# ---------------------------------------------------------------------------
# Dublês em memória — nenhum toca banco.
# ---------------------------------------------------------------------------


class _RepositorioCasosDublê:
    """Dublê restrito aos verbos que a rota Início usa: `buscar` e
    `pertence_a_conta`. Mesmo padrão de
    `tests/app_aluno/test_rotas_plano.py::_RepositorioCasosDublê`."""

    def __init__(self, casos: tuple[Caso, ...]) -> None:
        self._casos = {caso.CASO_ID: caso for caso in casos}

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._casos.get(caso_id)

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        caso = self._casos.get(caso_id)
        return caso is not None and caso.conta_id == conta_id

    def transicionar_estado(self, caso_id, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def transicionar_estado_se(self, caso_id, estado_esperado, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_interacao(self, caso_id, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id, snapshot_raiz_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_liberado(self, caso_id, snapshot_liberado_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def listar_por_estado(self, estado):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def listar_todos(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui


class _RepositorioRespostasDublê:
    """As respostas do caso, em memória."""

    def __init__(self, respostas: tuple[Resposta, ...] = ()) -> None:
        self._respostas = respostas

    def gravar(self, resposta):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — a rota só lê

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(r for r in self._respostas if r.CASO_ID == caso_id)

    def buscar(self, caso_id, ID_PERGUNTA, item_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def remover_do_item(self, caso_id, item_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui


class _RepositorioItensDublê:
    """Os itens repetidos ATIVOS do caso, em memória."""

    def __init__(self, itens: tuple[ItemRepetido, ...] = ()) -> None:
        self._itens = itens

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        raise NotImplementedError  # pragma: no cover — a rota só lê

    def remover(self, caso_id, item_id, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — a rota só lê

    def listar_do_caso(
        self, caso_id: str, *, incluir_removidos: bool = True
    ) -> tuple[ItemRepetido, ...]:
        return tuple(
            item
            for item in self._itens
            if item.CASO_ID == caso_id
            and (incluir_removidos or item.removido_em is None)
        )


class _RepositorioSnapshotsDublê:
    """Guarda zero ou um snapshot — `obter` levanta
    `ErroSnapshotNaoEncontrado` para qualquer outro `SNAPSHOT_ID`, mesmo
    contrato do adaptador Postgres real."""

    def __init__(self, snapshot: SnapshotOrdem | None = None) -> None:
        self._snapshot = snapshot

    def anexar(self, s: SnapshotOrdem) -> None:  # pragma: no cover — não usado
        raise NotImplementedError

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        if self._snapshot is None or snapshot_id != self._snapshot.SNAPSHOT_ID:
            raise ErroSnapshotNaoEncontrado(f"sem snapshot {snapshot_id!r}")
        return self._snapshot

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Fixtures de dado — snapshot REAL, caso fabricado.
# ---------------------------------------------------------------------------


@cache
def _colecao_real() -> ColecaoDeRegistros:
    """`@cache` porque `carregar_registros()` reparseia os YAML a cada
    chamada, e vários testes deste módulo a injetam. O valor é imutável."""
    return carregar_registros()


@cache
def _snapshot_base() -> SnapshotOrdem:
    """Um `SnapshotOrdem` REAL, de `calcular_plano` sobre a fixture de caso
    completo (T-53) — mesma técnica de `test_bloco10.py::
    _montar_snapshot_base`. `ATAQUE_IMEDIATO_RECOMENDADO` sai zero deste
    cálculo; quem precisa de valor positivo usa
    `_com_ataque_imediato_recomendado`."""
    caso = caso_completo(DIVIDA_ID=_DIVIDA_ID)
    divida = montar_divida(caso.respostas, _DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def _com_ataque_imediato_recomendado(valor: str) -> SnapshotOrdem:
    """`ATAQUE_IMEDIATO_RECOMENDADO` controlado via `dataclasses.replace` —
    mesma técnica de `test_bloco10.py`, sem precisar montar um cenário
    completo de gates só para obter um valor positivo."""
    snapshot = _snapshot_base()
    diagnostico = dataclasses.replace(
        snapshot.diagnostico, ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(valor)
    )
    return dataclasses.replace(snapshot, diagnostico=diagnostico)


def _caso(
    estado: ESTADO_CASO,
    *,
    CASO_ID: str = _CASO_ID,
    conta_id: str = _CONTA_DONA,
    snapshot_liberado_id: str | None = None,
) -> Caso:
    return Caso(
        CASO_ID=CASO_ID,
        conta_id=conta_id,
        estado=estado,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot_liberado_id,
        snapshot_liberado_id=snapshot_liberado_id,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    casos: tuple[Caso, ...],
    respostas: tuple[Resposta, ...] = (),
    itens: tuple[ItemRepetido, ...] = (),
    snapshot: SnapshotOrdem | None = None,
    conta_da_sessao: str | None = _CONTA_DONA,
) -> TestClient:
    """A aplicação real, com os quatro pontos de injeção sobrescritos —
    `app.dependency_overrides`, o MESMO mecanismo da produção. Sem
    `DATABASE_URL`.

    `conta_da_sessao=None` deixa a requisição sem sessão, para o caminho de
    `401`."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = (
        lambda: _RepositorioCasosDublê(casos)
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros_do_inicio] = (
        _colecao_real
    )
    aplicacao.dependency_overrides[obter_repositorio_respostas_do_inicio] = (
        lambda: _RepositorioRespostasDublê(respostas)
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_do_inicio] = (
        lambda: _RepositorioItensDublê(itens)
    )
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = (
        lambda: _RepositorioSnapshotsDublê(snapshot)
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    if conta_da_sessao is not None:
        cliente.post(f"/_teste/abrir-sessao/{conta_da_sessao}")
    return cliente


def _payload_da_fase(
    monkeypatch: pytest.MonkeyPatch,
    estado: ESTADO_CASO,
    *,
    ataque_recomendado: str | None = None,
) -> dict[str, Any]:
    """`GET /caso/{CASO_ID}/inicio` para um caso no `estado` dado.

    `ataque_recomendado` presente ⇒ o caso tem snapshot LIBERADO com aquele
    `ATAQUE_IMEDIATO_RECOMENDADO`. Ausente ⇒ nenhum snapshot liberado."""
    snapshot = (
        _com_ataque_imediato_recomendado(ataque_recomendado)
        if ataque_recomendado is not None
        else None
    )
    caso = _caso(
        estado,
        snapshot_liberado_id=snapshot.SNAPSHOT_ID if snapshot is not None else None,
    )
    cliente = _montar_cliente(monkeypatch, casos=(caso,), snapshot=snapshot)

    resposta = cliente.get(f"/caso/{_CASO_ID}/inicio")

    assert resposta.status_code == 200, resposta.text
    payload: dict[str, Any] = resposta.json()
    return payload


def _percorrer_valores(no: object, caminho: str = "") -> list[tuple[str, object]]:
    """Achata o JSON em pares `(caminho, valor)` — toda folha, em qualquer
    profundidade. É o que permite afirmar sobre o payload INTEIRO em vez de
    sobre as chaves que alguém lembrou de listar."""
    if isinstance(no, dict):
        folhas: list[tuple[str, object]] = []
        for chave, valor in no.items():
            folhas.extend(_percorrer_valores(valor, f"{caminho}.{chave}"))
        return folhas
    if isinstance(no, list):
        folhas = []
        for indice, valor in enumerate(no):
            folhas.extend(_percorrer_valores(valor, f"{caminho}[{indice}]"))
        return folhas
    return [(caminho, no)]


# ---------------------------------------------------------------------------
# `AC-81` — uma fase, uma próxima etapa.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "fase_esperada", "ataque_recomendado"),
    [
        (ESTADO_CASO.COLETA_INICIAL, FASE_INICIO.COLETA, None),
        (ESTADO_CASO.AGUARDANDO_REVISAO, FASE_INICIO.REVISAO, None),
        (ESTADO_CASO.REPROVADO_EM_REVISAO, FASE_INICIO.REPROVADO, None),
        (ESTADO_CASO.PLANO_LIBERADO, FASE_INICIO.PLANO, "3000.00"),
        (ESTADO_CASO.ACOMPANHAMENTO, FASE_INICIO.ACOMPANHAMENTO, None),
    ],
)
def test_ac81_cada_fase_devolve_uma_unica_proxima_etapa(
    monkeypatch: pytest.MonkeyPatch,
    estado: ESTADO_CASO,
    fase_esperada: FASE_INICIO,
    ataque_recomendado: str | None,
) -> None:
    """`AC-81` — as cinco fases, uma a uma: a `fase` devolvida corresponde ao
    `ESTADO_CASO` conforme o mapa de `RF-61`, e `proxima_etapa` é UM objeto
    com UM destino — nunca uma lista, nunca duas opções.

    Oferecer duas já seria pedir ao aluno que escolhesse, que é exatamente o
    que a barra de sete abas fazia."""
    payload = _payload_da_fase(
        monkeypatch, estado, ataque_recomendado=ataque_recomendado
    )

    assert payload["fase"] == fase_esperada.value
    assert payload["estado"] == estado.value

    etapa = payload["proxima_etapa"]
    assert isinstance(etapa, dict)
    assert etapa["destino"]


def test_ac81_as_cinco_fases_sao_alcancaveis_pela_rota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-81` — o conjunto de fases que a rota de fato produz é EXATAMENTE
    as cinco de `FASE_INICIO`. Nenhuma fase é inalcançável (o que seria
    código morto) e nenhuma fase inventada aparece."""
    fases_observadas = {
        _payload_da_fase(monkeypatch, ESTADO_CASO.COLETA_INICIAL)["fase"],
        _payload_da_fase(monkeypatch, ESTADO_CASO.AGUARDANDO_REVISAO)["fase"],
        _payload_da_fase(monkeypatch, ESTADO_CASO.REPROVADO_EM_REVISAO)["fase"],
        _payload_da_fase(
            monkeypatch, ESTADO_CASO.PLANO_LIBERADO, ataque_recomendado="3000.00"
        )["fase"],
        _payload_da_fase(monkeypatch, ESTADO_CASO.ACOMPANHAMENTO)["fase"],
    }

    assert fases_observadas == {fase.value for fase in FASE_INICIO}


def test_ac81_cadastrado_aponta_para_o_consentimento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-81` — `CADASTRADO` é fase `coleta`, mas a próxima etapa é o
    consentimento: nenhuma resposta pode ser gravada antes dele (`RF-30`)."""
    payload = _payload_da_fase(monkeypatch, ESTADO_CASO.CADASTRADO)

    assert payload["fase"] == FASE_INICIO.COLETA.value
    assert payload["proxima_etapa"]["destino"] == "consentimento"


def test_ac81_coleta_em_andamento_aponta_para_a_pergunta_exata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-81` + `AC-01` — na coleta, a próxima etapa carrega o
    `ID_PERGUNTA` de onde o aluno parou, vindo da MESMA função da retomada.
    Sem nenhuma resposta gravada, é a primeira pergunta do primeiro bloco."""
    payload = _payload_da_fase(monkeypatch, ESTADO_CASO.COLETA_INICIAL)

    etapa = payload["proxima_etapa"]
    assert etapa["destino"] == "pergunta"
    assert etapa["ID_PERGUNTA"] == "B1.01"


def test_ac90_progresso_fecha_o_invariante_na_resposta_da_rota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-90` — o payload traz `respondidas` e `total`, e o que falta é a
    diferença entre os dois: `respondidas + faltam == total` sobrevive à
    fronteira HTTP.

    Com duas dívidas ativas, o total cresce em relação a nenhuma — a ficha
    repetida é trabalho real do aluno, e a barra o conta."""
    caso = _caso(ESTADO_CASO.COLETA_INICIAL)
    itens = tuple(
        ItemRepetido(
            item_id=item_id,
            CASO_ID=_CASO_ID,
            escopo=EscopoRepeticao.DIVIDA_ID,
            removido_em=None,
            criado_em=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for item_id in ("D001", "D002")
    )

    sem_itens = _montar_cliente(monkeypatch, casos=(caso,)).get(
        f"/caso/{_CASO_ID}/inicio"
    )
    com_itens = _montar_cliente(monkeypatch, casos=(caso,), itens=itens).get(
        f"/caso/{_CASO_ID}/inicio"
    )

    progresso_sem = sem_itens.json()["progresso"]
    progresso_com = com_itens.json()["progresso"]

    assert progresso_sem["respondidas"] == 0
    assert progresso_sem["total"] > 0
    assert progresso_com["total"] > progresso_sem["total"]
    assert progresso_com["respondidas"] <= progresso_com["total"]


# ---------------------------------------------------------------------------
# `AC-88` — o número nunca entra na frase.
# ---------------------------------------------------------------------------


def test_ac88_valor_em_destaque_e_string_e_o_rotulo_nao_tem_o_numero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-88` — na fase `plano`, `valor_em_destaque` é **string**, e o
    servidor não manda frase nenhuma em que o número pudesse ter entrado.

    A trava é estrutural, e é mais forte que procurar o número num rótulo: o
    payload de `proxima_etapa` **não tem campo de texto**. O servidor manda o
    `destino` (dado estrutural) e o valor separado; quem compõe a frase é o
    cliente (`RF-13` + Lei nº 3 + `AC-37`, que proíbe redação longa no código
    da aplicação). Sem campo de texto, não há onde interpolar."""
    payload = _payload_da_fase(
        monkeypatch, ESTADO_CASO.PLANO_LIBERADO, ataque_recomendado="3000.00"
    )

    assert payload["fase"] == FASE_INICIO.PLANO.value

    valor = payload["valor_em_destaque"]
    assert isinstance(valor, str), f"valor_em_destaque veio como {type(valor)!r}"
    assert valor

    etapa = payload["proxima_etapa"]
    assert set(etapa) == {"destino", "ID_PERGUNTA", "item_id"}, (
        f"proxima_etapa ganhou campo além do destino: {sorted(etapa)} — "
        "campo de texto aqui é onde o número voltaria a entrar na frase "
        "(AC-88), e redação no código da aplicação viola AC-37"
    )

    # `destino` é identificador estrutural (`"bloco10"`), não frase: um
    # dígito nele é parte do nome da tela. O que não pode existir é campo de
    # FRASE — e a asserção de forma acima é o que garante isso. Aqui só se
    # confirma que nenhum campo carrega o valor formatado nem sinal de moeda.
    for chave, conteudo in etapa.items():
        if not isinstance(conteudo, str):
            continue
        assert valor not in conteudo, (
            f"proxima_etapa[{chave!r}] = {conteudo!r} carrega o valor "
            f"{valor!r} — o número não entra em campo de texto do servidor"
        )
        assert "R$" not in conteudo


def test_ac88_valor_em_destaque_e_nulo_fora_da_fase_plano(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-88` — fora da fase `plano` não há decisão de dinheiro pendente, e
    `valor_em_destaque` é `null`: mandar um número que a tela não usa
    convidaria alguém a compor uma frase com ele."""
    for estado in (
        ESTADO_CASO.COLETA_INICIAL,
        ESTADO_CASO.AGUARDANDO_REVISAO,
        ESTADO_CASO.ACOMPANHAMENTO,
    ):
        payload = _payload_da_fase(monkeypatch, estado)

        assert payload["valor_em_destaque"] is None, estado.name


def test_rf13_todo_valor_monetario_do_payload_e_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RF-13` — varredura RECURSIVA do JSON: nenhuma folha sob uma chave
    monetária é `float` ou `int`.

    `JSON.parse` transformaria um número em `double` silenciosamente, e o
    centavo se perderia sem que nada falhasse. A varredura é recursiva para
    que um campo monetário acrescentado amanhã dentro de `proxima_etapa` (ou
    de qualquer objeto novo) também seja pego."""
    payload = _payload_da_fase(
        monkeypatch, ESTADO_CASO.PLANO_LIBERADO, ataque_recomendado="3000.00"
    )

    for caminho, valor in _percorrer_valores(payload):
        chave = caminho.rsplit(".", 1)[-1]
        if chave in _CHAVES_MONETARIAS and valor is not None:
            assert isinstance(valor, str), (
                f"{caminho} veio como {type(valor).__name__} — todo valor "
                "monetário viaja como string (RF-13)"
            )
            assert not isinstance(valor, bool)


def test_rf13_nenhuma_folha_do_payload_e_float(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RF-13` — reforço pelo lado oposto: NENHUMA folha do payload é
    `float`, em nenhum caminho. Um `float` no payload desta rota só poderia
    ser dinheiro (os demais campos são texto, booleano ou contagem
    inteira)."""
    payload = _payload_da_fase(
        monkeypatch, ESTADO_CASO.PLANO_LIBERADO, ataque_recomendado="3000.00"
    )

    floats = [
        (caminho, valor)
        for caminho, valor in _percorrer_valores(payload)
        if isinstance(valor, float)
    ]

    assert floats == []


def test_plano_liberado_sem_ataque_recomendado_cai_em_acompanhamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RF-61` — `PLANO_LIBERADO` com `ATAQUE_IMEDIATO_RECOMENDADO = 0` é
    fase `acompanhamento`, **não** `plano`: sem ataque a decidir não há
    decisão nenhuma, e "Decidir agora" mandaria o aluno a uma tela que o
    servidor fecha com `409`.

    A guarda é `bloco_10_alcancavel`, a mesma de `rotas_etapas.py` — nenhum
    limiar reescrito aqui."""
    payload = _payload_da_fase(
        monkeypatch, ESTADO_CASO.PLANO_LIBERADO, ataque_recomendado="0"
    )

    assert payload["estado"] == ESTADO_CASO.PLANO_LIBERADO.value
    assert payload["fase"] == FASE_INICIO.ACOMPANHAMENTO.value
    assert payload["valor_em_destaque"] is None
    assert payload["proxima_etapa"]["destino"] != "bloco10"


def test_plano_liberado_sem_snapshot_encontrado_cai_em_acompanhamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tolerância declarada: `snapshot_liberado_id` que o repositório não
    encontra não derruba a tela. A ausência de snapshot é estado legítimo do
    caso, não falha — e sem snapshot não há o que decidir."""
    caso = _caso(
        ESTADO_CASO.PLANO_LIBERADO, snapshot_liberado_id=_SNAPSHOT_ID_INEXISTENTE
    )
    cliente = _montar_cliente(monkeypatch, casos=(caso,), snapshot=None)

    resposta = cliente.get(f"/caso/{_CASO_ID}/inicio")

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["fase"] == FASE_INICIO.ACOMPANHAMENTO.value
    assert payload["versao_do_plano"] is None


# ---------------------------------------------------------------------------
# `AC-74` — isolamento por caso.
# ---------------------------------------------------------------------------


def test_ac74_rota_inicio_aparece_na_auditoria_de_isolamento_sem_violacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-74` — a auditoria de `test_mecanismo_isolamento.py` enumera as
    `APIRoute` REGISTRADAS e reconhece o par `CASO_ID` + subdependência de
    `app.http.isolamento`. A rota Início declara `CASO_ID` no path, então
    precisa de `exigir_caso_da_sessao` — e a auditoria não a lista como
    violação.

    A rota é procurada na aplicação real por seu `path`: se ela deixasse de
    ser registrada, o teste falharia por ausência, não por engano."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    caminhos_registrados = {
        getattr(rota, "path", None) for rota in aplicacao.routes
    } | {
        getattr(sub, "path", None)
        for rota in aplicacao.routes
        for sub in getattr(
            getattr(rota, "original_router", None), "routes", ()
        )
    }
    assert "/caso/{CASO_ID}/inicio" in caminhos_registrados

    assert "/caso/{CASO_ID}/inicio" not in rotas_sem_isolamento_por_caso(aplicacao)


def test_ac74_sem_sessao_responde_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AC-74` — sem sessão, a requisição é recusada com `401` antes de
    qualquer leitura de dado do caso."""
    cliente = _montar_cliente(
        monkeypatch,
        casos=(_caso(ESTADO_CASO.COLETA_INICIAL),),
        conta_da_sessao=None,
    )

    resposta = cliente.get(f"/caso/{_CASO_ID}/inicio")

    assert resposta.status_code == 401


def test_ac74_caso_de_outra_conta_responde_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-74` — caso que existe, mas pertence a outra conta: `404`, nunca
    `403` e nunca `200`. A existência do caso não vaza."""
    casos = (
        _caso(ESTADO_CASO.COLETA_INICIAL),
        _caso(
            ESTADO_CASO.COLETA_INICIAL,
            CASO_ID=_CASO_ALHEIO,
            conta_id=_CONTA_ALHEIA,
        ),
    )
    cliente = _montar_cliente(monkeypatch, casos=casos)

    resposta = cliente.get(f"/caso/{_CASO_ALHEIO}/inicio")

    assert resposta.status_code == 404


def test_ac74_caso_inexistente_responde_404_identico_ao_de_outra_conta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-74` — "caso de outra conta" e "caso que nunca existiu" produzem a
    MESMA resposta, byte a byte: a interface não deixa inferir quais casos
    existem."""
    casos = (
        _caso(ESTADO_CASO.COLETA_INICIAL),
        _caso(
            ESTADO_CASO.COLETA_INICIAL,
            CASO_ID=_CASO_ALHEIO,
            conta_id=_CONTA_ALHEIA,
        ),
    )
    cliente = _montar_cliente(monkeypatch, casos=casos)

    de_outra_conta = cliente.get(f"/caso/{_CASO_ALHEIO}/inicio")
    inexistente = cliente.get("/caso/CASO-QUE-NUNCA-EXISTIU/inicio")

    assert de_outra_conta.status_code == inexistente.status_code == 404
    assert de_outra_conta.text == inexistente.text


def test_ac74_caso_da_propria_conta_e_aceito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contraprova de `AC-74`: o dono do caso é atendido com `200` e recebe o
    seu próprio `CASO_ID` de volta."""
    cliente = _montar_cliente(monkeypatch, casos=(_caso(ESTADO_CASO.COLETA_INICIAL),))

    resposta = cliente.get(f"/caso/{_CASO_ID}/inicio")

    assert resposta.status_code == 200
    assert resposta.json()["CASO_ID"] == _CASO_ID


# ---------------------------------------------------------------------------
# `EC-25` — estado sem etapa óbvia: payload íntegro, erro técnico invisível.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "fase_esperada"),
    [
        (ESTADO_CASO.CALCULANDO, FASE_INICIO.REVISAO),
        (ESTADO_CASO.ERRO_DE_CALCULO, FASE_INICIO.REVISAO),
        (ESTADO_CASO.ENCERRADO, FASE_INICIO.ACOMPANHAMENTO),
    ],
)
def test_ec25_estado_sem_etapa_obvia_devolve_payload_integro_com_mensagem(
    monkeypatch: pytest.MonkeyPatch,
    estado: ESTADO_CASO,
    fase_esperada: FASE_INICIO,
) -> None:
    """`EC-25` — a tela Início mostra **o estado e o que esperar**, nunca uma
    tela vazia nem uma etapa inventada. O payload traz fase, mensagem e uma
    próxima etapa completa nos três estados."""
    payload = _payload_da_fase(monkeypatch, estado)

    assert payload["fase"] == fase_esperada.value
    assert payload["mensagem"] == mensagem_do_estado_do_caso(estado)
    assert payload["mensagem"]

    etapa = payload["proxima_etapa"]
    assert etapa["destino"]
    assert etapa["destino"]
    assert payload["progresso"]["total"] >= 0


def test_ec25_erro_de_calculo_nao_expoe_nenhuma_palavra_tecnica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-25` — o erro técnico **jamais** chega ao aluno.

    O payload inteiro de `ERRO_DE_CALCULO` (texto de todas as folhas, em
    minúsculas) não contém "traceback", "exception", "falha" nem "erro de
    cálculo" cru. A mensagem é a que `mensagens_de_estado.py` já produz:
    *"Seu plano está em nova análise."* — verdade, e acionável para quem pode
    agir (a equipe).

    O `estado` bruto (`ERRO_DE_CALCULO`) continua no payload porque é o
    identificador da máquina, não prosa exibida: a varredura ignora esse
    campo de propósito, e é a `mensagem` que o aluno lê."""
    payload = _payload_da_fase(monkeypatch, ESTADO_CASO.ERRO_DE_CALCULO)

    assert payload["mensagem"] == "Seu plano está em nova análise."

    textos_exibidos = " ".join(
        valor
        for caminho, valor in _percorrer_valores(payload)
        if isinstance(valor, str) and not caminho.endswith(".estado")
    ).lower()

    for palavra in _PALAVRAS_TECNICAS_DE_ERRO:
        assert palavra not in textos_exibidos, (
            f"a palavra técnica {palavra!r} apareceu no texto exibido ao "
            "aluno (EC-25)"
        )


def test_ec25_erro_de_calculo_e_calculando_tem_a_mesma_fase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-25` — *"é com a gente, você não faz nada"* é a mesma resposta nos
    dois estados, então a **fase** é a mesma. O que muda é só o destino: quem
    está calculando vê a tela do `.pulse`; quem caiu em erro vê a espera, sem
    animação de progresso que mentiria sobre haver progresso.

    É a distinção que importa: mesma fase (o aluno não age), destinos
    diferentes (a tela diz a verdade sobre o que está acontecendo)."""
    calculando = _payload_da_fase(monkeypatch, ESTADO_CASO.CALCULANDO)
    com_erro = _payload_da_fase(monkeypatch, ESTADO_CASO.ERRO_DE_CALCULO)

    assert calculando["fase"] == com_erro["fase"] == FASE_INICIO.REVISAO.value

    assert calculando["proxima_etapa"]["destino"] == "calculando"
    assert com_erro["proxima_etapa"]["destino"] == "aguardando"

    # A mensagem do erro é a que `mensagens_de_estado.py` já produz, e ela
    # não denuncia falha técnica — `EC-25` é explícito: o aluno não pode agir
    # sobre o erro, e saber dele só acrescenta medo.
    assert com_erro["mensagem"] == "Seu plano está em nova análise."


def test_ec25_encerrado_mostra_o_cartao_de_acompanhamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EC-25` — `ENCERRADO` não é uma sexta fase: é `acompanhamento`, com a
    mensagem de encerramento que `mensagens_de_estado.py` já produz."""
    payload = _payload_da_fase(monkeypatch, ESTADO_CASO.ENCERRADO)

    assert payload["fase"] == FASE_INICIO.ACOMPANHAMENTO.value
    assert payload["mensagem"] == "Seu caso foi encerrado."


def test_mensagem_do_payload_e_sempre_a_de_mensagens_de_estado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rota REUSA `mensagem_do_estado_do_caso` — não reescreve redação
    nenhuma. Verificado nos doze estados possíveis do caso, enumerados a
    partir do enum."""
    for estado in ESTADO_CASO:
        payload = _payload_da_fase(monkeypatch, estado)

        assert payload["mensagem"] == mensagem_do_estado_do_caso(estado), estado.name
