"""T-214 — o plano gerado de ponta a ponta com o questionário REAL.

A coleção é a mesma que `obter_colecao_de_registros` carrega em produção
(`collection/carga.py::carregar_registros`, os `collection/registros/*.yaml`);
só os repositórios são dublês em memória (os de `test_rotas_calculo.py`). O
perfil segue o caso T02 do QA (`docs/revisao-qa-2026-09-29.md`): renda
líquida R$ 5.000, gastos R$ 3.500, reserva R$ 1.000, D001 cartão rotativo e
D002 empréstimo pessoal. Os VALORES do plano não são critério aqui (validação
financeira é do especialista) — só que um plano é gerado e o caso avança.

REGRAS: `AC-11`, `AC-12`, `AC-13`, `RF-14`, `RF-16`
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import pendencias_obrigatorias
from app.http.rotas_calculo import (
    ParametrosExternosDoBloco6,
    _ParametrosExternosDerivadosDoBloco2,
)
from app.montagem.conversao import converter_para_dinheiro, converter_para_taxa
from app.montagem.estado import montar_divida, montar_estado_financeiro
from app.revisao.comprovacao import pendencias_de_homologacao
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import RespostasCaso
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.itens import ItemRepetido
from tests.app_aluno.fixtures.caso_completo import (
    CASO_ID,
    DATA_REFERENCIA,
    DESPESA_NAO_MENSAL_ID_UNICA,
    DIVIDA_ID_UNICA,
    ITEM_DESPESA_ID_UNICA,
    PARAMETROS_EXTERNOS_PADRAO,
    caso_completo,
    montar_respostas_caso,
)
from tests.app_aluno.test_rotas_calculo import (
    _caso_fabricado,
    _montar_aplicacao_de_teste,
    _RepositorioCasosDublê,
)
from tests.homologacao.registro import NAO_DISPONIVEL, emitir, registrar_homologacao

# Chave de B5.C02 no registro real — o `VARIAVEL_GRAVADA` composto.
_PARCELA_CONTRATUAL = "PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)"

_T02_CASO: dict[str, object] = {
    "RENDA_PRINCIPAL": converter_para_dinheiro("5.000,00"),
    "DINHEIRO_DISPONIVEL": converter_para_dinheiro("200,00"),
    "RESERVA_TOTAL": converter_para_dinheiro("1.000,00"),
    "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO": converter_para_dinheiro("500,00"),
    "QUANTIDADE_DIVIDAS_DECLARADA_INICIAL": 2,
    "TIPOS_DIVIDA_DECLARADOS": frozenset({"CARTAO_ROTATIVO", "PESSOAL"}),
}
_T02_D001: dict[str, object] = {
    "TIPO_DIVIDA": "CARTAO_ROTATIVO",
    "STATUS_DIVIDA": "ATIVA",
    "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("1.800,00"),
    "POSSUI_PARCELA_DEFINIDA": "NAO",
    "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("200,00"),
    "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
    "TAXA_INFORMADA": converter_para_taxa("10"),
    "PERIODICIDADE_TAXA": "MENSAL",
    "PESO_EMOCIONAL": 5,
}
_T02_D002: dict[str, object] = {
    "TIPO_DIVIDA": "PESSOAL",
    "STATUS_DIVIDA": "ATIVA",
    "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("6.000,00"),
    "POSSUI_PARCELA_DEFINIDA": "SIM",
    _PARCELA_CONTRATUAL: converter_para_dinheiro("400,21"),
    "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("400,21"),
    "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
    "TAXA_INFORMADA": converter_para_taxa("2"),
    "PERIODICIDADE_TAXA": "MENSAL",
    "PESO_EMOCIONAL": 5,
}


def _respostas_t02() -> RespostasCaso:
    """Fixture completa com o perfil T02 e uma segunda ficha de dívida."""
    base = caso_completo(
        valores_caso=_T02_CASO,
        valores_divida=_T02_D001,
        valores_item_despesa={"VALOR_DESPESA": converter_para_dinheiro("3.500,00")},
        valores_despesa_nao_mensal={
            "VALOR_DESPESA_NAO_MENSAL": converter_para_dinheiro("1.200,00")
        },
        DIVIDA_ID="D001",
    ).respostas
    d002 = tuple(
        r
        for r in montar_respostas_caso(valores_divida=_T02_D002, DIVIDA_ID="D002").respostas
        if r.item_id == "D002"
    )
    return RespostasCaso(respostas=base.respostas + d002)


def _itens(dividas: tuple[str, ...]) -> tuple[ItemRepetido, ...]:
    escopos = [(d, EscopoRepeticao.DIVIDA_ID) for d in dividas] + [
        (ITEM_DESPESA_ID_UNICA, EscopoRepeticao.ITEM_DESPESA),
        (DESPESA_NAO_MENSAL_ID_UNICA, EscopoRepeticao.DESPESA_NAO_MENSAL_ID),
    ]
    return tuple(
        ItemRepetido(
            item_id=item_id,
            CASO_ID=CASO_ID,
            escopo=escopo,
            removido_em=None,
            criado_em=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for item_id, escopo in escopos
    )


def _itens_por_escopo(itens: tuple[ItemRepetido, ...]) -> dict[EscopoRepeticao, tuple[str, ...]]:
    agrupado: dict[EscopoRepeticao, tuple[str, ...]] = {}
    for item in itens:
        agrupado[item.escopo] = (*agrupado.get(item.escopo, ()), item.item_id)
    return agrupado


def test_fixture_caso_completo_nao_tem_pendencia_obrigatoria_no_registro_real() -> None:
    """AC-11 — a fixture padrão responde todo `OBR` exigível do registro atual."""
    colecao = carregar_registros()
    itens = _itens_por_escopo(_itens((DIVIDA_ID_UNICA,)))

    assert pendencias_obrigatorias(colecao.registros, caso_completo().respostas, itens) == ()


def test_perfil_t02_nao_tem_pendencia_obrigatoria_no_registro_real() -> None:
    """AC-11 — o perfil T02 (duas dívidas) também fecha todo `OBR`."""
    colecao = carregar_registros()
    itens = _itens_por_escopo(_itens(("D001", "D002")))

    assert pendencias_obrigatorias(colecao.registros, _respostas_t02(), itens) == ()


def test_estado_financeiro_do_perfil_t02_preenche_todos_os_campos() -> None:
    """AC-13 — nenhum campo do `EstadoFinanceiro` fica sem valor."""
    respostas = _respostas_t02()

    estado = montar_estado_financeiro(
        respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=tuple(montar_divida(respostas, d) for d in ("D001", "D002")),
        **PARAMETROS_EXTERNOS_PADRAO,  # type: ignore[arg-type]
    )

    vazios = [f.name for f in dataclasses.fields(estado) if getattr(estado, f.name) is None]
    assert vazios == []
    assert [d.DIVIDA_ID for d in estado.dividas] == ["D001", "D002"]
    assert estado.INVENTARIO_COMPLETO is True


def _esperar_sair_de_calculando(repositorio: _RepositorioCasosDublê) -> ESTADO_CASO:
    # ponytail: espera por polling (o cálculo roda em asyncio.Task no loop do
    # TestClient); o prazo só limita um travamento, não mede desempenho.
    prazo = time.monotonic() + 30
    while time.monotonic() < prazo:
        caso = repositorio.buscar(CASO_ID)
        assert caso is not None
        if caso.estado is not ESTADO_CASO.CALCULANDO:
            return caso.estado
        time.sleep(0.05)
    raise AssertionError("caso ficou em CALCULANDO")


def _disparar_e_esperar(
    monkeypatch: pytest.MonkeyPatch,
    parametros_externos: ParametrosExternosDoBloco6 | None = None,
) -> tuple[int, str, ESTADO_CASO, list[SnapshotOrdem]]:
    """POST /calculo com a coleção real e o perfil T02; devolve status, corpo,
    estado final do caso e os snapshots anexados."""
    repositorio_casos = _RepositorioCasosDublê(
        _caso_fabricado(ESTADO_CASO.COLETA_INICIAL, caso_id=CASO_ID),
        conta_id_da_sessao="CONTA-1",
    )
    cliente, snapshots = _montar_aplicacao_de_teste(
        monkeypatch,
        repositorio_casos=repositorio_casos,
        colecao=carregar_registros(),
        respostas=_respostas_t02().respostas,
        itens=_itens(("D001", "D002")),
        parametros_externos=parametros_externos,
    )
    with cliente:  # mantém o loop vivo para a asyncio.Task do cálculo
        resposta = cliente.post(f"/caso/{CASO_ID}/calculo")
        estado_final = (
            _esperar_sair_de_calculando(repositorio_casos)
            if resposta.status_code == 200
            else ESTADO_CASO.COLETA_INICIAL
        )
    return resposta.status_code, resposta.text, estado_final, snapshots.snapshots


def test_post_calculo_com_registro_real_grava_um_snapshot_e_caso_avanca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-12 — `POST /calculo` com a coleção real e o perfil T02 gera plano:
    exatamente um snapshot anexado e o caso vai de `CALCULANDO` para
    `AGUARDANDO_REVISAO`. Parâmetros externos pelo dublê de
    `test_rotas_calculo.py` (`PARAMETROS_EXTERNOS_PADRAO`)."""
    status, corpo, estado_final, n_snapshots = _disparar_e_esperar(monkeypatch)

    assert status == 200, corpo
    assert estado_final is ESTADO_CASO.AGUARDANDO_REVISAO
    assert len(n_snapshots) == 1


