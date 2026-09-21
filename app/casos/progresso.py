"""Obrigatoriedade `OBR`/`COND`/`OPT`/`REP` no avanço da coleta — `RF-09`,
`RF-11`, `AC-11` (T-44) — e retomada na primeira pergunta não respondida —
`RF-10`, `AC-01` (T-45).

`plans/app-aluno.plan.md` §7.1 desenha a transição `COLETA_INICIAL →
CALCULANDO` (`app/casos/maquina.py::TABELA_TRANSICOES`, gatilho
`bloco_6_executa`) com a guarda textual "B5.FIM02 + campos OBR completos"
(T-33) — mas aquela guarda é só NOME/TEXTO, não código executável: `Transicao.
guarda` é um `str | None` descritivo, e `transicionar()` nunca o avalia. Esta
tarefa entrega a IMPLEMENTAÇÃO real da checagem.

**Decisão desta tarefa: o que "avanço" significa aqui.** Este módulo NÃO
dispara nem chama a máquina de estados — `app/casos/maquina.py` continua sendo
a única fonte de verdade sobre transição de estado, e nenhuma chamada a
`transicionar`/`ESTADO_CASO` aparece aqui (esse encadeamento, "quando todo
`OBR` está completo, disparar `bloco_6_executa`", é trabalho de uma tarefa de
orquestração futura, fora do escopo declarado desta tarefa: `app/casos/
progresso.py` e `app/http/rotas_coleta.py`). "Avanço" nesta implementação é o
SINALIZADOR que a função central abaixo (`pendencias_obrigatorias`) expõe:
dado o conjunto de registros carregados e as respostas já dadas de um caso,
quais perguntas obrigatórias ainda impedem a coleta de seguir adiante. A rota
de resposta (`app/http/rotas_coleta.py`, T-42) inclui esse sinalizador na
mesma resposta HTTP que já confirma a gravação (T-42), para que o cliente
HTMX (T-43) saiba se a coleta pode avançar sem que nenhuma regra de
obrigatoriedade seja duplicada em JS.

**Os quatro membros de `Obrigatoriedade` e como cada um afeta a pendência**
(nunca por lista de `ID` — sempre por `Obrigatoriedade.X in registro.
obrigatoriedade`, T-09):

  - `OBR` — obrigatório. Pendente enquanto não houver resposta gravada
    (`respostas.valor(...)` ou, para `REP`, `respostas.valor_no_item(...)`
    para cada item do escopo) E o registro não admitir "não sei"
    (`admite_nao_sei`) capaz de suprir o branco — ver a nota sobre
    `admite_nao_sei` abaixo. `AC-11` é exatamente este caso.
  - `COND` — só é exigível quando `condicao_exibicao` avalia como verdadeira
    sobre as respostas correntes (`collection.condicoes.avaliar`, T-11);
    condição falsa ou ausente de sentido (não aplicável) nunca gera
    pendência. Um registro `COND`+`OBR` (o caso comum: `COND` sozinho não
    seria obrigatório) só pendura quando as duas condições coincidem: a
    condição de exibição é verdadeira E não há resposta.
  - `OPT` — nunca gera pendência, em nenhuma circunstância. Um registro só
    `OPT` (sem `OBR` no mesmo `frozenset`) está sempre fora da varredura de
    pendência.
  - `REP` — replica a checagem por item: em vez de um único valor de caso,
    a pergunta tem um valor por item do `escopo_repeticao`. A lista de itens
    ATIVOS de cada escopo é um parâmetro de entrada (`itens_por_escopo`),
    nunca descoberta por este módulo — a fonte real vive em
    `persistencia/app_aluno/itens.py::RepositorioItens.listar_do_caso`
    (T-23), que é infraestrutura; este módulo permanece livre de I/O e
    testável só com os 245 registros reais (`collection/carga.py`, T-16)
    mais uma tupla de `item_id` fabricada em memória.

**Nota sobre `admite_nao_sei`.** Um campo `OBR` que ADMITE "não sei"
(`registro.admite_nao_sei = True`) e foi respondido com `NAO_SEI` NÃO está em
branco — está respondido, com uma resposta de primeira classe (`collection.
respostas.NAO_SEI`, `RF-11`). A pendência de `OBR` só existe quando NENHUMA
resposta foi gravada (nem um valor concreto, nem `NAO_SEI`) — o critério de
aceite fala especificamente do campo "sem `admite_nao_sei`" deixado em
branco, mas a regra geral (`respostas.valor(...) is None`) já cobre os dois
casos sem precisar checar `admite_nao_sei` na decisão de pendência: um campo
que ADMITE "não sei" e foi deixado em branco (nem "não sei" foi marcado)
também está pendente — a única coisa que muda é que ele TEM um caminho válido
a mais (`NAO_SEI`) para deixar de estar em branco. `admite_nao_sei` não entra
na condição de pendência; entra em `_resolver_valor` de `rotas_coleta.py`
(T-42, já concluída), que aceita `nao_sei` como valor gravável.

**Nenhum `ID` de pergunta aparece como "obrigatório" em código.** Toda
decisão deste módulo itera sobre `registros` (a coleção carregada de
`collection/carga.py`, T-16) e consulta `Obrigatoriedade` do próprio
registro — nunca uma lista de `ID`s ou de `VARIAVEL_GRAVADA` codificada à
mão. Auditado por `tests/app_aluno/estatica/test_sem_conteudo_de_
questionario_no_codigo.py` (T-08, `AC-37`).

Direção de dependência: este módulo usa só `dataclasses`/stdlib e
`collection.condicoes`/`collection.registro`/`collection.respostas` — nunca
`engine/` nem `persistencia/` (a fronteira de `tests/app_aluno/estatica/
test_fronteira_import_engine.py`, T-06, não é tocada por este módulo).

---

**T-45 — retomada na primeira pergunta não respondida (`RF-10`, `AC-01`).**

`proxima_pergunta_nao_respondida(registros, respostas, itens_por_escopo)`
devolve a primeira pergunta ABERTA (condição de exibição verdadeira ou
ausente — o mesmo critério de `_condicao_permite_exigencia` acima, mas
aplicado a TODO registro, não só aos `OBR`: a spec §7 do plano fala em
"retoma na primeira pergunta não respondida", sem restringir a
obrigatoriedade — um campo `OPT`/`COND` sem `OBR` que aparece antes de um
`OBR` na ordem do questionário também precisa ser oferecido primeiro, senão
a retomada pularia perguntas visíveis ao aluno) que ainda não tem NENHUMA
resposta gravada (nem valor concreto, nem `NAO_SEI` — mesmo critério de
"em branco" de `pendencias_obrigatorias`).

**Ordem da varredura**: `registros` é percorrido na ordem em que a coleção
chega (`collection/carga.py::carregar_registros`, que preserva a ordem dos
arquivos YAML por nome — `bloco-01.yaml` .. `bloco-11.yaml` — e a ordem de
aparição de cada pergunta dentro do arquivo, T-16/T-17..T-19); esta função
NÃO reordena por `RegistroPergunta.bloco` nem por `ID`: reordenar inventaria
uma ordem própria que poderia divergir da ordem real de exibição declarada
pelo registro (a mesma ordem que `T-43`/HTMX usa para andar de pergunta em
pergunta). Como os arquivos de registro nascem nomeados na ordem normativa
dos blocos (`bloco-01` < `bloco-02` < ... < `bloco-11`, T-17/T-18) e cada
arquivo lista suas perguntas na ordem da §11, a ordem de carga JÁ É a ordem
de blocos exigida por `AC-01` — sem duplicar esse conhecimento aqui.

**Pergunta `REP`**: a "primeira pergunta não respondida" de um registro
repetível é resolvida por item, na ordem de `itens_por_escopo` (a mesma
lista de itens ATIVOS fornecida pelo chamador, T-23/T-44) — o primeiro item
sem resposta para aquele registro interrompe a varredura; um registro `REP`
sem nenhum item cadastrado no escopo (`itens_por_escopo` ausente ou vazio
para aquele escopo) não pode gerar retomada — não há ficha para responder
ainda, então esta função passa para o próximo registro, sem inventar item.

**Pergunta cuja condição virou falsa depois de respondida (não reexibida
nem apagada)**: a resposta antiga permanece em `respostas` (nunca é
deletada nem sobrescrita por este módulo — o único gravador de
`app_aluno.respostas` é `persistencia/app_aluno/respostas.py`, T-22); esta
função simplesmente não a aponta como próxima, porque (a) ela JÁ tem uma
resposta gravada — não passa no critério de "em branco" — e (b), mesmo que
não tivesse, `_e_pergunta_aberta` abaixo a excluiria por a condição ser
falsa agora. As duas guardas juntas garantem que uma pergunta condicional
"desligada" depois de já respondida não vira alvo de retomada.

**Pureza sobre sessão HTTP**: esta função (como `pendencias_obrigatorias`)
opera só sobre `(registros, respostas, itens_por_escopo)` — nenhum
parâmetro de sessão, cookie ou requisição chega até aqui. É essa pureza que
faz "retomar de outro dispositivo, com sessão nova" ser trivialmente
verdadeiro: o mesmo `CASO_ID` sempre produz o mesmo `RespostasCaso` a partir
do banco (`persistencia/app_aluno/respostas.py::RepositorioRespostas.
listar_do_caso`, T-22), qualquer que seja a sessão HTTP que o carregou.

**Sem rota HTTP nesta tarefa (decisão de escopo).** O arquivo declarado por
`T-45` é só este módulo — diferente de `T-44`, que também tocava
`app/http/rotas_coleta.py`. `app/http/renderizacao.py` (T-43) já documenta
que "a rota GET decide QUAL pergunta mostrar" é trabalho de uma tarefa de
orquestração futura, consumindo esta função junto de `montar_contexto_
pergunta`; essa costura (rota GET "próxima pergunta"/"retomar", chamando
`proxima_pergunta_nao_respondida` e depois `montar_contexto_pergunta`)
permanece fora do escopo declarado de `T-45` e não é adicionada aqui, para
não introduzir uma rota nova por fora do que a tarefa pediu.

---

**`T-91` — a trilha de eventos de TODA transição da máquina (`RF-31`,
`AC-40`, `EC-14`).** Até esta tarefa, `app_aluno.eventos_caso` só registrava
um fato — a alteração cadastral (`registrar_alteracao_cadastral`, `T-87`),
que NUNCA transiciona o caso. As transições de estado propriamente ditas
(`app/http/rotas_consentimento.py`, `app/http/rotas_calculo.py`,
`app/revisao/fila.py`, `app/casos/acompanhamento.py`, `app/motor/
executor.py`) continuavam persistindo o novo `estado` sem deixar rastro na
trilha — o abandono ficava observável só por `Caso.ultima_interacao_em`,
nunca por "em que transição o caso passou e quando".

**Por que um wrapper único aqui, em vez de repetir o `INSERT` em cada
chamador.** Os nove pontos reais de chamada (`rotas_consentimento.py`;
`rotas_calculo.py`, duas vezes; `app/revisao/fila.py`, duas vezes;
`app/casos/acompanhamento.py`, duas vezes; `app/motor/executor.py`, quatro
vezes) já seguem o MESMO padrão de três passos: (1) validar o par contra
`app.casos.maquina.transicionar` (nunca uma transição "forçada" fora da
tabela); (2) persistir via `RepositorioCasos.transicionar_estado_se`
(condicional ao estado esperado, a mesma trava de concorrência de `T-56` —
nunca `transicionar_estado` incondicional, que reabriria a corrida dupla que
aquela tarefa fechou); (3), a partir de agora, gravar um `EventoCaso` na
trilha. Duplicar esses três passos em nove lugares arriscaria um chamador
futuro esquecer o terceiro passo (evento sem transição gravada, ou
vice-versa) — exatamente o tipo de dessincronia que `RF-31`/`AC-40` existem
para eliminar. `transicionar_e_registrar`, abaixo, é o ÚNICO lugar que faz os
três passos juntos; os cinco módulos chamadores foram ajustados nesta tarefa
para chamá-lo em vez de `RepositorioCasos.transicionar_estado_se` diretamente
(extensão de escopo documentada nas tarefas — mesmo precedente de `T-30`/
`T-87`, que também tocaram módulo além dos nominalmente listados quando
estritamente necessário para o critério de aceite).

**Só a transição CONDICIONAL (`transicionar_estado_se`) é envolvida.**
Nenhum chamador real desta feature usa `transicionar_estado` incondicional
para uma transição de domínio — os poucos usos de `transicionar_estado` que
sobram (ex.: fixtures de teste que preparam o `Caso` num estado inicial, fora
do fluxo de produção) não passam por uma `Transicao` da máquina e não fazem
sentido na trilha de eventos. Por isso `transicionar_e_registrar` só expõe a
variante condicional — a única que os cinco módulos de produção precisam.

**Evento só é gravado quando a transição de fato ocorreu.** Quando
`transicionar_estado_se` devolve `None` (a condição de estado esperado não
valia mais — outra transição concorrente já venceu a corrida), NENHUM evento
é gravado: não houve transição real, então não há fato a registrar na
trilha. `transicionar_e_registrar` devolve `None` no mesmo caso, preservando
a semântica que os chamadores já tratam (`ErroRecalculoRecusado`,
`ErroRevisaoJaDecidida`, `pendente.html` com status `409`, ...).

**Allowlist do `EventoCaso` gravado aqui — nenhum dado financeiro, saldo,
renda ou identificador pessoal.** `tipo_evento` é sempre o `gatilho` nomeado
pela própria `Transicao` da máquina (`app/casos/maquina.py::
TABELA_TRANSICOES`, ex.: `"bloco_6_executa"`, `"libera"`,
`"erro_no_calculo"`) — nunca um enunciado, nunca um valor de resposta.
`estado_de`/`estado_para` são os `.value` de `ESTADO_CASO` (os doze nomes do
plano §4.3). `detalhe` é opcional e, quando usado pelos chamadores desta
tarefa, carrega no máximo um `motivo_tecnico` curto (mesma disciplina de
`app/motor/executor.py::_registrar_evento`: nomes técnicos e IDs normativos,
nunca dado do aluno). `CASO_ID` é o único identificador — nunca `conta_id`,
nunca CPF/nome/e-mail.

**`EC-14` — retomável mesmo parado há meses.** A trilha (`listar_do_caso`)
nunca é consultada para decidir SE uma resposta pode ser gravada ou se um
caso pode retomar — essa decisão continua em `RespostasCaso`/`Resposta`
(`persistencia/app_aluno/respostas.py`) e na guarda de `app/casos/maquina.py`.
A trilha é só OBSERVAÇÃO: quanto tempo faz desde a última transição, e qual
foi. `Caso.ultima_interacao_em`, por sua vez, já é atualizada por toda
transição real (`RepositorioCasos.transicionar_estado*`, T-23) e agora
TAMBÉM por toda gravação de resposta (`persistencia/app_aluno/respostas.py::
RepositorioRespostasSupabase.gravar`/`RepositorioRespostasArquivo.gravar`,
ajustados nesta tarefa) — um caso parado há meses permanece com todas as
respostas gravadas e o carimbo exato de quando parou, sem que nada nesta
tarefa apague ou reescreva histórico.

---

**`T-92` — a consulta de trilha de progresso (`RF-31`, `AC-40`).** `T-91`
gravou o FATO de cada transição em `eventos_caso`; esta tarefa ACRESCENTA a
LEITURA agregada que devolve, por caso, tudo o que `AC-40` exige num só
lugar: o `estado` corrente, a `data` da última interação, ONDE o caso parou
na coleta e SE ele está esperando revisão humana. `consultar_trilha_de_
progresso`, abaixo, é essa função — puramente uma agregação de leitura,
sem gravar nada e sem tocar `eventos_caso` (a trilha de EVENTOS de `T-91` e a
trilha de PROGRESSO desta tarefa são consultas complementares, não a mesma
coisa: `T-91` responde "o que aconteceu e quando", esta função responde
"onde o caso está agora").

**"Onde parou" reusa `T-45`, não reinventa.** `RelatoDeProgresso.
proxima_pergunta` é literalmente o valor devolvido por `proxima_pergunta_
nao_respondida` (a mesma função acima, mesmo critério de "primeira pergunta
ABERTA e em branco", mesma ordem de blocos) — nenhuma segunda lógica de "por
onde o aluno anda" é escrita aqui. Isso garante que a trilha de progresso e a
retomada de fato mostrada ao aluno nunca divirjam: um caso "parado na
pergunta X" segundo esta consulta é EXATAMENTE onde `T-45` o faria retomar.

**`aguardando_revisao` é derivado de `Caso.estado`, nunca de uma segunda
fonte.** `estado is ESTADO_CASO.AGUARDANDO_REVISAO` — o mesmo `estado` que a
máquina (`T-33`) já valida a cada transição (`T-91`). Nenhuma tabela nova,
nenhuma heurística: o booleano é uma leitura direta do campo estrutural que
já existe.

**Nenhum dado financeiro do aluno na saída (`AC-40`).** `RelatoDeProgresso` é
um tipo PRÓPRIO, com só cinco campos estruturais (`CASO_ID`, `estado`,
`ultima_interacao_em`, `proxima_pergunta`, `aguardando_revisao`) — nenhum
campo de `Resposta`/`ValorResposta` (nenhum `Decimal`, nenhum valor de
formulário) nem de `EstadoFinanceiro`/`SnapshotOrdem` do motor entra na
composição. `proxima_pergunta` é um `PendenciaObrigatoria` (`ID` + `item_id`,
já auditado por `AC-37`/T-08 como isento de enunciado) — nunca o VALOR
respondido, só qual pergunta está em aberto.

**Por que este módulo não lê banco nem monta `RespostasCaso`/
`itens_por_escopo` sozinho.** Mesma disciplina de pureza de `T-44`/`T-45`
(nota acima, "Pureza sobre sessão HTTP"): `consultar_trilha_de_progresso`
recebe `caso`, `registros`, `respostas` e `itens_por_escopo` já montados
pelo chamador — a fonte real de cada um é infraestrutura
(`persistencia/app_aluno/casos.py::RepositorioCasos.buscar`,
`collection/carga.py::carregar_registros`, `persistencia/app_aluno/
respostas.py::RepositorioRespostas.listar_do_caso` mais `RespostasCaso`, e
`persistencia/app_aluno/itens.py::RepositorioItens.listar_do_caso`
agrupado por `escopo`) que este módulo continua livre de importar, para não
romper a fronteira de `tests/app_aluno/estatica/
test_fronteira_import_engine.py` (T-06) nem a de I/O que os testes desta
tarefa verificam só com os repositórios de arquivo (T-24), sem
`DATABASE_URL`.

**`OQ-07` — interface dedicada do operador NÃO é antecipada aqui.** A
trilha é entregue como DADO CONSULTÁVEL: uma função Python que devolve um
`RelatoDeProgresso`. Se essa consulta ganha um painel do operador (rota
HTTP, tela, autenticação de operador) é uma decisão em aberto — `OQ-07` da
spec §9 — que esta tarefa explicitamente NÃO decide. Nenhuma rota HTTP,
nenhum template e nenhum `app/http/` são tocados por `T-92`.

REGRAS: `RF-09`, `RF-10`, `RF-11`, `AC-01`, `AC-11`, `RF-31`, `AC-40`, `EC-14`
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol

from app.casos.maquina import ESTADO_CASO, transicionar
from collection.condicoes import avaliar
from collection.registro import EscopoRepeticao, Obrigatoriedade, RegistroPergunta
from collection.respostas import RespostasCaso
from persistencia.app_aluno.casos import Caso
from persistencia.app_aluno.eventos import EventoCaso, RepositorioEventosCaso

REGRAS: Final[tuple[str, ...]] = (
    "RF-09",
    "RF-10",
    "RF-11",
    "AC-01",
    "AC-11",
    "RF-31",
    "AC-40",
    "EC-14",
)


@dataclass(frozen=True, slots=True)
class PendenciaObrigatoria:
    """Uma pergunta obrigatória ainda em branco — `ID` é o `RegistroPergunta.
    ID` (nunca `VARIAVEL_GRAVADA`, para que o cliente HTMX, T-43, saiba
    exatamente qual campo do formulário reabrir); `item_id` é `None` para
    pergunta não repetível e o identificador do item (`D001`, ...) para
    pergunta `REP` pendente naquele item específico."""

    ID: str
    item_id: str | None


def _condicao_permite_exigencia(
    registro: RegistroPergunta, respostas: RespostasCaso
) -> bool:
    """`COND` só é exigível quando `condicao_exibicao` avalia como
    verdadeira sobre as respostas correntes (T-11). Registro sem
    `condicao_exibicao` (`None`) nunca teve a exibição condicionada — está
    sempre "exibível" do ponto de vista desta checagem, o que é irrelevante
    para um registro que não declara `COND` (`_e_exigivel_agora`, abaixo, só
    chama esta função quando `COND` está de fato presente)."""
    if registro.condicao_exibicao is None:
        return True
    return avaliar(registro.condicao_exibicao, respostas)


def _e_exigivel_agora(registro: RegistroPergunta, respostas: RespostasCaso) -> bool:
    """Um registro entra na varredura de pendência quando: (1) declara
    `OBR`, e (2) se também declarar `COND`, a condição de exibição vale
    agora. `OPT` puro nunca chega a este ponto: só `OBR` — sozinho ou
    coexistindo com `COND`/`REP` no mesmo `frozenset` (T-09 documenta um
    registro condicional e repetível ao mesmo tempo como caso real) — torna
    um registro exigível."""
    if Obrigatoriedade.OBR not in registro.obrigatoriedade:
        return False
    if Obrigatoriedade.COND in registro.obrigatoriedade:
        return _condicao_permite_exigencia(registro, respostas)
    return True


def _e_por_item_por_obrigatoriedade(registro: RegistroPergunta) -> bool:
    """O critério de "esta pergunta é por item" usado por `AC-11`: o membro
    `REP` em `obrigatoriedade`, que qualifica "obrigatório por item". Ver a
    nota comparativa em `_ocorrencias_abertas`."""
    return Obrigatoriedade.REP in registro.obrigatoriedade


def _e_por_item_por_escopo(registro: RegistroPergunta) -> bool:
    """O critério de "esta pergunta é por item" usado por `AC-01`: o
    `escopo_repeticao`, que qualifica "existe por item" — a mesma fonte de
    verdade de `collection/repeticao.py::perguntas_da_ficha`. Ver a nota
    comparativa em `_ocorrencias_abertas`."""
    return registro.escopo_repeticao != EscopoRepeticao.NENHUM


def _percorrer_ocorrencias(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    *,
    elegivel: Callable[[RegistroPergunta, RespostasCaso], bool],
    e_por_item: Callable[[RegistroPergunta], bool],
) -> Iterator[tuple[PendenciaObrigatoria, bool]]:
    """T-146 — a varredura ÚNICA sobre os registros, em ordem, rendendo TODA
    ocorrência elegível com um sinalizador de "está em branco".

    `pendencias_obrigatorias`, `proxima_pergunta_nao_respondida` e
    `contar_coleta` consomem esta função (as duas primeiras através de
    `_ocorrencias_abertas`, que filtra pelo sinalizador). Não existe uma
    segunda varredura em lugar nenhum, e é isso que impede a barra de
    progresso e a retomada de divergirem no dia em que uma condição mudar.

    **Por que render também o que NÃO está em branco.** `contar_coleta`
    precisa do denominador, e derivá-lo de um segundo percurso — ainda que
    com os mesmos predicados — reabriria a porta para as duas contagens
    discordarem. Rendendo tudo uma vez, `total` e `faltam` são dois
    acumuladores sobre o mesmo iterador, e `respondidas + faltam == total`
    (`AC-90`) é verdade por construção, não por coincidência.

    **Os dois predicados são parâmetros porque as varreduras divergem de
    propósito — não por descuido.** A tabela:

    | | pendência (`AC-11`) | retomada (`AC-01`) |
    | --- | --- | --- |
    | `elegivel` | `_e_exigivel_agora` (exige `OBR`) | `_e_pergunta_aberta` (qualquer registro) |
    | `e_por_item` | `_e_por_item_por_obrigatoriedade` | `_e_por_item_por_escopo` |

    O segundo eixo tem motivo registrado (era a docstring de
    `_pergunta_em_branco`, T-45): os registros reais têm perguntas repetíveis
    por item CONDICIONAIS **sem** o membro `REP` — todo o Bloco 7
    (`B7.05`..`B7.16`), o Bloco 8 e o Bloco 11 declaram `obrigatoriedade:
    [COND]` com `escopo_repeticao: DIVIDA_ID`/`ACAO_ID`. Ali `REP`
    qualificaria "obrigatório por item", não "existe por item". A retomada
    precisa oferecer TODA pergunta que o aluno de fato veria por item,
    inclusive as só `COND`; a varredura de pendência BLOQUEANTE, não — e essa
    distinção não afeta `AC-11`.

    Fixar qualquer um dos dois predicados aqui dentro quebraria `AC-11` ou
    `AC-01`. Por isso eles entram como parâmetro, e por isso este gerador não
    tem default para nenhum dos dois."""
    for registro in registros:
        if not elegivel(registro, respostas):
            continue

        if e_por_item(registro):
            for item_id in itens_por_escopo.get(registro.escopo_repeticao, ()):
                em_branco = respostas.valor_no_item(item_id, _variavel(registro)) is None
                yield PendenciaObrigatoria(ID=registro.ID, item_id=item_id), em_branco
            continue

        yield (
            PendenciaObrigatoria(ID=registro.ID, item_id=None),
            respostas.valor(_variavel(registro)) is None,
        )


def _ocorrencias_abertas(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]],
    *,
    elegivel: Callable[[RegistroPergunta, RespostasCaso], bool],
    e_por_item: Callable[[RegistroPergunta], bool],
) -> Iterator[PendenciaObrigatoria]:
    """As ocorrências de `_percorrer_ocorrencias` que estão EM BRANCO — o que
    `AC-11` (pendência) e `AC-01` (retomada) consomem.

    "Em branco" é `respostas.valor(...)` (ou `valor_no_item`) devolvendo
    `None`. `NAO_SEI` conta como resposta dada — `RF-11`: "não sei" é resposta
    de primeira classe, distinguível de "não respondido"."""
    for ocorrencia, em_branco in _percorrer_ocorrencias(
        registros,
        respostas,
        itens_por_escopo,
        elegivel=elegivel,
        e_por_item=e_por_item,
    ):
        if em_branco:
            yield ocorrencia


def pendencias_obrigatorias(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> tuple[PendenciaObrigatoria, ...]:
    """`AC-11` — para o conjunto de `registros` e as `respostas` já dadas,
    devolve toda pergunta `OBR` (exigível agora, considerando `COND`) que
    segue SEM NENHUMA resposta gravada — nem um valor concreto, nem `NAO_SEI`.
    Lista vazia significa "nada impede o avanço": a coleta pode seguir.

    `itens_por_escopo` é a lista de `item_id` ATIVOS por `EscopoRepeticao`,
    fornecida pelo chamador (a fonte real é `persistencia/app_aluno/
    itens.py::RepositorioItens.listar_do_caso`, T-23, infraestrutura que este
    módulo não importa) — necessária para varrer pendência de campo `REP`
    por item. Ausente ou `None`, nenhum registro `REP` é varrido (mesma
    convenção seguida por `dict.get`, sem inventar item)."""
    return tuple(
        _ocorrencias_abertas(
            registros,
            respostas,
            itens_por_escopo or {},
            elegivel=_e_exigivel_agora,
            e_por_item=_e_por_item_por_obrigatoriedade,
        )
    )


def _variavel(registro: RegistroPergunta) -> str:
    """`VARIAVEL_GRAVADA` é a chave por que `RespostasCaso` indexa (mesma
    convenção de `app/http/rotas_coleta.py`, T-42) — defensivo: nenhum
    registro real declara `VARIAVEL_GRAVADA=None` (T-17..T-19), mas a
    checagem evita indexar por `None` caso um registro fabricado em teste o
    faça."""
    if registro.VARIAVEL_GRAVADA is None:
        raise ErroRegistroSemVariavelGravada(registro.ID)
    return registro.VARIAVEL_GRAVADA


class ErroRegistroSemVariavelGravada(Exception):
    """Espelha `app/http/rotas_coleta.py::ErroRegistroSemVariavelGravada`
    (T-42) — mesma disciplina defensiva, módulo próprio para não criar
    dependência de `app/http/` a partir de `app/casos/` (direção de
    dependência: `app/casos/` não importa de `app/http/`)."""


def coleta_pode_avancar(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> bool:
    """Sinalizador de avanço — `True` quando `pendencias_obrigatorias` devolve
    vazio. É este booleano que `app/http/rotas_coleta.py` inclui na resposta
    HTTP de confirmação (T-42/T-44): a coleta "avança" no sentido desta
    tarefa quando nenhum `OBR` exigível agora está em branco. Disparar a
    transição de estado propriamente dita (`app/casos/maquina.py::
    transicionar`, gatilho `bloco_6_executa`) permanece fora do escopo
    declarado aqui."""
    return not pendencias_obrigatorias(registros, respostas, itens_por_escopo)


def _e_pergunta_aberta(registro: RegistroPergunta, respostas: RespostasCaso) -> bool:
    """T-45 — uma pergunta está ABERTA quando sua `condicao_exibicao` avalia
    como verdadeira sobre as respostas correntes (T-11), ou quando ela não
    declara condição alguma (`None`, sempre aberta). Mesmo critério de
    `_condicao_permite_exigencia`, mas aplicado a QUALQUER registro — nunca
    só aos `OBR` — porque a retomada precisa considerar toda pergunta que o
    aluno de fato veria no fluxo, `OPT`/`COND` puro inclusive."""
    return _condicao_permite_exigencia(registro, respostas)


def proxima_pergunta_nao_respondida(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> PendenciaObrigatoria | None:
    """`RF-10`, `AC-01` — dado o conjunto de `registros` (na ORDEM em que a
    coleção chega, T-16: bloco a bloco, na ordem de cada YAML) e as
    `respostas` já gravadas do caso, devolve a primeira pergunta ABERTA
    (`_e_pergunta_aberta`) que ainda está em branco (`_pergunta_em_branco`).
    `None` significa "nada pendente": todas as perguntas abertas já têm
    resposta — a coleta está completa até onde o grafo condicional permite
    enxergar hoje.

    Independe de `Obrigatoriedade`: `OPT`/`COND` puro entram na varredura
    igual a `OBR`, porque a retomada é sobre "o que o aluno ainda não
    respondeu e veria a seguir no fluxo", não sobre o que bloqueia o avanço
    (esse é o papel de `pendencias_obrigatorias`/`coleta_pode_avancar`,
    acima, com um critério mais estreito e propósito diferente).

    Uma pergunta cuja condição VIROU falsa depois de ter sido respondida
    nunca é devolvida aqui: `_pergunta_em_branco` já a exclui por ela ter
    uma resposta gravada, e `_e_pergunta_aberta` a excluiria de qualquer
    forma por a condição não valer mais — a resposta antiga permanece
    intacta em `respostas` (este módulo nunca apaga nem sobrescreve nada).

    `itens_por_escopo` segue a mesma convenção de `pendencias_obrigatorias`:
    ausente ou com o escopo sem entrada, nenhum item é varrido para um
    registro `REP` (nunca se inventa item; a fonte real é `persistencia/
    app_aluno/itens.py::RepositorioItens.listar_do_caso`, T-23)."""
    return next(
        _ocorrencias_abertas(
            registros,
            respostas,
            itens_por_escopo or {},
            elegivel=_e_pergunta_aberta,
            e_por_item=_e_por_item_por_escopo,
        ),
        None,
    )


@dataclass(frozen=True, slots=True)
class PosicaoNaFicha:
    """`RF-63`, `AC-92` — onde a pergunta está dentro da ficha corrente.

    É o que sustenta o localizador *"Dívida 3 · pergunta 4 de 12"* do
    protótipo. `posicao` é 1-indexada, como o aluno conta."""

    posicao: int
    total_na_ficha: int


def posicao_na_ficha(
    registro: RegistroPergunta,
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
) -> PosicaoNaFicha | None:
    """`RF-63`, `AC-92` — a posição de `registro` entre as perguntas ABERTAS
    da sua ficha, ou `None` quando ele não pertence a ficha nenhuma.

    **O denominador são as perguntas abertas agora**, não todas as do escopo
    — mesma disciplina de `contar_coleta` e pelo mesmo motivo: dizer "pergunta
    4 de 12" quando três daquelas doze nunca vão abrir para este aluno é uma
    promessa que a coleta não cumpre. O total encolhe e cresce conforme as
    condicionais mudam, e isso é honesto.

    `None` para `escopo_repeticao == NENHUM` é o caso honesto, não uma falha:
    não existe "pergunta 4 de 12" numa pergunta que não é de ficha. O cliente
    cai no rótulo do bloco (`serializacao.py`).

    **A ficha é por escopo E por BLOCO.** Filtrar só por `escopo_repeticao`
    parece natural e está errado: `DIVIDA_ID` tem 88 registros espalhados por
    três blocos — 55 no Bloco 5 (o inventário de dívidas), 13 no Bloco 7
    (renegociação) e 20 no Bloco 8 (troca). Os Blocos 7 e 8 são **coleta
    dirigida pelo motor, etapa pós-plano**: o aluno só os vê para as dívidas
    que o motor sinalizou, meses depois de terminar o inventário.

    Somar as três no mesmo denominador diria "pergunta 4 de 37" a quem está
    cadastrando a primeira dívida, contando contra ele perguntas que talvez
    nunca abram — e que, se abrirem, serão outra etapa da vida dele. A ficha
    que o aluno percebe é a do bloco em que está.

    Usa `_e_pergunta_aberta` — os predicados da RETOMADA, não os da pendência:
    o localizador conta o que o aluno percorre, igual à barra de progresso."""
    if registro.escopo_repeticao == EscopoRepeticao.NENHUM:
        return None

    abertas = [
        candidato
        for candidato in registros
        if candidato.escopo_repeticao == registro.escopo_repeticao
        and candidato.bloco == registro.bloco
        and _e_pergunta_aberta(candidato, respostas)
    ]

    try:
        indice = abertas.index(registro)
    except ValueError:
        # A própria pergunta está fechada agora (condição falsa). Acontece
        # quando o cliente pede uma pergunta por `ID` cuja condicional virou
        # falsa: não há posição honesta a informar, e inventar uma seria pior
        # que omitir.
        return None

    return PosicaoNaFicha(posicao=indice + 1, total_na_ficha=len(abertas))


@dataclass(frozen=True, slots=True)
class ContagemDeColeta:
    """`RF-62`, `AC-90` — o que a barra de progresso da tela Início precisa.

    `respondidas + faltam == total` é invariante, e é testado: os três saem da
    MESMA varredura, então não há como divergirem.

    **`total` conta só as perguntas ABERTAS agora** — aquelas cuja
    `condicao_exibicao` é verdadeira sobre as respostas correntes. O
    denominador varia conforme o aluno responde, e isso é deliberado: exibir
    um total que inclui perguntas que nunca abrirão mentiria sobre o tamanho
    do trabalho restante. O aluno que vê "62 de 195" e descobre no fim que
    eram 110 perde a confiança na barra — e na coleta."""

    respondidas: int
    faltam: int
    total: int


def contar_coleta(
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> ContagemDeColeta:
    """`RF-62`, `AC-90` — o `62 de 195` do protótipo.

    `pendencias_obrigatorias` devolve o que FALTA; a barra precisa também do
    que já foi respondido e do total. Os três números saem da mesma varredura
    de `_ocorrencias_abertas`, com os predicados da **retomada**
    (`_e_pergunta_aberta` + `_e_por_item_por_escopo`) — e não os da pendência.

    **Por que os predicados da retomada.** A barra conta o que o aluno VÊ, não
    o que bloqueia o avanço. Usar os da pendência produziria um denominador
    que ignora toda pergunta `OPT`/`COND` pura — o aluno responderia perguntas
    que a barra não conta, e ela andaria para trás quando uma condição abrisse
    um bloco novo. É a mesma varredura de `proxima_pergunta_nao_respondida`,
    o que garante que "continuar de onde parei" aponte sempre para dentro do
    que a barra está medindo."""
    total = 0
    faltam = 0

    for _, em_branco in _percorrer_ocorrencias(
        registros,
        respostas,
        itens_por_escopo or {},
        elegivel=_e_pergunta_aberta,
        e_por_item=_e_por_item_por_escopo,
    ):
        total += 1
        if em_branco:
            faltam += 1

    return ContagemDeColeta(respondidas=total - faltam, faltam=faltam, total=total)


# ---------------------------------------------------------------------------
# `T-91` — `transicionar_e_registrar`: o único caminho que transiciona o
# `Caso` E grava o evento correspondente na trilha (`RF-31`, `AC-40`, `EC-14`).
# Ver a nota extensa do módulo, seção "T-91", para o raciocínio completo.
# ---------------------------------------------------------------------------


class RepositorioCasosDaTransicao(Protocol):
    """Recorte mínimo de `persistencia.app_aluno.casos.RepositorioCasos`
    exigido por `transicionar_e_registrar` — só `transicionar_estado_se`.
    Mesma disciplina de `app/revisao/fila.py::RepositorioCasosDaDecisao`/
    `RepositorioCasosDaFila`: a orquestração depende só do verbo que usa,
    nunca da interface inteira. Qualquer repositório concreto que já
    implementa `RepositorioCasos` (`RepositorioCasosSupabase`,
    `RepositorioCasosArquivo`) satisfaz este `Protocol` estruturalmente, sem
    herança explícita — assim como os Protocols de `fila.py`."""

    def transicionar_estado_se(
        self,
        caso_id: str,
        estado_esperado: ESTADO_CASO,
        novo_estado: ESTADO_CASO,
        agora: datetime | None = None,
    ) -> Caso | None: ...


def transicionar_e_registrar(
    *,
    repositorio_casos: RepositorioCasosDaTransicao,
    repositorio_eventos: RepositorioEventosCaso,
    caso_id: str,
    de: ESTADO_CASO,
    para: ESTADO_CASO,
    agora: datetime | None = None,
    detalhe: str | None = None,
) -> Caso | None:
    """`RF-31`, `AC-40` — os três passos que toda transição de produção desta
    feature precisa: (1) validar `(de, para)` contra a MÁQUINA
    (`app.casos.maquina.transicionar`, que levanta `ErroTransicaoNaoDeclarada`
    para qualquer par não declarado — nenhuma transição "forçada" chega até
    o passo 2); (2) persistir CONDICIONALMENTE ao estado esperado
    (`RepositorioCasos.transicionar_estado_se`, a mesma trava de concorrência
    de `T-56`); (3), só quando a condição valia e a gravação de fato ocorreu,
    registrar um `EventoCaso` com `tipo_evento` igual ao `gatilho` nomeado
    pela própria `Transicao` da tabela.

    Devolve `None`, SEM gravar nenhum evento, quando `transicionar_estado_se`
    devolve `None` (o estado corrente já não era `de` — outra transição
    concorrente venceu a corrida): não houve transição real, então não há
    fato a registrar na trilha. Os chamadores continuam tratando esse `None`
    exatamente como tratavam antes desta tarefa (`ErroRecalculoRecusado`,
    `ErroRevisaoJaDecidida`, resposta HTTP `409`, ...).

    `detalhe` é o único campo de contexto livre do evento — nunca um valor
    monetário, saldo, renda ou identificador pessoal (mesma allowlist de
    `app/motor/executor.py::_registrar_evento`); os chamadores desta tarefa
    só o usam para um motivo técnico curto (ex.: `"ErroParametros: ..."`,
    já sem dado do aluno, propagado de `EC-04`/`EC-03`) ou o deixam `None`."""
    # `transicionar` devolve a própria `Transicao` declarada (com o
    # `gatilho` nomeado) — reaproveitada abaixo, em vez de uma segunda
    # consulta à tabela por fora da função de domínio.
    transicao = transicionar(de, para)

    caso_atualizado = repositorio_casos.transicionar_estado_se(caso_id, de, para, agora)
    if caso_atualizado is None:
        return None

    instante = agora if agora is not None else datetime.now(UTC)
    repositorio_eventos.registrar(
        EventoCaso(
            evento_id=f"EVENTO_{uuid.uuid4().hex}",
            CASO_ID=caso_id,
            tipo_evento=transicao.gatilho,
            estado_de=de.value,
            estado_para=para.value,
            detalhe=detalhe,
            ocorrido_em=instante,
        )
    )
    return caso_atualizado


# ---------------------------------------------------------------------------
# `T-92` — a consulta de trilha de progresso: por caso, estado atual, onde
# parou, se aguarda revisão e a data da última interação (`RF-31`, `AC-40`).
# Ver a nota extensa do módulo, seção "T-92", para o raciocínio completo.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RelatoDeProgresso:
    """`AC-40` — o retorno estrutural da trilha de progresso de um caso.
    Cinco campos, todos estruturais: nenhum valor de `Resposta`/
    `ValorResposta` (formulário do aluno) nem de `EstadoFinanceiro`/
    `SnapshotOrdem` (motor) aparece aqui — a consulta não expõe dado
    financeiro do aluno.

    `proxima_pergunta` é `None` quando não há nenhuma pergunta aberta em
    branco (mesmo significado de `proxima_pergunta_nao_respondida` devolver
    `None`: a coleta está completa até onde o grafo condicional permite
    enxergar hoje) — não confundir com "caso sem trilha"."""

    CASO_ID: str
    estado: ESTADO_CASO
    ultima_interacao_em: datetime
    proxima_pergunta: PendenciaObrigatoria | None
    aguardando_revisao: bool


def consultar_trilha_de_progresso(
    caso: Caso,
    registros: tuple[RegistroPergunta, ...],
    respostas: RespostasCaso,
    itens_por_escopo: Mapping[EscopoRepeticao, tuple[str, ...]] | None = None,
) -> RelatoDeProgresso:
    """`RF-31`, `AC-40` — agrega, para UM caso, tudo o que a trilha de
    progresso precisa reportar: `estado` corrente e `ultima_interacao_em`
    (lidos direto de `caso`, sem recalcular nada); a pergunta em que o caso
    parou (`proxima_pergunta_nao_respondida`, T-45 — mesmo mecanismo de
    retomada, reaproveitado aqui em vez de duplicado); e se o caso está
    `AGUARDANDO_REVISAO` (leitura direta de `caso.estado`).

    Não decide nada sobre a máquina de estados nem grava nada — puramente
    uma leitura agregada sobre dados já carregados pelo chamador (mesma
    pureza de `pendencias_obrigatorias`/`proxima_pergunta_nao_respondida`,
    acima): nenhum `Protocol` de repositório é parâmetro desta função, só os
    dados já resolvidos em memória.

    **Interface dedicada do operador — `OQ-07`, não antecipada aqui.** Esta
    função devolve DADO consultável; se um painel HTTP a expõe ao operador é
    decisão pendente de `OQ-07` (spec §9) e fica fora desta tarefa: nenhuma
    rota, nenhum template."""
    return RelatoDeProgresso(
        CASO_ID=caso.CASO_ID,
        estado=caso.estado,
        ultima_interacao_em=caso.ultima_interacao_em,
        proxima_pergunta=proxima_pergunta_nao_respondida(registros, respostas, itens_por_escopo),
        aguardando_revisao=caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO,
    )
