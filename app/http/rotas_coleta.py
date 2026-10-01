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

import logging
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.casos.inventario import pendencias_de_inventario
from app.casos.itens_despesa import (
    CHECKLISTS_DE_DESPESA,
    DESPESA_NAO_LISTADA,
    pede_nome,
    rotulos_dos_itens,
    sincronizar,
)
from app.casos.maquina import ErroConsentimentoNaoRegistrado
from app.casos.progresso import (
    PendenciaObrigatoria,
    _variaveis_da_condicao,
    em_branco_no_item,
    escopos_abertos_pela_resposta,
    pendencias_obrigatorias,
    posicao_na_ficha,
    proxima_pergunta_do_item,
    proxima_pergunta_nao_respondida,
)
from app.concorrencia import duas_em_paralelo
from app.http.isolamento import exigir_caso_da_sessao
from app.http.jornada import anexar_ao_payload
from app.http.renderizacao import ErroPerguntaNaoExibivel, montar_contexto_pergunta
from app.http.rotas_calculo import _respostas_do_calculo
from app.http.serializacao import serializar_painel, serializar_pergunta, serializar_valor
from app.montagem.conversao import (
    ErroConversaoInvalida,
    converter_para_dinheiro,
    converter_para_taxa,
)
from app.montagem.entrada import avisos_da_gravacao, fotografia_do_mes
from collection.carga import ColecaoDeRegistros, carregar_registros
from collection.condicoes import avaliar
from collection.materialidade import AvisoMaterialidade, avaliar_ao_responder
from collection.registro import EscopoRepeticao, Obrigatoriedade, RegistroPergunta, TipoResposta
from collection.respostas import NAO_SEI, Resposta, RespostasCaso, ValorResposta
from collection.validacao import validar_cruzada
from persistencia.app_aluno.arquivo import ErroGravacaoItem as ErroGravacaoItemArquivo
from persistencia.app_aluno.itens import (
    ErroGravacaoItem,
    ItemRepetido,
    RepositorioItens,
    RepositorioItensSupabase,
)
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
_MENSAGEM_FORA_DA_FAIXA: Final[str] = "Valor fora do intervalo aceito."
_MENSAGEM_FICHA_INCOMPLETA: Final[str] = "Antes de salvar, responda nesta ficha:"

_LOGGER: Final[logging.Logger] = logging.getLogger("app.http.rotas_coleta")


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


def _exigir_pergunta_aberta(
    registro: RegistroPergunta, respostas: RespostasCaso, item_id: str | None = None
) -> None:
    """Passo 2 (segunda metade): a pergunta está de fato aberta — sua
    `condicao_exibicao` avalia como verdadeira sobre as respostas já dadas
    (`RF-05`). Registro sem `condicao_exibicao` (`None`) está sempre aberto.
    `ErroPerguntaNaoAberta` recusa, sem nenhuma gravação, quando a condição
    é falsa. Pergunta de ficha avalia no próprio item (`T-199`), com o
    mesmo `item_id` que a retomada usou para oferecê-la."""
    if registro.condicao_exibicao is None:
        return
    if not avaliar(registro.condicao_exibicao, respostas, item_id):
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

    # `T-299`: nos tipos de valor, uma opção alternativa do registro (ex.:
    # `B3.01` `RENDA_VARIAVEL`) grava o próprio código — a montagem já o lê
    # como desconhecido (`T-296`). Código numérico (`"0"`) segue convertido.
    if registro.tipo in _TIPOS_DE_VALOR and valor_bruto in _codigos_alternativos(registro):
        return valor_bruto
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
    if registro.tipo is TipoResposta.SELECAO_UNICA:
        # `T-294`: com campo de outra variável o corpo traz dois `valor` — o
        # código da opção vem primeiro (`_resolver_campo` lê o segundo).
        return _resolver_selecao_unica(registro, valores_brutos[0] if valores_brutos else "")
    # TEXTO_CURTO, SIM_NAO_TALVEZ: `str` direto — já corretos
    # antes desta tarefa, nenhuma mudança de comportamento (quarto critério
    # de aceite de T-101).
    return valor_bruto


_TIPOS_DE_VALOR: Final[frozenset[TipoResposta]] = frozenset(
    {TipoResposta.MOEDA, TipoResposta.TAXA, TipoResposta.NUMERO, TipoResposta.DATA}
)


def _codigos_alternativos(registro: RegistroPergunta) -> frozenset[str]:
    """`T-299` — os `valor_interno` não numéricos das opções além do campo.
    A opção "não sei" fica de fora: ela é o `nao_sei` (`NAO_SEI`)."""
    return frozenset(
        opcao.valor_interno
        for opcao in registro.opcoes
        if opcao.valor_interno is not None
        and not opcao.admite_nao_sei
        and not opcao.valor_interno.isdigit()
    )


