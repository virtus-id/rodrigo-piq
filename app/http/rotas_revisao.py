"""Tela da fila de revisão humana — `RF-23`, `RF-25`, `AC-25`, `AC-28`
(T-69), com a guarda de papel de revisor de `T-100`; a tela de comparação
lado a lado (plano e `estado_inputs`) — `RF-26`, `AC-29` (T-70); e a ação de
liberar/reprovar — `RF-24`, `AC-27`, `EC-12` (T-71).

**Atualização de `T-100` — a lacuna de autorização abaixo foi FECHADA.** A
nota extensa a seguir (escrita em T-69) documentava, honestamente, que
`/revisao/*` ficava sem autenticação própria — decisão explícita, não
omissão silenciosa, mas registrada como limitação do piloto a ser resolvida.
O usuário decidiu fechar essa lacuna: `GET /revisao/fila` agora declara
`Depends(exigir_papel_revisor)` (`app/http/isolamento.py`, T-100) — a MESMA
dependência genérica que `T-71` (rotas de liberar/reprovar) vai reutilizar.
Sessão ausente ⇒ `401`; sessão de conta autenticada sem `e_revisor = true`
⇒ `403` (nunca `404` — a existência da tela não é segredo, o acesso é). O
texto abaixo permanece como registro histórico da decisão original de T-69
(por que a rota nasceu sem essa guarda) — não é mais o estado atual do
código, e a leitura completa desta atualização é necessária para entender a
evolução, não só o texto de baixo isoladamente.

`GET /revisao/fila` lista, em uma única tela, todos os `CASO_ID` cujo
`Caso.estado` é `AGUARDANDO_REVISAO` — incluindo recálculos: um caso que já
teve um snapshot liberado e volta a `AGUARDANDO_REVISAO` (segundo snapshot
do mesmo caso) aparece de novo, pelo mesmo mecanismo, porque a fila é uma
CONSULTA sobre o `estado` corrente (`app/revisao/fila.py`, ver a nota
extensa daquele módulo: "consulta, não tabela própria" — um snapshot novo
não é uma linha de fila nova, é só o caso voltando ao mesmo estado).

**Modelo de autorização desta tela — decisão explícita, não acidente
(`OQ-03` respondida em T-66: fila única, sem papéis/permissões/atribuição).**
Esta rota é DELIBERADAMENTE separada do isolamento por `CASO_ID` do aluno
(`app/http/isolamento.py`, T-31): ela não recebe nenhum `CASO_ID` de
sessão nem verifica posse de UM caso — ela lista TODOS os casos em
`AGUARDANDO_REVISAO`, de QUALQUER conta de aluno, porque um revisor
existe, por definição, para ver casos que não são os dele. Não há hoje, em
nenhum lugar desta feature, uma distinção de conta "revisora" vs. conta
"aluno" — `persistencia/app_aluno/contas.py` tem um único tipo de conta, e
a spec/`OQ-03` fecham "revisor único implícito" sem desenhar um sistema de
papéis (que `sdd.config.md` §6 proíbe inventar por conta própria: "nenhuma
decisão registrada na spec canônica fica a critério do desenvolvedor").

Diante disso, a rota `/revisao/*` ficava **fora do `SessionMiddleware` de
conta de aluno**: ela não declarava `Depends(exigir_caso_da_sessao(...))`
(não haveria `CASO_ID` de sessão para verificar — a tela é multi-caso por
natureza) nem qualquer outra dependência de autenticação, porque misturar os
dois modelos (sessão de aluno vs. acesso de revisor) numa mesma dependência
seria fingir uma distinção de papel que o sistema não modelava ainda.
**Limitação conhecida do piloto, documentada em T-69 em vez de resolvida por
invenção:** naquela entrega, `/revisao/*` não exigia autenticação alguma —
era acessível a quem alcançasse a URL, exatamente como uma rota
interna/operacional isolada de rede (proxy reverso, VPN, allowlist de IP)
teria que ficar, no piloto, FORA da aplicação FastAPI e a cargo da infra de
implantação. Isto ficou registrado como `Open Question` de segurança do
piloto — não uma omissão silenciosa.

**`T-100` fechou essa lacuna**, sem recriar o sistema de papéis que `OQ-03`
descartou: `app_aluno.contas.e_revisor` (`persistencia/supabase/migracoes/
003_papel_revisor.sql`) e `Depends(exigir_papel_revisor)` (`app/http/
isolamento.py`) agora exigem, no servidor, que a sessão pertença a uma conta
com `e_revisor = true` — ANTES de `RepositorioCasos.listar_por_estado` ser
chamado. `OQ-03` fala de ATRIBUIÇÃO DE CASOS dentro da fila (revisor A vs.
revisor B com filas separadas) — não de a fila ser acessível sem
credencial; `e_revisor` continua sendo uma fila ÚNICA para todo revisor, sem
nenhuma atribuição por revisor individual.

Esta rota **continua fora** da auditoria de isolamento por `CASO_ID`
(`tests/app_aluno/e2e/test_mecanismo_isolamento.py::
rotas_sem_isolamento_por_caso`, T-31/T-32) pelo MESMO motivo estrutural de
T-69: aquele mecanismo audita rotas que recebem `CASO_ID` de aluno via
path/query parameter, para garantir que TODA rota assim protege a posse do
caso; `/revisao/fila` nunca recebe `CASO_ID` como parâmetro de rota (ela
lista, não busca um caso por identificador) — não é uma rota "esquecida" da
auditoria, é estruturalmente fora do domínio que aquele mecanismo audita,
porque o revisor vendo todos os casos é a definição do papel, não uma falha
de isolamento. `T-100` complementa essa auditoria com um teste NOVO e
SEPARADO (`tests/app_aluno/test_rotas_revisao.py`) que prova que a guarda de
PAPEL (não de caso) existe e funciona — as duas auditorias cobrem domínios
diferentes e nenhuma substitui a outra.

**"A tela não expõe caso de outra conta ao aluno" (critério de aceite).**
Este critério é satisfeito pela SEPARAÇÃO DE ROTA — `/caso/{CASO_ID}/...`
(rotas do aluno, T-30/T-36/T-42/T-56/T-63/T-64) sempre passa por `exigir_
caso_da_sessao` e nunca lista mais de um caso; `/revisao/fila` é uma rota
INTEIRAMENTE DIFERENTE, sem prefixo `/caso/` — **e agora, desde `T-100`,
reforçada pela guarda de papel**: um aluno comum (conta com `e_revisor =
false`) que descobrisse a URL recebe `403`, não vê a fila.

**Nenhum valor é calculado (Lei nº 3).** Todo campo exibido é uma LEITURA
de `ItemFila`/`SnapshotOrdem` (`app/revisao/fila.py`, T-66): `CASO_ID`,
`SNAPSHOT_ID`, `versao`, `DATA_REFERENCIA`, `MOTIVO_RECALCULO`,
`EVENTO_RECALCULO`, `METODO_RECOMENDADO_PIQ`, `STATUS_METODO`,
`entra_por_politica`, `e_metodologico` — nenhuma soma, nenhuma derivação,
nenhuma agregação nova. `AC-28`: `entra_por_politica` e `e_metodologico`
chegam ao template como dois campos SEPARADOS de `ItemFila` (nunca
combinados numa única expressão, mesma disciplina de `app/revisao/
fila.py`), e o template os torna visivelmente distintos por um rótulo cada
(ver `app/http/serializacao_plano.py::serializar_item_da_fila`, que
mantém os dois campos separados no JSON).

**`GET /revisao/caso/{CASO_ID}` (`RF-26`, `AC-29`, T-70).** Mostra, na MESMA
sessão e sem navegação para outro caso, o plano do snapshot mais recente do
caso **exatamente como o aluno o verá** — reutilizando `report.plano.
montar_contexto_plano`/`report.pdf.renderizar_html_do_plano`, o MESMO par
função+template de `app/http/rotas_plano.py` (T-60/T-63/T-64), sem segunda
redação — e os `estado_inputs` completos que o produziram
(`report.plano.montar_contexto_estado_inputs`, T-70), com `DESCONHECIDO`
visível como tal (nunca `0`/vazio, `RF-16`). **Diferença deliberada em
relação à rota do aluno**: esta tela mostra o snapshot mais recente da
cadeia — inclusive quando ainda `AGUARDANDO_REVISAO`, sem liberação
registrada — porque é exatamente o que o revisor precisa avaliar; a rota do
aluno (`AC-25`) faz o oposto (só o liberado). As duas nunca compartilham
código de decisão de liberação: `montar_contexto_plano`/`renderizar_html_do_
plano` não exigem liberação (só `report.pdf.gerar_html_do_plano_liberado`,
usado exclusivamente pela rota do aluno, exige). Protegida pela MESMA
`exigir_papel_revisor` de `T-100` — nunca `exigir_caso_da_sessao` (T-31): o
revisor não é "dono" do caso no sentido de `app/http/isolamento.py`, ele
acessa qualquer caso por definição de papel (mesma nota de `/revisao/fila`
acima).

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.casos.maquina` (`ESTADO_CASO`, `Caso`), `app.revisao.fila`
(`listar_fila_de_revisao`, e desde T-71: `liberar`, `reprovar`,
`ErroRevisaoJaDecidida`, os `Protocol`s `RepositorioCasosDaDecisao`/
`RepositorioRevisoesDaDecisao`), `app.http.isolamento` (`exigir_papel_revisor`,
desde `T-100` — a nota acima documenta por que T-69 NÃO importava daquele
módulo; T-100 passa a importar exatamente `exigir_papel_revisor`, nunca
`exigir_caso_da_sessao`, que continua sem uso aqui), `persistencia.app_aluno.
casos` (`RepositorioCasos`), `persistencia.app_aluno.revisoes` (desde T-71:
`RepositorioRevisoes`/`RepositorioRevisoesSupabase`), `persistencia.supabase.
repositorio_snapshots` (o adaptador concreto da porta do motor) e, desde
T-70, `report.plano` (`carregar_textos_canonicos`, `montar_contexto_plano`,
`montar_contexto_estado_inputs`) e `report.pdf` (`renderizar_html_do_plano`)
— nunca de `engine/` além dos nomes já liberados transitivamente pela porta
`RepositorioSnapshots` (`AC-41`).

**T-71 — a ação de liberar e reprovar (`RF-24`, `AC-27`, `EC-12`).**
`GET /revisao/caso/{CASO_ID_REVISAO}/decisao` exibe o formulário de decisão
(sem campo de autor — ver abaixo); `POST` no mesmo caminho processa a
decisão. Esta rota nunca grava `RegistroRevisao` nem transiciona `Caso`
diretamente: ela só monta os argumentos de `app.revisao.fila.liberar`/
`reprovar` (T-68) e delega — mesmo precedente de `app/http/
rotas_consentimento.py::processar_consentimento` (T-36), "registro e
transição nunca ficam dessincronizados" fica inteiramente do lado da função
de domínio, não desta rota.

**`autor` vem exclusivamente da sessão do revisor (`exigir_papel_revisor`),
nunca de um campo do formulário — é isso que torna `AC-27` real, não
decorativo.** O formulário HTML de `decisao.html` não tem NENHUM campo
`autor`: só `decisao` (`LIBERAR`/`REPROVAR`) e `observacao` (texto livre do
revisor, gravado junto à decisão). Se o formulário tivesse um campo `autor`
editável, qualquer requisição poderia atribuir a decisão a outra pessoa —
o `conta_id` que `exigir_papel_revisor` devolve já foi verificado, no
servidor, a cada requisição, contra `RepositorioContas.buscar_por_id`
(`app/http/isolamento.py`, T-100); é este valor, nunca um campo de entrada
do usuário, que vira `RegistroRevisao.autor`.

**`classificacao_erro` do formulário (`RF-26`, `T-72`).** O campo
`classificacao_erro` do `POST`, quando presente, é convertido para o enum
fechado `app.revisao.fila.CLASSIFICACAO_ERRO` (seis rótulos, `OQ-12` aberta
— ver a docstring daquele enum) antes de chegar a `reprovar`; um valor fora
dos seis nomes devolve `422` (`_MENSAGEM_CLASSIFICACAO_INVALIDA`), nunca é
gravado como texto livre. `classificacao_erro` só é lido no ramo `REPROVAR`
— liberação nunca carrega classificação de erro.

**Nenhuma rota de edição nem de remoção existe sobre `/revisao/*`.** Só
`GET`/`POST` são declarados neste módulo (nenhum `PUT`/`PATCH`/`DELETE`) —
e a própria interface de persistência (`persistencia.app_aluno.revisoes.
RepositorioRevisoes`, T-67) não declara `atualizar`/`remover`: mesmo que
uma rota futura tentasse mutar um registro, não haveria verbo do repositório
para chamar. Verificado por enumeração de `app.routes`
(`tests/app_aluno/test_rotas_revisao_decisao.py`, T-71), mesmo padrão de
`tests/app_aluno/e2e/test_mecanismo_isolamento.py::rotas_sem_isolamento_por_
caso` (T-32).

REGRAS: `RF-23`, `RF-25`, `AC-25`, `AC-28`, `RF-26`, `AC-29`, `RF-24`,
`AC-27`, `EC-12`
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.casos.maquina import Caso
from app.http.isolamento import (
    exigir_papel_revisor,
    obter_repositorio_contas_para_papel,
)
from app.notificacao.email import (
    EnviadorDeEmail,
    obter_enviador,
)
from app.notificacao.mensagens import plano_liberado
from app.revisao.fila import (
    CLASSIFICACAO_ERRO,
    ErroRevisaoJaDecidida,
    ItemFila,
    RepositorioCasosDaDecisao,
    RepositorioRevisoesDaDecisao,
    liberar,
    reprovar,
)
from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import RepositorioCasos, RepositorioCasosSupabase
from persistencia.app_aluno.contas import RepositorioContas
from persistencia.app_aluno.eventos import (
    RepositorioEventosCaso,
    RepositorioEventosCasoSupabase,
)
from persistencia.app_aluno.revisoes import RepositorioRevisoesSupabase
from persistencia.supabase.repositorio_snapshots import RepositorioSnapshotsSupabase

REGRAS: Final[tuple[str, ...]] = (
    "RF-23",
    "RF-25",
    "AC-25",
    "AC-28",
    "RF-26",
    "AC-29",
    "RF-24",
    "AC-27",
    "EC-12",
)

# Mensagens curtas de propósito — mesma disciplina de `app/http/isolamento.py`
# (`AC-37`, T-08): ficam sob o limiar de 40 caracteres do teste estático.
_MENSAGEM_CASO_SEM_SNAPSHOT: Final[str] = "Caso sem snapshot para comparar."
_MENSAGEM_DECISAO_INVALIDA: Final[str] = "Decisão inválida: LIBERAR/REPROVAR."
_MENSAGEM_CLASSIFICACAO_INVALIDA: Final[str] = "Classificação de erro inválida."

roteador = APIRouter(prefix="/revisao", tags=["revisao"])



def obter_repositorio_casos_da_fila() -> RepositorioCasos:
    """Ponto único de injeção de `RepositorioCasos` para esta rota —
    sobrescrito nos testes via `app.dependency_overrides`, mesmo padrão de
    `app.http.isolamento.obter_repositorio_casos`. Declarado à parte (em vez
    de reaproveitar aquele) porque a fila não importa `app.http.isolamento`
    (ver a nota do módulo sobre a separação deliberada dos dois modelos)."""
    return RepositorioCasosSupabase()


def obter_repositorio_snapshots_da_fila() -> RepositorioSnapshots:
    """Ponto único de injeção da porta `RepositorioSnapshots` para esta
    rota — mesmo padrão de `app/http/rotas_plano.py::
    obter_repositorio_snapshots`."""
    return RepositorioSnapshotsSupabase()


def _item_para_contexto(item: ItemFila) -> dict[str, object]:
    """Achata um `ItemFila` nos campos que o template consome — cada valor
    é uma LEITURA direta de `ItemFila`/`SnapshotOrdem`, nunca uma soma ou
    derivação (Lei nº 3). `entra_por_politica` e `e_metodologico` seguem
    como dois campos DISTINTOS (`AC-28`), nunca combinados aqui."""
    snapshot = item.snapshot
    return {
        "CASO_ID": item.CASO_ID,
        "SNAPSHOT_ID": snapshot.SNAPSHOT_ID,
        "versao": snapshot.versao,
        "DATA_REFERENCIA": snapshot.DATA_REFERENCIA,
        "MOTIVO_RECALCULO": snapshot.MOTIVO_RECALCULO,
        "EVENTO_RECALCULO": snapshot.EVENTO_RECALCULO,
        "METODO_RECOMENDADO_PIQ": snapshot.METODO_RECOMENDADO_PIQ,
        "STATUS_METODO": snapshot.STATUS_METODO,
        "entra_por_politica": item.entra_por_politica,
        "e_metodologico": item.e_metodologico,
    }


# ---------------------------------------------------------------------------
# T-144: helpers e pontos de injeção que sobreviveram à remoção das TELAS.
# As telas do revisor viraram React (`/api/revisao/*`); o que está abaixo
# NÃO é tela — é o que a decisão precisa para funcionar, e os testes
# sobrescrevem via `app.dependency_overrides`.
# ---------------------------------------------------------------------------

def obter_repositorio_revisoes_da_decisao() -> RepositorioRevisoesDaDecisao:
    """Ponto único de injeção do repositório de revisões — sobrescrito nos
    testes via `app.dependency_overrides`."""
    return RepositorioRevisoesSupabase()


def obter_repositorio_eventos_da_decisao() -> RepositorioEventosCaso:
    """Ponto único de injeção da trilha de eventos (`T-91`, `RF-31`)."""
    return RepositorioEventosCasoSupabase()


async def _ler_formulario_de_decisao(request: Request) -> dict[str, str]:
    """`application/x-www-form-urlencoded` via `parse_qsl` (stdlib) — mesma
    decisão das demais rotas: `python-multipart` está fora do plano."""
    from urllib.parse import parse_qsl

    corpo = await request.body()
    return dict(parse_qsl(corpo.decode("utf-8"), keep_blank_values=True))


def _avisar_plano_liberado(
    conta_id: str,
    repositorio_contas: RepositorioContas,
    enviador: EnviadorDeEmail,
) -> None:
    """Avisa o ALUNO de que o plano dele saiu — `RF-31`, `T-182`.

    **Nada aqui pode derrubar a liberação.** Quando esta função é chamada, a
    decisão do revisor já está gravada e o plano já está acessível. Uma
    falha de e-mail — SMTP fora do ar, variável de ambiente esquecida,
    conta sem e-mail — é um aviso não entregue, não uma liberação
    desfeita. Por isso tudo é capturado aqui e nada propaga.

    O silêncio não é total: `email.py` já registra a falha, e o aluno
    continua podendo entrar e ver o plano por conta própria.

    **`except Exception`, deliberadamente — não é preguiça de enumerar.** A
    primeira versão capturava só os três erros de e-mail
    (`ErroConfiguracaoEmail`, `ErroEnvioEmail`, `ErroUrlBaseAusente`) e a
    promessa do parágrafo acima era falsa: a busca da conta também está
    aqui dentro, e um `ErroConexaoAusente` dela escapava e derrubava a
    liberação já gravada. Enumerar exceções obriga a prever tudo o que as
    duas dependências podem levantar, hoje e depois de cada mudança nelas —
    e errar por omissão custa uma liberação perdida. O critério certo não é
    QUAL erro aconteceu, é ONDE: nada deste bloco é essencial à liberação,
    então nada deste bloco a desfaz.

    `BaseException` continua propagando: `KeyboardInterrupt` e
    `SystemExit` não são falha de aviso, são o processo encerrando."""
    try:
        conta = repositorio_contas.buscar_por_id(conta_id)
        if conta is None:  # pragma: no cover — defensivo: o caso tem dono
            return
        mensagem = plano_liberado()
        enviador.enviar(conta.email, mensagem.assunto, mensagem.corpo)
    except Exception:
        return


def _buscar_caso_e_snapshot_mais_recente(
    caso_id: str,
    repositorio_casos: RepositorioCasosDaDecisao,
    repositorio_snapshots: RepositorioSnapshots,
) -> tuple[Caso, SnapshotOrdem]:
    """O caso e o ÚLTIMO snapshot da cadeia — é sobre ele que a decisão
    recai. `404` quando o caso não existe ou não tem snapshot: o revisor
    não decide sobre o que não há.

    **A cadeia se busca por `caso.snapshot_raiz_id`, nunca por `caso_id`**
    (`OQ-11`): `SnapshotOrdem` não modela um campo de caso próprio, e
    `historico` agrupa pela RAIZ da cadeia (ver a docstring de
    `persistencia/arquivo/repositorio_snapshots.py::historico`). Passar o
    `CASO_ID` aqui devolve sempre vazio — e o revisor veria `404` num caso
    que existe e tem plano. Mesmo idioma de `app/revisao/fila.py:276`."""
    caso = repositorio_casos.buscar(caso_id)
    if caso is None or caso.snapshot_raiz_id is None:
        raise HTTPException(status_code=404, detail=_MENSAGEM_CASO_SEM_SNAPSHOT)

    historico = repositorio_snapshots.historico(caso.snapshot_raiz_id)
    if not historico:
        raise HTTPException(status_code=404, detail=_MENSAGEM_CASO_SEM_SNAPSHOT)

    return caso, historico[-1]


@roteador.get("/caso/{CASO_ID_REVISAO}/decisao")
def formulario_de_decisao(
    CASO_ID_REVISAO: str,
    repositorio_casos: Annotated[
        RepositorioCasosDaDecisao, Depends(obter_repositorio_casos_da_fila)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots_da_fila)
    ],
    conta_id_revisor: Annotated[str, Depends(exigir_papel_revisor)],
) -> JSONResponse:
    """O que a tela de decisão precisa saber ANTES de decidir (`RF-24`,
    `RF-26`, `AC-27`).

    **Nenhum campo `autor`** (`AC-27`): o autor é o `conta_id` da sessão do
    revisor, já verificado por `exigir_papel_revisor`. Pedir o autor como
    entrada editável permitiria assinar a decisão com o nome de outra
    pessoa — por isso ele não aparece aqui nem como valor sugerido.

    **Os seis rótulos saem do enum, nunca de uma lista escrita aqui**: um
    sétimo rótulo só pode nascer em `CLASSIFICACAO_ERRO`, num lugar só.

    **Sem glosa** (`OQ-12` ABERTA): cada rótulo vai como o próprio nome, sem
    descrição, definição ou exemplo. O texto normativo da §25 não consta da
    canônica; inventar a explicação aqui faria o revisor classificar por uma
    definição que ninguém aprovou. A glosa entra quando a especialista
    responder `OQ-12` — e entrará neste enum, não nesta rota."""
    _caso, snapshot = _buscar_caso_e_snapshot_mais_recente(
        CASO_ID_REVISAO, repositorio_casos, repositorio_snapshots
    )

    return JSONResponse(
        {
            "CASO_ID": CASO_ID_REVISAO,
            "SNAPSHOT_ID": snapshot.SNAPSHOT_ID,
            "versao": snapshot.versao,
            "decisoes": ["LIBERAR", "REPROVAR"],
            "classificacoes_erro": [c.value for c in CLASSIFICACAO_ERRO],
        }
    )


@roteador.post("/caso/{CASO_ID_REVISAO}/decisao")
def processar_decisao(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario_de_decisao)],
    CASO_ID_REVISAO: str,
    repositorio_casos: Annotated[
        RepositorioCasosDaDecisao, Depends(obter_repositorio_casos_da_fila)
    ],
    repositorio_snapshots: Annotated[
        RepositorioSnapshots, Depends(obter_repositorio_snapshots_da_fila)
    ],
    repositorio_revisoes: Annotated[
        RepositorioRevisoesDaDecisao, Depends(obter_repositorio_revisoes_da_decisao)
    ],
    repositorio_eventos: Annotated[
        RepositorioEventosCaso, Depends(obter_repositorio_eventos_da_decisao)
    ],
    conta_id_revisor: Annotated[str, Depends(exigir_papel_revisor)],
    # `T-182`: para avisar o ALUNO quando o plano for liberado. O
    # repositório de contas é o mesmo que `exigir_papel_revisor` já usa —
    # reaproveitado, não duplicado.
    repositorio_contas: Annotated[
        RepositorioContas, Depends(obter_repositorio_contas_para_papel)
    ],
    enviador: Annotated[EnviadorDeEmail, Depends(obter_enviador)],
) -> JSONResponse:
    """`RF-24`/`AC-27`/`EC-12` — processa a decisão do revisor (liberar ou
    reprovar) sobre o snapshot mais recente do caso, delegando TODA a
    orquestração a `app.revisao.fila.liberar`/`reprovar` (T-68): esta rota
    nunca grava `RegistroRevisao` nem transiciona `Caso` diretamente, só
    monta os argumentos e chama a função de domínio correspondente.

    **`autor` vem exclusivamente de `conta_id_revisor` (`exigir_papel_
    revisor`, a sessão do revisor autenticado) — nunca de um campo do
    formulário.** É essa origem que torna `AC-27` real: um campo de
    formulário livre poderia ser preenchido com qualquer texto por quem
    envia a requisição; `conta_id_revisor` é o `conta_id` que a sessão
    assinada carrega e que `exigir_papel_revisor` já verificou pertencer a
    uma conta com `e_revisor = true`, consultando o banco a cada
    requisição — nenhum campo `autor` é sequer lido de `dados` abaixo.

    O formulário só contribui `decisao` (`"LIBERAR"`/`"REPROVAR"`) e
    `observacao` (texto livre do revisor, gravado junto à decisão,
    `RF-24`). Uma decisão sobre um caso que já saiu de `AGUARDANDO_REVISAO`
    (`ErroRevisaoJaDecidida`) devolve `409` — nunca uma segunda gravação
    silenciosa (mesma disciplina de `app/revisao/fila.py`).

    **`def`, não `async def` — `T-187`.** `liberar`/`reprovar` gravam no
    banco, e `_avisar_plano_liberado` envia e-mail por SMTP — as duas
    bloqueantes. Ver a nota em `rotas_api_conta.py::cadastrar`."""
    caso, snapshot = _buscar_caso_e_snapshot_mais_recente(
        CASO_ID_REVISAO, repositorio_casos, repositorio_snapshots
    )

    decisao = dados.get("decisao", "")
    observacao = dados.get("observacao") or None

    agora = datetime.now(UTC)
    revisao_id = f"REVISAO_{uuid.uuid4().hex}"

    if decisao == "LIBERAR":
        try:
            liberar(
                revisao_id=revisao_id,
                caso_id=CASO_ID_REVISAO,
                snapshot=snapshot,
                autor=conta_id_revisor,
                decidido_em=agora,
                repositorio_revisoes=repositorio_revisoes,
                repositorio_casos=repositorio_casos,
                repositorio_eventos=repositorio_eventos,
                observacao=observacao,
            )
        except ErroRevisaoJaDecidida as erro:
            raise HTTPException(status_code=409, detail=str(erro)) from erro

        # **O aviso que a interface promete** — `RF-31`, `T-182`.
        #
        # `TrilhaDaJornada` diz "Avisamos por e-mail" e `TelaAguardando`
        # diz "Avisaremos por e-mail assim que o plano estiver liberado".
        # Até `T-180` não havia envio nenhum: o aluno terminava a coleta,
        # fechava o navegador, e nunca ficava sabendo que o plano saiu — o
        # ponto de abandono mais provável do piloto.
        #
        # **DEPOIS de `liberar`, nunca antes.** Um e-mail dizendo "seu
        # plano está pronto" enviado antes da transição confirmada levaria
        # o aluno a uma tela que ainda recusa mostrar o plano (`AC-25`).
        #
        # **Falha de envio não desfaz a liberação.** A decisão do revisor
        # está gravada e o plano, acessível; devolver erro aqui faria o
        # revisor decidir de novo, e a segunda tentativa bateria em `409`.
        _avisar_plano_liberado(caso.conta_id, repositorio_contas, enviador)
    elif decisao == "REPROVAR":
        classificacao_erro_bruta = dados.get("classificacao_erro") or None
        classificacao_erro: CLASSIFICACAO_ERRO | None = None
        if classificacao_erro_bruta is not None:
            try:
                classificacao_erro = CLASSIFICACAO_ERRO(classificacao_erro_bruta)
            except ValueError as erro:
                raise HTTPException(
                    status_code=422, detail=_MENSAGEM_CLASSIFICACAO_INVALIDA
                ) from erro
        try:
            reprovar(
                revisao_id=revisao_id,
                caso_id=CASO_ID_REVISAO,
                snapshot=snapshot,
                autor=conta_id_revisor,
                decidido_em=agora,
                repositorio_revisoes=repositorio_revisoes,
                repositorio_casos=repositorio_casos,
                repositorio_eventos=repositorio_eventos,
                classificacao_erro=classificacao_erro,
                observacao=observacao,
            )
        except ErroRevisaoJaDecidida as erro:
            raise HTTPException(status_code=409, detail=str(erro)) from erro
    else:
        raise HTTPException(status_code=422, detail=_MENSAGEM_DECISAO_INVALIDA)

    return JSONResponse({"CASO_ID": CASO_ID_REVISAO, "decisao": decisao})
