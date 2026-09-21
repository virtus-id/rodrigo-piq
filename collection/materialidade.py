"""Materialidade derivada do contrato de entrada — `OQ-08`, `RF-11` · `RF-34`.

`plans/app-aluno.plan.md` §4.2 — o ponto mais delicado do plano. Avisar "na
hora" que um "não sei" pode deixar o plano provisório exige saber, durante o
preenchimento, se aquele campo é material — **antes** de o motor rodar. Esta
aplicação não pode reimplementar `INFORMACAO_PENDENTE` (`RF-34`, Lei nº 3):
fazer isso duplicaria a regra do Gate 1 em dois lugares.

O caminho adotado pelo plano é derivar a materialidade do PRÓPRIO CONTRATO DE
ENTRADA do motor, por introspecção, nunca por regra transcrita:

    um campo é MATERIAL  <=>  ele é anotado `DinheiroTalvez`/`TaxaTalvez`/
                              `int | Desconhecido` em `Divida`/`EstadoFinanceiro`

Ou seja: material é exatamente o campo que o motor **admite** receber como
`Desconhecido` — e que por isso pode propagar `INFORMACAO_PENDENTE`. Um campo
tipado `Dinheiro`/`Taxa` puro nem sequer aceita "não sei"; um campo que não é
um destes tipos-soma não afeta o plano dessa forma.

Critério operacional de introspecção (decisão desta tarefa): resolve-se cada
anotação de `typing.get_type_hints(Divida)`/`typing.get_type_hints(
EstadoFinanceiro)` — que, com `from __future__ import annotations` em
`engine/estado.py`, resolve as strings para os objetos de tipo reais — e
percorre-se `TypeAliasType` (o runtime de `type DinheiroTalvez = ...`) até o
tipo de valor final. Um campo é material se esse tipo final é uma união
(`types.UnionType`, produzida pela sintaxe `X | Y`) cujos membros incluem a
classe `Desconhecido`. Isso cobre uniformemente `DinheiroTalvez` (alias de
`Dinheiro | Desconhecido`), `TaxaTalvez` (alias de `Taxa | Desconhecido`) e
`int | Desconhecido` escrito diretamente — sem distinguir os três por nome,
só pela presença estrutural de `Desconhecido` na união. `Oportunidade | None`
não é material por este critério: `None` não é `Desconhecido` — ausência
estrutural e valor desconhecido são coisas diferentes (RF-16 do motor).

O QUE ISSO NÃO É, e a honestidade importa: esta função não prevê o que o
motor fará com o dado. Ela responde apenas "este campo é do tipo que o motor
aceita como desconhecido" — o fato (`INFORMACAO_PENDENTE`, `ORDEM_STATUS`
provisório) continua sendo decidido inteiramente pelo motor.

`AvisoMaterialidade`/`avaliar_ao_responder` (T-41, `OQ-08`) — o aviso NA HORA
------------------------------------------------------------------------------
`plans/app-aluno.plan.md` §4.2 e §8 (linha "não sei em campo material") fecham
a decisão de `OQ-08`: o aluno é avisado NA HORA, não só no relatório final.
`avaliar_ao_responder(variavel_gravada, valor_resposta)` devolve um
`AvisoMaterialidade` quando `variavel_gravada` está em `campos_materiais()` E
`valor_resposta` é `NaoSei.NAO_SEI` — e `None` em qualquer outro caso (campo
não material, ou resposta que não é "não sei"). Nenhuma outra condição entra
aqui: quem decide o FATO (se o plano realmente fica provisório) é o motor —
Gate 1, o fallback de taxa da §11.1, `ORDEM_STATUS` — nunca esta função.

**Redação: "pode", nunca "vai"/"será".** O plano §8 fixa a frase de referência
("esta informação pode deixar seu plano provisório") como a única regra
normativa sobre o texto: uma possibilidade derivada do contrato, nunca uma
previsão do fato. `AvisoMaterialidade.texto` carrega essa redação.

**Decisão desta tarefa sobre ONDE o texto vive, e por quê.** Diferente do
texto de consentimento (`app/consentimento/registro.py`, `PEND-01`), que é
insumo jurídico externo ainda pendente e por isso vive em YAML versionado à
parte, o aviso de materialidade é uma ÚNICA redação genérica — não há 291
variantes por pergunta, só uma frase curta reaproveitada para qualquer campo
material, e a regra sobre ela ("pode", nunca "vai"/"será") já é normativa
(plano §8), não um insumo externo em aberto como `PEND-01`. Por isso o texto
NÃO ganha um arquivo `.yaml` à parte (indireção sem benefício para uma frase
só, fixa por regra normativa, não por decisão editorial de terceiro) nem é
escrito boca a boca no template a cada uso: `TEXTO_AVISO_MATERIALIDADE`,
abaixo, é a ÚNICA fonte da redação-núcleo, curta o bastante (< 40 caracteres)
para não disparar `AC-37`/T-08 — que audita *enunciado de pergunta* longo,
não qualquer string — e `AvisoMaterialidade.texto` a carrega, exatamente
como o plano declara o campo `texto: str` do dataclass. O template
(`report/templates/coleta/aviso_materialidade.html`) é quem recebe esse
texto via Jinja2 e o insere na frase completa exibida ao aluno (rótulo,
pontuação, `role`/`aria-describedby`) — a REDAÇÃO NO CONTEXTO FINAL da UI é
do template, mas o NÚCLEO normativo ("pode deixar seu plano provisório") é
uma constante única do módulo, nunca duplicado por chamador. Isso preserva
"a redação é insumo do registro, não do desenvolvedor" no sentido em que
importa aqui: o texto não está espalhado por 291 lugares nem inventado pelo
código de rota — está declarado uma única vez, junto da regra que o rege.

**Fronteira com T-42.** Esta tarefa entrega a PEÇA: a função que decide SE o
aviso aparece (`avaliar_ao_responder`) e o template que o renderiza
isoladamente. A integração com a rota de resposta (`app/http/
rotas_coleta.py`) — chamar `avaliar_ao_responder` depois de gravar a
resposta e incluir o HTML renderizado do aviso NA MESMA resposta HTTP que
confirma a gravação (HTMX, sem recarregar a página) — é trabalho de `T-42`,
ainda não implementada. Os testes desta tarefa cobrem a função isoladamente
e a renderização do template isoladamente (Jinja2 direto); não existe hoje
uma rota HTTP real para testar a integração ponta a ponta.

REGRAS: `RF-11`, `RF-34`, `AC-41`
"""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from collection.respostas import NAO_SEI, ValorResposta
from engine.estado import Divida, EstadoFinanceiro
from engine.tipos import Desconhecido

