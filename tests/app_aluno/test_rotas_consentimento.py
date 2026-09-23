"""Testes de `app/http/rotas_consentimento.py` — `RF-30`, `AC-39` (T-36).

Critério 3: "a rota de consentimento registra o aceite e dispara a
transição num único caminho". Cobre também que a rota bloqueia sem
`PEND-01` e que ela usa o mesmo mecanismo de isolamento por `CASO_ID`
(`RF-02`, `AC-03`, T-31) de qualquer outra rota desta feature.

Dublês em memória para `RepositorioCasos`/`RepositorioConsentimentos`, mesmo
mecanismo de injeção que a produção usa — sem tocar Postgres. A sessão é
aberta por uma rota auxiliar de teste que chama `iniciar_sessao_conta` de
verdade (mesmo padrão de `test_rotas_conta.py::cliente`), nunca por um
cookie montado à mão — o formato exato do cookie assinado é detalhe interno
do `SessionMiddleware`, não algo que um teste deva reconstruir.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.consentimento.registro import RegistroConsentimento, TextoConsentimento
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_consentimento import obter_repositorio_consentimentos, obter_repositorio_eventos
from app.http.sessao import iniciar_sessao_conta
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.eventos import EventoCaso

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


class _RepositorioCasosDublê(RepositorioCasos):
    """Dublê em memória: um único `Caso`, mutável por `transicionar_estado`
    — suficiente para provar que a rota persiste a transição real."""

    def __init__(self, caso_inicial: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso_inicial
        self._conta_id_da_sessao = conta_id_da_sessao
        self.transicoes_chamadas: list[ESTADO_CASO] = []

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao

    def transicionar_estado(
        self, caso_id: str, novo_estado: ESTADO_CASO, agora: datetime | None = None
    ) -> Caso:
        self.transicoes_chamadas.append(novo_estado)
        self._caso = Caso(
            CASO_ID=self._caso.CASO_ID,
            conta_id=self._caso.conta_id,
            estado=novo_estado,
            DATA_REFERENCIA=self._caso.DATA_REFERENCIA,
            QUESTIONARIO_VERSION=self._caso.QUESTIONARIO_VERSION,
            snapshot_raiz_id=self._caso.snapshot_raiz_id,
            snapshot_liberado_id=self._caso.snapshot_liberado_id,
            ultima_interacao_em=agora or datetime.now(UTC),
            criado_em=self._caso.criado_em,
        )
        return self._caso

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None:
        """`T-91`: a rota de consentimento passou a usar a variante
        CONDICIONAL (via `app.casos.progresso.transicionar_e_registrar`) —
        mesma semântica de `RepositorioCasosSupabase`/`RepositorioCasosArquivo`:
        só grava se `self._caso.estado == estado_esperado`, devolvendo `None`
        sem gravar caso contrário."""
        if self._caso.CASO_ID != caso_id or self._caso.estado is not estado_esperado:
            return None
        return self.transicionar_estado(caso_id, novo_estado, agora)

    def registrar_interacao(self, caso_id: str, agora: datetime | None = None) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id: str, snapshot_raiz_id: str) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_liberado(self, caso_id: str, snapshot_liberado_id: str) -> None:
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def listar_por_estado(self, estado: ESTADO_CASO) -> tuple[str, ...]:
        raise NotImplementedError  # pragma: no cover — não usado aqui (T-69)

    def listar_todos(self) -> tuple[str, ...]:
        raise NotImplementedError  # pragma: no cover — não usado aqui (T-102)


class _RepositorioConsentimentosDublê:
    """Dublê em memória de `RepositorioConsentimentos` — grava em lista,
    nunca toca banco."""

    def __init__(self) -> None:
        self.registros: list[RegistroConsentimento] = []

    def gravar(self, consentimento_id: str, registro: RegistroConsentimento) -> None:
        self.registros.append(registro)

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroConsentimento, ...]:
        return tuple(r for r in self.registros if r.CASO_ID == caso_id)


class _RepositorioEventosDublê:
    """`T-91` (`RF-31`/`AC-40`) — dublê em memória da trilha de eventos do
    caso, mesmo papel de `_RepositorioConsentimentosDublê`: grava em lista,
    nunca toca banco."""

    def __init__(self) -> None:
        self.eventos: list[EventoCaso] = []

    def registrar(self, evento: EventoCaso) -> None:
        self.eventos.append(evento)

    def listar_do_caso(self, caso_id: str) -> tuple[EventoCaso, ...]:
        return tuple(e for e in self.eventos if e.CASO_ID == caso_id)


def _caso_fabricado(estado: ESTADO_CASO, caso_id: str = "CASO-CONSENTIMENTO-1") -> Caso:
    return Caso(
        CASO_ID=caso_id,
        conta_id="CONTA-1",
        estado=estado,
        DATA_REFERENCIA=date(2026, 1, 1),
        QUESTIONARIO_VERSION="PENDENTE",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_aplicacao_de_teste(
    monkeypatch: pytest.MonkeyPatch,
    repositorio_casos: _RepositorioCasosDublê,
    repositorio_consentimentos: _RepositorioConsentimentosDublê,
    diretorio_textos: Path | None = None,
    raise_server_exceptions: bool = True,
) -> TestClient:
    """Monta `criar_aplicacao()` com os dois repositórios substituídos e uma
    rota auxiliar `/_teste/abrir-sessao` que chama `iniciar_sessao_conta` de
    verdade — mesmo papel de `/_teste/quem-sou` em `test_rotas_conta.py`."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    if diretorio_textos is not None:

        def _carregar_texto_vigente_fabricado(
            diretorio: Path | None = None,
        ) -> TextoConsentimento:
            from app.consentimento.registro import carregar_texto_vigente as original

            return original(diretorio_textos)

        monkeypatch.setattr(
            "app.http.rotas_consentimento.carregar_texto_vigente",
            _carregar_texto_vigente_fabricado,
        )
        # T-144: a rota JSON (`/api/caso/{id}/consentimento`) vive noutro
        # módulo e importou sua PRÓPRIA referência a `carregar_texto_vigente`
        # — o patch acima não a alcança. Duas referências, dois patches.
        monkeypatch.setattr(
            "app.http.rotas_api_conta.carregar_texto_vigente",
            _carregar_texto_vigente_fabricado,
        )

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_consentimentos] = (
        lambda: repositorio_consentimentos
    )
    # T-91 (RF-31/AC-40): a rota agora também exige o repositório da trilha
    # de eventos — um dublê novo por chamada basta, nenhum teste desta suíte
    # precisa inspecioná-lo (o foco é o comportamento de RF-30/AC-39).
    repositorio_eventos = _RepositorioEventosDublê()
    aplicacao.dependency_overrides[obter_repositorio_eventos] = lambda: repositorio_eventos

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    return TestClient(
        aplicacao, base_url="https://teste.local", raise_server_exceptions=raise_server_exceptions
    )


