"""Painel dedicado do operador — `RF-35` (`OQ-07` respondida, T-102).

Tarefa nova, aberta depois do fechamento das 18 Open Questions da spec:
`OQ-07` foi respondida com "sim, painel dedicado, mesmo no piloto de 1–3
alunos" — decisão do usuário que reverteu o que a spec §9 originalmente
listava como Out of Scope. `RF-35` é o requisito que registra essa reversão.

`GET /operador/painel` lista TODOS os casos do piloto (`RepositorioCasos.
listar_todos`, extensão pequena e necessária desta tarefa — ver a nota em
`persistencia/app_aluno/casos.py`), cada um com `estado`, se está
`aguardando_revisao` e há quanto tempo desde `ultima_interacao_em`.

**Reusa `T-92` inteiramente — nenhuma lógica de trilha nova aqui.** Cada
linha do painel é o `RelatoDeProgresso` que `app/casos/progresso.py::
consultar_trilha_de_progresso` já produz (`CASO_ID`, `estado`,
`ultima_interacao_em`, `proxima_pergunta`, `aguardando_revisao`) — esta rota
só ORQUESTRA os mesmos três insumos que `app/http/rotas_coleta.py` já monta
para chamar aquela função (`ColecaoDeRegistros.registros`, `RespostasCaso`,
`itens_por_escopo`) e apresenta o resultado em tela própria. Nenhum campo é
recalculado: `estado` e `aguardando_revisao` são leituras diretas de `Caso`/
`RelatoDeProgresso`, exatamente como `T-92` já as expõe.

**"Tempo desde a última atividade" não é regra de negócio do motor.** É a
diferença entre `datetime.now(UTC)` e `RelatoDeProgresso.ultima_interacao_em`
— um campo estrutural do próprio `Caso` (T-23), nunca um campo de
`SnapshotOrdem`. A Lei nº 3 (`sdd.config.md` §6, `plans/app-aluno.plan.md`
§1) proíbe recalcular o que o motor produz; apresentar há quanto tempo um
carimbo de auditoria já existente foi gravado é apresentação, não gate,
ranqueamento nem fórmula da §11 — por isso a subtração de datas ocorre nesta
rota (não em `app/casos/progresso.py`, que continua puro e sem relógio).

**Nenhum dado financeiro do aluno aparece na tela (critério de aceite).**
Só os quatro campos estruturais de `RelatoDeProgresso` chegam ao template
(`CASO_ID`, `estado`, `aguardando_revisao`, tempo desde a última interação)
— nenhum valor de `Resposta`/`ValorResposta` nem de `EstadoFinanceiro`/
`SnapshotOrdem` é lido por este módulo, mesma disciplina de `T-92`.

**Protegida por `exigir_papel_revisor` (T-100), nunca `exigir_caso_da_
sessao` (T-31) — mesmo precedente de `/revisao/fila` (T-69) e `/revisao/
caso/{...}` (T-70).** O operador não é "dono" de um caso no sentido de
isolamento do aluno: ele vê todos os casos do piloto, por definição de
papel. Sessão ausente ⇒ `401`, ANTES de qualquer leitura de caso; sessão de
conta autenticada sem `e_revisor = true` ⇒ `403`, nunca `404` — a existência
do painel não é segredo, só o acesso é negado (mesma nota de `app/http/
isolamento.py::exigir_papel_revisor`).

**Fora da auditoria de isolamento por `CASO_ID` (`tests/app_aluno/e2e/
test_mecanismo_isolamento.py`), pelo mesmo motivo estrutural de `/revisao/
fila`/`/revisao/caso/{...}`.** Esta rota não recebe `CASO_ID` como path/query
parameter — ela lista, não busca um caso por identificador.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.casos.progresso` (`consultar_trilha_de_progresso`), `app.casos.maquina`
(`ESTADO_CASO`), `app.http.isolamento` (`exigir_papel_revisor`), `collection.
carga` (`carregar_registros`, `ColecaoDeRegistros`), `collection.respostas`
(`RespostasCaso`) e `persistencia.app_aluno.*` (`RepositorioCasos`,
`RepositorioRespostas`, `RepositorioItens`) — nunca de `engine/`.

REGRAS: `RF-35`, `RF-31`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from fastapi import APIRouter

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import RelatoDeProgresso
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from persistencia.app_aluno.casos import RepositorioCasos, RepositorioCasosSupabase
from persistencia.app_aluno.itens import RepositorioItens, RepositorioItensSupabase
from persistencia.app_aluno.respostas import RepositorioRespostas, RepositorioRespostasSupabase

REGRAS: Final[tuple[str, ...]] = ("RF-35", "RF-31")

roteador = APIRouter(prefix="/operador", tags=["operador"])



def obter_colecao_de_registros_do_painel() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros — sobrescrito nos
    testes via `app.dependency_overrides`, mesmo padrão de `app/http/
    rotas_coleta.py::obter_colecao_de_registros`. Declarado à parte para que
    este módulo não precise importar de `rotas_coleta.py` só por causa de um
    ponto de injeção."""
    return carregar_registros()


