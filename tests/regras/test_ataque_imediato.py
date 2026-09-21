"""Regras e edge cases da §13 — `T-112`, plano R3.9.3.

RF-44, RF-45, RF-46, RF-47, RF-48, RF-50, RF-52 · §13.1 a §13.8 ·
`AC-77` a `AC-83` · `EC-23` a `EC-31` · `US-16`, `US-17`.

Os 15 unitários de regra do plano R3.9.3, um por âncora, testando
**comportamento observável** das nove funções puras de
`engine/ataque_imediato.py` — nunca implementação interna. Este é o arquivo
que fecha a §13 por ÂNCORA: cada teste abaixo tem o nome que o plano lhe deu
e cita no docstring o `AC-NN` ou `EC-NN` que verifica.

**Relação com os quatro arquivos de regra de `T-102`..`T-107`.** As mesmas
âncoras já são exercitadas, por outros ângulos, em
`test_reserva_mobilizavel.py`, `test_ataque_imediato_potencial.py`,
`test_componentes_recomendados.py` e `test_reserva_recomendada.py`. Aqui os
cenários são deliberadamente DIFERENTES daqueles — mesma regra, outra
configuração de entrada — para que este arquivo acrescente cobertura em vez
de repeti-la, e para que uma implementação que passe por acidente lá tenha de
passar de novo aqui. Dois testes só existem neste arquivo e em lugar nenhum
mais: `test_item_compoe_no_maximo_um_componente` (`AC-83`/`RF-52`, origem
econômica única por `ITEM_ID`) e a verificação encadeada de `EC-27` sobre
potencial **e** recomendado ao mesmo tempo.

**Tolerância.** `assertar_exato` em toda asserção monetária — a régua da §13
é tolerância zero (spec §5, `OQ-34` respondida). `assertar_monetario` não
aparece neste arquivo, e o lint `tests/estatica/test_uso_de_tolerancia.py`
recusaria seu uso sobre `RESERVA_MOBILIZAVEL`, `NECESSIDADE_RESIDUAL` e
`ATAQUE_IMEDIATO_RECOMENDADO` (`T-109`).

Os gabaritos `GAB-AI` formais (`@pytest.mark.gabarito_ataque_imediato`) vivem
em `tests/gabaritos_ataque_imediato/` (`T-110`/`T-111`) e não estão aqui.
"""

from typing import Any

import pytest

from engine.ataque_imediato import (
    calcular_ATAQUE_IMEDIATO_POTENCIAL,
    calcular_ATAQUE_IMEDIATO_RECOMENDADO,
    calcular_ATIVOS_RECOMENDADOS,
    calcular_CAIXA_RECOMENDADO,
    calcular_EXTRAORDINARIOS_RECOMENDADOS,
    calcular_INVESTIMENTOS_RECOMENDADOS,
    calcular_NECESSIDADE_RESIDUAL,
    derivar_RESERVA_MOBILIZAVEL,
    derivar_RESERVA_RECOMENDADA,
    verificar_hierarquia_ataque_imediato,
)
from engine.ciclo_mensal import ErroInvariante
from engine.classificacao_ativos import classificar_ativo_fisico, classificar_investimento
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    ESSENCIALIDADE,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    RESERVA_EXISTE,
    TIPO_ATIVO_FISICO,
    ItemAtivo,
    ItemInvestimento,
    RecursoExtraordinario,
)
from engine.precisao import dinheiro
from engine.tipos import CLASSIFICACAO_MOBILIZACAO, DESCONHECIDO, Dinheiro
from tests.conftest import assertar_exato

# Resultado mensal superavitário: mantém a TRAVA MODO_ESTABILIZACAO da §13.4
# (`< 0`) desarmada, para que o que estes testes observam seja a regra sob
# exame e não o déficit.
SUPERAVIT: Dinheiro = dinheiro(2000)


def _ativo(item_id: str, valor: int, classe: CLASSIFICACAO_MOBILIZACAO) -> ItemAtivo:
    """RF-54, RF-59, T-125 — mesma fixture canônica de
    `tests/regras/test_componentes_recomendados.py::_ativo`: `classe` escolhe
    os campos BRUTOS de §14.4-§14.9 que fazem `classificar_ativo_fisico`
    DERIVAR exatamente `classe` (assume `valor > 0`, único caso deste
    arquivo)."""
    if classe == CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR:
        possibilidade_venda = POSSIBILIDADE_VENDA.NAO
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS:
        possibilidade_venda = POSSIBILIDADE_VENDA.SIM
        essencialidade = ESSENCIALIDADE.ESSENCIAL
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL:
        possibilidade_venda = POSSIBILIDADE_VENDA.TALVEZ
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL
    else:
        assert classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        possibilidade_venda = POSSIBILIDADE_VENDA.SIM
        essencialidade = ESSENCIALIDADE.NAO_ESSENCIAL

    return ItemAtivo(
        ITEM_ID=item_id,
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
        POSSIBILIDADE_VENDA=possibilidade_venda,
        ESSENCIALIDADE=essencialidade,
        VALOR_ESTIMADO_ATIVO=dinheiro(valor),
        POSSUI_PASSIVO_VINCULADO=False,
        SALDO_PASSIVO_VINCULADO=dinheiro(0),
        POSSUI_CUSTO_DESMOBILIZACAO=False,
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
        RENDA_RECORRENTE_ATIVO=dinheiro(0),
        CUSTO_RECORRENTE_ATIVO=dinheiro(0),
    )


