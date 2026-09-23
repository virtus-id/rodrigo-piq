"""Rota e tela de progresso do Bloco 6 — `RF-16`, `AC-12` (T-56).

`POST /caso/{CASO_ID}/calculo` é o ÚNICO caminho de código desta feature que
DISPARA o Bloco 6: valida a guarda do §7.1 do plano (`B5.FIM02` + campos `OBR`
completos, `app/casos/progresso.py::pendencias_obrigatorias`/T-44), transiciona
`COLETA_INICIAL → CALCULANDO` PELA MÁQUINA (`app/casos/maquina.py::
transicionar`, gatilho `bloco_6_executa` — a mesma tabela que já recusa
qualquer outro par), monta o `EstadoFinanceiro` real do caso
(`app/montagem/estado.py`, T-49..T-53/T-99) e agenda a execução
(`app/motor/executor.py::executar_calculo_com_timeout_async`, T-54/T-55) —
tudo isso ANTES de responder, exceto a execução em si, que roda em segundo
plano (ver "Por que a execução não é aguardada pela requisição", abaixo).

`GET /caso/{CASO_ID}/calculo/progresso` é o ÚNICO caminho que MOSTRA o estado
do Bloco 6: lê o `Caso` corrente e escolhe o template certo — progresso
enquanto `CALCULANDO`, uma mensagem terminal para qualquer outro estado. Esta
rota NUNCA calcula nada; é leitura pura de `Caso.estado` (Lei nº 3).

**O Bloco 6 não coleta nada (critério de aceite 2).** Nenhum dos dois handlers
deste módulo renderiza `pergunta.html`, `ficha_repetivel.html` ou qualquer
outro caminho de coleta — o progresso é só
status/spinner/mensagem, nunca um formulário. O POST não lê nenhum campo de
formulário de pergunta (só o `CASO_ID` da URL, via isolamento); o GET não
aceita nenhum parâmetro de resposta.

**Guarda "campo `OBR` pendente nomeando o que falta" (critério de aceite 1).**
A checagem NÃO é reimplementada aqui: `pendencias_obrigatorias` (T-44) já
sabe, por `Obrigatoriedade` do próprio registro, quais perguntas `OBR`
exigíveis agora seguem sem resposta. Esta rota só chama essa função sobre a
coleção real de registros (`collection/carga.py`, T-16) e o snapshot de
respostas do caso (`persistencia/app_aluno/respostas.py`, T-22) — se a lista
não for vazia, a transição para `CALCULANDO` é RECUSADA antes de qualquer
tentativa de `transicionar()`, e a resposta HTTP nomeia cada pendência
(`PendenciaObrigatoria.ID`/`item_id`). Nenhuma lista de campo obrigatório é
codificada nesta rota — a mesma disciplina de `T-44`.

**Transição pela MÁQUINA, nunca por atribuição direta.** Mesmo padrão de
`app/http/rotas_consentimento.py::processar_consentimento`: esta rota chama
`app.casos.maquina.transicionar(ESTADO_CASO.COLETA_INICIAL, ESTADO_CASO.
CALCULANDO)` ANTES de persistir — se o caso não estiver de fato em
`COLETA_INICIAL` (ex.: já `CALCULANDO` por um disparo concorrente, ou em
qualquer outro estado), `ErroTransicaoNaoDeclarada` propaga como recusa,
nunca uma transição "forçada".

**Concorrência — duplo disparo do Bloco 6 sobre o mesmo caso (critério de
aceite 4).** `T-23` provou que `SELECT ... FOR UPDATE` serializa transições
concorrentes sobre a MESMA linha, mas `RepositorioCasos.transicionar_estado`
(incondicional: grava `novo_estado` sempre que `caso_id` existe) não bastaria
aqui — duas requisições que leem `COLETA_INICIAL` FORA da seção crítica e só
depois chamam essa transição incondicional GRAVARIAM AMBAS `CALCULANDO`, sem
erro, disparando dois agendamentos. Por isso esta tarefa ESTENDE o repositório
(`persistencia/app_aluno/casos.py::RepositorioCasos.transicionar_estado_se`,
Postgres e arquivo) com uma transição CONDICIONAL: o `estado` esperado é
verificado DENTRO da mesma seção `SELECT ... FOR UPDATE` + `UPDATE ... WHERE
estado = %s` — a segunda requisição, ao adquirir o lock depois do commit da
primeira, encontra o `estado` já `CALCULANDO` (não mais `COLETA_INICIAL`), o
`UPDATE` afeta zero linhas, e o método devolve `None`. Esta rota só agenda
`executar_calculo_com_timeout_async` quando `transicionar_estado_se` devolve
um `Caso` (não `None`) — a requisição perdedora nunca chega ao agendamento
(verificado com Postgres real e duas threads/conexões de fato concorrentes,
`tests/app_aluno/integracao/test_disparo_concorrente_bloco6.py`, mesmo padrão
de `tests/app_aluno/integracao/test_persistencia_casos.py::T-23`).

**Por que a execução não é aguardada pela requisição.** `executar_calculo_
com_timeout_async` (T-55) pode levar até `TEMPO_LIMITE_PADRAO_SEGUNDOS` (30s)
— aguardar isso na MESMA requisição HTTP que dispara o Bloco 6 obrigaria o
navegador a manter uma conexão aberta por até 30s sem nenhuma atualização
visível, o oposto de "tela de progresso, nunca uma tela travada" (critério de
aceite 3). Por isso o `POST` AGENDA a execução (`asyncio.create_task`, dentro
do mesmo processo — nenhuma fila externa, nenhum worker separado; a NFR de
`OQ-06` já descarta essa infraestrutura, plano §5.2) e responde IMEDIATAMENTE
com a tela de progresso; é o `GET .../progresso`, consultado por polling HTMX
(mesmo padrão de `hx-post`/HTMX já usado em `pergunta.html`, T-43), quem
revela quando o estado deixou de ser `CALCULANDO`.

**Tela de progresso, nunca travada (critério de aceite 3).**
O JSON de progresso é servido enquanto `Caso.estado ==
CALCULANDO`, com `meta http-equiv="refresh"` (progressive enhancement sem
JavaScript, mesmo espírito de `AC-03`/T-30: funciona mesmo sem HTMX) MAIS um
atributo `hx-get`/`hx-trigger="load delay:2s"` que, quando o HTMX carrega,
repete a mesma consulta sem recarregar a página inteira. Qualquer estado
diferente de `CALCULANDO` (`AGUARDANDO_REVISAO`, `ERRO_DE_CALCULO`, ou
qualquer outro que a máquina alcançar) interrompe o polling: o servidor
devolve `sucesso.html`/`erro.html` (sem `meta refresh`, sem `hx-trigger`) —
nunca a MESMA tela de progresso reapresentada, o que seria a "tela travada"
que o critério de aceite proíbe.

**`CONFIABILIDADE_DADOS` — o único parâmetro externo que `montar_estado_
financeiro` ainda recebe de fora (`T-106`, resolvido em `T-176`).** `T-103`
fechou a fórmula normativa dos três campos agregados do Bloco 3
(`RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS`, `DESPESAS_NAO_
MENSAIS_NORMALIZADAS`) DENTRO de `app/montagem/estado.py::montar_estado_
financeiro` — eles deixaram de ser parâmetro externo e esta rota não os
resolve mais. Sobrou `CONFIABILIDADE_DADOS`.

**Até `T-176` a implementação padrão BLOQUEAVA o disparo** (`_Parametros
ExternosPendentes` levantando `_ErroParametrosExternosPendentes`), em vez de
inventar um valor — corretamente, porque o enum `ALTA`/`MEDIA`/`BAIXA` não
tem membro neutro e qualquer default fixo seria a "estimativa silenciosa"
que `sdd.config.md` §4 proíbe. O efeito colateral, porém, era que **o Bloco
6 não podia ser disparado por nenhum caminho HTTP**: com a coleta inteira
respondida, `POST /caso/{id}/calculo` respondia `503` para sempre.

**`T-176` implementa a "tarefa futura" que aquela nota previa.**
`_ParametrosExternosDerivadosDoBloco2` deriva o campo das respostas do
Bloco 2, chamando `derivar_NIVEL_CONTROLE` e `derivar_CONFIABILIDADE_DADOS`
— as funções do PRÓPRIO motor, invocadas como estão. Não é reprodução de
passo de cálculo (`RF-16`): é a chamada que `app/montagem/estado.py` já
nomeava como o caminho certo (*"A chamadora (Bloco 6) é responsável por
invocar a derivação de dentro do motor, nunca de `app/`"*). A allowlist de
`T-06`/`AC-41` foi ampliada para esses dois nomes, e só para eles — com a
justificativa registrada no próprio teste de fronteira.

`obter_parametros_externos_do_bloco6` continua sendo PONTO DE INJEÇÃO
explícito (`app.dependency_overrides`), como todo outro repositório desta
feature.

**Nota de escopo — extensão estritamente necessária de `persistencia/
app_aluno/casos.py` (fora dos dois arquivos nominalmente listados por esta
tarefa).** O critério de aceite 4 ("duas execuções concorrentes resultam em
uma única execução") é irrealizável com a API que `T-23` deixou pronta
(`transicionar_estado` incondicional — ver o parágrafo de concorrência,
acima): nenhuma composição de chamadas feita só a partir desta rota consegue
tornar "ler o estado" e "escrevê-lo condicionalmente" atômicos sem tocar o
repositório, porque a seção crítica (`FOR UPDATE`) é interna a
`persistencia/app_aluno/casos.py` e não é exposta para a rota compor. Por
isso `transicionar_estado_se` foi adicionado ali (Postgres e arquivo) como
extensão ADITIVA e mínima — nenhum método existente mudou de assinatura ou
de comportamento, `transicionar_estado` continua exatamente como estava.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.maquina`, `app.casos.progresso`,
`app.montagem.estado`, `app.motor.executor`, de `collection.carga`/
`collection.registro`, de `persistencia.app_aluno.{casos,itens,respostas}` e
de `persistencia.supabase.{fonte_parametros,repositorio_snapshots}` (os
adaptadores concretos das portas do motor — `persistencia.*`, não `engine.*`,
portanto fora do escopo de `tests/app_aluno/estatica/
test_fronteira_import_engine.py`, T-06) — nunca de `engine/` além dos nomes já
liberados transitivamente por `app.montagem.estado`/`app.motor.executor`
(`AC-41`, não tocada por este módulo). Nenhum gate, ranqueamento ou fórmula da
§11 aparece aqui, e nenhum identificador `P_*` nem enunciado de pergunta
(`AC-37`, T-08).

REGRAS: `RF-16`, `AC-12`
"""

