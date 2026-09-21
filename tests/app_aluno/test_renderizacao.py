"""Testes de `app/http/renderizacao.py` e `app/http/serializacao.py` —
RF-03, RF-06, AC-05, AC-36 (T-43, revisto em T-144).

**Mudou a camada, não o contrato.** Até T-144 a segunda metade destes testes
renderizava `report/templates/coleta/pergunta.html` e afirmava sobre o HTML.
A tela virou React e o template foi removido; quem decide hoje o que chega
ao cliente é `serializar_pergunta`. As garantias migraram para lá — é o
mesmo contrato ("o cliente recebe o que precisa para desenhar, e nada da
regra"), agora expresso em campos de JSON em vez de atributos de markup.

O que saiu de vez, porque perdeu objeto: as provas sobre `<form method>`/
`action` nativos e `hx-post` (`AC-3`), o botão submit sem script, o
fragmento sem `<script>` e o `htmx.min.js` vendorizado. Todas existiam para
o caminho sem JavaScript. Esse caminho foi encerrado por decisão de
arquitetura — ver `OQ-28` (respondida) e `OQ-29` (aberta) em
`specs/app-aluno.spec.md`.

Cobre os critérios de aceite da tarefa, no que sobreviveu à troca de camada:
1. nenhum enunciado, opção ou condição aparece como literal no código — o
   payload só ecoa o que veio do `RegistroPergunta` SINTÉTICO (verificado
   trocando o registro e vendo o campo mudar) e, complementarmente, pela
   suíte estática `tests/app_aluno/estatica/
   test_sem_conteudo_de_questionario_no_codigo.py` sobre `renderizacao.py`;
2. os nove `TipoResposta` chegam ao cliente — `tipo` correto no payload e,
   para os tipos com opções, `opcoes` preenchida. A associação rótulo/campo
   era garantia do HTML; hoje é responsabilidade do componente React, e
   prová-la é trabalho da suíte de front-end, não desta;
4. a avaliação da condição de exibição ocorre no servidor — `montar_contexto_
   pergunta` levanta `ErroPerguntaNaoExibivel` sobre a MESMA função `avaliar`
   de `collection/condicoes.py`, e o payload serializado não carrega
   `condicao_exibicao` nenhuma para o cliente reavaliar (`RF-52`).

REGRAS: `RF-03`, `RF-06`, `AC-05`, `AC-36`
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

import app.http.renderizacao as modulo_renderizacao
from app.http.renderizacao import (
    ContextoPergunta,
    ErroPerguntaNaoExibivel,
    montar_contexto_pergunta,
)
from app.http.serializacao import serializar_pergunta
from collection.condicoes import CondicaoIgual
from collection.interpolacao import Marcador
from collection.materialidade import AvisoMaterialidade
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    OpcaoRegistro,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import NAO_SEI, Resposta, RespostasCaso

_OPCOES_DE_TESTE = (
    OpcaoRegistro(rotulo="Rótulo da opção A", valor_interno="OPCAO_A"),
    OpcaoRegistro(rotulo="Rótulo da opção B", valor_interno="OPCAO_B"),
)

# TipoResposta que dependem de `ctx.opcoes` para ter algo a renderizar —
# os outros seis são campos de valor único.
_TIPOS_COM_OPCOES = frozenset(
    {TipoResposta.SELECAO_UNICA, TipoResposta.SELECAO_MULTIPLA, TipoResposta.SIM_NAO_TALVEZ}
)


def _registro(
    tipo: TipoResposta,
    *,
    ID: str = "B99.TESTE",
    admite_nao_sei: bool = False,
    condicao_exibicao: object | None = None,
    interpolacoes: tuple[Marcador, ...] = (),
    escopo_repeticao: EscopoRepeticao = EscopoRepeticao.NENHUM,
) -> RegistroPergunta:
    """Registro sintético — nunca um dos 291 reais: os testes desta tarefa
    exercitam o CONTRATO de renderização, não o conteúdo do questionário."""
    opcoes = _OPCOES_DE_TESTE if tipo in _TIPOS_COM_OPCOES else ()
    return RegistroPergunta(
        ID=ID,
        bloco=99,
        enunciado="Enunciado sintético de teste, nunca uma pergunta real da §11.",
        tipo=tipo,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=escopo_repeticao,
        opcoes=opcoes,
        VARIAVEL_GRAVADA="VARIAVEL_DE_TESTE",
        condicao_exibicao=condicao_exibicao,  # type: ignore[arg-type]
        interpolacoes=interpolacoes,
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=admite_nao_sei,
        salto_consequencia=None,
    )


def _serializar(
    ctx: ContextoPergunta, *, caso_id: str = "CASO-TESTE", item_id: str | None = None
) -> dict[str, object]:
    """O payload que o cliente de fato recebe — o sucessor de `_renderizar`,
    que produzia o HTML de `pergunta.html`."""
    return serializar_pergunta(ctx, CASO_ID=caso_id, item_id=item_id)


# ---------------------------------------------------------------------------
# Critério de aceite 1 — nenhum enunciado, opção ou condição como literal.
# ---------------------------------------------------------------------------


def test_ac1_enunciado_exibido_e_o_que_veio_do_registro_nao_um_literal_do_codigo() -> None:
    """Trocar o enunciado do registro sintético muda `payload["enunciado"]`,
    sem tocar no serializador — prova de que o texto vem do registro, nunca
    de um literal escrito em código. Antes de T-144 a mesma prova era feita
    sobre o HTML de `pergunta.html`; a camada mudou, a garantia não."""
    registro = _registro(TipoResposta.TEXTO_CURTO)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))
    payload_original = _serializar(ctx)
    assert payload_original["enunciado"] == registro.enunciado

    registro_outro_texto = _registro(TipoResposta.TEXTO_CURTO)
    object.__setattr__(registro_outro_texto, "enunciado", "Um enunciado completamente diferente.")
    ctx_outro = montar_contexto_pergunta(registro_outro_texto, RespostasCaso(respostas=()))
    payload_outro = _serializar(ctx_outro)

    assert payload_outro["enunciado"] == "Um enunciado completamente diferente."
    assert payload_outro["enunciado"] != payload_original["enunciado"]


def test_ac1_rotulos_de_opcao_do_payload_vem_do_registro() -> None:
    """Mesma prova para `SELECAO_UNICA`: os rótulos e valores internos do
    payload são os da tupla `opcoes` passada ao registro sintético, nunca um
    texto fixo do serializador."""
    registro = _registro(TipoResposta.SELECAO_UNICA)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx)

    assert payload["opcoes"] == [
        {"rotulo": "Rótulo da opção A", "valor_interno": "OPCAO_A", "admite_nao_sei": False},
        {"rotulo": "Rótulo da opção B", "valor_interno": "OPCAO_B", "admite_nao_sei": False},
    ]


def test_modulo_renderizacao_nao_contem_enunciado_opcao_ou_condicao_literal() -> None:
    """Auditoria direta do código-fonte de `app/http/renderizacao.py` — nenhum
    enunciado/opção/condição real está escrito nele (complementa, não
    substitui, a suíte estática `AC-37` de `tests/app_aluno/estatica/`)."""
    codigo_fonte = inspect.getsource(modulo_renderizacao)
    for termo_de_conteudo_real in ("CONSIGNADO", "AUTOPERCEPCAO_CONTROLE", "ESTABELECIDO"):
        assert termo_de_conteudo_real not in codigo_fonte


# ---------------------------------------------------------------------------
# Critério de aceite 2 — os nove TipoResposta chegam ao cliente com o que ele
# precisa para escolher o widget.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", list(TipoResposta))
def test_ac2_cada_um_dos_nove_tipos_chega_ao_payload_com_tipo_e_opcoes_coerentes(
    tipo: TipoResposta,
) -> None:
    """Para cada um dos nove `TipoResposta`: `payload["tipo"]` é o valor do
    enum do registro — é por ele que o cliente escolhe o widget e a máscara —
    e os três tipos que dependem de lista (`SELECAO_UNICA`,
    `SELECAO_MULTIPLA`, `SIM_NAO_TALVEZ`) chegam com `opcoes` preenchida,
    enquanto os campos de valor único chegam com `opcoes` vazia.

    A associação rótulo/campo (`<label for>`/`id`) era garantia do HTML de
    `pergunta.html` e morreu com ele: hoje quem a produz é o componente
    React, e prová-la é trabalho da suíte de front-end. Aqui prova-se só o
    que o payload de fato carrega."""
    registro = _registro(tipo)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx)

    assert payload["tipo"] == tipo.value
    if tipo in _TIPOS_COM_OPCOES:
        assert payload["opcoes"], f"{tipo}: esperava opções no payload"
    else:
        assert payload["opcoes"] == []


@pytest.mark.parametrize("tipo", list(TipoResposta))
def test_ac2_payload_identifica_a_pergunta_por_id_e_caso(tipo: TipoResposta) -> None:
    """O payload identifica a pergunta por `ID` e `CASO_ID` — o par que o
    cliente devolve no POST de resposta (`ID_PERGUNTA` é resolvido a partir
    do `ID` pelo SERVIDOR, em `app/http/rotas_coleta.py`).

    Antes de T-144 esta prova era sobre os campos `name="valor"` e
    `name="ID_PERGUNTA"` do `<form>`. O formulário nativo acabou junto com o
    template; o que resta como contrato de servidor é a identificação, e é
    ela que se verifica aqui. `VARIAVEL_GRAVADA` deliberadamente NÃO
    atravessa a fronteira (`RF-52`)."""
    registro = _registro(tipo)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx, caso_id="CASO-XYZ")

    assert payload["ID"] == registro.ID
    assert payload["CASO_ID"] == "CASO-XYZ"
    assert payload["bloco"] == registro.bloco
    assert "VARIAVEL_GRAVADA" not in payload


def test_ac2_admite_nao_sei_verdadeiro_atravessa_para_o_cliente() -> None:
    """`admite_nao_sei=True` chega ao payload — é o campo pelo qual o cliente
    sabe se pode oferecer "não sei", qualquer que seja o `TipoResposta`. A
    decisão continua sendo do registro; o cliente só recebe o resultado."""
    registro = _registro(TipoResposta.MOEDA, admite_nao_sei=True)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx)

    assert payload["admite_nao_sei"] is True


def test_ac2_admite_nao_sei_falso_atravessa_como_falso() -> None:
    """`admite_nao_sei=False` chega como `False` — a origem da regra é o
    registro, nunca uma decisão do cliente por tipo."""
    registro = _registro(TipoResposta.MOEDA, admite_nao_sei=False)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx)

    assert payload["admite_nao_sei"] is False


def test_ac2_item_id_de_pergunta_repetivel_vai_no_payload() -> None:
    """Pergunta `REP`: o `item_id` recebido vai no payload junto com o
    `escopo_repeticao` — é o par que o cliente devolve no POST para dizer
    qual item da ficha repetida está sendo respondido."""
    registro = _registro(TipoResposta.MOEDA, escopo_repeticao=EscopoRepeticao.DIVIDA_ID)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()), item_id="D001")

    payload = _serializar(ctx, item_id="D001")

    assert payload["item_id"] == "D001"
    assert payload["escopo_repeticao"] == EscopoRepeticao.DIVIDA_ID.value


def test_ac2_pergunta_nao_repetivel_vai_com_item_id_nulo() -> None:
    """Sem `item_id`, o campo vai `None` — a rota trata sua ausência como
    pergunta não repetível."""
    registro = _registro(TipoResposta.MOEDA, escopo_repeticao=EscopoRepeticao.NENHUM)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()))

    payload = _serializar(ctx)

    assert payload["item_id"] is None
    assert payload["escopo_repeticao"] == EscopoRepeticao.NENHUM.value


def test_ac2_valor_ja_respondido_vai_no_payload_para_reabrir_preenchido() -> None:
    """Uma resposta já gravada (`RespostasCaso` não vazia) atravessa como
    `valor_atual` — é com ele que o cliente reabre a pergunta preenchida."""
    registro = _registro(TipoResposta.TEXTO_CURTO)
    resposta_previa = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="VARIAVEL_DE_TESTE",
        item_id=None,
        valor="valor já respondido",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=(resposta_previa,)))

    payload = _serializar(ctx)

    assert payload["valor_atual"] == "valor já respondido"
    assert payload["respondida_como_nao_sei"] is False


def test_ac2_selecao_unica_informa_a_opcao_ja_respondida() -> None:
    """A opção já respondida volta em `valor_atual` — é o que o cliente usa
    para marcar aquela opção, e só aquela, ao reabrir. Antes de T-144 a prova
    era o atributo `checked` no `<input>` certo."""
    registro = _registro(TipoResposta.SELECAO_UNICA)
    resposta_previa = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="VARIAVEL_DE_TESTE",
        item_id=None,
        valor="OPCAO_B",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=(resposta_previa,)))

    payload = _serializar(ctx)

    assert payload["valor_atual"] == "OPCAO_B"
    assert payload["valores_marcados"] == []


def test_ac2_selecao_multipla_informa_as_duas_opcoes_ja_marcadas() -> None:
    """`SELECAO_MULTIPLA` reabre com AS DUAS opções marcadas quando ambas
    foram gravadas — o `frozenset[str]` de `ValorResposta` atravessa a
    fronteira JSON como lista ORDENADA (`frozenset` não é serializável e sua
    ordem de iteração não é estável; o serializador ordena)."""
    registro = _registro(TipoResposta.SELECAO_MULTIPLA)
    resposta_previa = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="VARIAVEL_DE_TESTE",
        item_id=None,
        valor=frozenset({"OPCAO_A", "OPCAO_B"}),
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=(resposta_previa,)))

    payload = _serializar(ctx)

    assert payload["valores_marcados"] == ["OPCAO_A", "OPCAO_B"]
    assert payload["valor_atual"] == ["OPCAO_A", "OPCAO_B"]


def test_ac2_resposta_nao_sei_nao_quebra_selecao_multipla_e_nao_marca_nenhuma_opcao() -> None:
    """Regressão do bug encontrado em T-43: uma resposta `NAO_SEI` prévia em
    pergunta `SELECAO_MULTIPLA` não pode levantar `TypeError` (`NaoSei` não é
    iterável) nem marcar opção nenhuma. Na camada de serialização o `NAO_SEI`
    vira a string canônica `"NAO_SEI"` com `respondida_como_nao_sei=True` —
    nunca `null` (que significaria "não respondida") e nunca uma opção
    marcada."""
    registro = _registro(TipoResposta.SELECAO_MULTIPLA, admite_nao_sei=True)
    resposta_previa = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="VARIAVEL_DE_TESTE",
        item_id=None,
        valor=NAO_SEI,
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=(resposta_previa,)))

    payload = _serializar(ctx)  # não deve levantar TypeError

    assert payload["valores_marcados"] == []
    assert payload["respondida_como_nao_sei"] is True
    assert payload["valor_atual"] == "NAO_SEI"


# ---------------------------------------------------------------------------
# Critério de aceite 4 — condição de exibição avaliada no servidor; nenhuma
# regra de exibição duplicada no cliente.
# ---------------------------------------------------------------------------


def test_ac4_condicao_falsa_impede_a_montagem_do_contexto_antes_da_serializacao() -> None:
    """`montar_contexto_pergunta` levanta `ErroPerguntaNaoExibivel` quando a
    condição é falsa — não há payload nenhum a serializar nesse caso (a
    decisão ocorre inteiramente no servidor, em Python)."""
    registro = _registro(
        TipoResposta.TEXTO_CURTO,
        condicao_exibicao=CondicaoIgual(variavel="OUTRA_VARIAVEL", valor="SIM"),
    )

    with pytest.raises(ErroPerguntaNaoExibivel):
        montar_contexto_pergunta(registro, RespostasCaso(respostas=()))


def test_ac4_condicao_verdadeira_permite_a_montagem_do_contexto() -> None:
    """Com a condição satisfeita pelas respostas do caso, a montagem funciona
    normalmente e a pergunta chega ao cliente."""
    registro = _registro(
        TipoResposta.TEXTO_CURTO,
        condicao_exibicao=CondicaoIgual(variavel="OUTRA_VARIAVEL", valor="SIM"),
    )
    resposta_que_satisfaz = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="OUTRA_VARIAVEL",
        item_id=None,
        valor="SIM",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(
        registro, RespostasCaso(respostas=(resposta_que_satisfaz,))
    )

    payload = _serializar(ctx)

    assert payload["enunciado"] == registro.enunciado


def test_ac4_condicao_usa_a_mesma_funcao_avaliar_de_collection_condicoes() -> None:
    """`app/http/renderizacao.py` importa `avaliar` de `collection/
    condicoes.py` — nunca reimplementa a interpretação da árvore de
    `Condicao`. Prova estrutural via AST (sem `getattr` sobre o módulo, que o
    `mypy --strict` recusa como reexportação implícita): o import existe
    literalmente no código-fonte."""
    import ast

    arvore = ast.parse(inspect.getsource(modulo_renderizacao))
    imports_de_avaliar = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
        and no.module == "collection.condicoes"
        and any(alias.name == "avaliar" for alias in no.names)
    ]
    assert imports_de_avaliar, "renderizacao.py deveria importar avaliar de collection.condicoes"


def test_ac4_nenhuma_regra_de_exibicao_atravessa_para_o_cliente() -> None:
    """A condição de exibição NÃO aparece no payload — nem como
    `condicao_exibicao`, nem como qualquer outro campo que permitisse ao
    cliente reavaliar a regra. A única forma de uma pergunta não aparecer é o
    servidor nem produzir o payload dela (`RF-52`, auditado por `AC-73`).

    Antes de T-144 esta prova era a ausência de `<script>`, `data-condicao` e
    `hx-trigger` no HTML; a fronteira mudou de markup para JSON e a prova
    acompanha — hoje é a ausência dos campos da REGRA no dicionário."""
    registro = _registro(
        TipoResposta.TEXTO_CURTO,
        condicao_exibicao=CondicaoIgual(variavel="OUTRA_VARIAVEL", valor="SIM"),
    )
    resposta_que_satisfaz = Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA="OUTRA_VARIAVEL",
        item_id=None,
        valor="SIM",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )
    ctx = montar_contexto_pergunta(
        registro, RespostasCaso(respostas=(resposta_que_satisfaz,))
    )

    payload = _serializar(ctx)

    for campo_de_regra in (
        "condicao_exibicao",
        "validacoes_cruzadas",
        "obrigatoriedade",
        "interpolacoes",
    ):
        assert campo_de_regra not in payload
    assert "OUTRA_VARIAVEL" not in repr(payload)


# ---------------------------------------------------------------------------
# Fronteira interpolação / opções-do-motor (documentada em app/http/
# renderizacao.py) — prova de que `montar_contexto_pergunta` de fato resolve
# as duas ANTES de o payload ser montado.
# ---------------------------------------------------------------------------


def test_fronteira_enunciado_interpolado_antes_de_chegar_ao_payload() -> None:
    """Um marcador `ID_DO_ITEM` no enunciado é substituído por
    `montar_contexto_pergunta` — o `enunciado` do payload não contém mais o
    texto do marcador, só o `item_id` resolvido. O cliente recebe texto
    pronto; a interpolação nunca atravessa a fronteira como regra."""
    registro = _registro(TipoResposta.TEXTO_CURTO, escopo_repeticao=EscopoRepeticao.DIVIDA_ID)
    object.__setattr__(registro, "enunciado", "Qual o valor da dívida [Dxxx]?")
    marcador_id_do_item = Marcador(marcador="[Dxxx]", origem="ID_DO_ITEM", referencia="")
    object.__setattr__(registro, "interpolacoes", (marcador_id_do_item,))

    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()), item_id="D003")
    payload = _serializar(ctx, item_id="D003")

    enunciado = payload["enunciado"]
    assert isinstance(enunciado, str)
    assert "[Dxxx]" not in enunciado
    assert "D003" in enunciado


def test_fronteira_opcoes_snapshot_ausente_produz_pergunta_sem_opcoes_nunca_inventadas() -> None:
    """`origem_opcoes.fonte=SNAPSHOT` sem snapshot disponível resolve para
    lista vazia (T-14, `AC-20`) — o payload vai com `opcoes` vazia, nunca com
    opções fixas inventadas para preencher a lacuna."""
    registro = _registro(TipoResposta.SELECAO_UNICA)
    origem_snapshot = OrigemOpcoes(fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS")
    object.__setattr__(registro, "origem_opcoes", origem_snapshot)
    object.__setattr__(registro, "opcoes", ())

    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()), snapshot=None)
    payload = _serializar(ctx)

    assert ctx.opcoes == ()
    assert payload["opcoes"] == []


# ---------------------------------------------------------------------------
# Aviso de materialidade — integração do template T-41 dentro de T-43, hoje
# um campo do payload.
# ---------------------------------------------------------------------------


def test_aviso_de_materialidade_aparece_no_payload_quando_presente() -> None:
    """O aviso atravessa como TEXTO já resolvido — o cliente exibe, não
    decide. Antes de T-144 o teste procurava o `id` do aviso no HTML; hoje o
    `id` é assunto do componente React e o que o servidor garante é o texto."""
    registro = _registro(TipoResposta.MOEDA, admite_nao_sei=True)
    aviso = AvisoMaterialidade(
        VARIAVEL_GRAVADA="VARIAVEL_DE_TESTE", texto="pode deixar seu plano provisório"
    )
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()), aviso=aviso)

    payload = _serializar(ctx)

    assert payload["aviso"] == "pode deixar seu plano provisório"


def test_aviso_de_materialidade_ausente_vai_como_nulo() -> None:
    """Sem aviso, o campo vai `None` — o cliente não tem nada a exibir, e a
    ausência é explícita no payload em vez de um campo faltando."""
    registro = _registro(TipoResposta.MOEDA, admite_nao_sei=True)
    ctx = montar_contexto_pergunta(registro, RespostasCaso(respostas=()), aviso=None)

    payload = _serializar(ctx)

    assert payload["aviso"] is None
