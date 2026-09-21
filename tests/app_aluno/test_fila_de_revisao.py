"""Testes de `app/revisao/fila.py` — `RF-23`, `RF-24`, `RF-25` (`AC-25`,
`AC-27`, `AC-28`), T-66, T-67.

Cobre os quatro critérios de aceite de T-66 pelo comportamento observável:

- `AC-25`: um snapshot com `REVISAO_HUMANA_OBRIGATORIA = False` entra na fila
  mesmo assim (a política do piloto manda, não o campo do motor).
- A condição de entrada lê só `POLITICA_REVISAO_INTEGRAL_PILOTO` — provado
  aqui pelo comportamento (o resultado não muda com o campo do motor); a
  prova ESTRUTURAL de que as duas expressões nunca se misturam é o teste
  ESTÁTICO `tests/app_aluno/estatica/test_fila_revisao_sinais_separados.py`.
- `AC-28`: a fila expõe os dois sinais como campos distintos de `ItemFila`.
- Fila única, sem papéis/permissões/atribuição (`OQ-03`): `ItemFila` não tem
  nenhum campo desse tipo — verificado aqui inspecionando os nomes de campo.

E os quatro critérios de aceite de T-67, na parte de `DECISAO_REVISAO`/
`RegistroRevisao` (a prova de `UPDATE`/`DELETE` recusado pelo banco é
`tests/app_aluno/integracao/test_persistencia_revisoes.py`, que exige
Postgres real):

- `AC-27`: autor e data são gravados — verificado aqui pela IMPOSSIBILIDADE
  de construir `RegistroRevisao` sem os dois (não são `Optional`).
- A interface do repositório de revisões não expõe `atualizar`/`remover` —
  verificado sobre o `Protocol` em `tests/app_aluno/integracao/
  test_persistencia_revisoes.py::test_interface_do_repositorio_nao_expoe_
  atualizar_nem_remover` (exige a implementação Postgres); aqui verificamos
  a imutabilidade EM MEMÓRIA do dataclass (`frozen=True`).
- Liberação e reprovação são ambas representáveis por `DECISAO_REVISAO`.

Um `SnapshotOrdem` REAL é produzido pela mesma cadeia do motor já usada por
`tests/app_aluno/test_executor.py` (`caso_completo()` + `executar_calculo`
sobre o adaptador de arquivo) — nunca um dublê que fabrica um snapshot falso.
`dataclasses.replace` varia só `REVISAO_HUMANA_OBRIGATORIA`, isolando a única
variável que estes testes precisam controlar.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.casos.maquina import ESTADO_CASO, Caso
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from app.revisao.fila import (
    CLASSIFICACAO_ERRO,
    DECISAO_REVISAO,
    POLITICA_REVISAO_INTEGRAL_PILOTO,
    ErroRevisaoJaDecidida,
    ItemFila,
    RegistroRevisao,
    e_caso_metodologico_S04,
    entra_na_fila_de_revisao,
    liberar,
    listar_fila_de_revisao,
    montar_item_da_fila,
    reprovar,
)
from engine.estado import EstadoFinanceiro
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.arquivo import RepositorioCasosArquivo, RepositorioEventosCasoArquivo
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_PARAMETROS_VERSAO: str = "1.0.1"
_CASO_ID: str = "caso-teste-t66-fila-revisao"


def _montar_estado() -> EstadoFinanceiro:
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    repositorio = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID=_CASO_ID,
            conta_id="conta-teste-t66",
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
    return repositorio


@pytest.fixture
def repositorio_snapshots(tmp_path: Path) -> RepositorioSnapshotsArquivo:
    return RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")


@pytest.fixture
def repositorio_eventos(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    """`T-91` (`RF-31`/`AC-40`) — trilha de eventos do caso, consumida por
    `liberar`/`reprovar` via `app.casos.progresso.transicionar_e_registrar`."""
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


@pytest.fixture
def snapshot_real(
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> SnapshotOrdem:
    """`SnapshotOrdem` REAL, produzido pela mesma cadeia do motor de
    `tests/app_aluno/test_executor.py` — nenhum campo é fabricado à mão."""
    insumos = ParametrosDoCalculo(
        fonte_parametros=FonteParametrosArquivo(),
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    return executar_calculo(_montar_estado(), insumos)


def test_politica_integral_do_piloto_e_true(snapshot_real: SnapshotOrdem) -> None:
    """A política do piloto (`sdd.config.md` §6, `PEND-06`) é revisar 100%
    dos relatórios — a constante nasce em `True` e não é um cálculo."""
    assert POLITICA_REVISAO_INTEGRAL_PILOTO is True
    del snapshot_real  # fixture só para reaproveitar o setup de `SnapshotOrdem` real


def test_ac25_snapshot_com_campo_do_motor_false_entra_na_fila(
    snapshot_real: SnapshotOrdem,
) -> None:
    """`AC-25`: dado um snapshot com `REVISAO_HUMANA_OBRIGATORIA = False`,
    quando avaliado por `entra_na_fila_de_revisao`, então ele entra na fila
    mesmo assim — a política do piloto manda, não o campo do motor."""
    snapshot_sem_caso_metodologico = dataclasses.replace(
        snapshot_real, REVISAO_HUMANA_OBRIGATORIA=False
    )

    assert entra_na_fila_de_revisao(snapshot_sem_caso_metodologico) is True


def test_snapshot_com_campo_do_motor_true_tambem_entra_na_fila(
    snapshot_real: SnapshotOrdem,
) -> None:
    """A entrada na fila não muda com o campo do motor em `True` — mesma
    condição de entrada, independente do valor de `REVISAO_HUMANA_OBRIGATORIA`
    (prova de que a política, não o campo, decide)."""
    snapshot_caso_metodologico = dataclasses.replace(
        snapshot_real, REVISAO_HUMANA_OBRIGATORIA=True
    )

    assert entra_na_fila_de_revisao(snapshot_caso_metodologico) is True


def test_e_caso_metodologico_s04_le_so_o_campo_do_motor(snapshot_real: SnapshotOrdem) -> None:
    """`e_caso_metodologico_S04` reflete fielmente
    `SnapshotOrdem.REVISAO_HUMANA_OBRIGATORIA` — `True` quando o campo é
    `True`, `False` quando é `False`, sem nenhuma influência da política."""
    snapshot_true = dataclasses.replace(snapshot_real, REVISAO_HUMANA_OBRIGATORIA=True)
    snapshot_false = dataclasses.replace(snapshot_real, REVISAO_HUMANA_OBRIGATORIA=False)

    assert e_caso_metodologico_S04(snapshot_true) is True
    assert e_caso_metodologico_S04(snapshot_false) is False


def test_ac28_item_fila_expoe_os_dois_sinais_separadamente(snapshot_real: SnapshotOrdem) -> None:
    """`AC-28`: um snapshot com `REVISAO_HUMANA_OBRIGATORIA = True`, quando
    exibido na fila, é sinalizado como caso metodológico de `S-04`,
    distinguível de um caso que está na fila apenas pela política — os dois
    sinais aparecem como campos DISTINTOS do mesmo `ItemFila`."""
    snapshot_metodologico = dataclasses.replace(snapshot_real, REVISAO_HUMANA_OBRIGATORIA=True)
    snapshot_so_politica = dataclasses.replace(snapshot_real, REVISAO_HUMANA_OBRIGATORIA=False)

    item_metodologico = montar_item_da_fila(_CASO_ID, snapshot_metodologico)
    item_so_politica = montar_item_da_fila(_CASO_ID, snapshot_so_politica)

    # Ambos entram na fila (política sempre True) — mas só um é metodológico.
    assert item_metodologico.entra_por_politica is True
    assert item_metodologico.e_metodologico is True
    assert item_so_politica.entra_por_politica is True
    assert item_so_politica.e_metodologico is False


def test_item_fila_nao_tem_campo_de_papel_permissao_ou_atribuicao() -> None:
    """`OQ-03` respondida — revisor único implícito: fila única, sem papéis,
    permissões nem atribuição. Nenhum campo de `ItemFila` nomeia isso."""
    nomes_dos_campos = {campo.name for campo in dataclasses.fields(ItemFila)}
    termos_proibidos = ("papel", "role", "permiss", "atribu", "assign")

    for nome_campo in nomes_dos_campos:
        nome_normalizado = nome_campo.lower()
        assert not any(termo in nome_normalizado for termo in termos_proibidos), (
            f"campo {nome_campo!r} de ItemFila parece modelar papel/permissão/atribuição — "
            "OQ-03 fechou por fila única, sem nenhum desses conceitos"
        )


def test_listar_fila_de_revisao_inclui_caso_em_aguardando_revisao(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
) -> None:
    """A fila (consulta, não tabela própria) inclui o caso assim que ele
    entra em `AGUARDANDO_REVISAO` e tem `snapshot_raiz_id` preenchido."""
    repositorio_casos.registrar_snapshot_raiz(_CASO_ID, snapshot_real.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(_CASO_ID, ESTADO_CASO.AGUARDANDO_REVISAO)

    itens = listar_fila_de_revisao([_CASO_ID], repositorio_casos, repositorio_snapshots)

    assert len(itens) == 1
    assert itens[0].CASO_ID == _CASO_ID
    assert itens[0].snapshot.SNAPSHOT_ID == snapshot_real.SNAPSHOT_ID


def test_listar_fila_de_revisao_omite_caso_fora_de_aguardando_revisao(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
) -> None:
    """Um caso que ainda não chegou a `AGUARDANDO_REVISAO` (aqui, ainda em
    `CALCULANDO`, pela fixture) não aparece na fila."""
    itens = listar_fila_de_revisao([_CASO_ID], repositorio_casos, repositorio_snapshots)

    assert itens == ()


def test_listar_fila_de_revisao_omite_caso_inexistente(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_snapshots: RepositorioSnapshotsArquivo,
) -> None:
    """`CASO_ID` desconhecido não derruba a consulta — é só omitido."""
    itens = listar_fila_de_revisao(
        ["caso-que-nao-existe"], repositorio_casos, repositorio_snapshots
    )

    assert itens == ()


# ---------------------------------------------------------------------------
# T-67 — `DECISAO_REVISAO` / `RegistroRevisao` (RF-24, AC-27)
# ---------------------------------------------------------------------------


def test_decisao_revisao_tem_exatamente_liberado_e_reprovado() -> None:
    """Liberação **e** reprovação são ambas registráveis — os dois únicos
    membros do enum, nenhum a mais."""
    assert {membro.value for membro in DECISAO_REVISAO} == {"LIBERADO", "REPROVADO"}


def test_registro_revisao_de_liberacao() -> None:
    """Uma liberação é representável por `RegistroRevisao` com `decisao =
    DECISAO_REVISAO.LIBERADO`, autor e data preenchidos."""
    agora = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    registro = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t67",
        CASO_ID=_CASO_ID,
        decisao=DECISAO_REVISAO.LIBERADO,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        classificacao_erro=None,
        observacao=None,
    )

    assert registro.decisao is DECISAO_REVISAO.LIBERADO
    assert registro.autor == "revisor@piq.invalido"
    assert registro.decidido_em == agora


def test_registro_revisao_de_reprovacao_com_classificacao() -> None:
    """Uma reprovação é representável pelo MESMO tipo, com
    `classificacao_erro` preenchido — domínio fechado nos seis rótulos de
    `CLASSIFICACAO_ERRO` (`RF-26`, `T-72`)."""
    agora = datetime(2026, 3, 2, 14, 30, tzinfo=UTC)
    registro = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t67",
        CASO_ID=_CASO_ID,
        decisao=DECISAO_REVISAO.REPROVADO,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        classificacao_erro=CLASSIFICACAO_ERRO.CALCULO,
        observacao="a ordem projetada diverge do gabarito",
    )

    assert registro.decisao is DECISAO_REVISAO.REPROVADO
    assert registro.classificacao_erro is CLASSIFICACAO_ERRO.CALCULO
    assert registro.observacao == "a ordem projetada diverge do gabarito"


def test_registro_revisao_exige_autor_e_decidido_em_na_construcao() -> None:
    """`AC-27`: autor e data são gravados — verificado aqui pela
    IMPOSSIBILIDADE de construir `RegistroRevisao` sem os dois. Nenhum dos
    dois campos tem valor padrão nem é `Optional`."""
    campos = {campo.name: campo for campo in dataclasses.fields(RegistroRevisao)}

    for nome_campo in ("autor", "decidido_em"):
        campo = campos[nome_campo]
        assert campo.default is dataclasses.MISSING, (
            f"{nome_campo!r} não pode ter valor padrão — AC-27 exige que seja "
            "sempre fornecido explicitamente"
        )


def test_registro_revisao_e_imutavel_em_memoria() -> None:
    """`AC-27`: o registro não pode ser alterado — `frozen=True` faz
    qualquer tentativa de reatribuição de campo levantar `FrozenInstanceError`
    em memória, mesma disciplina de `SnapshotOrdem` (`V-01`)."""
    registro = RegistroRevisao(
        SNAPSHOT_ID="snapshot-teste-t67",
        CASO_ID=_CASO_ID,
        decisao=DECISAO_REVISAO.LIBERADO,
        autor="revisor@piq.invalido",
        decidido_em=datetime(2026, 3, 1, tzinfo=UTC),
        classificacao_erro=None,
        observacao=None,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        registro.autor = "outro-revisor@piq.invalido"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T-68 — `liberar`/`reprovar` (RF-23, RF-24, AC-26, EC-12)
# ---------------------------------------------------------------------------


class _RepositorioRevisoesEmMemoria:
    """Dublê mínimo de `persistencia.app_aluno.revisoes.RepositorioRevisoes`
    — só `gravar`, o único verbo que `liberar`/`reprovar` exigem
    (`RepositorioRevisoesDaDecisao`). Guarda os registros em ordem de
    gravação para os testes inspecionarem quantas chamadas de fato
    persistiram algo."""

    def __init__(self) -> None:
        self.gravados: list[tuple[str, RegistroRevisao]] = []

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        self.gravados.append((revisao_id, registro))


@pytest.fixture
def repositorio_revisoes() -> _RepositorioRevisoesEmMemoria:
    return _RepositorioRevisoesEmMemoria()


def _preparar_caso_aguardando_revisao(
    repositorio_casos: RepositorioCasosArquivo, snapshot: SnapshotOrdem
) -> None:
    repositorio_casos.registrar_snapshot_raiz(_CASO_ID, snapshot.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(_CASO_ID, ESTADO_CASO.AGUARDANDO_REVISAO)


def test_liberar_grava_decisao_e_so_entao_preenche_snapshot_liberado_id(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_revisoes: _RepositorioRevisoesEmMemoria,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Critério 1: liberar registra a decisão e só então preenche
    `snapshot_liberado_id` — verificado pela ORDEM observável: o registro
    de revisão já está gravado (com `decisao=LIBERADO`) e o `Caso` devolvido
    já está em `PLANO_LIBERADO` com `snapshot_liberado_id` preenchido."""
    _preparar_caso_aguardando_revisao(repositorio_casos, snapshot_real)
    agora = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

    caso_liberado = liberar(
        revisao_id="revisao-t68-liberacao",
        caso_id=_CASO_ID,
        snapshot=snapshot_real,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )

    assert len(repositorio_revisoes.gravados) == 1
    revisao_id_gravada, registro_gravado = repositorio_revisoes.gravados[0]
    assert revisao_id_gravada == "revisao-t68-liberacao"
    assert registro_gravado.decisao is DECISAO_REVISAO.LIBERADO
    assert registro_gravado.autor == "revisor@piq.invalido"
    assert registro_gravado.decidido_em == agora
    assert registro_gravado.SNAPSHOT_ID == snapshot_real.SNAPSHOT_ID

    assert caso_liberado.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_liberado.snapshot_liberado_id == snapshot_real.SNAPSHOT_ID

    # A releitura do repositório confirma que o efeito foi persistido, não
    # só devolvido em memória pela chamada.
    caso_persistido = repositorio_casos.buscar(_CASO_ID)
    assert caso_persistido is not None
    assert caso_persistido.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_persistido.snapshot_liberado_id == snapshot_real.SNAPSHOT_ID


