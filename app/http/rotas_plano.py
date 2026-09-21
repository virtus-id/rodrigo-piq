"""Rotas do plano do aluno (tela e PDF) — `RF-20`, `RF-21`, `RF-23`, `AC-14`,
`AC-16`, `AC-25` (T-63, T-64).

`GET /caso/{CASO_ID}/plano/pdf` (T-63) serve o PDF do snapshot **liberado**
do caso (`report/pdf.py::gerar_pdf_do_plano`), sob demanda — nunca
pré-gerado, nunca cacheado em disco (o snapshot é imutável, então regenerar
sempre produz o mesmo HTML de entrada, ver `report/pdf.py`).

`GET /caso/{CASO_ID}/plano` (T-64) é a tela HTML equivalente: MESMA leitura
do `snapshot_liberado_id` do caso, MESMA guarda de liberação — nenhuma
segunda checagem inventada. As duas rotas compartilham a mesma sequência
(buscar caso → ler `snapshot_liberado_id` → obter snapshot → montar/renderizar
o MESMO `plano.html`), reaproveitando as funções de `report/pdf.py`
(`snapshot_tem_liberacao_registrada`, `gerar_html_do_plano_liberado`,
`gerar_pdf_do_plano`) — nenhuma delas é duplicada aqui.

**`AC-25`: snapshot sem liberação registrada não é acessível ao aluno, nem em
tela nem em PDF.** Quando `Caso.snapshot_liberado_id is None`, a tela NÃO
devolve `404`/erro genérico — ela exibe o ESTADO do caso (`Caso.estado`,
leitura pura, Lei nº 3), pelo template `plano/aguardando.html`, para que
"caso sem nenhum snapshot liberado" mostre o que está acontecendo ("sua
coleta está em andamento", "seu plano está em revisão"...) em vez de uma
tela de plano vazia. O PDF, por natureza (não tem "estado" para mostrar,
só bytes de um documento), continua devolvendo `404` nesse caso — mesmo
comportamento já entregue por T-63.

**Isolamento por `CASO_ID` (`RF-02`, `AC-03`, T-31).** As duas rotas
declaram `Depends(exigir_caso_da_sessao("CASO_ID"))`, o mesmo mecanismo de
qualquer outra rota desta feature — sessão ausente recusa antes de tocar o
banco; caso de outra conta devolve `404`, nunca `403`.

**"Snapshot com liberação registrada" (critério de aceite comum às duas
rotas).** Nenhuma das duas rotas decide sozinha o que conta como liberado:
ambas só leem `Caso.snapshot_liberado_id` e delegam a comparação a
`report.pdf.snapshot_tem_liberacao_registrada` (ver a nota extensa em
`report/pdf.py` sobre a fronteira com a Entrega 8/fila de revisão, ainda não
implementada).

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.maquina` (só `ESTADO_CASO`, tipo de estado
— nenhuma transição é disparada por estas rotas, que são só leitura),
`persistencia.app_aluno.casos`, `persistencia.supabase.repositorio_snapshots`
(o adaptador concreto da porta do motor, mesmo padrão de `app/http/
rotas_calculo.py`) e de `report.pdf`/`report.plano` — nunca de `engine/`
além dos nomes já liberados transitivamente por essas portas (`AC-41`).
Nenhum gate, ranqueamento ou fórmula da §11 aparece aqui, e nenhum
identificador `P_*` nem enunciado de pergunta (`AC-37`).

REGRAS: `RF-20`, `RF-21`, `RF-23`, `AC-14`, `AC-16`, `AC-25`
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from engine.portas import RepositorioSnapshots
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.supabase.repositorio_snapshots import (
    ErroSnapshotNaoEncontrado,
    RepositorioSnapshotsSupabase,
)
from report.pdf import ErroSnapshotNaoLiberado, gerar_pdf_do_plano
from report.plano import carregar_textos_canonicos

REGRAS: Final[tuple[str, ...]] = ("RF-20", "RF-21", "RF-23", "AC-14", "AC-16", "AC-25")

roteador = APIRouter(prefix="/caso", tags=["plano"])

# Mensagens curtas de propósito — mesma disciplina de `app/http/isolamento.py`
# e `app/http/rotas_consentimento.py` (`AC-37`, T-08): ficam sob o limiar de
# 40 caracteres do teste estático.
_MENSAGEM_SEM_SNAPSHOT_LIBERADO: Final[str] = "Nenhum plano liberado ainda."



class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: mesmo precedente de `app/http/rotas_consentimento.py`/
    `app/http/rotas_calculo.py` — `exigir_caso_da_sessao` já garantiu que
    `CASO_ID` existe e pertence à conta da sessão; este erro só ocorreria
    numa condição de corrida extrema."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento confirmá-lo")


def obter_repositorio_snapshots() -> RepositorioSnapshots:
    """Ponto único de injeção da porta `RepositorioSnapshots` — mesmo padrão
    de `app/http/rotas_calculo.py::obter_repositorio_snapshots`. Sobrescrito
    nos testes via `app.dependency_overrides`."""
    return RepositorioSnapshotsSupabase()


@roteador.get("/{CASO_ID}/plano/pdf")
def exportar_pdf_do_plano(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots)
    ],
) -> Response:
    """Serve o PDF do snapshot **liberado** do caso — nunca o último
    calculado (`AC-25`). Chama `report.pdf.gerar_pdf_do_plano`, que por sua
    vez chama a MESMA `montar_contexto_plano`/`plano.html` que a tela
    (`exibir_tela_do_plano`, abaixo) usa — nenhuma segunda redação do texto
    normativo."""
    caso = repositorio_casos.buscar(CASO_ID)
    if caso is None:  # pragma: no cover — defensivo: isolamento já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    if caso.snapshot_liberado_id is None:
        raise HTTPException(status_code=404, detail=_MENSAGEM_SEM_SNAPSHOT_LIBERADO)

    try:
        snapshot = repositorio_snapshots.obter(caso.snapshot_liberado_id)
    except ErroSnapshotNaoEncontrado as erro:
        raise HTTPException(
            status_code=404, detail=_MENSAGEM_SEM_SNAPSHOT_LIBERADO
        ) from erro

    textos = carregar_textos_canonicos()

    try:
        pdf_bytes = gerar_pdf_do_plano(caso, snapshot, textos)
    except ErroSnapshotNaoLiberado as erro:
        # Defensivo: `caso.snapshot_liberado_id` já filtrou isso acima — só
        # ocorreria se o snapshot obtido não bater com o SNAPSHOT_ID pedido,
        # o que `repositorio_snapshots.obter` já impede por contrato.
        raise HTTPException(  # pragma: no cover
            status_code=404, detail=_MENSAGEM_SEM_SNAPSHOT_LIBERADO
        ) from erro

    return Response(content=pdf_bytes, media_type="application/pdf")