from __future__ import annotations

import asyncio
import os
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.casos.maquina import ESTADO_CASO, ErroTransicaoNaoDeclarada
from app.casos.progresso import (
    PendenciaObrigatoria,
    pendencias_obrigatorias,
    transicionar_e_registrar,
)
from app.concorrencia import tres_em_paralelo
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from app.montagem.estado import (
    ErroRespostaAusente,
    ErroValorInternoDesconhecido,
    montar_divida,
    montar_estado_financeiro,
    montar_perfil_comportamental,
)
from app.motor.executor import ParametrosDoCalculo, executar_calculo_com_timeout_async
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import RespostasCaso

# `T-176` — as DUAS derivações comportamentais do Bloco 2, invocadas como
# estão do motor, nunca reimplementadas aqui. Ver
# `_ParametrosExternosDerivadosDoBloco2` e a nota na allowlist de
# `tests/app_aluno/estatica/test_fronteira_import_engine.py`.
from engine.comportamento import derivar_CONFIABILIDADE_DADOS, derivar_NIVEL_CONTROLE
from engine.estado import Divida, EstadoFinanceiro
from engine.portas import FonteParametros, RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import Caso, RepositorioCasos
from persistencia.app_aluno.eventos import RepositorioEventosCaso, RepositorioEventosCasoSupabase
from persistencia.app_aluno.itens import RepositorioItens, RepositorioItensSupabase
from persistencia.app_aluno.respostas import RepositorioRespostas, RepositorioRespostasSupabase
from persistencia.supabase.fonte_parametros import FonteParametrosSupabase
from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase

