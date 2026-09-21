"""`app/http/rotas_coleta.py::_resolver_valor` — os nove `TipoResposta`
convertidos corretamente (`T-101`, `RF-11`, `RF-13`, `AC-08`, `AC-13`).

Lacuna descoberta durante `T-95` (ver `tests/app_aluno/e2e/
test_ciclo_completo.py`): `_resolver_valor` só convertia `MOEDA`/`TAXA`
(`app/montagem/conversao.py`) e `NAO_SEI`; os outros seis `TipoResposta`
gravavam a string bruta do formulário, inutilizável por `app/montagem/
estado.py` (`_mecanismo_deficit` exige `frozenset[str]`; os campos
`ESCALA_0_10` exigem `int`).

Mesmo padrão de `tests/app_aluno/test_rotas_coleta_dirigida.py`: aplicação
FastAPI real, `dependency_overrides` de repositório substituídos por dublês
em memória (sem Postgres, sem `DATABASE_URL`), sessão aberta por uma rota de
teste (`iniciar_sessao_conta`), caso fabricado diretamente. Registros de
pergunta SINTÉTICOS (nunca conteúdo real das 291 perguntas) exercitam cada
`TipoResposta` isoladamente — a coleção real já é exercitada pelos testes de
`T-42`/`T-95`.

REGRAS: `RF-11`, `RF-13`, `AC-08`, `AC-13`
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_coleta import (
    obter_colecao_de_registros,
    obter_repositorio_itens,
    obter_repositorio_respostas,
)
from app.http.sessao import iniciar_sessao_conta
from app.montagem.estado import ErroSinalComportamentalAusente, _mecanismo_deficit
from collection.carga import ColecaoDeRegistros
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    OpcaoRegistro,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import Resposta, RespostasCaso

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-t101-conversao"
_CONTA_ID = "CONTA-T101-1"
_CASO_ID = "CASO-T101-1"


class _RepositorioRespostasEmMemoria:
    """Dublê mínimo de `persistencia.app_aluno.respostas.RepositorioRespostas`
    — grava em memória, sem checar consentimento (nunca levanta
    `ErroConsentimentoNaoRegistrado`)."""

    def __init__(self) -> None:
        self._respostas: list[Resposta] = []

    def gravar(self, resposta: Resposta) -> None:
        self._respostas = [
            r
            for r in self._respostas
            if not (r.ID_PERGUNTA == resposta.ID_PERGUNTA and r.item_id == resposta.item_id)
        ] + [resposta]

    def listar_do_caso(self, caso_id: str) -> tuple[Resposta, ...]:
        return tuple(r for r in self._respostas if r.CASO_ID == caso_id)


class _RepositorioItensVazio:
    """Dublê de `persistencia.app_aluno.itens.RepositorioItens` sem nenhum
    item — suficiente para os testes deste arquivo, que não exercitam
    perguntas `REP`."""

    def proximo_identificador(self, CASO_ID: str, escopo: object) -> str:  # pragma: no cover
        raise NotImplementedError

    def listar_do_caso(self, caso_id: str, *, incluir_removidos: bool = True) -> tuple[object, ...]:
        return ()


class _RepositorioCasosDublê:
    """Mesmo padrão de `tests/app_aluno/test_rotas_coleta_dirigida.py::
    _RepositorioCasosDublê` — só os métodos que `exigir_caso_da_sessao`
    (isolamento, T-31) usa."""

    def __init__(self, caso: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso
        self._conta_id_da_sessao = conta_id_da_sessao

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao


def _registro(
    ID: str,
    tipo: TipoResposta,
    VARIAVEL_GRAVADA: str,
    *,
    opcoes: tuple[OpcaoRegistro, ...] = (),
) -> RegistroPergunta:
    """Registro sintético mínimo — nenhum conteúdo das 291 perguntas reais,
    só a estrutura necessária para exercitar `_resolver_valor` por tipo."""
    return RegistroPergunta(
        ID=ID,
        bloco=99,
        enunciado="x",
        tipo=tipo,
        obrigatoriedade=frozenset({Obrigatoriedade.OPT}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=opcoes,
        VARIAVEL_GRAVADA=VARIAVEL_GRAVADA,
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=True,
        salto_consequencia=None,
    )


_REGISTRO_SELECAO_MULTIPLA = _registro(
    "T101.SEL_MULT",
    TipoResposta.SELECAO_MULTIPLA,
    "MECANISMO_DEFICIT_TESTE",
    opcoes=(
        OpcaoRegistro(rotulo="Corte", valor_interno="CORTE"),
        OpcaoRegistro(rotulo="Empréstimo", valor_interno="EMPRESTIMO"),
        OpcaoRegistro(rotulo="Atraso", valor_interno="ATRASO"),
    ),
)
_REGISTRO_NUMERO = _registro("T101.NUMERO", TipoResposta.NUMERO, "NUMERO_TESTE")
_REGISTRO_ESCALA = _registro("T101.ESCALA", TipoResposta.ESCALA_0_10, "ESCALA_TESTE")
_REGISTRO_DATA = _registro("T101.DATA", TipoResposta.DATA, "DATA_TESTE")
_REGISTRO_SELECAO_UNICA = _registro(
    "T101.SEL_UNICA",
    TipoResposta.SELECAO_UNICA,
    "SELECAO_UNICA_TESTE",
    opcoes=(OpcaoRegistro(rotulo="Sim", valor_interno="SIM"),),
)
_REGISTRO_TEXTO_CURTO = _registro("T101.TEXTO", TipoResposta.TEXTO_CURTO, "TEXTO_TESTE")
_REGISTRO_SIM_NAO_TALVEZ = _registro(
    "T101.SIM_NAO_TALVEZ",
    TipoResposta.SIM_NAO_TALVEZ,
    "SIM_NAO_TALVEZ_TESTE",
    opcoes=(
        OpcaoRegistro(rotulo="Sim", valor_interno="SIM"),
        OpcaoRegistro(rotulo="Não", valor_interno="NAO"),
        OpcaoRegistro(rotulo="Talvez", valor_interno="TALVEZ"),
    ),
)

_COLECAO_DE_TESTE = ColecaoDeRegistros(
    QUESTIONARIO_VERSION="T101-1.0.0",
    registros=(
        _REGISTRO_SELECAO_MULTIPLA,
        _REGISTRO_NUMERO,
        _REGISTRO_ESCALA,
        _REGISTRO_DATA,
        _REGISTRO_SELECAO_UNICA,
        _REGISTRO_TEXTO_CURTO,
        _REGISTRO_SIM_NAO_TALVEZ,
    ),
)


def _caso_fabricado() -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.COLETA_INICIAL,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="T101-1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, _RepositorioRespostasEmMemoria]:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    caso = _caso_fabricado()
    repositorio_casos = _RepositorioCasosDublê(caso, _CONTA_ID)
    repositorio_respostas = _RepositorioRespostasEmMemoria()

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: _COLECAO_DE_TESTE
    aplicacao.dependency_overrides[obter_repositorio_respostas] = lambda: repositorio_respostas
    aplicacao.dependency_overrides[obter_repositorio_itens] = lambda: _RepositorioItensVazio()

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente, repositorio_respostas


# ---------------------------------------------------------------------------
# Critério 1 — SELECAO_MULTIPLA grava frozenset[str], nunca string
# concatenada.
# ---------------------------------------------------------------------------


def test_ac08_selecao_multipla_grava_frozenset_a_partir_do_checklist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois checkboxes marcados (`name="valor"` repetido, mesmo formato de
    `report/templates/coleta/pergunta.html`) produzem um `frozenset[str]`
    com os dois valores — nunca uma string concatenada."""
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.SEL_MULT", "valor": ["CORTE", "ATRASO"]},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == "MECANISMO_DEFICIT_TESTE")
    assert valor_gravado == frozenset({"CORTE", "ATRASO"})
    assert isinstance(valor_gravado, frozenset)


