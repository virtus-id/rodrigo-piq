"""A mensagem do estado do caso — `AC-25` (T-145). Lida pela tela do plano
quando ainda não há plano liberado e pelo Início em todos os estados (T-300).

**Por que isto é um módulo, e não uma constante dentro da rota.** A mensagem
nasceu em `app/http/rotas_plano.py`, alimentando `plano/aguardando.html`.
Com a tela em React, quem a entrega é `GET /caso/{id}/api/plano`. Se cada
rota escrevesse a sua, o aluno leria coisas diferentes para o mesmo estado
dependendo de qual caminho o levou até ali — e ninguém perceberia, porque
as duas "funcionariam".

**O `match` é exaustivo de propósito.** Sem `case _`, `mypy --strict` recusa
compilar se um membro novo de `ESTADO_CASO` ficar sem mensagem. É a trava
que impede um estado novo de chegar ao aluno como tela vazia: o erro aparece
na verificação, não no piloto.

**Nenhuma mensagem cita valor.** São leituras de `Caso.estado` (Lei nº 3);
dizer "faltam R$ X" aqui seria calcular na camada de apresentação, e o
número exibido tem que vir de `SnapshotOrdem`.

REGRAS: `AC-25`, `RF-20`
"""

from __future__ import annotations

from typing import Final

from app.casos.maquina import ESTADO_CASO

REGRAS: Final[tuple[str, ...]] = ("AC-25", "RF-20")

_MENSAGEM_ESTADO_CADASTRADO: Final[str] = "Falta registrar seu consentimento."
_MENSAGEM_ESTADO_COLETA: Final[str] = "Sua coleta está em andamento."
# `T-293`: coleta completa, caso ainda em `COLETA_INICIAL` (o cálculo é a
# próxima etapa) — lida por `rotas_inicio.py`, que conhece a próxima etapa.
MENSAGEM_COLETA_COMPLETA: Final[str] = "Sua coleta está completa."
_MENSAGEM_ESTADO_CALCULANDO: Final[str] = "Seu plano está sendo calculado."
_MENSAGEM_ESTADO_ERRO_DE_CALCULO: Final[str] = "Seu plano está em nova análise."
_MENSAGEM_ESTADO_AGUARDANDO_REVISAO: Final[str] = "Seu plano está em revisão."
# `T-333` (RF-113): a conferência devolveu o plano — "em revisão" era falso.
# Redação da equipe técnica, a aprovar pelo produto. Lida também por
# `rotas_inicio.py` quando o caso já voltou à coleta com a correção pedida.
MENSAGEM_CORRECAO_PEDIDA: Final[str] = "Seu plano voltou para você conferir."
# `T-300`: textos aprovados pelo produto em 2026-10-01 — antes estes três
# estados diziam "coleta em andamento" ou "em revisão", que já não é verdade
# depois que a equipe libera o plano.
_MENSAGEM_ESTADO_PLANO_LIBERADO: Final[str] = "Seu plano está liberado."
_MENSAGEM_ESTADO_CONFIRMACAO_ATAQUE: Final[str] = "Falta confirmar sua decisão."
_MENSAGEM_ESTADO_ACOMPANHAMENTO: Final[str] = "Seu plano está em acompanhamento."
_MENSAGEM_ESTADO_ENCERRADO: Final[str] = "Seu caso foi encerrado."


def mensagem_do_estado_do_caso(estado: ESTADO_CASO) -> str:
    """A redação exibida quando o caso não tem snapshot liberado, por
    LEITURA pura de `Caso.estado` — nenhum cálculo, nenhuma inferência
    sobre o histórico do caso."""
    match estado:
        case ESTADO_CASO.CADASTRADO:
            return _MENSAGEM_ESTADO_CADASTRADO
        case ESTADO_CASO.CONSENTIMENTO_REGISTRADO | ESTADO_CASO.COLETA_INICIAL:
            return _MENSAGEM_ESTADO_COLETA
        case ESTADO_CASO.CALCULANDO:
            return _MENSAGEM_ESTADO_CALCULANDO
        case ESTADO_CASO.ERRO_DE_CALCULO:
            return _MENSAGEM_ESTADO_ERRO_DE_CALCULO
        case ESTADO_CASO.AGUARDANDO_REVISAO:
            return _MENSAGEM_ESTADO_AGUARDANDO_REVISAO
        case ESTADO_CASO.REPROVADO_EM_REVISAO:
            return MENSAGEM_CORRECAO_PEDIDA
        case ESTADO_CASO.PLANO_LIBERADO:
            # `T-300`: o Início também lê esta mensagem COM plano liberado —
            # "coleta em andamento" aqui era falso.
            return _MENSAGEM_ESTADO_PLANO_LIBERADO
        case ESTADO_CASO.COLETA_DIRIGIDA:
            # Nova rodada de coleta pós-liberação (Blocos 7/8).
            return _MENSAGEM_ESTADO_COLETA
        case ESTADO_CASO.CONFIRMACAO_ATAQUE:
            return _MENSAGEM_ESTADO_CONFIRMACAO_ATAQUE
        case ESTADO_CASO.ACOMPANHAMENTO:
            return _MENSAGEM_ESTADO_ACOMPANHAMENTO
        case ESTADO_CASO.ENCERRADO:
            return _MENSAGEM_ESTADO_ENCERRADO
