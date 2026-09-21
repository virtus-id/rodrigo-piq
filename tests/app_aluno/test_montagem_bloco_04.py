"""Testes das cinco leituras do Bloco 4 (`T-113`) e da integração com o motor
real (`T-114`) — `RF-36`, `RF-37`, `RF-38`, `RF-44`.

`montar_estado_financeiro` passou a LER de `RespostasCaso` os cinco campos
escalares de reserva e caixa do Bloco 4: `RESERVA_EXISTE` (B4.02),
`RESERVA_TOTAL` (B4.02A), `DISPOSICAO_USO_RESERVA` (B4.03),
`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (B4.03A) e `DINHEIRO_DISPONIVEL`
(B4.01/B4.01A). Este módulo prova cada leitura pela **saída observável** — o
campo do `EstadoFinanceiro` que a montagem devolve —, nunca chamando a função
privada isolada (`sdd.config.md` §5, "comportamento observável, nunca
implementação").

**Tolerância ZERO em todo este arquivo.** `assertar_monetario` (± R$ 0,05) é
proibido aqui: aquela tolerância existe para valor monetário ACUMULADO ao longo
de um ciclo mensal, e nenhum valor desta fatia é acumulado — todos são leitura
direta de uma resposta ou o limite `MIN`/`MAX` de uma única expressão. A régua
é igualdade exata, e `is` para os singletons (`DESCONHECIDO`, membros de enum).

Nenhum `VARIAVEL_GRAVADA`/`valor_interno` é inventado: todos vêm do registro
REAL (`collection/registros/bloco-04.yaml`, `T-17`), e os testes de fidelidade
abaixo o carregam para confrontar, em vez de confiar na transcrição.

REGRAS: `RF-36`, `RF-37`, `RF-38`, `RF-44`, `AC-51`, `AC-52`, `AC-54`, `AC-55`,
`AC-56`, `AC-57`, `AC-58`, `AC-59`, `AC-60`, `AC-67`, `AC-68`, `AC-69`,
`EC-15`, `EC-16`, `EC-17`, `EC-20`
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import (
    ErroCampoAgregadoDesconhecido,
    ErroDinheiroDisponivelIndeterminado,
    ErroRespostaAusente,
    ErroValorInternoDesconhecido,
    montar_divida,
    montar_estado_financeiro,
)
from collection.respostas import NAO_SEI, RespostasCaso
from engine.estado import (
    DISPOSICAO_USO_RESERVA,
    RESERVA_EXISTE,
    EstadoFinanceiro,
)
from engine.motor import calcular_plano
from engine.tipos import DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

# A sentinela "não gravar esta resposta": `montar_respostas_caso` sobrescreve
# valores, e para exercitar a AUSÊNCIA de uma resposta é preciso REMOVÊ-LA da
# base, não sobrescrevê-la. `_sem` abaixo faz isso filtrando as respostas já
# montadas — mais fiel que um sentinela na base, porque age sobre o mesmo
# `RespostasCaso` que a fixture entrega ao resto da suíte.
_PARAMETROS_VERSAO: str = "1.0.1"


def _sem(respostas: RespostasCaso, *variaveis: str) -> RespostasCaso:
    """Devolve as mesmas respostas SEM as `variaveis` nomeadas — a forma de
    reproduzir a AUSÊNCIA ESTRUTURAL de uma pergunta `COND` que a
    `condicao_exibicao` do registro suprimiu (`bloco-04.yaml:36`, `:78-80`,
    `:135-137`, `:157-159`). Filtra só as respostas de caso (`item_id is
    None`); nenhuma ficha repetível é afetada."""
    return RespostasCaso(
        respostas=tuple(r for r in respostas.respostas if r.ID_PERGUNTA not in variaveis)
    )


def _montar(
    *, sobrescritas: dict[str, object] | None = None, remover: tuple[str, ...] = ()
) -> EstadoFinanceiro:
    """Monta o `EstadoFinanceiro` do caso completo com as sobrescritas de
    Bloco 4 pedidas, opcionalmente removendo respostas. Uma `RespostasCaso`
    montada em memória por caso, sem banco — mesmo padrão de
    `test_montagem_estado_financeiro.py`."""
    caso = caso_completo(valores_caso=sobrescritas)
    respostas = _sem(caso.respostas, *remover) if remover else caso.respostas
    return montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# AC-51 — RESERVA_EXISTE: um teste por membro, nenhum colapsado em outro.
# ---------------------------------------------------------------------------
class TestAC51ReservaExiste:
    """`AC-51`, `RF-36` — os três `valor_interno` de B4.02
    (`bloco-04.yaml:52-57`) chegam ao estado como os três membros distintos do
    enum, por `_membro_do_enum`."""

    def test_ac51_reserva_existe_sim(self) -> None:
        """`AC-51` — `B4.02 = SIM` → `RESERVA_EXISTE.SIM`."""
        estado = _montar(sobrescritas={"RESERVA_EXISTE": "SIM"})
        assert estado.RESERVA_EXISTE is RESERVA_EXISTE.SIM

    def test_ac51_reserva_existe_informal_nao_e_colapsado_em_sim_nem_em_nao(self) -> None:
        """`AC-51` — `B4.02 = INFORMAL` → `is RESERVA_EXISTE.INFORMAL`.

        `INFORMAL` é o membro em risco: a §13.1 só distingue `NAO` de
        não-`NAO`, então uma leitura que o colapsasse em `SIM` passaria
        despercebida na aritmética e ainda assim perderia o estado de coleta
        que a devolutiva usa (`OQ-25`).

        A prova de que NENHUM é colapsado em outro é a CARDINALIDADE das três
        leituras, e não três `is not` depois do `is` acima: `mypy --strict`
        estreita o tipo após a primeira identidade e recusa os `is not`
        seguintes como `comparison-overlap` — ele está certo, aqueles seriam
        estaticamente mortos. O conjunto abaixo é a asserção viva e mais
        forte: três respostas distintas produzem três membros distintos."""
        estado = _montar(sobrescritas={"RESERVA_EXISTE": "INFORMAL"})
        assert estado.RESERVA_EXISTE is RESERVA_EXISTE.INFORMAL

        lidos = [
            _montar(sobrescritas={"RESERVA_EXISTE": v}).RESERVA_EXISTE
            for v in ("SIM", "INFORMAL", "NAO")
        ]
        assert len(set(lidos)) == 3
        assert lidos == [RESERVA_EXISTE.SIM, RESERVA_EXISTE.INFORMAL, RESERVA_EXISTE.NAO]

    def test_ac51_reserva_existe_nao(self) -> None:
        """`AC-51` — `B4.02 = NAO` → `RESERVA_EXISTE.NAO`. As respostas
        condicionais suprimidas por `condicao_exibicao` são removidas junto,
        que é a situação real da coleta (`EC-16` prova que isso não é erro)."""
        estado = _montar(
            sobrescritas={"RESERVA_EXISTE": "NAO"},
            remover=("RESERVA_TOTAL", "DISPOSICAO_USO_RESERVA"),
        )
        assert estado.RESERVA_EXISTE is RESERVA_EXISTE.NAO

    def test_ac51_reserva_existe_ausente_e_erro_nomeado_nunca_default(self) -> None:
        """`AC-51`, `RF-36` — B4.02 é `[OBR]` e `admite_nao_sei: false`
        (`bloco-04.yaml:49`, `:63`), e `EstadoFinanceiro.RESERVA_EXISTE` é o
        enum PURO. Ausência é erro explícito, jamais um membro por default."""
        with pytest.raises(ErroRespostaAusente):
            _montar(remover=("RESERVA_EXISTE",))


# ---------------------------------------------------------------------------
# AC-52 — DISPOSICAO_USO_RESERVA: um teste por membro.
# ---------------------------------------------------------------------------
class TestAC52DisposicaoUsoReserva:
    """`AC-52`, `RF-36` — os quatro `valor_interno` de B4.03
    (`bloco-04.yaml:127-133`) chegam como os quatro membros do enum."""

    @pytest.mark.parametrize(
        ("valor_interno", "membro"),
        [
            ("PARTE", DISPOSICAO_USO_RESERVA.PARTE),
            ("GRANDE_PARTE", DISPOSICAO_USO_RESERVA.GRANDE_PARTE),
            ("TALVEZ", DISPOSICAO_USO_RESERVA.TALVEZ),
            ("NAO", DISPOSICAO_USO_RESERVA.NAO),
        ],
    )
    def test_ac52_cada_membro_do_dominio(
        self, valor_interno: str, membro: DISPOSICAO_USO_RESERVA
    ) -> None:
        """`AC-52` — um caso por membro; nenhum colapsado em outro."""
        estado = _montar(sobrescritas={"DISPOSICAO_USO_RESERVA": valor_interno})
        assert estado.DISPOSICAO_USO_RESERVA is membro

    def test_ac52_os_quatro_membros_sao_distintos_entre_si(self) -> None:
        """`AC-52` — a leitura dos quatro produz quatro resultados
        DIFERENTES. Sem esta asserção, uma implementação que devolvesse
        sempre o mesmo membro passaria em três dos quatro casos acima por
        acaso, dependendo da ordem."""
        lidos = {
            _montar(sobrescritas={"DISPOSICAO_USO_RESERVA": v}).DISPOSICAO_USO_RESERVA
            for v in ("PARTE", "GRANDE_PARTE", "TALVEZ", "NAO")
        }
        assert len(lidos) == 4


# ---------------------------------------------------------------------------
# AC-54 — valor_interno fora do domínio.
# ---------------------------------------------------------------------------
class TestAC54ValorInternoForaDoDominio:
    """`AC-54` — um `valor_interno` gravado que não corresponde a nenhum
    membro do enum é falha explícita, nunca um membro "parecido" nem um
    default. Só ocorre se o registro YAML e o enum de `engine/estado.py`
    divergirem (regressão de transcrição) — e é exatamente isso que o erro
    precisa denunciar."""

    def test_ac54_reserva_existe_fora_do_dominio_nomeia_o_enum_e_o_valor(self) -> None:
        """`AC-54` — a mensagem nomeia o enum (`RESERVA_EXISTE`) E o
        `valor_interno` recusado, para que a divergência seja localizável sem
        depurador."""
        with pytest.raises(ErroValorInternoDesconhecido) as capturado:
            _montar(sobrescritas={"RESERVA_EXISTE": "TALVEZ_UM_POUCO"})
        assert capturado.value.enum_alvo is RESERVA_EXISTE
        assert capturado.value.valor_interno == "TALVEZ_UM_POUCO"
        mensagem = str(capturado.value)
        assert "RESERVA_EXISTE" in mensagem
        assert "TALVEZ_UM_POUCO" in mensagem

    def test_ac54_disposicao_uso_reserva_fora_do_dominio_nomeia_o_enum_e_o_valor(self) -> None:
        """`AC-54` — o mesmo para B4.03, provando que a recusa é do mecanismo
        genérico `_membro_do_enum` e não de um `if` escrito por pergunta."""
        with pytest.raises(ErroValorInternoDesconhecido) as capturado:
            _montar(sobrescritas={"DISPOSICAO_USO_RESERVA": "METADE"})
        assert capturado.value.enum_alvo is DISPOSICAO_USO_RESERVA
        assert capturado.value.valor_interno == "METADE"
        mensagem = str(capturado.value)
        assert "DISPOSICAO_USO_RESERVA" in mensagem
        assert "METADE" in mensagem


# ---------------------------------------------------------------------------
# AC-55 — RESERVA_TOTAL "não sei".
# ---------------------------------------------------------------------------
class TestAC55ReservaTotalDesconhecida:
    """`AC-55`, `RF-37` — B4.02A `admite_nao_sei: true`
    (`bloco-04.yaml:84`), e o campo é `DinheiroTalvez` justamente porque a
    Regra 3 da §13.1 EXIGE o estado desconhecido."""

    def test_ac55_nao_sei_vira_desconhecido_e_nunca_zero_nem_none(self) -> None:
        """`AC-55` — `B4.02A = "Não sei."` → `RESERVA_TOTAL is DESCONHECIDO`.
        As duas asserções negativas são o coração do critério: um
        `Decimal("0")` aqui AFIRMARIA que a reserva foi medida e vale zero, e
        um `None` deixaria a decisão para quem consome. Nenhum dos dois é o
        que o aluno disse."""
        estado = _montar(sobrescritas={"RESERVA_TOTAL": NAO_SEI})
        assert estado.RESERVA_TOTAL is DESCONHECIDO
        assert estado.RESERVA_TOTAL != Decimal("0")
        assert estado.RESERVA_TOTAL is not None

    def test_ac55_valor_monetario_e_o_decimal_exato(self) -> None:
        """`AC-55`, `RF-13` — um `Decimal` real é repassado INALTERADO, sem
        arredondamento nem reconversão; igualdade exata, nunca tolerância."""
        estado = _montar(sobrescritas={"RESERVA_TOTAL": converter_para_dinheiro("7.432,19")})
        assert estado.RESERVA_TOTAL == Decimal("7432.19")

    def test_ac55_ausencia_estrutural_vira_desconhecido_e_nao_erro(self) -> None:
        """`AC-55`, `EC-16` — `B4.02 = NAO` suprime B4.02A
        (`condicao_exibicao`, `:78-80`). A ausência vira `DESCONHECIDO`,
        nunca erro e nunca zero."""
        estado = _montar(
            sobrescritas={"RESERVA_EXISTE": "NAO"},
            remover=("RESERVA_TOTAL", "DISPOSICAO_USO_RESERVA"),
        )
        assert estado.RESERVA_TOTAL is DESCONHECIDO


# ---------------------------------------------------------------------------
# AC-56 / EC-15 — VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO.
# ---------------------------------------------------------------------------
class TestAC56ValorMaximoReservaInformado:
    """`AC-56`, `EC-15`, `RF-37` — B4.03A tem TRÊS opções
    (`bloco-04.yaml:153-155`), e duas delas gravam `valor_interno: null`."""

    def test_ac56_nao_sei_vira_desconhecido(self) -> None:
        """`AC-56` — `B4.03A = "Não sei."` → `is DESCONHECIDO`."""
        estado = _montar(sobrescritas={"VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": NAO_SEI})
        assert estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO

    def test_ac56_valor_monetario_e_o_decimal_exato_da_fronteira_unica(self) -> None:
        """`AC-56`, `RF-13` — `B4.03A` com valor monetário produz o `Decimal`
        EXATO vindo da fronteira única (`app/montagem/conversao.py`), sem
        `float` em nenhum ponto do caminho. `"2.500,75"` (formato pt-BR do
        formulário) é exatamente `Decimal("2500.75")` — a igualdade é exata, e
        o tipo é conferido para que um `float` numericamente próximo não
        passasse."""
        estado = _montar(
            sobrescritas={
                "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": converter_para_dinheiro("2.500,75")
            }
        )
        assert estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO == Decimal("2500.75")
        assert isinstance(estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO, Decimal)
        assert not isinstance(estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO, float)

    def test_ec15_opcao_sem_valor_interno_e_o_mesmo_resultado_de_nao_sei(self) -> None:
        """`EC-15` — a opção "Prefiro decidir somente depois de ver a
        análise." (`bloco-04.yaml:154`) grava `valor_interno: null`, IGUAL à
        opção "Não sei." (`:155`). Enquanto `OQ-22`(a) estiver aberta as duas
        são indistinguíveis no dado, e a leitura correta é a MESMA nas duas —
        tratar a primeira como qualquer outra coisa seria inventar uma
        distinção que o registro não grava.

        O teste assere a IGUALDADE dos dois resultados, e não só que cada um é
        `DESCONHECIDO`: é essa igualdade que quebrará no dia em que `OQ-22`(a)
        fechar decidindo distingui-las, avisando que este teste precisa
        acompanhar a mudança de registro."""
        por_nulo = _montar(sobrescritas={"VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": None})
        por_nao_sei = _montar(sobrescritas={"VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": NAO_SEI})
        assert por_nulo.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO
        assert por_nao_sei.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO
        assert (
            por_nulo.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO
            is por_nao_sei.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO
        )


# ---------------------------------------------------------------------------
# AC-57 / AC-58 / AC-59 / EC-20 — DINHEIRO_DISPONIVEL, o único `Dinheiro` PURO.
# ---------------------------------------------------------------------------
class TestAC57DinheiroDisponivelComValor:
    def test_ac57_sim_com_valor_e_o_decimal_exato_sem_typeerror_de_recusar_float(self) -> None:
        """`AC-57`, `RF-38`, `RF-13` — `B4.01 = SIM` + `B4.01A = "1234,56"` →
        `DINHEIRO_DISPONIVEL == Decimal("1234.56")`.

        A construção NÃO levanta o `TypeError` de
        `engine/estado.py::_recusar_float`: esse guarda percorre os campos do
        `EstadoFinanceiro` no `__post_init__` e recusa qualquer `float`, então
        o simples fato de a montagem TER retornado já prova que nenhum `float`
        atravessou a fronteira. O teste torna essa prova explícita — se um dia
        a conversão passar por `float`, a montagem levantará aqui, e não
        silenciosamente arredondará."""
        estado = _montar(
            sobrescritas={
                "DINHEIRO_DISPONIVEL_EXISTE": "SIM",
                "DINHEIRO_DISPONIVEL": converter_para_dinheiro("1234,56"),
            }
        )
        assert estado.DINHEIRO_DISPONIVEL == Decimal("1234.56")
        assert isinstance(estado.DINHEIRO_DISPONIVEL, Decimal)
        assert not isinstance(estado.DINHEIRO_DISPONIVEL, float)


class TestAC58DinheiroDisponivelZeroLegitimo:
    def test_ac58_nao_e_o_zero_lido_da_resposta_nunca_um_default(self) -> None:
        """`AC-58`, `RF-38` — `B4.01 = NAO` com `B4.01A` suprimida por
        `condicao_exibicao` (`bloco-04.yaml:36`) → o zero da fronteira única.

        Este zero é **legítimo, LIDO de uma resposta**, não um default:
        `B4.01 = NAO` é resposta `[OBR]` AFIRMATIVA — "não possuo dinheiro
        disponível" — e o zero é a transcrição dela. `sdd.config.md` §4 proíbe
        INVENTAR dado, não transcrever um zero declarado; a prova de que a
        montagem não inventa zero por omissão é `AC-59`, logo abaixo, onde a
        MESMA ausência de `B4.01A` SEM o `NAO` levanta erro."""
        estado = _montar(
            sobrescritas={"DINHEIRO_DISPONIVEL_EXISTE": "NAO"},
            remover=("DINHEIRO_DISPONIVEL",),
        )
        assert estado.DINHEIRO_DISPONIVEL == Decimal("0")
        assert isinstance(estado.DINHEIRO_DISPONIVEL, Decimal)


class TestAC59EEC20DinheiroDisponivelIndeterminado:
    """`AC-59`, `EC-20`, `RF-38` — `EstadoFinanceiro.DINHEIRO_DISPONIVEL` é
    `Dinheiro` PURO, sem união com `Desconhecido`: quando a resposta não
    entrega um `Decimal` real nem o "não possuo" afirmativo, não há
    `DESCONHECIDO` a entregar — e zero por omissão seria a estimativa
    silenciosa que `sdd.config.md` §4 proíbe."""

    def test_ac59_ambas_ausentes_levanta_erro_citando_a_variavel(self) -> None:
        """`AC-59` — `B4.01` e `B4.01A` ambas sem resposta →
        `ErroDinheiroDisponivelIndeterminado`, citando a `VARIAVEL_GRAVADA`.
        A montagem NUNCA devolve `0` por omissão."""
        with pytest.raises(ErroDinheiroDisponivelIndeterminado) as capturado:
            _montar(remover=("DINHEIRO_DISPONIVEL_EXISTE", "DINHEIRO_DISPONIVEL"))
        assert capturado.value.VARIAVEL_GRAVADA == "DINHEIRO_DISPONIVEL_EXISTE"
        assert "DINHEIRO_DISPONIVEL_EXISTE" in str(capturado.value)

    def test_ac59_sim_com_b4_01a_ausente_levanta_erro_citando_a_variavel(self) -> None:
        """`AC-59` — `B4.01 = SIM` com `B4.01A` ausente: o aluno afirmou
        possuir, mas não disse quanto. Erro nomeado, jamais zero — a
        contraprova direta de `AC-58`, com a MESMA ausência de `B4.01A` e
        resultado oposto, porque a resposta de `B4.01` é outra."""
        with pytest.raises(ErroDinheiroDisponivelIndeterminado) as capturado:
            _montar(
                sobrescritas={"DINHEIRO_DISPONIVEL_EXISTE": "SIM"},
                remover=("DINHEIRO_DISPONIVEL",),
            )
        assert capturado.value.VARIAVEL_GRAVADA == "DINHEIRO_DISPONIVEL"

    def test_ac59_sim_com_b4_01a_nao_sei_levanta_erro(self) -> None:
        """`AC-59` — `B4.01 = SIM` com `B4.01A = NAO_SEI`. B4.01A tem
        `admite_nao_sei: false` (`bloco-04.yaml:40`), então este par não
        deveria existir na coleta; se existir no dado, é erro nomeado e nunca
        um zero."""
        with pytest.raises(ErroDinheiroDisponivelIndeterminado):
            _montar(
                sobrescritas={
                    "DINHEIRO_DISPONIVEL_EXISTE": "SIM",
                    "DINHEIRO_DISPONIVEL": NAO_SEI,
                }
            )

    def test_ec20_nao_sei_com_b4_01a_nao_exibida_levanta_a_mesma_excecao(self) -> None:
        """`EC-20` — `B4.01 = NAO_SEI` (`bloco-04.yaml:18`) com `B4.01A` não
        exibida (`condicao_exibicao` exige `SIM`, `:36`) → a MESMA exceção
        nomeada. "Não sei ao certo" não é "não possuo": colapsá-lo em zero
        seria inventar a resposta que o aluno declarou não ter."""
        with pytest.raises(ErroDinheiroDisponivelIndeterminado) as capturado:
            _montar(
                sobrescritas={"DINHEIRO_DISPONIVEL_EXISTE": "NAO_SEI"},
                remover=("DINHEIRO_DISPONIVEL",),
            )
        assert capturado.value.VARIAVEL_GRAVADA == "DINHEIRO_DISPONIVEL_EXISTE"

    def test_ec20_a_excecao_e_capturavel_distintamente_das_outras_duas(self) -> None:
        """`EC-20` — `ErroDinheiroDisponivelIndeterminado` é capturável
        DISTINTAMENTE de `ErroRespostaAusente` e de
        `ErroCampoAgregadoDesconhecido`: a chamadora precisa poder reagir a
        "o caixa é indeterminado" sem varrer junto "faltou uma resposta de
        ficha de dívida" nem "um agregado do Bloco 3 ficou desconhecido".

        Duas provas independentes: (a) as três classes não são parentes entre
        si em NENHUMA direção, então `except` de uma jamais captura outra; e
        (b) o caminho real de `EC-20` não é capturado por `except` das outras
        duas — verificado executando de verdade, não por inspeção de
        hierarquia apenas."""
        assert not issubclass(ErroDinheiroDisponivelIndeterminado, ErroRespostaAusente)
        assert not issubclass(ErroDinheiroDisponivelIndeterminado, ErroCampoAgregadoDesconhecido)
        assert not issubclass(ErroRespostaAusente, ErroDinheiroDisponivelIndeterminado)
        assert not issubclass(ErroCampoAgregadoDesconhecido, ErroDinheiroDisponivelIndeterminado)

        try:
            _montar(
                sobrescritas={"DINHEIRO_DISPONIVEL_EXISTE": "NAO_SEI"},
                remover=("DINHEIRO_DISPONIVEL",),
            )
        except (ErroRespostaAusente, ErroCampoAgregadoDesconhecido) as erro:  # pragma: no cover
            pytest.fail(f"EC-20 foi capturado pela exceção errada: {type(erro).__name__}")
        except ErroDinheiroDisponivelIndeterminado:
            pass
        else:  # pragma: no cover
            pytest.fail("EC-20 deveria ter levantado ErroDinheiroDisponivelIndeterminado")


# ---------------------------------------------------------------------------
# EC-16 / EC-17 — as duas ausências estruturais em cadeia.
# ---------------------------------------------------------------------------
class TestEC16EEC17AusenciasEstruturais:
    def test_ec16_reserva_existe_nao_com_condicionais_ausentes_nao_levanta(self) -> None:
        """`EC-16` — `B4.02 = NAO` suprime B4.02A, B4.02B e B4.03
        (`condicao_exibicao`, `:78-80`, `:105-107`, `:135-137`) e, por cadeia,
        B4.03A. A montagem **não levanta erro**: campo condicional ausente não
        é erro. Os três resultados são a leitura de fato — `NAO`,
        `DESCONHECIDO` e `NAO`."""
        estado = _montar(
            sobrescritas={"RESERVA_EXISTE": "NAO"},
            remover=(
                "RESERVA_TOTAL",
                "DISPOSICAO_USO_RESERVA",
                "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",
            ),
        )
        assert estado.RESERVA_EXISTE is RESERVA_EXISTE.NAO
        assert estado.RESERVA_TOTAL is DESCONHECIDO
        assert estado.DISPOSICAO_USO_RESERVA is DISPOSICAO_USO_RESERVA.NAO

    def test_ec17_disposicao_nao_com_b4_03a_ausente_nao_levanta(self) -> None:
        """`EC-17` — `B4.03 = NAO` suprime B4.03A (`condicao_exibicao`,
        `:157-159`). Sem erro; `DISPOSICAO_USO_RESERVA is NAO` e
        `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO`.

        Aqui `RESERVA_EXISTE` continua `SIM` e `RESERVA_TOTAL` continua um
        valor real: é o aluno que TEM reserva e escolheu preservá-la. **A
        montagem não antecipa o zero** — este teste não assere `RESERVA_
        MOBILIZAVEL` em lugar nenhum, porque a §13.1 é do motor (`RF-44`), e
        asserir aqui o zero que a Regra 1 produzirá seria exatamente
        reproduzir a regra no teste do app."""
        estado = _montar(
            sobrescritas={"RESERVA_EXISTE": "SIM", "DISPOSICAO_USO_RESERVA": "NAO"},
            remover=("VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",),
        )
        assert estado.DISPOSICAO_USO_RESERVA is DISPOSICAO_USO_RESERVA.NAO
        assert estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO
        assert estado.RESERVA_EXISTE is RESERVA_EXISTE.SIM
        assert estado.RESERVA_TOTAL == Decimal("10000.00")


# ---------------------------------------------------------------------------
# AC-60 — as três coleções são `()` mesmo com as fichas preenchidas.
# ---------------------------------------------------------------------------
# Fichas de patrimônio do Bloco 4 pelos `VARIAVEL_GRAVADA` REAIS do registro
# (`collection/registros/bloco-04.yaml`): investimento (B4.04/B4.04B), imóvel
# (B4.I01/B4.I03), veículo (B4.V01/B4.V03) e outro ativo (B4.O01/B4.O03). Só
# `INVESTIMENTOS_EXISTE` tem `valor_interno` no registro hoje; os `EXISTE` das
# outras três gravam `null` — por isso as respostas afirmativas usam o rótulo
# cru daquelas, que é o que a coleta grava. Nada disto é interpretado por
# `montar_estado_financeiro`: é justamente o ponto do critério.
_FICHAS_DE_PATRIMONIO: dict[str, object] = {
    "INVESTIMENTOS_EXISTE": "SIM",
    "VALOR_ESTIMADO_ATIVO (investimento)": converter_para_dinheiro("25.000,00"),
    "IMOVEL_EXISTE": "Sim",
    "VALOR_IMOVEL (= VALOR_ESTIMADO_ATIVO)": converter_para_dinheiro("380.000,00"),
    "VEICULO_EXISTE": "Sim",
    "VALOR_VEICULO (= VALOR_ESTIMADO_ATIVO)": converter_para_dinheiro("62.000,00"),
    "OUTRO_ATIVO_EXISTE": "Sim",
    "VALOR_ESTIMADO_ATIVO (outro)": converter_para_dinheiro("9.000,00"),
}


class TestAC60ColecoesVaziasDeclaradas:
    def test_ac60_as_tres_colecoes_sao_vazias_mesmo_com_as_fichas_preenchidas(self) -> None:
        """`AC-60`, `RF-39`, `EC-19` — `investimentos`, `ativos` e
        `recursos_extraordinarios` são `()` **mesmo com fichas de
        investimento, imóvel, veículo e outro ativo respondidas**.

        A lacuna é do CONTRATO, não da coleta: as três dataclasses de item de
        `engine/estado.py` exigem `CLASSIFICACAO_MOBILIZACAO` e
        `VALOR_LIQUIDO_REALIZAVEL*` como campos obrigatórios sem default, e
        nenhum dos dois é pergunta do questionário — são derivações
        patrimoniais (`motor-calculo:OQ-26` e `OQ-27`, ambas abertas; as DUAS
        precisam estar respondidas, responder só uma não destrava). Derivar
        qualquer um deles aqui seria fórmula patrimonial em `app/`, proibida
        pela Lei nº 3 (`RF-44`).

        Este teste é a prova de que a montagem NÃO tenta preencher as
        coleções a partir do que existe: se algum dia alguém escrever essa
        leitura sem que as duas `OQ` tenham fechado, ele falha aqui."""
        estado = _montar(sobrescritas=_FICHAS_DE_PATRIMONIO)
        assert estado.investimentos == ()
        assert estado.ativos == ()
        assert estado.recursos_extraordinarios == ()

    def test_ac60_as_colecoes_sao_identicas_com_e_sem_as_fichas(self) -> None:
        """`AC-60` — o resultado das três coleções é o MESMO com e sem as
        fichas respondidas. Sem esta asserção, uma leitura parcial que
        devolvesse `()` só por acaso (por exemplo, filtrando tudo por falta de
        classificação) passaria no teste acima."""
        com_fichas = _montar(sobrescritas=_FICHAS_DE_PATRIMONIO)
        sem_fichas = _montar()
        assert com_fichas.investimentos == sem_fichas.investimentos == ()
        assert com_fichas.ativos == sem_fichas.ativos == ()
        assert (
            com_fichas.recursos_extraordinarios == sem_fichas.recursos_extraordinarios == ()
        )


# ---------------------------------------------------------------------------
# T-114 — INTEGRAÇÃO COM O MOTOR REAL: a reserva declarada chega a
# RESERVA_MOBILIZAVEL. `AC-67`, `AC-68`, `AC-69`.
#
# O GANHO OBSERVÁVEL da fatia: antes, `montar_estado_financeiro` não lia o
# Bloco 4 e o estado saía com `RESERVA_EXISTE = NAO`, o que fazia a Regra 1 da
# §13.1 zerar `RESERVA_MOBILIZAVEL` em TODO caso. Agora o aluno que declara ter
# reserva e aceita analisar parte dela vê o valor que ele mesmo declarou.
#
# Os três testes abaixo rodam `calcular_plano` DE VERDADE, com os parâmetros
# reais carregados de `parameters/` — nenhum dublê, nenhum `Diagnostico`
# construído à mão. E a asserção é sobre `snapshot.diagnostico.
# RESERVA_MOBILIZAVEL`, a SAÍDA DO MOTOR, deliberadamente: `RESERVA_MOBILIZAVEL`
# é derivado por `engine/diagnostico.py:788-815` via `engine/ataque_imediato.py
# ::derivar_RESERVA_MOBILIZAVEL`, e reimplementar essa derivação na montagem
# seria erro — esta fatia muda a ENTRADA do motor, nunca a derivação.
# ---------------------------------------------------------------------------


def _reserva_mobilizavel_do_motor(**bloco_04: object) -> object:
    """Roda o motor REAL sobre o caso completo com as sobrescritas de Bloco 4
    pedidas e devolve `snapshot.diagnostico.RESERVA_MOBILIZAVEL`.

    `calcular_plano` de verdade, `FonteParametrosArquivo` de verdade — os 45
    parâmetros lidos de `parameters/`, nunca escritos no teste
    (`sdd.config.md` §4, "zero parâmetro no código"). A dívida do caso
    completo é montada por `montar_divida` a partir das MESMAS respostas, para
    que o motor tenha um inventário real para ranquear."""
    caso = caso_completo(valores_caso=dict(bloco_04))
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    snapshot = calcular_plano(estado, parametros)
    return snapshot.diagnostico.RESERVA_MOBILIZAVEL


class TestT114IntegracaoComOMotorReal:
    def test_ac67_valor_informado_abaixo_do_total_chega_intacto(self) -> None:
        """`AC-67` — `B4.02 = SIM`, `B4.03 = PARTE`, `B4.02A = 10000`,
        `B4.03A = 3000` → `RESERVA_MOBILIZAVEL == Decimal("3000")`.

        É o caso central da fatia: o aluno declarou uma reserva de 10.000 e
        aceitou colocar 3.000 em análise, e o valor que sai do motor é
        exatamente os 3.000 que ele declarou — não o zero de antes, não uma
        fração calculada, não o total. Igualdade EXATA (tolerância zero):
        nenhum valor desta fatia é acumulado."""
        assert _reserva_mobilizavel_do_motor(
            RESERVA_EXISTE="SIM",
            DISPOSICAO_USO_RESERVA="PARTE",
            RESERVA_TOTAL=converter_para_dinheiro("10.000,00"),
            VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=converter_para_dinheiro("3.000,00"),
        ) == Decimal("3000")

    def test_ac68_valor_informado_acima_do_total_e_limitado_pelo_motor(self) -> None:
        """`AC-68` — mesmo caso com `B4.03A = 30000` e `B4.02A = 10000` →
        `RESERVA_MOBILIZAVEL == Decimal("10000")`.

        **O limite é aplicado PELO MOTOR, não pela montagem.**
        `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))` é
        a Regra 2 da §13.1, implementada em
        `engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL` e invocada
        por `engine/diagnostico.py:788-815`. **A montagem não a reproduz em
        lugar nenhum**: `app/montagem/estado.py` lê `RESERVA_TOTAL` e
        `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` como dois campos
        INDEPENDENTES, sem nenhum `min`, `max` ou comparação entre os dois —
        `_reserva_total` e `_valor_maximo_reserva_informado_usuario` nem se
        conhecem.

        É essa ASSIMETRIA que o teste prova: a entrada carrega 30.000 e a
        saída vale 10.000, então alguém aplicou o limite; e como a montagem
        entregou os 30.000 intactos (verificado abaixo, no mesmo teste), quem
        aplicou foi o motor. Se a montagem passasse a "ajudar" limitando na
        entrada, o resultado final continuaria 10.000 e o bug ficaria
        invisível — por isso a asserção sobre o estado montado, e não só sobre
        o diagnóstico, faz parte do critério."""
        sobrescritas: dict[str, object] = {
            "RESERVA_EXISTE": "SIM",
            "DISPOSICAO_USO_RESERVA": "PARTE",
            "RESERVA_TOTAL": converter_para_dinheiro("10.000,00"),
            "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": converter_para_dinheiro("30.000,00"),
        }

        # A ENTRADA do motor: a montagem entrega os 30.000 INTACTOS, sem
        # limitar nada. Se este assert quebrar, a Regra 2 vazou para `app/`.
        estado = _montar(sobrescritas=sobrescritas)
        assert estado.VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO == Decimal("30000.00")
        assert estado.RESERVA_TOTAL == Decimal("10000.00")

        # A SAÍDA do motor: limitada ao total, pela Regra 2 da §13.1.
        assert _reserva_mobilizavel_do_motor(**sobrescritas) == Decimal("10000")

    def test_ac69_valor_desconhecido_nunca_vira_zero_no_caminho(self) -> None:
        """`AC-69` — `B4.02 = SIM`, `B4.03 = TALVEZ`, `B4.03A = "Não sei."` →
        `RESERVA_MOBILIZAVEL is DESCONHECIDO`.

        Nenhum ponto do caminho o converte em zero: nem a montagem (que
        devolve `DESCONHECIDO`, `AC-56`), nem o motor (Regra 3 da §13.1, que
        vence a Regra 2 e devolve o estado desconhecido em vez de `0`, porque
        zero seria uma decisão que o aluno não tomou). `TALVEZ` é deliberado:
        com `NAO` a Regra 1 zeraria antes, e o teste passaria pelo motivo
        errado."""
        mobilizavel = _reserva_mobilizavel_do_motor(
            RESERVA_EXISTE="SIM",
            DISPOSICAO_USO_RESERVA="TALVEZ",
            RESERVA_TOTAL=converter_para_dinheiro("10.000,00"),
            VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=NAO_SEI,
        )
        assert mobilizavel is DESCONHECIDO
        assert mobilizavel != Decimal("0")

    def test_o_ganho_da_fatia_reserva_declarada_deixa_de_sair_zero(self) -> None:
        """`AC-67`, `RF-36`, `RF-37` — a prova do GANHO, por contraste com o
        comportamento anterior à fatia.

        Antes de `T-110`/`T-111` a montagem não lia o Bloco 4 e o estado saía
        com `RESERVA_EXISTE = NAO`, o que fazia a Regra 1 da §13.1 zerar
        `RESERVA_MOBILIZAVEL` para TODO aluno — inclusive o que tinha reserva
        e aceitava usá-la. O teste roda os dois casos pelo motor real: o aluno
        que declara `NAO` continua vendo zero (correto, Regra 1), e o que
        declara `SIM` + `PARTE` + valor passa a ver o valor declarado. São
        resultados DIFERENTES a partir de respostas diferentes — que é
        exatamente o que deixou de acontecer quando o Bloco 4 não era lido."""
        sem_reserva = _reserva_mobilizavel_do_motor(
            RESERVA_EXISTE="NAO",
            DISPOSICAO_USO_RESERVA="NAO",
            RESERVA_TOTAL=NAO_SEI,
            VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=NAO_SEI,
        )
        com_reserva = _reserva_mobilizavel_do_motor(
            RESERVA_EXISTE="SIM",
            DISPOSICAO_USO_RESERVA="PARTE",
            RESERVA_TOTAL=converter_para_dinheiro("10.000,00"),
            VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=converter_para_dinheiro("3.000,00"),
        )
        assert sem_reserva == Decimal("0")
        assert com_reserva == Decimal("3000")
        assert sem_reserva != com_reserva
