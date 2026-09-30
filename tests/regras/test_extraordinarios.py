"""Recursos extraordinários na projeção — §15 · RF-70 a RF-76 · `DE-02` ·
T-156, T-161, T-165 (plano `R9M.9`).

Três blocos:

- `selecionar_aportes` isolada (`T-156`): partição por item, motivos, trava
  de déficit de `RF-74` (decisão do produto de 2026-09-30).
- `calcular_plano` ponta a ponta (`T-161`, `T-165`): estado montado à mão
  sobre `gab_b.json` (capacidade positiva, dívida com saldo conhecido
  injetado) e `gab_a.json` (déficit). Asserção sempre na saída do motor.
- Auditoria estática de `engine/extraordinarios.py` (`AC-126`, `RF-72`,
  `AC-130`).

Tolerância zero em tudo (`assertar_exato`).
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from engine.ataque_imediato import calcular_EXTRAORDINARIOS_RECOMENDADOS
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    JANELA_RECURSO_EXTRAORDINARIO,
    EstadoFinanceiro,
    RecursoExtraordinario,
)
from engine.extraordinarios import (
    MOTIVO_NAO_PROJETADO,
    PROJECAO_VAZIA,
    AporteProjetado,
    ItemNaoProjetado,
    aportes_por_mes,
    selecionar_aportes,
)
from engine.motor import calcular_plano
from engine.precisao import dinheiro
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO, DinheiroTalvez
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_a, carregar_gab_b

RAIZ = Path(__file__).resolve().parent.parent.parent
J = JANELA_RECURSO_EXTRAORDINARIO
C = CERTEZA_RECURSO_EXTRAORDINARIO
SO_CONFIRMADO = frozenset({C.CONFIRMADO})
TODAS = frozenset(C)


def _recurso(
    item_id: str,
    valor: DinheiroTalvez | int = 5000,
    *,
    janela: JANELA_RECURSO_EXTRAORDINARIO = J.QUATRO_A_SEIS_MESES,
    certeza: CERTEZA_RECURSO_EXTRAORDINARIO = C.CONFIRMADO,
) -> RecursoExtraordinario:
    return RecursoExtraordinario(
        ITEM_ID=item_id,
        VALOR_RECURSO_EXTRAORDINARIO=dinheiro(valor) if isinstance(valor, int) else valor,
        JANELA_RECURSO_EXTRAORDINARIO=janela,
        CERTEZA_RECURSO_EXTRAORDINARIO=certeza,
    )


# ---------------------------------------------------------------------------
# T-156 — selecionar_aportes isolada
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_particao_cada_item_em_exatamente_uma_tupla() -> None:
    """`RF-73`: origem única — todo `ITEM_ID` de entrada aparece em
    exatamente uma das duas tuplas."""
    recursos = (
        _recurso("A", janela=J.UM_A_TRES_MESES),
        _recurso("B", janela=J.ATE_30D),
        _recurso("C", certeza=C.PROVAVEL),
        _recurso("D", DESCONHECIDO),
        _recurso("E", janela=J.NAO_SEI),
        _recurso("F", janela=J.SETE_A_DOZE_MESES),
    )

    aportes, nao_projetados = selecionar_aportes(
        recursos, certezas=SO_CONFIRMADO, RESULTADO_MENSAL_ATUAL=dinheiro(100)
    )

    ids = [a.ITEM_ID for a in aportes] + [n.ITEM_ID for n in nao_projetados]
    assertar_exato(sorted(ids), ["A", "B", "C", "D", "E", "F"])


@pytest.mark.regra
def test_item_id_duplicado_levanta_value_error() -> None:
    """`RF-75`: duplicata é bug de montagem, nunca soma silenciosa."""
    with pytest.raises(ValueError, match="ITEM_ID repetido"):
        selecionar_aportes(
            (_recurso("A"), _recurso("A", janela=J.UM_A_TRES_MESES)),
            certezas=SO_CONFIRMADO,
            RESULTADO_MENSAL_ATUAL=dinheiro(100),
        )


@pytest.mark.regra
def test_dois_itens_no_mesmo_mes_sao_dois_aportes_somados_so_por_mes() -> None:
    """`RF-75`: itens nunca somados entre si — `aportes_por_mes` é a única
    soma, por mês."""
    aportes, _ = selecionar_aportes(
        (_recurso("A", 1000), _recurso("B", 2500), _recurso("C", 700, janela=J.UM_A_TRES_MESES)),
        certezas=SO_CONFIRMADO,
        RESULTADO_MENSAL_ATUAL=dinheiro(100),
    )

    assertar_exato(
        aportes,
        (
            AporteProjetado(ITEM_ID="A", mes=6, VALOR_DESTINADO=dinheiro(1000)),
            AporteProjetado(ITEM_ID="B", mes=6, VALOR_DESTINADO=dinheiro(2500)),
            AporteProjetado(ITEM_ID="C", mes=3, VALOR_DESTINADO=dinheiro(700)),
        ),
    )
    assertar_exato(dict(aportes_por_mes(aportes)), {6: dinheiro(3500), 3: dinheiro(700)})


@pytest.mark.regra
@pytest.mark.parametrize(
    ("recurso", "motivo"),
    [
        (_recurso("X", certeza=C.PROVAVEL), MOTIVO_NAO_PROJETADO.CERTEZA_FORA_DO_CONJUNTO),
        (_recurso("X", certeza=C.POSSIVEL), MOTIVO_NAO_PROJETADO.CERTEZA_FORA_DO_CONJUNTO),
        (_recurso("X", DESCONHECIDO), MOTIVO_NAO_PROJETADO.VALOR_DESCONHECIDO),
        (_recurso("X", janela=J.NAO_SEI), MOTIVO_NAO_PROJETADO.JANELA_NAO_SEI),
        (_recurso("X", janela=J.ATE_30D), MOTIVO_NAO_PROJETADO.ATAQUE_DE_HOJE),
    ],
)
def test_motivos_de_nao_projecao(
    recurso: RecursoExtraordinario, motivo: MOTIVO_NAO_PROJETADO
) -> None:
    """`RF-71`, `EC-51`, `EC-52` (nunca `0`), `RF-73`/`AC-130` (`ATE_30D` é
    ataque de hoje)."""
    aportes, nao_projetados = selecionar_aportes(
        (recurso,), certezas=SO_CONFIRMADO, RESULTADO_MENSAL_ATUAL=dinheiro(100)
    )

    assertar_exato(aportes, ())
    assertar_exato(nao_projetados, (ItemNaoProjetado(ITEM_ID="X", motivo=motivo),))


@pytest.mark.regra
def test_janela_define_o_ultimo_mes() -> None:
    """`OQ-47`/`AC-129`: `1_3M`→3, `4_6M`→6, `7_12M`→12."""
    aportes, _ = selecionar_aportes(
        (
            _recurso("A", janela=J.UM_A_TRES_MESES),
            _recurso("B", janela=J.QUATRO_A_SEIS_MESES),
            _recurso("C", janela=J.SETE_A_DOZE_MESES),
        ),
        certezas=SO_CONFIRMADO,
        RESULTADO_MENSAL_ATUAL=dinheiro(0),
    )

    assertar_exato(tuple(a.mes for a in aportes), (3, 6, 12))


@pytest.mark.regra
def test_deficit_estrutural_trava_todo_item_projetavel() -> None:
    """`RF-74`/`RF-76` — decisão do produto (2026-09-30): com
    `RESULTADO_MENSAL_ATUAL < 0` nenhum aporte é destinado."""
    aportes, nao_projetados = selecionar_aportes(
        (_recurso("A", janela=J.UM_A_TRES_MESES), _recurso("B", 90000)),
        certezas=SO_CONFIRMADO,
        RESULTADO_MENSAL_ATUAL=dinheiro("-0.01"),
    )

    assertar_exato(aportes, ())
    assertar_exato(
        nao_projetados,
        (
            ItemNaoProjetado(ITEM_ID="A", motivo=MOTIVO_NAO_PROJETADO.TRAVA_DEFICIT_ESTRUTURAL),
            ItemNaoProjetado(ITEM_ID="B", motivo=MOTIVO_NAO_PROJETADO.TRAVA_DEFICIT_ESTRUTURAL),
        ),
    )


@pytest.mark.regra
@pytest.mark.parametrize("resultado", ["0", "0.01", "5000"])
def test_fora_da_trava_valor_destinado_e_o_valor_liquido(resultado: str) -> None:
    """`RF-74`/`AC-126`: fora da trava, `VALOR_DESTINADO = VALOR` (≤ valor)."""
    aportes, _ = selecionar_aportes(
        (_recurso("A", 1234),), certezas=SO_CONFIRMADO, RESULTADO_MENSAL_ATUAL=dinheiro(resultado)
    )

    assertar_exato(aportes[0].VALOR_DESTINADO, dinheiro(1234))
    assert aportes[0].VALOR_DESTINADO <= dinheiro(1234)


# ---------------------------------------------------------------------------
# AC-126, RF-72, AC-130 — auditoria estática do módulo
# ---------------------------------------------------------------------------
@pytest.mark.regra
def test_modulo_sem_parametro_sem_tipo_sem_aprovacao() -> None:
    """`AC-126`: nenhum parâmetro `P_` no módulo nem na fonte (contagem
    igual entre 1.0.1 e 1.0.2); `RF-72`: o tipo do recurso não é lido;
    `AC-130`: nenhum aporte depende de aprovação do aluno."""
    texto = (RAIZ / "engine" / "extraordinarios.py").read_text(encoding="utf-8")
    assert re.search(r"\bP_[A-Z]", texto) is None
    assert "TIPO_RECURSO_EXTRAORDINARIO" not in texto
    assert "APROVADO" not in texto

    def _parametros(versao: str) -> set[str]:
        caminho = RAIZ / "parameters" / f"parametros-{versao}.json"
        return {c for c in json.loads(caminho.read_text(encoding="utf-8")) if c.startswith("P_")}

    assertar_exato(_parametros("1.0.2"), _parametros("1.0.1"))
    assert "TIPO_RECURSO_EXTRAORDINARIO" not in RecursoExtraordinario.__dataclass_fields__


# ---------------------------------------------------------------------------
# T-161 / T-165 — calcular_plano ponta a ponta
# ---------------------------------------------------------------------------
def _estado_capacidade_positiva(
    *recursos: RecursoExtraordinario, saldo: int = 60000
) -> EstadoFinanceiro:
    """`gab_b.json` (capacidade 200) com a dívida de saldo conhecido — sem
    saldo não há cronograma para receber aporte."""
    estado = carregar_gab_b()
    divida = dataclasses.replace(
        estado.dividas[0],
        SALDO_DEVEDOR_ATUAL=dinheiro(saldo),
        VALOR_QUITACAO_HOJE=dinheiro(saldo),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=dinheiro("0.01"),
    )
    return dataclasses.replace(estado, dividas=(divida,), recursos_extraordinarios=recursos)


def _plano(estado: EstadoFinanceiro, anterior: SnapshotOrdem | None = None) -> SnapshotOrdem:
    return calcular_plano(estado, FonteParametrosArquivo().carregar("1.0.2"), anterior)


def _publicado(s: SnapshotOrdem) -> tuple[object, ...]:
    """O que o motor publica: método, ordem, prazo, custo, ataque de hoje."""
    cenario = s.cenarios[s.METODO_RECOMENDADO_PIQ]
    return (
        s.METODO_RECOMENDADO_PIQ,
        s.ORDEM_QUITACAO,
        cenario.PRAZO_TOTAL,
        cenario.CUSTO_FUTURO_TOTAL,
        s.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO,
    )


@pytest.mark.regra
@pytest.mark.parametrize(
    ("janela", "mes"),
    [(J.UM_A_TRES_MESES, 3), (J.QUATRO_A_SEIS_MESES, 6), (J.SETE_A_DOZE_MESES, 12)],
)
def test_confirmado_entra_so_no_ultimo_mes_da_janela(
    janela: JANELA_RECURSO_EXTRAORDINARIO, mes: int
) -> None:
    """`AC-118`/`AC-129`: aporte só no mês 3/6/12; `PRAZO_TOTAL` ≤ o sem
    recurso. `AC-130`: nenhum `ATAQUE_IMEDIATO_APROVADO` foi preciso."""
    sem = _plano(_estado_capacidade_positiva())
    com = _plano(_estado_capacidade_positiva(_recurso("X", 5000, janela=janela)))

    base = sem.diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA
    cenario = com.cenarios[com.METODO_RECOMENDADO_PIQ]
    capacidades = [m.estado_final.CAPACIDADE_ATAQUE_M for m in cenario.meses]
    esperado = [base] * len(capacidades)
    esperado[mes - 1] = base + dinheiro(5000)
    assertar_exato(capacidades, esperado)
    assert cenario.PRAZO_TOTAL <= sem.cenarios[sem.METODO_RECOMENDADO_PIQ].PRAZO_TOTAL
    assertar_exato(
        com.projecao_extraordinarios.aportes_base,
        (AporteProjetado(ITEM_ID="X", mes=mes, VALOR_DESTINADO=dinheiro(5000)),),
    )
    assertar_exato(com.projecao_extraordinarios.nao_projetados, ())
    assertar_exato(com.ENGINE_VERSION, "1.0.2")


@pytest.mark.regra
def test_mes_alem_da_ultima_quitacao_nao_muda_a_projecao() -> None:
    """`AC-119`/`EC-56`: dívida quita no mês 5; aporte no mês 12 → projeção
    idêntica à sem recurso, item `FORA_DO_HORIZONTE`."""
    sem = _plano(_estado_capacidade_positiva(saldo=8000))
    com = _plano(
        _estado_capacidade_positiva(_recurso("X", janela=J.SETE_A_DOZE_MESES), saldo=8000)
    )

    assertar_exato(com.cenarios, sem.cenarios)
    assertar_exato(_publicado(com), _publicado(sem))
    assertar_exato(com.projecao_extraordinarios.aportes_base, ())
    assertar_exato(
        com.projecao_extraordinarios.nao_projetados,
        (ItemNaoProjetado(ITEM_ID="X", motivo=MOTIVO_NAO_PROJETADO.FORA_DO_HORIZONTE),),
    )


@pytest.mark.regra
def test_estados_iguais_exceto_tipo_sao_indistinguiveis() -> None:
    """`AC-121`/`RF-72`: o tipo (13º × precatório) nem existe no contrato —
    dois recebimentos de mesmo valor, janela e certeza produzem snapshots
    iguais."""
    decimo_terceiro = _plano(_estado_capacidade_positiva(_recurso("R1")))
    precatorio = _plano(_estado_capacidade_positiva(_recurso("R1")))

    assertar_exato(precatorio, decimo_terceiro)


@pytest.mark.regra
def test_item_recebido_entra_uma_unica_vez() -> None:
    """`AC-125`/`R9M.10` #6: mesmo `ITEM_ID` projetado em `4_6M` e depois
    reentregue com `ATE_30D` → no segundo snapshot só em §13.3."""
    antes = _plano(_estado_capacidade_positiva(_recurso("R1", 5000)))
    recebido = _estado_capacidade_positiva(_recurso("R1", 5000, janela=J.ATE_30D))
    depois = _plano(recebido, anterior=antes)

    assertar_exato(len(antes.projecao_extraordinarios.aportes_base), 1)
    assertar_exato(depois.projecao_extraordinarios.aportes_base, ())
    assertar_exato(
        depois.projecao_extraordinarios.nao_projetados,
        (ItemNaoProjetado(ITEM_ID="R1", motivo=MOTIVO_NAO_PROJETADO.ATAQUE_DE_HOJE),),
    )
    assertar_exato(
        calcular_EXTRAORDINARIOS_RECOMENDADOS(
            recursos_extraordinarios=recebido.recursos_extraordinarios
        ),
        dinheiro(5000),
    )


@pytest.mark.regra
def test_deficit_estrutural_nao_muda_diagnostico_nem_recebe_aporte() -> None:
    """`AC-127`/`RF-76` + trava de `RF-74` (decisão de 2026-09-30):
    `gab_a` + `CONFIRMADO` alto → `MODO_ESTABILIZACAO`, `STATUS_FINANCEIRO` e
    capacidades idênticos; nenhum aporte."""
    estado = carregar_gab_a()
    sem = _plano(estado)
    com = _plano(
        dataclasses.replace(
            estado,
            recursos_extraordinarios=(_recurso("R1", 500000, janela=J.UM_A_TRES_MESES),),
        )
    )

    for campo in (
        "MODO_ESTABILIZACAO",
        "STATUS_FINANCEIRO",
        "CAPACIDADE_ATAQUE_ATUAL",
        "CAPACIDADE_ATAQUE_CONSERVADORA",
        "CAPACIDADE_ATAQUE_POTENCIAL",
    ):
        assertar_exato(getattr(com.diagnostico, campo), getattr(sem.diagnostico, campo))
    assert com.diagnostico.MODO_ESTABILIZACAO
    assertar_exato(com.cenarios, sem.cenarios)
    assertar_exato(com.projecao_extraordinarios.aportes_base, ())
    assertar_exato(
        com.projecao_extraordinarios.nao_projetados,
        (ItemNaoProjetado(ITEM_ID="R1", motivo=MOTIVO_NAO_PROJETADO.TRAVA_DEFICIT_ESTRUTURAL),),
    )


@pytest.mark.regra
def test_ate_30d_so_no_ataque_de_hoje() -> None:
    """`AC-124`/`AC-130`/`EC-54`: `CONFIRMADO ∧ ATE_30D` compõe §13.3 e
    nenhum aporte; a projeção é a do estado sem recurso."""
    sem = _plano(_estado_capacidade_positiva())
    com = _plano(_estado_capacidade_positiva(_recurso("R1", 5000, janela=J.ATE_30D)))

    assertar_exato(com.cenarios, sem.cenarios)
    assertar_exato(com.projecao_extraordinarios.aportes_base, ())
    assertar_exato(
        com.projecao_extraordinarios.nao_projetados,
        (ItemNaoProjetado(ITEM_ID="R1", motivo=MOTIVO_NAO_PROJETADO.ATAQUE_DE_HOJE),),
    )


@pytest.mark.regra
def test_sem_recurso_projecao_vazia() -> None:
    """`EC-55`: estado sem recurso → `ProjecaoExtraordinarios((), (), None)`."""
    assertar_exato(
        _plano(_estado_capacidade_positiva()).projecao_extraordinarios, PROJECAO_VAZIA
    )


@pytest.mark.regra
@pytest.mark.parametrize("certeza", [C.PROVAVEL, C.POSSIVEL])
def test_incerto_so_no_cenario_adicional(certeza: CERTEZA_RECURSO_EXTRAORDINARIO) -> None:
    """`AC-120`/`RF-71`: só `PROVAVEL` (ou só `POSSIVEL`) → publicado
    idêntico ao sem recurso; o recurso aparece só no cenário adicional."""
    sem = _plano(_estado_capacidade_positiva())
    com = _plano(_estado_capacidade_positiva(_recurso("R1", 5000, certeza=certeza)))

    assertar_exato(_publicado(com), _publicado(sem))
    assertar_exato(com.cenarios, sem.cenarios)
    projecao = com.projecao_extraordinarios
    assertar_exato(projecao.aportes_base, ())
    assert projecao.cenario_adicional is not None
    assertar_exato(projecao.cenario_adicional.metodo, com.METODO_RECOMENDADO_PIQ)
    assertar_exato(
        projecao.cenario_adicional.aportes,
        (AporteProjetado(ITEM_ID="R1", mes=6, VALOR_DESTINADO=dinheiro(5000)),),
    )


@pytest.mark.regra
def test_provavel_e_possivel_formam_segunda_projecao_distinta() -> None:
    """`AC-131`: `PROVAVEL` + `POSSIVEL` → cenário adicional distinto da base
    e contendo os dois; a base não contém nenhum."""
    com = _plano(
        _estado_capacidade_positiva(
            _recurso("P1", 5000, certeza=C.PROVAVEL),
            _recurso("P2", 3000, janela=J.UM_A_TRES_MESES, certeza=C.POSSIVEL),
        )
    )

    adicional = com.projecao_extraordinarios.cenario_adicional
    assert adicional is not None
    assertar_exato(com.projecao_extraordinarios.aportes_base, ())
    assertar_exato(sorted(a.ITEM_ID for a in adicional.aportes), ["P1", "P2"])
    base = com.cenarios[com.METODO_RECOMENDADO_PIQ]
    assert (adicional.PRAZO_TOTAL, adicional.CUSTO_FUTURO_TOTAL) != (
        base.PRAZO_TOTAL,
        base.CUSTO_FUTURO_TOTAL,
    )


@pytest.mark.regra
def test_confirmado_e_provavel_iguais_so_o_confirmado_na_base() -> None:
    """`AC-122`: mesmo valor e janela — só o `CONFIRMADO` afeta a base, nunca
    somados num único valor; o adicional carrega os dois, item a item."""
    so_confirmado = _plano(_estado_capacidade_positiva(_recurso("C1", 5000)))
    com = _plano(
        _estado_capacidade_positiva(
            _recurso("C1", 5000), _recurso("P1", 5000, certeza=C.PROVAVEL)
        )
    )

    assertar_exato(
        com.projecao_extraordinarios.aportes_base,
        (AporteProjetado(ITEM_ID="C1", mes=6, VALOR_DESTINADO=dinheiro(5000)),),
    )
    assertar_exato(com.cenarios, so_confirmado.cenarios)
    adicional = com.projecao_extraordinarios.cenario_adicional
    assert adicional is not None
    assertar_exato(
        adicional.aportes,
        (
            AporteProjetado(ITEM_ID="C1", mes=6, VALOR_DESTINADO=dinheiro(5000)),
            AporteProjetado(ITEM_ID="P1", mes=6, VALOR_DESTINADO=dinheiro(5000)),
        ),
    )


@pytest.mark.regra
def test_confirmado_de_valor_desconhecido_nao_entra_nem_vira_zero() -> None:
    """`AC-122`/`EC-52`: visível no snapshot com o motivo; projeção idêntica
    à sem recurso."""
    sem = _plano(_estado_capacidade_positiva())
    com = _plano(_estado_capacidade_positiva(_recurso("R1", DESCONHECIDO)))

    assertar_exato(com.cenarios, sem.cenarios)
    assertar_exato(
        com.projecao_extraordinarios.nao_projetados,
        (ItemNaoProjetado(ITEM_ID="R1", motivo=MOTIVO_NAO_PROJETADO.VALOR_DESCONHECIDO),),
    )


@pytest.mark.regra
@pytest.mark.parametrize("certeza", [C.PROVAVEL, C.POSSIVEL])
def test_incerto_ate_30d_entra_no_mes_1_do_cenario_adicional(
    certeza: CERTEZA_RECURSO_EXTRAORDINARIO,
) -> None:
    """`OQ-47`: `ATE_30D` → mês 1. A exceção de `OQ-50` (ataque de hoje, não
    duplicado) vale só para `CONFIRMADO`; `PROVAVEL`/`POSSIVEL` em `ATE_30D`
    ficam fora da base e entram no mês 1 do cenário adicional (`RF-71`)."""
    aportes, _ = selecionar_aportes(
        (_recurso("I", 900, janela=J.ATE_30D, certeza=certeza),),
        certezas=TODAS,
        RESULTADO_MENSAL_ATUAL=dinheiro(100),
    )
    assertar_exato(aportes, (AporteProjetado(ITEM_ID="I", mes=1, VALOR_DESTINADO=dinheiro(900)),))

    sem = _plano(_estado_capacidade_positiva())
    com = _plano(
        _estado_capacidade_positiva(_recurso("I", 900, janela=J.ATE_30D, certeza=certeza))
    )
    assertar_exato(_publicado(com), _publicado(sem))
    assertar_exato(com.projecao_extraordinarios.aportes_base, ())
    adicional = com.projecao_extraordinarios.cenario_adicional
    assert adicional is not None
    assertar_exato(
        adicional.aportes, (AporteProjetado(ITEM_ID="I", mes=1, VALOR_DESTINADO=dinheiro(900)),)
    )


@pytest.mark.regra
def test_confirmado_ate_30d_fora_tambem_do_cenario_adicional() -> None:
    """`OQ-50`/`RF-73`: `CONFIRMADO ∧ ATE_30D` é ataque de hoje em qualquer
    conjunto de certezas — nunca aporte, nem no cenário adicional."""
    aportes, nao_projetados = selecionar_aportes(
        (_recurso("R1", janela=J.ATE_30D),), certezas=TODAS, RESULTADO_MENSAL_ATUAL=dinheiro(100)
    )

    assertar_exato(aportes, ())
    assertar_exato(
        nao_projetados,
        (ItemNaoProjetado(ITEM_ID="R1", motivo=MOTIVO_NAO_PROJETADO.ATAQUE_DE_HOJE),),
    )
