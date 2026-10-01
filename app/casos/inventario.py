"""Pendências de inventário — `RF-86`, `RF-87`, `RF-88` (`T-246`, `DE-04`).

`plans/app-aluno.plan.md` §R9.5. Função PURA: recebe os registros, as
respostas e os itens ativos por escopo, e devolve o que impede o cálculo
final. Nunca grava nada — as pendências são derivadas a cada leitura
(`R9.7`), para que não exista segunda fonte que envelheça.

- **Dívidas** (`RF-87`): com `QUANTIDADE_DIVIDAS_DECLARADA_INICIAL` numérica,
  cadastradas abaixo (`DIVIDAS_FALTANDO`) ou acima (`DIVIDAS_ACIMA`, `EC-33`)
  do declarado bloqueiam. Declarada "não sei": a completude é a confirmação
  "esta foi a última" em alguma ficha de dívida (`AC-153`, `EC-32`).
- **Itens declarados** (`RF-88`): só a resposta `SIM` exige ao menos um item
  (`EC-34` — "não sei" não exige).
- **Quais dívidas faltam** (`T-324`): a pendência de dívidas faltando leva
  os tipos marcados na declaração de tipos sem nenhuma ficha daquele tipo
  e as fichas já cadastradas. A declaração dá só o total, nunca quantas
  por tipo — então não há contagem por tipo, só "tipos sem ficha".
- **Consignado sem vínculo** (`T-282`, `DE-04`, `AC-139`): dívida em que
  `B5.A02V` se aplica, sem nenhum vínculo cadastrado para apontar.

"Cadastrado" = item ATIVO com ao menos uma resposta: ficha criada e vazia
não conta. `ID_PARA_CORRIGIR` é resolvido pela `VARIAVEL_GRAVADA` no
registro — nenhum `ID` de pergunta aqui, nenhum texto (`AC-37`): a redação
vive em `textos/inventario.yaml`.

REGRAS: `RF-86`, `RF-87`, `RF-88`, `AC-37`
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Final

import yaml

from collection.condicoes import avaliar
from collection.opcoes_do_motor import sem_itens_para_escolher
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.respostas import RespostasCaso
from persistencia.app_aluno.eventos import EventoCaso, RepositorioEventosCaso

REGRAS: Final[tuple[str, ...]] = ("RF-86", "RF-87", "RF-88", "AC-37")

CAMINHO_TEXTOS: Final[Path] = Path(__file__).parent / "textos" / "inventario.yaml"

_QUANTIDADE_DECLARADA: Final[str] = "QUANTIDADE_DIVIDAS_DECLARADA_INICIAL"
_FIM_DO_CADASTRO: Final[str] = "SYS (loop)"
_ESTA_FOI_A_ULTIMA: Final[str] = "NAO_ESTA_FOI_A_ULTIMA"
_SIM: Final[str] = "SIM"
# T-324: os tipos declarados e o tipo/credor de cada ficha. Os `valor_interno`
# da declaração e da ficha são os mesmos códigos (`T-208`).
_TIPOS_DECLARADOS: Final[str] = "TIPOS_DIVIDA_DECLARADOS"
_TIPO_DA_FICHA: Final[str] = "TIPO_DIVIDA"
_CREDOR: Final[str] = "CREDOR"

# Trilha (`RF-31`) e painel (`RF-35`): o bloqueio é um motivo NOMEADO — o
# `detalhe` leva só os tipos de pendência, nunca valor (NFR da Rodada 9).
TIPO_EVENTO_CALCULO_BLOQUEADO: Final[str] = "calculo_bloqueado_inventario"


class TIPO_PENDENCIA_INVENTARIO(Enum):
    DIVIDAS_FALTANDO = "DIVIDAS_FALTANDO"
    DIVIDAS_ACIMA = "DIVIDAS_ACIMA"
    DIVIDAS_SEM_CONFIRMACAO = "DIVIDAS_SEM_CONFIRMACAO"
    RENDA_EXTRA_SEM_ITEM = "RENDA_EXTRA_SEM_ITEM"
    VINCULO_SEM_ITEM = "VINCULO_SEM_ITEM"
    NAO_MENSAL_SEM_ITEM = "NAO_MENSAL_SEM_ITEM"
    CONSIGNADO_SEM_VINCULO = "CONSIGNADO_SEM_VINCULO"


# RF-88 — declaração "Sim" → escopo em que ao menos um item é exigido.
_DECLARACOES_DE_ITEM: Final[
    tuple[tuple[TIPO_PENDENCIA_INVENTARIO, str, EscopoRepeticao], ...]
] = (
    (
        TIPO_PENDENCIA_INVENTARIO.RENDA_EXTRA_SEM_ITEM,
        "RENDA_RECORRENTE_ADICIONAL_EXISTE",
        EscopoRepeticao.RENDA_ADICIONAL_ID,
    ),
    (
        TIPO_PENDENCIA_INVENTARIO.VINCULO_SEM_ITEM,
        "VINCULO_CONSIGNAVEL",
        EscopoRepeticao.VINCULO_ID,
    ),
    (
        TIPO_PENDENCIA_INVENTARIO.NAO_MENSAL_SEM_ITEM,
        "DESPESAS_NAO_MENSAIS_EXISTE",
        EscopoRepeticao.DESPESA_NAO_MENSAL_ID,
    ),
)


# T-282 (DE-04) — escopo das opções de uma pergunta `ITENS_DO_ESCOPO` que
# ficou sem item para escolher → a pendência e a declaração a corrigir. A
# pergunta em si (qual, e quando se aplica) vem do registro, nunca daqui.
_REFERENCIAS_SEM_ITEM: Final[
    Mapping[EscopoRepeticao, tuple[TIPO_PENDENCIA_INVENTARIO, str]]
] = {
    EscopoRepeticao.VINCULO_ID: (
        TIPO_PENDENCIA_INVENTARIO.CONSIGNADO_SEM_VINCULO,
        "VINCULO_CONSIGNAVEL",
    ),
}


@dataclass(frozen=True, slots=True)
class FichaDeDivida:
    """T-324 — uma ficha de dívida cadastrada, como o aluno a reconhece:
    credor e rótulo do tipo, `None` enquanto não respondidos."""

    item_id: str
    credor: str | None
    tipo: str | None


@dataclass(frozen=True, slots=True)
class DetalheDasDividas:
    """T-324 — o que acompanha `DIVIDAS_FALTANDO`: rótulos dos tipos
    declarados ainda sem ficha, as fichas cadastradas e a ficha criada e
    ainda vazia (a reabrir antes de criar outra), se houver."""

    tipos_sem_ficha: tuple[str, ...]
    fichas: tuple[FichaDeDivida, ...]
    ficha_vazia: str | None


@dataclass(frozen=True, slots=True)
class PendenciaInventario:
    """Uma pendência que bloqueia o cálculo. `ID_PARA_CORRIGIR` é a pergunta
    da declaração (a ação direta de `AC-154`); `escopo`, quando a correção
    também pode ser cadastrar item, é o escopo das fichas a abrir."""

    tipo: TIPO_PENDENCIA_INVENTARIO
    declaradas: int | None
    cadastradas: int | None
    ID_PARA_CORRIGIR: str
    escopo: EscopoRepeticao | None
    dividas: DetalheDasDividas | None = None


def pendencias_de_inventario(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[PendenciaInventario, ...]:
    """RF-86..RF-88 — as pendências de inventário do caso, na ordem:
    dívidas primeiro, depois os itens declarados."""
    com_resposta = {r.item_id for r in respostas.respostas if r.item_id}

    def cadastrados(escopo: EscopoRepeticao) -> tuple[str, ...]:
        return tuple(i for i in itens_por_escopo.get(escopo, ()) if i in com_resposta)

    pendencias: list[PendenciaInventario] = []
    dividas = cadastrados(EscopoRepeticao.DIVIDA_ID)
    declaradas = respostas.valor(_QUANTIDADE_DECLARADA)
    id_declaradas = _id_da_variavel(registros, _QUANTIDADE_DECLARADA)
    if id_declaradas is not None and isinstance(declaradas, int) and declaradas != len(dividas):
        faltando = declaradas > len(dividas)
        pendencias.append(
            PendenciaInventario(
                tipo=TIPO_PENDENCIA_INVENTARIO.DIVIDAS_FALTANDO
                if faltando
                else TIPO_PENDENCIA_INVENTARIO.DIVIDAS_ACIMA,
                declaradas=declaradas,
                cadastradas=len(dividas),
                ID_PARA_CORRIGIR=id_declaradas,
                escopo=EscopoRepeticao.DIVIDA_ID if faltando else None,
                dividas=_detalhe_das_dividas(
                    registros,
                    respostas,
                    dividas,
                    itens_por_escopo.get(EscopoRepeticao.DIVIDA_ID, ()),
                )
                if faltando
                else None,
            )
        )
    if id_declaradas is not None and declaradas is not None and not isinstance(declaradas, int):
        # Declarada "não sei" (AC-153): só a confirmação "esta foi a última"
        # numa ficha de dívida encerra a contagem.
        confirmada = any(
            respostas.valor_no_item(item_id, _FIM_DO_CADASTRO) == _ESTA_FOI_A_ULTIMA
            for item_id in dividas
        )
        if not confirmada:
            pendencias.append(
                PendenciaInventario(
                    tipo=TIPO_PENDENCIA_INVENTARIO.DIVIDAS_SEM_CONFIRMACAO,
                    declaradas=None,
                    cadastradas=len(dividas),
                    ID_PARA_CORRIGIR=id_declaradas,
                    escopo=EscopoRepeticao.DIVIDA_ID,
                )
            )

    for tipo, variavel, escopo in _DECLARACOES_DE_ITEM:
        id_declaracao = _id_da_variavel(registros, variavel)
        if (
            id_declaracao is not None
            and respostas.valor(variavel) == _SIM
            and not cadastrados(escopo)
        ):
            pendencias.append(
                PendenciaInventario(
                    tipo=tipo,
                    declaradas=None,
                    cadastradas=0,
                    ID_PARA_CORRIGIR=id_declaracao,
                    escopo=escopo,
                )
            )
    pendencias.extend(_referencias_sem_item(registros, respostas, itens_por_escopo))
    return tuple(pendencias)


def _detalhe_das_dividas(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    cadastradas: tuple[str, ...],
    todas: tuple[str, ...],
) -> DetalheDasDividas:
    """T-324 — relaciona os tipos declarados com os tipos das fichas. Rótulos
    vêm das opções do registro de cada variável; código sem opção (ou o
    "não tenho certeza", que não é tipo) não aparece."""
    rotulos_declarados = _rotulos(registros, _TIPOS_DECLARADOS)
    rotulos_da_ficha = _rotulos(registros, _TIPO_DA_FICHA)
    declarados = respostas.valor(_TIPOS_DECLARADOS)
    marcados = declarados if isinstance(declarados, frozenset) else frozenset()
    tipos_com_ficha = {respostas.valor_no_item(i, _TIPO_DA_FICHA) for i in cadastradas}
    fichas = []
    for item_id in cadastradas:
        tipo = respostas.valor_no_item(item_id, _TIPO_DA_FICHA)
        credor = respostas.valor_no_item(item_id, _CREDOR)
        fichas.append(
            FichaDeDivida(
                item_id=item_id,
                credor=credor if isinstance(credor, str) and credor.strip() else None,
                tipo=rotulos_da_ficha.get(tipo) if isinstance(tipo, str) else None,
            )
        )
    return DetalheDasDividas(
        tipos_sem_ficha=tuple(
            rotulo
            for codigo, rotulo in rotulos_declarados.items()
            if codigo in marcados and codigo not in tipos_com_ficha
        ),
        fichas=tuple(fichas),
        ficha_vazia=next((i for i in todas if i not in cadastradas), None),
    )


def _rotulos(registros: tuple[RegistroPergunta, ...], variavel: str) -> dict[str, str]:
    """`valor_interno → rótulo` das opções da pergunta que grava `variavel`,
    na ordem do registro. A opção "não sei" não é tipo e fica de fora."""
    registro = next((r for r in registros if r.VARIAVEL_GRAVADA == variavel), None)
    if registro is None:
        return {}
    return {
        o.valor_interno: o.rotulo
        for o in registro.opcoes
        if o.valor_interno is not None and not o.admite_nao_sei
    }


def _referencias_sem_item(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[PendenciaInventario, ...]:
    """T-282 (`DE-04`, `AC-139`) — a pergunta que aponta um item do caso
    (`B5.A02V`, o vínculo da dívida consignada) se aplica a algum item, mas
    o escopo apontado não tem item nenhum: a ficha segue (a pergunta nem é
    exibida, `sem_itens_para_escolher`) e a falta bloqueia só o cálculo
    final. Uma pendência por escopo, com atalho para cadastrar o item."""
    faltando: dict[EscopoRepeticao, PendenciaInventario] = {}
    for registro in registros:
        escopo = registro.origem_opcoes.escopo
        if (
            escopo is None
            or escopo not in _REFERENCIAS_SEM_ITEM
            or escopo in faltando
            or not sem_itens_para_escolher(registro, itens_por_escopo)
        ):
            continue
        tipo, variavel = _REFERENCIAS_SEM_ITEM[escopo]
        id_declaracao = _id_da_variavel(registros, variavel)
        condicao = registro.condicao_exibicao
        if id_declaracao is not None and any(
            condicao is None or avaliar(condicao, respostas, item_id)
            for item_id in itens_por_escopo.get(registro.escopo_repeticao, ())
        ):
            faltando[escopo] = PendenciaInventario(
                tipo=tipo,
                declaradas=None,
                cadastradas=0,
                ID_PARA_CORRIGIR=id_declaracao,
                escopo=escopo,
            )
    return tuple(faltando.values())


class ErroInventarioIncompleto(Exception):
    """RF-86 — o cálculo final foi recusado por inventário incompleto. Carrega
    as pendências para a porta que recusou montar a resposta ao aluno."""

    def __init__(self, pendencias: tuple[PendenciaInventario, ...]) -> None:
        self.pendencias = pendencias
        super().__init__(",".join(p.tipo.value for p in pendencias))


def exigir_inventario_completo(
    pendencias: tuple[PendenciaInventario, ...],
    *,
    caso_id: str,
    repositorio_eventos: RepositorioEventosCaso,
    agora: datetime | None = None,
) -> None:
    """RF-86 (`T-248`) — a guarda ÚNICA das duas portas do cálculo
    (`rotas_calculo._preparar_calculo` e `acompanhamento.disparar_recalculo`),
    chamada ANTES de qualquer transição: o caso nunca fica em `CALCULANDO`.
    Com pendência, registra o motivo na trilha (sem valor) e levanta
    `ErroInventarioIncompleto`; sem pendência, não faz nada."""
    if not pendencias:
        return
    repositorio_eventos.registrar(
        EventoCaso(
            evento_id=f"EVENTO_{uuid.uuid4().hex}",
            CASO_ID=caso_id,
            tipo_evento=TIPO_EVENTO_CALCULO_BLOQUEADO,
            estado_de=None,
            estado_para=None,
            detalhe=",".join(p.tipo.value for p in pendencias),
            ocorrido_em=agora if agora is not None else datetime.now(UTC),
        )
    )
    raise ErroInventarioIncompleto(pendencias)


def mensagem_da_pendencia(pendencia: PendenciaInventario) -> str:
    """A mensagem ao aluno, de `textos/inventario.yaml` — `RF-87` literal
    para dívidas faltando (`AC-133`); as demais, redação aprovada pelo
    produto (`T-289`)."""
    textos = _textos()
    chave = pendencia.tipo.value
    if pendencia.tipo is TIPO_PENDENCIA_INVENTARIO.DIVIDAS_FALTANDO:
        assert pendencia.declaradas is not None and pendencia.cadastradas is not None
        faltam = pendencia.declaradas - pendencia.cadastradas
        if pendencia.declaradas == 1:
            chave = "DIVIDAS_FALTANDO_UMA_DE_UMA"
        elif faltam == 1:
            chave = "DIVIDAS_FALTANDO_UMA"
        return textos[chave].format(
            declaradas=pendencia.declaradas, cadastradas=pendencia.cadastradas, faltam=faltam
        )
    return textos[chave].format(
        declaradas=pendencia.declaradas, cadastradas=pendencia.cadastradas, faltam=None
    )


@cache
def _textos(caminho: Path = CAMINHO_TEXTOS) -> Mapping[str, str]:
    with caminho.open(encoding="utf-8") as arquivo:
        bruto = yaml.safe_load(arquivo)
    return {str(chave): str(valor) for chave, valor in bruto.items()}


def _id_da_variavel(registros: tuple[RegistroPergunta, ...], variavel: str) -> str | None:
    """A pergunta que grava `variavel` — a primeira, quando há mais de uma.
    `None` quando o questionário não tem a declaração: sem pergunta, não há
    o que declarar nem pendência sem destino."""
    return next((r.ID for r in registros if r.VARIAVEL_GRAVADA == variavel), None)