def _investimento(
    item_id: str, valor: int, *, liquidez: bool, classe: CLASSIFICACAO_MOBILIZACAO
) -> ItemInvestimento:
    """RF-53, RF-59, T-125 — mesma fixture canônica de
    `tests/regras/test_componentes_recomendados.py::_investimento`: `classe`
    escolhe os campos BRUTOS de §14.3.1 que fazem `classificar_investimento`
    DERIVAR exatamente `classe` (assume `valor > 0`, único caso deste
    arquivo)."""
    if classe == CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.NAO
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D0
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.TALVEZ
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D1
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True
    elif classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS:
        disposicao = DISPOSICAO_USO_INVESTIMENTO.SIM
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.MAIS_30
        tem_custo_conhecido = False
        sem_custo_perda_relevante = False
    else:
        assert classe == CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        disposicao = DISPOSICAO_USO_INVESTIMENTO.SIM
        liquidez_investimentos = LIQUIDEZ_INVESTIMENTOS.D0
        tem_custo_conhecido = False
        sem_custo_perda_relevante = True

    return ItemInvestimento(
        ITEM_ID=item_id,
        VALOR_LIQUIDO_REALIZAVEL=dinheiro(valor),
        POSSUI_LIQUIDEZ=liquidez,
        LIQUIDEZ_INVESTIMENTOS=liquidez_investimentos,
        DISPOSICAO_USO_INVESTIMENTO=disposicao,
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(valor),
        TEM_CUSTO_CONHECIDO=tem_custo_conhecido,
        SEM_CUSTO_PERDA_RELEVANTE=sem_custo_perda_relevante,
    )


def _recurso(
    item_id: str,
    valor: int,
    *,
    janela: JANELA_RECURSO_EXTRAORDINARIO,
    certeza: CERTEZA_RECURSO_EXTRAORDINARIO,
) -> RecursoExtraordinario:
    return RecursoExtraordinario(
        ITEM_ID=item_id,
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(valor),
        JANELA_RECURSO_EXTRAORDINARIO=janela,
        CERTEZA_RECURSO_EXTRAORDINARIO=certeza,
    )


# ===========================================================================
# AC-77 a AC-83 — as sete âncoras de comportamento
# ===========================================================================
@pytest.mark.regra
def test_potencial_soma_apenas_possivel_e_recomendavel() -> None:
    """`AC-77` · §13.2: com as quatro classificações presentes, o potencial
    soma `DINHEIRO_DISPONIVEL`, `RESERVA_MOBILIZAVEL`, os investimentos
    líquidos mobilizáveis, os recursos extraordinários potenciais e os ativos
    `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL` — "e nenhum item
    `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra na soma".

    Cenário com as quatro classes em AMBAS as coleções por item (investimentos
    e ativos), o que o arquivo de `T-103` não faz: lá as ressalvas aparecem
    uma coleção por vez. Cada parcela legítima é uma potência de dois
    (100 + 200 + 400 + 800 + 1.600 + 3.200 = 6.300); os quatro excluídos
    valem 10.000, 20.000, 40.000 e 80.000, então qualquer um que entrasse
    seria identificável pelo total.
    """
    obtido = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(100),
        RESERVA_MOBILIZAVEL=dinheiro(200),
        investimentos=(
            _investimento(
                "I_POSSIVEL",
                400,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
            ),
            _investimento(
                "I_RECOMENDAVEL",
                800,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            ),
            _investimento(
                "I_RESSALVAS",
                10000,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS,
            ),
            _investimento(
                "I_NAO_MOBILIZAR",
                20000,
                liquidez=True,
                classe=CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
            ),
        ),
        recursos_extraordinarios=(
            _recurso(
                "R_POTENCIAL",
                1600,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
        ),
        ativos=(
            _ativo("A_POSSIVEL", 3200, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL),
            _ativo("A_RESSALVAS", 40000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS),
            _ativo("A_NAO_MOBILIZAR", 80000, CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR),
        ),
    )

    assertar_exato(obtido, dinheiro(6300))


