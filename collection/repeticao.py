"""Fichas repetíveis — o núcleo de `RF-04` (`AC-04`).

`plans/app-aluno.plan.md` §4.1/§4.3. 115 das 291 perguntas são `REP`
(`escopo_repeticao != NENHUM`, T-09): cada uma delas pertence a uma FICHA —
uma instância de dívida, vínculo, margem, item de despesa, ação, renda
adicional ou despesa não-mensal (os dois últimos desde `T-105`/`OQ-19`) — e é
respondida uma vez por item cadastrado, nunca uma vez por caso.

Este módulo cobre duas responsabilidades, e só essas duas:

1. `perguntas_da_ficha` — dado um `escopo_repeticao` e o conjunto de
   registros carregados, devolve exatamente as perguntas que pertencem a uma
   ficha daquele escopo. O filtro é `registro.escopo_repeticao == escopo`,
   nunca uma lista de blocos ou de `ID`s escrita à mão — é isso que garante
   que o conjunto de perguntas de uma ficha nasce do próprio registro, não de
   um mapeamento paralelo que pode divergir dele (`AC-37`).

2. `GeradorDeIdentificadorDeItem` (`Protocol`) + `GeradorDeIdentificadorEmMemoria`
   — o mecanismo de identificador ESTÁVEL e NUNCA REAPROVEITADO por
   `(CASO_ID, escopo)`. Este módulo NÃO persiste nada: a persistência real de
   `itens_repetidos` (`DIVIDA_ID`/`MARGEM_ID`/`VINCULO_ID` estáveis por caso,
   plano §4.5) é trabalho de `persistencia/app_aluno/itens.py` (T-23) — fora
   de escopo aqui. O `Protocol` declara o contrato que essa persistência
   futura implementa; a implementação em memória deste módulo só existe para
   permitir testar o mecanismo e para uso em contexto sem banco (mesmo
   precedente de `Respostas`/`Protocol` em `collection/condicoes.py`,
   `collection/interpolacao.py` e `collection/validacao.py`).

MECANISMO DE ESTABILIDADE E NÃO-REAPROVEITAMENTO (decisão desta tarefa,
plano não especifica o mecanismo exato): sequência crescente por
`(CASO_ID, escopo)`, nunca reiniciada e nunca reciclada — cada chamada a
`proximo_identificador` avança um contador que só cresce, mesmo quando um
item anterior é removido. Um identificador de item é sempre
`f"{prefixo_do_escopo}{numero:03d}"` (ex.: `D001`, `D002`, `M001`),
formando o `[Dxxx]` referenciado por `collection/interpolacao.py::Marcador`
em `B11.Q01`. UUID foi descartado: o plano usa literalmente `[Dxxx]`/`Dxxx`
como formato de exemplo (§4.1, comentário de `Marcador`) e uma sequência
curta e legível é o que um revisor humano (Entrega 1, `sdd.config.md` §6)
consegue ler em uma tela de revisão sem truncar.

REGRAS: `RF-04`, `AC-04`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol

from collection.registro import EscopoRepeticao, RegistroPergunta

REGRAS: Final[tuple[str, ...]] = ("RF-04", "AC-04")

# Prefixo do identificador de item por escopo — só existe para os escopos que
# de fato nomeiam um item (NENHUM nunca gera item, então não tem prefixo).
# Público (sem `_`): `persistencia/app_aluno/itens.py` (T-23) reaproveita o
# MESMO mapeamento para a implementação real de `GeradorDeIdentificadorDeItem`
# sobre o banco — uma só fonte de verdade do prefixo por escopo, nunca uma
# cópia paralela que poderia divergir dela.
PREFIXO_POR_ESCOPO: Final[dict[EscopoRepeticao, str]] = {
    EscopoRepeticao.DIVIDA_ID: "D",
    EscopoRepeticao.VINCULO_ID: "V",
    EscopoRepeticao.MARGEM_ID: "M",
    EscopoRepeticao.ITEM_DESPESA: "DESP",
    EscopoRepeticao.ACAO_ID: "A",
    EscopoRepeticao.RENDA_ADICIONAL_ID: "REND",
    EscopoRepeticao.DESPESA_NAO_MENSAL_ID: "NM",
}


def perguntas_da_ficha(
    registros: tuple[RegistroPergunta, ...], escopo: EscopoRepeticao
) -> tuple[RegistroPergunta, ...]:
    """RF-04 — as perguntas de uma ficha repetível são exatamente as de
    `registros` cujo `escopo_repeticao` é `escopo`. Filtro derivado do
    próprio campo do registro, sem nenhuma lista de bloco ou de `ID`
    codificada à mão neste módulo — uma pergunta muda de escopo editando o
    YAML (`collection/registros/`), nunca este código."""
    return tuple(registro for registro in registros if registro.escopo_repeticao == escopo)


def erro_escopo_sem_item(escopo: EscopoRepeticao) -> ValueError:
    # Público pelo mesmo motivo de `PREFIXO_POR_ESCOPO` acima — reaproveitado
    # por `persistencia/app_aluno/itens.py` (T-23).
    # Mensagem TÉCNICA curta (nunca exibida ao aluno), dentro do limiar de
    # `AC-37`/`T-08`.
    return ValueError(f"escopo sem prefixo de item: {escopo!r}")


class GeradorDeIdentificadorDeItem(Protocol):
    """O contrato que a persistência futura de `itens_repetidos` (T-21+,
    `persistencia/app_aluno/itens.py`, T-23) implementa sobre uma sequência
    real em banco. Este módulo consome o contrato — nunca decide como ele é
    armazenado; a fronteira entre "gerar/validar identificador de item"
    (esta tarefa) e "persistir o item" (tarefas futuras) é exatamente esta
    interface.

    Estabilidade/não-reaproveitamento (`AC-04`, critério 1 e 4): para um
    mesmo `(CASO_ID, escopo)`, `proximo_identificador` nunca devolve um
    identificador já devolvido antes para aquele par — nem mesmo depois de o
    item correspondente ter sido removido."""

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        """Devolve um novo identificador de item, estável e nunca
        reaproveitado, para o par `(CASO_ID, escopo)`."""
        ...


@dataclass
class GeradorDeIdentificadorEmMemoria:
    """Implementação de referência de `GeradorDeIdentificadorDeItem`, sem
    banco: um contador monotônico por `(CASO_ID, escopo)`, que só cresce.

    Não reciclar índice de item removido é a regra central (critério de
    aceite 4): este gerador nunca decrementa nem reutiliza o contador —
    "remover um item" é assunto de quem persiste (T-23), e mesmo removido,
    o próximo identificador gerado para aquele escopo continua a sequência,
    nunca volta a um número já usado. É a mesma garantia que a persistência
    real precisará dar com uma coluna de sequência monotônica (ex.:
    `GENERATED ALWAYS AS IDENTITY`, nunca reaproveitada mesmo após
    `DELETE`) — este dataclass existe para provar o mecanismo antes de a
    tabela existir, e para uso em teste e em contexto sem `DATABASE_URL`
    (mesmo precedente de `persistencia/arquivo/` no slug do motor)."""

    _contadores: dict[tuple[str, EscopoRepeticao], int] = field(default_factory=dict)

    def proximo_identificador(self, CASO_ID: str, escopo: EscopoRepeticao) -> str:
        prefixo = PREFIXO_POR_ESCOPO.get(escopo)
        if prefixo is None:
            raise erro_escopo_sem_item(escopo)

        chave = (CASO_ID, escopo)
        proximo_numero = self._contadores.get(chave, 0) + 1
        self._contadores[chave] = proximo_numero
        return f"{prefixo}{proximo_numero:03d}"
