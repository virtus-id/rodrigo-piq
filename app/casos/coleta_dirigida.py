"""Blocos 7 e 8 dirigidos pelo motor — `RF-17`, `AC-19` (T-75, T-76).

`ESTADO_CASO.COLETA_DIRIGIDA` (`app/casos/maquina.py`, T-33) reabre as
perguntas do Bloco 7 (`collection/registros/bloco-07.yaml::B7.05`..`B7.16`,
T-18) repetidas por `DIVIDA_ID`, exclusivamente para as dívidas com ação de
renegociação em `ORDEM_ACOES`, e as do Bloco 8
(`collection/registros/bloco-08.yaml::B8.01`..`B8.15`, T-18), exclusivamente
para as dívidas com ação de troca. **A interface nunca decide sozinha qual
dívida é candidata** — este módulo só LÊ o que `app/motor/acoes.py::
acoes_em_acompanhamento` (T-74) já expôs, nunca avalia saldo, taxa ou
qualquer critério financeiro próprio (Lei nº 3, `plans/app-aluno.plan.md`
§1: a aplicação não calcula).

**Mesmo mecanismo para os dois blocos (T-76).** `dividas_para_bloco_7` e
`dividas_para_bloco_8` não duplicam a lógica de filtro por Gate 3 — ambas são
chamadas finas de `dividas_por_gate_e_campo`, parametrizada pelo NOME do
campo booleano lido (`RENEGOCIACAO_PENDENTE` ou `TROCA_PENDENTE`). A única
diferença entre os dois blocos é esse nome de campo e, em `perguntas_do_
bloco_7`/`_8`, o número do bloco consultado no registro — nunca uma segunda
cópia da filtragem por `gate_origem`.

## A FRONTEIRA REAL COM `TIPO_ACAO` — a técnica desta tarefa, documentada
## em detalhe porque é sutil e frágil.

`engine.gates.AcaoRequerida` (hoje) tem apenas `DIVIDA_ID`, `descricao`,
`gate_origem: Literal[2, 3]` e `prioridade_excepcional` — **não tem
`TIPO_ACAO`** (`OQ-13` aberta, dependência externa do slug `motor-calculo`;
ver `app/motor/acoes.py`, T-74, para a mesma trava). Sem `TIPO_ACAO`, é
IMPOSSÍVEL, a partir da `AcaoRequerida` isolada, saber se uma ação do Gate 3
é "renegociação" ou "troca" — as duas únicas causas que disparam aquele gate
(`engine/gates.py::aplicar_gate_3_transformacao`, T-30). Duas saídas foram
descartadas antes de chegar à usada aqui:

  1. **Parsing de `descricao`** (`str.split`/`in`/regex sobre o texto livre
     da ação) — EXPLICITAMENTE proibido por `T-74` (mesma trava se aplica
     aqui: `descricao` é texto auditável para humano, Q-05, nunca dado
     estruturado para a aplicação decidir sobre ele) e auditado por
     `tests/app_aluno/test_acoes.py`.
  2. **Inventar `TIPO_ACAO` aqui** — proibido pela mesma razão de `T-74`:
     `OQ-13` não tem identificador respondido pelo especialista; escrever um
     literal de tipo de ação nesta camada seria inventar o domínio que só
     `engine/` pode publicar.

**A técnica real, e por que ela funciona sem literal de tipo de ação e sem
parsing.** `engine/gates.py::aplicar_gate_3_transformacao` (T-30) só desvia
uma dívida para o Gate 3 quando `divida.RENEGOCIACAO_PENDENTE` OU
`divida.TROCA_PENDENTE` é `True` — os dois ÚNICOS campos de `Divida`
(`engine/estado.py`, ambos comentados "# Gate 3") que alimentam aquele gate.
`SnapshotOrdem.estado_inputs` (`engine/snapshot.py`, `V-02`: "nada se
perde") é o MESMO `EstadoFinanceiro` que o motor consumiu para produzir
`ORDEM_ACOES` — a mesma carteira de dívidas, incluindo os dois booleanos,
está ali, intacta. Então, para uma `AcaoRequerida` com `gate_origem == 3`:

    1. localizar, em `snapshot.estado_inputs.dividas`, a `Divida` cujo
       `DIVIDA_ID` bate com `acao.DIVIDA_ID` (mesmo identificador — ambos
       vêm do mesmo `EstadoFinanceiro`, nunca de fontes divergentes);
    2. ler `divida.RENEGOCIACAO_PENDENTE` — campo REAL do contrato, booleano
       que o motor já expõe, não um `TIPO_ACAO` inventado nem uma string
       interpretada.

Isso é LEITURA de campo — não derivação (o booleano já existe pronto em
`Divida`, este módulo não o calcula) nem parsing (nenhuma string é
interpretada; `RENEGOCIACAO_PENDENTE` é `bool`, comparado por identidade
`is True`/truthiness direta). Nenhum nome de `TIPO_ACAO` aparece neste
módulo, e a busca por `DIVIDA_ID` é indexação simples (`==` sobre um campo
que já é o identificador estável da dívida), nunca inferência.

**Ambiguidade conhecida e não resolvida por desempate inventado.** Uma
`Divida` com `gate_origem == 3` E `RENEGOCIACAO_PENDENTE = True` E
`TROCA_PENDENTE = True` simultaneamente dispara os DOIS blocos (7 e 8) —
`dividas_para_bloco_7` e `dividas_para_bloco_8` (T-76) não são mutuamente
exclusivas por desenho: `aplicar_gate_3_transformacao` já trata
esse caso como "os dois motivos coexistem" (ver `origem = "RENEGOCIACAO_
PENDENTE e TROCA_PENDENTE"` naquele módulo) e não escolhe um sobre o outro.
Este módulo espelha a mesma decisão — abrir os dois blocos para a mesma
dívida quando os dois booleanos são `True` é o comportamento correto, não
uma falha de desempate a resolver. Não há Open Question aqui: a leitura
direta dos dois campos, independentemente um do outro, já resolve o caso sem
ambiguidade.

**Gate 2 (`gate_origem == 2`, contenção de risco) nunca abre o Bloco 7** —
aquele gate não tem relação com renegociação/troca (`RISCO_MATERIAL_
IMINENTE`, um campo totalmente diferente); só ações de `gate_origem == 3`
são consideradas por este módulo.

**Nenhum critério de elegibilidade é avaliado aqui.** Este módulo nunca
calcula saldo, taxa, CET ou qualquer condição financeira — a decisão de
"esta dívida precisa de intervenção" já foi tomada pelo motor
(`engine/gates.py::aplicar_gate_3_transformacao`) antes de `ORDEM_ACOES`
existir; a aplicação só lê `gate_origem` e os dois booleanos já prontos de
`Divida`.

REGRAS: `RF-17`, `AC-19`
"""

