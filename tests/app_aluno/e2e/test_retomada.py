"""`US-01` ponta a ponta: retomada multissessão e persistência a cada
resposta — `RF-10`, `AC-01`, `AC-02` (T-46).

**O que já está coberto por outras tarefas, e por que este arquivo não
duplica.** `tests/app_aluno/test_retomada_progresso.py` (T-45) já prova,
exaustivamente e com os 245 registros REAIS, o comportamento PURO de
`app/casos/progresso.py::proxima_pergunta_nao_respondida` — ordem dos blocos,
escopo de repetição, condição que virou falsa depois de respondida. Este
arquivo não repete aquelas provas unitárias: ele prova o CENÁRIO FIM-A-FIM que
T-45 documenta como fora do seu escopo — dois `TestClient` diferentes
(simulando dois dispositivos/sessões), cadastro real (`app/http/
rotas_conta.py`, T-30), consentimento real (`app/http/rotas_consentimento.py`,
T-36) e respostas REAIS gravadas via `POST /caso/{CASO_ID}/resposta`
(`app/http/rotas_coleta.py`, T-42/T-44).

**Fronteira explícita desta tarefa (documentada também no plano de
implementação e na tarefa).** NÃO existe rota GET de "retomar"/"próxima
pergunta" ainda — essa costura (`app/http/renderizacao.py` já documenta como
trabalho de uma tarefa de orquestração futura, consumindo `proxima_pergunta_
nao_respondida` junto de `montar_contexto_pergunta`) está fora do escopo
declarado de T-45 e, por consequência, fora do escopo de T-46. Este teste
prova duas coisas DISTINTAS, cada uma pelo caminho que de fato existe hoje:

  1. **Persistência real através de duas conexões/clientes distintos**: as
     respostas gravadas pelo cliente/sessão 1 são lidas de volta do banco
     (`RepositorioRespostasSupabase.listar_do_caso`, T-22) por uma sessão/
     cliente 2 completamente novo (novo `TestClient`, novo login) — nenhum
     estado em memória é compartilhado entre os dois.
  2. **Retomada no ponto certo**: as respostas lidas do banco pelo cliente 2
     são passadas para `proxima_pergunta_nao_respondida` (chamada DIRETA à
     função, não por uma rota HTTP — a rota não existe) para confirmar que o
     algoritmo aponta exatamente a próxima pergunta esperada, e não uma já
     respondida.

Isso é exatamente o que o critério de aceite pede: "retomada multissessão e
persistência a cada resposta", provadas com dado real de ponta a ponta, sem
inventar uma rota GET que não faz parte de nenhuma tarefa concluída.

`@pytest.mark.requer_banco`: exige Postgres real com as migrações `001` e
`002` aplicadas — pulado com mensagem explícita sem `DATABASE_URL` (hook de
`tests/app_aluno/conftest.py`).

Cobertura dos quatro critérios de aceite desta tarefa:

- `AC-01` (cliente novo, sessão nova, todas as respostas presentes e retomada
  no ponto correto): `test_ac01_...` abaixo.
- `AC-02` (matar o cliente logo após a confirmação da resposta não perde a
  resposta): `test_ac02_...` abaixo — mesmo ângulo de `tests/app_aluno/e2e/
  test_rota_resposta.py::test_ac02_...` (T-42), reproduzido aqui no cenário
  MULTISSESSÃO completo de `US-01` (cadastro → consentimento → responder →
  "matar" o cliente → novo cliente → retomada), que é o que esta tarefa pede.
- Nenhum campo já respondido é reapresentado como pendente: reafirmado em
  `test_ac01_...` (a retomada nunca aponta `PACTO`/`NOVA_DIVIDA_PREVISTA`,
  já respondidos) e em `test_nenhum_campo_ja_respondido_e_reapresentado_
  apos_responder_a_pendencia_seguinte`.
- Os testes citam `AC-01`/`AC-02` nos nomes: `test_ac01_...`/`test_ac02_...`.

REGRAS: `RF-10`, `AC-01`, `AC-02`
"""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import PendenciaObrigatoria, proxima_pergunta_nao_respondida
from app.consentimento.registro import TextoConsentimento
from app.http.aplicacao import criar_aplicacao
from collection.carga import carregar_registros
from collection.respostas import RespostasCaso
from persistencia.app_aluno.casos import RepositorioCasosSupabase
from persistencia.app_aluno.respostas import RepositorioRespostasSupabase
from persistencia.supabase.conexao import obter_database_url

