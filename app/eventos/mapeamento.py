"""Mapeamento de resposta do Bloco 11 para membro de `EVENTO_RECALCULO`
(`RF-28`, `AC-35`).

**A garantia estrutural de `AC-35` (`R-04`).** `engine.tipos.EVENTO_RECALCULO`
(`engine/tipos.py`, `T-05`) não tem — e não pode ter — um membro para
"alteração cadastral" ou "mudança cosmética de registro": o enum lista só
`QUITACAO_CONFIRMADA` e os dez eventos materiais externos da canônica
(`ALTERACAO_RENDA`, `ALTERACAO_DESPESAS`, `NOVA_DIVIDA`,
`RENEGOCIACAO_EXECUTADA`, `TROCA_EXECUTADA`, `RECURSO_EXTRAORDINARIO`,
`INFORMACAO_MATERIAL_CONHECIDA`, `MUDANCA_PATRIMONIAL`, `PROPOSTA_TEMPORARIA`,
`ALTERACAO_RISCO`, `OUTRO_MATERIAL`). `evento_recalculo_da_resposta`, abaixo,
devolve `EVENTO_RECALCULO | None` resolvendo o `valor_interno` da resposta
contra um dicionário estático (`_EVENTOS_POR_VALOR_INTERNO`) — para uma
alteração cadastral não existir na saída da função não é o resultado de um
`if` que a filtra: é que NENHUMA entrada do dicionário produz um evento a
partir dela, porque não existe (e não pode existir) o membro do enum que
seria necessário para a entrada existir. `AC-35` é satisfeito pelo TIPO do
enum, não por lógica condicional aqui — ver
`test_evento_recalculo_por_alteracao_cadastral_e_inexprimivel_no_enum`
(`tests/app_aluno/estatica/test_mapeamento_eventos_ac_35.py`) para a prova
estrutural (mesmo padrão de `engine/eventos.py::avaliar_gatilho_recalculo`,
que CONSOME o resultado desta função).

**Nenhuma leitura de relógio.** A função é pura sobre a resposta recebida:
não há `date.today()`/`datetime.now()` neste módulo, e "virada de mês" não é
sequer uma entrada que a função aceita — passagem de tempo, sozinha, nunca
chega a ser avaliada aqui (`R-04`, segundo critério de aceite de `T-81`).

**Mapeamento por `valor_interno`, sem `if` por pergunta (terceiro critério).**
Mesmo padrão de `_membro_do_enum` (`app/montagem/estado.py`, `T-50`): a
resolução é uma busca em dicionário por `valor_interno`, nunca uma cadeia de
`if resposta == "X": return EVENTO_RECALCULO.X`. Diferente de
`_membro_do_enum` (que resolve `EnumClasse[valor_interno]` por nome idêntico),
aqui o `valor_interno` do registro (`STATUS_QUITACAO_REAL`, `B11.Q01`,
`collection/registros/bloco-11.yaml`, T-18) usa o rótulo de NEGÓCIO
`"QUITADA"`, que não é o `name` de nenhum membro de `EVENTO_RECALCULO`
(`QUITACAO_CONFIRMADA`) — por isso o mecanismo genérico por nome não se
aplica, e o dicionário explícito é o mapeamento correto: ele mesmo é dado
declarativo, sem `if` de pergunta a pergunta.

**Escopo do dicionário — só o que `T-18` transcreveu com `valor_interno`
real.** `collection/registros/bloco-11.yaml` grava `valor_interno` não-nulo
apenas para as três opções de `B11.Q01` (`STATUS_QUITACAO_REAL`): `QUITADA`,
`NAO`, `A_CONFIRMAR`. As quatro perguntas de resultado de ação
(`B11.03-INF`/`-REN`/`-TRO`/`-ECO`, `RESULTADO_ACAO_*`) têm `valor_interno:
null` em todas as opções no registro real — nenhuma delas oferece hoje uma
chave utilizável para o mesmo mecanismo de mapeamento por `valor_interno`.
Codificar esses `valor_interno` é decisão de registro (fora do escopo desta
tarefa, `Arquivos: app/eventos/mapeamento.py`); mapear
`RENEGOCIACAO_EXECUTADA`/`TROCA_EXECUTADA`/os demais eventos materiais fica
para quando essa transcrição existir — lacuna documentada, não estimada
silenciosamente (mesmo padrão de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` em
`app/montagem/estado.py`, T-49).

**Ausência explícita, nunca membro genérico (quarto critério).** `NAO` e
`A_CONFIRMAR` (`RF-29`, `AC-31`: "acredito que sim, mas ainda preciso
confirmar" não dispara nada) não têm entrada no dicionário — resolvê-los
devolve `None` pelo mesmo `dict.get`, o mesmo caminho estrutural que atende a
alteração cadastral. Não há um evento "coringa" para resposta desconhecida:
uma variável ou `valor_interno` fora do dicionário também devolve `None`,
nunca um membro qualquer do enum.

O tipo de retorno (`EVENTO_RECALCULO | None`) é exatamente o parâmetro de
`engine.eventos.avaliar_gatilho_recalculo` (`engine/eventos.py`, T-66) — quem
CONSOME o evento que esta função produz.

REGRAS: `RF-28`, `AC-35`
"""

from __future__ import annotations

from typing import Final

from engine.tipos import EVENTO_RECALCULO

# `VARIAVEL_GRAVADA` de B11.Q01 (`collection/registros/bloco-11.yaml`, T-18).
VARIAVEL_STATUS_QUITACAO_REAL: Final[str] = "STATUS_QUITACAO_REAL"

# Mapeamento declarativo `(VARIAVEL_GRAVADA, valor_interno) → EVENTO_RECALCULO`
# — dado, não lógica de `if` por pergunta (terceiro critério de aceite de
# `T-81`). Só `QUITADA` tem entrada: `NAO`/`A_CONFIRMAR` (RF-29, AC-31) e
# qualquer alteração cadastral (R-04, AC-35) são ausência ESTRUTURAL de
# chave, nunca filtradas por condicional.
_EVENTOS_POR_VALOR_INTERNO: Final[dict[tuple[str, str], EVENTO_RECALCULO]] = {
    (VARIAVEL_STATUS_QUITACAO_REAL, "QUITADA"): EVENTO_RECALCULO.QUITACAO_CONFIRMADA,
}


def evento_recalculo_da_resposta(
    VARIAVEL_GRAVADA: str, valor_interno: str
) -> EVENTO_RECALCULO | None:
    """RF-28, AC-35 — resolve a resposta do Bloco 11 (identificada por sua
    `VARIAVEL_GRAVADA` e o `valor_interno` gravado) para o membro
    correspondente de `EVENTO_RECALCULO`, ou `None` quando não há
    correspondência (`RF-29`/`AC-31` para `NAO`/`A_CONFIRMAR`; `R-04`/`AC-35`
    para qualquer alteração cadastral ou cosmética — inexprimível no enum, ver
    docstring do módulo).

    Pura sobre os dois parâmetros recebidos: nenhuma leitura de relógio,
    nenhuma consulta a estado do caso — "virada de mês" não é uma entrada
    aceita por esta função, e por isso nunca produz evento (segundo critério
    de aceite de `T-81`)."""
    return _EVENTOS_POR_VALOR_INTERNO.get((VARIAVEL_GRAVADA, valor_interno))
