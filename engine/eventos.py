"""Gatilhos de recálculo (`EVENTO_RECALCULO`) e evento futuro previsto —
RF-02, RF-22, AC-30, AC-31 · §3, §11.6.

## Gatilhos de recálculo — `avaliar_gatilho_recalculo` (`T-66`)

Fonte normativa (`specs/piq-app-spec.md`, tabela "Devolutiva final", família
`R`):

```
R-01  RECALCULAR_ORDEM = QUITACAO_CONFIRMADA (de qualquer divida, inclusive
      a que se encerrou apenas pelo pagamento normal) OU
      EVENTO_RECALCULO_EXTERNO.
R-04  Alteracao meramente cadastral, correcao textual, mudanca cosmetica de
      registro ou passagem ordinaria do tempo nao constitui EVENTO_RECALCULO.
R-05  Ocorrendo EVENTO_RECALCULO material, a engine DEVE reavaliar todas as
      decisoes afetadas e gerar novo snapshot. Recalcular nao implica mudar:
      se metodo, D* e ordem seguirem sendo os melhores, permanecem.
```

**Nomenclatura `R-*` — duas famílias distintas sob o mesmo prefixo.** A
spec canônica usa `R-01`..`R-05` tanto para os gatilhos de recálculo
*externo* que produzem um novo `SnapshotOrdem` (RF-02, esta função) quanto
`tests/regras/test_R.py` (T-47) já usa `R-01`..`R-03` para o
reranqueamento *intramês* de `simular_cenario`/`executar_mes`
(`engine/ciclo_mensal.py`) — conceito relacionado (ambos decidem "quando
recalcular a ordem"), mas em camadas diferentes: um é o laço de simulação
interno de um cenário, o outro é o gatilho que decide se o mundo real
justifica um NOVO cálculo/snapshot fora desse laço. Os testes desta tarefa
vivem em `tests/regras/test_gatilho_recalculo.py` — arquivo novo, para não
colidir com nem sobrescrever `test_R.py` — e cada teste cita o RF/AC/EC que
desambigua (RF-02, AC-13, AC-31, EC-02, EC-08, EC-09) em vez de reusar o
prefixo `R-*` isolado no nome.

**`EVENTO_RECALCULO` (o enum) já existe em `engine/tipos.py` desde `T-05`** —
domínio fechado sem membro cosmético (`R-04`/`EC-08` já garantidos por
construção, ver docstring do enum). O que faltava, e é o que esta função
acrescenta, é a regra de decisão "este evento (ou a ausência dele) justifica
produzir um novo snapshot?" — hoje reimplementada implicitamente pelo
chamador de `engine/motor.py:calcular_plano` (§4 do plano técnico); esta
função a centraliza para que `calcular_plano` (fora do escopo de `T-66`,
ver `T-70`/`T-73`) a consuma em vez de duplicá-la.

A regra é deliberadamente trivial — e a trivialidade é a prova de `R-02`/
`R-04`/`R-05`: não há caminho de código que avalie "o resultado seria
igual, então pulo o recálculo" (`R-05`/`EC-09`). Existe evento material
(`EVENTO_RECALCULO` não-`None`) ou não existe; não há terceiro caso, porque
`EVENTO_RECALCULO` não tem membro cosmético e "virada de mês" nunca produz
um `EVENTO_RECALCULO` (nenhuma função do motor constrói um a partir da mera
passagem do tempo — `R-02`, `AC-13`, já verificado no ciclo mensal por T-47).

## Evento futuro previsto — `gerar_alerta_evento_futuro` (`T-34`/`T-35`)

Fonte normativa (`specs/motor-calculo.spec.md` §11.6):

```
NOVA_DIVIDA_PREVISTA = SIM ou TALVEZ nao entra na projecao-base. E insumo
de RISCO_RECAIDA, alerta de sustentabilidade, condicao de revisao futura e
informacao para o relatorio - nao e divida do inventario.
```

> A projeção-base incorpora somente eventos futuros **determinísticos** já
> pertencentes ao estado financeiro ou expressamente aprovados para o
> cenário. Intenção, possibilidade ou probabilidade de nova dívida não é
> evento determinístico.

**A garantia desta tarefa é dupla — positiva e negativa.**

*Positiva*: `gerar_alerta_evento_futuro` lê `NOVA_DIVIDA_PREVISTA` (já um dos
5 sinais de `classificar_RISCO_RECAIDA`, `engine/risco.py`, T-15) e produz um
`AlertaEventoFuturo` puramente informativo quando SIM ou TALVEZ, carregando
`JANELA_NOVA_DIVIDA` (B1.05) para uso futuro do relatório (fora do escopo
deste slug — §9 da spec: "geração do relatório é escopo de `relatorio`").

*Negativa* — e esta é a parte que realmente implementa o "filtro" do título
da tarefa: **este módulo nunca constrói uma `Divida`, nunca lê nem escreve
`EstadoFinanceiro.dividas`, nunca altera nenhum saldo.** Não existe, em
`gerar_alerta_evento_futuro`, nenhum caminho que promova a previsão a dívida
do inventário. A prova de que o RESTO do motor também respeita essa regra
não está neste módulo — está na ausência: nenhuma função de
`engine/estado.py`, `engine/gates.py`, `engine/diagnostico.py` ou
`engine/risco.py` lê `NOVA_DIVIDA_PREVISTA`/`JANELA_NOVA_DIVIDA` para
qualquer coisa além de contagem de sinal (D.4, T-15). A verificação ad-hoc
de T-34 (comparação de dois `EstadoFinanceiro` idênticos exceto por
`NOVA_DIVIDA_PREVISTA`) demonstra empiricamente que `calcular_diagnostico`
produz saldos e resultados financeiros IDÊNTICOS nos dois casos — a única
diferença observável é `RISCO_RECAIDA` (via `classificar_RISCO_RECAIDA`) e
o alerta que este módulo gera.

**Por que não há partição de elegibilidade a filtrar aqui.**
`ParticaoElegibilidade` (`engine/gates.py`, T-32) consolida `elegiveis`/
`bloqueadas`/`ORDEM_ACOES` a partir de `EstadoFinanceiro.dividas` — uma
tupla que só contém `Divida` de verdade, nunca hipotéticas. Como
`gerar_alerta_evento_futuro` não cria `Divida` nem altera essa tupla, a
garantia "nenhuma dívida hipotética chega à partição de elegibilidade" vale
por CONSTRUÇÃO: não há código, em lugar nenhum do motor, capaz de inserir
uma dívida hipotética em `EstadoFinanceiro.dividas` a partir de
`NOVA_DIVIDA_PREVISTA`. Não é necessário — e seria incorreto — consumir
`ParticaoElegibilidade` aqui: isso acoplaria um módulo puramente informativo
a uma estrutura de elegibilidade que ele nunca deveria influenciar.

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-22", "AC-31", "EC-08", "EC-09", "§3", "§11.6")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from engine.estado import JANELA_NOVA_DIVIDA, EstadoFinanceiro
from engine.tipos import EVENTO_RECALCULO, SimNaoTalvez

REGRAS: Final[tuple[str, ...]] = ("RF-02", "RF-22", "AC-31", "EC-08", "EC-09", "§3", "§11.6")


@dataclass(frozen=True, slots=True)
class ResultadoGatilhoRecalculo:
    """Decisão auditável de `avaliar_gatilho_recalculo` — RF-02 · R-01/R-02/
    R-05 (família de gatilho externo, ver desambiguação no docstring do
    módulo).

    Mesmo padrão de auditabilidade de `AlertaEventoFuturo`/`ResultadoGates`:
    a decisão nunca é um `bool` solto, sempre vem com o motivo textual que a
    justifica — o revisor humano (e o snapshot, `V-02`) precisa do motivo,
    não só do resultado.
    """

    deve_recalcular: bool
    evento: EVENTO_RECALCULO | None  # ecoa o evento avaliado, para auditoria
    motivo: str


def avaliar_gatilho_recalculo(evento: EVENTO_RECALCULO | None) -> ResultadoGatilhoRecalculo:
    """RF-02 · R-01/R-02/R-04/R-05 · AC-13, AC-31, EC-02, EC-08, EC-09 —
    decide se um evento observado no mundo real justifica produzir um novo
    `SnapshotOrdem` (fora do escopo desta função: `engine/snapshot.py`,
    `T-67`; `engine/motor.py:calcular_plano`, `T-70`/`T-73`).

    Contrato, por caso:

    - `evento is None` (nenhuma quitação confirmada, nenhum evento material
      — inclui a virada de mês sozinha, que nunca produz um
      `EVENTO_RECALCULO`): `deve_recalcular = False` (`R-02`, `AC-13`).
    - `evento is not None` — qualquer membro de `EVENTO_RECALCULO`,
      incluindo `QUITACAO_CONFIRMADA` (`R-01`, `EC-02`) e `NOVA_DIVIDA`
      (`AC-31`): `deve_recalcular = True`, SEMPRE — nunca condicionado ao
      resultado do recálculo. Não há, aqui ou em qualquer outro lugar deste
      módulo, comparação entre o snapshot anterior e um snapshot hipotético
      "seria igual" que pudesse suprimir a produção do novo snapshot
      (`R-05`, `EC-09`): a decisão depende só de ter havido evento, nunca do
      resultado que ele produziria.

    Não existe terceiro caso porque `EVENTO_RECALCULO` (`engine/tipos.py`,
    `T-05`) não tem — e não pode ter — um membro para alteração cadastral
    ou cosmética (`R-04`, `EC-08`): a ausência é estrutural, não uma
    checagem de runtime. Um chamador que queira expressar "o usuário só
    corrigiu um apelido de dívida" não tem como construir um
    `EVENTO_RECALCULO` para isso — o único jeito de chegar a
    `deve_recalcular = False` por uma mudança cosmética é não ter evento
    algum, que é exatamente o caso `None` acima. Ver
    `test_R04_alteracao_cosmetica_e_inexprimivel_no_enum`
    (`tests/regras/test_gatilho_recalculo.py`) para a prova estrutural.
    """
    if evento is None:
        return ResultadoGatilhoRecalculo(
            deve_recalcular=False,
            evento=None,
            motivo=(
                "Nenhum EVENTO_RECALCULO observado — nem quitação confirmada, nem "
                "evento externo material. A mera passagem do tempo (virada de mês) "
                "nunca constitui, por si só, um gatilho de recálculo (R-02, AC-13)."
            ),
        )

    return ResultadoGatilhoRecalculo(
        deve_recalcular=True,
        evento=evento,
        motivo=(
            f"EVENTO_RECALCULO = {evento.value} — evento material confirmado. "
            "Novo snapshot é produzido mesmo que método, D* e ordem resultantes "
            "sejam idênticos aos do snapshot anterior (R-05, EC-09)."
        ),
    )


@dataclass(frozen=True, slots=True)
class AlertaEventoFuturo:
    """Alerta de sustentabilidade produzido por uma previsão de nova dívida
    — §11.6, AC-30.

    Puramente informativo: nenhum campo aqui é `Divida`, nenhum campo altera
    saldo, nenhum campo entra em `ORDEM_QUITACAO`. Existe só para (a)
    carregar `NOVA_DIVIDA_PREVISTA`/`JANELA_NOVA_DIVIDA` de forma auditável
    até o relatório (fora do escopo deste slug) e (b) documentar, no próprio
    tipo, que o dado é "condição de revisão futura" (§11.6) — não projeção.

    `NOVA_DIVIDA_PREVISTA` é reproduzido aqui (não só implícito por o alerta
    existir) para que o revisor humano veja o valor exato — SIM ou TALVEZ —
    sem precisar voltar ao `EstadoFinanceiro` de origem, mesmo princípio de
    auditabilidade de `SinalD4`/`ClassificacaoRisco` (`engine/risco.py`) e
    `ResultadoValorRelevante` (`engine/valor_quitacao.py`).
    """

    NOVA_DIVIDA_PREVISTA: SimNaoTalvez  # sempre SIM ou TALVEZ — ver contrato da função
    JANELA_NOVA_DIVIDA: JANELA_NOVA_DIVIDA | None  # B1.05: pode ser NAO_SEI ou ausente
    motivo: str  # texto auditável — mesmo padrão de ResultadoGates.motivo


def gerar_alerta_evento_futuro(estado: EstadoFinanceiro) -> AlertaEventoFuturo | None:
    """RF-22 · AC-30 · §11.6 — produz o alerta de sustentabilidade quando
    `NOVA_DIVIDA_PREVISTA ∈ {SIM, TALVEZ}`, e `None` quando `NAO`.

    Contrato negativo, explícito por não ter alternativa no código: esta
    função lê exatamente um campo de `estado` (`sinais_comportamentais.
    NOVA_DIVIDA_PREVISTA`, mais `JANELA_NOVA_DIVIDA` para compor o alerta) e
    NUNCA escreve em `estado`, nunca lê `estado.dividas` além de não tocá-la,
    nunca constrói `Divida`. `EstadoFinanceiro` é `frozen=True` (T-08) — não
    haveria sequer como mutá-lo aqui, mas a garantia normativa (RF-22) exige
    mais do que imutabilidade estrutural: exige que NENHUM código do motor
    trate esta previsão como fluxo determinístico. Este módulo cumpre sua
    parte não fazendo isso; a verificação ad-hoc de T-34 prova que o resto
    do motor também não faz.

    `SimNaoTalvez` não tem membro `DESCONHECIDO` (`engine/tipos.py`) — não há
    terceiro caso a tratar além de SIM/TALVEZ (gera alerta) e NAO (não
    gera). Devolve `None` em vez de um `AlertaEventoFuturo` vazio: ausência
    de alerta é ausência de objeto, não um objeto com campos nulos — mesmo
    padrão de `Divida.OPORTUNIDADE_VIGENTE: Oportunidade | None` (T-08) e
    das funções de gate (`ResultadoGates | None`, `engine/gates.py`).
    """
    sinais = estado.sinais_comportamentais
    previsao = sinais.NOVA_DIVIDA_PREVISTA

    if previsao not in (SimNaoTalvez.SIM, SimNaoTalvez.TALVEZ):
        # NAO: nenhum alerta. Não há caso DESCONHECIDO em SimNaoTalvez.
        return None

    motivo = (
        f"NOVA_DIVIDA_PREVISTA = {previsao.value} — evento apenas provável, "
        "fora da projeção-base (§11.6). Insumo de RISCO_RECAIDA, alerta de "
        "sustentabilidade e condição de revisão futura; nunca dívida do "
        "inventário. Contratada de fato, dispara EVENTO_RECALCULO = "
        "NOVA_DIVIDA e novo snapshot (ver avaliar_gatilho_recalculo, AC-31)."
    )

    return AlertaEventoFuturo(
        NOVA_DIVIDA_PREVISTA=previsao,
        JANELA_NOVA_DIVIDA=sinais.JANELA_NOVA_DIVIDA,
        motivo=motivo,
    )