def test_selecao_multipla_sem_nenhum_valor_marcado_grava_frozenset_vazio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nenhum checkbox marcado ⇒ `frozenset()`, um conjunto vazio de
    primeira classe — nunca ausência de gravação nem string vazia dentro do
    conjunto."""
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.SEL_MULT"},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == "MECANISMO_DEFICIT_TESTE")
    assert valor_gravado == frozenset()


# ---------------------------------------------------------------------------
# Critério 2 — ESCALA_0_10 e NUMERO gravam int; EC-01 para entrada inválida.
# ---------------------------------------------------------------------------


def test_ac08_numero_grava_int(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.NUMERO", "valor": "42"},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == "NUMERO_TESTE")
    assert valor_gravado == 42
    assert isinstance(valor_gravado, int)


def test_ec01_numero_com_entrada_nao_numerica_e_recusado_sem_gravar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nunca trunca (`"3.7"` não vira `3`) nem coage a `0` — recusa (`EC-01`)."""
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.NUMERO", "valor": "3.7"},
    )

    assert resposta.status_code == 400
    assert "NUMERO_TESTE" in resposta.text
    assert repositorio_respostas.listar_do_caso(_CASO_ID) == ()


def test_ac08_escala_0_10_grava_int(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.ESCALA", "valor": "7"},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == "ESCALA_TESTE")
    assert valor_gravado == 7
    assert isinstance(valor_gravado, int)


@pytest.mark.parametrize("valor_bruto", ["-1", "11", "abc"])
def test_ec01_escala_0_10_fora_do_dominio_ou_nao_numerica_e_recusada_sem_gravar(
    monkeypatch: pytest.MonkeyPatch, valor_bruto: str
) -> None:
    """Domínio fechado 0–10 (`AC-08`): fora da faixa ou não numérico, `EC-01`
    recusa sem gravar — nunca trunca para o extremo mais próximo."""
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.ESCALA", "valor": valor_bruto},
    )

    assert resposta.status_code == 400
    assert repositorio_respostas.listar_do_caso(_CASO_ID) == ()


