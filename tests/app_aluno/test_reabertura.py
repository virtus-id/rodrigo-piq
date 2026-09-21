"""Testes de `app/casos/reabertura.py` — `RF-27`, `AC-33`, `AC-34`, `T-80`,
`T-85`.

Mesma técnica de `tests/app_aluno/test_coleta_dirigida.py` (T-75/T-76):
monta um `SnapshotOrdem` REAL via `calcular_plano`, com `D002` sinalizada
por `RENEGOCIACAO_PENDENTE=True` (Gate 3) e saldo inquitável no horizonte
para não violar `ErroOrdemInconsistente`.

Os testes de `AC-33` (`T-85`) usam o `id_pergunta`/`divida_id` já
conhecidos, passados como parâmetro explícito — a fixture "de ação de
informação com o campo já conhecido" pedida para esta tarefa, honesta
sobre o que é testável hoje: `campo_para_reabertura_informacao` (extrair
o campo a partir de uma `AcaoRequerida` real) está bloqueada por lacuna
de contrato do motor, sem `AcaoRequerida` de fixture nesta suíte para essa
função — ver `test_campo_para_reabertura_informacao_falha_ruidosamente`.

REGRAS: RF-27, AC-33, AC-34
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.casos.reabertura import (
    ErroCampoDeInformacaoIndeterminavel,
    campo_para_reabertura_informacao,
    divida_elegivel_para_reabertura_renegociacao,
    perguntas_pendentes_por_reabertura_informacao,
    perguntas_pendentes_por_reabertura_renegociacao,
)
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.carga import carregar_registros
from collection.respostas import Resposta, RespostasCaso
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

# Mesmo valor de T-75: saldo alto o bastante para nunca ser quitado dentro de
# P_HORIZONTE_MAXIMO_SIMULACAO.
_SALDO_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")

_QUESTIONARIO_VERSION = "1.0.0"  # collection/registros/bloco-07.yaml


def _montar_snapshot(*, renegociacao_em: str | None) -> SnapshotOrdem:
    """Mesma fixture de `tests/app_aluno/test_coleta_dirigida.py`."""
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

    caso = caso_completo()
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_d001, divida_d002),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def _resposta(divida_id: str, id_pergunta: str, valor: str) -> Resposta:
    return Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA=id_pergunta,
        item_id=divida_id,
        valor=valor,
        QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
        respondida_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_ac34_reabrir_renegociacao_torna_pendentes_exatamente_b7_05_a_b7_16() -> None:
    """`AC-34`, primeiro critério: reabrir a renegociação de `D002` torna
    pendentes exatamente as perguntas de `B7.05` a `B7.16` para aquela
    dívida, e nenhuma outra."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)
    colecao = carregar_registros()
    respostas = RespostasCaso(respostas=())

    pendencias = perguntas_pendentes_por_reabertura_renegociacao(
        snapshot, colecao.registros, respostas, _DIVIDA_ID_D002
    )

    ids = {p.ID for p in pendencias}
    esperado = {registro.ID for registro in colecao.registros if registro.bloco == 7}
    assert ids == esperado
    assert "B7.05" in ids
    assert "B7.16" in ids
    assert all(p.item_id == _DIVIDA_ID_D002 for p in pendencias)


