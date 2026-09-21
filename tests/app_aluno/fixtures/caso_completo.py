"""Fixture de caso COMPLETO — dado de teste, nunca de produção (`T-53`).

Um conjunto de respostas simuladas que cobre TODOS os blocos obrigatórios que
`app/montagem/estado.py::montar_estado_financeiro` consome (`RF-12`, `RF-14`,
`RF-15`): as 8 variáveis de `PerfilComportamental` (Bloco 2), os 8 campos de
`SinaisComportamentais` lidos por `respostas.valor` (Blocos 1/2/9), `TIPO_RENDA`
e `CAPACIDADE_ATAQUE_DECLARADA` (Bloco 3), os cinco campos escalares de
reserva e caixa do Bloco 4 (`T-112`: `DINHEIRO_DISPONIVEL_EXISTE`/
`DINHEIRO_DISPONIVEL`, `RESERVA_EXISTE`, `RESERVA_TOTAL`,
`DISPOSICAO_USO_RESERVA`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` — `RF-36`,
`RF-37`, `RF-38`), `CONFIRMACAO_FIM_CADASTRO`/`B5.FIM02` (Bloco 5) e uma ficha
de dívida completa do Bloco 5 (`DIVIDA_ID`).

**Por que este arquivo vive em `tests/`, não em `app/`/`collection/`.** Os
valores de resposta abaixo (`"TUDO"`, `"CARTAO_ROTATIVO"`, `"SIM"`, ...) são
dado de teste — a mesma classe de literal que os testes estáticos de `T-06`/
`T-08` (`AC-37`, `AC-41`) auditam em `app/`, `collection/` e `report/`. Este
módulo NUNCA é importado de nenhum desses três pacotes; só de `tests/`.

Nenhum `VARIAVEL_GRAVADA`/`valor_interno` aqui é inventado: todos são
conferidos contra os registros REAIS (`collection/registros/bloco-0{1,2,3,5}
.yaml`, `T-17`/`T-99`) pelos testes de fidelidade já existentes em
`tests/app_aluno/test_montagem_divida.py`,
`test_montagem_perfil_comportamental.py` e `test_montagem_estado_financeiro.py`
— este módulo reaproveita os MESMOS nomes de variável, nunca uma nova
transcrição.

REGRAS: `RF-12`, `RF-14`, `RF-15`, `AC-07`, `AC-08`, `AC-13`, `AC-18`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

from app.montagem.conversao import converter_para_dinheiro
from collection.respostas import NaoSei, Resposta, RespostasCaso
from engine.tipos import CONFIABILIDADE_DADOS

CASO_ID: Final[str] = "caso-teste-t53-completo"
QUESTIONARIO_VERSION: Final[str] = "1.0.0"
RESPONDIDA_EM: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
DATA_REFERENCIA: Final[date] = date(2026, 3, 15)

# A única ficha de dívida do caso completo — DIVIDA_ID estável, reaproveitado
# por todos os testes que precisam de uma dívida concreta.
DIVIDA_ID_UNICA: Final[str] = "D-CASO-COMPLETO"

# O único parâmetro externo que `montar_estado_financeiro` continua exigindo
# depois de `T-103` (`OQ-16`) é `CONFIABILIDADE_DADOS` (derivada pelo motor,
# fora do escopo desta camada) — a fixture o fornece explicitamente, nunca
# presume que vem da coleta. `RENDA_TOTAL_RECORRENTE`, `DESPESAS_
# OPERACIONAIS_ATUAIS` e `DESPESAS_NAO_MENSAIS_NORMALIZADAS` NÃO são mais
# parâmetro externo (`T-103`): são CALCULADAS por `montar_estado_financeiro`
# a partir das respostas de origem do Bloco 3 (`_VALORES_CASO`, abaixo) —
# `RENDA_PRINCIPAL=8.000,00` sem fonte adicional, uma ficha de `ITEM_DESPESA`
# de `6.500,00` e uma ficha de `DESPESA_NAO_MENSAL_ID` de `6.000,00`/ano
# (÷12 = 500,00) reproduzem exatamente os mesmos três totais que este caso
# completo sempre teve, agora por cálculo real em vez de parâmetro.
PARAMETROS_EXTERNOS_PADRAO: Final[dict[str, object]] = {
    "CONFIABILIDADE_DADOS": CONFIABILIDADE_DADOS.ALTA,
    # Nenhum gasto fantasma identificado no caso completo padrão — ver
    # `_economia_potencial_imediata` em `app/montagem/estado.py`.
    "economia_nao_identificada": Decimal("0"),
}

# Identificadores de item de teste para as fichas REP do Bloco 3 que
# alimentam os três campos agregados de `montar_estado_financeiro` (`T-103`,
# `OQ-16`/`OQ-19`) — mesmo padrão de `DIVIDA_ID_UNICA`, acima.
ITEM_DESPESA_ID_UNICA: Final[str] = "DESP-CASO-COMPLETO"
DESPESA_NAO_MENSAL_ID_UNICA: Final[str] = "NM-CASO-COMPLETO"


def _resposta_caso(ID_PERGUNTA: str, valor: object) -> Resposta:
    """Resposta não repetível (`item_id=None`) do caso completo."""
    return Resposta(
        CASO_ID=CASO_ID,
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=None,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION=QUESTIONARIO_VERSION,
        respondida_em=RESPONDIDA_EM,
    )


def _resposta_item(ID_PERGUNTA: str, item_id: str, valor: object) -> Resposta:
    """Resposta de uma ficha repetível (qualquer `EscopoRepeticao`, por
    `item_id`) — generalizado por `T-103` para servir também às fichas de
    `ITEM_DESPESA`/`RENDA_ADICIONAL_ID`/`DESPESA_NAO_MENSAL_ID`, não só
    `DIVIDA_ID` (Bloco 5)."""
    return Resposta(
        CASO_ID=CASO_ID,
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION=QUESTIONARIO_VERSION,
        respondida_em=RESPONDIDA_EM,
    )


# ---------------------------------------------------------------------------
# Respostas não repetíveis do caso completo: PerfilComportamental (Bloco 2),
# SinaisComportamentais (Blocos 1/2/9), TIPO_RENDA/CAPACIDADE_ATAQUE_DECLARADA
# (Bloco 3) e CONFIRMACAO_FIM_CADASTRO (B5.FIM02). Mesmos valores usados por
# `tests/app_aluno/test_montagem_estado_financeiro.py::
# _respostas_minimas_completas` — a fixture os centraliza para reúso.
# ---------------------------------------------------------------------------
_VALORES_CASO: Final[dict[str, object]] = {
    # PerfilComportamental (Bloco 2, T-50)
    "REGISTRO_GASTOS": "TUDO",
    "FREQUENCIA_REGISTRO": "DIARIA",
    "DEFASAGEM_REGISTRO": "NA_HORA",
    "COBERTURA_PEQUENOS_GASTOS": "TODOS",
    "COBERTURA_MEIOS_PAGAMENTO": "TOTAL",
    "CONHECIMENTO_GASTO": "BOA_APROXIMACAO",
    "GASTOS_NAO_IDENTIFICADOS": "NUNCA",
    "REVISAO_SEMANAL": "SEMPRE",
    # AUTOPERCEPCAO_CONTROLE (B2.13, escala 0-10)
    "AUTOPERCEPCAO_CONTROLE": 6,
    # SinaisComportamentais (Blocos 1/2/9, T-50/T-99)
    "NOVA_DIVIDA_PREVISTA": "NAO",
    "MECANISMO_DEFICIT": frozenset({"CORTE"}),
    "HISTORICO_RECAIDA": "NENHUMA",
    "NOVO_PARCELAMENTO_PREVISTO": "NAO",
    "PACTO": "ESTABELECIDO",
    "RISCO_IMPULSO": "NENHUMA",
    "NECESSIDADE_VITORIA": 5,
    "HISTORICO_ABANDONO": "NAO",
    # EstadoFinanceiro propriamente dito (Bloco 3, T-51)
    "TIPO_RENDA": "FIXA",
    "CAPACIDADE_ATAQUE_DECLARADA": converter_para_dinheiro("500,00"),
    # RENDA_TOTAL_RECORRENTE (T-103, OQ-16): B3.01, sem nenhuma ficha de
    # renda adicional no caso completo padrão — RENDA_TOTAL_RECORRENTE =
    # RENDA_PRINCIPAL = 8.000,00 (mesmo total que T-51 recebia como
    # parâmetro externo, agora calculado).
    "RENDA_PRINCIPAL": converter_para_dinheiro("8.000,00"),
    # B5.FIM02 (T-52) — "Sim. O inventário está completo." por padrão; os
    # testes de AC-07 sobrescrevem este valor com os outros dois membros do
    # domínio (NAO/NAO_SEI).
    "CONFIRMACAO_FIM_CADASTRO": "SIM",
    # ---------------------------------------------------------------------
    # Bloco 4 — reserva e caixa (T-112, RF-36/RF-37/RF-38). Os cinco campos
    # escalares que `montar_estado_financeiro` passou a LER das respostas em
    # `T-110`/`T-111`: sem eles, toda montagem a partir desta fixture cai no
    # caminho de erro de `_dinheiro_disponivel` (`Erro DinheiroDisponivel
    # Indeterminado`) ou de `_reserva_existe` (`ErroRespostaAusente`).
    # Todos os `valor_interno` abaixo são os do registro REAL
    # (`collection/registros/bloco-04.yaml`, T-17), caractere por caractere.
    #
    # POR QUE CADA VALOR no caso padrão — o caso completo é o aluno que
    # respondeu TUDO que dava para responder, então cada campo recebe o ramo
    # AFIRMATIVO E CONHECIDO, aquele que exercita a leitura de verdade em vez
    # de um atalho:
    #
    # - B4.01 = SIM + B4.01A = 1.200,00: o ramo do `Decimal` real de
    #   `_dinheiro_disponivel` (AC-57). `NAO` daria o zero legítimo (AC-58),
    #   mas zero é caminho de borda, não caso completo; e `NAO_SEI` levantaria
    #   erro (EC-20). Valor menor que a reserva porque é caixa de curto prazo
    #   "não comprometido até a próxima entrada de renda" (enunciado B4.01),
    #   não poupança.
    # - B4.02 = SIM + B4.02A = 10.000,00: reserva ESTRUTURADA e MEDIDA.
    #   `INFORMAL` também é reserva, mas `SIM` é o membro que a devolutiva
    #   trata como reserva plena; `NAO` suprimiria B4.02A/B4.03/B4.03A por
    #   `condicao_exibicao` (:78-80, :135-137) e deixaria três dos cinco
    #   campos em ausência estrutural — o oposto de um caso completo (EC-16).
    # - B4.03 = PARTE + B4.03A = 3.000,00: o aluno aceita colocar PARTE da
    #   reserva em análise e DECLARA quanto. `TALVEZ` sem valor levaria
    #   `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` a DESCONHECIDO (AC-56) e
    #   `NAO` suprimiria B4.03A (EC-17) — de novo, bordas, não caso completo.
    #   3.000,00 < 10.000,00 deliberadamente: assim o MIN da Regra 2 da §13.1
    #   (`MIN(RESERVA_TOTAL, MAX(0, informado))`) NÃO satura, e o valor que o
    #   motor devolve é o que o aluno informou. Quem quiser o caso saturado
    #   sobrescreve `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (T-114, AC-68) —
    #   a fixture não antecipa esse cálculo em lugar nenhum (RF-44).
    #
    # Os três monetários passam por `converter_para_dinheiro(...)`, a
    # fronteira única (RF-13), como `RENDA_PRINCIPAL` e
    # `CAPACIDADE_ATAQUE_DECLARADA` acima — nenhum `float`, nenhum `Decimal`
    # construído à mão. Todos sobrescrevíveis parcialmente por
    # `montar_respostas_caso(valores_caso=...)`, como os demais.
    "DINHEIRO_DISPONIVEL_EXISTE": "SIM",
    "DINHEIRO_DISPONIVEL": converter_para_dinheiro("1.200,00"),
    "RESERVA_EXISTE": "SIM",
    "RESERVA_TOTAL": converter_para_dinheiro("10.000,00"),
    "DISPOSICAO_USO_RESERVA": "PARTE",
    "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": converter_para_dinheiro("3.000,00"),
}

# ---------------------------------------------------------------------------
# DESPESAS_OPERACIONAIS_ATUAIS (T-103, OQ-16): uma única ficha de
# ITEM_DESPESA com VALOR_DESPESA = 6.500,00 reproduz o mesmo total que T-51
# recebia como parâmetro externo. DESPESAS_NAO_MENSAIS_NORMALIZADAS: uma
# única ficha de DESPESA_NAO_MENSAL_ID com VALOR_DESPESA_NAO_MENSAL =
# 6.000,00 (anual) ÷ 12 = 500,00/mês, mesmo total de antes.
# ---------------------------------------------------------------------------
_VALORES_ITEM_DESPESA_PADRAO: Final[dict[str, object]] = {
    "VALOR_DESPESA": converter_para_dinheiro("6.500,00"),
}
_VALORES_DESPESA_NAO_MENSAL_PADRAO: Final[dict[str, object]] = {
    "VALOR_DESPESA_NAO_MENSAL": converter_para_dinheiro("6.000,00"),
}

# ---------------------------------------------------------------------------
# A ficha de dívida do Bloco 5 (DIVIDA_ID_UNICA) — os campos REP obrigatórios
# de `montar_divida` preenchidos com valores concretos. `AC-08`/`GAB-03`
# (rotativo com saldo e pagamento "não sei") é reproduzido por
# `caso_completo_com_divida_gab03` abaixo, que sobrescreve só os dois campos.
# ---------------------------------------------------------------------------
_VALORES_DIVIDA_PADRAO: Final[dict[str, object]] = {
    "TIPO_DIVIDA": "CARTAO_ROTATIVO",
    "STATUS_DIVIDA": "ATIVA",
    "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("5.000,00"),
    "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("300,00"),
    "PESO_EMOCIONAL": 5,
}


@dataclass(frozen=True, slots=True)
class CasoCompleto:
    """O par (`RespostasCaso`, parâmetros externos) que monta um
    `EstadoFinanceiro` completo e válido de ponta a ponta — reutilizável por
    outras tarefas futuras que precisem do mesmo caso de prova."""

    respostas: RespostasCaso
    parametros_externos: dict[str, object]
    DIVIDA_ID: str


def montar_respostas_caso(
    *,
    valores_caso: dict[str, object] | None = None,
    valores_divida: dict[str, object] | None = None,
    valores_item_despesa: dict[str, object] | None = None,
    valores_despesa_nao_mensal: dict[str, object] | None = None,
    DIVIDA_ID: str = DIVIDA_ID_UNICA,
    ITEM_DESPESA_ID: str = ITEM_DESPESA_ID_UNICA,
    DESPESA_NAO_MENSAL_ID: str = DESPESA_NAO_MENSAL_ID_UNICA,
) -> RespostasCaso:
    """Monta o `RespostasCaso` completo: as respostas não repetíveis de
    `_VALORES_CASO` mais a ficha de dívida `DIVIDA_ID` de
    `_VALORES_DIVIDA_PADRAO`, a ficha de despesa `ITEM_DESPESA_ID` de
    `_VALORES_ITEM_DESPESA_PADRAO` e a ficha de despesa não-mensal
    `DESPESA_NAO_MENSAL_ID` de `_VALORES_DESPESA_NAO_MENSAL_PADRAO` (`T-103`,
    `OQ-16`/`OQ-19`) — todas sobrescrevíveis por sobrescrita parcial, sem
    duplicar a base em cada teste."""
    caso = dict(_VALORES_CASO)
    if valores_caso is not None:
        caso.update(valores_caso)
    divida = dict(_VALORES_DIVIDA_PADRAO)
    if valores_divida is not None:
        divida.update(valores_divida)
    item_despesa = dict(_VALORES_ITEM_DESPESA_PADRAO)
    if valores_item_despesa is not None:
        item_despesa.update(valores_item_despesa)
    despesa_nao_mensal = dict(_VALORES_DESPESA_NAO_MENSAL_PADRAO)
    if valores_despesa_nao_mensal is not None:
        despesa_nao_mensal.update(valores_despesa_nao_mensal)

    respostas = (
        tuple(
            _resposta_caso(ID_PERGUNTA=variavel, valor=valor) for variavel, valor in caso.items()
        )
        + tuple(
            _resposta_item(ID_PERGUNTA=variavel, item_id=DIVIDA_ID, valor=valor)
            for variavel, valor in divida.items()
        )
        + tuple(
            _resposta_item(ID_PERGUNTA=variavel, item_id=ITEM_DESPESA_ID, valor=valor)
            for variavel, valor in item_despesa.items()
        )
        + tuple(
            _resposta_item(ID_PERGUNTA=variavel, item_id=DESPESA_NAO_MENSAL_ID, valor=valor)
            for variavel, valor in despesa_nao_mensal.items()
        )
    )
    return RespostasCaso(respostas=respostas)


def caso_completo(
    *,
    valores_caso: dict[str, object] | None = None,
    valores_divida: dict[str, object] | None = None,
    valores_item_despesa: dict[str, object] | None = None,
    valores_despesa_nao_mensal: dict[str, object] | None = None,
    DIVIDA_ID: str = DIVIDA_ID_UNICA,
    ITEM_DESPESA_ID: str = ITEM_DESPESA_ID_UNICA,
    DESPESA_NAO_MENSAL_ID: str = DESPESA_NAO_MENSAL_ID_UNICA,
) -> CasoCompleto:
    """O caso completo padrão: todas as respostas de todos os blocos
    obrigatórios, prontas para `montar_estado_financeiro` (depois de montar a
    `Divida` via `montar_divida` e passá-la em `dividas=(...)`)."""
    respostas = montar_respostas_caso(
        valores_caso=valores_caso,
        valores_divida=valores_divida,
        valores_item_despesa=valores_item_despesa,
        valores_despesa_nao_mensal=valores_despesa_nao_mensal,
        DIVIDA_ID=DIVIDA_ID,
        ITEM_DESPESA_ID=ITEM_DESPESA_ID,
        DESPESA_NAO_MENSAL_ID=DESPESA_NAO_MENSAL_ID,
    )
    return CasoCompleto(
        respostas=respostas,
        parametros_externos=dict(PARAMETROS_EXTERNOS_PADRAO),
        DIVIDA_ID=DIVIDA_ID,
    )


def caso_completo_com_divida_gab03() -> CasoCompleto:
    """`AC-08` — reproduz `GAB-03` (`tests/invariantes/test_gab03_rotativo.py`)
    pela via da coleta: cartão rotativo (`TIPO_DIVIDA.CARTAO_ROTATIVO`) com
    `SALDO_DEVEDOR_ATUAL` e `PAGAMENTO_MENSAL_EFETIVO` respondidos como
    "não sei" — os MESMOS dois campos que `GAB-03` fixa em `DESCONHECIDO`
    diretamente no motor. Aqui a via é a coleta: a resposta gravada é
    `NAO_SEI` (`collection.respostas.NAO_SEI`), e é `montar_divida` quem
    precisa traduzir para `DESCONHECIDO` (`engine.tipos.DESCONHECIDO`) —
    exatamente a tradução central de `app/montagem/estado.py::
    _ou_desconhecido` (RF-12)."""
    return caso_completo(
        valores_divida={
            "SALDO_DEVEDOR_ATUAL": NaoSei.NAO_SEI,
            "PAGAMENTO_MENSAL_EFETIVO": NaoSei.NAO_SEI,
        }
    )
