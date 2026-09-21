"""Lint estático: `CLASSIFICACAO_MOBILIZACAO` só é DERIVADA em
`engine/classificacao_ativos.py` — AC-97, RF-60, US-21 · plano R4.9.5.

**Liberação registrada em 2026-09-09, fonte §14 da spec canônica
(`specs/motor-calculo.spec.md`, "Definições incorporadas — Rodada 4").**
`OQ-26`, que mantinha este arquivo em modo "zero ocorrências esperadas" desde
a Rodada 3, foi respondida pelo documento canônico transcrito na §14: as seis
regras de `classificar_investimento` (§14.3.1, `RF-53`) e os oito ramos de
`classificar_ativo_fisico` (§14.4-§14.9, `RF-54`-`RF-56`) publicam a regra de
derivação que antes não existia.

**Não é relaxamento — é prova do oposto (`RF-60`).** O teste original
(Rodada 3) reprovava QUALQUER função de `engine/` com `CLASSIFICACAO_
MOBILIZACAO` na anotação de retorno — a premissa era "o motor nunca deriva a
classificação". Essa premissa está estruturalmente invertida agora:
`classificar_investimento`/`classificar_ativo_fisico` PRECISAM ter essa
anotação para existir (`T-122`, `T-123`). Reescrever este arquivo para
simplesmente apagar o lint seria relaxamento disfarçado de atualização; em
vez disso, a heurística de detecção é PRESERVADA por completo — o que muda é
o veredito sobre o que ela deveria encontrar: antes, zero ocorrências em todo
`engine/`; agora, EXATAMENTE as duas ocorrências de
`engine/classificacao_ativos.py`, nomeadas e esperadas, e nenhuma outra em
nenhum outro arquivo do pacote. O portão contra "decidir metodologia
implementando" (`sdd.config.md` §6) continua de pé — só que agora ele aponta
para o único lugar em que a metodologia foi formalmente publicada.

Três provas, conforme R4.9.5 do plano
-----------------------------------------------------------------------------
1. **Documentação da liberação** — esta docstring, citando data, fonte e
   `AC-97` (acima), preservando a nota histórica da Rodada 3 (a seguir).
2. **Prova positiva por execução** — `test_derivacao_segue_RF_53_a_RF_56_na_
   ordem_certa` chama `classificar_investimento`/`classificar_ativo_fisico`
   sobre os cenários de `GAB-NFI-06` a `GAB-NFI-11` (mesmos de `T-126`/
   `T-127`) e confirma que a derivação segue exatamente a ordem normativa.
3. **Prova estrutural complementar** — `test_sem_derivacao_de_classificacao_
   mobilizacao_fora_do_modulo_autorizado` varre `engine/**/*.py` e confirma
   que a função de classificação SÓ existe em `engine/classificacao_
   ativos.py`: nenhum outro arquivo de `engine/` define uma função com
   anotação de retorno `CLASSIFICACAO_MOBILIZACAO` (ou `| None`).

Nota histórica original (Rodada 3, preservada)
-----------------------------------------------------------------------------
`piq-app-spec.md:2614` fixava que as classes de mobilização eram "derivadas
pelo motor, nunca perguntadas" — mas a REGRA de derivação não estava
publicada por nenhuma fonte (`OQ-26`, então aberta). Enquanto ela esteve
aberta, a Rodada 3 entregou apenas o DOMÍNIO (o enum de `engine/tipos.py`,
`T-93`) e recebeu a classificação JÁ FEITA, por item, como campo obrigatório
de `ItemInvestimento`/`ItemAtivo` (`EC-31`, revogado na Rodada 4 por `EC-32`
— ver `engine/estado.py`). Este teste foi o portão que impediu a metodologia
de ser decidida no código antes de ela existir formalmente.

Heurística de detecção e suas limitações (preservada da Rodada 3)
-----------------------------------------------------------------------------
Detecção por AST, mesma família de `tests/estatica/test_sem_float_no_motor.py`
e `test_uso_de_tolerancia.py`: percorre todo `FunctionDef`/`AsyncFunctionDef`
de `engine/**/*.py` e reporta aquele cuja **anotação de retorno** mencione
`CLASSIFICACAO_MOBILIZACAO` em qualquer posição da sub-árvore da anotação.
Isso cobre, por construção (`ast.walk` sobre o nó `returns`), as três formas:

1. **direta** — `-> CLASSIFICACAO_MOBILIZACAO`, e a forma qualificada
   `-> tipos.CLASSIFICACAO_MOBILIZACAO`;
2. **em `Optional`/união** — `-> CLASSIFICACAO_MOBILIZACAO | None`,
   `-> Optional[CLASSIFICACAO_MOBILIZACAO]`, `-> Union[..., ...]`;
3. **em coleção** — `-> tuple[CLASSIFICACAO_MOBILIZACAO, ...]`,
   `-> dict[str, CLASSIFICACAO_MOBILIZACAO]`, `-> list[...]`, e a anotação
   como STRING (`-> "CLASSIFICACAO_MOBILIZACAO"`, comum sob
   `from __future__ import annotations`), tratada por comparação textual.

A mensagem de falha nomeia arquivo, linha e função culpada.

**O que este lint NÃO pega, deliberadamente.** É uma varredura estrutural
sobre a anotação de retorno, não uma prova de tipo: uma função anotada
`-> object` (ou sem anotação nenhuma) que devolvesse um membro do enum
passaria despercebida. Duas razões para não tentar cobrir isso aqui: (a)
`mypy --strict` já proíbe função sem anotação de retorno em `engine/`
(comando `build`), então a anotação sempre existe; (b) alargar a heurística
para "qualquer `return CLASSIFICACAO_MOBILIZACAO.X`" produziria falso
positivo em código legítimo de LEITURA — por exemplo, um filtro que compara
`item.CLASSIFICACAO_MOBILIZACAO is CLASSIFICACAO_MOBILIZACAO.
MOBILIZACAO_RECOMENDAVEL` e devolve o item, que é exatamente o que a §13.3
manda o motor fazer. **Consumir a classificação é obrigatório; produzi-la
FORA de `engine/classificacao_ativos.py` é o que está proibido**, e a
anotação de retorno é a fronteira que separa os dois de forma inequívoca.

Também não são inspecionados os arquivos fora de `engine/` (`app/`,
`collection/`, `report/`): `AC-97` fala do código do MOTOR, que é onde a
derivação teria efeito sobre o valor recomendado ao usuário.

Evidência complementar de `RF-59` (verificação cruzada, não substitui este
teste): `mypy --strict` confirma que `ItemAtivo`/`ItemInvestimento`
(`engine/estado.py`) não aceitam mais `CLASSIFICACAO_MOBILIZACAO` como
parâmetro de construtor — a classificação chega DERIVADA pelas funções deste
módulo, nunca armazenada como campo bruto. Esse fato é o motivo estrutural
pelo qual `test_regra_1_vence_regra_4_quando_ambas_se_aplicam` e os demais
testes de `tests/regras/test_classificacao_ativos.py` (`T-127`) constroem
`ItemInvestimento`/`ItemAtivo` sem esse campo: `mypy` recusaria a chamada com
`unexpected keyword argument` se ele ainda existisse.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from engine.classificacao_ativos import classificar_ativo_fisico, classificar_investimento
from engine.estado import (
    DISPOSICAO_USO_INVESTIMENTO,
    ESSENCIALIDADE,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
    ItemInvestimento,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO
from tests.conftest import assertar_exato

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

NOME_PROIBIDO = "CLASSIFICACAO_MOBILIZACAO"

# Único módulo de `engine/` autorizado a definir função com essa anotação de
# retorno (RF-59, RF-60, AC-97) — `classificar_investimento` e
# `classificar_ativo_fisico`, T-122/T-123.
MODULO_AUTORIZADO = "classificacao_ativos.py"

# As duas funções que a §14 publica, e só elas, com a anotação esperada.
FUNCOES_AUTORIZADAS: frozenset[str] = frozenset(
    {"classificar_investimento", "classificar_ativo_fisico"}
)


@dataclass(frozen=True, slots=True)
class DerivacaoDeClassificacao:
    arquivo: str
    linha: int
    funcao: str
    anotacao: str


def _anotacao_menciona_classificacao(anotacao: ast.expr) -> bool:
    """`True` se a sub-árvore da anotação de retorno mencionar
    `CLASSIFICACAO_MOBILIZACAO` de qualquer forma — nome simples, atributo
    qualificado, dentro de `Optional`/união/coleção, ou como string adiada."""
    for no in ast.walk(anotacao):
        if isinstance(no, ast.Name) and no.id == NOME_PROIBIDO:
            return True
        if isinstance(no, ast.Attribute) and no.attr == NOME_PROIBIDO:
            return True
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            # Anotação adiada como string: `-> "CLASSIFICACAO_MOBILIZACAO"`,
            # `-> "tuple[CLASSIFICACAO_MOBILIZACAO, ...]"`.
            if NOME_PROIBIDO in no.value:
                return True
    return False


def _detectar_derivacoes(codigo_fonte: str, nome_arquivo: str) -> list[DerivacaoDeClassificacao]:
    """Percorre a AST de `codigo_fonte` e devolve toda função cuja anotação de
    retorno mencione `CLASSIFICACAO_MOBILIZACAO` — isto é, que PRODUZA a
    classificação em vez de apenas consumi-la. Heurística inalterada da
    Rodada 3 — o que muda é o veredito aplicado sobre o resultado."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    derivacoes: list[DerivacaoDeClassificacao] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if no.returns is None:
            continue
        if _anotacao_menciona_classificacao(no.returns):
            derivacoes.append(
                DerivacaoDeClassificacao(
                    arquivo=nome_arquivo,
                    linha=no.lineno,
                    funcao=no.name,
                    anotacao=ast.unparse(no.returns),
                )
            )

    return derivacoes


