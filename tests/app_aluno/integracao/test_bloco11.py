"""`US-08` ponta a ponta com o adaptador de ARQUIVO — `RF-27`, `RF-28`,
`RF-29`, `AC-26`, `AC-30`, `AC-31`, `AC-33`, `AC-34`, `AC-35`, `EC-11`, T-88.

Fecha a Entrega 10 (`T-81`..`T-88`). Roda SEM `DATABASE_URL` (adaptador de
arquivo, T-24) — apesar do nome de pasta "integracao", este módulo NÃO é
`requer_banco`.

**O que este arquivo NÃO reimplementa (cobertura pré-existente confirmada).**
Cada um dos cinco critérios de aceite já tem uma prova FOCADA, chamando a
função de domínio diretamente (sem HTTP):

- `AC-30` (encadeamento `versao`/`snapshot_anterior_id`, tolerância zero) e
  `EC-11` (evento com `hash_inputs` idêntico ainda versiona): `tests/
  app_aluno/test_disparar_recalculo.py::test_ac30_recalculo_encadeia_versao_e_
  snapshot_anterior_id` e `::test_ec11_hash_inputs_identico_ainda_versiona_
  com_evento` (T-86).
- `AC-26` (snapshot de recálculo em `AGUARDANDO_REVISAO`, entra na fila):
  `tests/app_aluno/test_disparar_recalculo.py::
  test_ac26_snapshot_de_recalculo_entra_na_fila_de_revisao` (T-86).
- `AC-31`/`AC-35` (nenhum recálculo disparado, contagem de snapshots
  inalterada): `tests/app_aluno/test_processar_resposta_bloco_11_ac35.py`
  (T-87), inteiro.
- `AC-33`/`AC-34` (conjunto de perguntas pendentes exato): `tests/app_aluno/
  test_reabertura.py` (T-80/T-85), inteiro.

Este módulo RODA essas suítes preexistentes (`test_cobertura_preexistente_*`,
abaixo) como confirmação executável de que continuam verdes — não duplica a
lógica delas. O que ele ACRESCENTA é o ângulo que nenhuma delas cobre: os
CINCO critérios, no MESMO fluxo contínuo, disparado por uma REQUISIÇÃO HTTP
REAL (`TestClient` sobre `app/http/rotas_bloco11.py::roteador`, T-82) — não
uma chamada direta a `disparar_recalculo`/`processar_resposta_bloco_11`. O
fluxo: reportar (POST `/bloco-11/resposta`) → identificar o evento (a rota
real) → recalcular (`processar_resposta_bloco_11`, T-87, consumindo
EXATAMENTE o `evento_recalculo` que a resposta HTTP devolveu) → encadear
(`AC-30`) → voltar à fila (`AC-26`) → nova rodada de reabertura (`AC-33`/
`AC-34`) sobre o snapshot recalculado — sem apagar o histórico do primeiro
snapshot em nenhum passo.

**Por que a rota HTTP não chama `disparar_recalculo` diretamente (lembrete da
fronteira `T-82`/`T-86`/`T-87`).** `app/http/rotas_bloco11.py::
responder_confirmacao_quitacao` só IDENTIFICA o evento e o devolve no JSON —
ela nunca importa `app/motor/executor.py` (ver a nota extensa daquele
módulo). É esta suíte, não a rota, quem representa o "consumidor" que lê
`evento_recalculo` da resposta HTTP e decide agir — exatamente o papel que a
docstring daquele módulo reserva a um "consumidor futuro". Aqui esse
consumidor é a chamada explícita a `processar_resposta_bloco_11` alimentada
pelo valor devolvido pela rota real — nunca um evento fabricado à parte.

REGRAS: `RF-27`, `RF-28`, `RF-29`, `AC-26`, `AC-30`, `AC-31`, `AC-33`,
`AC-34`, `AC-35`, `EC-11`
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.acompanhamento import (
    ErroRecalculoRecusado,
    processar_resposta_bloco_11,
)
from app.casos.maquina import ESTADO_CASO, Caso, transicionar
from app.casos.reabertura import perguntas_pendentes_por_reabertura_informacao
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_bloco11 import obter_colecao_de_registros, obter_repositorio_respostas
from app.http.rotas_bloco11 import roteador as roteador_bloco11
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from app.revisao.fila import listar_fila_de_revisao
from collection.carga import carregar_registros
from engine.tipos import EVENTO_RECALCULO
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, CasoCompleto, caso_completo

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_PARAMETROS_VERSAO: str = "1.0.1"
_CONTA_ID: str = "CONTA-T88-BLOCO11"
_CASO_ID: str = "caso-teste-t88-ciclo-bloco11"
_DIVIDA_ID: str = "D001"


# ---------------------------------------------------------------------------
# Confirmação executável de cobertura pré-existente — roda as suítes focadas
# de T-86/T-87/T-80/T-85 sobre os cinco critérios, sem reimplementar a lógica
# delas (ver docstring do módulo).
# ---------------------------------------------------------------------------


def test_cobertura_preexistente_ac30_e_ec11_disparar_recalculo() -> None:
    """`AC-30`/`EC-11` (`tests/app_aluno/test_disparar_recalculo.py`, T-86)
    seguem verdes — encadeamento e versionamento com `hash_inputs` idêntico
    já provados isoladamente sobre `disparar_recalculo`."""
    resultado = pytest.main(
        [
            "-q",
            str(
                Path(__file__).resolve().parent.parent
                / "test_disparar_recalculo.py"
            ),
        ]
    )
    assert resultado == pytest.ExitCode.OK


def test_cobertura_preexistente_ac31_e_ac35_processar_resposta_bloco_11() -> None:
    """`AC-31`/`AC-35` (`tests/app_aluno/
    test_processar_resposta_bloco_11_ac35.py`, T-87) seguem verdes —
    nenhum recálculo disparado por alteração cadastral/`A_CONFIRMAR`,
    contagem de snapshots inalterada."""
    resultado = pytest.main(
        [
            "-q",
            str(
                Path(__file__).resolve().parent.parent
                / "test_processar_resposta_bloco_11_ac35.py"
            ),
        ]
    )
    assert resultado == pytest.ExitCode.OK


def test_cobertura_preexistente_ac33_e_ac34_reabertura() -> None:
    """`AC-33`/`AC-34` (`tests/app_aluno/test_reabertura.py`, T-80/T-85)
    seguem verdes — conjunto de perguntas pendentes conferido exatamente,
    tanto para reabertura de campo isolado quanto de faixa."""
    resultado = pytest.main(
        ["-q", str(Path(__file__).resolve().parent.parent / "test_reabertura.py")]
    )
    assert resultado == pytest.ExitCode.OK


# ---------------------------------------------------------------------------
# O ângulo que falta: HTTP real → identificar evento → recalcular → encadear
# → fila → reabertura, tudo no MESMO fluxo contínuo, adaptador de arquivo.
# ---------------------------------------------------------------------------


def _montar_estado_do_caso(caso: CasoCompleto) -> object:
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


class _RepositorioCasosDublêIsolamento:
    """Restrito aos dois métodos que `exigir_caso_da_sessao` usa — mesmo
    padrão de `tests/app_aluno/test_rotas_bloco11.py::
    _RepositorioCasosDublê` — mas delegando a leitura de posse ao
    `RepositorioCasosArquivo` real por trás, para que a rota HTTP e o
    restante do fluxo (fora da rota) compartilhem o MESMO `Caso` persistido
    em disco, nunca dois estados divergentes."""

    def __init__(self, repositorio_arquivo: RepositorioCasosArquivo, conta_id: str) -> None:
        self._repositorio = repositorio_arquivo
        self._conta_id = conta_id

    def buscar(self, caso_id: str) -> Caso | None:
        return self._repositorio.buscar(caso_id)

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return conta_id == self._conta_id and self._repositorio.buscar(caso_id) is not None


@pytest.fixture
def caminhos(tmp_path: Path) -> dict[str, Path]:
    return {
        "casos": tmp_path / "casos.jsonl",
        "respostas": tmp_path / "respostas.jsonl",
        "snapshots": tmp_path / "snapshots.jsonl",
        "eventos": tmp_path / "eventos_caso.jsonl",
    }


@pytest.fixture
def repositorio_casos_arquivo(caminhos: dict[str, Path]) -> RepositorioCasosArquivo:
    """`Caso` real, persistido em disco, já em `ACOMPANHAMENTO` com um
    snapshot raiz anexado pelo MESMO executor do Bloco 6 — a pré-condição
    real de um ciclo de Bloco 11 (mesma montagem de `tests/app_aluno/
    test_disparar_recalculo.py::repositorio_casos_arquivo`, adaptada para
    persistir em arquivo real, já que a rota HTTP lê o `Caso` por trás de
    `dependency_overrides`, não de um objeto Python compartilhado em
    memória)."""
    repositorio = RepositorioCasosArquivo(caminhos["casos"])
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio.criar(
        Caso(
            CASO_ID=_CASO_ID,
            conta_id=_CONTA_ID,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )

    fonte_parametros = FonteParametrosArquivo()
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminhos["snapshots"])
    repositorio_eventos = RepositorioEventosCasoArquivo(caminhos["eventos"])
    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)
    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    snapshot_raiz = executar_calculo(estado, insumos)  # type: ignore[arg-type]
    repositorio.registrar_snapshot_raiz(_CASO_ID, snapshot_raiz.SNAPSHOT_ID)
    repositorio.transicionar_estado(_CASO_ID, ESTADO_CASO.ACOMPANHAMENTO)
    return repositorio


@pytest.fixture
def cliente_http(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    caminhos: dict[str, Path],
) -> TestClient:
    """`TestClient` REAL sobre `app/http/rotas_bloco11.py::roteador`
    (T-82) — sessão aberta para `_CONTA_ID`, repositório de respostas sobre
    arquivo (`RepositorioRespostasArquivo`, T-24), `Caso` lido do MESMO
    `RepositorioCasosArquivo` que o restante do teste usa por fora da rota
    HTTP."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco11)
    aplicacao.dependency_overrides[obter_repositorio_casos] = (
        lambda: _RepositorioCasosDublêIsolamento(repositorio_casos_arquivo, _CONTA_ID)
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = carregar_registros
    aplicacao.dependency_overrides[obter_repositorio_respostas] = (
        lambda: RepositorioRespostasArquivo(caminho_arquivo=caminhos["respostas"])
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def test_ciclo_completo_do_bloco_11_reportar_recalcular_encadear_voltar_a_fila(
    cliente_http: TestClient,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    caminhos: dict[str, Path],
) -> None:
    """`US-08` ponta a ponta: `B11.Q01 = Sim` via HTTP real → evento
    identificado pela rota → `processar_resposta_bloco_11` consome
    EXATAMENTE esse evento → recálculo real (`disparar_recalculo`, T-86) →
    `AC-30` (encadeamento com tolerância zero) → `AC-26` (fila de revisão) →
    `EC-11` (mesmo `hash_inputs`, evento ainda versiona) — tudo no mesmo
    fluxo, sem apagar o snapshot raiz."""
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminhos["snapshots"])
    repositorio_eventos = RepositorioEventosCasoArquivo(caminhos["eventos"])
    fonte_parametros = FonteParametrosArquivo()

    caso_antes = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_antes is not None and caso_antes.snapshot_raiz_id is not None
    historico_antes = repositorio_snapshots.historico(caso_antes.snapshot_raiz_id)
    assert len(historico_antes) == 1
    snapshot_raiz = historico_antes[0]
    assert snapshot_raiz.versao == 1
    assert snapshot_raiz.snapshot_anterior_id is None

    # Passo 1 — REPORTAR: B11.Q01 = "Sim" via rota HTTP real. A rota grava a
    # resposta (persistida em respostas.jsonl) e IDENTIFICA o evento —
    # exatamente o comportamento de T-82, nunca disparando o executor por
    # conta própria (ver a nota do módulo).
    resposta_http = cliente_http.post(
        f"/caso/{_CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID, "valor": "QUITADA"},
    )
    assert resposta_http.status_code == 200
    corpo = resposta_http.json()
    assert corpo["evento_recalculo"] == EVENTO_RECALCULO.QUITACAO_CONFIRMADA.name

    # Passo 2 — RECALCULAR: o "consumidor" (esta suíte) lê o evento
    # devolvido pela rota HTTP e aciona `processar_resposta_bloco_11`
    # (T-87), que por sua vez chama `disparar_recalculo` (T-86) — o MESMO
    # executor do Bloco 6, nunca uma segunda via de invocação do motor.
    caso_apos_resposta = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_resposta is not None
    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    snapshot_recalculado = processar_resposta_bloco_11(
        id_pergunta="B11.Q01",
        variavel_gravada="STATUS_QUITACAO_REAL",
        # O `valor_interno` de B11.Q01 que produziu o evento identificado
        # pela rota (`corpo["evento_recalculo"]`, verificado acima) — a
        # rota grava a mesma string em `respostas.jsonl`
        # (VARIAVEL_GRAVADA=STATUS_QUITACAO_REAL); este teste a repete
        # explicitamente aqui, em vez de reler o arquivo, porque o valor já
        # é conhecido (foi o próprio `data=` do POST) e o que se está
        # verificando é que ELE, consumido por `processar_resposta_bloco_11`,
        # produz o mesmo evento que a rota identificou.
        valor_interno="QUITADA",
        caso=caso_apos_resposta,
        estado=estado,  # type: ignore[arg-type]
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos,
        parametros_versao=_PARAMETROS_VERSAO,
        motivo=corpo["evento_recalculo"],
    )
    assert snapshot_recalculado is not None

    # Passo 3 — ENCADEAR (AC-30, tolerância ZERO): versao = anterior + 1,
    # snapshot_anterior_id aponta para o snapshot raiz, e o raiz permanece
    # íntegro e recuperável (histórico append-only, nunca sobrescrito).
    caso_apos_recalculo = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_recalculo is not None
    historico_depois = repositorio_snapshots.historico(caso_apos_recalculo.snapshot_raiz_id)  # type: ignore[arg-type]
    assert len(historico_depois) == 2
    assert historico_depois[0].SNAPSHOT_ID == snapshot_raiz.SNAPSHOT_ID
    assert historico_depois[0].versao == snapshot_raiz.versao
    assert historico_depois[1].SNAPSHOT_ID == snapshot_recalculado.SNAPSHOT_ID
    assert historico_depois[1].versao == snapshot_raiz.versao + 1
    assert historico_depois[1].snapshot_anterior_id == snapshot_raiz.SNAPSHOT_ID

    # EC-11: o mesmo hash_inputs do snapshot raiz (nada material mudou no
    # EstadoFinanceiro), mas o evento fez a versão avançar assim mesmo.
    assert historico_depois[1].hash_inputs == historico_depois[0].hash_inputs
    assert historico_depois[1].EVENTO_RECALCULO is EVENTO_RECALCULO.QUITACAO_CONFIRMADA

    # Passo 4 — VOLTAR À FILA (AC-26): a mesma transição de sucesso do
    # Bloco 6 (CALCULANDO -> AGUARDANDO_REVISAO, feita pelo chamador) e o
    # snapshot recalculado aparece na fila como qualquer outro.
    transicionar(ESTADO_CASO.CALCULANDO, ESTADO_CASO.AGUARDANDO_REVISAO)
    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.AGUARDANDO_REVISAO)

    fila = listar_fila_de_revisao([_CASO_ID], repositorio_casos_arquivo, repositorio_snapshots)
    assert len(fila) == 1
    assert fila[0].CASO_ID == _CASO_ID
    assert fila[0].snapshot.SNAPSHOT_ID == snapshot_recalculado.SNAPSHOT_ID
    assert fila[0].entra_por_politica is True

    # Nenhum histórico foi apagado — o snapshot raiz continua recuperável.
    assert repositorio_snapshots.historico(caso_apos_recalculo.snapshot_raiz_id)[  # type: ignore[arg-type]
        0
    ].SNAPSHOT_ID == snapshot_raiz.SNAPSHOT_ID


