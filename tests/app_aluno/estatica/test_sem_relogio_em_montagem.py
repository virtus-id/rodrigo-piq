"""Nenhuma chamada a `date.today()`/`datetime.now()` em `app/montagem/` —
`RF-14`, `AC-18` (`T-51`).

`EstadoFinanceiro.DATA_REFERENCIA` (`engine/estado.py`) é INPUT, nunca lido do
relógio: `Caso.DATA_REFERENCIA` (`app/casos/maquina.py`) é a única fonte, e
`app/montagem/estado.py::montar_estado_financeiro` a recebe como parâmetro
explícito (`T-51`). É isso que faz recalcular o mesmo caso com a mesma
`DATA_REFERENCIA` produzir o mesmo `SNAPSHOT_ID` (`AC-18`) — um único
`date.today()`/`datetime.now()` escondido em `app/montagem/` quebraria essa
determinística silenciosamente, sem que nenhum teste de comportamento (que
usa datas fixas de fixture) jamais pegasse a regressão.

Mesma técnica de `test_fronteira_import_engine.py` (T-06),
`test_sem_conteudo_de_questionario_no_codigo.py` (T-08) e
`test_fronteira_decimal_unica.py` (T-27): `ast.parse` sobre o texto do
arquivo, nunca `importlib`/exec — o teste real sobre o repositório (que hoje
deve dar zero violações) é separado dos testes que provam a detecção com
casos SINTÉTICOS de violação, parseados isoladamente via `tmp_path`.

Escopo desta tarefa: só `app/montagem/` (`Arquivos: app/montagem/estado.py`
de `T-51`) — não as quatro pastas de `T-06`/`T-08`/`T-27`. `date`/`datetime`
seguem sendo usados normalmente em `app/montagem/` como TIPO (anotação,
`isinstance`) e para RECEBER um valor já construído fora daqui (parâmetro de
função) — só a CHAMADA `date.today()`/`datetime.now()`/`datetime.utcnow()` é
violação.

REGRAS: `RF-14`, `AC-18`
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent

# Escopo desta tarefa (T-51): só app/montagem/ — não as quatro pastas mais
# amplas de T-06/T-08/T-27, que cobrem uma preocupação diferente (fronteira
# de import, conteúdo de questionário, fronteira Decimal).
PASTA_VERIFICADA: Final[str] = "app/montagem"

# `Attribute.attr` que, chamado como `ast.Call`, é leitura de relógio —
# qualquer forma de obter a data/hora corrente, não só `date.today()`.
NOMES_DE_CHAMADA_DE_RELOGIO: Final[frozenset[str]] = frozenset(
    {"today", "now", "utcnow", "utcnow_factory"}
)

# `Attribute.value` (o "dono" do atributo) precisa ser um destes dois nomes
# — `date`/`datetime`, importados de `datetime` (stdlib) — para que a
# chamada seja considerada leitura de relógio. Isso evita falso positivo
# sobre um método `.now()`/`.today()` de outra classe qualquer que não seja
# `date`/`datetime` (nenhum caso hoje, mas o critério fica explícito).
NOMES_DE_CLASSE_DE_RELOGIO: Final[frozenset[str]] = frozenset({"date", "datetime"})


@dataclass(frozen=True, slots=True)
class ViolacaoRelogio:
    arquivo: str
    linha: int
    descricao: str


def _caminho_relativo(nome_arquivo: str) -> str:
    caminho = Path(nome_arquivo)
    try:
        relativo = caminho.resolve().relative_to(RAIZ_PROJETO)
        return relativo.as_posix()
    except (ValueError, OSError):
        return nome_arquivo.replace("\\", "/")


def verificar_arquivo(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoRelogio]:
    """Percorre a AST de `codigo_fonte` e devolve toda chamada a
    `date.today()`/`datetime.now()`/`datetime.utcnow()` (AC-18). Nunca
    importa o arquivo — só o parseia.

    Cobre `date.today()`/`datetime.now()`/`datetime.utcnow()` chamados via
    o nome da classe importada diretamente (`from datetime import date,
    datetime`) e via módulo (`datetime.date.today()`,
    `datetime.datetime.now()`, `import datetime`).
    """
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoRelogio] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr not in NOMES_DE_CHAMADA_DE_RELOGIO:
            continue

        dono = no.func.value
        # Caso 1: `date.today()` / `datetime.now()` — dono é o Name importado
        # diretamente de `datetime` (`from datetime import date, datetime`).
        if isinstance(dono, ast.Name) and dono.id in NOMES_DE_CLASSE_DE_RELOGIO:
            violacoes.append(_violacao(nome_arquivo, no))
            continue
        # Caso 2: `datetime.datetime.now()` / `datetime.date.today()` — dono
        # é um Attribute cujo valor é o módulo `datetime` (`import datetime`).
        if (
            isinstance(dono, ast.Attribute)
            and dono.attr in NOMES_DE_CLASSE_DE_RELOGIO
            and isinstance(dono.value, ast.Name)
            and dono.value.id == "datetime"
        ):
            violacoes.append(_violacao(nome_arquivo, no))
            continue
        # Caso 3: `datetime.now()` via `import datetime` direto (sem duplo
        # atributo) — dono é o Name do módulo `datetime`.
        if isinstance(dono, ast.Name) and dono.id == "datetime":
            violacoes.append(_violacao(nome_arquivo, no))

    return violacoes


def _violacao(nome_arquivo: str, no: ast.Call) -> ViolacaoRelogio:
    assert isinstance(no.func, ast.Attribute)
    return ViolacaoRelogio(
        arquivo=nome_arquivo,
        linha=no.lineno,
        descricao=(
            f"`.{no.func.attr}()` lê o relógio do sistema — DATA_REFERENCIA "
            "deve vir do Caso, nunca de date.today()/datetime.now() (AC-18)"
        ),
    )


def _mensagem(violacoes: list[ViolacaoRelogio]) -> str:
    return "leitura de relógio em app/montagem/ (AC-18):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )


def _arquivos_py_da_pasta_verificada() -> list[Path]:
    pasta = RAIZ_PROJETO / PASTA_VERIFICADA
    if not pasta.is_dir():
        return []
    return sorted(pasta.rglob("*.py"))


def test_sem_relogio_em_app_montagem_ac_18() -> None:
    """AC-18: nenhuma chamada a `date.today()`/`datetime.now()` existe em
    `app/montagem/` hoje — `DATA_REFERENCIA` é sempre parâmetro explícito
    (`Caso.DATA_REFERENCIA`, `app/casos/maquina.py`), nunca lida do relógio."""
    violacoes: list[ViolacaoRelogio] = []
    for arquivo in _arquivos_py_da_pasta_verificada():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(verificar_arquivo(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_date_today_importado_diretamente(tmp_path: Path) -> None:
    """Caso sintético: `from datetime import date` + `date.today()` — a
    forma mais comum de vazamento de relógio."""
    codigo_com_violacao = """