def test_sem_derivacao_de_classificacao_mobilizacao_fora_do_modulo_autorizado() -> None:
    """`AC-97` (`RF-59`, `RF-60`): nenhuma função de `engine/**/*.py`, FORA de
    `engine/classificacao_ativos.py`, tem `CLASSIFICACAO_MOBILIZACAO` (ou
    `| None` dessa anotação) como anotação de retorno. Dentro do módulo
    autorizado, só as duas funções publicadas pela §14 —
    `classificar_investimento` e `classificar_ativo_fisico` — podem ter essa
    anotação; qualquer terceira função ali, ou qualquer função em outro
    arquivo, é uma segunda via de derivação não autorizada pela spec."""
    derivacoes: list[DerivacaoDeClassificacao] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        derivacoes.extend(_detectar_derivacoes(codigo_fonte, str(arquivo)))

    fora_do_modulo = [d for d in derivacoes if not d.arquivo.endswith(MODULO_AUTORIZADO)]
    dentro_mas_nao_autorizada = [
        d
        for d in derivacoes
        if d.arquivo.endswith(MODULO_AUTORIZADO) and d.funcao not in FUNCOES_AUTORIZADAS
    ]
    nao_autorizadas = fora_do_modulo + dentro_mas_nao_autorizada

    mensagem = (
        "AC-97 violado — função de engine/ que DERIVA CLASSIFICACAO_MOBILIZACAO "
        "fora da autorização da §14 (só classificar_investimento/"
        "classificar_ativo_fisico, em engine/classificacao_ativos.py, podem "
        "ter essa anotação de retorno):\n"
    ) + "\n".join(
        f"  {d.arquivo}:{d.linha} — função `{d.funcao}` retorna `{d.anotacao}`"
        for d in nao_autorizadas
    )
    assert not nao_autorizadas, mensagem

    # Prova complementar, não vácua: as duas funções autorizadas EXISTEM e
    # foram de fato encontradas — sem isto, um detector quebrado que nunca
    # encontrasse nada passaria "por vácuo" na asserção acima.
    encontradas = {d.funcao for d in derivacoes if d.arquivo.endswith(MODULO_AUTORIZADO)}
    assert encontradas == FUNCOES_AUTORIZADAS, (
        "esperava encontrar exatamente as duas funções autorizadas em "
        f"engine/classificacao_ativos.py, obteve: {encontradas!r}"
    )


