"""Testes de `persistencia/app_aluno/arquivo.py` — RF-10, RF-01 (T-24).

Roda SEMPRE, sem `DATABASE_URL` — é justamente o ponto desta tarefa: a suíte
principal desta feature (`pytest -m "not requer_banco"`) não deveria mais
precisar de Postgres para validar respostas/casos/itens. Cobre:

1. `RepositorioRespostasArquivo`/`RepositorioCasosArquivo`/
   `RepositorioItensArquivo` satisfazem o MESMO `Protocol` que o adaptador
   Postgres — checagem estática (`mypy --strict`, relatada na entrega desta
   tarefa) reforçada aqui por atribuição a uma variável tipada pelo
   `Protocol`, o suficiente para o type checker recusar uma implementação
   incompatível.
2. `Decimal` de alta precisão sobrevive ao round-trip via arquivo, comparado
   por `str()` exata — nunca só por `==` numérico.
3. Round-trip completo de `Resposta` (incluindo `NAO_SEI`, sem merge — `EC-10`),
   `Caso` (transição de estado, interação, snapshot raiz/liberado) e
   `ItemRepetido` (não-reaproveitamento de identificador após remoção).

REGRAS: RF-10, RF-01
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from collection.registro import EscopoRepeticao
from collection.respostas import NAO_SEI, Resposta
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import ESTADO_CASO, Caso, RepositorioCasos
from persistencia.app_aluno.itens import RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

# ---------------------------------------------------------------------------
# Critério 1 — mesmo `Protocol` do adaptador Postgres (mypy --strict).
# ---------------------------------------------------------------------------


def test_repositorio_respostas_arquivo_satisfaz_o_protocol(tmp_path: Path) -> None:
    """Atribuição a uma variável tipada pelo `Protocol` — se
    `RepositorioRespostasArquivo` não implementasse `gravar`/`listar_do_caso`
    com as assinaturas exigidas, `mypy --strict` recusaria esta linha."""
    repositorio: RepositorioRespostas = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    assert repositorio is not None


def test_repositorio_casos_arquivo_satisfaz_o_protocol(tmp_path: Path) -> None:
    repositorio: RepositorioCasos = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    assert repositorio is not None


def test_repositorio_itens_arquivo_satisfaz_o_protocol(tmp_path: Path) -> None:
    repositorio: RepositorioItens = RepositorioItensArquivo(tmp_path / "itens.jsonl")
    assert repositorio is not None


# ---------------------------------------------------------------------------
# Critério 2 — Decimal preservado exatamente no round-trip.
# ---------------------------------------------------------------------------


def test_decimal_alta_precisao_preserva_string_exata_no_round_trip(tmp_path: Path) -> None:
    valor_original = Decimal("1234567.123456789012345")  # 15 casas decimais
    repositorio = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    repositorio.gravar(
        Resposta(
            CASO_ID="CASO-1",
            ID_PERGUNTA="B5.VALOR_ALTA_PRECISAO",
            item_id="D001",
            valor=valor_original,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    (resposta_lida,) = repositorio.listar_do_caso("CASO-1")
    assert isinstance(resposta_lida.valor, Decimal)
    assert str(resposta_lida.valor) == str(valor_original), (
        f"round-trip perdeu precisão: gravado {valor_original!s}, lido {resposta_lida.valor!s}"
    )
    assert resposta_lida.valor == valor_original


def test_decimal_negativo_e_com_zeros_a_direita_preserva_string_exata(tmp_path: Path) -> None:
    """`Decimal("100.00")` e `Decimal("100")` têm `str()` diferentes — o
    round-trip precisa preservar exatamente a representação gravada, não só
    o valor numérico equivalente."""
    repositorio = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    valores = {
        "B5.V1": Decimal("100.00"),
        "B5.V2": Decimal("-42.5"),
        "B5.V3": Decimal("0.000001"),
    }
    for id_pergunta, valor in valores.items():
        repositorio.gravar(
            Resposta(
                CASO_ID="CASO-2",
                ID_PERGUNTA=id_pergunta,
                item_id=None,
                valor=valor,
                QUESTIONARIO_VERSION="1.0.0",
                respondida_em=datetime.now(UTC),
            )
        )

    respostas = {r.ID_PERGUNTA: r.valor for r in repositorio.listar_do_caso("CASO-2")}
    for id_pergunta, valor_original in valores.items():
        valor_lido = respostas[id_pergunta]
        assert isinstance(valor_lido, Decimal)
        assert str(valor_lido) == str(valor_original)


# ---------------------------------------------------------------------------
# Critério 3 — a suíte roda sem DATABASE_URL: round-trip funcional completo.
# ---------------------------------------------------------------------------


def test_gravar_e_listar_respostas_incluindo_nao_sei(tmp_path: Path) -> None:
    repositorio = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    repositorio.gravar(
        Resposta(
            CASO_ID="CASO-3",
            ID_PERGUNTA="B1.01",
            item_id=None,
            valor="sim",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )
    repositorio.gravar(
        Resposta(
            CASO_ID="CASO-3",
            ID_PERGUNTA="B1.02",
            item_id=None,
            valor=NAO_SEI,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    respostas = {r.ID_PERGUNTA: r.valor for r in repositorio.listar_do_caso("CASO-3")}
    assert respostas["B1.01"] == "sim"
    assert respostas["B1.02"] is NAO_SEI


def test_ec10_regravar_mesma_chave_sobrescreve_sem_merge(tmp_path: Path) -> None:
    """`EC-10`: duas gravações confirmadas sobre a MESMA `(CASO_ID,
    ID_PERGUNTA, item_id)` resultam numa única resposta observável, com o
    valor da ÚLTIMA — nada da gravação antiga sobrevive misturado, mesmo
    critério provado contra Postgres em `T-22`."""
    repositorio = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
    repositorio.gravar(
        Resposta(
            CASO_ID="CASO-4",
            ID_PERGUNTA="B5.VALOR",
            item_id="D001",
            valor=Decimal("100.00"),
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )
    repositorio.gravar(
        Resposta(
            CASO_ID="CASO-4",
            ID_PERGUNTA="B5.VALOR",
            item_id="D001",
            valor=NAO_SEI,
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=datetime.now(UTC),
        )
    )

    respostas = repositorio.listar_do_caso("CASO-4")
    assert len(respostas) == 1, "EC-10: só uma resposta observável por chave, sem merge"
    assert respostas[0].valor is NAO_SEI


def test_gravar_e_transicionar_caso(tmp_path: Path) -> None:
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime.now(UTC)
    repositorio.criar(
        Caso(
            CASO_ID="CASO-5",
            conta_id="CONTA-5",
            estado=ESTADO_CASO.CADASTRADO,
            DATA_REFERENCIA=date(2026, 1, 1),
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )

    caso_lido = repositorio.buscar("CASO-5")
    assert caso_lido is not None
    assert caso_lido.estado == ESTADO_CASO.CADASTRADO
    assert caso_lido.snapshot_raiz_id is None

    caso_transicionado = repositorio.transicionar_estado(
        "CASO-5", ESTADO_CASO.CONSENTIMENTO_REGISTRADO
    )
    assert caso_transicionado.estado == ESTADO_CASO.CONSENTIMENTO_REGISTRADO

    repositorio.registrar_snapshot_raiz("CASO-5", "SNAP-RAIZ-1")
    repositorio.registrar_snapshot_liberado("CASO-5", "SNAP-LIB-1")

    caso_final = repositorio.buscar("CASO-5")
    assert caso_final is not None
    assert caso_final.estado == ESTADO_CASO.CONSENTIMENTO_REGISTRADO
    assert caso_final.snapshot_raiz_id == "SNAP-RAIZ-1"
    assert caso_final.snapshot_liberado_id == "SNAP-LIB-1"


def test_buscar_caso_inexistente_devolve_none(tmp_path: Path) -> None:
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    assert repositorio.buscar("CASO-INEXISTENTE") is None


def test_ultima_interacao_em_e_gravada_e_legivel(tmp_path: Path) -> None:
    """RF-31/EC-14: a trilha de acompanhamento lê `ultima_interacao_em` —
    comparação por igualdade exata do `datetime` gravado vs. lido, mesmo
    critério de `T-23` contra Postgres."""
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    criado_em = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID="CASO-6",
            conta_id="CONTA-6",
            estado=ESTADO_CASO.CADASTRADO,
            DATA_REFERENCIA=date(2026, 1, 1),
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=criado_em,
            criado_em=criado_em,
        )
    )

    instante_interacao = datetime(2026, 1, 5, 15, 30, 0, tzinfo=UTC)
    repositorio.registrar_interacao("CASO-6", agora=instante_interacao)

    caso = repositorio.buscar("CASO-6")
    assert caso is not None
    assert caso.ultima_interacao_em == instante_interacao


def test_gerar_identificadores_de_item_estaveis_e_nunca_reaproveitados(tmp_path: Path) -> None:
    """`AC-04`: três dívidas produzem três `DIVIDA_ID` distintos; um item
    removido não reaproveita seu identificador para um item novo."""
    repositorio = RepositorioItensArquivo(tmp_path / "itens.jsonl")

    d001 = repositorio.proximo_identificador("CASO-7", EscopoRepeticao.DIVIDA_ID)
    d002 = repositorio.proximo_identificador("CASO-7", EscopoRepeticao.DIVIDA_ID)
    d003 = repositorio.proximo_identificador("CASO-7", EscopoRepeticao.DIVIDA_ID)
    assert (d001, d002, d003) == ("D001", "D002", "D003")

    repositorio.remover("CASO-7", "D002")
    d004 = repositorio.proximo_identificador("CASO-7", EscopoRepeticao.DIVIDA_ID)
    assert d004 == "D004", "item removido não deve liberar seu número para reaproveitamento"

    itens_ativos = repositorio.listar_do_caso("CASO-7", incluir_removidos=False)
    assert {item.item_id for item in itens_ativos} == {"D001", "D003", "D004"}

    itens_completos = repositorio.listar_do_caso("CASO-7", incluir_removidos=True)
    assert {item.item_id for item in itens_completos} == {"D001", "D002", "D003", "D004"}
    (item_removido,) = [item for item in itens_completos if item.item_id == "D002"]
    assert item_removido.removido_em is not None


def test_identificadores_de_item_sao_isolados_por_caso(tmp_path: Path) -> None:
    """Dois casos distintos gerando cada um o seu `D001` não colidem — o
    contador é por `(CASO_ID, escopo)`."""
    repositorio = RepositorioItensArquivo(tmp_path / "itens.jsonl")
    identificador_caso_a = repositorio.proximo_identificador("CASO-A", EscopoRepeticao.DIVIDA_ID)
    identificador_caso_b = repositorio.proximo_identificador("CASO-B", EscopoRepeticao.DIVIDA_ID)
    assert identificador_caso_a == "D001"
    assert identificador_caso_b == "D001"

    itens_a = repositorio.listar_do_caso("CASO-A")
    itens_b = repositorio.listar_do_caso("CASO-B")
    assert [item.CASO_ID for item in itens_a] == ["CASO-A"]
    assert [item.CASO_ID for item in itens_b] == ["CASO-B"]