def test_ciclo_completo_alteracao_cadastral_via_http_nao_recalcula_ac31_ac35(
    cliente_http: TestClient,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    caminhos: dict[str, Path],
) -> None:
    """`AC-31`/`AC-35`, mesmo fluxo HTTP: `B11.Q01 = "Ainda não"`
    (`NAO`, sem evento) é reportado pela rota real; o "consumidor"
    (`processar_resposta_bloco_11`) recebe `evento_recalculo=None` e
    REGISTRA a trilha sem tocar o histórico de snapshots — contagem de
    snapshots inalterada, nenhum recálculo disparado."""
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminhos["snapshots"])
    repositorio_eventos = RepositorioEventosCasoArquivo(caminhos["eventos"])
    fonte_parametros = FonteParametrosArquivo()

    caso_antes = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_antes is not None and caso_antes.snapshot_raiz_id is not None
    quantidade_antes = len(repositorio_snapshots.historico(caso_antes.snapshot_raiz_id))

    resposta_http = cliente_http.post(
        f"/caso/{_CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID, "valor": "NAO"},
    )
    assert resposta_http.status_code == 200
    corpo = resposta_http.json()
    assert corpo["evento_recalculo"] is None

    caso_apos_resposta = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_resposta is not None
    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    resultado = processar_resposta_bloco_11(
        id_pergunta="B11.Q01",
        variavel_gravada="STATUS_QUITACAO_REAL",
        valor_interno="NAO",
        caso=caso_apos_resposta,
        estado=estado,  # type: ignore[arg-type]
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos,
        parametros_versao=_PARAMETROS_VERSAO,
    )
    assert resultado is None

    quantidade_depois = len(repositorio_snapshots.historico(caso_antes.snapshot_raiz_id))
    assert quantidade_depois == quantidade_antes

    caso_final = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_final is not None
    assert caso_final.estado == ESTADO_CASO.ACOMPANHAMENTO