@pytest.mark.regra
def test_ativo_possivel_fica_so_no_potencial() -> None:
    """`AC-78` literal: "dado um ativo classificado `MOBILIZACAO_POSSIVEL` e
    outro `MOBILIZACAO_RECOMENDAVEL`, apenas o `MOBILIZACAO_RECOMENDAVEL`
    compõe a soma [de `ATIVOS_RECOMENDADOS`] — e o `MOBILIZACAO_POSSIVEL`
    permanece contando apenas em `ATAQUE_IMEDIATO_POTENCIAL`".

    Os DOIS lados da frase no mesmo teste, sobre os MESMOS dois ativos: o
    recomendado vê só 300; o potencial vê os 800. A diferença de 500 entre as
    duas somas é exatamente o ativo possível — é essa diferença que a §13.6
    chama de hierarquia, e testá-la em dois arquivos separados (como fazem
    `T-103` e `T-104`) não prova que ela vale para o mesmo conjunto.
    """
    ativos = (
        _ativo("A_POSSIVEL", 500, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL),
        _ativo("A_RECOMENDAVEL", 300, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
    )

    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=ativos)
    ATAQUE_IMEDIATO_POTENCIAL = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=ativos,
    )

    assertar_exato(ATIVOS_RECOMENDADOS, dinheiro(300))
    assertar_exato(ATAQUE_IMEDIATO_POTENCIAL, dinheiro(800))
    assertar_exato(ATAQUE_IMEDIATO_POTENCIAL - ATIVOS_RECOMENDADOS, dinheiro(500))


@pytest.mark.regra
def test_extraordinario_futuro_nao_compoe_recomendado() -> None:
    """`AC-79` · §13.3: "dado um recurso extraordinário previsto para o futuro
    e não confirmado, ... ele não compõe [`EXTRAORDINARIOS_RECOMENDADOS`],
    ainda que componha `RECURSOS_EXTRAORDINARIOS_POTENCIAIS`".

    O "ainda que" é a parte que só se prova comparando as duas somas sobre a
    MESMA coleção: o recurso futuro e não confirmado de 5.000 está no
    potencial e ausente do recomendado; o `CONFIRMADO`/`ATE_30D` de 1.000 está
    nos dois. Potencial 6.000 × recomendado 1.000.
    """
    recursos = (
        _recurso(
            "R_AGORA_CONFIRMADO",
            1000,
            janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
            certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
        ),
        _recurso(
            "R_FUTURO_POSSIVEL",
            5000,
            janela=JANELA_RECURSO_EXTRAORDINARIO.QUATRO_A_SEIS_MESES,
            certeza=CERTEZA_RECURSO_EXTRAORDINARIO.POSSIVEL,
        ),
    )

    EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=recursos
    )
    ATAQUE_IMEDIATO_POTENCIAL = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=recursos,
        ativos=(),
    )

    assertar_exato(EXTRAORDINARIOS_RECOMENDADOS, dinheiro(1000))
    assertar_exato(ATAQUE_IMEDIATO_POTENCIAL, dinheiro(6000))


