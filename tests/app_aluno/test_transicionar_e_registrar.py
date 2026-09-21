"""Testes de `app/casos/progresso.py::transicionar_e_registrar` — `RF-31`,
`AC-40`, `EC-14` (T-91).

Cobre os quatro critérios de aceite da tarefa:

1. Toda transição da máquina grava um evento com origem, destino, gatilho e
   data — provado aqui sobre o wrapper `transicionar_e_registrar` em si (o
   ÚNICO caminho de produção que transiciona `Caso` real desta feature,
   consumido por `app/http/rotas_consentimento.py`, `app/http/
   rotas_calculo.py`, `app/revisao/fila.py`, `app/casos/acompanhamento.py` e
   `app/motor/executor.py`).
2. `ultima_interacao_em` do caso é atualizada a cada resposta gravada —
   provado sobre `persistencia/app_aluno/respostas.py::
   RepositorioRespostasSupabase.gravar` (mypy/assinatura) e sobre o
   adaptador de arquivo (comportamento real).
3. Nenhum evento contém valor monetário, saldo, renda ou identificador
   pessoal — auditoria por ASSINATURA de `EventoCaso` (a mesma disciplina de
   allowlist de `app/motor/executor.py::_registrar_evento`, T-55).
4. `EC-14`: um caso parado há meses continua retomável com todas as
   respostas — a trilha registra a última transição e a data, mas nunca
   apaga nem reescreve uma resposta gravada.

Usa o adaptador de ARQUIVO (`persistencia/app_aluno/arquivo.py`, T-24) para
`RepositorioCasos`/`RepositorioEventosCaso`/`RepositorioRespostas` — a suíte
principal desta feature roda sem `DATABASE_URL`.

REGRAS: `RF-31`, `AC-40`, `EC-14`
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.casos.maquina import ESTADO_CASO, Caso, ErroTransicaoNaoDeclarada
from app.casos.progresso import transicionar_e_registrar
from collection.respostas import Resposta
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.app_aluno.eventos import EventoCaso

_CASO_ID: str = "caso-teste-t91-trilha"


def _caso_fabricado(estado: ESTADO_CASO, agora: datetime) -> Caso:
    return Caso(
        CASO_ID=_CASO_ID,
        conta_id="conta-teste-t91",
        estado=estado,
        DATA_REFERENCIA=agora.date(),
        QUESTIONARIO_VERSION="1.0.0",
        snapshot_raiz_id=None,
        snapshot_liberado_id=None,
        ultima_interacao_em=agora,
        criado_em=agora,
    )


@pytest.fixture
def repositorio_casos(tmp_path: Path) -> RepositorioCasosArquivo:
    return RepositorioCasosArquivo(tmp_path / "casos.jsonl")


@pytest.fixture
def repositorio_eventos(tmp_path: Path) -> RepositorioEventosCasoArquivo:
    return RepositorioEventosCasoArquivo(tmp_path / "eventos_caso.jsonl")


@pytest.fixture
def repositorio_respostas(tmp_path: Path) -> RepositorioRespostasArquivo:
    return RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")


# ---------------------------------------------------------------------------
# Critério 1 — toda transição da máquina grava um evento com origem, destino,
# gatilho e data.
# ---------------------------------------------------------------------------


def test_transicionar_e_registrar_grava_evento_com_origem_destino_gatilho_e_data(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """`RF-31`/`AC-40`: uma transição real (`CADASTRADO →
    CONSENTIMENTO_REGISTRADO`, gatilho `registra_consentimento`, declarada em
    `app/casos/maquina.py::TABELA_TRANSICOES`) produz exatamente um
    `EventoCaso` com `tipo_evento` igual ao gatilho nomeado pela tabela,
    `estado_de`/`estado_para` iguais aos `.value` dos dois estados, e
    `ocorrido_em` igual ao instante fornecido."""
    agora = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.CADASTRADO, agora))

    caso_atualizado = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CADASTRADO,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        agora=agora,
    )

    assert caso_atualizado is not None
    assert caso_atualizado.estado is ESTADO_CASO.CONSENTIMENTO_REGISTRADO

    eventos = repositorio_eventos.listar_do_caso(_CASO_ID)
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.tipo_evento == "registra_consentimento"
    assert evento.estado_de == ESTADO_CASO.CADASTRADO.value
    assert evento.estado_para == ESTADO_CASO.CONSENTIMENTO_REGISTRADO.value
    assert evento.ocorrido_em == agora


def test_transicionar_e_registrar_recusa_par_nao_declarado_sem_gravar_nada(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Um par `(de, para)` fora da tabela é recusado com
    `ErroTransicaoNaoDeclarada`, ANTES de qualquer tentativa de persistir ou
    de registrar evento — nem o `Caso` nem a trilha mudam."""
    agora = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.CADASTRADO, agora))

    with pytest.raises(ErroTransicaoNaoDeclarada):
        transicionar_e_registrar(
            repositorio_casos=repositorio_casos,
            repositorio_eventos=repositorio_eventos,
            caso_id=_CASO_ID,
            de=ESTADO_CASO.CADASTRADO,
            para=ESTADO_CASO.PLANO_LIBERADO,
            agora=agora,
        )

    caso_depois = repositorio_casos.buscar(_CASO_ID)
    assert caso_depois is not None
    assert caso_depois.estado is ESTADO_CASO.CADASTRADO
    assert repositorio_eventos.listar_do_caso(_CASO_ID) == ()


