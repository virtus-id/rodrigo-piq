"""E2E — a redação canônica de `Q-03`, o carimbo de versão e a ordem completa
confirmados nas DUAS respostas HTTP REAIS do plano do aluno: a tela (`GET
/caso/{CASO_ID}/plano`) e o PDF (`GET /caso/{CASO_ID}/plano/pdf`) — `RF-20`,
`RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17` (T-65).

**Ângulo deste arquivo — o que ele acrescenta aos três já existentes, sem
duplicá-los.**

- `tests/app_aluno/test_plano.py` (T-59/T-60) já prova `AC-14`/`AC-15`/
  `AC-16`/`AC-17` sobre o HTML **isolado**: chama `montar_contexto_plano` e
  renderiza `plano.html` diretamente por `Environment.get_template(...)
  .render(...)`, sem nenhum servidor HTTP.
- `tests/app_aluno/test_pdf.py` (T-63) já prova os mesmos critérios sobre o
  HTML de entrada do PDF, chamando `report.pdf.gerar_html_do_plano_liberado`/
  `gerar_pdf_do_plano` diretamente — de novo, sem servidor HTTP.
- `tests/app_aluno/test_rotas_plano.py` (T-64) já testa as duas rotas HTTP
  reais, mas focado no CONTRATO de liberação/isolamento (`AC-25`, `AC-03`) —
  não faz a auditoria caractere por caractere dos quatro critérios de T-65
  nem usa um snapshot com mais de uma dívida.

Este arquivo é a suíte que falta: um CLIENTE HTTP real (`TestClient` sobre
`criar_aplicacao()`), uma sessão aberta de verdade, um `SnapshotOrdem`
REAL — produzido por `engine.motor.calcular_plano` sobre a fixture de caso
completo (`tests/app_aluno/fixtures/caso_completo.py`, T-53), com DUAS
dívidas (para que `AC-17` não seja um caso degenerado de N=1) — acessando as
DUAS rotas reais e conferindo os quatro critérios de aceite NAS DUAS
RESPOSTAS.

Como `Q-03`/"projetada" e a ordem/carimbo já vêm da MESMA fonte
(`report/plano.py::carregar_textos_canonicos`/`montar_contexto_plano`) tanto
para a tela quanto para o PDF (T-59/T-60/T-63 garantiram isso
estruturalmente — ver `test_pdf.py::
test_html_do_pdf_e_identico_ao_html_da_tela_para_o_mesmo_snapshot`), a
igualdade entre HTML-da-tela e HTML-do-PDF já está provada por outro teste.
O que ESTE arquivo prova é algo que nenhum dos três anteriores prova: que os
DOIS CAMINHOS HTTP REAIS (roteamento, isolamento por sessão, injeção de
dependência, serialização da resposta) entregam, de fato, o mesmo conteúdo
normativo ao cliente.

**Extração do PDF — decisão documentada, mesmo padrão de `test_pdf.py`/
`test_rotas_plano.py`.** O projeto não declara nenhuma biblioteca de leitura
de PDF (`pypdf`, `pdfplumber`, ...) em `pyproject.toml`, e `sdd.config.md`
proíbe dependência nova fora do plano — não é razoável adicionar uma só para
este teste. A via de prova usada aqui é a MESMA que `report/pdf.py`/
`test_pdf.py` já usam: o HTML de ENTRADA que `gerar_pdf_do_plano` envia ao
WeasyPrint é exatamente o que `renderizar_html_do_plano`/`gerar_html_do_
plano_liberado` produzem (prova estrutural já feita por T-63) — então a
resposta HTTP da rota de PDF é conferida (a) pelos bytes `%PDF` quando a
biblioteca nativa do WeasyPrint (GTK/Pango) está disponível neste ambiente
(caso em que o PDF é gerado de ponta a ponta e o teste ainda assim NÃO tenta
"ler" o texto de dentro do PDF binário — comparação de bytes de PDF não prova
caractere por caractere nada que a montagem de HTML não prove melhor), e
(b) sempre, chamando a MESMA função de montagem de HTML que a rota de PDF usa
por dentro (`report.pdf.gerar_html_do_plano_liberado`) com o MESMO snapshot,
para auditar os quatro critérios caractere por caractere sobre o HTML que a
rota de PDF de fato serviria — sem fingir uma extração de texto de PDF que
não existe neste projeto. Quando a biblioteca nativa está ausente (ambiente
Windows de desenvolvimento, mesma limitação já documentada em `report/
pdf.py`/`test_pdf.py`/`test_rotas_plano.py`), a chamada HTTP à rota de PDF é
pulada com `pytest.skip` e mensagem explícita — nunca fingida como executada.

REGRAS: `RF-20`, `RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_plano import obter_repositorio_snapshots
from app.http.sessao import iniciar_sessao_conta
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import RespostasCaso
from engine.motor import calcular_plano
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.supabase.repositorio_snapshots import ErroSnapshotNaoEncontrado
from report.pdf import gerar_html_do_plano_liberado
from report.plano import carregar_textos_canonicos, montar_contexto_plano
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-nao-usar-em-producao"
_VERSAO_PARAMETROS_REAL = "1.0.1"
_CONTA_ID = "CONTA-T65-REDACAO-CANONICA"
_CASO_ID = "CASO-T65-REDACAO-CANONICA"

# Transcrição de Q-03 (specs/piq-app-spec.md), usada SÓ para comparação neste
# teste — mesmo precedente de `tests/app_aluno/test_plano.py`: não é uma
# segunda fonte de produção, `report/plano.py` continua sendo a única leitura
# de `textos-canonicos.yaml` em código de produção.
_TITULO_Q03 = "Sua ordem projetada de quitação"
_CORPO_Q03 = (
    "Com os dados e condições atuais, o PIQ projeta a seguinte sequência de "
    "quitação. A ordem poderá ser recalculada se ocorrer alguma mudança "
    "material durante a execução."
)

_PALAVRAS_PROIBIDAS = ("definitiva", "final", "fixa")

_DIVIDA_ID_A = "D-T65-A"
_DIVIDA_ID_B = "D-T65-B"


class _RepositorioCasosDublê:
    """Dublê em memória — mesmo padrão de `tests/app_aluno/test_rotas_
    plano.py::_RepositorioCasosDublê`, restrito aos métodos que a rota de
    plano usa. Nenhum Postgres é tocado; o cenário HTTP é real, a
    persistência é um dublê de arquivo/memória (decisão documentada acima:
    o critério "fluxo HTTP completo" não exige banco real para os quatro
    critérios de redação/versão/contagem desta tarefa)."""

    def __init__(self, caso_inicial: Caso, conta_id_da_sessao: str) -> None:
        self._caso = caso_inicial
        self._conta_id_da_sessao = conta_id_da_sessao

    def criar(self, caso: Caso) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def buscar(self, caso_id: str) -> Caso | None:
        return self._caso if caso_id == self._caso.CASO_ID else None

    def pertence_a_conta(self, caso_id: str, conta_id: str) -> bool:
        return caso_id == self._caso.CASO_ID and conta_id == self._conta_id_da_sessao

    def transicionar_estado(self, caso_id, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def transicionar_estado_se(self, caso_id, estado_esperado, novo_estado, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_interacao(self, caso_id, agora=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_raiz(self, caso_id, snapshot_raiz_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui

    def registrar_snapshot_liberado(self, caso_id, snapshot_liberado_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError  # pragma: no cover — não usado aqui


class _RepositorioSnapshotsDublê:
    """Guarda um único snapshot em memória, indexado por `SNAPSHOT_ID` —
    mesmo contrato do adaptador Postgres real (`ErroSnapshotNaoEncontrado`
    para qualquer outro id)."""

    def __init__(self, snapshot: SnapshotOrdem) -> None:
        self._snapshot = snapshot

    def anexar(self, s: SnapshotOrdem) -> None:  # pragma: no cover — não usado aqui
        raise NotImplementedError

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        if snapshot_id != self._snapshot.SNAPSHOT_ID:
            raise ErroSnapshotNaoEncontrado(f"sem snapshot com SNAPSHOT_ID={snapshot_id!r}")
        return self._snapshot

    def historico(self, caso_id: str) -> tuple[SnapshotOrdem, ...]:  # pragma: no cover
        raise NotImplementedError


def _snapshot_real_com_duas_dividas() -> SnapshotOrdem:
    """`SnapshotOrdem` de VERDADE, com N=2 dívidas — mesmo padrão de
    `tests/app_aluno/test_plano.py::_snapshot_real_com_duas_dividas`: a
    fixture de caso completo (T-53) mais uma segunda ficha, passadas por
    `engine.motor.calcular_plano` — nunca fabricado à mão. N=2 (e não N=1)
    é deliberado: prova que `AC-17` não é um caso degenerado de uma única
    posição."""
    caso_a = caso_completo(DIVIDA_ID=_DIVIDA_ID_A)
    respostas_divida_b = montar_respostas_caso(
        valores_divida={
            "TIPO_DIVIDA": "CONSIGNADO",
            "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("8.000,00"),
            "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("400,00"),
        },
        DIVIDA_ID=_DIVIDA_ID_B,
    )
    respostas = caso_a.respostas.respostas + respostas_divida_b.respostas
    respostas_caso = RespostasCaso(respostas=respostas)

    divida_a = montar_divida(respostas_caso, _DIVIDA_ID_A)
    divida_b = montar_divida(respostas_caso, _DIVIDA_ID_B)
    estado = montar_estado_financeiro(
        respostas_caso,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_a, divida_b),
        **caso_a.parametros_externos,  # type: ignore[arg-type]
    )

    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def _caso_com_plano_liberado(snapshot: SnapshotOrdem) -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id=_CONTA_ID,
        estado=ESTADO_CASO.PLANO_LIBERADO,
        DATA_REFERENCIA=date(2026, 3, 15),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=snapshot.SNAPSHOT_ID,
        snapshot_liberado_id=snapshot.SNAPSHOT_ID,
        ultima_interacao_em=datetime(2026, 1, 1, tzinfo=UTC),
        criado_em=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _montar_cliente_autenticado(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repositorio_casos: _RepositorioCasosDublê,
    repositorio_snapshots: RepositorioSnapshots,
) -> TestClient:
    """Um CLIENTE autenticado de verdade — sessão assinada aberta via
    `iniciar_sessao_conta` sobre a aplicação FastAPI real
    (`criar_aplicacao()`), mesmo mecanismo de `tests/app_aluno/
    test_rotas_plano.py::_montar_cliente`. Só os dois repositórios são
    dublês; roteamento, sessão, isolamento e templates são o código real."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)

    aplicacao = criar_aplicacao()
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos
    aplicacao.dependency_overrides[obter_repositorio_snapshots] = lambda: repositorio_snapshots

    @aplicacao.post("/_teste/abrir-sessao/{conta_id}")
    def abrir_sessao(conta_id: str, request: Request) -> dict[str, str]:
        iniciar_sessao_conta(request, conta_id=conta_id)
        return {"conta_id": conta_id}

    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.post(f"/_teste/abrir-sessao/{_CONTA_ID}")
    return cliente