@pytest.mark.regra
def test_elegivel_entra_por_argumento_explicito() -> None:
    """`AC-80` · `RF-48` · §13.5: "o resultado é o menor dos dois, e a chamada
    recebe `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` como argumento explícito
    — a função não a busca em `EstadoFinanceiro` nem em `Diagnostico`".

    Três provas, na ordem em que `AC-80` as enuncia:

    1. Com os cinco componentes somando 30.000 contra elegível de 12.000, o
       resultado é o MENOR dos dois.
    2. A chamada posicional é recusada (`TypeError`): não existe forma de
       passar o elegível senão nomeando-o. Com seis parâmetros `Dinheiro` do
       mesmo tipo, é o que impede a troca silenciosa.
    3. As duas funções que recebem o elegível não têm canal implícito para
       ele — nenhum nome de `EstadoFinanceiro` ou `Diagnostico` aparece na
       assinatura, verificado por introspecção dos parâmetros, e o módulo
       não importa `EstadoFinanceiro` nem `Diagnostico`.
    """
    import inspect

    import engine.ataque_imediato as modulo

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(12000),
        CAIXA_RECOMENDADO=dinheiro(6000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(6000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(6000),
        ATIVOS_RECOMENDADOS=dinheiro(6000),
        RESERVA_RECOMENDADA=dinheiro(6000),
    )
    assertar_exato(obtido, dinheiro(12000))

    with pytest.raises(TypeError):
        calcular_ATAQUE_IMEDIATO_RECOMENDADO(  # type: ignore[call-arg]
            dinheiro(12000),
            dinheiro(6000),
            dinheiro(6000),
            dinheiro(6000),
            dinheiro(6000),
            dinheiro(6000),
        )

    for funcao in (calcular_ATAQUE_IMEDIATO_RECOMENDADO, calcular_NECESSIDADE_RESIDUAL):
        parametros = inspect.signature(funcao).parameters
        assert "NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL" in parametros
        assert all(
            p.kind is inspect.Parameter.KEYWORD_ONLY for p in parametros.values()
        ), f"{funcao.__name__} admite argumento posicional (AC-80)"
        assert not {"estado", "diagnostico", "EstadoFinanceiro", "Diagnostico"} & set(parametros)

    assert not hasattr(modulo, "EstadoFinanceiro")
    assert not hasattr(modulo, "Diagnostico")


@pytest.mark.regra
def test_hierarquia_potencial_maior_ou_igual_recomendado() -> None:
    """`AC-82` · `RF-50` · §13.6: `ATAQUE_IMEDIATO_POTENCIAL >=
    ATAQUE_IMEDIATO_RECOMENDADO >= 0`, com tolerância ZERO.

    A violação levanta `ErroInvariante` (`A-04`) — nunca corrige, nunca
    rebaixa valor. E a comparação é exata: um centavo de excesso já viola.
    Os dois lados saem da mesma rodada de cálculo sobre os mesmos itens, então
    divergência é erro de filtro (item que entrou na §13.3 sem estar na
    §13.2), não ruído de arredondamento — e `± R$ 0,05` de folga esconderia
    exatamente o bug que a função existe para pegar.
    """
    # Igualdade passa (o normal quando tudo que é potencial é recomendável).
    verificar_hierarquia_ataque_imediato(
        ATAQUE_IMEDIATO_POTENCIAL=dinheiro("4200.37"),
        ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("4200.37"),
    )

    # Um centavo de excesso já levanta — a prova da tolerância ZERO.
    with pytest.raises(ErroInvariante) as capturado:
        verificar_hierarquia_ataque_imediato(
            ATAQUE_IMEDIATO_POTENCIAL=dinheiro("4200.37"),
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("4200.38"),
        )
    mensagem = str(capturado.value)
    assert "ATAQUE_IMEDIATO_POTENCIAL" in mensagem
    assert "ATAQUE_IMEDIATO_RECOMENDADO" in mensagem
    assert "4200.37" in mensagem and "4200.38" in mensagem

    # O segundo ramo verificável da §13.6: `RECOMENDADO >= 0`.
    with pytest.raises(ErroInvariante):
        verificar_hierarquia_ataque_imediato(
            ATAQUE_IMEDIATO_POTENCIAL=dinheiro(100),
            ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("-0.01"),
        )


@pytest.mark.regra
def test_item_compoe_no_maximo_um_componente() -> None:
    """`AC-83` · `RF-52` · §13.8 (TRAVA de dupla contagem): "cada recurso deve
    possuir **origem econômica única** no cálculo" — nenhum item aparece
    simultaneamente em `INVESTIMENTOS_RECOMENDADOS` e `ATIVOS_RECOMENDADOS`,
    nem em `ATIVOS_RECOMENDADOS` e `CAIXA_RECOMENDADO`.

    A prova usa `ITEM_ID` (`RF-38`): sem identidade estável por item, esta
    asserção é **inexprimível** — só se poderia comparar totais, e dois totais
    iguais não distinguem "o mesmo item contado duas vezes" de "dois itens de
    mesmo valor". Aqui os `ITEM_ID` que compõem cada componente são
    reconstruídos pelo MESMO filtro normativo da §13.3 e comparados como
    conjuntos:

      - investimentos e ativos são coleções de tipos DISTINTOS
        (`ItemInvestimento`/`ItemAtivo`), então um item não pode estar nas
        duas — a modelagem é a trava, e o teste a confirma sobre um caso com
        `ITEM_ID` deliberadamente colidente entre as duas coleções, que é o
        pior caso possível: mesmo assim cada componente conta o seu, uma vez
        só, e a soma dos dois componentes é a soma dos dois valores, nunca o
        dobro de um;
      - `CAIXA_RECOMENDADO` é escalar (`DINHEIRO_DISPONIVEL`), sem `ITEM_ID`
        nenhum: nenhum item de coleção o compõe, o que fecha o par
        `ATIVOS_RECOMENDADOS` × `CAIXA_RECOMENDADO` do enunciado.

    O caso vedado que a §13.8 nomeia — "reserva aplicada em CDB contada como
    `RESERVA_MOBILIZAVEL` e novamente como `INVESTIMENTOS_RECOMENDADOS`" —
    aparece no fim: a reserva também é escalar, e não tem `ITEM_ID` por onde
    reentrar na soma dos investimentos.
    """
    # `ITEM_ID` colidente de propósito ("X1" nas duas coleções): é o caso que
    # uma implementação com coleção única e sem tipo distinto confundiria.
    investimentos = (
        _investimento(
            "X1", 1000, liquidez=True, classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
        ),
    )
    ativos = (_ativo("X1", 2000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),)

    INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=investimentos)
    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=ativos)
    CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=dinheiro(500))

    # Cada componente conta o seu item UMA vez, pelo seu próprio valor.
    assertar_exato(INVESTIMENTOS_RECOMENDADOS, dinheiro(1000))
    assertar_exato(ATIVOS_RECOMENDADOS, dinheiro(2000))
    assertar_exato(INVESTIMENTOS_RECOMENDADOS + ATIVOS_RECOMENDADOS, dinheiro(3000))

    # Origem econômica única, expressa por `ITEM_ID`: os conjuntos de itens que
    # compõem cada componente são disjuntos POR TIPO — nenhum objeto pertence
    # às duas coleções, ainda que o texto do `ITEM_ID` coincida.
    itens_de_investimento = {
        item.ITEM_ID
        for item in investimentos
        if item.POSSUI_LIQUIDEZ
        and classificar_investimento(item) is CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    }
    itens_de_ativo = {
        item.ITEM_ID
        for item in ativos
        if classificar_ativo_fisico(item) is CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
    }
    assert itens_de_investimento == {"X1"}
    assert itens_de_ativo == {"X1"}
    assert not {type(item) for item in investimentos} & {type(item) for item in ativos}, (
        "investimento e ativo precisam ser tipos distintos para que a origem "
        "econômica única da §13.8 seja garantida pela modelagem (RF-52)"
    )

    # `CAIXA_RECOMENDADO` e `RESERVA_MOBILIZAVEL` são escalares: não têm
    # `ITEM_ID`, logo nenhum item de coleção pode compô-los duas vezes.
    assert not hasattr(CAIXA_RECOMENDADO, "ITEM_ID")
    RESERVA_MOBILIZAVEL = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=dinheiro(9000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(4000),
    )
    assert not hasattr(RESERVA_MOBILIZAVEL, "ITEM_ID")
    # A reserva entra no potencial como parcela própria, não pelos itens: o
    # total é caixa 500 + reserva 4.000 + investimento 1.000 + ativo 2.000.
    assertar_exato(
        calcular_ATAQUE_IMEDIATO_POTENCIAL(
            DINHEIRO_DISPONIVEL=CAIXA_RECOMENDADO,
            RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
            investimentos=investimentos,
            recursos_extraordinarios=(),
            ativos=ativos,
        ),
        dinheiro(7500),
    )