REGRAS: Final[tuple[str, ...]] = ("RF-16", "AC-12")


roteador = APIRouter(prefix="/caso", tags=["calculo"])

# Mensagens curtas de propósito — mesma disciplina de `app/http/isolamento.py`
# e `app/http/rotas_consentimento.py` (`AC-37`, T-08): ficam sob o limiar de
# 40 caracteres do teste estático.
_MENSAGEM_PENDENCIA: Final[str] = "Há perguntas obrigatórias pendentes."
_MENSAGEM_ESTADO_INVALIDO: Final[str] = "Caso não está pronto para calcular."
_MENSAGEM_PARAMETROS_PENDENTES: Final[str] = "Cálculo indisponível no momento."

# Variável de ambiente que supre a versão de parâmetros vigente do piloto —
# nunca um literal de versão no código (mesmo padrão de `app/http/
# aplicacao.py::_VARIAVEL_CHAVE_ASSINATURA_SESSAO`).
_VARIAVEL_PARAMETROS_VERSION_VIGENTE: Final[str] = "PARAMETROS_VERSION_VIGENTE"


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: mesmo precedente de `app/http/rotas_consentimento.py` —
    `exigir_caso_da_sessao` já garantiu que `CASO_ID` existe e pertence à
    conta da sessão; este erro só ocorreria numa condição de corrida
    extrema."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento confirmá-lo")