def test_derivacao_segue_RF_53_a_RF_56_na_ordem_certa() -> None:
    """Prova positiva por execução (prova 2 de R4.9.5): os cenários de
    `GAB-NFI-06` a `GAB-NFI-11` (§14.16, mesmos de `T-126`/`T-127`) confirmam
    que `classificar_investimento`/`classificar_ativo_fisico` derivam a
    classificação seguindo exatamente `RF-53`-`RF-56`, na ordem normativa —
    não é suficiente que a anotação exista; a REGRA por trás dela precisa
    bater com a spec."""
    # GAB-NFI-06 (AC-88): Regra 1 (bloqueio) — LIQUIDEZ_INVESTIMENTOS=BLOQUEADO
    # vence mesmo com DISPOSICAO_USO_INVESTIMENTO=SIM.
    investimento_bloqueado = ItemInvestimento(
        ITEM_ID="INV-GAB-NFI-06",
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(10000),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.BLOQUEADO,
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.SIM,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(10000),
        TEM_CUSTO_CONHECIDO=False,
        SEM_CUSTO_PERDA_RELEVANTE=True,
    )
    assertar_exato(
        classificar_investimento(investimento_bloqueado), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
    )

    # GAB-NFI-07 (AC-89): Regra 4 — líquido/disponível/sem custo relevante.
    investimento_recomendavel = ItemInvestimento(
        ITEM_ID="INV-GAB-NFI-07",
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(10000),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D1,
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.SIM,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(10000),
        TEM_CUSTO_CONHECIDO=False,
        SEM_CUSTO_PERDA_RELEVANTE=True,
    )
    assertar_exato(
        classificar_investimento(investimento_recomendavel),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
    )

    # GAB-NFI-08 (AC-90): Regra 3 — disposição TALVEZ, resgatável.
    investimento_possivel = ItemInvestimento(
        ITEM_ID="INV-GAB-NFI-08",
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(10000),
        POSSUI_LIQUIDEZ=True,
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D7,
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.TALVEZ,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(10000),
        TEM_CUSTO_CONHECIDO=False,
        SEM_CUSTO_PERDA_RELEVANTE=True,
    )
    assertar_exato(
        classificar_investimento(investimento_possivel),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
    )

    def _ativo(
        *,
        possibilidade_venda: POSSIBILIDADE_VENDA,
        essencialidade: ESSENCIALIDADE,
        renda_recorrente_ativo: int,
        custo_recorrente_ativo: int,
    ) -> ItemAtivo:
        return ItemAtivo(
            ITEM_ID="ATV-GAB-NFI",
            TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
            POSSIBILIDADE_VENDA=possibilidade_venda,
            ESSENCIALIDADE=essencialidade,
            VALOR_ESTIMADO_ATIVO=dinheiro(30000),
            POSSUI_PASSIVO_VINCULADO=False,
            SALDO_PASSIVO_VINCULADO=dinheiro(0),
            POSSUI_CUSTO_DESMOBILIZACAO=False,
            CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
            RENDA_RECORRENTE_ATIVO=dinheiro(renda_recorrente_ativo),
            CUSTO_RECORRENTE_ATIVO=dinheiro(custo_recorrente_ativo),
        )

    # GAB-NFI-09 (AC-91, EC-34): Ramo 4 — essencial NUNCA recomendável.
    ativo_essencial = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.ESSENCIAL,
        renda_recorrente_ativo=0,
        custo_recorrente_ativo=0,
    )
    assertar_exato(
        classificar_ativo_fisico(ativo_essencial),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
    )

    # GAB-NFI-10 (AC-92): Ramo 8c — não essencial, fluxo <= 0, recomendável.
    ativo_fluxo_negativo = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.NAO_ESSENCIAL,
        renda_recorrente_ativo=0,
        custo_recorrente_ativo=500,
    )
    assertar_exato(
        classificar_ativo_fisico(ativo_fluxo_negativo),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
    )

    # GAB-NFI-11 (AC-93): Ramo 8d — não essencial, fluxo > 0, possível.
    ativo_fluxo_positivo = _ativo(
        possibilidade_venda=POSSIBILIDADE_VENDA.SIM,
        essencialidade=ESSENCIALIDADE.NAO_ESSENCIAL,
        renda_recorrente_ativo=700,
        custo_recorrente_ativo=0,
    )
    assertar_exato(
        classificar_ativo_fisico(ativo_fluxo_positivo),
        CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
    )


