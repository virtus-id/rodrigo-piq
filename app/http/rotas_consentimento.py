"""Rota de consentimento — `RF-30`, `AC-39` (T-36).

`POST /caso/{CASO_ID}/consentimento` é o ÚNICO caminho de código desta
feature que grava um `RegistroConsentimento` E dispara a transição
`registra_consentimento` (`CADASTRADO → CONSENTIMENTO_REGISTRADO`,
`app/casos/maquina.py`, T-33) — um único caminho, como exige o critério de
aceite desta tarefa, para que registro e transição nunca fiquem
dessincronizados (aceite gravado sem o caso avançar, ou vice-versa).

**A guarda de verdade não vive aqui.** Esta rota só ORQUESTRA: carrega o
texto vigente (`app.consentimento.registro.carregar_texto_vigente`), grava o
carimbo de aceite (`persistencia.app_aluno.consentimentos.
RepositorioConsentimentos`) e transiciona o estado do caso
(`persistencia.app_aluno.casos.RepositorioCasos.transicionar_estado`, que
delega a `app.casos.maquina.transicionar` — a própria tabela recusa
`(CADASTRADO, COLETA_INICIAL)` direto, e RECUSA também `(estado_atual,
CONSENTIMENTO_REGISTRADO)` para qualquer `estado_atual` que não seja
`CADASTRADO`, com `ErroTransicaoNaoDeclarada`). A guarda "sem consentimento,
nenhuma resposta é gravada" propriamente dita está em
`persistencia/app_aluno/respostas.py::RepositorioRespostasSupabase.gravar`
(chama `app.casos.maquina.exigir_estado_permite_resposta`) — verificável sem
esta rota, sem HTTP, chamando as duas funções de domínio diretamente
(`tests/app_aluno/test_guarda_consentimento_resposta.py`).

**Isolamento por `CASO_ID` (`RF-02`, `AC-03`, T-31).** A rota declara
`Depends(exigir_caso_da_sessao("CASO_ID"))`, o mesmo mecanismo de qualquer
outra rota desta feature que recebe `CASO_ID` — sessão ausente recusa antes
de tocar o banco; caso de outra conta devolve `404`, nunca `403`.

**Sem `PEND-01`, a rota bloqueia.** Se `carregar_texto_vigente()` levantar
`ErroTextoConsentimentoAusente` (nenhum `.yaml` publicado em
`app/consentimento/textos/`), a rota devolve `503` — nunca assume um texto
padrão nem avança o estado do caso sem ele.

REGRAS: `RF-30`, `AC-39`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Final
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.casos.maquina import ESTADO_CASO, transicionar
from app.casos.progresso import transicionar_e_registrar
from app.consentimento.registro import (
    ErroTextoConsentimentoAusente,
    RegistroConsentimento,
    carregar_texto_vigente,
    registrar_consentimento,
)
from app.http.isolamento import exigir_caso_da_sessao, obter_repositorio_casos
from persistencia.app_aluno.casos import RepositorioCasos
from persistencia.app_aluno.consentimentos import (
    RepositorioConsentimentos,
    RepositorioConsentimentosSupabase,
)
from persistencia.app_aluno.eventos import (
    RepositorioEventosCaso,
    RepositorioEventosCasoSupabase,
)

REGRAS: Final[tuple[str, ...]] = ("RF-30", "AC-39")


roteador = APIRouter(prefix="/caso", tags=["consentimento"])

# Mensagem curta de propósito — mesma disciplina de `app/http/isolamento.py`
# (`AC-37`, T-08): fica sob o limiar de 40 caracteres do teste estático.
_MENSAGEM_TEXTO_AUSENTE: Final[str] = "PEND-01: texto indisponível."


class ErroCasoDesaparecidoAposIsolamento(Exception):
    """Defensivo: `exigir_caso_da_sessao` já garantiu que `CASO_ID` existe e
    pertence à conta da sessão — este erro só ocorreria numa condição de
    corrida extrema (caso removido entre a checagem de isolamento e esta
    consulta), nunca em uso normal."""

    def __init__(self, caso_id: str) -> None:
        super().__init__(f"CASO_ID={caso_id!r} desapareceu após isolamento confirmá-lo")


def obter_repositorio_consentimentos() -> RepositorioConsentimentos:
    """Ponto único de injeção do repositório de consentimentos — sobrescrito
    nos testes via `app.dependency_overrides`, mesmo padrão de
    `app/http/rotas_conta.py::obter_repositorio_contas` e `app/http/
    isolamento.py::obter_repositorio_casos`."""
    return RepositorioConsentimentosSupabase()


def obter_repositorio_eventos() -> RepositorioEventosCaso:
    """`T-91` (`RF-31`, `AC-40`) — ponto único de injeção do repositório da
    trilha de eventos do caso, sobrescrito nos testes via
    `app.dependency_overrides`, mesmo padrão das demais dependências desta
    rota."""
    return RepositorioEventosCasoSupabase()


async def _ler_formulario(request: Request) -> dict[str, str]:
    """Mesma decodificação de `app/http/rotas_conta.py::_ler_formulario` —
    stdlib (`parse_qsl`), sem `python-multipart` (fora do plano)."""
    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return dict(pares)


@roteador.post("/{CASO_ID}/consentimento")
async def processar_consentimento(
    request: Request,
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    repositorio_consentimentos: Annotated[
        RepositorioConsentimentos, Depends(obter_repositorio_consentimentos)
    ],
    repositorio_casos: Annotated[RepositorioCasos, Depends(obter_repositorio_casos)],
    repositorio_eventos: Annotated[RepositorioEventosCaso, Depends(obter_repositorio_eventos)],
) -> JSONResponse:
    """Único caminho que grava o aceite E dispara `registra_consentimento`.

    Ordem: (1) carrega o texto vigente — bloqueia com `503` se `PEND-01`
    ainda não publicou nenhum; (2) valida a transição contra a MÁQUINA de
    estados (`app.casos.maquina.transicionar`, não apenas contra o
    repositório — `RepositorioCasos.transicionar_estado` persiste o estado
    recebido sem revalidar a tabela de transições, então é esta rota quem
    garante que só `CADASTRADO → CONSENTIMENTO_REGISTRADO` é aceito, nunca
    um estado arbitrário); (3) grava o `RegistroConsentimento`; (4) só então
    persiste a transição E registra o evento na trilha
    (`app.casos.progresso.transicionar_e_registrar`, `T-91`, `RF-31`/`AC-40`)
    num único passo. Se o texto estiver ausente, ou o caso não estiver em
    `CADASTRADO`, nem o registro nem a transição ocorrem."""
    try:
        texto = carregar_texto_vigente()
    except ErroTextoConsentimentoAusente:
        return JSONResponse({"erro": _MENSAGEM_TEXTO_AUSENTE}, status_code=503)

    caso_atual = repositorio_casos.buscar(CASO_ID)
    if caso_atual is None:  # pragma: no cover — defensivo: exigir_caso_da_sessao já garantiu
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    # RF-01: valida contra a MÁQUINA antes de qualquer gravação — levanta
    # ErroTransicaoNaoDeclarada (não capturada aqui, propaga como 500) se o
    # caso não estiver em CADASTRADO. Nenhum registro de consentimento nem
    # transição ocorre se a validação falhar. Redundante, mas deliberado,
    # com a validação interna de `transicionar_e_registrar` (T-91, abaixo):
    # esta chamada recusa ANTES de gravar `RegistroConsentimento`, para que
    # uma transição inválida nunca deixe um registro de aceite órfão.
    transicionar(caso_atual.estado, ESTADO_CASO.CONSENTIMENTO_REGISTRADO)

    dados = await _ler_formulario(request)
    aceite = dados.get("aceite") == "on"

    agora = datetime.now(UTC)
    registro: RegistroConsentimento = registrar_consentimento(CASO_ID, texto, aceite, agora)
    repositorio_consentimentos.gravar(f"CONSENTIMENTO_{uuid.uuid4().hex}", registro)

    # T-91: transição E registro na trilha num único caminho — nunca dois
    # passos separados que poderiam dessincronizar.
    caso_atualizado = transicionar_e_registrar(
        repositorio_casos=repositorio_casos,
        repositorio_eventos=repositorio_eventos,
        caso_id=CASO_ID,
        de=caso_atual.estado,
        para=ESTADO_CASO.CONSENTIMENTO_REGISTRADO,
        agora=agora,
    )
    if caso_atualizado is None:  # pragma: no cover — defensivo: `transicionar`
        # acima já validou o par contra a máquina; só restaria uma corrida
        # concorrente extrema (outra transição já mudou o estado entre a
        # leitura de `caso_atual` e este ponto), fora do fluxo normal desta
        # rota (sem concorrência real sobre CADASTRADO documentada no plano).
        raise ErroCasoDesaparecidoAposIsolamento(CASO_ID)

    return JSONResponse(
        {"CASO_ID": caso_atualizado.CASO_ID, "estado": caso_atualizado.estado.value}
    )