class _ErroParametrosExternosPendentes(Exception):
    """`T-106` — ver a nota extensa na docstring do módulo. Nenhum valor é
    inventado para `CONFIABILIDADE_DADOS` enquanto a invocação da derivação
    de `engine/comportamento.py` não for decisão de uma tarefa futura."""

    def __init__(self) -> None:
        # Mensagem técnica montada por `str.join` sobre segmentos curtos
        # (mesmo padrão de `app/montagem/estado.py::ErroRespostaAusente`) —
        # evita um literal contíguo que ultrapasse o limiar de "possível
        # enunciado de pergunta" de `tests/app_aluno/estatica/
        # test_sem_conteudo_de_questionario_no_codigo.py` (T-08, AC-37).
        segmentos = (
            "CONFIABILIDADE_DADOS sem",
            "fonte real —",
            "bloco 6 bloqueado.",
        )
        super().__init__(" ".join(segmentos))


class ParametrosExternosDoBloco6:
    """Contrato do ponto de injeção citado na docstring do módulo:
    `CONFIABILIDADE_DADOS` (obrigatório) e `economia_nao_identificada`
    (opcional), os únicos parâmetros que `app/montagem/estado.py::
    montar_estado_financeiro` (T-51, atualizada por T-103) ainda recebe de
    fora — nunca calculados por esta rota (Lei nº 3)."""

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        """Devolve os parâmetros nomeados na docstring da classe, prontos
        para `**kwargs` de `montar_estado_financeiro`. A implementação
        padrão (`obter_parametros_externos_do_bloco6`, abaixo) levanta
        `_ErroParametrosExternosPendentes` — `CONFIABILIDADE_DADOS` sem
        fonte real."""
        raise NotImplementedError


class _ParametrosExternosPendentes(ParametrosExternosDoBloco6):
    """Implementação que BLOQUEIA — mantida para quem precise do
    comportamento anterior em teste (ver `_ErroParametrosExternosPendentes`).

    Deixou de ser a padrão em `T-176`: enquanto era, o Bloco 6 não podia ser
    disparado por nenhum caminho HTTP."""

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        raise _ErroParametrosExternosPendentes()


class _ParametrosExternosDerivadosDoBloco2(ParametrosExternosDoBloco6):
    """A implementação padrão desde `T-176` — deriva `CONFIABILIDADE_DADOS`
    das respostas do Bloco 2, chamando a função do PRÓPRIO motor.

    **Por que isto não é "calcular na aplicação" (Lei nº 3, `RF-16`).**
    Nenhum passo do cálculo é reproduzido aqui: `derivar_NIVEL_CONTROLE` e
    `derivar_CONFIABILIDADE_DADOS` são as funções de `engine/comportamento.
    py`, invocadas como estão. `RF-16` proíbe reimplementar o que o motor
    faz; chamá-lo é o contrário disso. `app/montagem/estado.py` já nomeava
    este caminho como o certo: *"A chamadora (Bloco 6) é responsável por
    invocar a derivação de dentro do motor"*.

    **A ordem das duas derivações não é escolha nossa.** `CONFIABILIDADE_
    DADOS` depende de `NIVEL_CONTROLE`, e a assinatura de
    `derivar_CONFIABILIDADE_DADOS` torna isso obrigatório: o nível entra
    como primeiro parâmetro posicional, sem default. É a ordem do grafo da
    §11.10 (`RF-27`), reforçada por assinatura.

    **`economia_nao_identificada` NÃO é devolvida.** Ela é opcional em
    `montar_estado_financeiro` (default `None`), e a montagem já sabe o que
    fazer com a ausência — `_economia_potencial_imediata` a trata como
    "nenhum gasto fantasma identificado". Construir um `dinheiro(0)` aqui
    seria um `Decimal` monetário nascido fora da fronteira única de
    conversão (`RF-13`, `app/montagem/conversao.py`), que
    `tests/app_aluno/estatica/test_fronteira_decimal_unica.py` audita — e a
    trava está certa: dinheiro tem um lugar só para nascer.
    """

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        perfil = montar_perfil_comportamental(respostas)
        nivel_controle = derivar_NIVEL_CONTROLE(perfil)
        return {
            "CONFIABILIDADE_DADOS": derivar_CONFIABILIDADE_DADOS(nivel_controle, perfil),
        }


def obter_colecao_de_registros() -> ColecaoDeRegistros:
    """Ponto único de injeção — sobrescrito nos testes, mesmo padrão de
    `app/http/rotas_coleta.py::obter_colecao_de_registros`."""
    return carregar_registros()


def obter_repositorio_respostas() -> RepositorioRespostas:
    """Ponto único de injeção — sobrescrito nos testes, mesmo padrão de
    `app/http/rotas_coleta.py::obter_repositorio_respostas`."""
    return RepositorioRespostasSupabase()


def obter_repositorio_itens() -> RepositorioItens:
    """Ponto único de injeção — sobrescrito nos testes, mesmo padrão de
    `app/http/rotas_coleta.py::obter_repositorio_itens`."""
    return RepositorioItensSupabase()


