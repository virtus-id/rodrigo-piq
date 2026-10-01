"""Fichas repetíveis — RF-04, AC-04 (T-47, convertido em T-144).

**O que este arquivo testava antes, e o que testa agora.** Até T-144 a ficha
repetível era o template `report/templates/coleta/ficha_repetivel.html`, e
cada asserção aqui olhava o HTML que o Jinja2 produzia. A tela virou React
(`frontend/src/telas/TelaFichas.tsx`), o template foi removido, e o sucessor
servidor daquele template é a rota `GET /caso/{CASO_ID}/fichas/{escopo}`
(`app/http/rotas_fichas.py`), que entrega os MESMOS dados por ficha —
`item_id`, `completa`, `campos` — em JSON. As asserções mudaram de markup
para payload; a intenção de cada critério de aceite é a mesma.

Os quatro critérios de aceite da tarefa, no estado em que hoje são
testáveis deste lado da fronteira:

1. "utilizável a 360 px sem rolagem horizontal" — o HTML não é mais
   produzido em Python, então não há markup a auditar aqui. A garantia
   sobrevive em duas camadas: `tests/app_aluno/estatica/test_css_360px.py`
   (nenhuma largura fixa acima de 360px, nenhum seletor de tabela em
   `app/http/estaticos/estilo.css`) e os testes de navegador do frontend.
   Este arquivo mantém apenas o espelho do lint de CSS, que continua válido.
2. "adicionar uma ficha cria um item com identificador estável e não altera
   as demais" — provado agora sobre o payload da rota: cada ficha listada
   traz o `item_id` tal como o `RepositorioItens` o gerou, e criar uma ficha
   nova (`POST`) não toca resposta nenhuma das existentes.
3. "cada campo tem rótulo associado e é alcançável por teclado" — é markup,
   e markup hoje é React. A associação rótulo/campo, a focabilidade e a
   ausência de `tabindex` negativo são verificadas em
   `frontend/tests/unit/componentes/CampoPergunta.test.tsx` e nos testes de
   acessibilidade do frontend. O que RESTA deste lado, e é o que se testa
   aqui, é que o servidor entrega por ficha os campos que a tela precisa
   desenhar — com `ID` e `enunciado`, sem os quais nenhum rótulo existiria.
4. "a lista de fichas mostra quais estão completas e quais têm pendência,
   sem calcular nada" — a rota só LÊ o resultado de
   `app/casos/progresso.py::pendencias_obrigatorias` (T-40/T-44) para montar
   `completa`; nenhuma obrigatoriedade é recalculada, e nada de
   `obrigatoriedade` atravessa a fronteira (`RF-52`). Ambas as metades são
   testadas abaixo.

REGRAS: `RF-04`, `RF-51`, `RF-52`, `AC-04`
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from collection.carga import ColecaoDeRegistros
from collection.condicoes import Condicao, CondicaoIgual
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import Resposta
from persistencia.app_aluno.arquivo import (
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.casos import Caso

_CHAVE_TESTE: Final[str] = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_CONTA_ID: Final[str] = "CONTA-FICHA-1"
_CASO_ID: Final[str] = "CASO-FICHA-1"
_ESCOPO: Final[str] = EscopoRepeticao.DIVIDA_ID.value

_ORIGEM_OPCOES_DE_TESTE = OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None)

_OBRIGATORIEDADE_REP_PADRAO: frozenset[Obrigatoriedade] = frozenset(
    {Obrigatoriedade.OBR, Obrigatoriedade.REP}
)


class _RepositorioCasosDublê:
    """Restrito ao que `exigir_caso_da_sessao` usa — mesmo padrão de
    `tests/app_aluno/test_rotas_pergunta.py::_RepositorioCasosDublê`."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _registro_rep(
    ID: str,
    *,
    variavel: str,
    obrigatoriedade: frozenset[Obrigatoriedade] = _OBRIGATORIEDADE_REP_PADRAO,
    escopo_repeticao: EscopoRepeticao = EscopoRepeticao.DIVIDA_ID,
) -> RegistroPergunta:
    """Registro repetível sintético — enunciado curto de propósito (`AC-37`:
    nenhum conteúdo real de questionário escrito em `.py`)."""
    return RegistroPergunta(
        ID=ID,
        bloco=5,
        enunciado="Enunciado sintético de teste, nunca uma pergunta real da §11.",
        tipo=TipoResposta.TEXTO_CURTO,
        obrigatoriedade=obrigatoriedade,
        escopo_repeticao=escopo_repeticao,
        opcoes=(),
        VARIAVEL_GRAVADA=variavel,
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=_ORIGEM_OPCOES_DE_TESTE,
        admite_nao_sei=False,
        salto_consequencia=None,
    )