def _resolver_campo(
    registro: RegistroPergunta, valor: ValorResposta, valores_brutos: tuple[str, ...]
) -> tuple[str, ValorResposta] | None:
    """`T-294` — a opção escolhida declara `variavel_do_campo` (ex.: `B5.B01`
    "Sim." → `VALOR_ORIGINAL`): o segundo `valor` do corpo é o R$ digitado,
    convertido pela mesma fronteira de `MOEDA` (`RF-13`). Vazio ou inválido
    recusa a resposta inteira (`EC-01`) — nada é gravado."""
    opcao = next(
        (o for o in registro.opcoes if o.variavel_do_campo and o.valor_interno == valor),
        None,
    )
    if opcao is None or opcao.variavel_do_campo is None:
        return None
    digitado = valores_brutos[1] if len(valores_brutos) > 1 else ""
    return opcao.variavel_do_campo, converter_para_dinheiro(digitado)


def _dentro_da_faixa(
    registro: RegistroPergunta, dados: dict[str, str], valor: ValorResposta
) -> bool:
    """`T-238` — a `faixa` vale na unidade que o aluno digitou: para `TAXA`,
    o percentual (`"120"` é 120%, antes da fração de `converter_para_taxa`),
    renormalizado pela MESMA fronteira (`RF-13`); para `MOEDA`/`NUMERO`, o
    próprio valor. "Não sei" e tipos sem número não têm faixa."""
    assert registro.faixa is not None
    if valor is NAO_SEI or isinstance(valor, str):
        return True
    numero: object = valor
    if registro.tipo is TipoResposta.TAXA:
        numero = converter_para_dinheiro(dados.get("valor", ""))
    if not isinstance(numero, Decimal | int) or isinstance(numero, bool):
        return True
    minimo, maximo = registro.faixa
    return minimo <= numero <= maximo