def test_detector_pega_derivacao_proposital_fora_do_modulo_autorizado() -> None:
    """Prova negativa, mesmo padrão de
    `tests/estatica/test_tipo_acao_apenas_quatro_valores.py::
    test_verificador_pega_quinto_literal_proposital`: alimenta o PRÓPRIO
    detector usado acima com uma função de derivação construída como
    STRING — nunca escrita em `engine/` real, nunca executada, atribuída a
    um arquivo FORA de `engine/classificacao_ativos.py` — e confere que ela
    é pega como não autorizada, nomeando linha e função.

    Sem esta prova, `test_sem_derivacao_de_classificacao_mobilizacao_fora_do_
    modulo_autorizado` passaria igualmente bem se o detector estivesse
    quebrado: hoje ele varre um conjunto em que a resposta correta é "só as
    duas funções de classificacao_ativos.py", e verificação vácua não
    distingue "não há violação" de "não sei detectar violação". O trecho
    abaixo é exatamente o caso que `RF-59`/`RF-60` proíbem — uma SEGUNDA via
    de derivação da classe a partir de liquidez e custo de desmobilização,
    fora do módulo autorizado."""
    codigo_com_derivacao = """
def classificar_mobilizacao(*, liquidez, custo_desmobilizacao) -> CLASSIFICACAO_MOBILIZACAO:
    if liquidez and not custo_desmobilizacao:
        return CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
"""
    derivacoes = _detectar_derivacoes(codigo_com_derivacao, "engine/outro_modulo.py")

    assert derivacoes, "esperava que o detector pegasse a derivação proposital, obteve 0"
    assert len(derivacoes) == 1, f"esperava exatamente 1 derivação, obteve: {derivacoes!r}"
    assert derivacoes[0].funcao == "classificar_mobilizacao"
    assert derivacoes[0].linha == 2
    assert derivacoes[0].anotacao == "CLASSIFICACAO_MOBILIZACAO"
    # Confirma que o veredito de "não autorizada" se aplicaria: o arquivo não
    # termina em classificacao_ativos.py.
    assert not derivacoes[0].arquivo.endswith(MODULO_AUTORIZADO)


