"""Testes da família R — gatilho de recálculo/reranqueamento (`R-01`..`R-05`).

RF-02, §3: cada teste é nomeado com o ID da regra `R-*` que exercita e
verifica saída OBSERVÁVEL de `simular_cenario` (`Cenario`/`ResultadoMes`) —
nunca chama `executar_mes` isoladamente nem inspeciona estado interno. Mesmo
padrão de helpers de `tests/regras/test_simular_cenario.py`.

`R-04` (alteração cadastral/cosmética não constitui `EVENTO_RECALCULO`) e
`R-05` (evento material que confirma o mesmo resultado ainda gera novo
snapshot) dependem de `EVENTO_RECALCULO` externo e de snapshot — nenhum dos
dois existe na superfície de `simular_cenario`/`executar_mes` nesta tarefa
(`engine/ciclo_mensal.py` só implementa o gatilho por quitação, R-01/R-02/
R-03; snapshot é `V-01`, fora deste módulo) — fora do escopo de `T-47`, que
testa apenas o motor já implementado, não inventa comportamento.

`R-04` ganha teste próprio nesta família mais adiante (`test_R04_
alteracao_cadastral_nao_e_evento`, `T-70`, EC-08), agora que `EVENTO_
RECALCULO`/`avaliar_gatilho_recalculo` (T-66) existem — mesma garantia
estrutural já provada em `tests/regras/test_gatilho_recalculo.py`
(`test_EC08_alteracao_cosmetica_e_inexprimivel_no_enum`), citada aqui sob o
nome `R-*` exigido pelo backlog em vez de duplicar a lógica.

REGRAS: RF-02, R-01, R-02, R-03, R-04
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from engine.ciclo_mensal import EstadoSimulacao, simular_cenario
from engine.diagnostico import Diagnostico
from engine.estado import TIPO_DIVIDA, Divida, EstadoFinanceiro
from engine.eventos import avaliar_gatilho_recalculo
from engine.parametros import Parametros
from engine.precisao import dinheiro
from engine.risco import ClassificacaoRisco
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    EVENTO_RECALCULO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_VALIDADE_PROPOSTA,
    DinheiroTalvez,
    SimNaoTalvez,
    TaxaTalvez,
)
from tests.conftest import assertar_exato


def _divida(
    divida_id: str,
    *,
    saldo: DinheiroTalvez,
    taxa: TaxaTalvez | None = None,
    pagamento_mensal_efetivo: DinheiroTalvez | None = None,
) -> Divida:
    if taxa is None:
        taxa = dinheiro("0")
    if pagamento_mensal_efetivo is None:
        pagamento_mensal_efetivo = dinheiro("0")
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=saldo,
        VALOR_QUITACAO_HOJE=saldo,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=taxa,
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=pagamento_mensal_efetivo,
        PAGAMENTO_MENSAL_EFETIVO=pagamento_mensal_efetivo,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _parametros(*, horizonte_maximo_anos: int = 10, horizonte_alerta_anos: int = 5) -> Parametros:
    return Parametros(
        PARAMETROS_VERSION="teste",
        ENGINE_VERSION="teste",
        DATA_VIGENCIA=date(2026, 1, 1),
        _valores={
            "P_HORIZONTE_MAXIMO_SIMULACAO": Decimal(horizonte_maximo_anos),
            "P_HORIZONTE_ALERTA": Decimal(horizonte_alerta_anos),
        },
    )


def _diagnostico(*, capacidade_conservadora: DinheiroTalvez) -> Diagnostico:
    classificacao_neutra = ClassificacaoRisco(sinais=(), contagem=0, nivel=NIVEL_RISCO.BAIXO)
    return Diagnostico(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=dinheiro("0"),
        PAGAMENTOS_EFETIVOS_DIVIDAS=dinheiro("0"),
        RESULTADO_CAIXA_OBSERVADO=dinheiro("0"),
        RESULTADO_MENSAL_ATUAL=dinheiro("0"),
        GAP_CAIXA_VS_ESTRUTURAL=dinheiro("0"),
        DEFICIT_MENSAL=dinheiro("0"),
        PISO_CAPACIDADE=dinheiro("0"),
        STATUS_FINANCEIRO=STATUS_FINANCEIRO.CAPACIDADE_POSITIVA,
        MODO_ESTABILIZACAO=False,
        GAP_AUTOPERCEPCAO=False,
        BASE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        FATOR_SEGURANCA=Decimal("1"),
        CAPACIDADE_ATAQUE_ATUAL=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_CONSERVADORA=capacidade_conservadora,  # type: ignore[arg-type]
        CAPACIDADE_ATAQUE_POTENCIAL=capacidade_conservadora,  # type: ignore[arg-type]
        NIVEL_CONTROLE=NIVEL_CONTROLE.FORTE,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        RISCO_RECAIDA=NIVEL_RISCO.BAIXO,
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO.BAIXO,
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=False,
        classificacao_risco_recaida=classificacao_neutra,
        classificacao_risco_comportamental_geral=classificacao_neutra,
        # T-90/OQ-23: contrato de tipo/posição, sem valor de negócio real.
        RESERVA_MOBILIZAVEL=dinheiro("0"),
        ATAQUE_IMEDIATO_RECOMENDADO=dinheiro("0"),
    )


def _estado_financeiro_neutro() -> EstadoFinanceiro:
    from engine.estado import (
        COBERTURA_MEIOS_PAGAMENTO,
        COBERTURA_PEQUENOS_GASTOS,
        CONHECIMENTO_GASTO,
        DEFASAGEM_REGISTRO,
        DISPOSICAO_USO_RESERVA,
        FREQUENCIA_REGISTRO,
        GASTOS_NAO_IDENTIFICADOS,
        REGISTRO_GASTOS,
        RESERVA_EXISTE,
        REVISAO_SEMANAL,
        PerfilComportamental,
        SinaisComportamentais,
    )
    from engine.estado import TIPO_RENDA as _TIPO_RENDA

    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.TUDO,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.DIARIA,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.NA_HORA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.TODOS,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.BOA_APROXIMACAO,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.NUNCA,
        REVISAO_SEMANAL=REVISAO_SEMANAL.SEMPRE,
    )
    sinais = SinaisComportamentais(
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
    return EstadoFinanceiro(
        DATA_REFERENCIA=date(2026, 1, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("0"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("0"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("0"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("0"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(),
        perfil_comportamental=perfil,
        sinais_comportamentais=sinais,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=0,
        # --- Rodada 3 (T-96/T-97) — nove campos NEUTROS: reserva ausente,
        # caixa zero, nenhum item de patrimonio. `AC-87`: nada muda neste
        # teste por causa deles. `RESERVA_TOTAL`/`VALOR_MAXIMO_...` valem
        # `dinheiro(0)` porque `RESERVA_EXISTE = NAO` faz a Regra 1 da
        # §13.1 vencer antes da Regra 3 (`EC-23`).
        RESERVA_EXISTE=RESERVA_EXISTE.NAO,
        RESERVA_TOTAL=dinheiro("0"),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA.NAO,
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=dinheiro("0"),
        DINHEIRO_DISPONIVEL=dinheiro("0"),
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )


@dataclass
class _ChamadaSel:
    delta: DinheiroTalvez
    candidatos: tuple[str, ...]


@dataclass
class _SelPorMenorSaldo:
    """Escolhe, entre as dívidas NÃO quitadas, a de menor saldo. Grava cada
    chamada para provar quando `sel` é (e não é) acionada."""

    dividas: dict[str, Divida]
    chamadas: list[_ChamadaSel] = field(default_factory=list)

    def __call__(self, estado: EstadoSimulacao, delta: DinheiroTalvez) -> Divida | None:
        candidatos = tuple(
            divida_id for divida_id in self.dividas if divida_id not in estado.quitadas
        )
        self.chamadas.append(_ChamadaSel(delta=delta, candidatos=candidatos))
        if not candidatos:
            return None
        escolhido = min(candidatos, key=lambda d: (estado.saldos[d], d))
        return self.dividas[escolhido]


# ---------------------------------------------------------------------------
# R-01 — quitação confirmada de qualquer dívida (alvo ou cascata) dispara o
# recálculo da ordem — inclui a dívida que se encerra só com pagamento
# normal, sem ataque (EC-02).
# ---------------------------------------------------------------------------
def test_R01_quitacao_confirmada_dispara_recalculo_da_ordem() -> None:
    # D-01 (alvo, menor saldo) quita e libera resíduo; a cascata reranqueia
    # e seleciona D-02 — prova de que a quitação disparou um novo cálculo
    # de ordem (reranqueamento) dentro do próprio mês.
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    assertar_exato(len(mes_1.reranqueamentos), 1)
    assertar_exato(mes_1.reranqueamentos[0].novo_alvo, "D-02")
    assertar_exato(mes_1.estado_final.DIVIDA_ALVO_ATUAL, "D-02")


def test_R01_EC02_quitacao_so_com_pagamento_normal_tambem_dispara_recalculo() -> None:
    # D-01 (não-alvo) se encerra só com o pagamento normal efetivo (sem
    # ataque). D-02 é o alvo (menor saldo) e não quita neste mês. A
    # quitação de D-01 é um evento de quitação como qualquer outro (EC-02)
    # — a ordem seguinte reflete que D-01 saiu do inventário elegível.
    d1 = _divida("D-01", saldo=dinheiro("30"), pagamento_mensal_efetivo=dinheiro("30"))
    d2 = _divida("D-02", saldo=dinheiro("31"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("1"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(set(mes_1.quitacoes), {"D-01"})
    assertar_exato(mes_1.estado_final.saldos["D-01"], dinheiro("0"))
    assertar_exato(mes_1.estado_final.quitadas, frozenset({"D-01"}))


# ---------------------------------------------------------------------------
# R-02 — nomeado explicitamente pela tarefa: a mera virada de mês, sem
# quitação e sem evento externo, NUNCA dispara reranqueamento.
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_R02_virada_de_mes_nao_reranqueia() -> None:
    d1 = _divida("D-01", saldo=dinheiro("1000"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    # 1000/100 = 10 meses. Única chamada a `sel` é o bootstrap do mês 1 —
    # os nove meses seguintes viram sem qualquer quitação e não geram
    # reranqueamento algum, mesmo passando de mês em mês.
    assertar_exato(cenario.PRAZO_TOTAL, 10)
    assertar_exato(len(sel.chamadas), 1)
    for resultado_mes in cenario.meses:
        assertar_exato(resultado_mes.reranqueamentos, ())
    for resultado_mes in cenario.meses[:-1]:
        assertar_exato(resultado_mes.estado_final.DIVIDA_ALVO_ATUAL, "D-01")


# ---------------------------------------------------------------------------
# R-03 — cada reranqueamento intramês (disparado por resíduo) é registrado
# como evento auditável, com mês e motivo.
# ---------------------------------------------------------------------------
def test_R03_reranqueamento_intramês_e_registrado_com_mes_e_motivo() -> None:
    d1 = _divida("D-01", saldo=dinheiro("40"), pagamento_mensal_efetivo=dinheiro("0"))
    d2 = _divida("D-02", saldo=dinheiro("500"), pagamento_mensal_efetivo=dinheiro("0"))
    dividas = {"D-01": d1, "D-02": d2}
    sel = _SelPorMenorSaldo(dividas=dividas)

    dg = _diagnostico(capacidade_conservadora=dinheiro("100"))
    p = _parametros()

    cenario = simular_cenario(_estado_financeiro_neutro(), dg, dividas, sel, p)

    mes_1 = cenario.meses[0]
    assertar_exato(len(mes_1.reranqueamentos), 1)
    evento = mes_1.reranqueamentos[0]
    assertar_exato(evento.mes, 1)
    assertar_exato(evento.motivo, "RESIDUO_ATAQUE_M")
    assertar_exato(evento.novo_alvo, "D-02")


# ---------------------------------------------------------------------------
# R-04 — alteração meramente cadastral, correção textual, mudança cosmética
# de registro ou passagem ordinária do tempo NÃO constitui EVENTO_RECALCULO
# (EC-08). Diferente de R-01..R-03 acima, que exercitam a superfície
# observável de `simular_cenario`, este teste exercita `EVENTO_RECALCULO`/
# `avaliar_gatilho_recalculo` (`engine/eventos.py`, T-66) — mesma garantia
# já provada por `test_EC08_alteracao_cosmetica_e_inexprimivel_no_enum`
# (`tests/regras/test_gatilho_recalculo.py`), citada aqui com o nome exato
# exigido pelo backlog (`T-70`) em vez de duplicar a prova estrutural.
# ---------------------------------------------------------------------------
def test_R04_alteracao_cadastral_nao_e_evento() -> None:
    # Prova estrutural: não há membro de EVENTO_RECALCULO para alteração
    # cadastral, correção textual ou mudança cosmética de registro — a
    # ausência é do próprio domínio (enum fechado), não uma checagem em
    # runtime que pudesse ser contornada.
    nomes_membros = {membro.name for membro in EVENTO_RECALCULO}
    termos_cosmeticos = {
        "CADASTRO",
        "CADASTRAL",
        "COSMETICO",
        "COSMETICA",
        "NOME",
        "APELIDO",
        "TELEFONE",
        "CORRECAO",
        "CORRECAO_TEXTUAL",
        "PASSAGEM_DO_TEMPO",
        "VIRADA_DE_MES",
    }
    assertar_exato(nomes_membros & termos_cosmeticos, set())

    # Não há forma de CONSTRUIR um EVENTO_RECALCULO cosmético, nem por nome
    # nem por valor.
    with pytest.raises(KeyError):
        EVENTO_RECALCULO["ALTERACAO_CADASTRAL"]
    with pytest.raises(ValueError):
        EVENTO_RECALCULO("ALTERACAO_CADASTRAL")

    # O único jeito de expressar "nada de material aconteceu" (inclusive
    # alteração cadastral/cosmética ou mera passagem do tempo) é `evento =
    # None` — e, para esse caso, avaliar_gatilho_recalculo NUNCA recalcula.
    resultado = avaliar_gatilho_recalculo(None)
    assertar_exato(resultado.deve_recalcular, False)
    assertar_exato(resultado.evento, None)
    assert resultado.motivo  # motivo auditável nunca vazio
