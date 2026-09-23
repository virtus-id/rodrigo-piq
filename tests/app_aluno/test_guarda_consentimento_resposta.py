"""Testes da guarda "sem consentimento, nenhuma resposta é gravada" — `RF-30`,
`AC-39` (T-36).

Cobre os quatro critérios de aceite pelo comportamento observável:

1. `AC-39`: tentar gravar resposta com o caso em `CADASTRADO` é recusado e
   nada é persistido — provado aqui SEM banco (dublê de cursor que registra
   se `INSERT` chegou a ser executado) e reconfirmado contra Postgres real em
   `tests/app_aluno/integracao/test_guarda_consentimento_resposta.py`.
2. a guarda é uma transição nomeada da máquina, verificável sem subir a
   aplicação HTTP — chamando `app.casos.maquina.exigir_estado_permite_
   resposta` diretamente, sem `TestClient` nem `psycopg`.
3. a rota de consentimento registra o aceite e dispara a transição num único
   caminho — coberto por `tests/app_aluno/test_rotas_consentimento.py`
   (usa `TestClient`, então fica em arquivo separado deste, que é livre de
   HTTP).
4. nenhuma resposta é gravada antes do registro de consentimento, por
   nenhuma rota — reforçado aqui provando que a checagem vive no adaptador de
   persistência (`RepositorioRespostasSupabase.gravar`), não numa rota:
   chamar o repositório DIRETAMENTE, sem qualquer rota, já basta para a
   recusa acontecer.

REGRAS: `RF-30`, `AC-39`
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.casos.maquina import (
    ESTADO_CASO,
    ESTADOS_QUE_PERMITEM_RESPOSTA,
    ErroConsentimentoNaoRegistrado,
    exigir_estado_permite_resposta,
)
from collection.respostas import Resposta
from persistencia.app_aluno.respostas import (
    ErroCasoInexistenteParaResposta,
    RepositorioRespostasSupabase,
)

# ---------------------------------------------------------------------------
# Critério 2 — a guarda é verificável sem subir a aplicação HTTP: funções
# Python puras, sem FastAPI, sem TestClient, sem banco.
# ---------------------------------------------------------------------------


def test_exigir_estado_permite_resposta_aceita_coleta_inicial() -> None:
    """Nenhuma exceção — `COLETA_INICIAL` está no conjunto que permite
    gravação, é o próprio estado do plano §7.1 para os Blocos 1-5."""
    exigir_estado_permite_resposta("CASO-1", ESTADO_CASO.COLETA_INICIAL)


@pytest.mark.parametrize(
    "estado_bloqueado",
    [ESTADO_CASO.CADASTRADO, ESTADO_CASO.CONSENTIMENTO_REGISTRADO],
)
def test_exigir_estado_permite_resposta_recusa_antes_do_consentimento(
    estado_bloqueado: ESTADO_CASO,
) -> None:
    """`AC-39`, direto na função de domínio: `CADASTRADO` e
    `CONSENTIMENTO_REGISTRADO` (o estado ANTES de `inicia_coleta` disparar)
    são recusados — nomeando `CASO_ID` e `estado` na exceção."""
    with pytest.raises(ErroConsentimentoNaoRegistrado) as capturado:
        exigir_estado_permite_resposta("CASO-1", estado_bloqueado)

    erro = capturado.value
    assert erro.caso_id == "CASO-1"
    assert erro.estado is estado_bloqueado


def test_estados_que_permitem_resposta_exclui_exatamente_os_dois_anteriores_ao_consentimento() -> (
    None
):
    """O conjunto é ENUMERADO (não calculado por ordem) e cobre TODOS os
    doze estados menos exatamente os dois que antecedem `inicia_coleta` —
    nenhum terceiro estado bloqueado por engano, nenhum dos dois liberado."""
    bloqueados = frozenset(ESTADO_CASO) - ESTADOS_QUE_PERMITEM_RESPOSTA
    assert bloqueados == {ESTADO_CASO.CADASTRADO, ESTADO_CASO.CONSENTIMENTO_REGISTRADO}


@pytest.mark.parametrize("estado_liberado", sorted(ESTADOS_QUE_PERMITEM_RESPOSTA, key=str))
def test_todo_estado_liberado_e_de_fato_aceito_sem_excecao(estado_liberado: ESTADO_CASO) -> None:
    """Exaustivo sobre os dez estados liberados: nenhum deles levanta
    `ErroConsentimentoNaoRegistrado` — reforço direto de que o conjunto não
    é maior nem menor do que o declarado."""
    exigir_estado_permite_resposta("CASO-QUALQUER", estado_liberado)


# ---------------------------------------------------------------------------
# Critério 1 (AC-39) e critério 4 — a checagem vive no ADAPTADOR de
# persistência, não numa rota: chamar `RepositorioRespostasSupabase.gravar`
# DIRETAMENTE (sem qualquer rota HTTP) já recusa e não persiste nada, se o
# caso não tiver consentimento. Dublê de cursor/conexão, sem banco real —
# reconfirmado contra Postgres real em
# tests/app_aluno/integracao/test_guarda_consentimento_resposta.py.
# ---------------------------------------------------------------------------


class _CursorComEstado:
    """Dublê de cursor `psycopg`: qualquer `execute` cujo SQL contenha
    `SELECT estado` devolve o `estado` configurado via `fetchone`; qualquer
    `execute` cujo SQL contenha `INSERT` é registrada em
    `insercoes_executadas` — usado para provar que NENHUM `INSERT` chega a
    ser executado quando a guarda recusa. O `SET search_path` de `_conectar`
    (T-22) não bate em nenhum dos dois filtros e é ignorado."""

    def __init__(self, estado_bruto: str | None) -> None:
        self._estado_bruto = estado_bruto
        self.insercoes_executadas: list[str] = []

    def __enter__(self) -> _CursorComEstado:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, *_args: object, **_kwargs: object) -> None:
        if "INSERT" in sql:
            self.insercoes_executadas.append(sql)

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._estado_bruto is None:
            return None
        return (self._estado_bruto,)


class _ConexaoComEstado:
    def __init__(self, estado_bruto: str | None) -> None:
        self.cursor_dublê = _CursorComEstado(estado_bruto)
        self.commit_chamado = False
        self.rollback_chamado = False

    def cursor(self) -> _CursorComEstado:
        return self.cursor_dublê

    def commit(self) -> None:
        self.commit_chamado = True

    def rollback(self) -> None:
        self.rollback_chamado = True

    def close(self) -> None:
        pass


class _PoolQueDevolveConexaoFalsa:
    """Dublê de `ConnectionPool` (`T-187`): `getconn` sempre devolve a
    conexão falsa do teste; `putconn` só sinaliza, nunca fecha nada de
    verdade. `_conectar` (T-187) pega conexão do pool em vez de chamar
    `psycopg.connect` a cada operação — substituir `psycopg.connect` não
    intercepta mais nada; este dublê troca o seam certo."""

    def __init__(self, conexao: object) -> None:
        self._conexao = conexao

    def getconn(self) -> object:
        return self._conexao

    def putconn(self, _conexao: object) -> None:
        pass


def _resposta_de_teste(caso_id: str) -> Resposta:
    return Resposta(
        CASO_ID=caso_id,
        ID_PERGUNTA="B1.01",
        item_id=None,
        valor="sim",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )


def test_ac39_gravar_com_caso_em_cadastrado_e_recusado_e_nada_e_persistido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AC-39`, o critério literal: caso em `CADASTRADO`, tentativa de
    `RepositorioRespostasSupabase.gravar` DIRETO (sem nenhuma rota HTTP no
    caminho) — recusada, e o `INSERT` nunca chega a ser executado."""
    conexao_dublê = _ConexaoComEstado(ESTADO_CASO.CADASTRADO.value)
    monkeypatch.setattr(
        "persistencia.app_aluno.respostas.obter_pool",
        lambda: _PoolQueDevolveConexaoFalsa(conexao_dublê),
    )

    repositorio = RepositorioRespostasSupabase()

    with pytest.raises(ErroConsentimentoNaoRegistrado):
        repositorio.gravar(_resposta_de_teste("CASO-SEM-CONSENTIMENTO"))

    assert conexao_dublê.cursor_dublê.insercoes_executadas == [], (
        "AC-39: nenhum INSERT deveria ter sido executado"
    )
    assert conexao_dublê.commit_chamado is False
    assert conexao_dublê.rollback_chamado is True


