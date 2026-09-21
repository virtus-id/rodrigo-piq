"""Lint estático: `app/` não DERIVA patrimônio nem depende de
`valores_do_escopo` para variável do Bloco 4 — `RF-44`, `AC-61`, `AC-71`,
`T-118` (fatia 2A da Rodada 2).

Por que este arquivo existe, e por que ele NÃO é uma cópia do lint do motor
-----------------------------------------------------------------------------
O slug `motor-calculo` já tem um lint equivalente para a primeira metade:
`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` (`AC-67`
daquele slug). Ele varre **exclusivamente `engine/`** — a própria docstring
daquele módulo declara isso ("também não são inspecionados os arquivos fora
de `engine/` (`app/`, `collection/`, `report/`)"). Consequência direta:
alguém que escrevesse `classificar_mobilizacao(...) ->
CLASSIFICACAO_MOBILIZACAO` dentro de `app/` **passaria naquele lint** e ainda
assim estaria decidindo metodologia no código.

Achar o ponto cego de uma regra não é cumpri-la. `piq-app-spec.md:2614` fixa
que as classes de mobilização são "derivadas pelo motor, nunca perguntadas", e
a *regra* de derivação continua sendo `motor-calculo:OQ-26`, **aberta** — não
publicada por nenhuma fonte. A proibição vale em `app/` **por decisão**
(`AC-61`, `RF-44`, `sdd.config.md` §6: "Metodologia não se decide
implementando"), não por alcance de ferramenta. Este teste fecha o ponto cego
com varredura própria sobre `app/`, e é isso que o distingue de uma
duplicação: mesmo alvo normativo, pasta diferente, e mais três construções
que o lint do motor não procura (literal de classe atribuído a item, soma
patrimonial, e `valores_do_escopo` sobre variável do Bloco 4).

As quatro construções recusadas (`AC-61` + `AC-71`)
-----------------------------------------------------------------------------
Detecção por `ast` (stdlib), mesma família de
`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`
(`T-08`) e `test_sem_aritmetica_sobre_snapshot.py`:

**(a) `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno.** Qualquer
`FunctionDef`/`AsyncFunctionDef` de `app/**/*.py` cuja anotação de retorno
mencione o nome em qualquer posição da sub-árvore — direta, qualificada por
módulo, em `Optional`/união, em coleção, ou como anotação adiada em string.
Mesma fronteira do lint do motor, e pelo mesmo motivo: **consumir** a
classificação é legítimo (§13.3 manda o motor filtrar por ela); **produzi-la**
é o que está proibido, e a anotação de retorno separa os dois de forma
inequívoca.

**(b) Literal de membro do domínio atribuído a um item.** Qualquer um dos
quatro membros de `CLASSIFICACAO_MOBILIZACAO` (`MOBILIZACAO_POSSIVEL`,
`MOBILIZACAO_RECOMENDAVEL`, `MOBILIZACAO_COM_RESSALVAS`, `NAO_MOBILIZAR` —
lidos do PRÓPRIO enum de `engine/tipos.py`, nunca copiados à mão para uma
lista deste arquivo) aparecendo como valor atribuído: `ast.Assign`,
`ast.AnnAssign`, ou argumento nomeado de chamada (`ItemAtivo(...,
CLASSIFICACAO_MOBILIZACAO=...)`). Cobre tanto o acesso ao membro
(`CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR`) quanto o literal de string
(`"NAO_MOBILIZAR"`) — classificar "porque é neutro" para destravar 2C é
exatamente o risco que `specs/app-aluno.spec.md:621` registra, e produziria
o mesmo número da coleção vazia **com a aparência de que houve
classificação**.

**(c) Soma envolvendo variável patrimonial.** Qualquer `ast.BinOp` de adição
(`+`), `ast.AugAssign` (`+=`) ou chamada a `sum(...)` em cuja sub-árvore
apareça `VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO` ou
`CUSTOS_ESTIMADOS_DESMOBILIZACAO` (nome, atributo ou string). `RF-44` proíbe
"qualquer agregação ou fórmula patrimonial" nesta camada: líquido realizável,
corte de liquidez e total de patrimônio são do motor
(`engine/diagnostico.py`), nunca da montagem.

**(d) `valores_do_escopo` sobre variável do Bloco 4 (`AC-71`).**
`collection/respostas.py:114-128` **ignora o parâmetro `escopo`**: o corpo é
`if nome_variavel == variavel and item_id != ""`, e a própria docstring
admite ("`escopo` não é usado para filtrar aqui"). Funcionou até hoje porque
cada escopo usava nomes de variável distintos — mas `VALOR_ESTIMADO_ATIVO` é
gravado em **quatro** lugares de `collection/registros/bloco-04.yaml`
(`:222` investimento, `:363` imóvel, `:570` veículo, `:833` outro),
`SALDO_PASSIVO_VINCULADO` em três e `CUSTOS_ESTIMADOS_DESMOBILIZACAO` em
três. Ler itens por ali devolveria também os das outras famílias:
**dupla contagem**, que a §13.8 da canônica veda por escrito ("nenhum recurso
pode aparecer simultaneamente em dois componentes", "origem econômica
única"). Isso é `OQ-24`, **aberta e bloqueante para as fatias 2B e 2C** —
nenhuma linha de leitura de item pode ser escrita antes dela, e a correção é
em `collection/`, não em `app/`.

A fatia 2A não lê item nenhum: os cinco campos que ela lê do Bloco 4
(`DINHEIRO_DISPONIVEL_EXISTE`/`DINHEIRO_DISPONIVEL`, `RESERVA_EXISTE`,
`RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA`,
`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`) são escalares, lidos por
`respostas.valor(...)`. `AC-71` é o que torna essa **não-dependência
verificável em vez de presumida**: sem este teste, a independência seria uma
afirmação de prosa no plano, e a armadilha de `OQ-24` poderia ser herdada por
engano na primeira tarefa de 2B que copiasse o padrão de `_despesas_
operacionais_atuais` sem notar a diferença. O teste é a sentinela que 2B/2C
encontram já montada.

`valores_do_escopo` sobre variável de OUTRO bloco continua permitido — e é
usado hoje, legitimamente, por `_renda_recorrente_adicional_total`
(`RENDA_RECORRENTE_ADICIONAL`, escopo `RENDA_ADICIONAL_ID`) e
`_despesas_operacionais_atuais` (`VALOR_DESPESA`, escopo `ITEM_DESPESA`),
ambos do Bloco 3. `AC-71` fala do Bloco 4, e o alvo do detector é exatamente
esse recorte: a lista de variáveis do Bloco 4 é lida do REGISTRO REAL
(`collection.carga.carregar_registros`, filtrando `bloco == 4`), nunca
transcrita à mão para este arquivo — se uma variável nova entrar no
`bloco-04.yaml`, ela passa a ser vigiada sem edição deste teste.

Limitações declaradas
-----------------------------------------------------------------------------
É varredura estrutural, não prova de tipo. Uma função anotada `-> object` que
devolvesse um membro do enum escaparia de (a) — a mesma lacuna que o lint do
motor documenta, e pelo mesmo par de razões: `mypy --strict` (comando `build`)
já exige anotação de retorno em `app/`, e alargar a heurística para "qualquer
`return CLASSIFICACAO_MOBILIZACAO.X`" produziria falso positivo em código
legítimo de leitura. Igualmente, (c) procura a forma sintática da soma, não
toda agregação concebível: uma soma escrita via `functools.reduce` com
`operator.add` passaria. O projeto prefere, aqui como no lint irmão, um
detector simples e auditável a uma heurística elaborada e frágil — e por isso
cada uma das quatro construções tem prova negativa própria abaixo.

Quando `motor-calculo:OQ-26` e `OQ-24` forem respondidas, este teste não deve
ser apagado em silêncio: ele documenta a data e a fonte em que cada proibição
deixou de valer.

REGRAS: RF-44, AC-61, AC-71
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from collection.carga import carregar_registros
from engine.tipos import CLASSIFICACAO_MOBILIZACAO

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
RAIZ_APP = RAIZ_PROJETO / "app"

NOME_CLASSIFICACAO: Final[str] = "CLASSIFICACAO_MOBILIZACAO"

# Os quatro membros do domínio, lidos do PRÓPRIO enum de `engine/tipos.py` —
# nunca copiados à mão para cá (uma cópia divergiria em silêncio no dia em que
# o domínio mudasse, e o detector passaria a vigiar um conjunto errado).
MEMBROS_CLASSIFICACAO: Final[frozenset[str]] = frozenset(
    membro.name for membro in CLASSIFICACAO_MOBILIZACAO
)

# As três variáveis patrimoniais que `RF-44`/`AC-61` proíbem somar nesta
# camada. São nomes de variável da canônica (§13), não conteúdo de
# questionário.
VARIAVEIS_PATRIMONIAIS: Final[frozenset[str]] = frozenset(
    {
        "VALOR_ESTIMADO_ATIVO",
        "SALDO_PASSIVO_VINCULADO",
        "CUSTOS_ESTIMADOS_DESMOBILIZACAO",
    }
)

_NOME_VALORES_DO_ESCOPO: Final[str] = "valores_do_escopo"
_BLOCO_PATRIMONIO: Final[int] = 4


def _variaveis_do_bloco_4() -> frozenset[str]:
    """As `VARIAVEL_GRAVADA` do Bloco 4, lidas do REGISTRO REAL (`collection/
    registros/bloco-04.yaml` via `collection.carga`, T-16) — nunca uma lista
    transcrita neste arquivo. Quatro delas são strings COMPOSTAS no registro
    (`"VALOR_ESTIMADO_ATIVO (investimento)"`, `"VALOR_IMOVEL (=
    VALOR_ESTIMADO_ATIVO)"`, ...), então o conjunto guarda tanto a string
    inteira quanto o primeiro token — é por esse token que uma chamada a
    `valores_do_escopo` a referenciaria."""
    variaveis: set[str] = set()
    for registro in carregar_registros().registros:
        if registro.bloco != _BLOCO_PATRIMONIO:
            continue
        variavel = registro.VARIAVEL_GRAVADA
        # `VARIAVEL_GRAVADA` é `str | None` no contrato de `RegistroPergunta`
        # (pergunta puramente informativa não grava variável) — nenhuma do
        # Bloco 4 é assim hoje, mas o detector não presume isso.
        if variavel is None:
            continue
        variaveis.add(variavel)
        variaveis.add(variavel.split(" ")[0])
    return frozenset(variaveis)


VARIAVEIS_BLOCO_4: Final[frozenset[str]] = _variaveis_do_bloco_4()


@dataclass(frozen=True, slots=True)
class ViolacaoPatrimonial:
    arquivo: str
    linha: int
    construcao: str
    descricao: str


def _menciona(no: ast.AST, nomes: frozenset[str] | set[str]) -> str | None:
    """O primeiro nome de `nomes` mencionado na sub-árvore de `no` — como
    `ast.Name`, `ast.Attribute` ou literal de string. `None` se nenhum."""
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name) and filho.id in nomes:
            return filho.id
        if isinstance(filho, ast.Attribute) and filho.attr in nomes:
            return filho.attr
        if isinstance(filho, ast.Constant) and isinstance(filho.value, str):
            if filho.value in nomes:
                return filho.value
    return None


# ---------------------------------------------------------------------------
# (a) — CLASSIFICACAO_MOBILIZACAO na anotação de retorno (AC-61).
# ---------------------------------------------------------------------------


def _anotacao_menciona_classificacao(anotacao: ast.expr) -> bool:
    """`True` se a sub-árvore da anotação de retorno mencionar
    `CLASSIFICACAO_MOBILIZACAO` de qualquer forma — nome simples, atributo
    qualificado, dentro de `Optional`/união/coleção, ou como anotação adiada
    em string (comum sob `from __future__ import annotations`, que TODO
    módulo de `app/` usa)."""
    for no in ast.walk(anotacao):
        if isinstance(no, ast.Name) and no.id == NOME_CLASSIFICACAO:
            return True
        if isinstance(no, ast.Attribute) and no.attr == NOME_CLASSIFICACAO:
            return True
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            if NOME_CLASSIFICACAO in no.value:
                return True
    return False


def _detectar_derivacao_de_classificacao(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoPatrimonial]:
    """(a) — função de `app/` que PRODUZ `CLASSIFICACAO_MOBILIZACAO`, isto é,
    que a tem na anotação de retorno. Consumir a classificação (compará-la,
    filtrar por ela) nunca é reportado."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoPatrimonial] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if no.returns is None:
            continue
        if _anotacao_menciona_classificacao(no.returns):
            violacoes.append(
                ViolacaoPatrimonial(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    construcao="(a) derivação de CLASSIFICACAO_MOBILIZACAO",
                    descricao=(
                        f"função `{no.name}` retorna "
                        f"`{ast.unparse(no.returns)}` — a classificação é "
                        "recebida como dado por item, nunca produzida "
                        "(motor-calculo:OQ-26, aberta)"
                    ),
                )
            )

    return violacoes


