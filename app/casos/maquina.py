"""Máquina de estados do caso — `RF-01`, `AC-33`, `AC-34` (plano §4.3, §7.1).

**Este módulo é a fonte canônica de `ESTADO_CASO` e `Caso`.** A tabela
`persistencia/app_aluno/casos.py` (T-23) originalmente definiu esses dois
tipos de forma provisória, documentando explicitamente que "quando T-33
implementar `app/casos/maquina.py`, ela IMPORTA `ESTADO_CASO`/`Caso` deste
módulo — nunca os redefine". Na prática a direção correta é a INVERSA da
descrita naquele comentário: a máquina de estados é uma regra de domínio
(`app/`), e a persistência é infraestrutura (`persistencia/`) — infraestrutura
importa de domínio, nunca o contrário (mesma Lei nº 3 do backlog: `app/`
importa de `persistencia/`, a recíproca nunca ocorre; aqui o mesmo princípio
vale internamente a `app/` vs. `persistencia/app_aluno/`). Por isso `ESTADO_CASO`
e `Caso` nascem AQUI, e `persistencia/app_aluno/casos.py` foi ajustado (nesta
mesma tarefa) para importar os dois daqui em vez de os duplicar — ver o
comentário atualizado naquele módulo.

`ESTADO_CASO` tem exatamente os doze membros do plano §4.3, nomeados
caractere por caractere. **Reabertura de pergunta não é estado**: o plano
§7.1 é explícito — "reabriu B5.B03" não multiplica estados; a pendência mora
na PERGUNTA (`AC-33`, `AC-34`), o estado do caso só diz em que fase ele está.
Por isso não existe (e nunca deve existir) um membro `REABERTO` ou similar.

**A tabela de transições é total sobre o domínio.** Todo par `(de, para)` é
uma decisão explícita: ou está na tabela (permitido, com gatilho nomeado e
guarda opcional), ou `transicionar` recusa com `ErroTransicaoNaoDeclarada`
nomeando origem e destino. Nunca há undefined behavior: não existe "par não
coberto" silenciosamente tolerado.

**`ERRO_DE_CALCULO` retorna a um dos quatro estados de origem de `CALCULANDO`
(`EC-06`), nunca a um destino fixo único.** O plano §7.1 desenha a seta de
retorno como "volta ao estado anterior" — e `CALCULANDO` é alcançável a
partir de `COLETA_INICIAL`, `COLETA_DIRIGIDA`, `CONFIRMACAO_ATAQUE` e
`ACOMPANHAMENTO` (as quatro origens do recálculo). Modelar isso como uma
única transição fixa inventaria um destino que o plano não fixa; em vez
disso, a tabela declara as QUATRO transições possíveis de `ERRO_DE_CALCULO`
(uma para cada estado de origem de `CALCULANDO`), todas com o mesmo gatilho
nomeado (`operador_retoma_apos_erro`) e a mesma guarda textual (`EC-06`) —
o chamador (fora desta tarefa) escolhe qual delas invocar, mas TODAS e
SOMENTE essas quatro são declaradas; qualquer outro destino a partir de
`ERRO_DE_CALCULO` é recusado.

**`REPROVADO_EM_REVISAO` não tem transição de saída declarada nesta
máquina.** O plano §7.1 diz que a reprovação vai para "tratamento do
operador" sem desenhar seta de volta — `EC-12` confirma que o snapshot
permanece intacto e o caso aguarda o operador fora do fluxo desta máquina.
Nenhuma transição de `REPROVADO_EM_REVISAO` é declarada; qualquer tentativa
é recusada como não declarada, até que uma tarefa futura, se necessário,
declare explicitamente o que o operador faz a partir daqui.

Direção de dependência: este módulo usa só `dataclasses`/`enum`/stdlib —
nunca `engine.gates`, `engine.ciclo_mensal` ou qualquer módulo interno do
motor (a fronteira de `tests/app_aluno/estatica/test_fronteira_import_
engine.py` não é tocada por este módulo).

**Guarda "sem consentimento, nenhuma resposta é gravada" (`RF-30`, `AC-39`,
T-36), no final do módulo.** `ESTADOS_QUE_PERMITEM_RESPOSTA` e
`exigir_estado_permite_resposta` são a peça que faltava além da topologia:
a tabela acima já torna `CADASTRADO → COLETA_INICIAL` impossível de existir
como transição direta, mas isso só impede pular consentimento SE todo
caminho de gravação de resposta também consultar o estado do caso antes de
persistir — é isso que a guarda formaliza, para que a checagem viva aqui
(domínio) e seja chamada pelo adaptador de persistência, nunca reimplementada
por rota.

REGRAS: `RF-01`, `AC-33`, `AC-34`, `RF-30`, `AC-39`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Final

REGRAS: Final[tuple[str, ...]] = ("RF-01", "AC-33", "AC-34", "RF-30", "AC-39")


class ESTADO_CASO(Enum):
    """Os doze estados do plano §4.3 — nomes caractere por caractere."""

    CADASTRADO = "CADASTRADO"
    CONSENTIMENTO_REGISTRADO = "CONSENTIMENTO_REGISTRADO"
    COLETA_INICIAL = "COLETA_INICIAL"
    CALCULANDO = "CALCULANDO"
    ERRO_DE_CALCULO = "ERRO_DE_CALCULO"
    AGUARDANDO_REVISAO = "AGUARDANDO_REVISAO"
    REPROVADO_EM_REVISAO = "REPROVADO_EM_REVISAO"
    PLANO_LIBERADO = "PLANO_LIBERADO"
    COLETA_DIRIGIDA = "COLETA_DIRIGIDA"
    CONFIRMACAO_ATAQUE = "CONFIRMACAO_ATAQUE"
    ACOMPANHAMENTO = "ACOMPANHAMENTO"
    ENCERRADO = "ENCERRADO"


@dataclass(frozen=True, slots=True)
class Caso:
    """Um caso — o ciclo de vida do aluno (`RF-01`).

    Os dois campos de snapshot seguem o SQL real de `002_app_aluno.sql`
    (T-21, já concluída), não a prosa do plano §4.3 (que desenha um único
    `snapshot_corrente_id`): `snapshot_raiz_id` (`OQ-11`) só é preenchido
    quando o PRIMEIRO snapshot nasce; `snapshot_liberado_id` (`OQ-09`) aponta
    o último snapshot LIBERADO em revisão. Esta divergência já estava
    documentada por T-23 e é preservada aqui, agora na fonte canônica."""

    CASO_ID: str
    conta_id: str
    estado: ESTADO_CASO
    DATA_REFERENCIA: date  # RF-14 · AC-18 — entrada explícita, nunca relógio
    QUESTIONARIO_VERSION: str
    snapshot_raiz_id: str | None  # OQ-11 — preenchido só no primeiro snapshot
    snapshot_liberado_id: str | None  # OQ-09 — último snapshot LIBERADO
    ultima_interacao_em: datetime  # RF-31 · EC-14
    criado_em: datetime


@dataclass(frozen=True, slots=True)
class Transicao:
    """Uma transição nomeada da máquina — `de`/`para` fixam o par de
    estados; `gatilho` nomeia o evento que a dispara (nunca implícito);
    `guarda` é a condição textual que precisa valer, quando houver uma."""

    de: ESTADO_CASO
    para: ESTADO_CASO
    gatilho: str
    guarda: str | None = None


class ErroTransicaoNaoDeclarada(Exception):
    """Levantado quando `(de, para)` não corresponde a nenhuma `Transicao`
    da tabela — nomeia origem e destino. Nunca uma transição é
    silenciosamente aceita fora da tabela."""

    def __init__(self, de: ESTADO_CASO, para: ESTADO_CASO) -> None:
        self.de = de
        self.para = para
        super().__init__(
            f"transição não declarada: {de.value!r} → {para.value!r} (RF-01)"
        )


# Tabela de transições nomeadas — plano §7.1. Cada linha é uma decisão
# explícita: par (de, para), gatilho nomeado e guarda opcional. Um par fora
# desta tabela é recusado por `transicionar` — nunca tolerado.
TABELA_TRANSICOES: Final[tuple[Transicao, ...]] = (
    Transicao(
        de=ESTADO_CASO.CADASTRADO,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        gatilho="registra_consentimento",
        guarda=None,
    ),
    Transicao(
        de=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        para=ESTADO_CASO.COLETA_INICIAL,
        gatilho="inicia_coleta",
        guarda="RF-30 · AC-39: nada gravado antes daqui",
    ),
    Transicao(
        de=ESTADO_CASO.COLETA_INICIAL,
        para=ESTADO_CASO.CALCULANDO,
        gatilho="bloco_6_executa",
        guarda="B5.FIM02 + campos OBR completos",
    ),
    Transicao(
        de=ESTADO_CASO.CALCULANDO,
        para=ESTADO_CASO.ERRO_DE_CALCULO,
        gatilho="erro_no_calculo",
        guarda="ErroInvariante/ErroParametros do motor",
    ),
    Transicao(
        de=ESTADO_CASO.CALCULANDO,
        para=ESTADO_CASO.AGUARDANDO_REVISAO,
        gatilho="snapshot_anexado",
        guarda="AC-12: snapshot anexado",
    ),
    # ERRO_DE_CALCULO retorna a um dos quatro estados de origem de
    # CALCULANDO (EC-06) — ver a nota do módulo sobre por que são quatro
    # transições, não uma única com destino fixo inventado.
    Transicao(
        de=ESTADO_CASO.ERRO_DE_CALCULO,
        para=ESTADO_CASO.COLETA_INICIAL,
        gatilho="operador_retoma_apos_erro",
        guarda="EC-06: volta ao estado anterior",
    ),
    Transicao(
        de=ESTADO_CASO.ERRO_DE_CALCULO,
        para=ESTADO_CASO.COLETA_DIRIGIDA,
        gatilho="operador_retoma_apos_erro",
        guarda="EC-06: volta ao estado anterior",
    ),
    Transicao(
        de=ESTADO_CASO.ERRO_DE_CALCULO,
        para=ESTADO_CASO.CONFIRMACAO_ATAQUE,
        gatilho="operador_retoma_apos_erro",
        guarda="EC-06: volta ao estado anterior",
    ),
    Transicao(
        de=ESTADO_CASO.ERRO_DE_CALCULO,
        para=ESTADO_CASO.ACOMPANHAMENTO,
        gatilho="operador_retoma_apos_erro",
        guarda="EC-06: volta ao estado anterior",
    ),
    Transicao(
        de=ESTADO_CASO.AGUARDANDO_REVISAO,
        para=ESTADO_CASO.REPROVADO_EM_REVISAO,
        gatilho="reprova",
        guarda="EC-12: decisão = REPROVADO",
    ),
    Transicao(
        de=ESTADO_CASO.AGUARDANDO_REVISAO,
        para=ESTADO_CASO.PLANO_LIBERADO,
        gatilho="libera",
        guarda="RF-24: decisão = LIBERADO",
    ),
    Transicao(
        de=ESTADO_CASO.PLANO_LIBERADO,
        para=ESTADO_CASO.COLETA_DIRIGIDA,
        gatilho="abre_blocos_7_8",
        guarda="AC-19: ORDEM_ACOES tem ação",
    ),
    Transicao(
        de=ESTADO_CASO.PLANO_LIBERADO,
        para=ESTADO_CASO.CONFIRMACAO_ATAQUE,
        gatilho="abre_bloco_10",
        guarda="AC-22: ataque recomendado > 0",
    ),
    Transicao(
        de=ESTADO_CASO.PLANO_LIBERADO,
        para=ESTADO_CASO.ACOMPANHAMENTO,
        gatilho="abre_bloco_11",
        guarda="ação reportada, meses depois",
    ),
    Transicao(
        de=ESTADO_CASO.COLETA_DIRIGIDA,
        para=ESTADO_CASO.CALCULANDO,
        gatilho="recalcula",
        guarda="AC-26: entra na fila de novo",
    ),
    Transicao(
        de=ESTADO_CASO.CONFIRMACAO_ATAQUE,
        para=ESTADO_CASO.CALCULANDO,
        gatilho="recalcula",
        guarda="AC-26: entra na fila de novo",
    ),
    Transicao(
        de=ESTADO_CASO.ACOMPANHAMENTO,
        para=ESTADO_CASO.CALCULANDO,
        gatilho="recalcula",
        guarda="AC-30/RF-28: quitação ou evento",
    ),
)

# Índice (de, para) -> Transicao, montado uma vez a partir da tabela acima.
# Nunca é a fonte de verdade — só um cache de lookup sobre TABELA_TRANSICOES.
_INDICE_TRANSICOES: Final[dict[tuple[ESTADO_CASO, ESTADO_CASO], Transicao]] = {
    (transicao.de, transicao.para): transicao for transicao in TABELA_TRANSICOES
}


def transicionar(de: ESTADO_CASO, para: ESTADO_CASO) -> Transicao:
    """Devolve a `Transicao` declarada para o par `(de, para)`. Função TOTAL
    sobre o domínio: todo par de estados é uma decisão explícita — permitido
    (devolve a `Transicao` da tabela) ou recusado (`ErroTransicaoNaoDeclarada`,
    nomeando origem e destino). Nunca há um terceiro caminho silencioso."""
    transicao = _INDICE_TRANSICOES.get((de, para))
    if transicao is None:
        raise ErroTransicaoNaoDeclarada(de, para)
    return transicao


def transicoes_a_partir_de(de: ESTADO_CASO) -> tuple[Transicao, ...]:
    """Todas as transições declaradas que partem de `de` — útil para listar
    os gatilhos disponíveis num estado sem precisar conhecer os destinos de
    antemão."""
    return tuple(transicao for transicao in TABELA_TRANSICOES if transicao.de == de)


# ---------------------------------------------------------------------------
# Guarda "sem consentimento, nenhuma resposta é gravada" — RF-30, AC-39 (T-36).
#
# A topologia da tabela acima já torna estruturalmente impossível pular
# `CONSENTIMENTO_REGISTRADO`: não existe (e nunca existiu) uma transição
# `CADASTRADO → COLETA_INICIAL`. O que falta declarar aqui, para que a guarda
# seja verificável sem subir a aplicação HTTP e sem depender de nenhuma rota,
# é EM QUAIS ESTADOS gravar uma resposta é uma operação válida — porque a
# máquina não é linear a partir de `COLETA_INICIAL` (o caso volta a receber
# respostas em `COLETA_DIRIGIDA`, `CONFIRMACAO_ATAQUE`, `ACOMPANHAMENTO` etc.,
# nunca só "estado >= COLETA_INICIAL" por uma ordem que a máquina não define).
#
# Por isso o conjunto é ENUMERADO explicitamente — nunca um cálculo de
# "distância" a partir de CADASTRADO — e é justamente TODOS os estados MENOS
# os dois anteriores ao consentimento (`CADASTRADO`,
# `CONSENTIMENTO_REGISTRADO`): a partir de `COLETA_INICIAL` em diante, sempre
# existe alguma pergunta pendente de algum bloco (coleta inicial, dirigida,
# confirmação de ataque ou acompanhamento). `CALCULANDO` está incluído porque
# uma resposta em trânsito no momento em que o Bloco 6 dispara não deveria ser
# perdida; nenhuma rota desta feature grava fora desses estados hoje.
ESTADOS_QUE_PERMITEM_RESPOSTA: Final[frozenset[ESTADO_CASO]] = frozenset(ESTADO_CASO) - {
    ESTADO_CASO.CADASTRADO,
    ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
}


class ErroConsentimentoNaoRegistrado(Exception):
    """Levantado por `exigir_estado_permite_resposta` quando o caso ainda
    está em `CADASTRADO` ou `CONSENTIMENTO_REGISTRADO` — nenhuma resposta é
    gravada antes de `inicia_coleta` disparar (`RF-30`, `AC-39`). Nomeia o
    `CASO_ID` e o `estado` corrente, nunca falha silenciosamente."""

    def __init__(self, caso_id: str, estado: ESTADO_CASO) -> None:
        self.caso_id = caso_id
        self.estado = estado
        super().__init__(
            f"CASO_ID={caso_id!r} estado={estado.value!r}: "
            "RF-30 · AC-39 — sem consentimento."
        )


def exigir_estado_permite_resposta(caso_id: str, estado: ESTADO_CASO) -> None:
    """A GUARDA em si — função total, sem I/O, chamada pelo caminho de
    gravação de resposta (hoje `persistencia/app_aluno/respostas.py::
    RepositorioRespostasSupabase.gravar`) ANTES de qualquer `INSERT`. Não
    devolve nada em caso de sucesso; levanta `ErroConsentimentoNaoRegistrado`
    caso o `estado` não pertença a `ESTADOS_QUE_PERMITEM_RESPOSTA` — nunca
    tolera silenciosamente um estado fora do conjunto.

    Por viver aqui (regra de domínio, `app/`) e ser invocada pelo adaptador
    de persistência (infraestrutura, `persistencia/`), a guarda é a mesma
    para qualquer chamador presente ou futuro de `RepositorioRespostas.gravar`
    — uma rota nova não pode contorná-la sem deixar de chamar o repositório,
    o que a tornaria incapaz de gravar nada."""
    if estado not in ESTADOS_QUE_PERMITEM_RESPOSTA:
        raise ErroConsentimentoNaoRegistrado(caso_id, estado)