from datetime import date

def montar_data_referencia() -> date:
    return date.today()
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "estado.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse date.today()"
    assert violacoes[0].linha == 5
    assert "today" in violacoes[0].descricao


def test_detector_pega_datetime_now_importado_diretamente(tmp_path: Path) -> None:
    """`datetime.now()` — mesma classe de violação, outra chamada."""
    codigo_com_violacao = """
from datetime import datetime

def marcar_interacao() -> datetime:
    return datetime.now()
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "conversao.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse datetime.now()"
    assert "now" in violacoes[0].descricao


def test_detector_pega_datetime_utcnow_via_modulo_importado(tmp_path: Path) -> None:
    """`import datetime` + `datetime.datetime.utcnow()` — forma via módulo,
    não via `from datetime import ...`."""
    codigo_com_violacao = """
import datetime

def marcar_interacao() -> datetime.datetime:
    return datetime.datetime.utcnow()
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "estado.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_com_violacao, str(arquivo_temporario))

    assert violacoes, "esperava que o detector pegasse datetime.datetime.utcnow()"
    assert "utcnow" in violacoes[0].descricao


def test_detector_aceita_data_referencia_como_parametro_explicito(tmp_path: Path) -> None:
    """Prova negativa: usar `date`/`datetime` como TIPO de anotação e
    receber o valor como parâmetro (o padrão real de `montar_estado_
    financeiro`) não é violação — só a CHAMADA de leitura de relógio é."""
    codigo_permitido = """
from datetime import date

def montar_estado_financeiro(DATA_REFERENCIA: date) -> date:
    return DATA_REFERENCIA
"""
    arquivo_temporario = tmp_path / "app" / "montagem" / "estado.py"
    arquivo_temporario.parent.mkdir(parents=True)
    arquivo_temporario.write_text(codigo_permitido, encoding="utf-8")

    violacoes = verificar_arquivo(codigo_permitido, str(arquivo_temporario))

    assert not violacoes, _mensagem(violacoes)


def test_detector_nomeia_arquivo_e_linha_da_violacao() -> None:
    """Mesmo padrão de T-06/T-08/T-27: a falha nomeia arquivo e linha."""
    codigo_com_violacao = """
def a():
    pass


from datetime import date
date.today()
"""
    violacoes = verificar_arquivo(codigo_com_violacao, "app/montagem/estado.py")

    assert len(violacoes) == 1
    assert violacoes[0].arquivo == "app/montagem/estado.py"
    assert violacoes[0].linha == 7
