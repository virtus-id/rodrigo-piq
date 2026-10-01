"""`RegistroHomologacao` — os cinco itens de `DE-08` (`RF-96`, `RF-97`,
`app-aluno` T-268; em produção desde `T-304`).

Só leitura do `SnapshotOrdem` gravado: nada é calculado de novo pelo motor,
nenhum parâmetro nem literal numérico preenche item ausente. Cada item traz
o valor e os campos de origem, ou `"não disponível"` com o motivo (decisão
do produto `R9-6`, 2026-09-30). Nasceu como helper de teste
(`tests/homologacao/`, que o emite no relatório JUnit); `T-304` o trouxe
para cá para o revisor vê-lo no `GET` da decisão — uma montagem só.

**Exceção declarada a `AC-42`.** `_juros` faz a soma telescópica abaixo —
derivação exata autorizada por `RF-96` — e é a única função de `app/` fora
de `quantizar_exibicao` com aritmética sobre campo do snapshot
(`tests/app_aluno/estatica/test_sem_aritmetica_sobre_snapshot.py`). O valor
vai só ao revisor, nunca ao aluno.

Correspondência (tabela de `R9.9` do plano, fechada pelo `R9-6`):

| Item | Origem |
| --- | --- |
| Ordem final de ataque | `ORDEM_QUITACAO[*].DIVIDA_ID` |
| Mês de quitação | `report.plano.meses_de_quitacao` (`quitacoes` × `estado_final.mes`) |
| Valor mensal destinado | `diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA` |
| Custo total de juros | `CUSTO_FUTURO_TOTAL − Σ SALDO_DEVEDOR_ATUAL + Σ saldos finais` (abaixo) |
| Uso da reserva | não disponível (abaixo) |

**Juros — derivação exata.** O ciclo mensal (`M-02`/`M-03`) faz, por dívida
e por mês, `saldo_pos_juros = abertura + juros` e `desembolso = saldo_pos_
juros − saldo_final_do_mes`. Somando todos os meses, a soma telescópica dá
`Σ juros = DESEMBOLSO_ACUMULADO − Σ saldos iniciais + Σ saldos finais`, e
`CUSTO_FUTURO_TOTAL` É o `DESEMBOLSO_ACUMULADO` final (`simular_cenario`). Os
saldos iniciais são os `SALDO_DEVEDOR_ATUAL` de `estado_inputs` (as mesmas
dívidas que o motor simula). Não disponível quando o cenário recomendado não
existe, estourou o horizonte (juros só até o corte) ou alguma dívida tem saldo
desconhecido (fica fora do cronograma).

**Uso da reserva — não disponível.** O quanto da reserva o plano usa é
`RESERVA_RECOMENDADA` (§13.4), que o snapshot não grava: entra somada a outros
quatro componentes em `ATAQUE_IMEDIATO_RECOMENDADO`, e o cronograma não
consome reserva (§13.6). `RESERVA_MOBILIZAVEL` é o limite aceito pelo aluno,
não o uso — nunca registrado como o item (o revisor o vê em `estado_inputs`).

REGRAS: `RF-96`, `RF-97`, `DE-08`
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from app.revisao.comprovacao import PendenciaHomologacao
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO
from report.plano import formatar_dinheiro_br, meses_de_quitacao

NAO_DISPONIVEL: Final[str] = "não disponível"


@dataclass(frozen=True, slots=True)
class ItemHomologacao:
    """Valor e campos de origem — ou `NAO_DISPONIVEL` com o motivo."""

    valor: object
    origem: tuple[str, ...]
    motivo: str | None = None

    @property
    def disponivel(self) -> bool:
        return self.valor != NAO_DISPONIVEL


@dataclass(frozen=True, slots=True)
class RegistroHomologacao:
    ordem_final_de_ataque: ItemHomologacao
    mes_de_quitacao_por_divida: ItemHomologacao
    valor_mensal_destinado: ItemHomologacao
    custo_total_de_juros: ItemHomologacao
    uso_da_reserva: ItemHomologacao
    homologavel: bool
    pendencias: tuple[PendenciaHomologacao, ...]


def _nao_disponivel(motivo: str) -> ItemHomologacao:
    return ItemHomologacao(valor=NAO_DISPONIVEL, origem=(), motivo=motivo)


def registrar_homologacao(
    snapshot: SnapshotOrdem, pendencias: tuple[PendenciaHomologacao, ...]
) -> RegistroHomologacao:
    """`RF-96`/`RF-97` — os cinco itens lidos de `snapshot`; `homologavel`
    é `False` com qualquer pendência de `pendencias_de_homologacao`."""
    origem_cenario = f"cenarios[{snapshot.METODO_RECOMENDADO_PIQ.value}]"
    quitacoes = meses_de_quitacao(snapshot)

    if quitacoes is None:
        meses: ItemHomologacao = _nao_disponivel("sem cenário do método recomendado")
        juros = _nao_disponivel("sem cenário do método recomendado")
    else:
        meses = ItemHomologacao(
            valor=quitacoes,
            origem=(f"{origem_cenario}.meses[*].quitacoes", "meses[*].estado_final.mes"),
        )
        juros = _juros(snapshot, origem_cenario)

    diagnostico = snapshot.diagnostico
    return RegistroHomologacao(
        ordem_final_de_ataque=ItemHomologacao(
            valor=tuple(p.DIVIDA_ID for p in snapshot.ORDEM_QUITACAO),
            origem=("ORDEM_QUITACAO[*].DIVIDA_ID",),
        ),
        mes_de_quitacao_por_divida=meses,
        valor_mensal_destinado=ItemHomologacao(
            valor=diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
            origem=("diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA",),
        ),
        custo_total_de_juros=juros,
        uso_da_reserva=_nao_disponivel("RESERVA_RECOMENDADA não gravada (R9-6)"),
        homologavel=not pendencias,
        pendencias=pendencias,
    )


def _juros(snapshot: SnapshotOrdem, origem_cenario: str) -> ItemHomologacao:
    cenario = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]
    if cenario.ESTOUROU_HORIZONTE:
        return _nao_disponivel("estourou o horizonte (EC-13)")
    saldos = [d.SALDO_DEVEDOR_ATUAL for d in snapshot.estado_inputs.dividas]
    iniciais = [saldo for saldo in saldos if saldo is not DESCONHECIDO]
    if len(iniciais) != len(saldos):
        # A dívida sem saldo fica fora do cronograma: somar só as outras
        # daria o juro de um plano parcial, não o do caso.
        return _nao_disponivel("SALDO_DEVEDOR_ATUAL desconhecido")
    finais = cenario.meses[-1].estado_final.saldos.values() if cenario.meses else ()
    return ItemHomologacao(
        valor=cenario.CUSTO_FUTURO_TOTAL - sum(iniciais) + sum(finais),
        origem=(
            f"{origem_cenario}.CUSTO_FUTURO_TOTAL",
            "estado_inputs.dividas[*].SALDO_DEVEDOR_ATUAL",
            f"{origem_cenario}.meses[-1].estado_final.saldos",
        ),
    )


def serializar_registro(registro: RegistroHomologacao) -> dict[str, Any]:
    """`T-304` — os cinco itens para a tela do revisor; dinheiro formatado
    (`G-01`), o resto como veio. As pendências já vão nomeadas ao lado, em
    `pendencias_homologacao` — aqui só `homologavel`."""

    def valor(bruto: object) -> object:
        if isinstance(bruto, Decimal):
            return formatar_dinheiro_br(bruto)
        return list(bruto) if isinstance(bruto, tuple) else bruto

    return {
        "homologavel": registro.homologavel,
        "itens": {
            nome: {
                "valor": valor(item.valor),
                "origem": list(item.origem),
                "motivo": item.motivo,
            }
            for nome, item in (
                ("ordem_final_de_ataque", registro.ordem_final_de_ataque),
                ("mes_de_quitacao_por_divida", registro.mes_de_quitacao_por_divida),
                ("valor_mensal_destinado", registro.valor_mensal_destinado),
                ("custo_total_de_juros", registro.custo_total_de_juros),
                ("uso_da_reserva", registro.uso_da_reserva),
            )
        },
    }
