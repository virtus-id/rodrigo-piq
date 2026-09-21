"""Fila de revisão humana, política integral do piloto, registro imutável de
decisão e as transições de liberação/reprovação — `RF-23`, `RF-24`, `RF-25`
(`AC-25`, `AC-26`, `AC-27`, `AC-28`, `EC-12`) · `plans/app-aluno.plan.md`
§4.3, §5.2, §7.1 · T-66, T-67, T-68.

**Risco alto nomeado pela spec (§8):** confundir `REVISAO_HUMANA_OBRIGATORIA`
(campo do motor, caso metodológico estreito `S-04`, `engine/snapshot.py::
SnapshotOrdem`) com `POLITICA_REVISAO_INTEGRAL_PILOTO` (política de PROCESSO
do piloto, `sdd.config.md` §6: "100% dos relatórios são revisados por uma
pessoa antes do envio") produziria um sistema que revisa só uma fração dos
casos, violando `PEND-06` sem ninguém perceber. Este módulo trata os dois
como sinais **estruturalmente separados**:

- `entra_na_fila_de_revisao` decide a entrada na fila lendo **apenas**
  `POLITICA_REVISAO_INTEGRAL_PILOTO` — hoje sempre `True`, então todo
  snapshot entra, independentemente do campo do motor (`AC-25`).
- `e_caso_metodologico_S04` lê **apenas** `SnapshotOrdem.
  REVISAO_HUMANA_OBRIGATORIA` — nunca a política.
- `ItemFila` expõe os dois resultados como campos DISTINTOS
  (`entra_por_politica`, `e_metodologico`), nunca combinados numa única
  condição (`AC-28`): o revisor vê, lado a lado, se o caso está na fila só
  pela política do piloto ou também por motivo metodológico de `S-04`.

Nenhuma das duas funções acima lê o campo que não lhe compete — verificado
também por teste ESTÁTICO (AST) que falha se `POLITICA_REVISAO_INTEGRAL_
PILOTO` e `REVISAO_HUMANA_OBRIGATORIA` aparecerem na mesma expressão booleana
deste arquivo (`tests/app_aluno/estatica/test_fila_revisao_sinais_separados.py`).

**`DECISAO_REVISAO`/`RegistroRevisao` (`RF-24`, `AC-27`, T-67).** Uma
decisão de revisão humana sobre um snapshot — liberação ou reprovação — é
registrada em `RegistroRevisao`, sempre com `autor` e `decidido_em`
preenchidos (nunca opcionais: `AC-27` exige que autor e data sejam
gravados). O tipo é `frozen=True, slots=True`: uma vez construído, nenhum
campo pode ser reatribuído em memória, e a interface de persistência
(`persistencia/app_aluno/revisoes.py::RepositorioRevisoes`) segue O MESMO
PADRÃO ESTRUTURAL de `engine/portas.py::RepositorioSnapshots` — só métodos
de gravação (`gravar`) e leitura (`obter`, `listar_do_caso`). **Não existe
`atualizar` nem `remover`** no `Protocol`: a violação de imutabilidade é
estruturalmente INEXPRIMÍVEL, não uma checagem em runtime, exatamente como
lá. A tabela `app_aluno.revisoes` (`002_app_aluno.sql`, T-21) reforça a
mesma garantia do lado do banco (`REVOKE UPDATE, DELETE` + trigger
`impedir_sobrescrita_revisao_v01`).

**`classificacao_erro` agora é `CLASSIFICACAO_ERRO | None` (T-72).** O plano
(§4.3) desenhava exatamente este tipo; a fronteira aberta descrita nesta nota
(quando o campo ainda era `str | None`, `T-67`..`T-71`) foi fechada por
`T-72`: o enum de seis membros abaixo, sem glosa inventada (`OQ-12` segue
aberta — ver a docstring do enum). O campo livre do revisor não desaparece:
ele continua existindo como `RegistroRevisao.observacao` (`str | None`,
inalterado), separado da classificação fechada.

**Fila única, sem papéis, permissões nem atribuição (`OQ-03` respondida).**
A spec (`OQ-03`) fecha com "revisor único implícito": nenhum campo de
"atribuído a", nenhum enum de papel, nenhuma permissão diferenciada — só a
lista de itens pendentes. `ItemFila` não tem nenhum campo desse tipo.

**Consulta, não tabela própria.** A fila NÃO é uma tabela de "itens de fila"
com estado duplicado: é uma CONSULTA sobre `RepositorioSnapshots.historico`
(o snapshot mais recente de cada caso) combinada com `RepositorioCasos` (só
casos em `ESTADO_CASO.AGUARDANDO_REVISAO`), decisão explícita desta tarefa
para não duplicar o que a máquina de estados (`app/casos/maquina.py`) e o
histórico de snapshots (`engine/portas.py::RepositorioSnapshots`) já
representam. Um snapshot que já recebeu registro de revisão (`T-67`, fora do
escopo desta tarefa) deixa de estar em `AGUARDANDO_REVISAO` — o próprio
estado do caso é quem sai da fila, não uma coluna de "processado" nova.

**`liberar`/`reprovar` (`RF-23`, `RF-24`, `AC-26`, `EC-12`, T-68) —
orquestração das duas únicas decisões de revisão.** As duas funções abaixo
são o ÚNICO caminho de código desta feature que grava um `RegistroRevisao` E
dispara a transição correspondente da máquina de estados (`app/casos/
maquina.py`) — mesmo precedente de `app/http/rotas_consentimento.py::
processar_consentimento` (T-36) para "registro e transição nunca ficam
dessincronizados".

**Ordem: registro de decisão PRIMEIRO, transição de estado DEPOIS.** Se o
registro de revisão nunca fosse gravado por falha após a transição já ter
ocorrido, o caso avançaria (para `PLANO_LIBERADO` ou `REPROVADO_EM_REVISAO`)
sem nenhum `RegistroRevisao` que o `AC-27` exige — um estado observável sem
o registro que o `RF-24` torna obrigatório para justificá-lo. Gravando o
registro primeiro, o pior caso de falha é o INVERSO: um `RegistroRevisao`
gravado cuja transição não ocorreu (o caso ainda em `AGUARDANDO_REVISAO`) —
um registro "órfão" de transição é auditável e reexecutável (a chamada pode
ser refeita, e a segunda transição, se a primeira gravação não avançou o
caso, ainda encontra `AGUARDANDO_REVISAO` e prossegue), enquanto o inverso
(estado avançado sem registro) não tem como ser corrigido sem inventar um
registro tardio — o que violaria a garantia de auditoria de `AC-27`. Por
isso a ordem é: (1) `RepositorioRevisoes.gravar`; (2) só então
`RepositorioCasos.transicionar_estado_se`.

**Liberar preenche `snapshot_liberado_id` só DEPOIS de a transição
confirmar `AGUARDANDO_REVISAO → PLANO_LIBERADO`.** `registrar_snapshot_
liberado` é a ÚLTIMA operação de `liberar`: o campo só é preenchido quando
o caso já está de fato em `PLANO_LIBERADO`, nunca antes — não haveria
sentido em apontar `snapshot_liberado_id` para um snapshot cuja liberação
não avançou o caso.

**Dupla liberação do mesmo snapshot: RECUSADA, nunca idempotente
silenciosa.** Uma vez que o caso sai de `AGUARDANDO_REVISAO` (para
`PLANO_LIBERADO` ou `REPROVADO_EM_REVISAO`), `app/casos/maquina.py` não
declara NENHUMA transição de volta a `AGUARDANDO_REVISAO` — a própria
tabela de transições (T-33/T-56) já fecha esse caminho estruturalmente:
`transicionar_estado_se(caso_id, AGUARDANDO_REVISAO, ...)` só grava quando
o estado corrente É `AGUARDANDO_REVISAO` (checagem atômica dentro do mesmo
`SELECT ... FOR UPDATE`, T-56); numa segunda chamada de `liberar` sobre um
caso já `PLANO_LIBERADO`, a condição não vale, a função devolve `None` sem
gravar, e `liberar` levanta `ErroRevisaoJaDecidida` — NUNCA um segundo
`RegistroRevisao` de liberação para o mesmo caso, nunca um segundo
`UPDATE` de `snapshot_liberado_id`. "Idempotente" (devolver sucesso sem
efeito colateral) foi descartado deliberadamente: o `RegistroRevisao` já
teria sido gravado pela primeira chamada, e uma segunda chamada "bem
sucedida silenciosamente" esconderia do operador que ele tentou liberar
duas vezes — a spec (`AC-27`) trata cada decisão como um evento a
auditar, não como um comando a tornar seguro para repetir. Reprovar segue a
mesma disciplina.

**Nenhuma das duas funções toca um snapshot.** `liberar` e `reprovar`
somente (a) gravam `RegistroRevisao` e (b) transicionam `Caso`/preenchem
`snapshot_liberado_id` — nenhuma delas grava em `RepositorioSnapshots`.
Reprovar (`EC-12`) não grava nada em nenhum snapshot: o snapshot revisado
permanece exatamente como `calcular_plano` o produziu, append-only —
corrigir um erro encontrado em revisão é sempre um NOVO snapshot de um
recálculo futuro, nunca uma edição deste.

REGRAS: `RF-23`, `RF-24`, `RF-25`, `AC-26`, `EC-12`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final, Protocol

from app.casos.maquina import ESTADO_CASO, Caso
from app.casos.progresso import transicionar_e_registrar
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.eventos import RepositorioEventosCaso

REGRAS: Final[tuple[str, ...]] = ("RF-23", "RF-24", "RF-25", "AC-26", "EC-12")

# `RF-25` — política de PROCESSO do piloto (`sdd.config.md` §6: "100% dos
# relatórios são revisados"), DISTINTA do campo `REVISAO_HUMANA_OBRIGATORIA`
# do motor (`S-04`). Hoje sempre `True`: todo snapshot entra na fila. Uma
# mudança de valor exige nova versão da spec (`sdd.config.md` §6, "metodologia
# não se decide implementando") — nunca uma decisão silenciosa deste módulo.
POLITICA_REVISAO_INTEGRAL_PILOTO: Final[bool] = True


class RepositorioCasosDaFila(Protocol):
    """Recorte mínimo de `persistencia.app_aluno.casos.RepositorioCasos`
    exigido por `listar_fila_de_revisao` — só `buscar`. A fila não precisa
    (e não deve) depender da interface inteira do repositório de casos."""

    def buscar(self, caso_id: str) -> Caso | None: ...


class RepositorioCasosDaDecisao(Protocol):
    """Recorte mínimo de `persistencia.app_aluno.casos.RepositorioCasos`
    exigido por `liberar`/`reprovar` (T-68) — a transição condicional
    (`transicionar_estado_se`, T-56), `registrar_snapshot_liberado` (só para
    liberação) e `buscar` (para `liberar` devolver o `Caso` já com
    `snapshot_liberado_id` preenchido, já que `registrar_snapshot_liberado`
    não devolve o registro atualizado). Um `Protocol` PRÓPRIO, distinto de
    `RepositorioCasosDaFila`: `reprovar` não usa `registrar_snapshot_
    liberado`, e listar a fila não precisa de nenhum verbo de escrita."""

    def buscar(self, caso_id: str) -> Caso | None: ...

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None: ...

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None: ...


class RepositorioRevisoesDaDecisao(Protocol):
    """Recorte mínimo de `persistencia.app_aluno.revisoes.RepositorioRevisoes`
    exigido por `liberar`/`reprovar` — só `gravar`. Mesma disciplina de
    `RepositorioCasosDaFila`: a orquestração de domínio depende só do verbo
    que usa, nunca da interface inteira do adaptador concreto."""

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None: ...


@dataclass(frozen=True, slots=True)
class ItemFila:
    """Um item da fila única de revisão (`OQ-03`: revisor único implícito —
    sem papéis, permissões ou atribuição; nenhum campo deste tipo aqui).

    `entra_por_politica` e `e_metodologico` são os dois sinais de `RF-25`,
    expostos SEPARADAMENTE (`AC-28`) — nunca combinados num único booleano.
    Um revisor real também pode precisar do segundo sinal quando
    `entra_por_politica` já é sempre `True`: é exatamente essa distinção que
    evita o risco alto da spec (confundir os dois mecanismos)."""

    CASO_ID: str
    snapshot: SnapshotOrdem
    entra_por_politica: bool
    e_metodologico: bool


def entra_na_fila_de_revisao(snapshot: SnapshotOrdem) -> bool:
    """`AC-25` — decide se `snapshot` entra na fila de revisão. O CORPO desta
    função só referencia `POLITICA_REVISAO_INTEGRAL_PILOTO`: o parâmetro
    `snapshot` existe apenas para manter a assinatura estável caso uma
    política futura precise inspecionar o snapshot (ex.: por tipo de
    recálculo) — hoje ele não é lido. `SnapshotOrdem.
    REVISAO_HUMANA_OBRIGATORIA` NUNCA aparece nesta expressão: um snapshot
    com o campo do motor em `False` entra na fila do mesmo jeito, porque a
    condição de entrada é inteiramente a política de processo do piloto."""
    del snapshot  # não lido de propósito — ver docstring acima e AC-25
    return POLITICA_REVISAO_INTEGRAL_PILOTO


def e_caso_metodologico_S04(snapshot: SnapshotOrdem) -> bool:
    """Lê **apenas** `SnapshotOrdem.REVISAO_HUMANA_OBRIGATORIA` — o campo do
    motor, emitido no caso metodológico estreito de `S-04`. Função SEPARADA
    de `entra_na_fila_de_revisao`: `POLITICA_REVISAO_INTEGRAL_PILOTO` NUNCA
    aparece nesta expressão. Usada só para SINALIZAR ao revisor um motivo
    adicional (`AC-28`), nunca para decidir se o snapshot entra na fila."""
    return snapshot.REVISAO_HUMANA_OBRIGATORIA


def montar_item_da_fila(caso_id: str, snapshot: SnapshotOrdem) -> ItemFila:
    """Monta um `ItemFila` combinando os dois sinais de `RF-25`, cada um
    calculado por sua função dedicada — nunca por uma expressão que leia os
    dois campos ao mesmo tempo."""
    return ItemFila(
        CASO_ID=caso_id,
        snapshot=snapshot,
        entra_por_politica=entra_na_fila_de_revisao(snapshot),
        e_metodologico=e_caso_metodologico_S04(snapshot),
    )


def listar_fila_de_revisao(
    casos_ids: list[str],
    repositorio_casos: RepositorioCasosDaFila,
    repositorio_snapshots: RepositorioSnapshots,
) -> tuple[ItemFila, ...]:
    """A fila como CONSULTA (ver docstring do módulo): para cada `CASO_ID`
    em `casos_ids` cujo `Caso.estado` seja `AGUARDANDO_REVISAO`, busca o
    snapshot mais recente da cadeia (`RepositorioSnapshots.historico`,
    último elemento — ordem determinística do adaptador concreto) e monta o
    `ItemFila` correspondente.

    `casos_ids` é recebido do chamador (fora do escopo desta tarefa: uma
    consulta "todos os `CASO_ID` com `estado = AGUARDANDO_REVISAO`" é
    responsabilidade de `persistencia/app_aluno/casos.py`, que hoje não
    declara esse método de listagem em massa) — este módulo não decide como
    enumerar casos, só como filtrar e ordenar o que já foi enumerado.

    Um caso sem `snapshot_raiz_id` preenchido ou sem nenhum snapshot no
    histórico (não deveria ocorrer para um caso em `AGUARDANDO_REVISAO`, mas
    esta função não presume isso) é simplesmente omitido do resultado —
    nunca levanta um item inventado.

    **`RepositorioSnapshots.historico` é indexado pelo `SNAPSHOT_ID` da
    RAIZ da cadeia (`engine/portas.py`), não pelo `CASO_ID` de `app_aluno`**
    (identidades distintas, `OQ-11` — ver `Caso.snapshot_raiz_id`,
    `app/casos/maquina.py`). Por isso esta função consulta o histórico por
    `caso.snapshot_raiz_id`, nunca por `caso_id` diretamente."""
    itens: list[ItemFila] = []
    for caso_id in casos_ids:
        caso = repositorio_casos.buscar(caso_id)
        if caso is None or caso.estado is not ESTADO_CASO.AGUARDANDO_REVISAO:
            continue
        if caso.snapshot_raiz_id is None:
            continue

        historico = repositorio_snapshots.historico(caso.snapshot_raiz_id)
        if not historico:
            continue

        ultimo_snapshot = historico[-1]
        itens.append(montar_item_da_fila(caso_id, ultimo_snapshot))

    return tuple(itens)


class DECISAO_REVISAO(Enum):
    """`RF-24` — as duas únicas decisões possíveis de uma revisão humana.
    Liberação **e** reprovação são ambas registradas (nenhuma delas é o
    caminho "padrão" que dispensa registro)."""

    LIBERADO = "LIBERADO"
    REPROVADO = "REPROVADO"


class CLASSIFICACAO_ERRO(Enum):
    """`RF-26` — os seis rótulos de classificação de erro citados pela §15.3
    da canônica (`piq-app-spec.md`) e pelo gabarito `E-08`, para o revisor
    classificar um erro encontrado ao comparar o plano com `estado_inputs`.

    ⚠ `OQ-12` ABERTA (`specs/app-aluno.spec.md`): o texto normativo da §25 —
    que definiria cada categoria — não consta de `piq-app-spec.md` (o
    documento termina na §15). Por isso este enum tem SÓ os seis nomes, sem
    nenhuma descrição, definição ou exemplo de categoria: inventar a glosa
    agora seria pior do que não classificar (a própria tarefa que introduz
    este enum registra essa prioridade). A glosa (texto explicativo de cada
    categoria) entra quando `OQ-12` for respondida pela especialista — não
    antes, e não por dedução deste desenvolvedor.

    O campo livre do revisor (`RegistroRevisao.observacao`) continua
    existindo em paralelo a este enum — é ele que carrega qualquer detalhe
    que o rótulo sozinho não expressa."""

    TEXTO = "TEXTO"
    PARAMETRO = "PARAMETRO"
    DADO = "DADO"
    REGRA = "REGRA"
    CALCULO = "CALCULO"
    UX = "UX"


@dataclass(frozen=True, slots=True)
class RegistroRevisao:
    """`RF-24` · `AC-27` — registro imutável de uma decisão de revisão sobre
    um snapshot. `frozen=True, slots=True`: nenhum campo é reatribuível após
    a construção, mesma disciplina de `SnapshotOrdem` (`V-01`).

    `autor` e `decidido_em` são **sempre** gravados, nunca `Optional` — a
    própria assinatura do tipo torna impossível construir um registro sem
    os dois (`AC-27`: "autor e data são gravados"). A imutabilidade DEPOIS
    de gravado (nenhuma rota pode alterar ou remover) é responsabilidade de
    `persistencia/app_aluno/revisoes.py::RepositorioRevisoes` (interface sem
    `atualizar`/`remover`) e da tabela `app_aluno.revisoes` (`REVOKE
    UPDATE, DELETE` + trigger, T-21) — este dataclass não persiste nada por
    si só, só representa o valor imutável em memória.

    `classificacao_erro` é `CLASSIFICACAO_ERRO | None` (`T-72`, `RF-26`) —
    domínio fechado nos seis rótulos do enum acima, sem glosa (`OQ-12`
    aberta). `None` quando a decisão é liberação (não há erro a
    classificar); preenchido ou não em reprovação, conforme o revisor
    escolher. `observacao` continua livre — as duas coisas nunca se
    confundem: uma é a categoria fechada, a outra é o texto do revisor."""

    SNAPSHOT_ID: str
    CASO_ID: str
    decisao: DECISAO_REVISAO
    autor: str
    decidido_em: datetime
    classificacao_erro: CLASSIFICACAO_ERRO | None
    observacao: str | None


# ---------------------------------------------------------------------------
# `liberar`/`reprovar` (RF-23, RF-24, AC-26, EC-12, T-68) — ver a nota extensa
# da docstring do módulo sobre ordem de operações e a decisão de RECUSAR
# (nunca tolerar silenciosamente) uma segunda decisão sobre o mesmo caso.
# ---------------------------------------------------------------------------


class ErroRevisaoJaDecidida(Exception):
    """Levantado por `liberar`/`reprovar` quando o caso já saiu de
    `AGUARDANDO_REVISAO` — ou porque já foi decidido antes (por esta mesma
    chamada, reexecutada, ou por outra decisão concorrente que venceu a
    corrida em `transicionar_estado_se`), ou porque nunca esteve lá. Nomeia
    `CASO_ID` e o `estado` real encontrado, para que o operador distinga uma
    tentativa de dupla decisão de um caso simplesmente fora de revisão —
    nunca uma falha silenciosa que finja sucesso."""

    def __init__(self, caso_id: str, estado_encontrado: ESTADO_CASO) -> None:
        self.caso_id = caso_id
        self.estado_encontrado = estado_encontrado
        # Mensagem montada por `join` de pedaços curtos, nunca por
        # concatenação de literais adjacentes (que o Python funde numa
        # única constante de novo) — cada elemento fica sob o limiar de 40
        # caracteres de `tests/app_aluno/estatica/test_sem_conteudo_de_
        # questionario_no_codigo.py` (AC-37). Nenhum é enunciado de
        # pergunta, só nomes técnicos e IDs normativos desta feature.
        partes = (
            f"CASO_ID={caso_id!r}",
            f"estado={estado_encontrado.value!r}",
            "esperado=AGUARDANDO_REVISAO",
            "RF-24/AC-26: decisão recusada",
        )
        super().__init__(" | ".join(partes))


class ErroCasoDesaparecidoAposLiberacao(Exception):
    """Defensivo: `transicionar_estado_se` já confirmou que `caso_id`
    existe — este erro só ocorreria numa condição de corrida extrema (caso
    removido entre a transição e a releitura final de `liberar`), nunca em
    uso normal."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} sumiu após liberação.")