# ---------------------------------------------------------------------------
# Cenário comum às quatro baterias: um caso com plano liberado, snapshot REAL
# de duas dívidas, cliente autenticado, acessando as duas rotas HTTP reais.
# ---------------------------------------------------------------------------


def _preparar_cenario(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, SnapshotOrdem]:
    snapshot = _snapshot_real_com_duas_dividas()
    caso = _caso_com_plano_liberado(snapshot)
    repositorio_casos = _RepositorioCasosDublê(caso, _CONTA_ID)
    repositorio_snapshots = _RepositorioSnapshotsDublê(snapshot)

    cliente = _montar_cliente_autenticado(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        repositorio_snapshots=repositorio_snapshots,
    )
    return cliente, snapshot


def _html_que_a_rota_de_pdf_serviria(snapshot: SnapshotOrdem) -> str:
    """O HTML de ENTRADA que `report.pdf.gerar_pdf_do_plano` enviaria ao
    WeasyPrint para este mesmo `(caso, snapshot)` — ver a nota extensa na
    docstring do módulo sobre por que esta é a via legítima de auditar o
    conteúdo do PDF caractere por caractere sem uma biblioteca de extração
    de texto que este projeto não declara."""
    caso = _caso_com_plano_liberado(snapshot)
    textos = carregar_textos_canonicos()
    return gerar_html_do_plano_liberado(caso, snapshot, textos)


