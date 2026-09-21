"""`AC-45`..`AC-49` sobre a dependência externa JÁ ENTREGUE — `RF-33`, T-90,
atualizado por `T-119A`.

Os cinco critérios abaixo dependiam das TRÊS mudanças previstas em
`engine/gates.py::AcaoRequerida`, todas do slug `motor-calculo` (nunca
executadas por este slug, `sdd.config.md`/`plans/app-aluno.plan.md` §1 —
"`engine/` está CONGELADO"), listadas em `specs/app-aluno.spec.md` §7
(bloco "Exceção ao congelamento de `engine/`") e nas Open Questions
`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`:

| # | Mudança | Critérios que dependem dela | Situação |
| - | ------- | ---------------------------- | -------- |
| 1 | `AcaoRequerida` ganha `ACAO_ID` e `TIPO_ACAO` | `AC-45`, `AC-46`, `AC-48` | **entregue** |
| 2 | Gate 1 passa a emitir `AcaoRequerida` de tipo informação | `AC-47` | **entregue** |
| 3 | Ação de economia emitida fora do fluxo de gates | `AC-49` | **entregue** |

**As três chegaram, e este arquivo funcionou exatamente como projetado.**
`T-90` escreveu os cinco testes como `xfail(strict=True)` com o raciocínio
declarado: cada um contém a asserção REAL do critério (`ACAO_ID` idêntico
entre dois snapshots; exatamente uma pergunta de resultado por tipo; uma ação
de informação em `ORDEM_ACOES`; tipagem correta de renegociação/troca; uma
ação de economia condicionada a `ECONOMIA_POTENCIAL_IMEDIATA`), e o
`strict=True` existia para que, no dia em que a asserção passasse de verdade,
o "passar inesperado" fosse reportado como FALHA — forçando quem visse isso a
remover o marcador em vez de deixá-lo acumular silenciosamente. Foi o que
aconteceu: a Rodada 2 de `motor-calculo` entregou as três mudanças, os cinco
testes passaram a `XPASS(strict)`, e `T-119A` é a remoção que o próprio
`strict=True` exigiu. Nenhuma asserção foi tocada — os corpos dos cinco
testes são os mesmos de `T-90`; o que saiu foi apenas o marcador que dizia
"isto ainda não pode passar".

Cada teste é construído em cima de uma `AcaoRequerida` REAL, produzida por
`calcular_plano` de verdade (nunca um dublê) — mesma técnica de
`tests/app_aluno/test_acompanhamento_acao_id.py` (T-83) e
`tests/app_aluno/test_acoes.py` (T-84): o cenário de negócio (dívida
bloqueada por Gate 1/2/3, ou orçamento com gasto fantasma) é montado de
verdade, o motor roda de verdade, e as funções de fronteira já entregues
(`acao_id_de`, `tipo_acao_de`, `perguntas_do_bloco_11`) leem o campo real.

**Nenhum literal de `TIPO_ACAO` aparece neste módulo** — mesma disciplina de
`T-84`/`app/motor/acoes.py`, mantida mesmo com `OQ-13` respondida: onde um
valor de `TIPO_ACAO` é necessário para comparação (`AC-46`, `AC-47`,
`AC-48`, `AC-49`), ele é extraído programaticamente da `condicao_exibicao`
dos registros REAIS de `collection/registros/bloco-11.yaml` (a mesma técnica
auxiliar de `tests/app_aluno/test_acoes.py::_extrair_valor_tipo_acao`), nunca
copiado à mão para uma string deste arquivo. O mapeamento continua sendo
DADO: editar o YAML muda o que estes testes comparam, sem tocar numa linha
daqui.

REGRAS: RF-33, AC-45, AC-46, AC-47, AC-48, AC-49
"""

from __future__ import annotations

from dataclasses import replace

from app.casos.acompanhamento import acao_id_de
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.acoes import perguntas_do_bloco_11, tipo_acao_de
from collection.carga import carregar_registros
from collection.condicoes import CondicaoE, CondicaoIgual
from collection.registro import RegistroPergunta
from engine.estado import Divida
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from engine.tipos import EVENTO_RECALCULO, STATUS_DIVIDA
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    CasoCompleto,
    caso_completo,
    montar_respostas_caso,
)

