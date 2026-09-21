"""Testes de `app/casos/acompanhamento.py::acao_id_de`/`item_id_do_bloco_11`
— `RF-27`, `RF-33`, `AC-50`, T-83, atualizados por `T-119A`.

**A dependência externa CHEGOU (`T-119A`).** Quando `T-83` escreveu este
arquivo, `engine.gates.AcaoRequerida` não publicava `ACAO_ID`, e dois testes
daqui eram a SENTINELA disso: afirmavam a ausência do campo e diziam, no
próprio texto, *"se este assert falhar, a dependência externa chegou e `T-83`
precisa ser revisitada"*. A Rodada 2 do slug `motor-calculo` entregou o campo
— `AcaoRequerida.__dataclass_fields__` hoje inclui `ACAO_ID` e `TIPO_ACAO` —,
os dois testes falharam exatamente como projetado, e `T-119A` é a revisita que
eles mandaram fazer. Onde antes se afirmava ausência, agora se exercita o
comportamento real com o campo presente: `acao_id_de` sobre uma
`AcaoRequerida` de verdade DEVOLVE o `ACAO_ID` publicado pelo motor, e
`item_id_do_bloco_11` devolve esse mesmo valor — nunca o `DIVIDA_ID`, que é a
garantia que `T-83` sempre quis e que só agora pode ser verificada no caminho
de sucesso com dado real.

Nenhum teste foi removido, pulado ou enfraquecido: os dois viraram asserções
MAIS fortes (comportamento observável sobre dado real, em vez de ausência de
atributo), e os que já provavam o caminho de sucesso com objeto de teste
continuam intactos — eles cobrem casos que a `AcaoRequerida` real não produz
hoje (ação sem `DIVIDA_ID`, `ACAO_ID` de tipo inesperado), e por isso seguem
sendo a única forma de exercitá-los.

Cobertura dos quatro critérios de aceite de `T-83`, depois de `T-119A`:

  1. e 2. (nenhum caminho exige `DIVIDA_ID`) são provados com uma
     `AcaoRequerida` REAL (mesma técnica de `tests/app_aluno/test_acoes.py`,
     T-74): `acao_id_de` devolve o `ACAO_ID` do motor, distinto do
     `DIVIDA_ID` da mesma ação — prova direta de que a função nunca caiu de
     volta no identificador errado.
  3. (o `item_id` da `Resposta` do Bloco 11 é o `ACAO_ID`) é provado tanto
     sobre a ação REAL quanto sobre o objeto de teste — este último cobre a
     ação SEM `DIVIDA_ID` (a ação de economia, `OQ-15`), caminho que o motor
     ainda não emite a partir dos gates deste cenário.
  4. `AC-50` propriamente dito ("ação sem `DIVIDA_ID` é exibida e gravada")
     — o caminho de SUCESSO ponta a ponta (exibição + gravação) é `T-89`
     (`tests/app_aluno/test_acao_sem_divida.py`). Este arquivo prova a
     INTERFACE (`acao_id_de`/`item_id_do_bloco_11`) que `T-89` consome.

`ErroAcaoIdAusenteDoMotor` continua existindo e continua testada — ela nunca
foi uma marca de "campo ainda não entregue", e sim a fronteira ruidosa contra
um contrato incompatível. O teste que a exercita hoje é o do `ACAO_ID` de tipo
inesperado, abaixo.

REGRAS: RF-27, RF-33, AC-50
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from app.casos.acompanhamento import (
    ErroAcaoIdAusenteDoMotor,
    acao_id_de,
    item_id_do_bloco_11,
)
from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from engine.gates import AcaoRequerida
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_PARAMETROS_VERSAO = "1.0.1"
_DIVIDA_ID_ELEGIVEL = "D-CASO-COMPLETO-ELEGIVEL"

# Mesmo valor de tests/app_aluno/test_acoes.py (T-74): saldo alto o bastante
# para a dívida bloqueada por gate nunca ser quitada dentro do horizonte de
# simulação — sem isso o motor recusaria com `ErroOrdemInconsistente`.
_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE = converter_para_dinheiro("10.000.000,00")


def _snapshot_com_acao_real() -> SnapshotOrdem:
    """Mesma técnica de `tests/app_aluno/test_acoes.py::
    _snapshot_com_gates_2_e_3_disparados` — um `SnapshotOrdem` REAL, com
    `ORDEM_ACOES` não vazia, produzido por `calcular_plano` de verdade."""
    caso = caso_completo()
    divida_bloqueada = replace(
        montar_divida(caso.respostas, caso.DIVIDA_ID),
        SALDO_DEVEDOR_ATUAL=_SALDO_BLOQUEADA_INQUITAVEL_NO_HORIZONTE,
        RISCO_MATERIAL_IMINENTE=True,
    )
    respostas_segunda_divida = montar_respostas_caso(DIVIDA_ID=_DIVIDA_ID_ELEGIVEL)
    divida_elegivel = montar_divida(respostas_segunda_divida, _DIVIDA_ID_ELEGIVEL)

    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_bloqueada, divida_elegivel),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


@dataclass(frozen=True, slots=True)
class _AcaoRequeridaComAcaoId:
    """Objeto de TESTE, não `engine.gates.AcaoRequerida`. Desde `T-119A` o
    tipo real do motor TEM `ACAO_ID` — este objeto continua existindo porque
    ele permite construir combinações que o motor não emite a partir dos
    gates deste cenário: em particular uma ação SEM `DIVIDA_ID` (a ação de
    economia, `OQ-15`). Ele nunca substituiu a prova com dado real, que agora
    existe logo acima; é o complemento dela para o caso de borda."""

    ACAO_ID: str
    DIVIDA_ID: str | None = None


def test_acao_id_de_devolve_o_acao_id_publicado_pelo_motor() -> None:
    """Critérios 2 e 4 de `T-83`, exercitados com o campo PRESENTE
    (`T-119A`): sobre uma `AcaoRequerida` REAL — que tem `DIVIDA_ID`
    disponível e um `ACAO_ID` distinto dele —, `acao_id_de` devolve
    exatamente o `ACAO_ID` publicado pelo motor, e NUNCA o `DIVIDA_ID`.

    Este é o teste que, enquanto `engine.gates.AcaoRequerida` não publicava
    `ACAO_ID`, afirmava a ausência do campo e a falha ruidosa da fronteira.
    A Rodada 2 de `motor-calculo` entregou o campo; a asserção passou a ser
    sobre o comportamento real, que é mais forte: antes se provava que a
    função não inventava um identificador, agora se prova que ela lê o
    identificador CERTO."""
    snapshot = _snapshot_com_acao_real()
    assert len(snapshot.ORDEM_ACOES) > 0, "o caso de prova precisa de fato disparar um gate"
    acao_real = snapshot.ORDEM_ACOES[0]
    assert isinstance(acao_real, AcaoRequerida)

    acao_id = acao_id_de(acao_real)

    assert acao_id == acao_real.ACAO_ID
    assert isinstance(acao_id, str) and acao_id != ""
    # O ponto que `T-83` sempre quis provar e só agora pode ser verificado no
    # caminho de sucesso: a ação real TEM `DIVIDA_ID`, e o `ACAO_ID` não é
    # ele — nenhuma queda silenciosa de volta no identificador da dívida.
    assert acao_real.DIVIDA_ID is not None
    assert acao_id != acao_real.DIVIDA_ID


def test_item_id_do_bloco_11_devolve_o_acao_id_da_acao_real() -> None:
    """`item_id_do_bloco_11` é chamada fina sobre `acao_id_de` — sobre a ação
    REAL, devolve o mesmo `ACAO_ID`, nunca o `DIVIDA_ID` que a ação também
    carrega. É a chave de vínculo da `Resposta` do Bloco 11 (`AC-50`),
    verificada agora contra o contrato entregue pelo motor."""
    snapshot = _snapshot_com_acao_real()
    acao_real = snapshot.ORDEM_ACOES[0]
    assert acao_real.DIVIDA_ID is not None  # a ação real TEM DIVIDA_ID disponível

    item_id = item_id_do_bloco_11(acao_real)

    assert item_id == acao_real.ACAO_ID
    assert item_id != acao_real.DIVIDA_ID


def test_erro_de_acao_id_ausente_continua_nomeando_a_fronteira() -> None:
    """`ErroAcaoIdAusenteDoMotor` nunca foi uma marca de "campo ainda não
    entregue" — é a fronteira ruidosa contra um objeto que não cumpre o
    contrato. Ela continua nomeando o campo e a origem da regra (`T-83`,
    `OQ-10`) quando um objeto sem `ACAO_ID` chega até ela.

    O objeto usado aqui é construído no teste: depois de `T-119A` nenhuma
    `AcaoRequerida` real produz esta situação, e é justamente por isso que
    ela precisa continuar coberta — a fronteira não pode apodrecer sem
    ninguém notar."""

    @dataclass(frozen=True, slots=True)
    class _AcaoSemAcaoId:
        DIVIDA_ID: str | None = "D999"

    with pytest.raises(ErroAcaoIdAusenteDoMotor) as excinfo:
        acao_id_de(_AcaoSemAcaoId())  # type: ignore[arg-type]

    mensagem = str(excinfo.value)
    assert "ACAO_ID" in mensagem
    assert "T-83" in mensagem
    assert "OQ-10" in mensagem


def test_item_id_do_bloco_11_le_acao_id_quando_o_campo_existe() -> None:
    """Critério 3: o `item_id` da resposta do Bloco 11 é o `ACAO_ID` — sobre
    um objeto que publica `ACAO_ID`, `item_id_do_bloco_11` devolve
    exatamente esse valor, e não o de `DIVIDA_ID`."""
    acao = _AcaoRequeridaComAcaoId(ACAO_ID="A001", DIVIDA_ID="D999")

    # `_AcaoRequeridaComAcaoId` não É `AcaoRequerida` — é DELIBERADAMENTE um
    # tipo próprio de teste (ver docstring da classe): `mypy --strict` recusa
    # a passagem por tipo nominal, exatamente o comportamento correto. A
    # prova equivalente sobre o tipo REAL do motor é
    # `test_item_id_do_bloco_11_devolve_o_acao_id_da_acao_real`, acima.
    assert item_id_do_bloco_11(acao) == "A001"  # type: ignore[arg-type]


def test_item_id_do_bloco_11_le_acao_id_sem_divida_associada() -> None:
    """Critérios 1 e 2: uma ação SEM `DIVIDA_ID` (a futura ação de economia,
    `OQ-15`) tem seu `item_id` resolvido normalmente por `ACAO_ID` — nenhum
    caminho de código exige `DIVIDA_ID` presente."""
    acao_sem_divida = _AcaoRequeridaComAcaoId(ACAO_ID="A007", DIVIDA_ID=None)

    assert item_id_do_bloco_11(acao_sem_divida) == "A007"  # type: ignore[arg-type]


def test_acao_id_de_nao_aceita_valor_de_tipo_inesperado() -> None:
    """Defensivo: se `ACAO_ID` existir mas não for `str`, a função ainda
    falha ruidosamente em vez de devolver um valor não confiável como
    identificador."""

    @dataclass(frozen=True, slots=True)
    class _AcaoComAcaoIdNaoString:
        ACAO_ID: int

    with pytest.raises(ErroAcaoIdAusenteDoMotor):
        acao_id_de(_AcaoComAcaoIdNaoString(ACAO_ID=123))  # type: ignore[arg-type]
