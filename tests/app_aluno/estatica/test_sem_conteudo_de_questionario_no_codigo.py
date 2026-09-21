"""Lint estático: nenhum enunciado, opção ou condição das 291 perguntas, e
nenhum valor `P_*` da §8, em `.py` de `app/`, `collection/` e `report/` —
RF-03, RF-32, AC-37.

`AC-37`: "Dado o código-fonte desta feature, quando auditado, então nenhum
enunciado, opção ou condição de exibição das 291 perguntas aparece escrito
nele, e nenhum valor `P_*` da §8 aparece nele." A coleta é DADO (YAML em
`collection/registros/`, carregado por `collection/carga.py` — T-16), nunca
código; este teste é o portão que impede a regressão inversa (alguém
"otimizar" reescrevendo um enunciado direto em `.py`).

Regra operacional (decisão desta tarefa) e suas LIMITAÇÕES
------------------------------------------------------------------
Como em `tests/estatica/test_nenhum_parametro_no_codigo.py` (o precedente do
motor para "nenhum `P_*` no código"), a varredura por AST não prova ausência
de conteúdo de questionário em sentido absoluto — ela prova a ausência dos
padrões que procura. Dois alvos, tratados por regras distintas:

**(a) Identificador `P_*` — robusta, sem limiar.** Qualquer nome (`ast.Name`,
alvo de atribuição, argumento de função, ou acesso a atributo/chamada) que
comece literalmente com `P_` é reportado, dentro de `app/`, `collection/` e
`report/`. Diferente do teste irmão do motor, aqui a regra é mais estrita:
nesta feature **nenhum** parâmetro P_* deveria ser referenciado por nome de
jeito nenhum — quem lê parâmetro é `engine/`, nunca a camada de aplicação
(Lei nº 3, `plans/app-aluno.plan.md` §1). Não há "leitura legítima via
`Parametros.numero(...)` com prefixo correto" a excluir aqui, ao contrário do
motor.

**(b) Enunciado/opção/condição como string longa — LIMITADA por um limiar de
tamanho, e por quê.** Não existe como distinguir por AST puro "esta string é
um enunciado de pergunta da §11" de "esta string é uma mensagem técnica
legítima" sem uma lista de conteúdo real das 291 perguntas (que não deveria
existir em `.py`, sob pena de reintroduzir o próprio problema que o teste
audita). A operacionalização adotada:

  - **Limiar: N = 40 caracteres.** Todo literal de string (`ast.Constant`,
    `value: str`) com mais de 40 caracteres, fora de docstring e fora das
    exceções explícitas abaixo, é reportado como suspeito de ser um
    enunciado/opção/condição de pergunta.
    Justificativa do valor: mensagens técnicas curtas em pt-BR do próprio
    projeto (nomes de chave de configuração, identificadores, mensagens de
    erro técnicas como "Sessão inválida ou expirada.") ficam tipicamente
    abaixo de 40 caracteres; um enunciado real de pergunta da §11 (ex.:
    `B2.13`/`AUTOPERCEPCAO_CONTROLE`, ou qualquer rótulo de opção com
    contexto) é sempre uma frase com mais de 40 caracteres. 40 é uma escolha
    conservadora — alta o bastante para não pegar mensagem técnica curta,
    baixa o bastante para pegar qualquer enunciado real.
  - **Docstrings são sempre isentas.** O primeiro `ast.Constant` de string de
    um `Module`/`ClassDef`/`FunctionDef`/`AsyncFunctionDef` (a docstring, na
    posição em que `ast.get_docstring` a reconhece) nunca é avaliado pelo
    limiar — documentação narrativa do próprio código, nunca conteúdo do
    questionário.
  - **Lista de exceções EXPLÍCITA (não heurística implícita).** Strings que
    batem em qualquer padrão de `EXCECOES_PERMITIDAS` abaixo são isentas do
    limiar mesmo tendo mais de 40 caracteres. A lista é curada e comentada
    caso a caso — nunca "qualquer string com jeito de mensagem de erro".

O que este teste **não** garante: um enunciado de pergunta com menos de 40
caracteres (não há caso conhecido nas 291 perguntas da §11 — a mais curta
ainda é uma frase) escaparia da detecção por tamanho. É uma lacuna conhecida
e documentada, na mesma lógica do teste irmão do motor: o projeto prefere um
limiar simples e auditável a uma heurística elaborada e frágil.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
PASTAS_AUDITADAS: Final[tuple[str, ...]] = ("app", "collection", "report")

# Limiar operacional — ver docstring do módulo, item (b).
LIMITE_CARACTERES_STRING: Final[int] = 40

# Lista EXPLÍCITA de exceções permitidas (critério de aceite: "declaradas
# explicitamente numa lista no teste, não implícitas"). Cada padrão é um
# regex ancorado que precisa CASAR A STRING INTEIRA (`re.fullmatch`) — nunca
# um "contém", para não abrir uma brecha ampla demais.
EXCECOES_PERMITIDAS: Final[tuple[re.Pattern[str], ...]] = (
    # Mensagens de erro técnicas reconhecíveis desta camada de aplicação —
    # falam de infraestrutura (sessão, autenticação, validação de payload),
    # nunca de conteúdo financeiro ou de pergunta.
    re.compile(r"Sess[ãa]o inv[áa]lida ou expirada\.?"),
    re.compile(r"Credenciais inv[áa]lidas\.?"),
    re.compile(r"N[ãa]o autorizado(a)?( para este caso)?\.?"),
    re.compile(r"Caso n[ãa]o encontrado\.?"),
    re.compile(r"Registro de pergunta inv[áa]lido: .+"),
    re.compile(r"Falha ao (gravar|ler|carregar) .+ no banco de dados\.?"),
    # Chaves de configuração / variáveis de ambiente — identificadores
    # técnicos, nunca conteúdo do questionário.
    re.compile(r"DATABASE_URL"),
    re.compile(r"CHAVE_ASSINATURA_SESSAO"),
    re.compile(r"[A-Z][A-Z0-9_]{2,}"),  # CONSTANTE_ESTILO_ENV, sem espaço/pontuação de frase
)


@dataclass(frozen=True, slots=True)
class ViolacaoConteudo:
    arquivo: str
    linha: int
    descricao: str


def _e_excecao_permitida(texto: str) -> bool:
    return any(padrao.fullmatch(texto) for padrao in EXCECOES_PERMITIDAS)


def _linhas_de_docstring(arvore: ast.Module) -> set[int]:
    """Coleta o `lineno` de todo nó de string que é a docstring de um
    `Module`/`ClassDef`/`FunctionDef`/`AsyncFunctionDef` — essas são sempre
    isentas do limiar de tamanho, independentemente do conteúdo."""
    linhas: set[int] = set()
    candidatos: list[ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef] = [
        arvore
    ]
    for no in ast.walk(arvore):
        if isinstance(no, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            candidatos.append(no)

    for candidato in candidatos:
        corpo = candidato.body
        if not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            linhas.add(primeiro.value.lineno)

    return linhas


def _detectar_identificador_p(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoConteudo]:
    """(a) — qualquer identificador começando por `P_` referenciado no
    arquivo: nome simples, alvo de atribuição, argumento de função, ou
    atributo. Nesta camada, nenhuma referência a parâmetro é legítima."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoConteudo] = []

    for no in ast.walk(arvore):
        nome_talvez: str | None = None
        linha: int | None = None
        if isinstance(no, ast.Name):
            nome_talvez, linha = no.id, no.lineno
        elif isinstance(no, ast.Attribute):
            nome_talvez, linha = no.attr, no.lineno
        elif isinstance(no, ast.arg):
            nome_talvez, linha = no.arg, no.lineno
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            # Cobre string literal que É o próprio nome do parâmetro, ex.:
            # `"P_TAXA_TOX_ALTA"` passada como chave de configuração solta.
            if no.value.startswith("P_"):
                nome_talvez, linha = no.value, no.lineno

        if nome_talvez is not None and linha is not None and nome_talvez.startswith("P_"):
            violacoes.append(
                ViolacaoConteudo(
                    arquivo=nome_arquivo,
                    linha=linha,
                    descricao=f"referência a identificador de parâmetro {nome_talvez!r}",
                )
            )

    return violacoes