_PARAMETROS_VERSAO = "1.0.1"
_DIVIDA_ID_ELEGIVEL = "D-CASO-COMPLETO-ELEGIVEL-T90"

# Mesmo valor de tests/app_aluno/test_acoes.py (T-74/T-84): saldo alto o
# bastante para a dívida bloqueada por gate nunca ser quitada dentro do
# horizonte de simulação — sem isso o motor recusaria com
# `ErroOrdemInconsistente` (dívida bloqueada só é filtrada na publicação
# final, não durante a simulação).
_SALDO_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")

_REGISTROS_REAIS: tuple[RegistroPergunta, ...] = carregar_registros().registros


def _extrair_valor_tipo_acao(registro: RegistroPergunta) -> str:
    """Extrai o `valor` do termo `TIPO_ACAO` de `condicao_exibicao` de um
    registro REAL de resultado do Bloco 11 — mesma técnica de
    `tests/app_aluno/test_acoes.py::_extrair_valor_tipo_acao` (T-84): nunca
    um literal copiado à mão. `OQ-13` foi respondida, mas a disciplina se
    mantém — o valor de `TIPO_ACAO` é DADO do registro, e nenhum teste deste
    arquivo o transcreve."""
    condicao = registro.condicao_exibicao
    if isinstance(condicao, CondicaoIgual) and condicao.variavel == "TIPO_ACAO":
        return condicao.valor
    if isinstance(condicao, CondicaoE):
        for termo in condicao.termos:
            if isinstance(termo, CondicaoIgual) and termo.variavel == "TIPO_ACAO":
                return termo.valor
    raise AssertionError(f"registro sem termo TIPO_ACAO: {registro!r}")  # pragma: no cover


def _montar_snapshot(
    *,
    divida_desviada: Divida,
    parametros_externos: dict[str, object] | None = None,
    anterior: SnapshotOrdem | None = None,
    evento: EVENTO_RECALCULO | None = None,
) -> SnapshotOrdem:
    """Monta um `SnapshotOrdem` REAL a partir de `calcular_plano`, com UMA
    dívida desviada por gate (`divida_desviada`) e uma SEGUNDA dívida
    elegível — mesma técnica de `tests/app_aluno/test_acoes.py::
    _snapshot_com_gates_2_e_3_disparados` (a segunda dívida é o mínimo
    necessário para o motor produzir um snapshot válido com `elegiveis` não
    vazio ao mesmo tempo que a primeira permanece bloqueada/desviada)."""
    caso = caso_completo()
    respostas_segunda_divida = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_ELEGIVEL)
    divida_elegivel = montar_divida(respostas_segunda_divida, _DIVIDA_ID_ELEGIVEL)

    externos = dict(caso.parametros_externos)
    if parametros_externos is not None:
        externos.update(parametros_externos)

    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_desviada, divida_elegivel),
        **externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros, anterior=anterior, evento=evento)


def _divida_bloqueada_gate1_informacao(caso: CasoCompleto) -> Divida:
    """Dívida que o Gate 1 bloqueia por falta de informação estrutural —
    `STATUS_DIVIDA = QUITADA_A_CONFIRMAR` (`engine/gates.py::
    aplicar_gate_1_informacao`, primeiro ramo) — mesma condição citada por
    `AC-47`."""
    return replace(
        montar_divida(caso.respostas, caso.DIVIDA_ID),
        SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
        STATUS_DIVIDA=STATUS_DIVIDA.QUITADA_A_CONFIRMAR,
    )


def _divida_bloqueada_gate2_ou_3(
    caso: CasoCompleto, *, renegociacao: bool, troca: bool
) -> Divida:
    """Dívida desviada pelo Gate 2 (`RISCO_MATERIAL_IMINENTE`) ou Gate 3
    (`RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE`) — mesma técnica de T-84."""
    return replace(
        montar_divida(caso.respostas, caso.DIVIDA_ID),
        SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
        RENEGOCIACAO_PENDENTE=renegociacao,
        TROCA_PENDENTE=troca,
    )


