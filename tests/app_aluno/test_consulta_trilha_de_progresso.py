"""Testes de `app/casos/progresso.py::consultar_trilha_de_progresso` — a
consulta de trilha de progresso (`RF-31`, `AC-40`, T-92).

Cobre os quatro critérios de aceite da tarefa, com um conjunto de casos REAIS
em estados diferentes (usando os repositórios de arquivo, `persistencia/
app_aluno/arquivo.py`, T-24 — sem `DATABASE_URL`) e a coleção de registros
REAL (`collection/carga.py`, T-16), no mesmo estilo de `tests/app_aluno/
test_progresso.py` (T-44) e `test_retomada_progresso.py` (T-45).

REGRAS: `RF-31`, `AC-40`
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.casos.maquina import ESTADO_CASO, Caso
from app.casos.progresso import (
    RelatoDeProgresso,
    consultar_trilha_de_progresso,
    proxima_pergunta_nao_respondida,
)
from collection.carga import carregar_registros
from collection.registro import RegistroPergunta
from collection.respostas import Resposta, RespostasCaso
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo


def _colecao_real() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _resposta(caso_id: str, variavel: str, valor: object) -> Resposta:
    return Resposta(
        CASO_ID=caso_id,
        ID_PERGUNTA=variavel,
        item_id=None,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )


def _caso(
    caso_id: str, estado: ESTADO_CASO, ultima_interacao_em: datetime, conta_id: str = "conta-teste"
) -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id=conta_id,
        estado=estado,
        DATA_REFERENCIA=ultima_interacao_em.date(),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=ultima_interacao_em,
        criado_em=ultima_interacao_em,
    )


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    return RepositorioCasosArquivo(tmp_path / "casos.jsonl")


# ---------------------------------------------------------------------------
# Critério 1 (`AC-40`) — para um conjunto de casos em estados diferentes,
# cada um reporta seu estado atual e a data da última interação.
# ---------------------------------------------------------------------------


def test_ac40_conjunto_de_casos_em_estados_diferentes_reporta_estado_e_data(
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """Quatro casos reais, em quatro estados diferentes do plano §4.3, cada
    um com sua própria `ultima_interacao_em` — a consulta devolve, para CADA
    um, exatamente o `estado` e a data gravados, sem misturar casos."""
    registros = _colecao_real()
    t_cadastrado = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    t_coleta = datetime(2026, 2, 10, 14, 30, tzinfo=UTC)
    t_calculando = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    t_revisao = datetime(2026, 3, 15, 17, 45, tzinfo=UTC)

    casos = {
        "CASO-001": _caso("CASO-001", ESTADO_CASO.CADASTRADO, t_cadastrado),
        "CASO-002": _caso("CASO-002", ESTADO_CASO.COLETA_INICIAL, t_coleta),
        "CASO-003": _caso("CASO-003", ESTADO_CASO.CALCULANDO, t_calculando),
        "CASO-004": _caso("CASO-004", ESTADO_CASO.AGUARDANDO_REVISAO, t_revisao),
    }
    for caso in casos.values():
        repositorio_casos.criar(caso)

    relatos = {
        caso_id: consultar_trilha_de_progresso(
            repositorio_casos.buscar(caso_id) or _falha(caso_id),
            registros,
            RespostasCaso(respostas=()),
        )
        for caso_id in casos
    }

    assert relatos["CASO-001"].estado is ESTADO_CASO.CADASTRADO
    assert relatos["CASO-001"].ultima_interacao_em == t_cadastrado
    assert relatos["CASO-002"].estado is ESTADO_CASO.COLETA_INICIAL
    assert relatos["CASO-002"].ultima_interacao_em == t_coleta
    assert relatos["CASO-003"].estado is ESTADO_CASO.CALCULANDO
    assert relatos["CASO-003"].ultima_interacao_em == t_calculando
    assert relatos["CASO-004"].estado is ESTADO_CASO.AGUARDANDO_REVISAO
    assert relatos["CASO-004"].ultima_interacao_em == t_revisao

    # CASO_ID de cada relato é o do próprio caso — nenhuma mistura entre eles.
    for caso_id, relato in relatos.items():
        assert relato.CASO_ID == caso_id


def _falha(caso_id: str) -> Caso:  # pragma: no cover — defensivo, nunca deveria disparar
    raise AssertionError(f"CASO_ID={caso_id!r} deveria existir no repositório de teste")


# ---------------------------------------------------------------------------
# Critério 2 — a consulta indica a pergunta em que o caso parou, derivada do
# mesmo mecanismo de retomada de T-45.
# ---------------------------------------------------------------------------


def test_proxima_pergunta_do_relato_e_identica_a_retomada_de_t45(
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """`proxima_pergunta` do relato é EXATAMENTE o que `proxima_pergunta_
    nao_respondida` (T-45) devolveria para o mesmo `(registros, respostas)`
    — a trilha nunca inventa uma segunda lógica de "onde parou"."""
    registros = _colecao_real()
    agora = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    caso_id = "CASO-PAROU-NO-MEIO"
    repositorio_casos.criar(_caso(caso_id, ESTADO_CASO.COLETA_INICIAL, agora))

    # Respostas parciais: só os primeiros registros do Bloco 1, sem repetição,
    # foram respondidos — reproduz "parou no meio da coleta".
    registros_bloco_1 = [r for r in registros if r.bloco == 1][:3]
    respostas = RespostasCaso(
        respostas=tuple(
            _resposta(caso_id, r.VARIAVEL_GRAVADA, "X")
            for r in registros_bloco_1
            if r.VARIAVEL_GRAVADA is not None
        )
    )

    esperado = proxima_pergunta_nao_respondida(registros, respostas)
    caso = repositorio_casos.buscar(caso_id)
    assert caso is not None

    relato = consultar_trilha_de_progresso(caso, registros, respostas)

    assert esperado is not None, "fixture inválida: nenhuma pergunta pendente para comparar"
    assert relato.proxima_pergunta == esperado


def test_proxima_pergunta_e_none_quando_colecao_vazia(
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """Uma coleção de registros vazia não tem o que varrer — `proxima_
    pergunta` é `None`, mesma semântica de `proxima_pergunta_nao_respondida`
    devolver `None` (nada pendente)."""
    agora = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    caso_id = "CASO-SEM-REGISTROS"
    repositorio_casos.criar(_caso(caso_id, ESTADO_CASO.CADASTRADO, agora))
    caso = repositorio_casos.buscar(caso_id)
    assert caso is not None

    relato = consultar_trilha_de_progresso(caso, (), RespostasCaso(respostas=()))

    assert relato.proxima_pergunta is None


# ---------------------------------------------------------------------------
# Critério 3 — a consulta não expõe dado financeiro do aluno.
# ---------------------------------------------------------------------------


def test_relato_de_progresso_so_declara_campos_estruturais() -> None:
    """Auditoria por ASSINATURA: `RelatoDeProgresso.__slots__` é exatamente
    os cinco campos estruturais — nenhum campo de `Resposta`/`ValorResposta`
    (valor de formulário) nem de `EstadoFinanceiro`/`SnapshotOrdem` (motor)."""
    campos_permitidos = frozenset(
        {
            "CASO_ID",
            "estado",
            "ultima_interacao_em",
            "proxima_pergunta",
            "aguardando_revisao",
        }
    )
    assert set(RelatoDeProgresso.__slots__) == campos_permitidos


def test_relato_de_progresso_nao_carrega_valor_de_resposta(
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """Mesmo com respostas de valor concreto gravadas, nada do VALOR
    respondido aparece no relato — só o `ID` da pergunta em aberto (que é
    metadado do registro, não dado do aluno, já auditado por `AC-37`/T-08)."""
    registros = _colecao_real()
    agora = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    caso_id = "CASO-COM-VALORES"
    repositorio_casos.criar(_caso(caso_id, ESTADO_CASO.COLETA_INICIAL, agora))
    caso = repositorio_casos.buscar(caso_id)
    assert caso is not None

    respostas = RespostasCaso(
        respostas=(_resposta(caso_id, "RENDA_LIQUIDA_MENSAL", "9999.99"),)
    )
    relato = consultar_trilha_de_progresso(caso, registros, respostas)

    representacao = repr(relato)
    assert "9999.99" not in representacao


# ---------------------------------------------------------------------------
# Critério 4 — o módulo registra que a interface dedicada depende de
# `OQ-07`, sem antecipá-la.
# ---------------------------------------------------------------------------


def test_modulo_cita_oq07_sem_antecipar_interface_dedicada() -> None:
    """`app/casos/progresso.py` documenta, em prosa, que uma interface
    dedicada do operador depende de `OQ-07` — e a tarefa não antecipa essa
    interface: nenhuma rota HTTP nem template são criados por T-92."""
    import ast
    from pathlib import Path as _Path

    caminho = _Path(__file__).resolve().parents[2] / "app" / "casos" / "progresso.py"
    codigo_fonte = caminho.read_text(encoding="utf-8")
    assert "OQ-07" in codigo_fonte, (
        "T-92: o módulo precisa registrar que a interface dedicada do "
        "operador depende de OQ-07"
    )

    arvore = ast.parse(codigo_fonte, filename=str(caminho))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module is not None:
            assert "app.http" not in no.module, (
                f"T-92 não deveria importar de app.http (achado: {no.module})"
            )


def test_aguardando_revisao_true_somente_no_estado_correspondente(
    repositorio_casos: RepositorioCasosArquivo,
) -> None:
    """`aguardando_revisao` é `True` exclusivamente quando `Caso.estado is
    ESTADO_CASO.AGUARDANDO_REVISAO` — qualquer outro estado reporta `False`,
    sem uma segunda fonte de verdade."""
    registros = _colecao_real()
    agora = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

    caso_em_revisao = _caso("CASO-EM-REVISAO", ESTADO_CASO.AGUARDANDO_REVISAO, agora)
    caso_fora_de_revisao = _caso("CASO-FORA-DE-REVISAO", ESTADO_CASO.COLETA_INICIAL, agora)
    repositorio_casos.criar(caso_em_revisao)
    repositorio_casos.criar(caso_fora_de_revisao)

    relato_em_revisao = consultar_trilha_de_progresso(
        caso_em_revisao, registros, RespostasCaso(respostas=())
    )
    relato_fora_de_revisao = consultar_trilha_de_progresso(
        caso_fora_de_revisao, registros, RespostasCaso(respostas=())
    )

    assert relato_em_revisao.aguardando_revisao is True
    assert relato_fora_de_revisao.aguardando_revisao is False
