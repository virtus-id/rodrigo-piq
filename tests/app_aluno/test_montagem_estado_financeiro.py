"""Testes de `app/montagem/estado.py::montar_estado_financeiro` — RF-14,
AC-18 (T-51).

Cobre os quatro critérios de aceite de `T-51` com os registros REAIS dos
Blocos 1, 2, 3 e 5 (`collection/registros/bloco-0{1,2,3,5}.yaml`, T-17),
carregados por `collection.carga.carregar_registros` — nenhum
`VARIAVEL_GRAVADA`/`valor_interno` é inventado no teste.

REGRAS: RF-14, AC-18
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import (
    ErroCampoAgregadoDesconhecido,
    ErroRespostaAusente,
    montar_estado_financeiro,
)
from collection.carga import carregar_registros
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from engine.estado import TIPO_RENDA, EstadoFinanceiro
from engine.tipos import CONFIABILIDADE_DADOS, DESCONHECIDO

_CASO_ID = "caso-teste-t51"
_QUESTIONARIO_VERSION = "1.0.0"
_AGORA = datetime(2026, 1, 1, tzinfo=UTC)
_DATA_REFERENCIA = date(2026, 3, 15)

_OMITIR = object()  # sentinela local de teste: "não gravar esta resposta"


def _resposta(ID_PERGUNTA: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=ID_PERGUNTA,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
        respondida_em=_AGORA,
    )


# As respostas mínimas para montar um EstadoFinanceiro completo: os 8
# VARIAVEL_GRAVADA de PerfilComportamental (Bloco 2), os 8 de
# SinaisComportamentais lidos por `respostas.valor` (Blocos 1/2/9), TIPO_RENDA
# (B3.02) e CAPACIDADE_ATAQUE_DECLARADA (B3.C01).
def _respostas_minimas_completas(**sobrescritas: object) -> RespostasCaso:
    valores: dict[str, object] = {
        # PerfilComportamental (Bloco 2, T-50)
        "REGISTRO_GASTOS": "TUDO",
        "FREQUENCIA_REGISTRO": "DIARIA",
        "DEFASAGEM_REGISTRO": "NA_HORA",
        "COBERTURA_PEQUENOS_GASTOS": "TODOS",
        "COBERTURA_MEIOS_PAGAMENTO": "TOTAL",
        "CONHECIMENTO_GASTO": "BOA_APROXIMACAO",
        "GASTOS_NAO_IDENTIFICADOS": "NUNCA",
        "REVISAO_SEMANAL": "SEMPRE",
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
        # renda adicional por padrão — RENDA_TOTAL_RECORRENTE =
        # RENDA_PRINCIPAL = 8.000,00 nas respostas mínimas.
        "RENDA_PRINCIPAL": converter_para_dinheiro("8.000,00"),
        # B5.FIM02 (T-52) — inventário completo por padrão nas respostas
        # mínimas; testes de INVENTARIO_COMPLETO sobrescrevem este valor.
        "CONFIRMACAO_FIM_CADASTRO": "SIM",
        # Bloco 4 — reserva e caixa (T-112, RF-36/RF-37/RF-38). Desde
        # `T-110`/`T-111` estes cinco campos escalares são LIDOS das
        # respostas, então sem eles as respostas deixam de ser "mínimas
        # completas": `_dinheiro_disponivel` e `_reserva_existe` levantam.
        # Os mesmos valores e os mesmos motivos de
        # `tests/app_aluno/fixtures/caso_completo.py::_VALORES_CASO`, que
        # documenta a escolha de cada ramo — os dois construtores da base de
        # respostas deste slug ficam reconciliados, nunca divergentes.
        "DINHEIRO_DISPONIVEL_EXISTE": "SIM",
        "DINHEIRO_DISPONIVEL": converter_para_dinheiro("1.200,00"),
        "RESERVA_EXISTE": "SIM",
        "RESERVA_TOTAL": converter_para_dinheiro("10.000,00"),
        "DISPOSICAO_USO_RESERVA": "PARTE",
        "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": converter_para_dinheiro("3.000,00"),
    }
    valores.update(sobrescritas)
    respostas = tuple(
        _resposta(ID_PERGUNTA=variavel, valor=valor)
        for variavel, valor in valores.items()
        if valor is not _OMITIR
    )
    return RespostasCaso(respostas=respostas)


def _montar(respostas: RespostasCaso, **sobrescritas: object) -> EstadoFinanceiro:
    parametros: dict[str, object] = {
        "DATA_REFERENCIA": _DATA_REFERENCIA,
        "dividas": (),
        "CONFIABILIDADE_DADOS": CONFIABILIDADE_DADOS.ALTA,
        # Nenhum gasto fantasma identificado por padrão nas respostas
        # mínimas — sem este default, `_economia_potencial_imediata`
        # levantaria `ErroRespostaAusente` em todo teste que não testa a
        # economia potencial explicitamente. `test_economia_potencial_
        # imediata_sem_parametro_de_ausencia_levanta_erro` sobrescreve com
        # `None` para provar o caminho de erro.
        "economia_nao_identificada": Decimal("0"),
    }
    parametros.update(sobrescritas)
    return montar_estado_financeiro(respostas, **parametros)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-18 — DATA_REFERENCIA vem do Caso; nenhuma chamada a
# date.today()/datetime.now() existe em app/montagem/.
# ---------------------------------------------------------------------------
class TestAC18DataReferenciaExplicita:
    def test_data_referencia_e_exatamente_a_recebida_como_parametro(self) -> None:
        respostas = _respostas_minimas_completas()

        estado = _montar(respostas, DATA_REFERENCIA=_DATA_REFERENCIA)

        assert estado.DATA_REFERENCIA == _DATA_REFERENCIA
        assert estado.DATA_REFERENCIA is _DATA_REFERENCIA

    def test_data_referencia_diferente_produz_estado_diferente(self) -> None:
        """Prova de que DATA_REFERENCIA não é fixada/ignorada — é
        efetivamente repassada ao EstadoFinanceiro."""
        respostas = _respostas_minimas_completas()
        outra_data = date(2026, 6, 1)

        estado_1 = _montar(respostas, DATA_REFERENCIA=_DATA_REFERENCIA)
        estado_2 = _montar(respostas, DATA_REFERENCIA=outra_data)

        assert estado_1.DATA_REFERENCIA != estado_2.DATA_REFERENCIA

    def test_modulo_de_montagem_nao_chama_date_today_nem_datetime_now(self) -> None:
        """Mesma prova por AST usada pelo teste estático dedicado
        (`tests/app_aluno/estatica/test_sem_relogio_em_montagem.py`), aqui
        também como teste funcional direto sobre o código-fonte do módulo."""
        import ast
        import inspect

        from app.montagem import estado as modulo_estado

        codigo_fonte = inspect.getsource(modulo_estado)
        arvore = ast.parse(codigo_fonte)

        chamadas_de_relogio = [
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr in ("today", "now", "utcnow")
        ]
        assert not chamadas_de_relogio, (
            "app/montagem/estado.py não deve conter nenhuma chamada a "
            "date.today()/datetime.now()/datetime.utcnow() — DATA_REFERENCIA "
            "é sempre parâmetro explícito (AC-18)."
        )


# ---------------------------------------------------------------------------
# Critério 2 — todos os campos obrigatórios são preenchidos a partir de
# resposta ou DESCONHECIDO.
# ---------------------------------------------------------------------------
class TestTodosOsCamposObrigatoriosPreenchidos:
    def test_estado_financeiro_completo_com_todos_os_campos(self) -> None:
        respostas = _respostas_minimas_completas()

        estado = _montar(respostas)

        assert isinstance(estado, EstadoFinanceiro)
        assert estado.DATA_REFERENCIA == _DATA_REFERENCIA
        # RENDA_TOTAL_RECORRENTE (T-103, OQ-16): RENDA_PRINCIPAL das
        # respostas mínimas, sem nenhuma ficha de renda adicional.
        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("8000.00")
        assert estado.TIPO_RENDA is TIPO_RENDA.FIXA
        # DESPESAS_OPERACIONAIS_ATUAIS/DESPESAS_NAO_MENSAIS_NORMALIZADAS
        # (T-103, OQ-16): nenhuma ficha de ITEM_DESPESA/DESPESA_NAO_MENSAL_ID
        # nas respostas mínimas — soma de zero itens é zero, nunca erro
        # (ver TestT103CamposAgregadosDoBloco3 para os casos com fichas).
        assert estado.DESPESAS_OPERACIONAIS_ATUAIS == Decimal("0")
        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("0")
        assert estado.CAPACIDADE_ATAQUE_DECLARADA == Decimal("500.00")
        assert estado.ECONOMIA_POTENCIAL_IMEDIATA == Decimal("0")
        assert estado.INVENTARIO_COMPLETO is True
        assert estado.dividas == ()
        assert estado.perfil_comportamental is not None
        assert estado.sinais_comportamentais is not None
        assert estado.CONFIABILIDADE_DADOS is CONFIABILIDADE_DADOS.ALTA
        assert estado.AUTOPERCEPCAO_CONTROLE is DESCONHECIDO  # não respondida

    def test_tipo_renda_sem_resposta_levanta_erro_explicito(self) -> None:
        respostas = _respostas_minimas_completas(TIPO_RENDA=_OMITIR)

        with pytest.raises(ErroRespostaAusente) as excecao:
            _montar(respostas)

        assert excecao.value.VARIAVEL_GRAVADA == "TIPO_RENDA"

    def test_capacidade_ataque_declarada_sem_resposta_levanta_erro_explicito(self) -> None:
        respostas = _respostas_minimas_completas(CAPACIDADE_ATAQUE_DECLARADA=_OMITIR)

        with pytest.raises(ErroRespostaAusente) as excecao:
            _montar(respostas)

        assert excecao.value.VARIAVEL_GRAVADA == "CAPACIDADE_ATAQUE_DECLARADA"

    def test_capacidade_ataque_declarada_nao_sei_e_desconhecido(self) -> None:
        respostas = _respostas_minimas_completas(CAPACIDADE_ATAQUE_DECLARADA=NAO_SEI)

        estado = _montar(respostas)

        assert estado.CAPACIDADE_ATAQUE_DECLARADA is DESCONHECIDO

    def test_capacidade_ataque_declarada_zero_e_preservada_como_zero(self) -> None:
        """"Hoje não consigo separar nenhum valor adicional." grava
        Dinheiro(0) real (valor_interno "0" no registro), distinto de
        DESCONHECIDO."""
        respostas = _respostas_minimas_completas(
            CAPACIDADE_ATAQUE_DECLARADA=converter_para_dinheiro("0")
        )

        estado = _montar(respostas)

        assert estado.CAPACIDADE_ATAQUE_DECLARADA == Decimal("0")
        assert estado.CAPACIDADE_ATAQUE_DECLARADA is not DESCONHECIDO

    def test_autopercepcao_controle_presente_e_lida(self) -> None:
        respostas = _respostas_minimas_completas(AUTOPERCEPCAO_CONTROLE=7)

        estado = _montar(respostas)

        assert estado.AUTOPERCEPCAO_CONTROLE == 7

    def test_economia_potencial_imediata_com_aceite_repassa_valor_gastos_fantasmas(
        self,
    ) -> None:
        respostas = _respostas_minimas_completas(
            GASTOS_FANTASMAS="SIM",
            VALOR_GASTOS_FANTASMAS=converter_para_dinheiro("120,00"),
            ACEITA_REDUCAO_GASTOS_FANTASMAS="SIM",
        )

        estado = _montar(respostas)

        assert estado.ECONOMIA_POTENCIAL_IMEDIATA == Decimal("120.00")

    def test_economia_potencial_imediata_sem_aceite_usa_parametro_de_ausencia(self) -> None:
        respostas = _respostas_minimas_completas(
            GASTOS_FANTASMAS="SIM",
            VALOR_GASTOS_FANTASMAS=converter_para_dinheiro("120,00"),
            ACEITA_REDUCAO_GASTOS_FANTASMAS="NAO",
        )

        estado = _montar(respostas, economia_nao_identificada=Decimal("0"))

        assert estado.ECONOMIA_POTENCIAL_IMEDIATA == Decimal("0")

    def test_economia_potencial_imediata_sem_parametro_de_ausencia_levanta_erro(self) -> None:
        """Sem gasto fantasma identificado E sem `economia_nao_identificada`
        fornecido pela chamadora, a ausência é erro explícito — nunca um
        `Dinheiro(0)` inventado dentro deste módulo (RF-13: fronteira
        Decimal única)."""
        respostas = _respostas_minimas_completas()

        with pytest.raises(ErroRespostaAusente):
            _montar(respostas, economia_nao_identificada=None)


# ---------------------------------------------------------------------------
# Critério 3 — montar duas vezes o mesmo conjunto de respostas produz
# EstadoFinanceiro igual campo a campo (função pura).
# ---------------------------------------------------------------------------
class TestFuncaoPuraMesmaEntradaMesmaSaida:
    def test_montar_duas_vezes_produz_estados_iguais_por_igualdade_estrutural(self) -> None:
        respostas = _respostas_minimas_completas()

        estado_1 = _montar(respostas)
        estado_2 = _montar(respostas)

        assert estado_1 == estado_2

    def test_montar_duas_vezes_com_dividas_produz_estados_iguais(self) -> None:
        from app.montagem.estado import montar_divida

        respostas_divida = RespostasCaso(
            respostas=(
                Resposta(
                    CASO_ID=_CASO_ID,
                    ID_PERGUNTA="TIPO_DIVIDA",
                    item_id="D001",
                    valor="CARTAO_ROTATIVO",
                    QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
                    respondida_em=_AGORA,
                ),
                Resposta(
                    CASO_ID=_CASO_ID,
                    ID_PERGUNTA="STATUS_DIVIDA",
                    item_id="D001",
                    valor="ATIVA",
                    QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
                    respondida_em=_AGORA,
                ),
                Resposta(
                    CASO_ID=_CASO_ID,
                    ID_PERGUNTA="SALDO_DEVEDOR_ATUAL",
                    item_id="D001",
                    valor=converter_para_dinheiro("5.000,00"),
                    QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
                    respondida_em=_AGORA,
                ),
                Resposta(
                    CASO_ID=_CASO_ID,
                    ID_PERGUNTA="PAGAMENTO_MENSAL_EFETIVO",
                    item_id="D001",
                    valor=converter_para_dinheiro("300,00"),
                    QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
                    respondida_em=_AGORA,
                ),
                Resposta(
                    CASO_ID=_CASO_ID,
                    ID_PERGUNTA="PESO_EMOCIONAL",
                    item_id="D001",
                    valor=5,
                    QUESTIONARIO_VERSION=_QUESTIONARIO_VERSION,
                    respondida_em=_AGORA,
                ),
            )
        )
        respostas_base = _respostas_minimas_completas()
        respostas_completas = RespostasCaso(
            respostas=(*respostas_base.respostas, *respostas_divida.respostas)
        )
        divida = montar_divida(respostas_completas, "D001")

        estado_1 = _montar(respostas_completas, dividas=(divida,))
        estado_2 = _montar(respostas_completas, dividas=(divida,))

        assert estado_1 == estado_2
        assert estado_1.dividas == estado_2.dividas


# ---------------------------------------------------------------------------
# Prova de fidelidade aos registros reais do Bloco 3 (T-17) — nenhum
# VARIAVEL_GRAVADA usado por montar_estado_financeiro é inventado no teste.
# ---------------------------------------------------------------------------
def test_mapeamento_usa_variaveis_do_registro_real_do_bloco_3() -> None:
    colecao = carregar_registros()
    variaveis_existentes = {
        registro.VARIAVEL_GRAVADA
        for registro in colecao.registros
        if registro.VARIAVEL_GRAVADA is not None
    }

    variaveis_usadas_do_bloco_3 = {
        "TIPO_RENDA",
        "CAPACIDADE_ATAQUE_DECLARADA",
        # T-103 (OQ-16): os três campos agregados, agora calculados.
        "RENDA_PRINCIPAL",
        "RENDA_RECORRENTE_ADICIONAL",
        "VALOR_DESPESA",
        "VALOR_DESPESA_NAO_MENSAL",
    }
    ausentes = variaveis_usadas_do_bloco_3 - variaveis_existentes
    assert not ausentes, (
        f"montar_estado_financeiro usa variável(is) do Bloco 3 que não "
        f"existe(m) em nenhum registro real: {ausentes}"
    )


def test_mapeamento_economia_potencial_usa_variaveis_do_registro_real_do_bloco_2() -> None:
    colecao = carregar_registros()
    variaveis_existentes = {
        registro.VARIAVEL_GRAVADA
        for registro in colecao.registros
        if registro.VARIAVEL_GRAVADA is not None
    }

    variaveis_usadas = {
        "GASTOS_FANTASMAS",
        "VALOR_GASTOS_FANTASMAS",
        "ACEITA_REDUCAO_GASTOS_FANTASMAS",
    }
    ausentes = variaveis_usadas - variaveis_existentes
    assert not ausentes, (
        f"_economia_potencial_imediata usa variável(is) que não existe(m) "
        f"em nenhum registro real: {ausentes}"
    )


# ---------------------------------------------------------------------------
# Fronteira documentada — `CONFIABILIDADE_DADOS` é o ÚNICO parâmetro externo
# que sobrevive a `T-103` (`OQ-16`): `RENDA_TOTAL_RECORRENTE`,
# `DESPESAS_OPERACIONAIS_ATUAIS` e `DESPESAS_NAO_MENSAIS_NORMALIZADAS`
# deixaram de ser parâmetro (`TestT103CamposAgregadosDoBloco3`, abaixo, cobre
# o cálculo real). INVENTARIO_COMPLETO NÃO está nesta lista desde T-52: é
# lido de B5.FIM02 (ver TestAC07InventarioCompleto).
# ---------------------------------------------------------------------------
class TestFronteiraDeParametrosExternosDocumentada:
    def test_confiabilidade_dados_e_exatamente_o_parametro_recebido(self) -> None:
        respostas = _respostas_minimas_completas()

        estado = _montar(respostas, CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS.BAIXA)

        assert estado.CONFIABILIDADE_DADOS is CONFIABILIDADE_DADOS.BAIXA

    def test_montar_estado_financeiro_nao_aceita_mais_os_tres_parametros_removidos(
        self,
    ) -> None:
        """Critério de aceite de `T-103`: o parâmetro externo que `T-51`
        introduziu para os três campos agregados foi removido de
        `montar_estado_financeiro` — passá-los agora é erro de chamada."""
        respostas = _respostas_minimas_completas()

        with pytest.raises(TypeError):
            _montar(respostas, RENDA_TOTAL_RECORRENTE=Decimal("1"))
        with pytest.raises(TypeError):
            _montar(respostas, DESPESAS_OPERACIONAIS_ATUAIS=Decimal("1"))
        with pytest.raises(TypeError):
            _montar(respostas, DESPESAS_NAO_MENSAIS_NORMALIZADAS=Decimal("1"))


# ---------------------------------------------------------------------------
# T-103 (OQ-16) — as três fórmulas fechadas para os campos agregados do
# Bloco 3, calculadas a partir das respostas de origem (nunca mais parâmetro
# externo). Cada teste cobre um critério de aceite da tarefa.
# ---------------------------------------------------------------------------
class TestT103CamposAgregadosDoBloco3:
    # -- RENDA_TOTAL_RECORRENTE: 0, 1 e N fontes adicionais -----------------
    def test_renda_total_recorrente_sem_fonte_adicional_e_so_a_renda_principal(
        self,
    ) -> None:
        respostas = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )

        estado = _montar(respostas)

        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("8000.00")

    def test_renda_total_recorrente_com_uma_fonte_adicional_soma_as_duas(self) -> None:
        respostas_minimas = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )
        fonte_adicional = _resposta(
            "RENDA_RECORRENTE_ADICIONAL", converter_para_dinheiro("300,00"), item_id="REND001"
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, fonte_adicional))

        estado = _montar(respostas)

        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("8300.00")

    def test_renda_total_recorrente_com_tres_fontes_adicionais_soma_todas(self) -> None:
        respostas_minimas = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )
        fontes_adicionais = tuple(
            _resposta(
                "RENDA_RECORRENTE_ADICIONAL", converter_para_dinheiro(valor), item_id=item_id
            )
            for item_id, valor in (
                ("REND001", "300,00"),
                ("REND002", "150,50"),
                ("REND003", "1.000,00"),
            )
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fontes_adicionais))

        estado = _montar(respostas)

        # 8000 + 300 + 150,50 + 1000 = 9450,50 — lista aberta, sem limite de
        # quantidade codificado (OQ-19).
        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("9450.50")

    # -- Qualidade do dado é metadado, não filtro (ESTIMADA/CONFIRMADA) -----
    def test_renda_principal_estimada_entra_com_o_mesmo_valor_de_confirmada(self) -> None:
        """`OQ-16`: o registro real de `B3.01` não distingue qualidade —
        qualquer valor concreto (`Decimal`) informado é lido igual,
        independentemente de o aluno considerá-lo "confirmado" ou
        "estimado". Este teste prova que dois valores concretos idênticos,
        vindos de respostas distintas, produzem o mesmo total."""
        respostas_a = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )
        respostas_b = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )

        estado_a = _montar(respostas_a)
        estado_b = _montar(respostas_b)

        assert estado_a.RENDA_TOTAL_RECORRENTE == estado_b.RENDA_TOTAL_RECORRENTE

    def test_renda_principal_desconhecida_produz_erro_explicito_nunca_valor_inventado(
        self,
    ) -> None:
        """`OQ-16`: `DESCONHECIDA` produz `DESCONHECIDO`, nunca uma
        estimativa — como `RENDA_TOTAL_RECORRENTE` é `Dinheiro` puro
        (`engine/estado.py`, sem união com `Desconhecido`), a tradução
        correta é erro explícito nomeado, nunca um `0`/valor inventado
        (`ErroCampoAgregadoDesconhecido`, mesmo padrão de
        `_economia_potencial_imediata`)."""
        respostas = _respostas_minimas_completas(RENDA_PRINCIPAL=NAO_SEI)

        with pytest.raises(ErroCampoAgregadoDesconhecido) as excecao:
            _montar(respostas)

        assert excecao.value.VARIAVEL_GRAVADA == "RENDA_PRINCIPAL"

    def test_renda_principal_sem_resposta_produz_erro_explicito(self) -> None:
        respostas = _respostas_minimas_completas(RENDA_PRINCIPAL=_OMITIR)

        with pytest.raises(ErroCampoAgregadoDesconhecido) as excecao:
            _montar(respostas)

        assert excecao.value.VARIAVEL_GRAVADA == "RENDA_PRINCIPAL"

    def test_fonte_adicional_desconhecida_nao_impede_soma_das_demais_conhecidas(
        self,
    ) -> None:
        """Uma ficha de renda adicional com `NAO_SEI` não é a mesma
        situação de `RENDA_PRINCIPAL` desconhecida: a renda adicional é
        aditiva, e uma fonte incerta entre outras conhecidas não apaga as
        conhecidas nem bloqueia o total com erro."""
        respostas_minimas = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )
        fontes = (
            _resposta(
                "RENDA_RECORRENTE_ADICIONAL", converter_para_dinheiro("300,00"), item_id="REND001"
            ),
            _resposta("RENDA_RECORRENTE_ADICIONAL", NAO_SEI, item_id="REND002"),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fontes))

        estado = _montar(respostas)

        assert estado.RENDA_TOTAL_RECORRENTE == Decimal("8300.00")

    # -- RECURSOS_EXTRAORDINARIOS (B3.05) e renda extra potencial (B3.06) --
    def test_recursos_extraordinarios_e_renda_extra_potencial_nunca_somam(self) -> None:
        """`OQ-16`: `RECURSOS_EXTRAORDINARIOS_EXISTE`/`B3.05*` e `B3.06*`
        nunca entram em `RENDA_TOTAL_RECORRENTE`, mesmo quando
        preenchidos — a prova é que preenchê-los não muda o total."""
        respostas_sem_extraordinario = _respostas_minimas_completas(
            RENDA_PRINCIPAL=converter_para_dinheiro("8.000,00")
        )
        respostas_com_extraordinario = RespostasCaso(
            respostas=(
                *respostas_sem_extraordinario.respostas,
                _resposta("RECURSOS_EXTRAORDINARIOS_EXISTE", "SIM"),
                _resposta("VALOR_RECURSO_EXTRAORDINARIO", converter_para_dinheiro("50.000,00")),
                _resposta("RENDA_EXTRA_POTENCIAL_EXISTE", "CONCRETA"),
            )
        )

        estado_sem = _montar(respostas_sem_extraordinario)
        estado_com = _montar(respostas_com_extraordinario)

        assert estado_sem.RENDA_TOTAL_RECORRENTE == estado_com.RENDA_TOTAL_RECORRENTE
        assert estado_com.RENDA_TOTAL_RECORRENTE == Decimal("8000.00")

    # -- DESPESAS_OPERACIONAIS_ATUAIS: categorias parcialmente preenchidas --
    def test_despesas_operacionais_atuais_sem_nenhum_item_e_zero(self) -> None:
        respostas = _respostas_minimas_completas()

        estado = _montar(respostas)

        assert estado.DESPESAS_OPERACIONAIS_ATUAIS == Decimal("0")

    def test_despesas_operacionais_atuais_soma_itens_de_categorias_parcialmente_preenchidas(
        self,
    ) -> None:
        """`B3.D01` a `B3.D11` compartilham o MESMO escopo de ficha
        (`ITEM_DESPESA`) — categorias parcialmente preenchidas (nem toda
        categoria com item marcado) não são caso especial: a soma é sobre
        todos os itens de `ITEM_DESPESA` que de fato existem, venham eles
        de qual categoria for."""
        respostas_minimas = _respostas_minimas_completas()
        itens_despesa = tuple(
            _resposta("VALOR_DESPESA", converter_para_dinheiro(valor), item_id=item_id)
            for item_id, valor in (
                ("DESP001", "1.200,00"),
                ("DESP002", "350,00"),
                ("DESP003", "80,00"),
            )
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *itens_despesa))

        estado = _montar(respostas)

        assert estado.DESPESAS_OPERACIONAIS_ATUAIS == Decimal("1630.00")

    def test_despesas_operacionais_atuais_item_desconhecido_nao_impede_soma_dos_demais(
        self,
    ) -> None:
        respostas_minimas = _respostas_minimas_completas()
        itens_despesa = (
            _resposta("VALOR_DESPESA", converter_para_dinheiro("1.200,00"), item_id="DESP001"),
            _resposta("VALOR_DESPESA", NAO_SEI, item_id="DESP002"),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *itens_despesa))

        estado = _montar(respostas)

        assert estado.DESPESAS_OPERACIONAIS_ATUAIS == Decimal("1200.00")

    # -- DESPESAS_NAO_MENSAIS_NORMALIZADAS: soma anual / 12, Decimal exato --
    def test_despesas_nao_mensais_normalizadas_sem_nenhuma_ficha_e_zero(self) -> None:
        respostas = _respostas_minimas_completas()

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("0")

    def test_despesas_nao_mensais_normalizadas_soma_anual_dividida_por_12_decimal_exato(
        self,
    ) -> None:
        """`OQ-16`: soma dos valores anuais de todas as fichas / 12, com
        `Decimal` exato — nenhum arredondamento intermediário via `float`.
        `6.000,00` / 12 = `500,00` exato; somado a uma segunda ficha de
        `1.200,00` / 12 (não seria a fórmula — a soma é ANTES da divisão):
        (6000 + 1200) / 12 = 600,00 exato."""
        respostas_minimas = _respostas_minimas_completas()
        fichas_nao_mensais = (
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("6.000,00"), item_id="NM001"
            ),
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("1.200,00"), item_id="NM002"
            ),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fichas_nao_mensais))

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("600.00")
        # Precisão exata — nunca 599.99999... ou 600.00000001 por resíduo de
        # float: (6000 + 1200) / 12 em Decimal é exato.
        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("7200.00") / Decimal("12")

    def test_despesas_nao_mensais_normalizadas_valor_nao_divisivel_por_12_mantem_precisao_decimal(
        self,
    ) -> None:
        """Soma que não divide exatamente por 12 continua com `Decimal`
        exato (precisão interna integral, `sdd.config.md` §4), nunca
        arredondado via `float`."""
        respostas_minimas = _respostas_minimas_completas()
        ficha_nao_mensal = _resposta(
            "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("1.000,00"), item_id="NM001"
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, ficha_nao_mensal))

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("1000.00") / Decimal("12")
        assert isinstance(estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS, Decimal)

    # -- T-107 (OQ-16, correção de registro): exclusão de dupla contagem
    # quando DESPESA_NAO_MENSAL_JA_CONTABILIZADA (B3.NM02D) = Sim.
    def test_ficha_ja_contabilizada_sim_nao_contribui_ao_total_anual(self) -> None:
        """Primeiro critério de aceite de `T-107`: uma ficha com
        `DESPESA_NAO_MENSAL_JA_CONTABILIZADA = Sim` é EXCLUÍDA da soma —
        sozinha, o total normalizado é zero, não `6000/12`."""
        respostas_minimas = _respostas_minimas_completas()
        ficha_ja_contabilizada = (
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("6.000,00"), item_id="NM001"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "SIM", item_id="NM001"),
        )
        respostas = RespostasCaso(
            respostas=(*respostas_minimas.respostas, *ficha_ja_contabilizada)
        )

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("0")

    def test_ficha_ja_contabilizada_nao_ou_nao_sei_contribui_normalmente(self) -> None:
        """Segundo critério de aceite de `T-107`: `Não` ou `Não sei`
        (`NAO`/`NAO_SEI`) continuam entrando normalmente na soma — só
        exclusão explícita por `Sim`, nunca por incerteza."""
        respostas_minimas = _respostas_minimas_completas()
        fichas = (
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("1.200,00"), item_id="NM001"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "NAO", item_id="NM001"),
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("2.400,00"), item_id="NM002"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", NAO_SEI, item_id="NM002"),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fichas))

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("3600.00") / Decimal("12")

    def test_tres_fichas_uma_ja_contabilizada_exclui_so_essa_do_total(self) -> None:
        """Terceiro critério de aceite de `T-107` — teste numérico exato: 3
        fichas (`6.000,00`, `1.200,00`, `3.600,00`), a do meio com
        `DESPESA_NAO_MENSAL_JA_CONTABILIZADA = Sim`.
        `DESPESAS_NAO_MENSAIS_NORMALIZADAS` deve ser a soma das OUTRAS
        DUAS dividida por 12 — (6000 + 3600) / 12 = 800,00 exato — nunca a
        soma das três (`900,00`)."""
        respostas_minimas = _respostas_minimas_completas()
        fichas = (
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("6.000,00"), item_id="NM001"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "NAO", item_id="NM001"),
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("1.200,00"), item_id="NM002"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "SIM", item_id="NM002"),
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("3.600,00"), item_id="NM003"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "NAO", item_id="NM003"),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fichas))

        estado = _montar(respostas)

        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("9600.00") / Decimal("12")
        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("800.00")

    def test_leitura_correlaciona_por_item_nao_por_ordem_das_respostas(self) -> None:
        """Quarto critério de aceite de `T-107`: a exclusão é lida por
        ITEM (`valor_no_item`), nunca por índice posicional entre duas
        listas separadas — a ordem em que as respostas de cada variável
        aparecem em `RespostasCaso.respostas` é embaralhada (a ficha
        `Sim` é a PRIMEIRA a gravar `VALOR_DESPESA_NAO_MENSAL`, mas a
        ÚLTIMA a gravar `DESPESA_NAO_MENSAL_JA_CONTABILIZADA`); um
        mecanismo por índice posicional excluiria o item errado."""
        respostas_minimas = _respostas_minimas_completas()
        fichas = (
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("1.200,00"), item_id="NM001"
            ),
            _resposta(
                "VALOR_DESPESA_NAO_MENSAL", converter_para_dinheiro("3.600,00"), item_id="NM002"
            ),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "NAO", item_id="NM002"),
            _resposta("DESPESA_NAO_MENSAL_JA_CONTABILIZADA", "SIM", item_id="NM001"),
        )
        respostas = RespostasCaso(respostas=(*respostas_minimas.respostas, *fichas))

        estado = _montar(respostas)

        # Só NM002 (3.600,00) deve contribuir — NM001 é a ficha "Sim",
        # mesmo sendo a primeira a gravar VALOR_DESPESA_NAO_MENSAL.
        assert estado.DESPESAS_NAO_MENSAIS_NORMALIZADAS == Decimal("3600.00") / Decimal("12")


# ---------------------------------------------------------------------------
# T-52 — INVENTARIO_COMPLETO derivado de B5.FIM02 (CONFIRMACAO_FIM_CADASTRO),
# RF-15, AC-07. Domínio real (collection/registros/bloco-05.yaml, T-17):
# SIM · NAO · NAO_SEI.
# ---------------------------------------------------------------------------
class TestAC07InventarioCompleto:
    def test_sim_produz_inventario_completo_verdadeiro(self) -> None:
        respostas = _respostas_minimas_completas(CONFIRMACAO_FIM_CADASTRO="SIM")

        estado = _montar(respostas)

        assert estado.INVENTARIO_COMPLETO is True

    def test_nao_produz_inventario_completo_falso(self) -> None:
        """AC-07: "Não. Ainda falta pelo menos uma dívida" produz False."""
        respostas = _respostas_minimas_completas(CONFIRMACAO_FIM_CADASTRO="NAO")

        estado = _montar(respostas)

        assert estado.INVENTARIO_COMPLETO is False

    def test_nao_sei_produz_inventario_completo_falso(self) -> None:
        """AC-07: "Não tenho certeza" produz False."""
        respostas = _respostas_minimas_completas(CONFIRMACAO_FIM_CADASTRO="NAO_SEI")

        estado = _montar(respostas)

        assert estado.INVENTARIO_COMPLETO is False

    def test_nao_sei_como_sentinela_nao_sei_tambem_produz_falso(self) -> None:
        """O sentinela NAO_SEI (collection.respostas) também não é SIM —
        mesmo resultado do valor_interno "NAO_SEI" gravado como string."""
        respostas = _respostas_minimas_completas(CONFIRMACAO_FIM_CADASTRO=NAO_SEI)

        estado = _montar(respostas)

        assert estado.INVENTARIO_COMPLETO is False

    def test_ausencia_de_resposta_produz_inventario_completo_falso_nunca_true(self) -> None:
        """Segundo critério de aceite de T-52: B5.FIM02 não respondida
        produz False, nunca True por omissão."""
        respostas = _respostas_minimas_completas(CONFIRMACAO_FIM_CADASTRO=_OMITIR)

        estado = _montar(respostas)

        assert estado.INVENTARIO_COMPLETO is False

    def test_mapeamento_usa_variavel_do_registro_real_do_bloco_5(self) -> None:
        """Terceiro critério de aceite: o mapeamento usa o VARIAVEL_GRAVADA
        real do registro (B5.FIM02), sem literal de enunciado em código."""
        colecao = carregar_registros()
        variaveis_existentes = {
            registro.VARIAVEL_GRAVADA
            for registro in colecao.registros
            if registro.VARIAVEL_GRAVADA is not None
        }

        assert "CONFIRMACAO_FIM_CADASTRO" in variaveis_existentes
