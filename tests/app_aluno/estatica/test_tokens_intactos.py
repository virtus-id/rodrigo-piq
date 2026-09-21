"""Lint estático: a repaginação da Rodada 8 não altera nenhum sinal validado
— `RF-78`, `AC-107`, `AC-108` (T-162).

**Por que este arquivo existe.** A Rodada 8 acrescenta elevação, hierarquia
tipográfica, ícones e esqueleto de carregamento a uma interface cujo design
foi validado com stakeholders (`RF-50`). O risco da rodada não é o que ela
acrescenta — é o que ela poderia mudar sem querer no caminho: um token
renomeado, uma cor "ajustada", um alvo de toque arredondado.

`test_acessibilidade_coleta.py` já pega parte disso: ele recalcula o contraste
WCAG 2.1 AA de sete pares e falha se um token de cor for renomeado ou se o
contraste cair. Mas ele **não** audita `fontFamily`, `minHeight` nem
`maxWidth` — o parser dele para justamente em `fontFamily:` —, e não percebe
uma cor trocada por outra de contraste equivalente.

Este módulo fecha essa lacuna: fixa os valores literais de antes da rodada e
falha se qualquer um mudar.

**Sobre fixar valores literais em teste.** É deliberado, e é o mesmo padrão
de `test_acessibilidade_coleta.py`: estes números são um CONTRATO com os
stakeholders que validaram o protótipo, não uma escolha de implementação.
Quando um deles precisar mudar, a mudança passa por uma decisão registrada —
e este teste é o lugar onde essa decisão fica visível, em vez de entrar de
carona num commit de estilo.

REGRAS: `RF-78`, `AC-107`, `AC-108`
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
CAMINHO_TAILWIND: Final[Path] = RAIZ_PROJETO / "frontend" / "tailwind.config.js"
CAMINHO_CSS: Final[Path] = RAIZ_PROJETO / "frontend" / "src" / "index.css"

# Os onze tokens de cor do protótipo validado (`RF-50`), como estavam antes
# da Rodada 8. Os sete pares auditados por contraste saem daqui.
CORES_VALIDADAS: Final[dict[str, str]] = {
    "bg": "#FAFAF7",
    "surface": "#FFFFFF",
    "ink": "#1B2A2F",
    "muted": "#5E6E72",
    "line": "#D9E0DC",
    "accent.DEFAULT": "#0F6E56",
    "accent.ink": "#FFFFFF",
    "accent.soft": "#E3F1EB",
    "warn.DEFAULT": "#8A5A00",
    "warn.soft": "#FFF4DC",
    "bad.DEFAULT": "#A63A2C",
    "bad.soft": "#FBE8E4",
}

# Alvos de toque — medidas de acessibilidade, não estética.
TOQUES_VALIDADOS: Final[dict[str, str]] = {
    "botao": "56px",
    "opcao": "60px",
    "toque": "48px",
}

# As larguras que `AC-87` e `AC-106` fixam, e que `navegacao.spec.ts`
# verifica por string exata em navegador real.
LARGURAS_VALIDADAS: Final[dict[str, str]] = {
    "tela": "560px",
    "equipe": "900px",
}

# A tinta da paleta, de que TODA sombra desta interface deriva (`AC-108`).
INK_RGB: Final[str] = "27, 42, 47"


def _tokens_de_cor() -> dict[str, str]:
    """Lê os tokens de cor achatando aninhados em `pai.filho`.

    Mesma estratégia de `test_acessibilidade_coleta.py::_tokens_de_cor`, e
    deliberadamente duplicada: um `import` cruzado entre módulos de teste
    faria uma auditoria depender da outra, e o ponto das duas é serem
    independentes."""
    tokens: dict[str, str] = {}
    prefixo = ""
    dentro = False
    for linha in CAMINHO_TAILWIND.read_text(encoding="utf-8").splitlines():
        nu = linha.strip()
        if nu.startswith("colors:"):
            dentro = True
            continue
        if not dentro:
            continue
        if nu.startswith("fontFamily:"):
            break
        achado = re.match(r"([A-Za-z_][\w-]*):\s*'(#[0-9a-fA-F]{6})'", nu)
        if achado is not None:
            nome, valor = achado.group(1), achado.group(2)
            tokens[f"{prefixo}{nome}" if prefixo else nome] = valor
            continue
        abre = re.match(r"([A-Za-z_][\w-]*):\s*\{", nu)
        if abre is not None:
            prefixo = f"{abre.group(1)}."
            continue
        if nu.startswith("}"):
            prefixo = ""
    return tokens


def test_os_onze_tokens_de_cor_mantem_nome_e_valor() -> None:
    """`AC-107`: nenhuma cor validada muda de nome ou de valor.

    Um token renomeado quebraria `test_acessibilidade_coleta.py` com erro
    explícito; um token com valor trocado poderia passar por lá se o
    contraste continuasse acima de 4,5:1 — e ainda assim seria uma cor que
    os stakeholders não validaram."""
    lidos = _tokens_de_cor()
    for nome, esperado in CORES_VALIDADAS.items():
        assert nome in lidos, (
            f"token de cor {nome!r} sumiu de tailwind.config.js — "
            "a Rodada 8 é aditiva (`RF-78`) e não renomeia token"
        )
        assert lidos[nome].upper() == esperado.upper(), (
            f"token {nome!r} mudou de {esperado} para {lidos[nome]} — "
            "é uma cor validada com stakeholders (`RF-50`)"
        )


def test_as_duas_familias_tipograficas_permanecem() -> None:
    """`AC-107`: Atkinson Hyperlegible e Source Serif 4 continuam.

    Atkinson Hyperlegible foi desenhada para baixa visão, e a persona é um
    servidor público lendo o contracheque no celular — trocá-la **não é
    neutro**. O parser de `test_acessibilidade_coleta.py` para em
    `fontFamily:` e nunca audita isto."""
    conteudo = CAMINHO_TAILWIND.read_text(encoding="utf-8")
    assert "Atkinson Hyperlegible" in conteudo, (
        "a fonte de baixa visão sumiu de tailwind.config.js"
    )
    assert "Source Serif 4" in conteudo, "a serifada dos títulos sumiu"


def test_os_alvos_de_toque_permanecem() -> None:
    """`AC-107`: 56px / 60px / 48px são medidas de acessibilidade."""
    conteudo = CAMINHO_TAILWIND.read_text(encoding="utf-8")
    for nome, valor in TOQUES_VALIDADOS.items():
        assert re.search(rf"{nome}:\s*'{valor}'", conteudo), (
            f"alvo de toque {nome!r} deixou de ser {valor} — "
            "é medida de acessibilidade, não estética"
        )


def test_as_larguras_validadas_permanecem() -> None:
    """`AC-107`: 560px e 900px são verificados por string exata em
    `navegacao.spec.ts` (`:471`, `:483`) em navegador real."""
    conteudo = CAMINHO_TAILWIND.read_text(encoding="utf-8")
    for nome, valor in LARGURAS_VALIDADAS.items():
        assert re.search(rf"{nome}:\s*'{valor}'", conteudo), (
            f"largura {nome!r} deixou de ser {valor}"
        )


def test_a_escala_de_elevacao_existe_e_deriva_do_ink() -> None:
    """`AC-108`: três níveis, todos derivados de `ink`.

    A checagem é sobre a DEFINIÇÃO das variáveis, não sobre cada uso: quem
    usa escreve `var(--e1)`, e é na definição que a cor aparece."""
    conteudo = _css_sem_comentarios()
    for nivel in ("--e1", "--e2", "--e3"):
        achado = re.search(rf"{nivel}\s*:\s*([^;]+);", conteudo)
        assert achado is not None, (
            f"o nível de elevação {nivel} não existe em index.css (`RF-72`)"
        )
        definicao = achado.group(1)
        assert INK_RGB in definicao, (
            f"{nivel} não deriva de `ink` ({INK_RGB}): {definicao!r}. "
            "Preto neutro sobre o fundo quente da paleta lê como sujeira "
            "cinza, não como sombra (`AC-108`)"
        )


def _css_sem_comentarios() -> str:
    """O CSS com os blocos `/* … */` removidos.

    Necessário porque este arquivo documenta a própria regra: o comentário
    de `--e1` explica por que `rgba(0,0,0,…)` é proibido, e auditar o texto
    junto com o código faria a explicação da regra violar a regra."""
    return re.sub(r"/\*.*?\*/", "", CAMINHO_CSS.read_text(encoding="utf-8"), flags=re.S)


def test_nenhuma_sombra_usa_preto_neutro() -> None:
    """`AC-108`: `rgba(0,0,0,…)` não aparece no CSS da interface."""
    violacoes = re.findall(r"rgba\(\s*0\s*,\s*0\s*,\s*0", _css_sem_comentarios())
    assert not violacoes, (
        f"{len(violacoes)} uso(s) de preto neutro em index.css — "
        "toda sombra desta interface deriva de `ink` (`AC-108`)"
    )
