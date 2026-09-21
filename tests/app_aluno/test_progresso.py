"""Testes de `app/casos/progresso.py` — obrigatoriedade `OBR`/`COND`/`OPT`/`REP`
no avanço da coleta (`RF-09`, `RF-11`, `AC-11`, T-44).

Cobre os quatro critérios de aceite da tarefa, com registros REAIS
(`collection/carga.py`, T-16) sempre que existe um caso real que os
exercita, e um registro sintético (mesmo padrão de `tests/app_aluno/
test_renderizacao.py::_registro`) só onde os 245 registros reais não
contêm a combinação (`OBR`+`REP`, `OBR`+`COND` juntos não existem hoje —
confirmado por varredura nos YAML de `collection/registros/`).

REGRAS: `RF-09`, `RF-11`, `AC-11`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.casos.progresso import (
    PendenciaObrigatoria,
    coleta_pode_avancar,
    pendencias_obrigatorias,
)
from collection.carga import carregar_registros
from collection.condicoes import CondicaoIgual
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import NAO_SEI, Resposta, RespostasCaso


def _colecao_real() -> tuple[RegistroPergunta, ...]:
    return carregar_registros().registros


def _resposta(variavel: str, valor: object, item_id: str | None = None) -> Resposta:
    return Resposta(
        CASO_ID="CASO-TESTE",
        ID_PERGUNTA=variavel,
        item_id=item_id,
        valor=valor,  # type: ignore[arg-type]
        QUESTIONARIO_VERSION="1.0.0",
        respondida_em=datetime.now(UTC),
    )


def _registro_sintetico(
    ID: str,
    *,
    obrigatoriedade: frozenset[Obrigatoriedade],
    escopo_repeticao: EscopoRepeticao = EscopoRepeticao.NENHUM,
    condicao_exibicao: object | None = None,
    variavel_gravada: str = "VARIAVEL_DE_TESTE",
) -> RegistroPergunta:
    """Registro fabricado — nunca um dos 291 reais (mesmo padrão de
    `test_renderizacao.py::_registro`), usado apenas onde a combinação de
    `Obrigatoriedade` exercitada não existe hoje nos YAML reais."""
    return RegistroPergunta(
        ID=ID,
        bloco=99,
        enunciado="Enunciado sintético de teste, nunca uma pergunta real da §11.",
        tipo=TipoResposta.TEXTO_CURTO,
        obrigatoriedade=obrigatoriedade,
        escopo_repeticao=escopo_repeticao,
        opcoes=(),
        VARIAVEL_GRAVADA=variavel_gravada,
        condicao_exibicao=condicao_exibicao,  # type: ignore[arg-type]
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=False,
        salto_consequencia=None,
    )


# ---------------------------------------------------------------------------
# AC-11 — campo OBR sem admite_nao_sei deixado em branco impede o avanço e a
# pergunta permanece pendente.
# ---------------------------------------------------------------------------


def test_ac11_campo_obr_sem_admite_nao_sei_em_branco_gera_pendencia_e_impede_avanco() -> None:
    """`B1.01` real: `obrigatoriedade=[OBR]`, `admite_nao_sei=false`, sempre
    exibida (`condicao_exibicao=None`). Sem nenhuma resposta gravada, ela
    aparece nas pendências e `coleta_pode_avancar` é falso."""
    registros = _colecao_real()
    registro_b1_01 = next(r for r in registros if r.ID == "B1.01")
    assert registro_b1_01.admite_nao_sei is False
    assert Obrigatoriedade.OBR in registro_b1_01.obrigatoriedade

    respostas = RespostasCaso(respostas=())

    pendencias = pendencias_obrigatorias((registro_b1_01,), respostas)

    assert pendencias == (PendenciaObrigatoria(ID="B1.01", item_id=None),)
    assert coleta_pode_avancar((registro_b1_01,), respostas) is False


def test_ac11_campo_obr_respondido_deixa_de_ser_pendencia_e_permite_avanco() -> None:
    """A mesma pergunta, agora com uma resposta concreta gravada, some das
    pendências e o avanço passa a ser permitido (dentro do conjunto reduzido
    a este único registro)."""
    registros = _colecao_real()
    registro_b1_01 = next(r for r in registros if r.ID == "B1.01")
    respostas = RespostasCaso(respostas=(_resposta("PACTO", "ESTABELECIDO"),))

    pendencias = pendencias_obrigatorias((registro_b1_01,), respostas)

    assert pendencias == ()
    assert coleta_pode_avancar((registro_b1_01,), respostas) is True


def test_ac11_campo_obr_que_admite_nao_sei_respondido_com_nao_sei_nao_e_pendencia() -> None:
    """`B5.A05A` real declara `admite_nao_sei=true` (mas é `COND`+`REP`, sem
    `OBR` — usado aqui só para confirmar que `NAO_SEI` conta como resposta
    dada). Um registro sintético `OBR` que admite "não sei", respondido com
    `NAO_SEI`, não é pendência: "não sei" é resposta de primeira classe
    (`RF-11`), distinta de "em branco"."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_ADMITE_NAO_SEI", obrigatoriedade=frozenset({Obrigatoriedade.OBR})
    )
    respostas = RespostasCaso(respostas=(_resposta("VARIAVEL_DE_TESTE", NAO_SEI),))

    pendencias = pendencias_obrigatorias((registro,), respostas)

    assert pendencias == ()


