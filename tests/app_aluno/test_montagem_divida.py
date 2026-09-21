"""Testes de `app/montagem/estado.py::montar_divida` — RF-12, RF-14 (T-49).

Cobre os quatro critérios de aceite de `T-49` com o registro REAL do Bloco 5
(`collection/registros/bloco-05.yaml`, T-17), carregado por
`collection.carga.carregar_registros` — nenhum `ID`/`VARIAVEL_GRAVADA` é
inventado no teste; todos vêm do próprio registro de produção, para que uma
mudança no YAML que quebre o mapeamento seja pega aqui.

REGRAS: RF-12, RF-14, AC-08
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import ErroRespostaAusente, montar_divida
from collection.carga import carregar_registros
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.estado import TIPO_DIVIDA, Divida
from engine.tipos import DESCONHECIDO, STATUS_DIVIDA, STATUS_VALIDADE_PROPOSTA, SimNaoTalvez

_CASO_ID = "caso-teste-t49"
_QUESTIONARIO_VERSION = "1.0.0"
_AGORA = datetime(2026, 1, 1, tzinfo=UTC)

# Mesmas duas strings COMPOSTAS de `VARIAVEL_GRAVADA` do registro real do
# Bloco 5 (`collection/registros/bloco-05.yaml`, B5.C02 e B5.D05A) — ver
# `app/montagem/estado.py::_VARIAVEL_PARCELA_CONTRATUAL`/
# `_VARIAVEL_CUSTO_SEGURO`. Repetidas aqui (não importadas do módulo privado)
# porque o teste precisa gravar a `Resposta` sob a MESMA chave que
# `RespostasCaso.valor_no_item` vai indexar — provando que o mapeamento bate
# com o dado real, não com uma constante interna do próprio módulo testado.
_VARIAVEL_PARCELA_CONTRATUAL = "PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)"
_VARIAVEL_CUSTO_SEGURO = "CUSTO_SEGURO (+ base MENSAL/TOTAL)"
_VARIAVEL_CET_COMPOSTA = "CET (+ PERIODICIDADE_CET)"


def _resposta(ID_PERGUNTA: str, DIVIDA_ID: str, valor: object) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=DIVIDA_ID,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
        respondida_em=_AGORA,
    )


def _ficha_minima_completa(DIVIDA_ID: str, **sobrescritas: object) -> RespostasCaso:
    """Uma ficha de dívida com todos os campos `REP` obrigatórios de
    `montar_divida` preenchidos com valores concretos (nenhum `NAO_SEI`) —
    base para os testes sobrescreverem só o campo sob teste. Os nomes de
    variável usados aqui (`TIPO_DIVIDA`, `STATUS_DIVIDA`, `SALDO_DEVEDOR_
    ATUAL`, ...) são exatamente os `VARIAVEL_GRAVADA` do registro real do
    Bloco 5 (ver `test_mapeamento_usa_variaveis_do_registro_real_do_bloco_5`,
    que prova isso por introspecção do YAML carregado)."""
    valores: dict[str, object] = {
        "TIPO_DIVIDA": "CARTAO_ROTATIVO",
        "STATUS_DIVIDA": "ATIVA",
        "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("5.000,00"),
        "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("300,00"),
        "PESO_EMOCIONAL": 5,
    }
    valores.update(sobrescritas)
    respostas = tuple(
        _resposta(ID_PERGUNTA=variavel, DIVIDA_ID=DIVIDA_ID, valor=valor)
        for variavel, valor in valores.items()
        if valor is not _OMITIR
    )
    return RespostasCaso(respostas=respostas)


_OMITIR = object()  # sentinela local de teste: "não gravar esta resposta"


# ---------------------------------------------------------------------------
# Critério 1 — todos os campos de `Divida` são preenchidos a partir de
# resposta ou de `DESCONHECIDO`; nenhum default silencioso.
# ---------------------------------------------------------------------------
class TestCriterio1NenhumDefaultSilencioso:
    def test_ficha_completa_preenche_todos_os_campos_de_divida(self) -> None:
        respostas = _ficha_minima_completa("D001")

        divida = montar_divida(respostas, "D001")

        assert isinstance(divida, Divida)
        assert divida.DIVIDA_ID == "D001"
        assert divida.TIPO_DIVIDA is TIPO_DIVIDA.CARTAO_ROTATIVO
        assert divida.STATUS_DIVIDA is STATUS_DIVIDA.ATIVA
        assert divida.SALDO_DEVEDOR_ATUAL == Decimal("5000.00")
        assert divida.PAGAMENTO_MENSAL_EFETIVO == Decimal("300.00")
        assert divida.PESO_EMOCIONAL == 5
        # Campos COND sem resposta (estrutural, ficha não tinha esses ramos
        # abertos) são DESCONHECIDO — nunca None nem um valor inventado.
        assert divida.VALOR_QUITACAO_HOJE is DESCONHECIDO
        assert divida.PARCELA_CONTRATUAL is DESCONHECIDO
        assert divida.CUSTO_SEGURO is DESCONHECIDO
        assert divida.TAXA_EFETIVA_MENSAL_NORMALIZADA is DESCONHECIDO
        assert divida.CET is DESCONHECIDO

    @pytest.mark.parametrize(
        "campo_obrigatorio,id_pergunta",
        [
            ("TIPO_DIVIDA", "B5.A02"),
            ("STATUS_DIVIDA", "B5.A04"),
            ("PAGAMENTO_MENSAL_EFETIVO", "B5.C06"),
            ("PESO_EMOCIONAL", "B5.H01"),
            ("SALDO_DEVEDOR_ATUAL", "B5.B03"),
        ],
    )
    def test_campo_rep_obrigatorio_sem_resposta_levanta_erro_explicito(
        self, campo_obrigatorio: str, id_pergunta: str
    ) -> None:
        """RF-12: uma pergunta REP obrigatória sem resposta é erro
        explícito — nunca DESCONHECIDO, nunca 0, nunca None silencioso."""
        respostas = _ficha_minima_completa("D001", **{campo_obrigatorio: _OMITIR})

        with pytest.raises(ErroRespostaAusente) as excecao:
            montar_divida(respostas, "D001")

        assert excecao.value.DIVIDA_ID == "D001"
        assert excecao.value.VARIAVEL_GRAVADA == campo_obrigatorio


# ---------------------------------------------------------------------------
# Critério 2 (AC-08) — "não sei" em saldo e pagamento mensal produz
# DESCONHECIDO nos dois, nunca 0.
# ---------------------------------------------------------------------------
class TestCriterio2AC08NaoSeiProduzDesconhecido:
    def test_ac_08_nao_sei_em_saldo_e_pagamento_produz_desconhecido_nos_dois(self) -> None:
        respostas = _ficha_minima_completa(
            "D002",
            SALDO_DEVEDOR_ATUAL=NAO_SEI,
            PAGAMENTO_MENSAL_EFETIVO=NAO_SEI,
        )

        divida = montar_divida(respostas, "D002")

        assert divida.SALDO_DEVEDOR_ATUAL is DESCONHECIDO
        assert divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO
        # Nunca 0 — a igualdade com Decimal("0") seria um bug de conversão
        # clássico (NAO_SEI e 0 são semanticamente opostos).
        assert divida.SALDO_DEVEDOR_ATUAL != Decimal("0")
        assert divida.PAGAMENTO_MENSAL_EFETIVO != Decimal("0")

    def test_ac_08_nao_sei_apenas_no_saldo_nao_contamina_pagamento(self) -> None:
        respostas = _ficha_minima_completa("D003", SALDO_DEVEDOR_ATUAL=NAO_SEI)

        divida = montar_divida(respostas, "D003")

        assert divida.SALDO_DEVEDOR_ATUAL is DESCONHECIDO
        assert divida.PAGAMENTO_MENSAL_EFETIVO == Decimal("300.00")


# ---------------------------------------------------------------------------
# Critério 3 — PAGAMENTO_MENSAL_EFETIVO = 0 declarado é preservado como 0,
# distinto de DESCONHECIDO.
# ---------------------------------------------------------------------------
class TestCriterio3ZeroDistintoDeDesconhecido:
    def test_pagamento_mensal_efetivo_zero_e_preservado_como_zero(self) -> None:
        """B5.C06: 'Não estou pagando nada atualmente' grava valor_interno
        "0" — a conversão para Dinheiro(0) real, nunca DESCONHECIDO."""
        respostas = _ficha_minima_completa(
            "D004", PAGAMENTO_MENSAL_EFETIVO=converter_para_dinheiro("0")
        )

        divida = montar_divida(respostas, "D004")

        assert divida.PAGAMENTO_MENSAL_EFETIVO == Decimal("0")
        assert divida.PAGAMENTO_MENSAL_EFETIVO is not DESCONHECIDO
        assert isinstance(divida.PAGAMENTO_MENSAL_EFETIVO, Decimal)

    def test_valor_quitacao_hoje_zero_e_preservado_como_zero_nao_desconhecido(self) -> None:
        """Mesma garantia para um campo COND (`_dinheiro_estrutural_ou_
        desconhecido`) — o bug de truthiness (`Decimal("0") or NAO_SEI`)
        afetaria justamente este caminho se reintroduzido."""
        respostas = _ficha_minima_completa(
            "D005", VALOR_QUITACAO_HOJE=converter_para_dinheiro("0")
        )

        divida = montar_divida(respostas, "D005")

        assert divida.VALOR_QUITACAO_HOJE == Decimal("0")
        assert divida.VALOR_QUITACAO_HOJE is not DESCONHECIDO


# ---------------------------------------------------------------------------
# B5.C06 = "VARIA" (o valor pago varia muito) — quarta opção do domínio real,
# além de valor concreto/"0"/NAO_SEI. Não é um dos quatro critérios formais
# de T-49, mas é o mesmo campo (PAGAMENTO_MENSAL_EFETIVO) do AC-08/critério 3
# e um caso de borda descoberto ao ler o domínio completo do registro real.
# ---------------------------------------------------------------------------
class TestPagamentoMensalEfetivoVaria:
    def test_varia_sem_media_de_tres_meses_produz_desconhecido(self) -> None:
        respostas = _ficha_minima_completa("D011", PAGAMENTO_MENSAL_EFETIVO="VARIA")

        divida = montar_divida(respostas, "D011")

        assert divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO

    def test_varia_com_media_de_tres_meses_respondida_repassa_a_media(self) -> None:
        respostas = _ficha_minima_completa(
            "D012",
            PAGAMENTO_MENSAL_EFETIVO="VARIA",
            **{"PAGAMENTO_MENSAL_EFETIVO (média 3 meses)": converter_para_dinheiro("250,50")},
        )

        divida = montar_divida(respostas, "D012")

        assert divida.PAGAMENTO_MENSAL_EFETIVO == Decimal("250.50")

    def test_varia_com_media_nao_sei_produz_desconhecido(self) -> None:
        respostas = _ficha_minima_completa(
            "D013",
            PAGAMENTO_MENSAL_EFETIVO="VARIA",
            **{"PAGAMENTO_MENSAL_EFETIVO (média 3 meses)": NAO_SEI},
        )

        divida = montar_divida(respostas, "D013")

        assert divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO


# ---------------------------------------------------------------------------
# Critério 4 — mypy --strict obriga tratar DESCONHECIDO em todo
# DinheiroTalvez/TaxaTalvez (verificado no CI por `mypy --strict` sobre este
# módulo; aqui provamos o comportamento em runtime que o tipo garante em
# tempo de checagem: o valor É de fato Decimal ou Desconhecido, nunca outra
# coisa, então qualquer código que só trate um dos dois é incompleto).
# ---------------------------------------------------------------------------
class TestCriterio4TipoObrigaTratarDesconhecido:
    def test_campos_dinheiro_talvez_sao_sempre_decimal_ou_desconhecido(self) -> None:
        respostas = _ficha_minima_completa("D006")
        divida = montar_divida(respostas, "D006")

        campos_dinheiro_talvez = (
            divida.SALDO_DEVEDOR_ATUAL,
            divida.VALOR_QUITACAO_HOJE,
            divida.PARCELA_CONTRATUAL,
            divida.PAGAMENTO_MENSAL_EFETIVO,
            divida.CUSTO_SEGURO,
        )
        for campo in campos_dinheiro_talvez:
            assert isinstance(campo, Decimal) or campo is DESCONHECIDO

        campos_taxa_talvez = (divida.TAXA_EFETIVA_MENSAL_NORMALIZADA, divida.CET)
        for campo in campos_taxa_talvez:
            assert isinstance(campo, Decimal) or campo is DESCONHECIDO


# ---------------------------------------------------------------------------
# Prova de fidelidade ao registro real do Bloco 5 (T-17) — nenhum
# VARIAVEL_GRAVADA usado por `montar_divida` é inventado no teste.
# ---------------------------------------------------------------------------
def test_mapeamento_usa_variaveis_do_registro_real_do_bloco_5() -> None:
    colecao = carregar_registros()
    variaveis_do_bloco_5 = {
        registro.VARIAVEL_GRAVADA
        for registro in colecao.registros
        if registro.bloco == 5 and registro.VARIAVEL_GRAVADA is not None
    }

    variaveis_usadas_por_montar_divida = {
        "TIPO_DIVIDA",
        "STATUS_DIVIDA",
        "SALDO_DEVEDOR_ATUAL",
        "VALOR_QUITACAO_HOJE",
        "QUITACAO_CONSULTADA",
        "DATA_VALIDADE_PROPOSTA",
        _VARIAVEL_PARCELA_CONTRATUAL,
        "PAGAMENTO_MENSAL_EFETIVO",
        "PAGAMENTO_MENSAL_EFETIVO (média 3 meses)",
        "SEGURO_INCLUIDO_PARCELA",
        _VARIAVEL_CUSTO_SEGURO,
        "PESO_EMOCIONAL",
        "TAXA_INFORMADA",
        "PERIODICIDADE_TAXA",
    }
    ausentes = variaveis_usadas_por_montar_divida - variaveis_do_bloco_5
    assert not ausentes, (
        f"montar_divida usa variável(is) que não existe(m) no registro real "
        f"do Bloco 5: {ausentes}"
    )


def test_quitacao_consultada_expirou_produz_sim_e_status_expirada() -> None:
    """Decisão documentada de `_quitacao_consultada`/`_status_validade_
    proposta`: EXPIROU → SimNaoTalvez.SIM + STATUS_VALIDADE_PROPOSTA.EXPIRADA."""
    respostas = _ficha_minima_completa("D007", QUITACAO_CONSULTADA="EXPIROU")

    divida = montar_divida(respostas, "D007")

    assert divida.QUITACAO_CONSULTADA is SimNaoTalvez.SIM
    assert divida.STATUS_VALIDADE_PROPOSTA is STATUS_VALIDADE_PROPOSTA.EXPIRADA


def test_taxa_so_passa_quando_periodicidade_e_mensal() -> None:
    respostas = _ficha_minima_completa(
        "D008",
        TAXA_INFORMADA=converter_para_dinheiro("4,5"),
        PERIODICIDADE_TAXA="MENSAL",
    )

    divida = montar_divida(respostas, "D008")

    assert divida.TAXA_EFETIVA_MENSAL_NORMALIZADA == Decimal("4.5")


def test_taxa_anual_nao_e_convertida_vira_desconhecido() -> None:
    """A app nunca calcula a conversão de periodicidade (Lei nº 3) — taxa
    anual permanece DESCONHECIDO em vez de uma conversão estimada."""
    respostas = _ficha_minima_completa(
        "D009",
        TAXA_INFORMADA=converter_para_dinheiro("48"),
        PERIODICIDADE_TAXA="ANUAL",
    )

    divida = montar_divida(respostas, "D009")

    assert divida.TAXA_EFETIVA_MENSAL_NORMALIZADA is DESCONHECIDO


def test_cet_e_sempre_desconhecido_nesta_tarefa() -> None:
    """B5.D03A grava CET e periodicidade numa única resposta composta, sem
    variável própria de periodicidade (diferente de TAXA_INFORMADA/
    PERIODICIDADE_TAXA) — decisão documentada: CET nunca é lido nesta
    tarefa, sempre DESCONHECIDO, mesmo quando uma resposta de CET existe."""
    respostas = _ficha_minima_completa(
        "D010", **{_VARIAVEL_CET_COMPOSTA: converter_para_dinheiro("3,2")}
    )

    divida = montar_divida(respostas, "D010")

    assert divida.CET is DESCONHECIDO
