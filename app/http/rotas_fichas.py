"""Fichas repetíveis — `RF-04`, `RF-51`, `RF-53`, `AC-04` (T-134).

**A lacuna que estas rotas fecham.** A ficha repetível (antes
`report/templates/coleta/
ficha_repetivel.html` existe desde `T-47`, está testada, e **nenhuma rota a
renderiza**: era a tela mais cara já construída neste projeto e estava morta.
Pior — **108 das 247 perguntas** têm `escopo_repeticao != NENHUM` (Blocos 3,
5, 7, 8 e 11), e sem uma rota que liste/crie/remova itens o aluno não
cadastra nem uma dívida. O Bloco 5 inteiro, que é o núcleo do PIQ, dependia
disto.

**O que estas rotas NÃO fazem.** Não decidem quais perguntas pertencem à
ficha (`collection/repeticao.py::perguntas_da_ficha`, por
`escopo_repeticao`), não geram identificador (`RepositorioItens::
proximo_identificador`, que garante não-reaproveitamento mesmo após remoção)
e não decidem se uma ficha está completa (`itens_em_aberto`). Tudo
isso já existe e é apenas orquestrado aqui — mesma disciplina de
`rotas_pergunta.py`.

**Remoção é marcação, nunca `DELETE`.** `RepositorioItens.remover` grava
`removido_em`; o identificador daquele item **nunca** volta a ser gerado
(`AC-04`). Uma ficha removida some da lista, mas sua memória permanece.

REGRAS: `RF-04`, `RF-51`, `RF-53`, `AC-04`
"""

from __future__ import annotations

from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.itens_despesa import DESPESA_NAO_LISTADA, pede_nome, rotulos_dos_itens
from app.casos.progresso import (
    cabecas_das_fichas,
    em_branco_no_item,
    escopo_aberto,
    itens_em_aberto,
    percurso_da_coleta,
)
from app.concorrencia import duas_em_paralelo
from app.http.edicao import exigir_coleta_editavel
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.http.jornada import trilha_da_coleta
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_coleta import (
    _MENSAGEM_FICHA_INCOMPLETA,
    _agrupar,
    _ler_formulario,
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
    perguntas_da_ficha_inicial,
    perguntas_do_formulario,
)
from app.http.serializacao import serializar_pergunta
from collection.carga import ColecaoDeRegistros
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.repeticao import escopo_pai
from collection.respostas import RespostasCaso
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.itens import ItemRepetido, RepositorioItens
from persistencia.app_aluno.respostas import RepositorioRespostas

REGRAS: Final[tuple[str, ...]] = ("RF-04", "RF-51", "RF-53", "AC-04")

roteador = APIRouter(prefix="/caso", tags=["fichas"])

# Mensagens curtas de propósito — limiar de `AC-37` (T-08).
_MENSAGEM_ESCOPO_INVALIDO: Final[str] = "Escopo de repetição inválido."
_MENSAGEM_ITEM_INEXISTENTE: Final[str] = "Item não encontrado no caso."
_MENSAGEM_NOME_INVALIDO: Final[str] = "Informe um nome de até 60 letras."
_MENSAGEM_ITEM_SEM_NOME: Final[str] = "Este item já tem nome."
_MENSAGEM_PAI_INVALIDO: Final[str] = "Ficha sem item pai válido."

# `T-217` — "texto curto" (§11), sem limite na spec; 60 cabem num título.
_NOME_MAXIMO: Final[int] = 60


def _escopo_valido(escopo: str) -> EscopoRepeticao | None:
    """`escopo` da URL → membro do enum, ou `None`. Nunca um default
    "parecido": escopo desconhecido é `400`, não uma ficha de outro tipo."""
    try:
        membro = EscopoRepeticao(escopo)
    except ValueError:
        return None
    return None if membro is EscopoRepeticao.NENHUM else membro


def _perguntas_da_ficha(
    colecao: ColecaoDeRegistros, escopo: EscopoRepeticao
) -> tuple[RegistroPergunta, ...]:
    """As perguntas da ficha do escopo — ver `_campos_da_ficha`."""
    return perguntas_da_ficha_inicial(colecao, escopo)


