"""API JSON do plano, da fila de revisão e do painel — `RF-50`, `RF-51`
(T-140).

As telas do plano, do revisor e do operador passam a ser React. Estas rotas
entregam os MESMOS campos que os templates Jinja2 recebiam — nem um a mais.

**O PDF continua em Jinja2, e isso é deliberado.** `report/pdf.py` renderiza
`report/templates/plano/plano.html` para gerar o PDF, e `RF-21`/`AC-14`
exigem que a redação canônica de `Q-03` exista em UM lugar só. Aquele
template deixa de servir navegador, mas continua sendo a fonte do PDF —
apagá-lo criaria uma segunda cópia do texto normativo.

**Mesmas guardas de sempre, nenhuma nova.** Plano: só o snapshot LIBERADO
(`snapshot_tem_liberacao_registrada`, a mesma de `gerar_html_do_plano_
liberado`). Revisão e painel: `exigir_papel_revisor` — `401` sem sessão,
`403` para conta que não é revisora, nunca `404` (a existência da tela do
revisor não é segredo).

REGRAS: `RF-50`, `RF-51`, `AC-25`, `AC-28`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import consultar_trilha_de_progresso
from app.http.isolamento import (
    exigir_caso_da_sessao,
    exigir_papel_revisor,
    obter_repositorio_casos,
)
from app.http.mensagens_de_estado import mensagem_do_estado_do_caso
from app.http.rotas_operador import (
    CasosDoPainel,
    ItensDoPainel,
    RespostasDoPainel,
    _relato_para_linha,
    agrupar_itens_por_escopo,
    obter_colecao_de_registros_do_painel,
    obter_repositorio_casos_do_painel,
    obter_repositorio_itens_do_painel,
    obter_repositorio_respostas_do_painel,
)
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_snapshots_da_fila,
)
from app.http.serializacao_plano import (
    serializar_estado_inputs,
    serializar_item_da_fila,
    serializar_plano,
)
from app.revisao.fila import listar_fila_de_revisao, montar_item_da_fila
from collection.carga import ColecaoDeRegistros
from collection.respostas import RespostasCaso
from engine.portas import RepositorioSnapshots
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from report.pdf import snapshot_tem_liberacao_registrada
from report.plano import (
    carregar_textos_canonicos,
    montar_contexto_estado_inputs,
    montar_contexto_plano,
)

REGRAS: Final[tuple[str, ...]] = ("RF-50", "RF-51", "AC-25", "AC-28")

roteador = APIRouter(tags=["api-plano"])

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_SEM_PLANO: Final[str] = "Nenhum plano liberado ainda."


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: `exigir_caso_da_sessao` já garantiu que o caso existe."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento")


@roteador.get("/caso/{CASO_ID}/api/plano")
def plano_do_aluno(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """`AC-25` — sempre o snapshot **liberado**, nunca o último calculado.

    O ponto de injeção é `rotas_plano.obter_repositorio_snapshots` — o
    mesmo da rota de PDF, porque é a mesma tela do aluno vista de dois
    jeitos. Usar o de `rotas_coleta_dirigida` aqui faria o plano e o PDF
    lerem de repositórios distintos num teste que sobrescreve só um dos
    dois, e o aluno veria um plano que o PDF não confirma.

    Sem plano liberado, devolve o ESTADO do caso, `plano: null` e a
    mensagem correspondente àquele estado — nunca uma tela de plano vazia
    nem um "nenhum plano liberado" genérico. O aluno em revisão lê "seu
    plano está em revisão", não uma negativa que não explica nada.

    `mensagem_do_estado_do_caso` vive em `app/http/mensagens_de_estado.py`
    com `match` exaustivo: um estado novo sem mensagem não compila."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    if caso.snapshot_liberado_id is None:
        return JSONResponse(
            {
                "CASO_ID": CASO_ID,
                "plano": None,
                "estado": caso.estado.value,
                "mensagem": mensagem_do_estado_do_caso(caso.estado),
            }
        )

    try:
        snapshot = repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:
        return JSONResponse(
            {
                "CASO_ID": CASO_ID,
                "plano": None,
                "estado": caso.estado.value,
                "mensagem": mensagem_do_estado_do_caso(caso.estado),
            }
        )

    # A MESMA guarda de liberação que a rota do PDF usa — nenhuma segunda
    # checagem escrita aqui.
    if not snapshot_tem_liberacao_registrada(caso, snapshot):
        return JSONResponse(
            {
                "CASO_ID": CASO_ID,
                "plano": None,
                "estado": caso.estado.value,
                "mensagem": mensagem_do_estado_do_caso(caso.estado),
            }
        )

    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    return JSONResponse(
        {"CASO_ID": CASO_ID, "estado": caso.estado.value, "plano": serializar_plano(contexto)}
    )


