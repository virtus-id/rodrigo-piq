"""Serialização do plano, da fila de revisão e do painel — `RF-50`, `RF-51`
(T-140).

**Por que este módulo existe.** As telas do plano, da revisão e do operador
passam a ser React (`RF-50`: nenhuma tela fora do template do protótipo).
O servidor deixa de renderizar HTML para elas e passa a entregar os MESMOS
campos que os templates recebiam — nada a mais, nada a menos.

**O que NÃO muda: `report/templates/plano/plano.html` continua existindo.**
Ele não é servido a navegador nenhum a partir daqui, mas `report/pdf.py`
renderiza aquele mesmo arquivo para gerar o PDF. `RF-21`/`AC-14` exigem que
a redação canônica de `Q-03` viva em UM lugar só, compartilhado por tela e
PDF; apagá-lo criaria uma segunda cópia do texto normativo — exatamente o
que aquele critério proíbe. O texto continua saindo de lá: é
`ContextoPlano.titulo`/`corpo`, montado por `report/plano.py` a partir de
`textos-canonicos.yaml`, e é isso que este módulo transporta.

**Lei nº 3 intacta.** Todo valor aqui é leitura de campo de um
`ContextoPlano` já montado — nenhuma aritmética, nenhuma derivação. Se uma
tela precisasse de um número que não é campo do contexto, a resposta seria
Open Question ao especialista, nunca uma conta nova nesta camada.

REGRAS: `RF-50`, `RF-51`, `RF-21`, `AC-14`, `AC-16`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from app.revisao.comprovacao import NivelDaFicha
from app.revisao.fila import ItemFila
from report.plano import ContextoEstadoInputs, ContextoPlano, TextosCanonicosPlano

REGRAS: Final[tuple[str, ...]] = ("RF-50", "RF-51", "RF-21", "AC-14", "AC-16")


def rotulo_do_nivel(nivel: NivelDaFicha, textos: TextosCanonicosPlano) -> str:
    """`RF-91` — o rótulo do nível, de `textos-canonicos.yaml`; fonte sem
    resposta é "não informado", nunca um nível presumido."""
    chave = nivel.nivel.value if nivel.nivel is not None else "NAO_INFORMADO"
    return textos.rotulos_de_comprovacao.get(chave, chave)


def fontes_por_divida(
    niveis: tuple[NivelDaFicha, ...], textos: TextosCanonicosPlano
) -> dict[str, str]:
    """`RF-92` (`T-267`) — `item_id` → rótulo da fonte dos DADOS da dívida:
    a primeira pergunta de fonte da ficha, na ordem dos registros (a do
    Bloco 5; as de proposta vêm depois)."""
    fontes: dict[str, str] = {}
    for nivel in niveis:
        fontes.setdefault(nivel.item_id, rotulo_do_nivel(nivel, textos))
    return fontes


def serializar_plano(
    contexto: ContextoPlano,
    fontes: Mapping[str, str] | None = None,
    orientacoes_seguro: Mapping[str, str] | None = None,
    *,
    para_revisor: bool = False,
) -> dict[str, Any]:
    """`ContextoPlano` → JSON, campo a campo.

    `titulo` e `corpo` são a redação canônica de `Q-03`, carregada de
    `textos-canonicos.yaml` — transportada verbatim, jamais reescrita aqui
    (`AC-14`: caractere por caractere).

    O carimbo de versão (`ENGINE_VERSION`/`PARAMETROS_VERSION`) acompanha a
    saída, como `AC-16` exige — uma tela sem carimbo é uma tela que não diz
    de qual cálculo veio.

    `fontes` (`T-267`, `RF-92`): `DIVIDA_ID` → rótulo da fonte de
    comprovação, derivado das respostas (não do snapshot); `None` quando a
    dívida não tem ficha ativa.

    `orientacoes_seguro` (`T-245`, `RF-82`): `DIVIDA_ID` → orientação sobre
    o seguro prestamista, só para dívida com seguro; `None` nas demais.

    `para_revisor` (`T-305`): só o revisor recebe `JUSTIFICATIVA_POSICAO`.
    """
    fontes = fontes or {}
    orientacoes_seguro = orientacoes_seguro or {}
    return {
        "titulo": contexto.titulo,
        "corpo": contexto.corpo,
        "ordem": [
            {
                "posicao": posicao.posicao,
                "indice": posicao.indice,
                "total": posicao.total,
                "DIVIDA_ID": posicao.DIVIDA_ID,
                # `JUSTIFICATIVA_POSICAO` é o texto de AUDITORIA do motor —
                # o revisor precisa dele para refazer a decisão (`AC-29`).
                # `explicacao` (T-177) é o mesmo "porquê" dito ao ALUNO.
                # `T-305`: o texto técnico não sai para o aluno.
                **(
                    {"JUSTIFICATIVA_POSICAO": posicao.JUSTIFICATIVA_POSICAO}
                    if para_revisor
                    else {}
                ),
                "explicacao": posicao.explicacao,
                # `T-304` (`DE-08`): lido do cronograma; `None` = não disponível.
                "mes_de_quitacao": posicao.mes_de_quitacao,
                "fonte": fontes.get(posicao.DIVIDA_ID),
                "orientacao_seguro": orientacoes_seguro.get(posicao.DIVIDA_ID),
                "valores_de_apoio": [
                    {"rotulo": rotulo, "valor": valor}
                    for rotulo, valor in posicao.valores_de_apoio
                ],
            }
            for posicao in contexto.ordem
        ],
        "PRAZO_TOTAL": contexto.PRAZO_TOTAL,
        "CUSTO_FUTURO_TOTAL": contexto.CUSTO_FUTURO_TOTAL,
        "valor_mensal_destinado": contexto.valor_mensal_destinado,
        "ENGINE_VERSION": contexto.ENGINE_VERSION,
        "PARAMETROS_VERSION": contexto.PARAMETROS_VERSION,
        "cenario": contexto.cenario.value
        if hasattr(contexto.cenario, "value")
        else str(contexto.cenario),
        "acoes": [
            {
                "DIVIDA_ID": acao.DIVIDA_ID,
                "descricao": acao.descricao,
                "prioridade_excepcional": acao.prioridade_excepcional,
            }
            for acao in contexto.acoes
        ],
        "pendencias": None
        if contexto.pendencias is None
        else {
            "inventario_incompleto": contexto.pendencias.inventario_incompleto,
            "campos_faltantes_por_divida": [
                {"DIVIDA_ID": divida, "campos": list(campos)}
                for divida, campos in contexto.pendencias.campos_faltantes_por_divida
            ],
        },
        "MODO_ESTABILIZACAO": contexto.MODO_ESTABILIZACAO,
        "RESULTADO_CAIXA_OBSERVADO": contexto.RESULTADO_CAIXA_OBSERVADO,
        "reserva_mobilizavel": {
            # `AC-70`: reserva desconhecida é ESTADO explícito, nunca
            # `R$ 0,00` e nunca campo omitido.
            "pendente_de_decisao": contexto.reserva_mobilizavel.pendente_de_decisao,
            "valor": contexto.reserva_mobilizavel.valor,
        },
        # `T-276` (RF-98, AC-152): seção à parte, lida do snapshot pelo
        # contexto — nenhum campo acima vem daqui.
        "cenario_adicional": None
        if contexto.cenario_adicional is None
        else {
            "rotulo": contexto.cenario_adicional.rotulo,
            "explicacao": contexto.cenario_adicional.explicacao,
            "PRAZO_TOTAL": contexto.cenario_adicional.PRAZO_TOTAL,
            "CUSTO_FUTURO_TOTAL": contexto.cenario_adicional.CUSTO_FUTURO_TOTAL,
            "ordem": list(contexto.cenario_adicional.ordem),
            "itens": [
                {"ITEM_ID": item.ITEM_ID, "mes": item.mes, "valor": item.valor}
                for item in contexto.cenario_adicional.itens
            ],
        },
        "nao_projetados": [
            {"ITEM_ID": item_id, "motivo": motivo} for item_id, motivo in contexto.nao_projetados
        ],
    }


def serializar_item_da_fila(item: ItemFila) -> dict[str, Any]:
    """Uma linha da fila de revisão.

    `entra_por_politica` e `e_metodologico` seguem SEPARADOS — um teste
    estático falha se forem combinados num único booleano. São coisas
    diferentes: a política do piloto (100% revisado) e o campo
    `REVISAO_HUMANA_OBRIGATORIA` que o motor levantou.
    """
    snapshot = item.snapshot
    return {
        "CASO_ID": item.CASO_ID,
        "SNAPSHOT_ID": snapshot.SNAPSHOT_ID,
        "versao": snapshot.versao,
        "DATA_REFERENCIA": snapshot.DATA_REFERENCIA.isoformat(),
        "MOTIVO_RECALCULO": snapshot.MOTIVO_RECALCULO,
        "EVENTO_RECALCULO": (
            snapshot.EVENTO_RECALCULO.value
            if snapshot.EVENTO_RECALCULO is not None
            and hasattr(snapshot.EVENTO_RECALCULO, "value")
            else snapshot.EVENTO_RECALCULO
        ),
        "METODO_RECOMENDADO_PIQ": (
            snapshot.METODO_RECOMENDADO_PIQ.value
            if hasattr(snapshot.METODO_RECOMENDADO_PIQ, "value")
            else str(snapshot.METODO_RECOMENDADO_PIQ)
        ),
        "STATUS_METODO": (
            snapshot.STATUS_METODO.value
            if hasattr(snapshot.STATUS_METODO, "value")
            else str(snapshot.STATUS_METODO)
        ),
        "entra_por_politica": item.entra_por_politica,
        "e_metodologico": item.e_metodologico,
        "ENGINE_VERSION": snapshot.ENGINE_VERSION,
        "PARAMETROS_VERSION": snapshot.PARAMETROS_VERSION,
    }


def serializar_estado_inputs(contexto: ContextoEstadoInputs) -> dict[str, Any]:
    """`AC-29` — os `estado_inputs` que produziram o snapshot, para a tela
    de comparação do revisor.

    **Transporte, nunca formatação.** Cada `valor` já vem pronto de
    `montar_contexto_estado_inputs`, que passou por
    `_formatar_valor_ou_desconhecido` — é lá que se decide como um campo
    desconhecido aparece, e é lá que `DESCONHECIDO` deixa de poder virar
    `0` ou string vazia (`AC-08`/`GAB-03`). Reformatar aqui criaria uma
    segunda regra de exibição, divergente da primeira.

    Nenhum campo é omitido: o revisor compara o plano contra o estado
    COMPLETO, e um campo ausente da tela é um campo que ninguém confere.
    """
    return {
        "campos": [{"nome": c.nome, "valor": c.valor} for c in contexto.campos],
        "perfil_comportamental": [
            {"nome": c.nome, "valor": c.valor} for c in contexto.perfil_comportamental
        ],
        "sinais_comportamentais": [
            {"nome": c.nome, "valor": c.valor} for c in contexto.sinais_comportamentais
        ],
        "dividas": [
            {
                "DIVIDA_ID": d.DIVIDA_ID,
                "campos": [{"nome": c.nome, "valor": c.valor} for c in d.campos],
            }
            for d in contexto.dividas
        ],
    }
