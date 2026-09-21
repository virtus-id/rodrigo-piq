"""Monta o contexto de renderização de uma pergunta — `RF-03`, `RF-06`
(`AC-05`, `AC-36`, T-43).

`plans/app-aluno.plan.md` §4.1, §5.1. `app/http/serializacao.py`
(um template só, com um ramo Jinja2 por `TipoResposta`) não lê nada além das
variáveis que este módulo entrega: nenhum enunciado, opção ou condição está
escrito no template como literal — tudo vem do `RegistroPergunta` (T-09),
possivelmente reescrito por interpolação (T-12) e por opções vindas do motor
(T-14) ANTES de chegar ao Jinja2.

**Fronteira interpolação/opções-do-motor — decisão desta tarefa.** O enunciado
interpolado (marcadores `[Dxxx]`, `T-12`) e as opções efetivas (`origem_opcoes.
fonte = SNAPSHOT`, `T-14`) são resolvidos AQUI, em `montar_contexto_pergunta`,
nunca no template Jinja2 e nunca em uma rota GET. Duas razões:

1. **O servidor como única autoridade (T-43, descrição da tarefa).** Se o
   template chamasse `interpolar`/`opcoes_efetivas` diretamente (via função
   Jinja2 exposta), a lógica de resolução ficaria espalhada entre Python e
   template — o mesmo problema estrutural que a Lei nº 3 do backlog proíbe
   para condicional/materialidade. Resolver tudo em `renderizacao.py` mantém
   UM lugar só de onde "o que o aluno vê" é decidido.
2. **Não existe hoje uma rota GET que renderize a página de pergunta**
   (`app/http/rotas_coleta.py`, T-42, só tem o `POST` de gravação — o
   algoritmo de "qual é a próxima pergunta", `app/casos/progresso.py`, é
   `T-45`, ainda não implementado). `montar_contexto_pergunta` é escrita para
   ser chamada por QUALQUER caminho futuro que precise renderizar uma
   pergunta — a rota GET de T-45/T-44, ou os testes desta tarefa, que a
   exercitam diretamente com um `RegistroPergunta` sintético, sem subir uma
   rota HTTP. A fronteira documentada aqui é: `renderizacao.py` decide O QUE
   aparece (enunciado final, opções finais, se o campo está aberto); a futura
   rota GET decide QUAL pergunta mostrar; o template decide COMO desenhar o
   campo HTML para aquele `TipoResposta`.

Este módulo NUNCA decide se uma pergunta está aberta para RESPOSTA (isso
continua sendo `collection/condicoes.py::avaliar`, chamado por
`app/http/rotas_coleta.py` no momento do `POST`) — mas ele PRECISA saber se a
pergunta está aberta para EXIBIÇÃO, pela mesma função `avaliar`, para que o
HTML da pergunta simplesmente não seja produzido quando a condição é falsa
("nenhuma regra de exibição é duplicada em JS", critério de aceite 4: a única
implementação de `Condicao` continua sendo a de `collection/condicoes.py`).

REGRAS: `RF-03`, `RF-06`, `AC-05`, `AC-36`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from collection.condicoes import avaliar
from collection.interpolacao import ContextoItem, interpolar
from collection.materialidade import AvisoMaterialidade
from collection.opcoes_do_motor import opcoes_efetivas
from collection.registro import OpcaoRegistro, RegistroPergunta
from collection.respostas import NAO_SEI, RespostasCaso, ValorResposta
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-03", "RF-06", "AC-05", "AC-36")


class ErroPerguntaNaoExibivel(Exception):
    """A `condicao_exibicao` do registro avalia como falsa sobre as respostas
    do caso — a pergunta não deve ser renderizada. Mesmo critério de
    `app/http/rotas_coleta.py::_exigir_pergunta_aberta` (T-42), reaproveitado
    aqui para a exibição: nunca uma segunda implementação da regra."""


@dataclass(frozen=True, slots=True)
class ContextoPergunta:
    """Tudo que `app/http/serializacao.py::serializar_pergunta` recebe —
    nenhum outro
    dado chega ao template. `enunciado` já está interpolado (T-12);
    `opcoes` já são as efetivas (T-14, `REGISTRO` ou `SNAPSHOT`); `valor_atual`
    é o valor já respondido, para reabrir a pergunta com o campo preenchido
    (ou `None`, ainda não respondida). `respondida_como_nao_sei` e
    `valores_marcados` são derivados aqui (nunca no template): Jinja2 não
    compara Enum por identidade de forma natural, e decidir isso em Python
    evita qualquer ambiguidade de template sobre "o que conta como não sei"
    ou "o que conta como marcado" em `SELECAO_MULTIPLA`."""

    registro: RegistroPergunta
    enunciado: str
    opcoes: tuple[OpcaoRegistro, ...]
    valor_atual: ValorResposta | None
    respondida_como_nao_sei: bool
    valores_marcados: frozenset[str]
    aviso: AvisoMaterialidade | None


def montar_contexto_pergunta(
    registro: RegistroPergunta,
    respostas: RespostasCaso,
    *,
    item_id: str | None = None,
    snapshot: SnapshotOrdem | None = None,
    aviso: AvisoMaterialidade | None = None,
) -> ContextoPergunta:
    """Resolve tudo que o template precisa a partir do registro + respostas
    já dadas + snapshot opcional do caso (T-14).

    `item_id` é o identificador do item corrente, para pergunta `REP`
    (`escopo_repeticao != NENHUM`) — usado tanto para ler o valor já
    respondido NAQUELE item quanto como `ContextoItem.item_id` da
    interpolação (`[Dxxx]` em `B11.Q01`, RF-06/AC-05).

    Levanta `ErroPerguntaNaoExibivel` quando `condicao_exibicao` do registro
    avalia como falsa — a MESMA função `avaliar` de `collection/condicoes.py`
    usada pela rota de gravação (T-42), nunca uma segunda implementação."""
    if registro.condicao_exibicao is not None and not avaliar(
        registro.condicao_exibicao, respostas
    ):
        raise ErroPerguntaNaoExibivel(registro.ID)

    contexto_interpolacao = ContextoItem(
        item_id=item_id, respostas=respostas, snapshot=snapshot
    )
    enunciado = interpolar(registro.enunciado, registro.interpolacoes, contexto_interpolacao)
    opcoes = opcoes_efetivas(registro, snapshot)
    valor_atual = _valor_ja_respondido(registro, respostas, item_id)

    return ContextoPergunta(
        registro=registro,
        enunciado=enunciado,
        opcoes=opcoes,
        valor_atual=valor_atual,
        respondida_como_nao_sei=valor_atual is NAO_SEI,
        valores_marcados=_valores_marcados(valor_atual),
        aviso=aviso,
    )


def _valores_marcados(valor_atual: ValorResposta | None) -> frozenset[str]:
    """`SELECAO_MULTIPLA` grava um `frozenset[str]` (T-22, `ValorResposta`);
    qualquer outro valor corrente (`None`, `NAO_SEI`, ou um valor de outro
    tipo) não tem marcação nenhuma para reabrir — conjunto vazio, nunca uma
    tentativa de iterar algo que não é a coleção esperada."""
    if isinstance(valor_atual, frozenset):
        return valor_atual
    return frozenset()


def _valor_ja_respondido(
    registro: RegistroPergunta, respostas: RespostasCaso, item_id: str | None
) -> ValorResposta | None:
    """Lê o valor corrente da variável, no item quando repetível — mesma
    convenção de indexação de `RespostasCaso` (T-22): pergunta não repetível
    consulta `valor`, pergunta repetível consulta `valor_no_item`."""
    if registro.VARIAVEL_GRAVADA is None:
        return None
    if item_id is not None:
        return respostas.valor_no_item(item_id, registro.VARIAVEL_GRAVADA)
    return respostas.valor(registro.VARIAVEL_GRAVADA)
