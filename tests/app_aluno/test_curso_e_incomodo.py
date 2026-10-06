"""`T-352` a `T-354` — sobra zero, curso de entrada (Servidor Sem Dívidas) e
nota de incômodo no plano.

Os snapshots vêm do motor REAL (`calcular_plano` sobre os parâmetros de
`parameters/`), como em `test_plano_reserva_mobilizavel.py`: o contexto lê o
snapshot, e nenhuma regra de ordem muda (o motor não é tocado).

REGRAS: pedido do responsável do produto (2026-10-05); `GAB-04` (a palavra
"sobra" não aparece em plano de estabilização).
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import RespostasCaso
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.pdf import renderizar_html_do_plano
from report.plano import (
    ContextoPlano,
    carregar_textos_canonicos,
    montar_contexto_plano,
)
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_PARAMETROS_VERSAO = "1.0.1"
_ESTRUTURA_DO_CURSO = Path("docs/curso-ssd/estrutura.md")


def _snapshot(renda: Decimal | None = None, peso_b: int | None = None) -> SnapshotOrdem:
    """Duas dívidas (a segunda com a nota de incômodo pedida); `renda`
    sobrescreve `RENDA_PRINCIPAL`."""
    valores: dict[str, object] = {} if renda is None else {"RENDA_PRINCIPAL": renda}
    caso_a = caso_completo(DIVIDA_ID="D-A", valores_caso=valores)
    divida_b: dict[str, object] = {
        "TIPO_DIVIDA": "CONSIGNADO",
        "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("8.000,00"),
        "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("400,00"),
    }
    if peso_b is not None:
        divida_b["PESO_EMOCIONAL"] = peso_b
    respostas_b = montar_respostas_caso(
        valores_caso=valores, valores_divida=divida_b, DIVIDA_ID="D-B"
    )
    respostas = RespostasCaso(respostas=caso_a.respostas.respostas + respostas_b.respostas)
    estado = montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(respostas, "D-A"), montar_divida(respostas, "D-B")),
        **caso_a.parametros_externos,  # type: ignore[arg-type]
    )
    return calcular_plano(estado, FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO))


def _contexto(snapshot: SnapshotOrdem) -> ContextoPlano:
    return montar_contexto_plano(snapshot, carregar_textos_canonicos())


def _html(snapshot: SnapshotOrdem) -> str:
    textos = carregar_textos_canonicos()
    return renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos)


def _renda_para_resultado(resultado_desejado: Decimal) -> Decimal:
    """A renda que faz o resultado do mês valer `resultado_desejado`: parte
    do resultado do caso-base e ajusta a renda pela diferença (preparação do
    TESTE, não código de produção)."""
    base = _snapshot()
    resultado = base.diagnostico.RESULTADO_MENSAL_ATUAL
    assert isinstance(resultado, Decimal)
    return Decimal("8000.00") + (resultado_desejado - resultado)


# ---------------------------------------------------------------- sobra zero


def test_sobra_exatamente_zero_gera_plano_normal_sem_valor_extra() -> None:
    snapshot = _snapshot(renda=_renda_para_resultado(Decimal("0")))
    assert snapshot.diagnostico.RESULTADO_MENSAL_ATUAL == Decimal("0")
    contexto = _contexto(snapshot)

    assert contexto.MODO_ESTABILIZACAO is False
    assert contexto.cenario.value == "NORMAL"
    assert contexto.aviso_sem_valor_extra
    assert contexto.aviso_sem_valor_extra in _html(snapshot)


def test_aviso_de_sem_valor_extra_nao_aparece_quando_ha_valor_extra() -> None:
    snapshot = _snapshot()
    assert _contexto(snapshot).aviso_sem_valor_extra == ""


# --------------------------------------------------------------------- curso


def test_toda_aula_do_quadro_existe_na_estrutura_do_curso() -> None:
    estrutura = _ESTRUTURA_DO_CURSO.read_text(encoding="utf-8")
    numeros_do_curso = set(re.findall(r"^(\d+)\. ", estrutura, flags=re.MULTILINE))
    bruto = carregar_textos_canonicos().curso_ssd
    aulas = {str(n) for n in bruto["aulas"]}
    usadas = {str(n) for quadro in bruto["quadro_por_cenario"].values() for n in quadro}
    assert aulas <= numeros_do_curso
    assert usadas <= aulas


def test_plano_normal_traz_introducao_e_aulas_dos_metodos() -> None:
    contexto = _contexto(_snapshot())
    curso = contexto.curso_ssd
    assert curso is not None
    assert "Servidor Sem Dívidas" in curso.introducao
    assert "12" in {numero for numero, _, _ in curso.aulas}
    html = _html(_snapshot())
    assert curso.introducao in html
    assert "Aula 12" in html


def test_plano_de_estabilizacao_indica_as_aulas_de_gastos_e_renda_sem_a_palavra_sobra() -> None:
    snapshot = _snapshot(renda=_renda_para_resultado(Decimal("-500")))
    contexto = _contexto(snapshot)
    assert contexto.MODO_ESTABILIZACAO is True
    assert contexto.curso_ssd is not None
    assert {numero for numero, _, _ in contexto.curso_ssd.aulas} == {"5", "6", "19"}
    assert "sobra" not in _html(snapshot).lower()


# ------------------------------------------------------------------ incômodo


def test_nota_alta_em_divida_fora_do_topo_recebe_a_linha_e_o_aviso() -> None:
    contexto = _contexto(_snapshot(peso_b=9))
    por_id = {posicao.DIVIDA_ID: posicao for posicao in contexto.ordem}
    divida_b = por_id["D-B"]
    assert divida_b.indice > 1  # o cartão rotativo vem primeiro, pelo custo
    assert "nota 9" in divida_b.incomodo
    assert divida_b.aviso_incomodo
    assert por_id["D-A"].aviso_incomodo == ""


def test_nota_baixa_nao_gera_aviso() -> None:
    contexto = _contexto(_snapshot(peso_b=5))
    assert all(posicao.aviso_incomodo == "" for posicao in contexto.ordem)
    assert any("nota 5" in posicao.incomodo for posicao in contexto.ordem)


# ------------------------------------------------------------- ordem dos capítulos


def test_capitulos_do_pdf_abrem_com_resumo_dividas_ponto_de_partida_e_primeira_quitacao() -> None:
    html = _html(_snapshot())
    titulos = re.findall(
        r'<span class="secao-numero">(\d+)</span>\s*<h2[^>]*>([^<]*)</h2>', html
    )
    assert titulos[:5] == [
        ("1", "Seu plano em números"),
        ("2", "Suas dívidas, uma a uma"),
        ("3", "Seu ponto de partida"),
        ("4", "Sua primeira dívida quitada"),
        ("5", "O que fazer no Mês 1"),
    ]


def test_primeira_pagina_apresenta_o_plano_antes_do_primeiro_capitulo() -> None:
    html = _html(_snapshot())
    apresentacao = _contexto(_snapshot()).curso_ssd
    assert apresentacao is not None and apresentacao.apresentacao
    assert html.index(apresentacao.apresentacao_titulo) < html.index("Seu plano em números")
    assert all(paragrafo in html for paragrafo in apresentacao.apresentacao)


def test_ponto_de_partida_marca_entrada_e_saida_com_cor_e_etiqueta() -> None:
    html = _html(_snapshot())
    textos = carregar_textos_canonicos().ponto_de_partida
    marcadas = re.findall(
        r'<div class="linha (entrada|saida)"><span class="linha-rotulo">([^<]*)</span>', html
    )
    assert marcadas == [
        ("entrada", textos["renda"]),
        ("saida", textos["gastos"]),
        ("saida", textos["gastos_ocasionais"]),
        ("saida", textos["parcelas"]),
    ]
    assert textos["entrada_rotulo"] in html and textos["saida_rotulo"] in html
