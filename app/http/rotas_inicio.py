"""A tela Início — uma única próxima etapa — `RF-58`, `RF-60`, `AC-81`
(T-147).

No protótipo validado `PIQ Meu Plano`, `renderInicio` é o centro do produto:
lê a fase do caso e oferece **uma** próxima etapa. Esta rota é o lado servidor
disso.

**Por que a decisão é do servidor.** A implementação anterior oferecia ao aluno
uma barra com sete abas (Coleta · Dívidas · Plano · Ataque · Ações · Fila ·
Painel) e o deixava escolher. Isso parecia navegação inocente, mas era decisão
de fluxo no cliente: quem decidia se o caso ia para "Ataque" ou para "Ações"
era um servidor público endividado, diante de sete botões, sem saber qual se
aplicava ao seu caso — e vários não se aplicavam. `RF-58` devolve a decisão a
quem tem os dados para tomá-la.

**Arquivo próprio, e não `rotas_etapas.py`.** Aquele módulo trata da ABERTURA
das etapas pós-plano (Blocos 7/8/10/11) — quando o caso pode transicionar. Este
responde "o que o aluno vê ao abrir o app". São dois assuntos, e juntá-los faria
um módulo que muda por duas razões.

## Lei nº 3 — o que esta rota NÃO faz

Nenhum limiar é avaliado aqui. A fase vem de `app/casos/fases.py`; a guarda do
Bloco 10 vem de `app/casos/confirmacao_ataque.py::bloco_10_alcancavel`, a MESMA
que `rotas_etapas.py` consulta; a mensagem vem de
`app/http/mensagens_de_estado.py`. Esta rota LÊ e COMPÕE — não decide nada de
método (`RF-34`).

## O número nunca entra na frase

O protótipo escreve *"Decidir sobre os R$ 3.000,00"* no título da fase `plano`.
Esta rota **não** copia isso: manda o `rotulo` genérico e o
`valor_em_destaque` como **string** em campo separado, e o cliente compõe.

Dois motivos normativos, não estéticos: `RF-13` (dinheiro nunca atravessa
`float` — e `JSON.parse` transformaria um número em `double` silenciosamente,
por isso todo valor monetário viaja como string, mesma disciplina de
`rotas_etapas.py`); e a Lei nº 3 (o número é leitura de campo do snapshot, não
parte de uma frase montada no servidor). `AC-88` verifica os dois.

REGRAS: `RF-58`, `RF-60`, `RF-61`, `RF-62`, `AC-81`, `AC-88`, `AC-90`, `EC-25`
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.confirmacao_ataque import (
    ataque_imediato_recomendado_de,
    bloco_10_alcancavel,
)
from app.casos.fases import FASE_INICIO, fase_do_estado, fase_do_plano_liberado
from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import contar_coleta, proxima_pergunta_nao_respondida
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.mensagens_de_estado import mensagem_do_estado_do_caso
from app.http.rotas_coleta import _itens_por_escopo
from app.http.rotas_plano import obter_repositorio_snapshots
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import RespostasCaso
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import Caso, RepositorioCasos
from persistencia.app_aluno.itens import RepositorioItens, RepositorioItensSupabase
from persistencia.app_aluno.respostas import (
    RepositorioRespostas,
    RepositorioRespostasSupabase,
)
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado

REGRAS: Final[tuple[str, ...]] = (
    "RF-58",
    "RF-60",
    "RF-61",
    "RF-62",
    "AC-81",
    "AC-88",
    "AC-90",
    "EC-25",
)

roteador = APIRouter(prefix="/caso", tags=["inicio"])


# ---------------------------------------------------------------------------
# Pontos de injeção — um por dependência, em função própria.
#
# Mesmo padrão de `app/http/rotas_operador.py`: cada módulo de rota declara os
# SEUS, mesmo quando um idêntico já existe noutro módulo, para que este módulo
# não precise importar de `rotas_coleta.py` só por causa de um ponto de
# injeção. O que isso compra é o teste sobrescrever por
# `app.dependency_overrides` sem precisar de `DATABASE_URL`.
#
# A exceção deliberada é `obter_repositorio_snapshots`, importado de
# `rotas_plano.py` — ver a nota em `_snapshot_liberado`, abaixo.
# ---------------------------------------------------------------------------


def obter_colecao_de_registros_do_inicio() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros para esta rota."""
    return carregar_registros()


def obter_repositorio_respostas_do_inicio() -> RepositorioRespostas:
    """Ponto único de injeção do repositório de respostas para esta rota."""
    return RepositorioRespostasSupabase()


def obter_repositorio_itens_do_inicio() -> RepositorioItens:
    """Ponto único de injeção do repositório de itens repetidos — usado só
    para montar `itens_por_escopo`, que a varredura de `progresso.py`
    consome."""
    return RepositorioItensSupabase()


