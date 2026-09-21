"""Bloco 10 — confirmação do ataque imediato, condicional ao motor —
`RF-18`, `AC-22`, `AC-23`, `AC-24` (T-77, T-78).

`ESTADO_CASO.CONFIRMACAO_ATAQUE` (`app/casos/maquina.py`, T-33) só é
alcançável quando `snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO > 0`
(`PLANO_LIBERADO → CONFIRMACAO_ATAQUE`, gatilho `abre_bloco_10`, guarda
"AC-22: ataque recomendado > 0", já declarada na tabela de transições desde
T-33) — este módulo é quem AVALIA essa guarda: `bloco_10_alcancavel` LÊ o
campo, nunca recalcula (Lei nº 3, `plans/app-aluno.plan.md` §1: a aplicação
não calcula).

**`OQ-17` foi respondida e o campo foi implementado pelo slug
`motor-calculo`.** Confirmado por leitura direta de `engine/diagnostico.py`
(`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro`, RF-51/RF-66/RF-69) e
`engine/motor.py::calcular_plano` (a segunda passada substitui o placeholder
`dinheiro(0)` pelo valor REAL, via `_compor_ATAQUE_IMEDIATO_RECOMENDADO`,
antes de `montar_SnapshotOrdem` ser chamado) — `motor-calculo:OQ-29` está
"RESPONDIDA E IMPLEMENTADA POR COMPLETO" (`specs/motor-calculo.spec.md`
§14.2.4, fatia 4C, 2026-09-10). `snapshot.diagnostico.ATAQUE_IMEDIATO_
RECOMENDADO` já é o valor publicado no `SnapshotOrdem` — leitura direta de
campo, nenhuma segunda via de cálculo nesta camada.

## `B10.C01` — os três caminhos (RF-18)

`collection/registros/bloco-10.yaml::B10.C01` (`TODO`/`PARTE`/`NAO`/
`REVISAR`) cobre os três destinos normativos: aceite TOTAL (`TODO`), aceite
PARCIAL (`PARTE`, que abre `B10.C01A` para o valor exato) e NENHUM aceite
(`NAO`/`REVISAR` — a quarta opção existe no registro, mas os três CAMINHOS
de `RF-18` são total/parcial/nenhum; `REVISAR` cai no mesmo destino de "nada
confirmado ainda", conforme `salto_consequencia` do próprio registro). Os
três são sempre gravados como resposta (`VARIAVEL_GRAVADA:
ATAQUE_IMEDIATO_APROVADO`) — nenhum caminho é silenciosamente descartado.

## `AC-24` — nenhuma pergunta pede escolha de dívida

A ordem de quitação é do motor (`ORDEM_QUITACAO`, `SnapshotOrdem`), nunca do
aluno. `perguntas_do_bloco_10` devolve exatamente as perguntas do registro
com `bloco: 10` — nenhuma delas tem `escopo_repeticao: DIVIDA_ID` nem opção
cujo domínio seja "qual dívida" (`collection/registros/bloco-10.yaml`,
auditado por `tests/app_aluno/test_bloco10.py`, T-79). Este módulo não
filtra nem seleciona dívida nenhuma — só lê o registro, mesmo mecanismo de
`app/casos/coleta_dirigida.py::perguntas_do_bloco_7`.

## `T-78` — o limite superior da validação de `B10.C01A`

`collection/registros/bloco-10.yaml::B10.C01A` já declara, via o comparador
genérico de `T-13` (`collection/validacao.py::validar_cruzada`), duas
`ValidacaoCruzada`: `0 <= ATAQUE_IMEDIATO_APROVADO` (limite inferior, `ZERO`
é constante resolvida por qualquer `Respostas`) e `ATAQUE_IMEDIATO_APROVADO
<= ATAQUE_IMEDIATO_RECOMENDADO` (limite superior, nomeando literalmente o
campo do snapshot). Nenhum limiar é um literal em `.py` — a validação em si
é inteiramente declarativa no registro.

O problema que este módulo resolve: `validar_cruzada` só sabe consultar
`Respostas.valor_no_item` — uma fonte de RESPOSTAS gravadas
(`collection/respostas.py::RespostasCaso`), que nunca teve (e não deveria
ter) noção de campo de snapshot. `RespostasDoBloco10` é o adaptador que
satisfaz estruturalmente o mesmo `Protocol` (`collection/validacao.py::
Respostas`), delegando toda variável comum para a `RespostasCaso` real do
caso, mas RESOLVENDO as duas variáveis especiais desta validação sem tocar
o repositório de respostas:

- `ZERO` → `Decimal(0)` sempre, qualquer que seja o item — a mesma
  constante que `B10.C01A` usa como limite inferior, nunca uma dívida ou
  item real (comentário do próprio YAML).
- `ATAQUE_IMEDIATO_RECOMENDADO` → `ataque_imediato_recomendado_de(snapshot)`,
  a MESMA leitura de campo que `bloco_10_alcancavel` já usa — nunca um
  segundo cálculo, nunca uma segunda fonte de verdade.

Qualquer outra variável (`ATAQUE_IMEDIATO_APROVADO`, a resposta que o aluno
acabou de dar) é delegada sem alteração para a `RespostasCaso` recebida —
este adaptador NUNCA inventa um valor para uma variável que não seja uma das
duas constantes do snapshot.

REGRAS: `RF-18`, `AC-22`, `AC-23`, `AC-24`
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from app.montagem.conversao import converter_para_dinheiro
from collection.registro import RegistroPergunta
from engine.snapshot import SnapshotOrdem

if TYPE_CHECKING:
    from collection.respostas import RespostasCaso, ValorResposta

REGRAS: Final[tuple[str, ...]] = ("RF-18", "AC-22", "AC-23", "AC-24")

_BLOCO_10: Final[int] = 10

# Os dois nomes que `B10.C01A` (collection/registros/bloco-10.yaml) usa como
# `variavel_esquerda`/`variavel_direita` para expressar os limites sem
# literal em código — resolvidos por RespostasDoBloco10, nunca por
# RespostasCaso (que não conhece nem ZERO nem o snapshot).
_VARIAVEL_ZERO: Final[str] = "ZERO"
_VARIAVEL_ATAQUE_IMEDIATO_RECOMENDADO: Final[str] = "ATAQUE_IMEDIATO_RECOMENDADO"

# RF-13: `Decimal(...)` só é construído em `app/montagem/conversao.py` — este
# módulo nunca chama `Decimal(...)`/`dinheiro(...)` diretamente, mesmo para a
# constante zero (`tests/app_aluno/estatica/test_fronteira_decimal_unica.py`,
# T-27). `converter_para_dinheiro("0")` é a mesma fronteira única que
# `app/montagem/estado.py::_ZERO` já usa para o mesmo propósito.
_ZERO: Final[Decimal] = converter_para_dinheiro("0")


def ataque_imediato_recomendado_de(snapshot: SnapshotOrdem) -> Decimal:
    """`RF-18` — leitura direta de `snapshot.diagnostico.ATAQUE_IMEDIATO_
    RECOMENDADO`, o valor REAL já publicado por `engine.motor.calcular_plano`
    (`motor-calculo:OQ-29`, respondida). Nenhum recálculo: só o acesso ao
    campo, mesma disciplina de leitura de `app/casos/coleta_dirigida.py`
    sobre `ORDEM_ACOES`."""
    return snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO


def bloco_10_alcancavel(snapshot: SnapshotOrdem) -> bool:
    """`AC-22` — a guarda de `PLANO_LIBERADO → CONFIRMACAO_ATAQUE`
    (`app/casos/maquina.py::TABELA_TRANSICOES`, gatilho `abre_bloco_10`):
    `True` somente quando `ATAQUE_IMEDIATO_RECOMENDADO > 0`. Com o campo
    igual a zero, o caso nunca alcança `CONFIRMACAO_ATAQUE` e `B10.C01` não é
    exibida — o chamador (rota/orquestração do caso) consulta esta função
    antes de disparar o gatilho, nunca reimplementando o limiar."""
    return ataque_imediato_recomendado_de(snapshot) > _ZERO


def perguntas_do_bloco_10(
    registros: tuple[RegistroPergunta, ...],
) -> tuple[RegistroPergunta, ...]:
    """`AC-24` — as perguntas `B10.C01`/`B10.C01A`, na ordem do próprio
    registro (`collection/registros/bloco-10.yaml`, T-18) — filtro por
    `registro.bloco == 10`, nenhuma lista de `ID` codificada à mão. Nenhuma
    das duas tem `escopo_repeticao` por dívida nem opção de escolha de
    dívida (auditado por `tests/app_aluno/test_bloco10.py`, T-79) — este
    módulo não decide isso, só lê o que o registro já declara."""
    return tuple(registro for registro in registros if registro.bloco == _BLOCO_10)


@dataclass(frozen=True, slots=True)
class RespostasDoBloco10:
    """`T-78` — adaptador que satisfaz estruturalmente `collection.
    validacao.Respostas` (mesma assinatura de `valor_no_item`), resolvendo
    `ZERO`/`ATAQUE_IMEDIATO_RECOMENDADO` a partir do snapshot e delegando
    qualquer outra variável para `respostas` (a `RespostasCaso` real do
    caso, já incluindo a resposta provisória de `ATAQUE_IMEDIATO_APROVADO`
    que a rota resolveu). Usado como `respostas` de `collection.validacao.
    validar_cruzada` ao validar `B10.C01A` — nenhuma outra pergunta desta
    feature precisa deste adaptador, porque nenhuma outra validação cruzada
    do backlog compara contra um campo de snapshot."""

    respostas: RespostasCaso
    snapshot: SnapshotOrdem

    def valor_no_item(self, item_id: str, variavel: str) -> ValorResposta | None:
        if variavel == _VARIAVEL_ZERO:
            return _ZERO
        if variavel == _VARIAVEL_ATAQUE_IMEDIATO_RECOMENDADO:
            return ataque_imediato_recomendado_de(self.snapshot)
        return self.respostas.valor_no_item(item_id, variavel)
