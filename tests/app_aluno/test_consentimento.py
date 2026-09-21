"""Cadastro, consentimento e recusa de gravação sem consentimento, de ponta
a ponta — `RF-02`, `RF-30`, `AC-39` (T-37).

**O que já está coberto por T-36, e por que este arquivo não duplica.**
`tests/app_aluno/test_guarda_consentimento_resposta.py` e `tests/app_aluno/
integracao/test_guarda_consentimento_resposta.py` (T-36) já provam, de forma
exaustiva:

1. `AC-39` — caso em `CADASTRADO`/`CONSENTIMENTO_REGISTRADO` recusa
   `RepositorioRespostasSupabase.gravar` e nenhum `INSERT` chega a ser
   executado: com dublê de cursor (sem banco) E contra Postgres real (caso
   criado por fixture SQL direta).
2. a guarda é uma transição nomeada da máquina, verificável sem HTTP.
3. `COLETA_INICIAL` aceita a gravação normalmente (contraprova).
4. `CASO_ID` inexistente nunca é tratado como estado liberado por omissão.

`tests/app_aluno/test_rotas_consentimento.py` (T-36) já prova que a rota
`POST /caso/{CASO_ID}/consentimento` registra o aceite (com autor, versão do
texto e data) e dispara a transição num único caminho — com dublês de
repositório em memória, sessão aberta por `iniciar_sessao_conta` real.

O que falta, e que este arquivo acrescenta: o ÂNGULO FIM-A-FIM por HTTP que
nenhum dos dois cobre — um caso nascido de um cadastro REAL (`POST /conta/
cadastro`, T-30, contra Postgres real, não uma fixture SQL nem um dublê em
memória), a tentativa de gravação recusada SOBRE ESSE MESMO caso, o
consentimento registrado pela rota REAL (T-36) sobre ele, e só então a
gravação aceita — tudo com o MESMO `CASO_ID` produzido pelo fluxo HTTP de
produção, do início ao fim. `RepositorioRespostasSupabase.gravar` é chamado
diretamente (não existe rota de gravar resposta: isso é `T-42`, tarefa
futura) — mas agora no contexto de um caso criado pelo fluxo HTTP real, não
por fixture direta de banco.

`@pytest.mark.requer_banco`: exige Postgres real com as migrações `001` e
`002` aplicadas — pulado com mensagem explícita sem `DATABASE_URL` (hook de
`tests/app_aluno/conftest.py`).

Cobertura dos quatro critérios de aceite desta tarefa, e origem de cada um:

- `AC-39` (nenhuma linha em `respostas` após a tentativa sem consentimento):
  reafirmado aqui fim-a-fim (`test_ac39_...`); provado exaustivamente por
  T-36 nos dois arquivos citados acima.
- Após o registro de consentimento, a mesma gravação é aceita: provado aqui
  fim-a-fim (`test_ac39_...`, segunda metade); T-36 prova o equivalente
  contra `COLETA_INICIAL` fabricado, não alcançado por cadastro real.
- O registro de consentimento guarda autor (o caso), versão do texto e
  data: provado aqui contra Postgres real, lendo de volta
  `RepositorioConsentimentosSupabase.listar_do_caso` (T-36 prova o
  equivalente com um dublê em memória, em `test_rotas_consentimento.py`).
- O teste cita `AC-39` no nome: `test_ac39_...` abaixo.

REGRAS: `RF-02`, `RF-30`, `AC-39`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, ErroConsentimentoNaoRegistrado
from app.consentimento.registro import TextoConsentimento
from app.http.aplicacao import criar_aplicacao
from collection.respostas import Resposta
from persistencia.app_aluno.casos import RepositorioCasosSupabase
from persistencia.app_aluno.consentimentos import RepositorioConsentimentosSupabase
from persistencia.app_aluno.respostas import RepositorioRespostasSupabase
from persistencia.supabase.conexao import obter_database_url

pytestmark = pytest.mark.requer_banco

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"


@pytest.fixture
def diretorio_textos_fabricado(tmp_path: Path) -> Path:
    """Um `.yaml` de texto de consentimento FABRICADO (não é a redação real
    de `PEND-01`) — mesmo papel da fixture homônima de
    `test_rotas_consentimento.py`, só para exercitar o mecanismo de carga."""
    (tmp_path / "v1.yaml").write_text(
        "QUESTIONARIO_VERSION: 'T37-1.0.0'\ntitulo: fabricado\ncorpo: fabricado\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def cliente_http_real(
    monkeypatch: pytest.MonkeyPatch, diretorio_textos_fabricado: Path
) -> TestClient:
    """`TestClient` sobre `criar_aplicacao()` SEM nenhum `dependency_
    overrides`: cadastro e consentimento correm pelo caminho de produção
    (`persistencia.app_aluno.cadastro.cadastrar_conta_e_caso`,
    `RepositorioConsentimentosSupabase`, `RepositorioCasosSupabase`) contra o
    Postgres de `DATABASE_URL` — nenhum dublê no caminho HTTP."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setattr(
        "app.http.rotas_consentimento.carregar_texto_vigente",
        lambda diretorio=None: _carregar_texto_fabricado(diretorio_textos_fabricado),
    )
    aplicacao = criar_aplicacao()
    return TestClient(aplicacao, base_url="https://teste.local")


