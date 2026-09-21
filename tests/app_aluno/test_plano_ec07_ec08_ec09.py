"""Testes de `report/plano.py`/`report/templates/plano/{ordem_vazia,
estabilizacao,pendencias}.html` — `EC-07`, `EC-08`, `EC-09` (T-62).

Cada cenário é produzido por um `SnapshotOrdem` REAL (`engine.motor.
calcular_plano`), nunca fabricado à mão — mesmo padrão de
`tests/app_aluno/test_plano.py` (T-60) e `tests/invariantes/
test_gab04_estabilizacao.py` (`GAB-04`/`AC-11` do motor):

1. `EC-07` — `ORDEM_QUITACAO` vazia (`DIVIDA_ALVO_ATUAL is None`): a única
   dívida do caso tem `SALDO_DEVEDOR_ATUAL`/`PAGAMENTO_MENSAL_EFETIVO`
   respondidos como "não sei" (`caso_completo_com_divida_gab03`, mesma
   fixture de `AC-08`/`GAB-03`) — Gate 1 (`INFORMACAO_PENDENTE`,
   `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO`) a desvia para
   `ORDEM_ACOES`. Escolhido em vez de Gate 2/3 (`RISCO_MATERIAL_IMINENTE`/
   `RENEGOCIACAO_PENDENTE`) porque `engine/motor.py::_inventario` só exclui
   do cenário simulado dívida sem `SALDO_DEVEDOR_ATUAL` conhecido — uma
   dívida bloqueada por Gate 2/3 mas com saldo conhecido ainda entraria em
   `Cenario.ORDEM_QUITACAO` e violaria a checagem defensiva de
   `engine/ordem.py::publicar_ORDEM_QUITACAO` (`ErroOrdemInconsistente`,
   critério de aceite 4 de T-63) — comportamento correto do motor
   (congelado), não deste teste.

   Nota: hoje `engine/gates.py::aplicar_gate_1_informacao` sempre devolve
   `acao=None` (a extensão que faz Gate 1 emitir `AcaoRequerida` de tipo
   informação é dependência externa do slug `motor-calculo`, ver
   `tasks/app-aluno.tasks.md` "Dependências externas declaradas", que
   bloqueia `T-90`/`AC-47`) — então este cenário produz `ORDEM_QUITACAO` e
   `ORDEM_ACOES` ambas vazias hoje. O critério de aceite (`ORDEM_ACOES` em
   primeiro plano, nunca uma ordem vazia sem explicação) é satisfeito pelo
   TEMPLATE (`ordem_vazia.html` sempre explica a ausência de ataque, com ou
   sem ações listadas) e é reforçado por um segundo teste que prova, com
   `ORDEM_ACOES` sintética não-vazia (fila que HOJE só nasce de Gate 2/3),
   que a fila aparece em primeiro plano quando presente.
2. `EC-08` — `ORDEM_STATUS = PROVISORIA`: `CONFIRMACAO_FIM_CADASTRO = "NAO"`
   (`B5.FIM02`) produz `INVENTARIO_COMPLETO = False`
   (`app/montagem/estado.py::_inventario_completo`), que o motor rebaixa a
   `PROVISORIA` (`engine/ordem.py::consolidar_ORDEM_STATUS`, `AC-09`).
3. `EC-09` — `MODO_ESTABILIZACAO = True`: mesmo cenário numérico de `GAB-A`/
   `GAB-04` (`tests/invariantes/test_gab04_estabilizacao.py`), reproduzido
   aqui via `EstadoFinanceiro`/`Divida` construídos diretamente (mesmo
   padrão daquele arquivo) — resultado de caixa observado positivo (+200)
   com resultado mensal estrutural negativo.

REGRAS: `RF-21`, `RF-22`, `EC-07`, `EC-08`, `EC-09`
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_RESERVA,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_DIVIDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.estado import TIPO_RENDA as _TIPO_RENDA
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    ORDEM_STATUS,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.plano import (
    CENARIO_APRESENTACAO,
    ContextoAcaoRequerida,
    ContextoPlano,
    carregar_textos_canonicos,
    decidir_cenario_apresentacao,
    montar_contexto_plano,
)
from tests.app_aluno.fixtures.caso_completo import (
    caso_completo,
    caso_completo_com_divida_gab03,
)
from tests.fixtures.carregar import carregar_gab_c

_DIRETORIO_TEMPLATES_PLANO = (
    Path(__file__).resolve().parent.parent.parent / "report" / "templates" / "plano"
)
_VERSAO_PARAMETROS_REAL = "1.0.1"


def _renderizar_plano_html_com_contexto(contexto: ContextoPlano) -> str:
    """Mesmo padrão de `tests/app_aluno/test_plano.py::
    _renderizar_plano_html_com_contexto` (T-60), estendido com os campos
    novos de T-62 — nunca `dataclasses.asdict` (que converteria `ordem`/
    `acoes`/`pendencias`, dataclasses aninhados, em dicts sem atributo,
    incompatível com o acesso `posicao.indice` etc. dos templates)."""
    ambiente = Environment(
        loader=FileSystemLoader(str(_DIRETORIO_TEMPLATES_PLANO)),
        autoescape=select_autoescape(["html"]),
    )
    template = ambiente.get_template("plano.html")
    return template.render(
        titulo=contexto.titulo,
        corpo=contexto.corpo,
        ordem=contexto.ordem,
        PRAZO_TOTAL=contexto.PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=contexto.CUSTO_FUTURO_TOTAL,
        ENGINE_VERSION=contexto.ENGINE_VERSION,
        PARAMETROS_VERSION=contexto.PARAMETROS_VERSION,
        cenario=contexto.cenario,
        acoes=contexto.acoes,
        pendencias=contexto.pendencias,
        MODO_ESTABILIZACAO=contexto.MODO_ESTABILIZACAO,
        RESULTADO_CAIXA_OBSERVADO=contexto.RESULTADO_CAIXA_OBSERVADO,
    )


# ---------------------------------------------------------------------------
# EC-07 — ORDEM_QUITACAO vazia (DIVIDA_ALVO_ATUAL is None): a única dívida do
# caso é excluída do inventário simulável por Gate 1 (SALDO_DEVEDOR_ATUAL/
# PAGAMENTO_MENSAL_EFETIVO desconhecidos, mesma fixture de AC-08/GAB-03).
# ---------------------------------------------------------------------------


def _snapshot_ordem_vazia() -> SnapshotOrdem:
    caso = caso_completo_com_divida_gab03()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=date(2026, 3, 15),
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def test_ec07_ordem_quitacao_vazia_escolhe_cenario_ordem_vazia() -> None:
    """`EC-07`: com `DIVIDA_ALVO_ATUAL = None` (única dívida sem
    `SALDO_DEVEDOR_ATUAL` conhecido, excluída do inventário simulável pelo
    Gate 1), `decidir_cenario_apresentacao` escolhe `ORDEM_VAZIA` e o HTML
    renderizado explica a ausência de ataque — nunca uma ordem vazia sem
    explicação — em vez de mostrar o bloco de posições (vazio) do plano
    normal."""
    snapshot = _snapshot_ordem_vazia()

    assert snapshot.DIVIDA_ALVO_ATUAL is None
    assert snapshot.ORDEM_QUITACAO == ()
    assert decidir_cenario_apresentacao(snapshot) is CENARIO_APRESENTACAO.ORDEM_VAZIA

    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.cenario is CENARIO_APRESENTACAO.ORDEM_VAZIA
    assert contexto.ordem == ()

    html = _renderizar_plano_html_com_contexto(contexto)
    # Nenhuma seção de posição (posicao.html) é renderizada — a ordem está
    # vazia, e o HTML não pode sugerir uma ordem sem explicação.
    assert "Posição 1 de" not in html
    # O bloco de ordem_vazia.html (a explicação) está presente.
    assert "Nenhuma dívida pronta para ataque" in html


def test_ec07_ordem_acoes_e_o_conteudo_principal_quando_presente() -> None:
    """`EC-07`, segunda metade do critério: quando `ORDEM_ACOES` TEM
    conteúdo (fila que hoje só nasce de Gate 2/3 — Gate 1 ainda não emite
    `AcaoRequerida`, ver docstring do módulo), ela aparece em primeiro
    plano no HTML de `ordem_vazia.html`. Contexto sintético mínimo — só o
    suficiente para testar a INCLUSÃO do template, sem precisar de um
    `SnapshotOrdem` completo, já que `ContextoAcaoRequerida` já é, ele
    próprio, uma leitura pura de `AcaoRequerida` (T-62)."""
    ambiente = Environment(
        loader=FileSystemLoader(str(_DIRETORIO_TEMPLATES_PLANO)),
        autoescape=select_autoescape(["html"]),
    )
    template = ambiente.get_template("ordem_vazia.html")
    acao = ContextoAcaoRequerida(
        DIVIDA_ID="D-EC07",
        descricao="D-EC07: risco material iminente — ação exigida antes do ataque.",
        prioridade_excepcional=False,
    )

    html = template.render(acoes=(acao,))

    # T-92: ContextoAcaoRequerida.DIVIDA_ID é `str | None` (ação de economia,
    # RF-33, não tem dívida) — este teste usa uma ação de gate concreta
    # ("D-EC07"), então a asserção de não-nulidade documenta a garantia
    # antes do `in` (mypy --strict não aceita `str | None` como operando de
    # `in` sobre `str`).
    assert acao.DIVIDA_ID is not None
    assert acao.DIVIDA_ID in html
    assert acao.descricao in html


# ---------------------------------------------------------------------------
# EC-08 — ORDEM_STATUS = PROVISORIA (CONFIRMACAO_FIM_CADASTRO = "NAO" ->
# INVENTARIO_COMPLETO = False).
# ---------------------------------------------------------------------------


def _snapshot_provisorio() -> SnapshotOrdem:
    caso = caso_completo(valores_caso={"CONFIRMACAO_FIM_CADASTRO": "NAO"})
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=date(2026, 3, 15),
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def test_ec08_plano_provisorio_lista_pendencias_lidas_do_snapshot() -> None:
    """`EC-08`: `ORDEM_STATUS = PROVISORIA` produz `pendencias` não-nulo,
    com `inventario_incompleto = True` — leitura direta de
    `snapshot.estado_inputs.INVENTARIO_COMPLETO`, nunca recomputada."""
    snapshot = _snapshot_provisorio()

    assert snapshot.ORDEM_STATUS is ORDEM_STATUS.PROVISORIA
    assert snapshot.estado_inputs.INVENTARIO_COMPLETO is False

    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.pendencias is not None
    assert contexto.pendencias.inventario_incompleto is True

    html = _renderizar_plano_html_com_contexto(contexto)
    assert "provisório" in html.lower()


def test_ec08_plano_definitivo_nao_lista_pendencias() -> None:
    """Prova negativa: `GAB-C` (`tests/fixtures/carregar.py::carregar_gab_c`,
    a mesma fixture normativa de `tests/gabaritos/test_gabarito_c_
    recomendacao.py`) produz `ORDEM_STATUS = DEFINITIVA_NA_DATA` via
    `calcular_plano` ponta a ponta — e, nesse caso, `pendencias` é `None`:
    nada a relatar quando o plano não está `PROVISORIA`."""
    estado = carregar_gab_c()
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    snapshot = calcular_plano(estado, parametros)

    assert snapshot.ORDEM_STATUS is ORDEM_STATUS.DEFINITIVA_NA_DATA

    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.pendencias is None


# ---------------------------------------------------------------------------
# EC-09 — MODO_ESTABILIZACAO = True (mesmo cenário numérico de GAB-A/GAB-04).
# ---------------------------------------------------------------------------

# Termos que jamais podem rotular o observado positivo — mesma lista de
# `tests/regras/test_snapshot.py`/`test_gab04_estabilizacao.py` (AC-11).
_ROTULOS_PROIBIDOS = ("sobra", "superavit", "superávit")


def _divida_devido_sem_pagamento() -> Divida:
    """D001 de `GAB-A`/`GAB-04`: devido 1.200, efetivo 0."""
    return Divida(
        DIVIDA_ID="D001",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("24000"),
        VALOR_QUITACAO_HOJE=dinheiro("24000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("1200"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _divida_paga_em_dia() -> Divida:
    """D002 de `GAB-A`/`GAB-04`: devido 800, efetivo 800."""
    return Divida(
        DIVIDA_ID="D002",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("9600"),
        VALOR_QUITACAO_HOJE=dinheiro("9600"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("800"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _estado_gab04() -> EstadoFinanceiro:
    """Reproduz `GAB-A`/`GAB-04` — mesmo cenário de
    `tests/invariantes/test_gab04_estabilizacao.py::_estado_gab04`."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.MAIORIA,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.SEMANAL,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.MESMO_DIA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.MAIORIA,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.QUASE_TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.RAZOAVEL,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.RARAMENTE,
        REVISAO_SEMANAL=REVISAO_SEMANAL.MAIORIA,
    )
    sinais = SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
        MECANISMO_DEFICIT=frozenset(),
        HISTORICO_RECAIDA=SimNaoTalvez.NAO,
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
        PACTO="ESTABELECIDO",
        RISCO_IMPULSO="NENHUMA",
        LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
        NECESSIDADE_VITORIA=0,
        HISTORICO_ABANDONO=SimNaoTalvez.NAO,
        JANELA_NOVA_DIVIDA=None,
    )
    return EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 9, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("8000"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("6500"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("500"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("0"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(_divida_devido_sem_pagamento(), _divida_paga_em_dia()),
        perfil_comportamental=perfil,
        sinais_comportamentais=sinais,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=5,
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro("0"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro("0"),
        DINHEIRO_DISPONIVEL=dinheiro("0"),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )


def test_ec09_modo_estabilizacao_nunca_rotula_resultado_como_sobra() -> None:
    """`EC-09`: `MODO_ESTABILIZACAO = True` escolhe o cenário `ESTABILIZACAO`,
    e a palavra "sobra" (nem variantes) nunca qualifica
    `RESULTADO_CAIXA_OBSERVADO` — nem no contexto montado, nem no HTML
    renderizado por `estabilizacao.html`."""
    estado = _estado_gab04()
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    snapshot = calcular_plano(estado, parametros)

    assert snapshot.diagnostico.MODO_ESTABILIZACAO is True
    assert decidir_cenario_apresentacao(snapshot) is CENARIO_APRESENTACAO.ESTABILIZACAO

    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.cenario is CENARIO_APRESENTACAO.ESTABILIZACAO
    assert contexto.MODO_ESTABILIZACAO is True
    # `T-177`: o valor chega com `R$` do servidor (antes era `"200.00"` e o
    # template prefixava). O que este teste guarda é a REDAÇÃO — que o
    # resultado nunca seja chamado de "sobra" —, e isso continua abaixo.
    assert contexto.RESULTADO_CAIXA_OBSERVADO == "R$ 200,00"

    html = _renderizar_plano_html_com_contexto(contexto)
    html_minusculo = html.lower()
    for rotulo_proibido in _ROTULOS_PROIBIDOS:
        assert rotulo_proibido not in html_minusculo, (
            f"{rotulo_proibido!r} não pode qualificar RESULTADO_CAIXA_OBSERVADO "
            f"em modo estabilização (EC-09), mas apareceu no HTML renderizado"
        )
    # Prova positiva de que o resultado de caixa efetivamente aparece — o
    # teste acima não passaria trivialmente por ausência total do valor.
    assert "200.00" in html or "200,00" in html
    # Fase 2 condicional: nenhuma posição de ORDEM_QUITACAO é exibida no
    # bloco de estabilização.
    assert "Posição 1 de" not in html
