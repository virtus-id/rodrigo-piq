"""Testes da regra D.4 — `classificar_RISCO_RECAIDA` (T-15, 5 sinais) e
`classificar_RISCO_COMPORTAMENTAL_GERAL` (T-16, 6 sinais) — RF-18, AC-24,
AC-25, §11.4.

Cobre: a contagem exata de `AC-24` (3 sinais ⇒ ALTO), a trava de `AC-25`
(dado desconhecido não conta como risco positivo) e as quatro fronteiras de
classificação (`0` = BAIXO · `1–2` = MODERADO · `3+` = ALTO) nas DUAS
classificações — cada uma tem seu próprio conjunto de sinais (5 para
RISCO_RECAIDA, 6 para RISCO_COMPORTAMENTAL_GERAL), então a fronteira precisa
ser provada nas duas, não só em uma.

Sinais irrelevantes a cada caso recebem valores "sem risco" deliberados, para
que a contagem observada venha exclusivamente dos sinais que o teste declara
— mesmo padrão de `_sinais_comportamentais` em `test_comportamento.py`.
"""

import pytest

from engine.estado import SinaisComportamentais
from engine.risco import classificar_RISCO_COMPORTAMENTAL_GERAL, classificar_RISCO_RECAIDA
from engine.tipos import DESCONHECIDO, NIVEL_CONTROLE, NIVEL_RISCO, SimNaoTalvez
from tests.conftest import assertar_exato


def _sinais(
    *,
    nova_divida_prevista: SimNaoTalvez = SimNaoTalvez.NAO,
    mecanismo_deficit: frozenset[str] | object = frozenset(),
    historico_recaida: SimNaoTalvez = SimNaoTalvez.NAO,
    novo_parcelamento_previsto: SimNaoTalvez = SimNaoTalvez.NAO,
    pacto: str = "ESTABELECIDO",
    risco_impulso: str | object = "NENHUMA",
    linha_continua_sendo_utilizada: str | object = "NAO",
    necessidade_vitoria: int = 0,
    historico_abandono: SimNaoTalvez = SimNaoTalvez.NAO,
) -> SinaisComportamentais:
    """Monta `SinaisComportamentais` completo, "sem risco" por padrão em
    todos os 9 campos, com override pontual dos campos que cada teste
    declara — evita que um sinal não citado no teste altere a contagem por
    acidente de fixture."""
    return SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=nova_divida_prevista,
        MECANISMO_DEFICIT=mecanismo_deficit,  # type: ignore[arg-type]
        HISTORICO_RECAIDA=historico_recaida,
        NOVO_PARCELAMENTO_PREVISTO=novo_parcelamento_previsto,
        PACTO=pacto,
        RISCO_IMPULSO=risco_impulso,  # type: ignore[arg-type]
        LINHA_CONTINUA_SENDO_UTILIZADA=linha_continua_sendo_utilizada,  # type: ignore[arg-type]
        NECESSIDADE_VITORIA=necessidade_vitoria,
        HISTORICO_ABANDONO=historico_abandono,
        JANELA_NOVA_DIVIDA=None,  # T-34: nenhum teste deste arquivo varia B1.05
    )


# ---------------------------------------------------------------------------
# AC-24 — contagem exata de 3 sinais ⇒ ALTO (RISCO_RECAIDA)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_AC24_recaida_conta_tres_sinais_e_classifica_alto() -> None:
    """AC-24: `PACTO = EM_CONSTRUCAO` + `HISTORICO_RECAIDA = SIM` +
    `NOVA_DIVIDA_PREVISTA = TALVEZ` ⇒ contagem 3 e `ALTO`."""
    sinais = _sinais(
        nova_divida_prevista=SimNaoTalvez.TALVEZ,
        historico_recaida=SimNaoTalvez.SIM,
        pacto="EM_CONSTRUCAO",
    )
    resultado = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(resultado.contagem, 3)
    assertar_exato(resultado.nivel, NIVEL_RISCO.ALTO)


# ---------------------------------------------------------------------------
# AC-25 — dado desconhecido não conta como risco positivo
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_D4_desconhecido_nao_conta_como_risco() -> None:
    """AC-25: `MECANISMO_DEFICIT = DESCONHECIDO`, único sinal de entrada com
    domínio `Desconhecido` nas duas contagens, não incrementa a contagem em
    nenhuma das duas classificações — mesmo que, se soubéssemos o valor,
    "talvez fosse" risco. `desconhecido=True` fica registrado no `SinalD4`
    para auditoria, mas `ativo` é sempre `False`."""
    sinais = _sinais(mecanismo_deficit=DESCONHECIDO)

    recaida = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(recaida.contagem, 0)
    assertar_exato(recaida.nivel, NIVEL_RISCO.BAIXO)
    sinal_mecanismo_recaida = next(s for s in recaida.sinais if s.nome == "MECANISMO_DEFICIT")
    assertar_exato(sinal_mecanismo_recaida.ativo, False)
    assertar_exato(sinal_mecanismo_recaida.desconhecido, True)

    comportamental = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FORTE)
    assertar_exato(comportamental.contagem, 0)
    assertar_exato(comportamental.nivel, NIVEL_RISCO.BAIXO)
    sinal_mecanismo_comportamental = next(
        s for s in comportamental.sinais if s.nome == "MECANISMO_DEFICIT"
    )
    assertar_exato(sinal_mecanismo_comportamental.ativo, False)
    assertar_exato(sinal_mecanismo_comportamental.desconhecido, True)