# ---------------------------------------------------------------------------
# (b) — literal de membro do domínio atribuído a um item (AC-61).
# ---------------------------------------------------------------------------


def _detectar_literal_de_classificacao(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoPatrimonial]:
    """(b) — um dos quatro membros de `CLASSIFICACAO_MOBILIZACAO` aparecendo
    como VALOR atribuído: `ast.Assign` (`item.X = NAO_MOBILIZAR`),
    `ast.AnnAssign`, ou argumento nomeado de chamada
    (`ItemAtivo(CLASSIFICACAO_MOBILIZACAO=...)`). Cobre o acesso ao membro do
    enum e o literal de string equivalente."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoPatrimonial] = []

    def registrar(linha: int, membro: str, forma: str) -> None:
        violacoes.append(
            ViolacaoPatrimonial(
                arquivo=nome_arquivo,
                linha=linha,
                construcao="(b) literal de classificação atribuído a item",
                descricao=(
                    f"membro `{membro}` do domínio de "
                    f"CLASSIFICACAO_MOBILIZACAO atribuído ({forma}) — "
                    "classificar em app/ é decidir metodologia no código"
                ),
            )
        )

    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and no.value is not None:
            membro = _menciona(no.value, MEMBROS_CLASSIFICACAO)
            if membro is not None:
                registrar(no.lineno, membro, "atribuição")
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            membro = _menciona(no.value, MEMBROS_CLASSIFICACAO)
            if membro is not None:
                registrar(no.lineno, membro, "atribuição anotada")
        elif isinstance(no, ast.Call):
            for argumento in no.keywords:
                membro = _menciona(argumento.value, MEMBROS_CLASSIFICACAO)
                if membro is not None:
                    registrar(no.lineno, membro, f"argumento nomeado {argumento.arg!r}")

    return violacoes


# ---------------------------------------------------------------------------
# (c) — soma envolvendo variável patrimonial (RF-44, AC-61).
# ---------------------------------------------------------------------------


def _detectar_soma_patrimonial(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoPatrimonial]:
    """(c) — adição (`+`), acumulação (`+=`) ou `sum(...)` em cuja sub-árvore
    apareça uma das três variáveis patrimoniais. `RF-44`: nenhuma agregação
    ou fórmula patrimonial nesta camada — total, líquido realizável e corte
    de liquidez são do motor."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoPatrimonial] = []

    def registrar(linha: int, variavel: str, forma: str) -> None:
        violacoes.append(
            ViolacaoPatrimonial(
                arquivo=nome_arquivo,
                linha=linha,
                construcao="(c) soma patrimonial",
                descricao=(
                    f"{forma} envolvendo `{variavel}` — agregação "
                    "patrimonial é do motor (RF-44), nunca desta camada"
                ),
            )
        )

    for no in ast.walk(arvore):
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
            variavel = _menciona(no, VARIAVEIS_PATRIMONIAIS)
            if variavel is not None:
                registrar(no.lineno, variavel, "adição `+`")
        elif isinstance(no, ast.AugAssign) and isinstance(no.op, ast.Add):
            variavel = _menciona(no, VARIAVEIS_PATRIMONIAIS)
            if variavel is not None:
                registrar(no.lineno, variavel, "acumulação `+=`")
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "sum":
            variavel = _menciona(no, VARIAVEIS_PATRIMONIAIS)
            if variavel is not None:
                registrar(no.lineno, variavel, "chamada a `sum(...)`")

    return violacoes