def _campos_da_ficha(
    colecao: ColecaoDeRegistros,
    escopo: EscopoRepeticao,
    respostas: RespostasCaso,
    CASO_ID: str,
    item_id: str,
    rotulo: str | None = None,
    itens_por_escopo: dict[EscopoRepeticao, tuple[str, ...]] | None = None,
    rotulos: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """As perguntas da ficha, já serializadas, para UM item.

    Pergunta cuja `condicao_exibicao` é falsa **naquele item** é omitida —
    quem decide é `montar_contexto_pergunta`, no servidor (`RF-52`); o
    cliente recebe só o que deve desenhar.

    `T-200`: só as perguntas da coleta inicial. Os Blocos 7 e 8 também são
    `DIVIDA_ID`, mas são coleta dirigida, outra etapa (`RF-17`, `AC-92`) — o
    filtro fica aqui, e não em `perguntas_da_ficha`, porque a coleta dirigida
    usa aquela função justamente para chegar ao Bloco 7.

    `T-211`: o filtro só vale para escopo que TEM registro na coleta inicial
    — derivado da coleção, sem nome de escopo aqui. Escopo todo pós-plano
    (hoje, o do Bloco 11) fica com os seus campos."""
    campos: list[dict[str, Any]] = []
    for registro in _perguntas_da_ficha(colecao, escopo):
        try:
            contexto = montar_contexto_pergunta(
                registro,
                respostas,
                item_id=item_id,
                rotulo_do_item=rotulo,
                itens_por_escopo=itens_por_escopo,
                rotulos=rotulos,
            )
        except ErroPerguntaNaoExibivel:
            continue
        campos.append(serializar_pergunta(contexto, CASO_ID=CASO_ID, item_id=item_id))
    return campos


@roteador.get("/{CASO_ID}/fichas/{escopo}")
def listar_fichas(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> JSONResponse:
    """`RF-04`/`AC-04` — as fichas ATIVAS do escopo, com seus campos.

    `completa` é leitura de `itens_em_aberto` (`T-201`): a ficha está
    completa quando nenhuma pergunta aberta NAQUELE item está em branco —
    os predicados da retomada, na mesma varredura de `progresso.py`. Não é
    `pendencias_obrigatorias`: as perguntas da ficha são `REP`, sem `OBR`, e
    a ficha recém-criada saía "Completa". `T-219`: sobre as perguntas da
    própria ficha — as mesmas de `campos`.

    `T-217`: `rotulo` é o nome do item para o aluno ("Aluguel"), ou `None`;
    `pede_nome`, se a tela deve pedir um ("Outro", despesa não listada).

    `T-254` (`RF-90`, `EC-35`): cada ficha traz as `margens` criadas dentro
    dela e os `dependentes` — margens e dívidas que perdem o pai se ela for
    removida. `escopo_pai`: o escopo dentro do qual este é criado, ou `None`;
    `escopos_filhos`: os criados dentro deste."""
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    # Duas consultas independentes em paralelo — `T-191`.
    respostas_brutas, itens = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False),
    )
    respostas = RespostasCaso(respostas=respostas_brutas)
    agrupado = _agrupar(itens)
    rotulos = rotulos_dos_itens(itens, colecao.registros)
    pais = {item.item_id: item.item_pai_id for item in itens if item.item_pai_id}
    # `T-254`: os escopos cujas fichas nascem DENTRO de uma deste (a margem
    # no vínculo) e as perguntas que apontam um item deste (`T-256`) —
    # ambos lidos do registro, nunca listados aqui.
    filhos = {e for e in EscopoRepeticao if escopo_pai(colecao.registros, e) is membro}
    referencias = [
        registro
        for registro in colecao.registros
        if registro.origem_opcoes.fonte == "ITENS_DO_ESCOPO"
        and registro.origem_opcoes.escopo is membro
        and registro.VARIAVEL_GRAVADA is not None
    ]
    em_aberto = itens_em_aberto(
        tuple(r for e in (membro, *filhos) for r in _perguntas_da_ficha(colecao, e)),
        respostas,
        agrupado,
        pais,
    )

    def ficha(item: ItemRepetido) -> dict[str, Any]:
        rotulo = rotulos.get(item.item_id)
        margens = [
            filho for filho in itens if filho.escopo in filhos and filho.item_pai_id == item.item_id
        ]
        dividas = [
            item_id
            for registro in referencias
            for item_id in agrupado.get(registro.escopo_repeticao, ())
            if respostas.valor_no_item(item_id, registro.VARIAVEL_GRAVADA or "") == item.item_id
        ]
        return {
            "item_id": item.item_id,
            "item_pai_id": item.item_pai_id,
            "rotulo": rotulo,
            "pede_nome": pede_nome(item.origem),
            "completa": item.item_id not in em_aberto,
            "campos": _campos_da_ficha(
                colecao, item.escopo, respostas, CASO_ID, item.item_id, rotulo, agrupado, rotulos
            ),
            # `AC-138`: cada margem sob o seu vínculo — nenhum total entre eles.
            "margens": [ficha(margem) for margem in margens],
            # `EC-35`: o que perde o pai se este item for removido.
            "dependentes": {
                "margens": [margem.item_id for margem in margens],
                "dividas": list(dict.fromkeys(dividas)),
            },
        }

    fichas = [ficha(item) for item in itens if item.escopo is membro]
    pai = escopo_pai(colecao.registros, membro)
    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "escopo": membro.value,
            "escopo_pai": pai.value if pai else None,
            "escopos_filhos": sorted(filho.value for filho in filhos),
            "fichas": fichas,
            # `T-310` (RF-100): a trilha por partes, na parte da ficha.
            "trilha": trilha_da_coleta(
                colecao.registros,
                percurso_da_coleta(colecao.registros, respostas, agrupado),
                cabeca.bloco,
            )
            if (cabeca := cabecas_das_fichas(colecao.registros).get(membro))
            else None,
        }
    )


