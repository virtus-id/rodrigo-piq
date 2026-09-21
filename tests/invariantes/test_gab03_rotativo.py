"""Invariante `GAB-03` da dívida rotativa sem saldo/pagamento — RF-14, RF-16
· `AC-10` · `EC-06` · `T-73` (tarefa do backlog) · `AC-58` (`T-87`, reexecução
obrigatória).

`GAB-03` (`specs/motor-calculo.spec.md` `AC-10`/`EC-06`): dívida rotativa
(cartão de crédito) com saldo e pagamento DESCONHECIDOS, quando o motor
processar, a dívida é marcada `INFORMACAO_PENDENTE`, sua trajetória fica
`BLOQUEADO`, e NENHUM valor é estimado.

**Atualização `T-87` (`RF-32`/`AC-58`).** Antes de `T-87`, `aplicar_gate_1_
informacao` devolvia `acao=None` nos dois ramos de bloqueio — este teste
provava isso explicitamente (`resultado_bloqueio.acao is None`). `T-87` faz
o Gate 1 passar a construir `AcaoRequerida` (`TIPO_ACAO="INFORMACAO"`,
`CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"`, o ramo exato deste cenário — saldo
desconhecido, não `STATUS_DIVIDA` inválido) nos dois ramos. A asserção deste
arquivo foi invertida de propósito, com tolerância zero: `resultado_bloqueio.
acao` não é mais `None`, e `ORDEM_ACOES` (via `particionar_elegibilidade`)
passa a conter essa `AcaoRequerida`, em vez de ficar vazia.

**Onde a "trajetória `BLOQUEADO`" aparece no motor de fato.** Não existe um
membro de enum literal `"BLOQUEADO"` no motor — o comportamento observável
equivalente é a composição de três garantias já implementadas em módulos
distintos:

1. `engine/valor_quitacao.py::compor_VALOR_RELEVANTE_PARA_QUITACAO` (T-27):
   `SALDO_DEVEDOR_ATUAL = DESCONHECIDO` e nenhuma quitação vigente confirmada
   produz `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` (`AC-21`).
2. `engine/gates.py::aplicar_gate_1_informacao` (T-29): `VALOR_RELEVANTE_
   PARA_QUITACAO = DESCONHECIDO` bloqueia a dívida no Gate 1 —
   `DIVIDA_STATUS_ESTRATEGICO = INFORMACAO_PENDENTE`, `GATE_PENDENTE =
   INFORMACAO`, `DIVIDA_ELEGIVEL_ORDEM = False`. A dívida nunca entra em
   `ParticaoElegibilidade.elegiveis` — só em `bloqueadas`.
3. `engine/ciclo_mensal.py::simular_cenario` (T-46) só simula o subconjunto
   `elegiveis`: uma dívida bloqueada pelo Gate 1 nunca chega a ter uma
   trajetória simulada — nunca aparece em `Cenario.ORDEM_QUITACAO`, nunca
   recebe ataque, nunca amortiza. É essa AUSÊNCIA TOTAL de trajetória —
   nunca uma trajetória com números fabricados — que representa
   "`BLOQUEADO`" na saída observável do motor: o oposto de "estimar um
   valor" seria simular com um saldo inventado, o que RF-16 proíbe. A
   trajetória bloqueada é, por construção, a trajetória que NUNCA RODA.

Este arquivo prova o invariante composto rodando o motor por inteiro via
`calcular_plano` (`engine/motor.py`, T-68, ponto de entrada único) sobre uma
carteira cuja ÚNICA dívida é um cartão rotativo sem saldo nem pagamento
conhecidos — no local correto (`tests/invariantes/`, marcador `invariante`).

REGRAS: RF-14, RF-16, AC-10, EC-06
"""

from __future__ import annotations

from datetime import date

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
from engine.gates import particionar_elegibilidade
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    DIVIDA_STATUS_ESTRATEGICO,
    GATE_PENDENTE,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato


def _divida_rotativa_sem_dados() -> Divida:
    """Cartão de crédito rotativo (`TIPO_DIVIDA.CARTAO_ROTATIVO`) sem saldo
    nem pagamento conhecidos — `SALDO_DEVEDOR_ATUAL`, `VALOR_QUITACAO_HOJE`,
    `TAXA_EFETIVA_MENSAL_NORMALIZADA`, `CET`, `PARCELA_CONTRATUAL` e
    `PAGAMENTO_MENSAL_EFETIVO` todos `DESCONHECIDO` — o cenário normativo de
    `GAB-03`/`EC-06`: "dívida rotativa sem saldo e sem parcela conhecidos"."""
    return Divida(
        DIVIDA_ID="D-ROTATIVO",
        TIPO_DIVIDA=TIPO_DIVIDA.CARTAO_ROTATIVO,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=DESCONHECIDO,
        VALOR_QUITACAO_HOJE=DESCONHECIDO,
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=DESCONHECIDO,
        CET=DESCONHECIDO,
        PARCELA_CONTRATUAL=DESCONHECIDO,
        PAGAMENTO_MENSAL_EFETIVO=DESCONHECIDO,
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=DESCONHECIDO,
        PESO_EMOCIONAL=DESCONHECIDO,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _estado_com_rotativo_sem_dados() -> EstadoFinanceiro:
    """Carteira cuja única dívida é o cartão rotativo sem dados — carteira
    intencionalmente sem nenhuma outra dívida elegível, para que o
    invariante fique nítido: nenhum alvo é fabricado no lugar da que está
    bloqueada."""
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
        INVENTARIO_COMPLETO=False,  # a própria dívida rotativa é o dado faltante
        dividas=(_divida_rotativa_sem_dados(),),
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
def test_invariante_gab03_rotativo() -> None:
    """`AC-10`/`EC-06`/`GAB-03`: dívida rotativa sem saldo nem pagamento
    conhecidos é marcada `INFORMACAO_PENDENTE`, sua trajetória fica
    `BLOQUEADO` (nunca simulada, nunca aparece em `ORDEM_QUITACAO`), e
    nenhum valor é estimado para preencher a lacuna.

    Três ângulos do mesmo invariante:

    1. Gate 1 marca a dívida `INFORMACAO_PENDENTE`/`GATE_PENDENTE =
       INFORMACAO`, `DIVIDA_ELEGIVEL_ORDEM = False` — nunca entra em
       `elegiveis`.
    2. "Trajetória `BLOQUEADO`" — a dívida NUNCA aparece em `Cenario.
       ORDEM_QUITACAO` de nenhum método (Avalanche/Bola de Neve) do
       `SnapshotOrdem` final: ela nunca é simulada, nunca recebe ataque.
    3. Nenhum valor é estimado: o `motivo` do bloqueio é textual e
       auditável, e nenhum campo monetário da dívida é preenchido com um
       "chute" para forçar um cálculo — os campos permanecem `DESCONHECIDO`
       exatamente como declarados na entrada.
    """
    estado = _estado_com_rotativo_sem_dados()
    (divida,) = estado.dividas
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    # --- Ângulo 1: INFORMACAO_PENDENTE, GATE_PENDENTE = INFORMACAO -------
    particao = particionar_elegibilidade(estado.dividas)
    assertar_exato(particao.elegiveis, ())
    (resultado_bloqueio,) = particao.bloqueadas
    assertar_exato(resultado_bloqueio.DIVIDA_ID, "D-ROTATIVO")
    assertar_exato(
        resultado_bloqueio.DIVIDA_STATUS_ESTRATEGICO,
        DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
    )
    assertar_exato(resultado_bloqueio.GATE_PENDENTE, GATE_PENDENTE.INFORMACAO)
    assertar_exato(resultado_bloqueio.DIVIDA_ELEGIVEL_ORDEM, False)
    assertar_exato(resultado_bloqueio.gate_bloqueador, 1)

    # --- Ângulo 2: trajetória BLOQUEADO — nunca simulada, nunca na ordem -
    assertar_exato(snapshot.ORDEM_QUITACAO, ())
    assertar_exato(snapshot.DIVIDA_ALVO_ATUAL, None)
    for cenario in snapshot.cenarios.values():
        assert "D-ROTATIVO" not in cenario.ORDEM_QUITACAO, (
            "GAB-03/EC-06: dívida rotativa sem dados nunca pode aparecer "
            "simulada em ORDEM_QUITACAO de nenhum método — trajetória "
            "deveria estar BLOQUEADO"
        )
        assertar_exato(cenario.ORDEM_QUITACAO, ())

    # --- Ângulo 3: nenhum valor estimado ----------------------------------
    # Os campos que faltavam na entrada continuam DESCONHECIDO depois de
    # todo o cálculo — nenhum "chute" foi produzido para a dívida em
    # nenhum lugar do motor (frozen=True/slots=True já impediria mutação;
    # aqui confirmamos que os valores permanecem os originais).
    assertar_exato(divida.SALDO_DEVEDOR_ATUAL, DESCONHECIDO)
    assertar_exato(divida.PARCELA_CONTRATUAL, DESCONHECIDO)
    assertar_exato(divida.PAGAMENTO_MENSAL_EFETIVO, DESCONHECIDO)
    assertar_exato(divida.TAXA_EFETIVA_MENSAL_NORMALIZADA, DESCONHECIDO)
    assertar_exato(divida.CET, DESCONHECIDO)
    # O motivo do bloqueio é texto de auditoria — nunca um valor monetário
    # substituto embutido na string como se fosse um dado calculado.
    assert "DESCONHECIDO" in resultado_bloqueio.motivo

    # --- Ângulo 4 (T-87/RF-32/AC-58): Gate 1 agora emite AcaoRequerida -----
    # SALDO_DEVEDOR_ATUAL is DESCONHECIDO é exatamente o ramo 2 do Gate 1
    # (não STATUS_DIVIDA == QUITADA_A_CONFIRMAR, que é o ramo 1) — a
    # AcaoRequerida correspondente marca CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL".
    assert resultado_bloqueio.acao is not None, (
        "T-87: Gate 1 passa a emitir AcaoRequerida nos dois ramos de "
        "bloqueio (RF-32) — este cenário (saldo desconhecido) não pode mais "
        "produzir acao=None"
    )
    assertar_exato(resultado_bloqueio.acao.TIPO_ACAO, "INFORMACAO")
    assertar_exato(resultado_bloqueio.acao.CAMPO_PENDENTE, "SALDO_DEVEDOR_ATUAL")
    assertar_exato(resultado_bloqueio.acao.gate_origem, 1)
    assertar_exato(resultado_bloqueio.acao.DIVIDA_ID, "D-ROTATIVO")
    assertar_exato(resultado_bloqueio.acao.ACAO_ID, "D-ROTATIVO:INFORMACAO")

    # ORDEM_ACOES (fila paralela) reflete a AcaoRequerida agora emitida —
    # antes de T-87 vinha vazia (só Gates 2/3 geravam ação); AC-58 exige
    # tolerância zero na comparação.
    assertar_exato(len(particao.ORDEM_ACOES), 1)
    assertar_exato(particao.ORDEM_ACOES[0].ACAO_ID, "D-ROTATIVO:INFORMACAO")
    assertar_exato(particao.ORDEM_ACOES[0].CAMPO_PENDENTE, "SALDO_DEVEDOR_ATUAL")