def _carregar_texto_fabricado(diretorio: Path) -> TextoConsentimento:
    from app.consentimento.registro import carregar_texto_vigente as original

    return original(diretorio)


def _total_de_respostas(caso_id: str) -> int:
    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            'SELECT count(*) FROM app_aluno.respostas WHERE "CASO_ID" = %s',
            (caso_id,),
        )
        (total,) = cursor.fetchone()  # type: ignore[misc]
        return int(total)


def _resposta_de_teste(caso_id: str) -> Resposta:
    return Resposta(
        CASO_ID=caso_id,
        ID_PERGUNTA="B1.01",
        item_id=None,
        valor="sim",
        QUESTIONARIO_VERSION="T37-1.0.0",
        respondida_em=datetime.now(UTC),
    )


def test_ac39_cadastro_real_recusa_gravacao_e_apos_consentimento_real_a_mesma_gravacao_e_aceita(
    cliente_http_real: TestClient,
) -> None:
    """`AC-39`, fim-a-fim: (1) cadastro REAL via `POST /conta/cadastro` cria
    conta+caso em `CADASTRADO`, ambos persistidos de verdade; (2) tentativa
    de gravar resposta sobre ESSE `CASO_ID` é recusada, e `app_aluno.
    respostas` continua com zero linhas; (3) `POST /caso/{CASO_ID}/
    consentimento` (a mesma rota real de T-36) registra o aceite e
    transiciona o caso para `CONSENTIMENTO_REGISTRADO`; (3b) como a rota de
    consentimento só dispara `registra_consentimento` (T-36 prova, em
    `test_caso_em_consentimento_registrado_tambem_recusa_gravacao`, que
    `CONSENTIMENTO_REGISTRADO` sozinho AINDA recusa gravação — a transição
    seguinte, `inicia_coleta` para `COLETA_INICIAL`, ainda não tem rota HTTP
    própria, `T-42`), este teste dispara `inicia_coleta` chamando o
    repositório real diretamente, mesmo ângulo de "chamar o repositório sem
    rota" que T-36 já usa para a gravação; (4) a MESMA gravação de resposta,
    repetida, agora é aceita."""
    email = f"t37-{uuid.uuid4().hex}@teste.invalido"
    resposta_cadastro = cliente_http_real.post(
        "/api/conta/cadastro", data={"email": email, "senha": "senha-de-teste-t37"}
    )
    assert resposta_cadastro.status_code == 201  # `201 Created` (T-144)

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute('SELECT "CASO_ID" FROM app_aluno.casos WHERE conta_id = ('
                        "SELECT conta_id FROM app_aluno.contas WHERE email = %s)", (email,))
        linha = cursor.fetchone()
    assert linha is not None, "cadastro real deveria ter criado um caso para a conta"
    (caso_id,) = linha

    repositorio_respostas = RepositorioRespostasSupabase()

    # (2) — AC-39: caso recém-cadastrado está em CADASTRADO, sem consentimento.
    with pytest.raises(ErroConsentimentoNaoRegistrado):
        repositorio_respostas.gravar(_resposta_de_teste(caso_id))
    assert _total_de_respostas(caso_id) == 0

    # (3) — a MESMA rota real de T-36 registra o consentimento sobre o caso
    # nascido do cadastro real.
    resposta_consentimento = cliente_http_real.post(
        f"/caso/{caso_id}/consentimento", data={"aceite": "on"}
    )
    assert resposta_consentimento.status_code == 200

    # (3b) — inicia_coleta ainda não tem rota HTTP (T-42, futura): disparada
    # diretamente sobre o repositório real, mesmo ângulo já usado por T-36
    # para a gravação de resposta.
    RepositorioCasosSupabase().transicionar_estado(caso_id, ESTADO_CASO.COLETA_INICIAL)

    # (4) — a mesma gravação, agora aceita.
    repositorio_respostas.gravar(_resposta_de_teste(caso_id))
    assert _total_de_respostas(caso_id) == 1


def test_registro_de_consentimento_real_guarda_autor_versao_e_data(
    cliente_http_real: TestClient,
) -> None:
    """O registro gravado pela rota real carrega o autor (`CASO_ID`), a
    versão do texto vigente e a data do aceite — lido de volta do Postgres
    real via `RepositorioConsentimentosSupabase.listar_do_caso`."""
    email = f"t37-{uuid.uuid4().hex}@teste.invalido"
    cliente_http_real.post(
        "/api/conta/cadastro", data={"email": email, "senha": "senha-de-teste-t37"}
    )

    with psycopg.connect(obter_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            'SELECT "CASO_ID" FROM app_aluno.casos WHERE conta_id = ('
            "SELECT conta_id FROM app_aluno.contas WHERE email = %s)",
            (email,),
        )
        (caso_id,) = cursor.fetchone()  # type: ignore[misc]

    antes = datetime.now(UTC)
    resposta_consentimento = cliente_http_real.post(
        f"/caso/{caso_id}/consentimento", data={"aceite": "on"}
    )
    assert resposta_consentimento.status_code == 200
    depois = datetime.now(UTC)

    registros = RepositorioConsentimentosSupabase().listar_do_caso(caso_id)
    assert len(registros) == 1
    registro = registros[0]
    assert registro.CASO_ID == caso_id  # autor: o caso
    assert registro.versao_texto == "T37-1.0.0"  # versão do texto vigente
    assert registro.aceite is True
    assert antes <= registro.aceito_em <= depois  # data do aceite