def _resolver_selecao_unica(registro: RegistroPergunta, valor_bruto: str) -> ValorResposta:
    """`T-213`: com uma opção que abre campo de data (`abre_campo: DATA`),
    o que não é `valor_interno` de outra opção é a data digitada — convertida
    por `_resolver_data` e gravada na `VARIAVEL_GRAVADA` da pergunta. O rádio
    sozinho (vazio ou o próprio `valor_interno` da opção) recusa (`EC-01`).
    Sem essa opção, `str` direto, como sempre (o campo `MOEDA` de `T-294`
    grava em outra variável: `_resolver_campo`)."""
    if not any(opcao.abre_campo is TipoResposta.DATA for opcao in registro.opcoes):
        return valor_bruto
    comuns = {
        opcao.valor_interno
        for opcao in registro.opcoes
        if opcao.abre_campo is not TipoResposta.DATA
    }
    if valor_bruto in comuns:
        return valor_bruto
    return _resolver_data(valor_bruto)


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
    redação composta por esta rota) — a resposta HTTP leva só a `mensagem`,
    que já aponta os dois campos em linguagem do aluno; os nomes vão para o
    log (`T-209`)."""

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
        _exigir_pergunta_aberta(registro, respostas_do_caso, item_id)
    except ErroPerguntaNaoAberta:
        return _resposta_de_erro(request, _MENSAGEM_PERGUNTA_NAO_ABERTA, 400)

    # Passos 3 e 4: NAO_SEI pula a conversão; cada TipoResposta é traduzido
    # para o tipo Python que ValorResposta exige para ele (T-101). EC-01:
    # recusa sem gravar, nunca trunca nem coage.
    try:
        valor = _resolver_valor(registro, dados, valores_brutos)
        campo = _resolver_campo(registro, valor, valores_brutos)
    except (ErroConversaoInvalida, ErroValorInvalido) as erro:
        # `T-205`: o aluno lê só o motivo; a variável vai para o log.
        _LOGGER.info(
            "resposta recusada: %s — %s", registro.VARIAVEL_GRAVADA, erro.motivo
        )
        return _resposta_de_erro(request, f"Resposta não aceita: {erro.motivo}.", 400)

    # `T-238` (RF-84, AC-128): valor fora da `faixa` fechada do registro é
    # recusado como `EC-01` — nada gravado, mensagem do próprio registro.
    if registro.faixa is not None and not _dentro_da_faixa(registro, dados, valor):
        return _resposta_de_erro(
            request, registro.mensagem_faixa or _MENSAGEM_FORA_DA_FAIXA, 400
        )

    # Passo 5: validação cruzada, só quando o registro a declara. EC-02:
    # recusa apontando os dois campos, nenhum é gravado.
    respostas_com_valor_corrente = _respostas_com_valor_provisorio(
        respostas_do_caso, registro, item_id, valor
    )
    try:
        _exigir_validacao_cruzada(registro, item_id, respostas_com_valor_corrente)
    except ErroValidacaoCruzadaFalhou as erro:
        # `T-209`: o aluno lê só a `mensagem` do registro; as variáveis vão
        # para o log.
        _LOGGER.info(
            "validação cruzada recusada: %s/%s — %s",
            erro.variavel_esquerda,
            erro.variavel_direita,
            erro.mensagem,
        )
        return _resposta_de_erro(request, erro.mensagem, 400)

    # `T-292`: "salvar" a ficha com pergunta obrigatória (`REP`) aberta e em
    # branco naquele item é recusado, listando o que falta — nada é gravado.
    if item_id is not None and valor == _SALVAR_FICHA.get(registro.VARIAVEL_GRAVADA):
        faltam = _em_branco_antes_de(
            colecao, registro, respostas_do_caso, repositorio_itens, CASO_ID, item_id
        )
        if faltam:
            return _resposta_de_erro(
                request,
                f"{_MENSAGEM_FICHA_INCOMPLETA} {'; '.join(r.enunciado for r in faltam)}",
                400,
            )

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
        # `T-294`: o valor do campo vai para a variável própria, no mesmo
        # item — a resposta da pergunta continua sendo o código da opção.
        if campo is not None:
            repositorio.gravar(
                Resposta(
                    CASO_ID=CASO_ID,
                    ID_PERGUNTA=campo[0],
                    item_id=item_id,
                    valor=campo[1],
                    QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
                    respondida_em=_agora(),
                )
            )
    except ErroConsentimentoNaoRegistrado:
        return _resposta_de_erro(request, _MENSAGEM_PERGUNTA_NAO_ABERTA, 400)
    except (ErroGravacaoResposta, ErroCasoInexistenteParaResposta):
        # EC-05: a transação nunca foi commitada — nada foi salvo. Devolve
        # a mensagem exigida pelo critério de aceite, sem avançar.
        return _resposta_de_erro(request, _MENSAGEM_FALHA_SALVAR, 503)

    # `T-217`: o checklist de despesa cria e remove as fichas dos itens. A
    # resposta já está gravada; se isto falhar, o aluno reenvia e a
    # sincronização, idempotente, completa o que faltou.
    try:
        sem_nome = _sincronizar_itens_de_despesa(
            registro, valor, repositorio_itens, CASO_ID
        )
    except (ErroGravacaoItem, ErroGravacaoItemArquivo):
        return _resposta_de_erro(request, _MENSAGEM_FALHA_SALVAR, 503)

    # `T-274` (RF-81, AC-123, DE-03): restituição de seguro confirmada vira
    # ficha de recurso extraordinário. Mesma disciplina do `T-217`: a
    # resposta já está gravada; reenviar completa o que faltou.
    try:
        _sincronizar_restituicao_de_seguro(
            registro, item_id, valor, repositorio, repositorio_itens, CASO_ID, colecao
        )
    except (
        ErroGravacaoItem,
        ErroGravacaoItemArquivo,
        ErroGravacaoResposta,
        ErroCasoInexistenteParaResposta,
    ):
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
    # Duas consultas independentes em paralelo (`T-191`). `itens_por_escopo`
    # lê `app_aluno.itens`, nunca tocada pelo `gravar` acima (que só grava em
    # `app_aluno.respostas`/atualiza `casos.ultima_interacao_em`, T-91) —
    # rodar ao lado da releitura pós-gravação de `respostas` não arrisca
    # nada.
    respostas_brutas, (itens_por_escopo, rotulos) = duas_em_paralelo(
        lambda: repositorio.listar_do_caso(CASO_ID),
        lambda: _itens_e_rotulos(repositorio_itens, CASO_ID, colecao),
    )
    respostas_apos_gravar = RespostasCaso(respostas=respostas_brutas)
    pendencias = pendencias_obrigatorias(
        colecao.registros, respostas_apos_gravar, itens_por_escopo
    )

    # `T-193`: a PRÓXIMA pergunta já sai nesta mesma resposta — mesmos dados
    # de `respostas_apos_gravar`/`itens_por_escopo` que acabaram de ser
    # buscados acima, nenhuma consulta nova ao banco. Sem isto, o cliente
    # respondia e em seguida fazia um `GET /pergunta` só pra saber a
    # próxima — uma viagem de rede inteira (com seu próprio check de sessão)
    # por algo que o servidor já sabia neste exato momento. É a rota mais
    # chamada do sistema (uma vez por resposta, até ~291 vezes por aluno);
    # eliminar essa segunda viagem é o ganho, não uma segunda decisão de
    # QUAL pergunta vem a seguir — quem decide continua sendo só o servidor
    # (`RF-45`), com a MESMA função (`_primeira_exibivel`) que `GET
    # /pergunta` usa.
    proxima = _serializar_proxima(
        CASO_ID, colecao, respostas_apos_gravar, itens_por_escopo, rotulos
    )

    # `T-212`: a resposta que abre uma ficha ainda vazia (ex.: "Sim" em
    # `B3.03`) aponta a lista daquele escopo — sem item, o gerador não
    # produz as perguntas dela e a coleta seguiria como se nada houvesse.
    abrir_fichas = escopos_abertos_pela_resposta(
        colecao.registros, registro.VARIAVEL_GRAVADA, respostas_apos_gravar, itens_por_escopo
    )
    # `T-217`: "Outro" do checklist pede nome — na lista. `T-316` (RF-104):
    # a despesa não listada vai direto ao item novo, que o formulário da
    # ficha curta abre com o nome e `B3.DF01`–`DF04`.
    if sem_nome and registro.ID == DESPESA_NAO_LISTADA:
        proxima = (
            _proxima_do_item(
                CASO_ID, colecao, respostas_apos_gravar, repositorio_itens, sem_nome[0]
            )
            or proxima
        )
    elif sem_nome:
        abrir_fichas = (*abrir_fichas, EscopoRepeticao.ITEM_DESPESA)
    # `T-291` (RF-87, DE-04): a cabeça de `DIVIDA_ID` não tem condição, então
    # `escopos_abertos_pela_resposta` nunca a aponta. Com `B5.00` e `B5.00A`
    # respondidas e a pendência de dívidas pedindo fichas, a lista abre.
    if _abre_fichas_de_divida(
        colecao, registro.VARIAVEL_GRAVADA, respostas_apos_gravar, itens_por_escopo
    ):
        abrir_fichas = (*abrir_fichas, EscopoRepeticao.DIVIDA_ID)

    # `T-311` (RF-101): a ficha aberta ainda vazia nasce com o primeiro item,
    # e a coleta segue direto para a primeira pergunta dele; terminado um
    # item, a lista do escopo reabre ("Adicionar outro" / "Continuar").
    try:
        abrir_fichas, proxima = _primeiro_item_ou_lista(
            CASO_ID,
            colecao,
            registro,
            item_id,
            abrir_fichas,
            proxima,
            respostas_apos_gravar,
            itens_por_escopo,
            repositorio_itens,
        )
    except (ErroGravacaoItem, ErroGravacaoItemArquivo):
        return _resposta_de_erro(request, _MENSAGEM_FALHA_SALVAR, 503)

    # T-144: a resposta é sempre JSON — a tela é React. Os sete passos
    # acima correram idênticos ao que sempre correram; só a montagem da
    # resposta mudou de formato.
    return JSONResponse(
        {
            "ID_PERGUNTA": registro.ID,
            "aviso": aviso.texto if aviso is not None else None,
            "avanco_permitido": not pendencias,
            "total_pendencias": len(pendencias),
            "proxima": proxima,
            "abrir_fichas": [escopo.value for escopo in abrir_fichas],
            # `T-240` (RF-84, AC-129): aviso não é recusa — a resposta já
            # está gravada; `[]` quando não há nada a sinalizar.
            "avisos": [
                {"codigo": a.codigo, "mensagem": a.mensagem, "ID_PERGUNTA": registro.ID}
                for a in avisos_da_gravacao(
                    registro.VARIAVEL_GRAVADA, item_id, respostas_apos_gravar
                )
            ],
        }
    )


def _agora() -> datetime:
    return datetime.now(UTC)


# `T-311` — as fichas que nascem com o primeiro item ao serem declaradas
# (decisão do produto, 2026-10-01). `ITEM_DESPESA` fica de fora: as do
# checklist já nascem dele (`T-217`), e a não listada pede nome na lista;
# `MARGEM_ID` nasce dentro do vínculo.
_FICHAS_QUE_NASCEM_COM_ITEM: Final[frozenset[EscopoRepeticao]] = frozenset(
    {
        EscopoRepeticao.DIVIDA_ID,
        EscopoRepeticao.RENDA_ADICIONAL_ID,
        EscopoRepeticao.VINCULO_ID,
        EscopoRepeticao.DESPESA_NAO_MENSAL_ID,
        EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID,
    }
)


def _primeiro_item_ou_lista(
    CASO_ID: str,
    colecao: ColecaoDeRegistros,
    registro: RegistroPergunta,
    item_id: str | None,
    abrir_fichas: tuple[EscopoRepeticao, ...],
    proxima: dict[str, object],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    repositorio_itens: RepositorioItens,
) -> tuple[tuple[EscopoRepeticao, ...], dict[str, object]]:
    """`T-311` (RF-101) — o destino depois de gravar, nas fichas.

    (a) Escopo aberto pela resposta e ainda sem item: cria o primeiro e a
    `proxima` passa a ser a primeira pergunta dele — sem a lista no meio.
    (b) Resposta que fecha um item (nenhuma pergunta aberta em branco nele):
    a lista do escopo entra em `abrir_fichas`, para o aluno adicionar outro
    ou continuar. Quem decide as duas coisas é o servidor (`RF-45`)."""
    criar = [e for e in abrir_fichas if e in _FICHAS_QUE_NASCEM_COM_ITEM]
    if criar:
        novos = [repositorio_itens.proximo_identificador(CASO_ID, e) for e in criar]
        restantes = tuple(e for e in abrir_fichas if e not in criar)
        no_item = _proxima_do_item(CASO_ID, colecao, respostas, repositorio_itens, novos[0])
        return restantes, no_item or proxima

    if (
        item_id is not None
        and registro.escopo_repeticao in _FICHAS_QUE_NASCEM_COM_ITEM
        and registro.escopo_repeticao not in abrir_fichas
    ):
        if not em_branco_no_item(colecao.registros, respostas, itens_por_escopo, item_id):
            return (*abrir_fichas, registro.escopo_repeticao), proxima
    return abrir_fichas, proxima


def _proxima_do_item(
    CASO_ID: str,
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    repositorio_itens: RepositorioItens,
    item_id: str,
) -> dict[str, object] | None:
    """`T-311`/`T-316` — a `proxima` apontando a primeira pergunta do item
    recém-criado; `None` se ele não tem pergunta aberta (defensivo)."""
    itens_por_escopo, rotulos = _itens_e_rotulos(repositorio_itens, CASO_ID, colecao)
    primeira = proxima_pergunta_do_item(colecao.registros, respostas, itens_por_escopo, item_id)
    if primeira is None:  # pragma: no cover — defensivo: ficha sem pergunta aberta
        return None
    pergunta = serializar_pergunta_do_caso(
        CASO_ID,
        _localizar_registro(colecao, primeira.ID),
        respostas,
        colecao,
        itens_por_escopo,
        item_id,
        rotulos,
    )
    anexar_ao_payload(pergunta, colecao.registros, respostas, itens_por_escopo)
    return {"pergunta": pergunta, "coleta_completa": False}


# `T-292` — a variável da confirmação da ficha (`B5.CHECK`) e o valor que a
# salva. Chaves técnicas (`VARIAVEL_GRAVADA`/`valor_interno`).
_SALVAR_FICHA: Final[Mapping[str, str]] = {"SYS (salvar/editar)": "SIM_SALVAR_DIVIDA"}


def _em_branco_antes_de(
    colecao: ColecaoDeRegistros,
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    repositorio_itens: RepositorioItens,
    CASO_ID: str,
    item_id: str,
) -> tuple[RegistroPergunta, ...]:
    """`T-292` — as perguntas `REP` abertas e em branco do item que vêm
    ANTES de `registro` no percurso. As de depois (`B5.FIM01`) não contam:
    são respondidas depois de salvar."""
    posicao = {r.ID: indice for indice, r in enumerate(colecao.registros)}
    por_id = {r.ID: r for r in colecao.registros}
    return tuple(
        por_id[p.ID]
        for p in em_branco_no_item(
            colecao.registros, respostas, _itens_por_escopo(repositorio_itens, CASO_ID), item_id
        )
        if posicao[p.ID] < posicao[registro.ID]
        and Obrigatoriedade.REP in por_id[p.ID].obrigatoriedade
    )


# `T-291` — as variáveis de `B5.00` e `B5.00A`: a declaração das dívidas.
_DECLARACAO_DE_DIVIDAS: Final[tuple[str, ...]] = (
    "QUANTIDADE_DIVIDAS_DECLARADA_INICIAL",
    "TIPOS_DIVIDA_DECLARADOS",
)


def _abre_fichas_de_divida(
    colecao: ColecaoDeRegistros,
    variavel: str,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> bool:
    """A resposta fecha a declaração (as duas variáveis respondidas), não há
    ficha de dívida e `pendencias_de_inventario` pede fichas de `DIVIDA_ID`
    — quantidade numérica acima de zero ou "não sei" (`AC-153`). Quem decide
    se faltam fichas é a pendência de `RF-87`, não uma regra nova aqui."""
    return (
        variavel in _DECLARACAO_DE_DIVIDAS
        and not itens_por_escopo.get(EscopoRepeticao.DIVIDA_ID)
        and faltam_fichas_de_divida(colecao, respostas, itens_por_escopo)
    )


def faltam_fichas_de_divida(
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> bool:
    """A declaração está respondida e `pendencias_de_inventario` pede fichas
    de `DIVIDA_ID` — o sinal de `T-291`, lido também pelo Início (`T-301`)."""
    return all(respostas.valor(v) is not None for v in _DECLARACAO_DE_DIVIDAS) and any(
        p.escopo is EscopoRepeticao.DIVIDA_ID
        for p in pendencias_de_inventario(colecao.registros, respostas, itens_por_escopo)
    )


def posterior_a_declaracao_de_dividas(colecao: ColecaoDeRegistros, ID_PERGUNTA: str) -> bool:
    """`T-301`: a pergunta vem depois de `B5.00`/`B5.00A` na ordem da coleta."""
    ids = [r.ID for r in colecao.registros]
    declaracao = [
        i for i, r in enumerate(colecao.registros) if r.VARIAVEL_GRAVADA in _DECLARACAO_DE_DIVIDAS
    ]
    return bool(declaracao) and ID_PERGUNTA in ids and ids.index(ID_PERGUNTA) > max(declaracao)


def _itens_por_escopo(
    repositorio_itens: RepositorioItens, CASO_ID: str
) -> dict[EscopoRepeticao, tuple[str, ...]]:
    """T-44: agrupa os itens ATIVOS (`removido_em is None`) do caso por
    `EscopoRepeticao`, no formato que `app/casos/progresso.py::
    pendencias_obrigatorias` consome — um item removido nunca é varrido por
    obrigatoriedade `REP` (não há mais ficha a completar)."""
    return _agrupar(repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False))


def _agrupar(itens_ativos: tuple[ItemRepetido, ...]) -> dict[EscopoRepeticao, tuple[str, ...]]:
    agrupado: dict[EscopoRepeticao, list[str]] = {}
    for item in itens_ativos:
        agrupado.setdefault(item.escopo, []).append(item.item_id)
    return {escopo: tuple(item_ids) for escopo, item_ids in agrupado.items()}


def _itens_e_rotulos(
    repositorio_itens: RepositorioItens, CASO_ID: str, colecao: ColecaoDeRegistros
) -> tuple[dict[EscopoRepeticao, tuple[str, ...]], dict[str, str]]:
    """`T-217` — `_itens_por_escopo` e, da mesma leitura, o nome de cada
    item para o aluno ("Aluguel"), que `[despesa]` em `B3.DF01` mostra."""
    itens_ativos = repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
    return _agrupar(itens_ativos), rotulos_dos_itens(itens_ativos, colecao.registros)


def _sincronizar_itens_de_despesa(
    registro: RegistroPergunta,
    valor: ValorResposta,
    repositorio_itens: RepositorioItens,
    CASO_ID: str,
) -> tuple[str, ...]:
    """`T-217` — aplica `app/casos/itens_despesa.py::sincronizar`: remove a
    ficha de cada item desmarcado (remoção lógica, `AC-04`) e cria a de cada
    item marcado. Devolve os `item_id` das fichas criadas que pedem nome."""
    if registro.ID not in CHECKLISTS_DE_DESPESA and registro.ID != DESPESA_NAO_LISTADA:
        return ()
    ativos = repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
    sincronizacao = sincronizar(registro, valor, ativos)
    for item_id in sincronizacao.remover:
        repositorio_itens.remover(CASO_ID, item_id)
    criados = {
        origem: repositorio_itens.proximo_identificador(
            CASO_ID, EscopoRepeticao.ITEM_DESPESA, origem
        )
        for origem in sincronizacao.criar
    }
    return tuple(item_id for origem, item_id in criados.items() if pede_nome(origem))


# `T-274` — a variável de `B5.D05R` e o que ela escreve no item `EXT`. Chaves
# técnicas (`VARIAVEL_GRAVADA`/`valor_interno`), não conteúdo ao aluno.
_VARIAVEL_RESTITUICAO_SEGURO: Final[str] = "RESTITUICAO_SEGURO_CONFIRMADA"
_CERTEZA_CONFIRMADO: Final[str] = "CONFIRMADO"
# `T-286` (`DE-03`): marca o item com a pergunta de origem (`registro.ID`) —
# a condição de `B3.05A`–`D` no YAML abre a ficha dele mesmo com `B3.05 = Não`.
_VARIAVEL_ORIGEM_RECURSO: Final[str] = "ORIGEM_RECURSO_EXTRAORDINARIO"


def _sincronizar_restituicao_de_seguro(
    registro: RegistroPergunta,
    item_id: str | None,
    valor: ValorResposta,
    repositorio: RepositorioRespostas,
    repositorio_itens: RepositorioItens,
    CASO_ID: str,
    colecao: ColecaoDeRegistros,
) -> None:
    """`T-274` (RF-81, AC-123, DE-03) — valor confirmado em `B5.D05R` cria
    UM item `EXT` por dívida, `origem = "B5.D05R:<DIVIDA_ID>"`, com valor e
    certeza `CONFIRMADO`; reconfirmar atualiza o mesmo item. A janela (e o
    tipo) ficam para o aluno — nunca presumidos (`R9-10`). "Ainda não
    confirmada" → nenhum item: o que havia sai (remoção lógica, `AC-04`)."""
    if registro.VARIAVEL_GRAVADA != _VARIAVEL_RESTITUICAO_SEGURO or not item_id:
        return
    origem = f"{registro.ID}:{item_id}"
    existente = next(
        (
            item.item_id
            for item in repositorio_itens.listar_do_caso(CASO_ID, incluir_removidos=False)
            if item.escopo is EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID and item.origem == origem
        ),
        None,
    )
    if not isinstance(valor, Decimal):
        if existente is not None:
            repositorio_itens.remover(CASO_ID, existente)
        return
    recurso = existente or repositorio_itens.proximo_identificador(
        CASO_ID, EscopoRepeticao.RECURSO_EXTRAORDINARIO_ID, origem
    )
    for variavel, valor_do_item in (
        ("VALOR_RECURSO_EXTRAORDINARIO", valor),
        ("CERTEZA_RECURSO_EXTRAORDINARIO", _CERTEZA_CONFIRMADO),
        (_VARIAVEL_ORIGEM_RECURSO, registro.ID),
    ):
        repositorio.gravar(
            Resposta(
                CASO_ID=CASO_ID,
                ID_PERGUNTA=variavel,
                item_id=recurso,
                valor=valor_do_item,
                QUESTIONARIO_VERSION=colecao.QUESTIONARIO_VERSION,
                respondida_em=_agora(),
            )
        )


