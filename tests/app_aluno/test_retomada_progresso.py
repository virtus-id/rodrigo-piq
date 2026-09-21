"""Testes de `app/casos/progresso.py::proxima_pergunta_nao_respondida` —
retomada na primeira pergunta não respondida (`RF-10`, `AC-01`, T-45).

Cobre os quatro critérios de aceite da tarefa, com registros REAIS
(`collection/carga.py`, T-16), no mesmo estilo de `tests/app_aluno/
test_progresso.py` (T-44).

REGRAS: `RF-10`, `AC-01`
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.casos.progresso import PendenciaObrigatoria, proxima_pergunta_nao_respondida
from collection.carga import carregar_registros
from collection.condicoes import avaliar
from collection.registro import EscopoRepeticao, RegistroPergunta, TipoResposta
from collection.respostas import Resposta, RespostasCaso


def _colecao_real() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _registros_dos_blocos_sem_repeticao(
    registros: tuple[RegistroPergunta, ...], *blocos: int
) -> tuple[RegistroPergunta, ...]:
    """Subconjunto de `registros` nos `blocos` dados, restrito a
    `escopo_repeticao == NENHUM` — usado para não depender de fichas/itens
    ainda não cadastrados nos testes de retomada por bloco."""
    return tuple(
        r for r in registros if r.bloco in blocos and r.escopo_repeticao == EscopoRepeticao.NENHUM
    )


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )


def _valor_trivial(registro: RegistroPergunta) -> object:
    """Um valor qualquer aceitável para o `TipoResposta` do registro — usado
    só para "preencher" perguntas abertas dos Blocos 1–3 num teste que não
    quer exercitar a fronteira `Decimal` nem a conversão de formulário
    (isso é assunto de `app/montagem/conversao.py`, T-38, fora daqui). Opção
    do próprio registro quando existe (garante domínio válido para
    `CondicaoIgual`/`CondicaoContem` a jusante); senão, um literal
    compatível com o tipo."""
    if registro.opcoes:
        return registro.opcoes[0].valor_interno or registro.opcoes[0].rotulo
    if registro.tipo in (TipoResposta.NUMERO, TipoResposta.MOEDA, TipoResposta.ESCALA_0_10):
        return "1"
    return "X"


def _responder_todas_as_abertas(
    registros: tuple[RegistroPergunta, ...],
) -> tuple[Resposta, ...]:
    """Responde, em ordem, toda pergunta ABERTA (condição verdadeira ou
    ausente) de `registros` — perguntas cuja condição nunca fica verdadeira
    dentro deste subconjunto permanecem em branco de propósito (não fazem
    parte do critério de teste; `AC-01` fala em "Blocos 1–3 respondidos", e
    uma pergunta condicional cujo gatilho está fora do conjunto respondido
    não é uma pergunta que o aluno teria visto)."""
    respostas: list[Resposta] = []
    pendentes = list(registros)
    avancou = True
    while avancou:
        avancou = False
        proximos_pendentes = []
        for registro in pendentes:
            respostas_correntes = RespostasCaso(respostas=tuple(respostas))
            aberta = registro.condicao_exibicao is None or avaliar(
                registro.condicao_exibicao, respostas_correntes
            )
            if not aberta or registro.VARIAVEL_GRAVADA is None:
                proximos_pendentes.append(registro)
                continue
            respostas.append(
                _resposta(registro.VARIAVEL_GRAVADA, _valor_trivial(registro))
            )
            avancou = True
        pendentes = proximos_pendentes
    return tuple(respostas)


# ---------------------------------------------------------------------------
# AC-01 — com Blocos 1–3 respondidos, a retomada aponta a primeira pergunta
# não respondida do Bloco 4.
# ---------------------------------------------------------------------------


def test_ac01_blocos_1_a_3_respondidos_retoma_na_primeira_pergunta_do_bloco_4() -> None:
    """Todas as perguntas ABERTAS dos Blocos 1–3 (sem escopo de repetição,
    para não depender de fichas/itens ainda não cadastrados) são respondidas;
    nenhuma do Bloco 4 é tocada. A retomada aponta `B4.01` — `OBR`, sem
    condição de exibição, a primeira pergunta real do Bloco 4 na ordem de
    carga (`collection/carga.py`)."""
    registros = _colecao_real()
    blocos_1_a_3_sem_repeticao = _registros_dos_blocos_sem_repeticao(registros, 1, 2, 3)
    respostas_dadas = _responder_todas_as_abertas(blocos_1_a_3_sem_repeticao)
    respostas = RespostasCaso(respostas=respostas_dadas)

    # Confirma a premissa do teste: nenhuma resposta de Bloco 4 foi gravada.
    variaveis_de_bloco_4 = {
        r.VARIAVEL_GRAVADA for r in registros if r.bloco == 4 and r.VARIAVEL_GRAVADA
    }
    assert not any(r.ID_PERGUNTA in variaveis_de_bloco_4 for r in respostas_dadas)

    proxima = proxima_pergunta_nao_respondida(registros, respostas)

    assert proxima == PendenciaObrigatoria(ID="B4.01", item_id=None)


def test_ac01_apos_responder_b4_01_a_retomada_avanca_para_a_proxima_do_bloco_4() -> None:
    """Gravando também `B4.01`, a retomada deixa de apontar para ela — a
    função nunca pede de novo um campo já respondido."""
    registros = _colecao_real()
    blocos_1_a_3_sem_repeticao = _registros_dos_blocos_sem_repeticao(registros, 1, 2, 3)
    respostas_dadas = list(_responder_todas_as_abertas(blocos_1_a_3_sem_repeticao))
    respostas_dadas.append(_resposta("DINHEIRO_DISPONIVEL_EXISTE", "SIM"))
    respostas = RespostasCaso(respostas=tuple(respostas_dadas))

    proxima = proxima_pergunta_nao_respondida(registros, respostas)

    assert proxima is not None
    assert proxima.ID != "B4.01"


# ---------------------------------------------------------------------------
# A retomada funciona de outro dispositivo, com sessão nova — a função é pura
# sobre (registros, respostas): o mesmo par sempre produz o mesmo resultado,
# qualquer que seja a "sessão" que o chamou (nenhum parâmetro de sessão
# HTTP existe na assinatura).
# ---------------------------------------------------------------------------


def test_retomada_e_pura_mesmo_par_registros_respostas_produz_o_mesmo_resultado() -> None:
    """Chamar a função duas vezes com o MESMO snapshot de respostas — como
    aconteceria em duas requisições de dois dispositivos/sessões distintos
    consultando o mesmo `CASO_ID` — devolve exatamente o mesmo resultado.
    A função não recebe nem lê nenhum dado de sessão/cookie/requisição."""
    registros = _colecao_real()
    respostas = RespostasCaso(respostas=(_resposta("PACTO", "ESTABELECIDO"),))

    primeira_chamada = proxima_pergunta_nao_respondida(registros, respostas)
    segunda_chamada = proxima_pergunta_nao_respondida(registros, respostas)

    assert primeira_chamada == segunda_chamada


# ---------------------------------------------------------------------------
# Pergunta cuja condição virou falsa depois de respondida não é reexibida
# nem apagada.
# ---------------------------------------------------------------------------


def test_pergunta_cond_respondida_cuja_condicao_virou_falsa_nao_e_reexibida() -> None:
    """`B3.S02` real (`COND`, escopo `VINCULO_ID`, `REGIME_MARGEM`):
    condicionada a `VINCULO_CONSIGNAVEL != NAO`. Respondida para o item
    `V001` enquanto a condição valia (vínculo consignável); depois disso,
    `VINCULO_CONSIGNAVEL` muda para `NAO` (condição vira falsa). A retomada
    NUNCA aponta de volta para `B3.S02`/`V001` — nem a resposta antiga é
    apagada (ela continua presente em `respostas`, e o teste verifica isso
    explicitamente)."""
    registros = _colecao_real()
    registro_b3_s02 = next(r for r in registros if r.ID == "B3.S02")
    assert registro_b3_s02.escopo_repeticao == EscopoRepeticao.VINCULO_ID
    assert registro_b3_s02.VARIAVEL_GRAVADA == "REGIME_MARGEM"

    resposta_antiga = _resposta("REGIME_MARGEM", "CLT", item_id="V001")
    respostas = RespostasCaso(
        respostas=(
            _resposta("VINCULO_CONSIGNAVEL", "NAO", item_id="V001"),  # condição agora falsa
            resposta_antiga,
        )
    )

    # A resposta antiga permanece gravada — nunca é apagada por esta função.
    assert resposta_antiga in respostas.respostas

    proxima = proxima_pergunta_nao_respondida(
        (registro_b3_s02,), respostas, {EscopoRepeticao.VINCULO_ID: ("V001",)}
    )

    assert proxima is None


def test_pergunta_cond_ainda_verdadeira_e_nao_respondida_e_apontada() -> None:
    """Controle do teste acima: com a MESMA condição ainda verdadeira
    (`VINCULO_CONSIGNAVEL=SIM`) e sem nenhuma resposta para `B3.S02`/`V001`,
    a retomada aponta para ela — a ausência de reexibição do teste anterior
    é por causa da condição falsa, não de algum bug que sempre a
    esconderia."""
    registros = _colecao_real()
    registro_b3_s02 = next(r for r in registros if r.ID == "B3.S02")

    respostas = RespostasCaso(
        respostas=(_resposta("VINCULO_CONSIGNAVEL", "SIM", item_id="V001"),)
    )

    proxima = proxima_pergunta_nao_respondida(
        (registro_b3_s02,), respostas, {EscopoRepeticao.VINCULO_ID: ("V001",)}
    )

    assert proxima == PendenciaObrigatoria(ID="B3.S02", item_id="V001")


# ---------------------------------------------------------------------------
# A retomada respeita a ordem dos blocos e o escopo de repetição dos itens
# já criados.
# ---------------------------------------------------------------------------


def test_retomada_respeita_ordem_dos_blocos_nao_pula_para_bloco_posterior() -> None:
    """Com uma pergunta do Bloco 1 em branco e outra do Bloco 2 respondida,
    a retomada aponta a do Bloco 1 primeiro — nunca pula para um bloco
    posterior enquanto um anterior tem pendência aberta."""
    registros = _colecao_real()
    registro_b1_01 = next(r for r in registros if r.ID == "B1.01")
    registro_b2_01 = next(r for r in registros if r.ID == "B2.01")
    assert registro_b1_01.VARIAVEL_GRAVADA is not None
    assert registro_b2_01.VARIAVEL_GRAVADA is not None

    respostas = RespostasCaso(
        respostas=(_resposta(registro_b2_01.VARIAVEL_GRAVADA, "X"),)
    )

    proxima = proxima_pergunta_nao_respondida((registro_b1_01, registro_b2_01), respostas)

    assert proxima == PendenciaObrigatoria(ID="B1.01", item_id=None)


def test_retomada_escopo_de_repeticao_aponta_o_primeiro_item_ja_criado_em_branco() -> None:
    """Registro `COND`/`VINCULO_ID` (`B3.S02`) com dois vínculos já criados
    (`V001`, `V002`), ambos consignáveis: `V001` respondido, `V002` ainda em
    branco. A retomada aponta `V002` — o escopo de repetição dos itens JÁ
    CRIADOS é respeitado (nenhum item inventado, nenhum item ignorado)."""
    registros = _colecao_real()
    registro_b3_s02 = next(r for r in registros if r.ID == "B3.S02")

    respostas = RespostasCaso(
        respostas=(
            _resposta("VINCULO_CONSIGNAVEL", "SIM", item_id="V001"),
            _resposta("REGIME_MARGEM", "CLT", item_id="V001"),
            _resposta("VINCULO_CONSIGNAVEL", "SIM", item_id="V002"),
        )
    )

    proxima = proxima_pergunta_nao_respondida(
        (registro_b3_s02,),
        respostas,
        {EscopoRepeticao.VINCULO_ID: ("V001", "V002")},
    )

    assert proxima == PendenciaObrigatoria(ID="B3.S02", item_id="V002")


def test_retomada_sem_itens_por_escopo_nao_aponta_pergunta_rep() -> None:
    """Sem `itens_por_escopo` (nenhum item cadastrado ainda), um registro
    repetível por item nunca é apontado como próxima pergunta — não há
    ficha para responder, e a função não inventa item."""
    registro_b3_s02 = next(r for r in _colecao_real() if r.ID == "B3.S02")
    respostas = RespostasCaso(respostas=(_resposta("VINCULO_CONSIGNAVEL", "SIM", item_id="V001"),))

    assert proxima_pergunta_nao_respondida((registro_b3_s02,), respostas) is None
    assert proxima_pergunta_nao_respondida((registro_b3_s02,), respostas, {}) is None


# ---------------------------------------------------------------------------
# Toda a coleção real — a função varre sem erro e devolve `None` quando tudo
# está respondido.
# ---------------------------------------------------------------------------


def test_retomada_devolve_none_quando_nao_ha_nenhuma_pergunta_aberta_em_branco() -> None:
    """Conjunto reduzido a uma única pergunta `OPT` (`B1.03A`, condicionada a
    `FINALIDADE_NOVA_DIVIDA=OUTRA`), já respondida: nada pendente, `None`."""
    registro_b1_03a = next(r for r in _colecao_real() if r.ID == "B1.03A")
    assert registro_b1_03a.VARIAVEL_GRAVADA == "FINALIDADE_NOVA_DIVIDA_OUTRA"
    respostas = RespostasCaso(
        respostas=(
            _resposta("FINALIDADE_NOVA_DIVIDA", "OUTRA"),
            _resposta("FINALIDADE_NOVA_DIVIDA_OUTRA", "X"),
        )
    )

    assert proxima_pergunta_nao_respondida((registro_b1_03a,), respostas) is None