def test_ac34_nenhuma_pergunta_anterior_a_b7_05_e_reexibida() -> None:
    """`AC-34`, primeiro critério (negativo): nenhum `ID` fora da faixa
    `B7.05`–`B7.16` (em particular `B7.01`–`B7.04`, tentativa anterior —
    fora do escopo transcrito, `collection/registros/bloco-07.yaml`)
    aparece na lista de pendências de reabertura."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)
    colecao = carregar_registros()
    respostas = RespostasCaso(respostas=())

    pendencias = perguntas_pendentes_por_reabertura_renegociacao(
        snapshot, colecao.registros, respostas, _DIVIDA_ID_D002
    )

    ids = {p.ID for p in pendencias}
    fora_da_faixa = {"B7.01", "B7.02", "B7.03", "B7.04", "B7.S01"}
    assert ids.isdisjoint(fora_da_faixa)


def test_valor_anterior_permanece_gravado_e_visivel_apos_reabertura() -> None:
    """Segundo critério: o valor anterior das perguntas reabertas
    permanece gravado e visível como valor atual — reabrir nunca apaga
    nem zera a resposta em `RespostasCaso`."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)
    colecao = carregar_registros()
    respostas = RespostasCaso(
        respostas=(_resposta(_DIVIDA_ID_D002, "B7.05", "OBJETIVO_RENEGOCIACAO_TESTE"),)
    )

    pendencias = perguntas_pendentes_por_reabertura_renegociacao(
        snapshot, colecao.registros, respostas, _DIVIDA_ID_D002
    )

    # B7.05 está na lista de reabertas mesmo já tendo resposta gravada —
    # "reaberta" e "respondida" coexistem por desenho (T-80).
    assert any(p.ID == "B7.05" and p.item_id == _DIVIDA_ID_D002 for p in pendencias)
    # O valor não foi apagado nem alterado por esta função — `RespostasCaso`
    # indexa por `ID_PERGUNTA`, não por `VARIAVEL_GRAVADA` (ver
    # `collection/respostas.py::RespostasCaso._indice`).
    assert (
        respostas.valor_no_item(_DIVIDA_ID_D002, "B7.05") == "OBJETIVO_RENEGOCIACAO_TESTE"
    )


def test_estado_do_caso_nao_muda_por_causa_da_reabertura() -> None:
    """Terceiro critério: nenhuma chamada a `app/casos/maquina.py::
    transicionar` (nem qualquer nome de `ESTADO_CASO`) aparece no módulo —
    auditoria por AST, mesma disciplina de `test_coleta_dirigida.py`."""
    import ast
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parent.parent.parent / "app" / "casos" / "reabertura.py"
    )
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    proibidos = {"transicionar", "ESTADO_CASO", "TABELA_TRANSICOES"}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            assert no.id not in proibidos, (
                f"identificador proibido {no.id!r} na linha {no.lineno} — "
                "reabertura não pode transicionar o estado do caso"
            )
        if isinstance(no, ast.ImportFrom):
            assert no.module != "app.casos.maquina", (
                "reabertura não importa a máquina de estados — reabrir "
                "não é uma transição (plano §7.1)"
            )


def test_faixa_declarada_no_registro_sem_lista_literal_de_id_em_py() -> None:
    """Quarto critério: nenhum literal de `ID` de pergunta (`B7.xx`)
    aparece hardcoded em `app/casos/reabertura.py` — a faixa nasce da
    leitura de `registro.bloco` (via `perguntas_do_bloco_7`, T-75), nunca
    de uma lista escrita à mão neste arquivo."""
    import ast
    import re
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parent.parent.parent / "app" / "casos" / "reabertura.py"
    )
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    padrao_id_pergunta = re.compile(r"^B\d+\.")
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            assert not padrao_id_pergunta.match(no.value), (
                f"literal de ID de pergunta {no.value!r} na linha {no.lineno} — "
                "a faixa deve vir do registro (registro.bloco), nunca de "
                "lista literal em .py"
            )


def test_divida_nao_candidata_nao_reabre_nada() -> None:
    """Reforço do primeiro critério: dívida sem `RENEGOCIACAO_PENDENTE`
    (não sinalizada em `ORDEM_ACOES`) não tem nenhuma pergunta reaberta —
    a decisão de elegibilidade continua vindo do motor, nunca da
    aplicação."""
    snapshot = _montar_snapshot(renegociacao_em=_DIVIDA_ID_D002)
    colecao = carregar_registros()
    respostas = RespostasCaso(respostas=())

    assert not divida_elegivel_para_reabertura_renegociacao(snapshot, _DIVIDA_ID_D001)
    pendencias = perguntas_pendentes_por_reabertura_renegociacao(
        snapshot, colecao.registros, respostas, _DIVIDA_ID_D001
    )
    assert pendencias == ()


