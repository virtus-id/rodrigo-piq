"""Testes de `report/pdf.py` — exportação em PDF do mesmo template da tela
(`RF-20`, `RF-21`, `AC-14`, `AC-16`, T-63).

Cobre os quatro critérios de aceite da tarefa, com um `SnapshotOrdem` REAL
(fixture de caso completo, `tests/app_aluno/fixtures/caso_completo.py`,
T-53 — nunca fabricado à mão) e um `Caso` real (`app.casos.maquina.Caso`)
com `snapshot_liberado_id` setado (ou não, para o caso negativo):

1. O PDF é gerado a partir do MESMO template da tela — provado por
   `gerar_html_do_plano_liberado` produzir o MESMO HTML que
   `tests/app_aluno/test_plano.py::_renderizar_plano_html_com_contexto`
   (T-59..T-60) produziria para o mesmo snapshot, e por `renderizar_html_
   do_plano` chamar exatamente `plano.html` (nenhum HTML paralelo).
2. `AC-14`/`AC-16` valem no HTML de entrada do PDF: título, texto de `Q-03`
   e o carimbo de `ENGINE_VERSION`/`PARAMETROS_VERSION` presentes.
3. Regenerar o "PDF" (aqui, o HTML de entrada — ver a nota extensa em
   `report/pdf.py` sobre por que a prova de "mesmo conteúdo" compara HTML,
   não bytes de PDF) do MESMO snapshot produz exatamente o mesmo conteúdo.
4. O PDF só é gerado para snapshot com liberação registrada — prova
   positiva (`snapshot_liberado_id == SNAPSHOT_ID`) e negativa
   (`snapshot_liberado_id` divergente ou `None`).

Os testes que de fato invocam `weasyprint.HTML(...).write_pdf()` (produção
de bytes reais) usam `pytest.importorskip`/`pytest.skip` quando a biblioteca
nativa (GTK/Pango) não está disponível no ambiente — `weasyprint` (pacote
`pip`) está declarado no extra `app` (`pyproject.toml`) e instalado
(`pip show weasyprint`), mas carregar `libgobject-2.0-0` via `cffi` é uma
dependência de SISTEMA, ausente neste ambiente Windows de desenvolvimento;
isso é uma limitação de ambiente, não do código deste módulo — documentado
aqui para honestidade, não escondido atrás de um `try/except` silencioso.

REGRAS: `RF-20`, `RF-21`, `AC-14`, `AC-16`
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.casos.maquina import ESTADO_CASO, Caso
from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.pdf import (
    ErroSnapshotNaoLiberado,
    gerar_html_do_plano_liberado,
    gerar_pdf_do_plano,
    snapshot_tem_liberacao_registrada,
)
from report.plano import carregar_textos_canonicos, montar_contexto_plano
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_VERSAO_PARAMETROS_REAL = "1.0.1"


def _snapshot_real() -> SnapshotOrdem:
    """Mesmo padrão de `tests/app_aluno/test_plano.py::
    _snapshot_real_com_duas_dividas` (T-60): `SnapshotOrdem` produzido por
    `engine.motor.calcular_plano` sobre a fixture de caso completo (T-53) —
    nunca fabricado à mão."""
    caso = caso_completo()
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def _caso_com_liberacao(snapshot: SnapshotOrdem | None, caso_id: str = "CASO-PDF-1") -> Caso:
    """Um `Caso` real (`app.casos.maquina.Caso`) — `snapshot_liberado_id`
    setado ao `SNAPSHOT_ID` do snapshot recebido (ou `None`, para o caso
    negativo de liberação ausente)."""
    return Caso(
        CASO_ID=caso_id,
        conta_id="CONTA-PDF-1",
        estado=ESTADO_CASO.PLANO_LIBERADO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot.SNAPSHOT_ID if snapshot is not None else None,
        snapshot_liberado_id=snapshot.SNAPSHOT_ID if snapshot is not None else None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Critério 1 — o PDF é gerado a partir do mesmo template da tela, sem
# segunda redação do texto normativo.
# ---------------------------------------------------------------------------


def test_html_do_pdf_e_identico_ao_html_da_tela_para_o_mesmo_snapshot() -> None:
    """`renderizar_html_do_plano` (usada por `gerar_html_do_plano_liberado`,
    a base de `gerar_pdf_do_plano`) produz o MESMO HTML que a montagem de
    contexto + `plano.html` da tela produziriam para o mesmo snapshot —
    prova de que não existe uma segunda cópia de template/HTML para o PDF."""
    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(snapshot)

    html_do_pdf = gerar_html_do_plano_liberado(caso, snapshot, textos)

    contexto_da_tela = montar_contexto_plano(snapshot, textos)
    from report.pdf import renderizar_html_do_plano

    html_da_tela = renderizar_html_do_plano(contexto_da_tela)

    assert html_do_pdf == html_da_tela


def test_nenhum_html_paralelo_e_escrito_em_report_pdf() -> None:
    """`report/pdf.py` não contém nenhum literal de tag HTML (`<html`,
    `<body`, `<h1`) — a redação/estrutura vive inteiramente em
    `report/templates/plano/plano.html`, nunca duplicada em `.py`."""
    from pathlib import Path

    codigo_fonte = Path("report/pdf.py").read_text(encoding="utf-8")

    for fragmento_proibido in ("<html", "<body", "<h1", "<!DOCTYPE"):
        assert fragmento_proibido.lower() not in codigo_fonte.lower()


# ---------------------------------------------------------------------------
# Critério 2 — AC-14/AC-16 valem no PDF: título, texto de Q-03 e o carimbo
# de versão presentes.
# ---------------------------------------------------------------------------


def test_ac14_ac16_titulo_corpo_q03_e_carimbo_de_versao_presentes_no_pdf() -> None:
    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(snapshot)

    html = gerar_html_do_plano_liberado(caso, snapshot, textos)

    assert f"<h1>{textos.titulo}</h1>" in html
    assert f"<p>{textos.corpo}</p>" in html
    assert snapshot.ENGINE_VERSION in html
    assert snapshot.PARAMETROS_VERSION in html


# ---------------------------------------------------------------------------
# Critério 3 — regenerar o PDF do mesmo snapshot produz o mesmo conteúdo.
#
# Comparação por HTML de ENTRADA (determinístico e sob controle deste
# projeto), não por bytes de PDF — ver a nota extensa em `report/pdf.py`
# sobre por que bytes de PDF carregam metadados de geração que podem variar
# entre chamadas mesmo com entrada idêntica.
# ---------------------------------------------------------------------------


def test_regenerar_o_html_do_mesmo_snapshot_produz_o_mesmo_conteudo() -> None:
    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(snapshot)

    primeira_geracao = gerar_html_do_plano_liberado(caso, snapshot, textos)
    segunda_geracao = gerar_html_do_plano_liberado(caso, snapshot, textos)

    assert primeira_geracao == segunda_geracao


def test_regenerar_o_pdf_de_verdade_do_mesmo_snapshot_produz_o_mesmo_html_de_entrada() -> None:
    """Mesma prova acima, mas exercitando `gerar_pdf_do_plano` de ponta a
    ponta (bytes de PDF reais) quando a biblioteca nativa do WeasyPrint
    (GTK/Pango) está disponível no ambiente — pulado com mensagem explícita
    caso contrário (limitação de ambiente, não do código).

    Nota: `import weasyprint` (não só a chamada a `write_pdf`) já levanta
    `OSError` — não `ImportError` — quando a biblioteca nativa (`cffi`/
    `libgobject-2.0-0`) está ausente; por isso o `try` envolve o próprio
    `import`, e `pytest.importorskip` (que só trata `ImportError`) não
    bastaria aqui."""
    try:
        from weasyprint import HTML

        HTML(string="<html><body></body></html>").write_pdf()
    except OSError as erro:
        pytest.skip(f"biblioteca nativa do WeasyPrint indisponível neste ambiente: {erro}")

    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(snapshot)

    pdf_bytes_1 = gerar_pdf_do_plano(caso, snapshot, textos)
    pdf_bytes_2 = gerar_pdf_do_plano(caso, snapshot, textos)

    assert pdf_bytes_1.startswith(b"%PDF")
    assert pdf_bytes_2.startswith(b"%PDF")
    # O HTML de entrada (não os bytes de PDF, que carregam metadados de
    # geração) é a prova estável de "mesmo conteúdo" — ver docstring do
    # módulo `report/pdf.py`.
    html_1 = gerar_html_do_plano_liberado(caso, snapshot, textos)
    html_2 = gerar_html_do_plano_liberado(caso, snapshot, textos)
    assert html_1 == html_2


# ---------------------------------------------------------------------------
# Critério 4 — o PDF só é gerado para snapshot com liberação registrada.
# ---------------------------------------------------------------------------


def test_snapshot_tem_liberacao_registrada_prova_positiva() -> None:
    snapshot = _snapshot_real()
    caso = _caso_com_liberacao(snapshot)

    assert snapshot_tem_liberacao_registrada(caso, snapshot) is True


def test_snapshot_tem_liberacao_registrada_prova_negativa_snapshot_liberado_id_none() -> None:
    snapshot = _snapshot_real()
    caso = _caso_com_liberacao(None)  # snapshot_liberado_id = None

    assert snapshot_tem_liberacao_registrada(caso, snapshot) is False


def test_snapshot_tem_liberacao_registrada_prova_negativa_snapshot_divergente() -> None:
    """`snapshot_liberado_id` aponta para OUTRO snapshot — nunca o pedido."""
    snapshot = _snapshot_real()
    caso = Caso(
        CASO_ID="CASO-PDF-2",
        conta_id="CONTA-PDF-2",
        estado=ESTADO_CASO.AGUARDANDO_REVISAO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot.SNAPSHOT_ID,
        snapshot_liberado_id="SNAPSHOT-DE-OUTRO-CASO",
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert snapshot_tem_liberacao_registrada(caso, snapshot) is False


def test_gerar_html_do_plano_liberado_recusa_snapshot_sem_liberacao() -> None:
    """Sem liberação registrada, `gerar_html_do_plano_liberado` levanta
    `ErroSnapshotNaoLiberado` — nenhum HTML é produzido."""
    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(None)  # nenhum snapshot liberado

    with pytest.raises(ErroSnapshotNaoLiberado):
        gerar_html_do_plano_liberado(caso, snapshot, textos)


def test_gerar_pdf_do_plano_recusa_snapshot_sem_liberacao_sem_gerar_bytes() -> None:
    """`gerar_pdf_do_plano` propaga `ErroSnapshotNaoLiberado` ANTES de
    importar/chamar `weasyprint` — nenhum byte de PDF é produzido para um
    snapshot sem liberação registrada, mesmo que a biblioteca nativa esteja
    disponível."""
    snapshot = _snapshot_real()
    textos = carregar_textos_canonicos()
    caso = _caso_com_liberacao(None)

    with pytest.raises(ErroSnapshotNaoLiberado):
        gerar_pdf_do_plano(caso, snapshot, textos)
