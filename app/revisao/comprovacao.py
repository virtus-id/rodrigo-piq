"""Fonte de comprovação por ficha e pendências de homologação — `RF-91`,
`RF-92`, `RF-93`, `RF-97` (`T-262`, `DE-06`, `DE-08`).

`plans/app-aluno.plan.md` §R9.5. Funções PURAS: recebem os registros, as
respostas e os itens ativos por escopo. Nada é gravado — níveis e pendências
são derivados a cada leitura (`R9.7`), para que não exista segunda fonte que
envelheça; a lista do revisor reflete as respostas ATUAIS (`R9-12`).

- **Nível** (`RF-91`): atributo da opção no YAML (`nivel_comprovacao`, com
  `nivel_comprovacao_se` avaliado no item — "Outra" com documento). Pergunta
  de fonte = registro com alguma opção que declara nível.
- **Pendência** (`RF-93`, `RF-97`): registro `indispensavel` ABERTO no item
  (condição avaliada naquele item) e em branco/`NAO_SEI` → `AUSENTE`; com a
  fonte da mesma ficha (mesmo bloco e escopo) em `PENDENTE_DE_CONFIRMACAO` →
  `PENDENTE_DE_CONFIRMACAO`. Pergunta fechada pela condição nunca é
  pendência (parcela de rotativo, `GAB-03`). Pendência é por RESPOSTA, não
  por `DESCONHECIDO` no estado: taxa anual respondida não bloqueia (`R9-9`).
  A opção "não sei" de uma seleção indispensável (taxa `DESCONHECIDA` em
  "Você sabe a taxa?") também é `AUSENTE` (`T-283`, `DE-06`).

**Não alimenta `CONFIABILIDADE_DADOS`** (`OQ-63`): nada aqui chega ao motor.
Nenhum `ID` de pergunta nem texto neste módulo (`AC-37`).

REGRAS: `RF-91`, `RF-92`, `RF-93`, `RF-97`, `AC-37`
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from collection.condicoes import avaliar
from collection.registro import (
    NIVEL_COMPROVACAO,
    EscopoRepeticao,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import NAO_SEI, RespostasCaso

REGRAS: Final[tuple[str, ...]] = ("RF-91", "RF-92", "RF-93", "RF-97", "AC-37")

# A fonte em nível 3 pende o VALOR informado; a seleção que diz se o valor é
# conhecido só pende por "não sei" — sem duplicar a pendência do valor (`T-283`).
_SELECOES: Final = (TipoResposta.SELECAO_UNICA, TipoResposta.SELECAO_MULTIPLA)


@dataclass(frozen=True, slots=True)
class NivelDaFicha:
    """O nível da fonte de uma ficha. `origem_fonte` é o `ID` da pergunta de
    fonte; `nivel` é `None` quando ainda não respondida."""

    item_id: str
    origem_fonte: str
    nivel: NIVEL_COMPROVACAO | None


@dataclass(frozen=True, slots=True)
class PendenciaHomologacao:
    """Um dado indispensável que impede a liberação. `item_id` é `None` para
    pergunta fora de ficha (renda)."""

    item_id: str | None
    ID_PERGUNTA: str
    motivo: Literal["AUSENTE", "PENDENTE_DE_CONFIRMACAO"]


def niveis_por_ficha(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[NivelDaFicha, ...]:
    """RF-91 — o nível de cada pergunta de fonte aberta em cada item ativo."""
    return tuple(
        NivelDaFicha(
            item_id=item_id,
            origem_fonte=registro.ID,
            nivel=_nivel(registro, respostas, item_id),
        )
        for registro in registros
        if _e_fonte(registro)
        for item_id in itens_por_escopo.get(registro.escopo_repeticao, ())
        if _aberta(registro, respostas, item_id)
    )


def pendencias_de_homologacao(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[PendenciaHomologacao, ...]:
    """RF-93/RF-97 — o que impede a liberação, na ordem dos registros."""
    pendencias: list[PendenciaHomologacao] = []
    for registro in registros:
        if not registro.indispensavel or registro.VARIAVEL_GRAVADA is None:
            continue
        if registro.escopo_repeticao is EscopoRepeticao.NENHUM:
            if _aberta(registro, respostas, None) and _ausente(
                registro, respostas.valor(registro.VARIAVEL_GRAVADA)
            ):
                pendencias.append(PendenciaHomologacao(None, registro.ID, "AUSENTE"))
            continue
        fontes = tuple(
            r
            for r in registros
            if _e_fonte(r)
            and (r.bloco, r.escopo_repeticao) == (registro.bloco, registro.escopo_repeticao)
        )
        for item_id in itens_por_escopo.get(registro.escopo_repeticao, ()):
            if not _aberta(registro, respostas, item_id):
                continue
            if _ausente(registro, respostas.valor_no_item(item_id, registro.VARIAVEL_GRAVADA)):
                pendencias.append(PendenciaHomologacao(item_id, registro.ID, "AUSENTE"))
            elif registro.tipo not in _SELECOES and any(
                _aberta(fonte, respostas, item_id)
                and _nivel(fonte, respostas, item_id)
                is NIVEL_COMPROVACAO.PENDENTE_DE_CONFIRMACAO
                for fonte in fontes
            ):
                pendencias.append(
                    PendenciaHomologacao(item_id, registro.ID, "PENDENTE_DE_CONFIRMACAO")
                )
    return tuple(pendencias)


def _e_fonte(registro: RegistroPergunta) -> bool:
    return registro.escopo_repeticao is not EscopoRepeticao.NENHUM and any(
        opcao.nivel_comprovacao is not None for opcao in registro.opcoes
    )


def _aberta(registro: RegistroPergunta, respostas: RespostasCaso, item_id: str | None) -> bool:
    condicao = registro.condicao_exibicao
    return condicao is None or avaliar(condicao, respostas, item_id)


def _ausente(registro: RegistroPergunta, valor: object) -> bool:
    """Em branco, `NAO_SEI`, ou a opção "não sei" do próprio registro
    (`admite_nao_sei` com `valor_interno`, ex. taxa `DESCONHECIDA`, `T-283`)."""
    return (
        valor is None
        or valor is NAO_SEI
        or any(o.admite_nao_sei and o.valor_interno == valor for o in registro.opcoes)
    )


def _nivel(
    registro: RegistroPergunta, respostas: RespostasCaso, item_id: str
) -> NIVEL_COMPROVACAO | None:
    assert registro.VARIAVEL_GRAVADA is not None
    valor = respostas.valor_no_item(item_id, registro.VARIAVEL_GRAVADA)
    opcao = next((o for o in registro.opcoes if o.valor_interno == valor), None)
    if opcao is None:
        return None
    se = opcao.nivel_comprovacao_se
    if se is not None and avaliar(se.condicao, respostas, item_id):
        return se.nivel
    return opcao.nivel_comprovacao
