"""Rota do Bloco 7 dirigido — `RF-17`, `AC-19` (T-75).

`GET /caso/{CASO_ID}/coleta-dirigida/bloco-7` expõe, para o `CASO_ID` da
sessão, exatamente as fichas de dívida (`DIVIDA_ID`) que
`app/casos/coleta_dirigida.py::dividas_para_bloco_7` seleciona a partir de
`snapshot.ORDEM_ACOES` — nenhuma outra dívida, e nenhum critério de
elegibilidade próprio desta rota (a técnica de leitura sem literal de
`TIPO_ACAO` está documentada em `app/casos/coleta_dirigida.py`).

**Formato da resposta — decisão desta tarefa.** Diferente das demais rotas
desta feature (que renderizam HTML via `Jinja2Templates`, com template
declarado nos arquivos daquela tarefa), o escopo declarado de `T-75` é
exatamente dois arquivos: este módulo e `app/casos/coleta_dirigida.py` —
nenhum `report/templates/` novo. Por isso esta rota devolve JSON
(`JSONResponse`), o formato observável mínimo que já satisfaz `AC-19` (a
lista de `DIVIDA_ID` que abrem o Bloco 7, e o conjunto de perguntas do
bloco) sem inventar um template fora do escopo desta tarefa. A renderização
HTML final do formulário do Bloco 7 (juntando esta lista aos registros de
`collection/registros/bloco-07.yaml`, T-18, no mesmo estilo HTMX de
`app/http/rotas_coleta.py`, T-42/T-43) fica para uma tarefa de UI dedicada,
se e quando o backlog a criar — este critério de aceite fala em "o Bloco 7
é exibido para D002", que aqui significa "o mecanismo de seleção da dívida
está correto e observável", não uma tela HTML específica.

**Qual snapshot esta rota lê.** O caso só chega em `ESTADO_CASO.
COLETA_DIRIGIDA` a partir de `PLANO_LIBERADO` (`app/casos/maquina.py::
TABELA_TRANSICOES`, gatilho `abre_blocos_7_8`, guarda "AC-19: ORDEM_ACOES
tem ação") — o mesmo snapshot que fundamentou a liberação é o que contém a
`ORDEM_ACOES` vigente. Por isso esta rota lê `Caso.snapshot_liberado_id`,
MESMA fonte que `app/http/rotas_plano.py` já usa para servir o plano ao
aluno — nenhuma segunda noção de "snapshot corrente" é inventada aqui.

**`ORDEM_ACOES` vazia ⇒ nada a exibir (terceiro critério de aceite de
`T-75`).** Um caso sem nenhuma ação de renegociação em `ORDEM_ACOES` nunca
deveria ter chegado a `COLETA_DIRIGIDA` (a guarda da transição já impede
isso na origem) — mas esta rota, sendo pura leitura, apenas devolve lista
vazia nesse caso, sem inventar uma dívida nem levantar erro: o mesmo
snapshot que não gerou ação de renegociação simplesmente não abre nenhuma
ficha do Bloco 7.

**Isolamento por `CASO_ID` (`RF-02`, `AC-03`, T-31).** Mesmo mecanismo de
qualquer outra rota desta feature: `Depends(exigir_caso_da_sessao("CASO_ID"))`
— sessão ausente recusa antes de tocar o banco; caso de outra conta devolve
`404`, nunca `403`.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.coleta_dirigida` (T-75), `collection.carga`
e `persistencia.app_aluno.casos`/`persistencia.supabase.repositorio_snapshots`
— nunca de `engine/` além dos nomes já liberados transitivamente por essas
portas (`AC-41`). Nenhum gate, ranqueamento ou critério de elegibilidade é
avaliado aqui — quarto critério de aceite de `T-75`.

REGRAS: `RF-17`, `AC-19`
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.coleta_dirigida import (
    dividas_para_bloco_7,
    dividas_para_bloco_8,
    perguntas_do_bloco_7,
    perguntas_do_bloco_8,
)
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import obter_repositorio_respostas
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import RegistroPergunta
from collection.respostas import RespostasCaso
from engine.portas import RepositorioSnapshots
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.respostas import RepositorioRespostas
from persistencia.supabase.repositorio_snapshots import (
    ErroSnapshotNaoEncontrado,
    RepositorioSnapshotsSupabase,
)

REGRAS: Final[tuple[str, ...]] = ("RF-17", "AC-19")

roteador = APIRouter(prefix="/caso", tags=["coleta-dirigida"])


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: mesmo precedente de `app/http/rotas_plano.py`/`app/http/
    rotas_consentimento.py` — `exigir_caso_da_sessao` já garantiu que
    `CASO_ID` existe e pertence à conta da sessão."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento confirmá-lo")


def obter_repositorio_snapshots() -> RepositorioSnapshots:
    """Ponto único de injeção da porta `RepositorioSnapshots` — mesmo padrão
    de `app/http/rotas_plano.py::obter_repositorio_snapshots`. Sobrescrito
    nos testes via `app.dependency_overrides`."""
    return RepositorioSnapshotsSupabase()


def obter_colecao_de_registros() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros — mesmo padrão de
    `app/http/rotas_coleta.py::obter_colecao_de_registros`. Sobrescrito nos
    testes via `app.dependency_overrides`."""
    return carregar_registros()