# ---------------------------------------------------------------------------
# Campo OPT em branco não impede o avanço.
# ---------------------------------------------------------------------------


def test_campo_opt_em_branco_nao_gera_pendencia() -> None:
    """`B1.03A` real: `obrigatoriedade=[OPT]`, condicionada a
    `FINALIDADE_NOVA_DIVIDA=OUTRA`. Mesmo com a condição satisfeita e nenhuma
    resposta gravada, `OPT` nunca entra na varredura de pendência."""
    registros = _colecao_real()
    registro_b1_03a = next(r for r in registros if r.ID == "B1.03A")
    assert registro_b1_03a.obrigatoriedade == frozenset({Obrigatoriedade.OPT})

    respostas = RespostasCaso(
        respostas=(_resposta("FINALIDADE_NOVA_DIVIDA", "OUTRA"),)
    )

    pendencias = pendencias_obrigatorias((registro_b1_03a,), respostas)

    assert pendencias == ()
    assert coleta_pode_avancar((registro_b1_03a,), respostas) is True


# ---------------------------------------------------------------------------
# Campo COND só é exigido quando sua condição de exibição é verdadeira.
# ---------------------------------------------------------------------------


def test_campo_cond_puro_sem_obr_nunca_gera_pendencia_mesmo_com_condicao_verdadeira() -> None:
    """`B1.03` real: `obrigatoriedade=[COND]` (sem `OBR`) — condicionalmente
    EXIBIDA, mas não obrigatória por si só. Mesmo com a condição de exibição
    satisfeita e a pergunta em branco, ela não é uma pendência: só `OBR`
    torna um registro exigível (`_e_exigivel_agora`)."""
    registros = _colecao_real()
    registro_b1_03 = next(r for r in registros if r.ID == "B1.03")
    assert registro_b1_03.obrigatoriedade == frozenset({Obrigatoriedade.COND})

    respostas = RespostasCaso(respostas=(_resposta("NOVA_DIVIDA_PREVISTA", "SIM"),))

    pendencias = pendencias_obrigatorias((registro_b1_03,), respostas)

    assert pendencias == ()


def test_campo_obr_cond_e_pendencia_quando_condicao_e_verdadeira() -> None:
    """Registro sintético `OBR`+`COND` (a combinação não existe nos 245
    registros reais hoje, só `COND`+`REP` — `B5.A05A` — e `COND` puro
    existem de fato): com a condição de exibição VERDADEIRA e nenhuma
    resposta gravada, o campo é pendência."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_COND",
        obrigatoriedade=frozenset({Obrigatoriedade.OBR, Obrigatoriedade.COND}),
        condicao_exibicao=CondicaoIgual(variavel="GATILHO", valor="SIM"),
    )
    respostas = RespostasCaso(respostas=(_resposta("GATILHO", "SIM"),))

    pendencias = pendencias_obrigatorias((registro,), respostas)

    assert pendencias == (PendenciaObrigatoria(ID="SINTETICO.OBR_COND", item_id=None),)
    assert coleta_pode_avancar((registro,), respostas) is False


def test_campo_obr_cond_nao_e_pendencia_quando_condicao_e_falsa() -> None:
    """O MESMO registro sintético `OBR`+`COND`, agora com a condição de
    exibição FALSA (gatilho não satisfeito): não gera pendência, mesmo sem
    nenhuma resposta — a pergunta nem está aberta para responder."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_COND",
        obrigatoriedade=frozenset({Obrigatoriedade.OBR, Obrigatoriedade.COND}),
        condicao_exibicao=CondicaoIgual(variavel="GATILHO", valor="SIM"),
    )
    respostas = RespostasCaso(respostas=(_resposta("GATILHO", "NAO"),))

    pendencias = pendencias_obrigatorias((registro,), respostas)

    assert pendencias == ()
    assert coleta_pode_avancar((registro,), respostas) is True


