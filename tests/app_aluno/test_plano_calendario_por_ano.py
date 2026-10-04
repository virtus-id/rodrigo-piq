"""Calendário por ano em "Seu plano, mês a mês" — plano com mais de 12 meses.

Pedido do produto (2026-10-03): "e quando a pessoa tiver anos para pagar a
dívida? Mês a mês, vai se estender?". Com um cartão por mês, um plano de
3 anos virava páginas de cartões quase iguais. Acima de 12 meses, a grade
passa a ser um calendário: uma linha por ano, 12 meses lado a lado, com o
valor extra e as quitações do ano embaixo. `agrupar_grade_por_ano` só
reagrupa a lista que `montar_grade_meses` já leu do motor; nenhum número
novo é calculado (`AC-42`).
"""

from __future__ import annotations

import dataclasses
import re

from report.plano import (
    ContextoMesDaJornada,
    agrupar_grade_por_ano,
    carregar_textos_canonicos,
    montar_contexto_plano,
)
from tests.app_aluno.test_plano import (
    _renderizar_plano_html_com_contexto,
    _snapshot_real_com_duas_dividas,
)

_CARTAO = "Cartão de crédito rotativo (NUBANK)"
_CONSIGNADO = "Empréstimo consignado (BANCO DO BRASIL)"


def _grade(total_de_meses: int) -> tuple[ContextoMesDaJornada, ...]:
    """Grade sintética: o cartão é quitado no Mês 8 e o valor extra passa
    de R$ 300,00 para R$ 500,00 no Mês 9; o último mês é a chegada."""
    meses = []
    for mes in range(1, total_de_meses + 1):
        quitadas = (_CARTAO,) if mes == 8 else ()
        if mes == total_de_meses:
            tipo = "CHEGADA"
            quitadas = (_CONSIGNADO,)
        elif quitadas:
            tipo = "QUITACAO"
        else:
            tipo = "ATAQUE"
        meses.append(
            ContextoMesDaJornada(
                mes=mes,
                tipo=tipo,
                alvo=None if tipo == "CHEGADA" else _CARTAO,
                valor_extra=(
                    None if tipo == "CHEGADA" else "R$ 300,00" if mes <= 8 else "R$ 500,00"
                ),
                dividas_quitadas=quitadas,
                eh_primeira_vitoria=mes == 8,
                tem_aporte=False,
            )
        )
    return tuple(meses)


def test_plano_de_ate_12_meses_continua_com_os_cartoes() -> None:
    assert agrupar_grade_por_ano(_grade(12)) == ()
    assert agrupar_grade_por_ano(()) == ()


def test_plano_de_30_meses_vira_tres_linhas_de_ate_12_meses() -> None:
    anos = agrupar_grade_por_ano(_grade(30))

    assert [(ano.numero, ano.mes_inicio, ano.mes_fim) for ano in anos] == [
        (1, 1, 12),
        (2, 13, 24),
        (3, 25, 30),
    ]
    assert [len(ano.meses) for ano in anos] == [12, 12, 6]
    # Os meses são os mesmos objetos da grade, na mesma ordem.
    assert tuple(mes for ano in anos for mes in ano.meses) == _grade(30)


def test_cada_ano_traz_os_valores_extras_e_as_quitacoes_dele() -> None:
    anos = agrupar_grade_por_ano(_grade(30))

    assert anos[0].valores_extras == ("R$ 300,00", "R$ 500,00")
    assert anos[1].valores_extras == ("R$ 500,00",)
    assert anos[0].quitacoes == ((8, _CARTAO),)
    assert anos[1].quitacoes == ()
    assert anos[2].quitacoes == ((30, _CONSIGNADO),)


def _html_com_grade(total_de_meses: int) -> str:
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(_snapshot_real_com_duas_dividas(), textos)
    grade = _grade(total_de_meses)
    contexto = dataclasses.replace(
        contexto,
        grade_meses=grade,
        grade_anos=agrupar_grade_por_ano(grade),
        PRAZO_TOTAL_INT=total_de_meses,
    )
    return _renderizar_plano_html_com_contexto(contexto, textos)


def test_pdf_de_plano_longo_mostra_o_calendario_por_ano() -> None:
    textos = carregar_textos_canonicos().grade_meses
    html = _html_com_grade(30)

    assert 'class="calendario"' in html
    assert 'class="grade-meses"' not in html
    assert textos["introducao_anos"] in html
    assert "Mês 1 a 12" in html
    assert "Mês 13 a 24" in html
    assert "Mês 25 a 30" in html
    assert "Valor extra de cada mês: R$ 300,00, depois R$ 500,00" in html
    assert f"Mês 8: quitação de {_CARTAO}" in html


def test_pdf_de_plano_curto_continua_com_os_cartoes() -> None:
    html = _html_com_grade(10)

    assert 'class="grade-meses"' in html
    assert 'class="calendario"' not in html


def _rotulos_da_regua(html: str) -> list[str]:
    return re.findall(r'text-anchor="middle">(Ano \d+)</text>', html)


def test_regua_da_linha_do_tempo_marca_anos_em_plano_de_mais_de_dois_anos() -> None:
    # 30 meses: três faixas, a última com 6 meses, ainda com rótulo.
    assert _rotulos_da_regua(_html_com_grade(30)) == ["Ano 1", "Ano 2", "Ano 3"]
    # 26 meses: a terceira faixa tem só 2 meses e fica sem rótulo.
    assert _rotulos_da_regua(_html_com_grade(26)) == ["Ano 1", "Ano 2"]
    # Até 24 meses, a régua continua com os números de mês.
    assert _rotulos_da_regua(_html_com_grade(20)) == []
