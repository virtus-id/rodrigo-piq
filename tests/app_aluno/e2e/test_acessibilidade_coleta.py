"""Acessibilidade automatizada do fluxo de coleta — `RF-07`, `RF-09` (T-48).

**Escopo reduzido em T-144.** Este arquivo auditava o HTML de
`report/templates/coleta/`: rótulo associado a cada campo, ausência de
`tabindex` fora do fluxo, `role="alert"` na recusa e `aria-describedby`
ligando campo e mensagem. Aqueles templates foram removidos — a tela virou
React —, e auditar arquivo inexistente passaria para sempre sem provar
nada. As auditorias de markup migraram para `frontend/tests/e2e/
coleta.spec.ts`, que roda em Chromium de verdade sobre o DOM real; o caso
normativo de `EC-02`/`AC-06` (a mensagem nomeia os dois campos) já estava
coberto por `tests/app_aluno/test_gerador.py`, e não foi duplicado aqui.

O que PERMANECE neste arquivo é a auditoria de **contraste** sobre
`app/http/estaticos/estilo.css`, que continua existindo.

**Limitação honesta deste ambiente — leia antes de confiar no verde.**
`axe-core` real (a ferramenta que os critérios de aceite citam) audita o DOM
de uma página renderizada por um navegador de verdade (Chromium/Firefox via
Playwright ou Selenium). **Atualizado em 2026-09-14 (T-129):** o projeto
passou a declarar `playwright`/`pytest-playwright` no extra `browser` do
`pyproject.toml`, e `tests/app_aluno/e2e/test_navegador_mascaras.py` executa
`mascaras.js` em Chromium real. Isso **não** converte este arquivo em
`axe-core`: aquele teste cobre a máscara, num escopo estreito e declarado, e
a auditoria das ~90 regras do `axe-core` segue no checklist manual. O texto
abaixo descreve o substituto estático, que continua sendo o que este arquivo
faz. Originalmente este projeto **não** declarava `playwright`/
`pytest-playwright`/`selenium` em nenhum extra de `pyproject.toml`
(`sdd.config.md` "sem dependência nova que não esteja no plano" — nenhum dos
dois está no plano desta feature), e este ambiente **não tem Chromium
instalado** (confirmado: `node`/`npm` existem no sistema, mas nem `axe-core`
nem qualquer pacote de browser estão instalados — `npm ls -g` não lista
nenhum dos dois, e `node -e "require.resolve('axe-core')"` falha). Rodar
`axe-core` de verdade aqui seria simular, não testar.

**O que este arquivo faz em vez disso — substituto PARCIAL, declarado como
tal.** Três auditorias estáticas sobre o HTML/CSS de produção (nunca sobre
HTML fabricado à mão, para que a auditoria valha para o que o aluno de fato
vê):

1. **Contraste** — as cores de texto/fundo declaradas em `app/http/
   estaticos/estilo.css` (`.ficha-status-completa`, `.ficha-status-pendente`,
   `.aviso-materialidade`) têm a razão de contraste calculada pela fórmula
   de luminância relativa da própria WCAG 2.1 (critério 1.4.3, nível AA:
   ≥ 4.5:1 para texto normal) — é a MESMA fórmula que `axe-core` usa
   internamente para a regra `color-contrast`, aplicada aqui sem
   renderização visual (sem imagem, sem anti-aliasing, sem herança de
   estilo em cascata de um elemento pai não declarado neste arquivo — por
   isso é parcial: cores herdadas ou combinadas em runtime não entram
   nesta conta).
2. **Rótulo** — todo `<input>`/`<select>`/`<textarea>` do HTML renderizado
   (Bloco 5 real, com registros de produção via `collection/carga.py`, mais
   a ficha repetível) tem um `<label for="...">` com o mesmo `id`, ou é um
   campo oculto (`type="hidden"`, nunca lido por leitor de tela como campo
   de formulário) — a MESMA checagem estrutural que a regra `label`/
   `label-title-only` de `axe-core` faz, sem o motor de acessibilidade
   completo por trás.
3. **Ordem de foco** — nenhum `tabindex` positivo (que reordenaria o foco
   fora do fluxo natural do documento) nem negativo (que removeria um
   controle interativo da navegação por Tab) aparece no HTML — a mesma
   checagem que a regra `tabindex` de `axe-core` faz.

**O que fica de fora, e por quê é substituto parcial, não equivalente.**
`axe-core` real varre ~90 regras (ARIA inválido, ordem de heading, contraste
computado após cascata CSS completa, foco visível por pseudo-classe
`:focus`, papel semântico calculado pela árvore de acessibilidade do
navegador). Nada disso é verificável sem um motor de renderização real. A
auditoria completa por `axe-core` sobre browser real fica registrada como
item do checklist manual (`docs/checklist-acessibilidade.md`) — junto da
navegação por teclado com leitor de tela real, que `plans/app-aluno.plan.md`
§9 já declarava não automatizável ("navegação por teclado com leitor de tela
real exige verificação manual, registrada como checklist"). Este arquivo
apenas ESTENDE a mesma decisão de fronteira à parte de `axe` que também
depende de browser real, em vez de fingir que uma varredura de string
substitui o motor de acessibilidade do Chromium.

Marcador `e2e` (`pyproject.toml`, T-05): não bloqueia `pytest -m "not
requer_banco and not e2e"`, mesmo padrão de `tests/app_aluno/e2e/
test_retomada.py`/`test_rota_resposta.py`.

REGRAS: `RF-07`, `RF-09`
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.e2e

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
CAMINHO_TOKENS_TAILWIND: Final[Path] = RAIZ_PROJETO / "frontend" / "tailwind.config.js"

# WCAG 2.1 AA, critério 1.4.3 — texto normal exige ao menos 4.5:1.
LIMIAR_CONTRASTE_AA: Final[float] = 4.5


# ---------------------------------------------------------------------------
# Fórmula de luminância relativa/contraste da própria especificação WCAG —
# a mesma que `axe-core` usa internamente na regra `color-contrast`.
# https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
# ---------------------------------------------------------------------------


def _canal_linear(valor_8bit: int) -> float:
    c = valor_8bit / 255.0
    if c <= 0.03928:
        return c / 12.92
    return float(((c + 0.055) / 1.055) ** 2.4)


def _luminancia_relativa(cor_hex: str) -> float:
    cor_hex = cor_hex.lstrip("#")
    r, g, b = (int(cor_hex[i : i + 2], 16) for i in (0, 2, 4))
    r_lin, g_lin, b_lin = _canal_linear(r), _canal_linear(g), _canal_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _razao_de_contraste(cor_a: str, cor_b: str) -> float:
    luminancia_clara = max(_luminancia_relativa(cor_a), _luminancia_relativa(cor_b))
    luminancia_escura = min(_luminancia_relativa(cor_a), _luminancia_relativa(cor_b))
    return (luminancia_clara + 0.05) / (luminancia_escura + 0.05)


def _tokens_de_cor() -> dict[str, str]:
    """Todos os tokens de cor de `frontend/tailwind.config.js`, achatados.

    **T-145 mudou o arquivo, não a auditoria.** As cores que o aluno vê
    estavam em `app/http/estaticos/estilo.css`; com a interface em React,
    estão nos tokens do Tailwind. Continuar medindo o CSS antigo daria
    verde para sempre sobre cores que ninguém mais renderiza — o pior tipo
    de teste, o que tranquiliza sem verificar.

    Os aninhados viram `pai.filho` (`accent.DEFAULT`, `warn.soft`), porque
    `DEFAULT`/`soft`/`ink` se repetem entre blocos e um nome solto seria
    ambíguo."""
    conteudo = CAMINHO_TOKENS_TAILWIND.read_text(encoding="utf-8")
    tokens: dict[str, str] = {}
    prefixo = ""
    dentro_de_colors = False
    for linha in conteudo.splitlines():
        nu = linha.strip()
        if nu.startswith("colors:"):
            dentro_de_colors = True
            continue
        if not dentro_de_colors:
            continue
        if nu.startswith("fontFamily:"):
            break
        achado = re.match(r"([A-Za-z_][\w-]*):\s*'(#[0-9a-fA-F]{6})'", nu)
        if achado is not None:
            nome, valor = achado.group(1), achado.group(2)
            tokens[f"{prefixo}{nome}" if prefixo else nome] = valor
            continue
        abre_bloco = re.match(r"([A-Za-z_][\w-]*):\s*\{", nu)
        if abre_bloco is not None:
            prefixo = f"{abre_bloco.group(1)}."
            continue
        if nu.startswith("}"):
            prefixo = ""
    assert tokens, "nenhum token de cor lido de tailwind.config.js"
    return tokens


def _token_de_cor(nome: str) -> str:
    """UM token, com erro explícito se sumir — um token renomeado tem que
    quebrar aqui, nunca desaparecer da auditoria em silêncio."""
    tokens = _tokens_de_cor()
    assert nome in tokens, (
        f"token de cor {nome!r} não encontrado em tailwind.config.js "
        f"(conhecidos: {sorted(tokens)}) — se foi renomeado, esta "
        "auditoria precisa acompanhar"
    )
    return tokens[nome]


# ---------------------------------------------------------------------------
# 1 — Contraste (substituto estático da regra `color-contrast` do axe-core).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("par", "token_fundo", "token_texto"),
    [
        ("texto sobre o fundo da página", "bg", "ink"),
        ("texto sobre cartão", "surface", "ink"),
        ("texto secundário sobre o fundo", "bg", "muted"),
        ("botão primário", "accent.DEFAULT", "accent.ink"),
        ("aviso de atenção", "warn.soft", "warn.DEFAULT"),
        ("aviso de erro", "bad.soft", "bad.DEFAULT"),
        ("destaque sobre fundo suave", "accent.soft", "accent.DEFAULT"),
    ],
)
def test_contraste_texto_fundo_atende_wcag_aa_nos_pares_reais_da_interface(
    par: str, token_fundo: str, token_texto: str
) -> None:
    """Os pares de cor que o aluno de fato lê atendem ao limiar de 4.5:1 da
    WCAG 2.1 AA, pela fórmula normativa — a mesma que o `axe-core` usa na
    regra `color-contrast`.

    A persona tem baixa visão entre as possibilidades previstas, e o
    protótipo escolheu Atkinson Hyperlegible por isso. Contraste abaixo do
    limiar desfaz aquela escolha sem que ninguém perceba na revisão visual:
    a olho nu, `#5E6E72` sobre `#FAFAF7` parece perfeitamente legível para
    quem enxerga bem."""
    fundo = _token_de_cor(token_fundo)
    texto = _token_de_cor(token_texto)

    razao = _razao_de_contraste(fundo, texto)

    assert razao >= LIMIAR_CONTRASTE_AA, (
        f"{par}: contraste {razao:.2f}:1 abaixo do limiar AA "
        f"({LIMIAR_CONTRASTE_AA}:1) — fundo={fundo} texto={texto}"
    )


