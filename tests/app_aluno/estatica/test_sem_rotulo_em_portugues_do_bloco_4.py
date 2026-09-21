"""Auditoria estática: `app/montagem/estado.py` resolve `RESERVA_EXISTE` e
`DISPOSICAO_USO_RESERVA` por `_membro_do_enum`, sem uma única linha de
tradução de rótulo em português — `AC-53`, `AC-37`, `RF-36`, `T-119`.

`AC-53` tem duas metades verificáveis, e só a segunda estava sem portão:

1. **a leitura dos dois enums passa por `_membro_do_enum`** — nenhuma cadeia
   de `if valor_interno == "X": return Enum.X`, nenhum dicionário de tradução;
2. **nenhum rótulo em português de `B4.02`/`B4.03` aparece escrito no
   arquivo** — é esta metade que mantém `AC-37` verde depois da fatia 2A.

As duas são a mesma decisão vista de dois ângulos. Os `valor_interno` de
`B4.02` (`SIM`/`INFORMAL`/`NAO`) e de `B4.03`
(`PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO`) foram transcritos por `T-17`
IDÊNTICOS, caractere por caractere, aos `name` dos membros de
`engine/estado.py::RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` — e foram
transcritos assim **justamente para que nenhuma linha de tradução precisasse
existir**. `_membro_do_enum` (`app/montagem/estado.py`, `T-50`) resolve
`EnumClasse[valor_interno]` direto. Se em algum momento um `if` sobre texto
de rótulo aparecer, as duas metades caem juntas: o código estaria traduzindo
conteúdo de questionário (`AC-37`) e teria deixado de usar o mecanismo
genérico (`AC-53`).

Por que auditar em vez de ler
-----------------------------------------------------------------------------
A conformidade hoje é visível a olho nu — as duas funções (`_reserva_existe`,
`_disposicao_uso_reserva`) terminam num `return _membro_do_enum(...)`. Ler e
declarar "está certo" não deixa portão nenhum atrás: a próxima pessoa que
precisar tratar um caso de borda de `B4.03` (`EC-16`/`EC-17`) acrescenta um
`if` sobre o rótulo em dois minutos, e nada falha. `AC-53` pede uma
verificação, e é isso que este arquivo é.

Como os rótulos chegam aqui: do REGISTRO, nunca transcritos
-----------------------------------------------------------------------------
Um teste que procura por rótulos em português precisa dos rótulos. Escrevê-los
como literais NESTE arquivo reintroduziria, dentro de `tests/`, exatamente o
que `AC-37` proíbe em `app/` — conteúdo de questionário como código, e uma
segunda cópia que divergiria do YAML na primeira edição de redação. Por isso
os rótulos das duas perguntas são lidos do REGISTRO REAL
(`collection.carga.carregar_registros`, filtrando `ID in {B4.02, B4.03}`) em
tempo de execução: editar `collection/registros/bloco-04.yaml` muda o que
este teste procura, sem tocar numa linha daqui.

A busca é feita sobre o TEXTO do arquivo (`str.__contains__` sobre o
código-fonte lido), não sobre a AST: um rótulo poderia ser escrito num
comentário, e comentário não aparece na AST. A metade 1 (o mecanismo de
resolução), essa sim, é auditada por AST — é uma afirmação sobre estrutura de
código, não sobre texto.

Limitação declarada
-----------------------------------------------------------------------------
A metade 2 pega o rótulo escrito na forma exata do registro. Um rótulo
reescrito com outra pontuação ou parcialmente (só `"Talvez"` em vez de
`"Talvez. Quero ver os números antes."`) escaparia. Isso não deixa a
proibição sem portão: `tests/app_aluno/estatica/test_sem_conteudo_de_
questionario_no_codigo.py` (`T-08`, `AC-37`) já recusa QUALQUER literal de
string com mais de 40 caracteres fora de docstring em `app/`, o que cobre a
variação de redação por outro critério. Os dois testes são complementares —
este é específico e literal (nomeia a pergunta e o rótulo na mensagem de
falha), aquele é genérico e por limiar.

REGRAS: RF-36, AC-37, AC-53
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from collection.carga import carregar_registros
from collection.registro import RegistroPergunta

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
ARQUIVO_MONTAGEM: Final[Path] = RAIZ_PROJETO / "app" / "montagem" / "estado.py"

# As duas perguntas de `AC-53` e as duas funções que as leem — pelo `ID` do
# registro e pelo nome da função, nunca pelo texto do enunciado.
ID_RESERVA_EXISTE: Final[str] = "B4.02"
ID_DISPOSICAO_USO_RESERVA: Final[str] = "B4.03"

FUNCOES_AUDITADAS: Final[tuple[str, ...]] = (
    "_reserva_existe",
    "_disposicao_uso_reserva",
)

NOME_MECANISMO_GENERICO: Final[str] = "_membro_do_enum"


def _registro(id_pergunta: str) -> RegistroPergunta:
    for registro in carregar_registros().registros:
        if registro.ID == id_pergunta:
            return registro
    raise AssertionError(f"registro {id_pergunta!r} não encontrado na carga real")


def _rotulos_de(id_pergunta: str) -> tuple[str, ...]:
    """Os rótulos em português de uma pergunta, lidos do REGISTRO REAL —
    nunca transcritos para este arquivo (ver docstring do módulo)."""
    return tuple(opcao.rotulo for opcao in _registro(id_pergunta).opcoes)


ROTULOS_B4_02: Final[tuple[str, ...]] = _rotulos_de(ID_RESERVA_EXISTE)
ROTULOS_B4_03: Final[tuple[str, ...]] = _rotulos_de(ID_DISPOSICAO_USO_RESERVA)


@dataclass(frozen=True, slots=True)
class ViolacaoRotulo:
    id_pergunta: str
    rotulo: str
    linha: int


def _codigo_fonte_da_montagem() -> str:
    return ARQUIVO_MONTAGEM.read_text(encoding="utf-8")


def _detectar_rotulos_no_texto(
    codigo_fonte: str, id_pergunta: str, rotulos: tuple[str, ...]
) -> list[ViolacaoRotulo]:
    """Procura cada rótulo em português no TEXTO do arquivo — inclusive em
    comentário, que não aparece na AST. Reporta a linha exata."""
    linhas = codigo_fonte.splitlines()
    violacoes: list[ViolacaoRotulo] = []
    for rotulo in rotulos:
        for numero, linha in enumerate(linhas, start=1):
            if rotulo in linha:
                violacoes.append(
                    ViolacaoRotulo(id_pergunta=id_pergunta, rotulo=rotulo, linha=numero)
                )
    return violacoes


def _corpo_da_funcao(codigo_fonte: str, nome_funcao: str) -> ast.FunctionDef:
    arvore = ast.parse(codigo_fonte, filename=str(ARQUIVO_MONTAGEM))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome_funcao:
            return no
    raise AssertionError(f"função {nome_funcao!r} não encontrada em {ARQUIVO_MONTAGEM}")


def _chama_mecanismo_generico(funcao: ast.FunctionDef) -> bool:
    """`True` se o corpo da função chama `_membro_do_enum` — o mecanismo
    genérico de `T-50`, que resolve `EnumClasse[valor_interno]` por nome."""
    for no in ast.walk(funcao):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            if no.func.id == NOME_MECANISMO_GENERICO:
                return True
    return False


def _comparacoes_com_string(funcao: ast.FunctionDef) -> list[tuple[int, str]]:
    """Toda comparação do corpo contra um literal de STRING — o formato de
    uma cadeia de tradução (`if valor == "Sim.": return Enum.SIM`). Devolve
    `(linha, literal)` para cada uma, para que a mensagem de falha nomeie o
    texto exato encontrado.

    Comparações contra um valor NÃO-string (`is None`, `is not DESCONHECIDO`)
    nunca entram: `_reserva_existe`/`_disposicao_uso_reserva` fazem essas
    guardas legitimamente antes de resolver o enum, e reprovar isso tornaria
    `EC-16` (campo condicional ausente não é erro) inimplementável."""
    encontradas: list[tuple[int, str]] = []
    for no in ast.walk(funcao):
        if not isinstance(no, ast.Compare):
            continue
        for comparando in [no.left, *no.comparators]:
            if isinstance(comparando, ast.Constant) and isinstance(comparando.value, str):
                encontradas.append((no.lineno, comparando.value))
    return encontradas


def _dicionarios_literais(funcao: ast.FunctionDef) -> list[int]:
    """Todo `ast.Dict` literal no corpo — a outra forma de escrever uma
    tabela de tradução (`{"Sim.": RESERVA_EXISTE.SIM, ...}`)."""
    return [no.lineno for no in ast.walk(funcao) if isinstance(no, ast.Dict)]


# ---------------------------------------------------------------------------
# Metade 1 de `AC-53` — a resolução passa por `_membro_do_enum`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome_funcao", FUNCOES_AUDITADAS)
def test_ac53_resolucao_passa_por_membro_do_enum(nome_funcao: str) -> None:
    """`AC-53` (metade 1), `RF-36`: `_reserva_existe` e
    `_disposicao_uso_reserva` resolvem o membro do enum pelo mecanismo
    genérico `_membro_do_enum` — `EnumClasse[valor_interno]` por nome, o
    mesmo mecanismo dos 7 enums do Bloco 2 (`T-50`), nunca um caminho
    paralelo escrito só para o Bloco 4."""
    funcao = _corpo_da_funcao(_codigo_fonte_da_montagem(), nome_funcao)

    assert _chama_mecanismo_generico(funcao), (
        f"`{nome_funcao}` deveria resolver o enum por `{NOME_MECANISMO_GENERICO}` "
        "(AC-53) — nenhum caminho de resolução paralelo"
    )


@pytest.mark.parametrize("nome_funcao", FUNCOES_AUDITADAS)
def test_ac53_nenhuma_cadeia_de_if_sobre_valor_interno(nome_funcao: str) -> None:
    """`AC-53` (metade 1), `AC-37`: nenhuma comparação contra literal de
    string no corpo das duas funções — é essa a forma de uma cadeia de
    tradução (`if valor == "SIM": return RESERVA_EXISTE.SIM`), tanto sobre o
    `valor_interno` quanto sobre o rótulo em português. As guardas legítimas
    das duas funções comparam contra `None` e contra tipo (`isinstance`),
    nunca contra texto."""
    funcao = _corpo_da_funcao(_codigo_fonte_da_montagem(), nome_funcao)

    comparacoes = _comparacoes_com_string(funcao)

    assert not comparacoes, (
        f"`{nome_funcao}` compara contra literal de string (AC-53): "
        + "; ".join(f"linha {linha} — {texto!r}" for linha, texto in comparacoes)
    )


@pytest.mark.parametrize("nome_funcao", FUNCOES_AUDITADAS)
def test_ac53_nenhum_dicionario_de_traducao(nome_funcao: str) -> None:
    """`AC-53` (metade 1): nenhuma tabela literal de tradução no corpo das
    duas funções — a outra sintaxe da mesma violação, que uma auditoria só de
    `if` deixaria passar."""
    funcao = _corpo_da_funcao(_codigo_fonte_da_montagem(), nome_funcao)

    linhas = _dicionarios_literais(funcao)

    assert not linhas, (
        f"`{nome_funcao}` contém dicionário literal (possível tabela de "
        f"tradução, AC-53) nas linhas: {linhas}"
    )


# ---------------------------------------------------------------------------
# Metade 2 de `AC-53` — nenhum rótulo em português no arquivo (mantém `AC-37`).
# ---------------------------------------------------------------------------


def test_ac53_ac37_nenhum_rotulo_de_b4_02_no_arquivo() -> None:
    """`AC-53` (metade 2), `AC-37`: nenhum dos rótulos em português de
    `B4.02` (`RESERVA_EXISTE`) aparece escrito em
    `app/montagem/estado.py` — nem como literal, nem em comentário. Os
    rótulos vêm do registro real, nunca transcritos aqui."""
    violacoes = _detectar_rotulos_no_texto(
        _codigo_fonte_da_montagem(), ID_RESERVA_EXISTE, ROTULOS_B4_02
    )

    assert not violacoes, (
        "rótulo em português de B4.02 encontrado em app/montagem/estado.py "
        "(AC-53/AC-37):\n"
        + "\n".join(f"  linha {v.linha} — {v.rotulo!r}" for v in violacoes)
    )


def test_ac53_ac37_nenhum_rotulo_de_b4_03_no_arquivo() -> None:
    """`AC-53` (metade 2), `AC-37`: idem para `B4.03`
    (`DISPOSICAO_USO_RESERVA`), cujos quatro rótulos são frases longas — os
    candidatos mais prováveis a serem copiados para um comentário
    "explicativo" ao tratar `EC-16`/`EC-17`."""
    violacoes = _detectar_rotulos_no_texto(
        _codigo_fonte_da_montagem(), ID_DISPOSICAO_USO_RESERVA, ROTULOS_B4_03
    )

    assert not violacoes, (
        "rótulo em português de B4.03 encontrado em app/montagem/estado.py "
        "(AC-53/AC-37):\n"
        + "\n".join(f"  linha {v.linha} — {v.rotulo!r}" for v in violacoes)
    )


# ---------------------------------------------------------------------------
# A premissa que torna a ausência de tradução POSSÍVEL, e as provas negativas.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("id_pergunta", "nome_enum"),
    [
        (ID_RESERVA_EXISTE, "RESERVA_EXISTE"),
        (ID_DISPOSICAO_USO_RESERVA, "DISPOSICAO_USO_RESERVA"),
    ],
)
def test_valor_interno_bate_com_o_name_do_enum(id_pergunta: str, nome_enum: str) -> None:
    """A PREMISSA de `AC-53`: `_membro_do_enum` só resolve direto porque os
    `valor_interno` do registro batem CARACTERE POR CARACTERE com os `name`
    dos membros do enum (`T-17`). Se essa correspondência se quebrar, a
    pressão por escrever uma linha de tradução volta — e este teste falha
    ANTES, nomeando a divergência, em vez de a tradução aparecer como
    "solução"."""
    from engine.estado import DISPOSICAO_USO_RESERVA, RESERVA_EXISTE

    enums = {
        "RESERVA_EXISTE": RESERVA_EXISTE,
        "DISPOSICAO_USO_RESERVA": DISPOSICAO_USO_RESERVA,
    }
    enum_alvo = enums[nome_enum]
    nomes_do_enum = {membro.name for membro in enum_alvo}

    # `valor_interno` é `str | None` no contrato de `OpcaoResposta` (opção de
    # texto livre não tem valor interno) — as duas perguntas de `AC-53` são
    # `SELECAO_UNICA` com todas as opções codificadas, e este teste também
    # ancora isso: um `None` aqui significaria que a resolução por
    # `_membro_do_enum` deixou de ser possível para aquela opção.
    valores_internos: set[str] = set()
    for opcao in _registro(id_pergunta).opcoes:
        assert opcao.valor_interno is not None, (
            f"{id_pergunta}: opção {opcao.rotulo!r} sem `valor_interno` — "
            "sem ele `_membro_do_enum` não resolve, e a pressão por uma "
            "linha de tradução de rótulo volta (AC-53)"
        )
        valores_internos.add(opcao.valor_interno)

    assert valores_internos <= nomes_do_enum, (
        f"{id_pergunta}: valor_interno sem membro correspondente em "
        f"{nome_enum} — {sorted(valores_internos - nomes_do_enum)}"
    )


def test_detector_de_rotulo_pega_rotulo_proposital() -> None:
    """Prova negativa da metade 2: alimenta o PRÓPRIO detector com um trecho
    que traduz o rótulo em português — construído como string, nunca escrito
    em `app/` — e confere que ele é pego, nomeando a linha. Sem isto, os dois
    testes de rótulo passariam igualmente bem com o detector quebrado: eles
    varrem um arquivo em que a resposta correta é "nenhum", e verificação
    vácua não distingue "não há violação" de "não sei detectar violação"."""
    rotulo_real = ROTULOS_B4_03[0]
    codigo_com_traducao = (
        "def _disposicao_uso_reserva(respostas):\n"
        f'    if respostas.valor("DISPOSICAO_USO_RESERVA") == "{rotulo_real}":\n'
        "        return DISPOSICAO_USO_RESERVA.PARTE\n"
    )

    violacoes = _detectar_rotulos_no_texto(
        codigo_com_traducao, ID_DISPOSICAO_USO_RESERVA, ROTULOS_B4_03
    )

    assert violacoes, "esperava que o detector pegasse o rótulo em português proposital"
    assert violacoes[0].rotulo == rotulo_real
    assert violacoes[0].linha == 2


def test_detector_de_rotulo_pega_rotulo_em_comentario() -> None:
    """Prova negativa da metade 2, segunda forma: o rótulo copiado para um
    COMENTÁRIO — que não aparece na AST e escaparia de uma auditoria só
    estrutural. É por isso que esta metade busca sobre o texto."""
    rotulo_real = ROTULOS_B4_02[1]  # o rótulo longo de B4.02 ("reserva estruturada")
    codigo_com_comentario = f"# opção do meio de B4.02: {rotulo_real}\nvalor = None\n"

    violacoes = _detectar_rotulos_no_texto(
        codigo_com_comentario, ID_RESERVA_EXISTE, ROTULOS_B4_02
    )

    assert violacoes, "esperava pegar o rótulo escrito em comentário"
    assert violacoes[0].linha == 1


def test_detector_de_cadeia_pega_traducao_proposital() -> None:
    """Prova negativa da metade 1: uma cadeia de `if` sobre `valor_interno` —
    a violação que `_membro_do_enum` existe para tornar desnecessária — é
    pega pelo detector de comparações contra literal de string, e o
    dicionário de tradução equivalente é pego pelo detector de `ast.Dict`."""
    codigo_cadeia = """
