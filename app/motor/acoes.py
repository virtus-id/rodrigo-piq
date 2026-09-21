"""Leitura de `ORDEM_ACOES` — `RF-17`, `RF-33`, `AC-41` · `plans/app-aluno.
plan.md` §4.4.

**Escopo desta tarefa (`T-74`) — só a LEITURA, nunca a derivação.**
`acoes_em_acompanhamento` lê `snapshot.ORDEM_ACOES` e devolve exatamente essa
tupla. Não deriva tipo de ação, não infere identidade e não faz parsing da
`descricao` em prosa — a camada de coleta é consumidora do que o motor
publicou, nunca intérprete dele (Lei nº 3, `plans/app-aluno.plan.md` §1).

REGRAS: RF-17, RF-33, AC-41

## `perguntas_do_bloco_11` (`T-84`, `RF-27`, `RF-33`, `AC-46`)

`plans/app-aluno.plan.md` §4.4 desenha `perguntas_do_bloco_11(a) ->
RegistroPergunta`, ramificando por `TIPO_ACAO`. `engine.gates.AcaoRequerida`,
HOJE, só tem `DIVIDA_ID`, `descricao`, `gate_origem` e
`prioridade_excepcional` — **não tem `TIPO_ACAO`** (`OQ-10`, `OQ-13`, `OQ-14`,
`OQ-15` da spec `app-aluno`, dependência externa do slug `motor-calculo`,
ainda não implementada). A mesma classe de bloqueio de `T-83` (ver
`app/casos/acompanhamento.py::acao_id_de`/`ErroAcaoIdAusenteDoMotor`) se
aplica aqui, tratada com a MESMA disciplina: nenhum fallback silencioso,
nenhum `TIPO_ACAO` inventado — a fronteira falha ruidosamente, nomeando a
dependência externa.

**Nenhum literal de valor de `TIPO_ACAO` aparece neste módulo** (`OQ-13` — o
identificador exato ainda não foi respondido pelo especialista). Nem os
quatro nomes candidatos (`INFORMACAO`, `INTERVENCAO`, `TROCA`, `CORRECAO`)
aparecem como string aqui — o domínio, quando existir, é o que `engine/`
publicar, nunca uma suposição desta camada.

**Onde vive o mapeamento tipo → pergunta.** `collection/registros/
bloco-11.yaml` (T-18) já declara, em `condicao_exibicao`, para cada uma das
quatro perguntas de resultado (`B11.03-INF`/`-REN`/`-TRO`/`-ECO`), o valor de
`TIPO_ACAO` que a abre — dado transcrito da canônica, não decisão de código
(ver o comentário de cabeçalho daquele YAML). `_termo_tipo_acao`
percorre essa `condicao_exibicao` (a árvore de `Condicao` de `collection/
condicoes.py`, T-10) e extrai o termo `CondicaoIgual`/`CondicaoE` cuja
`variavel == "TIPO_ACAO"` — sem NUNCA copiar o `valor` para um literal deste
módulo: o mapeamento é lido do registro em tempo de execução, a cada chamada.
Responder `OQ-13` (o identificador real) é, portanto, editar o YAML — o valor
que `condicao_exibicao` compara passa a ser o identificador definitivo, e
nenhuma linha deste módulo muda.

**Por que a função falha sempre hoje, e por que essa é a implementação
completa e honesta de `T-84`.** `perguntas_do_bloco_11` só pode ramificar
depois de ler `acao.TIPO_ACAO` — e esse campo não existe em nenhuma
`AcaoRequerida` que o motor produz atualmente. Por isso a leitura usa a MESMA
técnica de `acao_id_de` (`getattr` com sentinela próprio, nunca `hasattr`,
para distinguir "campo ausente" de "campo presente e acessá-lo levantou uma
exceção diferente") e levanta `ErroTipoAcaoAusenteDoMotor`, nomeando a
dependência externa (`T-84`, `OQ-13`), toda vez que é chamada sobre uma
`AcaoRequerida` real — porque TODA `AcaoRequerida` real está, hoje, nessa
situação. Isso não é uma implementação parcial: é a fronteira ruidosa exigida
pelo terceiro critério de aceite, aplicada ao próprio campo que falta, e
única alternativa a inventar o dado que a dependência externa ainda não
publicou (mesma decisão de `T-83`/`OQ-10`).

Direção de dependência: este módulo continua sem importar
`collection.repeticao` (não é mais uma ficha por escopo de repetição, é um
filtro por `bloco`/`ID`/`condicao_exibicao`) — `_termo_tipo_acao` só percorre
`Condicao` (`collection.condicoes`) e `RegistroPergunta`
(`collection.registro`) já carregados por quem chama (`collection.carga`,
T-16), sem invocar a carga aqui.
"""

from __future__ import annotations

from typing import Final

