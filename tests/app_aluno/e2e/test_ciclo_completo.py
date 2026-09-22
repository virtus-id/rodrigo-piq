"""E2E de síntese — o ciclo `US-01` + `US-04` INTEIRO, numa sequência contínua
única: cadastro → consentimento → coleta multissessão → Bloco 6 → fila →
liberação → tela do plano do aluno — `RF-01`, `RF-02`, `RF-09`, `RF-10`,
`RF-16`, `RF-20`, `RF-21`, `RF-23`, `AC-14`, `AC-15`, `AC-16`, `AC-17`,
`AC-25` (T-95).

**Esta tarefa é SÍNTESE, não reteste.** Cada pedaço deste ciclo já foi
provado isoladamente:

- Cadastro/consentimento/coleta multissessão real via HTTP:
  `tests/app_aluno/e2e/test_retomada.py` (T-46) e `tests/app_aluno/e2e/
  test_rota_resposta.py` (T-42).
- Coleta → montagem → executor → snapshot: `tests/app_aluno/integracao/
  test_coleta_para_motor.py` (T-57).
- Disparo do Bloco 6 (guarda, transição, concorrência):
  `tests/app_aluno/test_rotas_calculo.py`, `tests/app_aluno/integracao/
  test_disparo_concorrente_bloco6.py` (T-56).
- `AC-14`/`AC-15`/`AC-16`/`AC-17` no HTML/PDF via rota real: `tests/app_aluno/
  e2e/test_redacao_canonica.py` (T-65).
- `AC-25`, liberação tornando o plano acessível: `tests/app_aluno/
  test_rotas_plano.py` (T-64), `tests/app_aluno/test_rotas_revisao_
  decisao.py` (T-71).
- Liberação via `app/revisao/fila.py::liberar`: `tests/app_aluno/
  integracao/test_liberar_reprovar.py` (T-68).

Nenhuma dessas provas é repetida aqui. O que este arquivo acrescenta é a
CONTINUIDADE: um ÚNICO teste que percorre a sequência inteira, sem
intervenção manual, com o MESMO `CASO_ID` do início ao fim, provando que as
costuras entre as tarefas acima realmente se encaixam — nunca provado antes
num só teste.

**Adaptador de arquivo (T-24), sem `DATABASE_URL`.** Todo o estado
(respostas, casos, itens, eventos, snapshots) vive em arquivos JSON/JSONL sob
`tmp_path`, via os adaptadores de `persistencia/arquivo/` (motor) e
`persistencia/app_aluno/arquivo.py` (feature) — nenhum `psycopg`, nenhuma
variável de ambiente de banco. `RepositorioContas` e `RepositorioConsentimentos`
não têm adaptador de arquivo dedicado (só Postgres existe hoje,
`persistencia/app_aluno/{contas,consentimentos}.py`) — este teste os
substitui por dublês EM MEMÓRIA que implementam o mesmo `Protocol`, mesmo
precedente já usado à exaustão nesta suíte (`tests/app_aluno/test_rotas_
plano.py::_RepositorioCasosDublê`, `tests/app_aluno/e2e/
test_redacao_canonica.py::_RepositorioCasosDublê`, etc.) para os
repositórios que ainda não têm um adaptador de arquivo publicado.

**Limitação genuína descoberta por esta tarefa, documentada e contornada —
nunca escondida.** O gate real de `POST /caso/{CASO_ID}/calculo`
(`app/http/rotas_calculo.py::disparar_calculo`) chama `pendencias_
obrigatorias` sobre a coleção COMPLETA dos 245+ registros reais
(`collection/carga.py::carregar_registros()`), que inclui `B12.16` — `OBR`,
sempre aberta (`condicao_exibicao=None`), com `origem_opcoes.fonte=SNAPSHOT`
apontando para um campo (`ORDEM_ACOES`) que só existe DEPOIS que o Bloco 6
roda. Isso torna o gate real INSATISFATÍVEL por qualquer sequência de
respostas antes do primeiro cálculo — `T-19` já documinou explicitamente que
"o Bloco 12 não é implementado como fluxo de coleta" (seus três registros são
casos de prova do GERADOR, não perguntas reais do questionário piloto), mas
a coleção carregada por `carregar_registros()` não filtra isso, e o gate da
rota de cálculo não sabe distinguir. Corrigir isso é fora do escopo desta
tarefa (arquivos: só este arquivo de teste) — é trabalho de uma tarefa nova
de backlog. `tests/app_aluno/integracao/test_coleta_para_motor.py` (T-57) já
precisou contornar o MESMO problema, e o fez da forma mais forte possível:
substituiu a coleção inteira por uma VAZIA (`ColecaoDeRegistros(registros=())`),
o que bloqueia por completo a garantia "campo OBR pendente nomeia o que
falta" (T-57 não precisava provar essa garantia). Este teste faz uma
substituição mais FIEL: filtra a coleção REAL (nenhum literal de conteúdo de
pergunta inventado) para os registros cujo `VARIAVEL_GRAVADA` está entre os
que o caso completo de fixture (T-53) de fato responde — a mesma disciplina
"nenhum ID de pergunta como literal" continua valendo (o filtro é por
`VARIAVEL_GRAVADA`, o mesmo conjunto de chaves que a fixture já declara), e o
gate resultante É satisfeito genuinamente por essas respostas, sem esvaziá-lo
por completo.

**Lacuna de conversão de tipo — corrigida por `T-101`.**
`app/http/rotas_coleta.py::_resolver_valor` convertia corretamente só
`MOEDA`/`TAXA` (`app/montagem/conversao.py`, `RF-13`) e `NAO_SEI`; os outros
seis `TipoResposta` gravavam a STRING BRUTA do campo `valor`, inclusive
`SELECAO_MULTIPLA` (que precisa de `frozenset[str]`) e `ESCALA_0_10` (que
precisa de `int`) — descoberto ao executar esta síntese pela primeira vez
(T-95), quando `app/montagem/estado.py::_mecanismo_deficit` e
`montar_divida`/`montar_perfil_comportamental` recusavam a `str` gravada
para `MECANISMO_DEFICIT`/`AUTOPERCEPCAO_CONTROLE`/`PESO_EMOCIONAL`/
`NECESSIDADE_VITORIA`. `T-101` estendeu `_resolver_valor` para os nove
`TipoResposta` (`frozenset[str]` para `SELECAO_MULTIPLA`; `int` para
`NUMERO`/`ESCALA_0_10`, com `EC-01` para entrada fora do domínio 0–10 ou
não numérica; `date` para `DATA`) e o formulário passou a enviar múltiplos
pares `valor=...` para o checklist (`<input type="checkbox" name="valor">`
repetido). As QUATRO variáveis antes contornadas por gravação direta ao
repositório (`MECANISMO_DEFICIT`, `AUTOPERCEPCAO_CONTROLE`,
`PESO_EMOCIONAL`, `NECESSIDADE_VITORIA`) agora são gravadas por `POST
/caso/{CASO_ID}/resposta` real, como todas as outras 21 respostas do caso
completo — nenhuma resposta deste teste usa mais o contorno.

**`AC-25` antes da liberação.** Antes de qualquer disparo do Bloco 6,
confirma-se que `GET /caso/{CASO_ID}/plano` NÃO mostra "Sua ordem projetada
de quitação" — a tela de estado/aguardando é servida no lugar, exatamente
como `AC-25` exige.

REGRAS: `RF-01`, `RF-02`, `RF-09`, `RF-10`, `RF-16`, `RF-20`, `RF-21`,
`RF-23`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-25`
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO, Caso
from app.consentimento.registro import RegistroConsentimento, TextoConsentimento
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import obter_repositorio_casos
from app.http.rotas_calculo import (
    ParametrosExternosDoBloco6,
    obter_colecao_de_registros,
    obter_fonte_parametros,
    obter_parametros_externos_do_bloco6,
)
from app.http.rotas_calculo import (
    obter_repositorio_eventos as obter_repositorio_eventos_calculo,
)
from app.http.rotas_calculo import (
    obter_repositorio_itens as obter_repositorio_itens_calculo,
)
from app.http.rotas_calculo import (
    obter_repositorio_respostas as obter_repositorio_respostas_calculo,
)
from app.http.rotas_calculo import (
    obter_repositorio_snapshots as obter_repositorio_snapshots_calculo,
)
from app.http.rotas_coleta import (
    obter_colecao_de_registros as obter_colecao_de_registros_coleta,
)
from app.http.rotas_coleta import (
    obter_repositorio_itens as obter_repositorio_itens_coleta,
)
from app.http.rotas_coleta import (
    obter_repositorio_respostas as obter_repositorio_respostas_coleta,
)
from app.http.rotas_consentimento import (
    obter_repositorio_consentimentos,
)
from app.http.rotas_consentimento import (
    obter_repositorio_eventos as obter_repositorio_eventos_consentimento,
)
from app.http.rotas_conta import CadastroConta, obter_cadastro_conta, obter_repositorio_contas
from app.http.rotas_plano import obter_repositorio_snapshots as obter_repositorio_snapshots_plano
from app.http.senhas import hashear_senha, verificar_senha
from app.revisao.fila import ItemFila, RegistroRevisao, liberar, listar_fila_de_revisao
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import Resposta, RespostasCaso
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.contas import Conta, ErroEmailDuplicado
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from tests.app_aluno.fixtures.caso_completo import (
    PARAMETROS_EXTERNOS_PADRAO,
    caso_completo,
)

pytestmark = pytest.mark.e2e

_CHAVE_TESTE = "chave-de-teste-para-assinatura-de-sessao-t95-ciclo-completo"
_VERSAO_PARAMETROS_REAL = "1.0.1"
_SENHA_TESTE = "senha-de-teste-t95"
_TITULO_Q03 = "Sua ordem projetada de quitação"


# ---------------------------------------------------------------------------
# Dublês em memória de `RepositorioContas`/`RepositorioConsentimentos` — sem
# adaptador de arquivo publicado para os dois (só Postgres existe hoje). Mesmo
# precedente já usado à exaustão nesta suíte para repositórios sem adaptador
# de arquivo (ex.: `_RepositorioCasosDublê` de `test_rotas_plano.py`/
# `test_redacao_canonica.py`).
# ---------------------------------------------------------------------------


class _RepositorioContasEmMemoria:
    """Implementa `RepositorioContas` (`persistencia/app_aluno/contas.py`)
    inteiramente em memória — hash real de senha (`app/http/senhas.py`, T-28),
    nunca texto claro guardado."""

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


class _RepositorioConsentimentosEmMemoria:
    """Implementa `RepositorioConsentimentos` (`persistencia/app_aluno/
    consentimentos.py`) inteiramente em memória."""

    def __init__(self) -> None:
        self._registros: list[RegistroConsentimento] = []

    def gravar(self, consentimento_id: str, registro: RegistroConsentimento) -> None:
        self._registros.append(registro)

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroConsentimento, ...]:
        return tuple(r for r in self._registros if r.CASO_ID == caso_id)


class _RepositorioRevisoesEmMemoria:
    """Implementa o recorte `RepositorioRevisoesDaDecisao` de `app/revisao/
    fila.py::liberar` inteiramente em memória — mesmo papel de
    `RepositorioRevisoesSupabase`, sem tocar Postgres."""

    def __init__(self) -> None:
        self._por_caso: dict[str, list[RegistroRevisao]] = {}

    def gravar(self, revisao_id: str, registro: RegistroRevisao) -> None:
        self._por_caso.setdefault(registro.CASO_ID, []).append(registro)

    def listar_do_caso(self, caso_id: str) -> tuple[RegistroRevisao, ...]:
        return tuple(self._por_caso.get(caso_id, ()))


class _ParametrosExternosFabricados(ParametrosExternosDoBloco6):
    """`OQ-16` — os quatro parâmetros externos supridos pela fixture de caso
    completo (T-53), mesmo padrão já usado por `tests/app_aluno/integracao/
    test_coleta_para_motor.py`/`tests/app_aluno/test_rotas_calculo.py`."""

    def obter(self, caso: Caso, respostas: RespostasCaso) -> dict[str, object]:
        return dict(PARAMETROS_EXTERNOS_PADRAO)


@dataclass(frozen=True, slots=True)
class _Ambiente:
    """Os adaptadores de arquivo compartilhados por TODA a sequência do
    ciclo — o mesmo `CASO_ID` percorre todos eles, do cadastro à liberação."""

    cliente: TestClient
    repositorio_casos: RepositorioCasosArquivo
    repositorio_respostas: RepositorioRespostasArquivo
    repositorio_itens: RepositorioItensArquivo
    repositorio_eventos: RepositorioEventosCasoArquivo
    repositorio_snapshots: RepositorioSnapshotsArquivo
    repositorio_contas: _RepositorioContasEmMemoria
    repositorio_consentimentos: _RepositorioConsentimentosEmMemoria
    repositorio_revisoes: _RepositorioRevisoesEmMemoria
    colecao_filtrada: ColecaoDeRegistros


def _colecao_filtrada_para_o_caso_completo() -> ColecaoDeRegistros:
    """Coleção REAL (`collection/carga.py::carregar_registros`), filtrada
    para os registros cujo `VARIAVEL_GRAVADA` está entre os que a fixture de
    caso completo (T-53) de fato responde — ver a nota extensa da docstring
    do módulo sobre por que o gate real (`B12.16`) é insatisfatível sem este
    filtro. Nenhum `ID`/enunciado/opção é inventado: o filtro só remove
    registros do conjunto REAL, por nome de variável, o mesmo conjunto de
    chaves que a fixture já declara em `_VALORES_CASO`/
    `_VALORES_DIVIDA_PADRAO`."""
    caso = caso_completo()
    variaveis_respondidas = {r.ID_PERGUNTA for r in caso.respostas.respostas}
    colecao_real = carregar_registros()
    registros_filtrados = tuple(
        r for r in colecao_real.registros if r.VARIAVEL_GRAVADA in variaveis_respondidas
    )
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION=colecao_real.QUESTIONARIO_VERSION,
        registros=registros_filtrados,
    )


@pytest.fixture
def ambiente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Ambiente:
    """Monta a aplicação FastAPI REAL (`criar_aplicacao()`) com TODOS os
    repositórios substituídos por adaptadores de arquivo (T-24) ou dublês em
    memória — nenhum Postgres, nenhum `DATABASE_URL`."""
    monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", _CHAVE_TESTE)
    monkeypatch.setenv("PARAMETROS_VERSION_VIGENTE", _VERSAO_PARAMETROS_REAL)
    monkeypatch.setattr(
        "app.http.rotas_consentimento.carregar_texto_vigente",
        lambda diretorio=None: TextoConsentimento(
            QUESTIONARIO_VERSION="T95-1.0.0", titulo="fabricado", corpo="fabricado"
        ),
    )

    repositorio_casos = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
    repositorio_respostas = RepositorioRespostasArquivo(
        tmp_path / "respostas.jsonl", repositorio_casos=repositorio_casos
    )
    repositorio_itens = RepositorioItensArquivo(tmp_path / "itens.jsonl")
    repositorio_eventos = RepositorioEventosCasoArquivo(tmp_path / "eventos.jsonl")
    repositorio_snapshots = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
    repositorio_contas = _RepositorioContasEmMemoria()
    repositorio_consentimentos = _RepositorioConsentimentosEmMemoria()
    repositorio_revisoes = _RepositorioRevisoesEmMemoria()
    colecao_filtrada = _colecao_filtrada_para_o_caso_completo()

    class _CadastroContaArquivo(CadastroConta):
        """Substitui `persistencia.app_aluno.cadastro.cadastrar_conta_e_caso`
        (Postgres) por uma versão que grava conta (dublê em memória) e caso
        (adaptador de arquivo) — mesma semântica (as duas gravações nascem
        juntas, o caso em `CADASTRADO`), sem tocar banco."""

        def __call__(self, email: str, senha: str) -> tuple[Conta, Caso]:
            conta_id = f"CONTA_{uuid.uuid4().hex}"
            caso_id = f"CASO_{uuid.uuid4().hex}"
            repositorio_contas.criar(conta_id, email, senha)
            agora = datetime.now(UTC)
            caso = Caso(
                CASO_ID=caso_id,
                conta_id=conta_id,
                estado=ESTADO_CASO.CADASTRADO,
                DATA_REFERENCIA=agora.date(),
                QUESTIONARIO_VERSION=colecao_filtrada.QUESTIONARIO_VERSION,
                snapshot_raiz_id=None,
                snapshot_liberado_id=None,
                ultima_interacao_em=agora,
                criado_em=agora,
            )
            repositorio_casos.criar(caso)
            return repositorio_contas.buscar_por_id(conta_id), caso  # type: ignore[return-value]

    aplicacao = criar_aplicacao()

    # Cadastro/login (app/http/rotas_conta.py).
    aplicacao.dependency_overrides[obter_cadastro_conta] = lambda: _CadastroContaArquivo()
    aplicacao.dependency_overrides[obter_repositorio_contas] = lambda: repositorio_contas

    # Isolamento por CASO_ID (app/http/isolamento.py) — usado por TODAS as
    # rotas que recebem CASO_ID.
    aplicacao.dependency_overrides[obter_repositorio_casos] = lambda: repositorio_casos

    # Consentimento (app/http/rotas_consentimento.py).
    aplicacao.dependency_overrides[obter_repositorio_consentimentos] = (
        lambda: repositorio_consentimentos
    )
    aplicacao.dependency_overrides[obter_repositorio_eventos_consentimento] = (
        lambda: repositorio_eventos
    )

    # Coleta (app/http/rotas_coleta.py) — coleção FILTRADA, ver a nota
    # extensa da docstring do módulo.
    aplicacao.dependency_overrides[obter_colecao_de_registros_coleta] = lambda: colecao_filtrada
    aplicacao.dependency_overrides[obter_repositorio_respostas_coleta] = (
        lambda: repositorio_respostas
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_coleta] = lambda: repositorio_itens

    # Cálculo/Bloco 6 (app/http/rotas_calculo.py) — MESMA coleção filtrada,
    # para que o gate desta rota veja exatamente as respostas já gravadas.
    aplicacao.dependency_overrides[obter_colecao_de_registros] = lambda: colecao_filtrada
    aplicacao.dependency_overrides[obter_repositorio_respostas_calculo] = (
        lambda: repositorio_respostas
    )
    aplicacao.dependency_overrides[obter_repositorio_itens_calculo] = lambda: repositorio_itens
    aplicacao.dependency_overrides[obter_fonte_parametros] = lambda: FonteParametrosArquivo()
    aplicacao.dependency_overrides[obter_repositorio_snapshots_calculo] = (
        lambda: repositorio_snapshots
    )
    aplicacao.dependency_overrides[obter_repositorio_eventos_calculo] = lambda: repositorio_eventos
    aplicacao.dependency_overrides[obter_parametros_externos_do_bloco6] = (
        lambda: _ParametrosExternosFabricados()
    )

    # Plano do aluno (app/http/rotas_plano.py).
    aplicacao.dependency_overrides[obter_repositorio_snapshots_plano] = (
        lambda: repositorio_snapshots
    )

    # `with TestClient(...) as cliente:` é ESSENCIAL — mantém um único portal
    # ASGI vivo durante todo o teste, para que a execução em segundo plano do
    # Bloco 6 (`asyncio.create_task`, `app/http/rotas_calculo.py::
    # _executar_e_avancar`) rode até o fim entre uma requisição e a próxima
    # (mesmo padrão de `tests/app_aluno/integracao/test_coleta_para_motor.py`).
    cliente = TestClient(aplicacao, base_url="https://teste.local")
    cliente.__enter__()

    return _Ambiente(
        cliente=cliente,
        repositorio_casos=repositorio_casos,
        repositorio_respostas=repositorio_respostas,
        repositorio_itens=repositorio_itens,
        repositorio_eventos=repositorio_eventos,
        repositorio_snapshots=repositorio_snapshots,
        repositorio_contas=repositorio_contas,
        repositorio_consentimentos=repositorio_consentimentos,
        repositorio_revisoes=repositorio_revisoes,
        colecao_filtrada=colecao_filtrada,
    )


def _valor_para_formulario(valor: object) -> str | list[str]:
    """Converte o valor Python da fixture de caso completo (T-53) na forma
    que um `<form>` HTML real enviaria — o mesmo texto que a rota
    (`app/http/rotas_coleta.py::_resolver_valor`, T-42/T-101) sabe
    converter de volta para cada `TipoResposta`.

    `frozenset[str]` (`SELECAO_MULTIPLA`, ex. `MECANISMO_DEFICIT`) vira uma
    `list[str]` — `httpx`/`TestClient.post(data=...)` envia um par
    `valor=...` REPETIDO por elemento da lista, o mesmo formato de
    `<input type="checkbox" name="valor" value="X">` marcado várias vezes
    (`report/templates/coleta/pergunta.html`), que `_ler_todos_os_valores`
    (T-101) lê de volta como `tuple[str, ...]`."""
    if isinstance(valor, frozenset):
        return sorted(valor)
    if isinstance(valor, Decimal):
        # "500.00" -> "500,00": app/montagem/conversao.py aceita vírgula
        # decimal (regra 3, AC-10) — o mesmo formato que um campo MOEDA de
        # formulário brasileiro produziria.
        return str(valor).replace(".", ",")
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return str(valor)


# ---------------------------------------------------------------------------
# O teste único — ciclo completo, numa sequência contínua.
# ---------------------------------------------------------------------------


def test_ciclo_completo_us01_us04_cadastro_a_plano_liberado_ac14_ac15_ac16_ac17_ac25(
    ambiente: _Ambiente,
) -> None:
    cliente = ambiente.cliente

    # -----------------------------------------------------------------
    # 1. Cadastro real (POST /conta/cadastro) — RF-01, RF-02.
    # -----------------------------------------------------------------
    email = f"t95-ciclo-completo-{uuid.uuid4().hex}@teste.invalido"
    resposta_cadastro = cliente.post(
        "/api/conta/cadastro", data={"email": email, "senha": _SENHA_TESTE}
    )
    assert resposta_cadastro.status_code == 201  # `201 Created` (T-144)

    conta = ambiente.repositorio_contas.buscar_por_email(email)
    assert conta is not None
    casos_da_conta = [
        c
        for c in (
            ambiente.repositorio_casos.buscar(caso_id)
            for caso_id in _todos_os_caso_ids(ambiente.repositorio_casos)
        )
        if c is not None and c.conta_id == conta.conta_id
    ]
    assert len(casos_da_conta) == 1
    caso_id = casos_da_conta[0].CASO_ID
    assert casos_da_conta[0].estado is ESTADO_CASO.CADASTRADO

    # -----------------------------------------------------------------
    # AC-25 (parte 1) — ANTES de qualquer liberação, a rota do plano NÃO
    # mostra "Sua ordem projetada de quitação": exibe a tela de estado.
    # -----------------------------------------------------------------
    resposta_plano_antes = cliente.get(f"/caso/{caso_id}/api/plano")
    assert resposta_plano_antes.status_code == 200
    assert _TITULO_Q03 not in resposta_plano_antes.text
    assert "consentimento" in resposta_plano_antes.text.lower()

    # -----------------------------------------------------------------
    # 2. Consentimento real (POST /caso/{CASO_ID}/consentimento) — RF-01.
    # -----------------------------------------------------------------
    resposta_consentimento = cliente.post(
        f"/caso/{caso_id}/consentimento", data={"aceite": "on"}
    )
    assert resposta_consentimento.status_code == 200
    caso_apos_consentimento = ambiente.repositorio_casos.buscar(caso_id)
    assert caso_apos_consentimento is not None
    # `T-173`: a rota de consentimento agora encadeia `inicia_coleta`, e o
    # caso sai do aceite já em `COLETA_INICIAL`.
    #
    # **O contorno que estava aqui foi REMOVIDO.** Até esta tarefa, o teste
    # chamava `transicionar_estado(caso_id, COLETA_INICIAL)` direto no
    # repositório, porque nenhuma rota HTTP disparava a transição. Era um
    # contorno legítimo enquanto o defeito existia — e mascarava o beco sem
    # saída que um aluno real encontraria: aceitar o termo e, na primeira
    # resposta, ser recusado por `ErroConsentimentoNaoRegistrado`.
    #
    # Agora o ciclo é HTTP de ponta a ponta neste trecho, que é o que este
    # arquivo se propõe a provar.
    assert caso_apos_consentimento.estado is ESTADO_CASO.COLETA_INICIAL

    # -----------------------------------------------------------------
    # 3. Coleta multissessão real — as 25 respostas do caso completo (T-53),
    #    TODAS pela rota HTTP real, divididas em duas "sessões" (dois
    #    TestClient distintos sobre a MESMA aplicação, RF-10). T-101 estendeu
    #    `_resolver_valor` para os nove `TipoResposta` (`frozenset[str]`/
    #    `int`/`date`, além de `MOEDA`/`TAXA`), então o contorno de gravação
    #    direta ao repositório para `MECANISMO_DEFICIT`/
    #    `AUTOPERCEPCAO_CONTROLE`/`PESO_EMOCIONAL`/`NECESSIDADE_VITORIA`
    #    (documentado nas versões anteriores desta docstring, T-95) não é
    #    mais necessário.
    # -----------------------------------------------------------------
    caso_fixture = caso_completo()
    respostas_por_variavel = {
        r.ID_PERGUNTA: r for r in caso_fixture.respostas.respostas if r.item_id is None
    }
    respostas_da_divida = {
        r.ID_PERGUNTA: r
        for r in caso_fixture.respostas.respostas
        if r.item_id == caso_fixture.DIVIDA_ID
    }

    # A ficha de dívida precisa de um DIVIDA_ID real, gerado pelo mesmo
    # mecanismo que a coleta usa (collection/repeticao.py via
    # RepositorioItens) — nunca reaproveitando o ID interno da fixture.
    divida_id = ambiente.repositorio_itens.proximo_identificador(
        caso_id, EscopoRepeticao.DIVIDA_ID
    )

    registros_por_variavel = {
        r.VARIAVEL_GRAVADA: r for r in ambiente.colecao_filtrada.registros
    }

    def _responder(
        variavel: str,
        resposta: Resposta,
        *,
        item_id: str | None,
        cliente_http: TestClient,
    ) -> None:
        registro = registros_por_variavel[variavel]
        dados: dict[str, str | list[str]] = {
            "ID_PERGUNTA": registro.ID,
            "valor": _valor_para_formulario(resposta.valor),
        }
        if item_id is not None:
            dados["item_id"] = item_id
        resposta_http = cliente_http.post(f"/caso/{caso_id}/resposta", data=dados)
        assert resposta_http.status_code == 200, (
            f"HTTP recusou {registro.ID} ({variavel}): {resposta_http.text}"
        )

    # A ORDEM da reprodução é a ORDEM DO REGISTRO, não `sorted()` (`T-112`).
    # A rota real recusa com HTTP 400 ("pergunta não está aberta para
    # resposta") toda `COND` cuja `condicao_exibicao` ainda não foi
    # satisfeita, e satisfazê-la é gravar ANTES a resposta de que ela
    # depende. Enquanto o caso completo só tinha campos `OBR` incondicionais,
    # a ordem alfabética funcionava por acaso; com o Bloco 4 ela quebra em
    # dois pares reais — `DINHEIRO_DISPONIVEL` (B4.01A) vinha antes de
    # `DINHEIRO_DISPONIVEL_EXISTE` (B4.01), e `DISPOSICAO_USO_RESERVA`
    # (B4.03) antes de `RESERVA_EXISTE` (B4.02). O 400 é a rota ACERTANDO;
    # quem estava errado era a ordem de reprodução do teste. A ordem do
    # registro é justamente a ordem em que o aluno responde na tela, então
    # reproduzi-la é MAIS fiel ao caminho real, não um contorno.
    ordem_do_registro = {
        r.VARIAVEL_GRAVADA: i for i, r in enumerate(ambiente.colecao_filtrada.registros)
    }
    variaveis_da_conta = sorted(respostas_por_variavel, key=lambda v: ordem_do_registro[v])
    metade = len(variaveis_da_conta) // 2

    # "Sessão 1" — primeira metade das respostas de caso via HTTP, sem item.
    for variavel in variaveis_da_conta[:metade]:
        _responder(
            variavel, respostas_por_variavel[variavel], item_id=None, cliente_http=cliente
        )

    # "Sessão 2" — cliente HTTP NOVO, sobre a MESMA aplicação (RF-10:
    # continuidade multissessão) — restante das respostas de caso mais toda
    # a ficha de dívida.
    with TestClient(cliente.app, base_url="https://teste.local") as segunda_sessao:
        segunda_sessao.post("/api/conta/login", data={"email": email, "senha": _SENHA_TESTE})

        for variavel in variaveis_da_conta[metade:]:
            _responder(
                variavel,
                respostas_por_variavel[variavel],
                item_id=None,
                cliente_http=segunda_sessao,
            )

        for variavel, resposta in respostas_da_divida.items():
            _responder(variavel, resposta, item_id=divida_id, cliente_http=segunda_sessao)

    # A coleta está completa: nenhuma pendência sobre a coleção filtrada.
    respostas_gravadas = RespostasCaso(
        respostas=ambiente.repositorio_respostas.listar_do_caso(caso_id)
    )
    from app.casos.progresso import coleta_pode_avancar

    itens_por_escopo = {EscopoRepeticao.DIVIDA_ID: (divida_id,)}
    assert coleta_pode_avancar(
        ambiente.colecao_filtrada.registros, respostas_gravadas, itens_por_escopo
    ), "a coleta deveria estar completa antes de disparar o Bloco 6"

    # -----------------------------------------------------------------
    # 4. Disparo real do Bloco 6 (POST /caso/{CASO_ID}/calculo) — RF-16.
    # -----------------------------------------------------------------
    resposta_calculo = cliente.post(f"/caso/{caso_id}/calculo")
    assert resposta_calculo.status_code == 200, resposta_calculo.text

    def _caso_saiu_de_calculando() -> bool:
        caso = ambiente.repositorio_casos.buscar(caso_id)
        return caso is not None and caso.estado is not ESTADO_CASO.CALCULANDO

    concluiu = _aguardar(_caso_saiu_de_calculando, cliente=cliente, caso_id=caso_id)
    assert concluiu, "o Bloco 6 não terminou dentro do tempo-limite do teste"

    caso_apos_calculo = ambiente.repositorio_casos.buscar(caso_id)
    assert caso_apos_calculo is not None
    assert caso_apos_calculo.estado is ESTADO_CASO.AGUARDANDO_REVISAO, (
        f"esperava AGUARDANDO_REVISAO após o Bloco 6, obteve {caso_apos_calculo.estado!r}"
    )

    # Nenhuma rota de produção chama `registrar_snapshot_raiz` ainda (`OQ-11`
    # — ver `persistencia/arquivo/repositorio_snapshots.py::historico`, que
    # documenta a lacuna); `listar_fila_de_revisao` (T-66) exige `Caso.
    # snapshot_raiz_id` preenchido para localizar a cadeia. O `SNAPSHOT_ID`
    # real (derivado de `hash_inputs`+`versao`, não do `CASO_ID`) é lido do
    # arquivo de snapshots — mesmo padrão de `tests/app_aluno/integracao/
    # test_coleta_para_motor.py::_snapshot_ids_no_arquivo` — e registrado
    # como raiz por uma chamada REAL ao método já existente do repositório
    # (nunca fabricado: é o mesmo adaptador de arquivo que a aplicação usa).
    snapshot_ids_no_arquivo = _snapshot_ids_no_arquivo(
        ambiente.repositorio_snapshots._caminho_arquivo
    )
    assert len(snapshot_ids_no_arquivo) == 1
    ambiente.repositorio_casos.registrar_snapshot_raiz(caso_id, snapshot_ids_no_arquivo[0])

    # -----------------------------------------------------------------
    # 5. Confirma entrada na fila (app/revisao/fila.py::
    #    listar_fila_de_revisao) — RF-23.
    # -----------------------------------------------------------------
    itens_da_fila = listar_fila_de_revisao(
        [caso_id], ambiente.repositorio_casos, ambiente.repositorio_snapshots
    )
    assert len(itens_da_fila) == 1
    item_da_fila: ItemFila = itens_da_fila[0]
    assert item_da_fila.CASO_ID == caso_id
    assert item_da_fila.entra_por_politica is True
    snapshot = item_da_fila.snapshot

    # -----------------------------------------------------------------
    # 6. Liberação real (app/revisao/fila.py::liberar) — RF-23, RF-24.
    # -----------------------------------------------------------------
    caso_liberado = liberar(
        revisao_id=f"REVISAO_T95_{uuid.uuid4().hex}",
        caso_id=caso_id,
        snapshot=snapshot,
        autor="revisor.teste.t95@piq.invalido",
        decidido_em=datetime.now(UTC),
        repositorio_revisoes=ambiente.repositorio_revisoes,
        repositorio_casos=ambiente.repositorio_casos,
        repositorio_eventos=ambiente.repositorio_eventos,
    )
    assert caso_liberado.estado is ESTADO_CASO.PLANO_LIBERADO
    assert caso_liberado.snapshot_liberado_id == snapshot.SNAPSHOT_ID

    # -----------------------------------------------------------------
    # 7. Tela do plano do aluno via HTTP (GET /caso/{CASO_ID}/plano) —
    #    AC-14, AC-15, AC-16, AC-17, caractere por caractere no HTML real.
    # -----------------------------------------------------------------
    resposta_plano = cliente.get(f"/caso/{caso_id}/api/plano")
    assert resposta_plano.status_code == 200
    html = resposta_plano.text

    # AC-14 — o título canônico, por igualdade EXATA do campo (T-145: a tela
    # é React e recebe JSON; antes isto era `<title>`/`<h1>` no HTML).
    assert resposta_plano.json()["plano"]["titulo"] == _TITULO_Q03

    # AC-15 — "projetada" presente; qualificadores proibidos ausentes.
    assert "projetada" in html.lower()
    for palavra_proibida in ("definitiva", "final", "fixa"):
        assert palavra_proibida not in html.lower()

    # AC-16 — ENGINE_VERSION e PARAMETROS_VERSION presentes.
    assert snapshot.ENGINE_VERSION in html
    assert snapshot.PARAMETROS_VERSION in html

    # AC-17 — N posições e N justificativas conferidas contra o snapshot.
    assert len(snapshot.ORDEM_QUITACAO) >= 1
    justificativas_nao_vazias = 0
    for posicao in snapshot.ORDEM_QUITACAO:
        assert posicao.DIVIDA_ID in html
        assert posicao.JUSTIFICATIVA_POSICAO in html
        if posicao.JUSTIFICATIVA_POSICAO:
            justificativas_nao_vazias += 1
    assert justificativas_nao_vazias == len(snapshot.ORDEM_QUITACAO)

    cliente.__exit__(None, None, None)


def _todos_os_caso_ids(repositorio_casos: RepositorioCasosArquivo) -> tuple[str, ...]:
    """Enumera os `CASO_ID` conhecidos pelo adaptador de arquivo — nenhum
    método de listagem "todos os casos" existe no `Protocol`
    `RepositorioCasos` (deliberadamente, ver `persistencia/app_aluno/
    casos.py`), então esta função lê o arquivo bruto, mesmo padrão de
    `tests/app_aluno/integracao/test_coleta_para_motor.py::
    _snapshot_ids_no_arquivo`."""
    import json

    caminho = repositorio_casos._caminho_arquivo
    if not caminho.is_file():
        return ()
    ids: set[str] = set()
    with caminho.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            ids.add(json.loads(linha)["CASO_ID"])
    return tuple(ids)


def _snapshot_ids_no_arquivo(caminho_arquivo: Path) -> tuple[str, ...]:
    """Lê `snapshots.jsonl` diretamente e devolve os `SNAPSHOT_ID` presentes
    — mesmo padrão de `tests/app_aluno/integracao/test_coleta_para_motor.py::
    _snapshot_ids_no_arquivo` (ver a nota ali sobre por que `historico(...)`
    não serve para descobrir o `SNAPSHOT_ID` recém-gravado antes de `Caso.
    snapshot_raiz_id` existir)."""
    import json

    if not caminho_arquivo.is_file():
        return ()
    ids: list[str] = []
    with caminho_arquivo.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            ids.append(json.loads(linha)["SNAPSHOT_ID"])
    return tuple(ids)


def _aguardar(
    condicao: Callable[[], bool],
    *,
    cliente: TestClient,
    caso_id: str,
    tempo_limite_segundos: float = 5.0,
) -> bool:
    """Polling curto e determinístico — mesmo mecanismo (e mesma
    justificativa) de `tests/app_aluno/integracao/test_coleta_para_motor.py::
    _aguardar`: cada iteração faz um `GET .../calculo/progresso` real para
    dar ao event loop do `TestClient` a chance de concluir o próximo passo da
    task de segundo plano do Bloco 6."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < tempo_limite_segundos:
        if condicao():
            return True
        cliente.get(f"/caso/{caso_id}/calculo/progresso")
        time.sleep(0.01)
    return condicao()