@pytest.fixture
def diretorio_textos_fabricado(tmp_path: Path) -> Path:
    """Um `.yaml` de texto de consentimento FABRICADO (não é a redação real
    de `PEND-01`) — só para exercitar o mecanismo de carga."""
    (tmp_path / "v1.yaml").write_text(
        "QUESTIONARIO_VERSION: '1.0.0'\ntitulo: fabricado\ncorpo: fabricado\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def cliente_com_sessao(
    monkeypatch: pytest.MonkeyPatch,
    diretorio_textos_fabricado: Path,
) -> tuple[TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str]:
    """Cliente com sessão aberta para `conta_id="CONTA-1"`, dona do caso
    `CASO-CONSENTIMENTO-1` (em `CADASTRADO`) e texto de consentimento
    fabricado disponível — equivalente a um aluno já logado, prestes a
    consentir pela primeira vez."""
    caso_id = "CASO-CONSENTIMENTO-1"
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.CADASTRADO, caso_id), conta_id_da_sessao="CONTA-1"
    )
    repositorio_consentimentos = _RepositorioConsentimentosDublê()

    cliente = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos, repositorio_consentimentos, diretorio_textos_fabricado
    )
    cliente.post("/_teste/abrir-sessao/CONTA-1")

    return cliente, repositorio_casos, repositorio_consentimentos, caso_id


# ---------------------------------------------------------------------------
# Critério 3 — a rota registra o aceite e dispara a transição num único
# caminho.
# ---------------------------------------------------------------------------


