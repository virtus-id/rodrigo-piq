"""Lint estático: o ramo de veículo de `classificar_ativo_fisico` nunca
inventa renda nem produz classificação — RF-56, AC-100, EC-39, US-19 ·
plano R4.3, R4.9.

**`OQ-42` (discovery, Rodada 4, não spec) explicitamente REJEITADA — não
implementada.** A coleta não tem `RENDA_RECORRENTE_VEICULO`/equivalente
(`OQ-38`: `bloco-04.yaml` só publica `CUSTO_RECORRENTE_VEICULO`). Diante
dessa ausência estrutural, `RF-56` manda `classificar_ativo_fisico` retornar
o sentinela `None` — nunca um valor do domínio de `CLASSIFICACAO_
MOBILIZACAO`. `OQ-42` era a leitura alternativa de tratar essa mesma ausência
como se fosse `RENDA_RECORRENTE_ATIVO is DESCONHECIDO` (dado do domínio de
DADO, não sentinela estrutural) e cair no ramo "fluxo desconhecido →
`MOBILIZACAO_POSSIVEL`" de `§14.9` — produzindo uma classificação sobre um
valor de renda que ninguém informou. O usuário rejeitou essa leitura por
pedido explícito, e `T-123` implementa o sentinela `None`, nunca
`DESCONHECIDO`, para o ramo de veículo (`engine/classificacao_ativos.py`).

Este arquivo prova, por AST sobre o CÓDIGO-FONTE real — não apenas por
comportamento observado em uma chamada (isso é `T-127`,
`tests/regras/test_classificacao_ativos.py::
test_veiculo_nao_essencial_sem_renda_recorrente_retorna_none`) — que essa
garantia está estruturalmente presente e que a leitura de `OQ-42`, se
reintroduzida, é detectável. Mesmo espírito de prova negativa dos testes
estáticos já existentes (`test_sem_percentual_automatico_de_reserva.py`,
Rodada 3): detector por AST + teste-companheiro que alimenta o próprio
detector com o caso proposital + prova comportamental complementar.

Duas provas estruturais, uma comportamental
-----------------------------------------------------------------------------
1. **Retorno `None` antes de aritmética** — dentro do ramo `NAO_ESSENCIAL` +
   `POSSIBILIDADE_VENDA em {SIM, JA_PRETENDE}` (§14.8/§14.9) de
   `classificar_ativo_fisico`, o `if` que testa `TIPO_ATIVO_FISICO=VEICULO`
   E `RENDA_RECORRENTE_ATIVO is None` precisa aparecer, na AST, ANTES de
   qualquer `BinOp` de subtração envolvendo `RENDA_RECORRENTE_ATIVO`/
   `CUSTO_RECORRENTE_ATIVO`, e o corpo desse `if` precisa ser exatamente
   `return None` — sem cálculo intermediário.
2. **Nenhum literal numérico vira "renda" dentro do ramo de veículo** —
   varredura por `ast.Assign`/`ast.AnnAssign` cujo alvo mencione "RENDA"
   dentro do bloco condicionado a `TIPO_ATIVO_FISICO=VEICULO`: se alguém
   inventasse `RENDA_RECORRENTE_ATIVO = dinheiro(0)` (ou qualquer literal)
   para "resolver" a ausência de dado, este detector pega.
3. **Comportamental** (`test_cenario_AC_100_retorna_None_nunca_
   MOBILIZACAO_POSSIVEL`) — chama a função real sobre o cenário de `AC-100`
   e confirma `is None`.

Heurística de detecção e suas limitações
-----------------------------------------------------------------------------
Mesma família de `tests/estatica/test_sem_percentual_automatico_de_reserva.py`
e `test_sem_derivacao_de_classificacao_mobilizacao.py`: detecção por AST
sobre o código-fonte real de `engine/classificacao_ativos.py`, não por
`grep`. O escopo é um único arquivo (não `engine/**/*.py`) porque `RF-56` é
uma regra interna de `classificar_ativo_fisico` — não há outro lugar do
motor onde o ramo de veículo poderia existir sem violar
`test_sem_derivacao_de_classificacao_mobilizacao_fora_do_modulo_autorizado`
(`T-130`).

**Limitação documentada**, como os demais lints desta suíte: é varredura
estrutural sobre a função REAL do módulo (localizada por nome, não por
posição fixa de linha), não prova semântica por interpretação simbólica —
não rastreia aliases (`renda = item.RENDA_RECORRENTE_ATIVO` seguido de uso
indireto). O custo/benefício não se sustenta contra a camada que já cobre
isso: a prova comportamental (3) e `T-127` verificam o RESULTADO sobre o
cenário real, e nenhuma forma de contornar via alias escaparia de ambas ao
mesmo tempo.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from engine.classificacao_ativos import classificar_ativo_fisico
from engine.estado import (
    ESSENCIALIDADE,
    POSSIBILIDADE_VENDA,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
)
from engine.precisao import dinheiro

CAMINHO_MODULO = (
    Path(__file__).resolve().parent.parent.parent / "engine" / "classificacao_ativos.py"
)

NOME_FUNCAO = "classificar_ativo_fisico"
TIPO_VEICULO = "VEICULO"
RENDA_ATIVO = "RENDA_RECORRENTE_ATIVO"
CUSTO_ATIVO = "CUSTO_RECORRENTE_ATIVO"


@dataclass(frozen=True, slots=True)
class AchadoAST:
    linha: int
    descricao: str


def _localizar_funcao(arvore: ast.Module, nome: str) -> ast.FunctionDef:
    """Localiza `FunctionDef` de nome `nome` no nível do módulo — não depende
    de número de linha fixo, resiste a edição de código acima da função."""
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    raise AssertionError(f"função `{nome}` não encontrada na AST fornecida")


def _menciona_nome(no: ast.expr, nome: str) -> bool:
    """`True` se a sub-árvore de `no` referenciar `nome` como `Name` simples
    ou como atributo (`item.NOME`)."""
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name) and filho.id == nome:
            return True
        if isinstance(filho, ast.Attribute) and filho.attr == nome:
            return True
    return False


def _testa_veiculo_e_renda_none(teste: ast.expr) -> bool:
    """`True` se a expressão de teste de um `if` mencionar, simultaneamente,
    o literal `"VEICULO"` (comparação de `TIPO_ATIVO_FISICO`) e uma
    comparação `is None` sobre `RENDA_RECORRENTE_ATIVO` — a assinatura do
    guarda de bloqueio de veículo (RF-56)."""
    menciona_veiculo = any(
        isinstance(n, ast.Attribute) and n.attr == TIPO_VEICULO for n in ast.walk(teste)
    )
    menciona_renda_is_none = False
    for n in ast.walk(teste):
        if isinstance(n, ast.Compare) and any(isinstance(op, ast.Is) for op in n.ops):
            operandos = [n.left, *n.comparators]
            tem_none = any(isinstance(o, ast.Constant) and o.value is None for o in operandos)
            tem_renda = any(_menciona_nome(o, RENDA_ATIVO) for o in operandos)
            if tem_none and tem_renda:
                menciona_renda_is_none = True
    return menciona_veiculo and menciona_renda_is_none


def _coletar_binops_de_fluxo(no: ast.AST) -> list[ast.BinOp]:
    """Todo `BinOp` de subtração cuja sub-árvore mencione
    `RENDA_RECORRENTE_ATIVO` ou `CUSTO_RECORRENTE_ATIVO` — a aritmética de
    fluxo que `RF-56` proíbe de ocorrer sobre um veículo sem renda."""
    achados: list[ast.BinOp] = []
    for filho in ast.walk(no):
        if (
            isinstance(filho, ast.BinOp)
            and isinstance(filho.op, ast.Sub)
            and (
                _menciona_nome(filho.left, RENDA_ATIVO)
                or _menciona_nome(filho.left, CUSTO_ATIVO)
                or _menciona_nome(filho.right, RENDA_ATIVO)
                or _menciona_nome(filho.right, CUSTO_ATIVO)
            )
        ):
            achados.append(filho)
    return achados


def _guarda_de_veiculo_retorna_none_antes_de_aritmetica(
    funcao: ast.FunctionDef,
) -> list[AchadoAST]:
    """Prova estrutural 1: localiza o(s) `if` cuja condição testa
    simultaneamente `TIPO_ATIVO_FISICO=VEICULO` e `RENDA_RECORRENTE_ATIVO is
    None`; confirma que (a) o corpo é exatamente `return None`, sem
    aritmética; e que (b) nenhuma subtração envolvendo `RENDA_RECORRENTE_
    ATIVO`/`CUSTO_RECORRENTE_ATIVO` aparece ANTES dele, na ordem de
    aparição na árvore da função. Devolve a lista de problemas encontrados —
    vazia significa "estrutura correta"."""
    problemas: list[AchadoAST] = []

    guardas_de_veiculo: list[ast.If] = [
        n for n in ast.walk(funcao) if isinstance(n, ast.If) and _testa_veiculo_e_renda_none(n.test)
    ]

    if not guardas_de_veiculo:
        problemas.append(
            AchadoAST(
                linha=funcao.lineno,
                descricao=(
                    "nenhum `if` encontrado testando TIPO_ATIVO_FISICO=VEICULO "
                    "junto de RENDA_RECORRENTE_ATIVO is None — o guarda de "
                    "bloqueio de RF-56 não está presente"
                ),
            )
        )
        return problemas

    for guarda in guardas_de_veiculo:
        # (a) corpo do `if` é exatamente `return None`.
        corpo_e_return_none = (
            len(guarda.body) == 1
            and isinstance(guarda.body[0], ast.Return)
            and isinstance(guarda.body[0].value, ast.Constant)
            and guarda.body[0].value.value is None
        )
        if not corpo_e_return_none:
            problemas.append(
                AchadoAST(
                    linha=guarda.lineno,
                    descricao=(
                        "o corpo do guarda de veículo não é exatamente `return None` "
                        "— aritmética ou cálculo pode estar ocorrendo antes do bloqueio"
                    ),
                )
            )

        # (b) nenhuma subtração de fluxo antes do guarda, na ordem de
        # aparição por número de linha dentro da função.
        binops_de_fluxo = _coletar_binops_de_fluxo(funcao)
        anteriores = [b for b in binops_de_fluxo if b.lineno < guarda.lineno]
        if anteriores:
            for b in anteriores:
                problemas.append(
                    AchadoAST(
                        linha=b.lineno,
                        descricao=(
                            f"aritmética de fluxo (`{ast.unparse(b)}`) ocorre ANTES do "
                            "guarda de bloqueio de veículo — RF-56 exige o `is None` "
                            "checado antes de qualquer subtração"
                        ),
                    )
                )

    return problemas


def _literais_numericos_atribuidos_a_renda_no_ramo_veiculo(
    funcao: ast.FunctionDef,
) -> list[AchadoAST]:
    """Prova estrutural 2: varre todo `Assign`/`AnnAssign` cujo alvo
    mencione `RENDA` E cujo valor atribuído seja um literal numérico
    (`ast.Constant` com `int`/`float`) ou uma chamada a `dinheiro(<literal>)`
    — a assinatura de "inventar um valor de renda" para o veículo. Escopo:
    toda a função (o único ramo de veículo do módulo é este; se um segundo
    ramo de veículo fosse introduzido em outro ponto da função, também
    seria pego)."""
    achados: list[AchadoAST] = []

    def _e_literal_numerico_ou_dinheiro_literal(valor: ast.expr) -> bool:
        if isinstance(valor, ast.Constant) and isinstance(valor.value, (int, float)):
            return True
        if (
            isinstance(valor, ast.Call)
            and isinstance(valor.func, ast.Name)
            and valor.func.id == "dinheiro"
            and valor.args
            and isinstance(valor.args[0], ast.Constant)
            and isinstance(valor.args[0].value, (int, float))
        ):
            return True
        return False

    for no in ast.walk(funcao):
        alvos: list[ast.expr] = []
        valor: ast.expr | None = None
        linha_atribuicao = 0
        if isinstance(no, ast.Assign):
            alvos = no.targets
            valor = no.value
            linha_atribuicao = no.lineno
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvos = [no.target]
            valor = no.value
            linha_atribuicao = no.lineno

        if valor is None:
            continue

        for alvo in alvos:
            nome_alvo = (
                alvo.id
                if isinstance(alvo, ast.Name)
                else alvo.attr
                if isinstance(alvo, ast.Attribute)
                else None
            )
            eh_renda_literal = nome_alvo and "RENDA" in nome_alvo
            if eh_renda_literal and _e_literal_numerico_ou_dinheiro_literal(valor):
                achados.append(
                    AchadoAST(
                        linha=linha_atribuicao,
                        descricao=(
                            f"literal numérico atribuído a variável de renda `{nome_alvo}` "
                            f"(`{ast.unparse(valor)}`) — RF-56 proíbe inventar renda de veículo"
                        ),
                    )
                )

    return achados


def test_ramo_de_veiculo_retorna_none_antes_de_qualquer_aritmetica_de_fluxo() -> None:
    """RF-56, AC-100, EC-39: em `engine/classificacao_ativos.py::
    classificar_ativo_fisico`, o guarda que testa `TIPO_ATIVO_FISICO=VEICULO`
    E `RENDA_RECORRENTE_ATIVO is None` retorna `None` sem executar nenhuma
    subtração envolvendo `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO`
    antes dele — nomeando linha se encontrar violação."""
    codigo_fonte = CAMINHO_MODULO.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(CAMINHO_MODULO))
    funcao = _localizar_funcao(arvore, NOME_FUNCAO)

    problemas = _guarda_de_veiculo_retorna_none_antes_de_aritmetica(funcao)

    mensagem = (
        "RF-56 violado em engine/classificacao_ativos.py::classificar_ativo_fisico "
        "— o ramo de veículo não bloqueia antes de aritmética de fluxo:\n"
    ) + "\n".join(f"  {CAMINHO_MODULO}:{p.linha} — {p.descricao}" for p in problemas)
    assert not problemas, mensagem


def test_nenhum_literal_numerico_vira_renda_no_ramo_de_veiculo() -> None:
    """RF-56, AC-100: nenhuma atribuição dentro de `classificar_ativo_fisico`
    inventa um valor de renda (literal numérico ou `dinheiro(<literal>)`)
    para uma variável cujo nome mencione "RENDA" — nomeando arquivo e linha
    se encontrar."""
    codigo_fonte = CAMINHO_MODULO.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(CAMINHO_MODULO))
    funcao = _localizar_funcao(arvore, NOME_FUNCAO)

    achados = _literais_numericos_atribuidos_a_renda_no_ramo_veiculo(funcao)

    mensagem = (
        "RF-56 violado em engine/classificacao_ativos.py::classificar_ativo_fisico "
        "— literal numérico atribuído a variável de renda:\n"
    ) + "\n".join(f"  {CAMINHO_MODULO}:{a.linha} — {a.descricao}" for a in achados)
    assert not achados, mensagem


def test_detector_pega_versao_proposital_que_implementa_OQ_42() -> None:
    """Prova negativa, mesmo padrão de
    `test_sem_percentual_automatico_de_reserva.py::
    test_detector_pega_cada_uma_das_tres_formulas_proibidas`: alimenta o
    PRÓPRIO detector usado acima com uma versão PROPOSITAL de
    `classificar_ativo_fisico` — construída como STRING, nunca escrita em
    `engine/` real, nunca executada — que implementa exatamente a leitura de
    `OQ-42` rejeitada: trata `RENDA_RECORRENTE_ATIVO is None` (veículo) como
    se fosse `DESCONHECIDO` e cai no ramo "fluxo desconhecido →
    `MOBILIZACAO_POSSIVEL`", calculando `fluxo` antes de checar o bloqueio.

    Sem esta prova, os dois testes acima passariam igualmente bem com os
    detectores quebrados: hoje eles varrem um arquivo em que a resposta
    correta é "nenhuma violação", e verificação vácua não distingue "não há
    violação" de "não sei detectar violação". Este é o caso que `RF-56`
    proíbe e `OQ-42` propunha."""
    codigo_com_leitura_de_OQ_42 = '''
def classificar_ativo_fisico(item):
    if item.POSSIBILIDADE_VENDA == POSSIBILIDADE_VENDA.NAO:
        return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
    if item.ESSENCIALIDADE == ESSENCIALIDADE.NAO_ESSENCIAL:
        # Leitura de OQ-42 (rejeitada): trata ausência estrutural de veículo
        # como DESCONHECIDO em vez de sentinela None, calcula fluxo antes do
        # bloqueio explícito de RENDA_RECORRENTE_ATIVO is None.
        if item.RENDA_RECORRENTE_ATIVO is None or item.RENDA_RECORRENTE_ATIVO is DESCONHECIDO:
            return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
        fluxo_liquido_recorrente = item.RENDA_RECORRENTE_ATIVO - item.CUSTO_RECORRENTE_ATIVO
        if (
            item.TIPO_ATIVO_FISICO == TIPO_ATIVO_FISICO.VEICULO
            and item.RENDA_RECORRENTE_ATIVO is None
        ):
            return None
        if fluxo_liquido_recorrente <= dinheiro(0):
            return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS
'''
    arvore = ast.parse(codigo_com_leitura_de_OQ_42, filename="caso_proposital.py")
    funcao_proposital = _localizar_funcao(arvore, NOME_FUNCAO)

    problemas_guarda = _guarda_de_veiculo_retorna_none_antes_de_aritmetica(funcao_proposital)

    assert problemas_guarda, (
        "esperava que o detector pegasse a leitura de OQ-42 (fluxo calculado "
        "antes do guarda de veículo), obteve 0 problemas"
    )
    assert any("ANTES do" in p.descricao for p in problemas_guarda), (
        f"esperava um problema citando aritmética antes do guarda, obteve: {problemas_guarda!r}"
    )


def test_detector_pega_literal_de_renda_inventado_proposital() -> None:
    """Segunda prova negativa: alimenta o detector de literal numérico com
    uma versão PROPOSITAL, construída como string, que "resolve" a ausência
    de `RENDA_RECORRENTE_ATIVO` de veículo atribuindo um literal — outra
    forma pela qual `OQ-42`/uma leitura equivalente poderia inventar renda
    sem passar pelo guarda `is None`."""
    codigo_com_renda_inventada = """