# ---------------------------------------------------------------------------
# AC-45 — ACAO_ID idêntico entre dois snapshots consecutivos da mesma ação.
# Mudança 1 (ACAO_ID em AcaoRequerida, OQ-10) — ENTREGUE pela Rodada 2 de
# motor-calculo; o xfail(strict) de T-90 foi removido por T-119A.
# ---------------------------------------------------------------------------


def test_ac45_acao_id_identico_entre_dois_snapshots_consecutivos() -> None:
    """`AC-45` — a mesma dívida bloqueada por Gate 2/3 em dois cálculos
    consecutivos (o segundo com `anterior`/`evento` preenchidos, como um
    recálculo real do Bloco 11) produz, nos dois snapshots, uma
    `AcaoRequerida` cujo `ACAO_ID` é idêntico — a resposta de `B11.01` dada
    no primeiro continua vinculada à mesma ação no segundo."""
    caso = caso_completo()
    divida_desviada = _divida_bloqueada_gate2_ou_3(caso, renegociacao=True, troca=False)

    primeiro_snapshot = _montar_snapshot(divida_desviada=divida_desviada)
    assert len(primeiro_snapshot.ORDEM_ACOES) > 0, "o caso de prova precisa disparar um gate"

    segundo_snapshot = _montar_snapshot(
        divida_desviada=divida_desviada,
        anterior=primeiro_snapshot,
        evento=EVENTO_RECALCULO.INFORMACAO_MATERIAL_CONHECIDA,
    )
    assert len(segundo_snapshot.ORDEM_ACOES) > 0, "o recálculo precisa manter a ação desviada"

    acao_id_primeiro = acao_id_de(primeiro_snapshot.ORDEM_ACOES[0])
    acao_id_segundo = acao_id_de(segundo_snapshot.ORDEM_ACOES[0])
    assert acao_id_primeiro == acao_id_segundo


# ---------------------------------------------------------------------------
# AC-46 — cada tipo abre exclusivamente sua pergunta de resultado, os quatro
# tipos cobertos. Mudanças 1, 2 e 3 (TIPO_ACAO em AcaoRequerida, ação de
# informação do Gate 1, ação de economia fora dos gates — OQ-10/OQ-13/OQ-14/
# OQ-15) — ENTREGUES; o xfail(strict) de T-90 foi removido por T-119A.
# ---------------------------------------------------------------------------