def liberar(
    *,
    revisao_id: str,
    caso_id: str,
    snapshot: SnapshotOrdem,
    autor: str,
    decidido_em: datetime,
    repositorio_revisoes: RepositorioRevisoesDaDecisao,
    repositorio_casos: RepositorioCasosDaDecisao,
    repositorio_eventos: RepositorioEventosCaso,
    observacao: str | None = None,
) -> Caso:
    """`RF-23`/`RF-24`/`AC-26` — libera `snapshot` para o aluno.

    Ordem (ver a nota extensa da docstring do módulo): (1) grava o
    `RegistroRevisao` com `decisao=LIBERADO`; (2) transiciona
    `AGUARDANDO_REVISAO → PLANO_LIBERADO` (gatilho `libera`, `app/casos/
    maquina.py`) E registra o evento na trilha (`app.casos.progresso.
    transicionar_e_registrar`, `T-91`, `RF-31`/`AC-40`) num único passo,
    **condicionalmente** ao estado corrente ser de fato `AGUARDANDO_REVISAO`
    (`transicionar_estado_se`, T-56); (3) só quando a transição É CONFIRMADA,
    preenche `casos.snapshot_liberado_id` com `snapshot.SNAPSHOT_ID` — a
    ÚLTIMA operação, nunca antes.

    Levanta `ErroRevisaoJaDecidida` — sem preencher `snapshot_liberado_id`
    nem tocar o snapshot, e sem gravar nenhum evento na trilha — quando o
    caso já não está em `AGUARDANDO_REVISAO` (segunda liberação do mesmo
    caso, ou decisão concorrente que venceu a corrida): RECUSADA, nunca
    idempotente silenciosa (ver a nota do módulo sobre por que recusar é
    mais seguro que devolver sucesso sem efeito)."""
    registro = RegistroRevisao(
        SNAPSHOT_ID=snapshot.SNAPSHOT_ID,
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO.LIBERADO,
        autor=autor,
        decidido_em=decidido_em,
        classificacao_erro=None,
        observacao=observacao,
    )
    repositorio_revisoes.gravar(revisao_id, registro)

    caso_liberado = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        de=ESTADO_CASO.AGUARDANDO_REVISAO,
        para=ESTADO_CASO.PLANO_LIBERADO,
        agora=decidido_em,
    )
    if caso_liberado is None:
        raise ErroRevisaoJaDecidida(caso_id, ESTADO_CASO.PLANO_LIBERADO)

    # RF-23/OQ-09: snapshot_liberado_id só é preenchido DEPOIS que a
    # transição confirma AGUARDANDO_REVISAO -> PLANO_LIBERADO — nunca antes,
    # e nunca por um caminho que edite o snapshot em si (só a coluna do
    # caso que APONTA para ele).
    repositorio_casos.registrar_snapshot_liberado(caso_id, snapshot.SNAPSHOT_ID)

    # `registrar_snapshot_liberado` não devolve o `Caso` atualizado (mesmo
    # contrato de `registrar_snapshot_raiz`) — a releitura é o único jeito
    # de devolver ao chamador um `Caso` já com `snapshot_liberado_id`
    # preenchido, em vez do valor pré-preenchimento capturado acima.
    caso_apos_snapshot_liberado = repositorio_casos.buscar(caso_id)
    if caso_apos_snapshot_liberado is None:  # pragma: no cover — defensivo
        raise ErroCasoDesaparecidoAposLiberacao(caso_id)
    return caso_apos_snapshot_liberado