def classificar_ativo_fisico(item):
    if item.TIPO_ATIVO_FISICO == TIPO_ATIVO_FISICO.VEICULO and item.RENDA_RECORRENTE_ATIVO is None:
        RENDA_RECORRENTE_ATIVO_ASSUMIDA = dinheiro(0)
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL
    return None
"""
    arvore = ast.parse(codigo_com_renda_inventada, filename="caso_proposital.py")
    funcao_proposital = _localizar_funcao(arvore, NOME_FUNCAO)

    achados = _literais_numericos_atribuidos_a_renda_no_ramo_veiculo(funcao_proposital)

    assert achados, "esperava que o detector pegasse o literal de renda inventado, obteve 0"
    assert any("RENDA_RECORRENTE_ATIVO_ASSUMIDA" in a.descricao for a in achados)


def test_cenario_AC_100_retorna_None_nunca_MOBILIZACAO_POSSIVEL() -> None:
    """Prova comportamental complementar (não substitui as provas
    estruturais acima): chama `classificar_ativo_fisico` REAL sobre o
    cenário de `AC-100` — veículo, `NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=
    SIM`, `RENDA_RECORRENTE_ATIVO=None` — e confirma que o retorno é `None`,
    nunca `MOBILIZACAO_POSSIVEL` (o resultado que a leitura de `OQ-42`
    produziria) nem qualquer outro valor do domínio de `CLASSIFICACAO_
    MOBILIZACAO`."""
    item = ItemAtivo(
        ITEM_ID="ATV-AC-100",
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.VEICULO,
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
        ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
        VALOR_ESTIMADO_ATIVO=dinheiro(30000),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=None,
        CUSTO_RECORRENTE_ATIVO=dinheiro(0),
    )

    obtido = classificar_ativo_fisico(item)

    assert obtido is None, f"esperava None (RF-56, AC-100), obteve: {obtido!r}"
