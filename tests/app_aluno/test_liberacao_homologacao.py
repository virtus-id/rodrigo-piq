"""Liberação recusada por pendência de homologação — `RF-92`, `RF-93`,
`RF-97` (`T-265`).

`AC-141`, `AC-142`, `AC-149`, `EC-40` pela rota REAL `POST /revisao/caso/
{id}/decisao` (a única rota de liberação) e pela função de domínio
`liberar`, com repositórios de arquivo (`T-24`) e snapshot REAL — mesmo
arranjo de `test_rotas_revisao_decisao.py`. As pendências são derivadas das
respostas gravadas, nunca fabricadas.

`T-266`: o contexto de `GET .../decisao` (fontes, seguro "não informado",
divergências, rateios e pendências), pela mesma rota.

REGRAS: `RF-92`, `RF-93`, `RF-97`, `AC-141`, `AC-142`, `AC-149`, `EC-40`,
`AC-124`, `AC-155`, `AC-156`, `EC-39`
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.casos.maquina import ESTADO_CASO
from app.casos.progresso import pendencias_obrigatorias
from app.http.aplicacao import criar_aplicacao
from app.http.isolamento import exigir_papel_revisor
from app.http.rotas_revisao import (
    obter_repositorio_casos_da_fila,
    obter_repositorio_eventos_da_decisao,
    obter_repositorio_itens_da_revisao,
    obter_repositorio_respostas_da_revisao,
    obter_repositorio_revisoes_da_decisao,
    obter_repositorio_snapshots_da_fila,
)
from app.revisao.comprovacao import PendenciaHomologacao
from app.revisao.fila import ErroHomologacaoBloqueada, liberar, listar_fila_de_revisao
from collection.carga import carregar_registros
from collection.registro import EscopoRepeticao
from collection.respostas import NAO_SEI, Resposta, RespostasCaso
from persistencia.app_aluno.arquivo import (
    RepositorioCasosArquivo,
    RepositorioEventosCasoArquivo,
    RepositorioItensArquivo,
    RepositorioRespostasArquivo,
)
from persistencia.arquivo.repositorio_snapshots import RepositorioSnapshotsArquivo
from report.plano import carregar_textos_canonicos
from tests.app_aluno.test_rotas_revisao_decisao import (
    _calcular_snapshot,
    _criar_caso,
    _RepositorioRevisoesDublê,
)

_CASO = "CASO-HOMOLOGACAO"
_AGORA = datetime(2026, 9, 30, tzinfo=UTC)

# Os quatro dados que o motor lê, respondidos, com fonte comprovada.
_DIVIDA_COMPLETA: dict[str, object] = {
    "SALDO_DEVEDOR_ATUAL": "5000",
    "POSSUI_PARCELA_DEFINIDA": "SIM",
    "PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)": "300",
    "QUALIDADE_TAXA_INFORMADA": "CONFIRMADA",
    "TAXA_INFORMADA": "2",
    "FONTE_DADO": "DOCUMENTO_CONTRATO",
}


class _Ambiente:
    def __init__(self, tmp_path: Path) -> None:
        self.casos = RepositorioCasosArquivo(tmp_path / "casos.jsonl")
        self.snapshots = RepositorioSnapshotsArquivo(tmp_path / "snapshots.jsonl")
        self.eventos = RepositorioEventosCasoArquivo(tmp_path / "eventos.jsonl")
        self.itens = RepositorioItensArquivo(tmp_path / "itens.jsonl")
        self.respostas = RepositorioRespostasArquivo(tmp_path / "respostas.jsonl")
        self.revisoes = _RepositorioRevisoesDublê()
        _criar_caso(self.casos, _CASO, "conta-aluno-homologacao")
        self.snapshot = _calcular_snapshot(_CASO, self.casos, self.snapshots, self.eventos)
        self.divida = self.itens.proximo_identificador(_CASO, EscopoRepeticao.DIVIDA_ID)
        self.responder("RENDA_PRINCIPAL", Decimal("8000"))

    def responder(self, variavel: str, valor: object, item_id: str | None = None) -> None:
        self.respostas.gravar(
            Resposta(
                CASO_ID=_CASO,
                ID_PERGUNTA=variavel,
                item_id=item_id,
                valor=valor,  # type: ignore[arg-type]
                QUESTIONARIO_VERSION="1.0.3",
                respondida_em=_AGORA,
            )
        )

    def responder_divida(self, **mudancas: object) -> None:
        for variavel, valor in {**_DIVIDA_COMPLETA, **mudancas}.items():
            self.responder(variavel, valor, self.divida)

    def cliente(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setenv("CHAVE_ASSINATURA_SESSAO", "chave-de-teste-t265-nao-usar-em-producao")
        aplicacao = criar_aplicacao()
        sobrescritas: dict[Callable[..., object], object] = {
            obter_repositorio_casos_da_fila: self.casos,
            obter_repositorio_snapshots_da_fila: self.snapshots,
            obter_repositorio_revisoes_da_decisao: self.revisoes,
            obter_repositorio_eventos_da_decisao: self.eventos,
            obter_repositorio_respostas_da_revisao: self.respostas,
            obter_repositorio_itens_da_revisao: self.itens,
            exigir_papel_revisor: "conta-revisor-t265",
        }
        for dependencia, valor in sobrescritas.items():
            aplicacao.dependency_overrides[dependencia] = _constante(valor)
        return TestClient(aplicacao, base_url="https://teste.local")

    def liberar_pela_rota(self, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
        resposta = self.cliente(monkeypatch).post(
            f"/revisao/caso/{_CASO}/decisao",
            content="decisao=LIBERAR",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        return resposta.status_code, resposta.json()


def _constante(valor: object) -> Callable[[], object]:
    """Sem parâmetro: o FastAPI leria `lambda v=valor` como query e copiaria
    o padrão."""
    return lambda: valor


@pytest.fixture
def ambiente(tmp_path: Path) -> _Ambiente:
    return _Ambiente(tmp_path)


def _assert_nada_gravado(ambiente: _Ambiente, eventos_antes: int) -> None:
    caso = ambiente.casos.buscar(_CASO)
    assert caso is not None
    assert caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO
    assert caso.snapshot_liberado_id is None
    assert ambiente.revisoes.registros == {}
    assert len(ambiente.eventos.listar_do_caso(_CASO)) == eventos_antes
    historico = ambiente.snapshots.historico(ambiente.snapshot.SNAPSHOT_ID)
    assert [s.SNAPSHOT_ID for s in historico] == [ambiente.snapshot.SNAPSHOT_ID]


def test_ac142_ec40_indispensavel_em_nivel_3_recusa_pela_rota_e_nada_grava(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(FONTE_DADO="ATENDIMENTO_CREDOR")
    eventos_antes = len(ambiente.eventos.listar_do_caso(_CASO))

    status, corpo = ambiente.liberar_pela_rota(monkeypatch)

    assert status == 409
    pendencias = corpo["pendencias_homologacao"]
    assert isinstance(pendencias, list)
    assert {(p["item_id"], p["ID_PERGUNTA"], p["motivo"]) for p in pendencias} == {
        (ambiente.divida, "B5.B03", "PENDENTE_DE_CONFIRMACAO"),
        (ambiente.divida, "B5.C02", "PENDENTE_DE_CONFIRMACAO"),
        (ambiente.divida, "B5.D01A", "PENDENTE_DE_CONFIRMACAO"),
    }
    _assert_nada_gravado(ambiente, eventos_antes)


def test_ac142_ec40_funcao_de_dominio_recusa_antes_de_gravar(ambiente: _Ambiente) -> None:
    eventos_antes = len(ambiente.eventos.listar_do_caso(_CASO))
    pendencia = PendenciaHomologacao(ambiente.divida, "B5.B03", "PENDENTE_DE_CONFIRMACAO")

    with pytest.raises(ErroHomologacaoBloqueada) as erro:
        liberar(
            revisao_id="REVISAO_T265",
            caso_id=_CASO,
            snapshot=ambiente.snapshot,
            autor="conta-revisor-t265",
            decidido_em=_AGORA,
            repositorio_revisoes=ambiente.revisoes,
            repositorio_casos=ambiente.casos,
            repositorio_eventos=ambiente.eventos,
            pendencias_homologacao=(pendencia,),
        )

    assert erro.value.pendencias == (pendencia,)
    _assert_nada_gravado(ambiente, eventos_antes)


def test_ac142_corrigido_o_dado_a_liberacao_e_aceita(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(FONTE_DADO="ATENDIMENTO_CREDOR")
    assert ambiente.liberar_pela_rota(monkeypatch)[0] == 409

    ambiente.responder("FONTE_DADO", "CONTRACHEQUE", ambiente.divida)

    assert ambiente.liberar_pela_rota(monkeypatch)[0] == 200
    caso = ambiente.casos.buscar(_CASO)
    assert caso is not None and caso.estado is ESTADO_CASO.PLANO_LIBERADO


def test_reprovar_continua_possivel_com_pendencia(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(SALDO_DEVEDOR_ATUAL=NAO_SEI)

    resposta = ambiente.cliente(monkeypatch).post(
        f"/revisao/caso/{_CASO}/decisao",
        content="decisao=REPROVAR",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert resposta.status_code == 200


def test_ac149_indispensavel_ausente_calculo_roda_e_liberacao_nomeia_o_dado(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(SALDO_DEVEDOR_ATUAL=NAO_SEI)
    registros = carregar_registros().registros
    respostas = RespostasCaso(respostas=ambiente.respostas.listar_do_caso(_CASO))
    itens = {EscopoRepeticao.DIVIDA_ID: (ambiente.divida,)}

    # O cálculo não é barrado: "não sei" é resposta (RF-11), nenhuma
    # pendência obrigatória nasce do saldo desconhecido.
    assert not any(p.ID == "B5.B03" for p in pendencias_obrigatorias(registros, respostas, itens))

    status, corpo = ambiente.liberar_pela_rota(monkeypatch)

    assert status == 409
    pendencias = corpo["pendencias_homologacao"]
    assert isinstance(pendencias, list)
    (pendencia,) = pendencias
    saldo = next(r for r in registros if r.ID == "B5.B03")
    assert pendencia == {
        "item_id": ambiente.divida,
        "ID_PERGUNTA": "B5.B03",
        "enunciado": saldo.enunciado,
        "motivo": "AUSENTE",
    }


def test_ac141_fontes_nivel_2_e_3_sem_indispensavel_pendente_liberam(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(
        FONTE_DADO="MEMORIA",
        EXISTE_PROPOSTA_RENEGOCIACAO="VIGENTE",
        **{"FONTE_DADO (proposta)": "ATENDIMENTO"},
    )

    fila = listar_fila_de_revisao([_CASO], ambiente.casos, ambiente.snapshots)
    assert [item.CASO_ID for item in fila] == [_CASO]

    assert ambiente.liberar_pela_rota(monkeypatch)[0] == 200


def test_t266_contexto_do_revisor_fontes_avisos_e_pendencias(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambiente.responder_divida(
        FONTE_DADO="ATENDIMENTO_CREDOR",
        SEGURO_PRESTAMISTA="SIM",
        SITUACAO_SEGURO=NAO_SEI,
        **{
            "CUSTO_SEGURO (+ base MENSAL/TOTAL)": "TOTAL",
            "CUSTO_SEGURO_VALOR": Decimal("1200"),
            "CUSTO_SEGURO_MESES": 24,
        },
    )
    for vinculo, liquida in (("V001", "4000"), ("V002", "2500")):
        ambiente.responder("RENDA_LIQUIDA_VINCULO", Decimal(liquida), vinculo)
    textos = carregar_textos_canonicos().rotulos_de_comprovacao

    corpo = ambiente.cliente(monkeypatch).get(f"/revisao/caso/{_CASO}/decisao").json()

    assert corpo["fontes"] == [
        {
            "item_id": ambiente.divida,
            "origem": "B5.I02",
            "nivel": "PENDENTE_DE_CONFIRMACAO",
            "rotulo": textos["PENDENTE_DE_CONFIRMACAO"],
        }
    ]
    # AC-155/EC-39: seguro "não sei" é "não informado", nunca nível 3.
    assert corpo["seguros_nao_informados"] == [ambiente.divida]
    assert corpo["rotulo_nao_informado"] == textos["NAO_INFORMADO"]
    assert {"tipo": "RENDA_VINCULOS"}.items() <= corpo["divergencias"][0].items()
    # AC-124: R$ 1.200 no total em 24 meses → R$ 50,00 rotulado rateio.
    assert [r["valor_mensal"] for r in corpo["rateios"]] == ["R$ 50,00"]
    assert {p["ID_PERGUNTA"] for p in corpo["pendencias_homologacao"]} == {
        "B5.B03",
        "B5.C02",
        "B5.D01A",
    }


def test_t283_taxa_nao_sei_calculo_roda_liberacao_recusada_ate_corrigir(
    ambiente: _Ambiente, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T-283`/`DE-06`: "Não sei a taxa" não barra o cálculo, mas bloqueia a
    liberação até a taxa ser informada."""
    ambiente.responder_divida(QUALIDADE_TAXA_INFORMADA="DESCONHECIDA")
    registros = carregar_registros().registros
    respostas = RespostasCaso(respostas=ambiente.respostas.listar_do_caso(_CASO))
    itens = {EscopoRepeticao.DIVIDA_ID: (ambiente.divida,)}

    assert not any(
        p.ID in {"B5.D01", "B5.D01A"} for p in pendencias_obrigatorias(registros, respostas, itens)
    )
    status, corpo = ambiente.liberar_pela_rota(monkeypatch)
    assert status == 409
    assert [(p["ID_PERGUNTA"], p["motivo"]) for p in corpo["pendencias_homologacao"]] == [  # type: ignore[attr-defined]
        ("B5.D01", "AUSENTE")
    ]

    ambiente.responder("QUALIDADE_TAXA_INFORMADA", "CONFIRMADA", ambiente.divida)

    assert ambiente.liberar_pela_rota(monkeypatch)[0] == 200
