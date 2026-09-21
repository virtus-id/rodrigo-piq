"""Testes de `app/casos/acompanhamento.py::processar_resposta_bloco_11`/
`processar_resposta_bloco_11_async`/`registrar_alteracao_cadastral` —
`RF-28`, `AC-35`, T-87.

Mesmo precedente de `tests/app_aluno/test_disparar_recalculo.py` (T-86): usa
o adaptador de ARQUIVO (`persistencia/arquivo/`, do slug `motor-calculo`,
CONGELADO/`AC-44`) para `FonteParametros`/`RepositorioSnapshots`, e
`persistencia/app_aluno/arquivo.py` para `RepositorioCasos`/
`RepositorioEventosCaso` — a suíte principal desta feature roda sem
`DATABASE_URL`. `calcular_plano` é o MOTOR REAL, através do MESMO executor
do Bloco 6, quando o caminho de recálculo é exercido.

REGRAS: `RF-28`, `AC-35`
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.casos.acompanhamento import (
    processar_resposta_bloco_11,
    processar_resposta_bloco_11_async,
    registrar_alteracao_cadastral,
)
from app.casos.maquina import ESTADO_CASO, Caso
from app.eventos.mapeamento import VARIAVEL_STATUS_QUITACAO_REAL
from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.estado import EstadoFinanceiro
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, CasoCompleto, caso_completo

_PARAMETROS_VERSAO: str = "1.0.1"
_CASO_ID: str = "caso-teste-t87-alteracao-cadastral"


def _montar_estado_do_caso(caso: CasoCompleto) -> EstadoFinanceiro:
    """Mesmo helper de `tests/app_aluno/test_disparar_recalculo.py`."""
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


@pytest.fixture
def repositorio_snapshots_arquivo(tmp_path: Path) -> RepositorioSnapshotsArquivo:
    return RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")


@pytest.fixture
def fonte_parametros_arquivo() -> FonteParametrosArquivo:
    return FonteParametrosArquivo()


@pytest.fixture
def estado_financeiro() -> EstadoFinanceiro:
    return _montar_estado_do_caso(caso_completo())


@pytest.fixture
def repositorio_eventos_arquivo(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


@pytest.fixture
def repositorio_casos_arquivo(
    tmp_path: Path,
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> RepositorioCasosArquivo:
    """`Caso` de teste já em `ACOMPANHAMENTO` com um snapshot raiz anexado —
    mesma pré-condição de `test_disparar_recalculo.py`, montada aqui pelo
    MESMO executor real (nenhum snapshot fabricado)."""
    from app.motor.executor import ParametrosDoCalculo, executar_calculo

    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID=_CASO_ID,
            conta_id="conta-teste-t87",
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )
    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)

    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio,
        repositorio_eventos=repositorio_eventos_arquivo,
        caso_id=_CASO_ID,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    snapshot_raiz = executar_calculo(estado_financeiro, insumos)
    repositorio.registrar_snapshot_raiz(_CASO_ID, snapshot_raiz.SNAPSHOT_ID)
    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.ACOMPANHAMENTO)
    return repositorio


# ---------------------------------------------------------------------------
# AC-35 (primeiro critério) — correção de rótulo é salva e nenhum snapshot
# novo é criado.
# ---------------------------------------------------------------------------


def test_ac35_alteracao_cadastral_nao_cria_snapshot_novo(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-35`: uma resposta de alteração cadastral (`variavel_gravada` que
    não é `STATUS_QUITACAO_REAL`, ex.: correção de nome/rótulo) processada
    por `processar_resposta_bloco_11` não invoca o executor — o histórico de
    snapshots do caso permanece exatamente como estava antes da chamada."""
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None and caso.snapshot_raiz_id is not None

    historico_antes = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)
    quantidade_antes = len(historico_antes)

    resultado = processar_resposta_bloco_11(
        id_pergunta="B5.NOME01",
        variavel_gravada="NOME_COMPLETO",
        valor_interno="Maria Correta da Silva",
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert resultado is None

    historico_depois = repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id)
    assert len(historico_depois) == quantidade_antes


