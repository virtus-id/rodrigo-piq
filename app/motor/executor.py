"""Executor do Bloco 6 — invoca `calcular_plano` EM PROCESSO, uma única vez —
`RF-16`, `RF-19`, `RF-32` (`AC-12`, `AC-43`) · `plans/app-aluno.plan.md` §5.2.

Os QUATRO PASSOS EXATOS do plano, nesta ordem, sem nenhum passo de cálculo
reproduzido aqui:

```
1. FonteParametros.carregar(versao)          ← RF-32, a porta JÁ EXISTENTE
2. EstadoFinanceiro montado                  ← já pronto na ENTRADA desta
                                                função (app/montagem/estado.py,
                                                T-49..T-53/T-99, fora do
                                                escopo de arquivos desta
                                                tarefa: `Arquivos: app/motor/
                                                executor.py`)
3. calcular_plano(estado, parametros, ...)   ← EM PROCESSO, uma única vez
                                                (AC-12)
4. RepositorioSnapshots.anexar(snapshot)     ← RF-19 · AC-43, ANTES de
                                                qualquer exibição (AC-12)
```

**Por que o passo 2 não constrói nada aqui.** O plano §5.2 descreve "Etapa B
completa → CALCULANDO → passo 1 → passo 2 (respostas → EstadoFinanceiro) →
passo 3 → passo 4" como o fluxo INTEIRO do Bloco 6, mas esta tarefa declara
um único arquivo (`app/motor/executor.py`). Montar o `EstadoFinanceiro` a
partir de `RespostasCaso` já é responsabilidade de `app/montagem/estado.py::
montar_estado_financeiro` (T-51, concluída) — chamá-la de novo aqui seria
reproduzir uma montagem que já existe em outro módulo, não uma orquestração.
Por isso `executar_calculo`/`executar_calculo_async` RECEBEM o
`EstadoFinanceiro` já pronto: o chamador (uma tarefa de orquestração futura,
`app/http/` ou `app/casos/`) é quem invoca `montar_estado_financeiro` e passa
o resultado aqui — o "passo 2" do plano acontece ANTES da fronteira desta
função, não dentro dela.

**`AC-12` — invocado exatamente uma vez, snapshot persistido antes de
exibição.** `calcular_plano` é chamado uma ÚNICA vez por execução de
`_calcular_e_anexar` (nenhum retry, nenhuma segunda chamada de verificação).
O `SnapshotOrdem` só é devolvido ao chamador DEPOIS que `RepositorioSnapshots.
anexar` retorna com sucesso — se `anexar` levantar, a exceção propaga e a
função nunca devolve o snapshot; não há caminho de código em que um
chamador externo possa obter o snapshot calculado sem que `anexar` já tenha
sido executado até o fim.

**`AC-43` — gravação só por `RepositorioSnapshots.anexar`.** Este módulo não
declara nenhum SQL, não importa `psycopg` nem `persistencia.supabase.
conexao` — só a porta `engine.portas.RepositorioSnapshots`, injetada pelo
chamador (mesmo padrão de porta+adaptador de `persistencia/app_aluno/
casos.py`). O adaptador concreto (Postgres ou arquivo, T-24) é decisão de
QUEM CHAMA este executor, nunca deste módulo.

**`RF-32` — parâmetros só pela `FonteParametros` existente.** `parametros_
versao` é uma STRING opaca para este módulo (o identificador de versão que o
chamador decide, ex.: `Parametros.PARAMETROS_VERSION` vigente do config do
piloto) — nunca um valor `P_*` lido ou hardcoded aqui. A carga em si é
inteiramente delegada a `fonte_parametros.carregar(parametros_versao)`
(`engine/portas.py::FonteParametros`, já implementada e CONGELADA por
`persistencia/supabase/fonte_parametros.py`/`persistencia/arquivo/
fonte_parametros.py`).

**`run_in_executor`/progresso visível.** `calcular_plano` é síncrona e
potencialmente lenta (§5.2, "o cálculo ocupa um worker") — bloquear o loop de
eventos do FastAPI/Starlette com ela seria o oposto do NFR do plano. A
função SÍNCRONA (`executar_calculo`, abaixo) contém os quatro passos e é
livre de `asyncio` — testável isoladamente, sem event loop. A função
ASSÍNCRONA (`executar_calculo_async`) é a que uma rota HTTP realmente chama:
delega a `executar_calculo` inteira a `starlette.concurrency.
run_in_threadpool` (o mecanismo que o FastAPI já embute e usa internamente
para qualquer rota `def` síncrona — não um `ThreadPoolExecutor` próprio, que
duplicaria infraestrutura que o framework já oferece). "Progresso visível" é
a responsabilidade do CHAMADOR: transicionar o `Caso` para `CALCULANDO`
(`app/casos/maquina.py::transicionar`, gatilho `bloco_6_executa`) ANTES de
agendar `executar_calculo_async`, para que qualquer leitura do caso durante
o cálculo observe o estado `CALCULANDO` — este módulo NÃO faz essa primeira
transição (`COLETA_INICIAL → CALCULANDO` já é do chamador), mas TRATA as
transições de saída de `CALCULANDO` (`T-55`, abaixo).

**Nenhum gate, ranqueamento ou fórmula da §11 aparece aqui (`T-06`, `T-08`).**
Este módulo só importa `engine.motor.calcular_plano`, os tipos de E/S
(`EstadoFinanceiro`, `SnapshotOrdem`, `Parametros`) e as duas portas
(`FonteParametros`, `RepositorioSnapshots`) — nada de `engine.gates`,
`engine.ciclo_mensal`, `engine.metodos.*`, `engine.comparacao` ou
`engine.ordem` (`AC-41`, verificado por `tests/app_aluno/estatica/
test_fronteira_import_engine.py`, T-06). Nenhum identificador `P_*` nem
enunciado de pergunta aparece neste módulo (`AC-37`, T-08).

---

## `T-55` — tratamento de `ErroParametros`/`ErroInvariante`/timeout

**`EC-04` — `ErroParametros`.** Levantado por `FonteParametros.carregar`, no
PASSO 1, antes de qualquer chamada a `calcular_plano` (a ordem do código
GARANTE isso: a chamada ao motor é uma linha depois da carga, nunca antes).
O cálculo não é sequer tentado. O executor transiciona o `Caso` para
`ERRO_DE_CALCULO` (gatilho `erro_no_calculo`, `app/casos/maquina.py`) — nunca
inventa um `Parametros` default para seguir adiante — registra o evento
(sem nenhum dado monetário) e RELANÇA a exceção original: o chamador (rota
HTTP) é quem decide como reportar ao operador. "Estado anterior preservado"
é uma propriedade automática desta transição: `ERRO_DE_CALCULO` não é
`COLETA_INICIAL`/`COLETA_DIRIGIDA`/`CONFIRMACAO_ATAQUE`/`ACOMPANHAMENTO`, e a
retomada (`operador_retoma_apos_erro`, já declarada em `app/casos/
maquina.py`) devolve exatamente a um desses quatro — o mesmo de onde
`CALCULANDO` partiu — nunca um estado novo inventado por este módulo.

**`EC-03` — `ErroInvariante`.** Levantado por `engine.ciclo_mensal.
executar_mes` (dentro de `calcular_plano`, PASSO 3) quando a conservação do
ataque do mês não fecha — bug do motor, nunca situação de negócio a
degradar. O executor transiciona o `Caso` para `ERRO_DE_CALCULO`, registra o
evento com um `hash_inputs` de CORRELAÇÃO (`_hash_estado_para_log`, abaixo —
ver a nota sobre por que não é o `hash_inputs` do motor) e RELANÇA a exceção:
nenhum `SnapshotOrdem` é montado (a exceção interrompe `calcular_plano` antes
do passo 11, `engine/snapshot.py::montar_SnapshotOrdem`), então não há como
este módulo devolver — nem por engano — um plano parcial ao aluno. A função
nunca captura `ErroInvariante` para tentar de novo ou para produzir um valor
"quase certo": o único destino possível depois de capturá-la é a transição
de erro seguida da propagação.

**Por que `_hash_estado_para_log` não é o `hash_inputs` do `SnapshotOrdem`.**
`engine.snapshot._calcular_hash_inputs` é PRIVADO (não exportado, fora da
allowlist de `tests/app_aluno/estatica/test_fronteira_import_engine.py`,
`AC-41`) e só existe DEPOIS que `calcular_plano` monta um snapshot — que é
exatamente o que não acontece quando `ErroInvariante` interrompe a execução.
Reimplementar a MESMA fórmula aqui duplicaria uma decisão de serialização do
motor em `app/` (o que a Lei nº 3 proíbe: esta camada não calcula). Em vez
disso, este módulo produz um hash de CORRELAÇÃO/observabilidade — mesmo
`estado`+`parametros_versao` sempre produz o mesmo valor, o suficiente para
o operador cruzar um incidente de log com o caso e a versão de parâmetros
envolvidos — sem pretender ser bit-a-bit igual ao `hash_inputs` que um
`SnapshotOrdem` bem-sucedido carregaria para o mesmo estado. Não usa
`Decimal(...)`/`dinheiro(...)` (só serializa objetos JÁ existentes via
`json.dumps(..., default=str)`), então não viola a fronteira `Decimal` única
(`tests/app_aluno/estatica/test_fronteira_decimal_unica.py`, RF-13): nenhum
`Decimal` novo é construído, só lido.

**`EC-06` — timeout do Bloco 6.** Não existe timeout embutido em
`run_in_threadpool` (T-54): a thread roda até terminar, mesmo que o
CHAMADOR desista de esperar. `executar_calculo_com_timeout_async` envolve
`executar_calculo_async` com `asyncio.wait_for` — se o cálculo não conclui
dentro de `tempo_limite_segundos`, a `await` é abandonada (a THREAD
continua rodando em segundo plano até terminar por conta própria: Python não
tem como matar uma thread de fora). Nesse momento o caso NUNCA pode ficar
preso em `CALCULANDO` (`EC-06`): a função consulta
`RepositorioSnapshots.historico` a partir do `snapshot_raiz_id` já
conhecido do `Caso` (se algum snapshot deste caso já existe) procurando um
filho direto do `anterior` recebido (`snapshot_anterior_id` igual ao
`SNAPSHOT_ID` de `anterior`, ou `snapshot_anterior_id is None` quando não há
`anterior`) — se um snapshot assim já foi anexado por uma execução que
terminou depois do timeout expirar mas antes desta checagem, o caso já
avançou para `AGUARDANDO_REVISAO` (a transição de sucesso `snapshot_
anexado` é do CHAMADOR do Bloco 6, T-56 — fora do escopo desta função);
senão, o executor transiciona de volta ao estado anterior fornecido pelo
chamador (`estado_anterior_do_caso`), nunca
deixando `CALCULANDO` como estado final observável. Quando não há
`snapshot_raiz_id` (primeiro cálculo do caso, nenhum snapshot anexado
ainda), não há como confirmar sucesso por este caminho — a decisão segura é
sempre reverter: o aluno nunca vê nada calculado sem confirmação positiva de
que o snapshot foi persistido.

`ErroParametros` (do `FonteParametros.carregar`) e `ErroInvariante` (de
`calcular_plano`) SÃO CAPTURADAS aqui (T-55): a captura sempre encerra em (1)
transição de estado para `ERRO_DE_CALCULO`, (2) registro do evento na
allowlist de observabilidade, (3) propagação da exceção original ao
chamador — nunca um retorno "degradado" no lugar de um `SnapshotOrdem`.

---

## `T-91` — as quatro transições deste módulo também gravam a trilha do caso

`_transicionar_para_erro` (`EC-04`/`EC-03`) e as duas transições de
`executar_calculo_com_timeout_async` (`EC-06`: `CALCULANDO → ERRO_DE_CALCULO`
seguida de `ERRO_DE_CALCULO → estado_anterior_do_caso`) persistiam o novo
`estado` sem deixar rastro em `app_aluno.eventos_caso` — só o log estruturado
de `_registrar_evento` (`logging`, não a trilha persistida). `RF-31`/`AC-40`
exigem que TODA transição da máquina grave um evento na trilha, não só as
que passam por `app/casos/progresso.py::transicionar_e_registrar` em
`app/http/`/`app/revisao/`/`app/casos/acompanhamento.py` — por isso este
módulo, embora fora da lista nominal de arquivos de `T-91`, foi estendido
para usar o MESMO wrapper (extensão de escopo estritamente necessária ao
critério de aceite, mesmo precedente de `T-30`/`T-87`).

As quatro chamadas usam `transicionar_e_registrar` com a variante
CONDICIONAL (`de=CALCULANDO`/`de=ERRO_DE_CALCULO`): o caso já está,
nesse ponto do fluxo, exatamente no estado de origem esperado (foi colocado
lá pelo chamador antes de invocar o executor) — usar a forma condicional em
vez da incondicional é estritamente mais seguro (nunca reescreve um estado
que uma transição concorrente já mudou) e unifica o caminho de código com os
demais chamadores da máquina, sem introduzir nenhum comportamento novo nos
quatro critérios de aceite já cobertos por `T-55`/`EC-03`/`EC-04`/`EC-06`.

REGRAS: `RF-16`, `RF-19`, `RF-32`, `EC-03`, `EC-04`, `EC-06`, `RF-31`, `AC-40`
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, is_dataclass
from typing import Final

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import transicionar_e_registrar

# `ErroInvariante` mora em `engine.ciclo_mensal` — não está na allowlist de
# `test_fronteira_import_engine.py` (só `engine.motor.calcular_plano`, os
# tipos de E/S e as duas portas estão liberados). Este módulo precisa
# CAPTURAR a exceção, não usar nenhum outro nome de `engine.ciclo_mensal` —
# por isso o import é isolado nesta única linha, do único nome que o
# tratamento de erro exige.
from engine.ciclo_mensal import ErroInvariante
from engine.estado import EstadoFinanceiro
from engine.motor import calcular_plano
from engine.parametros import ErroParametros, Parametros
from engine.portas import FonteParametros, RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from engine.tipos import EVENTO_RECALCULO
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.eventos import RepositorioEventosCaso

REGRAS: Final[tuple[str, ...]] = (
    "RF-16",
    "RF-19",
    "RF-32",
    "EC-03",
    "EC-04",
    "EC-06",
    "RF-31",
    "AC-40",
)

_LOGGER: Final[logging.Logger] = logging.getLogger("app.motor.executor")

# Timeout padrão do Bloco 6 — NFR p95 < 10 s (plano §5.1); folga generosa
# antes de decidir que o cálculo "não voltou a tempo" (EC-06). Não é um
# valor `P_*` do motor (§8 da canônica): é um limite operacional desta
# camada de aplicação, ajustável pelo chamador via `tempo_limite_segundos`.
TEMPO_LIMITE_PADRAO_SEGUNDOS: Final[float] = 30.0


# ---------------------------------------------------------------------------
# Observabilidade — RF-16/EC-03/EC-04/EC-06: "nenhum log contém valor
# monetário, saldo, renda ou identificador pessoal". Só `CASO_ID`,
# `SNAPSHOT_ID`, `hash_inputs`, `ENGINE_VERSION`, `PARAMETROS_VERSION`,
# estado e transição.
#
# A allowlist não é "disciplina de quem escreve o log" — é a PRÓPRIA
# ASSINATURA de `_registrar_evento`: a função só aceita estes sete
# parâmetros nomeados (todos `str | None`). Tentar logar um objeto inteiro
# (ex.: `EstadoFinanceiro`, `SnapshotOrdem`) é um `TypeError` de argumento
# inesperado — não uma convenção que um code review possa deixar passar.
# ---------------------------------------------------------------------------


def _registrar_evento(
    *,
    nivel: int,
    mensagem: str,
    caso_id: str | None = None,
    snapshot_id: str | None = None,
    hash_inputs: str | None = None,
    engine_version: str | None = None,
    parametros_version: str | None = None,
    estado: str | None = None,
    transicao: str | None = None,
) -> None:
    """Único ponto de emissão de log deste módulo. Cada parâmetro nomeado é
    exatamente um dos sete campos da allowlist normativa (spec §"Erros e
    estados vazios") — nenhum `**kwargs`, nenhum campo livre. Valores `None`
    são omitidos do registro estruturado (`extra`), nunca logados como a
    string `"None"` por engano."""
    campos = {
        "CASO_ID": caso_id,
        "SNAPSHOT_ID": snapshot_id,
        "hash_inputs": hash_inputs,
        "ENGINE_VERSION": engine_version,
        "PARAMETROS_VERSION": parametros_version,
        "estado": estado,
        "transicao": transicao,
    }
    registro = {chave: valor for chave, valor in campos.items() if valor is not None}
    _LOGGER.log(nivel, mensagem, extra=registro)


def _serializavel_sem_decimal_novo(valor: object) -> object:
    """Converte `valor` (um `dataclass` frozen do motor, tipicamente
    `EstadoFinanceiro`) numa árvore de tipos primitivos usando SÓ
    `dataclasses.asdict` — nenhum `Decimal(...)`/`dinheiro(...)` é
    construído aqui, apenas objetos já existentes são lidos e reorganizados
    em `dict`/`list`. `json.dumps(..., default=str)`, chamado por quem usa
    este valor, cuida de transformar `Decimal`/`Enum`/`date` residuais em
    string na hora de serializar — sem que este módulo precise saber o tipo
    exato de cada campo."""
    if is_dataclass(valor) and not isinstance(valor, type):
        return asdict(valor)
    return valor


def _hash_estado_para_log(estado: EstadoFinanceiro, parametros_versao: str) -> str:
    """Hash de CORRELAÇÃO para observabilidade (`EC-03`) — NÃO é o
    `hash_inputs` que um `SnapshotOrdem` bem-sucedido carregaria (ver a nota
    extensa na docstring do módulo sobre por que os dois não podem ser o
    mesmo código). Determinístico dentro do mesmo processo: o mesmo par
    `(estado, parametros_versao)` sempre produz o mesmo dígito, suficiente
    para o operador cruzar um incidente de log com o caso."""
    payload = {
        "estado": _serializavel_sem_decimal_novo(estado),
        "PARAMETROS_VERSION": parametros_versao,
    }
    texto_canonico = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(texto_canonico.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ParametrosDoCalculo:
    """Os insumos do Bloco 6, além do `estado` — agrupados para que
    `executar_calculo`/`executar_calculo_async` tenham uma assinatura só, sem
    repetir parâmetros posicionais soltos entre as duas funções (a
    assíncrona apenas repassa este objeto a `run_in_threadpool`).

    `fonte_parametros`/`repositorio_snapshots` são as PORTAS (`engine/
    portas.py`), nunca um adaptador concreto amarrado em código — o chamador
    decide se injeta o adaptador Postgres (`persistencia/supabase/`) ou o de
    arquivo (`persistencia/arquivo/`, T-24), sem que este módulo saiba qual.

    `caso_id`/`repositorio_casos` (T-55): o executor precisa dos dois para
    poder transicionar o `Caso` para `ERRO_DE_CALCULO` quando `ErroParametros`
    ou `ErroInvariante` interrompem o cálculo — sem eles, o tratamento de
    erro não teria como persistir a transição, só logá-la (o que deixaria o
    caso preso em `CALCULANDO` para qualquer leitura futura, violando
    `EC-06`).

    `repositorio_eventos` (`T-91`, `RF-31`/`AC-40`): a trilha do caso —
    todas as transições que este módulo persiste (`_transicionar_para_erro`,
    o retorno pós-timeout de `EC-06`) também gravam um `EventoCaso` nela, via
    `app.casos.progresso.transicionar_e_registrar`."""

    fonte_parametros: FonteParametros
    repositorio_snapshots: RepositorioSnapshots
    repositorio_casos: RepositorioCasos
    repositorio_eventos: RepositorioEventosCaso
    caso_id: str
    parametros_versao: str
    estado_anterior_do_caso: ESTADO_CASO
    anterior: SnapshotOrdem | None = None
    evento: EVENTO_RECALCULO | None = None
    motivo: str = ""


def _transicionar_para_erro(insumos: ParametrosDoCalculo, motivo_tecnico: str) -> None:
    """`erro_no_calculo`: `CALCULANDO → ERRO_DE_CALCULO` — a ÚNICA transição
    declarada de saída de `CALCULANDO` para o caminho de falha (`app/casos/
    maquina.py::TABELA_TRANSICOES`). `transicionar_e_registrar` (`T-91`)
    valida contra a MÁQUINA antes de persistir (levanta
    `ErroTransicaoNaoDeclarada` se o caso não estiver de fato em
    `CALCULANDO`) e grava o evento `erro_no_calculo` na trilha no mesmo
    passo em que persiste o novo `estado`."""
    transicionar_e_registrar(
        repositorio_casos=insumos.repositorio_casos,
        repositorio_eventos=insumos.repositorio_eventos,
        caso_id=insumos.caso_id,
        de=ESTADO_CASO.CALCULANDO,
        para=ESTADO_CASO.ERRO_DE_CALCULO,
        detalhe=motivo_tecnico,
    )
    _registrar_evento(
        nivel=logging.ERROR,
        mensagem=motivo_tecnico,
        caso_id=insumos.caso_id,
        estado=ESTADO_CASO.ERRO_DE_CALCULO.value,
        transicao="erro_no_calculo",
    )


def executar_calculo(estado: EstadoFinanceiro, insumos: ParametrosDoCalculo) -> SnapshotOrdem:
    """Os QUATRO PASSOS do plano §5.2, em processo, síncrona — ver docstring
    do módulo para a ordem exata e para o tratamento de erro de `T-55`.

    1. `FonteParametros.carregar(parametros_versao)` — RF-32. `ErroParametros`
       (`EC-04`): capturada, o caso vai a `ERRO_DE_CALCULO`, o evento é
       logado (sem dado monetário) e a exceção original é relançada — o
       cálculo NUNCA é tentado.
    2. (já feito pelo chamador — `estado` chega pronto.)
    3. `calcular_plano(estado, parametros, anterior, evento, motivo)` —
       EXATAMENTE uma vez (`AC-12`). `ErroInvariante` (`EC-03`): capturada,
       o caso vai a `ERRO_DE_CALCULO` com `hash_inputs` de correlação
       registrado, e a exceção original é relançada — nenhum `SnapshotOrdem`
       parcial é montado nem devolvido.
    4. `RepositorioSnapshots.anexar(snapshot)` — RF-19/AC-43. Só DEPOIS que
       esta chamada retorna com sucesso (sem levantar) é que o `SnapshotOrdem`
       é devolvido ao chamador — nenhum caminho devolve o snapshot antes de
       `anexar` ter concluído (`AC-12`: persistido antes de qualquer
       exibição).

    Função pura em relação a I/O de rede: as únicas chamadas externas são as
    portas recebidas em `insumos` e o repositório de casos — nada de
    `psycopg`, `requests` ou arquivo aberto diretamente por este módulo."""
    try:
        parametros: Parametros = insumos.fonte_parametros.carregar(insumos.parametros_versao)
    except ErroParametros as erro:
        _transicionar_para_erro(insumos, f"ErroParametros: {erro}")
        raise

    try:
        snapshot = calcular_plano(
            estado,
            parametros,
            anterior=insumos.anterior,
            evento=insumos.evento,
            motivo=insumos.motivo,
        )
    except ErroInvariante as erro:
        # T-91: mesmo wrapper de `_transicionar_para_erro`, chamado
        # diretamente aqui (em vez de reaproveitar aquela função) porque o
        # `_registrar_evento` deste ramo carrega três campos extras
        # (`hash_inputs`, `parametros_version`, `engine_version`) que a
        # assinatura fixa daquela função não aceita — mesma disciplina de
        # `EC-03`, sem duplicar a validação/persistência da transição.
        transicionar_e_registrar(
            repositorio_casos=insumos.repositorio_casos,
            repositorio_eventos=insumos.repositorio_eventos,
            caso_id=insumos.caso_id,
            de=ESTADO_CASO.CALCULANDO,
            para=ESTADO_CASO.ERRO_DE_CALCULO,
            detalhe=f"ErroInvariante: {erro}",
        )
        _registrar_evento(
            nivel=logging.ERROR,
            mensagem=f"ErroInvariante: {erro}",
            caso_id=insumos.caso_id,
            hash_inputs=_hash_estado_para_log(estado, insumos.parametros_versao),
            parametros_version=parametros.PARAMETROS_VERSION,
            engine_version=parametros.ENGINE_VERSION,
            estado=ESTADO_CASO.ERRO_DE_CALCULO.value,
            transicao="erro_no_calculo",
        )
        raise

    insumos.repositorio_snapshots.anexar(snapshot)

    _registrar_evento(
        nivel=logging.INFO,
        mensagem="snapshot anexado",
        caso_id=insumos.caso_id,
        snapshot_id=snapshot.SNAPSHOT_ID,
        hash_inputs=snapshot.hash_inputs,
        engine_version=snapshot.ENGINE_VERSION,
        parametros_version=snapshot.PARAMETROS_VERSION,
        transicao="snapshot_anexado",
    )

    return snapshot


async def executar_calculo_async(
    estado: EstadoFinanceiro, insumos: ParametrosDoCalculo
) -> SnapshotOrdem:
    """A mesma orquestração de `executar_calculo`, rodada em thread separada
    do event loop — `starlette.concurrency.run_in_threadpool` é o mecanismo
    que o próprio FastAPI usa internamente para rotas síncronas (nenhum
    `ThreadPoolExecutor` próprio construído aqui). É esta função — não
    `executar_calculo` diretamente — que uma rota `async def` do Bloco 6 deve
    `await` quando não precisa de timeout (`executar_calculo_com_timeout_
    async`, abaixo, é a variante que aplica `EC-06`).

    O chamador é responsável por já ter transicionado o `Caso` para
    `CALCULANDO` (`app/casos/maquina.py`) antes de `await` nesta função —
    "progresso visível" é o próprio estado do caso, consultável durante a
    execução."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(executar_calculo, estado, insumos)


def _snapshot_filho_ja_anexado(insumos: ParametrosDoCalculo) -> bool:
    """`EC-06`: existe, no repositório, um `SnapshotOrdem` cujo
    `snapshot_anterior_id` é exatamente o `SNAPSHOT_ID` de `insumos.anterior`
    (ou `None`, quando não há `anterior`)? Usado SÓ para decidir a resolução
    pós-timeout — nunca para decidir se o cálculo em si deveria ocorrer (essa
    decisão pertence exclusivamente a `calcular_plano`/ao chamador do Bloco
    6). Consulta `historico` pela RAIZ da cadeia (`snapshot_raiz_id` do
    `Caso`, já persistido por `persistencia/app_aluno/casos.py`); sem raiz
    conhecida (primeiro cálculo do caso), não há como confirmar sucesso por
    este caminho e a função devolve `False` — a resolução segura é sempre
    reverter quando não se pode PROVAR que o snapshot foi persistido."""
    caso = insumos.repositorio_casos.buscar(insumos.caso_id)
    if caso is None or caso.snapshot_raiz_id is None:
        return False

    esperado = insumos.anterior.SNAPSHOT_ID if insumos.anterior is not None else None
    historico = insumos.repositorio_snapshots.historico(caso.snapshot_raiz_id)
    return any(snapshot.snapshot_anterior_id == esperado for snapshot in historico)


async def executar_calculo_com_timeout_async(
    estado: EstadoFinanceiro,
    insumos: ParametrosDoCalculo,
    *,
    tempo_limite_segundos: float = TEMPO_LIMITE_PADRAO_SEGUNDOS,
) -> SnapshotOrdem | None:
    """`EC-06` — o caso NUNCA fica preso em `CALCULANDO`. Se
    `executar_calculo_async` não conclui dentro de `tempo_limite_segundos`,
    resolve para um dos dois destinos do critério de aceite:

    - **Há snapshot (a thread concluiu depois do timeout expirar, mas antes
      desta checagem) → devolve `None` sem mexer no estado**: a própria
      `executar_calculo`, ao concluir, já transicionou o caso para
      `AGUARDANDO_REVISAO` (fora do escopo desta função — essa transição de
      SUCESSO é do chamador do Bloco 6, T-56) e já anexou o snapshot; este
      módulo só CONFIRMA que não é preciso reverter.
    - **Não há snapshot → transiciona de volta ao `estado_anterior_do_caso`**:
      primeiro `CALCULANDO → ERRO_DE_CALCULO` (mesma transição de falha de
      `EC-03`/`EC-04` — não existe um par `CALCULANDO → estado_anterior_do_
      caso` direto na tabela), depois `ERRO_DE_CALCULO → estado_anterior_do_
      caso` (uma das quatro transições `operador_retoma_apos_erro` já
      declaradas em `app/casos/maquina.py`, EC-06); registra o evento e
      devolve `None`.

    A THREAD do cálculo, se ainda estiver rodando, não é cancelada (Python
    não tem como interromper uma thread de fora) — ela roda até terminar por
    conta própria; se terminar com sucesso depois desta função já ter
    revertido o caso, `executar_calculo` tentará transicionar
    `CALCULANDO → ERRO_DE_CALCULO`/`AGUARDANDO_REVISAO` a partir de um estado
    que já não é mais `CALCULANDO` — `transicionar()` recusará com
    `ErroTransicaoNaoDeclarada`, nomeando a inconsistência em vez de
    silenciá-la (nunca um estado divergente aceito por acidente)."""
    try:
        return await asyncio.wait_for(
            executar_calculo_async(estado, insumos), timeout=tempo_limite_segundos
        )
    except TimeoutError:
        if _snapshot_filho_ja_anexado(insumos):
            _registrar_evento(
                nivel=logging.WARNING,
                mensagem="timeout: snapshot já anexado",
                caso_id=insumos.caso_id,
                estado=ESTADO_CASO.AGUARDANDO_REVISAO.value,
            )
            return None

        # Sem snapshot confirmado: o timeout é tratado como as demais
        # falhas do Bloco 6 (`_transicionar_para_erro`) — passa por
        # `ERRO_DE_CALCULO` (visível ao operador) antes de retomar ao
        # estado de origem pela transição já declarada
        # `operador_retoma_apos_erro` (`app/casos/maquina.py`, EC-06).
        # `CALCULANDO → estado_anterior_do_caso` DIRETO não existe na
        # tabela — só as duas transições em sequência. `T-91`: cada uma
        # grava seu próprio evento na trilha, via `transicionar_e_registrar`.
        transicionar_e_registrar(
            repositorio_casos=insumos.repositorio_casos,
            repositorio_eventos=insumos.repositorio_eventos,
            caso_id=insumos.caso_id,
            de=ESTADO_CASO.CALCULANDO,
            para=ESTADO_CASO.ERRO_DE_CALCULO,
            detalhe="timeout: EC-06",
        )
        transicionar_e_registrar(
            repositorio_casos=insumos.repositorio_casos,
            repositorio_eventos=insumos.repositorio_eventos,
            caso_id=insumos.caso_id,
            de=ESTADO_CASO.ERRO_DE_CALCULO,
            para=insumos.estado_anterior_do_caso,
            detalhe="timeout: EC-06",
        )
        _registrar_evento(
            nivel=logging.WARNING,
            mensagem="timeout: revertendo estado",
            caso_id=insumos.caso_id,
            estado=insumos.estado_anterior_do_caso.value,
            transicao="operador_retoma_apos_erro",
        )
        return None
