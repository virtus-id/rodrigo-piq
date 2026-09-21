"""Contrato de estado da fatia 3A e os dois enunciados de coleta (T-100)
— RF-36, RF-37, RF-38, RF-39, RF-40, RF-42, RF-52 · §13.1, §13.2, §13.3, §13.8.

Os sete testes do plano R3.9.4. Todos testam o **contrato observável** do
estado — presença e nome literal de campo, tipo que admite desconhecido,
coleção por item sem total agregado, decidibilidade por item, cardinalidade
do enum — nunca implementação interna (`sdd.config.md` §5).

Dois deles leem o YAML de coleta (`collection/registros/bloco-04.yaml`), e
isso é deliberado: a fronteira arquitetural do projeto proíbe `engine/`
IMPORTAR de `collection/` (`sdd.config.md` §3), não proíbe um teste ler o
registro como dado. `AC-69` e `AC-84` são afirmações sobre o texto do
registro — não há outro lugar de onde verificá-las.

Nomenclatura caractere por caractere (`sdd.config.md` §7): os nomes de campo
são comparados como STRING literal contra `dataclasses.fields`, não por
acesso a atributo. Um teste que escrevesse `estado.RESERVA_TOTAL` provaria
que o atributo existe, mas não que ele se chama exatamente assim no contrato
— um `AttributeError` numa refatoração de rename seria indistinguível de um
erro de digitação no próprio teste.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from engine.classificacao_ativos import classificar_ativo_fisico, classificar_investimento
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    ESSENCIALIDADE,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_ATIVO_FISICO,
    TIPO_RENDA,
    EstadoFinanceiro,
    ItemAtivo,
    ItemInvestimento,
    PerfilComportamental,
    RecursoExtraordinario,
    SinaisComportamentais,
)
from engine.precisao import dinheiro
from engine.tipos import (
    CLASSIFICACAO_MOBILIZACAO,
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    SimNaoTalvez,
)
from tests.conftest import assertar_exato

_BLOCO_04 = Path(__file__).resolve().parents[2] / "collection" / "registros" / "bloco-04.yaml"

_PERFIL_NEUTRO = PerfilComportamental(
    REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
    FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
    DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
    COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
    COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
    CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
    GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
    REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
)

_SINAIS_NEUTROS = SinaisComportamentais(
    NOVA_DIVIDA_PREVISTA=SimNaoTalvez.NAO,
    MECANISMO_DEFICIT=frozenset(),
    HISTORICO_RECAIDA=SimNaoTalvez.NAO,
    NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez.NAO,
    PACTO="ESTABELECIDO",
    RISCO_IMPULSO="NENHUMA",
    LINHA_CONTINUA_SENDO_UTILIZADA="NAO",
    NECESSIDADE_VITORIA=0,
    HISTORICO_ABANDONO=SimNaoTalvez.NAO,
    JANELA_NOVA_DIVIDA=None,
)


def _estado(**sobrescritas: Any) -> EstadoFinanceiro:
    """`EstadoFinanceiro` neutro; cada teste sobrescreve por nome só os campos
    da §13 que exercita. Mesmo padrão de `_estado(...)` em
    `tests/regras/test_diagnostico.py`."""
    campos: dict[str, Any] = {
        "DATA_REFERENCIA": date(2026, 9, 1),
        "RENDA_TOTAL_RECORRENTE": dinheiro(8000),
        "TIPO_RENDA": TIPO_RENDA.FIXA,
        "DESPESAS_OPERACIONAIS_ATUAIS": dinheiro(0),
        "DESPESAS_NAO_MENSAIS_NORMALIZADAS": dinheiro(0),
        "CAPACIDADE_ATAQUE_DECLARADA": dinheiro(0),
        "ECONOMIA_POTENCIAL_IMEDIATA": dinheiro(0),
        "INVENTARIO_COMPLETO": True,
        "dividas": (),
        "perfil_comportamental": _PERFIL_NEUTRO,
        "sinais_comportamentais": _SINAIS_NEUTROS,
        "CONFIABILIDADE_DADOS": CONFIABILIDADE_DADOS.ALTA,
        "AUTOPERCEPCAO_CONTROLE": 5,
        # --- Rodada 3 · nove campos neutros (`EC-23`: Regra 1 vence) ---
        "RESERVA_EXISTE": RESERVA_EXISTE.NAO,
        "RESERVA_TOTAL": dinheiro(0),
        "DISPOSICAO_USO_RESERVA": DISPOSICAO_USO_RESERVA.NAO,
        "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": dinheiro(0),
        "DINHEIRO_DISPONIVEL": dinheiro(0),
        "investimentos": (),
        "ativos": (),
        "recursos_extraordinarios": (),
    }
    campos.update(sobrescritas)
    return EstadoFinanceiro(**campos)


def _registros_do_bloco_04() -> dict[str, dict[str, Any]]:
    """Os registros de `bloco-04.yaml` indexados por `ID`, lidos como DADO.

    Leitura direta do YAML, sem passar por `collection/carga.py`: `AC-69` e
    `AC-84` são afirmações sobre o CONTEÚDO do registro publicado, e um
    carregador no meio poderia normalizar exatamente o que se quer verificar.
    """
    bruto = yaml.safe_load(_BLOCO_04.read_text(encoding="utf-8"))
    return {pergunta["ID"]: pergunta for pergunta in bruto["perguntas"]}


# ---------------------------------------------------------------------------
# AC-62 · AC-63 — os campos escalares da §13.1 e da §13.2
# ---------------------------------------------------------------------------
def test_estado_tem_os_quatro_campos_de_reserva_com_nome_literal() -> None:
    """`AC-62` (`RF-36`): `EstadoFinanceiro` tem `RESERVA_EXISTE`,
    `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA` e
    `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` escritos caractere por caractere
    com esses nomes, e os dois `DinheiroTalvez` aceitam tanto valor monetário
    quanto `DESCONHECIDO` — a Regra 3 da §13.1 EXIGE o estado desconhecido
    ("reserva total desconhecida → RESERVA_MOBILIZAVEL = DESCONHECIDA"),
    nunca zero silencioso."""
    nomes = {campo.name for campo in dataclasses.fields(EstadoFinanceiro)}

    for nome_literal in (
        "RESERVA_EXISTE",
        "RESERVA_TOTAL",
        "DISPOSICAO_USO_RESERVA",
        "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",
    ):
        assert nome_literal in nomes, (
            f"AC-62: `EstadoFinanceiro` não tem o campo {nome_literal!r} — "
            f"campos presentes: {sorted(nomes)}"
        )

    # Os dois `DinheiroTalvez` aceitam valor monetário...
    com_valor = _estado(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        RESERVA_TOTAL=dinheiro(20000),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.PARTE,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro(5000),
    )
    assertar_exato(com_valor.RESERVA_TOTAL, dinheiro(20000))
    assertar_exato(com_valor.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO, dinheiro(5000))

    # ...e o estado desconhecido, que sobrevive como sentinela — nunca 0, nunca None.
    com_desconhecido = _estado(
        RESERVA_EXISTE=RESERVA_EXISTE.SIM,
        RESERVA_TOTAL=DESCONHECIDO,
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.TALVEZ,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO,
    )
    assert com_desconhecido.RESERVA_TOTAL is DESCONHECIDO
    assert com_desconhecido.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO
    assert com_desconhecido.RESERVA_TOTAL != dinheiro(0)
    assert com_desconhecido.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is not None


def test_dinheiro_disponivel_sempre_presente_sem_revalidacao() -> None:
    """`AC-63` (`RF-37`): `DINHEIRO_DISPONIVEL` é campo monetário SEMPRE
    presente — `Dinheiro`, nunca `DinheiroTalvez` —, e o motor o consome sem
    revalidar "livre / não comprometido" (`OQ-28` encaminhada como garantia de
    COLETA: quem exclui valor comprometido é o enunciado de `B4.01`, não o
    motor).

    Duas afirmações observáveis: (a) o campo é obrigatório na construção — não
    tem default, logo não há como um estado existir sem ele; (b) `DESCONHECIDO`
    não pertence ao seu domínio declarado, ao contrário dos dois campos de
    reserva de `AC-62`."""
    por_nome = {campo.name: campo for campo in dataclasses.fields(EstadoFinanceiro)}
    assert "DINHEIRO_DISPONIVEL" in por_nome, "AC-63: campo `DINHEIRO_DISPONIVEL` ausente"

    campo = por_nome["DINHEIRO_DISPONIVEL"]
    assert campo.default is dataclasses.MISSING, (
        "AC-63: `DINHEIRO_DISPONIVEL` tem valor padrão — deixaria de ser "
        "'sempre presente' e passaria a ser omissível na construção"
    )
    assert campo.default_factory is dataclasses.MISSING, (
        "AC-63: `DINHEIRO_DISPONIVEL` tem default_factory — mesma consequência"
    )

    # Domínio declarado: `Dinheiro`, sem `Desconhecido` no tipo-soma — ao
    # contrário de `RESERVA_TOTAL`, que é `DinheiroTalvez` por `AC-62`.
    assertar_exato(campo.type, "Dinheiro")
    assertar_exato(por_nome["RESERVA_TOTAL"].type, "DinheiroTalvez")

    # Construído com valor, ele é lido como veio: nenhuma revalidação, nenhuma
    # transformação de "livre / não comprometido" entre construção e leitura.
    estado = _estado(DINHEIRO_DISPONIVEL=dinheiro("1234.56"))
    assertar_exato(estado.DINHEIRO_DISPONIVEL, dinheiro("1234.56"))
    assert type(estado.DINHEIRO_DISPONIVEL) is Decimal


# ---------------------------------------------------------------------------
# AC-64 · AC-65 — patrimônio por item, nunca total agregado
# ---------------------------------------------------------------------------
def test_investimentos_e_ativos_sao_colecao_por_item_sem_total_agregado() -> None:
    """`AC-64` (`RF-38`, `RF-53`, `RF-59`, `T-125`): 3 investimentos e 2
    ativos, cada um elemento distinto de uma coleção tipada imutável, com seu
    próprio valor líquido realizável e sua própria classificação DERIVADA
    (`classificar_investimento`/`classificar_ativo_fisico`, `RF-59` — não
    mais campo armazenado) — e NENHUM campo escalar de total agregado de
    investimentos ou de ativos existe em `EstadoFinanceiro`.

    A ausência é o coração do critério: a §13.3 exige
    `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` *dos ativos
    MOBILIZACAO_RECOMENDAVEL*, soma inexprimível sobre um escalar já somado.

    Campos brutos escolhidos de trás para frente a partir das regras de
    §14.3.1/§14.4-§14.9 para produzir a classificação que cada item deve ter
    (documentado por item, nunca valor aleatório):
      INV1 -> MOBILIZACAO_RECOMENDAVEL (Regra 4: SIM, D0, sem custo, líquido>0)
      INV2 -> MOBILIZACAO_POSSIVEL (Regra 3: TALVEZ, liquidez não bloqueada)
      INV3 -> NAO_MOBILIZAR (Regra 1: DISPOSICAO_USO_INVESTIMENTO=NAO)
      ATV1 -> MOBILIZACAO_RECOMENDAVEL (ramo 8c: não essencial, venda SIM,
        fluxo líquido recorrente <= 0)
      ATV2 -> MOBILIZACAO_COM_RESSALVAS (ramo 4: ESSENCIAL nunca RECOMENDAVEL)
    """
    investimentos = (
        ItemInvestimento(
            ITEM_ID="INV1",
            VALOR_LIQUIDO_REALIZAVEL=dinheiro(1000),
            POSSUI_LIQUIDEZ=True,
            LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D0,
            DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.SIM,
            VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(1000),
            TEM_CUSTO_CONHECIDO=False,
            SEM_CUSTO_PERDA_RELEVANTE=True,
        ),
        ItemInvestimento(
            ITEM_ID="INV2",
            VALOR_LIQUIDO_REALIZAVEL=dinheiro(2000),
            POSSUI_LIQUIDEZ=False,
            LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D30,
            DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.TALVEZ,
            VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(2000),
            TEM_CUSTO_CONHECIDO=False,
            SEM_CUSTO_PERDA_RELEVANTE=False,
        ),
        ItemInvestimento(
            ITEM_ID="INV3",
            VALOR_LIQUIDO_REALIZAVEL=dinheiro(3000),
            POSSUI_LIQUIDEZ=True,
            LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS.D0,
            DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO.NAO,
            VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=dinheiro(3000),
            TEM_CUSTO_CONHECIDO=False,
            SEM_CUSTO_PERDA_RELEVANTE=True,
        ),
    )
    ativos = (
        ItemAtivo(
            ITEM_ID="ATV1",
            TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.OUTRO_ATIVO,
            POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.SIM,
            ESSENCIALIDADE=ESSENCIALIDADE.NAO_ESSENCIAL,
            VALOR_ESTIMADO_ATIVO=dinheiro(50000),
            POSSUI_PASSIVO_VINCULADO=False,
            SALDO_PASSIVO_VINCULADO=dinheiro(0),
            POSSUI_CUSTO_DESMOBILIZACAO=False,
            CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
            RENDA_RECORRENTE_ATIVO=dinheiro(0),
            CUSTO_RECORRENTE_ATIVO=dinheiro(0),
        ),
        ItemAtivo(
            ITEM_ID="ATV2",
            TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO.IMOVEL,
            POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA.JA_PRETENDE,
            ESSENCIALIDADE=ESSENCIALIDADE.ESSENCIAL,
            VALOR_ESTIMADO_ATIVO=dinheiro(80000),
            POSSUI_PASSIVO_VINCULADO=False,
            SALDO_PASSIVO_VINCULADO=dinheiro(0),
            POSSUI_CUSTO_DESMOBILIZACAO=False,
            CUSTOS_ESTIMADOS_DESMOBILIZACAO=dinheiro(0),
            RENDA_RECORRENTE_ATIVO=dinheiro(0),
            CUSTO_RECORRENTE_ATIVO=dinheiro(0),
        ),
    )

    estado = _estado(investimentos=investimentos, ativos=ativos)

    assertar_exato(len(estado.investimentos), 3)
    assertar_exato(len(estado.ativos), 2)
    assert isinstance(estado.investimentos, tuple)  # imutável
    assert isinstance(estado.ativos, tuple)

    # Cada item é distinto e carrega o SEU valor e a SUA classificação
    # DERIVADA (RF-59) — nunca um campo armazenado.
    assertar_exato(
        tuple(item.ITEM_ID for item in estado.investimentos), ("INV1", "INV2", "INV3")
    )
    assertar_exato(
        tuple(item.VALOR_LIQUIDO_REALIZAVEL for item in estado.investimentos),
        (dinheiro(1000), dinheiro(2000), dinheiro(3000)),
    )
    assertar_exato(
        tuple(classificar_investimento(item) for item in estado.investimentos),
        (
            CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL,
            CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL,
            CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR,
        ),
    )
    assertar_exato(tuple(item.ITEM_ID for item in estado.ativos), ("ATV1", "ATV2"))

    # A `Σ` da §13.3, restrita aos MOBILIZACAO_RECOMENDAVEL, é exprimível —
    # é justamente o que um escalar já somado tornaria impossível. A
    # classificação de cada ativo, como a de investimento, é DERIVADA; o
    # valor líquido disponível também (RF-57), a partir de VALOR_ESTIMADO_ATIVO
    # já conhecido (Decimal puro, nunca DESCONHECIDO, nos dois itens acima).
    soma_recomendavel = dinheiro(0)
    for item in estado.ativos:
        if classificar_ativo_fisico(item) is not CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL:
            continue
        assert isinstance(item.VALOR_ESTIMADO_ATIVO, Decimal)
        soma_recomendavel += item.VALOR_ESTIMADO_ATIVO
    assertar_exato(soma_recomendavel, dinheiro(50000))

    # Nenhum campo escalar de total agregado — a asserção negativa de `AC-64`.
    nomes_de_colecao = {"investimentos", "ativos", "recursos_extraordinarios", "dividas"}
    agregadores_suspeitos: list[str] = []
    for campo in dataclasses.fields(EstadoFinanceiro):
        if campo.name in nomes_de_colecao:
            continue
        nome = campo.name.upper()
        menciona_patrimonio = "INVESTIMENTO" in nome or "ATIVO" in nome
        parece_total = any(
            marca in nome for marca in ("TOTAL", "SOMA", "AGREGAD", "SALDO", "VALOR")
        )
        if menciona_patrimonio and parece_total:
            agregadores_suspeitos.append(campo.name)

    assert not agregadores_suspeitos, (
        "AC-64: campo escalar de total agregado de investimentos/ativos "
        f"encontrado em `EstadoFinanceiro`: {agregadores_suspeitos!r} — a §13.3 "
        "exige Σ restrita aos MOBILIZACAO_RECOMENDAVEL, inexprimível sobre um "
        "escalar já somado"
    )


def test_recurso_extraordinario_decidivel_por_item() -> None:
    """`AC-65` (`RF-39`): com 2 recursos extraordinários, cada item carrega
    valor, janela e certeza — e "confirmado, disponível e apto no momento
    atual" (§13.3) se decide lendo SÓ os campos do próprio item, sem consultar
    nenhum outro campo do estado nem os demais itens.

    A prova de "sem consultar nenhum outro" é estrutural: o predicado abaixo
    recebe `RecursoExtraordinario` e nada mais — não tem como alcançar
    `EstadoFinanceiro`, e produz a decisão certa para os dois itens."""

    def _apto_no_momento_atual(item: RecursoExtraordinario) -> bool:
        """§13.3, lendo exclusivamente os campos do item recebido."""
        return (
            item.CERTEZA_RECURSO_EXTRAORDINARIO
            is CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO
            and item.JANELA_RECURSO_EXTRAORDINARIO
            is JANELA_RECURSO_EXTRAORDINARIO.ATE_30D
        )

    apto = RecursoExtraordinario(
        ITEM_ID="REC1",
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(3000),
        JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO.ATE_30D,
        CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO,
    )
    futuro_e_apenas_provavel = RecursoExtraordinario(
        ITEM_ID="REC2",
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(9000),
        JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO.QUATRO_A_SEIS_MESES,
        CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO.PROVAVEL,
    )

    estado = _estado(recursos_extraordinarios=(apto, futuro_e_apenas_provavel))

    assertar_exato(len(estado.recursos_extraordinarios), 2)
    for item in estado.recursos_extraordinarios:
        assert type(item.VALOR_RECURSO_EXTRAORDINARIO) is Decimal
        assert isinstance(item.JANELA_RECURSO_EXTRAORDINARIO, JANELA_RECURSO_EXTRAORDINARIO)
        assert isinstance(item.CERTEZA_RECURSO_EXTRAORDINARIO, CERTEZA_RECURSO_EXTRAORDINARIO)

    assertar_exato(
        tuple(_apto_no_momento_atual(item) for item in estado.recursos_extraordinarios),
        (True, False),
    )


# ---------------------------------------------------------------------------
# AC-66 · EC-31 — o enum de classificação e a obrigatoriedade por item
# ---------------------------------------------------------------------------
def test_classificacao_mobilizacao_tem_exatamente_quatro_membros() -> None:
    """`AC-66` (`RF-40`): `CLASSIFICACAO_MOBILIZACAO` tem exatamente quatro
    membros — `MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`,
    `MOBILIZACAO_COM_RESSALVAS`, `NAO_MOBILIZAR` — sem quinto valor, sem
    acento e sem sinônimo. Nome e valor conferidos caractere por caractere."""
    assertar_exato(
        tuple(membro.name for membro in CLASSIFICACAO_MOBILIZACAO),
        (
            "MOBILIZACAO_POSSIVEL",
            "MOBILIZACAO_RECOMENDAVEL",
            "MOBILIZACAO_COM_RESSALVAS",
            "NAO_MOBILIZAR",
        ),
    )
    assertar_exato(
        {membro.value for membro in CLASSIFICACAO_MOBILIZACAO},
        {
            "MOBILIZACAO_POSSIVEL",
            "MOBILIZACAO_RECOMENDAVEL",
            "MOBILIZACAO_COM_RESSALVAS",
            "NAO_MOBILIZAR",
        },
    )

    for membro in CLASSIFICACAO_MOBILIZACAO:
        assert membro.name.isascii(), f"AC-66: membro com acento: {membro.name!r}"
        assert membro.value.isascii(), f"AC-66: valor com acento: {membro.value!r}"


@pytest.mark.parametrize(
    ("construtor", "campos_sem_um_bruto", "campos_completos"),
    [
        (
            ItemInvestimento,
            {
                "ITEM_ID": "INV1",
                "VALOR_LIQUIDO_REALIZAVEL": dinheiro(1000),
                "POSSUI_LIQUIDEZ": True,
            },
            {
                "ITEM_ID": "INV1",
                "VALOR_LIQUIDO_REALIZAVEL": dinheiro(1000),
                "POSSUI_LIQUIDEZ": True,
                "LIQUIDEZ_INVESTIMENTOS": LIQUIDEZ_INVESTIMENTOS.D0,
                "DISPOSICAO_USO_INVESTIMENTO": DISPOSICAO_USO_INVESTIMENTO.NAO,
                "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL": dinheiro(1000),
                "TEM_CUSTO_CONHECIDO": False,
                "SEM_CUSTO_PERDA_RELEVANTE": True,
            },
        ),
        (
            ItemAtivo,
            {
                "ITEM_ID": "ATV1",
                "VALOR_ESTIMADO_ATIVO": dinheiro(50000),
            },
            {
                "ITEM_ID": "ATV1",
                "TIPO_ATIVO_FISICO": TIPO_ATIVO_FISICO.OUTRO_ATIVO,
                "POSSIBILIDADE_VENDA": POSSIBILIDADE_VENDA.NAO,
                "ESSENCIALIDADE": ESSENCIALIDADE.NAO_ESSENCIAL,
                "VALOR_ESTIMADO_ATIVO": dinheiro(50000),
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
    campos_sem_um_bruto: dict[str, Any],
    campos_completos: dict[str, Any],
) -> None:
    """`EC-32` (`RF-59`, `T-125`) — sucessor declarado de `EC-31`, REVOGADO
    (plano R4.1.1): item de entrada sem um campo BRUTO exigido por §14.3.1/
    §14.4-§14.9 é erro de contrato na CONSTRUÇÃO do estado — `TypeError`, não
    um default silencioso. `CLASSIFICACAO_MOBILIZACAO` não é mais campo do
    construtor (`RF-59`): o motor não escolhe classe por omissão — ele DERIVA
    a classificação de campos brutos que precisam estar todos presentes."""
    with pytest.raises(TypeError):
        construtor(**campos_sem_um_bruto)

    # Contraprova: os MESMOS campos, mais os demais campos brutos, constroem
    # sem erro — isola que o `TypeError` é pelo campo bruto ausente, não por
    # outro campo.
    construtor(**campos_completos)


# ---------------------------------------------------------------------------
# AC-69 · AC-84 — os dois enunciados de coleta, lidos do YAML
# ---------------------------------------------------------------------------
def test_bloco04_b4_03a_grava_valor_maximo_informado() -> None:
    """`AC-69` (`RF-42`): em `collection/registros/bloco-04.yaml`, o registro
    de `B4.03A` grava `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, o campo `ID`
    continua `B4.03A`, e nenhum outro registro de coleta grava em
    `RESERVA_MOBILIZAVEL` — que passa a designar exclusivamente o valor
    DERIVADO pelo motor (`T-99`)."""
    registros = _registros_do_bloco_04()

    assert "B4.03A" in registros, f"AC-69: registro B4.03A ausente em {_BLOCO_04}"
    b4_03a = registros["B4.03A"]

    assertar_exato(b4_03a["ID"], "B4.03A")
    assertar_exato(b4_03a["VARIAVEL_GRAVADA"], "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO")

    # Nenhum registro de coleta, em NENHUM bloco, grava em RESERVA_MOBILIZAVEL.
    diretorio_registros = _BLOCO_04.parent
    gravam_derivado: list[str] = []
    for arquivo in sorted(diretorio_registros.glob("*.yaml")):
        bruto = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
        for pergunta in bruto["perguntas"]:
            if pergunta.get("VARIAVEL_GRAVADA") == "RESERVA_MOBILIZAVEL":
                gravam_derivado.append(f"{arquivo.name}:{pergunta['ID']}")

    assert not gravam_derivado, (
        "AC-69: registro de coleta gravando em RESERVA_MOBILIZAVEL (valor "
        f"DERIVADO pelo motor, nunca coletado): {gravam_derivado!r}"
    )


def test_b4_04_continua_excluindo_valores_de_reserva() -> None:
    """`AC-84` (`RF-52`): o enunciado de `B4.04` continua excluindo
    explicitamente os valores já informados como reserva ("Além dos valores
    que você já informou como reserva, ..."), de modo que o PRIMEIRO caso
    vedado da §13.8 — o mesmo dinheiro contado como reserva e como
    investimento — permanece prevenido na ORIGEM, e não por uma
    desduplicação a posteriori no motor."""
    registros = _registros_do_bloco_04()

    assert "B4.04" in registros, f"AC-84: registro B4.04 ausente em {_BLOCO_04}"
    b4_04 = registros["B4.04"]

    assertar_exato(b4_04["ID"], "B4.04")
    enunciado = " ".join(b4_04["enunciado"].split())  # normaliza a quebra do YAML

    assert "Além dos valores que você já informou como reserva" in enunciado, (
        "AC-84: o enunciado de B4.04 não exclui mais os valores já informados "
        f"como reserva — §13.8 caso 1 deixaria de ser prevenido na origem. "
        f"Enunciado atual: {enunciado!r}"
    )
    assert "outros investimentos" in enunciado, (
        f"AC-84: B4.04 deixou de perguntar por OUTROS investimentos: {enunciado!r}"
    )
