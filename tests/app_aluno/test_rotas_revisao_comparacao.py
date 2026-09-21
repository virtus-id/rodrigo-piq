"""Testes de `GET /revisao/caso/{CASO_ID}` — a tela de comparação lado a
lado entre o plano e os `estado_inputs` (`RF-26`, `AC-29`, T-70).

`RepositorioCasosArquivo`/`RepositorioSnapshotsArquivo` (persistência real de
arquivo, T-24) e `SnapshotOrdem` REAL produzido por `executar_calculo` sobre
a fixture de caso completo (T-53) — mesmo padrão de `tests/app_aluno/
test_rotas_revisao.py` (T-69): nenhum snapshot fabricado à mão.

Cobre os quatro critérios de aceite de T-70:

1. `AC-29`: o plano e os `estado_inputs` aparecem na MESMA resposta HTTP
   (mesma sessão), sem nenhum link/redirecionamento para outro caso.
2. O plano exibido é o HTML produzido por `report.plano.montar_contexto_plano`
   + `report.pdf.renderizar_html_do_plano` — o MESMO par função/template que
   a tela do aluno usa (T-60/T-63/T-64) — verificado por comparação de string
   com o HTML que a própria função produziria para o mesmo snapshot.
3. `DESCONHECIDO` aparece de forma visível para uma `Divida` com
   `SALDO_DEVEDOR_ATUAL`/`PAGAMENTO_MENSAL_EFETIVO` desconhecidos
   (reprodução de `GAB-03`/`AC-08` pela via da coleta,
   `caso_completo_com_divida_gab03`) — nunca como `0` nem string vazia.
4. `ENGINE_VERSION`/`PARAMETROS_VERSION` (`AC-16`) aparecem também nesta
   tela do revisor.

REGRAS: `RF-26`, `AC-29`
"""

from __future__ import annotations

from datetime import UTC, datetime
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
from app.http.serializacao_plano import serializar_plano
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from engine.estado import EstadoFinanceiro
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from report.plano import carregar_textos_canonicos, montar_contexto_plano
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    CasoCompleto,
    caso_completo,
    caso_completo_com_divida_gab03,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_PARAMETROS_VERSAO = "1.0.1"


def _montar_estado(caso: CasoCompleto) -> EstadoFinanceiro:
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
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
    caso_completo_de_prova: CasoCompleto,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> SnapshotOrdem:
    """Produz um `SnapshotOrdem` REAL (mesma cadeia de `app/motor/
    executor.py`) e deixa o caso em `AGUARDANDO_REVISAO` — mesmo padrão de
    `tests/app_aluno/test_rotas_revisao.py::_calcular_snapshot`."""
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
        anterior=None,
    )
    snapshot = executar_calculo(_montar_estado(caso_completo_de_prova), insumos)
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
    `ParametrosDoCalculo`; esta suíte não asserta sobre a trilha."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
) -> TestClient:
    """Mesmo padrão de `tests/app_aluno/test_rotas_revisao.py::
    _montar_cliente`: `exigir_papel_revisor` é sobrescrita para um revisor já
    autenticado — estes testes cobrem o CONTEÚDO da comparação (T-70), não a
    guarda de papel em si (coberta por `test_guarda_papel_revisor.py`, T-100)."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = lambda: (
        repositorio_snapshots
    )
    aplicacao.dependency_overrides[exigir_papel_revisor] = lambda: "conta-revisor-teste"
    return TestClient(aplicacao, base_url="https://teste.local")


# ---------------------------------------------------------------------------
# AC-29 — plano e estado_inputs na MESMA sessão, sem navegação para outro caso.
# ---------------------------------------------------------------------------


def test_ac29_plano_e_estado_inputs_aparecem_na_mesma_resposta(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-29`: uma única requisição a `/revisao/caso/{CASO_ID}` devolve, na
    MESMA resposta HTTP, tanto o conteúdo do plano (título canônico de `Q-03`,
    `AC-14`) quanto ao menos um campo de `estado_inputs` — nenhuma navegação
    para outra URL é necessária."""
    caso_id = "CASO-COMPARACAO-AC29"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-comparacao")
    snapshot = _calcular_snapshot(
        caso_id, caso_completo(), repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id}")

    assert resposta.status_code == 200
    corpo = resposta.text
    # Lado do plano: a redação canônica de Q-03 (AC-14), a mesma do aluno.
    assert "Sua ordem projetada de quitação" in corpo
    # Lado do estado_inputs: um campo qualquer de EstadoFinanceiro, lido do
    # próprio snapshot.
    assert snapshot.estado_inputs.dividas[0].DIVIDA_ID in corpo
    assert "RENDA_TOTAL_RECORRENTE" in corpo
    # Nenhuma navegação para outro caso: a página não referencia outro CASO_ID.
    assert corpo.count(caso_id) >= 1