@roteador.get("/{CASO_ID}/formulario/{escopo}/{item_id}")
def formulario_do_item(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    item_id: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> JSONResponse:
    """`T-314` (RF-102) — a ficha curta inteira numa tela: as perguntas
    exibíveis DO ITEM, cada uma serializada como na coleta
    (`serializar_pergunta_do_caso`, com `complementares` de `T-307`). A filha
    que uma opção abre vem só sob a mãe, nunca de novo na lista — o cliente
    a mostra pela tabela, sem avaliar condição (`RF-45`).

    `T-317` (RF-105): `posicao_do_item`/`total_de_itens` ("Despesa 2 de 4") e
    `itens_concluidos` — entre os itens do escopo com o mesmo pai."""
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    respostas_brutas, itens = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False),
    )
    item = next((i for i in itens if i.escopo is membro and i.item_id == item_id), None)
    if item is None:
        return JSONResponse({"erro": _MENSAGEM_ITEM_INEXISTENTE}, status_code=404)

    respostas = RespostasCaso(respostas=respostas_brutas)
    agrupado = _agrupar(itens)
    rotulos = rotulos_dos_itens(itens, colecao.registros)
    perguntas = perguntas_do_formulario(
        CASO_ID, colecao, membro, respostas, agrupado, item_id, rotulos
    )

    irmaos = [i for i in itens if i.escopo is membro and i.item_pai_id == item.item_pai_id]
    em_aberto = itens_em_aberto(
        _perguntas_da_ficha(colecao, membro),
        respostas,
        agrupado,
        {i.item_id: i.item_pai_id for i in itens if i.item_pai_id},
    )
    cabeca = cabecas_das_fichas(colecao.registros).get(membro)
    pai = escopo_pai(colecao.registros, membro)
    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "escopo": membro.value,
            "escopo_pai": pai.value if pai else None,
            "item_id": item_id,
            "rotulo": rotulos.get(item_id),
            "pede_nome": pede_nome(item.origem),
            "completa": item_id not in em_aberto,
            "perguntas": perguntas,
            "posicao_do_item": irmaos.index(item) + 1,
            "total_de_itens": len(irmaos),
            "itens_concluidos": sum(1 for i in irmaos if i.item_id not in em_aberto),
            "trilha": trilha_da_coleta(
                colecao.registros,
                percurso_da_coleta(colecao.registros, respostas, agrupado),
                cabeca.bloco,
            )
            if cabeca
            else None,
        }
    )