def test_ac46_cada_tipo_abre_exclusivamente_sua_pergunta_de_resultado() -> None:
    """`AC-46` — para os quatro tipos de ação, `perguntas_do_bloco_11`
    devolve exatamente a pergunta de resultado correspondente, e nenhuma das
    outras três seria aberta: a asserção verifica, para CADA uma das quatro
    `AcaoRequerida` reais produzidas por gates/orçamento distintos, que a
    pergunta devolvida é a certa e que ela é diferente das perguntas dos
    outros três tipos."""
    caso = caso_completo()
    ids_resultado = {"B11.03-INF", "B11.03-REN", "B11.03-TRO", "B11.03-ECO"}
    registros_de_resultado = {r.ID: r for r in _REGISTROS_REAIS if r.ID in ids_resultado}
    assert len(registros_de_resultado) == 4, "as quatro perguntas de resultado precisam existir"

    divida_unica = montar_divida(caso.respostas, caso.DIVIDA_ID)
    divida_informacao = _divida_bloqueada_gate1_informacao(caso)
    divida_renegociacao = _divida_bloqueada_gate2_ou_3(caso, renegociacao=True, troca=False)
    divida_troca = _divida_bloqueada_gate2_ou_3(caso, renegociacao=False, troca=True)

    snapshot_informacao = _montar_snapshot(divida_desviada=divida_informacao)
    snapshot_renegociacao = _montar_snapshot(divida_desviada=divida_renegociacao)
    snapshot_troca = _montar_snapshot(divida_desviada=divida_troca)
    snapshot_economia = _montar_snapshot(
        divida_desviada=divida_unica,
        parametros_externos={"economia_nao_identificada": converter_para_dinheiro("400,00")},
    )

    # Cada cenário precisa de fato produzir a ação correspondente — quando
    # as três mudanças chegarem, os quatro `ORDEM_ACOES` abaixo deixam de
    # ser vazios/incompletos e passam a conter a ação do tipo esperado.
    assert len(snapshot_informacao.ORDEM_ACOES) > 0, "Gate 1 precisa emitir a ação de informação"
    assert len(snapshot_renegociacao.ORDEM_ACOES) > 0, (
        "Gate 3 precisa emitir a ação de renegociação"
    )
    assert len(snapshot_troca.ORDEM_ACOES) > 0, "Gate 3 precisa emitir a ação de troca"
    assert len(snapshot_economia.ORDEM_ACOES) > 0, "a economia precisa ser emitida fora dos gates"

    pergunta_informacao = perguntas_do_bloco_11(
        snapshot_informacao.ORDEM_ACOES[0], _REGISTROS_REAIS
    )
    pergunta_renegociacao = perguntas_do_bloco_11(
        snapshot_renegociacao.ORDEM_ACOES[0], _REGISTROS_REAIS
    )
    pergunta_troca = perguntas_do_bloco_11(snapshot_troca.ORDEM_ACOES[0], _REGISTROS_REAIS)
    pergunta_economia = perguntas_do_bloco_11(snapshot_economia.ORDEM_ACOES[0], _REGISTROS_REAIS)

    assert pergunta_informacao.ID == "B11.03-INF"
    assert pergunta_renegociacao.ID == "B11.03-REN"
    assert pergunta_troca.ID == "B11.03-TRO"
    assert pergunta_economia.ID == "B11.03-ECO"
    # Cada tipo abre exclusivamente a sua pergunta — as quatro são distintas
    # entre si (nunca a mesma pergunta abrindo para tipos diferentes).
    assert len(
        {pergunta_informacao.ID, pergunta_renegociacao.ID, pergunta_troca.ID, pergunta_economia.ID}
    ) == 4


# ---------------------------------------------------------------------------
# AC-47 — dívida bloqueada pelo Gate 1 tem ação de tipo informação em
# ORDEM_ACOES. Mudança 2 (Gate 1 emitir AcaoRequerida) — ENTREGUE; o
# xfail(strict) de T-90 foi removido por T-119A.
# ---------------------------------------------------------------------------


def test_ac47_divida_bloqueada_pelo_gate_1_tem_acao_de_tipo_informacao() -> None:
    """`AC-47` — uma dívida com `STATUS_DIVIDA = QUITADA_A_CONFIRMAR`
    (`GATE_PENDENTE.INFORMACAO`, Gate 1) precisa ter, em `ORDEM_ACOES`, uma
    `AcaoRequerida` referente ao mesmo `DIVIDA_ID` — a dívida travada nunca
    fica sem ação reportável."""
    caso = caso_completo()
    divida_bloqueada = _divida_bloqueada_gate1_informacao(caso)

    snapshot = _montar_snapshot(divida_desviada=divida_bloqueada)

    divida_id_bloqueada = divida_bloqueada.DIVIDA_ID
    acoes_da_divida = [a for a in snapshot.ORDEM_ACOES if a.DIVIDA_ID == divida_id_bloqueada]
    assert len(acoes_da_divida) > 0, (
        "esperada ao menos uma AcaoRequerida em ORDEM_ACOES para a dívida "
        "bloqueada pelo Gate 1"
    )
    tipo_da_acao = tipo_acao_de(acoes_da_divida[0])
    registro_informacao = next(r for r in _REGISTROS_REAIS if r.ID == "B11.03-INF")
    assert tipo_da_acao == _extrair_valor_tipo_acao(registro_informacao)


# ---------------------------------------------------------------------------
# AC-48 — tipagem de renegociação/troca. Mudança 1 (TIPO_ACAO em
# AcaoRequerida, OQ-14: Gate 3 + RENEGOCIACAO_PENDENTE/TROCA_PENDENTE) —
# ENTREGUE; o xfail(strict) de T-90 foi removido por T-119A.
# ---------------------------------------------------------------------------


