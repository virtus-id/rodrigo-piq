"""Testes de `app/casos/coleta_dirigida.py` — `RF-17`, `AC-19`, `T-75`, `T-76`.

Mesma técnica de `tests/app_aluno/test_acoes.py` (T-74): monta um
`SnapshotOrdem` REAL via `calcular_plano`, sobrescrevendo os booleanos de
gate de `Divida` (sempre `False` na saída de `montar_divida`, T-49) via
`dataclasses.replace`. Uma dívida com saldo altíssimo
(`_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE`) garante que a dívida bloqueada
nunca é quitada dentro do horizonte de simulação — sem isso o motor
recusaria com `ErroOrdemInconsistente` (mesma nota de T-74).

`D002` é o `DIVIDA_ID` da dívida com `RENEGOCIACAO_PENDENTE = True`
(critério de aceite 1: "com ação de renegociação só para D002").

Os testes de `dividas_para_bloco_8`/`perguntas_do_bloco_8` (T-76) reaproveitam
a MESMA fixture `_montar_snapshot`, estendida com o parâmetro `troca_em`, para
provar que Bloco 7 e Bloco 8 abrem pelo mesmo mecanismo
(`dividas_por_gate_e_campo`) sem vazamento cruzado.

REGRAS: RF-17, AC-19
"""

from __future__ import annotations

from dataclasses import replace

from app.casos.coleta_dirigida import (
    dividas_para_bloco_7,
    dividas_para_bloco_8,
    perguntas_do_bloco_7,
    perguntas_do_bloco_8,
)
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import carregar_registros
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_PARAMETROS_VERSAO = "1.0.1"

_DIVIDA_ID_D001 = "D001"
_DIVIDA_ID_D002 = "D002"

# Mesmo valor de T-74: saldo alto o bastante para nunca ser quitado dentro de
# P_HORIZONTE_MAXIMO_SIMULACAO — necessário para a dívida desviada por gate
# não aparecer em ORDEM_QUITACAO (o que faria publicar_ORDEM_QUITACAO recusar
# com ErroOrdemInconsistente).
_SALDO_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")


def _montar_snapshot(
    *,
    renegociacao_em: str | None,
    risco_em: str | None = None,
    troca_em: str | None = None,
) -> SnapshotOrdem:
    """Monta um `SnapshotOrdem` real com duas ou três dívidas:

    - `D001`: sempre elegível, sem gate disparado — garante que o motor tem
      ao menos uma dívida para ranquear (mesma necessidade de T-74).
    - `D002`: elegível também, a menos que `renegociacao_em`/`risco_em`/
      `troca_em` aponte para ela — quando apontada, é sobrescrita com
      `RENEGOCIACAO_PENDENTE=True` (Gate 3), `RISCO_MATERIAL_IMINENTE=True`
      (Gate 2) ou `TROCA_PENDENTE=True` (Gate 3, T-76), com saldo inquitável
      para não violar a publicação da ordem.
    """
    respostas_d001 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D001)
    divida_d001 = montar_divida(respostas_d001, _DIVIDA_ID_D001)

    respostas_d002 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D002)
    divida_d002 = montar_divida(respostas_d002, _DIVIDA_ID_D002)

    if renegociacao_em == _DIVIDA_ID_D002:
        divida_d002 = replace(
            divida_d002,
            SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
            RENEGOCIACAO_PENDENTE=True,
        )
    if risco_em == _DIVIDA_ID_D002:
        divida_d002 = replace(
            divida_d002,
            SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
            RISCO_MATERIAL_IMINENTE=True,
        )
    if troca_em == _DIVIDA_ID_D002:
        divida_d002 = replace(
            divida_d002,
            SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
            TROCA_PENDENTE=True,
        )

    caso = caso_completo()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_d001, divida_d002),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def test_ac19_bloco_7_abre_so_para_d002_com_renegociacao() -> None:
    """`AC-19` — com ação de renegociação só para `D002`, o Bloco 7 é
    exibido para `D002` e para nenhuma outra dívida."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)

    dividas = dividas_para_bloco_7(snapshot)

    assert dividas == (_DIVIDA_ID_D002,)
    assert _DIVIDA_ID_D001 not in dividas


def test_lista_vem_de_ordem_acoes_sem_criterio_proprio() -> None:
    """Segundo critério: a lista de dívidas abertas vem de `ORDEM_ACOES` —
    prova indireta: a dívida `D001` (sem gate disparado, mesmo saldo/taxa
    "normais") nunca aparece, mesmo tendo os mesmos campos financeiros que
    `D002` teria se não fosse desviada por gate."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)

    ids_em_ordem_acoes = {acao.DIVIDA_ID for acao in snapshot.ORDEM_ACOES}
    dividas = dividas_para_bloco_7(snapshot)

    assert set(dividas) <= ids_em_ordem_acoes
    assert _DIVIDA_ID_D001 not in dividas


