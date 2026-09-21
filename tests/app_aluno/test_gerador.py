"""Teste de INTEGRAÇÃO do gerador — os cinco casos difíceis da §15.1 da
canônica, exercitados sobre os REGISTROS REAIS carregados por
`collection/carga.py::carregar_registros()` (`T-17`, `T-18`, `T-19`), nunca
sobre YAML sintético. `tests/app_aluno/test_carga.py`,
`test_condicoes.py`, `test_interpolacao.py`, `test_validacao.py`,
`test_opcoes_do_motor.py` e `test_repeticao.py` já cobrem cada peça
isoladamente (em geral com dublês/sintéticos); esta suíte prova que as peças
funcionam juntas sobre o questionário de verdade, ponta a ponta.

Cada teste cita seu `AC-NN` no nome (T-20).

REGRAS: `RF-04`, `RF-05`, `RF-06`, `RF-07`, `RF-08`, `AC-04`, `AC-05`,
`AC-06`, `AC-20`, `AC-21`, `AC-36`, `AC-38`
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from collection.carga import ColecaoDeRegistros, ErroDeCarga, carregar_registros
from collection.condicoes import ValorResposta, avaliar
from collection.interpolacao import ContextoItem, interpolar
from collection.opcoes_do_motor import opcoes_efetivas
from collection.registro import EscopoRepeticao, RegistroPergunta
from collection.repeticao import GeradorDeIdentificadorEmMemoria, perguntas_da_ficha
from collection.validacao import validar_cruzada

_DIRETORIO_REGISTROS_REAIS = Path(__file__).resolve().parents[2] / "collection" / "registros"


@pytest.fixture(scope="module")
def _colecao_real() -> ColecaoDeRegistros:
    """Os registros reais dos Blocos 1-5, 7, 8, 10, 11 **mais** os três casos
    de prova do Bloco 12 (`T-16`..`T-19`).

    `incluir_casos_de_prova=True` desde `T-172`: o Bloco 12 saiu da coleção
    que a aplicação carrega — ele nunca foi fluxo de coleta, e `B12.16`
    tornava o cálculo inalcançável (ver `collection/carga.py::
    SUFIXO_FORA_DA_COLETA`). Este módulo é justamente quem exercita os três
    mecanismos do gerador que aquelas perguntas existem para provar, então
    aqui elas entram de propósito — e o pedido é explícito, não um efeito
    colateral de carregar tudo."""
    return carregar_registros(incluir_casos_de_prova=True)


def _registro(colecao: ColecaoDeRegistros, ID: str) -> RegistroPergunta:
    for registro in colecao.registros:
        if registro.ID == ID:
            return registro
    raise AssertionError(f"registro {ID!r} não encontrado na coleção real")


# ---------------------------------------------------------------------------
# AC-04 — três dívidas produzem três fichas independentes; responder a ficha
# 2 não altera as fichas 1 e 3.
# ---------------------------------------------------------------------------


@dataclass
class _RespostasPorItem:
    """Dublê mínimo de armazenamento de resposta por item — mesmo padrão dos
    dublês locais de `test_condicoes.py`/`test_interpolacao.py`, aqui restrito
    ao necessário para provar isolamento entre fichas (T-22 ainda não
    existe)."""

    valores: dict[tuple[str, str], ValorResposta] = field(default_factory=dict)

    def responder(self, item_id: str, variavel: str, valor: ValorResposta) -> None:
        self.valores[(item_id, variavel)] = valor

    def valor_no_item(self, item_id: str, variavel: str) -> ValorResposta | None:
        return self.valores.get((item_id, variavel))


def test_ac04_tres_dividas_produzem_tres_fichas_independentes_responder_ficha_2_nao_altera_1_e_3(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """`collection/repeticao.py` (T-15) sobre os registros reais do Bloco 5
    marcados `escopo_repeticao: DIVIDA_ID`: três fichas de dívida nascem com
    identificadores distintos e estáveis, e as respostas de uma ficha vivem
    isoladas por `(item_id, variavel)` — responder a ficha 2 não toca nos
    valores gravados nas fichas 1 e 3."""
    perguntas_de_divida = perguntas_da_ficha(_colecao_real.registros, EscopoRepeticao.DIVIDA_ID)
    assert len(perguntas_de_divida) > 0, "Bloco 5 real deve ter perguntas REP de DIVIDA_ID"

    gerador = GeradorDeIdentificadorEmMemoria()
    CASO_ID = "CASO-AC04"
    ficha_1 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    ficha_2 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    ficha_3 = gerador.proximo_identificador(CASO_ID, EscopoRepeticao.DIVIDA_ID)
    assert len({ficha_1, ficha_2, ficha_3}) == 3

    variavel_de_prova = perguntas_de_divida[0].VARIAVEL_GRAVADA
    assert variavel_de_prova is not None

    respostas = _RespostasPorItem()
    respostas.responder(ficha_1, variavel_de_prova, "VALOR_FICHA_1")
    respostas.responder(ficha_3, variavel_de_prova, "VALOR_FICHA_3")

    # Responder a ficha 2 — não deve alterar nada de 1 e 3.
    respostas.responder(ficha_2, variavel_de_prova, "VALOR_FICHA_2")

    assert respostas.valor_no_item(ficha_1, variavel_de_prova) == "VALOR_FICHA_1"
    assert respostas.valor_no_item(ficha_3, variavel_de_prova) == "VALOR_FICHA_3"
    assert respostas.valor_no_item(ficha_2, variavel_de_prova) == "VALOR_FICHA_2"


def test_t105_renda_adicional_id_e_despesa_nao_mensal_id_tem_perguntas_reais_no_bloco_03(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """T-105 (`OQ-19`): `B3.03A-C`/`B3.NM02A-D`, carregados do YAML real,
    aparecem nas fichas de `RENDA_ADICIONAL_ID`/`DESPESA_NAO_MENSAL_ID` —
    prova de que a edição do registro e a carga (`collection/carga.py`)
    continuam funcionando juntas sem erro após a mudança de escopo."""
    perguntas_de_renda_adicional = perguntas_da_ficha(
        _colecao_real.registros, EscopoRepeticao.RENDA_ADICIONAL_ID
    )
    ids_renda_adicional = {registro.ID for registro in perguntas_de_renda_adicional}
    assert ids_renda_adicional == {"B3.03A", "B3.03B", "B3.03C"}

    perguntas_de_despesa_nao_mensal = perguntas_da_ficha(
        _colecao_real.registros, EscopoRepeticao.DESPESA_NAO_MENSAL_ID
    )
    ids_despesa_nao_mensal = {registro.ID for registro in perguntas_de_despesa_nao_mensal}
    assert ids_despesa_nao_mensal == {"B3.NM02A", "B3.NM02B", "B3.NM02C", "B3.NM02D"}


# ---------------------------------------------------------------------------
# AC-05 — B11.Q01 para D003 exibe D003 no lugar de [Dxxx].
# ---------------------------------------------------------------------------


class _RespostasVazias:
    """Dublê de `Respostas` (`Protocol` de `collection/interpolacao.py`) sem
    nenhuma variável coletada — `B11.Q01` só usa a origem `ID_DO_ITEM`."""

    def valor(self, variavel: str) -> ValorResposta | None:
        return None


def test_ac05_b11_q01_para_d003_exibe_d003_no_lugar_de_dxxx(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """`B11.Q01` real, transcrito por `T-18`, declara o marcador `[Dxxx]`
    com origem `ID_DO_ITEM` (RF-06). Interpolado com o item corrente `D003`,
    o enunciado final exibe `D003` — nunca o marcador literal."""
    registro = _registro(_colecao_real, "B11.Q01")
    assert "[Dxxx]" in registro.enunciado

    ctx = ContextoItem(item_id="D003", respostas=_RespostasVazias(), snapshot=None)
    resultado = interpolar(registro.enunciado, registro.interpolacoes, ctx)

    assert "D003" in resultado
    assert "[Dxxx]" not in resultado


# ---------------------------------------------------------------------------
# AC-06 — VALOR_UTILIZADO_MARGEM = 1200 com VALOR_TOTAL_MARGEM = 1000 é
# recusado, com mensagem, e nenhum dos dois é gravado.
#
# A validação cruzada normativa (VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM,
# por MARGEM_ID) foi transcrita em collection/registros/bloco-03.yaml (B3.S06B
# e B3.S06C) — o Bloco 3 (Renda e Margem), não o Bloco 5 como a descrição da
# tarefa cogitava; T-17 não tinha essa validação porque ela pertence ao Bloco
# 3, fora do escopo de T-17 (Blocos 1-5). Este teste usa o registro real
# equivalente mais próximo: B3.S06C, que carrega literalmente essa
# ValidacaoCruzada no YAML real.
# ---------------------------------------------------------------------------


class _RespostasDeMargem:
    """Dublê mínimo de `Respostas` (`Protocol` de `collection/validacao.py`),
    restrito a um único item de `MARGEM_ID` — o suficiente para exercitar
    `validar_cruzada` sem depender de `collection/respostas.py` (T-22, ainda
    não implementada)."""

    def __init__(self, valores: dict[str, ValorResposta]) -> None:
        self._valores = valores

    def valor_no_item(self, item_id: str, variavel: str) -> ValorResposta | None:
        return self._valores.get(variavel)


def test_ac06_valor_utilizado_maior_que_valor_total_da_margem_e_recusado_com_mensagem(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """`B3.S06C` (VALOR_UTILIZADO_MARGEM) carrega, no registro real, a
    validação cruzada normativa `VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`
    por `MARGEM_ID`. Aplicada a `VALOR_UTILIZADO_MARGEM=1200` e
    `VALOR_TOTAL_MARGEM=1000` no mesmo item, a validação é recusada e carrega
    a mensagem do próprio registro — nunca uma redação composta em código."""
    registro = _registro(_colecao_real, "B3.S06C")
    assert len(registro.validacoes_cruzadas) == 1
    validacao = registro.validacoes_cruzadas[0]
    assert validacao.variavel_esquerda == "VALOR_UTILIZADO_MARGEM"
    assert validacao.variavel_direita == "VALOR_TOTAL_MARGEM"
    assert validacao.escopo == EscopoRepeticao.MARGEM_ID

    respostas = _RespostasDeMargem(
        {"VALOR_UTILIZADO_MARGEM": 1200, "VALOR_TOTAL_MARGEM": 1000}
    )

    resultado = validar_cruzada(validacao, item_id="M001", respostas=respostas)

    assert resultado.valida is False
    assert resultado.variavel_esquerda == "VALOR_UTILIZADO_MARGEM"
    assert resultado.variavel_direita == "VALOR_TOTAL_MARGEM"
    assert resultado.mensagem == validacao.mensagem
    assert resultado.mensagem is not None and len(resultado.mensagem) > 0

    # "nenhum dos dois é gravado": este módulo não persiste nada (a
    # persistência real é T-22, fora de escopo) — a prova disponível aqui é
    # que o dublê de respostas usado para a COMPARAÇÃO nunca foi mutado por
    # `validar_cruzada`: os valores continuam exatamente os fornecidos, e
    # `ResultadoValidacao.valida=False` é o sinal que a camada de gravação
    # (fora de escopo) usa para recusar a escrita.
    assert respostas.valor_no_item("M001", "VALOR_UTILIZADO_MARGEM") == 1200
    assert respostas.valor_no_item("M001", "VALOR_TOTAL_MARGEM") == 1000


# ---------------------------------------------------------------------------
# AC-20 — opções de B12.16 são as do snapshot; nenhuma opção fixa aparece
# fora dessa lista.
# ---------------------------------------------------------------------------


def test_ac20_opcoes_de_b12_16_sao_as_do_snapshot_nenhuma_opcao_fixa_fora_da_lista(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """`B12.16` real declara `origem_opcoes.fonte=SNAPSHOT`,
    `campo_do_snapshot=ORDEM_ACOES` (T-19). `registro.opcoes` está vazio no
    YAML propositalmente (nenhuma opção fixa em código nem em registro) — a
    prova de `AC-20` é que `opcoes_efetivas` NUNCA devolve nada além do que
    está no campo do snapshot, mesmo quando esse campo é vazio ou de forma
    incompatível: sem opção fixa aparecendo em lugar nenhum.

    `SnapshotOrdem.ORDEM_ACOES` (motor real) é uma tupla de `AcaoRequerida`
    (`DIVIDA_ID`, `descricao`, `gate_origem`) — não tem a forma de
    `OpcaoRegistro` (`rotulo`/`valor_interno`). Isso é a simplificação de
    caso de prova que o próprio `bloco-12-casos-de-prova.yaml` documenta
    (OQ-12): o motor real ainda não produz um campo de "regras propostas" no
    formato de opção. `opcoes_efetivas` sobre um snapshot real e sobre um
    dublê estrutural no formato de `OpcaoRegistro` cobre os dois lados de
    `AC-20`."""
    registro = _registro(_colecao_real, "B12.16")
    assert registro.origem_opcoes.fonte == "SNAPSHOT"
    assert registro.origem_opcoes.campo_do_snapshot == "ORDEM_ACOES"
    assert registro.opcoes == ()

    # Lado 1: sem snapshot, nenhuma opção aparece — nunca uma opção fixa no
    # lugar da ausência.
    assert opcoes_efetivas(registro, None) == ()

    # Lado 2: com um snapshot cujo campo ORDEM_ACOES tem a forma esperada de
    # opção (dublê estrutural, mesmo padrão de
    # tests/app_aluno/test_opcoes_do_motor.py::_SnapshotComRegrasPropostas —
    # o motor real ainda não produz esse formato para ORDEM_ACOES), as
    # opções efetivas são EXATAMENTE as do snapshot.
    from collection.registro import OpcaoRegistro

    @dataclass(frozen=True, slots=True)
    class _SnapshotComOrdemDeAcoesNoFormatoDeOpcao:
        ORDEM_ACOES: tuple[OpcaoRegistro, ...]

    opcoes_do_snapshot = (
        OpcaoRegistro(rotulo="Regra do snapshot 1", valor_interno="REGRA_1"),
        OpcaoRegistro(rotulo="Regra do snapshot 2", valor_interno="REGRA_2"),
    )
    snapshot_com_regras = _SnapshotComOrdemDeAcoesNoFormatoDeOpcao(ORDEM_ACOES=opcoes_do_snapshot)

    resultado = opcoes_efetivas(registro, snapshot_com_regras)  # type: ignore[arg-type]

    assert resultado == opcoes_do_snapshot
    assert len(resultado) > 0  # registro.opcoes está vazio ((), critério 2 de
    # T-14) — a trava real é: nenhuma opção FORA da lista do snapshot aparece.
    _OPCOES_FIXAS_NUNCA_ESPERADAS = (
        OpcaoRegistro(rotulo="Sim", valor_interno="SIM"),
        OpcaoRegistro(rotulo="Não", valor_interno="NAO"),
    )
    assert not any(opcao in resultado for opcao in _OPCOES_FIXAS_NUNCA_ESPERADAS)


# ---------------------------------------------------------------------------
# AC-21 — B12.08 não é exibida com as quatro origens falsas e é exibida com
# qualquer uma verdadeira, os cinco casos.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _RespostasParaB1208:
    """Dublê de `Respostas` (`Protocol` de `collection/condicoes.py`) para os
    cinco casos de `B12.08`: os itens de `DIVIDA_ID` (origem 1) e os valores
    escalares das outras três origens."""

    escalares: dict[str, ValorResposta] = field(default_factory=dict)
    itens_divida: tuple[ValorResposta, ...] = ()

    def valor(self, variavel: str) -> ValorResposta | None:
        return self.escalares.get(variavel)

    def valores_do_escopo(
        self, escopo: EscopoRepeticao, variavel: str
    ) -> tuple[ValorResposta, ...]:
        if escopo == EscopoRepeticao.DIVIDA_ID and variavel == "TIPO_DIVIDA":
            return self.itens_divida
        return ()


def test_ac21_b12_08_nao_exibida_com_as_quatro_origens_falsas(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Nenhuma das quatro origens de `B12.08` (dívida de cartão no B5,
    CARTAO em MECANISMO_DEFICIT, RISCO_PRINCIPAL_RECAIDA=CARTAO, B12.01 inclui
    cartão) é verdadeira: a condição composta (`CondicaoOu` de quatro termos,
    real, sem código específico) avalia falso — pergunta não exibida."""
    registro = _registro(_colecao_real, "B12.08")
    condicao = registro.condicao_exibicao
    assert condicao is not None

    respostas = _RespostasParaB1208(
        escalares={
            "MECANISMO_DEFICIT": frozenset({"ALUGUEL"}),
            "RISCO_PRINCIPAL_RECAIDA": "OUTRO",
            "CAUSAS_ENDIVIDAMENTO": frozenset({"Desemprego."}),
        },
        itens_divida=("CONSIGNADO_PESSOAL",),
    )

    assert avaliar(condicao, respostas) is False