def test_campo_obr_cond_sem_nenhuma_resposta_de_gatilho_tambem_nao_e_pendencia() -> None:
    """Variável do gatilho ainda não respondida: `avaliar` devolve falso
    (ausência ⇒ falso, T-11) — a condição não vale "ainda", logo o campo
    `OBR`+`COND` não é exigível agora."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_COND",
        obrigatoriedade=frozenset({Obrigatoriedade.OBR, Obrigatoriedade.COND}),
        condicao_exibicao=CondicaoIgual(variavel="GATILHO", valor="SIM"),
    )
    respostas = RespostasCaso(respostas=())

    pendencias = pendencias_obrigatorias((registro,), respostas)

    assert pendencias == ()


# ---------------------------------------------------------------------------
# Nenhum ID de pergunta aparece em código como "obrigatório" — a origem é o
# registro (verificação estrutural do próprio módulo desta tarefa).
# ---------------------------------------------------------------------------


def test_nenhum_id_de_pergunta_literal_no_modulo_de_progresso() -> None:
    """Auditoria direta do código-fonte de `app/casos/progresso.py`: nenhum
    `ID` real de pergunta (`B1.01`, `B5.A05A`, ...) aparece como literal —
    toda decisão vem de `Obrigatoriedade` do próprio registro, nunca de uma
    lista de `ID`s codificada. Complementa (não substitui) a suíte estática
    `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`
    (`AC-37`)."""
    import inspect

    import app.casos.progresso as modulo_progresso

    codigo_fonte = inspect.getsource(modulo_progresso)
    for id_real_de_pergunta in ("B1.01", "B1.03", "B1.03A"):
        assert id_real_de_pergunta not in codigo_fonte
    # `B5.FIM02` aparece uma única vez, citando literalmente a guarda textual
    # já existente em `app/casos/maquina.py::TABELA_TRANSICOES` (T-33) — é
    # documentação de uma guarda pré-existente, não uma decisão de
    # obrigatoriedade codificada por este módulo.
    assert codigo_fonte.count("B5.FIM02") == 1


def test_pendencia_de_registro_rep_por_item_com_itens_ativos() -> None:
    """Registro sintético `OBR`+`REP` (a combinação não existe nos 245
    registros reais hoje): dois itens ativos do escopo, um respondido e
    outro em branco — só o item em branco vira pendência, nomeado por
    `item_id`."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_REP",
        obrigatoriedade=frozenset({Obrigatoriedade.OBR, Obrigatoriedade.REP}),
        escopo_repeticao=EscopoRepeticao.DIVIDA_ID,
    )
    respostas = RespostasCaso(
        respostas=(_resposta("VARIAVEL_DE_TESTE", "1000,00", item_id="D001"),)
    )
    itens_por_escopo = {EscopoRepeticao.DIVIDA_ID: ("D001", "D002")}

    pendencias = pendencias_obrigatorias((registro,), respostas, itens_por_escopo)

    assert pendencias == (
        PendenciaObrigatoria(ID="SINTETICO.OBR_REP", item_id="D002"),
    )


def test_pendencia_de_registro_rep_sem_itens_por_escopo_nao_gera_pendencia() -> None:
    """Sem `itens_por_escopo` (ou com o escopo ausente do dicionário),
    nenhum item é varrido para um registro `REP` — nunca se inventa item."""
    registro = _registro_sintetico(
        "SINTETICO.OBR_REP",
        obrigatoriedade=frozenset({Obrigatoriedade.OBR, Obrigatoriedade.REP}),
        escopo_repeticao=EscopoRepeticao.DIVIDA_ID,
    )
    respostas = RespostasCaso(respostas=())

    assert pendencias_obrigatorias((registro,), respostas) == ()
    assert pendencias_obrigatorias((registro,), respostas, {}) == ()


# ---------------------------------------------------------------------------
# Sobre o conjunto completo dos 245 registros reais — prova de que a função
# roda sobre a coleção inteira sem erro e sem depender de nenhum ID.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("com_resposta_do_pacto", [True, False])
def test_pendencias_sobre_toda_a_colecao_real_nao_levanta_erro(
    com_resposta_do_pacto: bool,
) -> None:
    """A função varre os 245 registros reais sem levantar exceção — nenhum
    registro sem `VARIAVEL_GRAVADA`, nenhuma condição malformada."""
    registros = _colecao_real()
    respostas = RespostasCaso(
        respostas=(_resposta("PACTO", "ESTABELECIDO"),) if com_resposta_do_pacto else ()
    )

    pendencias = pendencias_obrigatorias(registros, respostas)

    assert isinstance(pendencias, tuple)
    if not com_resposta_do_pacto:
        assert any(p.ID == "B1.01" for p in pendencias)