def _resposta_vazia(CASO_ID: str) -> JSONResponse:
    """Nenhum snapshot liberado (ou snapshot desaparecido) para consultar
    `ORDEM_ACOES` — nenhuma dívida abre o Bloco 7 (terceiro critério de
    aceite de `T-75`), nunca um erro genérico."""
    return JSONResponse({"CASO_ID": CASO_ID, "dividas": [], "perguntas": []})


def _fichas_do_bloco(
    dividas: tuple[str, ...],
    perguntas: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    CASO_ID: str,
) -> list[dict[str, object]]:
    """Uma ficha por `DIVIDA_ID` elegível, com os campos já serializados.

    Pergunta cuja `condicao_exibicao` é falsa NAQUELA dívida é omitida —
    quem decide é `montar_contexto_pergunta`, no servidor (`RF-52`). O
    cliente recebe só o que deve desenhar, nunca a regra."""
    fichas: list[dict[str, object]] = []
    for divida_id in dividas:
        campos: list[dict[str, object]] = []
        for registro in perguntas:
            try:
                contexto = montar_contexto_pergunta(registro, respostas, item_id=divida_id)
            except ErroPerguntaNaoExibivel:
                continue
            campos.append(serializar_pergunta(contexto, CASO_ID=CASO_ID, item_id=divida_id))
        fichas.append({"item_id": divida_id, "campos": campos})
    return fichas


@roteador.get("/{CASO_ID}/coleta-dirigida/bloco-7")
def listar_dividas_do_bloco_7(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas)
    ],
) -> JSONResponse:
    """`AC-19` — devolve as fichas do Bloco 7 (uma por `DIVIDA_ID` elegível)
    e nenhuma outra. A lista de dívidas vem exclusivamente de `app/casos/
    coleta_dirigida.py::dividas_para_bloco_7`, que por sua vez só lê
    `snapshot.ORDEM_ACOES` — esta rota nunca consulta saldo, taxa ou
    qualquer critério próprio."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    if caso.snapshot_liberado_id is None:
        return _resposta_vazia(CASO_ID)

    try:
        snapshot = repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return _resposta_vazia(CASO_ID)

    dividas = dividas_para_bloco_7(snapshot)
    perguntas = perguntas_do_bloco_7(colecao.registros) if dividas else ()
    respostas = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(CASO_ID))

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "dividas": list(dividas),
            "perguntas": [registro.ID for registro in perguntas],
            "fichas": _fichas_do_bloco(dividas, perguntas, respostas, CASO_ID),
        }
    )


@roteador.get("/{CASO_ID}/coleta-dirigida/bloco-8")
def listar_dividas_do_bloco_8(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas)
    ],
) -> JSONResponse:
    """`AC-19` (T-139) — as fichas do Bloco 8, uma por `DIVIDA_ID` elegível.

    **A rota que faltava.** `dividas_para_bloco_8` e `perguntas_do_bloco_8`
    existiam desde `T-76`, testadas, e nenhuma rota as expunha: o Bloco 8
    (troca/portabilidade, 20 perguntas) era inalcançável por HTTP.

    Mesmo caminho de código do Bloco 7, trocando só o campo consultado em
    `ORDEM_ACOES` (`TROCA_PENDENTE` em vez de `RENEGOCIACAO_PENDENTE`) —
    nenhum critério de elegibilidade é avaliado aqui."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    if caso.snapshot_liberado_id is None:
        return _resposta_vazia(CASO_ID)

    try:
        snapshot = repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return _resposta_vazia(CASO_ID)

    dividas = dividas_para_bloco_8(snapshot)
    perguntas = perguntas_do_bloco_8(colecao.registros) if dividas else ()
    respostas = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(CASO_ID))

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "dividas": list(dividas),
            "perguntas": [registro.ID for registro in perguntas],
            "fichas": _fichas_do_bloco(dividas, perguntas, respostas, CASO_ID),
        }
    )
