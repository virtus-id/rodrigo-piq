"""Valor relevante para quitação — RF-06 · §11.2 · AC-20, AC-21 · EC-14.

Fórmula normativa (§11.2 da spec do slug):

```
SE VALOR_QUITACAO_HOJE = CONFIRMADO
E  STATUS_VALIDADE_PROPOSTA = VIGENTE:
       VALOR_RELEVANTE_PARA_QUITACAO = VALOR_QUITACAO_HOJE
SENAO:
       VALOR_RELEVANTE_PARA_QUITACAO = SALDO_DEVEDOR_ATUAL
```

**Ponte entre a redação normativa e o esquema de dados fixado em T-08.** A
fórmula fala em "`VALOR_QUITACAO_HOJE = CONFIRMADO`", mas `engine/estado.py`
(T-08) não modela um estado "CONFIRMADO" para o valor em si — modela duas
variáveis separadas: `QUITACAO_CONSULTADA: SimNaoTalvez` (a consulta foi
feita?) e `VALOR_QUITACAO_HOJE: DinheiroTalvez` (o valor, que pode ser
`DESCONHECIDO`). "`VALOR_QUITACAO_HOJE = CONFIRMADO`" é aplicado ao esquema
existente como a conjunção `QUITACAO_CONSULTADA == SIM E VALOR_QUITACAO_HOJE
conhecido (nao DESCONHECIDO)` — isto NAO é uma decisao metodologica nova (a
trava da secao 6 do sdd.config.md proibe inventar regra); e a aplicacao
literal da regra ja fechada ao tipo de dado que T-08 fixou: um valor so pode
estar "confirmado" se (a) foi de fato consultado e (b) o resultado da
consulta e um numero, nao uma ausencia.

**Tabela de situações (§11.2)** — todas cobertas por
`compor_VALOR_RELEVANTE_PARA_QUITACAO`:

| Situação | Comportamento |
| --- | --- |
| Proposta expirada | Fallback para `SALDO_DEVEDOR_ATUAL` |
| Quitação nunca consultada | Fallback para `SALDO_DEVEDOR_ATUAL` |
| Validade desconhecida | Não trata como vigente; fallback para saldo; |
|                        | sinaliza `PRIORIDADE_INFORMACAO` se relevante |
| Saldo também desconhecido | `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` |

**Estrutura de retorno — `ResultadoValorRelevante`.** O critério de aceite
"validade desconhecida com diferença materialmente relevante gera
`PRIORIDADE_INFORMACAO`" (EC-14) exige que a função comunique mais do que o
valor: precisa sinalizar que um item de prioridade de informação foi gerado.
A modelagem completa de `PRIORIDADE_INFORMACAO` (fila, agregação por
dívida/plano, exibição) é do motor inteiro e provavelmente serve outras
tarefas (T-29 em diante, gates). Aqui modela-se só o suficiente para este
critério: um booleano `gerou_PRIORIDADE_INFORMACAO` e o `motivo` textual
correspondente — auditável, reaproveitável por quem for montar a fila
completa depois, sem comprometer-se com essa modelagem agora.

**"Diferença materialmente relevante" — decisão de critério.** Nenhum dos 38
`P_*` ativos (`parameters/parametros-1.0.1.json`) nomeia um limiar de
materialidade entre `VALOR_QUITACAO_HOJE` e `SALDO_DEVEDOR_ATUAL`; os
candidatos mais próximos (`P_DIFERENCA_ECONOMICA_MATERIAL`,
`P_DIFERENCA_CUSTO_EQUIVALENTE`, `P_DIFERENCA_TAXAS_RELEVANTE`) são
parâmetros normativamente amarrados a outras regras (RF-19/RF-20, taxa de
troca) — reaproveitá-los aqui seria inventar um uso que a canônica não
escreveu, o que a §6 do sdd.config.md proíbe. Em vez de inventar uma
constante numérica de threshold não documentada, o critério adotado é o mais
simples que satisfaz o texto normativo sem extrapolá-lo: os dois valores são
conhecidos e diferentes (`!=`). Refinar isso para um threshold percentual ou
absoluto é trabalho de tarefa futura, se e quando a canônica nomear o
parâmetro correspondente — não é decisão deste módulo.

REGRAS: RF-06, AC-20, AC-21, EC-14, §11.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from engine.estado import Divida
from engine.tipos import DESCONHECIDO, STATUS_VALIDADE_PROPOSTA, DinheiroTalvez, SimNaoTalvez

REGRAS: Final[tuple[str, ...]] = ("RF-06", "AC-20", "AC-21", "EC-14", "§11.2")


@dataclass(frozen=True, slots=True)
class ResultadoValorRelevante:
    """Saída de `compor_VALOR_RELEVANTE_PARA_QUITACAO` — §11.2, EC-14.

    `gerou_PRIORIDADE_INFORMACAO` sinaliza o caso EC-14: validade
    desconhecida com diferença materialmente relevante entre
    `VALOR_QUITACAO_HOJE` e `SALDO_DEVEDOR_ATUAL`. `motivo` é texto
    auditável, reaproveitável por quem for montar a fila completa de
    `PRIORIDADE_INFORMACAO` (fora do escopo desta tarefa).
    """

    VALOR_RELEVANTE_PARA_QUITACAO: DinheiroTalvez
    gerou_PRIORIDADE_INFORMACAO: bool
    motivo: str | None  # None quando gerou_PRIORIDADE_INFORMACAO é False


def _diferenca_materialmente_relevante(
    valor_quitacao_hoje: DinheiroTalvez, saldo_devedor_atual: DinheiroTalvez
) -> bool:
    """Critério simples e documentado (ver docstring do módulo): os dois
    valores são conhecidos e diferentes. Nenhum threshold arbitrário."""
    if valor_quitacao_hoje is DESCONHECIDO or saldo_devedor_atual is DESCONHECIDO:
        return False
    return valor_quitacao_hoje != saldo_devedor_atual


def compor_VALOR_RELEVANTE_PARA_QUITACAO(divida: Divida) -> ResultadoValorRelevante:
    """§11.2 · RF-06 · AC-20 · AC-21 · EC-14.

    "`VALOR_QUITACAO_HOJE = CONFIRMADO`" (redação da fórmula) é aplicado ao
    esquema de `Divida` (T-08) como `QUITACAO_CONSULTADA == SIM E
    VALOR_QUITACAO_HOJE != DESCONHECIDO` — ver docstring do módulo.
    """
    valor_confirmado = (
        divida.QUITACAO_CONSULTADA == SimNaoTalvez.SIM
        and divida.VALOR_QUITACAO_HOJE is not DESCONHECIDO
    )
    vigente = divida.STATUS_VALIDADE_PROPOSTA == STATUS_VALIDADE_PROPOSTA.VIGENTE

    if valor_confirmado and vigente:
        # AC-20 negativo: caminho normal, quitação vigente e confirmada.
        return ResultadoValorRelevante(
            VALOR_RELEVANTE_PARA_QUITACAO=divida.VALOR_QUITACAO_HOJE,
            gerou_PRIORIDADE_INFORMACAO=False,
            motivo=None,
        )

    # SENÃO: fallback para SALDO_DEVEDOR_ATUAL — cobre proposta expirada,
    # quitação nunca consultada e validade desconhecida (AC-20, EC-14).
    saldo = divida.SALDO_DEVEDOR_ATUAL

    gerou_prioridade = False
    motivo: str | None = None
    if (
        divida.STATUS_VALIDADE_PROPOSTA == STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA
        and _diferenca_materialmente_relevante(divida.VALOR_QUITACAO_HOJE, saldo)
    ):
        # EC-14: validade desconhecida com diferença que pode alterar
        # materialmente a decisão ⇒ sinaliza PRIORIDADE_INFORMACAO.
        gerou_prioridade = True
        motivo = (
            f"{divida.DIVIDA_ID}: STATUS_VALIDADE_PROPOSTA = VALIDADE_DESCONHECIDA "
            f"com VALOR_QUITACAO_HOJE ({divida.VALOR_QUITACAO_HOJE}) divergente de "
            f"SALDO_DEVEDOR_ATUAL ({saldo}) — confirmar validade da proposta pode "
            "mudar a decisão (EC-14)."
        )

    if saldo is DESCONHECIDO:
        # AC-21: sem quitação vigente e saldo também desconhecido ⇒
        # DESCONHECIDO. Nunca uma estimativa (RF-16).
        return ResultadoValorRelevante(
            VALOR_RELEVANTE_PARA_QUITACAO=DESCONHECIDO,
            gerou_PRIORIDADE_INFORMACAO=gerou_prioridade,
            motivo=motivo,
        )

    return ResultadoValorRelevante(
        VALOR_RELEVANTE_PARA_QUITACAO=saldo,
        gerou_PRIORIDADE_INFORMACAO=gerou_prioridade,
        motivo=motivo,
    )
