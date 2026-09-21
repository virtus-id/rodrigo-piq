"""Confirmação de quitação do Bloco 11 — `RF-29`, `AC-05`, `AC-30`, `AC-31`,
mais o vínculo por `ACAO_ID` (`RF-27`, `RF-33`, `AC-50`, T-83)
(`plans/app-aluno.plan.md` §4.4, T-82/T-83).

`B11.Q01`–`B11.Q06` (`collection/registros/bloco-11.yaml`, T-18) fecham o
ciclo de confirmação de uma ação de quitação: `B11.Q01 = Sim` marca
`STATUS_QUITACAO_REAL = QUITADA` e identifica o gatilho de recálculo
(`app/eventos/mapeamento.py::evento_recalculo_da_resposta`, T-81);
*"Acredito que sim, mas ainda preciso confirmar"* (`A_CONFIRMAR`) e "Ainda
não" (`NAO`) **não disparam nada** (`RF-29`, `AC-31`) — `evento_recalculo_
da_resposta` já devolve `None` para essas duas respostas por ausência
estrutural de entrada no dicionário (T-81), e este módulo apenas RESPEITA
esse `None`, sem reintroduzir um `if valor == "QUITADA"` paralelo.

Este módulo cobre três responsabilidades:

1. `perguntas_do_bloco_11_confirmacao_quitacao` — as seis perguntas
   `B11.Q01`..`B11.Q06`, na sequência declarada no PRÓPRIO registro (a ordem
   em que `collection/registros/bloco-11.yaml` as lista, T-18) — nenhuma
   ordem paralela codificada aqui, mesmo precedente de `perguntas_da_ficha`
   (`collection/repeticao.py`, RF-04) e de `perguntas_do_bloco_7`/`_8`
   (`app/casos/coleta_dirigida.py`, T-75/T-76).

2. `evento_da_resposta_b11_q01` — chama fina sobre `app/eventos/
   mapeamento.py::evento_recalculo_da_resposta` (T-81), fixando a
   `VARIAVEL_GRAVADA` de `B11.Q01` (`STATUS_QUITACAO_REAL`) num único lugar,
   para que a rota (`app/http/rotas_bloco11.py`) não precise conhecer esse
   nome de variável.

3. `acao_id_de` / `item_id_do_bloco_11` — a CHAVE de vínculo real da
   resposta do Bloco 11 (`ACAO_ID`, `T-83`, ver seção abaixo).

## A fronteira `DIVIDA_ID` vs. `ACAO_ID` (`AC-05` vs. `AC-50`/T-83).

`collection/registros/bloco-11.yaml` já declara `escopo_repeticao: ACAO_ID`
para `B11.Q01`–`B11.Q06` (T-18, `AC-50`) — o vínculo da resposta do Bloco 11
é por `ACAO_ID`, **nunca** por `DIVIDA_ID`. `AC-05` (a exibição do enunciado)
é sobre TEXTO, não sobre a chave de gravação: continua correto usar o
identificador do item corrente (hoje sempre `DIVIDA_ID`, na ausência de
`ACAO_ID` real) na interpolação de `[Dxxx]` — nenhuma mudança de `T-82` é
revertida aqui.

**T-83 é o ponto de virada.** `engine.gates.AcaoRequerida` (ver
`app/motor/acoes.py`, T-74, e a nota extensa em `app/casos/coleta_dirigida.py`
sobre a mesma fronteira) só tem `DIVIDA_ID`, `descricao`, `gate_origem` e
`prioridade_excepcional` — **não tem `ACAO_ID`** (`OQ-10`, dependência
externa do slug `motor-calculo` que bloqueia esta tarefa). `acao_id_de`
tenta ler `acao.ACAO_ID` de verdade — nunca usa `DIVIDA_ID` como
substituto — e, como o campo ainda não existe no contrato real, ela SEMPRE
levanta `ErroAcaoIdAusenteDoMotor` quando chamada com uma `AcaoRequerida`
produzida pelo motor hoje. Essa falha é o comportamento CORRETO e
intencional desta tarefa: "falhar ruidosamente na fronteira" (quarto
critério de aceite de `T-83`) significa exatamente isto — nomear o campo
ausente e apontar para a dependência externa, nunca inventar um
identificador (nem `DIVIDA_ID` como stand-in silencioso, nem um UUID
gerado aqui).

**Por que não existe hoje um tipo próprio "envelope com ACAO_ID opcional".**
Uma alternativa considerada e descartada: definir, nesta camada, uma
dataclass que "estende" `AcaoRequerida` com um `ACAO_ID` fabricado (por
exemplo, derivado de `DIVIDA_ID` ou de um contador local) apenas para o
código compilar e os testes passarem sem depender do motor. Isso violaria
diretamente o quarto critério de aceite: seria inventar o identificador que
a dependência externa (`motor-calculo`) ainda não publicou, e esconderia a
lacuna real atrás de uma aparência de sucesso. Por isso `acao_id_de` opera
sobre `AcaoRequerida` (o tipo real do motor) e falha; ela não tenta
"simular" um `ACAO_ID` a partir de dados que não o carregam. A prova de
`AC-50` com uma ação de fixture que TEM `ACAO_ID` (ex.: um objeto de teste
com esse atributo, sem tocar no tipo real do motor) é `T-89`
("Testar `AC-50` (ação sem dívida) sobre o vínculo por `ACAO_ID`") — tarefa
própria, dependente desta, que a spec já reconhece como testável hoje
independentemente das mudanças pendentes em `engine/`. Esta tarefa
(`T-83`) entrega a INTERFACE/contrato (`acao_id_de`,
`item_id_do_bloco_11`, `ErroAcaoIdAusenteDoMotor`) e prova, com dado real,
que ela nunca inventa substituto; `T-89` prova o caminho de sucesso com
fixture.

**Nenhum caminho de código exige `DIVIDA_ID` (segundo critério de
aceite).** `item_id_do_bloco_11` só lê `acao.ACAO_ID` — nunca lê nem exige
`acao.DIVIDA_ID` em nenhum ramo, e o tipo de `Resposta.item_id`
(`collection/respostas.py`) já é `str | None`, sem amarra a um dos dois
identificadores (T-82 já documentava isso). Uma ação sem `DIVIDA_ID`
associado (a ação de economia, `OQ-15`, quando existir) segue exatamente o
mesmo caminho: `item_id_do_bloco_11` lê `ACAO_ID`, ponto — a presença ou
ausência de `DIVIDA_ID` na `AcaoRequerida` nunca é consultada por esta
função.

## `T-86` — o disparo real do recálculo (`disparar_recalculo`)

`T-82` parava um passo antes de acionar o motor: `evento_da_resposta_b11_q01`
IDENTIFICAVA o evento, sem disparar nada. `T-86` é quem CONSOME esse evento e
constrói o recálculo de fato — `disparar_recalculo`, abaixo.

**Sem segunda via de invocação do motor.** `disparar_recalculo` NUNCA chama
`engine.motor.calcular_plano` diretamente: ela monta `app.motor.executor.
ParametrosDoCalculo` com `anterior`/`evento`/`motivo` preenchidos e delega a
`executar_calculo`/`executar_calculo_async` — o MESMO executor que o Bloco 6
usa (`T-54`/`T-55`/`T-56`). Não existe, neste módulo, nenhum `import` de
`engine.motor` nem uma segunda função que reimplemente os quatro passos do
executor — a única diferença entre um cálculo do Bloco 6 e um recálculo do
Bloco 11 é os TRÊS CAMPOS que `ParametrosDoCalculo` já previa desde `T-55`
(`anterior`, `evento`, `motivo`), nunca um caminho de código paralelo.

**`anterior` — o snapshot corrente da cadeia (`AC-30`).** `disparar_
recalculo` busca o snapshot mais recente do caso via `RepositorioSnapshots.
historico(caso.snapshot_raiz_id)` (último elemento — mesma leitura de
`app/revisao/fila.py::listar_fila_de_revisao`, nunca uma consulta paralela)
e o passa como `anterior` ao executor. `engine.snapshot.montar_SnapshotOrdem`
(consumida por `calcular_plano`, dentro do executor) já garante `versao =
anterior.versao + 1` e `snapshot_anterior_id = anterior.SNAPSHOT_ID` — esta
função não recalcula nem reimplementa esse encadeamento, só fornece o
`anterior` correto. O snapshot anterior nunca é tocado nem substituído
(`RepositorioSnapshots.anexar` é append-only, `engine/portas.py`): ele
permanece íntegro e recuperável via `historico`, exatamente como antes do
recálculo.

**Transição `ACOMPANHAMENTO → CALCULANDO` (gatilho `recalcula`).** A mesma
tabela declarada desde `T-33` (`app/casos/maquina.py::TABELA_TRANSICOES`) —
`disparar_recalculo` chama `transicionar(ACOMPANHAMENTO, CALCULANDO)` (que
recusa com `ErroTransicaoNaoDeclarada` se o caso não estiver de fato em
`ACOMPANHAMENTO`) e só então persiste a transição via `RepositorioCasos.
transicionar_estado_se` — o mesmo padrão de concorrência de `app/http/
rotas_calculo.py::disparar_calculo` (T-56): a segunda chamada concorrente,
ao encontrar o caso já fora de `ACOMPANHAMENTO`, recebe `None` e não agenda
uma segunda execução.

**`AC-26`/`EC-11` são garantias que esta função HERDA, nunca reimplementa.**
O snapshot de recálculo entra na fila de revisão pelo MESMO mecanismo de
qualquer outro (`app/revisao/fila.py::entra_na_fila_de_revisao`/
`listar_fila_de_revisao`): a fila é uma CONSULTA sobre `Caso.estado ==
AGUARDANDO_REVISAO` e o snapshot mais recente do histórico — não distingue
snapshot de primeiro cálculo de snapshot de recálculo, e esta função não
introduz nenhuma lógica nova de fila. `EC-11` (evento com `hash_inputs`
idêntico ainda versiona) é garantia do MOTOR (`engine/motor.py::
calcular_plano` sempre versiona quando `evento is not None`, ver a nota da
docstring daquele módulo) — `disparar_recalculo` apenas REPASSA `evento` ao
executor sem NUNCA comparar `hash_inputs` contra o `anterior` para decidir
se "vale a pena" chamar o motor: a chamada ao executor ocorre sempre que
esta função é invocada com um evento não-`None`, nenhuma lógica de atalho.

Direção de dependência: este módulo importa de `collection.registro`,
`collection.repeticao`, `app.eventos.mapeamento`, `engine.gates`
(`AcaoRequerida`, liberado por `AC-41`), `app.casos.maquina`, `app.motor.
executor` (o MESMO executor do Bloco 6, `T-54`), `persistencia.app_aluno.
casos::RepositorioCasos` (o `Protocol`, mesmo tipo que `app/http/
rotas_calculo.py` já injeta no executor — reaproveitado aqui em vez de
duplicado num `Protocol` próprio, já que `ParametrosDoCalculo.repositorio_
casos` exige exatamente esse tipo) e `persistencia.app_aluno.eventos::
RepositorioEventosCaso` (T-87, abaixo) — nunca `engine.motor` diretamente.

## `T-87` — impedir que alteração cadastral dispare recálculo (`AC-35`)

`T-81` já torna `AC-35` uma garantia ESTRUTURAL: `evento_recalculo_da_
resposta` devolve `None` para qualquer alteração cadastral, porque o enum
`EVENTO_RECALCULO` não tem (e não pode ter) um membro para isso. O que
faltava, e é o que esta tarefa entrega, é a ORQUESTRAÇÃO que conecta os três
passos (gravar resposta → identificar evento → talvez disparar recálculo)
sem NUNCA fabricar um evento genérico só para "ter algo para disparar":

- `processar_resposta_bloco_11` é o ÚNICO lugar deste módulo que decide se
  `disparar_recalculo`/`disparar_recalculo_async` é chamada a partir de uma
  resposta do Bloco 11. Ela primeiro chama `evento_da_resposta_b11_q01`
  (T-82, que por sua vez chama `app.eventos.mapeamento.evento_recalculo_da_
  resposta`, T-81) e só invoca o executor SE o resultado não for `None`. Não
  existe, neste módulo nem em nenhum outro desta feature, um segundo caminho
  que construa um `EVENTO_RECALCULO` a partir de uma resposta — a auditoria
  (`tests/app_aluno/estatica/test_mapeamento_eventos_ac_35.py`, T-81, mais o
  teste desta tarefa) confirma que `evento_recalculo_da_resposta` é o único
  ponto de construção desse enum a partir de uma resposta em todo `app/`.
- Quando o evento é `None` (alteração cadastral, `NAO`, `A_CONFIRMAR`, ou
  qualquer pergunta do bloco que não seja `B11.Q01`), `processar_resposta_
  bloco_11` NÃO chama `disparar_recalculo` — ela chama `registrar_alteracao_
  cadastral`, que grava um evento na TRILHA do caso (`app_aluno.eventos_
  caso`, T-21) sem tocar `estado` nem `Caso.snapshot_raiz_id`/
  `snapshot_liberado_id`: nenhuma transição, nenhum snapshot novo.

`registrar_alteracao_cadastral` é a peça de trilha que faltava: até esta
tarefa, `app_aluno.eventos_caso` (T-21) não tinha nenhum repositório que a
usasse (confirmado por busca no repositório inteiro). `persistencia.app_
aluno.eventos::RepositorioEventosCaso` (T-87) é o repositório mínimo — só
`registrar`/`listar_do_caso`, mesmo padrão dos outros três repositórios desta
feature — e esta função é a ÚNICA deste módulo que o chama.

REGRAS: `RF-01`, `RF-19`, `RF-27`, `RF-28`, `RF-29`, `RF-33`, `AC-05`,
`AC-26`, `AC-30`, `AC-31`, `AC-35`, `AC-50`, `EC-11`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Final

from app.casos.maquina import ESTADO_CASO, Caso
from app.casos.progresso import transicionar_e_registrar
from app.eventos.mapeamento import (
    VARIAVEL_STATUS_QUITACAO_REAL,
    evento_recalculo_da_resposta,
)
from app.motor.executor import ParametrosDoCalculo, executar_calculo, executar_calculo_async
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.repeticao import perguntas_da_ficha
from engine.estado import EstadoFinanceiro
from engine.gates import AcaoRequerida
from engine.portas import FonteParametros, RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from engine.tipos import EVENTO_RECALCULO
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.eventos import EventoCaso, RepositorioEventosCaso

REGRAS: Final[tuple[str, ...]] = (
    "RF-01",
    "RF-19",
    "RF-27",
    "RF-28",
    "RF-29",
    "RF-33",
    "AC-05",
    "AC-26",
    "AC-30",
    "AC-31",
    "AC-35",
    "AC-50",
    "EC-11",
)

# T-83: mensagem técnica (nunca exibida ao aluno) que nomeia a dependência
# externa bloqueada — curta o bastante para não disparar o limiar de
# `AC-37`/`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_
# codigo.py` (strings de conteúdo de questionário, não desta tarefa). O
# detalhe completo (motor-calculo, OQ-10) vive na docstring de
# `ErroAcaoIdAusenteDoMotor` e do módulo, não nesta constante.
_MENSAGEM_ACAO_ID_AUSENTE: Final[str] = "ACAO_ID ausente (T-83, OQ-10)"

# Sentinela distinto de qualquer ACAO_ID real possível — usado só para
# distinguir "atributo ausente" de "atributo presente e igual a None/''" em
# `getattr`, sem depender de `hasattr` (que engoliria qualquer AttributeError
# levantado DENTRO de uma property, mascarando um erro diferente do que esta
# função quer relatar).
_ACAO_ID_AUSENTE: Final[object] = object()

_BLOCO_ACOMPANHAMENTO: Final[int] = 11

# As seis perguntas desta tarefa, pelo próprio `ID` do registro (T-18) — usado
# só como FILTRO de pertencimento, nunca como fonte de ordem: a ordem devolvida
# é a de `registros` (a ordem de carga do YAML), não a desta tupla.
_IDS_CONFIRMACAO_QUITACAO: Final[frozenset[str]] = frozenset(
    {"B11.Q01", "B11.Q02", "B11.Q03", "B11.Q04", "B11.Q04A", "B11.Q05", "B11.Q06"}
)


def perguntas_do_bloco_11_confirmacao_quitacao(
    registros: tuple[RegistroPergunta, ...],
) -> tuple[RegistroPergunta, ...]:
    """`B11.Q01`–`B11.Q06` (mais `B11.Q04A`, condicional a `B11.Q04`), na
    SEQUÊNCIA em que `registros` as lista — a ordem de carga do YAML
    (`collection/carga.py`, T-16) é a sequência declarada no registro; este
    módulo nunca reordena por conta própria. Reaproveita `perguntas_da_ficha`
    (`collection/repeticao.py`, RF-04) para restringir ao escopo `ACAO_ID`
    (`AC-50`) e depois filtra pelo `ID` de cada pergunta desta tarefa — sem
    duplicar a lista de perguntas de outra ficha por `ACAO_ID` que não seja
    de confirmação de quitação (ex.: `B11.01`, `B11.03-*`)."""
    da_ficha_acao = perguntas_da_ficha(registros, EscopoRepeticao.ACAO_ID)
    return tuple(
        registro
        for registro in da_ficha_acao
        if registro.bloco == _BLOCO_ACOMPANHAMENTO and registro.ID in _IDS_CONFIRMACAO_QUITACAO
    )


def evento_da_resposta_b11_q01(valor_interno: str) -> EVENTO_RECALCULO | None:
    """`AC-30`/`AC-31` — identifica o `EVENTO_RECALCULO` correspondente à
    resposta de `B11.Q01` (`STATUS_QUITACAO_REAL`), ou `None` quando a
    resposta não dispara nada (`NAO`, `A_CONFIRMAR`).

    Chamada fina sobre `app/eventos/mapeamento.py::evento_recalculo_da_
    resposta` (T-81) fixando a `VARIAVEL_GRAVADA` de `B11.Q01` — a rota
    (`app/http/rotas_bloco11.py`) chama esta função em vez de conhecer o
    nome `STATUS_QUITACAO_REAL` diretamente. NÃO dispara o executor do
    recálculo (`T-86`, ainda não implementada) — apenas identifica o
    evento, deixando-o pronto para o consumidor futuro (ver nota do módulo
    sobre a fronteira com `T-86`)."""
    return evento_recalculo_da_resposta(VARIAVEL_STATUS_QUITACAO_REAL, valor_interno)


class ErroAcaoIdAusenteDoMotor(Exception):
    """`T-83` — levantada quando `acao_id_de` é chamada com uma
    `AcaoRequerida` que não publica `ACAO_ID` (o caso de TODA `AcaoRequerida`
    produzida pelo motor hoje: `OQ-10`, dependência externa do slug
    `motor-calculo` ainda não entregue). Esta exceção é a fronteira ruidosa
    exigida pelo quarto critério de aceite de `T-83` — o módulo nunca
    resolve a ausência usando `DIVIDA_ID` como substituto silencioso, nem
    fabricando qualquer outro identificador.

    Consumidores desta função DEVEM deixar esta exceção propagar (ou
    traduzi-la para um erro de camada superior que preserve a causa) — nunca
    capturá-la para cair de volta em `DIVIDA_ID`."""


def acao_id_de(acao: AcaoRequerida) -> str:
    """`RF-27`, `RF-33`, `AC-50` — lê `ACAO_ID` de uma `AcaoRequerida` REAL,
    e só isso. Nunca lê `acao.DIVIDA_ID` como plano B, nunca gera um
    identificador próprio: se `ACAO_ID` não existir no objeto recebido,
    levanta `ErroAcaoIdAusenteDoMotor` nomeando a dependência externa
    bloqueada (`OQ-10`, ver a nota extensa do módulo sobre por que nenhum
    tipo "envelope" foi criado para contornar esta falta).

    Usa `getattr` com sentinela (nunca `hasattr`) para distinguir "o campo
    não existe no objeto" de "o campo existe e o acesso a ele levantou uma
    outra exceção" — esta função relata exclusivamente a primeira situação;
    qualquer outra exceção de acesso propaga tal como foi levantada, sem
    ser mascarada por um `except` amplo."""
    valor = getattr(acao, "ACAO_ID", _ACAO_ID_AUSENTE)
    if valor is _ACAO_ID_AUSENTE:
        raise ErroAcaoIdAusenteDoMotor(_MENSAGEM_ACAO_ID_AUSENTE)
    if not isinstance(valor, str):
        # Defensivo: se o campo existir mas não for `str`, o contrato
        # publicado pelo motor mudou de forma incompatível com o que esta
        # tarefa espera — falhar ruidosamente é preferível a silenciosamente
        # converter um tipo que pode não ser um identificador de verdade.
        # Mensagem curta (limiar de AC-37, ver nota da constante acima); o
        # tipo recebido vai à parte, sem compor uma única string longa.
        raise ErroAcaoIdAusenteDoMotor(f"{_MENSAGEM_ACAO_ID_AUSENTE}: tipo {type(valor).__name__}")
    return valor


def item_id_do_bloco_11(acao: AcaoRequerida) -> str:
    """`AC-50` — a chave de vínculo (`item_id`) da `Resposta` do Bloco 11 é
    o `ACAO_ID` da ação, **nunca** o `DIVIDA_ID`. Chamada fina sobre
    `acao_id_de`: esta função não lê nenhum outro campo de `acao` (nem
    `DIVIDA_ID`, nem `descricao`, nem `gate_origem`) — nenhum caminho aqui
    exige `DIVIDA_ID` presente para decidir o `item_id` (segundo critério de
    aceite de `T-83`), porque `DIVIDA_ID` sequer é consultado. Ação sem
    dívida associada (a futura ação de economia, `OQ-15`) segue exatamente
    o mesmo caminho de código de qualquer outra ação."""
    return acao_id_de(acao)


# ---------------------------------------------------------------------------
# `T-86` — disparo real do recálculo (`anterior`, `evento`, `motivo`), sempre
# através do MESMO executor do Bloco 6. Ver a nota extensa do módulo sobre
# por que não existe segunda via de invocação do motor.
# ---------------------------------------------------------------------------


class ErroRecalculoRecusado(Exception):
    """Levantado por `disparar_recalculo` quando o caso não está de fato em
    `ACOMPANHAMENTO` no momento da chamada — ou porque já mudou de estado
    (disparo concorrente que já venceu a corrida), ou porque o chamador
    invocou esta função fora do fluxo previsto (`AC-30`/`RF-28`: só quitação
    confirmada ou evento material, sempre a partir de `ACOMPANHAMENTO`).
    Nomeia `CASO_ID`, nunca falha silenciosamente nem agenda uma segunda
    execução.

    Mensagem montada por `join` de pedaços curtos, nunca por concatenação de
    literais adjacentes — mesma disciplina de `app/revisao/fila.py::
    ErroRevisaoJaDecidida` (`AC-37`/T-08: cada elemento fica sob o limiar de
    40 caracteres de `tests/app_aluno/estatica/test_sem_conteudo_de_
    questionario_no_codigo.py`); nenhum é enunciado de pergunta, só nomes
    técnicos e IDs normativos desta feature."""

    def __init__(self, caso_id: str) -> None:
        partes = (
            f"CASO_ID={caso_id!r}",
            "recálculo recusado",
            "esperado=ACOMPANHAMENTO",
            "RF-28/AC-30",
        )
        super().__init__(" | ".join(partes))


def _snapshot_corrente(
    caso: Caso, repositorio_snapshots: RepositorioSnapshots
) -> SnapshotOrdem | None:
    """`AC-30` — o `anterior` da cadeia: o último elemento do histórico do
    caso (mesma leitura de `app/revisao/fila.py::listar_fila_de_revisao`,
    nunca uma consulta paralela). `None` quando o caso ainda não tem nenhum
    snapshot (`snapshot_raiz_id` ausente ou histórico vazio) — não deveria
    ocorrer para um caso que já passou por `ACOMPANHAMENTO` (que pressupõe
    ao menos um snapshot liberado antes), mas esta função não presume isso."""
    if caso.snapshot_raiz_id is None:
        return None
    historico = repositorio_snapshots.historico(caso.snapshot_raiz_id)
    return historico[-1] if historico else None


def disparar_recalculo(
    *,
    estado: EstadoFinanceiro,
    caso: Caso,
    evento: EVENTO_RECALCULO,
    fonte_parametros: FonteParametros,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasos,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_versao: str,
    motivo: str = "",
) -> SnapshotOrdem:
    """`RF-01`, `RF-19`, `RF-28`, `AC-26`, `AC-30`, `EC-11` — consome o
    `EVENTO_RECALCULO` já identificado (`evento_da_resposta_b11_q01`, T-82,
    ou um evento material externo, `T-87`/`T-88`) e dispara o recálculo real
    do caso, **sempre pelo mesmo executor do Bloco 6** (`app/motor/
    executor.py::executar_calculo`, T-54/T-55) — nunca uma segunda via de
    invocação de `engine.motor.calcular_plano`.

    Os quatro passos:

    1. Busca o `anterior` — o snapshot mais recente da cadeia do caso
       (`_snapshot_corrente`, acima).
    2. Transiciona `ACOMPANHAMENTO → CALCULANDO` (gatilho `recalcula`,
       `app/casos/maquina.py::TABELA_TRANSICOES`, declarada desde `T-33`):
       primeiro validada contra a MÁQUINA (`transicionar`, que recusa com
       `ErroTransicaoNaoDeclarada` se `caso.estado` não for
       `ACOMPANHAMENTO`), depois persistida condicionalmente
       (`transicionar_estado_se`, mesma trava de concorrência de `T-56`) —
       se a condição não vale mais (disparo concorrente que já venceu),
       `ErroRecalculoRecusado` é levantada, e NENHUM cálculo é tentado.
    3. Monta `ParametrosDoCalculo` com `anterior`, `evento` e `motivo`
       preenchidos — os três campos que `T-55` já previa na assinatura do
       executor.
    4. Chama `executar_calculo` (o MESMO executor do Bloco 6) — que por sua
       vez chama `calcular_plano(..., anterior=..., evento=...,
       motivo=...)` exatamente uma vez e anexa o snapshot antes de devolver
       (`AC-12`, herdado de `T-54`).

    `AC-26` (entra na fila como qualquer outro) e `EC-11` (evento com
    `hash_inputs` idêntico ainda versiona) são garantias que esta função
    HERDA sem reimplementar — ver a nota extensa do módulo. Em particular,
    esta função NUNCA compara `hash_inputs` do `anterior` contra nada antes
    de chamar o executor: o evento, sozinho, já é suficiente para disparar o
    recálculo (a decisão de "vale a pena" é do MOTOR, `engine/eventos.py::
    avaliar_gatilho_recalculo`, nunca desta camada — Lei nº 3)."""
    anterior = _snapshot_corrente(caso, repositorio_snapshots)

    # Passo 2: validada pela máquina ANTES de qualquer tentativa de
    # persistir — nunca uma transição "forçada" fora da tabela declarada.
    # `transicionar_e_registrar` (`T-91`, `RF-31`/`AC-40`) faz a validação, a
    # persistência condicional E o registro do evento `recalcula` na trilha
    # num único passo.
    caso_calculando = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso.CASO_ID,
        de=ESTADO_CASO.ACOMPANHAMENTO,
        para=ESTADO_CASO.CALCULANDO,
    )
    if caso_calculando is None:
        raise ErroRecalculoRecusado(caso.CASO_ID)

    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso.CASO_ID,
        parametros_versao=parametros_versao,
        estado_anterior_do_caso=ESTADO_CASO.ACOMPANHAMENTO,
        anterior=anterior,
        evento=evento,
        motivo=motivo,
    )

    # Passos 3-4: o MESMO executor do Bloco 6 — nenhuma segunda via de
    # invocação de engine.motor.calcular_plano.
    return executar_calculo(estado, insumos)


async def disparar_recalculo_async(
    *,
    estado: EstadoFinanceiro,
    caso: Caso,
    evento: EVENTO_RECALCULO,
    fonte_parametros: FonteParametros,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasos,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_versao: str,
    motivo: str = "",
) -> SnapshotOrdem:
    """A mesma orquestração de `disparar_recalculo`, mas delegando a
    `executar_calculo_async` (T-54) em vez de `executar_calculo` — para um
    chamador HTTP que não deve bloquear o event loop durante o recálculo,
    mesmo padrão de `app/http/rotas_calculo.py::disparar_calculo` para o
    Bloco 6. Repete os passos 1-2 aqui (em vez de compor sobre
    `disparar_recalculo`) porque a única diferença é qual das duas funções
    do executor é chamada no passo final — nenhuma lógica de negócio nova."""
    anterior = _snapshot_corrente(caso, repositorio_snapshots)

    caso_calculando = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso.CASO_ID,
        de=ESTADO_CASO.ACOMPANHAMENTO,
        para=ESTADO_CASO.CALCULANDO,
    )
    if caso_calculando is None:
        raise ErroRecalculoRecusado(caso.CASO_ID)

    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso.CASO_ID,
        parametros_versao=parametros_versao,
        estado_anterior_do_caso=ESTADO_CASO.ACOMPANHAMENTO,
        anterior=anterior,
        evento=evento,
        motivo=motivo,
    )

    return await executar_calculo_async(estado, insumos)


# ---------------------------------------------------------------------------
# `T-87` — trilha de alteração cadastral (`AC-35`) e a orquestração completa
# que impede fabricar um `EVENTO_RECALCULO` genérico. Ver a nota extensa do
# módulo (seção "T-87") para o raciocínio completo.
# ---------------------------------------------------------------------------

# `tipo_evento` gravado em `app_aluno.eventos_caso` para uma alteração
# cadastral — nomeia o FATO (correção de rótulo/nome), nunca um gatilho da
# tabela de transições (`app/casos/maquina.py::TABELA_TRANSICOES`): não
# existe, e não pode existir, uma `Transicao` com este nome, porque este
# evento nunca transiciona o caso (mensagem curta, sob o limiar de `AC-37`).
_TIPO_EVENTO_ALTERACAO_CADASTRAL: Final[str] = "alteracao_cadastral"


def registrar_alteracao_cadastral(
    *,
    caso: Caso,
    id_pergunta: str,
    repositorio_eventos: RepositorioEventosCaso,
    agora: datetime | None = None,
) -> None:
    """`AC-35` — registra, na TRILHA do caso (`app_aluno.eventos_caso`,
    T-21), que uma correção de nome/rótulo foi respondida. Esta função NUNCA
    muda `estado`: `estado_de`/`estado_para` do evento gravado são sempre
    `None` (não há origem nem destino, porque não há transição), e nenhuma
    chamada aqui toca `app.casos.maquina.transicionar` nem
    `RepositorioCasos.transicionar_estado*` — apenas um `INSERT` na trilha,
    o mesmo repositório mínimo que qualquer outro evento observável desta
    feature usaria.

    `id_pergunta` vai para `detalhe` como contexto técnico (o `ID` do
    registro, ex.: `B5.NOME01` — nunca o enunciado nem o valor respondido,
    que já estão persistidos por `RepositorioRespostas`; esta trilha não
    duplica o dado da resposta, só nomeia o fato de que uma correção
    cadastral ocorreu)."""
    instante = agora if agora is not None else datetime.now(UTC)
    repositorio_eventos.registrar(
        EventoCaso(
            evento_id=f"EVENTO_{uuid.uuid4().hex}",
            CASO_ID=caso.CASO_ID,
            tipo_evento=_TIPO_EVENTO_ALTERACAO_CADASTRAL,
            estado_de=None,
            estado_para=None,
            detalhe=id_pergunta,
            ocorrido_em=instante,
        )
    )


def processar_resposta_bloco_11(
    *,
    id_pergunta: str,
    variavel_gravada: str,
    valor_interno: str | None,
    caso: Caso,
    estado: EstadoFinanceiro,
    fonte_parametros: FonteParametros,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasos,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_versao: str,
    motivo: str = "",
) -> SnapshotOrdem | None:
    """`RF-28`, `AC-35` — a orquestração completa desta tarefa: gravar a
    resposta já ocorreu no CHAMADOR (`app/http/rotas_bloco11.py`, antes de
    invocar esta função — esta função não grava `Resposta`, só decide o que
    acontece DEPOIS da gravação); aqui só restam os passos "identificar
    evento" e "talvez disparar recálculo".

    1. Identifica o evento pela MESMA função que a rota já usa
       (`evento_da_resposta_b11_q01`, T-82, sobre `app.eventos.mapeamento.
       evento_recalculo_da_resposta`, T-81) — só quando `variavel_gravada`
       é `STATUS_QUITACAO_REAL` (a única variável do Bloco 11 que carrega um
       `valor_interno` capaz de produzir um evento, ver `app/eventos/
       mapeamento.py`); para qualquer outra variável (as demais perguntas do
       bloco, incluindo alteração cadastral fora do Bloco 11), o evento é
       `None` sem sequer chamar aquela função — nada aqui CONSTRÓI um
       `EVENTO_RECALCULO` por conta própria; o único caminho de construção
       continua sendo `app.eventos.mapeamento.evento_recalculo_da_resposta`.
    2. Evento não-`None` → `disparar_recalculo` (T-86), que por sua vez é o
       ÚNICO caminho de invocação do motor. Devolve o `SnapshotOrdem` novo.
    3. Evento `None` → `registrar_alteracao_cadastral` (acima): grava a
       trilha, sem transição de estado, sem snapshot novo. Devolve `None`.

    Nunca os dois passos 2 e 3 ocorrem juntos: um evento não-`None` sempre
    dispara o recálculo (nunca também registra "alteração cadastral"); um
    evento `None` sempre registra a trilha (nunca dispara o executor)."""
    evento = (
        evento_da_resposta_b11_q01(valor_interno)
        if variavel_gravada == VARIAVEL_STATUS_QUITACAO_REAL and valor_interno is not None
        else None
    )
    if evento is not None:
        return disparar_recalculo(
            estado=estado,
            caso=caso,
            evento=evento,
            fonte_parametros=fonte_parametros,
            repositorio_snapshots=repositorio_snapshots,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            parametros_versao=parametros_versao,
            motivo=motivo,
        )

    registrar_alteracao_cadastral(
        caso=caso, id_pergunta=id_pergunta, repositorio_eventos=repositorio_eventos
    )
    return None


async def processar_resposta_bloco_11_async(
    *,
    id_pergunta: str,
    variavel_gravada: str,
    valor_interno: str | None,
    caso: Caso,
    estado: EstadoFinanceiro,
    fonte_parametros: FonteParametros,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_casos: RepositorioCasos,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_versao: str,
    motivo: str = "",
) -> SnapshotOrdem | None:
    """A mesma orquestração de `processar_resposta_bloco_11`, delegando a
    `disparar_recalculo_async` (T-86) em vez de `disparar_recalculo` — para
    um chamador HTTP que não deve bloquear o event loop, mesmo padrão de
    `disparar_recalculo`/`disparar_recalculo_async` acima."""
    evento = (
        evento_da_resposta_b11_q01(valor_interno)
        if variavel_gravada == VARIAVEL_STATUS_QUITACAO_REAL and valor_interno is not None
        else None
    )
    if evento is not None:
        return await disparar_recalculo_async(
            estado=estado,
            caso=caso,
            evento=evento,
            fonte_parametros=fonte_parametros,
            repositorio_snapshots=repositorio_snapshots,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            parametros_versao=parametros_versao,
            motivo=motivo,
        )

    registrar_alteracao_cadastral(
        caso=caso, id_pergunta=id_pergunta, repositorio_eventos=repositorio_eventos
    )
    return None
