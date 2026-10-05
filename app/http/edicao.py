"""Em conferência, as respostas ficam só para leitura — `RF-114`, `RF-115`
(T-336).

**Por que existe.** A tela do revisor lê o snapshot do cálculo, congelado
(`rotas_api_plano.py::caso_para_revisao`). Uma resposta mudada depois dele
nunca chegava à conferência: o revisor liberava um plano calculado com dado
que já não era o do aluno. Aqui a divergência é impedida, não sincronizada.

**A regra vive no servidor.** Esconder o botão "Editar" não basta: um link
antigo, uma aba aberta ou uma chamada direta gravariam mesmo assim. A
função abaixo é chamada nas rotas de escrita e recusa com `409`.

**Quem é dono do caso é decidido antes.** A chamada vem DEPOIS de
`exigir_caso_da_sessao`: caso inexistente ou de outra conta já terminou em
`401`/`404` e nunca chega aqui. Mesmo assim, caso ausente passa adiante em
vez de virar `409` — nada aqui vaza a existência de um caso.

REGRAS: `RF-114`, `RF-115`, `AC-176`
"""

from __future__ import annotations

from typing import Final

from fastapi import HTTPException

from app.casos.maquina import ESTADO_CASO
from persistencia.app_aluno.casos import RepositorioCasos

#: Os estados em que o plano está sendo calculado ou conferido: nenhuma
#: resposta pode mudar por baixo dele.
ESTADOS_SOMENTE_LEITURA: Final[frozenset[ESTADO_CASO]] = frozenset(
    {ESTADO_CASO.CALCULANDO, ESTADO_CASO.AGUARDANDO_REVISAO}
)

# Montadas por `join` de pedaços curtos: nenhum literal isolado passa do
# limiar de "possível enunciado de pergunta" de `T-08`/`AC-37` — são mensagens
# de estado, não conteúdo do questionário.
MENSAGEM_EM_CONFERENCIA: Final[str] = " ".join(
    (
        "Seu plano está em conferência.",
        "Para mudar uma resposta,",
        "retire-o da conferência.",
    )
)

#: `AC-178`: o que o revisor lê quando o caso saiu da conferência antes da
#: decisão — porque o aluno o retirou para editar (`RF-115`) ou porque ele já
#: foi devolvido (`RF-113`). Os dois voltam ao aluno em `COLETA_INICIAL`.
MENSAGEM_FORA_DA_CONFERENCIA: Final[str] = " ".join(
    (
        "Este plano saiu da conferência:",
        "o aluno o retirou para editar",
        "ou ele foi devolvido.",
        "Ele volta à fila quando for reenviado.",
    )
)


def exigir_coleta_editavel(caso_id: str, repositorio: RepositorioCasos) -> None:
    """`409` quando o caso está em cálculo ou em conferência (`AC-176`).

    Chamada de dentro do handler, não declarada como dependência: a auditoria
    de isolamento (`T-32`) só admite `CASO_ID` como parâmetro de rota na
    dependência de `exigir_caso_da_sessao`, e aqui o `CASO_ID` já chega
    validado por ela."""
    caso = repositorio.buscar(caso_id)
    if caso is not None and caso.estado in ESTADOS_SOMENTE_LEITURA:
        raise HTTPException(status_code=409, detail=MENSAGEM_EM_CONFERENCIA)
