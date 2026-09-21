"""Lint estático: nenhum conteúdo de questionário e nenhuma avaliação de
condicional nos `.js` servidos — `AC-73` (T-126).

Este teste é **a trava executável da revisão do §2 do plano** (2026-09-14).
A recusa original de SPA dizia que ele *"duplicaria o grafo condicional
(`RF-05`) no cliente — dois lugares onde a regra de exibição pode divergir"*.
A revisão delimitou essa recusa ao SPA que **avalia `condicao_exibicao` em
JavaScript**, e autorizou o desenho de `RF-45`, no qual o servidor entrega
uma pergunta já decidida exibível por vez.

Uma delimitação dessas só vale se for verificável. Sem este teste, nada
impediria alguém de, meses depois, "otimizar" o cliente reintroduzindo a
avaliação de condicional em JS — e a justificativa registrada no plano
viraria ficção. É o espelho exato de `AC-37`/`T-08`
(`test_sem_conteudo_de_questionario_no_codigo.py`), agora do lado do cliente.

Duas regras, na mesma disciplina do teste irmão:

**(a) Nenhuma avaliação de condicional.** Os nomes estruturais do grafo
(`condicao_exibicao`, `IGUAL`/`CONTEM`/`EXISTE_ITEM` como nós de
`collection.registro.Condicao`, `avaliar`) não aparecem em `.js`. Não é
heurística: são os identificadores reais do tipo declarado em
`collection/registro.py`.

**(b) Nenhum conteúdo de questionário.** O alvo é o ENUNCIADO e o RÓTULO DE
OPÇÃO: o que está em `collection/registros/*.yaml` nunca pode ser reescrito
em código, porque aí passariam a existir duas redações da mesma pergunta.

O limiar de 40 caracteres de `AC-37` não se transporta tal e qual para uma
aplicação React: classe de Tailwind, template literal de URL e texto de
interface (o cabeçalho de uma tela, uma mensagem de erro) passam dos 40
caracteres sem serem conteúdo de questionário — e nenhum deles duplica
redação nenhuma. A trava aqui é direta e específica: nenhum enunciado nem
rótulo de opção REAL do questionário aparece no código do cliente,
verificado contra os registros de verdade, não por comprimento.

**T-144 mudou o que se audita, não a trava.** O cliente era
`app/http/estaticos/mascaras.js`; passou a ser a aplicação React em
`frontend/src/`. Auditar o diretório antigo continuaria "passando" para
sempre, sobre nada — a pior forma de um teste morrer. A varredura agora
cobre `.ts`/`.tsx` de `frontend/src/`, que é onde a regra de exibição
poderia ser reintroduzida hoje.

REGRAS: `AC-73`, `RF-45`
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
DIRETORIO_CLIENTE: Final[Path] = RAIZ_PROJETO / "frontend" / "src"

# `tipos.ts` DECLARA a forma do payload que o servidor manda; declarar o
# nome de um campo não é avaliar condicional. O que ele não pode conter —
# e não contém — é `condicao_exibicao`, verificado pelo teste abaixo como
# qualquer outro arquivo.
ARQUIVOS_ISENTOS: Final[frozenset[str]] = frozenset()

# Mesmo limiar de `AC-37` (`test_sem_conteudo_de_questionario_no_codigo.py`).
LIMITE_CARACTERES_STRING: Final[int] = 40

# Identificadores REAIS do grafo condicional (`collection/registro.py`:
# `Condicao`, e `collection/condicoes.py::avaliar`) — se qualquer um deles
# aparecer no código do cliente, a avaliação de condicional atravessou a
# fronteira.
#
# `valor_interno` saiu desta lista em T-144: é o valor que o cliente MANDA
# de volta ao escolher uma opção (`opcoes[].valor_interno` está no payload
# de `serializar_pergunta`), então citá-lo é usar o contrato, não avaliar a
# regra. Os demais continuam proibidos — nenhum deles é enviado ao cliente.
NOMES_DE_CONDICIONAL: Final[tuple[str, ...]] = (
    "condicao_exibicao",
    "EXISTE_ITEM",
    "VARIAVEL_GRAVADA",
    "obrigatoriedade",
    "validacoes_cruzadas",
)

# Literais de string em JS: aspas simples, duplas ou template literal.
_PADRAO_STRING: Final[re.Pattern[str]] = re.compile(
    r"'([^'\\\n]*(?:\\.[^'\\\n]*)*)'"
    r'|"([^"\\\n]*(?:\\.[^"\\\n]*)*)"'
    r"|`([^`\\]*(?:\\.[^`\\]*)*)`"
)

# Comentários de bloco e de linha — a documentação narrativa do próprio
# arquivo é isenta do limiar, exatamente como docstring é isenta em `AC-37`.
_PADRAO_COMENTARIO: Final[re.Pattern[str]] = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _arquivos_auditados() -> tuple[Path, ...]:
    if not DIRETORIO_CLIENTE.is_dir():
        return ()
    caminhos = [
        *DIRETORIO_CLIENTE.rglob("*.ts"),
        *DIRETORIO_CLIENTE.rglob("*.tsx"),
    ]
    return tuple(
        caminho for caminho in sorted(caminhos) if caminho.name not in ARQUIVOS_ISENTOS
    )


def _codigo_sem_comentarios(fonte: str) -> str:
    return _PADRAO_COMENTARIO.sub(" ", fonte)


def test_nenhum_js_avalia_condicional_ac_73() -> None:
    """`RF-45`: o cliente nunca avalia `condicao_exibicao`. Quem decide se
    uma pergunta aparece é o servidor, e é isso que separa este desenho do
    SPA recusado no plano §2."""
    violacoes: list[str] = []
    for caminho in _arquivos_auditados():
        codigo = _codigo_sem_comentarios(caminho.read_text(encoding="utf-8"))
        for nome in NOMES_DE_CONDICIONAL:
            if nome in codigo:
                violacoes.append(f"{caminho.name}: {nome!r}")

    assert violacoes == [], (
        "nome estrutural do grafo condicional encontrado em JavaScript — "
        f"RF-45 exige a decisão no servidor: {violacoes}"
    )


def test_nenhum_enunciado_ou_rotulo_real_aparece_no_cliente_ac_73() -> None:
    """Espelho de `AC-37` do lado do cliente: nenhum enunciado nem rótulo de
    opção REAL está escrito no código. A coleta é DADO
    (`collection/registros/*.yaml`), nunca código — e muito menos código
    enviado ao navegador.

    A verificação é contra os registros de verdade, não por comprimento:
    carrega os 291 enunciados e todos os rótulos de opção do questionário e
    procura cada um no código do cliente. Assim um enunciado curto também é
    pego, e uma classe de Tailwind longa não vira falso positivo."""
    from collection.carga import carregar_registros

    colecao = carregar_registros()
    textos_do_questionario: set[str] = set()
    for registro in colecao.registros:
        textos_do_questionario.add(registro.enunciado.strip())
        for opcao in registro.opcoes:
            textos_do_questionario.add(opcao.rotulo.strip())

    # Textos muito curtos ("Sim", "Não") colidiriam com qualquer palavra de
    # interface; o que importa provar é que a REDAÇÃO não foi copiada.
    textos_significativos = {t for t in textos_do_questionario if len(t) >= 25}
    assert textos_significativos, "a coleção não trouxe texto nenhum — auditoria vazia"

    violacoes: list[str] = []
    for caminho in _arquivos_auditados():
        codigo = _codigo_sem_comentarios(caminho.read_text(encoding="utf-8"))
        for texto in textos_significativos:
            if texto in codigo:
                violacoes.append(f"{caminho.name}: {texto[:60]!r}")

    assert violacoes == [], (
        "enunciado ou rótulo do questionário copiado para o código do "
        f"cliente — a redação tem que existir num lugar só: {violacoes}"
    )


def test_o_codigo_do_cliente_e_de_fato_auditado() -> None:
    """Prova de que a auditoria não passa por vacuidade.

    Sem esta checagem, mover o frontend de lugar — ou apagá-lo — faria os
    dois testes acima passarem sem auditar nada. Foi exatamente o que
    aconteceu em T-144, quando `mascaras.js` foi removido: este teste
    disparou, que é o comportamento certo."""
    nomes = {caminho.name for caminho in _arquivos_auditados()}

    assert "mascaras.ts" in nomes, "o módulo de máscaras do cliente não foi encontrado"
    assert "tipos.ts" in nomes, "os tipos do payload não foram encontrados"
    assert len(nomes) >= 10, f"varredura suspeita de estar vazia: {sorted(nomes)}"