def test_post_consentimento_grava_registro_e_transiciona_o_caso(
    cliente_com_sessao: tuple[
        TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str
    ],
) -> None:
    cliente, repositorio_casos, repositorio_consentimentos, caso_id = cliente_com_sessao

    resposta = cliente.post(f"/caso/{caso_id}/consentimento", data={"aceite": "on"})

    assert resposta.status_code == 200
    assert len(repositorio_consentimentos.registros) == 1
    assert repositorio_consentimentos.registros[0].CASO_ID == caso_id
    assert repositorio_consentimentos.registros[0].aceite is True

    # `T-173`: DUAS transições, nesta ordem. O aceite registra o
    # consentimento e, em seguida, `inicia_coleta` abre a coleta — antes,
    # a segunda não existia em rota nenhuma, e o aluno travava logo após
    # aceitar o termo (a gravação da primeira resposta era recusada por
    # `ErroConsentimentoNaoRegistrado`).
    assert repositorio_casos.transicoes_chamadas == [
        ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        ESTADO_CASO.COLETA_INICIAL,
    ]
    # O estado FINAL é `COLETA_INICIAL`: é onde o aluno precisa estar para
    # a primeira resposta ser aceita (`exigir_estado_permite_resposta`).
    caso_apos = repositorio_casos.buscar(caso_id)
    assert caso_apos is not None
    assert caso_apos.estado == ESTADO_CASO.COLETA_INICIAL


def test_recusa_registra_mas_nao_avanca_o_caso(
    cliente_com_sessao: tuple[
        TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str
    ],
) -> None:
    """`RF-30`, `T-178` — quem recusa o termo NÃO tem a coleta iniciada.

    **O defeito que este teste fecha.** A transição acontecia sem olhar o
    valor de `aceite`: quem recusasse ficava no mesmo estado de quem
    aceitou, e a coleta começava. A proteção existia só na tela (botão
    desabilitado sem o checkbox), então um `POST` direto sem `aceite`
    avançava o caso — e "recusou, mas o sistema seguiu" é exatamente o que
    a LGPD não admite.

    **A recusa é REGISTRADA.** Negar consentimento é um fato com valor
    probatório; apagá-lo deixaria o caso indistinguível de "nunca
    respondeu". O que não acontece é a transição."""
    cliente, repositorio_casos, repositorio_consentimentos, caso_id = cliente_com_sessao

    # Sem `aceite` no corpo — é o que um POST direto (fora da tela) envia.
    resposta = cliente.post(f"/caso/{caso_id}/consentimento", data={})

    assert resposta.status_code == 200

    # A recusa foi gravada, com `aceite=False`.
    assert len(repositorio_consentimentos.registros) == 1
    assert repositorio_consentimentos.registros[0].aceite is False

    # E NENHUMA transição aconteceu: o caso segue onde estava.
    assert repositorio_casos.transicoes_chamadas == []
    caso_apos = repositorio_casos.buscar(caso_id)
    assert caso_apos is not None
    assert caso_apos.estado == ESTADO_CASO.CADASTRADO


def test_post_consentimento_grava_versao_do_texto_vigente(
    cliente_com_sessao: tuple[
        TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str
    ],
) -> None:
    """O registro guarda a versão do texto que embasou o aceite (critério de
    aceite herdado de T-35, reafirmado aqui pela rota real)."""
    cliente, _repositorio_casos, repositorio_consentimentos, caso_id = cliente_com_sessao

    cliente.post(f"/caso/{caso_id}/consentimento", data={"aceite": "on"})

    assert repositorio_consentimentos.registros[0].versao_texto == "1.0.0"