# ---------------------------------------------------------------------------
# (d) — valores_do_escopo sobre variável do Bloco 4 (AC-71, OQ-24 aberta).
# ---------------------------------------------------------------------------


def _detectar_valores_do_escopo_do_bloco_4(
    codigo_fonte: str, nome_arquivo: str, variaveis_bloco_4: frozenset[str]
) -> list[ViolacaoPatrimonial]:
    """(d) — chamada a `valores_do_escopo(...)` cujo argumento de VARIÁVEL é
    uma variável do Bloco 4. A assinatura real é
    `valores_do_escopo(escopo, variavel)` (`collection/respostas.py:114`);
    o detector examina todos os argumentos (posicionais e nomeados) porque
    a chamada pode ser escrita com `variavel=` explícito.

    Chamada com variável de OUTRO bloco não é reportada: `_renda_recorrente_
    adicional_total` e `_despesas_operacionais_atuais` (Bloco 3) usam este
    método legitimamente hoje, e `AC-71` fala do Bloco 4."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoPatrimonial] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome_chamado = (
            alvo.attr
            if isinstance(alvo, ast.Attribute)
            else alvo.id
            if isinstance(alvo, ast.Name)
            else None
        )
        if nome_chamado != _NOME_VALORES_DO_ESCOPO:
            continue

        argumentos: list[ast.expr] = list(no.args) + [k.value for k in no.keywords]
        for argumento in argumentos:
            variavel = _menciona(argumento, variaveis_bloco_4)
            if variavel is None:
                continue
            violacoes.append(
                ViolacaoPatrimonial(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    construcao="(d) valores_do_escopo sobre variável do Bloco 4",
                    descricao=(
                        f"variável {variavel!r} do Bloco 4 — "
                        "`valores_do_escopo` ignora o parâmetro `escopo` "
                        "(OQ-24, aberta); ler item do Bloco 4 por ali "
                        "produz dupla contagem (§13.8)"
                    ),
                )
            )
            break

    return violacoes


# ---------------------------------------------------------------------------
# Varredura sobre `app/` — os quatro detectores.
# ---------------------------------------------------------------------------


def _arquivos_py_de_app() -> list[Path]:
    return sorted(RAIZ_APP.rglob("*.py"))


def _mensagem(violacoes: list[ViolacaoPatrimonial], criterio: str) -> str:
    return f"{criterio} violado em app/:\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.construcao}: {v.descricao}" for v in violacoes
    )


def test_ac61_nenhuma_funcao_de_app_deriva_classificacao_mobilizacao() -> None:
    """`AC-61` (a), `RF-44`: nenhuma função de `app/**/*.py` tem
    `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno. O lint de
    `motor-calculo` (`tests/estatica/test_sem_derivacao_de_classificacao_
    mobilizacao.py`) só varre `engine/` — a proibição vale aqui por decisão
    (`sdd.config.md` §6), não por alcance de ferramenta. A regra de derivação
    é `motor-calculo:OQ-26`, **aberta**."""
    violacoes: list[ViolacaoPatrimonial] = []
    for arquivo in _arquivos_py_de_app():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_derivacao_de_classificacao(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes, "AC-61 (a) — derivação de classificação")


def test_ac61_nenhum_literal_de_classificacao_atribuido_a_item_em_app() -> None:
    """`AC-61` (b), `RF-44`: nenhum dos quatro membros do domínio de
    `CLASSIFICACAO_MOBILIZACAO` aparece como valor atribuído em `app/` —
    classificar "porque é neutro" (`NAO_MOBILIZAR`) para destravar a fatia 2C
    produziria o mesmo número da coleção vazia com a APARÊNCIA de que houve
    classificação (`specs/app-aluno.spec.md`, tabela de riscos)."""
    violacoes: list[ViolacaoPatrimonial] = []
    for arquivo in _arquivos_py_de_app():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_literal_de_classificacao(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes, "AC-61 (b) — literal de classificação")


def test_ac61_nenhuma_soma_patrimonial_em_app() -> None:
    """`AC-61` (c), `RF-44`: nenhuma soma envolvendo `VALOR_ESTIMADO_ATIVO`,
    `SALDO_PASSIVO_VINCULADO` ou `CUSTOS_ESTIMADOS_DESMOBILIZACAO` é escrita
    em `app/`. Todo valor patrimonial entregue ao motor nesta fatia é uma
    resposta lida, convertida e tipada — nada derivado."""
    violacoes: list[ViolacaoPatrimonial] = []
    for arquivo in _arquivos_py_de_app():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_soma_patrimonial(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes, "AC-61 (c) — soma patrimonial")


def test_ac71_app_nao_usa_valores_do_escopo_para_variavel_do_bloco_4() -> None:
    """`AC-71`: nenhuma chamada a `valores_do_escopo` em `app/` usa variável
    do Bloco 4. A fatia 2A lê apenas os cinco campos escalares por
    `respostas.valor(...)` e por isso NÃO é afetada pela ausência de filtro
    por escopo de `OQ-24` (**aberta**, bloqueante para 2B/2C) — este teste é
    o que torna essa não-dependência verificável em vez de presumida, e a
    sentinela que 2B/2C encontram já montada."""
    violacoes: list[ViolacaoPatrimonial] = []
    for arquivo in _arquivos_py_de_app():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(
            _detectar_valores_do_escopo_do_bloco_4(codigo_fonte, str(arquivo), VARIAVEIS_BLOCO_4)
        )

    assert not violacoes, _mensagem(violacoes, "AC-71 — valores_do_escopo sobre Bloco 4")


# ---------------------------------------------------------------------------
# Prova NEGATIVA — cada um dos quatro detectores é alimentado com um caso
# proposital, construído como STRING (nunca escrito em `app/` real, nunca
# executado), e precisa pegá-lo. Sem isto, os quatro testes acima passariam
# igualmente bem com o detector quebrado: hoje eles varrem um conjunto em que
# a resposta correta é "nenhuma", e verificação vácua não distingue "não há
# violação" de "não sei detectar violação".
# ---------------------------------------------------------------------------


def test_detector_a_pega_derivacao_proposital_em_app() -> None:
    """Prova negativa de (a): o caso exato que `motor-calculo:OQ-26` proíbe —
    derivar a classe a partir de liquidez e custo de desmobilização —,
    escrito como se estivesse em `app/montagem/`."""
    codigo = """
def _classificar_mobilizacao_do_item(*, liquidez, custo) -> CLASSIFICACAO_MOBILIZACAO:
    if liquidez and not custo:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
"""
    violacoes = _detectar_derivacao_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, "esperava que o detector (a) pegasse a derivação proposital"
    assert len(violacoes) == 1, f"esperava exatamente 1 violação, obteve: {violacoes!r}"
    assert violacoes[0].linha == 2
    assert "_classificar_mobilizacao_do_item" in violacoes[0].descricao


@pytest.mark.parametrize(
    ("descricao", "anotacao"),
    [
        ("direta", "CLASSIFICACAO_MOBILIZACAO"),
        ("qualificada por módulo", "tipos.CLASSIFICACAO_MOBILIZACAO"),
        ("união com None", "CLASSIFICACAO_MOBILIZACAO | None"),
        ("Optional", "Optional[CLASSIFICACAO_MOBILIZACAO]"),
        ("tupla homogênea", "tuple[CLASSIFICACAO_MOBILIZACAO, ...]"),
        ("dicionário como valor", "dict[str, CLASSIFICACAO_MOBILIZACAO]"),
        ("anotação adiada como string", '"CLASSIFICACAO_MOBILIZACAO"'),
    ],
)
def test_detector_a_pega_cada_forma_de_anotacao(descricao: str, anotacao: str) -> None:
    """Prova negativa de (a), forma a forma — não por amostra. Cada uma das
    anotações de retorno pelas quais uma derivação poderia entrar em `app/` é
    detectada."""
    codigo = f"def derivar(item) -> {anotacao}:\n    return item\n"

    violacoes = _detectar_derivacao_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, f"o detector (a) não pegou a forma {descricao!r}: `-> {anotacao}`"
    assert violacoes[0].linha == 1


def test_detector_a_pega_funcao_assincrona() -> None:
    """Prova negativa de (a): `AsyncFunctionDef` é varrido junto com
    `FunctionDef` — uma derivação não escapa por ser declarada `async def`
    (relevante em `app/`, onde há rotas assíncronas)."""
    codigo = """
async def derivar_async(item) -> CLASSIFICACAO_MOBILIZACAO:
    return item.CLASSIFICACAO_MOBILIZACAO
"""
    violacoes = _detectar_derivacao_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, "esperava detectar a derivação em `async def`"
    assert "derivar_async" in violacoes[0].descricao


@pytest.mark.parametrize("membro", sorted(MEMBROS_CLASSIFICACAO))
def test_detector_b_pega_cada_membro_atribuido(membro: str) -> None:
    """Prova negativa de (b), membro a membro: os QUATRO valores do domínio
    são pegos quando atribuídos, inclusive `NAO_MOBILIZAR` — o candidato mais
    provável a ser escrito "porque é neutro"."""
    codigo = f"item.CLASSIFICACAO_MOBILIZACAO = CLASSIFICACAO_MOBILIZACAO.{membro}\n"

    violacoes = _detectar_literal_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, f"o detector (b) não pegou o membro {membro!r} atribuído"
    assert membro in violacoes[0].descricao


def test_detector_b_pega_membro_como_argumento_nomeado() -> None:
    """Prova negativa de (b): a forma mais realista da violação — montar um
    `ItemAtivo` já classificado, passando o membro como argumento nomeado."""
    codigo = """
def montar_item(valor):
    return ItemAtivo(
        VALOR_ESTIMADO_ATIVO=valor,
        CLASSIFICACAO_MOBILIZACAO=CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
    )
"""
    violacoes = _detectar_literal_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, "esperava que o detector (b) pegasse o argumento nomeado"
    assert "NAO_MOBILIZAR" in violacoes[0].descricao


def test_detector_b_pega_membro_como_literal_de_string() -> None:
    """Prova negativa de (b): o membro escrito como STRING (`"NAO_MOBILIZAR"`)
    é a mesma decisão de metodologia com outra sintaxe — também é pego."""
    codigo = 'classificacao = "MOBILIZACAO_RECOMENDAVEL"\n'

    violacoes = _detectar_literal_de_classificacao(codigo, "caso_proposital.py")

    assert violacoes, "esperava que o detector (b) pegasse o literal de string"


@pytest.mark.parametrize("variavel", sorted(VARIAVEIS_PATRIMONIAIS))
def test_detector_c_pega_soma_de_cada_variavel_patrimonial(variavel: str) -> None:
    """Prova negativa de (c), variável a variável: as TRÊS variáveis
    patrimoniais são pegas numa adição."""
    codigo = f"total = {variavel} + outro_valor\n"

    violacoes = _detectar_soma_patrimonial(codigo, "caso_proposital.py")

    assert violacoes, f"o detector (c) não pegou a soma de {variavel!r}"
    assert variavel in violacoes[0].descricao


def test_detector_c_pega_acumulacao_e_sum() -> None:
    """Prova negativa de (c): as outras duas formas da mesma agregação —
    `+=` num laço e `sum(...)` numa compreensão (a forma que `engine/
    diagnostico.py` usa legitimamente, e que esta camada não pode copiar)."""
    codigo_acumulacao = """
def somar(itens):
    total = 0
    for item in itens:
        total += item.VALOR_ESTIMADO_ATIVO
    return total
"""
    codigo_sum = """
def somar(itens):
    return sum(item.SALDO_PASSIVO_VINCULADO for item in itens)
"""
    violacoes_acumulacao = _detectar_soma_patrimonial(codigo_acumulacao, "caso_proposital.py")
    violacoes_sum = _detectar_soma_patrimonial(codigo_sum, "caso_proposital.py")

    assert violacoes_acumulacao, "esperava que o detector (c) pegasse a acumulação `+=`"
    assert violacoes_sum, "esperava que o detector (c) pegasse a chamada a `sum(...)`"


def test_detector_c_nao_reporta_leitura_simples_de_variavel_patrimonial() -> None:
    """Contraprova da fronteira de (c): LER e repassar uma variável
    patrimonial é exatamente o que `RF-44` autoriza ("uma resposta lida,
    convertida e tipada") — só a AGREGAÇÃO é proibida. Um teste que
    reprovasse este trecho tornaria a fatia 2B inimplementável."""
    codigo = """
def _valor_estimado_ativo(respostas, item_id):
    valor = respostas.valor_no_item(item_id, "VALOR_ESTIMADO_ATIVO")
    return converter_para_dinheiro(valor)
"""
    violacoes = _detectar_soma_patrimonial(codigo, "caso_correto.py")

    assert not violacoes, (
        f"leitura simples não pode ser reportada como soma, obteve: {violacoes!r}"
    )


@pytest.mark.parametrize(
    "variavel",
    ["VALOR_ESTIMADO_ATIVO", "RESERVA_TOTAL", "SALDO_PASSIVO_VINCULADO"],
)
def test_detector_d_pega_valores_do_escopo_sobre_variavel_do_bloco_4(variavel: str) -> None:
    """Prova negativa de (d): a chamada que produziria dupla contagem
    (`OQ-24`) é pega para variável do Bloco 4 — inclusive
    `VALOR_ESTIMADO_ATIVO`, gravada em QUATRO lugares do `bloco-04.yaml`, que
    é o caso concreto que a §13.8 veda."""
    assert variavel in VARIAVEIS_BLOCO_4, (
        f"premissa da prova: {variavel!r} precisa ser variável do Bloco 4 no registro real"
    )
    codigo = (
        "def somar(respostas):\n"
        f'    return respostas.valores_do_escopo(EscopoRepeticao.ATIVO_ID, "{variavel}")\n'
    )

    violacoes = _detectar_valores_do_escopo_do_bloco_4(
        codigo, "caso_proposital.py", VARIAVEIS_BLOCO_4
    )

    assert violacoes, f"o detector (d) não pegou `valores_do_escopo` sobre {variavel!r}"
    assert variavel in violacoes[0].descricao


def test_detector_d_pega_argumento_nomeado_e_constante_intermediaria() -> None:
    """Prova negativa de (d): a chamada escrita com `variavel=` explícito, e
    a variável passada por uma constante de módulo cujo NOME é o da variável
    do Bloco 4 — as duas formas realistas de escrever a mesma dependência."""
    codigo_nomeado = (
        "respostas.valores_do_escopo(escopo=EscopoRepeticao.ATIVO_ID, "
        'variavel="CUSTOS_ESTIMADOS_DESMOBILIZACAO")\n'
    )
    codigo_constante = (
        "respostas.valores_do_escopo(EscopoRepeticao.ATIVO_ID, VALOR_ESTIMADO_ATIVO)\n"
    )

    violacoes_nomeado = _detectar_valores_do_escopo_do_bloco_4(
        codigo_nomeado, "caso_proposital.py", VARIAVEIS_BLOCO_4
    )
    violacoes_constante = _detectar_valores_do_escopo_do_bloco_4(
        codigo_constante, "caso_proposital.py", VARIAVEIS_BLOCO_4
    )

    assert violacoes_nomeado, "esperava pegar `valores_do_escopo(variavel=...)`"
    assert violacoes_constante, "esperava pegar a variável passada como nome"


def test_detector_d_nao_reporta_valores_do_escopo_de_outro_bloco() -> None:
    """Contraprova da fronteira de (d): `_renda_recorrente_adicional_total` e
    `_despesas_operacionais_atuais` (`app/montagem/estado.py`, Bloco 3) usam
    `valores_do_escopo` HOJE, legitimamente — `AC-71` fala do Bloco 4. Um
    detector que reprovasse o trecho abaixo quebraria `T-103` sem que nenhuma
    regra tivesse sido violada."""
    codigo = """
def _renda_recorrente_adicional_total(respostas):
    return respostas.valores_do_escopo(
        EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL"
    )
"""
    violacoes = _detectar_valores_do_escopo_do_bloco_4(
        codigo, "caso_correto.py", VARIAVEIS_BLOCO_4
    )

    assert not violacoes, (
        "`valores_do_escopo` sobre variável do Bloco 3 é legítimo e não pode "
        f"ser reportado, obteve: {violacoes!r}"
    )


def test_variaveis_do_bloco_4_vem_do_registro_real() -> None:
    """A lista vigiada por (d) é DADO, não código: vem de `collection/
    registros/bloco-04.yaml` via `collection.carga`. Este teste ancora a
    premissa — se o registro deixar de declarar as variáveis patrimoniais que
    `OQ-24` cita, o detector (d) estaria vigiando um conjunto vazio e
    passaria vácuo."""
    assert len(VARIAVEIS_BLOCO_4) > 0, "o registro do Bloco 4 precisa estar carregado"
    for variavel in VARIAVEIS_PATRIMONIAIS:
        assert variavel in VARIAVEIS_BLOCO_4, (
            f"{variavel!r} deveria aparecer entre as VARIAVEL_GRAVADA do Bloco 4 "
            "(é uma das três que OQ-24 cita como gravadas em vários lugares)"
        )
    # Os cinco campos escalares que a fatia 2A de fato lê (`AC-71`).
    for escalar in (
        "DINHEIRO_DISPONIVEL_EXISTE",
        "DINHEIRO_DISPONIVEL",
        "RESERVA_EXISTE",
        "RESERVA_TOTAL",
        "DISPOSICAO_USO_RESERVA",
        "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",
    ):
        assert escalar in VARIAVEIS_BLOCO_4, f"{escalar!r} deveria estar no registro do Bloco 4"