from __future__ import annotations

from typing import Final, Literal

from app.motor.acoes import acoes_em_acompanhamento
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.repeticao import perguntas_da_ficha
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-17", "AC-19")

_GATE_ORIGEM_TRANSFORMACAO: Final[int] = 3
_BLOCO_RENEGOCIACAO: Final[int] = 7
_BLOCO_TROCA: Final[int] = 8

_CampoGateTransformacao = Literal["RENEGOCIACAO_PENDENTE", "TROCA_PENDENTE"]


def dividas_por_gate_e_campo(
    snapshot: SnapshotOrdem, gate_origem: int, nome_campo: _CampoGateTransformacao
) -> tuple[str, ...]:
    """Mecanismo genérico (T-76) por trás de `dividas_para_bloco_7` e
    `dividas_para_bloco_8` — **o único caminho de código** que filtra
    `ORDEM_ACOES` por gate e lê o booleano correspondente de `Divida`. Nem
    Bloco 7 nem Bloco 8 têm uma segunda cópia desta lógica; cada um só
    fornece o `gate_origem` e o NOME do campo a ler.

    A lista vem exclusivamente de `snapshot.ORDEM_ACOES`
    (`app/motor/acoes.py::acoes_em_acompanhamento`, T-74, leitura pura) —
    nenhum saldo, taxa ou critério de elegibilidade próprio é avaliado
    aqui. Para cada ação cujo `gate_origem` bate com o parâmetro, localiza a
    `Divida` correspondente em `snapshot.estado_inputs.dividas` (mesmo
    `EstadoFinanceiro` que o motor consumiu, `V-02`) e inclui o `DIVIDA_ID`
    quando `getattr(divida, nome_campo)` é `True` — ver a nota extensa no
    cabeçalho do módulo sobre por que esta é a única forma de distinguir
    renegociação/troca sem literal de `TIPO_ACAO` e sem parsing de
    `descricao`.

    `ORDEM_ACOES` vazia devolve tupla vazia — nenhuma dívida abre o bloco
    (terceiro critério de aceite de `T-75`, reaproveitado por `T-76`).

    **T-92 — `acao.DIVIDA_ID: str | None`.** `AcaoRequerida.DIVIDA_ID`
    (`engine/gates.py`, T-79/RF-31) relaxou para `str | None`: a ação de
    economia (`TIPO_ACAO="ECONOMIA"`, `RF-33`) não tem dívida associada e
    tem `gate_origem=None`. Como este filtro já exige `gate_origem ==
    gate_origem` (aqui sempre `3`, Gate 3/Transformação — ver
    `_GATE_ORIGEM_TRANSFORMACAO`), a ação de economia NUNCA passaria do
    primeiro `if` mesmo sem a checagem abaixo (`gate_origem=None != 3`). A
    checagem explícita `acao.DIVIDA_ID is not None` é mantida ainda assim,
    por construção: nenhuma `AcaoRequerida` com `gate_origem == 3` tem
    `DIVIDA_ID=None` no contrato atual (só a ação de economia tem
    `DIVIDA_ID=None`, e ela nunca tem `gate_origem=3`) — mas o `mypy
    --strict` não infere essa correlação entre dois campos independentes da
    dataclass, então a checagem torna a garantia explícita em vez de um
    `# type: ignore`. O comportamento para o caso (hoje inatingível, mas
    tratado) é PULAR o item, o mesmo tratamento já dado ao `DIVIDA_ID` órfão
    logo abaixo — nenhuma ação sem dívida associada pode abrir um bloco por
    `DIVIDA_ID`."""
    dividas_por_id = {divida.DIVIDA_ID: divida for divida in snapshot.estado_inputs.dividas}

    ids: list[str] = []
    for acao in acoes_em_acompanhamento(snapshot):
        if acao.gate_origem != gate_origem:
            continue
        if acao.DIVIDA_ID is None:
            # T-92: ação sem dívida associada (ação de economia, RF-33) não
            # pode abrir bloco por DIVIDA_ID — pula, mesmo tratamento do
            # DIVIDA_ID órfão abaixo. Inatingível hoje (só gate_origem=3
            # chega aqui, e a ação de economia nunca tem gate_origem=3), mas
            # explícito para satisfazer mypy --strict sem type: ignore.
            continue
        divida = dividas_por_id.get(acao.DIVIDA_ID)
        if divida is None:
            # Defensivo: toda AcaoRequerida do Gate 3 se origina de uma
            # Divida do MESMO EstadoFinanceiro (engine/gates.py::
            # particionar_elegibilidade) — não deveria haver DIVIDA_ID órfão.
            continue
        if getattr(divida, nome_campo):
            ids.append(acao.DIVIDA_ID)

    return tuple(ids)


