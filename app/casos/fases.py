"""As cinco fases do aluno — `RF-61`, `AC-89`, `EC-25` (T-146).

O protótipo validado `PIQ Meu Plano` decide o que a tela Início mostra a
partir de uma **fase**, não do estado bruto do caso: `renderInicio` tem cinco
ramos (`coleta`, `revisao`, `reprovado`, `plano`, `acompanhamento`), enquanto
`app/casos/maquina.py::ESTADO_CASO` tem doze membros. Este módulo é o mapa
entre os dois, e nada além disso.

**Por que uma fase, e não o estado direto.** O estado é a verdade da máquina —
`CALCULANDO` e `AGUARDANDO_REVISAO` são transições distintas, com guardas
distintas, e a máquina precisa dessa distinção. A fase é a verdade do **aluno**:
nos dois casos a resposta à pergunta "o que eu faço agora?" é a mesma, *é com a
gente, você não faz nada*. Colapsar os doze em cinco é o que permite a tela
Início oferecer **uma** próxima etapa (`RF-58`) em vez de expor a máquina de
estados a quem não precisa dela.

**Módulo puro.** Sem I/O, sem FastAPI, sem `engine/`, sem `persistencia/` —
mesma disciplina de `app/casos/progresso.py` e de
`app/http/mensagens_de_estado.py`. A única dependência é o próprio enum de
estados.

## A trava do `match` exaustivo

`fase_do_estado` não tem `case _`. Isso é deliberado e é o mecanismo central
de `AC-89`: um membro novo em `ESTADO_CASO` sem fase declarada **não compila**
sob `mypy --strict`, em vez de cair num default silencioso que mandaria o aluno
para a tela errada. É o mesmo padrão já provado em `mensagens_de_estado.py`.

## Nenhuma fase nova — as duas tentações recusadas

`ENCERRADO` **não** vira uma sexta fase. Ele é `ACOMPANHAMENTO` com a lista de
ações vazia. Uma fase existe para responder *o que o aluno faz agora*; o
encerramento não muda essa resposta, muda o conteúdo do cartão — e
`mensagem_do_estado_do_caso` já produz *"Seu caso foi encerrado."*.

`ERRO_DE_CALCULO` **não** vira uma tela de erro. Ele é `REVISAO`, e o aluno lê
*"Seu plano está em nova análise."* — o texto que `mensagens_de_estado.py` já
produz para esse estado. Expor erro técnico a um aluno endividado e inseguro é
escopo extra e é dano: ele não pode agir sobre a falha, e saber dela só
acrescenta medo. A falha é observável pelo operador, que é quem pode agir.

## `PLANO_LIBERADO` — a única exceção

É o único estado cuja fase **não** é função apenas do estado: depende também do
snapshot. Ver `fase_do_plano_liberado`, abaixo.

REGRAS: `RF-58`, `RF-61`, `AC-81`, `AC-89`, `EC-25`
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from app.casos.maquina import ESTADO_CASO

REGRAS: Final[tuple[str, ...]] = ("RF-58", "RF-61", "AC-81", "AC-89", "EC-25")


class FASE_INICIO(Enum):
    """As cinco fases de `renderInicio` no protótipo validado.

    Os valores são os do protótipo, caractere por caractere — eles atravessam
    a fronteira HTTP no campo `fase` de `GET /caso/{CASO_ID}/inicio` e o
    cliente os consome como união de literais."""

    COLETA = "coleta"
    REVISAO = "revisao"
    REPROVADO = "reprovado"
    PLANO = "plano"
    ACOMPANHAMENTO = "acompanhamento"


def fase_do_estado(estado: ESTADO_CASO) -> FASE_INICIO:
    """`RF-61` — a fase do aluno para um `ESTADO_CASO`, por leitura pura.

    **`match` EXAUSTIVO, sem `case _`** — a trava de `AC-89`: membro novo sem
    fase declarada não passa no `mypy --strict`. Mesma disciplina de
    `app/http/mensagens_de_estado.py::mensagem_do_estado_do_caso`.

    `PLANO_LIBERADO` devolve `PLANO` aqui — a fase "otimista", a do caso que
    tem uma decisão a tomar. Quando não há ataque imediato recomendado, quem
    corrige para `ACOMPANHAMENTO` é `fase_do_plano_liberado`, abaixo, que é o
    único ponto do sistema autorizado a olhar o snapshot para decidir fase."""
    match estado:
        # --- coleta: o aluno tem perguntas a responder ---
        case ESTADO_CASO.CADASTRADO:
            # Ainda não consentiu. A próxima etapa é o consentimento, que do
            # ponto de vista do aluno é o começo da coleta — não uma fase
            # própria: ele não distingue "registrar consentimento" de
            # "começar a responder", e nem precisa.
            return FASE_INICIO.COLETA
        case ESTADO_CASO.CONSENTIMENTO_REGISTRADO:
            return FASE_INICIO.COLETA
        case ESTADO_CASO.COLETA_INICIAL:
            # O caso canônico do protótipo: "62 de 195".
            return FASE_INICIO.COLETA
        case ESTADO_CASO.COLETA_DIRIGIDA:
            # Blocos 7 e 8 são coleta — dirigida pelo motor, mas coleta: o
            # aluno responde perguntas. A diferença com `COLETA_INICIAL` é
            # o destino, não a fase.
            return FASE_INICIO.COLETA

        # --- revisão: é com a equipe, o aluno não faz nada ---
        case ESTADO_CASO.CALCULANDO:
            # O aluno vê "estamos montando o seu plano". A FASE é a mesma de
            # `AGUARDANDO_REVISAO` — *você não precisa fazer nada* —; o que
            # muda é só o destino (a tela do `.pulse`).
            return FASE_INICIO.REVISAO
        case ESTADO_CASO.ERRO_DE_CALCULO:
            # Ver a nota do cabeçalho: o erro técnico nunca chega ao aluno.
            # `mensagem_do_estado_do_caso` já diz "Seu plano está em nova
            # análise.", que é verdade e é acionável — para a equipe.
            return FASE_INICIO.REVISAO
        case ESTADO_CASO.AGUARDANDO_REVISAO:
            return FASE_INICIO.REVISAO

        # --- reprovado: a equipe pediu ajuste ---
        case ESTADO_CASO.REPROVADO_EM_REVISAO:
            return FASE_INICIO.REPROVADO

        # --- plano: há uma decisão do aluno a tomar ---
        case ESTADO_CASO.PLANO_LIBERADO:
            # A fase otimista. `fase_do_plano_liberado` corrige para
            # `ACOMPANHAMENTO` quando não há o que decidir.
            return FASE_INICIO.PLANO
        case ESTADO_CASO.CONFIRMACAO_ATAQUE:
            # É exatamente o "Decidir sobre os R$ X" do protótipo: o caso já
            # entrou no Bloco 10, então a decisão é o próximo passo.
            return FASE_INICIO.PLANO

        # --- acompanhamento: executar e reportar ---
        case ESTADO_CASO.ACOMPANHAMENTO:
            return FASE_INICIO.ACOMPANHAMENTO
        case ESTADO_CASO.ENCERRADO:
            # Ver a nota do cabeçalho: não é uma sexta fase. É acompanhamento
            # com ações vazias e a mensagem de encerramento.
            return FASE_INICIO.ACOMPANHAMENTO


def fase_do_plano_liberado(*, tem_ataque_a_decidir: bool) -> FASE_INICIO:
    """`RF-61` — a exceção declarada: `PLANO_LIBERADO` é o **único** estado
    cuja fase depende de algo além do estado.

    A fase `plano` do protótipo é literalmente *"Decidir sobre os
    R$ 3.000,00"* — ou seja, o Bloco 10. Sem ataque imediato recomendado não
    há decisão nenhuma a tomar, e oferecer "Decidir agora" a quem não tem o
    que decidir é pior que não oferecer nada: manda o aluno a uma tela que o
    servidor fecha com `409`. Nesse caso a próxima etapa é *"ver o que fazer
    agora"*, que é `ACOMPANHAMENTO`.

    **`tem_ataque_a_decidir` é lido, nunca calculado aqui.** O chamador o
    obtém de `app/casos/confirmacao_ataque.py::bloco_10_alcancavel`, a MESMA
    guarda que `app/http/rotas_etapas.py` já consulta antes de abrir o Bloco
    10 — nenhum limiar é reescrito neste módulo (`RF-34`, Lei nº 3). Receber
    o booleano pronto, em vez do snapshot, é o que mantém este módulo puro e
    fora do alcance de `engine/`."""
    return FASE_INICIO.PLANO if tem_ataque_a_decidir else FASE_INICIO.ACOMPANHAMENTO
