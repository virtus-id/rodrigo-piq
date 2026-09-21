"""Testes de `engine/ordem.py` — `T-63`, `T-64`, `RF-09`, `RF-21`, `RF-16`,
`Q-01..Q-05`, `AC-09`, `AC-18`, `AC-33`.

Cobre os cinco critérios de aceite de `T-63`:

1. Toda `PosicaoOrdem` tem `JUSTIFICATIVA_POSICAO` não vazia (`Q-05`).
2. `valores_de_apoio` traz números `Decimal`/`Dinheiro` reais, não só texto.
3. A ordem publicada vem de `Cenario.ORDEM_QUITACAO` do método recomendado —
   nunca um ranqueamento recalculado à parte por `engine/ordem.py`.
4. Dívida bloqueada por gate não aparece em `ORDEM_QUITACAO` — vai para
   `ORDEM_ACOES` (checagem defensiva via `ErroOrdemInconsistente`, e caso
   normal via `particionar_elegibilidade`).
5. `JUSTIFICATIVA_POSICAO` é texto técnico/estruturado de auditoria interna,
   não prosa de usuário final (nenhuma dependência de `report/`, que nem
   existe implementado neste projeto).

E os quatro critérios de aceite de `T-64` (`consolidar_ORDEM_STATUS`):

1. `INVENTARIO_COMPLETO = False` ⇒ `ORDEM_STATUS != DEFINITIVA_NA_DATA` (`AC-09`).
2. `origem != SIMULACAO` em qualquer dívida da ordem ⇒ `ORDEM_STATUS = PROVISORIA`
   (`AC-33`), mesmo que só uma dívida entre várias tenha origem de fallback.
3. Os motivos do rebaixamento são acumulados e expostos em `motivos_rebaixamento`.
4. Nenhum rebaixamento é silencioso: toda causa tem motivo nomeado.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.beneficio_marginal import BeneficioMarginal
from engine.ciclo_mensal import Cenario
from engine.estado import TIPO_DIVIDA, Divida
from engine.gates import AcaoRequerida, ParticaoElegibilidade, ResultadoGates
from engine.ordem import (
    ErroOrdemInconsistente,
    PosicaoOrdem,
    ResultadoConsolidacaoOrdemStatus,
    consolidar_ORDEM_STATUS,
    publicar_ORDEM_QUITACAO,
)
from engine.precisao import dinheiro
from engine.tipos import (
    DIVIDA_STATUS_ESTRATEGICO,
    GATE_PENDENTE,
    METODO,
    ORDEM_STATUS,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    SimNaoTalvez,
)
from tests.conftest import assertar_exato


def _divida(**overrides: object) -> Divida:
    """Dívida elegível "neutra" por padrão — mesmo padrão de
    `tests/regras/test_gates.py::_divida`."""
    base: dict[str, object] = dict(
        DIVIDA_ID="D-01",
        TIPO_DIVIDA=TIPO_DIVIDA.CONSIGNADO,
        STATUS_DIVIDA=STATUS_DIVIDA.ATIVA,
        SALDO_DEVEDOR_ATUAL=Decimal("1000.00"),
        VALOR_QUITACAO_HOJE=Decimal("1000.00"),
        QUITACAO_CONSULTADA=SimNaoTalvez.SIM,
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA.VIGENTE,
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.02"),
        CET=Decimal("0.025"),
        PARCELA_CONTRATUAL=Decimal("100.00"),
        PAGAMENTO_MENSAL_EFETIVO=Decimal("100.00"),
        SEGURO_INCLUIDO_PARCELA=False,
        CUSTO_SEGURO=Decimal("0.00"),
        PESO_EMOCIONAL=0,
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )
    base.update(overrides)
    return Divida(**base)  # type: ignore[arg-type]


def _cenario(ordem_quitacao: tuple[str, ...], metodo: METODO = METODO.AVALANCHE) -> Cenario:
    """`Cenario` sintético mínimo — só `ORDEM_QUITACAO` é significativo para
    `publicar_ORDEM_QUITACAO`; o resto é neutro. Mesmo padrão de
    `tests/regras/test_S.py::_cenario`."""
    return Cenario(
        metodo=metodo,
        classificacao=None,
        ORDEM_QUITACAO=ordem_quitacao,
        PRAZO_TOTAL=0,
        CUSTO_FUTURO_TOTAL=Decimal("0"),
        MESES_PRIMEIRA_VITORIA=None,
        meses=(),
        ESTOUROU_HORIZONTE=False,
        MESES_ATE_ALERTA_HORIZONTE=None,
    )


def _particao_sem_bloqueio() -> ParticaoElegibilidade:
    return ParticaoElegibilidade(elegiveis=(), ORDEM_ACOES=(), bloqueadas=())


@pytest.mark.regra
def test_justificativa_posicao_nao_vazia_para_toda_posicao() -> None:
    """Critério de aceite 1 / `Q-05`: `JUSTIFICATIVA_POSICAO` é obrigatória e
    nunca vazia, para cada uma das posições publicadas."""
    d1 = _divida(DIVIDA_ID="D-01")
    d2 = _divida(DIVIDA_ID="D-02")
    dividas = {"D-01": d1, "D-02": d2}
    cenario = _cenario(("D-01", "D-02"), METODO.AVALANCHE)

    resultado = publicar_ORDEM_QUITACAO(
        cenario, METODO.AVALANCHE, dividas, _particao_sem_bloqueio()
    )

    assert len(resultado.ORDEM_QUITACAO) == 2
    for posicao in resultado.ORDEM_QUITACAO:
        assert isinstance(posicao.JUSTIFICATIVA_POSICAO, str)
        assert posicao.JUSTIFICATIVA_POSICAO.strip() != "", (
            f"posição {posicao.posicao} ({posicao.DIVIDA_ID}) com "
            "JUSTIFICATIVA_POSICAO vazia — viola Q-05."
        )


@pytest.mark.regra
def test_valores_de_apoio_traz_numeros_decimal_reais() -> None:
    """Critério de aceite 2: `valores_de_apoio` carrega `Decimal`/`Dinheiro`
    concretos — não apenas uma frase. O revisor deve conseguir refazer a
    conta a partir desses números."""
    d1 = _divida(
        DIVIDA_ID="D-01",
        SALDO_DEVEDOR_ATUAL=Decimal("2500.00"),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=Decimal("0.035"),
    )
    dividas = {"D-01": d1}
    cenario = _cenario(("D-01",), METODO.AVALANCHE)

    resultado = publicar_ORDEM_QUITACAO(
        cenario, METODO.AVALANCHE, dividas, _particao_sem_bloqueio()
    )

    posicao = resultado.ORDEM_QUITACAO[0]
    assert posicao.valores_de_apoio, "valores_de_apoio não pode ser vazio quando há dado conhecido"
    for chave, valor in posicao.valores_de_apoio.items():
        assert isinstance(valor, Decimal), (
            f"valores_de_apoio[{chave!r}] = {valor!r} não é Decimal — critério de aceite 2."
        )
    assertar_exato(posicao.valores_de_apoio["SALDO_DEVEDOR_ATUAL"], Decimal("2500.00"))
    assertar_exato(
        posicao.valores_de_apoio["TAXA_EFETIVA_MENSAL_NORMALIZADA"], Decimal("0.035")
    )
    # AC-19/§11.1: para a Avalanche, a taxa (proxy de custo evitado) e o CET
    # de fallback também compõem os valores de apoio, quando conhecidos.
    assert "CET" in posicao.valores_de_apoio


@pytest.mark.regra
def test_ordem_vem_do_cenario_recomendado_nao_recalcula() -> None:
    """Critério de aceite 3 / `Q-01`/`Q-04`: a ordem publicada é EXATAMENTE
    `Cenario.ORDEM_QUITACAO`, na mesma sequência — mesmo quando essa
    sequência contraria o que um ranqueamento "do zero" pela regra do
    método produziria (aqui: D-02 tem saldo/benefício maiores que D-01, mas
    o cenário já simulado colocou D-02 primeiro por ter quitado antes — o
    módulo não deve "corrigir" essa ordem)."""
    d1 = _divida(DIVIDA_ID="D-01", SALDO_DEVEDOR_ATUAL=Decimal("100.00"))
    d2 = _divida(DIVIDA_ID="D-02", SALDO_DEVEDOR_ATUAL=Decimal("9000.00"))
    dividas = {"D-01": d1, "D-02": d2}
    # Sequência deliberadamente "fora" do que a leitura ingênua de saldo
    # sugeriria — vem pronta do Cenario, ORDEM_QUITACAO é a fonte única.
    cenario = _cenario(("D-02", "D-01"), METODO.BOLA_DE_NEVE)

    resultado = publicar_ORDEM_QUITACAO(
        cenario, METODO.BOLA_DE_NEVE, dividas, _particao_sem_bloqueio()
    )

    assertar_exato(
        tuple(p.DIVIDA_ID for p in resultado.ORDEM_QUITACAO), ("D-02", "D-01")
    )
    assertar_exato(resultado.ORDEM_QUITACAO[0].posicao, 1)
    assertar_exato(resultado.ORDEM_QUITACAO[1].posicao, 2)


@pytest.mark.regra
def test_ordem_quitacao_vazia_quando_cenario_nao_quita_nada() -> None:
    """`Q-01`: se o cenário recomendado não quitou nenhuma dívida (ex.:
    horizonte estourado sem quitação), a ordem publicada é vazia — nenhuma
    dívida é inventada para preenchê-la."""
    cenario = _cenario((), METODO.AVALANCHE)

    resultado = publicar_ORDEM_QUITACAO(cenario, METODO.AVALANCHE, {}, _particao_sem_bloqueio())

    assertar_exato(resultado.ORDEM_QUITACAO, ())


@pytest.mark.regra
def test_dividas_bloqueadas_por_gate_nao_aparecem_e_vao_para_ordem_acoes() -> None:
    """Critério de aceite 4: `ParticaoElegibilidade.ORDEM_ACOES` (fila
    paralela produzida pelos gates) é repassada por `publicar_ORDEM_
    QUITACAO`, e uma dívida bloqueada nunca aparece em `ORDEM_QUITACAO`
    (aqui: o `Cenario` de entrada já só contém a elegível, D-01 — reflete o
    contrato real de `simular_cenario`, que roda sobre `elegiveis`)."""
    elegivel = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": elegivel}
    cenario = _cenario(("D-01",), METODO.AVALANCHE)

    acao = AcaoRequerida(
        # ACAO_ID/TIPO_ACAO provisórios — valor real vem de T-80/T-83
        # (T-79 só estende o shape da dataclass; este teste cobre o
        # repasse de ORDEM_ACOES, não a derivação desses campos).
        ACAO_ID="D-02",
        DIVIDA_ID="D-02",
        TIPO_ACAO="",
        descricao="D-02: RISCO_MATERIAL_IMINENTE = True — ação necessária antes do ataque.",
        gate_origem=2,
        # T-133 (RF-61/RF-62 · §14.2.1): Gate 2 sem oferta de valor
        # conhecida neste ponto — dinheiro(0), mesmo raciocínio do ponto de
        # construção real em engine/gates.py.
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
        prioridade_excepcional=False,
    )
    resultado_gate_bloqueio = ResultadoGates(
        DIVIDA_ID="D-02",
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INTERVENCAO_PENDENTE,
        GATE_PENDENTE=GATE_PENDENTE.CONTENCAO_RISCO,
        DIVIDA_ELEGIVEL_ORDEM=False,
        gate_bloqueador=2,
        motivo=acao.descricao,
        acao=acao,
    )
    particao = ParticaoElegibilidade(
        elegiveis=(elegivel,),
        ORDEM_ACOES=(acao,),
        bloqueadas=(resultado_gate_bloqueio,),
    )

    resultado = publicar_ORDEM_QUITACAO(cenario, METODO.AVALANCHE, dividas, particao)

    ids_publicados = {p.DIVIDA_ID for p in resultado.ORDEM_QUITACAO}
    assert "D-02" not in ids_publicados, (
        "dívida bloqueada por gate não pode estar em ORDEM_QUITACAO"
    )
    assertar_exato(resultado.ORDEM_ACOES, (acao,))
    assertar_exato([a.DIVIDA_ID for a in resultado.ORDEM_ACOES], ["D-02"])


@pytest.mark.regra
def test_dividida_bloqueada_no_cenario_levanta_erro_defensivo() -> None:
    """Critério de aceite 4, camada defensiva: se por inconsistência do
    chamador `Cenario.ORDEM_QUITACAO` contiver um `DIVIDA_ID` também
    presente em `bloqueadas`, `publicar_ORDEM_QUITACAO` recusa publicar —
    erro ruidoso (`ErroOrdemInconsistente`), nunca silencioso."""
    d1 = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": d1}
    # Inconsistência deliberada: D-01 aparece como quitada no cenário, mas
    # também está listada como bloqueada — nunca deveria acontecer em uso
    # normal (simular_cenario já filtra por elegíveis).
    cenario = _cenario(("D-01",), METODO.AVALANCHE)

    resultado_gate_bloqueio = ResultadoGates(
        DIVIDA_ID="D-01",
        DIVIDA_STATUS_ESTRATEGICO=DIVIDA_STATUS_ESTRATEGICO.INFORMACAO_PENDENTE,
        GATE_PENDENTE=GATE_PENDENTE.INFORMACAO,
        DIVIDA_ELEGIVEL_ORDEM=False,
        gate_bloqueador=1,
        motivo="D-01: VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO.",
        acao=None,
    )
    particao = ParticaoElegibilidade(
        elegiveis=(), ORDEM_ACOES=(), bloqueadas=(resultado_gate_bloqueio,)
    )

    with pytest.raises(ErroOrdemInconsistente):
        publicar_ORDEM_QUITACAO(cenario, METODO.AVALANCHE, dividas, particao)


@pytest.mark.regra
def test_justificativa_e_texto_tecnico_nao_prosa_de_usuario_final() -> None:
    """Critério de aceite 5: `JUSTIFICATIVA_POSICAO` cita o vocabulário
    técnico da spec (posição numérica, DIVIDA_ID, METODO, o ID normativo do
    critério) — não é texto de apresentação ao usuário final, que é escopo
    de um módulo `relatorio/` futuro, ainda não implementado."""
    d1 = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": d1}
    cenario = _cenario(("D-01",), METODO.BOLA_DE_NEVE)

    resultado = publicar_ORDEM_QUITACAO(
        cenario, METODO.BOLA_DE_NEVE, dividas, _particao_sem_bloqueio()
    )

    justificativa = resultado.ORDEM_QUITACAO[0].JUSTIFICATIVA_POSICAO
    assert "D-01" in justificativa
    assert METODO.BOLA_DE_NEVE.value in justificativa
    assert "O-04" in justificativa  # ID normativo citado — §4 do sdd.config.md


@pytest.mark.regra
def test_justificativa_varia_por_metodo_recomendado() -> None:
    """`Q-05`: o critério textual reflete o método recomendado — Avalanche
    (`O-01`), Bola de Neve (`O-04`) e Híbrido (`H-05`) produzem
    justificativas distintas para a MESMA dívida na mesma posição."""
    d1 = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": d1}

    justificativas: dict[METODO, str] = {}
    for metodo in (METODO.AVALANCHE, METODO.BOLA_DE_NEVE, METODO.HIBRIDO):
        cenario = _cenario(("D-01",), metodo)
        resultado = publicar_ORDEM_QUITACAO(cenario, metodo, dividas, _particao_sem_bloqueio())
        justificativas[metodo] = resultado.ORDEM_QUITACAO[0].JUSTIFICATIVA_POSICAO

    assert len(set(justificativas.values())) == 3, "cada método deve gerar justificativa distinta"


@pytest.mark.regra
def test_posicao_dataclass_e_o_contrato_do_plano() -> None:
    """Confirma o shape de `PosicaoOrdem` (`posicao`, `DIVIDA_ID`,
    `JUSTIFICATIVA_POSICAO`, `valores_de_apoio`) — §4 do plano técnico."""
    d1 = _divida(DIVIDA_ID="D-01")
    dividas = {"D-01": d1}
    cenario = _cenario(("D-01",), METODO.AVALANCHE)

    resultado = publicar_ORDEM_QUITACAO(
        cenario, METODO.AVALANCHE, dividas, _particao_sem_bloqueio()
    )

    posicao = resultado.ORDEM_QUITACAO[0]
    assert isinstance(posicao, PosicaoOrdem)
    assertar_exato(posicao.posicao, 1)
    assertar_exato(posicao.DIVIDA_ID, "D-01")


def _beneficio(divida_id: str, origem: str = "SIMULACAO") -> BeneficioMarginal:
    """`BeneficioMarginal` sintético mínimo — só `origem` é significativo
    para `consolidar_ORDEM_STATUS`; o resto é neutro (mesmo padrão de
    `_cenario` acima)."""
    return BeneficioMarginal(
        DIVIDA_ID=divida_id,
        DELTA_TESTE_AVALANCHE=Decimal("0"),
        DELTA_REALMENTE_APLICADO=Decimal("0"),
        DESEMBOLSO_FUTURO_SEM_DELTA=Decimal("0"),
        DESEMBOLSO_FUTURO_COM_DELTA=Decimal("0"),
        BENEFICIO_MARGINAL_AMORTIZACAO=Decimal("0"),
        origem=origem,  # type: ignore[arg-type]
    )


@pytest.mark.regra
def test_inventario_incompleto_rebaixa_ordem_status_a_provisoria() -> None:
    """Critério de aceite 1 de `T-64` / `AC-09`: `INVENTARIO_COMPLETO =
    False` impede `ORDEM_STATUS = DEFINITIVA_NA_DATA`, mesmo que toda
    dívida da ordem tenha `origem = SIMULACAO`."""
    beneficios = {
        "D-01": _beneficio("D-01", "SIMULACAO"),
        "D-02": _beneficio("D-02", "SIMULACAO"),
    }

    resultado = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=False, beneficios_marginais=beneficios
    )

    assert resultado.ORDEM_STATUS is not ORDEM_STATUS.DEFINITIVA_NA_DATA
    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.PROVISORIA)
    assert resultado.motivos_rebaixamento, "rebaixamento sem motivo nomeado viola T-64"
    assert any("INVENTARIO_COMPLETO" in motivo for motivo in resultado.motivos_rebaixamento)


@pytest.mark.regra
def test_uma_unica_divida_com_fallback_contamina_ordem_inteira() -> None:
    """Critério de aceite 2 de `T-64` / `AC-33`: entre várias dívidas, só
    uma com `origem != SIMULACAO` já basta para rebaixar `ORDEM_STATUS`
    da ordem inteira — consolidação = pior caso, nunca maioria/média."""
    beneficios = {
        "D-01": _beneficio("D-01", "SIMULACAO"),
        "D-02": _beneficio("D-02", "FALLBACK_TAXA"),
        "D-03": _beneficio("D-03", "SIMULACAO"),
    }

    resultado = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=True, beneficios_marginais=beneficios
    )

    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.PROVISORIA)
    assert any("D-02" in motivo for motivo in resultado.motivos_rebaixamento), (
        "motivo deve nomear explicitamente a dívida que causou o rebaixamento"
    )


@pytest.mark.parametrize("origem", ["FALLBACK_TAXA", "FALLBACK_CET", "INDISPONIVEL"])
@pytest.mark.regra
def test_qualquer_origem_de_fallback_rebaixa_ordem_status(origem: str) -> None:
    """`AC-33`: as três origens de fallback (`FALLBACK_TAXA`, `FALLBACK_CET`,
    `INDISPONIVEL`) rebaixam a ordem — nenhuma delas é `SIMULACAO`."""
    beneficios = {"D-01": _beneficio("D-01", origem)}

    resultado = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=True, beneficios_marginais=beneficios
    )

    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.PROVISORIA)
    assert resultado.motivos_rebaixamento


@pytest.mark.regra
def test_motivos_acumulam_as_duas_causas_simultaneamente() -> None:
    """Critério de aceite 3 de `T-64`: inventário incompleto E fallback de
    benefício marginal presentes ao mesmo tempo geram DOIS motivos
    distintos na tupla, não apenas um — mesmo espírito de
    `ResultadoStatusMetodo.motivos` (`engine/status_metodo.py`, T-60)."""
    beneficios = {"D-01": _beneficio("D-01", "FALLBACK_CET")}

    resultado = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=False, beneficios_marginais=beneficios
    )

    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.PROVISORIA)
    assertar_exato(len(resultado.motivos_rebaixamento), 2)
    assert any("INVENTARIO_COMPLETO" in motivo for motivo in resultado.motivos_rebaixamento)
    assert any("D-01" in motivo for motivo in resultado.motivos_rebaixamento)


@pytest.mark.regra
def test_ordem_definitiva_na_data_quando_tudo_completo_e_toda_simulacao() -> None:
    """Sem nenhuma causa de rebaixamento — `INVENTARIO_COMPLETO = True` e
    toda dívida com `origem = SIMULACAO` — `ORDEM_STATUS =
    DEFINITIVA_NA_DATA` e `motivos_rebaixamento` vazio."""
    beneficios = {
        "D-01": _beneficio("D-01", "SIMULACAO"),
        "D-02": _beneficio("D-02", "SIMULACAO"),
    }

    resultado = consolidar_ORDEM_STATUS(
        INVENTARIO_COMPLETO=True, beneficios_marginais=beneficios
    )

    assert isinstance(resultado, ResultadoConsolidacaoOrdemStatus)
    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.DEFINITIVA_NA_DATA)
    assertar_exato(resultado.motivos_rebaixamento, ())


@pytest.mark.regra
def test_ordem_definitiva_na_data_sem_nenhuma_divida() -> None:
    """Caso limite: `beneficios_marginais` vazio (ordem sem nenhuma dívida
    quitada) não é, por si só, causa de rebaixamento — só
    `INVENTARIO_COMPLETO` decide neste caso."""
    resultado = consolidar_ORDEM_STATUS(INVENTARIO_COMPLETO=True, beneficios_marginais={})

    assertar_exato(resultado.ORDEM_STATUS, ORDEM_STATUS.DEFINITIVA_NA_DATA)
    assertar_exato(resultado.motivos_rebaixamento, ())