def test_reprovar_registra_autor_e_data_nao_libera_e_nao_toca_snapshot_liberado_ec12(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_revisoes: _RepositorioRevisoesEmMemoria,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Critério 2 (`EC-12`): reprovar registra autor e data, não libera nada
    ao aluno (`estado` vai a `REPROVADO_EM_REVISAO`, nunca `PLANO_LIBERADO`,
    e `snapshot_liberado_id` permanece `None`) e o snapshot fica inalterado —
    esta função nunca grava em `RepositorioSnapshots`."""
    _preparar_caso_aguardando_revisao(repositorio_casos, snapshot_real)
    agora = datetime(2026, 4, 2, 14, 0, tzinfo=UTC)
    snapshot_antes = dataclasses.replace(snapshot_real)

    caso_reprovado = reprovar(
        revisao_id="revisao-t68-reprovacao",
        caso_id=_CASO_ID,
        snapshot=snapshot_real,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        classificacao_erro=CLASSIFICACAO_ERRO.CALCULO,
        observacao="ordem projetada diverge do gabarito",
    )

    assert len(repositorio_revisoes.gravados) == 1
    _, registro_gravado = repositorio_revisoes.gravados[0]
    assert registro_gravado.decisao is DECISAO_REVISAO.REPROVADO
    assert registro_gravado.autor == "revisor@piq.invalido"
    assert registro_gravado.decidido_em == agora
    assert registro_gravado.classificacao_erro is CLASSIFICACAO_ERRO.CALCULO

    assert caso_reprovado.estado is ESTADO_CASO.REPROVADO_EM_REVISAO
    assert caso_reprovado.snapshot_liberado_id is None

    # O snapshot em si nunca é tocado — comparação de igualdade estrutural
    # completa contra uma cópia tirada ANTES da chamada.
    assert snapshot_real == snapshot_antes


def test_liberar_duas_vezes_o_mesmo_snapshot_e_recusado_nao_idempotente(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_revisoes: _RepositorioRevisoesEmMemoria,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Critério 3: liberar duas vezes o mesmo snapshot é RECUSADO (decisão
    documentada na docstring do módulo), nunca produz dois registros que
    ambos aparentem ter sido aplicados. A segunda chamada levanta
    `ErroRevisaoJaDecidida` e não altera o `Caso` já liberado pela
    primeira."""
    _preparar_caso_aguardando_revisao(repositorio_casos, snapshot_real)
    agora = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)

    caso_apos_primeira = liberar(
        revisao_id="revisao-t68-primeira",
        caso_id=_CASO_ID,
        snapshot=snapshot_real,
        autor="revisor@piq.invalido",
        decidido_em=agora,
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )
    assert caso_apos_primeira.estado is ESTADO_CASO.PLANO_LIBERADO

    with pytest.raises(ErroRevisaoJaDecidida) as excinfo:
        liberar(
            revisao_id="revisao-t68-segunda",
            caso_id=_CASO_ID,
            snapshot=snapshot_real,
            autor="outro-revisor@piq.invalido",
            decidido_em=datetime(2026, 4, 3, 11, 0, tzinfo=UTC),
            repositorio_revisoes=repositorio_revisoes,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
        )
    assert excinfo.value.caso_id == _CASO_ID

    # O caso continua exatamente como a PRIMEIRA liberação o deixou —
    # nenhum campo foi sobrescrito pela segunda tentativa recusada.
    caso_final = repositorio_casos.buscar(_CASO_ID)
    assert caso_final is not None
    assert caso_final.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_final.snapshot_liberado_id == snapshot_real.SNAPSHOT_ID