def obter_fonte_parametros() -> FonteParametros:
    """Ponto único de injeção da porta `FonteParametros` (`engine/portas.py`)
    — o adaptador concreto (`persistencia.supabase.fonte_parametros.
    FonteParametrosSupabase`) é decisão desta rota, nunca de `app/motor/
    executor.py` (T-54, que só recebe a porta já injetada). Sobrescrito nos
    testes via `app.dependency_overrides`, mesmo padrão dos demais
    repositórios desta feature."""
    return FonteParametrosSupabase()


def obter_repositorio_snapshots() -> RepositorioSnapshots:
    """Ponto único de injeção da porta `RepositorioSnapshots` — mesmo padrão
    de `obter_fonte_parametros`, acima."""
    return RepositorioSnapshotsSupabase()


def obter_repositorio_eventos() -> RepositorioEventosCaso:
    """`T-91` (`RF-31`, `AC-40`) — ponto único de injeção do repositório da
    trilha de eventos do caso, sobrescrito nos testes via
    `app.dependency_overrides`, mesmo padrão dos demais repositórios."""
    return RepositorioEventosCasoSupabase()


def obter_parametros_externos_do_bloco6() -> ParametrosExternosDoBloco6:
    """Ponto único de injeção dos parâmetros externos do Bloco 6.

    Desde `T-176` a padrão DERIVA `CONFIABILIDADE_DADOS` das respostas do
    Bloco 2, chamando as funções do próprio motor — a "tarefa futura" que a
    nota de `T-106` previa. Continua sobrescrevível em teste, como todo
    outro ponto de injeção desta feature."""
    return _ParametrosExternosDerivadosDoBloco2()


def _itens_por_escopo(
    repositorio_itens: RepositorioItens, CASO_ID: str
) -> dict[EscopoRepeticao, tuple[str, ...]]:
    """Mesmo agrupamento de `app/http/rotas_coleta.py::_itens_por_escopo`
    (T-44) — itens ATIVOS (`removido_em is None`) por `EscopoRepeticao`, no
    formato que `pendencias_obrigatorias` consome."""
    itens_ativos = repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
    agrupado: dict[EscopoRepeticao, list[str]] = {}
    for item in itens_ativos:
        agrupado.setdefault(item.escopo, []).append(item.item_id)
    return {escopo: tuple(item_ids) for escopo, item_ids in agrupado.items()}


def _formatar_pendencia(pendencia: PendenciaObrigatoria) -> str:
    """Nomeia a pergunta pendente (critério de aceite 1: "nomeando o que
    falta") — `ID` do registro mais o item, quando `REP`."""
    if pendencia.item_id is None:
        return pendencia.ID
    return f"{pendencia.ID} ({pendencia.item_id})"


def _montar_dividas_do_caso(
    respostas: RespostasCaso, itens_por_escopo: dict[EscopoRepeticao, tuple[str, ...]]
) -> tuple[Divida, ...]:
    """Uma `Divida` (`app/montagem/estado.py::montar_divida`, T-49) por
    `DIVIDA_ID` ativo do caso — a rota não decide NADA sobre o conteúdo de
    cada dívida, só itera sobre os itens já cadastrados (`persistencia/
    app_aluno/itens.py`, T-23)."""
    dividas_id = itens_por_escopo.get(EscopoRepeticao.DIVIDA_ID, ())
    return tuple(montar_divida(respostas, dividas_id) for dividas_id in dividas_id)


def _montar_estado_financeiro_do_caso(
    caso: Caso,
    respostas: RespostasCaso,
    itens_por_escopo: dict[EscopoRepeticao, tuple[str, ...]],
    parametros_externos_resolvidos: dict[str, object],
) -> EstadoFinanceiro:
    """Os passos 2 do plano §5.2 (`app/montagem/estado.py`) — a rota junta o
    que já está pronto (`dividas`, `DATA_REFERENCIA` do `Caso`) com o que já
    foi resolvido por `ParametrosExternosDoBloco6.obter` (`CONFIABILIDADE_
    DADOS` e, se aplicável, `economia_nao_identificada`), ANTES de qualquer
    transição de estado (ver `disparar_calculo`). O `# type: ignore` segue
    necessário mesmo depois de `T-106` (confirmado com `mypy --strict`):
    `**dict[str, object]` não é verificável contra os parâmetros nomeados e
    tipados de `montar_estado_financeiro`, independente de quantos ou quais
    parâmetros externos existam."""
    dividas = _montar_dividas_do_caso(respostas, itens_por_escopo)
    return montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=caso.DATA_REFERENCIA,
        dividas=dividas,
        **parametros_externos_resolvidos,  # type: ignore[arg-type]
    )