def test_ordem_acoes_vazia_nao_abre_bloco_7() -> None:
    """Terceiro critério: com `ORDEM_ACOES` vazia, o Bloco 7 não abre —
    nenhuma dívida sinalizada, nenhum gate disparado."""
    snapshot = _montar_snapshot(renegociacao_em=None)

    assert snapshot.ORDEM_ACOES == ()
    assert dividas_para_bloco_7(snapshot) == ()


def test_gate_2_risco_nao_abre_bloco_7() -> None:
    """Gate 2 (contenção de risco) desvia para `ORDEM_ACOES`, mas não é
    renegociação — não deve abrir o Bloco 7. Prova que `gate_origem == 2`
    é ignorado por `dividas_para_bloco_7` (só `gate_origem == 3` conta)."""
    snapshot = _montar_snapshot(renegociacao_em=None, risco_em=_DIVIDA_ID_D002)

    assert len(snapshot.ORDEM_ACOES) > 0, "o caso de prova precisa disparar o Gate 2"
    assert all(acao.gate_origem == 2 for acao in snapshot.ORDEM_ACOES)
    assert dividas_para_bloco_7(snapshot) == ()


def test_nenhum_criterio_de_elegibilidade_e_avaliado_na_aplicacao() -> None:
    """Quarto critério: `dividas_para_bloco_7` não lê `SALDO_DEVEDOR_ATUAL`,
    `TAXA_EFETIVA_MENSAL_NORMALIZADA` nem qualquer outro campo financeiro
    além de `gate_origem`/`RENEGOCIACAO_PENDENTE` — auditado por AST, não só
    por inspeção manual."""
    import ast
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parent.parent.parent
        / "app"
        / "casos"
        / "coleta_dirigida.py"
    )
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    campos_financeiros_proibidos = {
        "SALDO_DEVEDOR_ATUAL",
        "TAXA_EFETIVA_MENSAL_NORMALIZADA",
        "CET",
        "PARCELA_CONTRATUAL",
        "PAGAMENTO_MENSAL_EFETIVO",
        "VALOR_QUITACAO_HOJE",
    }
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute):
            assert no.attr not in campos_financeiros_proibidos, (
                f"campo financeiro {no.attr!r} lido na linha {no.lineno} — "
                "nenhum critério de elegibilidade deve ser avaliado aqui"
            )


def test_perguntas_do_bloco_7_sao_so_as_de_divida_id_e_bloco_7() -> None:
    """As perguntas devolvidas pertencem exclusivamente ao Bloco 7
    (`escopo_repeticao: DIVIDA_ID`, `bloco: 7`) — nenhuma do Bloco 5 nem do
    Bloco 11, que também usam repetição por dívida/ação."""
    colecao = carregar_registros()

    perguntas = perguntas_do_bloco_7(colecao.registros)

    assert len(perguntas) > 0
    assert all(registro.bloco == 7 for registro in perguntas)
    ids = {registro.ID for registro in perguntas}
    assert "B7.05" in ids
    assert "B7.16" in ids


def test_ac19_bloco_7_nao_abre_para_qualquer_outra_dividia_alem_da_sinalizada() -> None:
    """Reforço do critério 1, com três dívidas: só a sinalizada por
    `RENEGOCIACAO_PENDENTE` abre o Bloco 7."""
    respostas_d003 = montar_respostas_caso(DIVIDA_ID="D003")
    divida_d003 = montar_divida(respostas_d003, "D003")

    respostas_d001 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D001)
    divida_d001 = montar_divida(respostas_d001, _DIVIDA_ID_D001)

    respostas_d002 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D002)
    divida_d002 = replace(
        montar_divida(respostas_d002, _DIVIDA_ID_D002),
        SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
        RENEGOCIACAO_PENDENTE=True,
    )

    caso = caso_completo()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_d001, divida_d002, divida_d003),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    snapshot = calcular_plano(estado, parametros)

    dividas = dividas_para_bloco_7(snapshot)

    assert dividas == (_DIVIDA_ID_D002,)


def test_bloco_8_abre_pelo_mesmo_mecanismo_do_bloco_7_sem_codigo_especifico() -> None:
    """Primeiro critério de `T-76`: `dividas_para_bloco_7` e
    `dividas_para_bloco_8` são chamadas finas da MESMA função genérica
    `dividas_por_gate_e_campo` — não duas implementações paralelas."""
    import inspect

    corpo_bloco_7 = inspect.getsource(dividas_para_bloco_7)
    corpo_bloco_8 = inspect.getsource(dividas_para_bloco_8)

    assert "dividas_por_gate_e_campo" in corpo_bloco_7
    assert "dividas_por_gate_e_campo" in corpo_bloco_8
    # Nenhuma das duas reimplementa o laço de filtragem por ORDEM_ACOES —
    # só a genérica itera sobre `acoes_em_acompanhamento`.
    assert "acoes_em_acompanhamento" not in corpo_bloco_7
    assert "acoes_em_acompanhamento" not in corpo_bloco_8


