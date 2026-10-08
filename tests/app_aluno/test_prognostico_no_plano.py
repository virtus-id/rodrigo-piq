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
from report.plano import carregar_textos_canonicos, montar_contexto_plano
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


def test_cada_caminho_e_uma_linha_com_veredito_barra_e_no_maximo_tres_numeros() -> None:
    caminhos = _caminhos(_snapshot(converter_para_dinheiro("500,00")))
    for caminho in caminhos.values():
        assert caminho.veredito and len(caminho.destaques) <= 3
        assert 1 <= caminho.mes_fim <= caminho.escala
    vermelho = caminhos["vermelho"].veredito
    assert "ainda deve" in vermelho or "sozinhas" in vermelho
    assert caminhos["azul"].veredito.startswith("Você quita tudo em")
    assert caminhos["azul"].mes_fim == caminhos["azul"].escala
    assert caminhos["verde"].mes_sombra == caminhos["verde"].escala
    assert caminhos["verde"].mes_fim <= caminhos["azul"].mes_fim


def test_verde_diz_quanto_antecipa_com_a_conta_vinda_do_motor() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    extra = snapshot.prognostico.com_extra  # type: ignore[union-attr]
    assert extra is not None
    verde = _caminhos(snapshot)["verde"]
    if extra.MESES_ANTECIPADOS > 0:
        assert "antes do plano" in verde.veredito
        assert f"{extra.MESES_ANTECIPADOS} " in verde.veredito


def test_pdf_mostra_uma_barra_por_caminho_na_mesma_escala() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos)
    assert html.count('class="caminho caminho-') == 3
    assert "Seu plano em números" in html and "qual caminho seguir" not in html


def test_cada_linha_traz_valor_a_mais_e_primeira_quitacao() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    caminhos = _caminhos(snapshot)
    for cor in ("azul", "verde"):
        rotulos = [rotulo for rotulo, _ in caminhos[cor].destaques]
        assert "Valor a mais por mês" in rotulos and len(rotulos) <= 4
    vermelho = dict(caminhos["vermelho"].destaques)
    assert vermelho["Valor a mais por mês"] == "Nenhum"
    extra = snapshot.prognostico.com_extra  # type: ignore[union-attr]
    assert extra is not None and extra.ATAQUE_MENSAL_TOTAL is not None
    assert dict(caminhos["verde"].destaques)["Valor a mais por mês"].startswith("R$")


def test_so_azul_e_verde_levam_marcos_na_barra_e_a_legenda_explica_cada_numero() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)
    assert contexto.prognostico is not None
    caminhos = {c.cor: c for c in contexto.prognostico.caminhos}
    assert caminhos["vermelho"].marcos == ()
    assert caminhos["azul"].marcos and caminhos["verde"].marcos
    # O mês a mês e a tabela continuam lendo as quitações do vermelho.
    assert caminhos["vermelho"].quitacoes == tuple(
        sorted(
            (mes, 1)
            for _, mes in snapshot.prognostico.sem_acao.QUITACOES  # type: ignore[union-attr]
        )
    )
    legenda = contexto.prognostico.legenda
    assert [numero for numero, _ in legenda] == [p.indice for p in contexto.ordem]
    assert [nome for _, nome in legenda] == [p.nome for p in contexto.ordem]
    html = renderizar_html_do_plano(contexto, textos)
    assert "Números nas barras:" in html and "sua primeira dívida quitada" in html
    assert all(nome in html for _, nome in legenda)


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
    ids = re.findall(r'<div class="cartao-mes [^"]*" id="([^"]+)"', html)
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
