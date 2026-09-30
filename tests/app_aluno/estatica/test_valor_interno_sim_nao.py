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
from datetime import date
from typing import Final

from app.montagem.estado import montar_divida
from collection.carga import carregar_registros
from collection.registro import RegistroPergunta, TipoResposta
from engine.tipos import STATUS_VALIDADE_PROPOSTA
from tests.app_aluno.fixtures.caso_completo import caso_completo

DOMINIO_SIM_NAO: Final[frozenset[str]] = frozenset({"SIM", "NAO", "TALVEZ", "NAO_SEI"})

# `T-208`: opção nula ainda permitida só aqui — decisão pendente. `B5.I02`
# fica por "Outra", sem classificação até a decisão do especialista (`T-218`).
EXCECOES_VALOR_NULO: Final[frozenset[str]] = frozenset({"B5.I02", "B7.16"})

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