def test_detector_nao_reporta_as_duas_funcoes_autorizadas() -> None:
    """Contraprova: as duas funções publicadas pela §14, dentro do módulo
    autorizado, com anotação `CLASSIFICACAO_MOBILIZACAO`/`| None`, NÃO são
    reportadas como violação — é exatamente o resultado que `RF-59`/`RF-60`
    autorizam. Isola que o lint pega derivação NÃO AUTORIZADA, não a
    anotação em si."""
    codigo_legitimo = """
def classificar_investimento(item: ItemInvestimento) -> CLASSIFICACAO_MOBILIZACAO:
    return CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR


def classificar_ativo_fisico(item: ItemAtivo) -> CLASSIFICACAO_MOBILIZACAO | None:
    return None
"""
    derivacoes = _detectar_derivacoes(codigo_legitimo, str(RAIZ_ENGINE / MODULO_AUTORIZADO))

    assert {d.funcao for d in derivacoes} == FUNCOES_AUTORIZADAS
    for d in derivacoes:
        assert d.arquivo.endswith(MODULO_AUTORIZADO)


@pytest.mark.parametrize(
    ("descricao", "anotacao"),
    [
        ("direta", "CLASSIFICACAO_MOBILIZACAO"),
        ("qualificada por módulo", "tipos.CLASSIFICACAO_MOBILIZACAO"),
        ("união com None", "CLASSIFICACAO_MOBILIZACAO | None"),
        ("Optional", "Optional[CLASSIFICACAO_MOBILIZACAO]"),
        ("Union", "Union[CLASSIFICACAO_MOBILIZACAO, Desconhecido]"),
        ("tupla homogênea", "tuple[CLASSIFICACAO_MOBILIZACAO, ...]"),
        ("lista", "list[CLASSIFICACAO_MOBILIZACAO]"),
        ("dicionário como valor", "dict[str, CLASSIFICACAO_MOBILIZACAO]"),
        ("anotação adiada como string", '"CLASSIFICACAO_MOBILIZACAO"'),
        ("string com coleção", '"tuple[CLASSIFICACAO_MOBILIZACAO, ...]"'),
    ],
)
def test_detector_pega_cada_forma_de_anotacao_de_retorno(
    descricao: str, anotacao: str
) -> None:
    """`AC-97`, "direta, em `Optional`/união, ou em coleção": cada uma
    das formas de anotação de retorno pelas quais uma derivação poderia entrar
    é detectada. Prova item a item, não por amostra. Heurística inalterada da
    Rodada 3."""
    codigo = f"def derivar(item) -> {anotacao}:\n    return item\n"

    derivacoes = _detectar_derivacoes(codigo, "caso_proposital.py")

    assert derivacoes, f"o detector não pegou a forma {descricao!r}: `-> {anotacao}`"
    assert derivacoes[0].funcao == "derivar"
    assert derivacoes[0].linha == 1