def _reserva_existe(respostas):
    valor = respostas.valor("RESERVA_EXISTE")
    if valor == "SIM":
        return RESERVA_EXISTE.SIM
    if valor == "INFORMAL":
        return RESERVA_EXISTE.INFORMAL
    return RESERVA_EXISTE.NAO
"""
    codigo_dicionario = """
def _reserva_existe(respostas):
    tabela = {"SIM": RESERVA_EXISTE.SIM, "NAO": RESERVA_EXISTE.NAO}
    return tabela[respostas.valor("RESERVA_EXISTE")]
"""
    funcao_cadeia = ast.parse(codigo_cadeia).body[0]
    funcao_dicionario = ast.parse(codigo_dicionario).body[0]
    assert isinstance(funcao_cadeia, ast.FunctionDef)
    assert isinstance(funcao_dicionario, ast.FunctionDef)

    comparacoes = _comparacoes_com_string(funcao_cadeia)
    dicionarios = _dicionarios_literais(funcao_dicionario)

    assert comparacoes, "esperava pegar a cadeia de `if` sobre valor_interno"
    assert {texto for _, texto in comparacoes} >= {"SIM", "INFORMAL"}
    assert dicionarios, "esperava pegar o dicionário literal de tradução"

    # E a contraprova: a função REAL, que usa `_membro_do_enum`, não é pega
    # por nenhum dos dois — a fronteira separa tradução de resolução.
    funcao_real = _corpo_da_funcao(_codigo_fonte_da_montagem(), "_reserva_existe")
    assert not _comparacoes_com_string(funcao_real)
    assert not _dicionarios_literais(funcao_real)
    assert _chama_mecanismo_generico(funcao_real)


def test_detector_de_mecanismo_pega_funcao_sem_membro_do_enum() -> None:
    """Prova negativa da metade 1, complemento: uma função que resolve o enum
    por outro caminho (`RESERVA_EXISTE[valor]` inline, sem passar pelo
    mecanismo genérico) é reportada — o teste não passa só por a função
    existir."""
    codigo_sem_mecanismo = """
def _reserva_existe(respostas):
    return RESERVA_EXISTE[respostas.valor("RESERVA_EXISTE")]
"""
    funcao = ast.parse(codigo_sem_mecanismo).body[0]
    assert isinstance(funcao, ast.FunctionDef)

    assert not _chama_mecanismo_generico(funcao), (
        "o detector deveria reportar ausência de `_membro_do_enum` nesta função"
    )