def _primeira_exibivel(
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
) -> tuple[RegistroPergunta, PendenciaObrigatoria] | None:
    """`EC-24` — a primeira pendência cuja pergunta é de fato EXIBÍVEL.

    Vive aqui (não em `rotas_pergunta.py`, que a importa) por `T-193`:
    `responder_pergunta`, abaixo, reusa esta mesma função pra devolver a
    PRÓXIMA pergunta já dentro da resposta do `POST` — reaproveitando os
    dados que a gravação já buscou em paralelo, sem nova consulta. Import
    de `rotas_pergunta.py` pra cá criaria ciclo (aquele módulo já importa
    `_itens_por_escopo` e os pontos de injeção daqui); o caminho natural é
    o mesmo desta função original.

    `proxima_pergunta_nao_respondida` (T-45) já exclui pergunta cuja
    condição não vale, mas quem levanta `ErroPerguntaNaoExibivel` é
    `montar_contexto_pergunta` — e é ele a autoridade, porque é a mesma
    `avaliar` usada na gravação. Varrer aqui as pendências EM ORDEM e parar
    na primeira que monta contexto sem erro mantém as duas leituras
    coerentes sem reimplementar nenhuma delas.

    Devolve `None` quando não há mais pendência exibível — coleta completa
    do ponto de vista do grafo condicional corrente (`EC-23`)."""
    pendencia = proxima_pergunta_nao_respondida(colecao.registros, respostas, itens_por_escopo)
    if pendencia is None:
        return None

    registro = _localizar_registro(colecao, pendencia.ID)
    try:
        montar_contexto_pergunta(registro, respostas, item_id=pendencia.item_id)
    except ErroPerguntaNaoExibivel:
        return None
    return registro, pendencia