class DESTINO_DA_ETAPA(Enum):
    """Para onde a próxima etapa leva — dado ESTRUTURAL, não redação.

    **Por que um enum e não o texto.** `AC-37` proíbe string longa no código
    da aplicação, e a trava está certa: redação ao aluno não é decisão de
    quem escreve rota. O servidor decide **qual é** a próxima etapa (isso
    depende do estado do caso, que só ele conhece); o cliente decide **como
    dizer** (isso é interface). Codificar "Decidir sobre o dinheiro que você
    tem disponível" aqui punha as duas decisões no mesmo lugar, e a errada
    ganhava — texto ao aluno em arquivo de rota não passa por revisão de
    conteúdo.

    O cliente mapeia cada membro para rótulo e detalhe em
    `frontend/src/telas/TelaInicio.tsx`. Um membro novo sem texto lá não
    compila, pela mesma disciplina de `match` exaustivo usada aqui."""

    CONSENTIMENTO = "consentimento"
    PERGUNTA = "pergunta"
    CALCULANDO = "calculando"
    AGUARDANDO = "aguardando"
    PROGRESSO = "progresso"
    BLOCO_10 = "bloco10"
    ACOES = "acoes"
    PLANO = "plano"


@dataclass(frozen=True, slots=True)
class ProximaEtapa:
    """A ÚNICA próxima etapa do aluno — `RF-58`.

    `destino` é a tela do cliente, não uma URL: o roteamento é do cliente, e
    acoplar o servidor a hashes de navegação faria a interface não poder mudar
    de rota sem mexer no backend. O TEXTO da etapa também é do cliente — ver
    a nota de `DESTINO_DA_ETAPA`.

    `ID_PERGUNTA` e `item_id` só vêm preenchidos quando o destino é a coleta —
    é o que permite "continuar de onde parei" cair na pergunta exata, e vem
    de `proxima_pergunta_nao_respondida`, a MESMA função da retomada
    (`AC-01`)."""

    destino: DESTINO_DA_ETAPA
    ID_PERGUNTA: str | None = None
    item_id: str | None = None


def _snapshot_liberado(
    caso: Caso, repositorio_snapshots: RepositorioSnapshots
) -> SnapshotOrdem | None:
    """O snapshot LIBERADO do caso, ou `None` — nunca o último calculado.

    **O ponto de injeção é `rotas_plano.obter_repositorio_snapshots`, nunca o
    de `rotas_coleta_dirigida`.** Esse foi o defeito nº 1 corrigido em `T-145`,
    e a justificativa está em `rotas_api_plano.py`: pontos de injeção
    diferentes fazem a tela e o PDF lerem de repositórios distintos num teste
    que sobrescreve só um dos dois, e "o aluno veria um plano que o PDF não
    confirma". Repeti-lo aqui faria a tela Início discordar do plano que ela
    anuncia — pior ainda, porque o Início é a tela que manda o aluno até lá.

    Mesma tolerância de `rotas_etapas.py::_snapshot_liberado`: devolve `None`
    em vez de levantar, porque a ausência de snapshot é estado legítimo do
    caso (ninguém calculou ainda), não falha."""
    if caso.snapshot_liberado_id is None:
        return None
    try:
        return repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado:  # pragma: no cover — defensivo
        return None


def _fase_do_caso(caso: Caso, snapshot: SnapshotOrdem | None) -> FASE_INICIO:
    """A fase do aluno — `RF-61`.

    Para onze dos doze estados é `fase_do_estado`, função pura do estado.
    `PLANO_LIBERADO` é a exceção declarada: a fase `plano` do protótipo é
    literalmente *"Decidir sobre os R$ X"*, e sem ataque imediato recomendado
    não há decisão nenhuma a tomar — mandar o aluno ao Bloco 10 nesse caso o
    levaria a uma tela que o servidor fecha com `409`.

    A guarda é `bloco_10_alcancavel`, a MESMA que `rotas_etapas.py` consulta
    antes de abrir o Bloco 10 — nenhum limiar novo é escrito aqui (`RF-34`).
    Sem snapshot, não há o que decidir: cai em `acompanhamento`."""
    if caso.estado is not ESTADO_CASO.PLANO_LIBERADO:
        return fase_do_estado(caso.estado)

    tem_ataque = snapshot is not None and bloco_10_alcancavel(snapshot)
    return fase_do_plano_liberado(tem_ataque_a_decidir=tem_ataque)