def _caso_em_coleta() -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _resposta_no_item(variavel: str, item_id: str, valor: str) -> Resposta:
    return Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    colecao: ColecaoDeRegistros,
    respostas_iniciais: tuple[Resposta, ...] = (),
) -> TestClient:
    """Sobe a aplicação com repositórios de arquivo sobre `tmp_path` — mesmo
    padrão de `tests/app_aluno/test_rotas_pergunta.py::_montar_cliente`."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    repositorio_respostas = RepositorioRespostasArquivo(
        caminho_arquivo=tmp_path / "respostas.jsonl"
    )
    for resposta in respostas_iniciais:
        repositorio_respostas.gravar(resposta)

    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: _RepositorioCasosDublê(
        _caso_em_coleta(), _CONTA_ID
    )
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: repositorio_respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: RepositorioItensArquivo(
        caminho_arquivo=tmp_path / "itens.jsonl"
    )

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


def _colecao_de_uma_pergunta_rep(
    obrigatoriedade: frozenset[Obrigatoriedade] = _OBRIGATORIEDADE_REP_PADRAO,
) -> ColecaoDeRegistros:
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION="1.0.0",
        registros=(
            _registro_rep("B5.A02", variavel="VALOR_DIVIDA", obrigatoriedade=obrigatoriedade),
        ),
    )


def _listar(cliente: TestClient) -> dict[str, Any]:
    resposta = cliente.get(f"/caso/{_CASO_ID}/fichas/{_ESCOPO}")
    assert resposta.status_code == 200, resposta.text
    corpo: dict[str, Any] = resposta.json()
    return corpo


def _criar(cliente: TestClient) -> dict[str, Any]:
    resposta = cliente.post(f"/caso/{_CASO_ID}/fichas/{_ESCOPO}")
    assert resposta.status_code == 201, resposta.text
    corpo: dict[str, Any] = resposta.json()
    return corpo


# ---------------------------------------------------------------------------
# Critério de aceite 1 — utilizável a 360px, sem rolagem horizontal.
#
# T-144: as duas asserções que olhavam o HTML produzido (nenhuma largura fixa
# inline, nenhuma `<table>`) morreram com o template. O CSS continua sendo
# escrito à mão neste repositório, e é ele que decide se a tela rola na
# horizontal — o lint abaixo é a parte da garantia que ainda tem objeto.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Critério de aceite 2 — adicionar cria item com identificador estável e não
# altera as demais.
# ---------------------------------------------------------------------------


def test_ac2_cada_ficha_listada_traz_o_item_id_gerado_sem_alterar_os_demais(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Três fichas criadas, três `item_id` distintos e estáveis na listagem —
    exatamente como o `RepositorioItens` os gerou (`D001`, `D002`, `D003`;
    quem gera é `collection/repeticao.py`/`RepositorioItens`, T-15, nem a
    rota nem a tela). Antes de T-144 isto era `data-item-id="D001"` no HTML;
    agora é o campo `item_id` de cada ficha do payload."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_colecao_de_uma_pergunta_rep())
    for _ in range(3):
        _criar(cliente)

    corpo = _listar(cliente)

    assert [ficha["item_id"] for ficha in corpo["fichas"]] == ["D001", "D002", "D003"]
    assert corpo["escopo"] == _ESCOPO


def test_ac2_criar_ficha_nao_altera_resposta_nenhuma_das_fichas_existentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Criar uma ficha nova é uma submissão independente: o `POST` não manda
    valor nenhum e não toca as respostas já gravadas. Antes de T-144 isto era
    "o formulário de adicionar não repete `name="valor"` nem o `item_id` de
    ficha existente" no markup; agora é a prova direta — a resposta de `D001`
    continua lá, com o mesmo valor, depois de `D002` nascer."""
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=_colecao_de_uma_pergunta_rep(),
        respostas_iniciais=(_resposta_no_item("VALOR_DIVIDA", "D001", "1000"),),
    )
    assert _criar(cliente)["ficha"]["item_id"] == "D001"

    ficha_nova = _criar(cliente)["ficha"]
    corpo = _listar(cliente)

    assert ficha_nova["item_id"] == "D002"
    d001 = next(f for f in corpo["fichas"] if f["item_id"] == "D001")
    assert [campo["valor_atual"] for campo in d001["campos"]] == ["1000"]
    d002 = next(f for f in corpo["fichas"] if f["item_id"] == "D002")
    assert [campo["valor_atual"] for campo in d002["campos"]] == [None]


