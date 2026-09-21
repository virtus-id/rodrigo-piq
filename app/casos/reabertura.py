"""Reabertura de faixa de perguntas (`RF-27`, `AC-34`, T-80) e de campo
isolado (`RF-27`, `AC-33`, T-85).

`plans/app-aluno.plan.md` §5.4/§7.1 é explícito: **reabertura é da
PERGUNTA, nunca do estado do caso**. `RESULTADO_ACAO_RENEGOCIACAO = Sim`
(`B11.03-REN`) reabre `B7.05`–`B7.16` para a dívida da ação — "reabrir"
significa apenas que aquelas perguntas voltam a ser candidatas a
"próxima pendente" (mesmo conceito de `app/casos/progresso.py::
PendenciaObrigatoria`, T-44/T-45), **sem apagar nem sobrescrever** o valor
já gravado. `app/casos/maquina.py` já documenta por que isso não é
estado: modelar "reabriu B7" como `ESTADO_CASO` multiplicaria estados por
pergunta — a pendência mora na pergunta (`respostas` + conjunto de
reaberturas), o estado do caso só diz em que fase ele está.

**A faixa `B7.05`–`B7.16`, sem lista literal de `ID` em `.py` — o
mecanismo desta tarefa.** A faixa não é um intervalo de string comparado
por ordem lexicográfica nem uma tupla de `ID` escrita à mão aqui: é
exatamente o conjunto que `app/casos/coleta_dirigida.py::
perguntas_do_bloco_7` (T-75) já declara a partir dos PRÓPRIOS CAMPOS do
registro (`registro.bloco == 7` + `escopo_repeticao == DIVIDA_ID`,
`collection/registro.py`, T-09) — nunca um literal novo. Dois fatos do
dado (não do código) fecham a equivalência com "B7.05–B7.16":

  1. `collection/registros/bloco-07.yaml` (T-18) transcreve, por decisão
     DAQUELE registro (comentário de cabeçalho do YAML), exclusivamente
     as perguntas `B7.05` a `B7.16` — `B7.01`–`B7.04` (tentativa
     anterior) e `B7.S01`/`B7.EX01`–`B7.EX03` (seguro/execução) não
     fazem parte do arquivo. Logo, "toda pergunta com `bloco == 7`" já É
     "a faixa B7.05–B7.16", por construção do dado, não por cálculo
     deste módulo.
  2. Reaproveitar `perguntas_do_bloco_7` (em vez de duplicar o filtro por
     `bloco == 7`) garante que, se o registro crescer no futuro (T-18
     documenta `B7.01`-`B7.04`/`B7.S01`/`B7.EX01`-`EX03` como
     "transcrição futura"), esta função e a de coleta dirigida
     permanecem a MESMA fonte de verdade — nunca duas cópias do que é
     "o Bloco 7" que possam divergir.

Este módulo, portanto, não introduz nenhum novo mecanismo de "faixa" no
esquema de registro (nenhuma mudança em `collection/registro.py`,
`collection/carga.py` ou `collection/esquema-registros.json`): o único
campo necessário, `bloco`, já existe desde T-09/T-16, e o filtro por ele
já existe desde T-75. "Declarar a faixa no registro/ação" é reaproveitar
esse campo do registro, não inventar um segundo.

**A dívida da ação, pela mesma técnica de `T-75` (Gate 3 +
`RENEGOCIACAO_PENDENTE`).** "Reabrir renegociação" pressupõe saber que a
ação é do tipo renegociação. `engine.gates.AcaoRequerida` não tem
`TIPO_ACAO` (`OQ-13`, mesma lacuna documentada em `app/casos/
coleta_dirigida.py` e `app/motor/acoes.py`) — não se inventa esse campo
aqui. `dividas_para_bloco_7(snapshot)` (T-75) já resolve exatamente "quais
`DIVIDA_ID` têm uma ação de renegociação pendente segundo o motor", pela
leitura de `gate_origem == 3` + `Divida.RENEGOCIACAO_PENDENTE`, nunca por
parsing de `descricao` nem por um `TIPO_ACAO` literal. Reabrir a
renegociação de uma dívida específica é chamar essa mesma função e
confirmar que o `DIVIDA_ID` da ação está no resultado — reaproveito,
nunca uma segunda implementação da mesma decisão.

**Como o valor anterior permanece gravado e visível.** Este módulo NUNCA
importa nem chama nada de `persistencia/app_aluno/respostas.py` que
grave, apague ou sobrescreva (nenhum `INSERT`/`UPDATE`/`DELETE`, nenhuma
chamada de gravação em lugar nenhum do arquivo) — a única leitura feita é
`RespostasCaso.valor_no_item` (`collection/respostas.py`, T-22), que
devolve o valor corrente sem jamais zerá-lo. "Reaberta" não é um estado
mutuamente exclusivo com "respondida": as duas coexistem por desenho —
`perguntas_pendentes_por_reabertura` devolve a pendência mesmo quando
`RespostasCaso.valor_no_item(...)` já tem um valor concreto (diferença
deliberada de `app/casos/progresso.py::pendencias_obrigatorias`, cujo
critério de pendência é "em branco"; aqui a pendência é "reaberta",
independentemente de estar em branco ou não) — o chamador (rota HTTP,
fora do escopo desta tarefa) usa essa lista para decidir QUAIS perguntas
oferecer de novo ao aluno, pré-preenchidas com `valor_no_item`, exatamente
como `app/http/renderizacao.py` já faz para reabrir um campo com o valor
anterior.

**O estado do caso não muda por causa desta função.** Nenhuma chamada a
`app/casos/maquina.py::transicionar` aparece neste módulo — a mesma
disciplina de `app/casos/progresso.py` (T-44/T-45), que documenta que
"disparar a transição de estado é trabalho de uma tarefa de orquestração
futura". A reabertura de `B7.05`–`B7.16` é compatível com o caso já estar
em `ACOMPANHAMENTO` (Bloco 11) e nunca exige `COLETA_DIRIGIDA` de novo —
o plano §7.1 mostra que o retorno a campo isolado (`AC-33`) permanece em
`ACOMPANHAMENTO`; o mesmo vale para a faixa (`AC-34`): reabrir não é
transicionar.

Direção de dependência: este módulo usa `app/casos/coleta_dirigida.py`
(mesma camada, `app/casos/`), `app/casos/progresso.py` (o tipo
`PendenciaObrigatoria`, para reaproveitar a mesma representação de
"pergunta pendente" já consumida pelo cliente HTMX) e `collection/*` —
nunca `engine.gates`/`engine.ciclo_mensal`/`engine.ordem` (a fronteira de
`tests/app_aluno/estatica/test_fronteira_import_engine.py`, T-06, permite
`engine.snapshot.SnapshotOrdem`, já importado por `coleta_dirigida.py`).

## `perguntas_pendentes_por_reabertura_informacao` (`T-85`, `RF-27`, `AC-33`)

`RESULTADO_ACAO_INFORMACAO = Sim` reabre **exclusivamente** o campo isolado
que faltava (ex.: `B5.B03`) — nunca a faixa inteira de um bloco, ao
contrário de `perguntas_pendentes_por_reabertura_renegociacao` acima. A
diferença de mecanismo entre as duas funções é o próprio conteúdo de
`AC-33` versus `AC-34`: renegociação reabre uma FAIXA declarada por
`registro.bloco` (fonte: o próprio arquivo YAML, ver acima); informação
reabre um ÚNICO campo, e esse campo não é "o Bloco 5 inteiro" nem uma
faixa — é a pergunta específica que ficou sem resposta e causou o
bloqueio do Gate 1.

**Lacuna de contrato adicional, distinta de `TIPO_ACAO` (`OQ-13`) — sem
Open Question existente que a cubra.** Ramificar por `TIPO_ACAO` (`T-84`,
`app/motor/acoes.py::tipo_acao_de`) resolve apenas "que a ação é do tipo
informação"; não resolve "qual pergunta reabrir". `engine.gates.
AcaoRequerida` publica só `DIVIDA_ID`, `descricao` (texto auditável, cujo
parsing é proibido desde `T-74`), `gate_origem` e `prioridade_excepcional`
— nenhum campo aponta qual `RegistroPergunta.ID` (`B5.B03` vs. `B5.D01A`,
os dois exemplos da própria `RF-27`) corresponde ao dado que bloqueou o
Gate 1. Inspecionado `engine/gates.py::aplicar_gate_1_informacao`: hoje a
função nem chega a instanciar uma `AcaoRequerida` no caso de bloqueio por
`VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` nem no de
`STATUS_DIVIDA = QUITADA_A_CONFIRMAR` — ambos os ramos devolvem
`acao=None` (ver `ResultadoGates.acao` no próprio arquivo). Isso é
consistente com a spec: a emissão de `AcaoRequerida` de tipo informação
pelo Gate 1 é `AC-47`, dependência externa ainda não implementada
(`T-90`). Revisadas `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15` (as Open Questions
que tratam de `AcaoRequerida`/`TIPO_ACAO`): nenhuma pergunta "qual campo
da dívida está pendente" — `OQ-10` é sobre identidade (`ACAO_ID`) e tipo
(`TIPO_ACAO`) da ação, não sobre qual pergunta reabrir dentro dela. Este
módulo, portanto, NÃO inventa um campo novo em `AcaoRequerida` nem
deriva o campo a reabrir por conta própria (violaria a mesma disciplina
de "nunca adivinhar o que o motor não publica" de `T-83`/`T-84`) — a
função abaixo declara o campo a reabrir como PARÂMETRO explícito, para
que o dia em que o motor publicar essa informação (em `AcaoRequerida` ou
em outro contrato) baste ao chamador extraí-la e passá-la adiante, sem
mudar a assinatura desta função nem seu comportamento.

**O que é testável e implementado hoje, independentemente da lacuna.**
Dado o `ID` da pergunta a reabrir (parâmetro explícito, nunca uma lista
codificada aqui) e o `DIVIDA_ID` da ação, a função devolve exatamente uma
`PendenciaObrigatoria` para aquele par — nenhuma outra pergunta do bloco
do registro é incluída. O valor anterior permanece gravado (mesma técnica
de leitura de `RespostasCaso`, nunca gravação, desta função vizinha) e o
estado do caso nunca muda (nenhuma importação de `app/casos/maquina.py`,
mesma auditoria estática de `T-80`).

REGRAS: `RF-27`, `AC-33`, `AC-34`
"""