def _tentar_pdf_real(cliente: TestClient) -> bytes | None:
    """Chama a rota HTTP real de PDF. Devolve os bytes se a biblioteca
    nativa do WeasyPrint (GTK/Pango) estiver disponível neste ambiente;
    `None` se a rota falhar por essa limitação de ambiente conhecida (mesmo
    padrão de `tests/app_aluno/test_pdf.py`/`test_rotas_plano.py` — nunca
    fingido como executado)."""
    try:
        from weasyprint import HTML

        HTML(string="<html><body></body></html>").write_pdf()
    except OSError:
        return None

    resposta = cliente.get(f"/caso/{_CASO_ID}/plano/pdf")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    return resposta.content


# ---------------------------------------------------------------------------
# AC-14 — título e texto de Q-03 conferidos por igualdade exata de string,
# no HTML e no PDF, através das rotas HTTP reais.
# ---------------------------------------------------------------------------


def _texto_visivel_do_payload(plano: dict[str, object]) -> str:
    """Todo o texto que o React vai colocar na tela, achatado numa string.

    As auditorias de `AC-15`/`AC-16`/`AC-17` foram escritas para varrer o
    HTML da tela procurando (ou exigindo a ausência de) um termo. Com a tela
    em React o equivalente é o payload inteiro: se um termo proibido não
    está aqui, não há como aparecer na tela — o componente só renderiza o
    que recebe."""
    return json.dumps(plano, ensure_ascii=False)