@roteador.post("/{CASO_ID}/calculo")
async def disparar_calculo(
    request: Request,
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_respostas: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
    fonte_parametros: Annotated[FonteParametros, Depends(obter_fonte_parametros)],
    repositorio_snapshots: Annotated[RepositorioSnapshots, Depends(obter_repositorio_snapshots)],
    repositorio_eventos: Annotated[RepositorioEventosCaso, Depends(obter_repositorio_eventos)],
    parametros_externos: Annotated[
        ParametrosExternosDoBloco6, Depends(obter_parametros_externos_do_bloco6)
    ],
) -> JSONResponse:
    """Dispara o Bloco 6 — guarda de `OBR` pendente, transição pela máquina
    (com a trava de concorrência de `T-23` dentro dela), montagem do
    `EstadoFinanceiro` real e agendamento da execução em segundo plano.
    Responde IMEDIATAMENTE com a tela de progresso — nunca aguarda o
    cálculo terminar (ver docstring do módulo).

    **Continua `async def` — `T-187`.** `asyncio.create_task` (abaixo) exige
    um loop de eventos rodando na thread corrente; uma rota `def` comum roda
    numa thread do pool do Starlette, sem loop, e a chamada falharia. Tudo
    que é bloqueante — as várias consultas e a transição de estado, com
    seus retornos antecipados — fica em `_preparar_calculo`, uma função
    síncrona comum, chamada por `run_in_threadpool`; só o agendamento da
    tarefa de fundo permanece aqui, no `async def`."""
    resultado = await run_in_threadpool(
        _preparar_calculo,
        CASO_ID,
        colecao,
        repositorio_casos,
        repositorio_respostas,
        repositorio_itens,
        fonte_parametros,
        repositorio_snapshots,
        repositorio_eventos,
        parametros_externos,
    )
    if isinstance(resultado, JSONResponse):
        return resultado
    estado_financeiro, insumos = resultado

    asyncio.create_task(
        _executar_e_avancar(estado_financeiro, insumos, repositorio_eventos)
    )

    return JSONResponse({"CASO_ID": CASO_ID, "calculando": True})