def test_ac19_bloco_8_abre_so_para_d002_com_troca() -> None:
    """Segundo critério de `T-76`: dívida com ação de troca abre
    `B8.01`–`B8.15`; dívida sem, não abre nada — `D001` (sem `TROCA_PENDENTE`)
    nunca aparece."""
    snapshot = _montar_snapshot(renegociacao_em=None, troca_em=_DIVIDA_ID_D002)

    dividas = dividas_para_bloco_8(snapshot)

    assert dividas == (_DIVIDA_ID_D002,)
    assert _DIVIDA_ID_D001 not in dividas


def test_divida_sem_troca_nao_abre_bloco_8() -> None:
    """Segundo critério de `T-76`, reforço: sem nenhuma dívida com
    `TROCA_PENDENTE`, o Bloco 8 não abre para ninguém."""
    snapshot = _montar_snapshot(renegociacao_em=None)

    assert dividas_para_bloco_8(snapshot) == ()


def test_renegociacao_e_troca_em_dividas_distintas_abrem_blocos_diferentes_sem_vazamento() -> (
    None
):
    """Terceiro critério de `T-76` — prova de não-vazamento cruzado: DUAS
    dívidas distintas, uma só com `RENEGOCIACAO_PENDENTE=True` (`D002`) e
    outra só com `TROCA_PENDENTE=True` (`D003`). O Bloco 7 abre exclusivamente
    para `D002`; o Bloco 8 abre exclusivamente para `D003`. Nenhum dos dois
    campos vaza para o bloco do outro."""
    respostas_d001 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D001)
    divida_d001 = montar_divida(respostas_d001, _DIVIDA_ID_D001)

    respostas_d002 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D002)
    divida_d002 = replace(
        montar_divida(respostas_d002, _DIVIDA_ID_D002),
        SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
        RENEGOCIACAO_PENDENTE=True,
    )

    _DIVIDA_ID_D003 = "D003"
    respostas_d003 = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_D003)
    divida_d003 = replace(
        montar_divida(respostas_d003, _DIVIDA_ID_D003),
        SALDO_DEVEDOR_ATUAL=_SALDO_INQUITAVEL_NO_HORIZONTE,
        TROCA_PENDENTE=True,
    )

    caso = caso_completo()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_d001, divida_d002, divida_d003),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    snapshot = calcular_plano(estado, parametros)

    dividas_bloco_7 = dividas_para_bloco_7(snapshot)
    dividas_bloco_8 = dividas_para_bloco_8(snapshot)

    assert dividas_bloco_7 == (_DIVIDA_ID_D002,)
    assert dividas_bloco_8 == (_DIVIDA_ID_D003,)
    # Não-vazamento cruzado explícito: a dívida de renegociação não aparece
    # no Bloco 8, e a dívida de troca não aparece no Bloco 7.
    assert _DIVIDA_ID_D003 not in dividas_bloco_7
    assert _DIVIDA_ID_D002 not in dividas_bloco_8
    assert set(dividas_bloco_7).isdisjoint(dividas_bloco_8)


def test_nenhuma_decisao_de_qual_e_o_caso_e_tomada_na_aplicacao() -> None:
    """Quarto critério de `T-76`: auditoria por AST — nem `dividas_para_
    bloco_7` nem `dividas_para_bloco_8` contêm um literal de `TIPO_ACAO` ou
    parsing de `descricao`; a única diferença entre as duas chamadas é o
    literal de NOME DE CAMPO passado para `dividas_por_gate_e_campo`."""
    import ast
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parent.parent.parent
        / "app"
        / "casos"
        / "coleta_dirigida.py"
    )
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    proibidos_no_modulo = {"TIPO_ACAO", "split", "descricao"}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            assert no.id not in proibidos_no_modulo, (
                f"identificador proibido {no.id!r} na linha {no.lineno} — "
                "nenhuma decisão de 'qual é o caso' pode ser tomada aqui"
            )
        if isinstance(no, ast.Attribute):
            assert no.attr not in proibidos_no_modulo, (
                f"atributo proibido {no.attr!r} na linha {no.lineno}"
            )


def test_perguntas_do_bloco_8_sao_so_as_de_divida_id_e_bloco_8() -> None:
    """Mesmo padrão de `test_perguntas_do_bloco_7_sao_so_as_de_divida_id_e_
    bloco_7`, para o Bloco 8: as perguntas devolvidas pertencem
    exclusivamente ao Bloco 8 (`escopo_repeticao: DIVIDA_ID`, `bloco: 8`)."""
    colecao = carregar_registros()

    perguntas = perguntas_do_bloco_8(colecao.registros)

    assert len(perguntas) > 0
    assert all(registro.bloco == 8 for registro in perguntas)
    ids = {registro.ID for registro in perguntas}
    assert "B8.01" in ids
    assert "B8.15" in ids