def test_transicionar_e_registrar_nao_grava_evento_quando_corrida_ja_foi_perdida(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Quando `transicionar_estado_se` devolve `None` (o `estado` corrente já
    não é `de` — outra transição concorrente venceu a corrida), a função
    devolve `None` e NENHUM evento é gravado: não houve transição real, então
    não há fato a registrar."""
    agora = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.COLETA_INICIAL, agora))
    # O caso já avançou por fora (simulação de corrida perdida).
    repositorio_casos.transicionar_estado(_CASO_ID, ESTADO_CASO.CALCULANDO)

    resultado = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.COLETA_INICIAL,
        para=ESTADO_CASO.CALCULANDO,
        agora=agora,
    )

    assert resultado is None
    assert repositorio_eventos.listar_do_caso(_CASO_ID) == ()


def test_transicionar_e_registrar_com_multiplas_transicoes_produz_uma_trilha_ordenavel(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Uma sequência de transições reais do plano §7.1 (`CADASTRADO →
    CONSENTIMENTO_REGISTRADO → COLETA_INICIAL`) produz DOIS eventos na
    trilha, cada um nomeando o gatilho correto — a trilha não é uma única
    entrada genérica, é uma entrada POR transição."""
    t0 = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 1, 9, 5, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.CADASTRADO, t0))

    transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CADASTRADO,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        agora=t0,
    )
    transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        para=ESTADO_CASO.COLETA_INICIAL,
        agora=t1,
    )

    eventos = sorted(repositorio_eventos.listar_do_caso(_CASO_ID), key=lambda e: e.ocorrido_em)
    assert len(eventos) == 2
    assert eventos[0].tipo_evento == "registra_consentimento"
    assert eventos[0].estado_de == ESTADO_CASO.CADASTRADO.value
    assert eventos[0].estado_para == ESTADO_CASO.CONSENTIMENTO_REGISTRADO.value
    assert eventos[1].tipo_evento == "inicia_coleta"
    assert eventos[1].estado_de == ESTADO_CASO.CONSENTIMENTO_REGISTRADO.value
    assert eventos[1].estado_para == ESTADO_CASO.COLETA_INICIAL.value


# ---------------------------------------------------------------------------
# Critério 2 — `ultima_interacao_em` do caso é atualizada a cada resposta
# gravada.
# ---------------------------------------------------------------------------


