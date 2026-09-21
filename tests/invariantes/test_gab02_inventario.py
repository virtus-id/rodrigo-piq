"""Invariante `GAB-02` do inventário incompleto — RF-14, RF-16 · `AC-09` ·
`EC-07` · `T-73` (tarefa do backlog).

`GAB-02` (`specs/motor-calculo.spec.md` `AC-09`/`EC-07`): dado
`INVENTARIO_COMPLETO = FALSO`, quando o plano for emitido, os totais saem
marcados como PARCIAIS, `ORDEM_STATUS != DEFINITIVA_NA_DATA` e `STATUS_
METODO` é, no máximo, `PROVISORIO` — nunca `DEFINITIVO_NA_DATA`, mesmo que
todos os cenários calculáveis estejam completos.

Três peças já implementam esta regra, cada uma isolada:

- `engine/diagnostico.py::calcular_pagamentos_e_resultados` (T-20) — soma
  parcial quando há dívida com `PARCELA_CONTRATUAL`/`PAGAMENTO_MENSAL_
  EFETIVO` desconhecidos, sinalizada por `PagamentosEResultados.completo`.
- `engine/status_metodo.py::derivar_STATUS_METODO` (T-60) — `INVENTARIO_
  COMPLETO = False` limita `STATUS_METODO` a `PROVISORIO` no máximo.
- `engine/ordem.py::consolidar_ORDEM_STATUS` (T-64) — a mesma condição
  impede `ORDEM_STATUS = DEFINITIVA_NA_DATA`.

Este arquivo formaliza o invariante COMPOSTO — as três regras ao mesmo tempo
— rodando o motor por inteiro via `calcular_plano` (`engine/motor.py`, T-68)
sobre uma carteira com `EstadoFinanceiro.INVENTARIO_COMPLETO = False`
(dívida com `PARCELA_CONTRATUAL` desconhecida), no local correto
(`tests/invariantes/`, marcador `invariante`).

`INVENTARIO_COMPLETO` é campo de ENTRADA de `EstadoFinanceiro` (booleano
declarado, não recalculado internamente pelo motor — `engine/estado.py`), daí
a montagem abaixo o define explicitamente como `False` na carteira sintética,
condizente com a dívida que carrega um campo material desconhecido.

REGRAS: RF-14, RF-16, AC-09, EC-07
"""

from __future__ import annotations

from datetime import date

import pytest