from __future__ import annotations

from typing import Final

from app.casos.coleta_dirigida import dividas_para_bloco_7, perguntas_do_bloco_7
from app.casos.progresso import PendenciaObrigatoria
from collection.registro import RegistroPergunta
from collection.respostas import RespostasCaso
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-27", "AC-33", "AC-34")


def divida_elegivel_para_reabertura_renegociacao(
    snapshot: SnapshotOrdem, divida_id: str
) -> bool:
    """`divida_id` é "a dívida da ação" de renegociação quando, e somente
    quando, `dividas_para_bloco_7` (T-75 — Gate 3 + `RENEGOCIACAO_PENDENTE`,
    a MESMA técnica de distinção sem `TIPO_ACAO` documentada naquele
    módulo) a inclui. Nenhuma segunda leitura de `gate_origem`/
    `RENEGOCIACAO_PENDENTE` acontece aqui — reaproveita a função já
    testada de T-75, para que as duas nunca divirjam sobre "quem é
    candidata a renegociação"."""
    return divida_id in dividas_para_bloco_7(snapshot)


def perguntas_pendentes_por_reabertura_renegociacao(
    snapshot: SnapshotOrdem,
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    divida_id: str,
) -> tuple[PendenciaObrigatoria, ...]:
    """`AC-34` — reabrir a renegociação de `divida_id` torna pendentes
    EXATAMENTE as perguntas do Bloco 7 (`B7.05`–`B7.16`, por construção do
    dado — ver a nota do módulo) para aquela dívida.

    Devolve tupla VAZIA (nenhuma pendência de reabertura) quando
    `divida_id` não é candidata segundo o motor
    (`divida_elegivel_para_reabertura_renegociacao`) — reabrir nunca é
    decisão da aplicação sobre uma dívida que o motor não sinalizou.

    Quando elegível, TODA pergunta de `perguntas_do_bloco_7(registros)`
    entra na lista, pareada com `item_id=divida_id` — inclusive as que já
    têm valor gravado (`respostas.valor_no_item(...)` não é consultado
    para excluir nada aqui: essa é a diferença deliberada frente a
    `app/casos/progresso.py::pendencias_obrigatorias`, cujo critério é
    "em branco". Aqui o critério é "faz parte da faixa reaberta",
    independentemente de já ter resposta — é assim que o valor anterior
    permanece "gravado e visível como valor atual": nenhuma linha de
    `respostas` é tocada, e a pergunta ainda aparece com seu valor
    corrente para quem for exibi-la de novo, via
    `respostas.valor_no_item(divida_id, VARIAVEL_GRAVADA)`.

    Nenhuma pergunta anterior a `B7.05` é devolvida: `perguntas_do_bloco_7`
    só enxerga o que `collection/registros/bloco-07.yaml` declara com
    `bloco == 7`, e aquele arquivo não contém `B7.01`–`B7.04` (fora do
    escopo transcrito por T-18) — não há filtro adicional a fazer aqui
    para excluí-las, porque elas nunca chegam a existir no conjunto de
    entrada."""
    if not divida_elegivel_para_reabertura_renegociacao(snapshot, divida_id):
        return ()

    return tuple(
        PendenciaObrigatoria(ID=registro.ID, item_id=divida_id)
        for registro in perguntas_do_bloco_7(registros)
    )