@roteador.post("/{CASO_ID}/concluir/{escopo}/{item_id}")
def concluir_item(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    item_id: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """`T-320` (RF-107, AC-169) — fecha o formulário da ficha curta: toda
    pergunta aberta do item precisa de resposta ou "Não sei" — os predicados
    de `itens_em_aberto`/`em_branco_no_item` (`T-201`), não uma lista nova.
    Faltando algo, `400` com a mensagem e as `pendencias` (nada é gravado:
    as respostas já foram, uma a uma, pela rota de `RF-69`). A despesa que
    pede nome também precisa dele.

    `T-321` (RF-108, AC-170): concluído, `proximo_item` é o próximo item
    pendente do escopo (mesmo pai) — depois deste, senão o primeiro antes —,
    ou `None` quando todos estão concluídos e a lista reabre."""
    exigir_coleta_editavel(CASO_ID, repositorio_casos)  # `RF-114`: em conferência, só leitura
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    respostas_brutas, itens = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False),
    )
    item = next((i for i in itens if i.escopo is membro and i.item_id == item_id), None)
    if item is None:
        return JSONResponse({"erro": _MENSAGEM_ITEM_INEXISTENTE}, status_code=404)

    respostas = RespostasCaso(respostas=respostas_brutas)
    agrupado = _agrupar(itens)
    rotulos = rotulos_dos_itens(itens, colecao.registros)
    da_ficha = _perguntas_da_ficha(colecao, membro)
    por_id = {registro.ID: registro for registro in da_ficha}
    pendencias = [
        {
            "ID": falta.ID,
            "item_id": item_id,
            "enunciado": montar_contexto_pergunta(
                por_id[falta.ID],
                respostas,
                item_id=item_id,
                rotulo_do_item=rotulos.get(item_id),
                itens_por_escopo=agrupado,
                rotulos=rotulos,
            ).enunciado,
        }
        for falta in em_branco_no_item(da_ficha, respostas, agrupado, item_id)
    ]
    if pede_nome(item.origem) and not item.nome:
        pendencias.insert(0, {"ID": "", "item_id": item_id, "enunciado": "Nome da despesa"})
    if pendencias:
        return JSONResponse(
            {
                "erro": f"{_MENSAGEM_FICHA_INCOMPLETA} "
                f"{'; '.join(str(p['enunciado']) for p in pendencias)}",
                "pendencias": pendencias,
            },
            status_code=400,
        )

    irmaos = [i.item_id for i in itens if i.escopo is membro and i.item_pai_id == item.item_pai_id]
    em_aberto = itens_em_aberto(
        da_ficha, respostas, agrupado, {i.item_id: i.item_pai_id for i in itens if i.item_pai_id}
    )
    posicao = irmaos.index(item_id)
    proximo = next((i for i in irmaos[posicao + 1 :] + irmaos[:posicao] if i in em_aberto), None)
    return JSONResponse(
        {"CASO_ID": CASO_ID, "escopo": membro.value, "item_id": item_id, "proximo_item": proximo}
    )


@roteador.post("/{CASO_ID}/fichas/{escopo}")
def criar_ficha(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """`AC-04` — cria um item com identificador estável (`D001`, `M002`…).

    O identificador vem de `RepositorioItens.proximo_identificador`, que
    conta TODAS as linhas do par `(CASO_ID, escopo)` — removidas inclusive —
    para que um número já usado nunca volte. Criar uma ficha não altera
    nenhuma das existentes: nenhuma resposta é tocada aqui.

    `T-217`: a ficha de despesa criada pela lista é uma despesa não listada
    (`B3.D11`) — as dos checklists nascem da resposta a eles.

    `T-254` (`AC-137`): ficha de escopo com pai (a margem) exige
    `item_pai_id` de um item ATIVO do escopo pai neste caso — senão `422` e
    nada é criado."""
    exigir_coleta_editavel(CASO_ID, repositorio_casos)  # `RF-114`: em conferência, só leitura
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    item_pai_id: str | None = None
    pai = escopo_pai(colecao.registros, membro)
    if pai is not None:
        item_pai_id = dados.get("item_pai_id", "")
        ativos_do_pai = {
            item.item_id
            for item in repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
            if item.escopo is pai
        }
        if item_pai_id not in ativos_do_pai:
            return JSONResponse({"erro": _MENSAGEM_PAI_INVALIDO}, status_code=422)

    # Duas consultas de LEITURA independentes em paralelo (`T-191`):
    # `proximo_identificador` só conta linhas existentes, não escreve nada
    # (a ficha em si só passa a existir quando uma resposta referencia o
    # `item_id` — ver a nota da rota, acima).
    origem = DESPESA_NAO_LISTADA if membro is EscopoRepeticao.ITEM_DESPESA else None
    item_id, respostas_brutas = duas_em_paralelo(
        lambda: repositorio_itens.proximo_identificador(CASO_ID, membro, origem, item_pai_id),
        lambda: repositorio.listar_do_caso(CASO_ID),
    )
    respostas = RespostasCaso(respostas=respostas_brutas)
    campos = _campos_da_ficha(colecao, membro, respostas, CASO_ID, item_id)

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "escopo": membro.value,
            "ficha": {
                "item_id": item_id,
                "item_pai_id": item_pai_id,
                "rotulo": None,
                "pede_nome": pede_nome(origem),
                "completa": False,
                "campos": campos,
                "margens": [],
                "dependentes": {"margens": [], "dividas": []},
            },
        },
        status_code=201,
    )


