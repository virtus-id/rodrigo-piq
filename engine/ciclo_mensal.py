"""Ciclo mensal canônico — RF-01, RF-02, RF-04 · M-01..M-12 · AC-13, AC-15,
AC-32 · EC-02, EC-13, EC-18.

Fonte normativa dos doze passos (`specs/piq-app-spec.md`, tabela "Devolutiva
final §9", linhas 303-314 — citada por `specs/motor-calculo.spec.md` RF-01
como `M-01`..`M-12` · §2):

```
M-01  Abrir o mês com os saldos e a capacidade disponíveis no início do período.
M-02  Aplicar juros, encargos e evolução contratual conforme o modelo de cada dívida.
M-03  Aplicar os pagamentos mensais normais de todas as dívidas, limitados ao saldo.
M-04  Aplicar o ataque adicional à DIVIDA_ALVO_ATUAL.
M-05  Se a dívida-alvo não for quitada: manter o mesmo alvo para o mês seguinte,
      salvo EVENTO_RECALCULO externo.
M-06  Se for quitada: confirmar a quitação, atualizar o estado e calcular
      RESIDUO_ATAQUE_M.
M-07  Havendo RESIDUO_ATAQUE_M > 0: recalcular a ordem das dívidas restantes,
      selecionar o novo alvo e aplicar o resíduo ainda no mês m.
M-08  Repetir o passo 7 enquanto houver resíduo e houver dívida elegível.
M-09  Encerrar o mês.
M-10  Consolidar o VALOR_FLUXO_LIBERADO das dívidas quitadas no período.
M-11  Incorporar o fluxo liberado à capacidade a partir de m+1.
M-12  Reavaliar a ordem para o próximo período somente se houve quitação no
      período ou EVENTO_RECALCULO externo material. Na ausência de ambos,
      preservar a DIVIDA_ALVO_ATUAL.
```

**Escopo (`T-42` + `T-43` + `T-44` + `T-45` + `T-46`).** `executar_mes`
implementa `M-01` a `M-09`, mais a consolidação de `M-10` (o embutir do
fluxo liberado em *m+1*, `M-11`, é de quem orquestra vários meses — ver
abaixo): `T-42` cobriu `M-01`..`M-06`; `T-43` estendeu com o laço de
cascata do resíduo (`M-07`/`M-08`, `A-01`..`A-03`, `O-03`) — ver "Laço de
cascata do resíduo" abaixo; `T-44` fecha o destino do resíduo que sobra ao
fim do laço (`A-04`, `EC-01`) — ver "Resíduo sem destino —
`ATAQUE_NAO_UTILIZADO`" abaixo; `T-45` fecha `VALOR_FLUXO_LIBERADO` (`RF-04`,
`F-01`..`F-03`, §11.7) — ver "Fluxo liberado — `VALOR_FLUXO_LIBERADO`"
abaixo. `T-46` (`simular_cenario`, ao final deste módulo) orquestra vários
meses: repete `executar_mes` até quitar tudo ou estourar
`P_HORIZONTE_MAXIMO_SIMULACAO` (`M-12`, `AC-13` completo entre chamadas, e
`M-11` — incorpora o `VALOR_FLUXO_LIBERADO` devolvido por este mês à
`CAPACIDADE_ATAQUE_M` do mês seguinte) — ver "Encadeamento de vários meses
— `simular_cenario`" ao final deste módulo.

**Fluxo liberado — `VALOR_FLUXO_LIBERADO` (`RF-04`, `F-01`..`F-03`, §11.7,
`T-45`).** Toda dívida quitada dentro do mês — o alvo original (M-04) ou
qualquer uma quitada dentro da cascata de resíduo (M-07/M-08) — libera o
`PAGAMENTO_MENSAL_EFETIVO` que de fato saía do orçamento por ela, nunca a
parcela contratual (`F-01`, `AC-32`, `EC-18`: efetivo 0 libera 0, mesmo com
contratual > 0). `DESCONHECIDO` não soma (RF-16: nunca estimar um valor
ausente). A soma de todas as liberações do mês é `VALOR_FLUXO_LIBERADO` de
`ResultadoMes` — apenas DEVOLVIDO por esta função, nunca somado a
`CAPACIDADE_ATAQUE_M` nem a `ataque_total` dentro do próprio mês (`F-02`:
"entra em *m+1*"; `F-03`: nenhum valor conta ao mesmo tempo como pagamento
normal de *m* e como capacidade adicional de *m*, `AC-15`). Incorporar esse
valor à capacidade do mês seguinte é responsabilidade de quem encadeia
`executar_mes` entre meses (`simular_cenario`, `T-46`) — este módulo não tem
acesso ao mês seguinte para fazê-lo, nem deveria: caso contrário haveria
liberação retroativa ou dupla contagem dentro do mesmo `executar_mes`.

**Resíduo sem destino — `ATAQUE_NAO_UTILIZADO` (`A-04`, `EC-01`, `T-44`).**
Quando o laço de cascata do resíduo (`T-43`) para porque não há mais dívida
elegível — ou quando não há alvo algum para atacar no mês (sem dívidas, sem
seleção no bootstrap, ou alvo herdado já quitado) — a capacidade de ataque
que não coube em nenhuma dívida vira `ATAQUE_NAO_UTILIZADO` do mês. Este
valor NUNCA desaparece da simulação (TRAVA, `piq-app-spec.md` linha 117): é
mantido como caixa do usuário e acumulado em
`EstadoSimulacao.ATAQUE_NAO_UTILIZADO_ACUMULADO`, campo que atravessa os
meses (soma exata, sem arredondamento intermediário — `G-01`). Ao final do
mês, a invariante de conservação `ataque_efetivamente_aplicado +
ATAQUE_NAO_UTILIZADO == CAPACIDADE_ATAQUE_M` é verificada e levanta
`ErroInvariante` (ruidosamente, nunca um `assert` mudo) se a conta não
fechar — nenhum caminho deste módulo pode descartar resíduo em silêncio.

**Laço de cascata do resíduo — `M-07`/`M-08`, `A-01`..`A-03`, `O-03`
(`T-43`).** Quitado o alvo com `RESIDUO_ATAQUE_M > 0` (`M-06`, `A-01`):
1. Reranqueia ENTRE as dívidas ainda não quitadas (excluindo a recém-quitada)
   — `sel(estado, residuo_corrente)`, delta = resíduo restante, NUNCA a
   capacidade cheia do mês (`A-03`, `AC-14`). Esta chamada é registrada em
   `reranqueamentos` — a chamada de bootstrap do início do mês (ver
   "`SelecionarAlvo` — quando é chamada" abaixo) não conta, já é `T-42`.
2. Aplica o resíduo à dívida selecionada, registrando o evento em
   `aplicacoes_residuo` (`A-02`).
3. Se essa aplicação também quitar a nova alvo, sobra um resíduo NOVO: o
   laço volta ao passo 1 com o resíduo remanescente — cada quitação em
   cascata produz uma nova rodada (novo reranqueamento + nova aplicação).
4. O laço para quando o resíduo se esgota (aplicado integralmente, sem
   sobra) OU quando não há mais dívida elegível — nesse segundo caso
   (`EC-01`), o resíduo remanescente vira `ATAQUE_NAO_UTILIZADO` do mês
   logo após o laço (`A-04`, `T-44` — ver "Resíduo sem destino" acima), sem
   travar nem gerar erro.

`DELTA_TESTE_AVALANCHE_RESIDUO = MIN(RESIDUO_ATAQUE_M,
VALOR_RELEVANTE_PARA_QUITACAO)` (§11.1 "Exceção intramês"): este módulo só
garante que o delta passado a `sel()` seja o resíduo restante bruto — o
`MIN` contra `VALOR_RELEVANTE_PARA_QUITACAO` de CADA candidata é
responsabilidade INTERNA de quem implementa `SelecionarAlvo` de verdade
(`T-49`+), porque esse valor varia por dívida e não é conhecido por
`executar_mes`.

**M-02, interpretação adotada.** A "Estrutura mínima" do orquestrador desta
tarefa não separa M-02 como bloco próprio, mas a fonte canônica primária o
lista explicitamente como o segundo dos doze passos, antes dos pagamentos
normais. Seguido aqui como passo distinto e obrigatório, na mesma mecânica já
usada por `engine/trajetoria.py::_simular_trajetoria_isolada_sem_cache`
(`saldo *= (1 + TAXA_EFETIVA_MENSAL_NORMALIZADA)` antes de abater qualquer
pagamento) — reaproveita a leitura já validada daquele módulo em vez de
inventar uma segunda fórmula de evolução de saldo. Dívida com taxa
`DESCONHECIDO` não evolui por juro (RF-16: não estimar) — permanece com o
saldo do mês anterior até que o dado exista; o bloqueio por dado ausente é
tratado pelos gates (Gate 1, `engine/gates.py`, já aplicado antes de a
dívida chegar a `elegiveis`), não por este módulo.

**Parâmetro adicional a `executar_mes` — extensão documentada do contrato do
plano.** O plano (`§4`) desenha `executar_mes(e: EstadoSimulacao, sel:
SelecionarAlvo, p: Parametros) -> ResultadoMes`. `EstadoSimulacao.saldos` é
só `Mapping[str, Dinheiro]` — não carrega taxa, pagamento mensal efetivo nem
os demais campos de `Divida` que M-02/M-03 precisam para TODAS as dívidas
elegíveis (não só a alvo, que `sel` devolve). Não há como `executar_mes`
aplicar M-02/M-03 ao inventário inteiro sem acesso a esses dados. Resolvido
adicionando `dividas: Mapping[str, Divida]` como parâmetro explícito — o
inventário completo (ou já filtrado para as elegíveis, decisão do chamador),
indexado por `DIVIDA_ID`. É extensão mínima e necessária, não mudança de
comportamento: mantém o restante da assinatura do plano intacta e documenta
a lacuna em vez de silenciá-la.

**`SelecionarAlvo` — quando é chamada.** O plano define `SelecionarAlvo =
Callable[[EstadoSimulacao, Dinheiro], Divida | None]` como o único ponto de
variação entre os três métodos. `sel` é chamada:

1. No bootstrap — `e.DIVIDA_ALVO_ATUAL is None` (primeira execução do
   ciclo, nenhum alvo herdado do mês anterior). Delta = `CAPACIDADE_ATAQUE_M`
   cheia (`T-42`).
2. Uma vez por rodada do laço de cascata do resíduo (`T-43`, ver acima),
   sempre que o alvo (original ou de uma rodada anterior da cascata) é
   quitado e ainda resta `RESIDUO_ATAQUE_M > 0` — delta = resíduo restante
   (`A-03`, `AC-14`), nunca a capacidade cheia. Cada uma dessas chamadas
   gera um `Reranqueamento` em `ResultadoMes.reranqueamentos` (`R-03`).

Em qualquer outro caso — alvo já definido e não quitado neste mês, ou
resíduo esgotado, ou nenhuma dívida elegível remanescente — `sel` NÃO é
chamada: `DIVIDA_ALVO_ATUAL` é preservado tal como veio (`M-05`), sem
reranqueamento por mera passagem de mês (`R-02`, `AC-13`).

REGRAS: RF-01, RF-02, RF-03, RF-04, M-01, M-02, M-03, M-04, M-05, M-06,
M-07, M-08, M-10, M-11, M-12, A-01, A-02, A-03, A-04, F-01, F-02, F-03,
O-03, R-02, R-03, AC-13, AC-14, AC-15, AC-32, EC-01, EC-02, EC-13, EC-18
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import localcontext
from typing import Final

from engine.diagnostico import Diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.parametros import Parametros
from engine.precisao import CONTEXTO_MOTOR, dinheiro
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO, METODO, Dinheiro, Meses

REGRAS: Final[tuple[str, ...]] = (
    "RF-01",
    "RF-02",
    "RF-03",
    "RF-04",
    "M-01",
    "M-02",
    "M-03",
    "M-04",
    "M-05",
    "M-06",
    "M-07",
    "M-08",
    "M-10",
    "M-11",
    "M-12",
    "A-01",
    "A-02",
    "A-03",
    "A-04",
    "F-01",
    "F-02",
    "F-03",
    "O-03",
    "R-02",
    "R-03",
    "AC-13",
    "AC-14",
    "AC-15",
    "AC-32",
    "EC-01",
    "EC-02",
    "EC-13",
    "EC-18",
)


class ErroInvariante(Exception):
    """Levantado quando uma invariante de conservação do ciclo mensal não
    fecha — `A-04`/`T-44`: ataque aplicado + `ATAQUE_NAO_UTILIZADO` DEVE ser
    exatamente igual à capacidade de ataque disponível no mês, sempre.

    Mesmo padrão de `engine/parametros.py::ErroParametros`: não há caminho de
    recuperação silenciosa — a TRAVA de `piq-app-spec.md` (linha 117) proíbe
    que qualquer valor disponível ao usuário desapareça da simulação por
    convenção de cálculo, então uma divergência aqui é bug do motor, não
    situação de negócio a tolerar.
    """


@dataclass(frozen=True, slots=True)
class EstadoSimulacao:
    """§4 do plano técnico — estado imutável de uma simulação mês a mês.

    Cada passo do ciclo devolve uma NOVA instância — nunca muta uma
    existente (`frozen=True`), condição de `RF-10`/`V-01` estendida ao
    estado intramês e de determinismo (NFR).
    """

    mes: Meses
    saldos: Mapping[str, Dinheiro]
    quitadas: frozenset[str]
    DIVIDA_ALVO_ATUAL: str | None
    CAPACIDADE_ATAQUE_M: Dinheiro
    ATAQUE_NAO_UTILIZADO_ACUMULADO: Dinheiro  # A-04/EC-01 — acumulação: T-44
    DESEMBOLSO_ACUMULADO: Dinheiro


@dataclass(frozen=True, slots=True)
class AplicacaoResiduo:
    """A-02 — um item da cascata auditável de aplicação de resíduo.

    Uma instância por rodada do laço de cascata (`T-43`, "Laço de cascata
    do resíduo" na docstring do módulo): `DIVIDA_ID` é quem recebeu o
    resíduo naquela rodada, `valor_aplicado` é `MIN(resíduo restante, saldo
    da dívida)` e `ordem_aplicacao` é a posição da rodada dentro da cascata
    do mês (`1`, `2`, `3`, ...), na ordem em que ocorreram.
    """

    DIVIDA_ID: str
    valor_aplicado: Dinheiro
    ordem_aplicacao: int


@dataclass(frozen=True, slots=True)
class Reranqueamento:
    """R-03 — um evento de reranqueamento intramês, para auditoria.

    Uma instância por chamada a `sel()` ocorrida DENTRO do laço de cascata
    do resíduo (`T-43`) — nunca a chamada de bootstrap do início do mês
    (`e.DIVIDA_ALVO_ATUAL is None`, tratada por `T-42` e não contada aqui).
    `motivo` é sempre `"RESIDUO_ATAQUE_M"` nesta tarefa — o único gatilho de
    reranqueamento intramês que `executar_mes` implementa (`O-03`).
    """

    mes: Meses
    motivo: str
    novo_alvo: str | None


@dataclass(frozen=True, slots=True)
class ResultadoMes:
    """§4 do plano técnico — saída de `executar_mes`."""

    estado_final: EstadoSimulacao
    quitacoes: tuple[str, ...]
    RESIDUO_ATAQUE_M: Dinheiro  # A-01 — valor calculado em M-06, antes da cascata
    aplicacoes_residuo: tuple[AplicacaoResiduo, ...]  # A-02 — uma por rodada da cascata (T-43)
    ATAQUE_NAO_UTILIZADO: Dinheiro  # A-04/EC-01 — resíduo sem destino ao fim da cascata (T-44)
    VALOR_FLUXO_LIBERADO: Dinheiro  # F-01/F-02 · §11.7 — devolvido, não incorporado neste mês
    reranqueamentos: tuple[Reranqueamento, ...]  # R-03 — um por rodada da cascata (T-43)


type SelecionarAlvo = Callable[[EstadoSimulacao, Dinheiro], Divida | None]
# ÚNICO ponto de variação entre Avalanche, Bola de Neve e Híbrido (§1, §4 do
# plano). Nenhuma ramificação por METODO existe dentro deste módulo.


def _saldo_apos_juros(saldo: Dinheiro, divida: Divida) -> Dinheiro:
    """M-02: aplica juros, encargos e evolução contratual sobre o saldo de
    ABERTURA do mês (§9 da canônica). Taxa desconhecida ⇒ saldo não evolui
    (RF-16: nunca estimar uma taxa ausente) — a dívida fica bloqueada pelo
    Gate 1 antes de chegar a este ciclo, então este caminho é defensivo.
    """
    taxa = divida.TAXA_EFETIVA_MENSAL_NORMALIZADA
    if taxa is DESCONHECIDO:
        return saldo
    with localcontext(CONTEXTO_MOTOR):
        return saldo * (dinheiro(1) + taxa)


def _pagamento_normal_efetivo(saldo_apos_juros: Dinheiro, divida: Divida) -> Dinheiro:
    """M-03: pagamento mensal normal de UMA dívida, limitado ao saldo (§9 da
    canônica — "limitados ao saldo"). `PAGAMENTO_MENSAL_EFETIVO`
    `DESCONHECIDO` não paga nada (RF-16); dívida nesse estado é bloqueada
    pelo Gate 1 antes de chegar aqui.
    """
    pagamento = divida.PAGAMENTO_MENSAL_EFETIVO
    if pagamento is DESCONHECIDO:
        return dinheiro(0)
    with localcontext(CONTEXTO_MOTOR):
        pagamento_efetivo = min(pagamento, saldo_apos_juros)
        if pagamento_efetivo < dinheiro(0):
            return dinheiro(0)
        return pagamento_efetivo


def executar_mes(
    e: EstadoSimulacao,
    dividas: Mapping[str, Divida],
    sel: SelecionarAlvo,
    p: Parametros,  # noqa: ARG001 — parte do contrato do plano; sem uso nesta tarefa
) -> ResultadoMes:
    """`M-01` a `M-08`, nesta ordem, sem pular etapa — `RF-01`, `RF-03` —
    mais a consolidação de `M-10` (`VALOR_FLUXO_LIBERADO`, `RF-04`).

    `M-05`: sem quitação do alvo, `DIVIDA_ALVO_ATUAL` é devolvido idêntico
    ao recebido — nenhum reranqueamento por mera passagem de mês (`R-02`,
    `AC-13`). `M-06`: dívida que se encerra apenas com o pagamento normal —
    sem precisar do ataque — também conta como quitação (`EC-02`). `M-07`/
    `M-08`: quitado o alvo com resíduo, cascateia o resíduo entre as
    dívidas ainda elegíveis, reranqueando antes de cada aplicação (`O-03`,
    ver "Laço de cascata do resíduo" na docstring do módulo). `M-10`: toda
    quitação do mês (alvo original ou cascata) consolida o
    `PAGAMENTO_MENSAL_EFETIVO` que ela liberava em `VALOR_FLUXO_LIBERADO`
    — apenas devolvido em `ResultadoMes`, nunca somado à capacidade deste
    mesmo mês (`F-02`/`F-03`, ver "Fluxo liberado" na docstring do módulo).
    """
    # M-01: abertura do mês — ponto de partida explícito, saldos e
    # capacidade herdados de `e` tal como recebidos. Nenhuma mutação aqui;
    # os passos seguintes constroem os saldos pós-M-02/M-03/M-04 a partir
    # deste snapshot de abertura.
    saldos_abertura = dict(e.saldos)
    mes_atual = e.mes + 1

    # M-02: juros, encargos e evolução contratual — aplicados a toda dívida
    # ainda não quitada, alvo ou não.
    saldos_pos_juros: dict[str, Dinheiro] = {}
    for divida_id, saldo in saldos_abertura.items():
        if divida_id in e.quitadas:
            saldos_pos_juros[divida_id] = saldo
            continue
        divida = dividas[divida_id]
        saldos_pos_juros[divida_id] = _saldo_apos_juros(saldo, divida)

    # M-03: pagamentos normais de TODA dívida não-alvo e ainda não quitada.
    # Dívida já quitada não recebe pagamento algum (EC-02: uma vez quitada,
    # sai do fluxo de pagamento).
    alvo_id = e.DIVIDA_ALVO_ATUAL
    saldos_pos_normais = dict(saldos_pos_juros)
    for divida_id, saldo in saldos_pos_juros.items():
        if divida_id in e.quitadas or divida_id == alvo_id:
            continue
        divida = dividas[divida_id]
        pagamento = _pagamento_normal_efetivo(saldo, divida)
        with localcontext(CONTEXTO_MOTOR):
            saldos_pos_normais[divida_id] = saldo - pagamento

    # M-04: ataque adicional na DIVIDA_ALVO_ATUAL — pagamento normal + toda
    # a capacidade de ataque do mês. Bootstrap: se ainda não há alvo, `sel`
    # decide agora, antes de aplicar qualquer ataque (§ "SelecionarAlvo —
    # quando é chamada nesta tarefa" na docstring do módulo).
    quitadas_acumuladas = set(e.quitadas)
    saldos_apos_ataque = dict(saldos_pos_normais)
    residuo_ataque = dinheiro(0)

    if alvo_id is None and dividas:
        estado_para_selecao = EstadoSimulacao(
            mes=mes_atual,
            saldos=saldos_pos_normais,
            quitadas=frozenset(quitadas_acumuladas),
            DIVIDA_ALVO_ATUAL=None,
            CAPACIDADE_ATAQUE_M=e.CAPACIDADE_ATAQUE_M,
            ATAQUE_NAO_UTILIZADO_ACUMULADO=e.ATAQUE_NAO_UTILIZADO_ACUMULADO,
            DESEMBOLSO_ACUMULADO=e.DESEMBOLSO_ACUMULADO,
        )
        alvo_selecionado = sel(estado_para_selecao, e.CAPACIDADE_ATAQUE_M)
        alvo_id = alvo_selecionado.DIVIDA_ID if alvo_selecionado is not None else None

    if alvo_id is not None and alvo_id not in quitadas_acumuladas:
        saldo_alvo_pos_juros = saldos_pos_juros[alvo_id]
        divida_alvo = dividas[alvo_id]
        pagamento_normal_alvo = _pagamento_normal_efetivo(saldo_alvo_pos_juros, divida_alvo)
        with localcontext(CONTEXTO_MOTOR):
            ataque_total = pagamento_normal_alvo + e.CAPACIDADE_ATAQUE_M
            aplicado = min(ataque_total, saldo_alvo_pos_juros)
            if aplicado < dinheiro(0):
                aplicado = dinheiro(0)
            saldo_alvo_final = saldo_alvo_pos_juros - aplicado
            if saldo_alvo_final < dinheiro(0):
                saldo_alvo_final = dinheiro(0)
            # A-01: o que sobrou do ataque depois de zerar o saldo do alvo —
            # `aplicado` já é `min(ataque_total, saldo_alvo_pos_juros)`, então
            # qualquer diferença positiva é dinheiro que não coube na dívida
            # (ela quitou com folga). Equivale a "aplicado == saldo restante
            # E ataque_total > saldo restante", mas comparar os totais
            # diretamente evita duplicar a lógica do `min` acima.
            if ataque_total > saldo_alvo_pos_juros:
                residuo_ataque = ataque_total - saldo_alvo_pos_juros
        saldos_apos_ataque[alvo_id] = saldo_alvo_final
    elif alvo_id is None:
        # A-04/EC-01/T-44: nenhum alvo para atacar neste mês (sem dívidas,
        # sem seleção no bootstrap, ou nenhuma candidata elegível) — a
        # capacidade de ataque inteira não coube em lugar nenhum. Tratado
        # como resíduo desde já para não descartar silenciosamente: cai no
        # mesmo destino do resíduo pós-cascata (`ATAQUE_NAO_UTILIZADO`).
        residuo_ataque = e.CAPACIDADE_ATAQUE_M
    # alvo_id is not None and alvo_id in quitadas_acumuladas: alvo herdado já
    # quitado por evento externo antes deste mês — hoje inalcançável pelo
    # próprio invariante do ciclo (dívida quitada nunca permanece
    # DIVIDA_ALVO_ATUAL), mas tratado defensivamente: sem alvo válido, toda
    # a capacidade também não coube em lugar nenhum.
    elif alvo_id in quitadas_acumuladas:
        residuo_ataque = e.CAPACIDADE_ATAQUE_M

    # M-05/M-06: verificação de quitação. Uma dívida está quitada quando seu
    # saldo final do mês é <= 0 — inclui tanto o alvo (M-04) quanto qualquer
    # dívida não-alvo encerrada só com o pagamento normal (EC-02).
    quitacoes_do_mes: list[str] = []
    valor_fluxo_liberado = dinheiro(0)
    for divida_id, saldo in saldos_apos_ataque.items():
        if divida_id in quitadas_acumuladas:
            continue
        if saldo <= dinheiro(0):
            quitacoes_do_mes.append(divida_id)
            quitadas_acumuladas.add(divida_id)
            divida = dividas[divida_id]
            pagamento_efetivo_divida = divida.PAGAMENTO_MENSAL_EFETIVO
            # F-01/AC-32/EC-18: dívida que não estava sendo paga de fato
            # libera zero, nunca a parcela contratual fictícia — consolidado
            # aqui (M-10); incorporação em m+1 (M-11) é responsabilidade de
            # `simular_cenario` (T-46), fora desta função.
            if pagamento_efetivo_divida is not DESCONHECIDO:
                with localcontext(CONTEXTO_MOTOR):
                    valor_fluxo_liberado = valor_fluxo_liberado + pagamento_efetivo_divida

    alvo_quitado = alvo_id is not None and alvo_id in quitacoes_do_mes

    novo_alvo_id = alvo_id
    reranqueamentos_do_mes: list[Reranqueamento] = []
    aplicacoes_residuo_do_mes: list[AplicacaoResiduo] = []
    ordem_aplicacao = 0

    # M-07/M-08 (`T-43`): laço de cascata do resíduo, `A-01`..`A-03`. Cada
    # rodada (a) reranqueia ENTRE as dívidas ainda elegíveis, excluindo a que
    # acabou de quitar — `O-03`: o recálculo ocorre imediatamente após a
    # quitação e ANTES de aplicar o resíduo; (b) aplica o resíduo à nova
    # dívida-alvo selecionada — `A-02`. Se essa aplicação também quitar a
    # nova alvo, sobra um resíduo NOVO e o laço repete — `M-08`: "enquanto
    # houver resíduo e houver dívida elegível". O laço para quando o resíduo
    # se esgota (`residuo_ataque_corrente <= 0`, aplicado integralmente sem
    # sobra) OU quando não há mais candidata elegível — nesse segundo caso, o
    # que sobra em `residuo_ataque_corrente` ao sair do laço vira
    # `ATAQUE_NAO_UTILIZADO` do mês (`A-04`, `EC-01`, `T-44` — ver bloco após
    # o laço).
    #
    # `DELTA_TESTE_AVALANCHE_RESIDUO = MIN(RESIDUO_ATAQUE_M,
    # VALOR_RELEVANTE_PARA_QUITACAO)` (§11.1 "Exceção intramês", `A-03`,
    # `AC-14`): esta função só garante que o delta passado a `sel()` seja o
    # `residuo_ataque_corrente` BRUTO — nunca `CAPACIDADE_ATAQUE_M` (a
    # capacidade cheia do mês). O `MIN` contra `VALOR_RELEVANTE_PARA_QUITACAO`
    # de CADA dívida candidata é responsabilidade INTERNA de quem implementa
    # `SelecionarAlvo` de verdade (a Avalanche real é `T-49`); esse valor
    # varia por dívida e não pode ser resolvido aqui, que não conhece
    # `VALOR_RELEVANTE_PARA_QUITACAO` de ninguém.
    residuo_ataque_corrente = residuo_ataque
    if alvo_quitado:
        # O alvo original já não existe mais (quitado) — `novo_alvo_id` só
        # volta a ter valor se o laço abaixo selecionar e aplicar a uma
        # nova dívida. Sem resíduo algum (`residuo_ataque_corrente == 0`),
        # o laço nem chega a rodar e o alvo permanece `None` (M-06: dívida
        # quitada sai do papel de alvo; resseleção sem resíduo é o mesmo
        # caso — nenhuma capacidade adicional para decidir agora, mas
        # também nenhum alvo válido a preservar).
        novo_alvo_id = None
        while residuo_ataque_corrente > dinheiro(0):
            candidatas = {
                divida_id: divida
                for divida_id, divida in dividas.items()
                if divida_id not in quitadas_acumuladas
            }
            if not candidatas:
                # EC-01/A-04: sem dívida elegível remanescente — para o
                # laço e deixa o resíduo em `residuo_ataque_corrente`, que
                # vira `ATAQUE_NAO_UTILIZADO` logo após o laço (`T-44`).
                # `novo_alvo_id` fica sem alvo.
                novo_alvo_id = None
                break

            estado_para_reranqueamento = EstadoSimulacao(
                mes=mes_atual,
                saldos=saldos_apos_ataque,
                quitadas=frozenset(quitadas_acumuladas),
                DIVIDA_ALVO_ATUAL=None,
                CAPACIDADE_ATAQUE_M=e.CAPACIDADE_ATAQUE_M,
                ATAQUE_NAO_UTILIZADO_ACUMULADO=e.ATAQUE_NAO_UTILIZADO_ACUMULADO,
                DESEMBOLSO_ACUMULADO=e.DESEMBOLSO_ACUMULADO,
            )
            # O-03/R-03(a): reranqueamento COM o resíduo restante como
            # delta — nunca a capacidade cheia (AC-14). Cada chamada aqui
            # É um evento de `reranqueamentos` (a chamada de bootstrap de
            # M-04 não conta — já é T-42).
            novo_alvo = sel(estado_para_reranqueamento, residuo_ataque_corrente)
            reranqueamentos_do_mes.append(
                Reranqueamento(
                    mes=mes_atual,
                    motivo="RESIDUO_ATAQUE_M",
                    novo_alvo=novo_alvo.DIVIDA_ID if novo_alvo is not None else None,
                )
            )

            if novo_alvo is None:
                # `sel` não encontrou candidata apesar de `candidatas` não
                # vazio (ex.: todas bloqueadas por gate) — mesmo tratamento
                # de EC-01/A-04: para o laço, resíduo vira ATAQUE_NAO_UTILIZADO.
                novo_alvo_id = None
                break

            novo_alvo_id = novo_alvo.DIVIDA_ID
            saldo_novo_alvo = saldos_apos_ataque[novo_alvo_id]

            with localcontext(CONTEXTO_MOTOR):
                aplicado = min(residuo_ataque_corrente, saldo_novo_alvo)
                if aplicado < dinheiro(0):
                    aplicado = dinheiro(0)
                saldo_novo_alvo_final = saldo_novo_alvo - aplicado
                if saldo_novo_alvo_final < dinheiro(0):
                    saldo_novo_alvo_final = dinheiro(0)
                residuo_da_rodada = residuo_ataque_corrente - aplicado

            saldos_apos_ataque[novo_alvo_id] = saldo_novo_alvo_final
            ordem_aplicacao += 1
            aplicacoes_residuo_do_mes.append(
                AplicacaoResiduo(
                    DIVIDA_ID=novo_alvo_id,
                    valor_aplicado=aplicado,
                    ordem_aplicacao=ordem_aplicacao,
                )
            )

            if saldo_novo_alvo_final <= dinheiro(0):
                # Nova quitação em cascata — A-02: continua o laço com o
                # resíduo remanescente desta rodada, reranqueando de novo.
                quitacoes_do_mes.append(novo_alvo_id)
                quitadas_acumuladas.add(novo_alvo_id)
                divida_quitada = dividas[novo_alvo_id]
                pagamento_efetivo_divida = divida_quitada.PAGAMENTO_MENSAL_EFETIVO
                if pagamento_efetivo_divida is not DESCONHECIDO:
                    with localcontext(CONTEXTO_MOTOR):
                        valor_fluxo_liberado = valor_fluxo_liberado + pagamento_efetivo_divida
                residuo_ataque_corrente = residuo_da_rodada
                # A dívida recém-quitada não pode permanecer como alvo — o
                # próximo giro do laço reranqueia e decide de novo (ou o
                # laço termina, se não houver mais resíduo/elegível).
                novo_alvo_id = None
                continue

            # Resíduo aplicado sem quitar a nova alvo: cascata termina aqui
            # — o resíduo foi consumido integralmente (`aplicado ==
            # residuo_ataque_corrente`, já que `min` só limitou pelo saldo
            # quando o saldo era menor, e nesse caso teria quitado).
            residuo_ataque_corrente = residuo_da_rodada
            break
    # M-05: sem quitação do alvo, `novo_alvo_id` permanece `alvo_id` — o
    # mesmo valor recebido, sem qualquer chamada a `sel` (AC-13).

    reranqueamentos: tuple[Reranqueamento, ...] = tuple(reranqueamentos_do_mes)

    # A-04/EC-01 (`T-44`): o que sobrou em `residuo_ataque_corrente` ao sair
    # do laço de cascata — por falta de dívida elegível, ou por não haver
    # alvo algum desde M-04 — é o `ATAQUE_NAO_UTILIZADO` do mês. Nenhum
    # caminho descarta esse valor: ele é sempre o que resta da variável do
    # laço, nunca reconstruído por diferença (evita mascarar um bug de
    # conservação atrás de uma subtração que "dá certo por acaso").
    ataque_nao_utilizado = residuo_ataque_corrente

    with localcontext(CONTEXTO_MOTOR):
        ataque_nao_utilizado_acumulado = (
            e.ATAQUE_NAO_UTILIZADO_ACUMULADO + ataque_nao_utilizado
        )

    # Invariante de conservação (TRAVA, `piq-app-spec.md` linha 117): tudo
    # que foi efetivamente aplicado (alvo original + cada rodada da cascata)
    # mais o que sobrou sem destino tem que fechar, exatamente, com a
    # capacidade de ataque disponível no mês — nunca ± tolerância, é
    # subtração exata dentro do próprio mês. `ErroInvariante` ruidoso em vez
    # de assert mudo: um motor que perde ou inventa dinheiro é bug crítico,
    # não algo para logar e seguir.
    with localcontext(CONTEXTO_MOTOR):
        ataque_aplicado = e.CAPACIDADE_ATAQUE_M - residuo_ataque + sum(
            (aplicacao.valor_aplicado for aplicacao in aplicacoes_residuo_do_mes),
            start=dinheiro(0),
        )
        soma_conservacao = ataque_aplicado + ataque_nao_utilizado
    if soma_conservacao != e.CAPACIDADE_ATAQUE_M:
        raise ErroInvariante(
            "conservação do ataque do mês não fechou (A-04/TRAVA): "
            f"aplicado={ataque_aplicado!r} + nao_utilizado={ataque_nao_utilizado!r} "
            f"= {soma_conservacao!r}, esperado CAPACIDADE_ATAQUE_M={e.CAPACIDADE_ATAQUE_M!r} "
            f"(mes={mes_atual})"
        )

    desembolso_do_mes = dinheiro(0)
    with localcontext(CONTEXTO_MOTOR):
        for divida_id in saldos_apos_ataque:
            if divida_id in e.quitadas:
                continue
            anterior = saldos_abertura.get(divida_id, dinheiro(0))
            posterior = saldos_apos_ataque[divida_id]
            juros_aplicado = saldos_pos_juros.get(divida_id, anterior)
            desembolso_do_mes = desembolso_do_mes + max(dinheiro(0), juros_aplicado - posterior)
        desembolso_acumulado = e.DESEMBOLSO_ACUMULADO + desembolso_do_mes

    estado_final = EstadoSimulacao(
        mes=mes_atual,
        saldos=saldos_apos_ataque,
        quitadas=frozenset(quitadas_acumuladas),
        DIVIDA_ALVO_ATUAL=novo_alvo_id,
        CAPACIDADE_ATAQUE_M=e.CAPACIDADE_ATAQUE_M,
        ATAQUE_NAO_UTILIZADO_ACUMULADO=ataque_nao_utilizado_acumulado,
        DESEMBOLSO_ACUMULADO=desembolso_acumulado,
    )

    return ResultadoMes(
        estado_final=estado_final,
        quitacoes=tuple(quitacoes_do_mes),
        # A-01: RESIDUO_ATAQUE_M é o valor calculado em M-06, ANTES do laço
        # de cascata — o que "sobrou do ataque depois de zerar o alvo
        # original", conforme a fórmula normativa.
        RESIDUO_ATAQUE_M=residuo_ataque,
        aplicacoes_residuo=tuple(aplicacoes_residuo_do_mes),  # A-02 — cascata (T-43)
        ATAQUE_NAO_UTILIZADO=ataque_nao_utilizado,  # A-04/EC-01 — resíduo sem destino (T-44)
        VALOR_FLUXO_LIBERADO=valor_fluxo_liberado,  # F-01/F-02 — devolvido; entra em m+1 (T-46)
        reranqueamentos=reranqueamentos,  # R-03 — reranqueamento pleno (T-43)
    )


# ---------------------------------------------------------------------------
# Encadeamento de vários meses — `simular_cenario` (`T-46`, `M-10`..`M-12`,
# `RF-01`, `RF-02`, `AC-13`, `EC-13`).
#
# `executar_mes` (acima) resolve UM mês isolado e DEVOLVE o
# `VALOR_FLUXO_LIBERADO` sem incorporá-lo (`F-02`/`F-03`, `T-45`). É papel
# desta função — a única que enxerga o mês N *e* o mês N+1 ao mesmo tempo —
# fechar o ciclo completo:
#
# - `M-11`: o `VALOR_FLUXO_LIBERADO` devolvido pelo mês N soma-se a
#   `CAPACIDADE_ATAQUE_M` do `EstadoSimulacao` de ABERTURA do mês N+1, antes
#   de chamar `executar_mes` de novo — nunca dentro do mês N.
# - `M-12`/`R-02`/`AC-13`: `DIVIDA_ALVO_ATUAL` já atravessa os meses via
#   `estado_final.DIVIDA_ALVO_ATUAL` de `executar_mes`, que preserva o
#   alvo sem chamar `sel()` quando não há quitação (`M-05`, ver docstring
#   de `executar_mes` acima — "`SelecionarAlvo` — quando é chamada"). Este
#   laço NÃO adiciona nenhuma chamada extra a `sel()` entre meses: apenas
#   repassa o `EstadoSimulacao` devolvido por um mês como entrada do
#   próximo. Reranquear "por hábito" a cada virada de mês violaria `R-02`
#   (ver `piq-app-spec.md` linha 267, "Riscos e Antipadrões") — a garantia
#   aqui é estrutural: nenhuma linha deste laço chama `sel` diretamente.
# - `EC-13`: o laço para quando todas as dívidas estão quitadas OU quando o
#   mês simulado ultrapassa `P_HORIZONTE_MAXIMO_SIMULACAO` (convertido de
#   anos para meses, mesmo padrão de `engine/beneficio_marginal.py::
#   _horizonte_em_meses`). O estouro NÃO levanta exceção — encerra a
#   simulação normalmente e sinaliza em `Cenario.ESTOUROU_HORIZONTE`
#   (`condicional`, ver "Estouro do horizonte" abaixo). O alerta de
#   `P_HORIZONTE_ALERTA` (5 anos, < horizonte máximo de 10) é um sinal
#   DIFERENTE e mais cedo: `Cenario.MESES_ATE_ALERTA_HORIZONTE` sinaliza se
#   o `PRAZO_TOTAL` alcançado ultrapassa esse limiar, sem encerrar nada —
#   não existe hoje, em `engine/eventos.py` ou em qualquer outro módulo,
#   nenhuma função que já produza esse alerta (`gerar_alerta_evento_futuro`
#   é exclusivamente `NOVA_DIVIDA_PREVISTA`, RF-22 — assunto não relacionado
#   ao horizonte de simulação), então o campo é definido aqui.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Cenario:
    """§4 do plano técnico — saída de `simular_cenario` (`T-46`).

    Os seis primeiros campos (`ORDEM_QUITACAO`, `PRAZO_TOTAL`,
    `CUSTO_FUTURO_TOTAL`, `MESES_PRIMEIRA_VITORIA`, `meses`) são cópia
    literal do bloco `Cenario` da §4 do plano (`plans/motor-calculo.
    plan.md`, linhas 522-530), nomes idênticos. `metodo`/`classificacao`
    (também do bloco literal do plano) NÃO são preenchidos por esta tarefa:
    `SelecionarAlvo` ainda não tem implementação real de método (Avalanche/
    Bola de Neve/Híbrido são `T-49`+) e `CLASSIFICACAO_CENARIO` depende do
    Híbrido (`H-08`, `T-56`+) — ambos ficam com o valor neutro de cada
    domínio (`None`) até que a tarefa que os produz de fato exista. Não é
    lacuna silenciosa: o campo existe, tipado, documentado como
    "preenchido por tarefa futura" — não removido nem inventado.

    `ESTOUROU_HORIZONTE`/`MESES_ATE_ALERTA_HORIZONTE` são extensão desta
    tarefa (`EC-13`, "Estouro do horizonte" na docstring do módulo) — não
    aparecem no snippet literal do plano, mas o próprio plano (linha 536:
    "EC-13: encerra em P_HORIZONTE_MAXIMO_SIMULACAO e sinaliza") exige que
    `simular_cenario` sinalize esse estado no `Cenario` resultante; sem um
    campo próprio não haveria onde carregar o sinal. Mesmo padrão de
    extensão mínima e documentada já usado por `executar_mes` para o
    parâmetro `dividas` (ver docstring do módulo, "Parâmetro adicional a
    `executar_mes`").
    """

    metodo: METODO | None
    classificacao: CLASSIFICACAO_CENARIO | None
    ORDEM_QUITACAO: tuple[str, ...]
    PRAZO_TOTAL: Meses
    CUSTO_FUTURO_TOTAL: Dinheiro
    MESES_PRIMEIRA_VITORIA: Meses | None
    meses: tuple[ResultadoMes, ...]  # rastro completo para auditoria (NFR)
    ESTOUROU_HORIZONTE: bool  # EC-13: True ⇒ cenário condicional, sem abortar
    MESES_ATE_ALERTA_HORIZONTE: Meses | None  # P_HORIZONTE_ALERTA — None se nunca alcançado


def _horizonte_em_meses(p: Parametros, nome: str) -> int:
    """`P_HORIZONTE_MAXIMO_SIMULACAO`/`P_HORIZONTE_ALERTA` estão em ANOS na
    fonte de parâmetros — converte para meses (×12). Mesmo padrão de
    `engine/beneficio_marginal.py::_horizonte_em_meses`: `int(Decimal)`
    trunca exato, sem passar por `float` (RF-12), porque o parâmetro é um
    inteiro de anos por natureza.
    """
    anos = p.numero(nome)
    return int(anos) * 12


def simular_cenario(
    e: EstadoFinanceiro,  # noqa: ARG001 — parte do contrato do plano; sem uso nesta tarefa
    dg: Diagnostico,
    dividas: Mapping[str, Divida],
    sel: SelecionarAlvo,
    p: Parametros,
) -> Cenario:
    """`M-10`..`M-12` · `RF-01`, `RF-02` · `AC-13` · `EC-13` — encadeia
    `executar_mes` mês a mês até quitar todas as dívidas ou estourar
    `P_HORIZONTE_MAXIMO_SIMULACAO`. Ver "Encadeamento de vários meses" na
    docstring do módulo para o detalhamento de cada regra.

    **Parâmetro adicional `dividas` — mesma extensão documentada de
    `executar_mes`.** `EstadoFinanceiro.dividas` é `tuple[Divida, ...]` com
    `SALDO_DEVEDOR_ATUAL: DinheiroTalvez` — filtrar o inventário para o
    subconjunto elegível com saldo determinístico é responsabilidade dos
    gates (`engine/gates.py::aplicar_gates`, `T-64`), fora do escopo desta
    tarefa. `simular_cenario` recebe o inventário já resolvido (`Mapping[str,
    Divida]`, mesmo padrão de `executar_mes`) — nenhuma decisão de
    elegibilidade é tomada aqui. `e` (o `EstadoFinanceiro` bruto) fica na
    assinatura por ser parte do contrato do plano (§4), mesmo sem uso direto
    nesta tarefa — o inventário de fato consumido é o parâmetro `dividas`.

    `dg` carrega `CAPACIDADE_ATAQUE_CONSERVADORA` (RF-14/RF-15 — "a única
    capacidade que alimenta o cronograma-base", `engine/diagnostico.py`),
    usada como `CAPACIDADE_ATAQUE_M` do mês de abertura.

    RF-16: dívida com `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` não pode entrar
    na simulação — estimar o saldo ausente é proibido. Bloqueio explícito e
    ruidoso (`ValueError`) em vez de descartar a dívida em silêncio, porque
    filtragem silenciosa mascararia dado incompleto como se fosse inventário
    completo (mesma preocupação de `GAB-02`); a triagem definitiva (`Gate 1`,
    `INFORMACAO_PENDENTE`) é de `engine/gates.py` (`T-64`), fora do escopo
    desta tarefa — aqui só a recusa explícita existe, não a triagem.

    Devolve sempre um `Cenario` — nunca levanta exceção por estouro de
    horizonte (`EC-13`, o motor "continua e devolve os cenários... marcados
    como condicionais", §5 passo 5 do plano): o único erro possível é
    `ErroInvariante`, propagado de `executar_mes`, que é bug real do motor,
    não estado de negócio.
    """
    horizonte_maximo = _horizonte_em_meses(p, "P_HORIZONTE_MAXIMO_SIMULACAO")
    horizonte_alerta = _horizonte_em_meses(p, "P_HORIZONTE_ALERTA")

    saldos_iniciais: dict[str, Dinheiro] = {}
    for divida_id, divida in dividas.items():
        if divida.SALDO_DEVEDOR_ATUAL is DESCONHECIDO:
            raise ValueError(
                f"simular_cenario recebeu {divida_id!r} com SALDO_DEVEDOR_ATUAL "
                "DESCONHECIDO — RF-16 proíbe estimar; a triagem de dado ausente "
                "é responsabilidade dos gates (Gate 1), fora do escopo de T-46."
            )
        saldos_iniciais[divida_id] = divida.SALDO_DEVEDOR_ATUAL

    estado = EstadoSimulacao(
        mes=0,
        saldos=saldos_iniciais,
        quitadas=frozenset(),
        DIVIDA_ALVO_ATUAL=None,
        CAPACIDADE_ATAQUE_M=dg.CAPACIDADE_ATAQUE_CONSERVADORA,
        ATAQUE_NAO_UTILIZADO_ACUMULADO=dinheiro(0),
        DESEMBOLSO_ACUMULADO=dinheiro(0),
    )

    meses: list[ResultadoMes] = []
    ordem_quitacao: list[str] = []
    mes_primeira_vitoria: Meses | None = None
    estourou_horizonte = False
    mes_alerta_horizonte: Meses | None = None
    todas_dividas = frozenset(dividas.keys())

    while estado.quitadas != todas_dividas:
        if estado.mes >= horizonte_maximo:
            # EC-13: encerra SEM rodar mais um mês e SEM levantar exceção —
            # "cenário roda em modo estabilização e é marcado condicional",
            # nunca aborta.
            estourou_horizonte = True
            break

        resultado_mes = executar_mes(estado, dividas, sel, p)
        meses.append(resultado_mes)

        for divida_id in resultado_mes.quitacoes:
            ordem_quitacao.append(divida_id)
            if mes_primeira_vitoria is None:
                # RF-01/§9: primeira dívida quitada de toda a simulação,
                # qualquer que seja a origem (alvo original ou cascata).
                mes_primeira_vitoria = resultado_mes.estado_final.mes

        if mes_alerta_horizonte is None and resultado_mes.estado_final.mes >= horizonte_alerta:
            # Alerta a partir de P_HORIZONTE_ALERTA — sinal diferente do
            # estouro, não encerra a simulação (ver docstring do módulo).
            mes_alerta_horizonte = resultado_mes.estado_final.mes

        # M-11: o VALOR_FLUXO_LIBERADO devolvido por ESTE mês só entra na
        # CAPACIDADE_ATAQUE_M do PRÓXIMO EstadoSimulacao — nunca no que
        # acabou de ser produzido (`estado_final` já foi consumido acima
        # para tudo que não é capacidade; a soma abaixo é a ÚNICA alteração
        # que este laço faz sobre o estado devolvido por `executar_mes`).
        with localcontext(CONTEXTO_MOTOR):
            capacidade_proximo_mes = (
                resultado_mes.estado_final.CAPACIDADE_ATAQUE_M
                + resultado_mes.VALOR_FLUXO_LIBERADO
            )

        # M-12/R-02/AC-13: `DIVIDA_ALVO_ATUAL` é repassado tal como
        # `executar_mes` o devolveu — nenhuma chamada a `sel()` acontece
        # aqui. Sem quitação no mês, `estado_final.DIVIDA_ALVO_ATUAL` já é
        # idêntico ao alvo recebido (`M-05`, garantido por `executar_mes`);
        # este laço não reranqueia por conta própria em nenhum caso.
        estado = EstadoSimulacao(
            mes=resultado_mes.estado_final.mes,
            saldos=resultado_mes.estado_final.saldos,
            quitadas=resultado_mes.estado_final.quitadas,
            DIVIDA_ALVO_ATUAL=resultado_mes.estado_final.DIVIDA_ALVO_ATUAL,
            CAPACIDADE_ATAQUE_M=capacidade_proximo_mes,
            ATAQUE_NAO_UTILIZADO_ACUMULADO=(
                resultado_mes.estado_final.ATAQUE_NAO_UTILIZADO_ACUMULADO
            ),
            DESEMBOLSO_ACUMULADO=resultado_mes.estado_final.DESEMBOLSO_ACUMULADO,
        )

    # CUSTO_FUTURO_TOTAL — nenhuma fonte normativa do slug (motor-calculo.
    # spec.md, plans/motor-calculo.plan.md) escreve a fórmula explícita para
    # o Cenario agregado (só existe DESEMBOLSO_FUTURO por TRAJETÓRIA isolada,
    # engine/trajetoria.py, Definições §2). Adotado EstadoSimulacao.
    # DESEMBOLSO_ACUMULADO — a soma exata, mês a mês, de tudo que
    # efetivamente saiu do caixa para abater saldo (pagamento normal +
    # ataque, já líquido de juros absorvidos), acumulada por `executar_mes`
    # desde T-42/T-43 (ver `desembolso_do_mes` em executar_mes, acima) — é a
    # definição operacional mais direta de "custo total da trajetória
    # completa do cenário" disponível hoje no motor, coerente com o mesmo
    # princípio de DESEMBOLSO_FUTURO por trajetória isolada, sem inventar
    # fórmula nova. Ambiguidade registrada — se uma fonte futura (gabarito
    # numérico do Híbrido, T-56+) desambiguizar de forma diferente, esta
    # escolha deve ser revisitada (§6 do sdd.config.md).
    custo_futuro_total = estado.DESEMBOLSO_ACUMULADO

    return Cenario(
        metodo=None,  # T-49+: nenhum método real ainda implementado nesta tarefa
        classificacao=None,  # T-56+: classificação do Híbrido, fora do escopo
        ORDEM_QUITACAO=tuple(ordem_quitacao),
        PRAZO_TOTAL=estado.mes,
        CUSTO_FUTURO_TOTAL=custo_futuro_total,
        MESES_PRIMEIRA_VITORIA=mes_primeira_vitoria,
        meses=tuple(meses),  # rastro completo mês a mês, para auditoria
        ESTOUROU_HORIZONTE=estourou_horizonte,
        MESES_ATE_ALERTA_HORIZONTE=mes_alerta_horizonte,
    )