def test_ordem_acoes_vazia_nao_reabre_nada() -> None:
    """Sem nenhuma ação de renegociação em `ORDEM_ACOES`, reabrir qualquer
    dívida não produz pendência — mesmo comportamento de `dividas_para_
    bloco_7` com `ORDEM_ACOES` vazia (T-75)."""
    snapshot = _montar_snapshot(renegociacao_em=None)
    colecao = carregar_registros()
    respostas = RespostasCaso(respostas=())

    assert snapshot.ORDEM_ACOES == () or all(
        acao.gate_origem != 3 for acao in snapshot.ORDEM_ACOES
    )
    pendencias = perguntas_pendentes_por_reabertura_renegociacao(
        snapshot, colecao.registros, respostas, _DIVIDA_ID_D002
    )
    assert pendencias == ()


# --- AC-33 (T-85): reabertura de campo isolado -----------------------------

_ID_PERGUNTA_B5_B03 = "B5.B03"


def test_ac33_reabrir_campo_isolado_torna_pendente_apenas_aquele_campo() -> None:
    """`AC-33`: reabrir o campo isolado `B5.B03` para `D001` torna pendente
    EXATAMENTE `B5.B03` — nenhuma outra pergunta do Bloco 5 aparece na
    lista, ao contrário da reabertura de faixa (`AC-34`)."""
    pendencias = perguntas_pendentes_por_reabertura_informacao(
        _ID_PERGUNTA_B5_B03, _DIVIDA_ID_D001
    )

    assert len(pendencias) == 1
    assert pendencias[0].ID == _ID_PERGUNTA_B5_B03
    assert pendencias[0].item_id == _DIVIDA_ID_D001


def test_ac33_nenhuma_outra_pergunta_do_bloco_5_e_devolvida() -> None:
    """`AC-33`, reforço: o conjunto de pendências não contém nenhum outro
    `ID` do Bloco 5 (`B5.B01`, `B5.B02`, `B5.B04`, ...) — a reabertura de
    campo isolado nunca degenera na faixa inteira do bloco."""
    colecao = carregar_registros()
    outros_ids_do_bloco_5 = {
        registro.ID
        for registro in colecao.registros
        if registro.bloco == 5 and registro.ID != _ID_PERGUNTA_B5_B03
    }

    pendencias = perguntas_pendentes_por_reabertura_informacao(
        _ID_PERGUNTA_B5_B03, _DIVIDA_ID_D001
    )

    ids_devolvidos = {p.ID for p in pendencias}
    assert ids_devolvidos == {_ID_PERGUNTA_B5_B03}
    assert ids_devolvidos.isdisjoint(outros_ids_do_bloco_5)


def test_ac33_campo_a_reabrir_e_parametro_nunca_lista_literal_no_modulo() -> None:
    """Terceiro critério de `T-85`: nenhum literal de `ID` de pergunta do
    Bloco 5 (`B5.xx`) aparece hardcoded em `app/casos/reabertura.py` — o
    campo a reabrir chega como parâmetro (`id_pergunta`), nunca de uma
    lista escrita à mão neste arquivo. Mesma auditoria de AST de
    `test_faixa_declarada_no_registro_sem_lista_literal_de_id_em_py`."""
    import ast
    import re
    from pathlib import Path

    caminho = (
        Path(__file__).resolve().parent.parent.parent / "app" / "casos" / "reabertura.py"
    )
    codigo_fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(caminho))

    padrao_id_pergunta = re.compile(r"^B\d+\.")
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            assert not padrao_id_pergunta.match(no.value), (
                f"literal de ID de pergunta {no.value!r} na linha {no.lineno} — "
                "o campo a reabrir deve vir de parâmetro, nunca de lista "
                "literal em .py"
            )


