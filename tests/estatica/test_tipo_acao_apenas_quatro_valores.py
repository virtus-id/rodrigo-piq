"""Domínio fechado de `TIPO_ACAO` como propriedade estrutural — RF-29, AC-49
· plano §R2.9, T-82.

`TIPO_ACAO_VALORES` (`engine/gates.py`, T-79) é o domínio fechado de quatro
literais ASCII — `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}` — que
`AcaoRequerida.TIPO_ACAO: str` deveria sempre respeitar (decisão de plano
R2.2/R2.10: `str` livre, não `Enum`, porque `RF-29`/`OQ-13` já fixaram o tipo;
o domínio fechado não é imposto pelo `mypy`, só por revisão de código e por
este teste estático).

Este módulo prova a propriedade em dois níveis, como pede a tarefa:

1. **`TIPO_ACAO_VALORES` em si** — confere que a constante contém exatamente
   os quatro valores esperados, nenhum a mais nem a menos, ASCII puro (sem
   acento, sem parêntese).
2. **Toda `AcaoRequerida` produzida pelos três gabaritos** — varre
   `particionar_elegibilidade(estado.dividas)` para `GAB-A`, `GAB-B` e
   `GAB-C` (mesmo carregador de `tests/fixtures/carregar.py` usado pelos
   testes de gabarito, `pytest.mark.gabarito`) e falha se algum `TIPO_ACAO`
   emitido estiver fora de `TIPO_ACAO_VALORES`.

**Nota de rastreabilidade — por que a varredura de (2) não encontra nenhuma
`AcaoRequerida` hoje.** Nas fixtures atuais de `GAB-A`/`GAB-B`/`GAB-C`, toda
dívida tem `RISCO_MATERIAL_IMINENTE=False`, `RENEGOCIACAO_PENDENTE=False` e
`TROCA_PENDENTE=False` (`tests/fixtures/gab_{a,b,c}.json`) — os Gates 2 e 3
(únicos pontos que hoje constroem `AcaoRequerida` com `TIPO_ACAO=""`
provisório, ver `engine/gates.py::aplicar_gate_2_contencao_risco`/
`aplicar_gate_3_transformacao`, comentários "provisório — valor real vem de
T-83/T-84") nunca bloqueiam para nenhuma das dívidas dos três gabaritos.
`GAB-A`/`GAB-B` bloqueiam no Gate 1 (que devolve `acao=None`, não constrói
`AcaoRequerida`); `GAB-C` não bloqueia gate nenhum. Verificado empiricamente
antes de escrever este teste: `particionar_elegibilidade(...).ORDEM_ACOES ==
()` nos três casos. A varredura de (2) portanto passa por conjunto vazio —
verificação vácua legítima, não uma lacuna disfarçada: o teste está pronto
para pegar a primeira `AcaoRequerida` com `TIPO_ACAO` fora do domínio assim
que uma fixture ou gabarito futuro disparar Gate 2/Gate 3, e a prova negativa
do item (3) abaixo garante que o mecanismo de verificação em si funciona
mesmo sem depender de uma fixture específica tocar esse caminho.
3. **Prova negativa** (mesmo padrão de
   `tests/estatica/test_nenhum_parametro_no_codigo.py::
   test_detector_pega_caso_proposital_de_parametro_atribuido`): monta uma
   `AcaoRequerida` com um quinto literal fabricado à mão e confere que o
   PRÓPRIO verificador usado em (2) a rejeita — não depende de nenhuma
   fixture tocar Gate 2/Gate 3 para provar que a checagem funciona.
"""

from __future__ import annotations

import pytest

from engine.estado import EstadoFinanceiro
from engine.gates import TIPO_ACAO_VALORES, AcaoRequerida, particionar_elegibilidade
from engine.precisao import dinheiro
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_b, carregar_gab_c

pytestmark = pytest.mark.gabarito


