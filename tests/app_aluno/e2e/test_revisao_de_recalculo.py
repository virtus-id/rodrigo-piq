"""E2E de síntese — `US-07` ponta a ponta: quitação confirmada → recálculo →
fila → tela lado a lado do revisor → liberação — `RF-23`, `RF-26`, `AC-26`,
`AC-29` (T-96).

**Esta tarefa CONTINUA de onde `test_ciclo_completo.py` (T-95/T-101) parou —
não repete a jornada de coleta.** T-95 já prova, com as rotas HTTP reais de
cadastro/consentimento/coleta multissessão/Bloco 6, que um caso chega ao
PRIMEIRO plano liberado. A política de revisão (`plans/app-aluno.plan.md`,
citada na descrição de T-96) **não distingue primeiro envio de recálculo**:
por isso este arquivo não RECONSTITUI aquela jornada de 25 respostas — ele
parte de um caso já em `ACOMPANHAMENTO`, com um snapshot raiz liberado, pelo
MESMO mecanismo de preparação que `tests/app_aluno/integracao/
test_bloco11.py::repositorio_casos_arquivo` (T-88) já usa e prova
isoladamente: fixture de caso completo (`tests/app_aluno/fixtures/
caso_completo.py`, T-53) montada em `EstadoFinanceiro` real e calculada pelo
MESMO executor do Bloco 6 (`app/motor/executor.py::executar_calculo`), com o
primeiro snapshot liberado por uma chamada real a `app.revisao.fila.liberar`
(a mesma função que a rota `POST /revisao/caso/{CASO_ID_REVISAO}/decisao`,
abaixo, delega por dentro — T-95 já prova esse caminho via HTTP; reconstituir
aqui uma segunda vez a via HTTP da PRIMEIRA liberação seria repetir T-95, não
estender). **Nenhuma duplicação de `test_bloco11.py`/T-88 (recálculo em si) e
`test_disparar_recalculo.py`/T-86 (`AC-26` isolado)**: a PARTE NOVA desta
tarefa é tudo o que vem DEPOIS do recálculo — a experiência real do REVISOR,
com as rotas `/revisao/*` (T-69 a T-72), nunca chamando `app/revisao/
fila.py::liberar` diretamente para a SEGUNDA decisão.

**O fluxo provado por este arquivo, num único teste contínuo:**

1. Preparação (reaproveitada, não nova): caso em `ACOMPANHAMENTO`, primeiro
   snapshot liberado (`snapshot_liberado_id` preenchido) — o aluno já vê o
   primeiro plano por `GET /caso/{CASO_ID}/plano`.
2. `B11.Q01 = "Sim"` via `POST /caso/{CASO_ID}/bloco-11/resposta` (rota real,
   T-82) — identifica `EVENTO_RECALCULO.QUITACAO_CONFIRMADA`.
3. O "consumidor" (`app.casos.acompanhamento.processar_resposta_bloco_11`,
   T-87, o mesmo padrão de T-88) recebe EXATAMENTE esse evento e dispara o
   recálculo real (`disparar_recalculo`, T-86) — segundo snapshot, encadeado.
4. `AC-26`: **antes de qualquer acesso do aluno**, o snapshot de recálculo já
   aparece em `GET /revisao/fila` (rota real, sessão de revisor via
   `e_revisor=True`, T-100) — verificado consultando a fila ANTES de o
   aluno acessar `GET /caso/{CASO_ID}/plano` de novo.
5. `AC-29`: `GET /revisao/caso/{CASO_ID_REVISAO}` (rota real, T-70) mostra
   plano e `estado_inputs` do snapshot recalculado NA MESMA sessão do
   revisor, sem navegação para outro caso.
6. `POST /revisao/caso/{CASO_ID_REVISAO}/decisao` com `decisao=LIBERAR`
   (rota real, T-71) — a SEGUNDA liberação, via HTTP, nunca por chamada
   direta a `app.revisao.fila.liberar`.
7. Depois da liberação: `GET /caso/{CASO_ID}/plano` (aluno) mostra o plano
   NOVO (`SNAPSHOT_ID` do recálculo), e o snapshot anterior (primeiro plano)
   permanece recuperável no histórico (`RepositorioSnapshots.historico`,
   append-only — nunca sobrescrito).

**Adaptador de arquivo (T-24), sem `DATABASE_URL`.** Mesma disciplina de
`test_ciclo_completo.py`: `RepositorioCasosArquivo`/`RepositorioRespostasArquivo`/
`RepositorioItensArquivo`/`RepositorioEventosCasoArquivo`/
`RepositorioSnapshotsArquivo` sobre `tmp_path`, e um dublê em memória de
`RepositorioContas` (nenhum adaptador de arquivo publicado para contas) que,
diferente do de T-95, PERMITE marcar uma conta como revisora
(`e_revisor=True`) — o equivalente em memória de `persistencia/app_aluno/
contas.py::promover_a_revisor` (T-100), nunca uma segunda via de autorização
inventada: a guarda real (`app/http/isolamento.py::exigir_papel_revisor`)
continua sendo a que decide, consultando este mesmo repositório a cada
requisição.

**Credencial de revisor real (T-100).** O revisor loga por `POST /conta/
login` como qualquer conta — a distinção de papel é inteiramente pelo campo
`e_revisor` da conta, nunca por uma rota de login separada (não existe uma).

REGRAS: `RF-23`, `RF-26`, `AC-26`, `AC-29`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.casos.acompanhamento import processar_resposta_bloco_11
from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos, obter_repositorio_contas_para_papel
from app.http.rotas_bloco11 import obter_colecao_de_registros as obter_colecao_bloco11
from app.http.rotas_bloco11 import obter_repositorio_respostas as obter_repositorio_respostas_b11
from app.http.rotas_bloco11 import roteador as roteador_bloco11
from app.http.rotas_conta import CadastroConta, obter_cadastro_conta, obter_repositorio_contas
from app.http.rotas_plano import obter_repositorio_snapshots as obter_repositorio_snapshots_plano
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_eventos_da_decisao,
    obter_repositorio_revisoes_da_decisao,
    obter_repositorio_snapshots_da_fila,
)
from app.http.rotas_revisao import roteador as roteador_revisao
from app.http.senhas import hashear_senha, verificar_senha
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.motor.executor import ParametrosDoCalculo, executar_calculo
from app.revisao.fila import RegistroRevisao, liberar
from collection.carga import carregar_registros
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    CasoCompleto,
    caso_completo,
)

pytestmark = pytest.mark.e2e

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-t96-revisao-recalculo"
_PARAMETROS_VERSAO = "1.0.1"
_SENHA_ALUNO = "senha-de-teste-t96-aluno"
_SENHA_REVISOR = "senha-de-teste-t96-revisor"
_DIVIDA_ID = "D001"


# ---------------------------------------------------------------------------
# Dublê em memória de `RepositorioContas` — mesmo papel de
# `test_ciclo_completo.py::_RepositorioContasEmMemoria`, ACRESCIDO da
# capacidade de marcar `e_revisor=True` (equivalente em memória de
# `persistencia/app_aluno/contas.py::promover_a_revisor`, T-100) — nenhum
# adaptador de arquivo publicado para contas.
# ---------------------------------------------------------------------------


class _RepositorioContasEmMemoria:
    """Implementa `RepositorioContas` (`persistencia/app_aluno/contas.py`)
    inteiramente em memória, com hash real de senha (`app/http/senhas.py`,
    T-28) — nunca texto claro guardado."""

    def __init__(self) -> None:
        self._por_email: dict[str, Conta] = {}
        self._por_id: dict[str, Conta] = {}

    def criar(self, conta_id: str, email: str, senha: str) -> None:
        if email in self._por_email:
            raise ErroEmailDuplicado(f"e-mail já cadastrado: email={email!r}")
        conta = Conta(
            conta_id=conta_id,
            email=email,
            senha_hash=hashear_senha(senha),
            criado_em=datetime.now(UTC),
        )
        self._por_email[email] = conta
        self._por_id[conta_id] = conta

    def buscar_por_email(self, email: str) -> Conta | None:
        return self._por_email.get(email)

    def buscar_por_id(self, conta_id: str) -> Conta | None:
        return self._por_id.get(conta_id)

    def autenticar(self, email: str, senha: str) -> Conta | None:
        conta = self._por_email.get(email)
        if conta is None:
            return None
        # `T-179`: conta provisionada sem senha não autentica — mesma
        # guarda do `RepositorioContasSupabase` real.
        if conta.senha_hash is None:
            return None
        if not verificar_senha(conta.senha_hash, senha):
            return None
        return conta

    def promover_a_revisor(self, email: str) -> None:
        """Equivalente em memória de `persistencia/app_aluno/contas.py::
        promover_a_revisor` (T-100) — mesma operação de administração fora
        de UI, nunca uma rota HTTP nova. Usada só por este teste para dar a
        uma conta já cadastrada pelo fluxo normal (`criar`, acima) a
        credencial de revisor real."""
        conta = self._por_email[email]
        promovida = Conta(
            conta_id=conta.conta_id,
            email=conta.email,
            senha_hash=conta.senha_hash,
            criado_em=conta.criado_em,
            e_revisor=True,
        )
        self._por_email[email] = promovida
        self._por_id[conta.conta_id] = promovida


class _RepositorioRevisoesEmMemoria:
    """Implementa o recorte `RepositorioRevisoesDaDecisao` de `app/revisao/
    fila.py::liberar`/`reprovar` — mesmo papel de `test_ciclo_completo.py::
    _RepositorioRevisoesEmMemoria`, sem tocar Postgres."""

    def __init__(self) -> None:
        self._por_caso: dict[str, list[RegistroRevisao]] = {}

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        self._por_caso.setdefault(registro.CASO_ID, []).append(registro)

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroRevisao, ...]:
        return tuple(self._por_caso.get(caso_id, ()))


def _montar_estado_do_caso(caso: CasoCompleto) -> object:
    """Mesma montagem de `tests/app_aluno/integracao/test_bloco11.py::
    _montar_estado_do_caso` — leitura pura das respostas da fixture,
    nenhuma invenção de dado."""
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    return montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )


def test_us07_recalculo_passa_pela_fila_ac26_ac29_e_segunda_liberacao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    repositorio_casos = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    repositorio_respostas = RepositorioRespostasArquivo(
        tmp_path / "respostas.jsonl", repositorio_casos=repositorio_casos
    )
    repositorio_eventos = RepositorioEventosCasoArquivo(tmp_path / "eventos.jsonl")
    repositorio_snapshots = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
    repositorio_contas = _RepositorioContasEmMemoria()
    repositorio_revisoes = _RepositorioRevisoesEmMemoria()
    fonte_parametros = FonteParametrosArquivo()

    email_aluno = f"t96-aluno-{uuid.uuid4().hex}@teste.invalido"
    email_revisor = f"t96-revisor-{uuid.uuid4().hex}@teste.invalido"
    conta_aluno_id = f"CONTA_{uuid.uuid4().hex}"
    conta_revisor_id = f"CONTA_{uuid.uuid4().hex}"
    caso_id = f"CASO_{uuid.uuid4().hex}"

    repositorio_contas.criar(conta_aluno_id, email_aluno, _SENHA_ALUNO)
    repositorio_contas.criar(conta_revisor_id, email_revisor, _SENHA_REVISOR)
    repositorio_contas.promover_a_revisor(email_revisor)

    class _CadastroContaJaExistente(CadastroConta):
        """Não usada por este teste (a conta nasce diretamente acima) — a
        aplicação exige o ponto de injeção declarado; devolve o par já
        criado para satisfazer o tipo sem duplicar `/conta/cadastro`
        (já provado por T-95)."""

        def __call__(self, email: str, senha: str) -> tuple[Conta, Caso]:  # pragma: no cover
            raise NotImplementedError("cadastro via HTTP já provado por T-95")

    # -----------------------------------------------------------------
    # 1. PREPARAÇÃO reaproveitada — caso em ACOMPANHAMENTO com o PRIMEIRO
    #    snapshot liberado, mesmo mecanismo de `tests/app_aluno/integracao/
    #    test_bloco11.py::repositorio_casos_arquivo` (T-88): fixture de caso
    #    completo (T-53) → EstadoFinanceiro real → MESMO executor do
    #    Bloco 6 → liberação real (`app.revisao.fila.liberar`, T-68 — a
    #    mesma função que a rota de decisão usa por dentro).
    # -----------------------------------------------------------------
    agora = datetime(2026, 1, 1, tzinfo=UTC)
    repositorio_casos.criar(
        Caso(
            CASO_ID=caso_id,
            conta_id=conta_aluno_id,
            estado=ESTADO_CASO.COLETA_INICIAL,
            DATA_REFERENCIA=DATA_REFERENCIA,
            QUESTIONARIO_VERSION="1.0.0",
            snapshot_raiz_id=None,
            snapshot_liberado_id=None,
            ultima_interacao_em=agora,
            criado_em=agora,
        )
    )

    estado = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.CALCULANDO)
    insumos_primeiro_calculo = ParametrosDoCalculo(
        fonte_parametros=fonte_parametros,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=caso_id,
        parametros_versao=_PARAMETROS_VERSAO,
        estado_anterior_do_caso=ESTADO_CASO.COLETA_INICIAL,
    )
    snapshot_raiz = executar_calculo(estado, insumos_primeiro_calculo)  # type: ignore[arg-type]
    repositorio_casos.registrar_snapshot_raiz(caso_id, snapshot_raiz.SNAPSHOT_ID)
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.AGUARDANDO_REVISAO)

    caso_liberado_primeira_vez = liberar(
        revisao_id=f"REVISAO_T96_PRIMEIRA_{uuid.uuid4().hex}",
        caso_id=caso_id,
        snapshot=snapshot_raiz,
        autor=email_revisor,
        decidido_em=datetime.now(UTC),
        repositorio_revisoes=repositorio_revisoes,
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
    )
    assert caso_liberado_primeira_vez.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_liberado_primeira_vez.snapshot_liberado_id == snapshot_raiz.SNAPSHOT_ID

    # O caso volta a ACOMPANHAMENTO — pré-condição real de um ciclo de
    # Bloco 11 (mesma transição que `test_bloco11.py::
    # repositorio_casos_arquivo` faz antes de reportar quitação).
    repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.ACOMPANHAMENTO)

    # -----------------------------------------------------------------
    # Monta a aplicação FastAPI REAL com os roteadores de Bloco 11 e de
    # revisão incluídos — nenhum Postgres, nenhum `DATABASE_URL`.
    # -----------------------------------------------------------------
    aplicacao = criar_aplicacao()
    aplicacao.include_router(roteador_bloco11)
    aplicacao.include_router(roteador_revisao)

    # Cadastro/login (app/http/rotas_conta.py) — login real por senha para
    # as duas contas (aluno e revisor); nenhuma rota de cadastro é exercida
    # aqui (já provado por T-95).
    aplicacao.dependency_overrides[obter_cadastro_conta] = lambda: _CadastroContaJaExistente()
    aplicacao.dependency_overrides[obter_repositorio_contas] = lambda: repositorio_contas

    # Isolamento por CASO_ID (app/http/isolamento.py) — usado pelas rotas do
    # aluno (Bloco 11, plano).
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos

    # Guarda de papel de revisor (app/http/isolamento.py::exigir_papel_revisor,
    # T-100) — consulta este MESMO repositório de contas a cada requisição.
    aplicacao.dependency_overrides[obter_repositorio_contas_para_papel] = lambda: repositorio_contas

    # Bloco 11 (app/http/rotas_bloco11.py) — coleção REAL (nenhum filtro:
    # só a pergunta B11.Q01 é exercida, que já existe na coleção completa).
    aplicacao.dependency_overrides[obter_colecao_bloco11] = carregar_registros
    aplicacao.dependency_overrides[obter_repositorio_respostas_b11] = lambda: repositorio_respostas

    # Fila/comparação/decisão de revisão (app/http/rotas_revisao.py).
    aplicacao.dependency_overrides[obter_repositorio_casos_da_fila] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots_da_fila] = (
        lambda: repositorio_snapshots
    )
    aplicacao.dependency_overrides[obter_repositorio_revisoes_da_decisao] = (
        lambda: repositorio_revisoes
    )
    aplicacao.dependency_overrides[obter_repositorio_eventos_da_decisao] = (
        lambda: repositorio_eventos
    )

    # Plano do aluno (app/http/rotas_plano.py).
    aplicacao.dependency_overrides[obter_repositorio_snapshots_plano] = (
        lambda: repositorio_snapshots
    )

    cliente_aluno = TestClient(aplicacao, base_url="https://teste.local")
    cliente_aluno.__enter__()
    cliente_revisor = TestClient(aplicacao, base_url="https://teste.local")
    cliente_revisor.__enter__()

    try:
        resposta_login_aluno = cliente_aluno.post(
            "/api/conta/login", data={"email": email_aluno, "senha": _SENHA_ALUNO}
        )
        assert resposta_login_aluno.status_code == 200

        resposta_login_revisor = cliente_revisor.post(
            "/api/conta/login", data={"email": email_revisor, "senha": _SENHA_REVISOR}
        )
        assert resposta_login_revisor.status_code == 200

        # -----------------------------------------------------------------
        # O aluno vê o PRIMEIRO plano antes de qualquer recálculo — mesma
        # verificação de `test_ciclo_completo.py`. A tela do aluno (Lei
        # nº 3/`plano.html`) nunca expõe `SNAPSHOT_ID` (identificador
        # interno) — a prova de QUAL snapshot está liberado é o dado de
        # backend (`Caso.snapshot_liberado_id`), verificado logo abaixo;
        # aqui confirma-se só que a tela do plano já responde normalmente.
        # -----------------------------------------------------------------
        resposta_plano_antes = cliente_aluno.get(f"/caso/{caso_id}/api/plano")
        assert resposta_plano_antes.status_code == 200
        assert "Sua ordem projetada de quitação" in resposta_plano_antes.text
        caso_antes_do_recalculo = repositorio_casos.buscar(caso_id)
        assert caso_antes_do_recalculo is not None
        assert caso_antes_do_recalculo.snapshot_liberado_id == snapshot_raiz.SNAPSHOT_ID

        # -----------------------------------------------------------------
        # 2. REPORTAR quitação real: B11.Q01 = "Sim" via rota HTTP real
        #    (T-82) — a mesma especialização de `POST /caso/{CASO_ID}/
        #    resposta` que `test_bloco11.py` já exercita.
        # -----------------------------------------------------------------
        resposta_bloco11 = cliente_aluno.post(
            f"/caso/{caso_id}/bloco-11/resposta",
            data={"ID_PERGUNTA": "B11.Q01", "item_id": _DIVIDA_ID, "valor": "QUITADA"},
        )
        assert resposta_bloco11.status_code == 200
        corpo_bloco11 = resposta_bloco11.json()
        assert corpo_bloco11["evento_recalculo"] == "QUITACAO_CONFIRMADA"

        # -----------------------------------------------------------------
        # 3. RECALCULAR: o "consumidor" (esta suíte, mesmo padrão de T-88)
        #    lê o evento devolvido pela rota HTTP e aciona
        #    `processar_resposta_bloco_11` (T-87), que dispara
        #    `disparar_recalculo` (T-86) — o MESMO executor do Bloco 6.
        # -----------------------------------------------------------------
        caso_apos_resposta = repositorio_casos.buscar(caso_id)
        assert caso_apos_resposta is not None
        estado_para_recalculo = _montar_estado_do_caso(caso_completo(DIVIDA_ID=_DIVIDA_ID))

        snapshot_recalculado = processar_resposta_bloco_11(
            id_pergunta="B11.Q01",
            variavel_gravada="STATUS_QUITACAO_REAL",
            valor_interno="QUITADA",
            caso=caso_apos_resposta,
            estado=estado_para_recalculo,  # type: ignore[arg-type]
            fonte_parametros=fonte_parametros,
            repositorio_snapshots=repositorio_snapshots,
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            parametros_versao=_PARAMETROS_VERSAO,
            motivo=corpo_bloco11["evento_recalculo"],
        )
        assert snapshot_recalculado is not None
        assert snapshot_recalculado.versao == snapshot_raiz.versao + 1
        assert snapshot_recalculado.snapshot_anterior_id == snapshot_raiz.SNAPSHOT_ID

        # `disparar_recalculo` deixa o caso em CALCULANDO->AGUARDANDO_REVISAO
        # (mesma transição de sucesso do Bloco 6, feita pelo chamador em
        # produção — mesmo precedente de `test_bloco11.py`).
        from app.casos.maquina import transicionar

        transicionar(ESTADO_CASO.CALCULANDO, ESTADO_CASO.AGUARDANDO_REVISAO)
        repositorio_casos.transicionar_estado(caso_id, ESTADO_CASO.AGUARDANDO_REVISAO)

        # -----------------------------------------------------------------
        # AC-26 — "o snapshot de recálculo aparece na fila ANTES de
        # qualquer acesso do aluno": o aluno ainda não acessou nada desde o
        # recálculo (a única leitura dele foi ANTES, no passo acima). A
        # fila é consultada agora, pela rota HTTP real, sessão de revisor.
        # -----------------------------------------------------------------
        resposta_fila = cliente_revisor.get("/api/revisao/fila")
        assert resposta_fila.status_code == 200
        assert caso_id in resposta_fila.text
        assert snapshot_recalculado.SNAPSHOT_ID in resposta_fila.text

        # Reforço negativo de AC-26: uma sessão de ALUNO comum (sem
        # e_revisor) nunca alcança a fila — 403, nunca a lista de casos.
        resposta_fila_como_aluno = cliente_aluno.get("/api/revisao/fila")
        assert resposta_fila_como_aluno.status_code == 403

        # -----------------------------------------------------------------
        # 5. AC-29 — plano e estado_inputs na MESMA sessão do revisor, sem
        #    navegação para outro caso: GET /revisao/caso/{CASO_ID} real.
        # -----------------------------------------------------------------
        resposta_comparacao = cliente_revisor.get(f"/api/revisao/caso/{caso_id}")
        assert resposta_comparacao.status_code == 200
        html_comparacao = resposta_comparacao.text
        assert snapshot_recalculado.SNAPSHOT_ID in html_comparacao
        assert snapshot_recalculado.ENGINE_VERSION in html_comparacao
        assert snapshot_recalculado.PARAMETROS_VERSION in html_comparacao
        # O plano exibido é o do snapshot RECALCULADO (o mais recente da
        # cadeia) — não mais o primeiro snapshot liberado.
        for posicao in snapshot_recalculado.ORDEM_QUITACAO:
            assert posicao.DIVIDA_ID in html_comparacao
        # `AC-29`: os estado_inputs vêm na MESMA resposta que o plano — antes
        # era o cabeçalho da seção no HTML, agora é o campo próprio do JSON.
        assert resposta_comparacao.json()["estado_inputs"]["campos"]

        # -----------------------------------------------------------------
        # 6. Segunda LIBERAÇÃO, via rota HTTP real (T-71) — nunca chamando
        #    `app.revisao.fila.liberar` diretamente para esta decisão.
        # -----------------------------------------------------------------
        resposta_decisao = cliente_revisor.post(
            f"/revisao/caso/{caso_id}/decisao",
            data={"decisao": "LIBERAR", "observacao": "recalculo t96"},
        )
        assert resposta_decisao.status_code == 200

        # -----------------------------------------------------------------
        # 7. Depois da liberação: o aluno vê o plano NOVO, e o anterior
        #    permanece recuperável (histórico append-only, nunca apagado).
        #    A tela do aluno nunca expõe `SNAPSHOT_ID` (Lei nº 3) — "o
        #    aluno vê o plano novo" é provado pelo dado de backend que a
        #    própria rota do aluno lê para decidir o que renderizar
        #    (`Caso.snapshot_liberado_id`, `app/http/rotas_plano.py`),
        #    ANTES e DEPOIS da segunda liberação: mudou de `snapshot_raiz`
        #    para `snapshot_recalculado`, e a tela responde normalmente
        #    (200, mesmo título canônico) nos dois momentos.
        # -----------------------------------------------------------------
        caso_final = repositorio_casos.buscar(caso_id)
        assert caso_final is not None
        assert caso_final.estado is ESTADO_CASO.PLANO_LIBERADO
        assert caso_final.snapshot_liberado_id == snapshot_recalculado.SNAPSHOT_ID
        assert caso_final.snapshot_liberado_id != caso_antes_do_recalculo.snapshot_liberado_id

        resposta_plano_depois = cliente_aluno.get(f"/caso/{caso_id}/api/plano")
        assert resposta_plano_depois.status_code == 200
        assert "Sua ordem projetada de quitação" in resposta_plano_depois.text
        for posicao in snapshot_recalculado.ORDEM_QUITACAO:
            assert posicao.DIVIDA_ID in resposta_plano_depois.text

        historico_final = repositorio_snapshots.historico(snapshot_raiz.SNAPSHOT_ID)
        assert len(historico_final) == 2
        assert historico_final[0].SNAPSHOT_ID == snapshot_raiz.SNAPSHOT_ID
        assert historico_final[1].SNAPSHOT_ID == snapshot_recalculado.SNAPSHOT_ID

        # O revisor continua conseguindo ver o snapshot anterior pela
        # mesma leitura de histórico — recuperável, nunca sobrescrito.
        assert repositorio_snapshots.obter(snapshot_raiz.SNAPSHOT_ID).SNAPSHOT_ID == (
            snapshot_raiz.SNAPSHOT_ID
        )
    finally:
        cliente_revisor.__exit__(None, None, None)
        cliente_aluno.__exit__(None, None, None)
