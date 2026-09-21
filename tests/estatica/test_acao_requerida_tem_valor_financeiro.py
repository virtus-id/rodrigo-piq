"""Prova estrutural complementar ao `mypy --strict`: toda construção de
`AcaoRequerida(...)` em `engine/` fornece `VALOR_ACAO_FINANCEIRA_IMEDIATA` —
`RF-61`, `AC-110`, `EC-47`, `US-25` · `T-136`.

`AcaoRequerida.VALOR_ACAO_FINANCEIRA_IMEDIATA` (`T-132`, §14.2.1/§14.2.2) é
campo OBRIGATÓRIO sem default, exatamente como `RF-31`/`RF-41`/`RF-59` antes
dele — quebra de contrato, não adição. `mypy --strict` já recusa qualquer
`AcaoRequerida(...)` que omita o `kwarg` (comando `build`), mas este teste
prova a mesma propriedade por um caminho estrutural independente do
verificador de tipos: varredura de AST sobre o código-fonte de `engine/`,
mesma família de `tests/estatica/test_sem_derivacao_de_classificacao_
mobilizacao.py` e `tests/estatica/test_tipo_acao_apenas_quatro_valores.py`.

Duas provas, mesmo padrão dos dois arquivos acima:

1. **Prova positiva por AST** — `test_toda_construcao_de_acaorequerida_tem_
   valor_acao_financeira_imediata` varre `engine/**/*.py`, localiza todo
   `ast.Call` cujo `func` resolve para o nome `AcaoRequerida` (direto —
   `AcaoRequerida(...)` — ou qualificado — `gates.AcaoRequerida(...)`) e
   confirma que cada chamada tem o `keyword`
   `VALOR_ACAO_FINANCEIRA_IMEDIATA`, nomeando arquivo e linha quando faltar.
   Asserção não vácua: confirma também que ao menos 6 construções foram
   encontradas (hoje: 5 em `engine/gates.py`, 1 em `engine/motor.py`).
2. **Prova negativa** — `test_detector_pega_construcao_proposital_sem_o_
   kwarg`: alimenta o mesmo detector usado em (1) com uma construção de
   `AcaoRequerida(...)` fabricada como STRING, propositalmente sem o
   `keyword` `VALOR_ACAO_FINANCEIRA_IMEDIATA`, e confirma que ela é pega,
   nomeando arquivo e linha — sem isto, (1) passaria igualmente bem com um
   detector quebrado que nunca encontrasse chamada nenhuma.

**O que este lint NÃO pega, deliberadamente.** É uma varredura sintática
sobre a AST, não uma prova de execução: uma construção via `**kwargs`
desempacotados de um dicionário (`AcaoRequerida(**dados)`) não tem um
`ast.keyword` nomeado visível na chamada e escaparia à detecção. Nenhum
ponto de `engine/` constrói `AcaoRequerida` dessa forma hoje (todos os 6
usam `keyword=valor` explícito), e `mypy --strict` continua sendo a
garantia formal que cobre esse caso.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

NOME_CLASSE = "AcaoRequerida"
KWARG_OBRIGATORIO = "VALOR_ACAO_FINANCEIRA_IMEDIATA"

MINIMO_CONSTRUCOES_ESPERADAS = 6
# Hoje: engine/gates.py (5 — Gate 1 dois ramos, Gate 2 dois ramos, Gate 3) +
# engine/motor.py (1 — ação de economia, RF-33). Mínimo, não exato: novas
# construções futuras não quebram este teste.


@dataclass(frozen=True, slots=True)
class ConstrucaoSemValor:
    arquivo: str
    linha: int


def _func_resolve_para_acaorequerida(func: ast.expr) -> bool:
    """`True` se o `func` de um `ast.Call` resolver para o nome
    `AcaoRequerida` — forma direta (`ast.Name`) ou qualificada por módulo
    (`ast.Attribute`, ex.: `gates.AcaoRequerida(...)`)."""
    if isinstance(func, ast.Name):
        return func.id == NOME_CLASSE
    if isinstance(func, ast.Attribute):
        return func.attr == NOME_CLASSE
    return False


def _tem_kwarg_obrigatorio(chamada: ast.Call) -> bool:
    """`True` se a chamada tiver `keyword=VALOR_ACAO_FINANCEIRA_IMEDIATA=...`
    explícito. `keyword.arg is None` é o caso `**dados` (desempacotamento) —
    não conta como o `keyword` nomeado explícito que este lint exige (ver
    limitação documentada na docstring do módulo)."""
    return any(kw.arg == KWARG_OBRIGATORIO for kw in chamada.keywords)


def _detectar_construcoes_sem_valor(
    codigo_fonte: str, nome_arquivo: str
) -> tuple[list[ConstrucaoSemValor], int]:
    """Percorre a AST de `codigo_fonte` e devolve (a) toda construção de
    `AcaoRequerida(...)` que NÃO tem o `keyword`
    `VALOR_ACAO_FINANCEIRA_IMEDIATA`, nomeando arquivo e linha; e (b) o total
    de construções de `AcaoRequerida(...)` encontradas (com ou sem o
    `kwarg`), para a asserção não vácua do chamador."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    sem_valor: list[ConstrucaoSemValor] = []
    total_construcoes = 0

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        if not _func_resolve_para_acaorequerida(no.func):
            continue
        total_construcoes += 1
        if not _tem_kwarg_obrigatorio(no):
            sem_valor.append(ConstrucaoSemValor(arquivo=nome_arquivo, linha=no.lineno))

    return sem_valor, total_construcoes