def test_tipo_acao_dominio_fechado_ascii() -> None:
    """AC-49: `TIPO_ACAO_VALORES` contém exatamente os quatro literais do
    domínio fechado — nenhum outro, nenhum acento, nenhum parêntese."""
    assertar_exato(
        TIPO_ACAO_VALORES,
        frozenset({"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}),
    )

    for valor in TIPO_ACAO_VALORES:
        assert valor.isascii(), f"TIPO_ACAO_VALORES contém valor não-ASCII: {valor!r}"
        assert "(" not in valor and ")" not in valor, (
            f"TIPO_ACAO_VALORES contém parêntese: {valor!r}"
        )


def _tipos_acao_fora_do_dominio(acoes: tuple[AcaoRequerida, ...]) -> list[str]:
    """Verificador reaproveitado por (2) e pela prova negativa de (3): devolve
    a lista de `TIPO_ACAO` que NÃO pertencem a `TIPO_ACAO_VALORES`, para que a
    mensagem de falha nomeie o valor intruso."""
    return [acao.TIPO_ACAO for acao in acoes if acao.TIPO_ACAO not in TIPO_ACAO_VALORES]


def _ordem_acoes_dos_tres_gabaritos() -> tuple[AcaoRequerida, ...]:
    """`ORDEM_ACOES` de `GAB-A`, `GAB-B` e `GAB-C` concatenadas, via o mesmo
    `particionar_elegibilidade` (`engine/gates.py`, T-32) usado por
    `tests/gabaritos/test_gabarito_c_recomendacao.py`."""
    estados: tuple[EstadoFinanceiro, ...] = (carregar_gab_a(), carregar_gab_b(), carregar_gab_c())
    acoes: list[AcaoRequerida] = []
    for estado in estados:
        particao = particionar_elegibilidade(estado.dividas)
        acoes.extend(particao.ORDEM_ACOES)
    return tuple(acoes)


def test_tipo_acao_apenas_quatro_valores() -> None:
    """AC-49: varre toda `AcaoRequerida` construída ao rodar os três
    gabaritos (`GAB-A`/`GAB-B`/`GAB-C`) e falha se algum `TIPO_ACAO` estiver
    fora de `TIPO_ACAO_VALORES` — propriedade estrutural, não exemplo
    isolado. Ver nota de rastreabilidade na docstring do módulo sobre por
    que `ORDEM_ACOES` está vazia hoje nos três gabaritos (Gate 2/Gate 3
    nunca bloqueiam nas fixtures atuais)."""
    acoes = _ordem_acoes_dos_tres_gabaritos()

    fora_do_dominio = _tipos_acao_fora_do_dominio(acoes)

    assert not fora_do_dominio, (
        "TIPO_ACAO fora do domínio fechado TIPO_ACAO_VALORES encontrado em "
        f"AcaoRequerida produzida pelos gabaritos: {fora_do_dominio!r}"
    )


def test_verificador_pega_quinto_literal_proposital() -> None:
    """Prova negativa (mesmo padrão de
    `test_nenhum_parametro_no_codigo.py::
    test_detector_pega_caso_proposital_de_parametro_atribuido`): fabrica uma
    `AcaoRequerida` com um quinto valor de `TIPO_ACAO` que não existe em
    `engine/gates.py` hoje e confere que `_tipos_acao_fora_do_dominio` (o
    mesmo verificador usado por `test_tipo_acao_apenas_quatro_valores`) a
    rejeita. Isola a garantia de (2) de depender de uma fixture tocar
    Gate 2/Gate 3 — se alguém introduzir um quinto literal em
    `engine/gates.py` (ex.: `TIPO_ACAO="RENEGOCIAÇÃO"` com acento, ou
    `TIPO_ACAO="(ECONOMIA)"` com parêntese, ou um quinto valor qualquer),
    este teste documenta que o mecanismo de verificação o pegaria."""
    acao_com_quinto_literal = AcaoRequerida(
        ACAO_ID="D999:RENEGOCIACAO_URGENTE",
        DIVIDA_ID="D999",
        TIPO_ACAO="RENEGOCIACAO_URGENTE",  # quinto literal proposital, fora do domínio
        descricao="caso proposital de T-82 — não existe em engine/gates.py real",
        gate_origem=3,
        # T-133 (RF-61/RF-62): irrelevante ao propósito deste teste negativo
        # (domínio de TIPO_ACAO) — dinheiro(0), sem oferta de valor no caso
        # fabricado.
        VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0),
    )

    fora_do_dominio = _tipos_acao_fora_do_dominio((acao_com_quinto_literal,))

    assert fora_do_dominio == ["RENEGOCIACAO_URGENTE"], (
        "esperava que o verificador pegasse o quinto literal proposital, "
        f"obteve: {fora_do_dominio!r}"
    )
