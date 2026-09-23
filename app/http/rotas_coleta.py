"""Rota de resposta — os sete passos do plano `plans/app-aluno.plan.md` §5.1
(`RF-05`, `RF-07`, `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-01`, `EC-02`,
`EC-05`, T-42).

`POST /caso/{CASO_ID}/resposta` é o ÚNICO caminho de código desta feature que
grava uma resposta de coleta a partir de uma requisição HTTP. Orquestra, na
ORDEM EXATA do plano, os módulos já entregues por tarefas anteriores — esta
rota não reimplementa nenhuma das sete regras, só as encadeia:

    1. isolamento: a sessão possui este CASO_ID? (`app/http/isolamento.py`,
       T-31) — não ⇒ 404/401, antes de qualquer leitura de dado do caso.
    2. registro carregado por ID (`collection/carga.py`, T-16) e verificação
       de que a pergunta está de fato aberta — condição de exibição
       verdadeira sobre as respostas já dadas (`collection/condicoes.py::
       avaliar`, T-11) — falsa ⇒ recusada, sem gravação.
    3. "não sei" marcado ⇒ grava `NAO_SEI` e PULA a conversão de tipo
       (`collection/respostas.py::NAO_SEI`, T-22).
    4. conversão para o tipo Python de cada `TipoResposta` (`_resolver_
       valor`, T-42/T-101), quando a resposta não é `NAO_SEI`: `MOEDA`/
       `TAXA` via `app/montagem/conversao.py` (T-38); `SELECAO_MULTIPLA` via
       `frozenset[str]` dos valores marcados; `NUMERO`/`ESCALA_0_10` via
       `int`; `DATA` via `date`; os três restantes (`SELECAO_UNICA`,
       `TEXTO_CURTO`, `SIM_NAO_TALVEZ`) via `str` direto — falha de qualquer
       conversão ⇒ `EC-01`: recusa, não avança, nada é gravado, nunca
       trunca nem coage.
    5. validação cruzada, só quando o registro declara `validacoes_cruzadas`
       (`collection/validacao.py::validar_cruzada`, T-13) — falha ⇒ `EC-02`:
       recusa apontando os DOIS campos, nenhum é gravado.
    6. gravação com transação confirmada
       (`persistencia/app_aluno/respostas.py::RepositorioRespostasSupabase.
       gravar`, T-22) — falha ⇒ `EC-05`: NÃO reporta como salva.
    7. aviso de materialidade, se houver (`collection/materialidade.py::
       avaliar_ao_responder`, T-41) — incluído na MESMA resposta HTTP.

Só então a resposta HTTP é devolvida (`AC-02`): como o passo 6 já commitou a
transação (disciplina de T-22: `with _conectar()` só sai sem exceção após
`conexao.commit()`) ANTES de o passo 7 rodar e do `return` desta função,
encerrar o processo logo depois de receber a resposta HTTP nunca perde a
resposta — ela já está no banco antes de a função começar a montar o corpo
da resposta.

**Formato do payload — decisão desta tarefa.** `application/x-www-
form-urlencoded`, decodificado por `urllib.parse.parse_qsl` (stdlib), MESMO
padrão de `app/http/rotas_conta.py::_ler_formulario` e `app/http/
rotas_consentimento.py::_ler_formulario` — não introduz `python-multipart`
(fora do plano) e é o `enctype` que um `<form>` HTML nativo ou uma requisição
HTMX (`hx-post`, que por padrão envia `application/x-www-form-urlencoded`)
enviam sem configuração extra. Campos do corpo:

    ID_PERGUNTA   — obrigatório, o `RegistroPergunta.ID` respondido.
    item_id       — opcional; presente só quando a pergunta é `REP`
                    (DIVIDA_ID/VINCULO_ID/MARGEM_ID/... do item respondido).
    valor         — a resposta em texto bruto do campo do formulário; ignorado
                    quando `nao_sei` está presente. Para `SELECAO_MULTIPLA`
                    (T-101), o par `valor=...` aparece REPETIDO no corpo — um
                    por checkbox marcado (o cliente envia um par
                    `valor=` por opção marcada, mesma forma de um
                    formulário nativo — ver `frontend/src/componentes/
                    pergunta.html`, `name="valor"` repetido) — e
                    `_ler_todos_os_valores` lê TODOS eles, não só o último.
    nao_sei       — presente com QUALQUER valor não vazio ⇒ resposta é
                    `NAO_SEI` (mesma convenção de checkbox HTML de `aceite`
                    em `rotas_consentimento.py`: valor `"on"`, mas qualquer
                    valor não vazio já basta aqui, pois não há redação
                    normativa que amarre o texto do valor).

**Fronteira com `T-43`/`T-45` — o que esta rota NÃO faz.** O algoritmo de
"qual é a próxima pergunta" (retomada por posição no grafo condicional,
`app/casos/progresso.py::pendencias_obrigatorias`, consumida por T-45, ainda
não implementado) está fora do escopo desta tarefa. Esta rota devolve uma
confirmação de gravação (mais o aviso de materialidade, quando houver, e o
sinalizador de avanço de `T-44`) — nunca a pergunta seguinte completa
renderizada. A renderização da pergunta a partir do registro com HTMX
(`T-43`) consome esta rota como o alvo de `hx-post` de cada campo, mas o HTML
do formulário em si não nasce aqui.

**Obrigatoriedade `OBR`/`COND`/`OPT`/`REP` no avanço da coleta (`RF-09`,
`RF-11`, `AC-11`, T-44).** Depois do passo 6 (gravação confirmada), esta rota
consulta `app/casos/progresso.py::pendencias_obrigatorias` sobre TODOS os
registros carregados e o snapshot de respostas do caso (já incluindo a
resposta recém-gravada) e inclui o resultado (`avanco_permitido` mais a
contagem de pendências) na MESMA resposta HTTP de confirmação — nunca como
rota separada. Esta rota NÃO decide se a resposta atual é aceita com base em
obrigatoriedade (isso já ocorreu nos passos 2/4/5 acima, por registro
isolado); o sinalizador de avanço é sobre a COLETA COMO UM TODO, não sobre a
pergunta que acabou de ser respondida. Disparar a transição de estado
`COLETA_INICIAL → CALCULANDO` (`app/casos/maquina.py`, gatilho
`bloco_6_executa`) a partir deste sinalizador é trabalho de tarefa futura de
orquestração, fora do escopo declarado aqui.

Direção de dependência: este módulo importa de `fastapi`/stdlib, de
`app.http.isolamento`, `app.casos.maquina`, `app.montagem.conversao`, de
`collection/` (`carga`, `condicoes`, `validacao`, `respostas`,
`materialidade`) e de `persistencia.app_aluno.respostas` — nunca de
`engine/` além dos tipos já usados transitivamente por `collection.
materialidade` (fronteira de `tests/app_aluno/estatica/
test_fronteira_import_engine.py`, T-06, não tocada por este módulo).

REGRAS: `RF-05`, `RF-07`, `RF-09`, `RF-10`, `RF-11`, `RF-13`, `AC-02`, `AC-11`,
`EC-01`, `EC-02`, `EC-05`
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.casos.maquina import ErroConsentimentoNaoRegistrado
from app.casos.progresso import pendencias_obrigatorias
from app.http.isolamento import exigir_caso_da_sessao
from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
    converter_para_taxa,
)
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.condicoes import avaliar
from collection.materialidade import AvisoMaterialidade, avaliar_ao_responder
from collection.registro import EscopoRepeticao, RegistroPergunta, TipoResposta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso, ValorResposta
from collection.validacao import validar_cruzada
from persistencia.app_aluno.itens import RepositorioItens, RepositorioItensSupabase
from persistencia.app_aluno.respostas import (
    ErroCasoInexistenteParaResposta,
    ErroGravacaoResposta,
    RepositorioRespostas,
    RepositorioRespostasSupabase,
)

REGRAS: Final[tuple[str, ...]] = (
    "RF-05",
    "RF-07",
    "RF-09",
    "RF-10",
    "RF-11",
    "RF-13",
    "AC-02",
    "AC-11",
    "EC-01",
    "EC-02",
    "EC-05",
)


roteador = APIRouter(prefix="/caso", tags=["coleta"])

# Tipos de resposta que passam pela fronteira Decimal única (`app/montagem/
# conversao.py`) — os demais nove membros de `TipoResposta` são convertidos
# para seu próprio tipo Python diretamente em `_resolver_valor` (T-101:
# `frozenset[str]`, `int` ou `date`, conforme o tipo — nunca a string bruta).
_TIPOS_QUE_EXIGEM_CONVERSAO_DECIMAL: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.MOEDA, TipoResposta.TAXA}
)

# Mensagens curtas de propósito — mesma disciplina de `app/http/isolamento.py`
# e `app/http/rotas_consentimento.py` (`AC-37`, T-08): ficam sob o limiar de
# 40 caracteres do teste estático.
_MENSAGEM_PERGUNTA_NAO_ENCONTRADA: Final[str] = "Registro de pergunta inválido: ID desconhecido."
_MENSAGEM_PERGUNTA_NAO_ABERTA: Final[str] = "Pergunta não está aberta para resposta."
_MENSAGEM_FALHA_SALVAR: Final[str] = "Não foi possível salvar."


class ErroRegistroSemVariavelGravada(Exception):
    """Defensivo: nenhum registro real declara `VARIAVEL_GRAVADA=None`
    (T-17..T-19) — `RespostasCaso`/`avaliar`/`validar_cruzada` indexam por
    `Resposta.ID_PERGUNTA`, que esta rota grava como `VARIAVEL_GRAVADA` (não
    o `RegistroPergunta.ID` do payload), para que a leitura por variável
    (`RF-05`, `RF-07`) funcione com os mesmos módulos já usados por T-13/T-11
    sem duplicar a chave de indexação. Um registro sem `VARIAVEL_GRAVADA` não
    tem como ser gravado nem lido de volta por variável, e é recusado aqui em
    vez de silenciosamente usar o `ID` do registro como substituto."""


class ErroPerguntaDesconhecida(Exception):
    """`ID_PERGUNTA` recebido não corresponde a nenhum `RegistroPergunta`
    carregado — recusado antes de qualquer avaliação de condição ou
    conversão, nunca tratado como pergunta "sempre aberta" por omissão."""


class ErroPerguntaNaoAberta(Exception):
    """A `condicao_exibicao` do registro avalia como falsa sobre as
    respostas já gravadas do caso — a pergunta não está de fato aberta e a
    resposta é recusada, sem gravação (passo 2 do plano §5.1)."""


class ErroValorInvalido(Exception):
    """T-101 (`EC-01`) — mesmo papel de `app/montagem/conversao.py::
    ErroConversaoInvalida` para os três `TipoResposta` que essa fronteira
    não cobre (`NUMERO`, `ESCALA_0_10`, `DATA`): carrega o valor exatamente
    como recebido e o motivo, nunca uma mensagem genérica. Não reaproveita
    `ErroConversaoInvalida` porque aquela é do módulo de conversão
    monetária/taxa (`app/montagem/conversao.py`, mensagem e domínio fixados
    em "entrada monetária/taxa") — uma segunda exceção, tratada no MESMO
    bloco `except` de `responder_pergunta` (mesmo caminho de erro, `EC-01`),
    documenta a origem sem forçar um tipo genérico a cobrir dois domínios
    diferentes."""

    def __init__(self, valor_recusado: str, motivo: str) -> None:
        self.valor_recusado = valor_recusado
        self.motivo = motivo
        super().__init__(f"entrada recusada: {valor_recusado!r} — {motivo}")


def obter_colecao_de_registros() -> ColecaoDeRegistros:
    """Ponto único de injeção da coleção de registros — sobrescrito nos
    testes via `app.dependency_overrides` (mesmo padrão de `app/http/
    isolamento.py::obter_repositorio_casos`), para exercitar registros
    fabricados sem depender dos 245 registros reais em todo teste."""
    return carregar_registros()


def obter_repositorio_respostas() -> RepositorioRespostas:
    """Ponto único de injeção do repositório de respostas — sobrescrito nos
    testes via `app.dependency_overrides` para rodar sem `DATABASE_URL`,
    mesmo padrão de `app/http/isolamento.py::obter_repositorio_casos`."""
    return RepositorioRespostasSupabase()


def obter_repositorio_itens() -> RepositorioItens:
    """Ponto único de injeção do repositório de itens repetidos — usado só
    para montar `itens_por_escopo` da checagem de obrigatoriedade `REP`
    (`app/casos/progresso.py`, T-44). Sobrescrito nos testes via
    `app.dependency_overrides`, mesmo padrão das duas dependências acima."""
    return RepositorioItensSupabase()


async def _ler_formulario(request: Request) -> dict[str, str]:
    """Mesma decodificação de `app/http/rotas_conta.py::_ler_formulario` e
    `app/http/rotas_consentimento.py::_ler_formulario` — stdlib
    (`parse_qsl`), sem `python-multipart` (fora do plano).

    `dict(pares)` mantém só o ÚLTIMO valor de cada chave repetida — correto
    para `ID_PERGUNTA`/`item_id`/`nao_sei` (nunca repetidos), mas insuficiente
    para `valor` de `SELECAO_MULTIPLA` (checkbox `name="valor"` repetido,
    `CampoPergunta.tsx`). Por isso `responder_pergunta`
    lê `valor` separadamente, por `_ler_todos_os_valores` (T-101)."""
    from urllib.parse import parse_qsl

    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return dict(pares)


async def _ler_todos_os_valores(request: Request) -> tuple[str, ...]:
    """T-101 (`RF-11`, `AC-08`): todos os pares `valor=...` do corpo, na
    ordem em que chegaram — o que `<input type="checkbox" name="valor"
    value="X">` repetido (`SELECAO_MULTIPLA`) envia de fato num `<form>`
    HTML nativo. Para os oito outros `TipoResposta`, que enviam no máximo um
    par `valor`, o resultado tem no máximo um elemento e `_resolver_valor`
    lê só esse elemento — nenhuma mudança de comportamento para eles.

    Lê o corpo de novo (mesma decodificação de `_ler_formulario`): FastAPI
    armazena o corpo consumido em cache interno de `Request`, então uma
    segunda chamada a `request.body()` na mesma requisição não relê o
    socket, só devolve os bytes já lidos."""
    from urllib.parse import parse_qsl

    corpo = await request.body()
    pares = parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)
    return tuple(valor for chave, valor in pares if chave == "valor")


def _localizar_registro(
    colecao: ColecaoDeRegistros, id_pergunta: str
) -> RegistroPergunta:
    """Passo 2 (primeira metade): registro carregado por `ID` — `RF-05`.
    `ErroPerguntaDesconhecida` se nenhum registro corresponder, nunca uma
    pergunta "genérica" assumida."""
    for registro in colecao.registros:
        if registro.ID == id_pergunta:
            return registro
    raise ErroPerguntaDesconhecida(id_pergunta)


def _exigir_pergunta_aberta(registro: RegistroPergunta, respostas: RespostasCaso) -> None:
    """Passo 2 (segunda metade): a pergunta está de fato aberta — sua
    `condicao_exibicao` avalia como verdadeira sobre as respostas já dadas
    (`RF-05`). Registro sem `condicao_exibicao` (`None`) está sempre aberto.
    `ErroPerguntaNaoAberta` recusa, sem nenhuma gravação, quando a condição
    é falsa."""
    if registro.condicao_exibicao is None:
        return
    if not avaliar(registro.condicao_exibicao, respostas):
        raise ErroPerguntaNaoAberta(registro.ID)


_ESCALA_0_10_MINIMO: Final[int] = 0
_ESCALA_0_10_MAXIMO: Final[int] = 10


def _resolver_valor(
    registro: RegistroPergunta, dados: dict[str, str], valores_brutos: tuple[str, ...]
) -> ValorResposta:
    """Passos 3 e 4: `"não sei"` grava `NAO_SEI` e PULA a conversão decimal
    (`RF-11`); caso contrário, o valor é traduzido para o tipo Python que
    `ValorResposta` exige PARA O `TipoResposta` do registro (T-101, `RF-11`,
    `RF-13`, `AC-08`, `AC-13`) — nunca a string crua do formulário, que
    `app/montagem/estado.py` (`_mecanismo_deficit` e os campos `ESCALA_0_10`)
    não consegue consumir.

    `EC-01` é o caminho de erro único para os três tipos que exigem
    conversão estrita (`MOEDA`/`TAXA` via `ErroConversaoInvalida`;
    `NUMERO`/`ESCALA_0_10`/`DATA` via `ErroValorInvalido`): a exceção
    propaga sem alteração, o chamador recusa a requisição inteira sem
    gravar nada, nunca trunca nem coage.

    `valores_brutos` é TODO par `valor=...` do corpo (`_ler_todos_os_
    valores`) — usado só por `SELECAO_MULTIPLA`; os oito outros tipos
    continuam lendo o único campo `valor` de `dados` (mesma convenção de
    antes desta tarefa)."""
    if dados.get("nao_sei"):
        return NAO_SEI

    valor_bruto = dados.get("valor", "")

    if registro.tipo is TipoResposta.MOEDA:
        return converter_para_dinheiro(valor_bruto)
    if registro.tipo is TipoResposta.TAXA:
        return converter_para_taxa(valor_bruto)
    if registro.tipo is TipoResposta.SELECAO_MULTIPLA:
        return _resolver_selecao_multipla(valores_brutos)
    if registro.tipo is TipoResposta.NUMERO:
        return _resolver_numero(valor_bruto)
    if registro.tipo is TipoResposta.ESCALA_0_10:
        return _resolver_escala_0_10(valor_bruto)
    if registro.tipo is TipoResposta.DATA:
        return _resolver_data(valor_bruto)
    # SELECAO_UNICA, TEXTO_CURTO, SIM_NAO_TALVEZ: `str` direto — já corretos
    # antes desta tarefa, nenhuma mudança de comportamento (quarto critério
    # de aceite de T-101).
    return valor_bruto


def _resolver_selecao_multipla(valores_brutos: tuple[str, ...]) -> frozenset[str]:
    """`AC-08`/`AC-13`: `SELECAO_MULTIPLA` grava `frozenset[str]` a partir
    dos valores efetivamente marcados no formulário (checklist) — nunca uma
    string concatenada. Entradas vazias (`keep_blank_values=True` de
    `parse_qsl` preservaria um `valor=""` de campo sem nenhuma opção
    marcada) são descartadas: nenhuma opção marcada é `frozenset()`, um
    conjunto vazio de primeira classe, não um conjunto com a string vazia
    dentro."""
    return frozenset(valor for valor in valores_brutos if valor)


def _resolver_numero(valor_bruto: str) -> int:
    """`AC-08`: `NUMERO` grava `int`, recusando com `EC-01` uma entrada que
    não seja um inteiro — nunca truncando (`int("3.7")` levantaria
    `ValueError`, capturado abaixo) nem coagindo a `0`. Sinal opcional é
    aceito (`int()` da stdlib já trata `"-3"`); qualquer outro caractere
    recusa."""
    texto = valor_bruto.strip()
    if not texto:
        raise ErroValorInvalido(valor_bruto, "entrada vazia")
    try:
        return int(texto)
    except ValueError as erro:
        raise ErroValorInvalido(valor_bruto, "não é um número inteiro") from erro


def _resolver_escala_0_10(valor_bruto: str) -> int:
    """`AC-08`: `ESCALA_0_10` grava `int` no domínio fechado 0–10 — a
    própria escala normativa da pergunta (`B2.13`/`B5.H01`/`B9.02`, cada
    `RegistroPergunta.opcoes` documenta as extremidades "0 = ..."/"10 =
    ..."). Não há nó de `Condicao` para validação de faixa numérica
    declarativa (`collection/condicoes.py` só expressa igualdade/
    pertencimento/existência — ver o comentário de `bloco-05.yaml` sobre a
    mesma lacuna), então o range é validado aqui, pelo mesmo caminho `EC-01`
    de qualquer outra entrada inválida — nunca truncado para o extremo mais
    próximo."""
    valor = _resolver_numero(valor_bruto)
    if not (_ESCALA_0_10_MINIMO <= valor <= _ESCALA_0_10_MAXIMO):
        raise ErroValorInvalido(valor_bruto, "fora do domínio 0–10")
    return valor


def _resolver_data(valor_bruto: str) -> date:
    """`AC-08`: `DATA` grava `date`, recusando com `EC-01` entrada que não
    seja uma data válida no formato ISO 8601 (`YYYY-MM-DD`) — o mesmo
    formato que `<input type="date">` (`frontend/src/componentes/
    pergunta.html`) envia nativamente em `value`, sem conversão adicional no
    navegador."""
    texto = valor_bruto.strip()
    if not texto:
        raise ErroValorInvalido(valor_bruto, "entrada vazia")
    try:
        return date.fromisoformat(texto)
    except ValueError as erro:
        raise ErroValorInvalido(valor_bruto, "não é uma data válida") from erro


def _exigir_validacao_cruzada(
    registro: RegistroPergunta, item_id: str | None, respostas: RespostasCaso
) -> None:
    """Passo 5: `validacoes_cruzadas` do registro, avaliadas dentro do MESMO
    item (`RF-07`) — `EC-02` levanta `ErroValidacaoCruzadaFalhou` nomeando OS
    DOIS campos (`ResultadoValidacao.variavel_esquerda`/`variavel_direita`,
    T-13) e carregando a `mensagem` do registro, antes de qualquer gravação.
    Registro sem `validacoes_cruzadas` não tem nada a validar aqui."""
    if not registro.validacoes_cruzadas:
        return
    chave_do_item = item_id or ""
    for validacao in registro.validacoes_cruzadas:
        resultado = validar_cruzada(validacao, chave_do_item, respostas)
        if not resultado.valida:
            raise ErroValidacaoCruzadaFalhou(
                variavel_esquerda=resultado.variavel_esquerda or "",
                variavel_direita=resultado.variavel_direita or "",
                mensagem=resultado.mensagem or "",
            )


class ErroValidacaoCruzadaFalhou(Exception):
    """`EC-02` — a validação cruzada declarada pelo registro falhou; carrega
    OS DOIS nomes de campo (`variavel_esquerda`/`variavel_direita`, de
    `ResultadoValidacao`, T-13) e a `mensagem` do próprio registro (nunca uma
    redação composta por esta rota) — a rota usa os três para montar a
    resposta HTTP que aponta o(s) campo(s), como o critério de aceite exige."""

    def __init__(self, variavel_esquerda: str, variavel_direita: str, mensagem: str) -> None:
        self.variavel_esquerda = variavel_esquerda
        self.variavel_direita = variavel_direita
        self.mensagem = mensagem
        super().__init__(mensagem)


@roteador.post("/{CASO_ID}/resposta", response_class=HTMLResponse)
def responder_pergunta(
    request: Request,
    dados: Annotated[dict[str, str], Depends(_ler_formulario)],
    valores_brutos: Annotated[tuple[str, ...], Depends(_ler_todos_os_valores)],
    CASO_ID: Annotated[str, Depends(exigir_caso_da_sessao("CASO_ID"))],
    colecao: Annotated[ColecaoDeRegistros, Depends(obter_colecao_de_registros)],
    repositorio: Annotated[RepositorioRespostas, Depends(obter_repositorio_respostas)],
    repositorio_itens: Annotated[RepositorioItens, Depends(obter_repositorio_itens)],
) -> Response:
    """Os sete passos do plano §5.1, na ordem, para uma única resposta.

    Devolve `200` com a confirmação de gravação (mais o aviso de
    materialidade, quando houver) somente APÓS o passo 6 ter commitado a
    transação — nunca antes (`AC-02`). Qualquer recusa (passos 2, 4 ou 5)
    devolve `400` sem gravar nada; falha do passo 6 devolve `503`
    (`EC-05`).

    **`def`, não `async def` — `T-187`.** É a rota mais chamada do sistema
    — uma vez por resposta, das 291 perguntas do questionário, por aluno.
    `repositorio.gravar` (passo 6) é bloqueante; ver a nota em
    `rotas_api_conta.py::cadastrar`. `dados`/`valores_brutos` chegam por
    `Depends`, resolvidos antes do handler — a mesma leitura de corpo que
    antes acontecia aqui dentro, agora feita pelo FastAPI."""
    # Passo 1 já ocorreu: `exigir_caso_da_sessao` (Depends acima) verificou,
    # no servidor, que a sessão possui este CASO_ID — 401/404 antes de
    # qualquer leitura de dado do caso, se aplicável.
    id_pergunta = dados.get("ID_PERGUNTA", "")
    item_id = dados.get("item_id") or None

    try:
        registro = _localizar_registro(colecao, id_pergunta)
    except ErroPerguntaDesconhecida:
        return _resposta_de_erro(request, _MENSAGEM_PERGUNTA_NAO_ENCONTRADA, 400)
    if registro.VARIAVEL_GRAVADA is None:
        raise ErroRegistroSemVariavelGravada(registro.ID)

    respostas_do_caso = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))

    # Passo 2 (segunda metade): a pergunta precisa estar de fato aberta.
    try:
        _exigir_pergunta_aberta(registro, respostas_do_caso)
    except ErroPerguntaNaoAberta:
        return _resposta_de_erro(request, _MENSAGEM_PERGUNTA_NAO_ABERTA, 400)

    # Passos 3 e 4: NAO_SEI pula a conversão; cada TipoResposta é traduzido
    # para o tipo Python que ValorResposta exige para ele (T-101). EC-01:
    # recusa sem gravar, nunca trunca nem coage.
    try:
        valor = _resolver_valor(registro, dados, valores_brutos)
    except (ErroConversaoInvalida, ErroValorInvalido) as erro:
        mensagem = f"{registro.VARIAVEL_GRAVADA}: {erro.motivo}"
        return _resposta_de_erro(request, mensagem, 400)

    # Passo 5: validação cruzada, só quando o registro a declara. EC-02:
    # recusa apontando os dois campos, nenhum é gravado.
    respostas_com_valor_corrente = _respostas_com_valor_provisorio(
        respostas_do_caso, registro, item_id, valor
    )
    try:
        _exigir_validacao_cruzada(registro, item_id, respostas_com_valor_corrente)
    except ErroValidacaoCruzadaFalhou as erro:
        mensagem = f"{erro.variavel_esquerda}/{erro.variavel_direita}: {erro.mensagem}"
        return _resposta_de_erro(request, mensagem, 400)

    # Passo 6: gravação com transação confirmada. EC-05: falha nunca reporta
    # sucesso — devolve erro explícito e NÃO avança.
    #
    # `ID_PERGUNTA` gravado é `VARIAVEL_GRAVADA` (não `registro.ID`): é essa
    # a chave que `RespostasCaso`/`avaliar`/`validar_cruzada` consultam por
    # nome de variável (ver `ErroRegistroSemVariavelGravada` acima) — a
    # mesma convenção já usada pelos testes de `collection/respostas.py`
    # (T-22) e pelo teste de integração do gerador (T-20, `AC-06`).
    resposta = Resposta(
        CASO_ID=CASO_ID,
        ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
        respondida_em=_agora(),
    )
    try:
        repositorio.gravar(resposta)
    except ErroConsentimentoNaoRegistrado:
        return _resposta_de_erro(request, _MENSAGEM_PERGUNTA_NAO_ABERTA, 400)
    except (ErroGravacaoResposta, ErroCasoInexistenteParaResposta):
        # EC-05: a transação nunca foi commitada — nada foi salvo. Devolve
        # a mensagem exigida pelo critério de aceite, sem avançar.
        return _resposta_de_erro(request, _MENSAGEM_FALHA_SALVAR, 503)

    # Neste ponto a resposta JÁ ESTÁ commitada no banco
    # (`RepositorioRespostasSupabase.gravar` só retorna sem exceção após
    # `conexao.commit()` de `_conectar`) — encerrar o processo agora não
    # perde a resposta (`AC-02`). Só então o passo 7 roda e a resposta HTTP
    # é montada.
    # `registro.VARIAVEL_GRAVADA` já foi confirmado não-nulo logo após
    # `_localizar_registro`, acima.
    aviso: AvisoMaterialidade | None = avaliar_ao_responder(registro.VARIAVEL_GRAVADA, valor)

    # T-44 (RF-09, RF-11, AC-11): sinalizador de avanço da coleta como um
    # todo, calculado sobre TODOS os registros e o snapshot de respostas do
    # caso já incluindo a resposta recém-gravada — `app/casos/progresso.py`
    # é quem decide, por `Obrigatoriedade` do próprio registro, nunca por
    # `ID` codificado aqui.
    respostas_apos_gravar = RespostasCaso(respostas=repositorio.listar_do_caso(CASO_ID))
    itens_por_escopo = _itens_por_escopo(repositorio_itens, CASO_ID)
    pendencias = pendencias_obrigatorias(
        colecao.registros, respostas_apos_gravar, itens_por_escopo
    )

    # T-144: a resposta é sempre JSON — a tela é React. Os sete passos
    # acima correram idênticos ao que sempre correram; só a montagem da
    # resposta mudou de formato.
    return JSONResponse(
        {
            "ID_PERGUNTA": registro.ID,
            "aviso": aviso.texto if aviso is not None else None,
            "avanco_permitido": not pendencias,
            "total_pendencias": len(pendencias),
        }
    )


def _agora() -> datetime:
    return datetime.now(UTC)


def _itens_por_escopo(
    repositorio_itens: RepositorioItens, CASO_ID: str
) -> dict[EscopoRepeticao, tuple[str, ...]]:
    """T-44: agrupa os itens ATIVOS (`removido_em is None`) do caso por
    `EscopoRepeticao`, no formato que `app/casos/progresso.py::
    pendencias_obrigatorias` consome — um item removido nunca é varrido por
    obrigatoriedade `REP` (não há mais ficha a completar)."""
    itens_ativos = repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
    agrupado: dict[EscopoRepeticao, list[str]] = {}
    for item in itens_ativos:
        agrupado.setdefault(item.escopo, []).append(item.item_id)
    return {escopo: tuple(item_ids) for escopo, item_ids in agrupado.items()}


def _respostas_com_valor_provisorio(
    respostas: RespostasCaso,
    registro: RegistroPergunta,
    item_id: str | None,
    valor: ValorResposta,
) -> RespostasCaso:
    """A validação cruzada (passo 5) precisa enxergar o valor que ACABOU de
    ser resolvido (ainda não gravado) junto dos já persistidos — sem isso,
    validar `VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM` na resposta que
    fecha o par sempre compararia contra a ausência do próprio campo que
    está sendo respondido agora. Constrói uma `RespostasCaso` nova (imutável,
    `frozen=True`) que é o snapshot persistido MAIS a resposta provisória —
    nunca grava esta resposta provisória, só a usa para a comparação."""
    if registro.VARIAVEL_GRAVADA is None:
        return respostas
    provisoria = Resposta(
        CASO_ID="",
        ID_PERGUNTA=registro.VARIAVEL_GRAVADA,
        item_id=item_id,
        valor=valor,
        QUESTIONARIO_VERSION="",
        respondida_em=_agora(),
    )
    return RespostasCaso(respostas=(*respostas.respostas, provisoria))


def _resposta_de_erro(request: Request, mensagem: str, status_code: int) -> JSONResponse:
    """A recusa NOMEIA o motivo, sempre (`EC-01`). O cliente mostra esta
    mensagem ao aluno; um erro genérico deixaria a pessoa sem saber o que
    corrigir, e foi por isso que a versão HTMX precisou do `htmx:beforeSwap`
    (T-130) — em JSON o corpo do 4xx chega ao cliente sem essa armadilha."""
    return JSONResponse({"erro": mensagem}, status_code=status_code)