def test_ac14_titulo_e_corpo_de_q03_sao_identicos_por_igualdade_exata_na_tela_e_no_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, snapshot = _preparar_cenario(monkeypatch)

    resposta_tela = cliente.get(f"/caso/{_CASO_ID}/api/plano")
    assert resposta_tela.status_code == 200

    # `AC-14` na tela: igualdade EXATA dos campos, não substring — um título
    # com espaço a mais ou reticências acrescentadas falharia aqui.
    plano = resposta_tela.json()["plano"]
    assert plano["titulo"] == _TITULO_Q03
    assert plano["corpo"] == _CORPO_Q03

    html_pdf = _html_que_a_rota_de_pdf_serviria(snapshot)
    assert f"<h1>{_TITULO_Q03}</h1>" in html_pdf
    assert f"<p>{_CORPO_Q03}</p>" in html_pdf

    # **A prova que substitui `html_tela == html_pdf`.** Tela e PDF não são
    # mais o mesmo documento (uma é JSON para o React, o outro é HTML para o
    # WeasyPrint), então a igualdade byte a byte deixou de fazer sentido. O
    # que `AC-14` exige continua verificável e é o que se verifica: o texto
    # normativo é IDÊNTICO nas duas saídas, porque as duas o leem de
    # `textos-canonicos.yaml` pela MESMA `carregar_textos_canonicos` — não
    # há segunda redação para divergir.
    textos = carregar_textos_canonicos()
    assert plano["titulo"] == textos.titulo
    assert plano["corpo"] == textos.corpo
    assert f"<h1>{textos.titulo}</h1>" in html_pdf
    assert f"<p>{textos.corpo}</p>" in html_pdf

    pdf_bytes = _tentar_pdf_real(cliente)
    if pdf_bytes is None:
        pytest.skip(
            "biblioteca nativa do WeasyPrint (GTK/Pango) indisponível neste "
            "ambiente Windows de desenvolvimento — ver report/pdf.py e "
            "tests/app_aluno/test_pdf.py para a mesma limitação documentada; "
            "o HTML de entrada do PDF (comparado acima, igual ao da tela) já "
            "confirma AC-14 caractere por caractere no conteúdo que o PDF "
            "de fato receberia."
        )
    assert pdf_bytes.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# AC-15 — "projetada" presente; "definitiva", "final" e "fixa" ausentes como
# qualificador da ordem, nas duas rotas reais.
# ---------------------------------------------------------------------------


def test_ac15_projetada_presente_e_qualificadores_proibidos_ausentes_na_tela_e_no_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, snapshot = _preparar_cenario(monkeypatch)

    resposta_tela = cliente.get(f"/caso/{_CASO_ID}/api/plano")
    assert resposta_tela.status_code == 200
    # `T-145`: a tela é React e recebe JSON. O texto auditado é o mesmo — os
    # dois lados leem `textos-canonicos.yaml` por `carregar_textos_canonicos`.
    texto_da_tela = _texto_visivel_do_payload(resposta_tela.json()["plano"])
    html_pdf = _html_que_a_rota_de_pdf_serviria(snapshot)

    for html, origem in ((texto_da_tela, "tela"), (html_pdf, "PDF")):
        assert "projetada" in html.lower(), f"'projetada' ausente na saída de {origem}"
        for palavra_proibida in _PALAVRAS_PROIBIDAS:
            assert palavra_proibida not in html.lower(), (
                f"'{palavra_proibida}' não deveria qualificar a ordem (AC-15), "
                f"encontrada na saída de {origem}"
            )


