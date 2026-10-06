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
    assert "Se nada mudar" not in renderizar_html_do_plano(contexto, textos)


def test_pdf_traz_os_tres_caminhos_com_os_numeros_do_snapshot() -> None:
    snapshot = _snapshot(converter_para_dinheiro("500,00"))
    textos = carregar_textos_canonicos()
    html = renderizar_html_do_plano(montar_contexto_plano(snapshot, textos), textos)
    for classe in ("caminho-vermelho", "caminho-azul", "caminho-verde"):
        assert classe in html
    assert "Se nada mudar" in html and "Seguindo o seu plano" in html
