"""As três saídas de `PLANO_LIBERADO` — `RF-54`, `AC-19`, `AC-22` (T-139).

**A lacuna que estas rotas fecham.** `app/casos/maquina.py:216-232` declara
três transições saindo de `PLANO_LIBERADO`:

    PLANO_LIBERADO → COLETA_DIRIGIDA    (gatilho `abre_blocos_7_8`)
    PLANO_LIBERADO → CONFIRMACAO_ATAQUE (gatilho `abre_bloco_10`)
    PLANO_LIBERADO → ACOMPANHAMENTO     (gatilho `abre_bloco_11`)

**Nenhuma rota as disparava.** O caso chegava a `PLANO_LIBERADO` e morria
ali: Blocos 7, 8, 10 e 11 existiam em código, testados, e eram inalcançáveis
porque o caso nunca saía do estado anterior a eles.

**As guardas são lidas, nunca reimplementadas.** `abre_bloco_10` só é
permitida quando `bloco_10_alcancavel(snapshot)` — que por sua vez lê
`ATAQUE_IMEDIATO_RECOMENDADO > 0` (`AC-22`). `abre_blocos_7_8` exige que
`ORDEM_ACOES` tenha ação para o bloco (`AC-19`). Este módulo consulta as
funções que já decidem isso; não conhece limiar nenhum.

**Concorrência.** `transicionar_e_registrar` grava CONDICIONALMENTE ao
estado esperado e devolve `None` quando outra transição venceu a corrida —
resposta `409`, nunca uma segunda transição forçada.

REGRAS: `RF-54`, `AC-19`, `AC-22`, `AC-40`
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.coleta_dirigida import dividas_para_bloco_7, dividas_para_bloco_8
from app.casos.confirmacao_ataque import (
    ataque_imediato_recomendado_de,
    bloco_10_alcancavel,
    perguntas_do_bloco_10,
)
from app.casos.maquina import ESTADO_CASO, ErroTransicaoNaoDeclarada
from app.casos.progresso import transicionar_e_registrar
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_calculo import obter_repositorio_eventos
from app.http.rotas_coleta import obter_colecao_de_registros, obter_repositorio_respostas
from app.http.rotas_coleta_dirigida import obter_repositorio_snapshots
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros
from collection.respostas import RespostasCaso
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.eventos import RepositorioEventosCaso
from persistencia.app_aluno.respostas import RepositorioRespostas
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado

REGRAS: Final[tuple[str, ...]] = ("RF-54", "AC-19", "AC-22", "AC-40")

roteador = APIRouter(prefix="/caso", tags=["etapas"])

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_SEM_PLANO: Final[str] = "Nenhum plano liberado."
_MENSAGEM_ETAPA_FECHADA: Final[str] = "Etapa não alcançável agora."
_MENSAGEM_ESTADO_INVALIDO: Final[str] = "Transição não permitida daqui."
_MENSAGEM_CONCORRENCIA: Final[str] = "O caso mudou de estado."


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: `exigir_caso_da_sessao` já garantiu que o caso existe."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento")


def _snapshot_liberado(
    CASO_ID: str,
    repositorio_casos: RepositorioCasos,
    repositorio_snapshots: RepositorioSnapshots,
) -> SnapshotOrdem | None:
    """O snapshot que o aluno de fato recebeu. `None` quando não há plano
    liberado — nenhuma etapa pós-plano abre sem ele."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)
    if caso.snapshot_liberado_id is None:
        return None
    try:
        return repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return None


def _abrir(
    *,
    CASO_ID: str,
    para: ESTADO_CASO,
    repositorio_casos: RepositorioCasos,
    repositorio_eventos: RepositorioEventosCaso,
) -> JSONResponse:
    """Dispara a transição a partir de `PLANO_LIBERADO`, com as mesmas três
    garantias de `rotas_calculo.py`: par validado contra a máquina, gravação
    condicional ao estado esperado, e evento na trilha (`AC-40`)."""
    try:
        caso = transicionar_e_registrar(
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            caso_id=CASO_ID,
            de=ESTADO_CASO.PLANO_LIBERADO,
            para=para,
        )
    except ErroTransicaoNaoDeclarada:
        return JSONResponse({"erro": _MENSAGEM_ESTADO_INVALIDO}, status_code=409)

    if caso is None:
        # Outra transição venceu a corrida — nada foi gravado.
        return JSONResponse({"erro": _MENSAGEM_CONCORRENCIA}, status_code=409)

    return JSONResponse({"CASO_ID": CASO_ID, "estado": caso.estado.value})