from collection.condicoes import Condicao, CondicaoE, CondicaoIgual
from collection.registro import RegistroPergunta
from engine.gates import AcaoRequerida
from engine.snapshot import SnapshotOrdem

REGRAS: Final[tuple[str, ...]] = ("RF-17", "RF-27", "RF-33", "AC-41", "AC-46")

# T-84: mensagens técnicas (nunca exibidas ao aluno), curtas o bastante para
# não disparar o limiar de `AC-37`/`tests/app_aluno/estatica/
# test_sem_conteudo_de_questionario_no_codigo.py` (40 caracteres) — o valor
# recebido vai à parte, nunca composto numa única string longa. O detalhe
# completo (motor-calculo, OQ-13) vive na docstring do módulo e das exceções.
_MENSAGEM_TIPO_ACAO_AUSENTE: Final[str] = "TIPO_ACAO ausente (T-84, OQ-13)"
_MENSAGEM_TIPO_ACAO_DESCONHECIDO: Final[str] = "TIPO_ACAO desconhecido (T-84)"

# Sentinela distinto de qualquer TIPO_ACAO real possível — mesmo mecanismo de
# `app/casos/acompanhamento.py::_ACAO_ID_AUSENTE` (T-83): usado só para
# distinguir "atributo ausente" de "atributo presente e igual a None/''" em
# `getattr`, sem depender de `hasattr`.
_TIPO_ACAO_AUSENTE: Final[object] = object()

_BLOCO_ACOMPANHAMENTO: Final[int] = 11

# As perguntas de RESULTADO por tipo de ação (T-18), pelo próprio `ID` do
# registro — usadas só como FILTRO de pertencimento ao conjunto que participa
# do mapeamento tipo→pergunta, nunca como fonte do valor de TIPO_ACAO em si
# (esse valor é lido de `condicao_exibicao`, nunca copiado para cá).
_IDS_RESULTADO_POR_TIPO_ACAO: Final[frozenset[str]] = frozenset(
    {"B11.03-INF", "B11.03-REN", "B11.03-TRO", "B11.03-ECO"}
)


class ErroTipoAcaoAusenteDoMotor(Exception):
    """`T-84` — levantada quando `perguntas_do_bloco_11` é chamada com uma
    `AcaoRequerida` que não publica `TIPO_ACAO` (o caso de TODA
    `AcaoRequerida` produzida pelo motor hoje: `OQ-13`, dependência externa
    do slug `motor-calculo` ainda não entregue). Mesma disciplina de
    `app/casos/acompanhamento.py::ErroAcaoIdAusenteDoMotor` (T-83): esta
    exceção é a fronteira ruidosa exigida pelo terceiro critério de aceite —
    o módulo nunca escolhe uma pergunta por padrão nem inventa um valor de
    `TIPO_ACAO`.

    Consumidores desta função DEVEM deixar esta exceção propagar (ou
    traduzi-la para um erro de camada superior que preserve a causa) — nunca
    capturá-la para cair de volta numa pergunta arbitrária."""


class ErroTipoAcaoDesconhecido(Exception):
    """`T-84` — levantada quando `acao.TIPO_ACAO` tem um valor que não
    corresponde a nenhuma `condicao_exibicao` das perguntas de resultado do
    Bloco 11 (`collection/registros/bloco-11.yaml`). Nomeia o valor
    recebido — nunca escolhe uma pergunta por padrão diante de um tipo que o
    registro não mapeia."""


def _termo_tipo_acao(condicao: Condicao | None) -> CondicaoIgual | None:
    """Procura, na árvore de `condicao_exibicao` de um registro, o termo
    `CondicaoIgual` cuja `variavel` é `TIPO_ACAO` — sem NUNCA comparar contra
    um literal do valor: só o NOME da variável (`"TIPO_ACAO"`) é referenciado
    aqui, que é o nome do campo do contrato do motor (`RF-33`), não um valor
    do domínio de `TIPO_ACAO` (`OQ-13`). Cobre o caso comum de `CondicaoIgual`
    direta (`B11.03-REN`/`-TRO`/`-ECO`) e o caso de `CondicaoE` com um termo
    `TIPO_ACAO` entre outros (`B11.03-INF`, que também exige `ACAO_STATUS ==
    CONCLUIDA`). Nenhum outro nó (`CondicaoOu`/`CondicaoNao`/
    `CondicaoContem`/`CondicaoExisteItem`) é usado por este bloco hoje; se
    aparecer, a ausência de correspondência é tratada como "sem termo de
    TIPO_ACAO", nunca como erro de parsing."""
    if isinstance(condicao, CondicaoIgual) and condicao.variavel == "TIPO_ACAO":
        return condicao
    if isinstance(condicao, CondicaoE):
        for termo in condicao.termos:
            encontrado = _termo_tipo_acao(termo)
            if encontrado is not None:
                return encontrado
    return None