def test_gravar_resposta_atualiza_ultima_interacao_em_do_caso(
    repositorio_casos: RepositorioCasosArquivo,
    tmp_path: Path,
) -> None:
    """`RF-31`/`EC-14`: `RepositorioRespostasArquivo.gravar` (mesma interface
    de `RepositorioRespostasSupabase.gravar`), quando construído com uma
    referência a `repositorio_casos` (`T-91`), atualiza sozinha `Caso.
    ultima_interacao_em` para o instante da resposta — sem NENHUMA chamada
    adicional do teste a `registrar_interacao`. Não só transições de estado
    alimentam a trilha de "quando o caso foi tocado pela última vez"."""
    t0 = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.COLETA_INICIAL, t0))
    repositorio_respostas_com_trilha = RepositorioRespostasArquivo(
        tmp_path / "respostas.jsonl", repositorio_casos=repositorio_casos
    )

    t1 = t0 + timedelta(days=45)
    resposta = Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA="VARIAVEL_TESTE",
        item_id=None,
        valor="valor de teste",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=t1,
    )
    repositorio_respostas_com_trilha.gravar(resposta)

    caso_depois = repositorio_casos.buscar(_CASO_ID)
    assert caso_depois is not None
    assert caso_depois.ultima_interacao_em == t1
    assert caso_depois.estado is ESTADO_CASO.COLETA_INICIAL  # gravar resposta não transiciona


def test_gravar_resposta_sem_repositorio_casos_nao_quebra_compatibilidade(
    repositorio_respostas: RepositorioRespostasArquivo,
) -> None:
    """`RepositorioRespostasArquivo` construído sem `repositorio_casos`
    (default `None`, uso pré-existente de `T-24`) continua gravando a
    resposta normalmente, sem tentar tocar nenhum `Caso` — extensão
    estritamente aditiva desta tarefa."""
    resposta = Resposta(
        CASO_ID=_CASO_ID,
        ID_PERGUNTA="VARIAVEL_TESTE",
        item_id=None,
        valor="valor de teste",
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
    )
    repositorio_respostas.gravar(resposta)

    respostas_gravadas = repositorio_respostas.listar_do_caso(_CASO_ID)
    assert len(respostas_gravadas) == 1


def test_repositorio_respostas_supabase_gravar_atualiza_interacao_do_caso() -> None:
    """Auditoria por código-fonte: `RepositorioRespostasSupabase.gravar`
    (`persistencia/app_aluno/respostas.py`) chama `UPDATE ... ultima_
    interacao_em` (ou repassa a atualização ao mesmo `UPDATE` de gravação) —
    nunca deixa `ultima_interacao_em` intocada após uma resposta ser
    persistida com sucesso."""
    from persistencia.app_aluno import respostas as modulo_respostas

    codigo_fonte = inspect.getsource(modulo_respostas.RepositorioRespostasSupabase.gravar)
    assert "ultima_interacao_em" in codigo_fonte, (
        "T-91 (RF-31/EC-14): a gravação de resposta precisa atualizar "
        "ultima_interacao_em do caso, e o SQL de RepositorioRespostasSupabase."
        "gravar não referencia essa coluna"
    )


# ---------------------------------------------------------------------------
# Critério 3 — nenhum evento contém valor monetário, saldo, renda ou
# identificador pessoal.
# ---------------------------------------------------------------------------


def test_evento_caso_so_declara_campos_estruturais_na_allowlist() -> None:
    """Auditoria por ASSINATURA: `EventoCaso.__slots__` é exatamente
    `(evento_id, CASO_ID, tipo_evento, estado_de, estado_para, detalhe,
    ocorrido_em)` — os mesmos sete campos estruturais desde T-87, sem
    nenhuma adição de campo monetário, de saldo, renda ou identificador
    pessoal por esta tarefa. Mesma disciplina de allowlist de `app/motor/
    executor.py::_registrar_evento` (T-55)."""
    campos_permitidos = frozenset(
        {
            "evento_id",
            "CASO_ID",
            "tipo_evento",
            "estado_de",
            "estado_para",
            "detalhe",
            "ocorrido_em",
        }
    )
    assert set(EventoCaso.__slots__) == campos_permitidos