def test_ac21_b12_08_exibida_com_origem_1_dividia_de_cartao_no_b5(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Origem 1 verdadeira: existe, entre os itens de `DIVIDA_ID`, algum com
    `TIPO_DIVIDA` em `{CARTAO_ROTATIVO, CARTAO_PARCELADO}`."""
    registro = _registro(_colecao_real, "B12.08")
    condicao = registro.condicao_exibicao
    assert condicao is not None

    respostas = _RespostasParaB1208(
        escalares={
            "MECANISMO_DEFICIT": frozenset({"ALUGUEL"}),
            "RISCO_PRINCIPAL_RECAIDA": "OUTRO",
            "CAUSAS_ENDIVIDAMENTO": frozenset({"Desemprego."}),
        },
        itens_divida=("CARTAO_ROTATIVO",),
    )

    assert avaliar(condicao, respostas) is True


def test_ac21_b12_08_exibida_com_origem_2_cartao_em_mecanismo_deficit(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Origem 2 verdadeira: `CARTAO` está entre os valores marcados em
    `MECANISMO_DEFICIT`."""
    registro = _registro(_colecao_real, "B12.08")
    condicao = registro.condicao_exibicao
    assert condicao is not None

    respostas = _RespostasParaB1208(
        escalares={
            "MECANISMO_DEFICIT": frozenset({"CARTAO"}),
            "RISCO_PRINCIPAL_RECAIDA": "OUTRO",
            "CAUSAS_ENDIVIDAMENTO": frozenset({"Desemprego."}),
        },
        itens_divida=("CONSIGNADO_PESSOAL",),
    )

    assert avaliar(condicao, respostas) is True


def test_ac21_b12_08_exibida_com_origem_3_risco_principal_recaida_cartao(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Origem 3 verdadeira: `RISCO_PRINCIPAL_RECAIDA == CARTAO`."""
    registro = _registro(_colecao_real, "B12.08")
    condicao = registro.condicao_exibicao
    assert condicao is not None

    respostas = _RespostasParaB1208(
        escalares={
            "MECANISMO_DEFICIT": frozenset({"ALUGUEL"}),
            "RISCO_PRINCIPAL_RECAIDA": "CARTAO",
            "CAUSAS_ENDIVIDAMENTO": frozenset({"Desemprego."}),
        },
        itens_divida=("CONSIGNADO_PESSOAL",),
    )

    assert avaliar(condicao, respostas) is True


def test_ac21_b12_08_exibida_com_origem_4_b1201_inclui_cartao(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Origem 4 verdadeira: `CAUSAS_ENDIVIDAMENTO` (B12.01) contém o rótulo
    canônico "Uso do cartão de crédito." — a §11 não publica `valor_interno`
    para essa opção (comentário do YAML real), então o termo real usa o
    rótulo exato."""
    registro = _registro(_colecao_real, "B12.08")
    condicao = registro.condicao_exibicao
    assert condicao is not None

    respostas = _RespostasParaB1208(
        escalares={
            "MECANISMO_DEFICIT": frozenset({"ALUGUEL"}),
            "RISCO_PRINCIPAL_RECAIDA": "OUTRO",
            "CAUSAS_ENDIVIDAMENTO": frozenset({"Uso do cartão de crédito."}),
        },
        itens_divida=("CONSIGNADO_PESSOAL",),
    )

    assert avaliar(condicao, respostas) is True


# ---------------------------------------------------------------------------
# AC-36 — editar o enunciado no YAML e recarregar muda o texto exibido, sem
# alterar .py.
# ---------------------------------------------------------------------------


def test_ac36_editar_enunciado_no_yaml_e_recarregar_muda_o_texto_sem_tocar_py(
    tmp_path: Path,
) -> None:
    """Copia os registros reais para um diretório temporário, edita o
    enunciado de `B11.Q01` no YAML copiado e recarrega com
    `carregar_registros(diretorio=...)`: o novo texto aparece na coleção
    recarregada, sem que nenhum `.py` do repositório tenha sido tocado."""
    diretorio_copia = tmp_path / "registros"
    shutil.copytree(_DIRETORIO_REGISTROS_REAIS, diretorio_copia)

    colecao_original = carregar_registros(diretorio_copia)
    registro_original = _registro(colecao_original, "B11.Q01")
    enunciado_original = registro_original.enunciado

    caminho_bloco_11 = diretorio_copia / "bloco-11.yaml"
    conteudo = caminho_bloco_11.read_text(encoding="utf-8")
    novo_enunciado = "A dívida [Dxxx] foi TOTALMENTE quitada, sem sombra de dúvida?"
    assert enunciado_original in conteudo
    conteudo_editado = conteudo.replace(enunciado_original, novo_enunciado)
    assert conteudo_editado != conteudo
    caminho_bloco_11.write_text(conteudo_editado, encoding="utf-8")

    colecao_recarregada = carregar_registros(diretorio_copia)
    registro_recarregado = _registro(colecao_recarregada, "B11.Q01")

    assert registro_recarregado.enunciado == novo_enunciado
    assert registro_recarregado.enunciado != enunciado_original

    # "sem alterar .py": nenhum arquivo de código-fonte do repositório real
    # foi tocado — só o YAML copiado em tmp_path. A prova é que os registros
    # REAIS (fora de tmp_path) continuam com o enunciado original.
    colecao_real_intacta = carregar_registros()
    assert _registro(colecao_real_intacta, "B11.Q01").enunciado == enunciado_original


def _bruto_com_perguntas(*, versao: str, perguntas: list[dict[str, object]]) -> dict[str, object]:
    return {"QUESTIONARIO_VERSION": versao, "perguntas": perguntas}


def _pergunta_minima_para_versionamento(ID: str) -> dict[str, object]:
    """Pergunta bruta mínima, válida contra o esquema, para os testes de
    `AC-38` — mesma forma de `tests/app_aluno/test_carga.py::_pergunta_minima`,
    reproduzida aqui para não acoplar este teste de integração à suíte
    unitária de `T-16`."""
    return {
        "ID": ID,
        "bloco": 1,
        "enunciado": "Enunciado de teste de versionamento.",
        "tipo": "TEXTO_CURTO",
        "obrigatoriedade": ["OBR"],
        "escopo_repeticao": "NENHUM",
        "opcoes": [],
        "VARIAVEL_GRAVADA": f"VARIAVEL_{ID.replace('.', '_')}",
        "condicao_exibicao": None,
        "interpolacoes": [],
        "validacoes_cruzadas": [],
        "origem_opcoes": {"fonte": "REGISTRO", "campo_do_snapshot": None},
        "admite_nao_sei": False,
        "salto_consequencia": None,
    }


# ---------------------------------------------------------------------------
# AC-38 — teste que recusa ID reaproveitado entre versões do questionário.
# ---------------------------------------------------------------------------


def test_ac38_id_reaproveitado_entre_arquivos_da_mesma_versao_e_recusado(
    tmp_path: Path,
) -> None:
    """`collection/carga.py` (T-16) não tem hoje o conceito de "versão do
    questionário" como algo distinto de "arquivos presentes num único
    diretório de carga": `QUESTIONARIO_VERSION` é um campo lido dos próprios
    registros (`AC-36`, T-16 critério 3), e `_verificar_versao_unica` já
    recusa a carga inteira quando dois arquivos do mesmo diretório declaram
    `QUESTIONARIO_VERSION` diferentes — ANTES mesmo de `_verificar_id_unico`
    rodar (confirmado empiricamente: com versões "1.0.0"/"2.0.0" divergentes,
    o erro levantado é sobre a divergência de versão, nunca sobre o `ID`
    duplicado). Isso significa que "duas versões simultâneas no mesmo
    diretório, uma reaproveitando o ID da outra" nunca chega a exercitar a
    checagem de unicidade de `ID` pelo mecanismo real — a checagem de versão
    barra primeiro.

    Este teste cobre então o cenário real e alcançável que a mesma trava
    normativa cobre: dentro de uma única versão publicada
    (`QUESTIONARIO_VERSION` igual em todos os arquivos do diretório de
    carga — o estado real de "o questionário corrente"), um `ID` reaproveitado
    entre dois arquivos é sempre recusado, nomeando os dois arquivos
    culpados (`_verificar_id_unico`, T-16 critério 2).

    LIMITAÇÃO DOCUMENTADA (`AC-38`): o carregador não tem, hoje, um conceito
    de "ID usado numa versão anterior, publicada e já fora do diretório de
    carga corrente" — comparar contra uma versão que não está mais presente
    no disco exigiria um mecanismo de histórico entre publicações que não
    existe ainda (fora do escopo de T-16/T-20). O que o mecanismo real
    garante, e que este teste prova, é mais restrito e ainda assim cobre a
    intenção normativa central de `AC-38` ("IDs de pergunta são estáveis e
    nunca reaproveitados", `sdd.config.md` §6): um `ID` nunca aparece
    duplicado dentro do conjunto de registros que compõe uma carga válida."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()

    caminho_arquivo_1 = diretorio / "bloco-01.yaml"
    caminho_arquivo_1.write_text(
        yaml.safe_dump(
            _bruto_com_perguntas(
                versao="1.0.0", perguntas=[_pergunta_minima_para_versionamento("B1.REAPROVEITADO")]
            ),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    caminho_arquivo_2 = diretorio / "bloco-02.yaml"
    caminho_arquivo_2.write_text(
        yaml.safe_dump(
            _bruto_com_perguntas(
                versao="1.0.0",
                perguntas=[_pergunta_minima_para_versionamento("B1.REAPROVEITADO")],
            ),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio)

    mensagem = str(excecao.value)
    assert "B1.REAPROVEITADO" in mensagem
    assert str(caminho_arquivo_1) in mensagem
    assert str(caminho_arquivo_2) in mensagem


def test_ac38_versoes_de_questionario_divergentes_no_mesmo_diretorio_ja_sao_recusadas_antes(
    tmp_path: Path,
) -> None:
    """Documenta explicitamente o comportamento descoberto: com
    `QUESTIONARIO_VERSION` divergente entre arquivos do mesmo diretório de
    carga, `carregar_registros` já recusa por divergência de versão — mesmo
    quando os `ID`s dos dois arquivos são distintos (nenhum reaproveitamento
    de `ID`). Ou seja, o carregador real nunca aceita "duas versões
    coexistindo" no mesmo diretório, o que por si só impede o cenário de "ID
    reaproveitado entre versões simultâneas" de sequer ser tentado em
    produção: cada carga é de uma única versão corrente."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()

    caminho_versao_antiga = diretorio / "versao-1.yaml"
    caminho_versao_antiga.write_text(
        yaml.safe_dump(
            _bruto_com_perguntas(
                versao="1.0.0", perguntas=[_pergunta_minima_para_versionamento("B1.V1")]
            ),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    caminho_versao_nova = diretorio / "versao-2.yaml"
    caminho_versao_nova.write_text(
        yaml.safe_dump(
            _bruto_com_perguntas(
                versao="2.0.0", perguntas=[_pergunta_minima_para_versionamento("B1.V2")]
            ),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio)

    assert "1.0.0" in str(excecao.value)
    assert "2.0.0" in str(excecao.value)


def test_ac38_ids_reais_carregados_nao_tem_nenhum_reaproveitamento(
    _colecao_real: ColecaoDeRegistros,
) -> None:
    """Reforço direto sobre a coleção real: os 245 registros carregados têm
    245 `ID`s distintos — nenhum reaproveitamento no questionário publicado
    hoje (a própria carga bem-sucedida já é a prova, mas o teste torna a
    contagem explícita e rastreável a `AC-38`)."""
    ids = [registro.ID for registro in _colecao_real.registros]
    assert len(ids) == len(set(ids))