def test_detector_pega_funcao_assincrona() -> None:
    """`AsyncFunctionDef` é varrido junto com `FunctionDef` — uma derivação não
    escapa por ser declarada `async def`. Heurística inalterada da Rodada 3."""
    codigo = """
async def derivar_async(item) -> CLASSIFICACAO_MOBILIZACAO:
    return item.CLASSIFICACAO_MOBILIZACAO
"""
    derivacoes = _detectar_derivacoes(codigo, "caso_proposital.py")

    assert derivacoes, "esperava detectar a derivação em `async def`"
    assert derivacoes[0].funcao == "derivar_async"


def test_detector_nao_reporta_consumo_da_classificacao() -> None:
    """Contraprova da fronteira: CONSUMIR a classificação é obrigatório pela
    §13.3 (`ATIVOS_RECOMENDADOS` = Σ dos ativos `MOBILIZACAO_RECOMENDAVEL`) e
    NÃO pode ser reportado. O trecho abaixo lê o campo, compara com um membro
    do enum e filtra — sem nunca produzir a classificação, o que a anotação de
    retorno atesta.

    Isola que o lint pega DERIVAÇÃO, não menção ao nome: um teste que
    reprovasse este trecho tornaria a §13.3 inimplementável. Heurística
    inalterada da Rodada 3."""
    codigo_legitimo = """
def calcular_ATIVOS_RECOMENDADOS(*, ativos) -> Dinheiro:
    return sum(
        (
            item.VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL
            for item in ativos
            if item.CLASSIFICACAO_MOBILIZACAO
            is CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        ),
        dinheiro(0),
    )
"""
    derivacoes = _detectar_derivacoes(codigo_legitimo, "caso_correto.py")

    assert not derivacoes, (
        "consumo da classificação (§13.3) não pode ser reportado como derivação, "
        f"obteve: {derivacoes!r}"
    )
