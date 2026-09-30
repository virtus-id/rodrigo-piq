"""`GET /caso/{CASO_ID}/inventario` — o alerta permanente de inventário
incompleto (`RF-86`, `AC-133`, `T-250`).

Só LÊ: as pendências são derivadas a cada chamada por
`app/casos/inventario.py::pendencias_de_inventario` — a mesma função que a
guarda do cálculo usa (`T-248`), nunca uma segunda regra. A tela consulta
esta rota a cada navegação (`AlertaInventario.tsx`, na casca), por isso o
alerta está "em toda tela do aluno" enquanto a diferença persistir.

Cada pendência sai na forma de `rotas_calculo.formatar_pendencia_inventario`
— a mesma do `400` do cálculo —, com `mensagem` e `ID_PARA_CORRIGIR`.

REGRAS: `RF-86`, `AC-133`, `AC-03`
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.casos.inventario import pendencias_de_inventario
from app.concorrencia import duas_em_paralelo
from app.http.isolamento import exigir_caso_da_sessao
from app.http.rotas_calculo import formatar_pendencia_inventario
from app.http.rotas_coleta import _itens_por_escopo
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.respostas import RespostasCaso
from persistencia.app_aluno.itens import RepositorioItens, RepositorioItensSupabase
from persistencia.app_aluno.respostas import RepositorioRespostas, RepositorioRespostasSupabase

REGRAS: Final[tuple[str, ...]] = ("RF-86", "AC-133", "AC-03")

roteador = APIRouter(prefix="/caso", tags=["inventario"])


def obter_colecao_de_registros_do_inventario() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros para esta rota."""
    return carregar_registros()


def obter_repositorio_respostas_do_inventario() -> RepositorioRespostas:
    """Ponto único de injeção do repositório de respostas para esta rota."""
    return RepositorioRespostasSupabase()


def obter_repositorio_itens_do_inventario() -> RepositorioItens:
    """Ponto único de injeção do repositório de itens para esta rota."""
    return RepositorioItensSupabase()


@roteador.get("/{CASO_ID}/inventario")
def inventario_do_caso(
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros_do_inventario)],
    repositorio_respostas: Annotated[
        RepositorioRespostas, Depends(obter_repositorio_respostas_do_inventario)
    ],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens_do_inventario)],
) -> JSONResponse:
    """`RF-86` — `200 {pendencias: [...]}`; lista vazia quando o inventário
    está completo. Isolamento por caso: `401` sem sessão, `404` para caso
    alheio (`exigir_caso_da_sessao`, `AC-03`)."""
    respostas_brutas, itens_por_escopo = duas_em_paralelo(
        lambda: repositorio_respostas.listar_do_caso(CASO_ID),
        lambda: _itens_por_escopo(repositorio_itens, CASO_ID),
    )
    pendencias = pendencias_de_inventario(
        colecao.registros, RespostasCaso(respostas=respostas_brutas), itens_por_escopo
    )
    return JSONResponse({"pendencias": [formatar_pendencia_inventario(p) for p in pendencias]})