def test_post_calculo_com_parametros_externos_de_producao_gera_plano(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-12 — o mesmo disparo, mas com a derivação padrão da produção
    (`obter_parametros_externos_do_bloco6`), sem dublê de parâmetros.

    Era `xfail`: sem `economia_nao_identificada`, quem não tinha gasto
    fantasma aceito recebia 422 com a pendência "B2.10/B2.10A"."""
    status, corpo, estado_final, n_snapshots = _disparar_e_esperar(
        monkeypatch, _ParametrosExternosDerivadosDoBloco2()
    )

    assert status == 200, corpo
    assert estado_final is ESTADO_CASO.AGUARDANDO_REVISAO
    assert len(n_snapshots) == 1


def test_t281_t02_ponta_a_ponta_registra_os_cinco_itens_de_de08(
    monkeypatch: pytest.MonkeyPatch, record_property: Callable[[str, object], None]
) -> None:
    """`RF-96`, `AC-148`, `DE-08` (`T-281`) — o snapshot do `POST /calculo`
    do T02 produz o `RegistroHomologacao`. Caso não gabarito: só
    invariantes, nenhum valor esperado de ordem, prazo ou reserva."""
    status, corpo, _, snapshots = _disparar_e_esperar(monkeypatch)
    assert status == 200, corpo
    (snapshot,) = snapshots
    itens = _itens(("D001", "D002"))
    pendencias = pendencias_de_homologacao(
        carregar_registros().registros, _respostas_t02(), _itens_por_escopo(itens)
    )

    registro = registrar_homologacao(snapshot, pendencias)
    emitir(record_property, registro)

    for nome in (
        "ordem_final_de_ataque",
        "mes_de_quitacao_por_divida",
        "valor_mensal_destinado",
        "custo_total_de_juros",
        "uso_da_reserva",
    ):
        item = getattr(registro, nome)
        assert item.origem if item.disponivel else (item.valor == NAO_DISPONIVEL and item.motivo)
    ordem = registro.ordem_final_de_ataque.valor
    meses = registro.mes_de_quitacao_por_divida.valor
    assert isinstance(ordem, tuple) and isinstance(meses, dict)
    assert set(ordem) <= {"D001", "D002"} and set(meses) <= {"D001", "D002"}
    assert registro.homologavel is (pendencias == ())