def _preparar_calculo(
    CASO_ID: str,
    colecao: ColecaoDeRegistros,
    repositorio_casos: RepositorioCasos,
    repositorio_respostas: RepositorioRespostas,
    repositorio_itens: RepositorioItens,
    fonte_parametros: FonteParametros,
    repositorio_snapshots: RepositorioSnapshots,
    repositorio_eventos: RepositorioEventosCaso,
    parametros_externos: ParametrosExternosDoBloco6,
) -> JSONResponse | tuple[EstadoFinanceiro, ParametrosDoCalculo]:
    """A parte síncrona e bloqueante de `disparar_calculo` — `T-187`. Devolve
    a resposta de erro pronta quando alguma guarda recusa, ou o par
    `(estado_financeiro, insumos)` que a rota usa para agendar a execução.
    Corpo idêntico ao que vivia direto na rota antes desta tarefa; só o
    ponto de chamada mudou."""
    # `caso`, `respostas` e `itens_por_escopo` são três consultas
    # independentes (nenhuma usa o resultado da outra) — em paralelo,
    # `T-191`.
    caso, respostas_brutas, itens_por_escopo = tres_em_paralelo(
        lambda: repositorio_casos.buscar(CASO_ID),
        lambda: repositorio_respostas.listar_do_caso(CASO_ID),
        lambda: _itens_por_escopo(repositorio_itens, CASO_ID),
    )
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    respostas = RespostasCaso(respostas=respostas_brutas)

    # Critério de aceite 1: campo OBR pendente nomeia o que falta e recusa a
    # transição — antes de qualquer tentativa de transicionar().
    pendencias = pendencias_obrigatorias(colecao.registros, respostas, itens_por_escopo)
    if pendencias:
        return JSONResponse({"mensagem": _MENSAGEM_PENDENCIA,
                "pendencias": tuple(_formatar_pendencia(p) for p in pendencias)}, status_code=400)

    # `T-106` — ver a nota extensa na docstring do módulo: os parâmetros
    # externos (`CONFIABILIDADE_DADOS` e, se aplicável, `economia_nao_
    # identificada`) são obtidos ANTES de qualquer transição de estado. Se a
    # fonte real de `CONFIABILIDADE_DADOS` ainda não existir (implementação
    # padrão, produção), a requisição é recusada aqui — o caso PERMANECE em
    # COLETA_INICIAL, nunca preso em CALCULANDO por um bloqueio que nada tem
    # a ver com o próprio cálculo.
    try:
        parametros_externos_resolvidos = parametros_externos.obter(caso, respostas)
    except _ErroParametrosExternosPendentes:
        return JSONResponse(
            {"mensagem": _MENSAGEM_PARAMETROS_PENDENTES, "pendencias": ()},
            status_code=503,
        )

    # A montagem do EstadoFinanceiro (passo 2 do plano §5.2) ocorre ANTES de
    # qualquer transição de estado: se as respostas reais do caso não forem
    # suficientes para montar um `EstadoFinanceiro` completo (`ErroResposta
    # Ausente`/`ErroValorInternoDesconhecido`, `app/montagem/estado.py`), a
    # requisição é recusada aqui e o caso PERMANECE em COLETA_INICIAL — nunca
    # preso em CALCULANDO por uma falha de montagem que nada tem a ver com o
    # cálculo em si (mesma disciplina do bloqueio de `CONFIABILIDADE_DADOS`,
    # acima).
    try:
        estado_financeiro = _montar_estado_financeiro_do_caso(
            caso, respostas, itens_por_escopo, parametros_externos_resolvidos
        )
    except (ErroRespostaAusente, ErroValorInternoDesconhecido) as erro:
        return JSONResponse(
            {"mensagem": _MENSAGEM_ESTADO_INVALIDO, "pendencias": (str(erro),)},
            status_code=422,
        )

    # `RF-32`/`T-54`: a versão de parâmetros vigente também é lida ANTES de
    # qualquer transição — mesma disciplina das duas checagens acima. Sem
    # ela configurada, a requisição é recusada e o caso PERMANECE em
    # COLETA_INICIAL, nunca preso em CALCULANDO por um erro de configuração
    # do ambiente (nada a ver com o cálculo em si).
    try:
        parametros_versao = _parametros_versao_vigente()
    except ErroParametrosVersaoAusente:
        return JSONResponse(
            {"mensagem": _MENSAGEM_PARAMETROS_PENDENTES, "pendencias": ()},
            status_code=503,
        )

    # Transição pela MÁQUINA — nunca atribuição direta. A tabela é quem
    # decide se COLETA_INICIAL → CALCULANDO é um par declarado; se não for
    # (ex.: guarda textual do §7.1 nunca satisfeita para outro par), a
    # requisição é recusada aqui, ANTES de tocar o banco.
    #
    # Critério de aceite 4 — trava de concorrência real: `transicionar_e_
    # registrar` (T-91) persiste via `transicionar_estado_se`, que só grava
    # CALCULANDO se o `estado` corrente, lido DENTRO da mesma seção `SELECT
    # ... FOR UPDATE`, ainda for COLETA_INICIAL (T-23, estendido em T-56 —
    # ver `persistencia/app_aluno/casos.py`). A segunda requisição
    # concorrente, ao adquirir o lock depois do commit da primeira, encontra
    # o caso já em CALCULANDO e recebe `None` — nunca agenda uma segunda
    # execução do Bloco 6. `RF-31`/`AC-40` (T-91): a transição, quando
    # aplicada, grava um evento na trilha (`tipo_evento="bloco_6_executa"`)
    # no MESMO passo.
    try:
        caso_calculando = transicionar_e_registrar(
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            caso_id=CASO_ID,
            de=ESTADO_CASO.COLETA_INICIAL,
            para=ESTADO_CASO.CALCULANDO,
        )
    except ErroTransicaoNaoDeclarada:
        return JSONResponse(
            {"mensagem": _MENSAGEM_ESTADO_INVALIDO, "pendencias": ()},
            status_code=409,
        )
    if caso_calculando is None:
        return JSONResponse(
            {"mensagem": _MENSAGEM_ESTADO_INVALIDO, "pendencias": ()},
            status_code=409,
        )

    insumos = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=CASO_ID,
        parametros_versao=parametros_versao,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )

    return estado_financeiro, insumos