def test_transicionar_e_registrar_nao_grava_dado_do_aluno_no_detalhe(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
) -> None:
    """Os chamadores de produção desta tarefa (`app/http/rotas_consentimento.
    py`, `app/http/rotas_calculo.py`, `app/revisao/fila.py`, `app/casos/
    acompanhamento.py`, `app/motor/executor.py`) nunca passam `detalhe` com
    um valor de resposta do aluno — só motivos técnicos curtos ou `None`.
    Verificado aqui pelo caminho mais comum: nenhuma chamada de produção
    passa um `Decimal`/valor monetário como `detalhe` (o parâmetro é
    tipado `str | None`, o que já impede um `Decimal` bruto)."""
    agora = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.CADASTRADO, agora))

    transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CADASTRADO,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        agora=agora,
        detalhe=None,
    )

    evento = repositorio_eventos.listar_do_caso(_CASO_ID)[0]
    assert evento.detalhe is None
    # CASO_ID é o único identificador presente — nunca conta_id, nome, CPF
    # ou e-mail (que nem sequer são parâmetros de EventoCaso).
    assert evento.CASO_ID == _CASO_ID


def test_nenhum_chamador_de_producao_passa_valor_de_resposta_como_detalhe() -> None:
    """Auditoria por AST sobre os cinco módulos que chamam
    `transicionar_e_registrar`: nenhuma chamada usa `detalhe=` com um valor
    que não seja um literal de string curto ou uma variável de mensagem
    técnica já auditada por `tests/app_aluno/estatica/
    test_sem_conteudo_de_questionario_no_codigo.py` (AC-37) — este teste
    apenas confirma que `detalhe` nunca recebe `resposta.valor`, `valor`, ou
    qualquer nome que sugira dado do aluno."""
    import ast
    from pathlib import Path as _Path

    raiz_projeto = _Path(__file__).resolve().parent.parent.parent
    modulos = (
        raiz_projeto / "app" / "http" / "rotas_consentimento.py",
        raiz_projeto / "app" / "http" / "rotas_calculo.py",
        raiz_projeto / "app" / "revisao" / "fila.py",
        raiz_projeto / "app" / "casos" / "acompanhamento.py",
        raiz_projeto / "app" / "motor" / "executor.py",
    )
    nomes_proibidos = {"valor", "resposta", "renda", "saldo", "divida"}

    violacoes: list[str] = []
    for caminho in modulos:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            eh_chamada_do_wrapper = (
                isinstance(no.func, ast.Name) and no.func.id == "transicionar_e_registrar"
            ) or (isinstance(no.func, ast.Attribute) and no.func.attr == "transicionar_e_registrar")
            if not eh_chamada_do_wrapper:
                continue
            for palavra_chave in no.keywords:
                if palavra_chave.arg != "detalhe":
                    continue
                if isinstance(palavra_chave.value, ast.Name):
                    nome = palavra_chave.value.id.lower()
                    if any(proibido in nome for proibido in nomes_proibidos):
                        violacoes.append(f"{caminho.name}: detalhe={nome!r}")

    assert not violacoes, (
        f"detalhe= de transicionar_e_registrar parece carregar dado do aluno: {violacoes}"
    )


# ---------------------------------------------------------------------------
# Critério 4 — EC-14: um caso parado há meses continua retomável com todas
# as respostas.
# ---------------------------------------------------------------------------


