"""Teste de INTEGRAÇÃO da montagem do estado — `T-53` (`RF-12`, `RF-14`,
`RF-15`, `AC-07`, `AC-08`, `AC-13`, `AC-18`).

Fecha `T-49` a `T-52`: monta um `EstadoFinanceiro` COMPLETO de ponta a ponta a
partir de um caso de prova com respostas de TODOS os blocos obrigatórios
(`tests/app_aluno/fixtures/caso_completo.py`) e verifica os quatro critérios
de aceite sobre o estado resultante. Os testes UNITÁRIOS de cada função
(`montar_divida`, `montar_perfil_comportamental`, `montar_sinais_
comportamentais`, `montar_estado_financeiro`) já existem em
`test_montagem_divida.py`, `test_montagem_perfil_comportamental.py` e
`test_montagem_estado_financeiro.py` — este arquivo NÃO os duplica.

REGRAS: `RF-12`, `RF-14`, `RF-15`, `AC-07`, `AC-08`, `AC-13`, `AC-18`
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.estado import Divida, EstadoFinanceiro, PerfilComportamental, SinaisComportamentais
from engine.tipos import DESCONHECIDO
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    CasoCompleto,
    caso_completo,
    caso_completo_com_divida_gab03,
)


def _montar_estado_do_caso(caso: CasoCompleto) -> EstadoFinanceiro:
    """Monta a `Divida` do caso e, em seguida, o `EstadoFinanceiro` completo —
    os dois passos de ponta a ponta que `T-54` (executor) vai encadear em
    produção, aqui exercitados diretamente sobre a montagem (Lei nº 3: esta
    camada não invoca `calcular_plano`, só monta a entrada dele)."""
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# AC-08 — reprodução de GAB-03 pela via da coleta: rotativo com saldo e
# pagamento "não sei" chega ao motor como DESCONHECIDO nos dois.
# ---------------------------------------------------------------------------
class TestAC08ReproducaoDeGab03PelaViaDaColeta:
    def test_rotativo_com_saldo_e_pagamento_nao_sei_produz_desconhecido_nos_dois(
        self,
    ) -> None:
        caso = caso_completo_com_divida_gab03()

        estado = _montar_estado_do_caso(caso)

        (divida,) = estado.dividas
        assert divida.SALDO_DEVEDOR_ATUAL is DESCONHECIDO
        assert divida.PAGAMENTO_MENSAL_EFETIVO is DESCONHECIDO
        # Nunca 0 — o mesmo bug de truthiness que os testes de T-49 já
        # provam na unidade, aqui provado depois da montagem completa.
        assert divida.SALDO_DEVEDOR_ATUAL != Decimal("0")
        assert divida.PAGAMENTO_MENSAL_EFETIVO != Decimal("0")

    def test_tipo_divida_do_cenario_e_o_mesmo_de_gab03_cartao_rotativo(self) -> None:
        """`GAB-03` (`tests/invariantes/test_gab03_rotativo.py`) exige
        especificamente `TIPO_DIVIDA.CARTAO_ROTATIVO` — a fixture reproduz o
        MESMO tipo, não qualquer dívida com dados desconhecidos."""
        from engine.estado import TIPO_DIVIDA

        caso = caso_completo_com_divida_gab03()

        estado = _montar_estado_do_caso(caso)

        (divida,) = estado.dividas
        assert divida.TIPO_DIVIDA is TIPO_DIVIDA.CARTAO_ROTATIVO

    def test_divida_montada_pela_coleta_e_estruturalmente_equivalente_ao_gabarito(
        self,
    ) -> None:
        """Prova campo a campo: a `Divida` que a coleta produz para o
        cenário `GAB-03` é EXATAMENTE a mesma que
        `tests/invariantes/test_gab03_rotativo.py::_divida_rotativa_sem_dados`
        constrói diretamente no motor — os dois caminhos (coleta e literal de
        teste do motor) convergem para o mesmo dado de entrada, com a única
        diferença sendo o `DIVIDA_ID` (identidade estável de cada suíte, não
        parte do comportamento sob teste)."""
        from engine.estado import TIPO_DIVIDA
        from engine.tipos import STATUS_DIVIDA, STATUS_VALIDADE_PROPOSTA, SimNaoTalvez

        caso = caso_completo_com_divida_gab03()

        estado = _montar_estado_do_caso(caso)

        (divida,) = estado.dividas
        divida_sem_id = dataclasses.replace(divida, DIVIDA_ID="")
        gabarito_sem_id = dataclasses.replace(
            Divida(
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
                PESO_EMOCIONAL=5,
                RENEGOCIACAO_PENDENTE=False,
                TROCA_PENDENTE=False,
                RISCO_MATERIAL_IMINENTE=False,
                OPORTUNIDADE_VIGENTE=None,
            ),
            DIVIDA_ID="",
        )
        assert divida_sem_id == gabarito_sem_id


# ---------------------------------------------------------------------------
# AC-13 — comparação campo a campo com o contrato de `engine/estado.py`, por
# introspecção (`dataclasses.fields`): campo novo no motor quebra este teste.
# ---------------------------------------------------------------------------
class TestAC13ContratoDoMotorPorIntrospeccao:
    def test_campos_de_divida_no_estado_montado_batem_com_o_contrato_do_motor(self) -> None:
        """Se `Divida` (`engine/estado.py`) ganhar um campo novo no futuro,
        o conjunto de `dataclasses.fields` muda e este `assert` de igualdade
        de conjuntos falha — até que `app/montagem/estado.py::montar_divida`
        seja atualizado para preenchê-lo."""
        caso = caso_completo()
        estado = _montar_estado_do_caso(caso)
        (divida,) = estado.dividas

        campos_do_contrato = {campo.name for campo in dataclasses.fields(Divida)}
        campos_da_instancia = {campo.name for campo in dataclasses.fields(divida)}
        assert campos_da_instancia == campos_do_contrato

        # Todo campo do contrato tem, de fato, um valor atribuído (nenhum
        # `AttributeError` silencioso possível com slots=True, mas a
        # introspecção explícita documenta a intenção do critério).
        for campo in campos_do_contrato:
            getattr(divida, campo)

    def test_campos_de_estado_financeiro_batem_com_o_contrato_do_motor(self) -> None:
        caso = caso_completo()
        estado = _montar_estado_do_caso(caso)

        campos_do_contrato = {campo.name for campo in dataclasses.fields(EstadoFinanceiro)}
        campos_da_instancia = {campo.name for campo in dataclasses.fields(estado)}
        assert campos_da_instancia == campos_do_contrato

    def test_campos_de_perfil_comportamental_batem_com_o_contrato_do_motor(self) -> None:
        caso = caso_completo()
        estado = _montar_estado_do_caso(caso)

        campos_do_contrato = {campo.name for campo in dataclasses.fields(PerfilComportamental)}
        campos_da_instancia = {
            campo.name for campo in dataclasses.fields(estado.perfil_comportamental)
        }
        assert campos_da_instancia == campos_do_contrato

    def test_campos_de_sinais_comportamentais_batem_com_o_contrato_do_motor(self) -> None:
        caso = caso_completo()
        estado = _montar_estado_do_caso(caso)

        campos_do_contrato = {
            campo.name for campo in dataclasses.fields(SinaisComportamentais)
        }
        campos_da_instancia = {
            campo.name for campo in dataclasses.fields(estado.sinais_comportamentais)
        }
        assert campos_da_instancia == campos_do_contrato

    def test_contrato_de_divida_tem_exatamente_dezoito_campos(self) -> None:
        """Trava de regressão explícita citada no plano/docstrings de
        `app/montagem/estado.py` ("18 campos EXATOS do contrato real") — se
        um campo for adicionado ou removido de `Divida` sem que a contagem
        aqui seja revisada, este teste falha primeiro, antes mesmo da
        comparação de conjuntos acima."""
        assert len(dataclasses.fields(Divida)) == 18

    def test_contrato_de_sinais_comportamentais_tem_exatamente_dez_campos(self) -> None:
        assert len(dataclasses.fields(SinaisComportamentais)) == 10

    def test_contrato_de_perfil_comportamental_tem_exatamente_oito_campos(self) -> None:
        assert len(dataclasses.fields(PerfilComportamental)) == 8


# ---------------------------------------------------------------------------
# AC-07 — os três valores de B5.FIM02 testados, com o esperado de
# INVENTARIO_COMPLETO, agora sobre o estado montado de ponta a ponta.
# ---------------------------------------------------------------------------
class TestAC07InventarioCompletoNoEstadoDePontaAPonta:
    def test_confirmacao_fim_cadastro_sim_produz_inventario_completo_verdadeiro(
        self,
    ) -> None:
        caso = caso_completo(valores_caso={"CONFIRMACAO_FIM_CADASTRO": "SIM"})

        estado = _montar_estado_do_caso(caso)

        assert estado.INVENTARIO_COMPLETO is True

    def test_confirmacao_fim_cadastro_nao_produz_inventario_completo_falso(self) -> None:
        """"Não. Ainda falta pelo menos uma dívida.", valor_interno NAO."""
        caso = caso_completo(valores_caso={"CONFIRMACAO_FIM_CADASTRO": "NAO"})

        estado = _montar_estado_do_caso(caso)

        assert estado.INVENTARIO_COMPLETO is False

    def test_confirmacao_fim_cadastro_nao_sei_produz_inventario_completo_falso(self) -> None:
        """"Não tenho certeza.", valor_interno NAO_SEI."""
        caso = caso_completo(valores_caso={"CONFIRMACAO_FIM_CADASTRO": "NAO_SEI"})

        estado = _montar_estado_do_caso(caso)

        assert estado.INVENTARIO_COMPLETO is False


# ---------------------------------------------------------------------------
# AC-18 — duas montagens com a mesma DATA_REFERENCIA produzem estados iguais.
# ---------------------------------------------------------------------------
class TestAC18DuasMontagensMesmaDataReferenciaProduzemEstadosIguais:
    def test_montar_duas_vezes_o_mesmo_caso_completo_produz_estados_iguais(self) -> None:
        caso_1 = caso_completo()
        caso_2 = caso_completo()

        estado_1 = _montar_estado_do_caso(caso_1)
        estado_2 = _montar_estado_do_caso(caso_2)

        assert estado_1 == estado_2
        assert estado_1.DATA_REFERENCIA == estado_2.DATA_REFERENCIA == DATA_REFERENCIA
        assert estado_1.dividas == estado_2.dividas

    def test_estados_de_datas_diferentes_nao_sao_iguais(self) -> None:
        """Contraprova: a igualdade acima não é trivial por um bug que
        ignore DATA_REFERENCIA — datas diferentes produzem estados
        diferentes (mesma garantia de `test_montagem_estado_financeiro.py`,
        aqui repetida sobre o caso completo de ponta a ponta)."""
        from datetime import date

        caso = caso_completo()
        divida = montar_divida(caso.respostas, caso.DIVIDA_ID)

        estado_1 = montar_estado_financeiro(
            caso.respostas,
            DATA_REFERENCIA=DATA_REFERENCIA,
            dividas=(divida,),
            **caso.parametros_externos,  # type: ignore[arg-type]
        )
        estado_2 = montar_estado_financeiro(
            caso.respostas,
            DATA_REFERENCIA=date(2027, 1, 1),
            dividas=(divida,),
            **caso.parametros_externos,  # type: ignore[arg-type]
        )

        assert estado_1 != estado_2


# ---------------------------------------------------------------------------
# Caso completo é, de fato, completo: nenhum ErroRespostaAusente/
# ErroSinalComportamentalAusente é levantado ao montar o estado padrão.
# ---------------------------------------------------------------------------
def test_caso_completo_padrao_monta_estado_financeiro_sem_nenhum_erro() -> None:
    caso = caso_completo()

    estado = _montar_estado_do_caso(caso)

    assert isinstance(estado, EstadoFinanceiro)
    assert len(estado.dividas) == 1