# ===========================================================================
# EC-23 a EC-31 — os nove edge cases
# ===========================================================================
@pytest.mark.regra
def test_reserva_existe_nao_vence_valor_informado() -> None:
    """`EC-23`: `RESERVA_EXISTE = NAO` com `VALOR_MAXIMO_RESERVA_INFORMADO_
    USUARIO` preenchido (entrada inconsistente) → `RESERVA_MOBILIZAVEL = 0`.
    "A Regra 1 da §13.1 é avaliada **antes** da Regra 2 e vence; o valor
    informado é ignorado, não somado."

    Aqui o informado (`7.000`) é MENOR que o total (`12.000`), de propósito:
    fosse a Regra 2 avaliada antes, o `MIN` devolveria 7.000 — um número
    plausível, que passaria despercebido. E a consequência é seguida até o
    fim: com a reserva zerada, a reserva recomendada também é `0`, e o
    recomendado fica só com os não protetivos.
    """
    RESERVA_MOBILIZAVEL = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=dinheiro(12000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(7000),
    )
    assertar_exato(RESERVA_MOBILIZAVEL, dinheiro(0))

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL=dinheiro(7000),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )

    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))


@pytest.mark.regra
@pytest.mark.parametrize(
    ("RESERVA_TOTAL", "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO", "esperado"),
    [
        (dinheiro(1000), dinheiro(-1000), dinheiro(0)),
        (dinheiro(1000), dinheiro("-0.01"), dinheiro(0)),
        (dinheiro(0), dinheiro(-5000), dinheiro(0)),
        (dinheiro(1000), dinheiro(0), dinheiro(0)),
        (dinheiro(1000), dinheiro("0.01"), dinheiro("0.01")),
    ],
)
def test_valor_maximo_negativo_zera_antes_do_min(
    RESERVA_TOTAL: Dinheiro,
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: Dinheiro,
    esperado: Dinheiro,
) -> None:
    """`EC-24`: "o `MAX(0, ...)` da Regra 2 zera a parcela antes do `MIN`;
    `RESERVA_MOBILIZAVEL` nunca é negativa".

    A varredura cerca a fronteira nos dois sentidos: negativo simétrico ao
    total, um centavo negativo, total zero com informado negativo, e as duas
    bordas do zero (`0` e `+0,01`) — que provam que o `MAX` corta apenas o
    lado negativo e não empurra o valor legítimo para cima.
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        RESERVA_TOTAL=RESERVA_TOTAL,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO,
    )

    assertar_exato(obtido, esperado)


@pytest.mark.regra
def test_reserva_total_desconhecida_vence_regra_2() -> None:
    """`EC-25`: `RESERVA_TOTAL` desconhecida, com valor máximo informado
    conhecido → `RESERVA_MOBILIZAVEL` desconhecida (Regra 3), "não o valor
    informado — a Regra 3 tem precedência sobre a Regra 2 quando o total é
    desconhecido".

    Sem saber o teto, o `MIN` não é calculável: devolver o informado seria
    afirmar que ele cabe no total, o que ninguém sabe. A asserção é de
    IDENTIDADE do sentinela, e a contraprova fecha o cerco — os MESMOS
    argumentos com o total conhecido devolvem o informado.
    """
    obtido = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=DESCONHECIDO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(3500),
    )

    assert obtido is DESCONHECIDO, f"EC-25 exige o sentinela, obtido={obtido!r}"
    assert obtido != dinheiro(3500), "o informado não vaza quando o total é desconhecido"

    contraprova = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.GRANDE_PARTE,
        RESERVA_TOTAL=dinheiro(9000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(3500),
    )
    assertar_exato(contraprova, dinheiro(3500))


@pytest.mark.regra
def test_mobilizavel_desconhecida_com_residual_positivo() -> None:
    """`EC-26`: `RESERVA_MOBILIZAVEL` desconhecida e `NECESSIDADE_RESIDUAL >
    0` → `RESERVA_RECOMENDADA = 0` "até existir decisão válida, e a pendência
    é registrada — nunca convertida silenciosamente em zero como informação".

    As duas metades, ambas observáveis:

    1. A ARITMÉTICA recebe `0` — a reserva não entra no recomendado, que fica
       com os 6.000 dos não protetivos (§13.1, `AC-73`).
    2. A INFORMAÇÃO não é convertida: o `DESCONHECIDO` derivado na §13.1
       continua sendo o sentinela, distinto de `dinheiro(0)`, e é ele que
       `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`) carrega
       para o relatório. O `0` vive só na saída de
       `derivar_RESERVA_RECOMENDADA`, que é onde a §13.9 o coloca.
    """
    RESERVA_MOBILIZAVEL = derivar_RESERVA_MOBILIZAVEL(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        RESERVA_TOTAL=dinheiro(15000),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )
    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(6000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(0),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
    )
    assertar_exato(NECESSIDADE_RESIDUAL, dinheiro(14000))

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(20000),
        CAIXA_RECOMENDADO=dinheiro(6000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(0),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(0),
        ATIVOS_RECOMENDADOS=dinheiro(0),
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )
    assertar_exato(obtido, dinheiro(6000))

    # A pendência permanece: o desconhecido derivado NÃO virou zero.
    assert RESERVA_MOBILIZAVEL is DESCONHECIDO
    assert RESERVA_MOBILIZAVEL != dinheiro(0)


@pytest.mark.regra
def test_colecoes_vazias_resultam_zero() -> None:
    """`EC-27`: "coleções de investimentos, ativos e recursos extraordinários
    todas vazias e `DINHEIRO_DISPONIVEL = 0` → `ATAQUE_IMEDIATO_POTENCIAL` e
    `ATAQUE_IMEDIATO_RECOMENDADO` valem `0`; nenhum erro, nenhum estado
    desconhecido fabricado".

    O enunciado fala das DUAS variáveis, então as duas são calculadas no mesmo
    cenário vazio, e a hierarquia da §13.6 é verificada sobre o par — que é o
    caso-limite `0 >= 0 >= 0`. A reserva entra desconhecida de propósito: o
    estado vazio somado à decisão adiada é o pior caso para "fabricar um
    desconhecido de saída", e nem assim ele aparece.
    """
    ATAQUE_IMEDIATO_POTENCIAL = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=(),
    )
    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=DESCONHECIDO,
        NECESSIDADE_RESIDUAL=dinheiro(0),
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    ATAQUE_IMEDIATO_RECOMENDADO = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(0),
        CAIXA_RECOMENDADO=calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=dinheiro(0)),
        INVESTIMENTOS_RECOMENDADOS=calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=()),
        EXTRAORDINARIOS_RECOMENDADOS=calcular_EXTRAORDINARIOS_RECOMENDADOS(
            recursos_extraordinarios=()
        ),
        ATIVOS_RECOMENDADOS=calcular_ATIVOS_RECOMENDADOS(ativos=()),
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )

    assertar_exato(ATAQUE_IMEDIATO_POTENCIAL, dinheiro(0))
    assertar_exato(ATAQUE_IMEDIATO_RECOMENDADO, dinheiro(0))

    # `0 >= 0 >= 0` — a hierarquia da §13.6 vale no caso-limite, sem erro.
    verificar_hierarquia_ataque_imediato(
        ATAQUE_IMEDIATO_POTENCIAL=ATAQUE_IMEDIATO_POTENCIAL,
        ATAQUE_IMEDIATO_RECOMENDADO=ATAQUE_IMEDIATO_RECOMENDADO,
    )


@pytest.mark.regra
def test_elegivel_zero_com_recursos_positivos() -> None:
    """`EC-28`: `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 0` com recursos
    recomendáveis positivos → `ATAQUE_IMEDIATO_RECOMENDADO = 0`, porque "a
    §13.5 proíbe recomendar recurso sem destinação financeira elegível".

    O cenário parte de itens REAIS, não de totais escritos à mão: os quatro
    componentes são derivados pelas funções da §13.3 sobre um investimento
    líquido recomendável (3.000), um recurso confirmado e imediato (2.000),
    um ativo recomendável (4.000) e 1.000 em caixa — 10.000 de recursos
    recomendáveis, todos legítimos. Ter dinheiro mobilizável não é razão para
    mobilizá-lo, e o resultado é `0`.

    O residual confirma o outro lado da mesma regra: com elegível `0`, não há
    o que a reserva cubra, e ela também fica em `0` (§13.4).
    """
    CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=dinheiro(1000))
    INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(
        investimentos=(
            _investimento(
                "I1", 3000, liquidez=True, classe=CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL
            ),
        )
    )
    EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(
        recursos_extraordinarios=(
            _recurso(
                "R1",
                2000,
                janela=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
                certeza=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
            ),
        )
    )
    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(
        ativos=(_ativo("A1", 4000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),)
    )

    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(0),
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
    )
    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(9000),
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(0),
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )

    assertar_exato(
        CAIXA_RECOMENDADO
        + INVESTIMENTOS_RECOMENDADOS
        + EXTRAORDINARIOS_RECOMENDADOS
        + ATIVOS_RECOMENDADOS,
        dinheiro(10000),
    )
    assertar_exato(NECESSIDADE_RESIDUAL, dinheiro(0))
    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))
    assertar_exato(obtido, dinheiro(0))


@pytest.mark.regra
def test_nao_protetivos_cobrem_tudo_residual_zero() -> None:
    """`EC-29`: "todos os componentes não protetivos já cobrem a necessidade
    elegível → `NECESSIDADE_RESIDUAL = 0` e `RESERVA_RECOMENDADA = 0` — a
    reserva é o último componente e só cobre residual".

    Os quatro não protetivos somam 16.000 contra elegível de 10.000: excesso
    de 6.000, que a subtração crua transformaria em residual `−6.000` e que o
    `MAX(0, ...)` da §13.4 corta. A reserva de 25.000 fica integralmente de
    fora — não há residual que ela cubra —, e o recomendado é os 10.000 do
    teto, provando que o excedente dos não protetivos também não vaza.
    """
    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(10000),
        CAIXA_RECOMENDADO=dinheiro(4000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(4000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(4000),
        ATIVOS_RECOMENDADOS=dinheiro(4000),
    )
    assertar_exato(NECESSIDADE_RESIDUAL, dinheiro(0))

    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=dinheiro(25000),
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=SUPERAVIT,
    )
    assertar_exato(RESERVA_RECOMENDADA, dinheiro(0))

    obtido = calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=dinheiro(10000),
        CAIXA_RECOMENDADO=dinheiro(4000),
        INVESTIMENTOS_RECOMENDADOS=dinheiro(4000),
        EXTRAORDINARIOS_RECOMENDADOS=dinheiro(4000),
        ATIVOS_RECOMENDADOS=dinheiro(4000),
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )
    assertar_exato(obtido, dinheiro(10000))


@pytest.mark.regra
def test_com_ressalvas_nao_entra_em_potencial_nem_recomendado() -> None:
    """`EC-30`: "ativo classificado `MOBILIZACAO_COM_RESSALVAS` com valor
    líquido realizável alto → não entra em `ATIVOS_RECOMENDADOS` **nem** em
    `ATAQUE_IMEDIATO_POTENCIAL` — as ressalvas não são resolvidas
    automaticamente pelo motor".

    O "nem" do enunciado é o ponto: `MOBILIZACAO_POSSIVEL` fica de fora só do
    recomendado, mas `MOBILIZACAO_COM_RESSALVAS` fica de fora dos DOIS. As
    duas somas são calculadas sobre a mesma coleção, com o item de ressalva
    valendo 250.000 contra 700 do recomendável: nenhuma das duas o enxerga.
    """
    ativos = (
        _ativo("A_RESSALVAS", 250000, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS),
        _ativo("A_RECOMENDAVEL", 700, CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL),
    )

    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=ativos)
    ATAQUE_IMEDIATO_POTENCIAL = calcular_ATAQUE_IMEDIATO_POTENCIAL(
        DINHEIRO_DISPONIVEL=dinheiro(0),
        RESERVA_MOBILIZAVEL=dinheiro(0),
        investimentos=(),
        recursos_extraordinarios=(),
        ativos=ativos,
    )

    assertar_exato(ATIVOS_RECOMENDADOS, dinheiro(700))
    assertar_exato(ATAQUE_IMEDIATO_POTENCIAL, dinheiro(700))


@pytest.mark.regra
@pytest.mark.parametrize(
    ("construtor", "campos_sem_classificacao", "campos_completos"),
    [
        (
            ItemInvestimento,
            {
                "ITEM_ID": "I_SEM_CLASSE",
                "VALOR_LIQUIDO_REALIZAVEL": dinheiro(4000),
                "POSSUI_LIQUIDEZ": True,
            },
            {
                "ITEM_ID": "I_SEM_CLASSE",
                "VALOR_LIQUIDO_REALIZAVEL": dinheiro(4000),
                "POSSUI_LIQUIDEZ": True,
                "LIQUIDEZ_INVESTIMENTOS": LIQUIDEZ_INVESTIMENTOS.D0,
                "DISPOSICAO_USO_INVESTIMENTO": DISPOSICAO_USO_INVESTIMENTO.NAO,
                "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL": dinheiro(4000),
                "TEM_CUSTO_CONHECIDO": False,
                "SEM_CUSTO_PERDA_RELEVANTE": True,
            },
        ),
        (
            ItemAtivo,
            {
                "ITEM_ID": "A_SEM_CLASSE",
                "VALOR_ESTIMADO_ATIVO": dinheiro(4000),
            },
            {
                "ITEM_ID": "A_SEM_CLASSE",
                "TIPO_ATIVO_FISICO": TIPO_ATIVO_FISICO.OUTRO_ATIVO,
                "POSSIBILIDADE_VENDA": POSSIBILIDADE_VENDA.NAO,
                "ESSENCIALIDADE": ESSENCIALIDADE.NAO_ESSENCIAL,
                "VALOR_ESTIMADO_ATIVO": dinheiro(4000),
                "POSSUI_PASSIVO_VINCULADO": False,
                "SALDO_PASSIVO_VINCULADO": dinheiro(0),
                "POSSUI_CUSTO_DESMOBILIZACAO": False,
                "CUSTOS_ESTIMADOS_DESMOBILIZACAO": dinheiro(0),
                "RENDA_RECORRENTE_ATIVO": dinheiro(0),
                "CUSTO_RECORRENTE_ATIVO": dinheiro(0),
            },
        ),
    ],
)
def test_item_sem_campo_bruto_falha_na_construcao(
    construtor: type[Any],
    campos_sem_classificacao: dict[str, Any],
    campos_completos: dict[str, Any],
) -> None:
    """`EC-32` (`RF-59`, `T-125`) — sucessor declarado de `EC-31`, que está
    REVOGADO (plano R4.1.1): "item de entrada chega sem os campos BRUTOS que
    a §14.3.1/§14.4-§14.9 exigem para a classificação → erro de contrato na
    construção do estado". `CLASSIFICACAO_MOBILIZACAO` não é mais campo do
    construtor (`RF-59`) — o que falta agora é um campo BRUTO qualquer.

    Visto da §13, que é o ângulo desta tarefa: o item incompleto nunca CHEGA
    às funções da §13.2/§13.3. A falha é na construção (`TypeError`), o que
    significa que nenhuma função deste módulo precisa — e nenhuma pode — ter
    um ramo de default para campo bruto ausente. A contraprova mostra o
    outro lado: com todos os campos brutos presentes, o item constrói e
    `classificar_investimento`/`classificar_ativo_fisico` decidem a
    classificação (aqui `NAO_MOBILIZAR`, que soma `0` nos dois lugares)."""
    with pytest.raises(TypeError):
        construtor(**campos_sem_classificacao)

    item = construtor(**campos_completos)
    if isinstance(item, ItemInvestimento):
        assertar_exato(
            classificar_investimento(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR
        )
        assertar_exato(calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=(item,)), dinheiro(0))
        potencial = calcular_ATAQUE_IMEDIATO_POTENCIAL(
            DINHEIRO_DISPONIVEL=dinheiro(0),
            RESERVA_MOBILIZAVEL=dinheiro(0),
            investimentos=(item,),
            recursos_extraordinarios=(),
            ativos=(),
        )
    else:
        assertar_exato(classificar_ativo_fisico(item), CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR)
        assertar_exato(calcular_ATIVOS_RECOMENDADOS(ativos=(item,)), dinheiro(0))
        potencial = calcular_ATAQUE_IMEDIATO_POTENCIAL(
            DINHEIRO_DISPONIVEL=dinheiro(0),
            RESERVA_MOBILIZAVEL=dinheiro(0),
            investimentos=(),
            recursos_extraordinarios=(),
            ativos=(item,),
        )
    assertar_exato(potencial, dinheiro(0))