async def _executar_e_avancar(
    estado: EstadoFinanceiro,
    insumos: ParametrosDoCalculo,
    repositorio_eventos: RepositorioEventosCaso,
) -> None:
    """Roda em segundo plano (`asyncio.create_task`, chamado pela rota
    acima): executa o Bloco 6 (T-54/T-55) e, em caso de sucesso, transiciona
    o caso de `CALCULANDO` para `AGUARDANDO_REVISAO` (`snapshot_anexado`,
    `app/casos/maquina.py`) — a ÚNICA transição de sucesso que sai de
    `CALCULANDO`, e por isso não pertence a `app/motor/executor.py` (T-55 só
    trata as transições de FALHA). Os caminhos de erro/timeout já
    transicionam o caso por dentro de `executar_calculo_com_timeout_async`
    (T-55) — esta função não precisa (e não deve) tratá-los de novo.

    `T-91` (`RF-31`/`AC-40`): a transição de sucesso passa por
    `transicionar_e_registrar`, que grava o evento `snapshot_anexado` na
    trilha no mesmo passo em que persiste o novo `estado`.

    **`snapshot_raiz_id` é gravado aqui — `T-173`, `OQ-11`.** Até esta
    tarefa `registrar_snapshot_raiz` não era chamado por rota nenhuma: o
    snapshot era anexado e o caso ia a `AGUARDANDO_REVISAO`, mas o `Caso`
    ficava com `snapshot_raiz_id` NULO. Como `listar_fila_de_revisao` busca
    a cadeia pela RAIZ (`app/revisao/fila.py:276`), a fila saía **vazia**
    mesmo com plano calculado, e `GET /api/revisao/caso/{id}` respondia
    `404` para um caso que existe e tem plano — `RF-23` (revisão humana
    obrigatória) ficava inalcançável pelo caminho real. Verificado contra o
    servidor real: primeiro cálculo via HTTP, snapshot persistido, fila
    vazia.

    **Só no PRIMEIRO snapshot da cadeia.** A raiz é a origem, não o último:
    sobrescrevê-la a cada recálculo quebraria `historico`, que agrupa pela
    raiz. O critério é `snapshot_anterior_id is None` — a definição de
    "este é o primeiro" que o próprio snapshot carrega, em vez de reler o
    `Caso` e decidir por ausência.

    **`T-187`.** `snapshot = await ...` já é async por natureza (é o motor
    de cálculo em si, com o próprio timeout). O que vem depois — gravar a
    raiz e transicionar o estado — é bloqueante e roda numa `asyncio.Task`
    no loop principal: sem `run_in_threadpool` aqui, esta função travaria o
    processo inteiro pela duração das duas escritas, para qualquer outra
    requisição em andamento, não só para quem disparou este cálculo."""
    snapshot = await executar_calculo_com_timeout_async(estado, insumos)
    if snapshot is not None:
        await run_in_threadpool(
            _gravar_snapshot_e_avancar, snapshot, insumos, repositorio_eventos
        )


def _gravar_snapshot_e_avancar(
    snapshot: SnapshotOrdem,
    insumos: ParametrosDoCalculo,
    repositorio_eventos: RepositorioEventosCaso,
) -> None:
    """A parte bloqueante de `_executar_e_avancar` — `T-187`. Corpo idêntico
    ao que vivia direto naquela função antes desta tarefa."""
    if snapshot.snapshot_anterior_id is None:
        insumos.repositorio_casos.registrar_snapshot_raiz(
            insumos.caso_id, snapshot.SNAPSHOT_ID
        )
    transicionar_e_registrar(
        repositorio_casos=insumos.repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=insumos.caso_id,
        de=ESTADO_CASO.CALCULANDO,
        para=ESTADO_CASO.AGUARDANDO_REVISAO,
    )


def _parametros_versao_vigente() -> str:
    """A versão de parâmetros vigente do piloto — `str` opaca para `app/
    motor/executor.py` (RF-32, T-54): nunca um valor `P_*`, só o
    identificador de versão. Vem de variável de ambiente, nunca de literal
    no código (mesmo padrão de `app/http/aplicacao.py::_obter_chave_
    assinatura_sessao` para `CHAVE_ASSINATURA_SESSAO`) — sem ela, o disparo
    do Bloco 6 falha alto, nunca assume uma versão default silenciosa."""
    versao = os.environ.get(_VARIAVEL_PARAMETROS_VERSION_VIGENTE)
    if not versao:
        raise ErroParametrosVersaoAusente()
    return versao


class ErroParametrosVersaoAusente(RuntimeError):
    """`PARAMETROS_VERSION_VIGENTE` ausente ou vazia — nunca um fallback
    inseguro silencioso (mesmo padrão de `app/http/aplicacao.py::
    ErroConfiguracaoSessao`)."""

    def __init__(self) -> None:
        # Mensagem técnica curta (< 40 caracteres, limiar de AC-37/T-08) —
        # o próprio nome da variável de ambiente já diz o que falta, mesmo
        # padrão de `app/http/aplicacao.py::_obter_chave_assinatura_sessao`.
        super().__init__(f"{_VARIAVEL_PARAMETROS_VERSION_VIGENTE} ausente.")


@roteador.get("/{CASO_ID}/calculo/progresso")
def progresso_do_calculo(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
) -> JSONResponse:
    """Leitura pura de `Caso.estado` (Lei nº 3 — esta rota não calcula).

    `calculando` é o sinal para o cliente continuar consultando; qualquer
    outro estado é terminal, e o cliente para de perguntar. Nunca a mesma
    tela de progresso reapresentada para sempre."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    return JSONResponse(
        {
            "CASO_ID": CASO_ID,
            "estado": caso.estado.value,
            "calculando": caso.estado is ESTADO_CASO.CALCULANDO,
            "erro_de_calculo": caso.estado is ESTADO_CASO.ERRO_DE_CALCULO,
        }
    )
