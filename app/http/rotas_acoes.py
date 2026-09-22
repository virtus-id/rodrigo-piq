"""Bloco 11 — as ações do plano e seu andamento (`RF-27`, `RF-33`, `AC-45`
a `AC-50`, T-143).

**A lacuna que estas rotas fecham.** `app/http/rotas_bloco11.py` grava as
SETE perguntas de confirmação de quitação (`B11.Q01`–`Q06`), e só elas — é
uma rota especializada, e a docstring dela diz isso. Mas o Bloco 11 tem doze
perguntas: `B11.01` (`ACAO_STATUS`) e as quatro `B11.03-*` (resultado por
tipo de ação) **não tinham caminho de gravação nenhum**.

Em vez de afrouxar a rota especializada — que tem uma garantia própria a
preservar —, este módulo acrescenta o que faltava, com a mesma disciplina.

**`item_id` é o `ACAO_ID`, nunca o `DIVIDA_ID`** (`AC-50`). Uma ação de
economia não tem dívida associada, e mesmo assim precisa de ficha: por isso
a chave é a ação. `item_id_do_bloco_11` é quem resolve isso, e este módulo
não reimplementa a regra.

**A lista de ações vem de `snapshot.ORDEM_ACOES`** — leitura pura, sem
derivar nada (Lei nº 3). Esta rota não decide o que é uma ação nem em que
ordem elas vêm.

REGRAS: `RF-27`, `RF-33`, `AC-45`, `AC-46`, `AC-50`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.casos.acompanhamento import item_id_do_bloco_11
from app.casos.maquina import ErroConsentimentoNaoRegistrado
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import (
    _ler_formulario,
    obter_colecao_de_registros,
    obter_repositorio_respostas,
)
from app.http.rotas_coleta_dirigida import obter_repositorio_snapshots
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.repeticao import perguntas_da_ficha
from collection.respostas import NAO_SEI, Resposta, RespostasCaso, ValorResposta
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.respostas import (
    ErroCasoInexistenteParaResposta,
    ErroGravacaoResposta,
    RepositorioRespostas,
)
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado

REGRAS: Final[tuple[str, ...]] = ("RF-27", "RF-33", "AC-45", "AC-46", "AC-50")

roteador = APIRouter(prefix="/caso", tags=["acoes"])

_BLOCO_ACOMPANHAMENTO: Final[int] = 11

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_PERGUNTA_INVALIDA: Final[str] = "Pergunta fora do Bloco 11."
_MENSAGEM_FALHA_SALVAR: Final[str] = "Não foi possível salvar."


def _agora() -> datetime:
    return datetime.now(UTC)


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: `exigir_caso_da_sessao` já garantiu que o caso existe."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento")


def _snapshot_liberado(
    CASO_ID: str,
    repositorio_casos: RepositorioCasos,
    repositorio_snapshots: RepositorioSnapshots,
) -> SnapshotOrdem | None:
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)
    if caso.snapshot_liberado_id is None:
        return None
    try:
        return repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return None


def _perguntas_do_bloco_11(registros: tuple[RegistroPergunta, ...]) -> tuple[RegistroPergunta, ...]:
    """As doze perguntas por `ACAO_ID` do Bloco 11 — filtro pelo próprio
    campo do registro, nunca por lista de `ID` escrita aqui (`RF-03`)."""
    da_ficha = perguntas_da_ficha(registros, EscopoRepeticao.ACAO_ID)
    return tuple(r for r in da_ficha if r.bloco == _BLOCO_ACOMPANHAMENTO)


@roteador.get("/{CASO_ID}/acoes")
def listar_acoes(
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
    """`RF-27`/`AC-45` — uma ficha por ação de `ORDEM_ACOES`.

    `AC-50`: ação sem `DIVIDA_ID` (a de economia) aparece como qualquer
    outra — a chave é o `ACAO_ID`, e nenhum caminho aqui exige dívida.

    `VALOR_ACAO_FINANCEIRA_IMEDIATA` vai como string (ou `null` quando
    desconhecido): `RF-13` proíbe dinheiro atravessar ponto flutuante, e
    `DinheiroTalvez` desconhecido nunca vira zero."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse({"CASO_ID": CASO_ID, "acoes": []})

    respostas = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(CASO_ID))
    perguntas = _perguntas_do_bloco_11(colecao.registros)

    acoes: list[dict[str, Any]] = []
    for acao in snapshot.ORDEM_ACOES:
        item_id = item_id_do_bloco_11(acao)
        campos: list[dict[str, Any]] = []
        for registro in perguntas:
            try:
                contexto = montar_contexto_pergunta(
                    registro, respostas, item_id=item_id, snapshot=snapshot
                )
            except ErroPerguntaNaoExibivel:
                continue
            campos.append(serializar_pergunta(contexto, CASO_ID=CASO_ID, item_id=item_id))

        valor = acao.VALOR_ACAO_FINANCEIRA_IMEDIATA
        acoes.append(
            {
                "ACAO_ID": acao.ACAO_ID,
                "TIPO_ACAO": acao.TIPO_ACAO,
                "DIVIDA_ID": acao.DIVIDA_ID,
                "descricao": acao.descricao,
                "prioridade_excepcional": acao.prioridade_excepcional,
                "CAMPO_PENDENTE": acao.CAMPO_PENDENTE,
                "VALOR_ACAO_FINANCEIRA_IMEDIATA": None
                if not hasattr(valor, "__str__") or valor is None
                else str(valor),
                "campos": campos,
            }
        )

    return JSONResponse({"CASO_ID": CASO_ID, "acoes": acoes})