def _proxima_etapa(
    caso: Caso,
    fase: FASE_INICIO,
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> ProximaEtapa:
    """A única próxima etapa, por fase — a transcrição dos cinco ramos de
    `renderInicio` (protótipo, linha ~917).

    **Uma só, sempre.** Não é uma lista com um item: é o contrato de `RF-58`.
    Oferecer duas já seria pedir ao aluno que escolhesse."""
    match fase:
        case FASE_INICIO.COLETA:
            if caso.estado is ESTADO_CASO.CADASTRADO:
                # Ainda não consentiu: nenhuma resposta pode ser gravada
                # antes disso (`RF-30`, `AC-39`).
                return ProximaEtapa(
                    destino=DESTINO_DA_ETAPA.CONSENTIMENTO,
                )

            pendencia = proxima_pergunta_nao_respondida(
                colecao.registros, respostas, itens_por_escopo
            )
            if pendencia is None:
                # `EC-23`: coleta completa. A próxima etapa é o cálculo, não
                # uma pergunta arbitrária nem uma tela vazia.
                return ProximaEtapa(
                    destino=DESTINO_DA_ETAPA.CALCULANDO,
                )
            return ProximaEtapa(
                destino=DESTINO_DA_ETAPA.PERGUNTA,
                ID_PERGUNTA=pendencia.ID,
                item_id=pendencia.item_id,
            )

        case FASE_INICIO.REVISAO:
            # `EC-25`: `CALCULANDO` e `ERRO_DE_CALCULO` caem aqui junto com
            # `AGUARDANDO_REVISAO`. A fase é a mesma — *é com a gente* —; só o
            # destino muda, para a tela do `.pulse` enquanto calcula. O erro
            # técnico NUNCA aparece: `mensagem_do_estado_do_caso` já diz "Seu
            # plano está em nova análise.", que é verdade e é o que o aluno
            # pode fazer com a informação (nada).
            destino = (
                DESTINO_DA_ETAPA.CALCULANDO
                if caso.estado is ESTADO_CASO.CALCULANDO
                else DESTINO_DA_ETAPA.AGUARDANDO
            )
            return ProximaEtapa(
                destino=destino,
            )

        case FASE_INICIO.REPROVADO:
            return ProximaEtapa(
                destino=DESTINO_DA_ETAPA.PROGRESSO,
            )

        case FASE_INICIO.PLANO:
            # O "Decidir sobre os R$ X" do protótipo. O valor NÃO entra no
            # rótulo — ver a nota do cabeçalho e `AC-88`.
            return ProximaEtapa(
                destino=DESTINO_DA_ETAPA.BLOCO_10,
            )

        case FASE_INICIO.ACOMPANHAMENTO:
            if caso.estado is ESTADO_CASO.ENCERRADO:
                # `EC-25`: encerrado não é uma sexta fase. É acompanhamento
                # sem ações a executar.
                return ProximaEtapa(
                    destino=DESTINO_DA_ETAPA.PLANO,
                )
            return ProximaEtapa(
                destino=DESTINO_DA_ETAPA.ACOES,
            )


@roteador.get("/{CASO_ID}/inicio")
def inicio_do_caso(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    colecao: Annotated[
        ColecaoDeRegistros, Depends(obter_colecao_de_registros_do_inicio)
    ],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas_do_inicio)
    ],
    repositorio_itens: Annotated[
        RepositorioItens, Depends(obter_repositorio_itens_do_inicio)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> JSONResponse:
    """`RF-58`, `RF-60`, `AC-81` — a fase do caso e a ÚNICA próxima etapa.

    `exigir_caso_da_sessao("CASO_ID")` não é boa prática, é obrigação
    verificada: `tests/app_aluno/e2e/test_mecanismo_isolamento.py` enumera as
    `APIRoute` registradas e exige o par `CASO_ID` + subdependência de
    `app.http.isolamento` (`AC-74`). Sem sessão ⇒ `401`; caso de outra conta
    ou inexistente ⇒ `404` indistinguível.

    Todo valor monetário sai como `str` (`RF-13`)."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    respostas = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(CASO_ID))
    itens_por_escopo = _itens_por_escopo(repositorio_itens, CASO_ID)
    snapshot = _snapshot_liberado(caso, repositorio_snapshots)

    fase = _fase_do_caso(caso, snapshot)
    contagem = contar_coleta(colecao.registros, respostas, itens_por_escopo)
    etapa = _proxima_etapa(caso, fase, colecao, respostas, itens_por_escopo)

    # O valor em destaque existe SÓ na fase `plano`, e sempre como string
    # separada do rótulo — `AC-88`. Nas outras fases é `null`: não há decisão
    # de dinheiro pendente, e mandar um número que a tela não usa convidaria
    # alguém a compor uma frase com ele.
    valor_em_destaque = (
        str(ataque_imediato_recomendado_de(snapshot))
        if fase is FASE_INICIO.PLANO and snapshot is not None
        else None
    )

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "estado": caso.estado.value,
            "fase": fase.value,
            "mensagem": mensagem_do_estado_do_caso(caso.estado),
            "proxima_etapa": {
                "destino": etapa.destino.value,
                "ID_PERGUNTA": etapa.ID_PERGUNTA,
                "item_id": etapa.item_id,
            },
            "progresso": {
                "respondidas": contagem.respondidas,
                "total": contagem.total,
            },
            "valor_em_destaque": valor_em_destaque,
            "plano_liberado": caso.snapshot_liberado_id is not None,
            "versao_do_plano": snapshot.versao if snapshot is not None else None,
        }
    )


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: `exigir_caso_da_sessao` já garantiu que o caso existe."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento")