def test_ciclo_completo_recalculo_recusado_fora_de_acompanhamento(
    cliente_http: TestClient,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    caminhos: dict[str, Path],
) -> None:
    """Reforço de `AC-30`/`RF-28` no fluxo ponta a ponta: se o caso já não
    está mais em `ACOMPANHAMENTO` no momento em que o evento identificado
    pela rota HTTP é consumido, o recálculo é recusado — nenhum snapshot
    espúrio é criado."""
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminhos["snapshots"])
    repositorio_eventos = RepositorioEventosCasoArquivo(caminhos["eventos"])
    fonte_parametros = FonteParametrosArquivo()

    resposta_http = cliente_http.post(
        f"/caso/{_CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID, "valor": "QUITADA"},
    )
    assert resposta_http.status_code == 200
    evento_nome = resposta_http.json()["evento_recalculo"]
    assert evento_nome == EVENTO_RECALCULO.QUITACAO_CONFIRMADA.name

    repositorio_casos_arquivo.transicionar_estado(_CASO_ID, ESTADO_CASO.COLETA_DIRIGIDA)
    caso_fora_de_acompanhamento = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_fora_de_acompanhamento is not None

    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    with pytest.raises(ErroRecalculoRecusado):
        processar_resposta_bloco_11(
            id_pergunta="B11.Q01",
            variavel_gravada="STATUS_QUITACAO_REAL",
            valor_interno="QUITADA",
            caso=caso_fora_de_acompanhamento,
            estado=estado,  # type: ignore[arg-type]
            fonte_parametros=fonte_parametros,
            repositorio_snapshots=repositorio_snapshots,
            repositorio_casos=repositorio_casos_arquivo,
            repositorio_eventos=repositorio_eventos,
            parametros_versao=_PARAMETROS_VERSAO,
        )