# ---------------------------------------------------------------------------
# Critério 3 — DATA grava date; recusa entrada inválida.
# ---------------------------------------------------------------------------


def test_ac08_data_grava_date(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.DATA", "valor": "2026-03-15"},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == "DATA_TESTE")
    assert valor_gravado == date(2026, 3, 15)
    assert isinstance(valor_gravado, date)


def test_ec01_data_invalida_e_recusada_sem_gravar(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.DATA", "valor": "31/02/2026"},
    )

    assert resposta.status_code == 400
    assert "DATA_TESTE" in resposta.text
    assert repositorio_respostas.listar_do_caso(_CASO_ID) == ()


# ---------------------------------------------------------------------------
# Critério 4 — SELECAO_UNICA/SIM_NAO_TALVEZ/TEXTO_CURTO continuam gravando
# str, sem mudança de comportamento.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("id_pergunta", "variavel_gravada", "valor_enviado"),
    [
        ("T101.SEL_UNICA", "SELECAO_UNICA_TESTE", "SIM"),
        ("T101.TEXTO", "TEXTO_TESTE", "um texto qualquer"),
        ("T101.SIM_NAO_TALVEZ", "SIM_NAO_TALVEZ_TESTE", "TALVEZ"),
    ],
)
def test_ac08_selecao_unica_texto_curto_sim_nao_talvez_continuam_gravando_str(
    monkeypatch: pytest.MonkeyPatch, id_pergunta: str, variavel_gravada: str, valor_enviado: str
) -> None:
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": id_pergunta, "valor": valor_enviado},
    )

    assert resposta.status_code == 200, resposta.text
    gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    valor_gravado = next(r.valor for r in gravadas if r.ID_PERGUNTA == variavel_gravada)
    assert valor_gravado == valor_enviado
    assert isinstance(valor_gravado, str)


# ---------------------------------------------------------------------------
# Critério 5 — teste de regressão: a montagem (`_mecanismo_deficit`) aceita
# o valor gravado pela rota real, sem erro de tipo.
# ---------------------------------------------------------------------------


def test_regressao_mecanismo_deficit_aceita_valor_gravado_pela_rota_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antes de `T-101`, `_resolver_valor` gravava a STRING BRUTA do
    checklist para `SELECAO_MULTIPLA` — `app/montagem/estado.py::
    _mecanismo_deficit` recusa qualquer valor que não seja `frozenset` (ou
    `Desconhecido`), levantando `ErroSinalComportamentalAusente`. Este teste
    grava pela rota HTTP real e confirma que a montagem aceita o valor sem
    erro de tipo — a prova de que a lacuna foi fechada de ponta a ponta, não
    só na fronteira HTTP."""
    cliente, repositorio_respostas = _montar_cliente(monkeypatch)

    resposta = cliente.post(
        f"/caso/{_CASO_ID}/resposta",
        data={"ID_PERGUNTA": "T101.SEL_MULT", "valor": ["CORTE"]},
    )
    assert resposta.status_code == 200, resposta.text

    respostas_do_caso = RespostasCaso(respostas=repositorio_respostas.listar_do_caso(_CASO_ID))
    valor_bruto = respostas_do_caso.valor("MECANISMO_DEFICIT_TESTE")

    # Não levanta ErroSinalComportamentalAusente — a montagem aceita o valor.
    traduzido = _mecanismo_deficit(valor_bruto)
    assert traduzido == frozenset({"CORTE"})


def test_regressao_mecanismo_deficit_recusaria_string_bruta_pre_t101(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contraprova: uma `str` bruta (o comportamento ANTES de `T-101`) é
    exatamente o que `_mecanismo_deficit` recusa — confirma que o teste de
    regressão acima está testando a coisa certa."""
    with pytest.raises(ErroSinalComportamentalAusente):
        _mecanismo_deficit("CORTE")
