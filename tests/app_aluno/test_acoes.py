"""Testes de `app/motor/acoes.py::acoes_em_acompanhamento` — `RF-17`, `RF-33`,
`AC-41`, `T-74` — e de `perguntas_do_bloco_11`/`tipo_acao_de` — `RF-27`,
`RF-33`, `AC-46`, `T-84`.

Reproduz um gate real (Gate 2/Gate 3) sobre a fixture `caso_completo`,
sobrescrevendo `RISCO_MATERIAL_IMINENTE`/`RENEGOCIACAO_PENDENTE`/
`TROCA_PENDENTE` (que `montar_divida` sempre fixa em `False` — T-49, fora do
escopo daquela tarefa) via `dataclasses.replace`, e roda `calcular_plano`
REAL para obter um `SnapshotOrdem` com `ORDEM_ACOES` de fato preenchida — os
quatro critérios de aceite de `T-74` são verificados contra esse snapshot
real, nunca contra um dublê.

Os testes de `T-84` (`Test` `perguntas_do_bloco_11`) usam a MESMA técnica de
`tests/app_aluno/test_acompanhamento_acao_id.py` (T-83): uma `AcaoRequerida`
REAL prova o comportamento sobre o contrato do motor; um objeto de TESTE
prova os casos que o motor não emite a partir deste cenário — sempre lendo o
mapeamento de `collection/registros/bloco-11.yaml` de verdade via
`collection.carga.carregar_registros`, nunca de uma cópia local do YAML.

**A dependência externa CHEGOU (`T-119A`).** `T-84` escreveu dois testes
daqui como SENTINELA de que `engine.gates.AcaoRequerida` ainda não publicava
`TIPO_ACAO` (`OQ-13`): eles afirmavam a ausência do campo e diziam, no
próprio texto, *"se este assert falhar, a dependência externa chegou e `T-84`
precisa ser revisitada"*. A Rodada 2 do slug `motor-calculo` entregou
`ACAO_ID` e `TIPO_ACAO`, os dois testes falharam exatamente como projetado, e
`T-119A` é a revisita que eles mandaram fazer. Onde antes se afirmava
ausência, agora se exercita o comportamento real: `tipo_acao_de` sobre uma
`AcaoRequerida` de verdade DEVOLVE o `TIPO_ACAO` publicado pelo motor, e
`perguntas_do_bloco_11` resolve, com esse valor real, exatamente a pergunta
de resultado do Bloco 11 que o REGISTRO mapeia para ele — o que fecha o
circuito completo motor → registro que `T-84` só pôde provar em duas metades
separadas.

Nenhum teste foi removido, pulado nem enfraquecido: os dois viraram asserções
mais fortes, e `ErroTipoAcaoAusenteDoMotor` continua coberta (a fronteira
ruidosa nunca foi uma marca de "campo não entregue" — é a recusa a escolher
uma pergunta por padrão diante de um objeto que não cumpre o contrato).

REGRAS: RF-17, RF-27, RF-33, AC-41, AC-46
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.acoes import (
    ErroTipoAcaoAusenteDoMotor,
    ErroTipoAcaoDesconhecido,
    acoes_em_acompanhamento,
    perguntas_do_bloco_11,
    tipo_acao_de,
)
from collection.carga import carregar_registros
from engine.gates import AcaoRequerida
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_PARAMETROS_VERSAO: str = "1.0.1"
_ARQUIVO_MODULO = Path(__file__).resolve().parent.parent.parent / "app" / "motor" / "acoes.py"


_DIVIDA_ID_ELEGIVEL: str = "D-CASO-COMPLETO-ELEGIVEL"

# Saldo alto o bastante para que a dívida bloqueada por gate NUNCA seja
# quitada dentro de `P_HORIZONTE_MAXIMO_SIMULACAO` (10 anos, parâmetros
# vigentes) — necessário porque `Cenario.ORDEM_QUITACAO` só lista uma
# dívida quando ela é efetivamente QUITADA na simulação (engine/
# ciclo_mensal.py); se a bloqueada fosse quitável dentro do horizonte, o
# ciclo mensal a incluiria em `ORDEM_QUITACAO` (o `SelecionarAlvo` de cada
# método não conhece a partição de gates), e `publicar_ORDEM_QUITACAO`
# recusaria com `ErroOrdemInconsistente` — não uma falha desta tarefa, mas
# uma característica real do motor (dívida bloqueada só é filtrada na
# publicação final, não durante a simulação em si).
_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")


def _snapshot_com_gates_2_e_3_disparados() -> SnapshotOrdem:
    """Monta um `SnapshotOrdem` real em que UMA dívida do caso dispara o
    Gate 2 (`RISCO_MATERIAL_IMINENTE`) e o Gate 3 (`RENEGOCIACAO_PENDENTE`,
    `TROCA_PENDENTE`) — os dois gates que hoje populam `ORDEM_ACOES`
    (`engine/gates.py`). Como os três campos são sempre `False` na saída de
    `montar_divida` (T-49, decisão documentada naquele módulo), esta função
    sobrescreve a `Divida` já montada, e não a coleta — a única forma de
    exercitar o gate real sem inventar suporte de coleta que T-74 não pede.

    Uma SEGUNDA dívida, sem nenhum gate disparado, é incluída no inventário:
    com uma única dívida bloqueada, `elegiveis == ()` e o motor não teria
    nenhuma dívida para o ciclo mensal ranquear, o que o próprio motor
    recusa como inconsistência (`engine.ordem.ErroOrdemInconsistente`) — a
    segunda dívida é só o mínimo necessário para o motor produzir um
    `SnapshotOrdem` válido com `ORDEM_ACOES` não vazia ao mesmo tempo."""
    caso = caso_completo()
    divida_bloqueada = replace(
        montar_divida(caso.respostas, caso.DIVIDA_ID),
        SALDO_DEVEDOR_ATUAL=_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE,
        RISCO_MATERIAL_IMINENTE=True,
        RENEGOCIACAO_PENDENTE=True,
        TROCA_PENDENTE=True,
    )
    respostas_segunda_divida = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_ELEGIVEL)
    divida_elegivel = montar_divida(respostas_segunda_divida, _DIVIDA_ID_ELEGIVEL)

    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_bloqueada, divida_elegivel),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def test_devolve_exatamente_a_tupla_ordem_acoes_do_snapshot() -> None:
    """Critério 1: a função devolve EXATAMENTE `snapshot.ORDEM_ACOES`, sem
    filtro nem derivação — mesma tupla, mesma identidade de conteúdo."""
    snapshot = _snapshot_com_gates_2_e_3_disparados()

    resultado = acoes_em_acompanhamento(snapshot)

    assert resultado == snapshot.ORDEM_ACOES
    assert len(resultado) > 0, "o caso de prova precisa de fato disparar um gate"
    assert all(isinstance(item, AcaoRequerida) for item in resultado)


def test_nenhuma_derivacao_ou_filtro_sobre_a_tupla() -> None:
    """Critério 1 (parte 2): nenhum item é descartado nem reordenado — a
    função não filtra por `gate_origem`, `prioridade_excepcional` nem
    qualquer outro campo."""
    snapshot = _snapshot_com_gates_2_e_3_disparados()

    resultado = acoes_em_acompanhamento(snapshot)

    assert resultado is snapshot.ORDEM_ACOES or tuple(resultado) == tuple(snapshot.ORDEM_ACOES)
    assert [a.DIVIDA_ID for a in resultado] == [a.DIVIDA_ID for a in snapshot.ORDEM_ACOES]


def test_nenhuma_regex_ou_str_split_ou_in_sobre_descricao() -> None:
    """Critério 2: nenhuma expressão regular ou `str.split`/`in` sobre
    `descricao` existe no módulo — auditado por AST, não por inspeção manual.
    Cobre tanto `re.compile`/`re.match`/... quanto `.split(...)` e o operador
    `in` aplicado a uma string, em qualquer parte do arquivo."""
    codigo_fonte = _ARQUIVO_MODULO.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(_ARQUIVO_MODULO))

    assert "import re" not in codigo_fonte
    assert not re.search(r"\bre\.\w+\(", codigo_fonte)

    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr == "split":
            raise AssertionError(f"`str.split` encontrado na linha {no.lineno}")
        if isinstance(no, ast.Compare) and any(
            isinstance(op, (ast.In, ast.NotIn)) for op in no.ops
        ):
            raise AssertionError(f"operador `in`/`not in` encontrado na linha {no.lineno}")


def test_nenhum_literal_de_tipo_de_acao_no_modulo() -> None:
    """Critério 3 de `T-74` / primeiro critério de `T-84`: nenhum valor de
    `TIPO_ACAO` aparece como literal de string no módulo. `OQ-13` foi
    respondida (`specs/app-aluno.spec.md`): domínio fechado de quatro
    valores ASCII sem parênteses — `INFORMACAO`, `RENEGOCIACAO`, `TROCA`,
    `ECONOMIA` — os mesmos que `collection/registros/bloco-11.yaml` (T-18,
    atualizado por `T-104`) usa na `condicao_exibicao` das perguntas de
    resultado. Também bane os identificadores "técnicos" genéricos
    (`INTERVENCAO`, `CORRECAO`) que a própria `OQ-13` descartou, e os
    literais pré-decisão com acento/parênteses que o registro usava antes de
    `T-104` — o valor de `TIPO_ACAO` só existe como DADO no YAML, nunca como
    literal em `.py`."""
    codigo_fonte = _ARQUIVO_MODULO.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(_ARQUIVO_MODULO))

    literais_de_tipo_acao = {
        "INFORMACAO",
        "RENEGOCIACAO",
        "TROCA",
        "ECONOMIA",
        "INTERVENCAO",  # identificador técnico genérico descartado por OQ-13
        "CORRECAO",  # identificador técnico genérico descartado por OQ-13
        "INFORMAÇÃO",  # literal pré-decisão, usado no registro antes de T-104
        "INTERVENÇÃO (renegociação)",  # literal pré-decisão
        "CORREÇÃO (economia)",  # literal pré-decisão
    }
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            assert no.value not in literais_de_tipo_acao, (
                f"literal de tipo de ação {no.value!r} encontrado na linha {no.lineno}"
            )


def test_modulo_le_apenas_ordem_acoes_sem_construir_acao_nova() -> None:
    """Reforço do critério 1: o módulo não instancia `AcaoRequerida` — ele só
    LÊ o que o motor publicou (nenhum `ast.Call` a `AcaoRequerida(...)`)."""
    codigo_fonte = _ARQUIVO_MODULO.read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename=str(_ARQUIVO_MODULO))

    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            assert no.func.id != "AcaoRequerida", (
                f"construção de AcaoRequerida encontrada na linha {no.lineno} — "
                "este módulo só lê, nunca deriva"
            )


# ---------------------------------------------------------------------------
# T-84 — `perguntas_do_bloco_11`/`tipo_acao_de`, RF-27, RF-33, AC-46
# ---------------------------------------------------------------------------

_REGISTROS_REAIS = carregar_registros().registros


@dataclass(frozen=True, slots=True)
class _AcaoRequeridaComTipoAcao:
    """Objeto de TESTE, não `engine.gates.AcaoRequerida`. Desde `T-119A` o
    tipo real do motor TEM `TIPO_ACAO` — este objeto continua existindo
    porque permite construir valores que o motor não emite a partir dos gates
    deste cenário: os outros três tipos do domínio, e um valor fora dele
    (`test_perguntas_do_bloco_11_tipo_desconhecido_falha_nomeando_o_valor`).
    Ele nunca substituiu a prova com dado real, que agora existe abaixo; é o
    complemento dela para os casos que o cenário não produz. Mesma técnica de
    `tests/app_aluno/test_acompanhamento_acao_id.py::
    _AcaoRequeridaComAcaoId` (T-83)."""

    TIPO_ACAO: str


def _snapshot_com_acao_real_do_bloco_11() -> SnapshotOrdem:
    """Mesma técnica de `_snapshot_com_gates_2_e_3_disparados` — um
    `SnapshotOrdem` REAL, com `ORDEM_ACOES` não vazia."""
    caso = caso_completo()
    divida_bloqueada = replace(
        montar_divida(caso.respostas, caso.DIVIDA_ID),
        SALDO_DEVEDOR_ATUAL=_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE,
        RISCO_MATERIAL_IMINENTE=True,
    )
    respostas_segunda_divida = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_ELEGIVEL)
    divida_elegivel = montar_divida(respostas_segunda_divida, _DIVIDA_ID_ELEGIVEL)

    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_bloqueada, divida_elegivel),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def test_tipo_acao_de_devolve_o_tipo_publicado_pelo_motor() -> None:
    """`RF-33`, `AC-46`, exercitado com o campo PRESENTE (`T-119A`): sobre
    uma `AcaoRequerida` REAL, `tipo_acao_de` devolve exatamente o `TIPO_ACAO`
    que o motor publicou — nunca um tipo inferido de `descricao`,
    `gate_origem` ou qualquer outro campo.

    Este é o teste que, enquanto `engine.gates.AcaoRequerida` não publicava
    `TIPO_ACAO`, afirmava a ausência do campo e a falha ruidosa da fronteira.
    A Rodada 2 de `motor-calculo` entregou o campo; a asserção passou a ser
    sobre o comportamento real, que é mais forte: antes se provava que a
    função não escolhia um tipo por padrão, agora se prova que ela lê o tipo
    CERTO — e que esse tipo é um dos que o REGISTRO mapeia (`OQ-13`
    respondida), sem nenhum literal de valor escrito neste teste."""
    snapshot = _snapshot_com_acao_real_do_bloco_11()
    assert len(snapshot.ORDEM_ACOES) > 0, "o caso de prova precisa de fato disparar um gate"
    acao_real = snapshot.ORDEM_ACOES[0]
    assert isinstance(acao_real, AcaoRequerida)

    tipo = tipo_acao_de(acao_real)

    assert tipo == acao_real.TIPO_ACAO
    assert isinstance(tipo, str) and tipo != ""
    # O tipo publicado pelo motor pertence ao domínio que o REGISTRO declara
    # — comparação contra os valores extraídos do YAML de verdade, nunca
    # contra um literal deste arquivo (mesma disciplina de `T-84`).
    tipos_do_registro = {
        _extrair_valor_tipo_acao(registro)
        for registro in _REGISTROS_REAIS
        if registro.ID in {"B11.03-INF", "B11.03-REN", "B11.03-TRO", "B11.03-ECO"}
    }
    assert tipo in tipos_do_registro


def test_perguntas_do_bloco_11_resolve_a_pergunta_da_acao_real() -> None:
    """`perguntas_do_bloco_11` é chamada fina sobre `tipo_acao_de` — sobre a
    ação REAL, o valor lido do motor atravessa o mapeamento e resolve
    exatamente UMA pergunta de resultado do Bloco 11.

    É o circuito completo motor → registro, que `T-84` só pôde provar em duas
    metades separadas (`tipo_acao_de` sobre ação real, mapeamento sobre
    objeto de teste) enquanto o campo não existia. A pergunta esperada é
    determinada pelo PRÓPRIO `TIPO_ACAO` da ação via `condicao_exibicao`,
    nunca por um `ID` fixado à mão aqui — se o motor mudar o tipo emitido
    para este cenário, o teste continua correto sem edição."""
    snapshot = _snapshot_com_acao_real_do_bloco_11()
    acao_real = snapshot.ORDEM_ACOES[0]
    tipo = tipo_acao_de(acao_real)

    resultado = perguntas_do_bloco_11(acao_real, _REGISTROS_REAIS)

    assert resultado.bloco == 11
    assert _extrair_valor_tipo_acao(resultado) == tipo
    # Exatamente uma pergunta de resultado corresponde a esse tipo — nenhuma
    # ambiguidade no mapeamento lido do registro.
    correspondentes = [
        registro
        for registro in _REGISTROS_REAIS
        if registro.ID in {"B11.03-INF", "B11.03-REN", "B11.03-TRO", "B11.03-ECO"}
        and _extrair_valor_tipo_acao(registro) == tipo
    ]
    assert len(correspondentes) == 1
    assert resultado.ID == correspondentes[0].ID


def test_erro_de_tipo_acao_ausente_continua_nomeando_a_fronteira() -> None:
    """`ErroTipoAcaoAusenteDoMotor` nunca foi uma marca de "campo ainda não
    entregue" — é a recusa a escolher uma pergunta por padrão diante de um
    objeto que não cumpre o contrato. Ela continua nomeando o campo e a
    origem da regra (`T-84`, `OQ-13`).

    O objeto usado aqui é construído no teste: depois de `T-119A` nenhuma
    `AcaoRequerida` real produz esta situação, e é justamente por isso que
    ela precisa continuar coberta — a fronteira não pode apodrecer sem
    ninguém notar."""

    @dataclass(frozen=True, slots=True)
    class _AcaoSemTipoAcao:
        DIVIDA_ID: str | None = "D999"

    with pytest.raises(ErroTipoAcaoAusenteDoMotor) as excinfo:
        tipo_acao_de(_AcaoSemTipoAcao())  # type: ignore[arg-type]

    mensagem = str(excinfo.value)
    assert "TIPO_ACAO" in mensagem
    assert "T-84" in mensagem
    assert "OQ-13" in mensagem

    # E a mesma falha se propaga por `perguntas_do_bloco_11`, antes de
    # qualquer consulta ao mapeamento.
    with pytest.raises(ErroTipoAcaoAusenteDoMotor):
        perguntas_do_bloco_11(_AcaoSemTipoAcao(), _REGISTROS_REAIS)  # type: ignore[arg-type]


def test_perguntas_do_bloco_11_devolve_exatamente_uma_pergunta_por_tipo_conhecido() -> None:
    """Quarto critério de aceite: a função devolve exatamente uma pergunta de
    resultado por ação, para cada um dos quatro tipos já transcritos em
    `collection/registros/bloco-11.yaml` — o valor de `TIPO_ACAO` usado aqui
    é lido do PRÓPRIO registro carregado (nunca um literal deste teste
    copiado de cabeça: é o `valor` real de `condicao_exibicao` de cada
    pergunta de resultado, extraído programaticamente)."""
    ids_resultado = {"B11.03-INF", "B11.03-REN", "B11.03-TRO", "B11.03-ECO"}
    registros_de_resultado = [r for r in _REGISTROS_REAIS if r.ID in ids_resultado]
    assert len(registros_de_resultado) == 4, (
        "premissa do teste: as quatro perguntas de resultado do Bloco 11 "
        "precisam estar carregadas (T-18)"
    )

    for registro_esperado in registros_de_resultado:
        tipo_acao_do_registro = _extrair_valor_tipo_acao(registro_esperado)
        acao = _AcaoRequeridaComTipoAcao(TIPO_ACAO=tipo_acao_do_registro)

        resultado = perguntas_do_bloco_11(acao, _REGISTROS_REAIS)  # type: ignore[arg-type]

        assert resultado.ID == registro_esperado.ID
        assert resultado == registro_esperado


def _extrair_valor_tipo_acao(registro: object) -> str:
    """Extrai, para o teste, o `valor` do termo `TIPO_ACAO` de
    `condicao_exibicao` de um registro de resultado do Bloco 11 — mesmo
    mecanismo genérico de `app/motor/acoes.py::_termo_tipo_acao`, replicado
    aqui apenas para MONTAR a fixture de teste (não para validar a função:
    a validação real é `resultado.ID == registro_esperado.ID` acima,
    verificada contra os dados carregados do YAML de verdade)."""
    from collection.condicoes import CondicaoE, CondicaoIgual

    condicao = registro.condicao_exibicao  # type: ignore[attr-defined]
    if isinstance(condicao, CondicaoIgual) and condicao.variavel == "TIPO_ACAO":
        return condicao.valor
    if isinstance(condicao, CondicaoE):
        for termo in condicao.termos:
            if isinstance(termo, CondicaoIgual) and termo.variavel == "TIPO_ACAO":
                return termo.valor
    raise AssertionError(f"registro sem termo TIPO_ACAO: {registro!r}")  # pragma: no cover


def test_perguntas_do_bloco_11_tipo_desconhecido_falha_nomeando_o_valor() -> None:
    """Terceiro critério de aceite: um `TIPO_ACAO` que não corresponde a
    nenhuma entrada do mapeamento falha ruidosamente, nomeando o valor
    recebido — nunca escolhe uma pergunta por padrão. Depois de `T-119A` o
    motor publica tipos que o registro MAPEIA (`test_perguntas_do_bloco_11_
    resolve_a_pergunta_da_acao_real`, acima), então o valor fora do domínio
    precisa ser construído: é o objeto de teste, que já supera o primeiro
    estágio (`tipo_acao_de`) e isola o comportamento do segundo (mapeamento)
    — o caminho que protege contra um tipo novo do motor sem pergunta
    correspondente no YAML."""
    acao = _AcaoRequeridaComTipoAcao(TIPO_ACAO="VALOR-QUE-NAO-EXISTE-NO-REGISTRO")

    with pytest.raises(ErroTipoAcaoDesconhecido) as excinfo:
        perguntas_do_bloco_11(acao, _REGISTROS_REAIS)  # type: ignore[arg-type]

    assert "VALOR-QUE-NAO-EXISTE-NO-REGISTRO" in str(excinfo.value)


def test_mapeamento_tipo_acao_e_lido_do_registro_editar_yaml_muda_o_resultado() -> None:
    """Segundo critério de aceite: o mapeamento tipo → pergunta é lido do
    YAML, não de uma tabela fixa no código — provado retirando uma das
    quatro perguntas de resultado da coleção de registros passada e
    confirmando que o tipo correspondente passa a ser "desconhecido", sem
    qualquer mudança em `app/motor/acoes.py`."""
    registros_sem_informacao = tuple(
        r for r in _REGISTROS_REAIS if r.ID != "B11.03-INF"
    )
    registro_informacao = next(r for r in _REGISTROS_REAIS if r.ID == "B11.03-INF")
    tipo_informacao = _extrair_valor_tipo_acao(registro_informacao)
    acao = _AcaoRequeridaComTipoAcao(TIPO_ACAO=tipo_informacao)

    with pytest.raises(ErroTipoAcaoDesconhecido):
        perguntas_do_bloco_11(acao, registros_sem_informacao)  # type: ignore[arg-type]

    # Com a coleção completa (o YAML "restaurado"), o mesmo tipo volta a
    # resolver — nenhuma mudança de código, só de dado de entrada.
    resultado = perguntas_do_bloco_11(acao, _REGISTROS_REAIS)  # type: ignore[arg-type]
    assert resultado.ID == "B11.03-INF"
