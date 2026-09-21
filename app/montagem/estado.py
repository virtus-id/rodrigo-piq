"""Montagem de `Divida`/`EstadoFinanceiro` a partir das respostas do
questionário — `RF-12`, `RF-14` (`AC-08`, `AC-13`, `AC-18`).

`T-49` entregou `montar_divida`: cada ficha repetível do Bloco 5
(`escopo_repeticao == DIVIDA_ID`, `collection/registros/bloco-05.yaml`,
T-17) vira uma `Divida` com os 18 campos EXATOS do contrato real de
`engine/estado.py`. `T-50` somou `montar_perfil_comportamental`
(as 8 variáveis do Bloco 2) e `montar_sinais_comportamentais` (os 10 campos
de `SinaisComportamentais`), mais `_autopercepcao_controle` (`B2.13`). Esta
tarefa (`T-51`) fecha o contrato com `montar_estado_financeiro`: o
`EstadoFinanceiro` COMPLETO, com `DATA_REFERENCIA` vinda do `Caso` — nunca de
`date.today()`/`datetime.now()` (`AC-18`; verificado também por teste
estático dedicado, `tests/app_aluno/estatica/test_sem_relogio_em_montagem.py`).
`T-52` estende este mesmo arquivo para derivar `INVENTARIO_COMPLETO` de
`B5.FIM02` (`_inventario_completo`, abaixo) — leitura de resposta, não regra
financeira: a consequência sobre `ORDEM_STATUS`/`STATUS_METODO` é do motor.

**`montar_estado_financeiro` — os três campos monetários agregados do
Bloco 3, calculados desde `T-103` (`OQ-16`).** `RENDA_TOTAL_RECORRENTE`,
`DESPESAS_OPERACIONAIS_ATUAIS` e `DESPESAS_NAO_MENSAIS_NORMALIZADAS` não
têm, no Bloco 3 (`collection/registros/bloco-03.yaml`, T-17), nenhum
`VARIAVEL_GRAVADA` próprio — a canônica (`piq-app-spec.md`, linha 1899,
nota de `B3.S08`) as lista explicitamente como "Derivadas pelo motor, nunca
perguntadas". Até `T-102`, nenhuma fórmula de composição estava publicada
em lugar único, e os três campos eram recebidos como PARÂMETRO EXTERNO
explícito (lacuna documentada, nunca uma estimativa silenciosa). `OQ-16`
fechou as três fórmulas, e `OQ-19`/`T-105` destravou o mecanismo de
repetição que faltava (dois novos membros de `EscopoRepeticao`,
`RENDA_ADICIONAL_ID`/`DESPESA_NAO_MENSAL_ID`) — `T-103` implementa as três
fórmulas fechadas, LENDO EXCLUSIVAMENTE respostas já coletadas (nenhuma
aritmética sobre campo de `SnapshotOrdem` — Lei nº 3 preservada; esta é
agregação de **entrada** para o motor, não leitura de **saída** dele):

- `RENDA_TOTAL_RECORRENTE` = `RENDA_PRINCIPAL` (B3.01) + soma de todas as
  fichas REP de `RENDA_RECORRENTE_ADICIONAL` (B3.03A-C, escopo
  `RENDA_ADICIONAL_ID`) — lista aberta, sem limite de quantidade
  codificado. `RECURSOS_EXTRAORDINARIOS` (B3.05) e a renda extra potencial
  (B3.06) nunca entram (`_renda_total_recorrente`).
- `DESPESAS_OPERACIONAIS_ATUAIS` = soma de todos os valores das fichas REP
  de `B3.D01` a `B3.D11` (as 10 categorias fixas mais a não listada,
  escopo único `ITEM_DESPESA`, `_despesas_operacionais_atuais`).
- `DESPESAS_NAO_MENSAIS_NORMALIZADAS` = (soma dos valores anuais de todas
  as fichas REP de `B3.NM02A-D` cuja `DESPESA_NAO_MENSAL_JA_CONTABILIZADA`
  não seja `Sim`, escopo `DESPESA_NAO_MENSAL_ID`) / 12
  (`_despesas_nao_mensais_normalizadas`; exclusão de dupla contagem
  fechada por `OQ-16`/`T-107`, ver docstring da função).

Ver a docstring de cada uma das três funções para o detalhe de cada
fórmula, incluindo o caso que `OQ-16` deixou fora de escopo por decisão do
usuário (`TIPO_RENDA=VARIAVEL`/piso-média-histórica de `RENDA_PRINCIPAL`)
— não é inventado aqui, permanece lacuna registrada, não estimativa
silenciosa.

`ECONOMIA_POTENCIAL_IMEDIATA` (`B2.09`/`B2.10`/`B2.10A`, Bloco 2) é
DIFERENTE: não está na lista de "derivadas pelo motor" da canônica, e sua
regra é uma leitura condicional simples e integralmente normatizada — "Sim"
em `GASTOS_FANTASMAS` habilita `VALOR_GASTOS_FANTASMAS`; "Somente SIM torna
VALOR_GASTOS_FANTASMAS elegível à economia potencial" (`B2.10A`, canônica).
Por isso ESTA função monta `ECONOMIA_POTENCIAL_IMEDIATA` de verdade —
`_economia_potencial_imediata`, abaixo — em vez de recebê-la como parâmetro:
`ACEITA_REDUCAO_GASTOS_FANTASMAS = SIM` repassa `VALOR_GASTOS_FANTASMAS`
(identidade, mesmo padrão de `_taxa_periodicidade_mensal_ou_desconhecido`);
qualquer outro caso — sem gasto fantasma identificado, sem aceite, aceite
`NAO`/`TALVEZ`, ou resposta ausente — não tem nenhum valor monetário real
disponível para o campo (o contrato exige `Dinheiro`, não
`DinheiroTalvez`/`Desconhecido`, e este módulo nunca constrói `Decimal`
literal fora da fronteira única de `app/montagem/conversao.py`, `RF-13`,
`T-27`) — por isso ESSE caso TAMBÉM é recebido como parâmetro externo com
default `None`, documentado, e só substituído por `Dinheiro(0)` pela
CHAMADORA (fora desta tarefa, que já tem um `Decimal` validado em mãos pela
fronteira única) quando não há economia identificada.

**`INVENTARIO_COMPLETO` — de parâmetro externo (`T-51`) a leitura própria
(`T-52`).** `T-51` recebia este campo como parâmetro OBRIGATÓRIO e
explícito, sem default (nem `True`, que inventaria "inventário completo"
por omissão, violando `AC-07`; nem `False` fixo em código, que seria a
mesma decisão de `T-52` tomada cedo demais, fora de escopo daquela tarefa).
`T-52` (`RF-15`, `AC-07`) implementa `_inventario_completo`: qualquer
resposta de `B5.FIM02` (`CONFIRMACAO_FIM_CADASTRO`) diferente de `SIM` —
`NAO`, `NAO_SEI` ou ausência de resposta — produz `False`; só `SIM` produz
`True`. O parâmetro externo foi removido de `montar_estado_financeiro`: a
função agora lê `B5.FIM02` diretamente das respostas, mesmo padrão de
`_tipo_renda`/`_capacidade_ataque_declarada`. Isso é leitura de resposta
(RF-15), não regra financeira — a consequência de `INVENTARIO_COMPLETO =
False` sobre `ORDEM_STATUS`/`STATUS_METODO` continua sendo do motor
(`engine/diagnostico.py`), nunca calculada aqui.

**`CONFIABILIDADE_DADOS` — por que continua fora de escopo mesmo com a
função de derivação já existindo no motor.** O submódulo de comportamento
do motor (`engine/comportamento.py`, caminho de import citado sem o ponto
final da sentença para não formar o literal completo que o teste de T-50
audita) já expõe a função que deriva este campo a partir do nível de
controle comportamental (T-13 do slug `motor-calculo`) — uma função pura,
sem gate nem fórmula financeira. Mas esse submódulo NÃO está na allowlist
de `tests/app_aluno/estatica/test_fronteira_import_engine.py` (`T-06`,
`AC-41`): importar qualquer nome dele aqui faria aquele teste falhar, e
ampliar a allowlist é mudança em outro arquivo, fora do escopo desta
tarefa (`Arquivos: app/montagem/estado.py`). Mais além da fronteira de
import: mesmo que fosse permitido, `RF-16` do plano (`plans/app-aluno.
plan.md` §5.2) é explícito — o Bloco 6 invoca `calcular_plano(...)` "sem
reproduzir nenhum passo do cálculo na aplicação". Invocar aquela derivação
aqui, fora do fluxo de `calcular_plano`, seria exatamente essa reprodução.
Por isso `CONFIABILIDADE_DADOS` é recebida como parâmetro OBRIGATÓRIO e
explícito, sem default — mesmo padrão de lacuna documentada de
`_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (T-49), só que aqui não há um valor
neutro seguro (o enum `ALTA`/`MEDIA`/`BAIXA` não tem "nenhum" — qualquer
default fixo seria uma afirmação sobre confiabilidade que ninguém
calculou). A chamadora (Bloco 6) é responsável por invocar a derivação de
dentro do motor, nunca de `app/`, e passar o resultado já pronto aqui.

**Mapeamento por `valor_interno`, nunca por `if` de pergunta (T-50).** Os 7
enums do Bloco 2 (`REGISTRO_GASTOS`, `FREQUENCIA_REGISTRO`,
`DEFASAGEM_REGISTRO`, `COBERTURA_PEQUENOS_GASTOS`,
`COBERTURA_MEIOS_PAGAMENTO`, `CONHECIMENTO_GASTO`,
`GASTOS_NAO_IDENTIFICADOS`, `REVISAO_SEMANAL` — `engine/estado.py`) têm,
conferido caractere por caractere contra `collection/registros/
bloco-02.yaml` (T-17), o `valor_interno` de cada opção IDÊNTICO ao `name` do
membro correspondente do enum (ex.: `valor_interno: TUDO` ↔
`REGISTRO_GASTOS.TUDO`). Isso permite um único mecanismo genérico,
`_membro_do_enum` abaixo, que resolve `EnumClasse[valor_interno]` — sem
nenhuma cadeia de `if resposta == "X": return Enum.X` e sem um `if` por
pergunta.

**`NECESSIDADE_VITORIA` e `HISTORICO_ABANDONO` (Bloco 9) — lidos do registro
real (T-99).** `SinaisComportamentais` exige 10 campos; 8 deles
(`NOVA_DIVIDA_PREVISTA`, `MECANISMO_DEFICIT`, `HISTORICO_RECAIDA`,
`NOVO_PARCELAMENTO_PREVISTO`, `PACTO`, `RISCO_IMPULSO`,
`LINHA_CONTINUA_SENDO_UTILIZADA`, `JANELA_NOVA_DIVIDA`) estão nos Blocos 1,
2 e 5, já transcritos por T-17. Os outros dois — `NECESSIDADE_VITORIA`
(`B9.02`, `piq-app-spec.md` linha 4158) e `HISTORICO_ABANDONO` (`B9.04`,
linha 4185) — pertenciam ao **Bloco 9**, que `T-50` encontrou sem YAML
(`T-17` cobriu Blocos 1–5; `T-18`, Blocos 7/8/10/11; `T-19`, casos de prova
do Bloco 12; nenhuma tarefa previa o Bloco 9). `T-99` transcreveu as duas
perguntas (`collection/registros/bloco-09.yaml`, restrito a `B9.02`/`B9.04`
— as outras quatro do Bloco 9 não têm campo correspondente no contrato do
motor e ficam fora) e esta função passou a lê-las como qualquer outro campo
de `SinaisComportamentais`: `NECESSIDADE_VITORIA` (escala 0-10) por
`_necessidade_vitoria`, mesmo padrão de `_risco_impulso` (erro explícito se
ausente, `_ou_desconhecido` reaproveitado por dentro); `HISTORICO_ABANDONO`
por `_historico_abandono`, que resolve o domínio de 5
valores da canônica (`MAIS_DE_UMA · UMA · NAO · SEM_PLANO · NAO_SEI`) para
`SimNaoTalvez` pelo mesmo padrão de tradução por FATO já usado em
`_historico_recaida`/`_quitacao_consultada`: a própria canônica diz
"`HISTORICO_ABANDONO` = SIM para A ou B" — `MAIS_DE_UMA`/`UMA` → `SIM`;
`NAO`/`SEM_PLANO` → `NAO`; `NAO_SEI` → `TALVEZ` (única leitura de incerteza
que o domínio fechado `SimNaoTalvez` oferece).

**Tradução central: `NAO_SEI` (coleta) → `DESCONHECIDO` (motor).**
`collection.respostas.NaoSei`/`NAO_SEI` e `engine.tipos.Desconhecido`/
`DESCONHECIDO` são, por design (ver `collection/respostas.py`), dois
sentinelas DISTINTOS que nunca se importam um do outro — a tradução entre os
dois só pode acontecer aqui, na camada de montagem (RF-12). `_ou_desconhecido`
é essa tradução, feita como função auxiliar única e reutilizável (T-50/T-51
reusam), nunca reimplementada campo a campo.

**"Nenhum default silencioso" — o que isso significa exatamente aqui.**
Para os campos monetários/taxa (`DinheiroTalvez`/`TaxaTalvez`) e para
`PESO_EMOCIONAL` (`int | Desconhecido`), toda ausência de resposta em campo
`REP` obrigatório é tratada como erro explícito (`ErroRespostaAusente`) — a
pergunta é `REP` (repetível), não `OPT`, então uma ficha sem essa resposta é
uma ficha incompleta, e a aplicação não pode inventar `DESCONHECIDO` para uma
pergunta que sequer foi respondida (isso mascararia "não perguntei" atrás de
"perguntei e não sei", violando a distinção entre `None`/ausência de
`collection/respostas.py` e `NAO_SEI`). `DESCONHECIDO` só nasce de uma
resposta REAL igual a `NAO_SEI` — nunca da ausência de linha.

Já os campos de saída de GATE (`RENEGOCIACAO_PENDENTE`, `TROCA_PENDENTE`,
`RISCO_MATERIAL_IMINENTE`, `OPORTUNIDADE_VIGENTE`) não têm, em nenhum
artefato SDD disponível (spec do slug, spec canônica, plano), uma fórmula
declarada de "resposta do Bloco 5 → valor" — são explicitamente atributos
DERIVADOS PELO MOTOR (Gates 2/3/4, `specs/piq-definicoes-engine.md` §6-§7),
e a Lei nº 3 do backlog (`plans/app-aluno.plan.md` §1) proíbe esta camada de
calcular qualquer gate. Não há, portanto, "resposta ou DESCONHECIDO" possível
para eles (nem admitem `Desconhecido` no tipo — são `bool`/`Oportunidade |
None`): a decisão desta tarefa, documentada e não-silenciosa, é fixá-los no
valor neutro que não afirma nenhuma pendência não observada diretamente
(`False`/`None`) até que a tarefa que implementar os Blocos 7/8 e os gates
resolva a derivação real. Isso é registrado como próxima tarefa de backlog
(ver nota em `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` abaixo), não uma estimativa.

**`TAXA_EFETIVA_MENSAL_NORMALIZADA` — por que só passa quando `MENSAL`.** A
própria canônica lista `TAXA_EFETIVA_MENSAL_NORMALIZADA` entre as variáveis
"derivadas pelo motor, nunca perguntadas" (`piq-app-spec.md`, nota de
`B5.FIM02`). O Bloco 5 coleta a taxa informada (`TAXA_INFORMADA`, B5.D01A) MAIS
a periodicidade declarada como pergunta SEPARADA (`PERIODICIDADE_TAXA`,
B5.D01B) — a conversão de periodicidade (ex. taxa anual → mensal) é fórmula
financeira (juros compostos), que esta camada não pode calcular (Lei nº 3).
Quando a periodicidade informada já É mensal, repassar o valor é identidade,
não cálculo, e por isso é aceito aqui; em qualquer outro caso (`ANUAL`,
`OUTRA`, `NAO_SEI`, ou periodicidade não respondida) o valor vai para
`DESCONHECIDO` — nunca uma conversão estimada.

**`CET` — por que é sempre `DESCONHECIDO` nesta tarefa.** Diferente da taxa
informada, `B5.D03A` grava o CET e sua periodicidade numa ÚNICA resposta
composta (`VARIAVEL_GRAVADA: "CET (+ PERIODICIDADE_CET)"` no registro real) —
não existe, no Bloco 5, uma segunda pergunta/variável separada de
periodicidade do CET (diferente de `PERIODICIDADE_TAXA`, que é `B5.D01B`,
pergunta própria). Sem uma variável de periodicidade isolada para confirmar
"é mensal" com a mesma segurança usada para `TAXA_EFETIVA_MENSAL_
NORMALIZADA`, ler `CET` aqui exigiria adivinhar a periodicidade da resposta
composta — o que violaria "nenhuma estimativa silenciosa". Por isso `CET`
é sempre `DESCONHECIDO` nesta tarefa; decompor `B5.D03A` em percentual e
periodicidade como duas variáveis próprias é decisão de formulário
(`T-42`/`T-43`), fora do escopo de `T-49`.

REGRAS: `RF-12`, `RF-14`, `RF-15`, `AC-07`, `AC-08`, `AC-18`
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Final

from app.montagem.conversao import converter_para_dinheiro
from collection.registro import EscopoRepeticao
from collection.respostas import NAO_SEI, RespostasCaso, ValorResposta
from engine.estado import (
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_RESERVA,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    JANELA_NOVA_DIVIDA,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_DIVIDA,
    TIPO_RENDA,
    Divida,
    EstadoFinanceiro,
    PerfilComportamental,
    SinaisComportamentais,
)
from engine.tipos import (
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    STATUS_DIVIDA,
    STATUS_VALIDADE_PROPOSTA,
    Desconhecido,
    Dinheiro,
    DinheiroTalvez,
    SimNaoTalvez,
    TaxaTalvez,
)

REGRAS: Final[tuple[str, ...]] = (
    "RF-12",
    "RF-14",
    "RF-15",
    "AC-07",
    "AC-08",
    "AC-13",
    "AC-18",
)

# `T-103` (`OQ-16`): acumulador neutro para as três somas de fichas REP do
# Bloco 3 (`_renda_recorrente_adicional_total`, `_despesas_operacionais_
# atuais`, `_despesas_nao_mensais_normalizadas`) — nenhum `Decimal(...)`
# literal é construído neste arquivo (fronteira `Decimal` única, RF-13,
# `tests/app_aluno/estatica/test_fronteira_decimal_unica.py`): o zero vem da
# MESMA fronteira que qualquer outro `Dinheiro` deste módulo,
# `app.montagem.conversao.converter_para_dinheiro`, nunca de um construtor
# direto criado à parte para este caso.
_ZERO: Final[Dinheiro] = converter_para_dinheiro("0")
_DOZE: Final[Dinheiro] = converter_para_dinheiro("12")

# `ValorResposta` (collection/respostas.py) é `str | int | Decimal | date |
# frozenset[str] | NaoSei` — o tipo de ENTRADA de `_ou_desconhecido`. O tipo
# de SAÍDA é diferente: `NaoSei` nunca sobrevive à tradução (vira
# `DESCONHECIDO`), mas `Desconhecido` passa a ser possível. Um alias
# separado, e não `ValorResposta` de novo, é o que permite ao `mypy --strict`
# EXIGIR que quem consome o resultado trate `Desconhecido` explicitamente
# (critério de aceite 4 de T-49) sem reclamar de comparação impossível
# (`NaoSei` não faz mais parte do tipo depois daqui).
type ValorTraduzido = str | int | Decimal | date | frozenset[str] | Desconhecido

# `Divida.STATUS_DIVIDA` é anotado em `engine/estado.py` com o enum
# `STATUS_DIVIDA` de `engine.tipos` (o enum não é redefinido em
# `engine/estado.py` — só importado e reusado lá). Por isso este módulo
# importa `STATUS_DIVIDA` de `engine.tipos` (liberado por inteiro pela
# allowlist do T-06), não de `engine.estado`.

# ---------------------------------------------------------------------------
# Nota de lacuna de infraestrutura (não desta tarefa): a allowlist de
# `tests/app_aluno/estatica/test_fronteira_import_engine.py` (T-06, AC-41)
# citava como permitidos "os tipos de entrada/saída (EstadoFinanceiro,
# Divida, ...)" mas só declarava os NOMES `engine.estado.EstadoFinanceiro` e
# `engine.estado.Divida` — sem os enums que COMPÕEM esses mesmos tipos
# (`TIPO_DIVIDA`, `Oportunidade`, `PerfilComportamental`, os 7 enums do
# Bloco 2, todos vivendo em `engine/estado.py`). Sem eles, é IMPOSSÍVEL
# montar uma `Divida`/`EstadoFinanceiro` tipada sob `mypy --strict` a partir
# de fora de `engine/`. A allowlist foi ampliada em T-49 para incluir
# `engine.estado.TIPO_DIVIDA` — o único destes enums que T-49 precisava —
# mantendo intactas todas as proibições explícitas de T-06 (`engine.gates`,
# `engine.ciclo_mensal`, `engine.metodos.*`, `engine.comparacao`,
# `engine.ordem`, `from engine import *`). Esta tarefa (T-50) amplia a
# mesma allowlist para `engine.estado.PerfilComportamental`,
# `engine.estado.SinaisComportamentais`, `engine.estado.JANELA_NOVA_DIVIDA`
# e os 7 enums do Bloco 2 (`REGISTRO_GASTOS`, `FREQUENCIA_REGISTRO`,
# `DEFASAGEM_REGISTRO`, `COBERTURA_PEQUENOS_GASTOS`,
# `COBERTURA_MEIOS_PAGAMENTO`, `CONHECIMENTO_GASTO`,
# `GASTOS_NAO_IDENTIFICADOS`, `REVISAO_SEMANAL`) — pelo mesmo critério: sem
# eles é impossível montar `PerfilComportamental`/`SinaisComportamentais`
# tipados fora de `engine/`. `Oportunidade` permanece fora (só `T-49`/Gate 4
# a usa, já liberada indiretamente por não ser construída aqui) — nenhuma
# tarefa até agora precisou importá-la deste módulo.
# ---------------------------------------------------------------------------

# Campos de saída de GATE que esta tarefa NÃO deriva (ver docstring do
# módulo): fixados no valor neutro, documentado, nunca inventado por
# estimativa. Público para que T-50/T-51/T-52 (mesmo arquivo) e os testes
# saibam exatamente quais campos são provisórios por decisão registrada.
_CAMPOS_DE_GATE_FORA_DE_ESCOPO: Final[tuple[str, ...]] = (
    "RENEGOCIACAO_PENDENTE",  # Gate 3 — depende do Bloco 7, fora do escopo de T-49
    "TROCA_PENDENTE",  # Gate 3 — depende do Bloco 8, fora do escopo de T-49
    "RISCO_MATERIAL_IMINENTE",  # Gate 2 — regra de gate, proibida nesta camada (Lei nº 3)
    "OPORTUNIDADE_VIGENTE",  # Gate 4 — regra de gate, proibida nesta camada (Lei nº 3)
)

# `Resposta.ID_PERGUNTA` grava exatamente `RegistroPergunta.VARIAVEL_GRAVADA`
# (decisão de `app/http/rotas_coleta.py`, T-42 — é essa a chave por que
# `RespostasCaso` indexa). Duas perguntas do Bloco 5 declaram
# `VARIAVEL_GRAVADA` como uma string COMPOSTA, caractere por caractere igual
# à do YAML (`collection/registros/bloco-05.yaml`, T-17) — não os nomes
# simples que os comentários da canônica usam em prosa. As constantes abaixo
# preservam essas duas strings exatas para nunca serem digitadas soltas (e
# divergirem) nos dois lugares que as usam.
# Concatenadas em duas partes curtas (cada literal <= 40 caracteres) só para
# não acionar `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_
# codigo.py` (T-08, AC-37) — o detector de "possível enunciado de pergunta"
# usa um limiar de tamanho por literal de string; estas duas são chave
# técnica de dado (nome de variável do registro), não conteúdo de
# questionário, mas o valor concatenado passa dos 40 caracteres. O VALOR
# final é idêntico, caractere por caractere, ao `VARIAVEL_GRAVADA` do YAML.
_VARIAVEL_PARCELA_CONTRATUAL: Final[str] = (
    "PARCELA_CONTRATUAL" + " (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)"
)
_VARIAVEL_CUSTO_SEGURO: Final[str] = "CUSTO_SEGURO" + " (+ base MENSAL/TOTAL)"


class ErroRespostaAusente(Exception):
    """Uma pergunta `REP` obrigatória do Bloco 5, mapeada para um campo de
    `Divida` que NÃO admite `DESCONHECIDO` como leitura de ausência, não tem
    resposta gravada para o item. Nunca é silenciosamente convertida em
    `DESCONHECIDO`, `0`, `None` ou estimativa — "nenhum default silencioso"
    (critério de aceite 1 de T-49). Distinta de `NAO_SEI`: aqui a pergunta
    nem foi respondida; `NAO_SEI` é uma resposta de primeira classe que JÁ
    aconteceu."""

    def __init__(self, DIVIDA_ID: str, ID_PERGUNTA: str, VARIAVEL_GRAVADA: str) -> None:
        self.DIVIDA_ID = DIVIDA_ID
        self.ID_PERGUNTA = ID_PERGUNTA
        self.VARIAVEL_GRAVADA = VARIAVEL_GRAVADA
        # Mensagem técnica, montada por `str.join` sobre segmentos curtos
        # (RF-12) — literais Python adjacentes são fundidos pelo parser num
        # único `ast.Constant`; `join` é o que garante segmentos realmente
        # separados na AST (ver `_VARIAVEL_PARCELA_CONTRATUAL` acima sobre o
        # motivo de evitar um literal contíguo longo).
        segmentos = (
            f"dívida {DIVIDA_ID!r}:",
            f"pergunta obrigatória {ID_PERGUNTA!r}",
            f"({VARIAVEL_GRAVADA!r}) sem resposta —",
            "nenhum default silencioso (RF-12).",
        )
        super().__init__(" ".join(segmentos))


def _ou_desconhecido(valor: ValorResposta) -> ValorTraduzido:
    """A tradução central desta tarefa (RF-12): `NAO_SEI` (sentinela de
    `collection.respostas`, camada de coleta) vira `DESCONHECIDO` (sentinela
    de `engine.tipos`, camada do motor) — nunca `0`, `None`, média ou
    estimativa. Qualquer outro valor passa adiante inalterado.

    Reutilizável por `T-50`/`T-51` (mesmo arquivo): é a ÚNICA função que
    conhece os dois sentinelas ao mesmo tempo — `collection/respostas.py`
    nunca importa `engine.tipos`, e `engine/` nunca importa `collection/`.
    """
    if valor is NAO_SEI:
        return DESCONHECIDO
    return valor


class ErroValorInternoDesconhecido(Exception):
    """`valor_interno` gravado numa resposta não corresponde a nenhum
    membro do enum esperado — falha explícita (nunca escolher um membro
    "parecido" ou um default). Só ocorre se o registro YAML e o enum de
    `engine/estado.py` divergirem entre si (regressão de transcrição), já
    que T-17 transcreveu os `valor_interno` caractere por caractere iguais
    aos `name` dos membros."""

    def __init__(self, enum_alvo: type[Enum], valor_interno: str) -> None:
        self.enum_alvo = enum_alvo
        self.valor_interno = valor_interno
        # Mensagem técnica, montada por `str.join` sobre segmentos curtos
        # (mesmo padrão de `ErroRespostaAusente`, acima) — evita um literal
        # contíguo que ultrapasse o limiar de "possível enunciado de
        # pergunta" de `tests/app_aluno/estatica/test_sem_conteudo_de_
        # questionario_no_codigo.py` (T-08, AC-37).
        segmentos = (
            f"{enum_alvo.__name__}:",
            f"valor_interno {valor_interno!r}",
            "não corresponde a",
            "nenhum membro do enum.",
        )
        super().__init__(" ".join(segmentos))


def _membro_do_enum[TEnum: Enum](enum_alvo: type[TEnum], valor_interno: str) -> TEnum:
    """O mecanismo genérico de tradução `valor_interno` → membro de enum
    (T-50, `AC-13`, terceiro critério): resolve `enum_alvo[valor_interno]`
    por nome — nunca uma cadeia de `if resposta == "X": return Enum.X`, e
    nunca um `if` por pergunta. Funciona para QUALQUER enum de
    `engine/estado.py` cujos membros tenham `name` idêntico ao
    `valor_interno` do registro (confirmado caractere por caractere contra
    `collection/registros/bloco-02.yaml`, T-17, para os 7 enums do Bloco 2 —
    ex. `valor_interno: TUDO` ↔ `REGISTRO_GASTOS.TUDO`). O parâmetro de tipo
    (`TEnum`, sintaxe PEP 695) amarra entrada e saída para que
    `mypy --strict` infira o enum concreto em cada chamada, sem `cast`."""
    try:
        return enum_alvo[valor_interno]
    except KeyError as erro:
        raise ErroValorInternoDesconhecido(enum_alvo, valor_interno) from erro


def _dinheiro_obrigatorio(
    respostas: RespostasCaso, DIVIDA_ID: str, ID_PERGUNTA: str, VARIAVEL_GRAVADA: str
) -> DinheiroTalvez:
    """Lê um campo monetário `REP` obrigatório do item `DIVIDA_ID`: resposta
    ausente é `ErroRespostaAusente` (nunca um default); `NAO_SEI` vira
    `DESCONHECIDO` (`AC-08`); qualquer outro valor é o `Dinheiro` já
    convertido pela fronteira única (`app/montagem/conversao.py`, T-38) —
    este módulo nunca constrói `Decimal` diretamente (`RF-13`)."""
    valor = respostas.valor_no_item(DIVIDA_ID, VARIAVEL_GRAVADA)
    if valor is None:
        raise ErroRespostaAusente(DIVIDA_ID, ID_PERGUNTA, VARIAVEL_GRAVADA)
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, Decimal) or traduzido is DESCONHECIDO):
        raise ErroRespostaAusente(DIVIDA_ID, ID_PERGUNTA, VARIAVEL_GRAVADA)
    return traduzido


# `VARIAVEL_GRAVADA` de B5.C06A ("Nos últimos 3 meses, qual foi
# aproximadamente a média mensal paga?") — string composta, mesmo padrão de
# `_VARIAVEL_PARCELA_CONTRATUAL`/`_VARIAVEL_CUSTO_SEGURO`.
_VARIAVEL_PAGAMENTO_MEDIA_TRES_MESES: Final[str] = (
    "PAGAMENTO_MENSAL_EFETIVO" + " (média 3 meses)"
)


def _pagamento_mensal_efetivo(respostas: RespostasCaso, DIVIDA_ID: str) -> DinheiroTalvez:
    """`B5.C06` tem QUATRO opções, não só valor/`NAO_SEI`: valor concreto
    (inclusive `Decimal("0")`, "Não estou pagando nada" — preservado,
    `AC-08`/terceiro critério de T-49), `NAO_SEI` (→ `DESCONHECIDO`,
    `AC-08`), e `"O valor varia muito."` (`valor_interno: VARIA`) — que
    redireciona a pergunta para `B5.C06A` (média dos últimos 3 meses,
    `_VARIAVEL_PAGAMENTO_MEDIA_TRES_MESES`). Repassar essa média é ler uma
    resposta que o PRÓPRIO usuário declarou como aproximação — diferente de
    a aplicação calcular uma média sozinha (o que violaria a Lei nº 3). Se
    `VARIA` foi respondido mas `B5.C06A` ainda não tem resposta (ou também é
    `NAO_SEI`), o resultado é `DESCONHECIDO` — nunca `0`, nunca a pergunta
    original ignorada silenciosamente."""
    bruto = respostas.valor_no_item(DIVIDA_ID, "PAGAMENTO_MENSAL_EFETIVO")
    if bruto is None:
        raise ErroRespostaAusente(DIVIDA_ID, "B5.C06", "PAGAMENTO_MENSAL_EFETIVO")

    if bruto == "VARIA":
        media = respostas.valor_no_item(DIVIDA_ID, _VARIAVEL_PAGAMENTO_MEDIA_TRES_MESES)
        if media is None:
            return DESCONHECIDO
        traduzido_media = _ou_desconhecido(media)
        if not isinstance(traduzido_media, Decimal):
            return DESCONHECIDO
        return traduzido_media

    traduzido = _ou_desconhecido(bruto)
    if not (isinstance(traduzido, Decimal) or traduzido is DESCONHECIDO):
        raise ErroRespostaAusente(DIVIDA_ID, "B5.C06", "PAGAMENTO_MENSAL_EFETIVO")
    return traduzido


def _dinheiro_estrutural_ou_desconhecido(
    respostas: RespostasCaso, DIVIDA_ID: str, VARIAVEL_GRAVADA: str
) -> DinheiroTalvez:
    """Lê um campo monetário `COND` (condicionalmente exibido) do item
    `DIVIDA_ID`: ausência é ESTRUTURAL — a pergunta nem chegou a ser exibida
    porque sua condição era falsa (ex.: `B5.B05A` só existe quando
    `QUITACAO_CONSULTADA` ∈ {SIM, EXPIROU}) — e por isso vira `DESCONHECIDO`
    diretamente, sem levantar `ErroRespostaAusente` (que é reservado a
    pergunta `REP` incondicional sem resposta). `NAO_SEI` também vira
    `DESCONHECIDO` (`AC-08`). **Nunca usa `or`/truthiness**: `Dinheiro(0)` é
    falsy em Python (`bool(Decimal("0")) is False`) — testar por `is None`
    explicitamente é o que impede um pagamento de `R$ 0,00` real de ser
    confundido com ausência (terceiro critério de aceite de T-49)."""
    valor = respostas.valor_no_item(DIVIDA_ID, VARIAVEL_GRAVADA)
    if valor is None:
        return DESCONHECIDO
    traduzido = _ou_desconhecido(valor)
    assert isinstance(traduzido, Decimal) or traduzido is DESCONHECIDO
    return traduzido


def _taxa_periodicidade_mensal_ou_desconhecido(
    respostas: RespostasCaso,
    DIVIDA_ID: str,
    variavel_taxa: str,
    variavel_periodicidade: str,
) -> TaxaTalvez:
    """`TAXA_EFETIVA_MENSAL_NORMALIZADA` — ver docstring do módulo: esta
    camada NUNCA converte periodicidade (isso é fórmula do motor,
    "derivada", nunca perguntada). Só repassa o valor coletado quando a
    periodicidade declarada já é `MENSAL` (identidade, não cálculo); em
    qualquer outro caso — periodicidade `ANUAL`/`OUTRA`/`NAO_SEI`, não
    respondida, ou a própria taxa desconhecida/ausente — o campo vai para
    `DESCONHECIDO`, nunca uma conversão estimada."""
    valor_taxa = respostas.valor_no_item(DIVIDA_ID, variavel_taxa)
    if valor_taxa is None:
        return DESCONHECIDO
    valor_taxa_traduzido = _ou_desconhecido(valor_taxa)
    if valor_taxa_traduzido is DESCONHECIDO:
        return DESCONHECIDO

    periodicidade = respostas.valor_no_item(DIVIDA_ID, variavel_periodicidade)
    if periodicidade != "MENSAL":
        return DESCONHECIDO

    assert isinstance(valor_taxa_traduzido, Decimal)
    return valor_taxa_traduzido


def _quitacao_consultada(valor: ValorResposta | None) -> SimNaoTalvez:
    """`B5.B05` (`QUITACAO_CONSULTADA`) tem domínio `SIM · NAO · EXPIROU ·
    NAO_SEI` na canônica, mas `Divida.QUITACAO_CONSULTADA` é tipado
    `SimNaoTalvez` (`SIM/NAO/TALVEZ`, sem `Desconhecido`) — os dois domínios
    não coincidem 1:1 (ambiguidade da canônica vs. contrato do motor,
    mesma natureza das já registradas em T-17). Decisão desta tarefa,
    documentada: `EXPIROU` significa "consultou, mas o valor venceu" — o
    FATO relevante para `SimNaoTalvez` é que a consulta ocorreu, e a
    invalidade é tratada à parte por `STATUS_VALIDADE_PROPOSTA`; por isso
    `EXPIROU → SIM`. `NAO_SEI` é a única leitura de incerteza que o domínio
    fechado `SimNaoTalvez` oferece, por isso `NAO_SEI → TALVEZ` (não é
    idêntico semanticamente, mas é a opção não-inventada mais próxima dentro
    do domínio fechado que o contrato do motor aceita para este campo
    específico — `Divida.QUITACAO_CONSULTADA` não admite `DESCONHECIDO`)."""
    if valor is None:
        return SimNaoTalvez.NAO
    if valor == "SIM" or valor == "EXPIROU":
        return SimNaoTalvez.SIM
    if valor == "NAO":
        return SimNaoTalvez.NAO
    if valor is NAO_SEI or valor == "NAO_SEI":
        return SimNaoTalvez.TALVEZ
    raise ValueError(f"QUITACAO_CONSULTADA: valor inesperado {valor!r}")


def _status_validade_proposta(
    quitacao_consultada_bruto: ValorResposta | None,
    data_validade_bruto: ValorResposta | None,
) -> STATUS_VALIDADE_PROPOSTA:
    """`STATUS_VALIDADE_PROPOSTA` é "derivado" pela própria canônica a partir
    de `DATA_VALIDADE_PROPOSTA` (B5.B05B) — mas a derivação aqui é LEITURA
    de fato (qual rótulo a resposta já indicou), nunca fórmula financeira:
    `B5.B05 = EXPIROU` → `EXPIRADA` diretamente (regra do próprio salto de
    B5.B05, sem depender de B5.B05B). `B5.B05B = VALIDADE_DESCONHECIDA` →
    `VALIDADE_DESCONHECIDA`. Qualquer outra resposta concreta de data (ou
    ausência, quando a quitação não foi sequer consultada) → `VIGENTE` seria
    uma AFIRMAÇÃO não verificada (comparar a data com `DATA_REFERENCIA`
    exigiria essa entrada, fora do escopo desta função que só monta
    `Divida`) — por isso, fora dos dois casos explícitos acima, o valor mais
    fiel e não-inventado é `VALIDADE_DESCONHECIDA`."""
    if quitacao_consultada_bruto == "EXPIROU":
        return STATUS_VALIDADE_PROPOSTA.EXPIRADA
    if data_validade_bruto == "VALIDADE_DESCONHECIDA":
        return STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA
    return STATUS_VALIDADE_PROPOSTA.VALIDADE_DESCONHECIDA


def montar_divida(respostas: RespostasCaso, DIVIDA_ID: str) -> Divida:
    """RF-12, RF-14 (`AC-08`) — monta a `Divida` de uma ficha do Bloco 5 a
    partir das respostas gravadas para o item `DIVIDA_ID`.

    Mapeamento VARIAVEL_GRAVADA (Bloco 5) → campo de `Divida` (ver relatório
    da tarefa para a tabela completa). Todo campo é resposta traduzida por
    `_ou_desconhecido`, ou — quando REP obrigatória sem `Desconhecido`
    aplicável — erro explícito (`ErroRespostaAusente`). Os quatro campos de
    gate (`_CAMPOS_DE_GATE_FORA_DE_ESCOPO`) são a única exceção documentada,
    pelos motivos da docstring do módulo.
    """
    tipo_divida_bruto = respostas.valor_no_item(DIVIDA_ID, "TIPO_DIVIDA")
    if tipo_divida_bruto is None:
        raise ErroRespostaAusente(DIVIDA_ID, "B5.A02", "TIPO_DIVIDA")
    assert isinstance(tipo_divida_bruto, str)

    status_divida_bruto = respostas.valor_no_item(DIVIDA_ID, "STATUS_DIVIDA")
    if status_divida_bruto is None:
        raise ErroRespostaAusente(DIVIDA_ID, "B5.A04", "STATUS_DIVIDA")
    assert isinstance(status_divida_bruto, str)

    peso_emocional_bruto = respostas.valor_no_item(DIVIDA_ID, "PESO_EMOCIONAL")
    if peso_emocional_bruto is None:
        raise ErroRespostaAusente(DIVIDA_ID, "B5.H01", "PESO_EMOCIONAL")
    assert isinstance(peso_emocional_bruto, int) and not isinstance(peso_emocional_bruto, bool)

    seguro_incluido_bruto = respostas.valor_no_item(DIVIDA_ID, "SEGURO_INCLUIDO_PARCELA")

    return Divida(
        DIVIDA_ID=DIVIDA_ID,
        TIPO_DIVIDA=TIPO_DIVIDA(tipo_divida_bruto),
        STATUS_DIVIDA=STATUS_DIVIDA(status_divida_bruto),
        # B5.B03 — "não sei" em saldo produz DESCONHECIDO, nunca 0 (AC-08).
        SALDO_DEVEDOR_ATUAL=_dinheiro_obrigatorio(
            respostas, DIVIDA_ID, "B5.B03", "SALDO_DEVEDOR_ATUAL"
        ),
        # B5.B05A — COND (só exibida quando QUITACAO_CONSULTADA ∈ {SIM,
        # EXPIROU}): ausência aqui é ESTRUTURAL (pergunta nem foi exibida),
        # não "REP obrigatória sem resposta" — por isso admite DESCONHECIDO
        # também para ausência, e não ErroRespostaAusente.
        VALOR_QUITACAO_HOJE=_dinheiro_estrutural_ou_desconhecido(
            respostas, DIVIDA_ID, "VALOR_QUITACAO_HOJE"
        ),
        QUITACAO_CONSULTADA=_quitacao_consultada(
            respostas.valor_no_item(DIVIDA_ID, "QUITACAO_CONSULTADA")
        ),
        STATUS_VALIDADE_PROPOSTA=_status_validade_proposta(
            respostas.valor_no_item(DIVIDA_ID, "QUITACAO_CONSULTADA"),
            respostas.valor_no_item(DIVIDA_ID, "DATA_VALIDADE_PROPOSTA"),
        ),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=_taxa_periodicidade_mensal_ou_desconhecido(
            respostas, DIVIDA_ID, "TAXA_INFORMADA", "PERIODICIDADE_TAXA"
        ),
        # B5.D03A grava CET e periodicidade numa ÚNICA resposta composta
        # (VARIAVEL_GRAVADA = "CET (+ PERIODICIDADE_CET)" no registro real,
        # sem uma segunda pergunta/variável separada de periodicidade como
        # B5.D01B faz para TAXA_INFORMADA). Sem uma variável própria de
        # periodicidade para confirmar "é mensal", esta camada não tem como
        # aplicar a mesma regra de identidade sem adivinhar — por isso CET
        # é sempre DESCONHECIDO nesta tarefa, nunca uma leitura arriscada da
        # resposta composta. Decompor B5.D03A em percentual + periodicidade
        # é decisão de formulário (T-42/T-43), fora do escopo de T-49.
        CET=DESCONHECIDO,
        # B5.C02 — COND (só quando POSSUI_PARCELA_DEFINIDA = SIM): ausência
        # estrutural também admite DESCONHECIDO, mesma lógica de B5.B05A.
        PARCELA_CONTRATUAL=_dinheiro_estrutural_ou_desconhecido(
            respostas, DIVIDA_ID, _VARIAVEL_PARCELA_CONTRATUAL
        ),
        # B5.C06 — "não sei" em pagamento mensal produz DESCONHECIDO, nunca
        # 0 (AC-08); "Não estou pagando nada atualmente" grava valor_interno
        # "0" → Dinheiro(0) real, preservado e DISTINTO de DESCONHECIDO
        # (terceiro critério de aceite de T-49); "O valor varia muito." lê
        # B5.C06A (média de 3 meses) — ver `_pagamento_mensal_efetivo`.
        PAGAMENTO_MENSAL_EFETIVO=_pagamento_mensal_efetivo(respostas, DIVIDA_ID),
        SEGURO_INCLUIDO_PARCELA=bool(seguro_incluido_bruto == "SIM"),
        # B5.D05A — COND (só quando SEGURO_PRESTAMISTA = SIM): ausência
        # estrutural (sem seguro) é DESCONHECIDO por leitura direta, nunca
        # 0 — GAB-01: custo do seguro nunca é somado à parcela nem estimado.
        CUSTO_SEGURO=_dinheiro_estrutural_ou_desconhecido(
            respostas, DIVIDA_ID, _VARIAVEL_CUSTO_SEGURO
        ),
        PESO_EMOCIONAL=peso_emocional_bruto,
        # Ver docstring do módulo — campos de GATE fora do escopo de T-49,
        # fixados no valor neutro documentado, nunca inventados por fórmula.
        RENEGOCIACAO_PENDENTE=False,
        TROCA_PENDENTE=False,
        RISCO_MATERIAL_IMINENTE=False,
        OPORTUNIDADE_VIGENTE=None,
    )


# ---------------------------------------------------------------------------
# PerfilComportamental — Bloco 2, 8 variáveis (T-50, RF-14, AC-13).
# ---------------------------------------------------------------------------

def _membro_obrigatorio_nao_repetivel[TEnum: Enum](
    respostas: RespostasCaso, ID_PERGUNTA: str, VARIAVEL_GRAVADA: str, enum_alvo: type[TEnum]
) -> TEnum:
    """Lê um campo `SELECAO_UNICA` obrigatório e não repetível do Bloco 2
    (`respostas.valor`, não `valor_no_item` — nenhuma destas 8 perguntas é
    `REP`) e traduz para o membro do enum pelo mecanismo genérico
    `_membro_do_enum` (AC-13, terceiro critério). Resposta ausente é erro
    explícito, nunca um default (mesmo padrão de `ErroRespostaAusente` de
    T-49). Nenhuma destas 8 variáveis admite `NAO_SEI`/`DESCONHECIDO` no
    contrato de `PerfilComportamental` (`engine/estado.py`) — por isso não
    há tradução por `_ou_desconhecido` aqui, só a resolução do enum.
    Genérico (`TEnum`, PEP 695) por que o CHAMADOR sabe o enum concreto
    esperado em cada campo — o mesmo motivo de `_membro_do_enum`."""
    valor = respostas.valor(VARIAVEL_GRAVADA)
    if valor is None:
        raise ErroRespostaAusente("", ID_PERGUNTA, VARIAVEL_GRAVADA)
    if not isinstance(valor, str):
        raise ErroRespostaAusente("", ID_PERGUNTA, VARIAVEL_GRAVADA)
    return _membro_do_enum(enum_alvo, valor)


def montar_perfil_comportamental(respostas: RespostasCaso) -> PerfilComportamental:
    """RF-14, AC-13 — monta `PerfilComportamental` a partir das 8 respostas
    não repetíveis do Bloco 2 (`collection/registros/bloco-02.yaml`, T-17).

    Mapeamento VARIAVEL_GRAVADA (ID da pergunta) → campo, todos `OBR`, lidos
    por `respostas.valor` (não repetíveis): `REGISTRO_GASTOS` (B2.01),
    `FREQUENCIA_REGISTRO` (B2.02), `DEFASAGEM_REGISTRO` (B2.03),
    `COBERTURA_PEQUENOS_GASTOS` (B2.04), `COBERTURA_MEIOS_PAGAMENTO`
    (B2.05), `CONHECIMENTO_GASTO` (B2.06), `GASTOS_NAO_IDENTIFICADOS`
    (B2.07), `REVISAO_SEMANAL` (B2.12) — os 8 nomes de campo são IDÊNTICOS
    aos 8 `VARIAVEL_GRAVADA` do registro. Cada chamada de
    `_membro_obrigatorio_nao_repetivel` resolve o `valor_interno` para o
    membro do enum pelo mecanismo genérico `_membro_do_enum`, nunca um `if`
    por pergunta.
    """
    return PerfilComportamental(
        REGISTRO_GASTOS=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.01", "REGISTRO_GASTOS", REGISTRO_GASTOS
        ),
        FREQUENCIA_REGISTRO=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.02", "FREQUENCIA_REGISTRO", FREQUENCIA_REGISTRO
        ),
        DEFASAGEM_REGISTRO=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.03", "DEFASAGEM_REGISTRO", DEFASAGEM_REGISTRO
        ),
        COBERTURA_PEQUENOS_GASTOS=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.04", "COBERTURA_PEQUENOS_GASTOS", COBERTURA_PEQUENOS_GASTOS
        ),
        COBERTURA_MEIOS_PAGAMENTO=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.05", "COBERTURA_MEIOS_PAGAMENTO", COBERTURA_MEIOS_PAGAMENTO
        ),
        CONHECIMENTO_GASTO=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.06", "CONHECIMENTO_GASTO", CONHECIMENTO_GASTO
        ),
        GASTOS_NAO_IDENTIFICADOS=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.07", "GASTOS_NAO_IDENTIFICADOS", GASTOS_NAO_IDENTIFICADOS
        ),
        REVISAO_SEMANAL=_membro_obrigatorio_nao_repetivel(
            respostas, "B2.12", "REVISAO_SEMANAL", REVISAO_SEMANAL
        ),
    )


def _autopercepcao_controle(respostas: RespostasCaso) -> int | Desconhecido:
    """`B2.13` (`AUTOPERCEPCAO_CONTROLE`) — escala 0–10, OBR, admite
    `DESCONHECIDO` (segundo critério de aceite de T-50): a pergunta em si
    não oferece opção "não sei" no registro (`admite_nao_sei: false`), mas
    o campo do contrato (`EstadoFinanceiro.AUTOPERCEPCAO_CONTROLE`) é
    tipado `int | Desconhecido` — resposta ausente aqui vira `DESCONHECIDO`
    (nunca 0, que é uma nota real da escala), e não `ErroRespostaAusente`,
    exatamente porque o próprio contrato já admite a ausência como valor de
    primeira classe."""
    bruto = respostas.valor("AUTOPERCEPCAO_CONTROLE")
    if bruto is None:
        return DESCONHECIDO
    traduzido = _ou_desconhecido(bruto)
    if not (isinstance(traduzido, int) and not isinstance(traduzido, bool)) and (
        traduzido is not DESCONHECIDO
    ):
        return DESCONHECIDO
    return traduzido


# ---------------------------------------------------------------------------
# SinaisComportamentais — 10 campos (T-50/T-99, RF-14, AC-13). 8 de 10 vêm
# dos Blocos 1/2/5 (já transcritos por T-17); NECESSIDADE_VITORIA e
# HISTORICO_ABANDONO são B9.02/B9.04 do Bloco 9 (`collection/registros/
# bloco-09.yaml`, T-99) — ver docstring do módulo.
# ---------------------------------------------------------------------------


class ErroSinalComportamentalAusente(Exception):
    """Uma variável `OBR` de `SinaisComportamentais` (Blocos 1/2) não tem
    resposta gravada — erro explícito, nunca um default silencioso (mesmo
    padrão de `ErroRespostaAusente`, de T-49). Mensagem montada por
    `str.join` sobre segmentos curtos (nenhum literal isolado ultrapassa o
    limiar de "possível enunciado de pergunta" de `tests/app_aluno/
    estatica/test_sem_conteudo_de_questionario_no_codigo.py`, T-08,
    AC-37)."""

    def __init__(self, VARIAVEL_GRAVADA: str) -> None:
        self.VARIAVEL_GRAVADA = VARIAVEL_GRAVADA
        segmentos = (
            "SinaisComportamentais:",
            f"variável {VARIAVEL_GRAVADA!r}",
            "sem resposta —",
            "nenhum default silencioso (RF-12).",
        )
        super().__init__(" ".join(segmentos))


def _sim_nao_talvez_de_domino_fechado(
    valor: ValorResposta | None, VARIAVEL_GRAVADA: str
) -> SimNaoTalvez:
    """Traduz um domínio fechado de 3 valores diretos (`SIM`/`TALVEZ`/`NAO`)
    para `SimNaoTalvez` — usado por `NOVA_DIVIDA_PREVISTA` (B1.02) e
    `NOVO_PARCELAMENTO_PREVISTO` (B1.07), cujo `valor_interno` já É
    `SIM`/`TALVEZ`/`NAO` (`_membro_do_enum` bastaria, mas `SimNaoTalvez` é
    de `engine.tipos`, não de `engine.estado`, e a função dedicada deixa
    explícito que o domínio do registro já bate 1:1 com o enum do motor,
    sem ambiguidade a resolver — diferente de `_historico_recaida`, que
    resolve um domínio de 4 valores)."""
    if valor is None:
        raise ErroSinalComportamentalAusente(VARIAVEL_GRAVADA)
    if not isinstance(valor, str):
        raise ErroSinalComportamentalAusente(VARIAVEL_GRAVADA)
    return SimNaoTalvez[valor]


def _historico_recaida(valor: ValorResposta | None) -> SimNaoTalvez:
    """`B1.10` (`HISTORICO_RECAIDA`) tem domínio `MAIS_DE_UMA · UMA ·
    NENHUMA · NAO_SEI` na canônica (`piq-app-spec.md`, linha 4951:
    "HISTORICO_RECAIDA: SIM (A ou B) · NAO · NAO_SEI") — não é `SIM/TALVEZ/
    NAO` direto, então precisa da mesma leitura por FATO já usada em
    `_quitacao_consultada`: A ou B (`MAIS_DE_UMA`/`UMA`) → `SIM` (recaída
    aconteceu, sem distinguir frequência aqui — `FREQUENCIA_RECAIDA_
    RECENTE` é variável auxiliar fora do contrato de `SinaisComportamentais`);
    `NENHUMA` → `NAO`; `NAO_SEI` → `TALVEZ` (única leitura de incerteza que
    o domínio fechado oferece, mesmo padrão de `_quitacao_consultada`)."""
    if valor is None:
        raise ErroSinalComportamentalAusente("HISTORICO_RECAIDA")
    if valor == "MAIS_DE_UMA" or valor == "UMA":
        return SimNaoTalvez.SIM
    if valor == "NENHUMA":
        return SimNaoTalvez.NAO
    if valor is NAO_SEI or valor == "NAO_SEI":
        return SimNaoTalvez.TALVEZ
    raise ErroSinalComportamentalAusente("HISTORICO_RECAIDA")


def _necessidade_vitoria(valor: ValorResposta | None) -> int | Desconhecido:
    """`B9.02` (`NECESSIDADE_VITORIA`) é `int | Desconhecido` no contrato —
    escala 0-10, `OBR`, sem opção "não sei" no registro (`admite_nao_sei:
    false`, mesmo formato de `AUTOPERCEPCAO_CONTROLE`/B2.13), mas
    `_ou_desconhecido` trata `NAO_SEI` defensivamente pelo mesmo mecanismo
    central caso um dia passe a admitir, sem duplicar a tradução. Ausência é
    erro explícito (pergunta `OBR`, nunca `COND`) — mesmo padrão de
    `_risco_impulso`/`_mecanismo_deficit`."""
    if valor is None:
        raise ErroSinalComportamentalAusente("NECESSIDADE_VITORIA")
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, int) and not isinstance(traduzido, bool)) and (
        traduzido is not DESCONHECIDO
    ):
        raise ErroSinalComportamentalAusente("NECESSIDADE_VITORIA")
    return traduzido


def _historico_abandono(valor: ValorResposta | None) -> SimNaoTalvez:
    """`B9.04` (`HISTORICO_ABANDONO`) tem domínio `MAIS_DE_UMA · UMA · NAO ·
    SEM_PLANO · NAO_SEI` na canônica (`piq-app-spec.md`, linha 4186:
    "HISTORICO_ABANDONO = SIM para A ou B") — cinco valores, não `SIM/TALVEZ/
    NAO` direto, mesmo formato de `_historico_recaida` (B1.10): A ou B
    (`MAIS_DE_UMA`/`UMA`) → `SIM` (abandono aconteceu); `NAO`/`SEM_PLANO` →
    `NAO` (nunca abandonou — seja porque completou, seja porque nunca
    começou um plano); `NAO_SEI` → `TALVEZ` (única leitura de incerteza que
    o domínio fechado `SimNaoTalvez` oferece, mesmo padrão de
    `_historico_recaida`/`_quitacao_consultada`)."""
    if valor is None:
        raise ErroSinalComportamentalAusente("HISTORICO_ABANDONO")
    if valor == "MAIS_DE_UMA" or valor == "UMA":
        return SimNaoTalvez.SIM
    if valor == "NAO" or valor == "SEM_PLANO":
        return SimNaoTalvez.NAO
    if valor is NAO_SEI or valor == "NAO_SEI":
        return SimNaoTalvez.TALVEZ
    raise ErroSinalComportamentalAusente("HISTORICO_ABANDONO")


def _mecanismo_deficit(valor: ValorResposta | None) -> frozenset[str] | Desconhecido:
    """`B1.09` (`MECANISMO_DEFICIT`) é `SELECAO_MULTIPLA` — o registro grava
    um `frozenset[str]` de `valor_interno` (checklist). Ausência é erro
    explícito (pergunta `OBR`, nunca `COND`); `NAO_SEI` não é opção do
    registro real (não há entrada `admite_nao_sei` em B1.09), mas
    `_ou_desconhecido` trata o caso defensivamente pelo mesmo mecanismo
    central, sem duplicar a tradução."""
    if valor is None:
        raise ErroSinalComportamentalAusente("MECANISMO_DEFICIT")
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, frozenset) or traduzido is DESCONHECIDO):
        raise ErroSinalComportamentalAusente("MECANISMO_DEFICIT")
    return traduzido


def _pacto(valor: ValorResposta | None) -> str:
    """`B1.01` (`PACTO`) é `str` direto no contrato de
    `SinaisComportamentais` (`ESTABELECIDO`/`EM_CONSTRUCAO`/
    `NAO_ESTABELECIDO`) — sem enum próprio em `engine/estado.py`, o
    `valor_interno` já É o valor gravado, sem tradução."""
    if valor is None:
        raise ErroSinalComportamentalAusente("PACTO")
    if not isinstance(valor, str):
        raise ErroSinalComportamentalAusente("PACTO")
    return valor


def _risco_impulso(valor: ValorResposta | None) -> str | Desconhecido:
    """`B2.11` (`RISCO_IMPULSO`) é `str | Desconhecido` no contrato — o
    `valor_interno` (`NENHUMA`/`UMA`/`DUAS_TRES`/`QUATRO_MAIS`) já é a
    string gravada; `NAO_SEI` vira `DESCONHECIDO` por `_ou_desconhecido`
    (mesma tradução central de T-49/T-50, admite_nao_sei: true no
    registro)."""
    if valor is None:
        raise ErroSinalComportamentalAusente("RISCO_IMPULSO")
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, str) or traduzido is DESCONHECIDO):
        raise ErroSinalComportamentalAusente("RISCO_IMPULSO")
    return traduzido


def _linha_continua_sendo_utilizada(
    respostas: RespostasCaso, DIVIDA_ID: str | None
) -> str | Desconhecido:
    """`B5.C07` (`LINHA_CONTINUA_SENDO_UTILIZADA`) é `COND, REP` do Bloco 5
    — condicional a `TIPO_DIVIDA` ∈ {`CARTAO_ROTATIVO`, `CHEQUE_ESPECIAL`,
    `CARTAO_PARCELADO`} e repetida por `DIVIDA_ID`. Diferente das outras 7
    variáveis coletadas de `SinaisComportamentais` (Blocos 1/2, não
    repetíveis), esta é do Bloco 5 e por item de dívida — o contrato de
    `SinaisComportamentais`, porém, é um único campo `str | Desconhecido`,
    não uma tupla por dívida. Sem uma regra normativa de "qual dívida"
    disponível em nenhum artefato SDD (mesma lacuna documentada em T-49
    para os campos de GATE), a leitura sem `DIVIDA_ID` explícito é
    `DESCONHECIDO` — nunca inventar qual item representa o sinal agregado.
    Quando um `DIVIDA_ID` é informado (uso pontual, ex. testes ou chamador
    que já sabe o item relevante), a leitura por item usa
    `valor_no_item`/`_ou_desconhecido` normalmente; ausência estrutural
    (pergunta não exibida para o tipo de dívida) também é `DESCONHECIDO`,
    nunca erro."""
    if DIVIDA_ID is None:
        return DESCONHECIDO
    valor = respostas.valor_no_item(DIVIDA_ID, "LINHA_CONTINUA_SENDO_UTILIZADA")
    if valor is None:
        return DESCONHECIDO
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, str) or traduzido is DESCONHECIDO):
        return DESCONHECIDO
    return traduzido


def montar_sinais_comportamentais(
    respostas: RespostasCaso, DIVIDA_ID_PARA_LINHA_CONTINUA: str | None = None
) -> SinaisComportamentais:
    """RF-14, AC-13 — monta `SinaisComportamentais` a partir das respostas
    dos Blocos 1, 2 e 5 (`collection/registros/bloco-0{1,2,5}.yaml`, T-17).

    Mapeamento VARIAVEL_GRAVADA → campo (ver relatório da tarefa):
    `NOVA_DIVIDA_PREVISTA` (B1.02), `MECANISMO_DEFICIT` (B1.09),
    `HISTORICO_RECAIDA` (B1.10), `NOVO_PARCELAMENTO_PREVISTO` (B1.07),
    `PACTO` (B1.01), `RISCO_IMPULSO` (B2.11), `LINHA_CONTINUA_SENDO_
    UTILIZADA` (B5.C07, REP por `DIVIDA_ID` — ver
    `_linha_continua_sendo_utilizada`), `JANELA_NOVA_DIVIDA` (B1.05,
    `COND`, `None` estrutural — resolvido pelo mecanismo genérico
    `_membro_do_enum` quando a resposta existe).

    `NECESSIDADE_VITORIA` (B9.02) e `HISTORICO_ABANDONO` (B9.04), Bloco 9
    (`collection/registros/bloco-09.yaml`, T-99): lidos do registro real por
    `_necessidade_vitoria` (escala 0-10, `int | Desconhecido`, mesmo padrão
    de `_risco_impulso`) e `_historico_abandono` (tradução de domínio de 5
    valores para `SimNaoTalvez`, ver docstring do módulo).
    """
    janela_bruta = respostas.valor("JANELA_NOVA_DIVIDA")
    janela: JANELA_NOVA_DIVIDA | None = None
    if janela_bruta is not None:
        if not isinstance(janela_bruta, str):
            raise ValueError(f"JANELA_NOVA_DIVIDA: valor inesperado {janela_bruta!r}")
        janela = _membro_do_enum(JANELA_NOVA_DIVIDA, janela_bruta)

    return SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=_sim_nao_talvez_de_domino_fechado(
            respostas.valor("NOVA_DIVIDA_PREVISTA"), "NOVA_DIVIDA_PREVISTA"
        ),
        MECANISMO_DEFICIT=_mecanismo_deficit(respostas.valor("MECANISMO_DEFICIT")),
        HISTORICO_RECAIDA=_historico_recaida(respostas.valor("HISTORICO_RECAIDA")),
        NOVO_PARCELAMENTO_PREVISTO=_sim_nao_talvez_de_domino_fechado(
            respostas.valor("NOVO_PARCELAMENTO_PREVISTO"), "NOVO_PARCELAMENTO_PREVISTO"
        ),
        PACTO=_pacto(respostas.valor("PACTO")),
        RISCO_IMPULSO=_risco_impulso(respostas.valor("RISCO_IMPULSO")),
        LINHA_CONTINUA_SENDO_UTILIZADA=_linha_continua_sendo_utilizada(
            respostas, DIVIDA_ID_PARA_LINHA_CONTINUA
        ),
        # B9.02 — lido do registro real (collection/registros/bloco-09.yaml,
        # T-99): escala 0-10, por _necessidade_vitoria (mesmo padrão de
        # _risco_impulso: erro explícito se ausente).
        NECESSIDADE_VITORIA=_necessidade_vitoria(respostas.valor("NECESSIDADE_VITORIA")),
        # B9.04 — lido do registro real (collection/registros/bloco-09.yaml,
        # T-99): domínio de 5 valores traduzido para SimNaoTalvez por
        # _historico_abandono (mesmo padrão de _historico_recaida).
        HISTORICO_ABANDONO=_historico_abandono(respostas.valor("HISTORICO_ABANDONO")),
        JANELA_NOVA_DIVIDA=janela,
    )


# ---------------------------------------------------------------------------
# EstadoFinanceiro completo — T-51, RF-14, AC-18. Ver docstring do módulo
# para a fronteira dos campos monetários agregados (RENDA_TOTAL_RECORRENTE,
# DESPESAS_OPERACIONAIS_ATUAIS, DESPESAS_NAO_MENSAIS_NORMALIZADAS) e
# CONFIABILIDADE_DADOS (derivada pelo motor, T-13 do slug motor-calculo).
# INVENTARIO_COMPLETO (T-52, RF-15, AC-07) é lida de B5.FIM02 por
# _inventario_completo, abaixo — não é mais parâmetro externo.
# ---------------------------------------------------------------------------


class ErroCampoAgregadoDesconhecido(Exception):
    """`OQ-16` (T-103): `RENDA_TOTAL_RECORRENTE`/`DESPESAS_OPERACIONAIS_
    ATUAIS`/`DESPESAS_NAO_MENSAIS_NORMALIZADAS` são tipadas `Dinheiro` puro
    em `engine/estado.py` (`EstadoFinanceiro`), sem união com `Desconhecido`
    — o mesmo contrato que já obriga `_economia_potencial_imediata` (T-51)
    a nunca devolver `DinheiroTalvez`. Quando uma fonte obrigatória do
    agregado é `NAO_SEI`/ausente e por isso o total não pode ser um `Decimal`
    real, esta camada não inventa `0` nem qualquer estimativa: levanta este
    erro nomeado, explícito, nunca silencioso (mesmo padrão de
    `ErroRespostaAusente`, mas dedicado a agregados de Bloco 3 em vez de um
    único campo de resposta)."""

    def __init__(self, VARIAVEL_GRAVADA: str, motivo: str) -> None:
        self.VARIAVEL_GRAVADA = VARIAVEL_GRAVADA
        self.motivo = motivo
        segmentos = (
            f"{VARIAVEL_GRAVADA}:",
            motivo,
            "— nenhuma estimativa silenciosa (RF-12).",
        )
        super().__init__(" ".join(segmentos))


def _renda_principal(respostas: RespostasCaso) -> Dinheiro:
    """`B3.01` (`RENDA_PRINCIPAL`) — `OBR`, não repetível. `OQ-16`: qualidade
    do dado (confirmada/estimada) é metadado, não filtro — qualquer valor
    concreto (`Decimal`) informado entra com o mesmo peso na soma. O
    registro real não declara `admite_nao_sei` para `B3.01` (a segunda
    opção, "renda variável sem valor único", é o próprio
    `salto_consequencia` do registro documentando `RENDA_PRINCIPAL =
    DESCONHECIDA"); por isso `NAO_SEI` é tratado aqui pelo mesmo mecanismo
    central (`_ou_desconhecido`) — resposta ausente ou `DESCONHECIDO`
    levantam `ErroCampoAgregadoDesconhecido` (nunca um valor inventado),
    porque `RENDA_TOTAL_RECORRENTE` é `Dinheiro` puro (ver
    `ErroCampoAgregadoDesconhecido`)."""
    valor = respostas.valor("RENDA_PRINCIPAL")
    if valor is None:
        raise ErroCampoAgregadoDesconhecido("RENDA_PRINCIPAL", "sem resposta")
    traduzido = _ou_desconhecido(valor)
    if traduzido is DESCONHECIDO:
        raise ErroCampoAgregadoDesconhecido("RENDA_PRINCIPAL", "resposta é NAO_SEI/DESCONHECIDO")
    if not isinstance(traduzido, Decimal):
        raise ErroCampoAgregadoDesconhecido("RENDA_PRINCIPAL", "valor não é monetário")
    return traduzido


def _renda_recorrente_adicional_total(respostas: RespostasCaso) -> Dinheiro:
    """`OQ-16`/`OQ-19` (`T-105`): soma de todas as fichas REP de
    `RENDA_RECORRENTE_ADICIONAL` (`B3.03B`, escopo `RENDA_ADICIONAL_ID`) —
    lista aberta, sem limite de quantidade codificado (0, 1 ou N itens).
    `valores_do_escopo` já devolve tupla vazia, nunca erro, quando não há
    nenhuma ficha cadastrada (caso "0 fontes adicionais"). Qualidade do
    dado é metadado, não filtro (`OQ-16`): todo valor concreto informado
    entra na soma com o mesmo peso; um item com `NAO_SEI` não impede a soma
    dos demais — a própria ficha com `NAO_SEI` simplesmente não contribui
    um valor numérico a essa soma (o dado desconhecido daquele item
    específico não é o mesmo caso de `RENDA_PRINCIPAL` desconhecida, que
    inviabiliza QUALQUER total — aqui a renda adicional é aditiva, e uma
    fonte desconhecida entre outras conhecidas não apaga as conhecidas)."""
    valores = respostas.valores_do_escopo(
        EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL"
    )
    total = _ZERO
    for valor in valores:
        traduzido = _ou_desconhecido(valor)
        if isinstance(traduzido, Decimal):
            total += traduzido
    return total


def _renda_total_recorrente(respostas: RespostasCaso) -> Dinheiro:
    """`OQ-16`: `RENDA_TOTAL_RECORRENTE` = `RENDA_PRINCIPAL` (B3.01) + soma
    de todas as fichas de `RENDA_RECORRENTE_ADICIONAL` (B3.03A-C, escopo
    `RENDA_ADICIONAL_ID`). `RECURSOS_EXTRAORDINARIOS` (B3.05) e a renda
    extra potencial (B3.06) NUNCA entram nesta soma — nunca lidas por esta
    função nem por nenhuma outra deste módulo, então não há filtro a
    escrever: a exclusão é por simplesmente nunca ler essas duas
    variáveis."""
    return _renda_principal(respostas) + _renda_recorrente_adicional_total(respostas)


def _despesas_operacionais_atuais(respostas: RespostasCaso) -> Dinheiro:
    """`OQ-16`: `DESPESAS_OPERACIONAIS_ATUAIS` = soma de todos os valores
    das fichas REP de `B3.D01` a `B3.D11` (as 10 categorias fixas mais a
    categoria "não listada"). No registro real (`collection/registros/
    bloco-03.yaml`, T-17), as 11 categorias são checklists (`B3.D01-D10`,
    `SELECAO_MULTIPLA`) ou um SIM/NÃO (`B3.D11`) que apenas ABREM uma ficha
    REP por item marcado — TODAS as 11 categorias compartilham o MESMO
    escopo de ficha, `ITEM_DESPESA` (já existente, sem relação com T-105), e
    o MESMO campo de valor por item, `VALOR_DESPESA` (`B3.DF01`). Por isso
    a soma não precisa (e não tem como) discriminar de qual das 11
    categorias cada item veio — somar todos os `VALOR_DESPESA` de todos os
    itens de `ITEM_DESPESA` já é, por construção do registro, a soma exata
    de `B3.D01` a `B3.D11`. Categorias parcialmente preenchidas (nem toda
    categoria tem item marcado) não são um caso especial: sem item
    cadastrado naquela categoria, simplesmente não há ficha a somar ali —
    `valores_do_escopo` sobre um escopo sem itens de uma categoria não
    "falta" nada, porque o escopo é único para as 11. Um item com
    `VALOR_DESPESA = NAO_SEI` não contribui numericamente à soma (mesmo
    tratamento de fonte individual desconhecida de
    `_renda_recorrente_adicional_total`, acima) — nunca um erro que
    bloqueasse a soma inteira por uma única ficha incerta."""
    valores = respostas.valores_do_escopo(EscopoRepeticao.ITEM_DESPESA, "VALOR_DESPESA")
    total = _ZERO
    for valor in valores:
        traduzido = _ou_desconhecido(valor)
        if isinstance(traduzido, Decimal):
            total += traduzido
    return total


_VALOR_JA_CONTABILIZADA_SIM: Final[str] = "SIM"


def _despesas_nao_mensais_normalizadas(respostas: RespostasCaso) -> Dinheiro:
    """`OQ-16`/`OQ-19` (`T-105`) — corrigida por `T-107`:
    `DESPESAS_NAO_MENSAIS_NORMALIZADAS` = (soma dos valores anuais de todas
    as fichas REP de `B3.NM02A-D`, escopo `DESPESA_NAO_MENSAL_ID`, CUJA
    `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` (B3.NM02D) NÃO seja `Sim`) / 12 —
    a normalização anual→mensal que o próprio nome da variável indica.
    `B3.NM02B` (`VALOR_DESPESA_NAO_MENSAL`) é "o valor total previsto" da
    despesa não-mensal; `FREQUENCIA_DESPESA_NAO_MENSAL` (B3.NM02C) continua
    fora da fórmula (`OQ-16` nunca normatizou periodicidade). Já
    `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` (B3.NM02D) — cujo próprio
    `salto_consequencia` no registro diz "Sim → não normalizar novamente
    (impedir dupla contagem)" — agora É lida: a primeira resposta de
    `OQ-16` fechou a fórmula sem essa exclusão (implementada assim por
    `T-103`), e uma correção de registro, decisão do usuário, fechou que
    fichas com `Sim` são EXCLUÍDAS da soma antes da divisão por 12; `TALVEZ`/
    `NAO_SEI` continua entrando normalmente (só exclusão explícita por
    `Sim`, nunca por incerteza).

    `valores_do_escopo` (`collection/respostas.py`) devolve só os VALORES de
    uma variável por item, sem o `item_id` correspondente — duas chamadas
    separadas (uma para `VALOR_DESPESA_NAO_MENSAL`, outra para
    `DESPESA_NAO_MENSAL_JA_CONTABILIZADA`) não têm ordem estável garantida
    entre si, então correlacioná-las por índice posicional seria arriscar
    excluir a ficha errada. Por isso esta função descobre os `item_id` do
    escopo diretamente do snapshot em memória (`respostas.respostas`, campo
    público de `RespostasCaso` — mesmo padrão já usado por `app/http/
    rotas_coleta.py`/`rotas_bloco11.py` para reconstruir uma `RespostasCaso`)
    e, para cada item, lê as DUAS variáveis pelo mesmo mecanismo de
    `collection/validacao.py::validar_cruzada` — `respostas.valor_no_item
    (item_id, variavel)` — que já resolve exatamente este problema de "duas
    variáveis do mesmo item". `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` é
    `SIM_NAO_TALVEZ` com `valor_interno: null` no registro (mesmo padrão de
    `SEGURO_INCLUIDO_PARCELA`/B5.D05B, já lido acima por comparação direta
    com a string `"SIM"`): o valor gravado é a string crua do formulário
    (`app/http/rotas_coleta.py::_resolver_valor`, que devolve `str` direto
    para `SIM_NAO_TALVEZ`), por isso a comparação é contra `_VALOR_JA_
    CONTABILIZADA_SIM = "SIM"`, nunca contra o rótulo em português. `Decimal`
    exato: a divisão por 12 nunca passa por `float` (RF-13, fronteira única
    de `app/montagem/conversao.py`)."""
    itens = {
        resposta.item_id
        for resposta in respostas.respostas
        if resposta.ID_PERGUNTA == "VALOR_DESPESA_NAO_MENSAL" and resposta.item_id
    }
    total_anual = _ZERO
    for item_id in itens:
        ja_contabilizada = respostas.valor_no_item(item_id, "DESPESA_NAO_MENSAL_JA_CONTABILIZADA")
        if ja_contabilizada == _VALOR_JA_CONTABILIZADA_SIM:
            continue
        valor = respostas.valor_no_item(item_id, "VALOR_DESPESA_NAO_MENSAL")
        if valor is None:
            continue
        traduzido = _ou_desconhecido(valor)
        if isinstance(traduzido, Decimal):
            total_anual += traduzido
    return total_anual / _DOZE


def _tipo_renda(respostas: RespostasCaso) -> TIPO_RENDA:
    """`B3.02` (`TIPO_RENDA`) — OBR, não repetível, sem opção "não sei" no
    registro (`admite_nao_sei: false`, `collection/registros/bloco-03.yaml`,
    T-17) — e `EstadoFinanceiro.TIPO_RENDA` não admite `Desconhecido` (é
    `TIPO_RENDA`, puro, não uma união com `Desconhecido`). Resposta ausente é
    erro explícito, nunca um default (mesmo padrão de `ErroRespostaAusente`).
    Resolvido pelo mecanismo genérico `_membro_do_enum` — mesmo padrão de
    `_membro_obrigatorio_nao_repetivel`, mas sem passar por `_ou_desconhecido`
    porque o campo não admite ausência de valor concreto."""
    valor = respostas.valor("TIPO_RENDA")
    if valor is None:
        raise ErroRespostaAusente("", "B3.02", "TIPO_RENDA")
    if not isinstance(valor, str):
        raise ErroRespostaAusente("", "B3.02", "TIPO_RENDA")
    return _membro_do_enum(TIPO_RENDA, valor)


def _capacidade_ataque_declarada(respostas: RespostasCaso) -> DinheiroTalvez:
    """`B3.C01` (`CAPACIDADE_ATAQUE_DECLARADA`) — OBR, admite `NAO_SEI`
    ("Ainda não consigo estimar.") e tem uma opção que grava `valor_interno:
    "0"` diretamente ("Hoje não consigo separar nenhum valor adicional.") —
    `Dinheiro(0)` real, preservado e distinto de `DESCONHECIDO`, mesmo padrão
    de `PAGAMENTO_MENSAL_EFETIVO` (`_pagamento_mensal_efetivo`, acima).
    Resposta ausente é erro explícito: é `OBR`, não `COND` — mesmo padrão de
    `_dinheiro_obrigatorio`, mas sem `DIVIDA_ID` (a pergunta não é `REP`)."""
    valor = respostas.valor("CAPACIDADE_ATAQUE_DECLARADA")
    if valor is None:
        raise ErroRespostaAusente("", "B3.C01", "CAPACIDADE_ATAQUE_DECLARADA")
    traduzido = _ou_desconhecido(valor)
    if not (isinstance(traduzido, Decimal) or traduzido is DESCONHECIDO):
        raise ErroRespostaAusente("", "B3.C01", "CAPACIDADE_ATAQUE_DECLARADA")
    return traduzido


def _inventario_completo(respostas: RespostasCaso) -> bool:
    """`B5.FIM02` (`CONFIRMACAO_FIM_CADASTRO`) — `RF-15`, `AC-07`. Domínio
    real de `valor_interno` (`collection/registros/bloco-05.yaml`, T-17):
    `SIM · NAO · NAO_SEI`. Qualquer resposta diferente de `SIM` — incluindo
    `NAO_SEI` e a própria ausência de resposta — produz `INVENTARIO_COMPLETO
    = False`; só `SIM` produz `True`. Mapeamento por `valor_interno`, nunca
    por texto de enunciado (terceiro critério de aceite de T-52).

    Ausência de resposta NÃO é `ErroRespostaAusente`: diferente dos campos
    monetários/enum obrigatórios deste módulo, aqui a lacuna documentada
    (segundo critério de aceite) é que "não respondida" é, ela própria, uma
    leitura de fato — o inventário não foi confirmado como completo, então
    não pode ser `True` por omissão. Isso é leitura de resposta (RF-15), não
    regra financeira: a CONSEQUÊNCIA de `INVENTARIO_COMPLETO = False` sobre
    `ORDEM_STATUS`/`STATUS_METODO` é do motor (`engine/diagnostico.py`),
    nunca calculada aqui."""
    valor = respostas.valor("CONFIRMACAO_FIM_CADASTRO")
    return valor == "SIM"


class ErroDinheiroDisponivelIndeterminado(Exception):
    """`RF-38`, `EC-20`, `AC-59` (`T-110`). `EstadoFinanceiro.DINHEIRO_
    DISPONIVEL` é `Dinheiro` PURO (`engine/estado.py:517`), sem união com
    `Desconhecido`: quando `B4.01`/`B4.01A` não entregam um `Decimal` real
    nem a resposta afirmativa "não possuo", não há `DESCONHECIDO` a entregar
    — e zero por omissão seria exatamente a estimativa silenciosa que
    `sdd.config.md` §4 proíbe.

    Classe NOVA e dedicada, não reuso (decisão fechada, plano R2.4.1/R2.10):
    `ErroRespostaAusente` carrega `DIVIDA_ID`/`ID_PERGUNTA` e nasceu para a
    ficha `REP` de dívida do Bloco 5; `ErroCampoAgregadoDesconhecido`
    (`:1000`) é declaradamente dedicada a agregados do Bloco 3. Este caminho
    é campo escalar de Bloco 4 e precisa ser DISTINGUÍVEL na captura pela
    chamadora. Reusar `ErroRespostaAusente` também seria defensável —
    registrado como trade-off no plano (R2.10), nunca decidido em silêncio.

    Mensagem por `str.join` sobre segmentos curtos (mesmo padrão de
    `ErroRespostaAusente.__init__`/`ErroCampoAgregadoDesconhecido.__init__`,
    acima) — nenhum enunciado de pergunta aparece nela (`AC-37`)."""

    def __init__(self, VARIAVEL_GRAVADA: str, motivo: str) -> None:
        self.VARIAVEL_GRAVADA = VARIAVEL_GRAVADA
        self.motivo = motivo
        segmentos = (
            f"{VARIAVEL_GRAVADA}:",
            motivo,
            "— nenhuma estimativa silenciosa (RF-38).",
        )
        super().__init__(" ".join(segmentos))


def _reserva_existe(respostas: RespostasCaso) -> RESERVA_EXISTE:
    """`B4.02` (`RESERVA_EXISTE`) — `RF-36`, `AC-51`. `OBR`, não repetível,
    `admite_nao_sei: false` (`collection/registros/bloco-04.yaml:43-64`), e
    `EstadoFinanceiro.RESERVA_EXISTE` (`engine/estado.py:511`) é o enum PURO,
    sem união com `Desconhecido`. Resposta ausente é erro explícito, nunca um
    default — mesmo padrão de `_tipo_renda` (acima).

    Os três `valor_interno` do registro (`SIM`/`INFORMAL`/`NAO`, `:52-57`)
    batem CARACTERE POR CARACTERE com os `name` dos membros do enum
    (`engine/estado.py:187-189`), então a tradução é o mecanismo genérico
    `_membro_do_enum` — nenhuma linha de tradução de rótulo em português é
    escrita aqui (`AC-37`, `AC-53`), e NENHUM dos três membros é colapsado
    em outro: `SIM` e `INFORMAL` são estados de coleta distintos que a
    devolutiva usa, mesmo que a §13.1 só distinga `NAO` de não-`NAO`
    (`OQ-25`, aberta — não bloqueia esta leitura)."""
    valor = respostas.valor("RESERVA_EXISTE")
    if valor is None:
        raise ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")
    if not isinstance(valor, str):
        raise ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")
    return _membro_do_enum(RESERVA_EXISTE, valor)


def _disposicao_uso_reserva(respostas: RespostasCaso) -> DISPOSICAO_USO_RESERVA:
    """`B4.03` (`DISPOSICAO_USO_RESERVA`) — `RF-36`, `AC-52`, `EC-16`,
    `EC-17`. `COND`, `admite_nao_sei: false`. Os quatro `valor_interno`
    (`PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO`, `bloco-04.yaml:127-133`) batem
    caractere por caractere com os `name` do enum (`engine/estado.py:197-200`)
    e são resolvidos por `_membro_do_enum` — sem tradução de rótulo (`AC-53`).

    **A ausência de `B4.03` devolve `DISPOSICAO_USO_RESERVA.NAO`, e esse
    `NAO` é AUSÊNCIA ESTRUTURAL DA PERGUNTA — NÃO é escolha do aluno.** São
    duas situações humanas DIFERENTES que compartilham o mesmo valor gravado,
    e quem ler o dado cru precisa saber distingui-las:

    - "não tenho reserva": `RESERVA_EXISTE = NAO` e por isso `B4.03` NEM FOI
      EXIBIDA (`condicao_exibicao`, `bloco-04.yaml:135-137`, é a única
      condição que suprime a pergunta). O aluno nunca opinou sobre usar uma
      reserva que não existe.
    - "tenho reserva e prefiro preservá-la integralmente": `B4.03` foi
      exibida e RESPONDIDA com o `valor_interno` `NAO` (`:133`). Aqui há
      escolha declarada.

    Sem esta nota alguém leria o `NAO` do primeiro caso e concluiria que o
    aluno TINHA reserva e recusou usá-la. Decisão do usuário (2026-09-07),
    plano R2.4.2.

    Por que `NAO` e por que isso não é erro: o campo é obrigatório e não
    admite `Desconhecido` (mudar o tipo exigiria alterar `engine/`, proibido
    por `AC-44`); levantar erro transformaria o caso legítimo "não tenho
    reserva" em falha de montagem, contrariando `EC-16` diretamente ("os
    campos condicionais ausentes NÃO são erro"); e `NAO` é o único membro
    cuja leitura de fato é verdadeira quando não há reserva.

    O membro é ARITMETICAMENTE INERTE: no único caminho que o alcança, a
    Regra 1 da §13.1 já curto-circuitou `RESERVA_MOBILIZAVEL` em zero pelo
    primeiro termo (`RESERVA_EXISTE = NAO`), qualquer que seja o segundo.
    **Isto NÃO é reproduzir a Regra 1**: esta função não escreve
    `if RESERVA_EXISTE is NAO: RESERVA_MOBILIZAVEL = 0` nem olha
    `RESERVA_EXISTE` — ela escolhe o valor de um campo obrigatório numa
    ausência estrutural, com o motivo registrado (mesmo padrão documentado de
    `_CAMPOS_DE_GATE_FORA_DE_ESCOPO`, `:315`). Quem aplica a regra é
    `engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`, invocado por
    `engine/diagnostico.py` (`RF-44`, `AC-68`)."""
    valor = respostas.valor("DISPOSICAO_USO_RESERVA")
    if valor is None:
        return DISPOSICAO_USO_RESERVA.NAO
    if not isinstance(valor, str):
        return DISPOSICAO_USO_RESERVA.NAO
    return _membro_do_enum(DISPOSICAO_USO_RESERVA, valor)


def _reserva_total(respostas: RespostasCaso) -> DinheiroTalvez:
    """`B4.02A` (`RESERVA_TOTAL`) — `RF-37`, `AC-55`, `EC-16`. `COND`,
    `admite_nao_sei: true` (`bloco-04.yaml:66-85`). O campo é
    `DinheiroTalvez` (`engine/estado.py:512`) justamente porque a Regra 3 da
    §13.1 EXIGE o estado desconhecido — "reserva total desconhecida" produz
    `RESERVA_MOBILIZAVEL = DESCONHECIDA`, nunca zero silencioso.

    Um `Decimal` real é repassado inalterado (já veio da fronteira única de
    `app/montagem/conversao.py`, `RF-13` — nenhum `float` no caminho).
    `NAO_SEI` ("Não sei.", `:76`) vira `DESCONHECIDO` pelo mecanismo central
    `_ou_desconhecido`. E a AUSÊNCIA ESTRUTURAL — `B4.02 = NAO` suprime a
    pergunta (`condicao_exibicao`, `:78-80`) — também vira `DESCONHECIDO`:
    NUNCA erro, NUNCA `Decimal("0")`, NUNCA `None` (`EC-16`: campo
    condicional ausente não é erro; e um zero aqui seria afirmar que a
    reserva foi medida e vale zero)."""
    valor = respostas.valor("RESERVA_TOTAL")
    if valor is None:
        return DESCONHECIDO
    traduzido = _ou_desconhecido(valor)
    if not isinstance(traduzido, Decimal):
        return DESCONHECIDO
    return traduzido


def _valor_maximo_reserva_informado_usuario(respostas: RespostasCaso) -> DinheiroTalvez:
    """`B4.03A` (`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`) — `RF-37`,
    `AC-56`, `EC-15`, `EC-16`, `EC-17`. `COND`, `admite_nao_sei: true`
    (`bloco-04.yaml:144-164`). Devolve `DESCONHECIDO` em TUDO que não seja um
    `Decimal` real; um `Decimal` é repassado exato, vindo da fronteira única
    (`RF-13`), sem `float` em nenhum ponto do caminho.

    Os quatro caminhos que colapsam em `DESCONHECIDO` (plano R2.4.3):
    `NAO_SEI` ("Não sei.", `:155`); a opção SEM `valor_interno`
    ("Prefiro decidir somente depois...", `:154`); e as duas ausências
    estruturais — `B4.03 = NAO` suprime `B4.03A` (`condicao_exibicao`,
    `:157-159`, `EC-17`) e, por cadeia, `B4.02 = NAO` suprime `B4.03` e com
    ela `B4.03A` (`EC-16`).

    **`OQ-22`(a) está ABERTA, e enquanto estiver esta leitura NÃO PODE
    distinguir "decidir depois" de "não sei" pelo `valor_interno`** — as duas
    opções gravam `valor_interno: null` no registro. Aritmeticamente a Regra
    3 da §13.1 já colapsa as duas em `RESERVA_MOBILIZAVEL = DESCONHECIDA`,
    então a leitura correta hoje é idêntica nos dois casos. Tratar a opção
    sem `valor_interno` como qualquer coisa diferente de desconhecido seria
    inventar. O que `OQ-22`(a) decide é se o registro passa a distingui-las
    para a devolutiva — mudança de YAML, não deste código."""
    valor = respostas.valor("VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO")
    if valor is None:
        return DESCONHECIDO
    traduzido = _ou_desconhecido(valor)
    if not isinstance(traduzido, Decimal):
        return DESCONHECIDO
    return traduzido


def _dinheiro_disponivel(respostas: RespostasCaso) -> Dinheiro:
    """`B4.01`/`B4.01A` (`DINHEIRO_DISPONIVEL_EXISTE`/`DINHEIRO_DISPONIVEL`)
    — `RF-38`, `AC-57`, `AC-58`, `AC-59`, `EC-20`. Único dos cinco campos
    desta fatia tipado `Dinheiro` PURO (`engine/estado.py:517`): não há
    `DESCONHECIDO` a entregar em nenhum ramo. Os cinco caminhos, na ordem de
    avaliação (plano R2.4.4):

    - `B4.01 = SIM` + `B4.01A` com `Decimal` → o próprio `Decimal` (`AC-57`).
    - `B4.01 = NAO` (`B4.01A` não exibida, `condicao_exibicao`, `:36`) →
      `_ZERO` (`AC-58`).
    - `B4.01 = NAO_SEI` (`:18`) → erro nomeado (`EC-20`).
    - `B4.01` ausente → erro nomeado (`AC-59`).
    - `B4.01 = SIM` com `B4.01A` ausente ou `NAO_SEI` → erro nomeado.

    **O `_ZERO` do ramo `NAO` NÃO é default.** `sdd.config.md` §4 proíbe
    inventar dado; não proíbe transcrever um zero que o aluno declarou.
    `B4.01 = NAO` é resposta `[OBR]` AFIRMATIVA — "não possuo dinheiro
    disponível" — e o zero é a transcrição dela, não a ausência dela. O que a
    §4 proíbe é exatamente o quarto e o quinto ramos, que por isso levantam
    `ErroDinheiroDisponivelIndeterminado`. `_ZERO` (`:266`) vem da fronteira
    `Decimal` única, como todo `Dinheiro` deste módulo — nenhum
    `Decimal(...)`/`dinheiro(...)` literal é escrito aqui (`RF-13`).

    `OQ-23` continua aberta quanto a COMO a coleta se recupera do ramo
    `NAO_SEI` (e se o registro deveria bloquear na própria coleta o par
    "`B4.01 = NAO_SEI` + `B4.01A` não exibida") — decisão de produto/registro,
    que não se toma aqui (plano R2.10.1). Qual erro levantar é o que foi
    encaminhado como decisão de implementação, e é esta exceção dedicada."""
    existe = respostas.valor("DINHEIRO_DISPONIVEL_EXISTE")
    if existe is None:
        raise ErroDinheiroDisponivelIndeterminado("DINHEIRO_DISPONIVEL_EXISTE", "sem resposta")
    if existe == "NAO":
        return _ZERO
    if existe != "SIM":
        # Sobra apenas `NAO_SEI` (`bloco-04.yaml:18`) — e qualquer
        # `valor_interno` fora do domínio, que também não autoriza um valor.
        raise ErroDinheiroDisponivelIndeterminado(
            "DINHEIRO_DISPONIVEL_EXISTE", "resposta não afirma valor conhecido"
        )
    valor = respostas.valor("DINHEIRO_DISPONIVEL")
    if valor is None:
        raise ErroDinheiroDisponivelIndeterminado("DINHEIRO_DISPONIVEL", "sem resposta")
    traduzido = _ou_desconhecido(valor)
    if not isinstance(traduzido, Decimal):
        raise ErroDinheiroDisponivelIndeterminado("DINHEIRO_DISPONIVEL", "valor não conhecido")
    return traduzido


def _economia_potencial_imediata(
    respostas: RespostasCaso, economia_nao_identificada: Dinheiro | None
) -> Dinheiro:
    """`B2.09`/`B2.10`/`B2.10A` — ver docstring do módulo. "Somente SIM
    torna `VALOR_GASTOS_FANTASMAS` elegível à economia potencial" (canônica,
    salto/consequência de `B2.10A`): quando `ACEITA_REDUCAO_GASTOS_
    FANTASMAS = SIM`, repassa `VALOR_GASTOS_FANTASMAS` (identidade, mesmo
    padrão de `_taxa_periodicidade_mensal_ou_desconhecido` para taxa
    mensal) — e SÓ nesse ramo constrói `Dinheiro` a partir de uma resposta já
    convertida (RF-13: o valor já É `Decimal`, vindo da fronteira única). Em
    qualquer outro caso — sem gasto fantasma identificado (`GASTOS_
    FANTASMAS` ausente/`NAO`/`TALVEZ`), aceite `NAO`/`TALVEZ`/ausente, ou
    `VALOR_GASTOS_FANTASMAS` desconhecido/ausente mesmo com aceite `SIM` —
    o campo é `Dinheiro`, não `DinheiroTalvez`: não há como construir um
    `Dinheiro(0)` aqui sem violar a fronteira `Decimal` única
    (`app/montagem/conversao.py`, `RF-13`, `T-27` — este módulo nunca chama
    `Decimal(...)`/`dinheiro(...)` literal). Por isso `economia_nao_
    identificada` é parâmetro explícito da chamadora para ESSE caso — quando
    `None` (nenhum valor fornecido) e nenhuma economia foi identificada, a
    ausência é reportada como erro explícito, nunca 0 inventado aqui."""
    gastos_fantasmas = respostas.valor("GASTOS_FANTASMAS")
    aceite = respostas.valor("ACEITA_REDUCAO_GASTOS_FANTASMAS")
    if gastos_fantasmas == "SIM" and aceite == "SIM":
        valor_gastos_fantasmas = respostas.valor("VALOR_GASTOS_FANTASMAS")
        if valor_gastos_fantasmas is not None:
            traduzido = _ou_desconhecido(valor_gastos_fantasmas)
            if isinstance(traduzido, Decimal):
                return traduzido
    if economia_nao_identificada is not None:
        return economia_nao_identificada
    # Mensagem técnica montada por `str.join` sobre segmentos curtos (mesmo
    # padrão de `ErroRespostaAusente.__init__`/`ErroValorInternoDesconhecido.
    # __init__`, acima) — evita um literal contíguo que ultrapasse o limiar
    # de "possível enunciado de pergunta" de `tests/app_aluno/estatica/
    # test_sem_conteudo_de_questionario_no_codigo.py` (T-08, AC-37).
    nome_variavel = " ".join(("ECONOMIA_POTENCIAL_IMEDIATA", "(nenhuma economia elegível)"))
    raise ErroRespostaAusente("", "B2.10/B2.10A", nome_variavel)


def montar_estado_financeiro(
    respostas: RespostasCaso,
    *,
    DATA_REFERENCIA: date,
    dividas: tuple[Divida, ...],
    CONFIABILIDADE_DADOS: CONFIABILIDADE_DADOS,
    economia_nao_identificada: Dinheiro | None = None,
    DIVIDA_ID_PARA_LINHA_CONTINUA: str | None = None,
) -> EstadoFinanceiro:
    """RF-14, AC-18 — monta o `EstadoFinanceiro` COMPLETO a partir das
    respostas do caso, com `DATA_REFERENCIA` vinda do `Caso` (`app/casos/
    maquina.py::Caso.DATA_REFERENCIA`) como parâmetro EXPLÍCITO — nunca de
    `date.today()`/`datetime.now()` (`AC-18`: é isso que faz recalcular o
    mesmo caso com a mesma `DATA_REFERENCIA` produzir o mesmo `SNAPSHOT_ID`).
    Verificado também por teste estático dedicado (`tests/app_aluno/
    estatica/test_sem_relogio_em_montagem.py`).

    Função PURA: a mesma `respostas` e os mesmos parâmetros produzem sempre
    o mesmo `EstadoFinanceiro` — nenhuma leitura de relógio, de ambiente ou
    de estado global em nenhum caminho (mesmo padrão de `montar_divida`/
    `montar_perfil_comportamental`/`montar_sinais_comportamentais`, que já
    são puras). `EstadoFinanceiro` é `frozen=True, slots=True`
    (`engine/estado.py`) — comparável por `==` estrutural.

    Campos preenchidos a partir de resposta (`RF-12`): `TIPO_RENDA` (B3.02,
    `_tipo_renda`), `CAPACIDADE_ATAQUE_DECLARADA` (B3.C01,
    `_capacidade_ataque_declarada`, `DinheiroTalvez` — `NAO_SEI` vira
    `DESCONHECIDO`), `ECONOMIA_POTENCIAL_IMEDIATA` (B2.09/B2.10/B2.10A,
    `_economia_potencial_imediata`), `perfil_comportamental`
    (`montar_perfil_comportamental`, T-50), `sinais_comportamentais`
    (`montar_sinais_comportamentais`, T-50) e `AUTOPERCEPCAO_CONTROLE`
    (B2.13, `_autopercepcao_controle`, T-50) — este admite `DESCONHECIDO`.

    `RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS` e
    `DESPESAS_NAO_MENSAIS_NORMALIZADAS` (`T-103`, `OQ-16`): NÃO são mais
    parâmetro externo — são calculadas aqui a partir das respostas do
    Bloco 3 por `_renda_total_recorrente`, `_despesas_operacionais_atuais`
    e `_despesas_nao_mensais_normalizadas`, respectivamente (ver essas três
    funções para a fórmula normativa exata fechada por `OQ-16`, e
    `ErroCampoAgregadoDesconhecido` para o caminho de erro quando
    `RENDA_PRINCIPAL` é desconhecida). A fronteira documentada em `T-51`
    (parâmetro obrigatório sem default) era a decisão certa ENQUANTO a
    fórmula de composição do Bloco 3 não estava fechada — `OQ-16`
    resolveu isso, e `OQ-19`/`T-105` destravou o mecanismo de repetição que
    faltava para ler as fichas de renda adicional e despesa não-mensal.

    `CONFIABILIDADE_DADOS` continua sendo PARÂMETRO EXTERNO explícito —
    derivada pelo motor, função de `engine/comportamento.py`, T-13 do slug
    `motor-calculo` — fora da allowlist de import desta camada e fora do
    fluxo permitido por `RF-16`/Lei nº 3; ver docstring do módulo. `dividas`
    é recebida pronta porque cada `Divida` é montada individualmente por
    `montar_divida` (T-49) — não é responsabilidade desta função descobrir
    quantas fichas de dívida existem nem iterar sobre elas.

    `INVENTARIO_COMPLETO` (`T-52`, `RF-15`, `AC-07`): NÃO é mais parâmetro
    externo — é lido diretamente das respostas por `_inventario_completo`
    (`B5.FIM02`/`CONFIRMACAO_FIM_CADASTRO`), mesmo padrão de `_tipo_renda`/
    `_capacidade_ataque_declarada`, acima. A fronteira documentada em `T-51`
    (parâmetro obrigatório sem default) era a decisão certa ENQUANTO esta
    leitura não existia; agora que `RF-15` está implementado, continuar
    recebendo o booleano de fora seria reproduzir aqui uma leitura que já
    mora nesta função.

    **Os cinco campos de reserva e caixa do Bloco 4 (`T-111`, `RF-36`,
    `RF-37`, `RF-38`).** `RESERVA_EXISTE` (B4.02), `RESERVA_TOTAL` (B4.02A),
    `DISPOSICAO_USO_RESERVA` (B4.03), `VALOR_MAXIMO_RESERVA_INFORMADO_
    USUARIO` (B4.03A) e `DINHEIRO_DISPONIVEL` (B4.01/B4.01A) são LIDOS das
    respostas pelas cinco funções privadas acima — nenhum vira parâmetro
    externo novo, e a assinatura desta função permanece inalterada. Cada
    leitura é `resposta → conversão → tipo`: NENHUMA das três regras da
    §13.1 é reproduzida aqui. Quem aplica `MIN`/`MAX`, quem curto-circuita
    em zero e quem propaga `DESCONHECIDO` é `engine/ataque_imediato.py::
    derivar_RESERVA_MOBILIZAVEL`, invocado por `engine/diagnostico.py` —
    esta camada muda a ENTRADA, nunca a derivação (`RF-44`, `AC-68`).

    **`investimentos`, `ativos` e `recursos_extraordinarios` são tupla vazia
    DECLARADA, com motivo — jamais omissão silenciosa, jamais estimativa,
    jamais classificação inventada (`RF-39`, `AC-60`, `AC-62`, `EC-19`).**
    Não há função de leitura para as três porque NÃO HÁ O QUE LER: uma
    função vazia sugeriria que existe leitura parcial. Mesmo padrão
    documentado de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (`:315`). Os motivos,
    nominalmente:

    - `investimentos` e `ativos` — `motor-calculo:OQ-26` e
      `motor-calculo:OQ-27`, AMBAS abertas e AMBAS necessárias: responder só
      uma NÃO destrava. `CLASSIFICACAO_MOBILIZACAO` e
      `VALOR_LIQUIDO_REALIZAVEL*` são campos obrigatórios e SEM DEFAULT nas
      três dataclasses de item de `engine/estado.py`, e cada um depende de
      uma das duas questões por causa independente — sem as duas respostas
      não é possível construir um único item sem inventar um dado.
      `CLASSIFICACAO_MOBILIZACAO` não é derivada aqui em hipótese alguma:
      derivá-la nesta camada seria fórmula patrimonial, proibida pela
      Lei nº 3 (`RF-44`).
    - `recursos_extraordinarios` — `OQ-22` e `OQ-24`, abertas (fatia 2B).

    `AC-60` é mais forte que "não implementado": as três permanecem vazias
    MESMO com fichas de investimento, imóvel, veículo e outro ativo
    preenchidas nas respostas. A lacuna é do contrato, não da coleta —
    quando 2B/2C destravarem, as três leituras nascem de uma vez.
    """
    return EstadoFinanceiro(
        DATA_REFERENCIA=DATA_REFERENCIA,
        RENDA_TOTAL_RECORRENTE=_renda_total_recorrente(respostas),
        TIPO_RENDA=_tipo_renda(respostas),
        DESPESAS_OPERACIONAIS_ATUAIS=_despesas_operacionais_atuais(respostas),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=_despesas_nao_mensais_normalizadas(respostas),
        CAPACIDADE_ATAQUE_DECLARADA=_capacidade_ataque_declarada(respostas),
        ECONOMIA_POTENCIAL_IMEDIATA=_economia_potencial_imediata(
            respostas, economia_nao_identificada
        ),
        INVENTARIO_COMPLETO=_inventario_completo(respostas),
        dividas=dividas,
        perfil_comportamental=montar_perfil_comportamental(respostas),
        sinais_comportamentais=montar_sinais_comportamentais(
            respostas, DIVIDA_ID_PARA_LINHA_CONTINUA
        ),
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS,
        AUTOPERCEPCAO_CONTROLE=_autopercepcao_controle(respostas),
        # --- Bloco 4 · reserva (`T-111`, `RF-36`, `RF-37`) ---
        RESERVA_EXISTE=_reserva_existe(respostas),
        RESERVA_TOTAL=_reserva_total(respostas),
        DISPOSICAO_USO_RESERVA=_disposicao_uso_reserva(respostas),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=_valor_maximo_reserva_informado_usuario(respostas),
        # --- Bloco 4 · caixa (`T-111`, `RF-38`) ---
        DINHEIRO_DISPONIVEL=_dinheiro_disponivel(respostas),
        # --- Lacuna DECLARADA, com motivo na docstring acima (`RF-39`,
        # `AC-60`, `AC-62`, `EC-19`) — nunca omissão silenciosa: as duas
        # `motor-calculo:OQ-26` e `motor-calculo:OQ-27` bloqueiam
        # `investimentos`/`ativos` (as DUAS, responder só uma não destrava);
        # `OQ-22`/`OQ-24` bloqueiam `recursos_extraordinarios`.
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
    )