# T-85: mensagem técnica (nunca exibida ao aluno), curta o bastante para não
# disparar o limiar de `AC-37`/`tests/app_aluno/estatica/test_sem_conteudo_
# de_questionario_no_codigo.py` (40 caracteres) — mesma disciplina de
# `_MENSAGEM_ACAO_ID_AUSENTE`/`_MENSAGEM_TIPO_ACAO_AUSENTE` (T-83/T-84). O
# detalhe completo (lacuna nova, sem OQ-NN) vive na docstring da exceção e
# da função, não nesta constante.
_MENSAGEM_CAMPO_INFORMACAO_INDETERMINAVEL: Final[str] = "campo indeterminável (T-85)"


class ErroCampoDeInformacaoIndeterminavel(Exception):
    """`T-85` — levantada por `campo_para_reabertura_informacao` quando o
    campo a reabrir é pedido a partir de uma `AcaoRequerida` REAL, sem que o
    chamador o informe explicitamente. Nenhuma `AcaoRequerida` publicada
    pelo motor hoje contém, em campo algum, qual `RegistroPergunta.ID`
    ficou pendente — nem `DIVIDA_ID`, nem `descricao` (cujo parsing é
    proibido, `T-74`), nem `gate_origem` dizem "foi `B5.B03`" ou "foi
    `B5.D01A`". Diferente de `TIPO_ACAO` (`OQ-13`) e `ACAO_ID` (`OQ-10`),
    esta lacuna NÃO tem Open Question registrada na spec `app-aluno`
    (revisadas `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`: nenhuma pergunta "qual
    campo da dívida está pendente dentro de uma ação de informação") — é
    uma lacuna nova, a registrar pelo especialista, não uma reafirmação de
    lacuna já conhecida.

    Consumidores DEVEM deixar esta exceção propagar (ou traduzi-la
    preservando a causa) — nunca capturá-la para cair de volta num campo
    do Bloco 5 escolhido por padrão."""