def _detectar_string_longa_suspeita(
    codigo_fonte: str, nome_arquivo: str
) -> list[ViolacaoConteudo]:
    """(b) — literal de string com mais de `LIMITE_CARACTERES_STRING`
    caracteres, fora de docstring e fora de `EXCECOES_PERMITIDAS`."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    linhas_docstring = _linhas_de_docstring(arvore)
    violacoes: list[ViolacaoConteudo] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        texto = no.value
        if len(texto) <= LIMITE_CARACTERES_STRING:
            continue
        if no.lineno in linhas_docstring:
            continue
        if _e_excecao_permitida(texto):
            continue

        violacoes.append(
            ViolacaoConteudo(
                arquivo=nome_arquivo,
                linha=no.lineno,
                descricao=(
                    f"string literal com {len(texto)} caracteres, suspeita de "
                    f"enunciado/opção/condição de pergunta: {texto!r}"
                ),
            )
        )

    return violacoes


def _arquivos_py_das_pastas_auditadas() -> list[Path]:
    arquivos: list[Path] = []
    for nome_pasta in PASTAS_AUDITADAS:
        pasta = RAIZ_PROJETO / nome_pasta
        if pasta.is_dir():
            arquivos.extend(sorted(pasta.rglob("*.py")))
    return arquivos


def test_ac37_nenhum_identificador_p_no_codigo_da_aplicacao() -> None:
    """AC-37: nenhum identificador `P_*` da §8 é referenciado em `.py` de
    `app/`, `collection/` ou `report/`."""
    violacoes: list[ViolacaoConteudo] = []
    for arquivo in _arquivos_py_das_pastas_auditadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_identificador_p(codigo_fonte, str(arquivo)))

    mensagem = "parâmetro P_* referenciado em app/collection/report (AC-37):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_ac37_nenhum_enunciado_de_pergunta_no_codigo_da_aplicacao() -> None:
    """AC-37: nenhuma string longa (enunciado, opção ou condição das 291
    perguntas) aparece como literal em `.py` de `app/`, `collection/` ou
    `report/`, fora de docstring e das exceções explícitas."""
    violacoes: list[ViolacaoConteudo] = []
    for arquivo in _arquivos_py_das_pastas_auditadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_string_longa_suspeita(codigo_fonte, str(arquivo)))

    mensagem = (
        "string longa suspeita de conteúdo de questionário em "
        "app/collection/report (AC-37):\n"
        + "\n".join(f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes)
    )
    assert not violacoes, mensagem


def test_detector_pega_caso_proposital_de_identificador_p(tmp_path: Path) -> None:
    """Prova que o detector de AST pega uma violação de verdade — string
    fabricada em memória e escrita num arquivo temporário (`tmp_path`), sem
    depender de um arquivo real violador em `app/`/`collection`/`report/`
    (as pastas ainda estão vazias). Cobre o critério de aceite "literal P_*
    de parâmetro da §8 faz o teste falhar"."""
    codigo_com_violacao = """
def calcular_algo_na_aplicacao() -> float:
    P_TAXA_TOX_ALTA = 4
    return P_TAXA_TOX_ALTA
"""
    arquivo_temporario = tmp_path / "caso_proposital_parametro.py"
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = _detectar_identificador_p(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse a referência a P_TAXA_TOX_ALTA"
    assert any("P_TAXA_TOX_ALTA" in v.descricao for v in violacoes)


def test_detector_pega_caso_proposital_de_enunciado_longo(tmp_path: Path) -> None:
    """Prova que o detector pega um enunciado de pergunta introduzido como
    string literal fora de docstring — critério de aceite "enunciado de
    pergunta (string longa fora de docstring/mensagem de erro técnica) faz o
    teste falhar". O enunciado usado é fabricado (não é transcrição de uma
    pergunta real da §11), só para provar a detecção."""
    codigo_com_violacao = '''
def montar_pergunta_de_teste() -> str:
    return "Qual é o valor total da sua dívida com o banco neste momento?"
'''
    arquivo_temporario = tmp_path / "caso_proposital_enunciado.py"
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = _detectar_string_longa_suspeita(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse a string longa suspeita de enunciado"
    assert any("suspeita de enunciado" in v.descricao for v in violacoes)


def test_detector_nao_acusa_docstring_longa(tmp_path: Path) -> None:
    """Prova que uma docstring de módulo/função, mesmo com mais de 40
    caracteres, NUNCA é reportada — ela é documentação do código, não
    conteúdo do questionário."""
    codigo_valido = '''
"""Este módulo documenta seu próprio comportamento com uma frase longa."""


def funcao_com_docstring_longa() -> None:
    """Docstring de função também longa, explicando o que a função faz."""
    return None
'''
    arquivo_temporario = tmp_path / "caso_docstring_longa.py"
    arquivo_temporario.write_text(codigo_valido, encoding="utf-8")

    violacoes = _detectar_string_longa_suspeita(codigo_valido, str(arquivo_temporario))

    assert not violacoes, f"docstring não deveria ser reportada, obteve: {violacoes}"


def test_detector_nao_acusa_excecao_explicita(tmp_path: Path) -> None:
    """Prova que uma mensagem técnica da lista `EXCECOES_PERMITIDAS`, mesmo
    longa, não é reportada — mas continua exigindo correspondência exata
    (`fullmatch`), não um "contém" frouxo."""
    codigo_valido = '''
def validar_sessao() -> None:
    raise ValueError("Sessão inválida ou expirada.")
'''
    arquivo_temporario = tmp_path / "caso_excecao_tecnica.py"
    arquivo_temporario.write_text(codigo_valido, encoding="utf-8")

    violacoes = _detectar_string_longa_suspeita(codigo_valido, str(arquivo_temporario))

    assert not violacoes, (
        f"mensagem técnica da lista de exceções não deveria ser reportada: {violacoes}"
    )


def test_pastas_ainda_vazias_nao_produzem_violacao() -> None:
    """AC-37 (parte final): o teste passa com `app/`, `collection/` e
    `report/` ainda vazias de lógica (T-04 só criou `__init__.py` sem
    conteúdo)."""
    violacoes: list[ViolacaoConteudo] = []
    for arquivo in _arquivos_py_das_pastas_auditadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_identificador_p(codigo_fonte, str(arquivo)))
        violacoes.extend(_detectar_string_longa_suspeita(codigo_fonte, str(arquivo)))

    assert not violacoes, f"pastas deveriam estar vazias de violação, obteve: {violacoes}"