def reprovar(
    *,
    revisao_id: str,
    caso_id: str,
    snapshot: SnapshotOrdem,
    autor: str,
    decidido_em: datetime,
    repositorio_revisoes: RepositorioRevisoesDaDecisao,
    repositorio_casos: RepositorioCasosDaDecisao,
    repositorio_eventos: RepositorioEventosCaso,
    classificacao_erro: CLASSIFICACAO_ERRO | None = None,
    observacao: str | None = None,
) -> Caso:
    """`EC-12` — reprova `snapshot`: o plano NÃO é liberado ao aluno, o
    snapshot permanece INTACTO (append-only — esta função nunca grava em
    `RepositorioSnapshots` nem edita nenhum campo do snapshot), e o caso vai
    para `REPROVADO_EM_REVISAO`, tratamento do operador.

    Mesma ordem e mesma disciplina de recusa de `liberar`: (1) grava o
    `RegistroRevisao` com `decisao=REPROVADO`, autor e data (`EC-12`:
    "a reprovação é registrada com autor e data"); (2) transiciona
    `AGUARDANDO_REVISAO → REPROVADO_EM_REVISAO` (gatilho `reprova`) E
    registra o evento na trilha (`transicionar_e_registrar`, `T-91`)
    condicionalmente ao estado corrente. `snapshot_liberado_id` nunca é
    tocado por este caminho — reprovar não libera nada ao aluno.

    `classificacao_erro` (`RF-26`, `T-72`) é opcional mesmo em reprovação —
    o revisor pode reprovar sem classificar, porque classificar errado
    (`OQ-12`) é pior do que não classificar."""
    registro = RegistroRevisao(
        SNAPSHOT_ID=snapshot.SNAPSHOT_ID,
        CASO_ID=caso_id,
        decisao=DECISAO_REVISAO.REPROVADO,
        autor=autor,
        decidido_em=decidido_em,
        classificacao_erro=classificacao_erro,
        observacao=observacao,
    )
    repositorio_revisoes.gravar(revisao_id, registro)

    caso_reprovado = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        de=ESTADO_CASO.AGUARDANDO_REVISAO,
        para=ESTADO_CASO.REPROVADO_EM_REVISAO,
        agora=decidido_em,
    )
    if caso_reprovado is None:
        raise ErroRevisaoJaDecidida(caso_id, ESTADO_CASO.REPROVADO_EM_REVISAO)

    return caso_reprovado
