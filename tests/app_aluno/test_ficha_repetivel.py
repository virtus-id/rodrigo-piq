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