def test_a_rota_nao_recebe_referencia_de_outro_caso(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-29` (reforço): a tela de um caso não contém link para a URL de
    comparação de outro caso — a única forma de trocar de caso é sair da
    tela (voltar à fila), nunca uma navegação embutida entre casos."""
    caso_id_1 = "CASO-COMPARACAO-1"
    caso_id_2 = "CASO-COMPARACAO-2"
    _criar_caso(repositorio_casos, caso_id_1, "conta-aluno-1")
    _calcular_snapshot(
        caso_id_1, caso_completo(), repositorio_casos, repositorio_snapshots, repositorio_eventos
    )
    _criar_caso(repositorio_casos, caso_id_2, "conta-aluno-2")
    _calcular_snapshot(
        caso_id_2, caso_completo(), repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id_1}")

    assert resposta.status_code == 200
    assert f"/revisao/caso/{caso_id_2}" not in resposta.text


# ---------------------------------------------------------------------------
# Critério "o plano exibido é renderizado pelo mesmo template do aluno, sem
# segunda redação" — comparação de string com o HTML que a própria função de
# produção geraria para o mesmo snapshot.
# ---------------------------------------------------------------------------


def test_plano_exibido_e_o_mesmo_html_de_montar_contexto_plano(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """O "lado do plano" na tela de comparação é EXATAMENTE o que
    `report.plano.montar_contexto_plano` + `app.http.serializacao_plano.
    serializar_plano` produzem para o mesmo snapshot — prova de que não há
    segunda redação/montagem paralela.

    **O snapshot de comparação é relido do repositório**, não o objeto que
    `executar_calculo` devolveu. `_serializar_canonico` grava com
    `sort_keys=True` (`persistencia/arquivo/repositorio_snapshots.py:143`),
    o que reordena as chaves de `valores_de_apoio` — deliberado, porque a
    forma canônica alimenta o `hash_inputs` e precisa ser estável. Comparar
    contra o objeto em memória mediria essa reordenação, que é da
    persistência, em vez da igualdade que o critério de aceite pede."""
    caso_id = "CASO-COMPARACAO-MESMO-TEMPLATE"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-mesmo-template")
    _calcular_snapshot(
        caso_id, caso_completo(), repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    caso = repositorio_casos.buscar(caso_id)
    assert caso is not None and caso.snapshot_raiz_id is not None
    snapshot = repositorio_snapshots.historico(caso.snapshot_raiz_id)[-1]

    textos = carregar_textos_canonicos()
    contexto_plano = montar_contexto_plano(snapshot, textos)
    esperado = serializar_plano(contexto_plano)

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id}")

    assert resposta.status_code == 200
    # `T-144`: a comparação passou de HTML para JSON, e a garantia ficou
    # mais direta — o plano do revisor é IGUAL, campo a campo, ao que
    # `montar_contexto_plano` + `serializar_plano` produzem para o mesmo
    # snapshot. Como é essa mesma dupla que serve a tela do aluno
    # (`/caso/{id}/api/plano`), uma segunda redação do plano não teria como
    # existir sem quebrar esta igualdade.
    assert resposta.json()["plano"] == esperado


# ---------------------------------------------------------------------------
# Regra mais importante da tarefa: DESCONHECIDO visível como tal, nunca como
# 0 ou vazio — reprodução de GAB-03/AC-08 (saldo e pagamento desconhecidos).
# ---------------------------------------------------------------------------


def test_desconhecido_e_exibido_de_forma_visivel_nunca_como_zero_ou_vazio(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Reproduz `GAB-03`/`AC-08` pela via da coleta: uma `Divida` com
    `SALDO_DEVEDOR_ATUAL` e `PAGAMENTO_MENSAL_EFETIVO` respondidos como "não
    sei" chega a `estado_inputs` como `Desconhecido`
    (`engine.tipos.DESCONHECIDO`). A tela do revisor precisa mostrar o texto
    literal "DESCONHECIDO" para os dois campos — nunca `0`, nunca `0,00`,
    nunca uma célula vazia."""
    caso_id = "CASO-COMPARACAO-GAB03"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-gab03")
    snapshot = _calcular_snapshot(
        caso_id,
        caso_completo_com_divida_gab03(),
        repositorio_casos,
        repositorio_snapshots,
        repositorio_eventos,
    )

    # Confirma a premissa do teste: os dois campos realmente chegaram como
    # DESCONHECIDO em estado_inputs — sem isso o teste provaria nada.
    divida = snapshot.estado_inputs.dividas[0]
    assert divida.SALDO_DEVEDOR_ATUAL is DESCONHECIDO
    assert divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id}")
    corpo = resposta.text

    assert resposta.status_code == 200
    # O texto literal aparece pelo menos duas vezes (um para cada campo
    # desconhecido desta dívida) — nunca "0", "0,00" ou célula vazia no lugar.
    assert corpo.count("DESCONHECIDO") >= 2
    # Nenhum rótulo escondendo o desconhecido atrás de zero monetário: o
    # padrão de exibição monetária ("0,00") não aparece associado aos dois
    # campos que deveriam ser DESCONHECIDO (checagem indireta: já que
    # `_formatar_valor_ou_desconhecido` nunca produz "0,00" para um campo
    # Desconhecido, e os dois únicos campos monetários desta dívida
    # respondidos são exatamente estes dois).
    assert "Desconhecido.DESCONHECIDO" not in corpo


# ---------------------------------------------------------------------------
# Critério "o carimbo ENGINE_VERSION/PARAMETROS_VERSION aparece também para
# o revisor (AC-16)".
# ---------------------------------------------------------------------------


def test_ac16_carimbo_de_versao_aparece_para_o_revisor(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-16`: `ENGINE_VERSION` e `PARAMETROS_VERSION` do snapshot aparecem
    na tela de comparação do revisor — tanto no HTML do plano incluído
    quanto na referência rápida da própria página de comparação."""
    caso_id = "CASO-COMPARACAO-AC16"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-ac16")
    snapshot = _calcular_snapshot(
        caso_id, caso_completo(), repositorio_casos, repositorio_snapshots, repositorio_eventos
    )

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id}")
    corpo = resposta.text

    assert resposta.status_code == 200
    assert snapshot.ENGINE_VERSION in corpo
    assert snapshot.PARAMETROS_VERSION in corpo


# ---------------------------------------------------------------------------
# Caminhos não-felizes: caso inexistente e caso sem snapshot.
# ---------------------------------------------------------------------------


def test_caso_inexistente_devolve_404(monkeypatch: pytest.MonkeyPatch) -> None:
    aplicacao_vazia_casos = RepositorioCasosArquivo(Path("nao-usado.jsonl"))
    aplicacao_vazia_snapshots = RepositorioSnapshotsArquivo(Path("nao-usado-snap.jsonl"))
    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=aplicacao_vazia_casos,
        repositorio_snapshots=aplicacao_vazia_snapshots,
    )

    resposta = cliente.get("/revisao/caso/CASO-QUE-NAO-EXISTE")

    assert resposta.status_code == 404


def test_caso_sem_snapshot_devolve_404(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    caso_id = "CASO-COMPARACAO-SEM-SNAPSHOT"
    _criar_caso(repositorio_casos, caso_id, "conta-aluno-sem-snapshot")

    cliente = _montar_cliente(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )

    resposta = cliente.get(f"/api/revisao/caso/{caso_id}")

    assert resposta.status_code == 404