def dividas_para_bloco_7(snapshot: SnapshotOrdem) -> tuple[str, ...]:
    """`AC-19` — os `DIVIDA_ID` que abrem o Bloco 7, e SOMENTE esses. Chamada
    fina de `dividas_por_gate_e_campo` com o campo de renegociação — mesmo
    caminho de código de `dividas_para_bloco_8` (T-76)."""
    return dividas_por_gate_e_campo(
        snapshot, _GATE_ORIGEM_TRANSFORMACAO, "RENEGOCIACAO_PENDENTE"
    )


def dividas_para_bloco_8(snapshot: SnapshotOrdem) -> tuple[str, ...]:
    """`AC-19` (T-76) — os `DIVIDA_ID` que abrem o Bloco 8, e SOMENTE esses.
    Chamada fina de `dividas_por_gate_e_campo` com o campo de troca — mesmo
    caminho de código de `dividas_para_bloco_7`, nenhuma lógica de filtro
    por gate duplicada aqui."""
    return dividas_por_gate_e_campo(snapshot, _GATE_ORIGEM_TRANSFORMACAO, "TROCA_PENDENTE")


def perguntas_do_bloco_7(registros: tuple[RegistroPergunta, ...]) -> tuple[RegistroPergunta, ...]:
    """As perguntas `B7.05`..`B7.16` (`escopo_repeticao: DIVIDA_ID`, `bloco:
    7`) — reaproveita o mecanismo genérico de `collection/repeticao.py::
    perguntas_da_ficha` (`RF-04`) para o escopo de repetição, e filtra por
    `registro.bloco == 7` (campo do próprio registro, T-09) para excluir as
    demais perguntas por `DIVIDA_ID` que não são deste bloco (Bloco 5 —
    cadastro da dívida; Bloco 11 — acompanhamento por `ACAO_ID`, não por
    `DIVIDA_ID`, `AC-50`). Nenhuma lista de `ID` de pergunta codificada à
    mão aqui: o conjunto nasce dos próprios campos do registro (T-18)."""
    da_ficha_divida = perguntas_da_ficha(registros, EscopoRepeticao.DIVIDA_ID)
    return tuple(registro for registro in da_ficha_divida if registro.bloco == _BLOCO_RENEGOCIACAO)


def perguntas_do_bloco_8(registros: tuple[RegistroPergunta, ...]) -> tuple[RegistroPergunta, ...]:
    """As perguntas `B8.01`..`B8.15` (`escopo_repeticao: DIVIDA_ID`, `bloco:
    8`) (T-76) — mesmo mecanismo de `perguntas_do_bloco_7`: reaproveita
    `collection/repeticao.py::perguntas_da_ficha` para o escopo de repetição
    e filtra por `registro.bloco == 8`. Nenhuma lista de `ID` de pergunta
    codificada à mão aqui."""
    da_ficha_divida = perguntas_da_ficha(registros, EscopoRepeticao.DIVIDA_ID)
    return tuple(registro for registro in da_ficha_divida if registro.bloco == _BLOCO_TROCA)