def _serializar_proxima(
    CASO_ID: str,
    colecao: ColecaoDeRegistros,
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    rotulos: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """`T-193` — o mesmo formato que `GET /caso/{CASO_ID}/pergunta` devolve
    (`rotas_pergunta.py::_renderizar_pergunta`), montado aqui pra ir junto
    da resposta do `POST` — o cliente deixa de precisar pedir de novo algo
    que o servidor já sabia no mesmo instante."""
    encontrada = _primeira_exibivel(colecao, respostas, itens_por_escopo)
    if encontrada is None:
        return {"pergunta": None, "coleta_completa": True}

    registro, pendencia = encontrada
    pergunta = serializar_pergunta_do_caso(
        CASO_ID,
        registro,
        respostas,
        colecao,
        itens_por_escopo,
        pendencia.item_id,
        rotulos or {},
    )
    # `T-309`/`T-310`: a anterior no percurso e a trilha por partes.
    anexar_ao_payload(pergunta, colecao.registros, respostas, itens_por_escopo)
    return {"pergunta": pergunta, "coleta_completa": False}


def serializar_pergunta_do_caso(
    CASO_ID: str,
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    colecao: ColecaoDeRegistros,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    item_id: str | None,
    rotulos: Mapping[str, str],
    com_complementares: bool = True,
) -> dict[str, object]:
    """A pergunta como o cliente a recebe — UMA função para `GET
    /pergunta` e para `proxima` do `POST` (`T-290`): antes eram duas
    montagens, e a do `POST` esquecia o `painel` de `B3.C00`.

    `com_complementares` (`T-307`): `False` ao serializar uma filha — a
    thread tem profundidade 1.

    `ErroPerguntaNaoExibivel` sobe para quem chama (`404` no `GET`)."""
    contexto = montar_contexto_pergunta(
        registro,
        respostas,
        item_id=item_id,
        rotulo_do_item=rotulos.get(item_id or ""),
        itens_por_escopo=itens_por_escopo,
        rotulos=rotulos,
    )
    # `RF-63` (T-148): o localizador do `.top` — "Dívida 3 · pergunta 4 de
    # 12". `None` fora de ficha repetível, e aí o cliente cai no rótulo do
    # bloco. Quem conta é o servidor: ele é que conhece o conjunto exibível.
    posicao = posicao_na_ficha(
        registro, colecao.registros, respostas, item_id, itens_por_escopo=itens_por_escopo
    )
    pergunta = serializar_pergunta(
        contexto,
        CASO_ID=CASO_ID,
        item_id=item_id,
        posicao=posicao.posicao if posicao is not None else None,
        total_na_ficha=posicao.total_na_ficha if posicao is not None else None,
    )
    # `T-294`: a opção escolhida grava o campo em outra variável — reabrir
    # mostra o valor digitado (`AC-102`). Só registro com essa opção.
    if any(opcao.variavel_do_campo for opcao in registro.opcoes):
        escolhida = next(
            (
                o.variavel_do_campo
                for o in registro.opcoes
                if o.variavel_do_campo and o.valor_interno == contexto.valor_atual
            ),
            None,
        )
        pergunta["valor_do_campo"] = (
            None
            if escolhida is None
            else serializar_valor(
                respostas.valor_no_item(item_id, escolhida)
                if item_id
                else respostas.valor(escolhida)
            )
        )
    # `T-227` (RF-79, RF-80): só registro com `painel` declarado no YAML —
    # nenhum `ID` aqui. As respostas são as que o cálculo leria
    # (`_respostas_do_calculo`), para a fotografia e o motor concordarem.
    if registro.painel is not None:
        pergunta["painel"] = serializar_painel(
            fotografia_do_mes(_respostas_do_calculo(colecao.registros, respostas)),
            colecao.registros,
            dict(rotulos),
        )
    # `T-307` (RF-99): as filhas abertas por cada opção, na mesma tela.
    if com_complementares:
        complementares = _complementares(
            CASO_ID, registro, respostas, colecao, itens_por_escopo, item_id, rotulos
        )
        if complementares:
            pergunta["complementares"] = complementares
    return pergunta


def _complementares(
    CASO_ID: str,
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    colecao: ColecaoDeRegistros,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    item_id: str | None,
    rotulos: Mapping[str, str],
) -> dict[str, list[dict[str, object]]]:
    """`T-307` (RF-99, AC-157) — para cada opção da mãe que abre algo, as
    filhas que ficariam exibíveis se a mãe recebesse aquele valor.

    Filha direta: vem logo depois da mãe, no mesmo bloco e escopo (mesma
    ficha), e sua condição lê a variável da mãe. Quem decide se ela abre é a MESMA
    `avaliar` de sempre (via `montar_contexto_pergunta`), sobre as respostas
    gravadas mais o valor provisório da mãe — o cliente só consulta a tabela
    pelo valor escolhido e nunca avalia condição (`RF-45`). Condição que
    depende de outra coisa além da mãe entra só se já vale com o estado
    atual. `SELECAO_MULTIPLA` e `ESCALA_0_10` ficam fora: o valor provisório
    não é uma opção só."""
    variavel = registro.VARIAVEL_GRAVADA
    if variavel is None:
        return {}
    if registro.tipo in _TIPOS_DE_VALOR:
        valores: tuple[str, ...] = tuple(
            o.valor_interno
            for o in registro.opcoes
            if o.valor_interno in _codigos_alternativos(registro)
        )
    elif registro.tipo in (TipoResposta.SELECAO_UNICA, TipoResposta.SIM_NAO_TALVEZ):
        valores = tuple(
            o.valor_interno
            for o in registro.opcoes
            if o.valor_interno is not None and o.abre_campo is not TipoResposta.DATA
        )
    else:
        return {}
    # A thread é o trecho CONTÍGUO depois da mãe que lê a variável dela (ou a
    # de uma filha): a primeira pergunta fora dele encerra a varredura, para
    # que a ordem da coleta não mude (`B5.A02` não puxa `B5.G03`).
    posicao = next(i for i, r in enumerate(colecao.registros) if r is registro)
    lidas = frozenset({variavel})
    filhas: list[RegistroPergunta] = []
    for seguinte in colecao.registros[posicao + 1 :]:
        variaveis = (
            _variaveis_da_condicao(seguinte.condicao_exibicao)
            if seguinte.condicao_exibicao is not None
            else frozenset()
        )
        if not variaveis & lidas:
            break
        if seguinte.VARIAVEL_GRAVADA is not None:
            lidas = lidas | {seguinte.VARIAVEL_GRAVADA}
        if (
            variavel in variaveis
            and seguinte.bloco == registro.bloco
            and seguinte.escopo_repeticao is registro.escopo_repeticao
        ):
            filhas.append(seguinte)
    resultado: dict[str, list[dict[str, object]]] = {}
    for valor in valores if filhas else ():
        provisorias = _respostas_com_valor_provisorio(respostas, registro, item_id, valor)
        abertas: list[dict[str, object]] = []
        for filha in filhas:
            try:
                abertas.append(
                    serializar_pergunta_do_caso(
                        CASO_ID,
                        filha,
                        provisorias,
                        colecao,
                        itens_por_escopo,
                        item_id,
                        rotulos,
                        com_complementares=False,
                    )
                )
            except ErroPerguntaNaoExibivel:
                continue
        if abertas:
            resultado[valor] = abertas
    return resultado


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