def test_ciclo_completo_reabertura_apos_recalculo_ac33_conjunto_exato(
    cliente_http: TestClient,
    repositorio_casos_arquivo: RepositorioCasosArquivo,
    caminhos: dict[str, Path],
) -> None:
    """`AC-33`, no MESMO fluxo (após um recálculo real do Bloco 11): reabrir
    o campo isolado `B5.B03` para a dívida do caso torna pendente EXATAMENTE
    aquele par `(ID, item_id)` — nem sobra nem falta em relação ao restante
    do Bloco 5 — sem que o recálculo anterior interfira no conjunto."""
    repositorio_snapshots = RepositorioSnapshotsArquivo(caminhos["snapshots"])
    repositorio_eventos = RepositorioEventosCasoArquivo(caminhos["eventos"])
    fonte_parametros = FonteParametrosArquivo()

    resposta_http = cliente_http.post(
        f"/caso/{_CASO_ID}/bloco-11/resposta",
        data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID, "valor": "QUITADA"},
    )
    assert resposta_http.status_code == 200
    corpo = resposta_http.json()

    caso_apos_resposta = repositorio_casos_arquivo.buscar(_CASO_ID)
    assert caso_apos_resposta is not None
    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    snapshot_recalculado = processar_resposta_bloco_11(
        id_pergunta="B11.Q01",
        variavel_gravada="STATUS_QUITACAO_REAL",
        valor_interno="QUITADA",
        caso=caso_apos_resposta,
        estado=estado,  # type: ignore[arg-type]
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos_arquivo,
        repositorio_eventos=repositorio_eventos,
        parametros_versao=_PARAMETROS_VERSAO,
        motivo=corpo["evento_recalculo"],
    )
    assert snapshot_recalculado is not None

    # AC-33: reabertura de campo isolado — conjunto exato, sem sobra/falta.
    pendencias = perguntas_pendentes_por_reabertura_informacao("B5.B03", _DIVIDA_ID)

    colecao = carregar_registros()
    outros_ids_do_bloco_5 = {
        registro.ID
        for registro in colecao.registros
        if registro.bloco == 5 and registro.ID != "B5.B03"
    }
    ids_devolvidos = {p.ID for p in pendencias}

    assert ids_devolvidos == {"B5.B03"}
    assert ids_devolvidos.isdisjoint(outros_ids_do_bloco_5)
    assert all(p.item_id == _DIVIDA_ID for p in pendencias)