pytestmark = pytest.mark.requer_banco

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_SENHA_TESTE = "senha-de-teste-t46"


@pytest.fixture
def diretorio_textos_fabricado(tmp_path: Path) -> Path:
    """Mesmo papel da fixture homônima de `test_consentimento.py`/
    `test_rota_resposta.py` (T-37/T-42): um `.yaml` de texto de consentimento
    FABRICADO só para exercitar o mecanismo de carga, nunca a redação real
    de `PEND-01`."""
    (tmp_path / "v1.yaml").write_text(
        "QUESTIONARIO_VERSION: 'T46-1.0.0'\ntitulo: fabricado\ncorpo: fabricado\n",
        encoding="utf-8",
    )
    return tmp_path


def _carregar_texto_fabricado(diretorio: Path) -> TextoConsentimento:
    from app.consentimento.registro import carregar_texto_vigente as original

    return original(diretorio)


@pytest.fixture
def aplicacao_real(
    monkeypatch: pytest.MonkeyPatch, diretorio_textos_fabricado: Path
) -> FastAPI:
    """A `FastAPI` de produção, sem `dependency_overrides` — cadastro, login
    e consentimento correm pelo caminho de produção contra o Postgres de
    `DATABASE_URL`, mesmo padrão de `test_rota_resposta.py::aplicacao_real`
    (T-42). Exposta separada do `TestClient` porque este teste precisa
    instanciar DOIS `TestClient` distintos sobre a MESMA aplicação — dois
    dispositivos apontando para o mesmo servidor, nunca dois servidores."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setattr(
        "app.http.rotas_consentimento.carregar_texto_vigente",
        lambda diretorio=None: _carregar_texto_fabricado(diretorio_textos_fabricado),
    )
    return criar_aplicacao()


def _database_url() -> str:
    return obter_database_url()


def _caso_id_da_conta(email: str) -> str:
    with psycopg.connect(_database_url()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SET search_path TO app_aluno, public")
        cursor.execute(
            'SELECT "CASO_ID" FROM app_aluno.casos WHERE conta_id = ('
            "SELECT conta_id FROM app_aluno.contas WHERE email = %s)",
            (email,),
        )
        linha = cursor.fetchone()
    assert linha is not None, "cadastro real deveria ter criado um caso para a conta"
    (caso_id,) = linha
    return str(caso_id)


def _cadastrar_consentir_e_iniciar_coleta(aplicacao_real: FastAPI, email: str) -> str:
    """Passos comuns de `US-01` que antecedem a coleta propriamente dita —
    reaproveita o MESMO caminho real de `test_rota_resposta.py::
    _caso_pronto_para_coleta` (T-42), mas devolve só o `CASO_ID`: o
    `TestClient` que fez o cadastro é "descartado" pelo chamador logo em
    seguida, para simular o fim da primeira sessão (ver
    `dispositivo_1_cadastra_consente_e_responde`, abaixo)."""
    cliente_do_cadastro = TestClient(aplicacao_real, base_url="https://teste.local")
    resposta_cadastro = cliente_do_cadastro.post(
        "/api/conta/cadastro", data={"email": email, "senha": _SENHA_TESTE}
    )
    assert resposta_cadastro.status_code == 201  # `201 Created` (T-144)

    caso_id = _caso_id_da_conta(email)

    resposta_consentimento = cliente_do_cadastro.post(
        f"/caso/{caso_id}/consentimento", data={"aceite": "on"}
    )
    assert resposta_consentimento.status_code == 200

    # `inicia_coleta` ainda não tem rota HTTP própria (T-42/T-45 documentam
    # essa costura como trabalho futuro) — disparada diretamente sobre o
    # repositório real, mesmo ângulo já usado por T-37/T-42.
    RepositorioCasosSupabase().transicionar_estado(caso_id, ESTADO_CASO.COLETA_INICIAL)

    return caso_id


# ---------------------------------------------------------------------------
# AC-01 — cliente novo, sessão nova, todas as respostas presentes e retomada
# no ponto correto.
# ---------------------------------------------------------------------------


def test_ac01_cliente_novo_sessao_nova_todas_as_respostas_presentes_e_retomada_no_ponto_certo(
    aplicacao_real: FastAPI,
) -> None:
    """Dispositivo 1: cadastro, consentimento e duas respostas reais
    (`B1.01=PACTO=ESTABELECIDO`, `B1.02=NOVA_DIVIDA_PREVISTA=NAO`) — ambas
    `OBR`, sempre abertas, sem escopo de repetição, exatamente os registros
    reais usados também por `tests/app_aluno/e2e/test_rota_resposta.py`. O
    `TestClient` do dispositivo 1 NUNCA é reutilizado depois disso — é
    literalmente "morto" (sai de escopo), simulando o fim daquela sessão.

    Dispositivo 2: um `TestClient` NOVO (nenhum cookie compartilhado com o
    dispositivo 1), login REAL (`POST /conta/login`, T-30) com a mesma conta.
    As respostas são lidas do banco por uma instância NOVA de
    `RepositorioRespostasSupabase` (nenhum estado em memória do dispositivo
    1 é reaproveitado) e devem conter as duas gravadas. A retomada, chamada
    DIRETAMENTE sobre `proxima_pergunta_nao_respondida` (não existe rota GET
    de retomada — ver nota do módulo) com essas respostas, aponta `B1.06`
    (`OBRIGACAO_FUTURA_INEVITAVEL`, `OBR`, sempre aberta, a próxima pergunta
    real na ordem de carga que ainda está em branco) — nunca `B1.01`/`B1.02`,
    já respondidas."""
    email = f"t46-ac01-{uuid.uuid4().hex}@teste.invalido"
    caso_id = _cadastrar_consentir_e_iniciar_coleta(aplicacao_real, email)

    # --- Dispositivo 1: responde duas perguntas reais e "morre" -----------
    dispositivo_1 = TestClient(aplicacao_real, base_url="https://teste.local")
    resposta_login_1 = dispositivo_1.post(
        "/api/conta/login", data={"email": email, "senha": _SENHA_TESTE}
    )
    assert resposta_login_1.status_code == 200

    resposta_pacto = dispositivo_1.post(
        f"/caso/{caso_id}/resposta", data={"ID_PERGUNTA": "B1.01", "valor": "ESTABELECIDO"}
    )
    assert resposta_pacto.status_code == 200
    resposta_nova_divida = dispositivo_1.post(
        f"/caso/{caso_id}/resposta", data={"ID_PERGUNTA": "B1.02", "valor": "NAO"}
    )
    assert resposta_nova_divida.status_code == 200
    del dispositivo_1  # fim da sessão 1 — nunca mais usado neste teste.

    # --- Dispositivo 2: cliente novo, sessão nova, login real --------------
    dispositivo_2 = TestClient(aplicacao_real, base_url="https://teste.local")
    resposta_login_2 = dispositivo_2.post(
        "/api/conta/login", data={"email": email, "senha": _SENHA_TESTE}
    )
    assert resposta_login_2.status_code == 200

    # Todas as respostas presentes — leitura por instância NOVA do
    # repositório, sem reaproveitar nada do dispositivo 1.
    respostas_do_banco = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    valores = {r.ID_PERGUNTA: r.valor for r in respostas_do_banco}
    assert valores.get("PACTO") == "ESTABELECIDO"
    assert valores.get("NOVA_DIVIDA_PREVISTA") == "NAO"

    # Retomada no ponto correto — chamada direta à função pura (T-45); não
    # existe rota GET de retomada ainda (ver nota do módulo).
    registros = carregar_registros().registros
    proxima = proxima_pergunta_nao_respondida(
        registros, RespostasCaso(respostas=respostas_do_banco)
    )

    assert proxima == PendenciaObrigatoria(ID="B1.06", item_id=None), (
        "AC-01: com PACTO/NOVA_DIVIDA_PREVISTA respondidos por outra sessão, "
        f"a retomada deveria apontar B1.06; obteve {proxima!r}"
    )
    # Nenhum campo já respondido é reapresentado como pendente.
    assert proxima.ID not in ("B1.01", "B1.02")


def test_ac01_apos_responder_a_pendencia_seguinte_nenhum_campo_antigo_e_reapresentado(
    aplicacao_real: FastAPI,
) -> None:
    """Continuação do cenário acima: o dispositivo 2 grava a resposta que a
    retomada apontou (`B1.06`) — a retomada seguinte, computada de novo com
    o snapshot atualizado do banco, avança para além de `B1.06` e continua
    sem jamais reapresentar `PACTO`, `NOVA_DIVIDA_PREVISTA` ou
    `OBRIGACAO_FUTURA_INEVITAVEL`."""
    email = f"t46-ac01b-{uuid.uuid4().hex}@teste.invalido"
    caso_id = _cadastrar_consentir_e_iniciar_coleta(aplicacao_real, email)

    dispositivo_1 = TestClient(aplicacao_real, base_url="https://teste.local")
    dispositivo_1.post("/api/conta/login", data={"email": email, "senha": _SENHA_TESTE})
    dispositivo_1.post(
        f"/caso/{caso_id}/resposta", data={"ID_PERGUNTA": "B1.01", "valor": "ESTABELECIDO"}
    )
    dispositivo_1.post(
        f"/caso/{caso_id}/resposta", data={"ID_PERGUNTA": "B1.02", "valor": "NAO"}
    )
    del dispositivo_1

    dispositivo_2 = TestClient(aplicacao_real, base_url="https://teste.local")
    dispositivo_2.post("/api/conta/login", data={"email": email, "senha": _SENHA_TESTE})
    resposta_obrigacao = dispositivo_2.post(
        f"/caso/{caso_id}/resposta",
        data={"ID_PERGUNTA": "B1.06", "valor": "NAO"},
    )
    assert resposta_obrigacao.status_code == 200
    del dispositivo_2

    # Terceiro dispositivo, terceira sessão — a mesma disciplina multissessão.
    dispositivo_3 = TestClient(aplicacao_real, base_url="https://teste.local")
    dispositivo_3.post("/api/conta/login", data={"email": email, "senha": _SENHA_TESTE})

    registros = carregar_registros().registros
    respostas_do_banco = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    proxima = proxima_pergunta_nao_respondida(
        registros, RespostasCaso(respostas=respostas_do_banco)
    )

    assert proxima is not None
    assert proxima.ID not in ("B1.01", "B1.02", "B1.06"), (
        "nenhum campo já respondido pode ser reapresentado como pendente "
        f"pela retomada; obteve {proxima!r}"
    )


# ---------------------------------------------------------------------------
# AC-02 — matar o cliente logo após a confirmação da resposta não perde a
# resposta.
# ---------------------------------------------------------------------------


def test_ac02_matar_o_cliente_apos_a_confirmacao_da_resposta_nao_perde_a_resposta(
    aplicacao_real: FastAPI,
) -> None:
    """`US-01` completo: cadastro real, consentimento real, uma resposta
    real via `POST /caso/{CASO_ID}/resposta` — e o `TestClient` que a enviou
    é imediatamente descartado (`del`) assim que a resposta HTTP `200`
    chega, sem nenhuma chamada adicional. Uma leitura NOVA, por um
    repositório novo (nenhum estado compartilhado com o cliente morto),
    confirma que a resposta já está no banco: a garantia de `AC-02` (a
    gravação já foi commitada ANTES do `return` da rota, `app/http/
    rotas_coleta.py`) sobrevive ao cliente ser "morto" logo em seguida."""
    email = f"t46-ac02-{uuid.uuid4().hex}@teste.invalido"
    caso_id = _cadastrar_consentir_e_iniciar_coleta(aplicacao_real, email)

    cliente = TestClient(aplicacao_real, base_url="https://teste.local")
    cliente.post("/api/conta/login", data={"email": email, "senha": _SENHA_TESTE})

    resposta_http = cliente.post(
        f"/caso/{caso_id}/resposta", data={"ID_PERGUNTA": "B1.01", "valor": "ESTABELECIDO"}
    )
    assert resposta_http.status_code == 200

    # "Mata" o cliente imediatamente após a confirmação — nenhuma chamada
    # adicional ocorre através dele a partir daqui.
    del cliente

    leitura_apos_matar_o_cliente = RepositorioRespostasSupabase().listar_do_caso(caso_id)
    valores = {r.ID_PERGUNTA: r.valor for r in leitura_apos_matar_o_cliente}
    assert valores.get("PACTO") == "ESTABELECIDO", (
        "AC-02: matar o cliente logo após a confirmação HTTP não deveria "
        f"perder a resposta; valores gravados: {valores}"
    )