def campo_para_reabertura_informacao(acao: object) -> str:
    """`T-85` — leria, de uma `AcaoRequerida` REAL, qual `RegistroPergunta.
    ID` reabrir (`B5.B03`, `B5.D01A`, ...). Não existe, hoje, nenhum campo
    em `engine.gates.AcaoRequerida` nem em `ResultadoGates` que publique
    essa informação (ver a nota extensa do módulo) — por isso esta função
    SEMPRE levanta `ErroCampoDeInformacaoIndeterminavel` sobre qualquer
    `acao` recebida, nomeando a lacuna, em vez de adivinhar um `ID` fixo
    (o que inventaria dado onde `sdd.config.md` §4 exige `INFORMACAO_
    PENDENTE`, nunca uma estimativa silenciosa, `GAB-03`).

    Assinatura deliberadamente `acao: object` (não `AcaoRequerida`): esta
    função nunca lê nenhum atributo de `acao` (nem por `getattr`, ao
    contrário de `acao_id_de`/`tipo_acao_de`, T-83/T-84) porque não há
    NENHUM atributo candidato a ler — a lacuna não é "o campo existe com
    outro nome", é "o campo não existe em lugar nenhum do contrato
    atual". Tipar como `AcaoRequerida` sugeriria falsamente que a função
    tenta algo sobre o objeto antes de desistir."""
    raise ErroCampoDeInformacaoIndeterminavel(_MENSAGEM_CAMPO_INFORMACAO_INDETERMINAVEL)