def test_ac33_estado_do_caso_nao_muda_por_causa_da_reabertura_de_campo() -> None:
    """Segundo critério de `T-85`: a auditoria de AST de
    `test_estado_do_caso_nao_muda_por_causa_da_reabertura` (T-80) já cobre
    o módulo inteiro (nenhum `import`/uso de `app.casos.maquina`,
    `transicionar`, `ESTADO_CASO` ou `TABELA_TRANSICOES`) — este teste
    confirma explicitamente, chamando a função de campo isolado, que ela
    não aciona nenhuma transição: a chamada não levanta nem depende de
    nada de `app/casos/maquina.py`."""
    import app.casos.reabertura as modulo_reabertura

    assert not hasattr(modulo_reabertura, "transicionar")
    assert not hasattr(modulo_reabertura, "ESTADO_CASO")

    # A própria chamada não exige nem manipula estado de caso algum — só
    # os dois parâmetros explícitos (id_pergunta, divida_id).
    pendencias = perguntas_pendentes_por_reabertura_informacao(
        _ID_PERGUNTA_B5_B03, _DIVIDA_ID_D001
    )
    assert pendencias != ()


def test_responder_o_campo_reaberto_fecha_a_pendencia_sem_reabrir_o_bloco() -> None:
    """Quarto critério de `T-85`: responder `B5.B03` (gravar valor em
    `RespostasCaso`) não é o que fecha a pendência aqui — quem decide
    "ainda pendente" é o CONJUNTO DE REABERTURAS explicitamente reaberto
    (mesmo desenho de `perguntas_pendentes_por_reabertura_renegociacao`,
    T-80): esta função sempre devolve a MESMA pendência única para o par
    (id_pergunta, divida_id) pedido, nunca a faixa inteira do bloco —
    "fechar a pendência" é o chamador (fora do escopo desta tarefa) parar
    de pedir a reabertura de B5.B03 depois que ela for respondida, sem que
    isso jamais implique reabrir nenhuma outra pergunta do Bloco 5."""
    respostas = RespostasCaso(
        respostas=(_resposta(_DIVIDA_ID_D001, _ID_PERGUNTA_B5_B03, "1000,00"),)
    )

    pendencias = perguntas_pendentes_por_reabertura_informacao(
        _ID_PERGUNTA_B5_B03, _DIVIDA_ID_D001
    )

    # O valor gravado permanece visível — responder não apaga nada.
    assert respostas.valor_no_item(_DIVIDA_ID_D001, _ID_PERGUNTA_B5_B03) == "1000,00"
    # E a pendência devolvida continua sendo exclusivamente B5.B03 — nunca
    # o Bloco 5 inteiro, mesmo com a resposta já gravada.
    assert {p.ID for p in pendencias} == {_ID_PERGUNTA_B5_B03}


def test_campo_para_reabertura_informacao_falha_ruidosamente_hoje() -> None:
    """A parte BLOQUEADA de `T-85`: `campo_para_reabertura_informacao`
    levanta `ErroCampoDeInformacaoIndeterminavel` para qualquer `acao`
    recebida, porque nenhuma `AcaoRequerida` publicada pelo motor hoje
    contém informação sobre qual `RegistroPergunta.ID` reabrir — lacuna
    de contrato distinta de `TIPO_ACAO` (`OQ-13`)/`ACAO_ID` (`OQ-10`),
    sem Open Question correspondente na spec `app-aluno` (ver a nota
    extensa do módulo e da exceção). Mesma disciplina de `acao_id_de`/
    `tipo_acao_de` (T-83/T-84): a fronteira falha nomeando a lacuna, nunca
    escolhe um campo do Bloco 5 por padrão."""
    with pytest.raises(ErroCampoDeInformacaoIndeterminavel):
        campo_para_reabertura_informacao(object())
