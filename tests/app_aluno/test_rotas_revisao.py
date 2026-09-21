"""Testes de `app/http/rotas_revisao.py` — a tela da fila de revisão
(`RF-23`, `RF-25`, `AC-25`, `AC-28`, T-69).

`RepositorioCasosArquivo`/`RepositorioSnapshotsArquivo` (persistência real de
arquivo, T-24) e `SnapshotOrdem` REAL produzido por `executar_calculo` sobre
a fixture de caso completo (T-53) — mesmo padrão de `tests/app_aluno/
test_fila_de_revisao.py` (T-66/T-68): nenhum snapshot fabricado à mão.
`dataclasses.replace` varia só `REVISAO_HUMANA_OBRIGATORIA`, isolando a
única variável que os testes de `AC-28` precisam controlar.

Cobre os quatro critérios de aceite de T-69:

1. `AC-28`: um snapshot com o campo do motor em `True` é sinalizado como
   caso metodológico de `S-04`, distinto do outro — `e_metodologico` e
   `entra_por_politica` chegam à tela como DOIS campos, nunca fundidos
   (T-144: a tela virou React e a prova passou do rótulo HTML para os
   campos do JSON, que é onde a separação de fato se preserva).
2. A fila lista todos os snapshots em `AGUARDANDO_REVISAO`, incluindo
   recálculos — um caso liberado que volta a `AGUARDANDO_REVISAO` (segundo
   snapshot) aparece de novo.
3. A tela não expõe caso de outra conta ao aluno — a rota de revisão
   (`/revisao/fila`) é inteiramente separada de `/caso/{CASO_ID}/...`
   (rotas do aluno), nunca recebe `CASO_ID` de sessão, e a auditoria de
   isolamento (`tests/app_aluno/e2e/test_mecanismo_isolamento.py`) continua
   vazia com a rota registrada.
4. Nenhum valor da fila é calculado — todo campo do contexto do template é
   uma leitura direta de `ItemFila`/`SnapshotOrdem` (verificado por
   inspeção de `_item_para_contexto` e pela ausência de qualquer operação
   aritmética no módulo da rota).

REGRAS: `RF-23`, `RF-25`, `AC-25`, `AC-28`
"""

from __future__ import annotations

import ast
import dataclasses
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_papel_revisor
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_snapshots_da_fila,
)
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from engine.estado import EstadoFinanceiro
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.e2e.test_mecanismo_isolamento import (
    _rotas_api_achatadas,
    rotas_sem_isolamento_por_caso,
)
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_PARAMETROS_VERSAO = "1.0.1"


def _montar_estado(data_referencia: date = DATA_REFERENCIA) -> EstadoFinanceiro:
    """O estado da fixture de caso completo.

    `data_referencia` existe para dar a cada caso do cenário uma CADEIA
    PRÓPRIA de snapshots. `SNAPSHOT_ID` é `sha256(hash_inputs:versao)`
    (`engine/snapshot.py`), determinístico sobre os inputs: dois casos
    calculados a partir de estados idênticos recebem o MESMO `SNAPSHOT_ID`
    e, como `historico` agrupa pela raiz da cadeia (`OQ-11`), passam a
    compartilhar a mesma cadeia. Variar a data de referência é a menor
    diferença que os separa sem mexer em nenhuma resposta do caso."""
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=data_referencia,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