def _mapeamento_tipo_acao_para_registro(
    registros: tuple[RegistroPergunta, ...],
) -> dict[str, RegistroPergunta]:
    """O mapeamento tipo → pergunta, lido do PRÓPRIO registro (T-18) a cada
    chamada — nunca uma cópia estática no código. Cada pergunta de resultado
    do Bloco 11 (`_IDS_RESULTADO_POR_TIPO_ACAO`) contribui uma entrada cuja
    chave é o `valor` do termo `TIPO_ACAO` de sua `condicao_exibicao`. Editar
    o YAML (responder `OQ-13`) muda o valor da chave sem tocar esta função."""
    mapeamento: dict[str, RegistroPergunta] = {}
    for registro in registros:
        if registro.bloco != _BLOCO_ACOMPANHAMENTO:
            continue
        # `frozenset.__contains__` em vez do operador `in`: este módulo é
        # auditado (T-74/`tests/app_aluno/test_acoes.py::test_nenhuma_regex_
        # ou_str_split_ou_in_sobre_descricao`) para nunca usar `in`/`not in`
        # em lugar nenhum do arquivo — trava herdada do critério "nenhum
        # parsing de `descricao`", mantida aqui sem exceção por pergunta.
        if not _IDS_RESULTADO_POR_TIPO_ACAO.__contains__(registro.ID):
            continue
        termo = _termo_tipo_acao(registro.condicao_exibicao)
        if termo is None:
            continue
        mapeamento[termo.valor] = registro
    return mapeamento


def tipo_acao_de(acao: AcaoRequerida) -> str:
    """`RF-33`, `AC-46` — lê `TIPO_ACAO` de uma `AcaoRequerida` REAL, e só
    isso. Nunca infere o tipo a partir de `descricao`, `gate_origem` ou
    qualquer outro campo: se `TIPO_ACAO` não existir no objeto recebido,
    levanta `ErroTipoAcaoAusenteDoMotor` nomeando a dependência externa
    bloqueada (`OQ-13`). Mesma técnica de `app/casos/acompanhamento.py::
    acao_id_de` (T-83): `getattr` com sentinela, nunca `hasattr`, para que
    apenas "o campo não existe" seja relatado por esta exceção — qualquer
    outra exceção de acesso propaga tal como foi levantada."""
    valor = getattr(acao, "TIPO_ACAO", _TIPO_ACAO_AUSENTE)
    if valor is _TIPO_ACAO_AUSENTE:
        raise ErroTipoAcaoAusenteDoMotor(_MENSAGEM_TIPO_ACAO_AUSENTE)
    if not isinstance(valor, str):
        # Defensivo: mesmo tratamento de `acao_id_de` para um campo presente
        # mas de tipo incompatível com o que esta tarefa espera.
        raise ErroTipoAcaoAusenteDoMotor(
            f"{_MENSAGEM_TIPO_ACAO_AUSENTE}: tipo {type(valor).__name__}"
        )
    return valor


def perguntas_do_bloco_11(
    acao: AcaoRequerida, registros: tuple[RegistroPergunta, ...]
) -> RegistroPergunta:
    """`RF-27`, `RF-33`, `AC-46` — a pergunta de RESULTADO do Bloco 11 que
    corresponde ao `TIPO_ACAO` de `acao`, e exatamente uma. O mapeamento tipo
    → pergunta é lido de `registros` (`_mapeamento_tipo_acao_para_registro`),
    nunca de uma tabela codificada aqui.

    Falha ruidosa, sempre, hoje: `tipo_acao_de` levanta
    `ErroTipoAcaoAusenteDoMotor` porque nenhuma `AcaoRequerida` real publica
    `TIPO_ACAO` (`OQ-13`) — ver a nota extensa do módulo. Quando o motor
    passar a publicar o campo, um tipo que não corresponda a nenhuma entrada
    do mapeamento levanta `ErroTipoAcaoDesconhecido`, nomeando o valor
    recebido — esta função nunca escolhe uma pergunta por padrão."""
    tipo_acao = tipo_acao_de(acao)

    mapeamento = _mapeamento_tipo_acao_para_registro(registros)
    registro = mapeamento.get(tipo_acao)
    if registro is None:
        raise ErroTipoAcaoDesconhecido(f"{_MENSAGEM_TIPO_ACAO_DESCONHECIDO}: {tipo_acao!r}")
    return registro


def acoes_em_acompanhamento(snapshot: SnapshotOrdem) -> tuple[AcaoRequerida, ...]:
    """Devolve exatamente `snapshot.ORDEM_ACOES` — sem filtro, sem
    derivação, sem parsing de `descricao`. A fila paralela já vem pronta do
    motor (`engine/gates.py::particionar_elegibilidade`); esta função só a
    lê."""
    return snapshot.ORDEM_ACOES