@roteador.get("/api/revisao/fila")
def fila_de_revisao(
    _revisor: Annotated[str, Depends(exigir_papel_revisor)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos_da_fila)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots_da_fila)
    ],
) -> JSONResponse:
    """`AC-28` — a fila, com os dois sinais SEPARADOS.

    `entra_por_politica` (piloto 100% revisado) e `e_metodologico`
    (`REVISAO_HUMANA_OBRIGATORIA` do motor) nunca viram um booleano só: são
    fatos diferentes, e um teste estático falha se forem combinados."""
    # Mesmo caminho de `rotas_revisao.py::exibir_fila_de_revisao`: os casos
    # vêm de `listar_por_estado`, e inclui recálculos sem tratamento
    # especial — um caso liberado que voltou a `AGUARDANDO_REVISAO` é achado
    # pela MESMA consulta de estado.
    casos_ids = repositorio_casos.listar_por_estado(ESTADO_CASO.AGUARDANDO_REVISAO)
    itens = listar_fila_de_revisao(list(casos_ids), repositorio_casos, repositorio_snapshots)
    return JSONResponse({"itens": [serializar_item_da_fila(item) for item in itens]})


@roteador.get("/api/revisao/caso/{CASO_ID_REVISAO}")
def caso_para_revisao(
    CASO_ID_REVISAO: str,
    _revisor: Annotated[str, Depends(exigir_papel_revisor)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos_da_fila)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots_da_fila)
    ],
) -> JSONResponse:
    """O plano como o aluno o verá, mais o carimbo — para a tela lado a lado
    do revisor (`AC-29`).

    O parâmetro se chama `CASO_ID_REVISAO`, não `CASO_ID`, de propósito: a
    auditoria de isolamento casa pelo nome literal, e esta rota é do
    REVISOR (protegida por papel), não do dono do caso.

    **O snapshot é o ÚLTIMO da cadeia, nunca `snapshot_liberado_id`.** É
    sobre o snapshot ainda não decidido que o revisor compara plano e
    `estado_inputs` — exigir o liberado deixaria a tela vazia exatamente
    nos casos em `AGUARDANDO_REVISAO`, que são todos os que importam aqui.
    A cadeia se busca por `caso.snapshot_raiz_id` (`OQ-11`), mesmo idioma
    de `app/revisao/fila.py:276`."""
    caso = repositorio_casos.buscar(CASO_ID_REVISAO)
    if caso is None or caso.snapshot_raiz_id is None:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=404)

    historico = repositorio_snapshots.historico(caso.snapshot_raiz_id)
    if not historico:
        return JSONResponse({"erro": _MENSAGEM_SEM_PLANO}, status_code=404)

    snapshot = historico[-1]

    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    item = montar_item_da_fila(CASO_ID_REVISAO, snapshot)
    # `AC-29`: plano e `estado_inputs` na MESMA resposta. O revisor compara
    # os dois lado a lado; se viessem de requisições diferentes, poderiam
    # ser de snapshots diferentes — e a comparação não provaria nada.
    estado_inputs = montar_contexto_estado_inputs(snapshot.estado_inputs)
    return JSONResponse(
        {
            "CASO_ID": CASO_ID_REVISAO,
            "plano": serializar_plano(contexto),
            "estado_inputs": serializar_estado_inputs(estado_inputs),
            "fila": serializar_item_da_fila(item),
        }
    )


@roteador.get("/api/operador/painel")
def painel_do_operador(
    _revisor: Annotated[str, Depends(exigir_papel_revisor)],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros_do_painel)],
    repositorio_casos: Annotated[CasosDoPainel, Depends(obter_repositorio_casos_do_painel)],
    repositorio_respostas: Annotated[
        RespostasDoPainel, Depends(obter_repositorio_respostas_do_painel)
    ],
    repositorio_itens: Annotated[ItensDoPainel, Depends(obter_repositorio_itens_do_painel)],
) -> JSONResponse:
    """`RF-35` — quem está onde, sem nenhum valor financeiro.

    Só etapa, pendência e tempo desde a última atividade: é critério de
    aceite de `T-102` que esta tela nunca exiba dinheiro do aluno. A
    montagem reusa `consultar_trilha_de_progresso` — nenhuma trilha nova
    calculada aqui.

    **Três consultas, não `1 + 3N` — `T-187`.** Antes desta tarefa, cada
    caso do piloto custava três consultas próprias (`buscar`,
    `listar_do_caso` de respostas, idem de itens) — com N casos, N vezes a
    viagem de rede até o banco. `buscar_varios`/`listar_de_varios_casos`
    trazem TUDO de uma vez; o `for` abaixo só organiza dados que já estão
    em memória, sem tocar o banco de novo."""
    agora = datetime.now(UTC)
    caso_ids = repositorio_casos.listar_todos()
    casos_por_id = repositorio_casos.buscar_varios(caso_ids)
    respostas_por_caso = repositorio_respostas.listar_de_varios_casos(caso_ids)
    itens_por_caso = repositorio_itens.listar_de_varios_casos(caso_ids, incluir_removidos=False)

    linhas = []
    for caso_id in caso_ids:
        caso = casos_por_id.get(caso_id)
        if caso is None:  # pragma: no cover — defensivo: removido entre as duas consultas
            continue
        respostas = RespostasCaso(respostas=respostas_por_caso.get(caso_id, ()))
        itens = agrupar_itens_por_escopo(itens_por_caso.get(caso_id, ()))
        relato = consultar_trilha_de_progresso(caso, colecao.registros, respostas, itens)
        linha = _relato_para_linha(relato, agora)
        linhas.append(
            {
                "CASO_ID": linha.CASO_ID,
                "estado": linha.estado.value,
                "aguardando_revisao": linha.aguardando_revisao,
                "tempo_desde_ultima_atividade": linha.tempo_desde_ultima_atividade,
            }
        )
    return JSONResponse({"linhas": linhas})