def obter_repositorio_casos_do_painel() -> RepositorioCasos:
    """Ponto único de injeção de `RepositorioCasos` para esta rota —
    sobrescrito nos testes via `app.dependency_overrides`, mesmo padrão de
    `app/http/rotas_revisao.py::obter_repositorio_casos_da_fila`."""
    return RepositorioCasosSupabase()


def obter_repositorio_respostas_do_painel() -> RepositorioRespostas:
    """Ponto único de injeção do repositório de respostas — mesmo padrão de
    `app/http/rotas_coleta.py::obter_repositorio_respostas`."""
    return RepositorioRespostasSupabase()


def obter_repositorio_itens_do_painel() -> RepositorioItens:
    """Ponto único de injeção do repositório de itens repetidos — usado só
    para montar `itens_por_escopo` que `consultar_trilha_de_progresso`
    consome (mesmo padrão de `app/http/rotas_coleta.py::
    obter_repositorio_itens`)."""
    return RepositorioItensSupabase()


def _itens_por_escopo(
    repositorio_itens: RepositorioItens, caso_id: str
) -> dict[EscopoRepeticao, tuple[str, ...]]:
    """Mesma agregação de `app/http/rotas_coleta.py::_itens_por_escopo`: só
    itens ATIVOS (`removido_em is None`), agrupados por `EscopoRepeticao`."""
    itens_ativos = repositorio_itens.listar_do_caso(caso_id, incluir_removidos=False)
    agrupado: dict[EscopoRepeticao, list[str]] = {}
    for item in itens_ativos:
        agrupado.setdefault(item.escopo, []).append(item.item_id)
    return {escopo: tuple(item_ids) for escopo, item_ids in agrupado.items()}


@dataclass(frozen=True, slots=True)
class _LinhaDoPainel:
    """Os quatro campos estruturais que o template exibe — nenhum dado
    financeiro do aluno (critério de aceite de T-102). `tempo_desde_ultima_
    atividade` é a única derivação desta rota (ver nota do módulo: diferença
    de datas sobre um campo estrutural de `Caso`, não uma regra do motor)."""

    CASO_ID: str
    estado: ESTADO_CASO
    aguardando_revisao: bool
    tempo_desde_ultima_atividade: str


def _formatar_tempo_decorrido(desde: datetime, agora: datetime) -> str:
    """Formata a diferença entre `agora` e `desde` como texto legível
    ("há N dia(s)"/"há N hora(s)"/"há N minuto(s)"/"agora mesmo") — apenas
    apresentação sobre um `timedelta`, nunca uma regra de negócio do motor
    (ver nota do módulo)."""
    decorrido = agora - desde
    segundos = int(decorrido.total_seconds())
    if segundos < 60:
        return "agora mesmo"
    minutos = segundos // 60
    if minutos < 60:
        return f"há {minutos} minuto{'s' if minutos != 1 else ''}"
    horas = minutos // 60
    if horas < 24:
        return f"há {horas} hora{'s' if horas != 1 else ''}"
    dias = horas // 24
    return f"há {dias} dia{'s' if dias != 1 else ''}"


def _relato_para_linha(relato: RelatoDeProgresso, agora: datetime) -> _LinhaDoPainel:
    return _LinhaDoPainel(
        CASO_ID=relato.CASO_ID,
        estado=relato.estado,
        aguardando_revisao=relato.aguardando_revisao,
        tempo_desde_ultima_atividade=_formatar_tempo_decorrido(relato.ultima_interacao_em, agora),
    )