# Redação-núcleo do aviso (plano §8), ver docstring acima: "pode", nunca
# "vai"/"será" — quem decide o FATO é o motor. Curta o bastante para não
# disparar o limiar de string longa de `AC-37`/T-08 (40 caracteres). O
# template (`report/templates/coleta/aviso_materialidade.html`) recebe este
# texto e o compõe na frase completa exibida ao aluno.
TEXTO_AVISO_MATERIALIDADE: Final[str] = "pode deixar seu plano provisório"


def _resolver_ate_o_valor(tipo: object) -> object:
    """Segue a cadeia de `typing.TypeAliasType` (`type X = ...`) até o tipo
    de valor final. `DinheiroTalvez`/`TaxaTalvez`/`Dinheiro`/`Taxa` chegam de
    `get_type_hints` como `TypeAliasType`; `__value__` dá um passo na cadeia
    — repetido até sobrar algo que não é mais um alias (ex.: a união
    `Decimal | Desconhecido`, ou a classe `Decimal`)."""
    while isinstance(tipo, typing.TypeAliasType):
        tipo = tipo.__value__
    return tipo


def _e_material(tipo_anotado: object) -> bool:
    """Um campo é material quando seu tipo resolvido é uma união (`X | Y`,
    `types.UnionType`) que inclui `Desconhecido` entre seus membros — o
    critério estrutural do contrato descrito no docstring do módulo. Nenhum
    nome de campo é comparado; só a forma do tipo."""
    tipo_resolvido = _resolver_ate_o_valor(tipo_anotado)
    if not isinstance(tipo_resolvido, types.UnionType):
        return False
    return Desconhecido in typing.get_args(tipo_resolvido)


@lru_cache(maxsize=1)
def campos_materiais() -> frozenset[str]:
    """Nomes dos campos de `Divida` e `EstadoFinanceiro` que o motor admite
    receber como `Desconhecido` — derivados por introspecção do contrato de
    entrada (`engine.estado`), nunca por lista escrita à mão (`RF-34`).

    `lru_cache` garante que a introspecção via `typing.get_type_hints` roda
    uma única vez, na primeira chamada (equivalente a "uma vez na carga"),
    não a cada resposta do aluno."""
    materiais: set[str] = set()
    for contrato in (Divida, EstadoFinanceiro):
        dicas = typing.get_type_hints(contrato)
        for nome_campo, tipo_anotado in dicas.items():
            if _e_material(tipo_anotado):
                materiais.add(nome_campo)
    return frozenset(materiais)


@dataclass(frozen=True, slots=True)
class AvisoMaterialidade:
    """O aviso a exibir NA HORA (`OQ-08`) quando o aluno responde "não sei" a
    um campo material. `VARIAVEL_GRAVADA` identifica o campo — é o que o
    template usa para vincular o aviso a ele (`id`/`aria-describedby`);
    `texto` é a redação-núcleo (`TEXTO_AVISO_MATERIALIDADE`), nunca
    reconstruída fora deste módulo."""

    VARIAVEL_GRAVADA: str
    texto: str


def avaliar_ao_responder(
    variavel_gravada: str, valor_resposta: ValorResposta
) -> AvisoMaterialidade | None:
    """Decide SE o aviso de materialidade aparece para a resposta recém-
    gravada — RF-11, `OQ-08`. Devolve `AvisoMaterialidade` quando as DUAS
    condições valem: (1) `variavel_gravada` está em `campos_materiais()`;
    (2) `valor_resposta` é `NAO_SEI`. Em qualquer outro caso — campo não
    material, ou resposta com valor concreto — devolve `None`, sem aviso.

    Nenhuma outra condição entra aqui: esta função não consulta o motor, não
    lê `SnapshotOrdem` e não prevê `ORDEM_STATUS` — ela só materializa o
    critério estrutural de `campos_materiais()` no momento em que uma
    resposta concreta chega. O FATO (se o plano realmente fica provisório)
    continua sendo decidido inteiramente pelo motor (Gate 1, fallback de
    taxa, `ORDEM_STATUS`), nunca por esta função.

    **Fronteira com T-42**: esta função é chamada pela rota de resposta
    (`app/http/rotas_coleta.py`, T-42, ainda não implementada) depois da
    gravação confirmada, para decidir se o aviso entra na mesma resposta
    HTTP. Aqui ela é testada isoladamente, sem rota."""
    if variavel_gravada not in campos_materiais():
        return None
    if valor_resposta is not NAO_SEI:
        return None
    return AvisoMaterialidade(
        VARIAVEL_GRAVADA=variavel_gravada, texto=TEXTO_AVISO_MATERIALIDADE
    )
