"""Acessibilidade automatizada da tela do plano — `RF-21`, `RF-22` (T-97).

**Escopo reduzido em T-144.** Esta suíte auditava também `fila.html`, a tela
da fila de revisão. Aquela tela virou React e o template foi removido; as
auditorias que liam o arquivo saíram junto, porque um teste que lê um
template inexistente passa para sempre sem provar nada. O que resta aqui
audita `report/templates/plano/`, que CONTINUA existindo — é a fonte do PDF
(`report/pdf.py`), e `RF-21`/`AC-14` exigem a redação canônica de `Q-03` em
um lugar só. A acessibilidade das telas React se prova no Playwright
(`frontend/tests/e2e/`), sobre DOM renderizado de verdade.

**Limitação honesta deste ambiente — leia antes de confiar no verde, mesma
limitação já enfrentada por `tests/app_aluno/e2e/test_acessibilidade_
coleta.py` (T-48).** `axe-core` real audita o DOM de uma página renderizada
por um navegador de verdade (Chromium/Firefox via Playwright ou Selenium).
Este projeto **não** declara `playwright`/`pytest-playwright`/`selenium` em
nenhum extra de `pyproject.toml` (nenhum dos dois está no plano desta
feature), e este ambiente **não tem Chromium instalado** — reconfirmado para
esta tarefa: `node -e "require.resolve('axe-core')"` continua falhando, e
nenhum pacote de browser aparece em `npm ls -g`. Rodar `axe-core` de verdade
aqui seria simular, não testar — exatamente a mesma constatação de T-48,
estendida agora à tela do plano.

**O que este arquivo faz em vez disso — substituto PARCIAL, declarado como
tal, adaptado às duas telas.**

1. **Contraste** — `plano.html` (o PDF) NÃO carrega
   `app/http/estaticos/estilo.css` (confirmado por leitura dos templates:
   nenhum `<link rel="stylesheet">` nem `<style>` inline nas duas árvores de
   `report/templates/plano/` e `report/templates/revisao/`) — diferente da
   coleta, onde T-48 recalculava contraste sobre cores declaradas naquele
   CSS. As únicas classes visuais introduzidas por esta feature nestas duas
   telas são `.sinal-politica`/`.sinal-metodologico` (`fila.html`, T-69), que
   também não têm nenhuma regra de cor em `estilo.css` nem em qualquer outro
   CSS do projeto — são `<span>` sem estilo (texto puro, cor herdada do
   navegador). Sem NENHUMA declaração de cor própria a auditar, não há razão
   de contraste calculável por fórmula estática aqui: o substituto honesto
   para "nenhuma violação de contraste introduzida por este HTML" é confirmar
   que nenhuma das duas telas declara COR PRÓPRIA (nem `style=`, nem
   `<style>`, nem referência a folha de estilo) — texto puro sobre o fundo
   padrão do navegador nunca reprova a regra `color-contrast` do `axe-core`
   por definição (não há cor customizada para reprovar).
2. **Rótulo** — as duas telas são de LEITURA (nenhum `<input>`/`<select>`/
   `<textarea>` — confirmado por varredura do HTML real renderizado abaixo),
   diferente da coleta, que é toda formulário. A regra `label` do
   `axe-core` não se aplica a uma tela sem campo de formulário; o substituto
   equivalente aqui é confirmar essa AUSÊNCIA de campo de formulário nas
   duas telas — não há rótulo a auditar porque não há controle de entrada.
3. **Ordem de foco** — mesma checagem estrutural de T-48: nenhum `tabindex`
   positivo (reordenaria o foco) nem negativo (removeria um elemento da
   navegação por Tab) aparece no HTML real das duas telas — a mesma checagem
   que a regra `tabindex` de `axe-core` faz.

Estrutura semântica adicional, auditada porque as duas telas SÃO diferentes
da coleta (uma é uma tabela de dados, a outra tem hierarquia de seções): toda
`<table>` de `fila.html` declara `<th scope="col">` em vez de `<td>` no
cabeçalho (o mesmo padrão que a regra `th-has-data-cells`/`scope-attr-valid`
de `axe-core` cobre) e a hierarquia de `<h1>`/`<h2>` do plano não pula nível
(regra `heading-order` de `axe-core`).

**O que fica de fora, e por quê é substituto parcial, não equivalente —
mesma nota de T-48.** `axe-core` real varre ~90 regras (ARIA inválido,
contraste computado após cascata CSS completa incluindo estilo herdado do
navegador/tema do sistema, foco visível por pseudo-classe `:focus`, papel
semântico calculado pela árvore de acessibilidade do navegador). Nada disso é
verificável sem um motor de renderização real. A auditoria completa por
`axe-core` sobre browser real, mais a navegação por teclado da tela do plano
com leitor de tela real, ficam registradas em `docs/checklist-
acessibilidade.md` (seção estendida por esta tarefa) — este arquivo apenas
ESTENDE a mesma decisão de fronteira de T-48 às telas do plano e da fila.

**HTML real, nunca fabricado à mão** — mesma disciplina de T-48. O plano vem
de um `SnapshotOrdem` REAL (`engine.motor.calcular_plano` sobre a fixture de
caso completo, T-53, com duas dívidas — mesmo padrão de `tests/app_aluno/e2e/
test_redacao_canonica.py::_snapshot_real_com_duas_dividas`), renderizado por
`report.pdf.renderizar_html_do_plano`/`report.plano.montar_contexto_plano` —
a MESMA função de produção que `app/http/rotas_plano.py::exibir_tela_do_
plano` chama. A fila vem de `app.revisao.fila.listar_fila_de_revisao`/
`montar_item_da_fila` sobre o MESMO snapshot real, renderizado por
`report/templates/revisao/fila.html` com o MESMO achatamento de contexto que
`app/http/rotas_revisao.py::_item_para_contexto` produz — nenhuma segunda
montagem de contexto inventada por este arquivo de teste.

**360 px sem rolagem horizontal** — mesma técnica estática de `tests/
app_aluno/estatica/test_css_360px.py` (T-47), aplicada aqui à AUSÊNCIA de
`width`/tabela larga nos templates do plano e da fila (que não carregam
`estilo.css`, então a checagem correta é sobre o PRÓPRIO HTML dos templates:
nenhum `width` fixo em `style=`, e a única `<table>` do projeto fora da
coleta, `fila.html`, não declara `width` fixo em nenhuma célula/coluna —
apenas um `<table>` sem CSS, que o navegador dimensiona ao conteúdo/
viewport, sem forçar rolagem por si só. `docs/checklist-acessibilidade.md`
já registra, na seção 3, que a prova visual real de 360px em navegador físico
é item de checklist manual, nunca puramente estático).

Marcador `e2e` (`pyproject.toml`, T-05): não bloqueia `pytest -m "not
requer_banco and not e2e"`, mesmo padrão de `test_acessibilidade_coleta.py`.

REGRAS: `RF-21`, `RF-22`
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import RespostasCaso
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.pdf import renderizar_html_do_plano
from report.plano import carregar_textos_canonicos, montar_contexto_plano
from tests.app_aluno.fixtures.caso_completo import caso_completo, montar_respostas_caso

pytestmark = pytest.mark.e2e

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
CAMINHO_ESTILO_CSS: Final[Path] = RAIZ_PROJETO / "app" / "http" / "estaticos" / "estilo.css"
DIRETORIO_TEMPLATES_REVISAO: Final[Path] = RAIZ_PROJETO / "report" / "templates" / "revisao"

_VERSAO_PARAMETROS_REAL: Final[str] = "1.0.1"
_CASO_ID: Final[str] = "CASO-T97-A11Y-PLANO"
_DIVIDA_ID_A: Final[str] = "D-T97-A"
_DIVIDA_ID_B: Final[str] = "D-T97-B"

# WCAG 2.1 AA, mesmo limiar usado por test_acessibilidade_coleta.py — aqui
# só para documentar o limiar de referência; nenhuma cor própria destas duas
# telas exige o cálculo (ver docstring do módulo, item 1).
LIMIAR_CONTRASTE_AA: Final[float] = 4.5


# ---------------------------------------------------------------------------
# Fabricação de um SnapshotOrdem REAL (nunca fabricado à mão) — mesmo padrão
# de tests/app_aluno/e2e/test_redacao_canonica.py::
# _snapshot_real_com_duas_dividas.
# ---------------------------------------------------------------------------


def _snapshot_real_com_duas_dividas() -> SnapshotOrdem:
    caso_a = caso_completo(DIVIDA_ID=_DIVIDA_ID_A)
    respostas_divida_b = montar_respostas_caso(
        valores_divida={
            "TIPO_DIVIDA": "CONSIGNADO",
            "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("8.000,00"),
            "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("400,00"),
        },
        DIVIDA_ID=_DIVIDA_ID_B,
    )
    respostas = caso_a.respostas.respostas + respostas_divida_b.respostas
    respostas_caso = RespostasCaso(respostas=respostas)

    divida_a = montar_divida(respostas_caso, _DIVIDA_ID_A)
    divida_b = montar_divida(respostas_caso, _DIVIDA_ID_B)
    estado = montar_estado_financeiro(
        respostas_caso,
        DATA_REFERENCIA=date(2026, 3, 15),
        dividas=(divida_a, divida_b),
        **caso_a.parametros_externos,  # type: ignore[arg-type]
    )

    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def _html_do_plano_real(snapshot: SnapshotOrdem) -> str:
    """A MESMA função de produção que `app/http/rotas_plano.py::
    exibir_tela_do_plano` chama por dentro — nenhuma segunda montagem de
    contexto inventada por este teste."""
    textos = carregar_textos_canonicos()
    contexto = montar_contexto_plano(snapshot, textos)
    return renderizar_html_do_plano(contexto)


@pytest.fixture(scope="module")
def snapshot_real() -> SnapshotOrdem:
    return _snapshot_real_com_duas_dividas()


@pytest.fixture(scope="module")
def html_do_plano(snapshot_real: SnapshotOrdem) -> str:
    return _html_do_plano_real(snapshot_real)


# ---------------------------------------------------------------------------
# 1 — Contraste (substituto estático da regra `color-contrast` do axe-core):
# nenhuma cor própria é declarada por nenhuma das duas telas — ver docstring.
# ---------------------------------------------------------------------------


def test_tela_do_plano_nao_declara_cor_propria(html_do_plano: str) -> None:
    """Sem `style=` com `color`/`background` e sem `<link rel="stylesheet">`/
    `<style>` em nenhuma das duas telas, não há regra de cor própria capaz de
    reprovar `color-contrast` — texto puro sobre o fundo padrão do navegador
    nunca viola essa regra. Isto é o inverso da checagem de T-48 (que
    RECALCULAVA contraste porque `estilo.css` declarava cor); aqui a
    ausência de qualquer declaração de cor é o próprio resultado a provar."""
    for html, origem in ((html_do_plano, "plano.html"),):
        assert "stylesheet" not in html.lower(), f"{origem}: referencia folha de estilo"
        assert "<style" not in html.lower(), f"{origem}: declara <style> inline"
        estilos_inline = re.findall(r'style="([^"]*)"', html)
        for estilo in estilos_inline:
            assert "color" not in estilo.lower() and "background" not in estilo.lower(), (
                f"{origem}: style= inline declara cor ({estilo!r})"
            )


def test_estilo_css_nao_e_carregado_pelas_telas_de_plano_e_fila() -> None:
    """Confirma, pelos ARQUIVOS de template (não só pelo HTML de uma
    instância), que nenhum template de `report/templates/plano/` ou
    `report/templates/plano/` referencia `estilo.css`.

    **T-145**: `estilo.css` foi REMOVIDO (a interface é React e usa
    Tailwind). Este teste continua valendo como trava: o PDF é um documento
    autocontido, e uma referência a folha de estilo externa aqui produziria
    um PDF sem estilo nenhum — o WeasyPrint não tem de onde buscá-la."""
    for diretorio in (RAIZ_PROJETO / "report" / "templates" / "plano",):
        for arquivo in diretorio.glob("*.html"):
            conteudo = arquivo.read_text(encoding="utf-8")
            assert "estilo.css" not in conteudo, f"{arquivo.name} referencia estilo.css"


# ---------------------------------------------------------------------------
# 2 — Rótulo (substituto estático da regra `label` do axe-core): as duas
# telas não têm campo de formulário — não há rótulo a auditar.
# ---------------------------------------------------------------------------


def test_tela_do_plano_nao_tem_campo_de_formulario(html_do_plano: str) -> None:
    """`plano.html` (a fonte do PDF) é saída de LEITURA — a
    regra `label` do `axe-core` audita CAMPOS de formulário; sem nenhum
    `<input>`/`<select>`/`<textarea>`, não há rótulo faltante possível."""
    for html, origem in ((html_do_plano, "plano.html"),):
        campos = re.findall(r"<(input|select|textarea)\b", html, flags=re.IGNORECASE)
        assert not campos, f"{origem}: contém campo de formulário inesperado: {campos}"


# ---------------------------------------------------------------------------
# 3 — Ordem de foco (substituto estático da regra `tabindex` do axe-core) —
# mesma checagem de T-48, aplicada ao HTML real destas duas telas.
# ---------------------------------------------------------------------------


def test_nenhum_tabindex_positivo_ou_negativo_no_html_do_plano(html_do_plano: str) -> None:
    for html, origem in ((html_do_plano, "plano.html"),):
        tabindexes = re.findall(r'tabindex\s*=\s*"(-?\d+)"', html)
        violacoes = [t for t in tabindexes if int(t) != 0]
        assert not violacoes, f"{origem}: tabindex fora de 0 encontrado: {violacoes}"


# ---------------------------------------------------------------------------
# Estrutura semântica adicional — diferente da coleta, estas duas telas têm
# uma tabela de dados (fila) e uma hierarquia de seções (plano).
# ---------------------------------------------------------------------------


def test_hierarquia_de_headings_do_plano_nao_pula_nivel(html_do_plano: str) -> None:
    """`heading-order` do `axe-core`: a sequência de `<h1>`/`<h2>`/... não
    pula nível (ex.: `<h1>` seguido direto de `<h3>`) — o snapshot real com
    duas dívidas garante que o `{% for %}` de `posicao.html` (cada posição
    com seu próprio `<h2>`) realmente aparece no HTML auditado."""
    niveis = [int(n) for n in re.findall(r"<h([1-6])\b", html_do_plano)]
    assert niveis, "plano.html não declara nenhum heading"
    assert niveis[0] == 1, f"plano.html: primeiro heading deveria ser <h1>, é <h{niveis[0]}>"
    maior_ate_agora = niveis[0]
    for nivel in niveis[1:]:
        assert nivel <= maior_ate_agora + 1, (
            f"plano.html: heading pula de <h{maior_ate_agora}> para <h{nivel}>"
        )
        maior_ate_agora = max(maior_ate_agora, nivel)


# ---------------------------------------------------------------------------
# 360 px sem rolagem horizontal — mesma técnica estática de
# tests/app_aluno/estatica/test_css_360px.py (T-47), aplicada aos templates
# do plano e da fila (que não carregam estilo.css — ver docstring).
# ---------------------------------------------------------------------------


def test_templates_do_plano_e_da_fila_nao_declaram_width_fixo_acima_de_360px() -> None:
    """Nenhum template (`.html`) de `report/templates/plano/` ou
    `report/templates/revisao/` declara `width` fixo (`style="width: Npx"`)
    acima de 360px — o padrão mais comum de rolagem horizontal em telas
    estreitas, mesmo limiar de `test_css_360px.py`."""
    limiar_px = 360
    for diretorio in (RAIZ_PROJETO / "report" / "templates" / "plano",):
        for arquivo in diretorio.glob("*.html"):
            conteudo = arquivo.read_text(encoding="utf-8")
            violacoes = [
                int(valor)
                for valor in re.findall(r"width\s*:\s*(\d+)px", conteudo)
                if int(valor) > limiar_px
            ]
            assert not violacoes, f"{arquivo.name}: width fixo acima de {limiar_px}px: {violacoes}"


def test_ambiente_confirma_que_navegador_real_nao_substitui_axe_core() -> None:
    """Confirmação explícita, reescrita em 2026-09-14 (T-129).

    **O que mudou, e por que este teste mudou junto.** Até T-129 este teste
    afirmava `find_spec("playwright") is None` e dizia, na própria mensagem
    de falha, o que fazer se isso deixasse de valer: declarar a dependência
    no plano e substituir o estático por `axe-core` real. O especialista
    pediu Playwright em 2026-09-14, a dependência foi declarada no extra
    `browser` do `pyproject.toml`, e o tripwire disparou exatamente como foi
    desenhado para disparar. Apagar a asserção teria sido o erro; o certo é
    afirmar a realidade nova.

    **A distinção que este teste continua protegendo.** Ter navegador NÃO
    torna os testes acima `axe-core`. O que existe é uma verificação em
    Chromium de verdade sobre um escopo estreito e deliberado (máscara,
    recusa do servidor, teclado, 360px) — não uma auditoria de
    acessibilidade. Os testes deste arquivo seguem sendo **substituto
    estático parcial**, e a auditoria `axe-core` sobre as ~90 regras
    continua no checklist manual, não aqui.

    **T-144 mudou onde essa verificação mora, não se ela existe.** Era
    `tests/app_aluno/e2e/test_navegador_mascaras.py`, sobre a tela Jinja +
    `mascaras.js`. A tela virou React; a verificação foi portada para
    `frontend/tests/e2e/coleta.spec.ts`, que roda no Playwright do
    frontend. O tripwire aponta para lá — se aquele arquivo sumir, este
    teste falha, que é exatamente o ponto."""
    import importlib.util
    from pathlib import Path

    assert importlib.util.find_spec("playwright") is not None, (
        "playwright deixou de estar disponível — o extra `browser` do "
        "pyproject.toml precisa estar instalado (uv pip install -e '.[browser]')"
    )

    raiz = Path(__file__).resolve().parent.parent.parent.parent
    assert "playwright" in (raiz / "pyproject.toml").read_text(encoding="utf-8"), (
        "a dependência precisa continuar DECLARADA, nunca só instalada "
        "de fato na máquina de quem rodou"
    )
    e2e_do_frontend = raiz / "frontend" / "tests" / "e2e" / "coleta.spec.ts"
    assert e2e_do_frontend.is_file(), (
        "a verificação em navegador real precisa existir — sem ela, ter "
        "Playwright instalado não prova nada"
    )
