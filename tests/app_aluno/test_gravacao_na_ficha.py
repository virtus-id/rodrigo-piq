"""`T-199` — a gravação avalia a condição no MESMO item em que a retomada
ofereceu a pergunta (`RF-05`, `RF-52`).

Achado C4 do QA: com a condição avaliada só no nível do caso, a retomada
passou a oferecer `B5.C02` para `D001` (`POSSUI_PARCELA_DEFINIDA=SIM` em
`D001`), mas `POST /resposta` recusava a gravação com
`ErroPerguntaNaoAberta` — o aluno via a pergunta e não conseguia respondê-la.

REGRAS: `RF-05`, `RF-52`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.http.rotas_coleta import ErroPerguntaNaoAberta, _exigir_pergunta_aberta
from collection.condicoes import CondicaoIgual
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import Resposta, RespostasCaso

_REGISTRO_DA_FICHA = RegistroPergunta(
    ID="T199.PARCELA",
    bloco=5,
    enunciado="x",
    tipo=TipoResposta.MOEDA,
    obrigatoriedade=frozenset({Obrigatoriedade.COND, Obrigatoriedade.REP}),
    escopo_repeticao=EscopoRepeticao.DIVIDA_ID,
    opcoes=(),
    VARIAVEL_GRAVADA="PARCELA_TESTE",
    condicao_exibicao=CondicaoIgual(variavel="POSSUI_PARCELA_TESTE", valor="SIM"),
    interpolacoes=(),
    validacoes_cruzadas=(),
    origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
    admite_nao_sei=True,
    salto_consequencia=None,
)

_RESPOSTAS = RespostasCaso(
    respostas=(
        Resposta(
            CASO_ID="CASO-T199",
            ID_PERGUNTA="POSSUI_PARCELA_TESTE",
            item_id="D001",
            valor="SIM",
            QUESTIONARIO_VERSION="T199",
            respondida_em=datetime(2026, 9, 29, tzinfo=UTC),
        ),
    )
)


def test_t199_gravacao_aceita_pergunta_aberta_no_proprio_item() -> None:
    _exigir_pergunta_aberta(_REGISTRO_DA_FICHA, _RESPOSTAS, "D001")


def test_t199_gravacao_recusa_no_item_em_que_a_condicao_e_falsa() -> None:
    with pytest.raises(ErroPerguntaNaoAberta):
        _exigir_pergunta_aberta(_REGISTRO_DA_FICHA, _RESPOSTAS, "D002")
