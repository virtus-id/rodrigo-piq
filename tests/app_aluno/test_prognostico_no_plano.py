"""`T-171`/`T-172` — o capítulo "Seu prognóstico: três caminhos" (`RF-77`, `RF-78`).

Snapshots do motor REAL, como em `test_curso_e_incomodo.py`. O app só lê o
snapshot; o verde só existe com a resposta de `B3.C01A`.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.pdf import renderizar_html_do_plano
from report.plano import (
    carregar_textos_canonicos,
    formatar_dinheiro_br,
    montar_contexto_plano,
)
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo


def _snapshot(extra: object | None = None) -> SnapshotOrdem:
    valores: dict[str, object] = {}
    if extra is not None:
        valores["CONTRIBUICAO_EXTRA_MENSAL"] = extra
    caso = caso_completo(DIVIDA_ID="D-A", valores_caso=valores)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(montar_divida(caso.respostas, "D-A"),),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    return calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.1"))


def _cores(snapshot: SnapshotOrdem) -> list[str]:
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    return [caminho.cor for caminho in contexto.prognostico.caminhos]


def test_sem_resposta_extra_mostra_vermelho_e_azul() -> None:
    assert _cores(_snapshot()) == ["vermelho", "azul"]


def test_com_valor_extra_mostra_tambem_o_verde() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    assert snapshot.estado_inputs.CONTRIBUICAO_EXTRA_MENSAL == Decimal("500.00")
    assert _cores(snapshot) == ["vermelho", "azul", "verde"]


def test_resposta_zero_nao_gera_verde() -> None:
    assert _cores(_snapshot(converter_para_dinheiro("0"))) == ["vermelho", "azul"]


def test_snapshot_sem_prognostico_nao_tem_capitulo() -> None:
    antigo = dataclasses.replace(_snapshot(), prognostico=None)
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(antigo, textos)
    assert contexto.prognostico is None
    html = renderizar_html_do_plano(contexto, textos)
    assert "Se nada mudar" not in html
    assert "Seu plano em números" in html and 'class="numeros"' in html


def test_pdf_traz_os_tres_caminhos_com_os_numeros_do_snapshot() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos)
    for classe in ("caminho-vermelho", "caminho-azul", "caminho-verde"):
        assert classe in html
    assert "Se nada mudar" in html and "Seguindo o seu plano" in html


def _caminhos(snapshot: SnapshotOrdem):  # type: ignore[no-untyped-def]
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    return {caminho.cor: caminho for caminho in contexto.prognostico.caminhos}


def test_cada_caminho_e_uma_linha_com_veredito_barra_e_numeros() -> None:
    caminhos = _caminhos(_snapshot(converter_para_dinheiro("500,00")))
    for caminho in caminhos.values():
        assert caminho.veredito and len(caminho.destaques) <= 4
        assert 1 <= caminho.mes_fim <= caminho.escala
    vermelho = caminhos["vermelho"]
    assert vermelho.veredito.startswith("No Mês ")
    assert [r for r, _ in vermelho.destaques][:2] == [
        "Dívida inicial",
        "Primeira quitação prevista",
    ]
    assert caminhos["azul"].veredito.startswith("Quitação prevista em")
    assert caminhos["azul"].mes_fim == caminhos["azul"].escala
    assert [r for r, _ in caminhos["azul"].destaques] == [
        "Aporte extra inicial / mês",
        "Total projetado de pagamentos",
    ]
    assert caminhos["verde"].mes_fim <= caminhos["azul"].mes_fim
    assert caminhos["verde"].nota.startswith("O mesmo plano, com mais R$ 500 por mês")


def test_veredito_traz_o_total_pago_por_mes_vindo_do_motor() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    prog = snapshot.prognostico
    assert prog is not None and prog.com_extra is not None
    caminhos = _caminhos(snapshot)
    assert (
        "Até R$" in caminhos["azul"].veredito
        and "para dívidas por mês" in caminhos["azul"].veredito
    )
    assert "Até R$" in caminhos["verde"].veredito and caminhos["verde"].veredito.endswith(
        "por mês."
    )
    # Snapshot anterior, sem o valor: o veredito perde só a segunda frase.
    antigo = dataclasses.replace(
        snapshot,
        prognostico=dataclasses.replace(prog, PAGAMENTO_MENSAL_PLANO=None),
    )
    veredito = _caminhos(antigo)["azul"].veredito
    assert "Até R$" not in veredito and veredito.startswith("Quitação prevista em")


def test_verde_diz_quanto_antecipa_com_a_conta_vinda_do_motor() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    extra = snapshot.prognostico.com_extra  # type: ignore[union-attr]
    assert extra is not None
    verde = _caminhos(snapshot)["verde"]
    if extra.MESES_ANTECIPADOS > 0:
        assert "antes." in verde.veredito
        assert f"{extra.MESES_ANTECIPADOS} " in verde.veredito


def test_pdf_mostra_uma_barra_por_caminho_na_mesma_escala() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos)
    assert html.count('class="caminho caminho-') == 3
    assert "Seu plano em números" in html and "qual caminho seguir" not in html


def test_verde_traz_o_ataque_total_e_a_economia_frente_ao_plano_base() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    caminhos = _caminhos(snapshot)
    extra = snapshot.prognostico.com_extra  # type: ignore[union-attr]
    assert extra is not None and extra.ATAQUE_MENSAL_TOTAL is not None
    aporte = dict(caminhos["verde"].destaques)["Aporte extra inicial / mês"]
    assert aporte.startswith("R$")
    if extra.ECONOMIA_CUSTO > 0:
        assert caminhos["verde"].economia.startswith("Economia frente ao plano base: R$")
    else:
        assert caminhos["verde"].economia == ""


def test_so_azul_e_verde_levam_marcos_e_o_quadro_de_dividas_dentro_do_bloco() -> None:
    import re

    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)
    assert contexto.prognostico is not None
    caminhos = {c.cor: c for c in contexto.prognostico.caminhos}
    assert caminhos["vermelho"].marcos == () and caminhos["vermelho"].itens == ()
    # O mês a mês e a tabela continuam lendo as quitações do vermelho.
    assert caminhos["vermelho"].quitacoes == tuple(
        sorted(
            (mes, 1)
            for _, mes in snapshot.prognostico.sem_acao.QUITACOES  # type: ignore[union-attr]
        )
    )
    for cor in ("azul", "verde"):
        caminho = caminhos[cor]
        assert caminho.marcos
        # Um item por marco, na mesma ordem: "M7 · Quita <nome curto>".
        assert [int(re.match(r"M(\d+)", t).group(1)) for t in caminho.itens] == [  # type: ignore[union-attr]
            mes for mes, _ in caminho.marcos
        ]
        assert all(re.fullmatch(r"M\d+ · Quita .+", texto) for texto in caminho.itens)
    html = renderizar_html_do_plano(contexto, textos)
    assert html.count('<ul class="caminho-itens">') == 2  # azul e verde, nunca o vermelho
    cap5 = html[: html.index('id="mural-do-plano"')]
    assert "Números nas barras" not in cap5 and "D9A400" not in cap5
    assert "anel dourado" not in cap5


def _html_com_extra() -> tuple[str, SnapshotOrdem]:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    return renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos), snapshot


def test_mural_e_cartoes_de_cada_mes_dos_dois_planos_sem_data_e_com_ancoras() -> None:
    import re

    html, snapshot = _html_com_extra()
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    planos = {p.cor: p for p in contexto.prognostico.detalhes}
    assert set(planos) == {"azul", "verde"}
    azul = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]
    assert len(planos["azul"].meses) == azul.PRAZO_TOTAL
    assert planos["azul"].meses[0].rotulo == "Mês 01"
    assert planos["azul"].meses[0].ancora == "mes-azul-01"
    assert planos["verde"].meses[-1].ultimo and planos["verde"].meses[-1].quitadas
    # Cada link do mural aponta para um cartão existente (e cada cartão tem id único).
    links = re.findall(r'class="mural-mes[^"]*" href="#([^"]+)"', html)
    ids = re.findall(r'<section class="pagina-mes [^"]*" id="([^"]+)"', html)
    assert links and set(links) == set(ids) and len(ids) == len(set(ids))
    assert "mural-do-plano" in html
    # Referência de mês, nunca data de calendário (ano ou nome de mês).
    capitulos = html.lower().split("seu plano detalhado")[-1].split("o que falta informar")[0]
    texto = re.sub(r"<[^>]+>", " ", capitulos)
    assert not re.search(r"\b(20\d\d|janeiro|fevereiro|março|abril|maio|junho|julho)\b", texto)


def test_sem_extra_so_o_plano_seguido_no_mural() -> None:
    snapshot = _snapshot()
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    assert [p.cor for p in contexto.prognostico.detalhes] == ["azul"]


def test_plano_antigo_sem_mes_a_mes_nao_traz_os_capitulos_detalhados() -> None:
    import dataclasses

    snapshot = _snapshot()
    assert snapshot.prognostico is not None
    antigo_prog = dataclasses.replace(snapshot.prognostico, MESES_DO_PLANO=())
    antigo = dataclasses.replace(snapshot, prognostico=antigo_prog)
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(antigo, textos), textos)
    assert "Seu plano detalhado" not in html and "Mês a mês, em detalhe" not in html


def test_capitulos_removidos_do_mes_1_nao_existem_mais() -> None:
    html, _ = _html_com_extra()
    assert "O que fazer no Mês 1" not in html and "checklist do Mês 1" not in html


def test_nome_curto_da_divida_vira_tipo_mais_credor_sem_banco() -> None:
    from dataclasses import replace

    from engine.estado import TIPO_DIVIDA
    from report.plano import VocabularioDoCaso, nomear_dividas_curtas

    snapshot = _snapshot()
    textos = carregar_textos_canonicos()
    base = snapshot.estado_inputs.dividas[0]
    cheque = replace(base, DIVIDA_ID="D-CHEQUE", TIPO_DIVIDA=TIPO_DIVIDA.CHEQUE_ESPECIAL)
    consignado = replace(base, DIVIDA_ID="D-CONS", TIPO_DIVIDA=TIPO_DIVIDA.CONSIGNADO)
    sem_credor = replace(base, DIVIDA_ID="D-SEM", TIPO_DIVIDA=TIPO_DIVIDA.CARTAO_ROTATIVO)
    vocabulario = VocabularioDoCaso(
        credores={"D-CHEQUE": "Banco Itaú", "D-CONS": "Banco do Brasil"}
    )
    nomes = nomear_dividas_curtas((cheque, consignado, sem_credor), textos, vocabulario)
    assert nomes == {
        "D-CHEQUE": "Cheque Itaú",
        "D-CONS": "Consignado Brasil",
        "D-SEM": "Cartão",
    }


def test_quando_cada_divida_termina_tem_uma_cor_por_coluna() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)
    tabela = contexto.quando_termina
    assert tabela is not None
    assert tabela.cores == ("vermelho", "azul", "verde")
    assert tabela.colunas == ("Se nada mudar", "Seu plano", "Acelerado")
    html = renderizar_html_do_plano(contexto, textos)
    for cor in ("vermelho", "azul", "verde"):
        assert f'class="coluna-{cor}"' in html
    # O título "Seu plano" não quebra linha (célula do cabeçalho sem quebra).
    assert "white-space: nowrap" in html


def test_plano_antigo_so_tem_a_coluna_azul() -> None:
    import dataclasses

    antigo = dataclasses.replace(_snapshot(), prognostico=None)
    contexto = montar_contexto_plano(antigo, carregar_textos_canonicos())
    assert contexto.quando_termina is not None
    assert contexto.quando_termina.cores == ("azul",)


def test_mural_troca_check_por_trofeu_e_diz_pagar_a_mais() -> None:
    html, snapshot = _html_com_extra()
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    for plano in contexto.prognostico.detalhes:
        com_quitacao = [m for m in plano.meses if m.quitadas]
        assert com_quitacao
        for mes in com_quitacao:
            assert len(mes.quitas) == len(mes.quitadas)
            assert all(q.startswith("Quita ") for q in mes.quitas)
        assert all(not m.quitas for m in plano.meses if not m.quitadas)
    inicio = html.index('id="mural-do-plano"')
    mural = html[inicio : html.index("Mês a mês, em detalhe", inicio)]
    assert mural.count('class="mural-trofeu"') >= 2  # um por plano, ao menos
    assert "Pagar a mais" in mural and "Ainda deve" in mural
    assert "Extra" not in mural.split("</h2>")[0]
    assert "além das parcelas de sempre" in html


def test_cada_mes_tem_uma_pagina_no_modelo_do_produto_com_a_conta_fechando() -> None:
    html, snapshot = _html_com_extra()
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    assert contexto.prognostico is not None
    for plano in contexto.prognostico.detalhes:
        for mes in plano.meses:
            assert mes.pagina is not None and mes.pagina.linhas
            assert mes.pagina.de_total.endswith(f" de {len(plano.meses)}")
    primeiro = contexto.prognostico.detalhes[0].meses[0].pagina
    assert primeiro is not None
    prog = snapshot.prognostico
    assert prog is not None and prog.MESES_DO_PLANO[0].TOTAL_PAGAR is not None
    assert primeiro.total_pagar == formatar_dinheiro_br(prog.MESES_DO_PLANO[0].TOTAL_PAGAR)
    assert html.count('<section class="pagina-mes ') == sum(
        len(p.meses) for p in contexto.prognostico.detalhes
    )
    for trecho in (
        "PLANO PREPARADO PARA VOCÊ",
        "VALORES POR DÍVIDA · EM REAIS",
        "COMO FECHA O MÊS",
        "QUANDO E COMO VOU EXECUTAR",
        "Período de pagamento:",
    ):
        assert trecho in html
    assert "Quitação prevista neste mês" in html  # a linha da dívida que acaba


def test_plano_antigo_sem_detalhe_por_divida_usa_o_cartao_simples() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    prog = snapshot.prognostico
    assert prog is not None
    simples = tuple(
        dataclasses.replace(
            m,
            DIVIDAS=(),
            SALDO_INICIAL_TOTAL=None,
            JUROS_TOTAL=None,
            HABITUAL_TOTAL=None,
            EXTRA_TOTAL=None,
            TOTAL_PAGAR=None,
        )
        for m in prog.MESES_DO_PLANO
    )
    antigo = dataclasses.replace(
        snapshot, prognostico=dataclasses.replace(prog, MESES_DO_PLANO=simples)
    )
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(antigo, textos), textos)
    assert '<div class="cartao-mes ' in html and "Pagar a mais: " in html


def _paginas_do_capitulo_7(n_dividas: int) -> tuple[int, int]:
    """(meses, páginas do capítulo 7) com `n_dividas` linhas de nome longo em cada mês."""
    from weasyprint import HTML

    from report.plano import ContextoLinhaDoMes

    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)
    assert contexto.prognostico is not None
    nome = "Empréstimo consignado (CAIXA ECONOMICA FEDERAL) · parcela R$ 292,55 · 2"
    detalhes = []
    for plano in contexto.prognostico.detalhes:
        meses = []
        for mes in plano.meses:
            assert mes.pagina is not None
            linhas = tuple(
                ContextoLinhaDoMes(
                    nome=f"{nome} {i}",
                    saldo_antes="191.417,92",
                    juros="1.800,93",
                    habitual="1.948,18",
                    extra="1.234,56",
                    total="3.182,74",
                    saldo_depois="191.270,67",
                    quita=i == 0 and bool(mes.quitadas),
                )
                for i in range(n_dividas)
            )
            pagina = dataclasses.replace(mes.pagina, linhas=linhas)
            meses.append(dataclasses.replace(mes, pagina=pagina))
        detalhes.append(dataclasses.replace(plano, meses=tuple(meses)))
    prognostico = dataclasses.replace(contexto.prognostico, detalhes=tuple(detalhes))
    contexto = dataclasses.replace(contexto, prognostico=prognostico)
    documento = HTML(string=renderizar_html_do_plano(contexto, textos)).render()

    def texto(caixa: object) -> str:
        pedacos = [getattr(caixa, "text", "")]
        for filho in getattr(caixa, "children", None) or []:
            pedacos.append(texto(filho))
        return " ".join(pedacos)

    paginas = [texto(p._page_box) for p in documento.pages]
    primeira = next(i for i, t in enumerate(paginas) if "VALORES POR DÍVIDA" in t)
    ultima = max(i for i, t in enumerate(paginas) if "PROJEÇÃO DE QUITAÇÃO" in t)
    return sum(len(p.meses) for p in detalhes), ultima - primeira + 1


def test_cada_mes_cabe_em_uma_pagina_mesmo_com_muitas_dividas() -> None:
    for n_dividas in (6, 9, 14, 20):
        meses, paginas = _paginas_do_capitulo_7(n_dividas)
        assert paginas == meses, f"{n_dividas} dívidas: {paginas} páginas para {meses} meses"