def test_gravar_com_caso_em_consentimento_registrado_tambem_e_recusado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reforço do critério 4: `CONSENTIMENTO_REGISTRADO` (o carimbo já foi
    gravado, mas `inicia_coleta` ainda não disparou) também recusa — o
    critério de aceite é "antes do registro de consentimento" no sentido de
    "antes da coleta começar", não apenas "antes do carimbo existir"."""
    conexao_dublê = _ConexaoComEstado(ESTADO_CASO.CONSENTIMENTO_REGISTRADO.value)
    monkeypatch.setattr(
        "persistencia.app_aluno.respostas.obter_pool",
        lambda: _PoolQueDevolveConexaoFalsa(conexao_dublê),
    )

    repositorio = RepositorioRespostasSupabase()

    with pytest.raises(ErroConsentimentoNaoRegistrado):
        repositorio.gravar(_resposta_de_teste("CASO-SO-CONSENTIU"))

    assert conexao_dublê.cursor_dublê.insercoes_executadas == []


def test_gravar_com_coleta_inicial_e_aceito_e_insert_e_executado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contraprova: com o caso em `COLETA_INICIAL`, a guarda deixa passar e
    o `INSERT` É executado — a recusa acima é da guarda, não de um bug que
    recusasse tudo."""
    conexao_dublê = _ConexaoComEstado(ESTADO_CASO.COLETA_INICIAL.value)
    monkeypatch.setattr(
        "persistencia.app_aluno.respostas.obter_pool",
        lambda: _PoolQueDevolveConexaoFalsa(conexao_dublê),
    )

    repositorio = RepositorioRespostasSupabase()
    repositorio.gravar(_resposta_de_teste("CASO-EM-COLETA"))

    assert len(conexao_dublê.cursor_dublê.insercoes_executadas) == 1
    assert conexao_dublê.commit_chamado is True


def test_gravar_com_caso_inexistente_e_recusado_sem_assumir_estado_liberado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um `CASO_ID` que não existe em `app_aluno.casos` nunca é tratado como
    "estado que permite resposta" por omissão — a ausência de linha vira
    `ErroCasoInexistenteParaResposta`, nunca uma gravação silenciosa."""
    conexao_dublê = _ConexaoComEstado(None)
    monkeypatch.setattr(
        "persistencia.app_aluno.respostas.obter_pool",
        lambda: _PoolQueDevolveConexaoFalsa(conexao_dublê),
    )

    repositorio = RepositorioRespostasSupabase()

    with pytest.raises(ErroCasoInexistenteParaResposta):
        repositorio.gravar(_resposta_de_teste("CASO-QUE-NAO-EXISTE"))

    assert conexao_dublê.cursor_dublê.insercoes_executadas == []