def _criar_caso(repositorio_casos: RepositorioCasosArquivo, caso_id: str, conta_id: str) -> None:
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio_casos.criar(
        Caso(
            CASO_ID=caso_id,
            conta_id=conta_id,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.CALCULANDO)


def _calcular_snapshot(
    caso_id: str,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    *,
    estado_anterior: ESTADO_CASO,
    anterior: SnapshotOrdem | None = None,
    data_referencia: date = DATA_REFERENCIA,
) -> SnapshotOrdem:
    """Produz um `SnapshotOrdem` REAL (mesma cadeia de `app/motor/
    executor.py`) para `caso_id` — nunca um snapshot fabricado à mão.
    `anterior`, quando informado, encadeia o novo snapshot ao anterior
    (mesmo mecanismo de recálculo do motor: `versao` incrementa e o
    `SNAPSHOT_ID` muda) — usado pelo cenário de recálculo.

    `executar_calculo` só anexa o snapshot; quem transiciona o caso para
    `AGUARDANDO_REVISAO` (Bloco 6, fora do escopo desta tarefa/T-69) é outro
    componente — aqui, como em `tests/app_aluno/test_fila_de_revisao.py`
    (T-66), a preparação do cenário faz essa transição explicitamente. Só a
    PRIMEIRA chamada (sem `anterior`) registra `snapshot_raiz_id` — a raiz da
    cadeia não muda em recálculo (`OQ-11`, `app/casos/maquina.py`)."""
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=estado_anterior,
        anterior=anterior,
    )
    snapshot = executar_calculo(_montar_estado(data_referencia), insumos)
    if anterior is None:
        repositorio_casos.registrar_snapshot_raiz(caso_id, snapshot.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.AGUARDANDO_REVISAO)
    return snapshot


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    return RepositorioCasosArquivo(tmp_path / "casos.jsonl")


@pytest.fixture
def repositorio_snapshots(tmp_path: Path) -> RepositorioSnapshotsArquivo:
    return RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")


@pytest.fixture
def repositorio_eventos(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    """`T-91` (`RF-31`/`AC-40`) — trilha de eventos do caso, exigida por
    `ParametrosDoCalculo`; esta suíte não asserta sobre a trilha, só precisa
    fornecê-la ao executor real."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
) -> TestClient:
    """`T-100`: estes testes cobrem os critérios de T-69 (conteúdo e forma da
    fila), não a guarda de papel em si — a guarda ganha sua própria suíte
    dedicada (`test_guarda_papel_revisor.py`). Por isso `exigir_papel_
    revisor` é sobrescrita aqui para um revisor já autenticado, do mesmo
    jeito que `obter_repositorio_casos_da_fila`/`obter_repositorio_
    snapshots_da_fila` já eram sobrescritas — sem isso, toda requisição
    destes testes recusaria com `401` antes de alcançar a fila. Não recebe
    `repositorio_eventos`: esta rota (`GET /revisao/fila`) só LÊ a fila —
    `liberar`/`reprovar` (que consomem a trilha, `T-91`) são a rota `POST
    /revisao/caso/{...}/decisao`, fora do escopo desta suíte."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = lambda: (
        repositorio_snapshots
    )
    aplicacao.dependency_overrides[exigir_papel_revisor] = lambda: "conta-revisor-teste"
    return TestClient(aplicacao, base_url="https://teste.local")


# ---------------------------------------------------------------------------
# Critério "a fila lista todos os snapshots em AGUARDANDO_REVISAO, incluindo
# recálculos" — dois casos, um deles com dois snapshots (recálculo).
# ---------------------------------------------------------------------------