def test_toda_construcao_de_acaorequerida_tem_valor_acao_financeira_imediata() -> None:
    """`RF-61`, `AC-110`, `EC-47`: varre `engine/**/*.py` por AST e confirma
    que toda construção de `AcaoRequerida(...)` fornece o `kwarg`
    `VALOR_ACAO_FINANCEIRA_IMEDIATA` — nomeando arquivo e linha se faltar.
    Asserção não vácua: ao menos 6 construções encontradas em `engine/`."""
    sem_valor: list[ConstrucaoSemValor] = []
    total_construcoes = 0

    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        sem_valor_arquivo, total_arquivo = _detectar_construcoes_sem_valor(
            codigo_fonte, str(arquivo)
        )
        sem_valor.extend(sem_valor_arquivo)
        total_construcoes += total_arquivo

    mensagem = (
        "AC-110 violado — construção de AcaoRequerida(...) em engine/ sem o "
        f"kwarg obrigatório {KWARG_OBRIGATORIO}:\n"
    ) + "\n".join(f"  {c.arquivo}:{c.linha}" for c in sem_valor)
    assert not sem_valor, mensagem

    # Não vácua: confirma que o detector de fato encontrou construções reais
    # — sem isto, um detector quebrado que nunca encontrasse `ast.Call` algum
    # passaria "por vácuo" na asserção acima.
    assert total_construcoes >= MINIMO_CONSTRUCOES_ESPERADAS, (
        f"esperava ao menos {MINIMO_CONSTRUCOES_ESPERADAS} construções de "
        f"AcaoRequerida(...) em engine/, encontrou {total_construcoes}"
    )


def test_detector_pega_construcao_proposital_sem_o_kwarg() -> None:
    """Prova negativa (mesmo padrão de
    `test_sem_derivacao_de_classificacao_mobilizacao.py::
    test_detector_pega_derivacao_proposital_fora_do_modulo_autorizado`):
    alimenta o PRÓPRIO detector usado acima com uma construção de
    `AcaoRequerida(...)` fabricada como STRING — nunca escrita em `engine/`
    real, nunca executada — propositalmente sem o `keyword`
    `VALOR_ACAO_FINANCEIRA_IMEDIATA`, e confere que ela é pega, nomeando
    arquivo e linha. Sem esta prova, o teste positivo acima passaria
    igualmente bem se o detector estivesse quebrado — verificação vácua não
    distingue "não há violação" de "não sei detectar violação"."""
    codigo_sem_kwarg = """
def construir_acao_incompleta(divida_id, tipo_acao, motivo):
    return AcaoRequerida(
        ACAO_ID=f"{divida_id}:{tipo_acao}",
        DIVIDA_ID=divida_id,
        TIPO_ACAO=tipo_acao,
        descricao=motivo,
        gate_origem=1,
    )
"""
    sem_valor, total = _detectar_construcoes_sem_valor(
        codigo_sem_kwarg, "engine/caso_proposital.py"
    )

    assert total == 1, f"esperava encontrar exatamente 1 construção, obteve {total}"
    assert sem_valor, "esperava que o detector pegasse a construção proposital sem o kwarg"
    assert len(sem_valor) == 1, f"esperava exatamente 1 violação, obteve: {sem_valor!r}"
    assert sem_valor[0].arquivo == "engine/caso_proposital.py"
    assert sem_valor[0].linha == 3  # linha do `AcaoRequerida(` no trecho fabricado


def test_detector_nao_reporta_construcao_com_o_kwarg_presente() -> None:
    """Contraprova: uma construção de `AcaoRequerida(...)` COM o `keyword`
    `VALOR_ACAO_FINANCEIRA_IMEDIATA` — mesmo que `dinheiro(0)`, o caso mais
    comum em `engine/gates.py` — não é reportada como violação. Isola que o
    lint pega AUSÊNCIA do kwarg, não a chamada em si."""
    codigo_completo = """
def construir_acao_completa(divida_id, tipo_acao, motivo):
    return AcaoRequerida(
        ACAO_ID=f"{divida_id}:{tipo_acao}",
        DIVIDA_ID=divida_id,
        TIPO_ACAO=tipo_acao,
        descricao=motivo,
        gate_origem=1,
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
    )
"""
    sem_valor, total = _detectar_construcoes_sem_valor(codigo_completo, "engine/caso_correto.py")

    assert total == 1
    assert not sem_valor, f"não deveria reportar violação, obteve: {sem_valor!r}"


def test_passa_sobre_o_engine_real() -> None:
    """Confirma explicitamente que o `engine/` real de hoje satisfaz a
    propriedade — mesma verificação de
    `test_toda_construcao_de_acaorequerida_tem_valor_acao_financeira_imediata`,
    isolada num teste próprio para deixar rastreável no relatório de teste
    que a suíte passou sobre o pacote real, não só sobre trechos fabricados."""
    sem_valor: list[ConstrucaoSemValor] = []
    total_construcoes = 0

    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        sem_valor_arquivo, total_arquivo = _detectar_construcoes_sem_valor(
            codigo_fonte, str(arquivo)
        )
        sem_valor.extend(sem_valor_arquivo)
        total_construcoes += total_arquivo

    assert not sem_valor
    assert total_construcoes >= MINIMO_CONSTRUCOES_ESPERADAS
