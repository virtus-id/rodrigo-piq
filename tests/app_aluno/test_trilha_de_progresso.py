"""Trilha de progresso — `RF-31`, `AC-40`, `EC-14`, T-93.

**Este módulo é deliberadamente mínimo — nunca duplicado.** Os quatro
critérios de aceite de `T-93` já estão provados, ponta a ponta, em duas
suítes irmãs que nasceram junto com a implementação que consomem:

- `tests/app_aluno/test_consulta_trilha_de_progresso.py` (T-92,
  `app/casos/progresso.py::consultar_trilha_de_progresso`):
    - `test_ac40_conjunto_de_casos_em_estados_diferentes_reporta_estado_e_data`
      — **critério 1** (`AC-40`): quatro casos reais, em quatro estados do
      plano §4.3 (`CADASTRADO`, `COLETA_INICIAL`, `CALCULANDO`,
      `AGUARDANDO_REVISAO`), cada um reportando seu próprio `estado` e sua
      própria `ultima_interacao_em`, sem mistura entre casos.
    - `test_relato_de_progresso_so_declara_campos_estruturais` e
      `test_relato_de_progresso_nao_carrega_valor_de_resposta` —
      **critério 3**: `RelatoDeProgresso` tem exatamente cinco campos
      estruturais (auditoria por assinatura de `__slots__`) e nenhum valor de
      resposta concreto (`Decimal`/texto de formulário) atravessa a consulta,
      mesmo com respostas de valor monetário gravadas no caso.
    - `test_proxima_pergunta_do_relato_e_identica_a_retomada_de_t45` e
      `test_aguardando_revisao_true_somente_no_estado_correspondente` —
      cobertura complementar de onde o caso parou e do sinalizador de
      revisão, ambos parte do mesmo relato de `AC-40`.

- `tests/app_aluno/test_transicionar_e_registrar.py` (T-91,
  `app/casos/progresso.py::transicionar_e_registrar` +
  `persistencia/app_aluno/eventos.py`):
    - `test_ec14_caso_parado_ha_meses_continua_retomavel_com_todas_as_
      respostas` — **critério 2** (`EC-14`): um caso cuja última interação
      ocorreu 180 dias antes (1) continua com TODAS as respostas gravadas,
      intactas e legíveis durante o hiato; (2) a trilha de eventos
      (`listar_do_caso`) e `Caso.ultima_interacao_em` marcam a última
      transição e a data exatas — o abandono é OBSERVÁVEL, nunca silencioso;
      (3) uma nova resposta na data de retomada é aceita normalmente e
      atualiza a trilha sozinha — o caso permanece RETOMÁVEL, sem nenhum
      bloqueio imposto pelo hiato.

Este arquivo nasce como o ponto de entrada nomeado que `T-93` pede
(`tests/app_aluno/test_trilha_de_progresso.py`, mesmo precedente de
`tests/app_aluno/integracao/test_revisao_imutavel.py`, T-73) e reafirma a
garantia com testes próprios: um que cita `AC-40` no nome (rastreabilidade
exigida por `sdd.config.md` §5, independentemente de a lógica já estar
majoritariamente provada alhures) e um de sanidade que confirma que as duas
suítes irmãs continuam existindo e cobrindo os quatro critérios — para que
apagar qualquer uma delas por engano quebre este teste também, em vez de
deixar `AC-40`/`EC-14` silenciosamente descobertos.

REGRAS: `RF-31`, `AC-40`, `EC-14`
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.casos.maquina import ESTADO_CASO, Caso
from app.casos.progresso import RelatoDeProgresso, consultar_trilha_de_progresso
from collection.respostas import RespostasCaso


def _caso_parado(ultima_interacao_em: datetime) -> Caso:
    return Caso(
        CASO_ID="CASO-T93-PARADO",
        conta_id="conta-teste-t93",
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=ultima_interacao_em.date(),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=ultima_interacao_em,
        criado_em=ultima_interacao_em,
    )


def test_ac40_relato_de_um_caso_parado_reporta_estado_e_data_da_ultima_interacao() -> None:
    """`AC-40`: um caso cuja última interação ficou há meses reporta, na
    trilha, exatamente o `estado` corrente e a `ultima_interacao_em`
    gravados — nenhum recálculo, nenhuma segunda fonte de verdade. Prova
    própria deste arquivo, complementar aos quatro estados já cobertos em
    `test_consulta_trilha_de_progresso.py::
    test_ac40_conjunto_de_casos_em_estados_diferentes_reporta_estado_e_data`."""
    ultima_interacao = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
    caso = _caso_parado(ultima_interacao)

    relato = consultar_trilha_de_progresso(caso, (), RespostasCaso(respostas=()))

    assert isinstance(relato, RelatoDeProgresso)
    assert relato.CASO_ID == "CASO-T93-PARADO"
    assert relato.estado is ESTADO_CASO.COLETA_INICIAL
    assert relato.ultima_interacao_em == ultima_interacao
    # Critério 3 — nenhum valor monetário na saída: repr do relato não
    # carrega dado de formulário, só os cinco campos estruturais.
    assert "R$" not in repr(relato)


def test_cobertura_completa_de_ac40_e_ec14_vive_nas_suites_irmas() -> None:
    """Sanidade: os testes que provam `AC-40` (quatro estados, campos
    estruturais, ausência de dado financeiro) e `EC-14` (caso parado há
    meses, retomável, com data e trilha observáveis) continuam existindo nas
    duas suítes irmãs — apagar qualquer uma delas por engano quebra este
    teste também, em vez de deixar os critérios silenciosamente sem
    cobertura."""
    from tests.app_aluno import test_consulta_trilha_de_progresso as suite_t92
    from tests.app_aluno import test_transicionar_e_registrar as suite_t91

    assert hasattr(
        suite_t92,
        "test_ac40_conjunto_de_casos_em_estados_diferentes_reporta_estado_e_data",
    )
    assert hasattr(suite_t92, "test_relato_de_progresso_so_declara_campos_estruturais")
    assert hasattr(suite_t92, "test_relato_de_progresso_nao_carrega_valor_de_resposta")
    assert hasattr(
        suite_t91,
        "test_ec14_caso_parado_ha_meses_continua_retomavel_com_todas_as_respostas",
    )
