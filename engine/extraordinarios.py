"""Recursos extraordinários na projeção — §15 · RF-70 a RF-76 · `DE-02` ·
T-155, T-162 (plano `R9M.4`).

O ataque de hoje (§13.3, `calcular_EXTRAORDINARIOS_RECOMENDADOS`) **não
muda**. Este módulo decide, POR ITEM, o que vira aporte pontual no
cronograma: `selecionar_aportes` particiona `recursos_extraordinarios` em
`AporteProjetado` (valor destinado a um único mês da simulação) ou
`ItemNaoProjetado` (com o motivo), e `aportes_por_mes` é a ÚNICA soma — por
mês, para alimentar `simular_cenario` (`engine/ciclo_mensal.py`).

**Só certeza e prazo decidem (`RF-72`).** Nenhuma leitura do tipo do
recurso: o campo nem existe em `RecursoExtraordinario`, e `AC-121` vale por
construção.

**Mês previsto (`OQ-47`, resolvida em 2026-09-30).** Último mês da janela —
`ATE_30D` → 1, `1_3M` → 3, `4_6M` → 6, `7_12M` → 12. É regra normativa, não
calibração: não entra na fonte de parâmetros e a contagem da §8 não muda
(`AC-126`). Exceção de `OQ-50`: `CONFIRMADO ∧ ATE_30D` já é ataque de hoje
(§13.3) e nunca é duplicado em aporte (`RF-73`, `AC-130`); `PROVAVEL`/
`POSSIVEL` com `ATE_30D` entram no mês 1 do cenário adicional (`RF-71`).
`NAO_SEI` não ganha janela presumida (`EC-51`).

**Preservação de `RF-74` — decisão do responsável do produto
(2026-09-30, plano `R9M.10` #1).** A preservação É a trava de déficit já
existente do §13.4 (a mesma de `derivar_RESERVA_RECOMENDADA`): com
`RESULTADO_MENSAL_ATUAL < 0` nenhum aporte é destinado (`RF-76`: o
extraordinário não cobre déficit estrutural); fora dela o valor destinado é o
valor líquido do item. Nenhuma dedução de essenciais/sazonais — eles já estão
fora da capacidade, deduzi-los de novo seria dupla contagem (`OQ-48`).
Decisão reversível: vive numa única expressão em `selecionar_aportes`.

Pureza (spec §5): tudo chega por parâmetro; nada de relógio, arquivo ou
global mutável.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import localcontext
from enum import Enum
from types import MappingProxyType
from typing import Final

from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    JANELA_RECURSO_EXTRAORDINARIO,
    RecursoExtraordinario,
)
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import DESCONHECIDO, METODO, Dinheiro, Meses

REGRAS: Final[tuple[str, ...]] = (
    "RF-70",
    "RF-71",
    "RF-72",
    "RF-73",
    "RF-74",
    "RF-75",
    "RF-76",
    "§15",
    "§13.3",
    "§13.4",
)

# OQ-47 (resolvida) — regra, não calibração. NAO_SEI fica de fora de
# propósito: não tem mês (EC-51).
MES_PREVISTO_POR_JANELA: Final[Mapping[JANELA_RECURSO_EXTRAORDINARIO, Meses]] = (
    MappingProxyType(
        {
            JANELA_RECURSO_EXTRAORDINARIO.ATE_30D: 1,
            JANELA_RECURSO_EXTRAORDINARIO.UM_A_TRES_MESES: 3,
            JANELA_RECURSO_EXTRAORDINARIO.QUATRO_A_SEIS_MESES: 6,
            JANELA_RECURSO_EXTRAORDINARIO.SETE_A_DOZE_MESES: 12,
        }
    )
)


class MOTIVO_NAO_PROJETADO(Enum):
    """Por que um item não virou aporte — visível no snapshot (`EC-51`,
    `EC-52`)."""

    ATAQUE_DE_HOJE = "ATAQUE_DE_HOJE"  # CONFIRMADO ∧ ATE_30D → §13.3 (RF-73, OQ-50, AC-130)
    CERTEZA_FORA_DO_CONJUNTO = "CERTEZA_FORA_DO_CONJUNTO"  # PROVAVEL/POSSIVEL na base (RF-71)
    VALOR_DESCONHECIDO = "VALOR_DESCONHECIDO"  # EC-52 — nunca vira 0
    JANELA_NAO_SEI = "JANELA_NAO_SEI"  # EC-51
    TRAVA_DEFICIT_ESTRUTURAL = "TRAVA_DEFICIT_ESTRUTURAL"  # RF-74/RF-76 (R9M.10 #1)
    FORA_DO_HORIZONTE = "FORA_DO_HORIZONTE"  # OQ-46, EC-56 — atribuído após a simulação


@dataclass(frozen=True, slots=True)
class AporteProjetado:
    """RF-70/RF-75 — UM item destinado a UM mês; nunca somado a outro item."""

    ITEM_ID: str
    mes: Meses  # 1 (só PROVAVEL/POSSIVEL) | 3 | 6 | 12
    VALOR_DESTINADO: Dinheiro  # ≤ VALOR_RECURSO_EXTRAORDINARIO (AC-126)


@dataclass(frozen=True, slots=True)
class ItemNaoProjetado:
    ITEM_ID: str
    motivo: MOTIVO_NAO_PROJETADO


@dataclass(frozen=True, slots=True)
class CenarioAdicional:
    """RF-71 · OQ-49 — segunda projeção, só do método recomendado da base,
    com os `CONFIRMADO` projetados MAIS os `PROVAVEL` e `POSSIVEL`. Nunca
    publicada como ordem: não alimenta comparação, método, ordem, prazo,
    custo nem `Diagnostico` (`AC-120`)."""

    metodo: METODO
    ORDEM_QUITACAO: tuple[str, ...]
    PRAZO_TOTAL: Meses
    CUSTO_FUTURO_TOTAL: Dinheiro
    MESES_PRIMEIRA_VITORIA: Meses | None
    ESTOUROU_HORIZONTE: bool
    aportes: tuple[AporteProjetado, ...]


@dataclass(frozen=True, slots=True)
class ProjecaoExtraordinarios:
    """Campo `SnapshotOrdem.projecao_extraordinarios` (T-163)."""

    aportes_base: tuple[AporteProjetado, ...]  # aplicados no cenário recomendado
    nao_projetados: tuple[ItemNaoProjetado, ...]  # inclui FORA_DO_HORIZONTE
    cenario_adicional: CenarioAdicional | None  # None ⇔ nenhum PROVAVEL/POSSIVEL projetável


PROJECAO_VAZIA: Final[ProjecaoExtraordinarios] = ProjecaoExtraordinarios((), (), None)  # EC-55


def selecionar_aportes(
    recursos: tuple[RecursoExtraordinario, ...],
    *,
    certezas: frozenset[CERTEZA_RECURSO_EXTRAORDINARIO],
    RESULTADO_MENSAL_ATUAL: Dinheiro,
) -> tuple[tuple[AporteProjetado, ...], tuple[ItemNaoProjetado, ...]]:
    """RF-70 a RF-75 — partição por item: cada `ITEM_ID` cai em EXATAMENTE
    uma das duas tuplas (origem única, `RF-73`). `ITEM_ID` repetido é
    `ValueError` — bug de montagem, nunca soma silenciosa (`RF-75`).

    Ordem dos motivos: certeza fora de `certezas` → valor `DESCONHECIDO`
    (`EC-52`, o item também é pulado pela §13.3) → `CONFIRMADO ∧ ATE_30D`
    (§13.3, `RF-73`/`OQ-50`) → `NAO_SEI` (`EC-51`) → trava de déficit
    (`RF-74`).
    """
    ids = [recurso.ITEM_ID for recurso in recursos]
    if len(ids) != len(set(ids)):
        raise ValueError(f"ITEM_ID repetido em recursos_extraordinarios: {ids!r} (RF-75)")

    # RF-74 — decisão do responsável do produto (2026-09-30, plano R9M.10 #1):
    # a preservação é a trava de déficit do §13.4. Se for revista, é esta linha.
    trava_deficit_estrutural = RESULTADO_MENSAL_ATUAL < dinheiro(0)

    aportes: list[AporteProjetado] = []
    nao_projetados: list[ItemNaoProjetado] = []
    for recurso in recursos:
        valor = recurso.VALOR_RECURSO_EXTRAORDINARIO
        mes = MES_PREVISTO_POR_JANELA.get(recurso.JANELA_RECURSO_EXTRAORDINARIO)
        if recurso.CERTEZA_RECURSO_EXTRAORDINARIO not in certezas:
            motivo = MOTIVO_NAO_PROJETADO.CERTEZA_FORA_DO_CONJUNTO
        elif valor is DESCONHECIDO:
            motivo = MOTIVO_NAO_PROJETADO.VALOR_DESCONHECIDO
        elif (
            recurso.CERTEZA_RECURSO_EXTRAORDINARIO is CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO
            and recurso.JANELA_RECURSO_EXTRAORDINARIO is JANELA_RECURSO_EXTRAORDINARIO.ATE_30D
        ):
            # OQ-50: já está no ataque de hoje (§13.3) — nunca duplicado.
            motivo = MOTIVO_NAO_PROJETADO.ATAQUE_DE_HOJE
        elif mes is None:
            motivo = MOTIVO_NAO_PROJETADO.JANELA_NAO_SEI
        elif trava_deficit_estrutural:
            motivo = MOTIVO_NAO_PROJETADO.TRAVA_DEFICIT_ESTRUTURAL
        else:
            # Fora da trava, VALOR_DESTINADO = valor líquido do item (RF-74).
            aportes.append(AporteProjetado(ITEM_ID=recurso.ITEM_ID, mes=mes, VALOR_DESTINADO=valor))
            continue
        nao_projetados.append(ItemNaoProjetado(ITEM_ID=recurso.ITEM_ID, motivo=motivo))
    return tuple(aportes), tuple(nao_projetados)


def aportes_por_mes(aportes: tuple[AporteProjetado, ...]) -> Mapping[Meses, Dinheiro]:
    """RF-70/RF-75 — a ÚNICA soma: por mês, para `simular_cenario`. A
    rastreabilidade por item fica nos `AporteProjetado` do snapshot."""
    por_mes: dict[Meses, Dinheiro] = {}
    with localcontext(CONTEXTO_MOTOR):
        for aporte in aportes:
            por_mes[aporte.mes] = por_mes.get(aporte.mes, dinheiro(0)) + aporte.VALOR_DESTINADO
    return MappingProxyType(por_mes)
