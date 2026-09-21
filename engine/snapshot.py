"""Montagem e carimbo do `SnapshotOrdem` — RF-10 · `V-01..V-03` · AC-16 ·
AC-18 · T-67.

`SnapshotOrdem` é o registro IMUTÁVEL final de uma rodada de cálculo do
motor — §4 do plano técnico (`plans/motor-calculo.plan.md`, linhas
556-594). Une, num único objeto `frozen=True, slots=True`, tudo que as
tarefas anteriores já produziram (`Diagnostico`, os três `Cenario`,
`ComparacaoCenarios`, `ResultadoMetodoRecomendado`, `ResultadoOrdemPublicada`)
mais o carimbo de versão (`V-03`, `AC-16`) e a cadeia de encadeamento
(`V-01`, `V-02`).

**Escopo desta tarefa — só a MONTAGEM, nunca a orquestração.**
`montar_SnapshotOrdem` recebe cada resultado JÁ CALCULADO pelos módulos de
`T-20`..`T-66` como parâmetro — não chama `calcular_diagnostico`,
`simular_cenario`, `comparar_cenarios`, `derivar_METODO_RECOMENDADO_PIQ` nem
`publicar_ORDEM_QUITACAO` internamente. Orquestrar os 11 passos do fluxo de
dados da §5 do plano (carga de parâmetros → derivações → diagnóstico →
gates → cenários → comparação → status → ordem → snapshot) é
`engine/motor.py::calcular_plano` — `T-68`, fora do escopo desta tarefa.
Esta função é o ÚLTIMO passo desse fluxo (passo 11), isolado para que
`calcular_plano` não precise conhecer o formato interno do carimbo.

## `V-01` — nunca sobrescrever, sempre encadear

`snapshot_anterior_id` aponta para o `SNAPSHOT_ID` do snapshot anterior
(`anterior.SNAPSHOT_ID`, quando existir) — cadeia imutável, tipo blockchain
simples. `versao` incrementa a cada novo snapshot na cadeia
(`anterior.versao + 1`, começando em 1 quando não há anterior). Nada aqui
sobrescreve o snapshot anterior: `montar_SnapshotOrdem` sempre CRIA um objeto
novo; o snapshot anterior, se recebido, não é mutado (é `frozen`, T-08/T-46
mesmo padrão) nem descartado — apenas referenciado por `SNAPSHOT_ID`.

## `V-02` — nada se perde

`DATA_REFERENCIA`, `MOTIVO_RECALCULO`, `EVENTO_RECALCULO`, os inputs
(`estado_inputs`), o método recomendado, a dívida-alvo e as justificativas de
cada posição da ordem (`PosicaoOrdem.JUSTIFICATIVA_POSICAO`, já dentro de
`ORDEM_QUITACAO`) — tudo é campo de primeira classe do snapshot, acessível
sem decodificação adicional (`AC-18`).

`DATA_REFERENCIA` do snapshot é `estado_inputs.DATA_REFERENCIA` — o motor não
lê relógio (NFR Determinismo, `engine/estado.py`); a data de referência do
cálculo é sempre a que já chegou como entrada do `EstadoFinanceiro`, nunca
`date.today()`.

`DIVIDA_ALVO_ATUAL`/`PROXIMA_DIVIDA` são lidos da PRIMEIRA e da SEGUNDA
posições de `ORDEM_QUITACAO` publicada (`ResultadoOrdemPublicada.
ORDEM_QUITACAO`, já ordenada por `publicar_ORDEM_QUITACAO`, T-63) — nunca
recalculados aqui: `ORDEM_QUITACAO` vazia (`EC-17`, nenhuma dívida elegível)
implica `DIVIDA_ALVO_ATUAL = None`.

## `V-03`/`AC-16` — carimbo de versão em toda saída

`ENGINE_VERSION` e `PARAMETROS_VERSION` já são campos de `Parametros`
(`engine/parametros.py`, T-07) — carregados da mesma fonte externa
(`parameters/parametros-1.0.1.json`) que fornece os `P_*` usados no cálculo.
`montar_SnapshotOrdem` apenas os REPASSA para o snapshot (`parametros.
ENGINE_VERSION`, `parametros.PARAMETROS_VERSION`) — nunca um literal novo,
nunca uma constante duplicada em `engine/snapshot.py`: a versão do motor e a
versão dos parâmetros usados são o MESMO dado, lido uma vez, carimbado aqui.

## `SNAPSHOT_ID` — derivado, nunca `uuid4()`

`SNAPSHOT_ID` é `hash_inputs` combinado com `versao` (§7 do plano: "SNAPSHOT_ID
é derivado de hash_inputs + versao"). Dado o mesmo `hash_inputs` e a mesma
`versao`, o `SNAPSHOT_ID` é sempre idêntico — condição de determinismo
(`tests/estatica/test_motor_e_deterministico.py`, que varre `engine/` e
falharia se este módulo importasse `uuid4`). `_calcular_hash_inputs` produz
`hash_inputs`: `sha256` sobre uma representação canônica e ESTÁVEL do
`EstadoFinanceiro` (a carteira de dívidas está embutida em
`EstadoFinanceiro.dividas`) e da `PARAMETROS_VERSION` usada — nunca sobre
`repr()` de objeto Python (não determinístico entre versões/processos) nem
sobre `id()`/endereço de memória. Ver `_serializar_canonico` abaixo.

REGRAS: Final[tuple[str, ...]] = ("RF-10", "V-01", "V-02", "V-03", "AC-16", "AC-18")
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Final

from engine.ciclo_mensal import Cenario
from engine.comparacao import ComparacaoCenarios
from engine.diagnostico import Diagnostico
from engine.estado import EstadoFinanceiro
from engine.gates import AcaoRequerida
from engine.ordem import PosicaoOrdem, ResultadoOrdemPublicada
from engine.parametros import Parametros
from engine.status_metodo import ResultadoMetodoRecomendado
from engine.tipos import EVENTO_RECALCULO, METODO, ORDEM_STATUS, STATUS_METODO

REGRAS: Final[tuple[str, ...]] = ("RF-10", "V-01", "V-02", "V-03", "AC-16", "AC-18")


@dataclass(frozen=True, slots=True)
class SnapshotOrdem:
    """§4 do plano técnico (`plans/motor-calculo.plan.md`, linhas 564-586) —
    registro IMUTÁVEL final de uma rodada de cálculo do motor. `frozen=True,
    slots=True`: não existe setter, não existe campo mutável, não existe
    caminho de sobrescrita de nenhum campo depois de montado (critério de
    aceite 5 de `T-67`) — mesma trava estrutural já usada por `Divida`/
    `EstadoFinanceiro` (T-08), `ResultadoStatusMetodo` (T-60) e
    `ResultadoOrdemPublicada` (T-63).
    """

    SNAPSHOT_ID: str
    versao: int  # ORDEM_QUITACAO_V1, V2, ... — V-01
    snapshot_anterior_id: str | None  # cadeia preservada — V-01
    DATA_REFERENCIA: date
    MOTIVO_RECALCULO: str
    EVENTO_RECALCULO: EVENTO_RECALCULO | None
    hash_inputs: str  # sha-256 canônico do estado — nunca uuid4()
    estado_inputs: EstadoFinanceiro  # V-02: inputs relevantes
    diagnostico: Diagnostico
    cenarios: Mapping[METODO, Cenario]
    comparacao: ComparacaoCenarios
    METODO_RECOMENDADO_PIQ: METODO
    STATUS_METODO: STATUS_METODO
    ORDEM_STATUS: ORDEM_STATUS
    REVISAO_HUMANA_OBRIGATORIA: bool
    DIVIDA_ALVO_ATUAL: str | None
    PROXIMA_DIVIDA: str | None
    ORDEM_QUITACAO: tuple[PosicaoOrdem, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]
    ENGINE_VERSION: str  # V-03 · AC-16
    PARAMETROS_VERSION: str  # V-03 · AC-16


def _serializar_canonico(valor: object) -> object:
    """Converte recursivamente um valor do motor numa forma que
    `json.dumps(..., sort_keys=True)` serializa de modo ESTÁVEL entre
    execuções e processos — a base de `_calcular_hash_inputs`.

    Nunca usa `repr()` de objeto Python (a representação de um `dataclass`
    inclui o endereço de campos não determinísticos em alguns tipos, e a
    ordem de atributos de um `Mapping`/`set` comum não é garantida entre
    processos) nem `id()`/endereço de memória. Cada tipo do motor tem uma
    conversão explícita e determinística:

    - `Decimal` -> `str` (RF-12/G-01: nunca perder precisão via `float`, e
      `str(Decimal(...))` é estável e exato — mesma regra de serialização
      já adotada para persistência, §6 do plano: "Decimal sempre vira
      string em JSON").
    - `Enum` (inclusive `Desconhecido`/`DESCONHECIDO`) -> `.value` (string).
    - `date` -> `.isoformat()`.
    - `dataclass` (frozen, T-08/T-46) -> dict ordenado por nome de campo.
    - `tuple`/`list` -> lista, preservando ORDEM (uma tupla é sequência
      significativa no motor — `EstadoFinanceiro.dividas`, `ORDEM_QUITACAO`
      — trocar a ordem muda o significado, não deve ser normalizada).
    - `frozenset`/`set` -> lista ORDENADA (`MECANISMO_DEFICIT`, T-08): um
      `frozenset` não tem ordem própria: para o hash ser determinístico
      entre processos, os elementos são ordenados antes de serializar.
    - `Mapping`/`dict` -> dict com chaves convertidas a `str` (`METODO` como
      chave de `cenarios`, por exemplo) e ordenadas por `json.dumps(...,
      sort_keys=True)` na chamada externa.
    - `None`, `str`, `int`, `bool` -> devolvidos como estão (já são
      serializáveis por natureza e já deterministas).
    """
    if valor is None or isinstance(valor, (str, int, bool)):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Mapping):
        return {
            str(_serializar_canonico(chave)): _serializar_canonico(item)
            for chave, item in valor.items()
        }
    if isinstance(valor, (frozenset, set)):
        # RF-12/determinismo: sem ordem própria — ordena a representação
        # canônica (já strings/valores primitivos) antes de listar.
        return sorted(_serializar_canonico(item) for item in valor)  # type: ignore[type-var]
    if isinstance(valor, (tuple, list)):
        return [_serializar_canonico(item) for item in valor]
    if hasattr(valor, "__dataclass_fields__"):
        # dataclass frozen do motor (EstadoFinanceiro, Divida,
        # PerfilComportamental, SinaisComportamentais, ...): serializa por
        # nome de campo, em ordem alfabética (json.dumps(sort_keys=True) já
        # ordena o dict resultante — a ordenação aqui só documenta a
        # intenção, o sort_keys externo é o que garante o determinismo).
        campos = valor.__dataclass_fields__
        return {
            nome: _serializar_canonico(getattr(valor, nome))
            for nome in sorted(campos)
        }
    raise TypeError(
        f"_serializar_canonico não sabe converter {type(valor).__name__!r} — "
        "tipo novo em EstadoFinanceiro/Divida precisa de um ramo explícito "
        "aqui (nunca repr()/id(), RF-10/determinismo)."
    )


def _calcular_hash_inputs(estado: EstadoFinanceiro, parametros: Parametros) -> str:
    """`sha256` canônico e determinístico sobre `estado` (a carteira de
    dívidas já está embutida em `EstadoFinanceiro.dividas`) e
    `PARAMETROS_VERSION` (a versão dos `P_*` efetivamente usados no
    cálculo — parâmetros são imutáveis por versão, T-07, então a versão já
    identifica os valores sem serializar o mapa inteiro de `Parametros.
    _valores`).

    `json.dumps(..., sort_keys=True)` sobre a representação canônica
    (`_serializar_canonico`) garante ordem de chave estável independente da
    ordem de inserção do dict Python — condição de reprodutibilidade entre
    execuções e processos (mesma entrada -> mesmo hash, sempre).
    """
    payload = {
        "estado_inputs": _serializar_canonico(estado),
        "PARAMETROS_VERSION": parametros.PARAMETROS_VERSION,
    }
    texto_canonico = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(texto_canonico.encode("utf-8")).hexdigest()


def montar_SnapshotOrdem(
    *,
    estado: EstadoFinanceiro,
    parametros: Parametros,
    diagnostico: Diagnostico,
    cenarios: Mapping[METODO, Cenario],
    comparacao: ComparacaoCenarios,
    resultado_metodo: ResultadoMetodoRecomendado,
    ordem_status: ORDEM_STATUS,
    ordem_publicada: ResultadoOrdemPublicada,
    evento: EVENTO_RECALCULO | None,
    motivo: str,
    anterior: SnapshotOrdem | None = None,
) -> SnapshotOrdem:
    """`RF-10` · `V-01..V-03` · `AC-16` · `AC-18` — monta e carimba o
    `SnapshotOrdem` final a partir dos resultados JÁ CALCULADOS pelos
    módulos anteriores (`Diagnostico`, os `Cenario` dos três métodos,
    `ComparacaoCenarios`, `ResultadoMetodoRecomendado`,
    `ResultadoOrdemPublicada`). Não recalcula nenhum deles — apenas
    envelopa, encadeia e carimba (mesmo padrão de composição de
    `publicar_ORDEM_QUITACAO`/`Q-04`: este módulo não decide nada que outro
    módulo já decidiu, só consolida).

    `evento`/`motivo` são repassados tal como o chamador os recebeu de
    `avaliar_gatilho_recalculo` (`engine/eventos.py`, T-66) — este módulo
    não decide SE deve recalcular (isso já aconteceu antes de chamar
    `montar_SnapshotOrdem`; T-68 orquestra), só registra o motivo no
    snapshot para auditoria (`V-02`).

    `anterior`, quando fornecido, encadeia `snapshot_anterior_id =
    anterior.SNAPSHOT_ID` e incrementa `versao = anterior.versao + 1`
    (`V-01`). Sem anterior (primeiro snapshot do caso), `snapshot_anterior_id
    = None` e `versao = 1`.

    `DIVIDA_ALVO_ATUAL`/`PROXIMA_DIVIDA` são lidos das duas primeiras
    posições de `ordem_publicada.ORDEM_QUITACAO` (já ordenada por
    `publicar_ORDEM_QUITACAO`) — `None` quando a ordem está vazia (`EC-17`,
    nenhuma dívida elegível).
    """
    hash_inputs = _calcular_hash_inputs(estado, parametros)
    versao = 1 if anterior is None else anterior.versao + 1
    snapshot_anterior_id = None if anterior is None else anterior.SNAPSHOT_ID

    # SNAPSHOT_ID: derivado de hash_inputs + versao — NUNCA uuid4() (§7 do
    # plano). Mesmo hash_inputs, mesma versao => mesmo SNAPSHOT_ID sempre,
    # em qualquer processo (tests/regras/test_snapshot.py cobre isso).
    snapshot_id = hashlib.sha256(f"{hash_inputs}:{versao}".encode()).hexdigest()

    posicoes = ordem_publicada.ORDEM_QUITACAO
    divida_alvo_atual = posicoes[0].DIVIDA_ID if posicoes else None
    proxima_divida = posicoes[1].DIVIDA_ID if len(posicoes) > 1 else None

    return SnapshotOrdem(
        SNAPSHOT_ID=snapshot_id,
        versao=versao,
        snapshot_anterior_id=snapshot_anterior_id,
        DATA_REFERENCIA=estado.DATA_REFERENCIA,
        MOTIVO_RECALCULO=motivo,
        EVENTO_RECALCULO=evento,
        hash_inputs=hash_inputs,
        estado_inputs=estado,
        diagnostico=diagnostico,
        cenarios=cenarios,
        comparacao=comparacao,
        METODO_RECOMENDADO_PIQ=resultado_metodo.METODO_RECOMENDADO_PIQ,
        STATUS_METODO=resultado_metodo.STATUS_METODO,
        ORDEM_STATUS=ordem_status,
        REVISAO_HUMANA_OBRIGATORIA=resultado_metodo.REVISAO_HUMANA_OBRIGATORIA,
        DIVIDA_ALVO_ATUAL=divida_alvo_atual,
        PROXIMA_DIVIDA=proxima_divida,
        ORDEM_QUITACAO=posicoes,
        ORDEM_ACOES=ordem_publicada.ORDEM_ACOES,
        ENGINE_VERSION=parametros.ENGINE_VERSION,
        PARAMETROS_VERSION=parametros.PARAMETROS_VERSION,
    )