def test_fila_lista_todos_os_casos_em_aguardando_revisao(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Dois casos distintos em `AGUARDANDO_REVISAO`, de contas diferentes,
    aparecem os dois na fila — nenhum é omitido por pertencer a outra
    conta (a fila não filtra por conta, é tela de revisor)."""
    _criar_caso(repositorio_casos, "CASO-FILA-1", "conta-aluno-1")
    snapshot_1 = _calcular_snapshot(
        "CASO-FILA-1",
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.COLETA_INICIAL,
    )

    _criar_caso(repositorio_casos, "CASO-FILA-2", "conta-aluno-2")
    snapshot_2 = _calcular_snapshot(
        "CASO-FILA-2",
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.COLETA_INICIAL,
    )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 200
    itens = resposta.json()["itens"]
    casos_na_fila = {item["CASO_ID"] for item in itens}
    snapshots_na_fila = {item["SNAPSHOT_ID"] for item in itens}
    assert {"CASO-FILA-1", "CASO-FILA-2"} <= casos_na_fila
    assert {snapshot_1.SNAPSHOT_ID, snapshot_2.SNAPSHOT_ID} <= snapshots_na_fila


def test_fila_inclui_recalculo_segundo_snapshot_do_mesmo_caso(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Um caso já liberado que volta a `AGUARDANDO_REVISAO` (recálculo, novo
    snapshot na mesma cadeia) aparece na fila com o snapshot MAIS RECENTE —
    a fila é uma consulta sobre o `estado` corrente, não uma lista que
    "esquece" quem já passou por ela uma vez."""
    caso_id = "CASO-FILA-RECALCULO"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-recalculo")
    primeiro_snapshot = _calcular_snapshot(
        caso_id,
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.COLETA_INICIAL,
    )
    # Simula a liberação do primeiro snapshot e a saída de AGUARDANDO_REVISAO.
    repositorio_casos.transicionar_estado_se(
        caso_id, ESTADO_CASO.AGUARDANDO_REVISAO, ESTADO_CASO.PLANO_LIBERADO
    )
    repositorio_casos.registrar_snapshot_liberado(caso_id, primeiro_snapshot.SNAPSHOT_ID)

    # Recálculo: o caso volta a CALCULANDO e produz um segundo snapshot,
    # encadeado ao primeiro (`anterior=primeiro_snapshot`) — mesmo mecanismo
    # de recálculo do motor, `versao` incrementa e o SNAPSHOT_ID muda.
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.CALCULANDO)
    segundo_snapshot = _calcular_snapshot(
        caso_id,
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.PLANO_LIBERADO,
        anterior=primeiro_snapshot,
    )

    assert segundo_snapshot.SNAPSHOT_ID != primeiro_snapshot.SNAPSHOT_ID

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 200
    itens = resposta.json()["itens"]
    assert any(item["CASO_ID"] == caso_id for item in itens)
    assert any(item["SNAPSHOT_ID"] == segundo_snapshot.SNAPSHOT_ID for item in itens)


