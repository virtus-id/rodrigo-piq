"""Auditoria estática: toda pergunta Sim/Não do registro declara
`valor_interno` em cada opção, e nenhuma pergunta de seleção repete
`valor_interno` entre opções — `T-195` (achado C1 do QA de 2026-09-29),
`RF-03`, `RF-14`, `RF-36`, `AC-13`, `AC-54`.

Sem `valor_interno`, o front grava `''` (`opcao.valor_interno ?? ''`) e a
montagem, que compara literais (`"SIM"`/`"NAO"`/`"NAO_SEI"` em
`app/montagem/estado.py`), lê "nenhuma opção" — `ValueError`, sinal ausente
ou, pior, `False` silencioso (`SEGURO_INCLUIDO_PARCELA`). A convenção é a que
o registro já usava em `B1.02`/`B1.07`: `SIM`/`NAO`/`TALVEZ`/`NAO_SEI`.

`T-208` estende a regra a TODA pergunta de escolha: sem `valor_interno`,
o front desabilita a opção (`T-194`) e o aluno trava — `B3.D01–D10` são OBR.
Exceções de valor nulo, por decisão de negócio em aberto: "Outra" de
`B5.I02` e `B7.16` (`ORIGEM_DADO` derivado — P2). `T-218`: `B5.I02` não
repete mais `valor_interno` — cada fonte tem código próprio. Opção com `abre_campo` (`T-213`,
ex.: "Data" de `B5.B05B`) não precisa de `valor_interno`: grava o valor
digitado.

REGRAS: RF-36, AC-53
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

import pytest

from app.montagem.estado import (
    ErroCampoAgregadoDesconhecido,
    _renda_principal,
    _valor_maximo_reserva_informado_usuario,
    montar_divida,
    montar_estado_financeiro,
)
from collection.carga import carregar_registros
from collection.registro import RegistroPergunta, TipoResposta
from collection.respostas import Resposta, RespostasCaso
from engine.tipos import DESCONHECIDO, STATUS_VALIDADE_PROPOSTA
from tests.app_aluno.fixtures.caso_completo import CasoCompleto, caso_completo

DOMINIO_SIM_NAO: Final[frozenset[str]] = frozenset({"SIM", "NAO", "TALVEZ", "NAO_SEI"})

# `T-208`: opção nula ainda permitida só aqui — decisão pendente. `B5.I02`
# saiu em `T-261`: "Outra" ganhou `OUTRA` com o nível de `DE-06`.
EXCECOES_VALOR_NULO: Final[frozenset[str]] = frozenset({"B7.16"})

_TIPOS_DE_ESCOLHA: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.SELECAO_UNICA, TipoResposta.SELECAO_MULTIPLA, TipoResposta.SIM_NAO_TALVEZ}
)

ID_SEGURO_INCLUIDO_PARCELA: Final[str] = "B5.D05B"


def _registros() -> tuple[RegistroPergunta, ...]:
    return tuple(carregar_registros().registros)


def _eh_sim_nao(registro: RegistroPergunta) -> bool:
    """`SIM_NAO_TALVEZ`, ou `SELECAO_UNICA` cujas opções são só Sim/Não/
    Talvez/Não sei (`B4.I01`, `B4.V01`, ...)."""
    if registro.tipo is TipoResposta.SIM_NAO_TALVEZ:
        return True
    rotulos = {opcao.rotulo for opcao in registro.opcoes}
    return (
        registro.tipo is TipoResposta.SELECAO_UNICA
        and bool(rotulos)
        and rotulos <= {"Sim", "Não", "Talvez", "Não sei"}
    )


def test_nenhuma_pergunta_sim_nao_tem_valor_interno_nulo() -> None:
    violacoes = [
        f"{registro.ID}: {opcao.rotulo!r}"
        for registro in _registros()
        if _eh_sim_nao(registro)
        for opcao in registro.opcoes
        if opcao.valor_interno is None
    ]

    assert not violacoes, "opção Sim/Não sem valor_interno (C1):\n" + "\n".join(violacoes)


def test_t208_nenhuma_pergunta_de_escolha_tem_valor_interno_nulo() -> None:
    violacoes = [
        f"{registro.ID}: {opcao.rotulo!r}"
        for registro in _registros()
        if registro.tipo in _TIPOS_DE_ESCOLHA and registro.ID not in EXCECOES_VALOR_NULO
        for opcao in registro.opcoes
        if opcao.valor_interno is None and opcao.abre_campo is None
    ]

    assert not violacoes, "opção de escolha sem valor_interno (T-208):\n" + "\n".join(violacoes)


def test_t213_opcao_de_data_de_b5b05b_sai_da_excecao_pelo_atributo() -> None:
    """`B5.B05B` não é mais exceção: "Data" é aceita por `abre_campo` e o
    "Não sei." grava `NAO_SEI` (a montagem o lê como `VALIDADE_DESCONHECIDA`)."""
    registro = next(r for r in _registros() if r.ID == "B5.B05B")
    nulas = [o for o in registro.opcoes if o.valor_interno is None and o.abre_campo is None]

    assert nulas == []
    assert "B5.B05B" not in EXCECOES_VALOR_NULO


def test_valor_interno_das_sim_nao_esta_no_dominio_que_a_montagem_compara() -> None:
    violacoes = [
        f"{registro.ID}: {opcao.rotulo!r} -> {opcao.valor_interno!r}"
        for registro in _registros()
        if _eh_sim_nao(registro)
        for opcao in registro.opcoes
        if opcao.valor_interno is not None and opcao.valor_interno not in DOMINIO_SIM_NAO
    ]

    assert not violacoes, "valor_interno fora de SIM/NAO/TALVEZ/NAO_SEI:\n" + "\n".join(violacoes)


def test_nenhuma_pergunta_de_selecao_repete_valor_interno() -> None:
    """Nulos não contam: os checklists `SELECAO_MULTIPLA` sem identificador
    são D1, rastreados à parte."""
    violacoes = []
    for registro in _registros():
        contagem = Counter(o.valor_interno for o in registro.opcoes if o.valor_interno)
        repetidos = sorted(valor for valor, n in contagem.items() if n > 1)
        if repetidos:
            violacoes.append(f"{registro.ID}: {repetidos}")

    assert not violacoes, "valor_interno repetido entre opções:\n" + "\n".join(violacoes)


def test_seguro_incluido_parcela_gravado_pelo_valor_interno_chega_a_montagem() -> None:
    """Reproduz C1 de ponta a ponta: grava cada opção de `B5.D05B` como o
    front grava (`valor_interno ?? ''`) no `caso_completo` e monta a dívida.
    Com `valor_interno` nulo, toda opção vira `''` e nenhuma produz
    `SEGURO_INCLUIDO_PARCELA = True` — o "Sim" do aluno se perdia calado."""
    registro = next(r for r in _registros() if r.ID == ID_SEGURO_INCLUIDO_PARCELA)
    assert registro.VARIAVEL_GRAVADA is not None

    lidos = []
    for opcao in registro.opcoes:
        caso = caso_completo(valores_divida={registro.VARIAVEL_GRAVADA: opcao.valor_interno or ""})
        divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
        lidos.append(divida.SEGURO_INCLUIDO_PARCELA)

    assert lidos.count(True) == 1, (
        f"{ID_SEGURO_INCLUIDO_PARCELA}: esperava exatamente uma opção lida como "
        f"SEGURO_INCLUIDO_PARCELA=True, obtive {lidos}"
    )


def test_t213_b5b05b_com_data_monta_a_divida_com_o_mesmo_status() -> None:
    """A opção "Data" de `B5.B05B` grava `date` em `DATA_VALIDADE_PROPOSTA`;
    a montagem não muda e lê `VALIDADE_DESCONHECIDA`, como antes."""
    caso = caso_completo(
        valores_divida={
            "QUITACAO_CONSULTADA": "SIM",
            "DATA_VALIDADE_PROPOSTA": date(2026, 12, 31),
        }
    )

    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)

    assert divida.STATUS_VALIDADE_PROPOSTA is STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA


# `T-296`: opções além do campo digitado ("R$ ______") em perguntas de valor.
# As de `B3.01` e `B4.03A` ganham código; as demais, em `T-299`.
_OPCOES_DE_VALOR_COM_CODIGO: Final[dict[str, tuple[str, ...]]] = {
    "B3.01": ("RENDA_VARIAVEL",),
    "B4.03A": ("DECIDIR_DEPOIS", "NAO_SEI"),
}


def test_t296_opcoes_alem_do_campo_tem_valor_interno_estavel() -> None:
    registros = {r.ID: r for r in _registros()}
    for id_pergunta, esperados in _OPCOES_DE_VALOR_COM_CODIGO.items():
        alem_do_campo = [o for o in registros[id_pergunta].opcoes if "__" not in o.rotulo]
        assert tuple(o.valor_interno for o in alem_do_campo) == esperados, id_pergunta


def test_t296_montagem_le_as_novas_opcoes_como_antes() -> None:
    """Sem regra nova: "Prefiro decidir depois" segue `DESCONHECIDO`, como
    o nulo de antes (`OQ-22`(a) aberta); "renda variável" segue recusando
    `RENDA_PRINCIPAL` como valor não monetário."""
    def uma(variavel: str, valor: str) -> RespostasCaso:
        resposta = Resposta(
            CASO_ID="C",
            ID_PERGUNTA=variavel,
            item_id=None,
            valor=valor,
            QUESTIONARIO_VERSION="1.0.3",
            respondida_em=datetime(2026, 9, 30, tzinfo=UTC),
        )
        return RespostasCaso(respostas=(resposta,))

    for valor in ("DECIDIR_DEPOIS", "NAO_SEI", ""):
        reserva = uma("VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO", valor)
        assert _valor_maximo_reserva_informado_usuario(reserva) is DESCONHECIDO
    with pytest.raises(ErroCampoAgregadoDesconhecido):
        _renda_principal(uma("RENDA_PRINCIPAL", "RENDA_VARIAVEL"))


# `T-299`: nos tipos de valor, o cliente desenha o campo, o "não sei" (a
# opção com `admite_nao_sei`) e as alternativas com código. Opção nula sem
# `admite_nao_sei` é o próprio campo — "R$ ______", "____ %" (questão de
# especialista, como `B7.13A`), "Data", "Mês/ano" ou a periodicidade do CET.
_TIPOS_DE_VALOR: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.MOEDA, TipoResposta.TAXA, TipoResposta.NUMERO, TipoResposta.DATA}
)
_ROTULOS_DO_CAMPO: Final[frozenset[str]] = frozenset(
    {"Data", "Mês/ano", "+ periodicidade: ao mês / ao ano"}
)


def test_t299_nos_tipos_de_valor_toda_opcao_nula_e_o_proprio_campo() -> None:
    sem_codigo = [
        (r.ID, o.rotulo)
        for r in _registros()
        if r.tipo in _TIPOS_DE_VALOR
        for o in r.opcoes
        if o.valor_interno is None
        and not o.admite_nao_sei
        and "__" not in o.rotulo
        and o.rotulo not in _ROTULOS_DO_CAMPO
    ]

    assert sem_codigo == []


def test_t299_nos_tipos_de_valor_a_opcao_nao_sei_admite_nao_sei() -> None:
    """Sem a marca, o cliente desenharia "Não sei." como alternativa ao
    lado do checkbox — dois "não sei" (`T-207`)."""
    sem_marca = [
        r.ID
        for r in _registros()
        if r.tipo in _TIPOS_DE_VALOR
        for o in r.opcoes
        if o.valor_interno in {"NAO_SEI", "DESCONHECIDA"} and not o.admite_nao_sei
    ]

    assert sem_marca == []


def test_t299_t294_codigos_e_valor_original_nao_mudam_o_calculo() -> None:
    """`VALOR_ORIGINAL` (`T-294`) e os códigos novos de `B5.B02`, `B4.I06` e
    `B4.V09` não são lidos pela montagem: dívida e estado saem iguais."""
    base = caso_completo()
    com_codigos = caso_completo(
        valores_caso={
            "CUSTO_IMOVEL": "SEM_CUSTO_RELEVANTE",
            "CUSTOS_ESTIMADOS_DESMOBILIZACAO (veículo)": "SEM_CUSTO_RELEVANTE",
        },
        valores_divida={
            "QUALIDADE_VALOR_ORIGINAL": "CONFIRMADA",
            "VALOR_ORIGINAL": Decimal("15000.00"),
            "VALOR_JA_PAGO": "APENAS_ESTIMATIVA",
        },
    )

    def montar(caso: CasoCompleto) -> object:
        divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
        estado = montar_estado_financeiro(
            caso.respostas,
            DATA_REFERENCIA=date(2026, 9, 30),
            dividas=(divida,),
            **caso.parametros_externos,  # type: ignore[arg-type]
        )
        return divida, estado

    assert montar(com_codigos) == montar(base)
