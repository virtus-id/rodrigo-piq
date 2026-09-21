"""Lint estático: todo ícone é decorativo e nenhum é focável — `RF-74`,
`AC-110`, `AC-111` (T-163).

**O que esta auditoria protege.** A tela de pergunta é o caminho mais longo
da coleta (cem e poucas perguntas) e tem a trava mais rígida do projeto:
`coleta.spec.ts:297` permite no máximo **dois** Tabs do campo até
"Continuar", e `:285` compara o nome acessível do botão por igualdade
estrita (`=== 'Continuar'`).

Um `<svg>` mal declarado quebra as duas coisas de uma vez:

- sem `aria-hidden`, alguns leitores compõem o nome acessível do botão com o
  conteúdo do `<svg>`, e a igualdade estrita falha;
- sem `focusable="false"`, motores legados tratam `<svg>` como focável, e a
  contagem de Tabs passa de dois.

`Icone.tsx` emite os dois atributos por construção e não expõe prop que
permita o contrário. Esta auditoria existe para o caso de alguém escrever um
`<svg>` à mão em vez de usar o componente — que é exatamente o tipo de
decisão silenciosa que `sdd.config.md` §6 proíbe.

**Ícone nunca é o único portador de significado** (WCAG 1.4.1). A persona
tem baixa visão presumida; um pictograma sem palavra ao lado é precisamente
o que ela não consegue usar. Isso não é auditável por regex — fica em
`docs/checklist-acessibilidade.md` —, mas a parte mecânica (`aria-hidden`)
é, e é o que este módulo cobre.

REGRAS: `RF-74`, `AC-110`, `AC-111`
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
DIR_FONTE: Final[Path] = RAIZ_PROJETO / "frontend" / "src"
SPRITE_REMOVIDO: Final[Path] = RAIZ_PROJETO / "frontend" / "public" / "icons.svg"

# Captura a tag `<svg` e tudo até o `>` que a fecha, atravessando linhas —
# os atributos de um SVG legível ficam em várias.
ABERTURA_DE_SVG: Final[re.Pattern[str]] = re.compile(r"<svg\b([^>]*)>", re.S)


def _arquivos_de_fonte() -> list[Path]:
    return sorted(
        caminho
        for caminho in DIR_FONTE.rglob("*")
        if caminho.suffix in {".ts", ".tsx"} and caminho.is_file()
    )


def _sem_comentarios(texto: str) -> str:
    """Remove `/* … */` e `// …`.

    `Icone.tsx` documenta a própria regra no docblock — citando
    `aria-hidden` e `focusable` em prosa. Auditar o texto junto com o código
    faria a explicação da regra ser lida como código."""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return re.sub(r"^\s*//.*$", "", texto, flags=re.M)


def test_o_sprite_de_boilerplate_do_vite_foi_removido() -> None:
    """`AC-111`: `public/icons.svg` não existe.

    Ele continha ícones de Bluesky, Discord, GitHub e "documentation" — o
    sprite do template `create-vite`, sem uma única referência no código do
    PIQ. Um arquivo assim no repositório sugere um sistema de ícones que
    nunca existiu."""
    assert not SPRITE_REMOVIDO.exists(), (
        f"{SPRITE_REMOVIDO} ainda existe — era boilerplate do Vite "
        "(ícones de redes sociais), sem referência no código (`AC-111`)"
    )


def test_todo_svg_do_frontend_e_decorativo() -> None:
    """`AC-110`: todo `<svg>` tem `aria-hidden="true"`.

    Sem isso o ícone entra na árvore de acessibilidade e pode compor o nome
    acessível do controle que o contém — quebrando `AC-114`."""
    faltando: list[str] = []
    for caminho in _arquivos_de_fonte():
        conteudo = _sem_comentarios(caminho.read_text(encoding="utf-8"))
        for achado in ABERTURA_DE_SVG.finditer(conteudo):
            atributos = achado.group(1)
            if 'aria-hidden="true"' not in atributos:
                linha = conteudo[: achado.start()].count("\n") + 1
                faltando.append(f"{caminho.relative_to(RAIZ_PROJETO)}:{linha}")
    assert not faltando, (
        "`<svg>` sem `aria-hidden=\"true\"` em: "
        + ", ".join(faltando)
        + " — use o componente `Icone`, que os emite por construção (`AC-110`)"
    )


def test_nenhum_svg_entra_na_ordem_de_foco() -> None:
    """`AC-110`/`AC-114`: todo `<svg>` declara `focusable="false"`.

    Em motores legados o padrão de `<svg>` é focável. Uma parada de Tab a
    mais entre o campo e "Continuar" estoura o orçamento de dois Tabs de
    `coleta.spec.ts:297`."""
    faltando: list[str] = []
    for caminho in _arquivos_de_fonte():
        conteudo = _sem_comentarios(caminho.read_text(encoding="utf-8"))
        for achado in ABERTURA_DE_SVG.finditer(conteudo):
            if 'focusable="false"' not in achado.group(1):
                linha = conteudo[: achado.start()].count("\n") + 1
                faltando.append(f"{caminho.relative_to(RAIZ_PROJETO)}:{linha}")
    assert not faltando, (
        '`<svg>` sem `focusable="false"` em: '
        + ", ".join(faltando)
        + " — em motor legado ele vira parada de Tab (`AC-114`)"
    )


def test_nenhum_icone_carrega_titulo() -> None:
    """`AC-110`: nenhum `<title>` dentro de `<svg>` no frontend.

    `<title>` é o mecanismo padrão de dar nome acessível a um SVG — e é
    justamente o que não pode existir aqui: ele entraria na composição do
    nome acessível do botão "Continuar", que `coleta.spec.ts:285` compara
    por igualdade estrita. O rótulo do controle é o TEXTO ao lado do ícone,
    nunca o ícone."""
    violacoes: list[str] = []
    for caminho in _arquivos_de_fonte():
        conteudo = _sem_comentarios(caminho.read_text(encoding="utf-8"))
        if "<svg" in conteudo and "<title" in conteudo:
            violacoes.append(str(caminho.relative_to(RAIZ_PROJETO)))
    assert not violacoes, (
        "`<title>` dentro de SVG em: "
        + ", ".join(violacoes)
        + " — o rótulo é o texto ao lado, nunca o ícone (`AC-110`)"
    )