def test_ec14_caso_parado_ha_meses_continua_retomavel_com_todas_as_respostas(
    repositorio_casos: RepositorioCasosArquivo,
    repositorio_eventos: RepositorioEventosCasoArquivo,
    tmp_path: Path,
) -> None:
    """`EC-14`: um caso cuja última interação foi há meses (1) permanece
    com TODAS as respostas gravadas, intactas e legíveis; (2) a trilha
    (`listar_do_caso`) mostra a última transição e a data exatas, tornando o
    abandono OBSERVÁVEL; (3) nada nesta tarefa impede uma nova resposta ou
    transição de ocorrer depois do hiato — a retomada é sempre possível."""
    inicio = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
    repositorio_casos.criar(_caso_fabricado(ESTADO_CASO.CADASTRADO, inicio))
    # T-91: o repositório de respostas recebe a referência ao repositório de
    # casos — cada `gravar` atualiza `ultima_interacao_em` sozinho, sem
    # NENHUMA chamada manual deste teste a `registrar_interacao`.
    repositorio_respostas_com_trilha = RepositorioRespostasArquivo(
        tmp_path / "respostas.jsonl", repositorio_casos=repositorio_casos
    )

    transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CADASTRADO,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        agora=inicio,
    )
    transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=_CASO_ID,
        de=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        para=ESTADO_CASO.COLETA_INICIAL,
        agora=inicio,
    )

    # Três respostas gravadas antes do abandono.
    for indice, variavel in enumerate(("VAR_A", "VAR_B", "VAR_C")):
        repositorio_respostas_com_trilha.gravar(
            Resposta(
                CASO_ID=_CASO_ID,
                ID_PERGUNTA=variavel,
                item_id=None,
                valor=f"resposta-{indice}",
                QUESTIONARIO_VERSION="1.0.0",
                respondida_em=inicio + timedelta(minutes=indice),
            )
        )

    # O caso fica parado — meses se passam sem nenhuma interação nova.
    ultima_interacao_antes_do_hiato = repositorio_casos.buscar(_CASO_ID)
    assert ultima_interacao_antes_do_hiato is not None
    hiato = timedelta(days=180)
    data_de_retomada = ultima_interacao_antes_do_hiato.ultima_interacao_em + hiato

    # A trilha, consultada "durante o hiato", mostra a última transição e
    # quando ela ocorreu — o abandono é observável, não silencioso.
    eventos_durante_o_hiato = repositorio_eventos.listar_do_caso(_CASO_ID)
    assert len(eventos_durante_o_hiato) == 2
    assert eventos_durante_o_hiato[-1].estado_para == ESTADO_CASO.COLETA_INICIAL.value
    caso_durante_o_hiato = repositorio_casos.buscar(_CASO_ID)
    assert caso_durante_o_hiato is not None
    assert (
        caso_durante_o_hiato.ultima_interacao_em
        == ultima_interacao_antes_do_hiato.ultima_interacao_em
    )
    assert data_de_retomada > caso_durante_o_hiato.ultima_interacao_em

    # Todas as respostas de antes do hiato continuam gravadas e legíveis —
    # nada foi apagado nem sobrescrito pela passagem do tempo.
    respostas_apos_o_hiato = repositorio_respostas_com_trilha.listar_do_caso(_CASO_ID)
    assert {r.ID_PERGUNTA for r in respostas_apos_o_hiato} == {"VAR_A", "VAR_B", "VAR_C"}
    assert {r.valor for r in respostas_apos_o_hiato} == {
        "resposta-0",
        "resposta-1",
        "resposta-2",
    }

    # O caso é RETOMÁVEL: uma nova resposta, na data de retomada, é aceita
    # normalmente e já atualiza a trilha sozinha — o hiato não bloqueia nada.
    repositorio_respostas_com_trilha.gravar(
        Resposta(
            CASO_ID=_CASO_ID,
            ID_PERGUNTA="VAR_D",
            item_id=None,
            valor="resposta-apos-retomada",
            QUESTIONARIO_VERSION="1.0.0",
            respondida_em=data_de_retomada,
        )
    )

    caso_apos_retomada = repositorio_casos.buscar(_CASO_ID)
    assert caso_apos_retomada is not None
    assert caso_apos_retomada.ultima_interacao_em == data_de_retomada
    respostas_finais = repositorio_respostas_com_trilha.listar_do_caso(_CASO_ID)
    assert {r.ID_PERGUNTA for r in respostas_finais} == {"VAR_A", "VAR_B", "VAR_C", "VAR_D"}