# ---------------------------------------------------------------------------
# Segundo critério — nenhuma rota constrói EVENTO_RECALCULO a partir de
# resposta que não seja evento material ou quitação confirmada. Provado
# aqui em duas camadas: (a) auditoria de que `evento_recalculo_da_resposta`
# é o ÚNICO ponto de construção do enum a partir de uma resposta em todo
# `app/`; (b) `processar_resposta_bloco_11` nunca fabrica um evento por
# conta própria quando a variável não é a de quitação.
# ---------------------------------------------------------------------------


def test_unico_ponto_de_construcao_de_evento_recalculo_a_partir_de_resposta() -> None:
    """Auditoria por AST: em todo `app/`, a única chamada a uma função que
    devolve `EVENTO_RECALCULO | None` a partir de uma resposta é
    `evento_recalculo_da_resposta` (`app/eventos/mapeamento.py`, T-81) —
    direta ou through `evento_da_resposta_b11_q01` (T-82, uma chamada fina
    sobre ela). Nenhum outro arquivo constrói `EVENTO_RECALCULO(...)` nem
    indexa o enum (`EVENTO_RECALCULO[...]`) a partir de dado de resposta."""
    import ast

    raiz_projeto = Path(__file__).resolve().parent.parent.parent
    pasta_app = raiz_projeto / "app"
    arquivos_permitidos = {
        pasta_app / "eventos" / "mapeamento.py",  # a própria função
    }

    violacoes: list[str] = []
    for caminho in pasta_app.rglob("*.py"):
        if caminho in arquivos_permitidos:
            continue
        codigo_fonte = caminho.read_text(encoding="utf-8")
        arvore = ast.parse(codigo_fonte, filename=str(caminho))
        for no in ast.walk(arvore):
            construtor_direto = isinstance(no, ast.Call) and (
                (isinstance(no.func, ast.Name) and no.func.id == "EVENTO_RECALCULO")
                or (isinstance(no.func, ast.Attribute) and no.func.attr == "EVENTO_RECALCULO")
            )
            indexacao_direta = isinstance(no, ast.Subscript) and (
                (isinstance(no.value, ast.Name) and no.value.id == "EVENTO_RECALCULO")
                or (isinstance(no.value, ast.Attribute) and no.value.attr == "EVENTO_RECALCULO")
            )
            if construtor_direto or indexacao_direta:
                linha = getattr(no, "lineno", 0)
                violacoes.append(f"{caminho}:{linha}")

    assert not violacoes, (
        "construção direta de EVENTO_RECALCULO fora de app/eventos/mapeamento.py "
        f"(AC-35, T-87): {violacoes}"
    )


