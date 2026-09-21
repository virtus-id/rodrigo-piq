"""Invariante `GAB-04` do modo estabilização — RF-15 · `AC-11` · `EC-10` ·
`T-74` (tarefa do backlog).

`GAB-04` (`specs/motor-calculo.spec.md` `AC-11`): mesmo cenário numérico de
`GAB-A`/`EC-10` (renda 8.000, despesas operacionais 6.500, despesas
não-mensais 500, D001 devido 1.200/efetivo 0, D002 devido 800/efetivo 800 —
`RESULTADO_CAIXA_OBSERVADO = +200`, `RESULTADO_MENSAL_ATUAL = -1.000`,
`MODO_ESTABILIZACAO = SIM`), visto pela lente da SAÍDA COMPLETA do motor
(`SnapshotOrdem`, via `calcular_plano`, T-68) em vez de só o `Diagnostico`
isolado (já coberto por `test_gabarito_a_deficit.py`, `AC-05`). A spec
canônica não define um gabarito numérico adicional para `GAB-04` — `RF-15`
(`specs/motor-calculo.spec.md` linha 62) e `EC-10` (linha 233) apontam
`GAB-04` para o MESMO cenário de `GAB-A`; `AC-11` é o capítulo de saída/
relatório desse cenário, não um cenário numérico novo.

O invariante a provar, conforme `AC-11`:

    - os R$ 200 observados NUNCA são rotulados/tratados como "sobra" ou
      "capacidade de ataque" disponível — o motor não finge capacidade real
      de atacar dívidas quando está em modo estabilização;
    - os cenários (Avalanche/Bola de Neve/Híbrido) ainda são CALCULADOS
      normalmente — o motor não "desiste" de calcular por estar em modo
      estabilização.

**Lacuna de contrato identificada — sem correção nesta tarefa.** `AC-11`
também pede que "método, ordem e cronograma aparecem como fase 2 condicional
à estabilização". Investigação (ver `engine/motor.py`, docstring do passo 5;
`plans/motor-calculo.plan.md` §5 passo 5 e §8, linha "Modo estabilização"):
o PRÓPRIO plano técnico atribui essa rotulagem — "marcados condicionais é
responsabilidade do `report/`" — a um slug FORA do escopo de `motor-calculo`.
Nenhum campo hoje existente em `Cenario` (`engine/ciclo_mensal.py`),
`SnapshotOrdem` (`engine/snapshot.py`) ou `STATUS_METODO` (`engine/tipos.py`,
que só tem `DEFINITIVO_NA_DATA`/`PROVISORIO`) carrega uma classificação
"condicional à estabilização" — `Cenario.ESTOUROU_HORIZONTE` é um sinal
CONDICIONAL diferente (estouro do horizonte de simulação, `EC-13`), não
relacionado a `MODO_ESTABILIZACAO`. Adicionar esse campo seria mudança de
contrato em módulos já fechados por tarefas anteriores (`T-46`, `T-63`,
`T-67`, `T-68`, todas com testes de gabarito/regra aprovados) — fora do
escopo de uma tarefa de TESTE (`T-74`). Por isso este arquivo prova o
invariante estrutural inteiramente com o contrato JÁ EXISTENTE:
`Diagnostico.MODO_ESTABILIZACAO` (`RF-15`, já implementado em `T-23`) é o
único sinal formal que a saída do motor carrega hoje para indicar que o
resultado é condicional à estabilização — o teste comprova que ele está
presente e correto no `SnapshotOrdem`, e reporta esta lacuna explicitamente
(ver relatório da tarefa) em vez de inventar uma implementação nova.

`_estado_gab04`: mesma carteira de `GAB-A` (`tests/fixtures/gab_a.json`),
mas com `SALDO_DEVEDOR_ATUAL`/taxa conhecidos nas duas dívidas — a fixture
de `GAB-A` original deixa esses campos `DESCONHECIDO` (o gabarito foca só em
diagnóstico financeiro), o que impediria `calcular_plano` de simular os
cenários ponta a ponta (RF-16, `ValueError` de `engine/ciclo_mensal.py`).
Preencher esses dois campos não normativos de `GAB-A`/`GAB-04` com valores
sintéticos plausíveis é o mesmo tipo de "preenchimento de fixture" já
documentado em `tests/fixtures/gab_a.json` (`_SALDO_DEVEDOR_ATUAL_
preenchimento_fixture`) — necessário para exercitar o motor por inteiro, sem
alterar nenhum dos oito valores normativos de `AC-05`/`GAB-A`.

REGRAS: RF-15, AC-11, EC-10
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
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato

# Termos que jamais podem rotular o observado positivo de GAB-04 — AC-11.
_ROTULOS_PROIBIDOS = ("SOBRA", "SUPERAVIT", "SUPERÁVIT")


def _divida_devido_sem_pagamento() -> Divida:
    """D001 de `GAB-A`/`GAB-04`: devido 1.200, efetivo 0 (parcela contratual
    que não está sendo paga de fato — `AC-32`). `SALDO_DEVEDOR_ATUAL`/taxa
    são preenchimento de fixture (não normativos em `GAB-A`, ver docstring
    do módulo) — só o suficiente para `calcular_plano` simular por inteiro.
    """
    return Divida(
        DIVIDA_ID="D001",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("24000"),
        VALOR_QUITACAO_HOJE=dinheiro("24000"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("1200"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("0"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _divida_paga_em_dia() -> Divida:
    """D002 de `GAB-A`/`GAB-04`: devido 800, efetivo 800 (paga integralmente)."""
    return Divida(
        DIVIDA_ID="D002",
        TIPO_DIVIDA=TIPO_DIVIDA.PESSOAL,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=dinheiro("9600"),
        VALOR_QUITACAO_HOJE=dinheiro("9600"),
        QUITACAO_CONSULTADA=SimNaoTalvez.NAO,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.02"),
        CET=dinheiro("0.02"),
        PARCELA_CONTRATUAL=dinheiro("800"),
        PAGAMENTO_MENSAL_EFETIVO=dinheiro("800"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=dinheiro("0"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


def _estado_gab04() -> EstadoFinanceiro:
    """Reproduz `GAB-A`/`GAB-04` (renda 8.000, despesas 6.500+500,
    `CAPACIDADE_ATAQUE_DECLARADA = 0`) com saldo/taxa conhecidos, para que
    `calcular_plano` simule os três cenários por inteiro em vez de bloquear
    por dado ausente (`GAB-03`, assunto de outro invariante)."""
    perfil = PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS.MAIORIA,
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO.SEMANAL,
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO.MESMO_DIA,
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS.MAIORIA,
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO.QUASE_TOTAL,
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO.RAZOAVEL,
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS.RARAMENTE,
        REVISAO_SEMANAL=REVISAO_SEMANAL.MAIORIA,
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
        DATA_REFERENCIA=date(2026, 9, 1),
        RENDA_TOTAL_RECORRENTE=dinheiro("8000"),
        TIPO_RENDA=_TIPO_RENDA.FIXA,
        DESPESAS_OPERACIONAIS_ATUAIS=dinheiro("6500"),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=dinheiro("500"),
        CAPACIDADE_ATAQUE_DECLARADA=dinheiro("0"),
        ECONOMIA_POTENCIAL_IMEDIATA=dinheiro("0"),
        INVENTARIO_COMPLETO=True,
        dividas=(_divida_devido_sem_pagamento(), _divida_paga_em_dia()),
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


def _textos_da_ordem(snapshot: object) -> tuple[str, ...]:
    """Todo texto livre rotulável da saída — `JUSTIFICATIVA_POSICAO` de cada
    posição publicada e `descricao` de cada `AcaoRequerida` da fila paralela
    `ORDEM_ACOES` — o universo de campos onde a palavra "sobra" poderia
    vazar para o usuário."""
    textos: list[str] = []
    for posicao in snapshot.ORDEM_QUITACAO:  # type: ignore[attr-defined]
        textos.append(posicao.JUSTIFICATIVA_POSICAO)
    for acao in snapshot.ORDEM_ACOES:  # type: ignore[attr-defined]
        textos.append(acao.descricao)
    return tuple(textos)


@pytest.mark.invariante
def test_invariante_gab04_estabilizacao() -> None:
    """`AC-11`/`GAB-04`: em modo estabilização, os R$ 200 observados nunca
    são rotulados como sobra/capacidade, e os cenários continuam sendo
    calculados (não abortados) mesmo com `CAPACIDADE_ATAQUE_ATUAL = 0`.

    Roda `calcular_plano` (T-68, ponto de entrada único) por inteiro sobre
    `GAB-04` e confere o invariante em três frentes:

    1. `MODO_ESTABILIZACAO = SIM` e `CAPACIDADE_ATAQUE_ATUAL = 0` — o
       observado positivo (+200) nunca vira capacidade de ataque real
       (`EC-10`).
    2. Nenhum campo textual da ordem publicada (`JUSTIFICATIVA_POSICAO`,
       `ORDEM_ACOES[].descricao`) contém "sobra"/"superávit" — os R$ 200
       nunca são apresentados como se fossem margem disponível.
    3. Os três cenários (Avalanche/Bola de Neve/Híbrido, quando aplicável)
       existem no snapshot com dados completos — o motor não "desiste" de
       calcular por estar em modo estabilização.
    """
    estado = _estado_gab04()
    parametros = FonteParametrosArquivo().carregar("1.0.1")

    snapshot = calcular_plano(estado, parametros)

    # --- Frente 1: diagnóstico — os oito valores de AC-05/GAB-A, aqui via
    # snapshot completo em vez de calcular_diagnostico isolado -------------
    diagnostico = snapshot.diagnostico
    assertar_exato(diagnostico.PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES, dinheiro("2000"))
    assertar_exato(diagnostico.PAGAMENTOS_EFETIVOS_DIVIDAS, dinheiro("800"))
    assertar_exato(diagnostico.RESULTADO_CAIXA_OBSERVADO, dinheiro("200"))
    assertar_exato(diagnostico.RESULTADO_MENSAL_ATUAL, dinheiro("-1000"))
    assertar_exato(diagnostico.MODO_ESTABILIZACAO, True)
    assertar_exato(diagnostico.CAPACIDADE_ATAQUE_ATUAL, dinheiro("0"))
    # RF-15/EC-10: o observado positivo (+200) nunca é o que alimenta o
    # cronograma. CAPACIDADE_ATAQUE_CONSERVADORA é a única capacidade que
    # alimenta o cronograma-base (AC-07); em modo estabilização ela reflete
    # o déficit estrutural (MIN(RESULTADO_MENSAL_ATUAL; DECLARADA), sem
    # MAX(0, ...) — nota de design em engine/diagnostico.py::Capacidades) e
    # por isso é negativa/zero aqui, NUNCA positiva nem igual aos 200
    # observados — provando que o "falso superávit" não vira capacidade.
    assert diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA <= dinheiro("0"), (
        "CAPACIDADE_ATAQUE_CONSERVADORA positiva em modo estabilização "
        "sugeriria capacidade real de ataque a partir do observado (AC-11)"
    )
    assert diagnostico.CAPACIDADE_ATAQUE_ATUAL != diagnostico.RESULTADO_CAIXA_OBSERVADO, (
        "CAPACIDADE_ATAQUE_ATUAL não pode coincidir com o observado positivo "
        "(+200) em modo estabilização — provaria que o motor tratou o "
        "observado como capacidade real (AC-11/EC-10)"
    )
    assert diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA != diagnostico.RESULTADO_CAIXA_OBSERVADO, (
        "CAPACIDADE_ATAQUE_CONSERVADORA não pode coincidir com o observado "
        "positivo (+200) em modo estabilização — mesma prova, na capacidade "
        "que de fato alimenta o cronograma-base (AC-11/EC-10)"
    )

    # --- Frente 2: nenhum campo textual rotula os 200 como sobra ----------
    for texto in _textos_da_ordem(snapshot):
        texto_maiusculo = texto.upper()
        for termo_proibido in _ROTULOS_PROIBIDOS:
            assert termo_proibido not in texto_maiusculo, (
                f"{termo_proibido!r} encontrado em texto da ordem publicada "
                f"({texto!r}) — GAB-04/AC-11 proíbe rotular o observado "
                "positivo de R$ 200 como sobra em modo estabilização"
            )

    # Introspecção estrutural complementar: nenhum campo de primeira classe
    # do Diagnostico se chama "SOBRA"/"SUPERAVIT" — o domínio de saída do
    # motor não tem sequer o VOCABULÁRIO para rotular o observado como tal.
    campos_diagnostico = tuple(type(diagnostico).__dataclass_fields__)
    for campo in campos_diagnostico:
        campo_maiusculo = campo.upper()
        for termo_proibido in _ROTULOS_PROIBIDOS:
            assert termo_proibido not in campo_maiusculo, (
                f"campo {campo!r} de Diagnostico sugere rótulo de {termo_proibido!r} "
                "— GAB-04/AC-11 proíbe essa classificação"
            )

    # --- Frente 3: os cenários são CALCULADOS, não abortados --------------
    # Em modo estabilização o motor continua e devolve os cenários reais —
    # nunca um mapa vazio nem cenários com dados incompletos (docstring de
    # engine/motor.py, passo 5: "o motor CONTINUA e devolve os cenários
    # mesmo em déficit").
    assert snapshot.cenarios, (
        "calcular_plano não produziu nenhum Cenario em modo estabilização — "
        "o motor não pode 'desistir' de calcular (AC-11)"
    )
    for metodo, cenario in snapshot.cenarios.items():
        assertar_exato(cenario.metodo, metodo)
        assert cenario.meses, (
            f"Cenario de {metodo} sem nenhum ResultadoMes simulado — o motor "
            "deve calcular por completo mesmo em modo estabilização (AC-11)"
        )
        assert cenario.PRAZO_TOTAL is not None
        assert cenario.CUSTO_FUTURO_TOTAL is not None
        assert cenario.ORDEM_QUITACAO is not None

    # --- Lacuna documentada: "fase 2 condicional" não tem campo próprio ---
    # AC-11 pede que método, ordem e cronograma apareçam marcados "fase 2
    # condicional à estabilização". O ÚNICO sinal formal que o SnapshotOrdem
    # carrega hoje para essa condição é diagnostico.MODO_ESTABILIZACAO — a
    # rotulagem textual/visual "fase 2 condicional" é responsabilidade do
    # `report/` (plans/motor-calculo.plan.md §5 passo 5, "quem os apresenta
    # como fase 2 é o report/"), fora do escopo deste slug. Este teste prova
    # que o sinal existe, está correto, e chega inalterado até o snapshot
    # final — não que exista uma classificação "condicional" própria em
    # Cenario/STATUS_METODO, que não existe no contrato atual.
    assertar_exato(snapshot.diagnostico.MODO_ESTABILIZACAO, True)