def test_ac2_lista_vazia_nao_inventa_ficha_nenhuma(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem item nenhum criado, a rota devolve lista vazia — nunca uma ficha
    em branco fabricada para "ter o que mostrar". Quem escreve a mensagem de
    "nenhuma ficha cadastrada" é a tela (`TelaFichas.tsx`), a partir desta
    lista vazia."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_colecao_de_uma_pergunta_rep())

    corpo = _listar(cliente)

    assert corpo["fichas"] == []


# ---------------------------------------------------------------------------
# Critério de aceite 3 — o que o servidor precisa entregar para que a tela
# consiga rotular e alcançar cada campo.
#
# T-144: rótulo associado, focabilidade e ausência de `tabindex` negativo são
# markup, e markup virou React — `frontend/tests/unit/componentes/
# CampoPergunta.test.tsx` cobre a associação `<label for>`/`id` e o vínculo
# `aria-describedby`. O que ainda depende deste lado é o payload trazer o que
# rotula cada campo.
# ---------------------------------------------------------------------------


def test_ac3_cada_campo_da_ficha_traz_id_e_enunciado_para_a_tela_rotular(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cada campo da ficha chega com `ID` (a âncora do `id`/`for` que
    `CampoPergunta.tsx` monta) e `enunciado` já interpolado (o texto do
    rótulo). Sem esses dois, nenhum rótulo associado seria possível na tela —
    é a metade servidor do critério de aceite 3."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_colecao_de_uma_pergunta_rep())
    _criar(cliente)

    corpo = _listar(cliente)

    campos = corpo["fichas"][0]["campos"]
    assert [campo["ID"] for campo in campos] == ["B5.A02"]
    assert all(campo["enunciado"] for campo in campos)
    assert all(campo["item_id"] == "D001" for campo in campos)


# ---------------------------------------------------------------------------
# Critério de aceite 4 — completas vs. pendência, sem calcular nada.
# ---------------------------------------------------------------------------


def test_ac4_completa_e_derivada_do_resultado_real_de_pendencias_obrigatorias(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A rota lê a ÚNICA implementação de obrigatoriedade
    (`app/casos/progresso.py::pendencias_obrigatorias`, T-40/T-44): a ficha
    cuja variável `REP` está respondida sai `completa=True`, a em branco sai
    `completa=False`. Antes de T-144 isto era "Completa"/"Pendência" no HTML;
    o booleano é o mesmo, e continua vindo de fora — a tela também não o
    recalcula."""
    # D001 respondida, D002 em branco.
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=_colecao_de_uma_pergunta_rep(),
        respostas_iniciais=(_resposta_no_item("VALOR_DIVIDA", "D001", "1000"),),
    )
    _criar(cliente)
    _criar(cliente)

    corpo = _listar(cliente)

    completa_por_item = {ficha["item_id"]: ficha["completa"] for ficha in corpo["fichas"]}
    assert completa_por_item == {"D001": True, "D002": False}


def test_ac4_ficha_recem_criada_nasce_pendente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Uma ficha sem nenhuma resposta nasce `completa=False` — o `POST` não
    declara "completa" por otimismo, e a listagem seguinte confirma o mesmo
    booleano pela via de `pendencias_obrigatorias`."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_colecao_de_uma_pergunta_rep())

    ficha_nova = _criar(cliente)["ficha"]
    corpo = _listar(cliente)

    assert ficha_nova["completa"] is False
    assert corpo["fichas"][0]["completa"] is False


def test_ac4_payload_da_ficha_nao_vaza_obrigatoriedade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Auditoria da fronteira, sucessora direta da auditoria que lia o texto
    do template (T-144). O que antes se provava sobre o arquivo
    `ficha_repetivel.html` — nenhuma palavra-chave de decisão de
    obrigatoriedade — prova-se agora sobre o JSON que sai da rota: nem
    `obrigatoriedade`, nem `OBR`/`REP`, nem `condicao_exibicao` ou
    `validacoes_cruzadas` atravessam (`RF-52`). A única fonte da regra
    continua sendo `app/casos/progresso.py`, no servidor."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_colecao_de_uma_pergunta_rep())
    _criar(cliente)

    resposta = cliente.get(f"/caso/{_CASO_ID}/fichas/{_ESCOPO}")
    texto_bruto = resposta.text
    campos = resposta.json()["fichas"][0]["campos"]

    assert "obrigatoriedade" not in texto_bruto
    assert "pendencias_obrigatorias" not in texto_bruto
    assert '"OBR"' not in texto_bruto
    for campo in campos:
        assert "obrigatoriedade" not in campo
        assert "condicao_exibicao" not in campo
        assert "validacoes_cruzadas" not in campo


# ---------------------------------------------------------------------------
# T-200 / T-201 — achados C4/C5 do QA (2026-09-29).
# ---------------------------------------------------------------------------


def test_t200_ficha_de_divida_nao_traz_perguntas_do_bloco_7(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reproduz C5: a ficha mostrava "37 campos" — os do Bloco 5 mais
    `B7.08`/`B7.09`, cuja condição `NAO(...)` abria sem resposta nenhuma."""
    from collection.carga import carregar_registros

    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=carregar_registros())
    _criar(cliente)

    campos = _listar(cliente)["fichas"][0]["campos"]

    assert campos
    assert {campo["bloco"] for campo in campos} == {5}


def _registro_de_ficha(
    ID: str, variavel: str, condicao: Condicao | None = None
) -> RegistroPergunta:
    """Como as perguntas reais da ficha do Bloco 5: `REP`/`COND, REP`, sem `OBR`."""
    obrigatoriedade = {Obrigatoriedade.REP} | ({Obrigatoriedade.COND} if condicao else set())
    registro = _registro_rep(ID, variavel=variavel, obrigatoriedade=frozenset(obrigatoriedade))
    return replace(registro, condicao_exibicao=condicao)


_COLECAO_DE_FICHA_REAL_LIKE = ColecaoDeRegistros(
    QUESTIONARIO_VERSION="1.0.0",
    registros=(
        _registro_de_ficha("B5.C01", "TEM_PARCELA"),
        _registro_de_ficha("B5.C02", "PARCELA", CondicaoIgual(variavel="TEM_PARCELA", valor="SIM")),
    ),
)


def test_t201_ficha_recem_criada_de_perguntas_rep_nao_e_completa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reproduz C5: sem `OBR`, nada pendia e a ficha vazia saía "Completa"."""
    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=_COLECAO_DE_FICHA_REAL_LIKE)
    _criar(cliente)

    assert _listar(cliente)["fichas"][0]["completa"] is False


def test_t201_ficha_com_as_abertas_respondidas_e_completa_mesmo_com_condicao_falsa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`D001` abre a condicional e responde as duas; `D002` a fecha e
    responde a única aberta; `D003` abre e deixa a condicional em branco."""
    cliente = _montar_cliente(
        monkeypatch,
        tmp_path,
        colecao=_COLECAO_DE_FICHA_REAL_LIKE,
        respostas_iniciais=(
            _resposta_no_item("TEM_PARCELA", "D001", "SIM"),
            _resposta_no_item("PARCELA", "D001", "300"),
            _resposta_no_item("TEM_PARCELA", "D002", "NAO"),
            _resposta_no_item("TEM_PARCELA", "D003", "SIM"),
        ),
    )
    for _ in range(3):
        _criar(cliente)

    completa_por_item = {f["item_id"]: f["completa"] for f in _listar(cliente)["fichas"]}

    assert completa_por_item == {"D001": True, "D002": True, "D003": False}


# ---------------------------------------------------------------------------
# T-211 — `GET /fichas/ACAO_ID` sem campos (efeito de T-200).
# ---------------------------------------------------------------------------


def test_t211_ficha_de_acao_lista_os_campos_do_bloco_11(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Todo registro de `ACAO_ID` é do Bloco 11, fora da coleta inicial; o
    filtro de `T-200` zerava a ficha. Só vale para escopo que TEM registro na
    coleta inicial."""
    from collection.carga import carregar_registros

    cliente = _montar_cliente(monkeypatch, tmp_path, colecao=carregar_registros())
    escopo = EscopoRepeticao.ACAO_ID.value
    assert cliente.post(f"/caso/{_CASO_ID}/fichas/{escopo}").status_code == 201

    resposta = cliente.get(f"/caso/{_CASO_ID}/fichas/{escopo}")

    assert resposta.status_code == 200, resposta.text
    campos = resposta.json()["fichas"][0]["campos"]
    assert campos
    assert {campo["bloco"] for campo in campos} == {11}
    assert all(campo["item_id"] == resposta.json()["fichas"][0]["item_id"] for campo in campos)


# ---------------------------------------------------------------------------
# T-212 — fichas repetíveis do Bloco 3 alcançáveis pelo aluno.
# ---------------------------------------------------------------------------


def _cliente_real(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    from collection.carga import carregar_registros

    return _montar_cliente(monkeypatch, tmp_path, colecao=carregar_registros())


def _responder(
    cliente: TestClient, id_pergunta: str, valor: str, item_id: str | None = None
) -> Any:
    corpo = {"ID_PERGUNTA": id_pergunta}
    corpo |= {"nao_sei": "on"} if valor == "NAO_SEI" else {"valor": valor}
    if item_id:
        corpo["item_id"] = item_id
    return cliente.post(f"/caso/{_CASO_ID}/resposta", data=corpo)


_GATILHOS_QUE_ABREM: Final = [
    ("B3.03", "SIM", ["RENDA_ADICIONAL_ID"]),
    ("B3.NM01", "SIM", ["DESPESA_NAO_MENSAL_ID"]),
    # `T-254` (`AC-137`): a margem nasce dentro do vínculo, não sozinha.
    ("B3.S01", "SIM", ["VINCULO_ID"]),
    ("B3.S01", "NAO_SEI", ["VINCULO_ID"]),
]


@pytest.mark.parametrize(("gatilho", "valor", "escopos"), _GATILHOS_QUE_ABREM)
def test_t212_gatilho_aponta_a_ficha_e_o_item_criado_abre_a_cabeca(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    gatilho: str,
    valor: str,
    escopos: list[str],
) -> None:
    """Reproduz o bug: o aluno respondia "Sim" e a coleta seguia sem ficha.

    `T-311` (decisão do produto, 2026-10-01): a ficha nasce com o primeiro
    item e a próxima pergunta é a cabeça dele — sem a lista no meio."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    resposta = _responder(cliente, gatilho, valor)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["abrir_fichas"] == []
    for escopo in escopos:
        (ficha,) = _fichas(cliente, escopo)
        proxima = resposta.json()["proxima"]["pergunta"]
        assert proxima["ID"] == ficha["campos"][0]["ID"]
        assert proxima["item_id"] == ficha["item_id"]


@pytest.mark.parametrize(
    ("gatilho", "valor"),
    [("B3.03", "NAO"), ("B3.03", "NAO_SEI"), ("B3.NM01", "NAO"), ("B3.S01", "NAO")],
)
def test_t212_gatilho_que_nao_abre_nao_aponta_ficha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gatilho: str, valor: str
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)

    resposta = _responder(cliente, gatilho, valor)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["abrir_fichas"] == []


def test_t212_escopo_que_ja_tem_item_nao_aponta_ficha_de_novo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)
    cliente.post(f"/caso/{_CASO_ID}/fichas/RENDA_ADICIONAL_ID")

    assert _responder(cliente, "B3.03", "SIM").json()["abrir_fichas"] == []


def test_t212_resposta_fora_de_gatilho_nao_aponta_ficha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`ITEM_DESPESA` e `DIVIDA_ID` não têm condição na cabeça: nada os abre."""
    cliente = _cliente_real(monkeypatch, tmp_path)

    assert _responder(cliente, "B3.03", "SIM").json()["proxima"]["pergunta"]["item_id"]
    assert _responder(cliente, "B3.NM01", "NAO").json()["abrir_fichas"] == []
    assert _fichas(cliente, "DESPESA_NAO_MENSAL_ID") == []


def test_t212_escopos_informa_se_cada_um_esta_aberto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cliente = _cliente_real(monkeypatch, tmp_path)

    def abertos() -> dict[str, bool]:
        corpo = cliente.get(f"/caso/{_CASO_ID}/escopos").json()
        assert "condicao" not in str(corpo)
        return {e["escopo"]: e["aberto"] for e in corpo["escopos"]}

    antes = abertos()
    _responder(cliente, "B3.03", "SIM")
    _responder(cliente, "B3.S01", "NAO")
    depois = abertos()

    assert antes["RENDA_ADICIONAL_ID"] is False
    assert depois["RENDA_ADICIONAL_ID"] is True
    assert depois["DESPESA_NAO_MENSAL_ID"] is False
    assert depois["VINCULO_ID"] is False
    assert depois["MARGEM_ID"] is False


def test_t212_validacao_cruzada_na_ficha_de_margem_criada_pela_tela(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-06` — `VALOR_UTILIZADO_MARGEM` (1200) acima de `VALOR_TOTAL_MARGEM`
    (1000) é recusado, e nada é gravado."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    vinculo = cliente.post(f"/caso/{_CASO_ID}/fichas/VINCULO_ID").json()["ficha"]["item_id"]
    item_id = cliente.post(
        f"/caso/{_CASO_ID}/fichas/MARGEM_ID", data={"item_pai_id": vinculo}
    ).json()["ficha"]["item_id"]

    assert _responder(cliente, "B3.S06B", "1000", item_id).status_code == 200
    recusa = _responder(cliente, "B3.S06C", "1200", item_id)

    assert recusa.status_code == 400
    assert "margem" in recusa.json()["erro"]
    ficha = cliente.get(f"/caso/{_CASO_ID}/fichas/MARGEM_ID").json()["fichas"][0]
    valores = {campo["ID"]: campo["valor_atual"] for campo in ficha["campos"]}
    assert valores["B3.S06C"] is None


def test_t212_fichas_de_um_escopo_nao_alteram_as_de_outro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-04` — criar, responder e remover no escopo de renda não toca a de
    despesa não mensal."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    # `T-311`: cada "Sim" já cria a primeira ficha do seu escopo.
    _responder(cliente, "B3.03", "SIM")
    _responder(cliente, "B3.NM01", "SIM")
    (despesa,) = _fichas(cliente, "DESPESA_NAO_MENSAL_ID")
    antes = cliente.get(f"/caso/{_CASO_ID}/fichas/DESPESA_NAO_MENSAL_ID").json()

    (renda,) = _fichas(cliente, "RENDA_ADICIONAL_ID")
    assert _responder(cliente, "B3.03B", "2000", renda["item_id"]).status_code == 200
    cliente.delete(f"/caso/{_CASO_ID}/fichas/RENDA_ADICIONAL_ID/{renda['item_id']}")

    assert cliente.get(f"/caso/{_CASO_ID}/fichas/DESPESA_NAO_MENSAL_ID").json() == antes
    assert antes["fichas"][0]["item_id"] == despesa["item_id"]
    assert cliente.get(f"/caso/{_CASO_ID}/fichas/RENDA_ADICIONAL_ID").json()["fichas"] == []


# ---------------------------------------------------------------------------
# T-254/T-256/T-257 — margem dentro do vínculo; consignado aponta vínculo
# (RF-90, AC-137, AC-139, EC-35, DE-05).
# ---------------------------------------------------------------------------


def _criar_em(cliente: TestClient, escopo: str, **dados: str) -> Any:
    return cliente.post(f"/caso/{_CASO_ID}/fichas/{escopo}", data=dados)


def _fichas(cliente: TestClient, escopo: str) -> list[dict[str, Any]]:
    corpo: dict[str, Any] = cliente.get(f"/caso/{_CASO_ID}/fichas/{escopo}").json()
    fichas: list[dict[str, Any]] = corpo["fichas"]
    return fichas


def test_t254_margem_sem_pai_valido_e_recusada_e_nada_e_criado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-137`: sem `item_pai_id`, com pai inexistente, removido ou de outro
    escopo → `422`; nenhuma margem nasce."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    removido = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    cliente.delete(f"/caso/{_CASO_ID}/fichas/VINCULO_ID/{removido}")
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]

    for dados in ({}, {"item_pai_id": "V999"}, {"item_pai_id": removido}, {"item_pai_id": divida}):
        assert _criar_em(cliente, "MARGEM_ID", **dados).status_code == 422

    assert _fichas(cliente, "MARGEM_ID") == []


def test_t254_margem_de_outro_caso_nao_serve_de_pai(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-137`: o vínculo `V001` de outro caso não é pai de margem neste."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    RepositorioItensArquivo(tmp_path / "itens.jsonl").proximo_identificador(
        "OUTRO-CASO", EscopoRepeticao.VINCULO_ID
    )

    assert _criar_em(cliente, "MARGEM_ID", item_pai_id="V001").status_code == 422


def test_t254_vinculo_lista_as_suas_margens_e_os_dependentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-137`/`AC-138`/`EC-35`: cada margem sob o seu vínculo, nunca
    somada; a dívida consignada que aponta o vínculo é dependente dele."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    v1 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    v2 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    m1 = _criar_em(cliente, "MARGEM_ID", item_pai_id=v1).json()["ficha"]["item_id"]
    m2 = _criar_em(cliente, "MARGEM_ID", item_pai_id=v2).json()["ficha"]["item_id"]
    assert _responder(cliente, "B3.S06D", "500", m1).status_code == 200
    assert _responder(cliente, "B3.S06D", "300", m2).status_code == 200
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]
    _responder(cliente, "B5.A02", "CONSIGNADO", divida)
    assert _responder(cliente, "B5.A02V", v2, divida).status_code == 200

    corpo = cliente.get(f"/caso/{_CASO_ID}/fichas/VINCULO_ID").json()
    por_id = {ficha["item_id"]: ficha for ficha in corpo["fichas"]}

    assert [m["item_id"] for m in por_id[v1]["margens"]] == [m1]
    assert [m["item_id"] for m in por_id[v2]["margens"]] == [m2]
    assert por_id[v1]["dependentes"] == {"margens": [m1], "dividas": []}
    assert por_id[v2]["dependentes"] == {"margens": [m2], "dividas": [divida]}
    assert "800" not in str(corpo)
    assert corpo["escopo_pai"] is None
    margens = cliente.get(f"/caso/{_CASO_ID}/fichas/MARGEM_ID").json()
    assert margens["escopo_pai"] == "VINCULO_ID"
    assert {m["item_id"]: m["item_pai_id"] for m in margens["fichas"]} == {m1: v1, m2: v2}


def test_t256_vinculo_da_divida_so_para_consignado_com_os_vinculos_do_caso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`AC-139` (parte `CONSIGNADO`, `R9-4`): `B5.A02V` só aparece para
    `CONSIGNADO`; as opções são os vínculos ATIVOS deste caso, rotulados
    pelo órgão pagador."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    RepositorioItensArquivo(tmp_path / "itens.jsonl").proximo_identificador(
        "OUTRO-CASO", EscopoRepeticao.VINCULO_ID
    )
    _responder(cliente, "B3.S01", "SIM")
    v1 = _fichas(cliente, "VINCULO_ID")[0]["item_id"]  # `T-311`: nasce com o "Sim"
    v2 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    v3 = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    cliente.delete(f"/caso/{_CASO_ID}/fichas/VINCULO_ID/{v3}")
    _responder(cliente, "B3.S03", "Prefeitura", v1)
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]

    def campo_vinculo() -> dict[str, Any] | None:
        (ficha,) = _fichas(cliente, "DIVIDA_ID")
        return next((c for c in ficha["campos"] if c["ID"] == "B5.A02V"), None)

    _responder(cliente, "B5.A02", "PESSOAL", divida)
    assert campo_vinculo() is None

    _responder(cliente, "B5.A02", "CONSIGNADO", divida)
    campo = campo_vinculo()
    assert campo is not None
    assert [(o["valor_interno"], o["rotulo"]) for o in campo["opcoes"]] == [
        (v1, "Prefeitura"),
        (v2, v2),
    ]


def test_t257_referencia_a_vinculo_removido_volta_a_ficar_em_aberto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EC-35`: removido o vínculo, a margem dele e a dívida que o apontava
    ficam em aberto; as respostas continuam gravadas (auditoria). `T-282`:
    resta outro vínculo — sem nenhum, a dívida não trava (pendência de
    inventário, `test_vinculos.py`)."""
    cliente = _cliente_real(monkeypatch, tmp_path)
    _responder(cliente, "B3.S01", "SIM")
    vinculo = _criar_em(cliente, "VINCULO_ID").json()["ficha"]["item_id"]
    _criar_em(cliente, "VINCULO_ID")
    margem = _criar_em(cliente, "MARGEM_ID", item_pai_id=vinculo).json()["ficha"]["item_id"]
    for ID, valor in (
        ("B3.S06A", "EMPRESTIMO"),
        ("B3.S06B", "1000"),
        ("B3.S06C", "400"),
        ("B3.S06D", "600"),
        ("B3.S06E", "2026-03-01"),
    ):
        assert _responder(cliente, ID, valor, margem).status_code == 200, ID
    divida = _criar_em(cliente, "DIVIDA_ID").json()["ficha"]["item_id"]
    _responder(cliente, "B5.A01", "Banco", divida)
    _responder(cliente, "B5.A02", "CONSIGNADO", divida)
    _responder(cliente, "B5.A02V", vinculo, divida)

    def completas() -> dict[str, bool]:
        return {
            f["item_id"]: f["completa"]
            for escopo in ("MARGEM_ID", "DIVIDA_ID")
            for f in _fichas(cliente, escopo)
        }

    def proxima_da_divida() -> str:
        corpo = cliente.get(f"/caso/{_CASO_ID}/pergunta", params={"item_id": divida}).json()
        ID: str = corpo["pergunta"]["ID"]
        return ID

    antes = completas()
    assert proxima_da_divida() != "B5.A02V"
    cliente.delete(f"/caso/{_CASO_ID}/fichas/VINCULO_ID/{vinculo}")
    depois = completas()

    assert antes[margem] is True
    assert depois[margem] is False
    assert proxima_da_divida() == "B5.A02V"
    gravadas = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl").listar_do_caso(_CASO_ID)
    assert any(
        r.ID_PERGUNTA == "VINCULO_DA_DIVIDA" and r.valor == vinculo for r in gravadas
    )


def test_t256_condicao_de_b5a02v_nao_menciona_cartao() -> None:
    """`R9-4` (decisão do produto, 2026-09-30): cartão consignado/benefício
    fica fora desta rodada (`T-279`)."""
    from collection.carga import carregar_registros

    (registro,) = [r for r in carregar_registros().registros if r.ID == "B5.A02V"]
    assert registro.condicao_exibicao is not None
    assert "CARTAO" not in repr(registro.condicao_exibicao)