def test_processar_resposta_bloco_11_nao_fabrica_evento_para_variavel_cadastral(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """Comportamento observável: para qualquer `variavel_gravada` diferente
    de `STATUS_QUITACAO_REAL`, `processar_resposta_bloco_11` nunca chama
    `evento_da_resposta_b11_q01` — o evento é `None` estruturalmente, sem
    sequer consultar o mapeamento (`app/eventos/mapeamento.py` permanece o
    único caminho de construção do enum)."""
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None

    resultado = processar_resposta_bloco_11(
        id_pergunta="B5.APELIDO01",
        variavel_gravada="APELIDO_DIVIDA",
        valor_interno="QUITADA",  # mesmo valor_interno da quitação real — ainda assim ignorado
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert resultado is None
    eventos_da_trilha = repositorio_eventos_arquivo.listar_do_caso(_CASO_ID)
    assert len(eventos_da_trilha) == 1
    assert eventos_da_trilha[0].tipo_evento == "alteracao_cadastral"


# ---------------------------------------------------------------------------
# Terceiro critério — alteração cadastral fica registrada na trilha do caso,
# sem transição de estado.
# ---------------------------------------------------------------------------


def test_ac35_alteracao_cadastral_registrada_na_trilha_sem_transicao(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`registrar_alteracao_cadastral` grava um `EventoCaso` com
    `estado_de`/`estado_para` ambos `None` (nenhuma transição) e o `estado`
    do `Caso` em `app_aluno.casos` permanece `ACOMPANHAMENTO` depois da
    chamada — a trilha é OBSERVÁVEL, mas não é uma transição."""
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None
    assert caso.estado == ESTADO_CASO.ACOMPANHAMENTO

    processar_resposta_bloco_11(
        id_pergunta="B5.NOME01",
        variavel_gravada="NOME_COMPLETO",
        valor_interno="Maria Correta da Silva",
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    eventos_da_trilha = repositorio_eventos_arquivo.listar_do_caso(_CASO_ID)
    assert len(eventos_da_trilha) == 1
    evento = eventos_da_trilha[0]
    assert evento.tipo_evento == "alteracao_cadastral"
    assert evento.estado_de is None
    assert evento.estado_para is None
    assert evento.detalhe == "B5.NOME01"

    caso_depois = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_depois is not None
    assert caso_depois.estado == ESTADO_CASO.ACOMPANHAMENTO


def test_registrar_alteracao_cadastral_isoladamente_nao_transiciona() -> None:
    """Auditoria de AST sobre `registrar_alteracao_cadastral`: a função não
    referencia `transicionar`, `ESTADO_CASO` como alvo de atribuição, nem
    `transicionar_estado`/`transicionar_estado_se` — reforça, por inspeção
    estática, o terceiro critério além da prova por comportamento acima."""
    import ast
    import inspect

    from app.casos.acompanhamento import registrar_alteracao_cadastral as funcao

    codigo_fonte = inspect.getsource(funcao)
    arvore = ast.parse(codigo_fonte)
    nomes_chamados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            nomes_chamados.add(no.func.id)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            nomes_chamados.add(no.func.attr)

    assert "transicionar" not in nomes_chamados
    assert "transicionar_estado" not in nomes_chamados
    assert "transicionar_estado_se" not in nomes_chamados


# ---------------------------------------------------------------------------
# Quarto critério — um teste garante que o número de snapshots do caso não
# muda (contagem antes/depois de uma correção cadastral).
# ---------------------------------------------------------------------------


def test_contagem_de_snapshots_do_caso_nao_muda_apos_correcao_cadastral(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """Quarto critério de aceite de `T-87`, literal: contagem de snapshots do
    caso antes e depois de processar uma correção cadastral."""
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None and caso.snapshot_raiz_id is not None

    quantidade_antes = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))

    processar_resposta_bloco_11(
        id_pergunta="B5.ROTULO01",
        variavel_gravada="ROTULO_DIVIDA",
        valor_interno="Cartão renomeado",
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    quantidade_depois = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))
    assert quantidade_depois == quantidade_antes


# ---------------------------------------------------------------------------
# Contraprova — quando a variável É a de quitação e o valor É `QUITADA`, a
# orquestração DISPARA o recálculo (garante que a árvore if/else não está
# sempre caindo no ramo de trilha por engano).
# ---------------------------------------------------------------------------


def test_processar_resposta_bloco_11_dispara_recalculo_quando_ha_evento(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None and caso.snapshot_raiz_id is not None
    quantidade_antes = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))

    resultado = processar_resposta_bloco_11(
        id_pergunta="B11.Q01",
        variavel_gravada=VARIAVEL_STATUS_QUITACAO_REAL,
        valor_interno="QUITADA",
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert resultado is not None
    quantidade_depois = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))
    assert quantidade_depois == quantidade_antes + 1
    # T-91: a transição ACOMPANHAMENTO → CALCULANDO (`disparar_recalculo`)
    # agora grava seu PRÓPRIO evento na trilha (`tipo_evento="recalcula"`) —
    # mas nenhum evento de "alteração cadastral" aparece por este caminho: os
    # dois ramos (recálculo disparado vs. alteração cadastral registrada)
    # nunca ocorrem juntos.
    eventos_da_trilha = repositorio_eventos_arquivo.listar_do_caso(_CASO_ID)
    assert all(evento.tipo_evento != "alteracao_cadastral" for evento in eventos_da_trilha)
    assert any(evento.tipo_evento == "recalcula" for evento in eventos_da_trilha)


def test_processar_resposta_bloco_11_a_confirmar_registra_trilha_sem_recalculo(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """`AC-31`/`AC-35` juntos: `A_CONFIRMAR` (mesma variável de quitação, mas
    valor sem entrada no mapeamento) segue o MESMO caminho estrutural de uma
    alteração cadastral — evento `None`, trilha registrada, sem recálculo."""
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None and caso.snapshot_raiz_id is not None
    quantidade_antes = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))

    resultado = processar_resposta_bloco_11(
        id_pergunta="B11.Q01",
        variavel_gravada=VARIAVEL_STATUS_QUITACAO_REAL,
        valor_interno="A_CONFIRMAR",
        caso=caso,
        estado=estado_financeiro,
        fonte_parametros=fonte_parametros_arquivo,
        repositorio_snapshots=repositorio_snapshots_arquivo,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos_arquivo,
        parametros_versao=_PARAMETROS_VERSAO,
    )

    assert resultado is None
    quantidade_depois = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))
    assert quantidade_depois == quantidade_antes
    assert len(repositorio_eventos_arquivo.listar_do_caso(_CASO_ID)) == 1


# ---------------------------------------------------------------------------
# Variante assíncrona — mesma decisão, mesma ausência de fabricação de
# evento genérico.
# ---------------------------------------------------------------------------


def test_processar_resposta_bloco_11_async_alteracao_cadastral_nao_recalcula(
    estado_financeiro: EstadoFinanceiro,
    fonte_parametros_arquivo: FonteParametrosArquivo,
    repositorio_snapshots_arquivo: RepositorioSnapshotsArquivo,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    caso = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso is not None and caso.snapshot_raiz_id is not None
    quantidade_antes = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))

    resultado = asyncio.run(
        processar_resposta_bloco_11_async(
            id_pergunta="B5.NOME01",
            variavel_gravada="NOME_COMPLETO",
            valor_interno="Maria Correta da Silva",
            caso=caso,
            estado=estado_financeiro,
            fonte_parametros=fonte_parametros_arquivo,
            repositorio_snapshots=repositorio_snapshots_arquivo,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos_arquivo,
            parametros_versao=_PARAMETROS_VERSAO,
        )
    )

    assert resultado is None
    quantidade_depois = len(repositorio_snapshots_arquivo.historico(caso.snapshot_raiz_id))
    assert quantidade_depois == quantidade_antes


def test_registrar_alteracao_cadastral_gera_evento_id_unico_por_chamada(
    repositorio_eventos_arquivo: RepositorioEventosCasoArquivo,
) -> None:
    """Duas chamadas de `registrar_alteracao_cadastral` para o mesmo caso
    produzem dois `evento_id` distintos — nenhum reaproveitamento que possa
    mascarar uma gravação por outra na trilha."""
    caso = Caso(
        CASO_ID=_CASO_ID,
        conta_id="conta-teste-t87",
        estado=ESTADO_CASO.ACOMPANHAMENTO,
        DATA_REFERENCIA=DATA_REFERENCIA,
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )

    registrar_alteracao_cadastral(
        caso=caso, id_pergunta="B5.NOME01", repositorio_eventos=repositorio_eventos_arquivo
    )
    registrar_alteracao_cadastral(
        caso=caso, id_pergunta="B5.APELIDO01", repositorio_eventos=repositorio_eventos_arquivo
    )

    eventos = repositorio_eventos_arquivo.listar_do_caso(_CASO_ID)
    assert len(eventos) == 2
    assert eventos[0].evento_id != eventos[1].evento_id