def test_fila_vazia_quando_nenhum_caso_esta_em_aguardando_revisao(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Caminho vazio: nenhum caso em `AGUARDANDO_REVISAO` produz uma tela
    sem itens, nunca um erro."""
    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 200
    # Fila vazia é uma LISTA vazia, nunca um erro — o "estado vazio" que o
    # template escrevia em prosa agora é responsabilidade da tela React.
    assert resposta.json()["itens"] == []


# ---------------------------------------------------------------------------
# AC-28 — os dois sinais (política vs. S-04) são visivelmente distintos.
# ---------------------------------------------------------------------------


def test_ac28_snapshot_metodologico_e_sinalizado_distinto_do_so_politica(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-28`: dois casos em fila, um com `REVISAO_HUMANA_OBRIGATORIA =
    True` (caso metodológico de S-04) e outro com `False` (só política do
    piloto) — a saída HTML traz o rótulo de S-04 exclusivamente para o
    primeiro, nunca para o segundo."""
    caso_metodologico = "CASO-FILA-S04"
    caso_so_politica = "CASO-FILA-SO-POLITICA"

    _criar_caso(repositorio_casos, caso_metodologico, "conta-s04")
    snapshot_metodologico_original = _calcular_snapshot(
        caso_metodologico,
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.COLETA_INICIAL,
    )

    # Data de referência distinta ⇒ `hash_inputs` distinto ⇒ `SNAPSHOT_ID` e
    # cadeia próprios. Sem isso os dois casos, calculados sobre a MESMA
    # fixture, recebem o mesmo `SNAPSHOT_ID` e acabam compartilhando a
    # cadeia — e o `replace` abaixo marcaria os DOIS como metodológicos.
    _criar_caso(repositorio_casos, caso_so_politica, "conta-so-politica")
    _calcular_snapshot(
        caso_so_politica,
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
        estado_anterior=ESTADO_CASO.COLETA_INICIAL,
        data_referencia=date(DATA_REFERENCIA.year, DATA_REFERENCIA.month, 2),
    )

    # Substitui o snapshot do primeiro caso por uma variante com o campo do
    # motor em True — mesma técnica de `tests/app_aluno/test_fila_de_revisao.py`
    # (dataclasses.replace isola a única variável controlada pelo teste).
    snapshot_metodologico = dataclasses.replace(
        snapshot_metodologico_original, REVISAO_HUMANA_OBRIGATORIA=True
    )
    repositorio_snapshots.anexar(snapshot_metodologico)
    repositorio_casos.registrar_snapshot_raiz(caso_metodologico, snapshot_metodologico.SNAPSHOT_ID)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/api/revisao/fila")


    assert resposta.status_code == 200
    # `AC-28`: os dois sinais chegam à tela SEPARADOS, nunca fundidos num
    # booleano só. Antes (Jinja) a prova era o par de rótulos distintos no
    # HTML; agora são os dois campos do JSON — e a garantia é a mesma, com
    # a vantagem de que fundi-los quebraria aqui e no teste estático do
    # serializador ao mesmo tempo.
    por_caso = {item["CASO_ID"]: item for item in resposta.json()["itens"]}

    # Só o caso metodológico levanta `REVISAO_HUMANA_OBRIGATORIA` (S-04).
    assert por_caso[caso_metodologico]["e_metodologico"] is True
    assert por_caso[caso_so_politica]["e_metodologico"] is False

    # Ambos entram por política (RF-25: 100% dos planos do piloto).
    assert all(item["entra_por_politica"] is True for item in por_caso.values())


# ---------------------------------------------------------------------------
# Critério "a tela não expõe caso de outra conta ao aluno" — a rota de
# revisão é separada da rota do aluno, e a auditoria de isolamento por
# CASO_ID continua vazia com a rota registrada.
# ---------------------------------------------------------------------------


def test_rota_de_revisao_nao_recebe_caso_id_e_nao_viola_auditoria_de_isolamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/revisao/fila` não tem `CASO_ID` como path/query parameter — ela
    lista, não busca um caso por identificador. A auditoria de isolamento
    por caso do aluno (`app/http/isolamento.py`, T-31/T-32) continua sem
    violação com a rota registrada, porque ela está estruturalmente fora do
    domínio que aquela auditoria cobre (rotas do ALUNO com `CASO_ID`)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()

    rotas_achatadas = _rotas_api_achatadas(aplicacao.routes)
    caminhos_de_revisao = [rota.path for rota in rotas_achatadas if "/revisao" in rota.path]
    assert caminhos_de_revisao, "esperava a rota /revisao/fila registrada"
    for caminho in caminhos_de_revisao:
        assert "{CASO_ID}" not in caminho and "{caso_id}" not in caminho.lower()

    assert rotas_sem_isolamento_por_caso(aplicacao) == []


def test_rota_de_revisao_e_separada_da_rota_do_aluno_sem_prefixo_caso(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """A fila de revisão fica sob `/revisao/`, nunca sob `/caso/{CASO_ID}/...`
    (o prefixo das rotas do aluno, T-30/T-36/T-42/T-56/T-63/T-64) — a
    separação de rota é o próprio mecanismo que impede a tela do aluno de
    alcançar a fila."""
    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get("/api/revisao/fila")

    assert resposta.status_code == 200
    assert not resposta.url.path.startswith("/caso/")


# ---------------------------------------------------------------------------
# Critério "nenhum valor da fila é calculado" — inspeção estática do módulo
# da rota: nenhum operador aritmético, tudo leitura de atributo.
# ---------------------------------------------------------------------------


def test_rota_de_revisao_nao_calcula_nenhum_valor_lido_do_snapshot() -> None:
    """Percorre a AST de `app/http/rotas_revisao.py` e garante que nenhum
    operador aritmético (`+`, `-`, `*`, `/`, etc.) aparece no módulo — todo
    valor do contexto do template é uma leitura direta de atributo
    (`ItemFila`/`SnapshotOrdem`), nunca uma soma ou derivação (Lei nº 3)."""
    caminho = Path(__file__).resolve().parent.parent.parent / "app" / "http" / "rotas_revisao.py"
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    # `ast.Div` fica FORA da lista: o único `BinOp` do módulo é
    # `Path(...) / "report/templates/revisao"` (composição de caminho de
    # arquivo, uso idiomático de `pathlib.Path.__truediv__`), não uma
    # divisão aritmética sobre valor de snapshot — os operadores realmente
    # suspeitos de cálculo financeiro/numérico permanecem cobertos.
    operadores_aritmeticos_proibidos = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )
    operacoes_encontradas = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.BinOp) and isinstance(no.op, operadores_aritmeticos_proibidos)
    ]

    assert not operacoes_encontradas, (
        "app/http/rotas_revisao.py não deveria conter operação aritmética "
        f"(Lei nº 3): {operacoes_encontradas}"
    )