@pytest.mark.regra
def test_D4_desconhecido_em_risco_impulso_nao_conta_no_comportamental() -> None:
    """AC-25, segundo campo com domínio `Desconhecido` da contagem
    comportamental: `RISCO_IMPULSO = DESCONHECIDO` não incrementa a
    contagem de `RISCO_COMPORTAMENTAL_GERAL`."""
    sinais = _sinais(risco_impulso=DESCONHECIDO)
    resultado = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FORTE)
    assertar_exato(resultado.contagem, 0)
    assertar_exato(resultado.nivel, NIVEL_RISCO.BAIXO)
    sinal = next(s for s in resultado.sinais if s.nome == "RISCO_IMPULSO")
    assertar_exato(sinal.ativo, False)
    assertar_exato(sinal.desconhecido, True)


# ---------------------------------------------------------------------------
# Fronteiras 0/1/2/3 sinais — RISCO_RECAIDA (5 sinais)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_recaida_zero_sinais_classifica_baixo() -> None:
    """§11.4: `0` sinais ativos ⇒ BAIXO, para os 5 sinais de RISCO_RECAIDA."""
    sinais = _sinais()
    resultado = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(resultado.contagem, 0)
    assertar_exato(resultado.nivel, NIVEL_RISCO.BAIXO)


@pytest.mark.regra
def test_recaida_um_sinal_classifica_moderado() -> None:
    """§11.4: `1` sinal ativo ⇒ MODERADO (faixa `1–2`), RISCO_RECAIDA."""
    sinais = _sinais(historico_recaida=SimNaoTalvez.SIM)
    resultado = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(resultado.contagem, 1)
    assertar_exato(resultado.nivel, NIVEL_RISCO.MODERADO)


@pytest.mark.regra
def test_recaida_dois_sinais_classifica_moderado() -> None:
    """§11.4: `2` sinais ativos ⇒ ainda MODERADO (limite superior da faixa
    `1–2`), RISCO_RECAIDA."""
    sinais = _sinais(
        historico_recaida=SimNaoTalvez.SIM,
        novo_parcelamento_previsto=SimNaoTalvez.SIM,
    )
    resultado = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(resultado.contagem, 2)
    assertar_exato(resultado.nivel, NIVEL_RISCO.MODERADO)


@pytest.mark.regra
def test_recaida_tres_sinais_classifica_alto() -> None:
    """§11.4: `3` sinais ativos ⇒ ALTO (piso da faixa `3+`), RISCO_RECAIDA —
    fronteira complementar a `AC-24`, com combinação de sinais distinta."""
    sinais = _sinais(
        historico_recaida=SimNaoTalvez.SIM,
        novo_parcelamento_previsto=SimNaoTalvez.SIM,
        nova_divida_prevista=SimNaoTalvez.SIM,
    )
    resultado = classificar_RISCO_RECAIDA(sinais)
    assertar_exato(resultado.contagem, 3)
    assertar_exato(resultado.nivel, NIVEL_RISCO.ALTO)


# ---------------------------------------------------------------------------
# Fronteiras 0/1/2/3 sinais — RISCO_COMPORTAMENTAL_GERAL (6 sinais)
# ---------------------------------------------------------------------------


@pytest.mark.regra
def test_comportamental_zero_sinais_classifica_baixo() -> None:
    """§11.4: `0` sinais ativos ⇒ BAIXO, para os 6 sinais de
    RISCO_COMPORTAMENTAL_GERAL — inclui `NIVEL_CONTROLE ≠ FRAGIL`."""
    sinais = _sinais()
    resultado = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FORTE)
    assertar_exato(resultado.contagem, 0)
    assertar_exato(resultado.nivel, NIVEL_RISCO.BAIXO)


@pytest.mark.regra
def test_comportamental_um_sinal_classifica_moderado() -> None:
    """§11.4: `1` sinal ativo ⇒ MODERADO (faixa `1–2`),
    RISCO_COMPORTAMENTAL_GERAL."""
    sinais = _sinais(historico_recaida=SimNaoTalvez.SIM)
    resultado = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FORTE)
    assertar_exato(resultado.contagem, 1)
    assertar_exato(resultado.nivel, NIVEL_RISCO.MODERADO)


@pytest.mark.regra
def test_comportamental_dois_sinais_classifica_moderado() -> None:
    """§11.4: `2` sinais ativos ⇒ ainda MODERADO (limite superior da faixa
    `1–2`), RISCO_COMPORTAMENTAL_GERAL."""
    sinais = _sinais(
        historico_recaida=SimNaoTalvez.SIM,
        novo_parcelamento_previsto=SimNaoTalvez.SIM,
    )
    resultado = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FORTE)
    assertar_exato(resultado.contagem, 2)
    assertar_exato(resultado.nivel, NIVEL_RISCO.MODERADO)


@pytest.mark.regra
def test_comportamental_tres_sinais_classifica_alto() -> None:
    """§11.4: `3` sinais ativos ⇒ ALTO (piso da faixa `3+`),
    RISCO_COMPORTAMENTAL_GERAL. Terceiro sinal é `NIVEL_CONTROLE = FRAGIL`,
    passado como parâmetro já derivado — prova que o sexto sinal (o único
    que não vem de `SinaisComportamentais`) também conta na contagem."""
    sinais = _sinais(
        historico_recaida=SimNaoTalvez.SIM,
        novo_parcelamento_previsto=SimNaoTalvez.SIM,
    )
    resultado = classificar_RISCO_COMPORTAMENTAL_GERAL(sinais, NIVEL_CONTROLE.FRAGIL)
    assertar_exato(resultado.contagem, 3)
    assertar_exato(resultado.nivel, NIVEL_RISCO.ALTO)