from engine.diagnostico import PagamentosEResultados, calcular_pagamentos_e_resultados
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
    TIPO_DIVIDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.estado import TIPO_RENDA as _TIPO_RENDA
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    ORDEM_STATUS,
    STATUS_DIVIDA,
    STATUS_METODO,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _divida_completa(divida_id: str) -> Divida:
    """Dívida elegível e simulável, sem nenhum dado ausente — a que garante
    que o motor tenha ao menos um alvo de ataque na ordem-base."""
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("10000"),
        VALOR_QUITACAO_HOJE=dinheiro("10000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("500"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("500"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _divida_com_parcela_desconhecida(divida_id: str) -> Divida:
    """Dívida com `PARCELA_CONTRATUAL` `DESCONHECIDO` — o dado material
    faltante que torna o inventário incompleto (`INVENTARIO_COMPLETO =
    False`, `EC-07`). `SALDO_DEVEDOR_ATUAL`/taxa continuam conhecidos para
    que esta dívida especificamente não caia no Gate 1 por falta de
    `VALOR_RELEVANTE_PARA_QUITACAO` — o ponto deste teste é o inventário
    incompleto (`AC-09`), não a triagem de gate (`GAB-03`, ver
    `test_gab03_rotativo.py`)."""
    return Divida(
        DIVIDA_ID=divida_id,
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("3000"),
        VALOR_QUITACAO_HOJE=dinheiro("3000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=DESCONHECIDO,  # EC-07: dado material faltante
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("200"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _estado_inventario_incompleto() -> EstadoFinanceiro:
    """Carteira sintética com `INVENTARIO_COMPLETO = False` — uma dívida
    completa (garante alvo elegível) e uma com `PARCELA_CONTRATUAL`
    desconhecida (o dado faltante que motiva o inventário incompleto)."""
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
        RENDA_TOTAL_RECORRENTE=dinheiro("6000"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("3000"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("0"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("1000"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=False,  # AC-09/EC-07: núcleo do invariante
        dividas=(
            _divida_completa("D-COMPLETA"),
            _divida_com_parcela_desconhecida("D-PARCIAL"),
        ),
        perfil_comportamental=perfil,
        sinais_comportamentais=sinais,
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.ALTA,
        AUTOPERCEPCAO_CONTROLE=5,
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


@pytest.mark.invariante
def test_invariante_gab02_inventario() -> None:
    """`AC-09`/`EC-07`/`GAB-02`: `INVENTARIO_COMPLETO = FALSO` produz totais
    PARCIAIS, `ORDEM_STATUS != DEFINITIVA_NA_DATA` e `STATUS_METODO` no
    máximo `PROVISORIO` — nunca `DEFINITIVO_NA_DATA`.

    Roda `calcular_plano` (T-68, ponto de entrada único) por inteiro sobre
    a carteira com inventário incompleto e confere os três ângulos do
    invariante composto no `SnapshotOrdem` final.
    """
    estado = _estado_inventario_incompleto()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    # --- Ângulo 1: totais do diagnóstico saem marcados como PARCIAIS -----
    # T-20: PARCELA_CONTRATUAL DESCONHECIDO de D-PARCIAL não entra na soma
    # de PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES — o total é parcial, nunca
    # zero silencioso, e a dívida faltante fica nomeada para auditoria.
    resultado_pagamentos = _recalcular_pagamentos_para_auditoria(estado)
    assert not resultado_pagamentos.completo, (
        "GAB-02/EC-07: inventário com dado material faltante deveria "
        "produzir totais parciais (completo=False)"
    )
    assertar_exato(resultado_pagamentos.dividas_com_devido_desconhecido, ("D-PARCIAL",))
    # A soma devida ignora a dívida faltante (500, só de D-COMPLETA) — nunca
    # estima os 200 do PAGAMENTO_MENSAL_EFETIVO como substituto da parcela
    # desconhecida (RF-16).
    assertar_exato(
        resultado_pagamentos.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES, dinheiro("500")
    )

    # --- Ângulo 2: ORDEM_STATUS nunca DEFINITIVA_NA_DATA ------------------
    assert snapshot.ORDEM_STATUS is not ORDEM_STATUS.DEFINITIVA_NA_DATA, (
        "GAB-02/AC-09: ORDEM_STATUS não pode ser DEFINITIVA_NA_DATA com "
        "INVENTARIO_COMPLETO = False"
    )
    assertar_exato(snapshot.ORDEM_STATUS, ORDEM_STATUS.PROVISORIA)

    # --- Ângulo 3: STATUS_METODO no máximo PROVISORIO ---------------------
    assert snapshot.STATUS_METODO is not STATUS_METODO.DEFINITIVO_NA_DATA, (
        "GAB-02/AC-09: STATUS_METODO não pode ser DEFINITIVO_NA_DATA com "
        "INVENTARIO_COMPLETO = False"
    )
    assertar_exato(snapshot.STATUS_METODO, STATUS_METODO.PROVISORIO)


def _recalcular_pagamentos_para_auditoria(estado: EstadoFinanceiro) -> PagamentosEResultados:
    """Reusa `calcular_pagamentos_e_resultados` (T-20) só para expor, neste
    teste, o sinalizador `completo`/as tuplas de dívidas com dado ausente —
    campos que `Diagnostico`/`SnapshotOrdem` não repassam adiante (ver
    docstring de `Diagnostico`, T-24: só os totais numéricos entram no
    diagnóstico consolidado, não o detalhe de auditoria por dívida). Não
    duplica a fórmula: chama a mesma função pura já usada por `calcular_
    plano` internamente."""
    return calcular_pagamentos_e_resultados(estado)