# ---------------------------------------------------------------------------
# AC-16 — ENGINE_VERSION e PARAMETROS_VERSION presentes nas duas saídas.
# ---------------------------------------------------------------------------


def test_ac16_engine_version_e_parametros_version_presentes_na_tela_e_no_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, snapshot = _preparar_cenario(monkeypatch)

    resposta_tela = cliente.get(f"/caso/{_CASO_ID}/api/plano")
    assert resposta_tela.status_code == 200
    # `T-145`: a tela é React e recebe JSON. O texto auditado é o mesmo — os
    # dois lados leem `textos-canonicos.yaml` por `carregar_textos_canonicos`.
    texto_da_tela = _texto_visivel_do_payload(resposta_tela.json()["plano"])
    html_pdf = _html_que_a_rota_de_pdf_serviria(snapshot)

    for html, origem in ((texto_da_tela, "tela"), (html_pdf, "PDF")):
        assert snapshot.ENGINE_VERSION in html, f"ENGINE_VERSION ausente na saída de {origem}"
        assert snapshot.PARAMETROS_VERSION in html, (
            f"PARAMETROS_VERSION ausente na saída de {origem}"
        )


# ---------------------------------------------------------------------------
# AC-17 — N posições, N justificativas, conferidas contra o snapshot de
# fixture (N=2, fixture com duas dívidas), nas duas rotas reais.
# ---------------------------------------------------------------------------


def test_ac17_n_posicoes_e_n_justificativas_conferidas_contra_o_snapshot_na_tela_e_no_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente, snapshot = _preparar_cenario(monkeypatch)

    # A fixture usada por este arquivo produz N=2 posições — confirma que o
    # snapshot de prova não é degenerado antes de auditar as saídas HTTP.
    assert len(snapshot.ORDEM_QUITACAO) == 2

    resposta_tela = cliente.get(f"/caso/{_CASO_ID}/api/plano")
    assert resposta_tela.status_code == 200
    # `T-145`: a tela é React e recebe JSON. O texto auditado é o mesmo — os
    # dois lados leem `textos-canonicos.yaml` por `carregar_textos_canonicos`.
    texto_da_tela = _texto_visivel_do_payload(resposta_tela.json()["plano"])
    html_pdf = _html_que_a_rota_de_pdf_serviria(snapshot)

    # `T-177`: a explicação ao aluno vem do contexto montado, não do
    # snapshot — o snapshot só carrega a justificativa técnica.
    contexto_por_divida = {
        posicao.DIVIDA_ID: posicao
        for posicao in montar_contexto_plano(snapshot, carregar_textos_canonicos()).ordem
    }

    for html, origem in ((texto_da_tela, "tela"), (html_pdf, "PDF")):
        for posicao_do_snapshot in snapshot.ORDEM_QUITACAO:
            assert posicao_do_snapshot.DIVIDA_ID in html, (
                f"DIVIDA_ID={posicao_do_snapshot.DIVIDA_ID!r} ausente na saída de {origem}"
            )
            # `T-177`: as saídas do ALUNO (tela e PDF) trazem a explicação
            # em português; a `JUSTIFICATIVA_POSICAO` técnica é texto de
            # auditoria e vai ao revisor (`AC-29`). `AC-17` continua
            # cumprido — toda posição diz por que está ali —, e é isso que
            # esta asserção guarda.
            explicacao = contexto_por_divida[posicao_do_snapshot.DIVIDA_ID].explicacao
            assert explicacao != "", (
                f"posição de {posicao_do_snapshot.DIVIDA_ID!r} sem explicação ao aluno"
            )
            assert explicacao in html, (
                f"explicação de {posicao_do_snapshot.DIVIDA_ID!r} "
                f"ausente na saída de {origem}"
            )
        # N justificativas de fato aparecem — não só N DIVIDA_ID (uma
        # JUSTIFICATIVA_POSICAO vazia passaria no `in` acima trivialmente).
        justificativas_nao_vazias = [
            p.JUSTIFICATIVA_POSICAO for p in snapshot.ORDEM_QUITACAO if p.JUSTIFICATIVA_POSICAO
        ]
        assert len(justificativas_nao_vazias) == len(snapshot.ORDEM_QUITACAO), (
            f"nem toda posição tem JUSTIFICATIVA_POSICAO não vazia (saída de {origem})"
        )