@roteador.post("/{CASO_ID}/etapas/blocos-7-8")
def abrir_blocos_7_8(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """`AC-19` — abre a coleta dirigida, e só quando há dívida sinalizada.

    A elegibilidade vem de `dividas_para_bloco_7`/`_8`, que leem apenas
    `snapshot.ORDEM_ACOES`. Esta rota não consulta saldo, taxa nem gate."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=409)

    if not dividas_para_bloco_7(snapshot) and not dividas_para_bloco_8(snapshot):
        return JSONResponse({"erro": _MENSAGEM_ETAPA_FECHADA}, status_code=409)

    return _abrir(
        CASO_ID=CASO_ID,
        para=ESTADO_CASO.COLETA_DIRIGIDA,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )


@roteador.post("/{CASO_ID}/etapas/bloco-10")
def abrir_bloco_10(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """`AC-22` — abre o Bloco 10 somente com `ATAQUE_IMEDIATO_RECOMENDADO > 0`.

    O limiar é de `bloco_10_alcancavel`; esta rota só o consulta."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=409)

    if not bloco_10_alcancavel(snapshot):
        return JSONResponse({"erro": _MENSAGEM_ETAPA_FECHADA}, status_code=409)

    resposta = _abrir(
        CASO_ID=CASO_ID,
        para=ESTADO_CASO.CONFIRMACAO_ATAQUE,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )
    return resposta


@roteador.post("/{CASO_ID}/etapas/bloco-11")
def abrir_bloco_11(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """Abre o acompanhamento. A guarda da tabela é "ação reportada, meses
    depois" — não há limiar numérico a consultar, só a exigência de haver
    plano liberado."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=409)

    return _abrir(
        CASO_ID=CASO_ID,
        para=ESTADO_CASO.ACOMPANHAMENTO,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )


@roteador.get("/{CASO_ID}/etapas")
def etapas_disponiveis(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """Quais etapas o caso pode abrir agora — para o cliente oferecer só o
    que existe, em vez de tentar e levar `409`.

    Os valores vêm das MESMAS funções que guardam as transições; nenhuma
    regra é reavaliada aqui."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse(
            {"CASO_ID": CASO_ID, "blocos_7_8": False, "bloco_10": False, "bloco_11": False}
        )

    tem_dirigida = bool(dividas_para_bloco_7(snapshot)) or bool(
        dividas_para_bloco_8(snapshot)
    )
    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "blocos_7_8": tem_dirigida,
            "bloco_10": bloco_10_alcancavel(snapshot),
            "bloco_11": True,
            "ATAQUE_IMEDIATO_RECOMENDADO": str(ataque_imediato_recomendado_de(snapshot)),
        }
    )


@roteador.get("/{CASO_ID}/bloco-10")
def perguntas_do_ataque_imediato(
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
    """`AC-22`/`AC-24` — as perguntas do Bloco 10 e o valor recomendado.

    Só responde quando `ATAQUE_IMEDIATO_RECOMENDADO > 0`; abaixo disso o
    bloco inteiro está fechado e não há o que perguntar (`bloco_10_
    alcancavel`). O valor vai como STRING — `RF-13` proíbe dinheiro
    atravessar ponto flutuante, e `JSON.parse` faria isso silenciosamente.

    **Nunca se pergunta qual dívida recebe o recurso** (`AC-24`): as duas
    perguntas têm `escopo_repeticao: NENHUM`, e o plano decide a alocação."""
    snapshot = _snapshot_liberado(CASO_ID, repositorio_casos, repositorio_snapshots)
    if snapshot is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=409)

    if not bloco_10_alcancavel(snapshot):
        return JSONResponse({"erro": _MENSAGEM_ETAPA_FECHADA}, status_code=409)

    respostas = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(CASO_ID))
    campos = []
    for registro in perguntas_do_bloco_10(colecao.registros):
        try:
            contexto = montar_contexto_pergunta(registro, respostas, snapshot=snapshot)
        except ErroPerguntaNaoExibivel:
            continue
        campos.append(serializar_pergunta(contexto, CASO_ID=CASO_ID))

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "ATAQUE_IMEDIATO_RECOMENDADO": str(ataque_imediato_recomendado_de(snapshot)),
            "campos": campos,
        }
    )