def test_ac48_tipagem_de_renegociacao_e_de_troca() -> None:
    """`AC-48` — dívida com `RENEGOCIACAO_PENDENTE = True` e
    `TROCA_PENDENTE = False` tem sua ação tipada como intervenção/
    renegociação; dívida com `TROCA_PENDENTE = True` e
    `RENEGOCIACAO_PENDENTE = False` tem sua ação tipada como troca — os dois
    tipos distintos, extraídos do registro REAL (`OQ-13` aberta, nenhum
    literal aqui)."""
    caso = caso_completo()
    divida_renegociacao = _divida_bloqueada_gate2_ou_3(caso, renegociacao=True, troca=False)
    divida_troca = _divida_bloqueada_gate2_ou_3(caso, renegociacao=False, troca=True)

    snapshot_renegociacao = _montar_snapshot(divida_desviada=divida_renegociacao)
    snapshot_troca = _montar_snapshot(divida_desviada=divida_troca)

    assert len(snapshot_renegociacao.ORDEM_ACOES) > 0
    assert len(snapshot_troca.ORDEM_ACOES) > 0

    tipo_renegociacao = tipo_acao_de(snapshot_renegociacao.ORDEM_ACOES[0])
    tipo_troca = tipo_acao_de(snapshot_troca.ORDEM_ACOES[0])

    registro_renegociacao = next(r for r in _REGISTROS_REAIS if r.ID == "B11.03-REN")
    registro_troca = next(r for r in _REGISTROS_REAIS if r.ID == "B11.03-TRO")

    assert tipo_renegociacao == _extrair_valor_tipo_acao(registro_renegociacao)
    assert tipo_troca == _extrair_valor_tipo_acao(registro_troca)
    assert tipo_renegociacao != tipo_troca


# ---------------------------------------------------------------------------
# AC-49 — emissão da ação de economia conforme ECONOMIA_POTENCIAL_IMEDIATA.
# Mudança 3 (ação de economia fora do fluxo de gates, OQ-15) — ENTREGUE; o
# xfail(strict) de T-90 foi removido por T-119A.
# ---------------------------------------------------------------------------


def test_ac49_acao_de_economia_conforme_economia_potencial_imediata() -> None:
    """`AC-49` — com `ECONOMIA_POTENCIAL_IMEDIATA > 0` (gasto fantasma
    identificado, `B2.09`/`B2.10`/`B2.10A`), existe em `ORDEM_ACOES` uma
    ação do tipo correção/economia; com `ECONOMIA_POTENCIAL_IMEDIATA = 0`
    (o caso completo padrão, sem gasto fantasma), nenhuma ação desse tipo é
    emitida."""
    caso = caso_completo()
    divida_elegivel_unica = montar_divida(caso.respostas, caso.DIVIDA_ID)
    registro_economia = next(r for r in _REGISTROS_REAIS if r.ID == "B11.03-ECO")
    tipo_economia = _extrair_valor_tipo_acao(registro_economia)

    snapshot_sem_economia = _montar_snapshot(divida_desviada=divida_elegivel_unica)
    tipos_sem_economia = {tipo_acao_de(a) for a in snapshot_sem_economia.ORDEM_ACOES}
    assert tipo_economia not in tipos_sem_economia, (
        "sem gasto fantasma identificado (ECONOMIA_POTENCIAL_IMEDIATA = 0), "
        "nenhuma ação de correção/economia deveria ser emitida"
    )

    snapshot_com_economia = _montar_snapshot(
        divida_desviada=divida_elegivel_unica,
        parametros_externos={"economia_nao_identificada": converter_para_dinheiro("400,00")},
    )
    tipos_com_economia = {tipo_acao_de(a) for a in snapshot_com_economia.ORDEM_ACOES}
    assert tipo_economia in tipos_com_economia, (
        "com ECONOMIA_POTENCIAL_IMEDIATA > 0, esperada uma ação de "
        "correção/economia em ORDEM_ACOES"
    )