@roteador.post("/{CASO_ID}/acoes/resposta")
async def responder_acao(
    request: Request,
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
) -> JSONResponse:
    """Grava `B11.01` e as `B11.03-*` — as perguntas do Bloco 11 que a rota
    de confirmação de quitação (`rotas_bloco11.py`) deliberadamente não
    aceita.

    **Restrita ao Bloco 11 por escopo `ACAO_ID`**, pelo mesmo princípio
    daquela: uma `ID_PERGUNTA` válida no questionário mas fora deste
    subconjunto é recusada como desconhecida.

    Só `SELECAO_UNICA` aqui — as quatro perguntas deste subconjunto são
    todas de domínio fechado, e valor é gravado como `str` direto, sem
    passar pela fronteira decimal."""
    dados = await _ler_formulario(request)
    id_pergunta = dados.get("ID_PERGUNTA", "")
    item_id = dados.get("item_id") or None

    registro = next(
        (r for r in _perguntas_do_bloco_11(colecao.registros) if r.ID == id_pergunta), None
    )
    if registro is None or registro.VARIAVEL_GRAVADA is None:
        return JSONResponse({"erro": _MENSAGEM_PERGUNTA_INVALIDA}, status_code=400)

    valor: ValorResposta = NAO_SEI if dados.get("nao_sei") else dados.get("valor", "")

    try:
        repositorio.gravar(
            Resposta(
                CASO_ID=CASO_ID,
                ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
                item_id=item_id,
                valor=valor,
                QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
                respondida_em=_agora(),
            )
        )
    except ErroConsentimentoNaoRegistrado:
        return JSONResponse({"erro": _MENSAGEM_PERGUNTA_INVALIDA}, status_code=400)
    except (ErroGravacaoResposta, ErroCasoInexistenteParaResposta):
        # `EC-05`: a transação nunca foi commitada — nada foi salvo. A rota
        # não reporta como salva uma resposta que não chegou ao banco.
        return JSONResponse({"erro": _MENSAGEM_FALHA_SALVAR}, status_code=503)

    return JSONResponse({"CASO_ID": CASO_ID, "ID_PERGUNTA": registro.ID, "item_id": item_id})
