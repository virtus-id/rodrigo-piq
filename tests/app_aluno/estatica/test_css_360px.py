"""Lint estático: o CSS da interface não força rolagem horizontal a 360 px
— RF-04, AC-04 (T-47, revisto em T-145).

A persona responde no celular, e 360 px é a largura que a NFR de
responsividade fixa. Rolagem horizontal numa tela de coleta é mais que
incômodo: um campo que sai da viewport pode simplesmente não ser
encontrado.

**T-145 mudou o arquivo auditado, não a regra.** O CSS era
`app/http/estaticos/estilo.css`, da coleta em Jinja2; com a interface em
React é `frontend/src/index.css` mais os tokens de `tailwind.config.js`.
Auditar o arquivo antigo — removido — passaria para sempre sem verificar
nada.

**O que se audita aqui e o que NÃO se audita.** Este módulo pega o padrão
problemático mais comum (largura fixa em px acima do limiar) por leitura
estática. A prova real de que não há rolagem horizontal roda em navegador,
a 360 px, em `frontend/tests/e2e/coleta.spec.ts` — as duas se complementam:
a estática falha rápido e aponta a linha; a de navegador mede o efeito.

REGRAS: `RF-04`, `AC-04`
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
CAMINHO_CSS: Final[Path] = RAIZ_PROJETO / "frontend" / "src" / "index.css"
CAMINHO_TAILWIND: Final[Path] = RAIZ_PROJETO / "frontend" / "tailwind.config.js"

# Nenhuma largura fixa acima deste limiar é tolerada — é o próprio critério
# de aceite da tarefa ("utilizável a 360 px de largura").
LARGURA_MAXIMA_PX: Final[int] = 360


def test_css_da_interface_existe() -> None:
    """O arquivo precisa existir para que os demais testes deste módulo
    façam sentido — falha explícita, nunca um `skip` silencioso.

    Esta trava fez seu trabalho em T-145: quando `estilo.css` foi removido,
    foi ela que avisou que a auditoria tinha ficado sem alvo."""
    assert CAMINHO_CSS.is_file(), f"{CAMINHO_CSS} não existe"
    assert CAMINHO_TAILWIND.is_file(), f"{CAMINHO_TAILWIND} não existe"


def test_nenhum_width_fixo_acima_de_360px_no_css_da_interface() -> None:
    """`width: <N>px` com `N` acima de 360 é o padrão mais comum de rolagem
    horizontal em telas estreitas — nenhuma regra do arquivo o declara.

    `max-width` é isento e não deveria ser pego pelo regex: limitar a
    largura é o oposto de forçá-la (a coluna de leitura do protótipo é
    `max-width: 560px`, e isso está correto)."""
    conteudo = CAMINHO_CSS.read_text(encoding="utf-8")

    violacoes = [
        int(valor)
        for valor in re.findall(r"(?<!max-)width\s*:\s*(\d+)px", conteudo)
        if int(valor) > LARGURA_MAXIMA_PX
    ]

    assert not violacoes, (
        f"{CAMINHO_CSS.name} declara width fixo acima de {LARGURA_MAXIMA_PX}px: {violacoes}"
    )


def test_nenhuma_largura_minima_acima_de_360px_nos_tokens() -> None:
    """`min-width` acima do limiar é pior que `width`: força a rolagem mesmo
    quando o contêiner poderia encolher. Os tokens de `tailwind.config.js`
    (que viram classes usadas nas telas) não declaram nenhum."""
    conteudo = CAMINHO_TAILWIND.read_text(encoding="utf-8")

    violacoes = [
        int(valor)
        for valor in re.findall(r"min[A-Za-z]*[Ww]idth[^:]*:\s*'?(\d+)px", conteudo)
        if int(valor) > LARGURA_MAXIMA_PX
    ]

    assert not violacoes, (
        f"tailwind.config.js declara min-width acima de {LARGURA_MAXIMA_PX}px: {violacoes}"
    )


def test_nenhuma_tag_table_estilizada_no_css_da_interface() -> None:
    """Nenhum seletor de tabela larga (`table`, `thead`, `tbody`) é
    estilizado — o layout é lista/cartão, que empilha verticalmente. Uma
    tabela de várias colunas é a forma mais rápida de estourar 360 px."""
    conteudo = CAMINHO_CSS.read_text(encoding="utf-8")

    for seletor_proibido in ("table", "thead", "tbody"):
        padrao = r"(^|[^\w-])" + seletor_proibido + r"\s*\{"
        assert not re.search(padrao, conteudo, flags=re.MULTILINE), (
            f"{CAMINHO_CSS.name} referencia seletor de tabela: {seletor_proibido!r}"
        )


def test_box_sizing_border_box_vale_universalmente() -> None:
    """`box-sizing: border-box` precisa valer no seletor universal, para que
    padding/borda nunca estourem a largura do contêiner — a causa mais comum
    de rolagem horizontal quando a largura já é 100%.

    **No React isso vem do Preflight do Tailwind** (`@tailwind base`), que
    declara `*, ::before, ::after { box-sizing: border-box }` — não é uma
    regra escrita à mão neste arquivo. Por isso a prova é a presença da
    diretiva: removê-la desativaria o reset inteiro de uma vez, e é
    exatamente essa remoção que este teste impede de passar despercebida."""
    conteudo = CAMINHO_CSS.read_text(encoding="utf-8")

    tem_preflight = re.search(r"@tailwind\s+base\s*;", conteudo) is not None
    tem_regra_propria = (
        re.search(r"\*\s*(,[^{]*)?\{[^}]*box-sizing\s*:\s*border-box", conteudo) is not None
    )

    assert tem_preflight or tem_regra_propria, (
        f"{CAMINHO_CSS.name} não garante box-sizing: border-box universal — "
        "nem via `@tailwind base` (Preflight), nem por regra própria"
    )
