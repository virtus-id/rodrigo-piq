"""Invariante `GAB-01` do seguro embutido — RF-14, RF-16 · `AC-08` · `EC-12` ·
`T-73` (tarefa do backlog).

`GAB-01` (`specs/motor-calculo.spec.md` `AC-08`/`EC-12`): parcela de R$ 1.000
com seguro de R$ 50 já incluído, quando o pagamento mensal for computado,
permanece R$ 1.000 e nunca vira R$ 1.050. O seguro embutido é apenas
informacional (`SEGURO_INCLUIDO_PARCELA`/`CUSTO_SEGURO`, `engine/estado.py`)
— `CUSTO_SEGURO` NUNCA é somado de novo à parcela, porque quando o seguro
está incluído ele já compõe `PARCELA_CONTRATUAL`/`PAGAMENTO_MENSAL_EFETIVO`
na origem (o dado coletado). Somar de novo duplicaria o custo.

`engine/diagnostico.py::calcular_pagamentos_e_resultados` (T-20) já implementa
esta regra e é ad-hoc verificada em `tests/regras/test_diagnostico.py`; este
arquivo formaliza o mesmo invariante no local correto (`tests/invariantes/`,
marcador `invariante`), rodando o motor **por inteiro** via `calcular_plano`
(`engine/motor.py`, T-68, ponto de entrada único) — não apenas a função
isolada de diagnóstico — para provar que o valor permanece 1.000 do início ao
fim de todo o cálculo, não só num único módulo interno.

`_estado_com_seguro_embutido`: carteira sintética mínima com uma única dívida
`ATIVA`, `SALDO_DEVEDOR_ATUAL`/taxa/pagamento conhecidos (para que o motor
consiga simular por completo, sem cair em `INFORMACAO_PENDENTE` por dado
ausente — isso é assunto de `GAB-03`/`test_gab03_rotativo.py`, não deste
teste), `PARCELA_CONTRATUAL = PAGAMENTO_MENSAL_EFETIVO = 1.000`,
`SEGURO_INCLUIDO_PARCELA = True`, `CUSTO_SEGURO = 50`.

REGRAS: RF-14, RF-16, AC-08, EC-12
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _divida_com_seguro_embutido() -> Divida:
    """Parcela e pagamento de 1.000, com R$ 50 de seguro JÁ incluído
    (`SEGURO_INCLUIDO_PARCELA = True`, `CUSTO_SEGURO = 50`) — mesma
    montagem normativa de `AC-08`/`EC-12`."""
    return Divida(
        DIVIDA_ID="D-GAB01",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("12000"),
        VALOR_QUITACAO_HOJE=dinheiro("12000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("1000"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("1000"),
        SEGURO_INCLUIDO_PARCELA=True,
        CUSTO_SEGURO=dinheiro("50"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _estado_com_seguro_embutido() -> EstadoFinanceiro:
    """Carteira mínima e completa (sem `DESCONHECIDO` em nenhum campo
    material) — só o suficiente para `calcular_plano` rodar do início ao
    fim sem cair em `INFORMACAO_PENDENTE`, isolando o invariante do seguro."""
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
        RENDA_TOTAL_RECORRENTE=dinheiro("5000"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("2000"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("0"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("500"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(_divida_com_seguro_embutido(),),
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
def test_invariante_gab01_seguro() -> None:
    """`AC-08`/`EC-12`/`GAB-01`: parcela de R$ 1.000 com seguro de R$ 50 já
    incluído permanece R$ 1.000 do início ao fim do cálculo do motor —
    nunca vira R$ 1.050.

    Roda `calcular_plano` (T-68, ponto de entrada único) por inteiro sobre
    a carteira sintética e confere o invariante em DOIS pontos observáveis:

    1. `Diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES`/`PAGAMENTOS_
       EFETIVOS_DIVIDAS` — a soma de UMA dívida com parcela/efetivo 1.000
       é exatamente 1.000, nunca 1.050 (`CUSTO_SEGURO` nunca somado de
       novo, T-20).
    2. O `CUSTO_SEGURO` (50) permanece disponível, intacto e não fundido
       à parcela em nenhum campo do `Divida` de origem — a dívida
       carregada no `EstadoFinanceiro` de entrada nunca é mutada pelo
       motor (`frozen=True, slots=True`, `engine/estado.py`).
    """
    estado = _estado_com_seguro_embutido()
    (divida,) = estado.dividas
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    # --- Ponto 1: diagnóstico consolidado — 1.000, nunca 1.050 -----------
    assertar_exato(
        snapshot.diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES, dinheiro("1000")
    )
    assertar_exato(snapshot.diagnostico.PAGAMENTOS_EFETIVOS_DIVIDAS, dinheiro("1000"))
    assert snapshot.diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES != dinheiro("1050"), (
        "CUSTO_SEGURO foi somado de novo à parcela — GAB-01/AC-08 violado"
    )
    assert snapshot.diagnostico.PAGAMENTOS_EFETIVOS_DIVIDAS != dinheiro("1050"), (
        "CUSTO_SEGURO foi somado de novo ao pagamento efetivo — GAB-01/AC-08 violado"
    )

    # --- Ponto 2: a Divida de entrada não foi mutada pelo motor ----------
    # `frozen=True` já impediria em tempo de execução qualquer tentativa de
    # reatribuir os campos — aqui confirmamos que os valores permanecem os
    # mesmos ORIGINAIS após a execução completa do motor, e que o seguro
    # continua exposto como informação separada, nunca fundido.
    assertar_exato(divida.PARCELA_CONTRATUAL, dinheiro("1000"))
    assertar_exato(divida.PAGAMENTO_MENSAL_EFETIVO, dinheiro("1000"))
    assertar_exato(divida.SEGURO_INCLUIDO_PARCELA, True)
    assertar_exato(divida.CUSTO_SEGURO, dinheiro("50"))

    # Sanidade adicional: o custo do seguro (50) somado à parcela (1.000)
    # daria 1.050 — provando que o valor observado no diagnóstico não é
    # coincidência de arredondamento, e sim ausência estrutural da soma.
    # `DinheiroTalvez` (RF-16) exige narrowing explícito de `DESCONHECIDO`
    # antes de somar — mesmo padrão de exaustividade de `mypy --strict`
    # já exercitado em `engine/diagnostico.py`.
    parcela = divida.PARCELA_CONTRATUAL
    custo_seguro = divida.CUSTO_SEGURO
    assert parcela is not DESCONHECIDO and custo_seguro is not DESCONHECIDO
    assert dinheiro("1000") + Decimal("50") == dinheiro("1050")
    assert snapshot.diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES != (
        parcela + custo_seguro
    )