def test_liberar_apos_reprovar_e_recusado(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_revisoes: _RepositorioRevisoesEmMemoria,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Extensão do critério 3: uma vez que o caso saiu de
    `AGUARDANDO_REVISAO` por REPROVAÇÃO, uma tentativa de LIBERAR o mesmo
    caso também é recusada — não existe transição de volta a
    `AGUARDANDO_REVISAO` na máquina (`app/casos/maquina.py`)."""
    _preparar_caso_aguardando_revisao(repositorio_casos, snapshot_real)
    reprovar(
        revisao_id="revisao-t68-reprovacao-previa",
        caso_id=_CASO_ID,
        snapshot=snapshot_real,
        autor="revisor@piq.invalido",
        decidido_em=datetime(2026, 4, 4, 9, 0, tzinfo=UTC),
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )

    with pytest.raises(ErroRevisaoJaDecidida):
        liberar(
            revisao_id="revisao-t68-liberacao-tardia",
            caso_id=_CASO_ID,
            snapshot=snapshot_real,
            autor="revisor@piq.invalido",
            decidido_em=datetime(2026, 4, 4, 10, 0, tzinfo=UTC),
            repositorio_revisoes=repositorio_revisoes,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
        )

    caso_final = repositorio_casos.buscar(_CASO_ID)
    assert caso_final is not None
    assert caso_final.estado is ESTADO_CASO.REPROVADO_EM_REVISAO
    assert caso_final.snapshot_liberado_id is None


def test_liberar_e_reprovar_nunca_gravam_em_repositorio_de_snapshots(
    snapshot_real: SnapshotOrdem,
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_revisoes: _RepositorioRevisoesEmMemoria,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Critério 4: nenhum caminho de código edita um snapshot como parte da
    revisão — verificado por ASSINATURA: nem `liberar` nem `reprovar`
    recebem (e portanto não podem chamar) nenhum `RepositorioSnapshots`."""
    assinatura_liberar = inspect.signature(liberar)
    assinatura_reprovar = inspect.signature(reprovar)

    for nome_parametro in assinatura_liberar.parameters:
        assert "snapshot" not in nome_parametro or nome_parametro == "snapshot", (
            f"parâmetro inesperado relacionado a snapshot em `liberar`: {nome_parametro!r}"
        )
    for nome_parametro in ("repositorio_snapshots", "repositorio_de_snapshots"):
        assert nome_parametro not in assinatura_liberar.parameters
        assert nome_parametro not in assinatura_reprovar.parameters

    # Prova adicional, por comportamento: liberar/reprovar completam sem
    # exigir nenhum repositório de snapshots injetado — a única referência a
    # `snapshot` em ambas as funções é de LEITURA (`snapshot.SNAPSHOT_ID`).
    _preparar_caso_aguardando_revisao(repositorio_casos, snapshot_real)
    liberar(
        revisao_id="revisao-t68-sem-repo-snapshot",
        caso_id=_CASO_ID,
        snapshot=snapshot_real,
        autor="revisor@piq.invalido",
        decidido_em=datetime(2026, 4, 5, 9, 0, tzinfo=UTC),
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )
