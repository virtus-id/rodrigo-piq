"""Fronteira `Decimal` única — RF-13, AC-09, EC-01.

`app/montagem/conversao.py` (ainda não existe — nasce em `T-38`) é o **único**
módulo desta feature autorizado a converter entrada de usuário em `Decimal`.
O plano (`plans/app-aluno.plan.md` §5.1) é explícito: *"o teste estático de §9
falha se qualquer outro arquivo chamar `Decimal(...)` sobre entrada de
usuário"*. `_recusar_float` do motor (`engine/precisao.py::dinheiro`) é a
**última** linha de defesa, em tempo de execução — tarde demais para pegar em
CI antes de rodar. Este teste é a primeira: AST em tempo de checagem estática,
escrito ANTES de `app/montagem/conversao.py` existir, para que o módulo nasça
já no lugar certo (nenhum arquivo real viola hoje, porque as pastas estão
vazias).

Dois alvos, na mesma varredura AST, sobre as mesmas quatro pastas
(`app/`, `collection/`, `report/`, `persistencia/app_aluno/`):

1. **`Decimal(...)` construído fora de `app/montagem/conversao.py`.** Cobre
   `Decimal` importado de `decimal` (`from decimal import Decimal`) e chamado
   como `Decimal(...)`, e também `decimal.Decimal(...)` via `import decimal`.
   `engine.precisao.dinheiro(...)` é tratado como equivalente — é o
   construtor autorizado pelo motor, mas se chamado fora da fronteira única
   ele reproduz exatamente o mesmo problema que `Decimal(...)` direto.
2. **`float(...)` chamado sobre qualquer valor, em qualquer uma das quatro
   pastas, sem exceção nenhuma** — nem `app/montagem/conversao.py` escapa
   disto: a fronteira converte para `Decimal`, nunca para `float`; `float`
   não tem nenhum uso legítimo em caminho de valor monetário nesta feature
   (`sdd.config.md` §4, "Precisão interna integral").

Exceção declarada explicitamente (critério de aceite): a DESSERIALIZAÇÃO do
adaptador de persistência. Um adaptador de banco/arquivo em
`persistencia/app_aluno/*.py` precisa reconstruir um `Decimal` a partir de uma
string/numeric que **já veio validada do próprio banco** — isso não é
"conversão de entrada de usuário nova" (o valor já passou pela fronteira
quando foi gravado) e não deveria ser forçado a existir em
`app/montagem/conversao.py`, que é código de camada de aplicação, não de
adaptador de dados.

Critério objetivo escolhido para diferenciar essa exceção de "conversão de
entrada de usuário comum" (decisão desta tarefa, ver AC "As exceções
permitidas... estão declaradas explicitamente"): **não é a pasta inteira que
é exceção** — só o CORPO DE UMA FUNÇÃO cujo nome comece literalmente com o
prefixo `desserializar_`, e apenas dentro de `persistencia/app_aluno/*.py`.
Fora desse prefixo de nome de função, `persistencia/app_aluno/` está sujeita
à mesma regra de `app/`, `collection/` e `report/`. Por quê um prefixo de
nome de função, e não "a pasta toda":
  - O critério de aceite da tarefa lista explicitamente
    `persistencia/app_aluno/` entre "essas pastas" onde a fronteira única se
    aplica — liberar a pasta inteira contradiria o próprio critério.
  - Um nome de função é um marcador objetivo, verificável por AST
    (`FunctionDef.name`), sem exigir comentário mágico nem heurística sobre
    a origem do dado.
  - O prefixo nomeia a intenção no próprio código: quem lê
    `desserializar_resposta_numerica` sabe, sem abrir o corpo, que ali dentro
    o valor já é confiável (veio de uma coluna `numeric`/linha já gravada),
    e não uma string de formulário.

Mesma técnica de `test_fronteira_import_engine.py` (T-06) e
`test_sem_conteudo_de_questionario_no_codigo.py` (T-08): `ast.parse` sobre o
texto do arquivo, nunca `importlib`/exec; o teste real sobre o repositório
(que hoje deve dar zero violações, pastas vazias) é separado dos testes que
provam a detecção com casos SINTÉTICOS de violação, escritos como string e
parseados isoladamente via `tmp_path` — nenhum arquivo violador real precisa
existir no repo hoje para provar que o detector funciona.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent

# As quatro pastas cobertas pelo critério de aceite ("essas pastas") — nomes
# relativos à raiz do projeto, para poder comparar o caminho do arquivo
# encontrado contra o único módulo isento (item abaixo).
PASTAS_VERIFICADAS: Final[tuple[str, ...]] = (
    "app",
    "collection",
    "report",
    "persistencia/app_aluno",
)

# O único módulo autorizado a construir Decimal/dinheiro(...) sobre entrada
# de usuário — caminho relativo à raiz do projeto, com barra normal.
MODULO_FRONTEIRA_UNICA: Final[str] = "app/montagem/conversao.py"

# Exceção EXPLÍCITA (critério de aceite: "declaradas explicitamente no
# teste"): dentro de `persistencia/app_aluno/*.py`, uma função cujo NOME
# comece com este prefixo é a desserialização do adaptador de persistência —
# reconstrução de um valor já validado, vindo do próprio banco, nunca de
# entrada de usuário nova. Ver docstring do módulo para a justificativa do
# critério (prefixo de nome de função, não "a pasta inteira").
PREFIXO_FUNCAO_DESSERIALIZACAO: Final[str] = "desserializar_"
PASTA_COM_EXCECAO_DE_DESSERIALIZACAO: Final[str] = "persistencia/app_aluno"

# Nomes que, chamados, constroem Decimal — direto ou via fronteira do motor.
NOMES_CONSTRUTORES_DECIMAL: Final[frozenset[str]] = frozenset({"Decimal", "dinheiro"})


@dataclass(frozen=True, slots=True)
class ViolacaoFronteiraDecimal:
    arquivo: str
    linha: int
    descricao: str


def _caminho_relativo(nome_arquivo: str) -> str:
    """Normaliza o caminho recebido para comparação com
    `MODULO_FRONTEIRA_UNICA`/`PASTA_COM_EXCECAO_DE_DESSERIALIZACAO` — troca
    `\\` por `/` (Windows) e tenta relativizar à raiz do projeto quando
    possível; se não for um caminho do projeto (caso sintético de teste),
    usa o próprio nome recebido, normalizado."""
    caminho = Path(nome_arquivo)
    try:
        relativo = caminho.resolve().relative_to(RAIZ_PROJETO)
        return relativo.as_posix()
    except (ValueError, OSError):
        return nome_arquivo.replace("\\", "/")


def _e_modulo_fronteira_unica(caminho_relativo: str) -> bool:
    return caminho_relativo == MODULO_FRONTEIRA_UNICA or caminho_relativo.endswith(
        "/" + MODULO_FRONTEIRA_UNICA
    )


def _e_arquivo_de_persistencia_app_aluno(caminho_relativo: str) -> bool:
    return caminho_relativo.startswith(
        PASTA_COM_EXCECAO_DE_DESSERIALIZACAO + "/"
    ) or (f"/{PASTA_COM_EXCECAO_DE_DESSERIALIZACAO}/" in caminho_relativo)


def _funcoes_que_envolvem_linha(
    arvore: ast.Module,
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]]:
    """Devolve, para cada função/método do módulo, a faixa de linhas
    (`lineno`..`end_lineno`) do seu corpo — usado para decidir se uma
    chamada de `Decimal(...)` cai dentro de uma função de desserialização."""
    funcoes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]] = []
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fim = no.end_lineno if no.end_lineno is not None else no.lineno
            funcoes.append((no, no.lineno, fim))
    return funcoes


def _dentro_de_funcao_de_desserializacao(
    linha: int, funcoes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int, int]]
) -> bool:
    """A chamada na `linha` está dentro do corpo de alguma função cujo nome
    comece com `PREFIXO_FUNCAO_DESSERIALIZACAO`? Usa a função mais interna
    (menor intervalo) que contém a linha, para lidar com funções aninhadas."""
    candidatas = [
        (nome_no, inicio, fim)
        for (nome_no, inicio, fim) in funcoes
        if inicio <= linha <= fim
    ]
    if not candidatas:
        return False
    # A mais interna é a de menor extensão (fim - inicio).
    mais_interna = min(candidatas, key=lambda item: item[2] - item[1])
    return mais_interna[0].name.startswith(PREFIXO_FUNCAO_DESSERIALIZACAO)


def verificar_arquivo(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoFronteiraDecimal]:
    """Percorre a AST de `codigo_fonte` e devolve toda violação da fronteira
    `Decimal` única (RF-13). Nunca importa o arquivo — só o parseia.

    - `Decimal(...)`/`dinheiro(...)` fora de `app/montagem/conversao.py` é
      violação, EXCETO se o arquivo pertence a
      `persistencia/app_aluno/*.py` E a chamada está dentro do corpo de uma
      função cujo nome comece com `desserializar_`.
    - `float(...)` é sempre violação, em qualquer uma das quatro pastas, sem
      exceção — nem a própria fronteira única a admite.
    """
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    caminho_relativo = _caminho_relativo(nome_arquivo)
    e_fronteira_unica = _e_modulo_fronteira_unica(caminho_relativo)
    e_persistencia_app_aluno = _e_arquivo_de_persistencia_app_aluno(caminho_relativo)
    funcoes = _funcoes_que_envolvem_linha(arvore) if e_persistencia_app_aluno else []

    violacoes: list[ViolacaoFronteiraDecimal] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue

        nome_chamado = _nome_da_chamada(no.func)
        if nome_chamado is None:
            continue

        if nome_chamado in NOMES_CONSTRUTORES_DECIMAL:
            if e_fronteira_unica:
                continue
            if e_persistencia_app_aluno and _dentro_de_funcao_de_desserializacao(
                no.lineno, funcoes
            ):
                continue
            violacoes.append(
                ViolacaoFronteiraDecimal(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao=(
                        f"`{nome_chamado}(...)` construído fora da fronteira única "
                        f"({MODULO_FRONTEIRA_UNICA}): RF-13"
                    ),
                )
            )
        elif nome_chamado == "float":
            violacoes.append(
                ViolacaoFronteiraDecimal(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    descricao="`float(...)` chamado sobre valor: RF-13 proíbe float no caminho",
                )
            )

    return violacoes


def _nome_da_chamada(no_func: ast.expr) -> str | None:
    """Extrai o nome "simples" de uma chamada — `Decimal(...)` → `"Decimal"`,
    `decimal.Decimal(...)` → `"Decimal"`, `engine.precisao.dinheiro(...)` →
    `"dinheiro"`, `float(...)` → `"float"`. Ignora chamadas cujo alvo não é
    nem `Name` nem `Attribute` (ex.: resultado de outra chamada)."""
    if isinstance(no_func, ast.Name):
        return no_func.id
    if isinstance(no_func, ast.Attribute):
        return no_func.attr
    return None


def _mensagem(violacoes: list[ViolacaoFronteiraDecimal]) -> str:
    return "fronteira Decimal única violada (RF-13):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )


def _arquivos_py_das_pastas_verificadas() -> list[Path]:
    arquivos: list[Path] = []
    for nome_pasta in PASTAS_VERIFICADAS:
        pasta = RAIZ_PROJETO / nome_pasta
        if pasta.is_dir():
            arquivos.extend(sorted(pasta.rglob("*.py")))
    return arquivos


def test_fronteira_decimal_unica_rf_13_pastas_ainda_vazias() -> None:
    """RF-13: nenhum arquivo de `app/`, `collection/`, `report/` ou
    `persistencia/app_aluno/` viola a fronteira `Decimal` única hoje — as
    pastas ainda não têm `app/montagem/conversao.py` nem qualquer outro
    módulo de lógica (só `__init__.py`), e `persistencia/app_aluno/` ainda
    nem existe como pasta (nasce em `T-22`/`T-23`/`T-24`)."""
    violacoes: list[ViolacaoFronteiraDecimal] = []
    for arquivo in _arquivos_py_das_pastas_verificadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(verificar_arquivo(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_decimal_construido_fora_da_fronteira(tmp_path: Path) -> None:
    """Caso sintético: `Decimal(...)` chamado num módulo qualquer de `app/`
    que não seja `app/montagem/conversao.py` — RF-13, "o teste falha se
    `Decimal(...)` for construído em qualquer arquivo dessas pastas que não
    seja `app/montagem/conversao.py`"."""
    codigo_com_violacao = """
from decimal import Decimal

def montar_valor(texto: str) -> Decimal:
    return Decimal(texto)
"""
    arquivo_temporario = tmp_path / "app" / "http" / "rotas_resposta.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse Decimal(...) fora da fronteira única"
    assert violacoes[0].linha == 5
    assert "Decimal" in violacoes[0].descricao


def test_detector_pega_dinheiro_chamado_fora_da_fronteira(tmp_path: Path) -> None:
    """`engine.precisao.dinheiro(...)` chamado fora de
    `app/montagem/conversao.py` é tratado como a mesma violação que
    `Decimal(...)` direto — é o mesmo problema (conversão de entrada de
    usuário fora da fronteira única), só que via o construtor do motor."""
    codigo_com_violacao = """
from engine.precisao import dinheiro

def montar_valor(texto: str) -> None:
    return dinheiro(texto)
"""
    arquivo_temporario = tmp_path / "collection" / "validacao.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse dinheiro(...) fora da fronteira única"
    assert "dinheiro" in violacoes[0].descricao


def test_detector_pega_float_em_qualquer_uma_das_pastas(tmp_path: Path) -> None:
    """RF-13/EC-01: `float(...)` nunca é permitido em nenhuma das quatro
    pastas — "o teste falha se `float(...)` for chamado sobre qualquer valor
    em qualquer dessas pastas". Verificado aqui em `report/`."""
    codigo_com_violacao = """
def exibir_valor(valor: str) -> float:
    return float(valor)
"""
    arquivo_temporario = tmp_path / "report" / "templates_apoio.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse float(...) em report/"
    assert "float" in violacoes[0].descricao


def test_detector_pega_float_mesmo_dentro_da_fronteira_unica(tmp_path: Path) -> None:
    """`float(...)` não tem exceção nenhuma — nem o próprio
    `app/montagem/conversao.py` pode chamá-lo. A fronteira converte para
    `Decimal`, nunca para `float`."""
    codigo_com_violacao = """
def normalizar(texto: str) -> float:
    return float(texto.replace(",", "."))
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "conversao.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que float(...) fosse pego mesmo dentro da fronteira única"
    assert "float" in violacoes[0].descricao


def test_detector_aceita_decimal_dentro_da_fronteira_unica(tmp_path: Path) -> None:
    """Prova negativa: `Decimal(...)`/`dinheiro(...)` DENTRO de
    `app/montagem/conversao.py` não é violação — é exatamente o módulo
    autorizado pelo critério de aceite."""
    codigo_permitido = """
from decimal import Decimal
from engine.precisao import dinheiro

def converter_para_dinheiro(texto: str) -> Decimal:
    normalizado = texto.replace(",", ".")
    return dinheiro(Decimal(normalizado))
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "conversao.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_aceita_desserializacao_no_adaptador_de_persistencia(tmp_path: Path) -> None:
    """Exceção declarada explicitamente: dentro de
    `persistencia/app_aluno/*.py`, uma função cujo nome comece com
    `desserializar_` pode construir `Decimal(...)` a partir de uma string já
    validada vinda do PRÓPRIO banco — não é conversão de entrada de usuário
    nova, é reconstrução de um valor já gravado."""
    codigo_permitido = """
from decimal import Decimal

def desserializar_resposta_numerica(linha_do_banco: dict[str, str]) -> Decimal:
    # `linha_do_banco["valor_numerico"]` já passou pela fronteira única
    # quando foi gravado — isto é leitura, não entrada de usuário nova.
    return Decimal(linha_do_banco["valor_numerico"])
"""
    arquivo_temporario = tmp_path / "persistencia" / "app_aluno" / "respostas.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_recusa_decimal_em_persistencia_fora_de_funcao_desserializar(
    tmp_path: Path,
) -> None:
    """A exceção NÃO é "a pasta inteira": `Decimal(...)` construído em
    `persistencia/app_aluno/*.py` FORA de uma função `desserializar_*`
    continua sendo violação — por exemplo, uma função de gravação que
    tentasse converter uma string de entrada nova em vez de delegar à
    fronteira única."""
    codigo_com_violacao = """
from decimal import Decimal

def gravar_resposta_numerica(texto_recebido_da_rota: str) -> None:
    valor = Decimal(texto_recebido_da_rota)
    _persistir(valor)


def _persistir(valor: Decimal) -> None:
    pass
"""
    arquivo_temporario = tmp_path / "persistencia" / "app_aluno" / "respostas.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, (
        "Decimal(...) fora de uma função desserializar_* em "
        "persistencia/app_aluno/ deveria continuar violando RF-13"
    )
    assert violacoes[0].linha == 5


def test_detector_recusa_float_dentro_de_funcao_desserializar(tmp_path: Path) -> None:
    """A exceção de desserialização cobre só `Decimal`/`dinheiro` — `float`
    continua proibido mesmo dentro de uma função `desserializar_*`."""
    codigo_com_violacao = """
def desserializar_resposta_numerica(linha_do_banco: dict[str, str]) -> float:
    return float(linha_do_banco["valor_numerico"])
"""
    arquivo_temporario = tmp_path / "persistencia" / "app_aluno" / "respostas.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "float(...) deveria continuar proibido mesmo dentro de desserializar_*"
    assert "float" in violacoes[0].descricao


def test_detector_nomeia_arquivo_e_linha_da_violacao() -> None:
    """O critério de aceite exige (por analogia com T-06/T-08, mesmo estilo
    de auditoria) que a falha nomeie arquivo e linha — verificado
    diretamente nos campos de `ViolacaoFronteiraDecimal`."""
    codigo_com_violacao = """
def a():
    pass


from decimal import Decimal
Decimal("1")
"""
    violacoes = verificar_arquivo(codigo_com_violacao, "app/exemplo.py")

    assert len(violacoes) == 1
    assert violacoes[0].arquivo == "app/exemplo.py"
    assert violacoes[0].linha == 7
