"""Testes de `collection/condicoes.py` — RF-05, AC-21 (T-10, T-11).

Cobre o interpretador genérico `avaliar` sobre os seis nós de `Condicao`,
pelo comportamento observável (entrada/saída booleana), nunca por
implementação interna. `B12.08` (quatro origens, `RF-05`) é usado como caso
de prova por já ser citado nominalmente em `AC-21` — os valores usados aqui
são fabricados para o teste, não uma transcrição do YAML real (T-19).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from collection.condicoes import (
    CondicaoContem,
    CondicaoE,
    CondicaoExisteItem,
    CondicaoIgual,
    CondicaoNao,
    CondicaoOu,
    ValorResposta,
    avaliar,
)
from collection.registro import EscopoRepeticao


@dataclass(frozen=True, slots=True)
class _RespostasDeTeste:
    """Dublê de `Respostas` (`Protocol`) para teste unitário: um mapa de
    variável escalar mais um mapa de variável repetida por escopo, sem
    depender de `collection/respostas.py` (T-22, ainda não implementada)."""

    escalares: dict[str, ValorResposta] = field(default_factory=dict)
    repetidas: dict[tuple[EscopoRepeticao, str], tuple[ValorResposta, ...]] = field(
        default_factory=dict
    )

    def valor(self, variavel: str) -> ValorResposta | None:
        return self.escalares.get(variavel)

    def valores_do_escopo(
        self, escopo: EscopoRepeticao, variavel: str
    ) -> tuple[ValorResposta, ...]:
        return self.repetidas.get((escopo, variavel), ())


def test_condicao_igual_verdadeira_quando_variavel_bate_o_valor() -> None:
    respostas = _RespostasDeTeste(escalares={"RISCO_PRINCIPAL_RECAIDA": "CARTAO"})
    condicao = CondicaoIgual(variavel="RISCO_PRINCIPAL_RECAIDA", valor="CARTAO")
    assert avaliar(condicao, respostas) is True


def test_condicao_igual_falsa_quando_variavel_ausente_sem_levantar_excecao() -> None:
    """Variável ausente de `respostas` avalia como falso, sem exceção."""
    respostas = _RespostasDeTeste()
    condicao = CondicaoIgual(variavel="RISCO_PRINCIPAL_RECAIDA", valor="CARTAO")
    assert avaliar(condicao, respostas) is False


def test_condicao_igual_falsa_para_resposta_nao_sei() -> None:
    """`NAO_SEI` não satisfaz `CondicaoIgual` de um valor concreto (AC-21)."""

    class _NaoSeiFalso:
        """Sentinela local só para provar que um valor não-`str` nunca
        satisfaz `CondicaoIgual` — não é o `NaoSei` real de T-22."""

    respostas = _RespostasDeTeste(escalares={"RISCO_PRINCIPAL_RECAIDA": _NaoSeiFalso()})
    condicao = CondicaoIgual(variavel="RISCO_PRINCIPAL_RECAIDA", valor="CARTAO")
    assert avaliar(condicao, respostas) is False


def test_condicao_contem_verdadeira_quando_valor_esta_no_conjunto_marcado() -> None:
    respostas = _RespostasDeTeste(
        escalares={"MECANISMO_DEFICIT": frozenset({"CARTAO", "CHEQUE_ESPECIAL"})}
    )
    condicao = CondicaoContem(variavel="MECANISMO_DEFICIT", valor="CARTAO")
    assert avaliar(condicao, respostas) is True


def test_condicao_contem_falsa_quando_valor_fora_do_conjunto() -> None:
    respostas = _RespostasDeTeste(escalares={"MECANISMO_DEFICIT": frozenset({"CHEQUE_ESPECIAL"})})
    condicao = CondicaoContem(variavel="MECANISMO_DEFICIT", valor="CARTAO")
    assert avaliar(condicao, respostas) is False


def test_condicao_existe_item_verdadeira_quando_algum_item_do_escopo_bate() -> None:
    respostas = _RespostasDeTeste(
        repetidas={
            (EscopoRepeticao.DIVIDA_ID, "TIPO_DIVIDA"): ("CONSIGNADO", "CARTAO")
        }
    )
    condicao = CondicaoExisteItem(
        escopo=EscopoRepeticao.DIVIDA_ID,
        variavel="TIPO_DIVIDA",
        valor_em=frozenset({"CARTAO"}),
    )
    assert avaliar(condicao, respostas) is True


def test_condicao_existe_item_falsa_quando_escopo_sem_itens() -> None:
    respostas = _RespostasDeTeste()
    condicao = CondicaoExisteItem(
        escopo=EscopoRepeticao.DIVIDA_ID,
        variavel="TIPO_DIVIDA",
        valor_em=frozenset({"CARTAO"}),
    )
    assert avaliar(condicao, respostas) is False


def test_condicao_e_exige_todos_os_termos() -> None:
    respostas = _RespostasDeTeste(escalares={"A": "1", "B": "2"})
    condicao = CondicaoE(
        termos=(CondicaoIgual(variavel="A", valor="1"), CondicaoIgual(variavel="B", valor="2"))
    )
    assert avaliar(condicao, respostas) is True

    condicao_falsa = CondicaoE(
        termos=(CondicaoIgual(variavel="A", valor="1"), CondicaoIgual(variavel="B", valor="X"))
    )
    assert avaliar(condicao_falsa, respostas) is False


def test_condicao_nao_inverte_o_termo() -> None:
    respostas = _RespostasDeTeste(escalares={"A": "1"})
    condicao = CondicaoNao(termo=CondicaoIgual(variavel="A", valor="1"))
    assert avaliar(condicao, respostas) is False
    assert avaliar(CondicaoNao(termo=CondicaoIgual(variavel="A", valor="X")), respostas) is True


def test_b12_08_e_um_condicaoou_de_quatro_termos_sem_codigo_especifico_dela() -> None:
    """AC-21: `B12.08` depende de quatro origens — dívida de cartão no
    Bloco 5, `CARTAO` em `MECANISMO_DEFICIT`, `RISCO_PRINCIPAL_RECAIDA =
    CARTAO` ou uma quarta variável equivalente a `B12.01`. É exibida quando
    QUALQUER uma é verdadeira, e oculta quando NENHUMA é."""
    condicao_b12_08 = CondicaoOu(
        termos=(
            CondicaoExisteItem(
                escopo=EscopoRepeticao.DIVIDA_ID,
                variavel="TIPO_DIVIDA",
                valor_em=frozenset({"CARTAO"}),
            ),
            CondicaoContem(variavel="MECANISMO_DEFICIT", valor="CARTAO"),
            CondicaoIgual(variavel="RISCO_PRINCIPAL_RECAIDA", valor="CARTAO"),
            CondicaoIgual(variavel="RECAIDA_PREVISTA_CARTAO", valor="SIM"),
        )
    )

    nenhuma_origem_verdadeira = _RespostasDeTeste(
        escalares={"MECANISMO_DEFICIT": frozenset(), "RISCO_PRINCIPAL_RECAIDA": "OUTRO"}
    )
    assert avaliar(condicao_b12_08, nenhuma_origem_verdadeira) is False

    cada_origem_isolada = (
        _RespostasDeTeste(
            repetidas={(EscopoRepeticao.DIVIDA_ID, "TIPO_DIVIDA"): ("CARTAO",)}
        ),
        _RespostasDeTeste(escalares={"MECANISMO_DEFICIT": frozenset({"CARTAO"})}),
        _RespostasDeTeste(escalares={"RISCO_PRINCIPAL_RECAIDA": "CARTAO"}),
        _RespostasDeTeste(escalares={"RECAIDA_PREVISTA_CARTAO": "SIM"}),
    )
    for respostas_com_uma_origem in cada_origem_isolada:
        assert avaliar(condicao_b12_08, respostas_com_uma_origem) is True