def perguntas_pendentes_por_reabertura_informacao(
    id_pergunta: str,
    divida_id: str,
) -> tuple[PendenciaObrigatoria, ...]:
    """`AC-33` — reabrir o campo isolado `id_pergunta` (ex.: `"B5.B03"`)
    para `divida_id` torna pendente EXATAMENTE essa pergunta — nenhuma
    outra do bloco a que ela pertence é incluída, ao contrário de
    `perguntas_pendentes_por_reabertura_renegociacao` (que devolve a FAIXA
    inteira do Bloco 7). `id_pergunta` é sempre um PARÂMETRO explícito,
    nunca uma lista literal de `ID` neste módulo (terceiro critério de
    aceite): o chamador é quem sabe, pela ação recebida do motor, qual
    campo reabrir — hoje essa extração está bloqueada
    (`campo_para_reabertura_informacao`), mas a forma de PENDÊNCIA já é a
    definitiva e não muda quando a lacuna for resolvida.

    Não consulta `registros` nem valida que `id_pergunta` pertence ao
    Bloco 5: esta função é o mecanismo de "reabertura de campo isolado",
    aplicável a qualquer `RegistroPergunta.ID` que o chamador informe —
    `B5.B03` é o exemplo normativo de `RF-27`/`AC-33`, não uma restrição
    de tipo aqui. Validar que `id_pergunta` de fato existe no questionário
    carregado é responsabilidade de quem grava/exibe a pendência (mesma
    divisão de responsabilidade das demais funções deste módulo, que não
    reabrem nada sem que o motor primeiro sinalize).

    Como em `perguntas_pendentes_por_reabertura_renegociacao`: nenhuma
    linha de `respostas` é tocada (a função nem recebe `RespostasCaso`) —
    o valor anterior de `id_pergunta`, se houver, permanece gravado e
    visível para quem for exibir a pergunta de novo. Nenhuma chamada a
    `app/casos/maquina.py::transicionar` aparece neste módulo (auditado
    por `tests/app_aluno/test_reabertura.py::
    test_estado_do_caso_nao_muda_por_causa_da_reabertura`) — reabrir um
    campo isolado é compatível com o caso permanecer em `ACOMPANHAMENTO`
    durante toda a reabertura, nunca uma transição para `COLETA_INICIAL`
    nem para nenhum outro estado."""
    return (PendenciaObrigatoria(ID=id_pergunta, item_id=divida_id),)