def test_api_entrega_o_texto_vigente_para_a_tela_de_aceite(
    cliente_com_sessao: tuple[
        TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str
    ],
) -> None:
    """T-144: o `GET` HTML virou `GET /api/caso/{id}/consentimento`.

    O propósito é o mesmo — o aluno precisa LER o que está aceitando antes
    de aceitar —, e o texto continua vindo de `carregar_texto_vigente`
    (`PEND-01`, insumo do jurídico), nunca escrito no código."""
    cliente, _repositorio_casos, _repositorio_consentimentos, caso_id = cliente_com_sessao

    resposta = cliente.get(
        f"/api/caso/{caso_id}/consentimento", headers={"accept": "application/json"}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["CASO_ID"] == caso_id
    assert corpo["titulo"]
    assert corpo["corpo"]
    assert corpo["QUESTIONARIO_VERSION"] == "1.0.0"


# ---------------------------------------------------------------------------
# A rota usa o MESMO mecanismo de isolamento por CASO_ID (RF-02, AC-03).
# ---------------------------------------------------------------------------


def test_post_consentimento_de_caso_de_outra_conta_recebe_404(
    cliente_com_sessao: tuple[
        TestClient, _RepositorioCasosDublê, _RepositorioConsentimentosDublê, str
    ],
) -> None:
    cliente, _repositorio_casos, repositorio_consentimentos, _caso_id = cliente_com_sessao

    resposta = cliente.post("/caso/CASO-DE-OUTRA-CONTA/consentimento", data={"aceite": "on"})

    assert resposta.status_code == 404
    assert repositorio_consentimentos.registros == []


def test_post_consentimento_sem_sessao_recebe_401_antes_de_tocar_o_banco(
    monkeypatch: pytest.MonkeyPatch,
    diretorio_textos_fabricado: Path,
) -> None:
    caso_id = "CASO-CONSENTIMENTO-1"
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.CADASTRADO, caso_id), conta_id_da_sessao="CONTA-1"
    )
    repositorio_consentimentos = _RepositorioConsentimentosDublê()
    # Nenhuma chamada a /_teste/abrir-sessao — cliente sem cookie de sessão.
    cliente_sem_sessao = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos, repositorio_consentimentos, diretorio_textos_fabricado
    )

    resposta = cliente_sem_sessao.post(f"/caso/{caso_id}/consentimento", data={"aceite": "on"})

    assert resposta.status_code == 401
    assert repositorio_consentimentos.registros == []
    assert repositorio_casos.transicoes_chamadas == []


# ---------------------------------------------------------------------------
# Sem PEND-01 (texto ausente), a rota bloqueia — nem registro nem transição.
# ---------------------------------------------------------------------------


def test_post_consentimento_sem_texto_vigente_bloqueia_com_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    caso_id = "CASO-CONSENTIMENTO-1"
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.CADASTRADO, caso_id), conta_id_da_sessao="CONTA-1"
    )
    repositorio_consentimentos = _RepositorioConsentimentosDublê()

    # `tmp_path` vazio de `.yaml`, não o diretório real `app/consentimento/
    # textos/` — desde que o texto de `PEND-01` foi publicado (T-190), o
    # diretório real deixou de estar vazio, e o bloqueio que este teste prova
    # precisa de um diretório fabricado sem arquivo, não mais do estado da
    # produção.
    cliente = _montar_aplicacao_de_teste(
        monkeypatch, repositorio_casos, repositorio_consentimentos, tmp_path
    )
    cliente.post("/_teste/abrir-sessao/CONTA-1")

    resposta = cliente.post(f"/caso/{caso_id}/consentimento", data={"aceite": "on"})

    assert resposta.status_code == 503
    assert repositorio_consentimentos.registros == []
    assert repositorio_casos.transicoes_chamadas == []


# ---------------------------------------------------------------------------
# A transição é validada contra a MÁQUINA — não confia cegamente no
# repositório (que não revalida a tabela de transições).
# ---------------------------------------------------------------------------


def test_post_consentimento_com_caso_fora_de_cadastrado_e_recusado(
    monkeypatch: pytest.MonkeyPatch,
    diretorio_textos_fabricado: Path,
) -> None:
    """Um caso já em `COLETA_INICIAL` (por exemplo, um replay do formulário)
    não deveria conseguir "reconsentir" — `app.casos.maquina.transicionar`
    recusa `(COLETA_INICIAL, CONSENTIMENTO_REGISTRADO)` com
    `ErroTransicaoNaoDeclarada`, e nem o registro nem a transição ocorrem."""
    caso_id = "CASO-JA-EM-COLETA"
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL, caso_id), conta_id_da_sessao="CONTA-1"
    )
    repositorio_consentimentos = _RepositorioConsentimentosDublê()

    cliente = _montar_aplicacao_de_teste(
        monkeypatch,
        repositorio_casos,
        repositorio_consentimentos,
        diretorio_textos_fabricado,
        raise_server_exceptions=False,
    )
    cliente.post("/_teste/abrir-sessao/CONTA-1")

    resposta = cliente.post(f"/caso/{caso_id}/consentimento", data={"aceite": "on"})

    assert resposta.status_code == 500
    assert repositorio_consentimentos.registros == []
    assert repositorio_casos.transicoes_chamadas == []
