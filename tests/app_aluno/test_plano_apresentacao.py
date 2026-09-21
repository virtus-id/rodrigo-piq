"""O plano é legível para o ALUNO, não para o motor — `RF-13`, `AC-37`
(T-177).

**Origem: olhar a tela do primeiro plano liberado de verdade.** O ciclo real
de 2026-09-19 (coleta inteira respondida pela interface, cálculo por HTTP,
liberação pela fila) produziu um plano correto e ilegível:

    73640.56                          ← quanto custa, sem dizer que é dinheiro
    0.04                              ← a taxa, na unidade interna do motor
    VALOR_RELEVANTE_PARA_QUITACAO     ← o nome da variável, ao aluno

Nenhum teste pegava isso: todos comparavam o valor exibido com o valor do
snapshot — e os dois eram, de fato, iguais. A asserção provava fidelidade
ao dado e nada dizia sobre legibilidade.

**A persona torna isto grave.** Um servidor público endividado, com baixa
familiaridade financeira presumida, recebendo o documento que esperou
semanas: `0.04` não é "quatro por cento" para ele, e
`VALOR_RELEVANTE_PARA_QUITACAO` pede que aprenda o vocabulário interno do
motor para ler o próprio plano.

**Por que o servidor formata.** `RF-13` fixa a fronteira de dinheiro no
servidor; o cliente exibe verbatim (`AC-14`). Formatar no React deixaria o
PDF (WeasyPrint, sem JavaScript) de fora, e criaria duas implementações da
mesma regra.

REGRAS: `RF-13`, `RF-21`, `AC-14`, `AC-37`
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from report.plano import (
    carregar_textos_canonicos,
    formatar_dinheiro_br,
    formatar_escala_br,
    formatar_taxa_br,
)

REGRAS: Final[tuple[str, ...]] = ("RF-13", "RF-21", "AC-14", "AC-37")


# ---------------------------------------------------------------------------
# Dinheiro — `R$ 1.234,56`, nunca `1234.56`
# ---------------------------------------------------------------------------


def test_dinheiro_sai_com_simbolo_virgula_e_milhar() -> None:
    """A mesma escrita que o aluno usa para DIGITAR dinheiro
    (`frontend/src/mascaras.ts::formatarMoeda`) — as duas pontas escrevem
    igual, senão ele vê um formato ao responder e outro ao ler o plano."""
    assert formatar_dinheiro_br(Decimal("73640.56")) == "R$ 73.640,56"
    assert formatar_dinheiro_br(Decimal("3000.00")) == "R$ 3.000,00"
    assert formatar_dinheiro_br(Decimal("999.90")) == "R$ 999,90"
    assert formatar_dinheiro_br(Decimal("1234567.89")) == "R$ 1.234.567,89"


def test_dinheiro_zero_nao_vira_vazio() -> None:
    """Zero é um valor, não ausência. `RF-16`/`AC-70` já proíbem converter
    desconhecido em zero; o inverso — apagar um zero legítimo — enganaria
    igual."""
    assert formatar_dinheiro_br(Decimal("0.00")) == "R$ 0,00"


def test_dinheiro_sempre_tem_duas_casas() -> None:
    """`R$ 1.200,5` não é como se escreve dinheiro."""
    assert formatar_dinheiro_br(Decimal("1200.5")) == "R$ 1.200,50"
    assert formatar_dinheiro_br(Decimal("1200")) == "R$ 1.200,00"


# ---------------------------------------------------------------------------
# Taxa — `4,2% a.m.`, nunca `0.042`
# ---------------------------------------------------------------------------


def test_taxa_sai_em_percentual_com_periodo() -> None:
    """O motor guarda fração (`0.042`) porque é a unidade em que a
    matemática financeira opera; `4,2%` é a MESMA grandeza na unidade em que
    uma pessoa lê. `converter_para_taxa` faz a viagem inversa na entrada.

    O `a.m.` não é enfeite: a variável é `TAXA_EFETIVA_MENSAL_NORMALIZADA`,
    e "4,2%" sozinho seria lido como anual por muita gente."""
    assert formatar_taxa_br(Decimal("0.042")) == "4,2% a.m."
    assert formatar_taxa_br(Decimal("0.069")) == "6,9% a.m."
    assert formatar_taxa_br(Decimal("0.018")) == "1,8% a.m."


def test_taxa_redonda_nao_mostra_casa_decimal_vazia() -> None:
    """`10% a.m.`, não `10,00% a.m.` — zero à direita não informa nada."""
    assert formatar_taxa_br(Decimal("0.10")) == "10% a.m."
    assert formatar_taxa_br(Decimal("0.00")) == "0% a.m."


def test_taxa_nunca_sai_em_notacao_cientifica() -> None:
    """`Decimal.normalize()` devolve `1E+1` para alguns valores. Um plano
    de quitação com notação científica é ilegível para a persona."""
    for bruto in ("0.1", "0.01", "0.001", "1.0", "0.10"):
        assert "E" not in formatar_taxa_br(Decimal(bruto))


# ---------------------------------------------------------------------------
# Escala 0–10 — `6 de 10`, nunca `6.00`
# ---------------------------------------------------------------------------


def test_escala_diz_o_que_o_numero_e() -> None:
    """`PESO_EMOCIONAL` é `ESCALA_0_10`; o motor o carrega como `Decimal`
    só para caber no mesmo mapa dos monetários. `6.00` sugere precisão
    decimal que a escala não tem."""
    assert formatar_escala_br(Decimal("6.00")) == "6 de 10"
    assert formatar_escala_br(Decimal("0")) == "0 de 10"
    assert formatar_escala_br(Decimal("10")) == "10 de 10"


# ---------------------------------------------------------------------------
# Rótulos — vocabulário do aluno, e fora do `.py`
# ---------------------------------------------------------------------------


def test_os_rotulos_traduzem_as_variaveis_que_o_motor_emite() -> None:
    """Toda chave que `engine/ordem.py::_valores_de_apoio` pode emitir tem
    rótulo em português.

    A lista é a daquela função; se o motor passar a emitir uma chave nova
    sem rótulo aqui, o aluno volta a ver o nome técnico — e este teste
    avisa antes disso chegar à tela."""
    emitidas_pelo_motor = {
        "SALDO_DEVEDOR_ATUAL",
        "VALOR_RELEVANTE_PARA_QUITACAO",
        "PAGAMENTO_MENSAL_EFETIVO",
        "TAXA_EFETIVA_MENSAL_NORMALIZADA",
        "CET",
        "PESO_EMOCIONAL",
    }
    rotulos = carregar_textos_canonicos().rotulos_de_apoio

    faltando = emitidas_pelo_motor - set(rotulos)
    assert not faltando, f"sem rótulo ao aluno: {sorted(faltando)}"


def test_a_primeira_posicao_explica_diferente_das_seguintes() -> None:
    """`T-177` — a mesma frase nas N posições parecia template, não
    explicação.

    "Esta é a de menor valor para quitar" é verdade na posição 1 e FALSA da
    2 em diante: há uma menor acima dela. Cada método declara duas redações,
    e a escolha é pelo índice."""
    por_metodo = carregar_textos_canonicos().explicacao_da_posicao

    assert por_metodo, "nenhuma explicação ao aluno cadastrada"
    for metodo, redacoes in por_metodo.items():
        assert set(redacoes) == {"primeira", "seguintes"}, (
            f"{metodo} precisa das duas redações"
        )
        assert redacoes["primeira"] != redacoes["seguintes"], (
            f"{metodo}: as duas redações são iguais — volta a parecer template"
        )


def test_todo_metodo_do_motor_tem_explicacao_ao_aluno() -> None:
    """Os três membros de `METODO` (engine/tipos.py). Um método novo sem
    redação cai na justificativa técnica — visível, mas é o defeito que
    `T-177` corrigiu."""
    por_metodo = carregar_textos_canonicos().explicacao_da_posicao

    faltando = {"AVALANCHE", "BOLA_DE_NEVE", "HIBRIDO"} - set(por_metodo)
    assert not faltando, f"sem explicação ao aluno: {sorted(faltando)}"


def test_a_explicacao_ao_aluno_nao_cita_o_vocabulario_do_motor() -> None:
    """Nada de `BOLA_DE_NEVE`, `VALOR_RELEVANTE_PARA_QUITACAO` ou `O-05` na
    redação que o aluno lê — era exatamente o que ele via antes."""
    proibidos = (
        "BOLA_DE_NEVE",
        "AVALANCHE",
        "HIBRIDO",
        "VALOR_RELEVANTE_PARA_QUITACAO",
        "BENEFICIO_MARGINAL_AMORTIZACAO",
        "O-04",
        "O-05",
    )
    for metodo, redacoes in carregar_textos_canonicos().explicacao_da_posicao.items():
        for quando, texto in redacoes.items():
            for termo in proibidos:
                assert termo not in texto, f"{metodo}/{quando} cita {termo!r} ao aluno"


def test_as_pendencias_sao_ditas_em_portugues() -> None:
    """O aviso de plano provisório dizia "falta VALOR_QUITACAO_HOJE, CET,
    PARCELA_CONTRATUAL". O aluno precisa saber o que buscar no extrato, não
    como o campo se chama no código."""
    rotulos = carregar_textos_canonicos().rotulos_de_pendencia

    assert rotulos, "nenhum rótulo de pendência cadastrado"
    for campo, rotulo in rotulos.items():
        assert rotulo != campo
        assert not rotulo.isupper(), f"{campo} → {rotulo!r} parece variável"


def test_nenhum_rotulo_e_nome_de_variavel() -> None:
    """Um rótulo em CAIXA_ALTA_COM_UNDERSCORE é nome de variável, não
    redação — foi exatamente o defeito que `T-177` corrigiu."""
    for chave, rotulo in carregar_textos_canonicos().rotulos_de_apoio.items():
        assert rotulo != chave, f"{chave} continua exibindo o nome técnico"
        assert not rotulo.isupper(), f"{chave} → {rotulo!r} parece variável"
        assert "_" not in rotulo, f"{chave} → {rotulo!r} parece variável"