@roteador.delete("/{CASO_ID}/fichas/{escopo}/{item_id}")
def remover_ficha(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    item_id: str,
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """`AC-04` — marca o item como removido; **nunca** apaga a linha.

    É essa memória que impede o reaproveitamento do identificador. Remover
    a ficha `D002` não faz a próxima nascer `D002`."""
    exigir_coleta_editavel(CASO_ID, repositorio_casos)  # `RF-114`: em conferência, só leitura
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    ativos = {
        item.item_id
        for item in repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
        if item.escopo is membro
    }
    if item_id not in ativos:
        return JSONResponse({"erro": _MENSAGEM_ITEM_INEXISTENTE}, status_code=404)

    repositorio_itens.remover(CASO_ID, item_id)
    return JSONResponse({"CASO_ID": CASO_ID, "escopo": membro.value, "removido": item_id})


@roteador.put("/{CASO_ID}/fichas/{escopo}/{item_id}")
def nomear_ficha(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    escopo: str,
    item_id: str,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """`T-217` — o nome curto de "Outro" e da despesa não listada (§11,
    `B3.D01`–`D11`), que vira o título da ficha e o `[despesa]` de `B3.DF01`.

    Só item que pede nome aceita: os demais já têm o rótulo da opção
    marcada, e renomeá-los esconderia qual opção o aluno marcou."""
    exigir_coleta_editavel(CASO_ID, repositorio_casos)  # `RF-114`: em conferência, só leitura
    membro = _escopo_valido(escopo)
    if membro is None:
        return JSONResponse({"erro": _MENSAGEM_ESCOPO_INVALIDO}, status_code=400)

    item = next(
        (
            item
            for item in repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
            if item.escopo is membro and item.item_id == item_id
        ),
        None,
    )
    if item is None:
        return JSONResponse({"erro": _MENSAGEM_ITEM_INEXISTENTE}, status_code=404)
    if not pede_nome(item.origem):
        return JSONResponse({"erro": _MENSAGEM_ITEM_SEM_NOME}, status_code=400)

    nome = " ".join(dados.get("nome", "").split())
    if not nome or len(nome) > _NOME_MAXIMO:
        return JSONResponse({"erro": _MENSAGEM_NOME_INVALIDO}, status_code=400)

    repositorio_itens.nomear(CASO_ID, item_id, nome)
    return JSONResponse(
        {"CASO_ID": CASO_ID, "escopo": membro.value, "item_id": item_id, "rotulo": nome}
    )


@roteador.get("/{CASO_ID}/escopos")
def listar_escopos(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
) -> JSONResponse:
    """Os escopos de repetição que o questionário de fato usa.

    Derivado dos próprios registros (`escopo_repeticao`), nunca de uma lista
    escrita aqui — um escopo novo no YAML aparece sem tocar neste código
    (`RF-03`).

    `T-212`: cada escopo diz se está `aberto` para o caso — a condição da
    cabeça da ficha, avaliada aqui (`RF-52`); o cliente não recebe condição."""
    respostas = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))
    escopos = [
        {"escopo": escopo.value, "aberto": escopo_aberto(cabeca, respostas)}
        for escopo, cabeca in sorted(
            cabecas_das_fichas(colecao.registros).items(), key=lambda par: par[0].value
        )
    ]
    return JSONResponse({"CASO_ID": CASO_ID, "escopos": escopos})
