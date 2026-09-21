# Discovery — `app-aluno`

| Campo | Valor          |
| ----- | -------------- |
| Slug  | `app-aluno`    |
| Data  | `2026-09-03`   |

## 1. Problema

O motor de cálculo está pronto e verificado (78/78 tarefas, três gabaritos
numéricos e cinco invariantes). Ele é uma função pura: recebe um
`EstadoFinanceiro` já montado em memória e devolve um `SnapshotOrdem`. Não
existe nada que produza aquela entrada nem nada que traduza aquela saída.

O problema, portanto, **não é construir "uma tela"**. É que o PIQ, como
método, é um *acompanhamento longitudinal* — e hoje só existe a peça que
calcula um instante dele.

Ler a seção 11 da canônica com atenção mostra que as "291 perguntas" não são
um formulário. São **cinco superfícies de interação distintas**, em momentos
diferentes da vida do aluno:

| Momento | Blocos | Natureza |
| --- | --- | --- |
| Diagnóstico inicial (Etapa B) | 1–5 (195 perguntas) | Coleta longa, com fichas repetíveis por dívida/despesa/vínculo/ativo |
| Processamento | 6 | **Nenhuma pergunta.** O motor roda entre a Etapa B e a Etapa D |
| Intervenção dirigida | 7, 8 (46 perguntas) | Abrem **somente** para as dívidas que o motor sinalizou, repetidas por `DIVIDA_ID` |
| Confirmação da recomendação | 10 (2 perguntas) | O aluno decide quanto do ataque recomendado aceita — condicionado a `ATAQUE_IMEDIATO_RECOMENDADO > 0` |
| Execução e acompanhamento | 11 (23 perguntas) | Explicitamente *"não é um questionário inicial"* — vinculado a `ACAO_ID`, ao longo de meses |

Isso reformula a dor de três maneiras que o briefing inicial não capturava:

**(a) O sistema não é um formulário que gera um PDF — é um ciclo.** O Bloco 11
reabre o Bloco 7, o Bloco 8 e até campos isolados do Bloco 5 (`B11.03-INF`:
*"Sim → abrir exclusivamente o campo que estava faltando (ex.: B5.B03,
B5.D01A)"*). Quitações e eventos materiais geram novos snapshots (`V-01`).
Um app que só faça "preencher → ver plano" atende ao primeiro dia e a nada
depois.

**(b) Parte do questionário é gerada pelo motor, não pela spec.** Em `B12.15`
o enunciado é *"O motor seleciona risco/sinal e apresenta: 'SE [sinal], ENTÃO
[resposta]'"*; em `B12.16`, *"O motor apresenta 2 ou 3 regras coerentes com o
caso"*. Existem perguntas cujas **opções são saída de cálculo**. Isso é mais
forte que "condicional composta": a camada de coleta depende do motor em
tempo de execução, não só de um grafo estático de regras de exibição.

**(c) O caminho até um plano útil é muito mais curto do que 291 perguntas.**
O contrato real do motor (`engine/estado.py::EstadoFinanceiro`) exige 13
campos no nível do caso e ~18 por dívida. Os demais ~250 campos coletados
alimentam relatório, narrativa comportamental, plano de ação e blindagem —
não o cálculo. Existe, portanto, um recorte legítimo em que o aluno responde
uma fração das perguntas e já obtém ordem de quitação, prazo e custo. Se esse
recorte é aceitável para o piloto é uma decisão de produto, não de engenharia
(`OQ-02`).

E há a restrição que reordena tudo: **`PEND-01` (LGPD) está ABERTO e bloqueia
coletar dado de pessoa real.** Consentimento, política de privacidade, prazo
de retenção e procedimento de exclusão não foram redigidos. A canônica é
explícita: *"não bloqueia especificar nem programar. Bloqueia coletar dado de
pessoa real"*, e adverte que, se ficar para o fim, *"o projeto chega com o
sistema pronto e sem poder ligar"*. A resposta honesta à pergunta que originou
este discovery — *"qual o próximo passo para o aluno ter isso na mão?"* — é
que existe um passo **não técnico** no caminho crítico, e ele já está
identificado há tempo.

## 2. Personas

| Persona | Objetivo | Contexto de uso |
| --- | --- | --- |
| **Aluno / servidor endividado** | Saber qual dívida atacar primeiro e conseguir executar o plano ao longo dos meses | Responde a coleta inicial longa, provavelmente em várias sessões, possivelmente com documentos em mãos (`DOCUMENTACAO_DISPONIVEL`, `FONTE_DADO`). Depois volta periodicamente para reportar ações, quitações e mudanças. Baixa familiaridade financeira presumida — a canônica cuida da redação das telas |
| **Revisor / especialista** | Conferir que o plano gerado faz sentido no caso concreto e liberar (ou barrar) o envio | Acessa uma fila de casos pendentes. Precisa ver o plano como o aluno verá **e** os dados que o produziram, para classificar erro em TEXTO, PARÂMETRO, DADO, REGRA, CÁLCULO ou UX (§25). No piloto, revisa 100% dos relatórios |
| **Operador do piloto** | Saber quem travou onde: quem parou no meio da coleta, quem espera revisão, quem não reporta execução há meses | Persona provável, não confirmada. O Bloco 11 pressupõe acompanhamento ativo ao longo do tempo; abandono silencioso é o modo de falha natural de um questionário de 291 perguntas (`OQ-07`) |

Observação: as três podem ser a **mesma pessoa** no piloto — o especialista
pode ser revisor e operador. Isso não elimina os papéis; muda apenas o custo
de separá-los em software (`OQ-03`).

## 3. Cenários de uso

- **Coleta inicial interrompida.** O aluno responde os Blocos 1–3, fecha o
  navegador e volta dois dias depois. Hoje não há onde salvar progresso
  parcial. Com 195 perguntas na Etapa B e fichas repetíveis por item, é o
  caso normal, não a exceção.
- **Inventário de dívidas com ficha repetível.** O Bloco 5 tem 55 das suas 58
  perguntas marcadas REP: o aluno cadastra dívida por dívida, cada uma com
  saldo, taxa, natureza da taxa, garantia, cobrança, documentação, peso
  emocional. Ao final, `B5.FIM02` pergunta se o inventário está completo — e
  *"≠ SIM → `INVENTARIO_COMPLETO` = falso → bloqueio global da Ordem
  Definitiva"*.
- **O aluno não sabe um número.** Saldo desconhecido, parcela desconhecida,
  taxa não indicada. O motor trata isso corretamente (`INFORMACAO_PENDENTE`,
  `GAB-03`) e nunca inventa valor. A interface precisa tornar "não sei" uma
  resposta de primeira classe, e depois explicar ao aluno por que o plano
  dele ficou provisório.
- **O motor abre uma intervenção.** Terminada a Etapa B, o Bloco 6 roda e
  qualificam-se dívidas para renegociação (Bloco 7) ou troca (Bloco 8). O
  aluno recebe perguntas que **não existiam** antes de o motor rodar,
  dirigidas a dívidas específicas.
- **Revisão antes do envio.** Gerado o plano, ele entra em fila. O revisor
  confere e libera. Só então o aluno vê. Hoje: não existe fila, nem
  visualização, nem registro de quem liberou o quê.
- **Execução, meses depois.** O aluno tentou renegociar. `B11.01` pergunta o
  status da ação; se concluída com proposta, reabre `B7.05–B7.16`. Se ele
  quitou uma dívida, `B11.Q01–Q06` confirmam — e quitação confirmada é
  gatilho de recálculo (`R-01`), gerando novo snapshot.
- **Ataque imediato parcialmente aceito.** O motor recomenda usar R$ X de
  recurso disponível; o aluno aceita R$ Y < X (`B10.C01A`). O plano é
  recalculado sobre o valor aceito. A canônica proíbe perguntar *qual* dívida
  recebe o recurso — *"a ordem é do motor"*.

## 4. Restrições

**Técnicas**

- O motor é função pura, sem I/O, já verificada. Esta feature **consome**
  `calcular_plano(...)`; não altera `engine/` para caber na interface.
- Como o motor será exposto (import em processo ou serviço HTTP) está
  explicitamente em aberto — o plano do motor registra *"consumirão
  `calcular_plano(...)` em processo, ou via FastAPI — a definir no slug"*.
- A coleta deve ser **gerada** a partir dos registros da seção 11, não
  codificada pergunta a pergunta: nova versão do questionário tem que ser
  edição de registro, não reescrita de código. IDs (`B5.D03A`) são estáveis e
  **nunca reaproveitados**.
- A geração precisa comportar: ficha repetível por `DIVIDA_ID`/`MARGEM_ID`/
  item de despesa; condicional composta entre blocos (`B12.08` depende de
  quatro origens diferentes); texto dinâmico; validação cruzada
  (`VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM`); e **opções produzidas pelo
  motor** (`B12.15`, `B12.16`).
- `Decimal` nunca atravessa `float` em nenhuma fronteira nova (`RF-12`). O
  motor recusa `float` em tempo de construção (`_recusar_float`), então toda
  entrada vinda de formulário HTML precisa ser convertida com cuidado na
  borda.
- Toda saída carimba `ENGINE_VERSION`/`PARAMETROS_VERSION` (`V-03`), e
  snapshots são append-only (`V-01`, garantido no banco por `REVOKE` +
  trigger).
- Redações canônicas obrigatórias no que o aluno vê — `Q-03` fixa título e
  texto da ordem projetada, e a palavra é sempre *"projetada"* (`Q-02`).

**Negócio / metodologia**

- **Revisão humana de 100% dos relatórios no piloto** (`PEND-06`,
  `sdd.config.md` §6). Note a distinção: o motor já emite
  `REVISAO_HUMANA_OBRIGATORIA` como campo, mas isso é o caso *metodológico*
  estreito de `S-04` (incompatibilidade comportamental grave sem alternativa
  próxima). A regra do piloto é uma **política de processo mais ampla** —
  todo relatório passa, mesmo com o campo em `False`. São dois mecanismos
  diferentes com nomes parecidos; confundi-los produziria um sistema que
  revisa só uma fração dos casos.
- **Google Forms puro está descartado** (§15.1). A canônica **recomenda**
  Sheets + Apps Script + Docs→PDF (§15.2), mas isso é recomendação de
  viabilidade, não trava metodológica — a §15 abre dizendo que as restrições
  *"decorrem da especificação, não de preferência de ferramenta"*. Um app web
  dedicado é alternativa legítima; a escolha pertence ao Plan (`OQ-01`).
- **Nenhuma decisão metodológica se resolve implementando.** Ambiguidade na
  tradução do snapshot para linguagem de aluno vira pergunta, não decisão de
  desenvolvedor.

**Legais / compliance**

- `PEND-01` **ABERTO — bloqueia piloto**: falta texto de consentimento,
  política de privacidade, prazo de retenção e procedimento de exclusão.
  Bloqueia coletar dado de pessoa real; não bloqueia construir.
- `PEND-01` também exige decidir **onde os dados residem e quem acessa a
  base** — o que condiciona o desenho de autenticação e persistência desta
  feature, hoje apoiada num Supabase compartilhado com outros sistemas.
- Os dados são sensíveis por natureza: dívidas, renda, contracheque,
  negativação, cobrança judicial, patrimônio familiar.

## 5. Definição de sucesso

- **Um aluno-piloto conclui a coleta inicial sem suporte manual** (sem
  planilha, WhatsApp ou e-mail para contornar limitação da interface) — hoje:
  impossível, não há interface; meta: 1 aluno completo, ponta a ponta.
- **100% dos planos do piloto passam por revisão humana registrada antes do
  envio**, com autor e data — hoje: fila inexistente; meta: nenhum envio sem
  registro de liberação.
- **Um ciclo completo de execução é fechado**: aluno recebe o plano, executa
  ao menos uma ação do `ORDEM_ACOES`, reporta o resultado (Bloco 11) e o
  sistema produz um segundo snapshot a partir disso — hoje: 0; meta: 1. Este
  é o sinal que separa "gerou um PDF" de "o método está rodando".
- **Retomada de coleta funciona**: um aluno que abandona no meio volta e
  continua de onde parou, sem redigitar.
- **Nenhum valor inventado**: toda resposta "não sei" chega ao motor como
  desconhecido e o plano resultante declara-se provisório quando for o caso
  (`GAB-02`, `GAB-03`). Verificável contra os próprios gabaritos.

## 6. Riscos e incógnitas

| Incógnita | Impacto se der errado | Como reduzir |
| --- | --- | --- |
| `PEND-01` (LGPD) resolvido tarde | Sistema pronto e impedido de ligar — risco que a própria canônica já registra por escrito | Dono e prazo definidos agora, correndo em paralelo, fora do caminho crítico técnico |
| Abandono do aluno no meio de 195 perguntas | O piloto não gera nenhum caso completo, e não se aprende nada sobre o método | Medir onde o abandono ocorre; avaliar recorte mínimo (`OQ-02`); salvar progresso desde o início |
| Tratar as 291 perguntas como um formulário único | Arquitetura que não comporta Bloco 7/8 dirigido pelo motor, nem Bloco 11 longitudinal — retrabalho estrutural | Desenhar desde a spec como máquina de estados por caso, não como wizard linear |
| Renderizador "quase" gerado, com atalhos manuais nos pontos difíceis | Nova versão do questionário vira reescrita de código, violando exigência explícita da §11 | Provar no Plan que ficha repetível, condicional composta e opções vindas do motor cabem no gerador — não codificar exceções |
| Revisão humana encaixada depois | Retrabalho estrutural; ou pior, primeiro envio a aluno real sem revisão | Fila como requisito de primeira classe na spec, não adendo |
| Confundir `REVISAO_HUMANA_OBRIGATORIA` (campo, caso `S-04`) com a política de revisar 100% no piloto | Sistema revisaria só uma fração dos casos, violando `PEND-06` sem ninguém perceber | Nomear os dois mecanismos distintamente já na spec |
| Conversão de formulário HTML para `Decimal` feita de forma descuidada | `float` atravessa a fronteira e corrompe precisão; o motor recusa em runtime, mas o erro aparece tarde | Fronteira de conversão única e testada, espelhando `persistencia/` |
| Supabase free tier pausa após ~7 dias sem atividade | Piloto de baixo volume pode encontrar o banco pausado justamente entre um acesso e outro do aluno | Dimensionar conforme `OQ-06`; considerar tier pago antes do piloto |

## 7. Perguntas abertas

| ID | Pergunta | Por que importa | Impacto |
| --- | --- | --- | --- |
| `OQ-01` | Arquitetura: seguir a recomendação da canônica (§15.2 — Sheets + Apps Script + Docs→PDF) ou construir aplicação web dedicada (front-end + API + banco), como indicado no briefing? Ou um híbrido — coleta web dedicada, revisão/relatório em Docs? | Decide stack, hospedagem, esforço e prazo de tudo que vem depois. São caminhos genuinamente distintos, não variação de detalhe. A canônica recomenda o primeiro por viabilidade rápida; o briefing pede o segundo | **alto** |
| `OQ-02` | O piloto exige a coleta completa (291 perguntas) ou é aceitável um recorte que alimente só o motor (13 campos + ~18 por dívida) e produza ordem, prazo e custo, deixando narrativa comportamental e blindagem para depois? | Diferença entre um piloto em semanas e um em meses — e entre um aluno que conclui e um que abandona. **É decisão metodológica, não de engenharia: só o especialista pode responder** | **alto** |
| `OQ-03` | Quem revisa no piloto, e são quantas pessoas? O especialista sozinho, uma equipe, ou papéis separados (revisor ≠ operador)? | Define se a fila precisa de papéis, permissões e atribuição, ou se um único revisor implícito resolve | **alto** |
| `OQ-04` | Um recálculo posterior (quitação real, evento material) também passa por revisão humana obrigatória, ou só o primeiro envio? | `sdd.config.md` §6 e `PEND-06` dizem "100% dos relatórios" sem distinguir. Como o Bloco 11 gera recálculos com frequência, a resposta muda o volume de trabalho do revisor de "uma vez por aluno" para "toda vez que algo acontece" | **alto** |
| `OQ-05` | Existe autenticação nesta fase, ou link único por aluno basta? Se há acompanhamento longitudinal (Bloco 11) por meses, o aluno precisa voltar de outro dispositivo? | Login multi-tenant é esforço significativamente maior; mas link único envelhece mal num acompanhamento de meses. Interage com `PEND-01` (quem acessa a base) | **alto** |
| `OQ-06` | Quantos alunos no piloto, e em que janela — 1, 5, 50? Simultâneos ou em série? | Dimensiona infra (o Supabase atual pausa após ~7 dias ociosos) e decide se concorrência e isolamento por aluno precisam de tratamento real já | **médio** |
| `OQ-07` | O operador precisa de um painel para ver quem travou onde (coleta incompleta, aguardando revisão, sem reportar execução)? | Define se entra uma terceira persona no escopo ou fica para depois. Com acompanhamento longitudinal, abandono silencioso é o modo de falha esperado | **médio** |
| `OQ-08` | Quando o aluno responde "não sei" a algo material, ele é avisado na hora ("isso deixará seu plano provisório") ou só descobre no relatório final? | Afeta a experiência numa coleta longa e a complexidade da camada de coleta — avisar na hora exige avaliar impacto durante o preenchimento, não só ao final | **médio** |
| `OQ-09` | O aluno recebe o plano dentro do app (tela) ou como documento entregue (PDF/e-mail)? Ou ambos? | A canônica assume relatório documental (template Docs → PDF); o briefing sugere tela. Muda o que a fila de revisão libera — uma página ou um arquivo — e como o carimbo de versão aparece | **médio** |

> Discovery levanta o problema. Não decide a solução aqui — isso é a spec.

---
---

# Discovery — Rodada 2: leitura do Bloco 4 para reserva, caixa e patrimônio (resposta a `OQ-37`)

| Campo | Valor |
| ----- | ----- |
| Slug afetado | `app-aluno` (Rodada 1 `104/107`, com `T-77`/`T-78`/`T-79` pendentes — esta é a segunda rodada) |
| Data | `2026-09-07` |
| Origem do pedido | Conclusão da **Rodada 3 do slug `motor-calculo`** (24/24 tarefas), que implementou as regras canônicas de Ataque Imediato e Reserva (documento PIQ v1.0.1, transcrito em `specs/motor-calculo.spec.md` §13) |
| Motivo | A Rodada 3 entregou um **contrato de entrada novo**: `EstadoFinanceiro` ganhou 8 campos obrigatórios que `app/montagem/estado.py` não preenche. Isso é a `OQ-37`, registrada em `specs/motor-calculo.discovery.md` §12.3 e marcada lá como desbloqueada |
| Estado hoje | `build` **falha** com 1 erro; suíte de `tests/app_aluno/` com ~129 falhas de causa raiz única |
| Numeração | Questões novas seguem a série local do slug: `specs/app-aluno.spec.md` §10 encerra em `OQ-19` (linha `:501`), logo esta rodada abre em **`OQ-20`** |

## 0. O que exatamente quebrou

`engine/estado.py:453-536` — `EstadoFinanceiro` passou de 13 para **21 campos**.
Os 8 novos (`:511-528`) são obrigatórios e **sem default**, por decisão explícita
de mitigação de risco registrada na própria docstring (`:485-489`): os nove campos
da §13 entraram numa leva só porque `EstadoFinanceiro` compõe
`SnapshotOrdem.estado_inputs`, que alimenta `hash_inputs` — "uma leva, uma mudança
de hash".

`app/montagem/estado.py:1326-1344` constrói `EstadoFinanceiro` com exatamente os
13 campos antigos. Daí o **único** erro de `build`:

```
app\montagem\estado.py:1326: error: Missing positional arguments "RESERVA_EXISTE",
"RESERVA_TOTAL", "DISPOSICAO_USO_RESERVA", "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",
"DINHEIRO_DISPONIVEL", "investimentos", "ativos", "recursos_extraordinarios"
in call to "EstadoFinanceiro"  [call-arg]
```

O mesmo defeito em runtime é `TypeError: EstadoFinanceiro.__init__() missing 8
required positional arguments`, e é o que derruba ~129 testes de
`tests/app_aluno/`. **Não são 129 defeitos**: é um defeito com 129 sintomas —
`montar_estado_financeiro` é o caminho comum de praticamente toda a suíte da
aplicação (fixture compartilhada em `tests/app_aluno/fixtures/caso_completo.py`,
mais os dois arquivos que constroem `EstadoFinanceiro` na mão,
`tests/app_aluno/test_conversao_decimal.py:300` e
`tests/app_aluno/test_plano_ec07_ec08_ec09.py:347`).

**O app do aluno não monta estado.** Esta é a rodada que o faz voltar a montar.

## 1. A tentativa mecânica e por que ela foi revertida — o achado que define a rodada

Preencher os 8 campos com valores neutros é trivial em aparência e **quebra a
arquitetura na prática**. Foi tentado, e falhou em:

```
tests/app_aluno/estatica/test_fronteira_import_engine.py::
    test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41
```

A edição foi **revertida integralmente**. A causa é que `RESERVA_EXISTE` e
`DISPOSICAO_USO_RESERVA` são enums que vivem em `engine/estado.py`
(`:181` e `:192`), e `engine.estado` é liberado **símbolo a símbolo** na
allowlist de `AC-41` — não por inteiro.

### 1.1. Verificação própria do levantamento de `T-116`

O pedido mandou conferir os dois pontos do levantamento feito na sinalização de
`motor-calculo`. **Ambos conferem**, e um deles com uma ressalva relevante.

**Ponto 1 — `engine.tipos` já é liberado por inteiro: CONFERE.**
`tests/app_aluno/estatica/test_fronteira_import_engine.py:151-156` define
`MODULOS_LIBERADOS_POR_INTEIRO = {"engine.tipos", "engine.precisao"}`, e
`_nome_liberado` (`:170-178`) aceita qualquer nome com esse prefixo. Como
`CLASSIFICACAO_MOBILIZACAO` está em `engine/tipos.py:173` e `Desconhecido` em
`engine/tipos.py`, **nenhum dos dois exige decisão de allowlist**. Confirmado por
uso real: `app/motor/executor.py:215` e `app/eventos/mapeamento.py:74` já importam
de `engine.tipos` sem constar da allowlist nominal.

**Ponto 2 — faltam exatamente sete nomes de `engine.estado`: CONFERE.**
Confrontando o `NOMES_PERMITIDOS_DE_ENGINE` (`:103-144`) com o que a montagem
precisaria construir:

| Nome | Onde vive | Está na allowlist? |
| --- | --- | --- |
| `RESERVA_EXISTE` | `engine/estado.py:181` | **não** |
| `DISPOSICAO_USO_RESERVA` | `engine/estado.py:192` | **não** |
| `ItemInvestimento` | `engine/estado.py:349` | **não** |
| `ItemAtivo` | `engine/estado.py:376` | **não** |
| `RecursoExtraordinario` | `engine/estado.py:399` | **não** |
| `JANELA_RECURSO_EXTRAORDINARIO` | `engine/estado.py:203` | **não** |
| `CERTEZA_RECURSO_EXTRAORDINARIO` | `engine/estado.py:216` | **não** |

São sete, como levantado. **Mas eles não são todos da mesma natureza**, e essa é
a parte que o levantamento não separou.

### 1.2. Os sete não são iguais — leitura dos comentários que justificam a allowlist

O arquivo de teste é incomum: cada entrada liberada carrega prosa explicando o
critério. Lendo `:47-102` inteiro, extraem-se **dois critérios distintos** já
praticados:

**Critério A — "é enum/tipo que COMPÕE um tipo de entrada já liberado".**
Usado para `TIPO_DIVIDA` (`:54-61`), os 8 enums do Bloco 2 mais
`PerfilComportamental`/`SinaisComportamentais`/`JANELA_NOVA_DIVIDA` (`:62-72`) e
`TIPO_RENDA` (`:73-78`). A formulação é sempre a mesma: *"sem este nome era
IMPOSSÍVEL montar uma `Divida` tipada fora de `engine/`"*, *"sem liberá-lo é
impossível montar um `EstadoFinanceiro` tipado fora de `engine/`"*.

**Critério B — "é tipo de DADO já produzido pelo motor, não função de cálculo".**
Usado para `ErroInvariante` (`:84-91`) e `AcaoRequerida` (`:92-102`). A prosa de
`AcaoRequerida` é explícita sobre a fronteira: *"`AcaoRequerida` é uma dataclass
de dados que o motor já produziu, não uma função de gate — lê-la não é 'calcular'
(Lei nº 3)"*.

Aplicando os critérios aos sete:

| Nome | Critério que se aplica | Precedente idêntico |
| --- | --- | --- |
| `RESERVA_EXISTE` | **A** — tipa `EstadoFinanceiro.RESERVA_EXISTE` (`engine/estado.py:511`) | `TIPO_RENDA` (`:73-78`), literalmente o mesmo caso |
| `DISPOSICAO_USO_RESERVA` | **A** — tipa `EstadoFinanceiro.DISPOSICAO_USO_RESERVA` (`:513`) | `TIPO_RENDA` |
| `JANELA_RECURSO_EXTRAORDINARIO` | **A** — tipa campo de `RecursoExtraordinario` (`:418`) | `TIPO_DIVIDA` compõe `Divida` |
| `CERTEZA_RECURSO_EXTRAORDINARIO` | **A** — tipa campo de `RecursoExtraordinario` (`:419`) | `TIPO_DIVIDA` |
| `ItemInvestimento` | **A**, um nível acima — é o tipo do ELEMENTO de `EstadoFinanceiro.investimentos` (`:526`) | `Divida`, elemento de `EstadoFinanceiro.dividas`, já liberado |
| `ItemAtivo` | **A** — elemento de `EstadoFinanceiro.ativos` (`:527`) | `Divida` |
| `RecursoExtraordinario` | **A** — elemento de `.recursos_extraordinarios` (`:528`) | `Divida` |

**Veredito da análise: os sete caem todos no Critério A, e nenhum é de natureza
diferente.** Nenhum é função, nenhum é gate, nenhum é módulo interno de cálculo.
Todos são dataclass de entrada ou enum que tipa um campo de dataclass de entrada
— exatamente a categoria que a allowlist já abriu quatro vezes (`TIPO_DIVIDA`,
os 8 do Bloco 2, `TIPO_RENDA`, `Divida`).

Há inclusive um precedente textual de que a ampliação é o procedimento previsto,
não uma exceção: o comentário de `:70-72` diz que `Oportunidade` fica fora e
*"deve ser adicionada pelo mesmo critério quando uma tarefa futura a consumir"*.
A allowlist foi desenhada para crescer sob critério, não para ser imutável.

**Mesmo assim, isto NÃO é decidido aqui.** Ampliar a allowlist de `AC-41` é
mudar um critério de aceite da spec deste slug, e `sdd.config.md` §6 é claro. O
que este discovery entrega é o levantamento com o critério explicitado e o
precedente citado; a decisão é `OQ-20`.

## 2. Mapa pergunta → campo, um a um

Verificação própria em `collection/registros/bloco-04.yaml` e
`bloco-03.yaml`. Achado geral favorável: **a matéria-prima da reserva e do caixa
está completa e alinhada**; a de patrimônio, não.

### 2.1. Reserva e caixa — prontos, inclusive `valor_interno` casando com o enum

| Campo de `EstadoFinanceiro` | Pergunta | Linha | Estado |
| --- | --- | --- | --- |
| `DINHEIRO_DISPONIVEL` | `B4.01A` | `bloco-04.yaml:35` | pronto (`MOEDA`, `admite_nao_sei: false`) |
| `RESERVA_EXISTE` | `B4.02` | `:58` | pronto — `valor_interno`: `SIM`/`INFORMAL`/`NAO` (`:52-57`) |
| `RESERVA_TOTAL` | `B4.02A` | `:77` | pronto (`MOEDA`, `admite_nao_sei: true`) |
| `DISPOSICAO_USO_RESERVA` | `B4.03` | `:134` | pronto — `valor_interno`: `PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO` (`:127-133`) |
| `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` | `B4.03A` | `:156` | quase — ver `OQ-21` |

Dois achados de verificação que valem registro explícito:

1. **`OQ-24` do slug `motor-calculo` já foi aplicada ao YAML.**
   `bloco-04.yaml:156` grava `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, não mais
   `RESERVA_MOBILIZAVEL`. A colisão de nome que aquele discovery apontou está
   resolvida no registro. Nada a fazer aqui.
2. **Os `valor_interno` batem caractere por caractere com os `name` dos enums.**
   `RESERVA_EXISTE.SIM`/`INFORMAL`/`NAO` (`engine/estado.py:187-189`) ↔ `:52-57`;
   `DISPOSICAO_USO_RESERVA.PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO`
   (`engine/estado.py:197-200`) ↔ `:127-133`. Isso significa que o mecanismo
   genérico `_membro_do_enum` (`app/montagem/estado.py:410`) resolve os dois sem
   nenhuma cadeia de `if` — mesmo padrão dos 7 enums do Bloco 2 descrito em
   `app/montagem/estado.py:111-122`.

**A exceção é `B4.03A`.** Suas três opções (`bloco-04.yaml:152-155`) são:

```yaml
- {rotulo: "R$ ______", valor_interno: null}
- {rotulo: Prefiro decidir somente depois de ver a análise., valor_interno: null}
- {rotulo: Não sei., valor_interno: null, admite_nao_sei: true}
```

A terceira tem `admite_nao_sei: true` e vira `DESCONHECIDO` pelo mecanismo já
existente (`_ou_desconhecido`, `app/montagem/estado.py:370`). **A segunda não
tem nada**: nem `valor_interno`, nem `admite_nao_sei`. É um terceiro estado
sem representação. Este é exatamente o estado que `OQ-25` de `motor-calculo`
levantou ("prefiro decidir depois" ≠ "não sei") e deixou aberto, e ele agora
chega na camada que precisa traduzi-lo. Ver `OQ-21`.

### 2.2. Recursos extraordinários — o registro não mapeia para o enum

| Campo de `RecursoExtraordinario` | Pergunta | Linha | Estado |
| --- | --- | --- | --- |
| `VALOR_RECURSO_EXTRAORDINARIO` | `B3.05B` | `bloco-03.yaml:266` | pronto (`MOEDA`) |
| `JANELA_RECURSO_EXTRAORDINARIO` | `B3.05C` | `:290` | **quebrado** — ver abaixo |
| `CERTEZA_RECURSO_EXTRAORDINARIO` | `B3.05D` | `:312` | pronto — `CONFIRMADO`/`PROVAVEL`/`POSSIVEL` (`:309-311`) |
| `ITEM_ID` | — | — | não existe pergunta; é identificador de sistema |

`B3.05C` (`bloco-03.yaml:284-289`) tem as cinco opções com **`valor_interno:
null` em todas**:

```yaml
- {rotulo: Próximos 30 dias, valor_interno: null}
- {rotulo: 1–3 meses, valor_interno: null}
- {rotulo: 4–6 meses, valor_interno: null}
- {rotulo: 7–12 meses, valor_interno: null}
- {rotulo: Ainda não sei, valor_interno: null, admite_nao_sei: true}
```

O enum `JANELA_RECURSO_EXTRAORDINARIO` (`engine/estado.py:203-213`) tem
`ATE_30D`, `UM_A_TRES_MESES = "1_3M"`, `QUATRO_A_SEIS_MESES = "4_6M"`,
`SETE_A_DOZE_MESES = "7_12M"`, `NAO_SEI`. **Não há como mapear rótulo em
português para membro de enum sem escrever a tradução em código** — e traduzir
rótulo no código de `app/` é precisamente o que `AC-37`
(`tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`)
proíbe. Este é o mesmo tipo de lacuna de registro que `OQ-19` resolveu para
`escopo_repeticao`, agora em `valor_interno`. Ver `OQ-22`.

Note também que `ATE_30D` é o **único** membro que a §13.3 qualifica como
"momento atual" (`engine/estado.py:209`) e `CONFIRMADO` o único que satisfaz
"confirmado" (`:220`) — errar esse mapeamento não produz erro de tipo, produz
um número silenciosamente errado no ataque imediato.

### 2.3. Investimentos e ativos — o registro é rico, o contrato é estreito

| Campo de `ItemInvestimento` | Pergunta candidata | Linha | Estado |
| --- | --- | --- | --- |
| `ITEM_ID` | — | — | identificador de sistema (ver §3) |
| `VALOR_LIQUIDO_REALIZAVEL` | `B4.04B` (`VALOR_ESTIMADO_ATIVO`) menos `B4.06A` (`CUSTO_DESMOBILIZACAO_INVESTIMENTOS`) | `:222`, `:286` | **fórmula é `OQ-27` de `motor-calculo`, ABERTA** |
| `POSSUI_LIQUIDEZ` | `B4.05` (`LIQUIDEZ_INVESTIMENTOS`, domínio `D0/D1/D7/D30/MAIS_30/BLOQUEADO`) | `:246` | corte não publicado — qual valor é "com liquidez"? |
| `CLASSIFICACAO_MOBILIZACAO` | **nenhuma** — proibido perguntar | — | **`OQ-26` de `motor-calculo`, ABERTA** |

| Campo de `ItemAtivo` | Pergunta candidata | Linha | Estado |
| --- | --- | --- | --- |
| `ITEM_ID` | — | — | identificador de sistema |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | `B4.I03`/`B4.V03`/`B4.O03` (valor) menos `B4.I04A`/`B4.V04A`/`B4.O04A` (passivo) menos `B4.I09`/`B4.V09`/`B4.O09` (custos) | `:363`, `:400`, `:516`; `:570`, `:605`, `:772`; `:833`, `:868`, `:960` | **`OQ-27`, ABERTA** |
| `CLASSIFICACAO_MOBILIZACAO` | **nenhuma** | — | **`OQ-26`, ABERTA** |

Achado relevante que o pedido não antecipava: **`ItemAtivo` é uma única coleção
para três famílias de ficha diferentes** — imóvel (`B4.I01`+), veículo
(`B4.V01`+, `bloco-04.yaml:525-772`) e outro ativo (`B4.O01`+, `:781-960`). Cada
família tem seu próprio conjunto de perguntas, com nomes de variável
distintos e um `VARIAVEL_GRAVADA` que carrega a família entre parênteses
(`"VALOR_IMOVEL (= VALOR_ESTIMADO_ATIVO)"`, `:363`;
`"VALOR_VEICULO (= VALOR_ESTIMADO_ATIVO)"`, `:570`;
`"VALOR_ESTIMADO_ATIVO (outro)"`, `:833`). Nenhuma leitura existente deste slug
lida com "três famílias de ficha alimentando uma coleção só". Ver `OQ-24`.

## 3. O mecanismo de repetição — investigado, e ele NÃO serve como está

O pedido pediu para investigar se o mecanismo destravado por `OQ-19`/`T-105`
serve para investimento/ativo. **Não serve, por duas razões independentes, e a
segunda é mais grave que a primeira.**

### 3.1. Razão 1 — o Bloco 4 inteiro está com `escopo_repeticao: NENHUM`

Varredura própria em `collection/registros/bloco-04.yaml`: **todas** as
perguntas marcadas `obrigatoriedade: [COND, REP]` declaram
`escopo_repeticao: NENHUM`. Verificado item a item nas fichas de investimento
(`:190-191`, `:217-218`, `:236-237`, `:261-262`, `:280-281`, `:300-301`), de
imóvel (`:336-337`, `:358-359`, `:377-378`, `:395-396`, `:414-415`, `:431-432`,
`:450-451`, `:468-469`, `:488-489`, `:510-511`), de veículo (`:546-547`,
`:565-566`, `:582-583`, `:600-601`, `:619-620`, `:636-637`, `:659-660`,
`:681-682`, `:702-703`, `:725-726`, `:747-748`, `:766-767`) e de outro ativo
(`:807-808`, `:828-829`, `:845-846`, `:863-864`, `:880-881`, `:897-898`,
`:914-915`, `:932-933`, `:954-955`). O mesmo vale para os recursos
extraordinários do Bloco 3 (`bloco-03.yaml:261-262`, `:282-283`, `:306-307`).

Isto é **exatamente** a situação que `OQ-19` descreveu para `B3.03A-C` e
`B3.NM02A-D`: a canônica diz REP, o registro diz `NENHUM`, e
`RespostasCaso.valores_do_escopo` (`collection/respostas.py:114`) exige um
`EscopoRepeticao` real. `EscopoRepeticao` (`collection/registro.py:62-79`) tem
oito membros e **nenhum** cobre investimento, imóvel, veículo ou outro ativo.

A diferença de escala em relação a `OQ-19` é grande: aquela precisou de dois
membros novos para duas famílias; esta precisa de **quatro ou cinco** (ou de
uma decisão de agrupar famílias num escopo só), mais os prefixos correspondentes
em `PREFIXO_POR_ESCOPO` (`collection/repeticao.py:59-67`).

### 3.2. Razão 2 — `valores_do_escopo` não filtra por escopo (o achado mais delicado desta seção)

`collection/respostas.py:114-128`, lido na íntegra, tem esta docstring:

> `escopo` **não é usado para filtrar aqui**: a filtragem por escopo já ocorreu
> na formação de `self.respostas` pelo chamador (o item_id por si é a unidade),
> mas o parâmetro é mantido para satisfazer o `Protocol` de
> `collection/condicoes.py`.

E a implementação confirma — o filtro é `if nome_variavel == variavel and
item_id != ""`. **A separação entre escopos hoje é feita pelo nome da variável,
não pelo escopo.** Isso funcionou até agora porque cada escopo usa nomes de
variável distintos (`RENDA_RECORRENTE_ADICIONAL` só existe em fichas de renda;
`VALOR_DESPESA` só em fichas de despesa — ver a justificativa explícita em
`app/montagem/estado.py:1085-1095`).

**Investimentos e ativos quebram essa premissa.** `VALOR_ESTIMADO_ATIVO` aparece
como `VARIAVEL_GRAVADA` em quatro lugares — `B4.04B` (investimento, `:222`),
`B4.I03` (imóvel, `:363`), `B4.V03` (veículo, `:570`) e `B4.O03` (outro,
`:833`) — e `SALDO_PASSIVO_VINCULADO` em três (`:400`, `:605`, `:868`), e
`CUSTOS_ESTIMADOS_DESMOBILIZACAO` em três (`:516`, `:772`, `:960`). Uma
chamada a `valores_do_escopo(ESCOPO_IMOVEL, "VALOR_ESTIMADO_ATIVO")` devolveria
**também** os veículos e os investimentos.

Isso não é um detalhe de implementação a resolver no plano: é a diferença entre
somar o patrimônio certo e somar o patrimônio três vezes — e a §13.8 do
documento canônico veda exatamente dupla contagem por origem econômica. Ver
`OQ-23`, que é decisão técnica nossa, mas **precisa ser decidida antes de
qualquer linha de leitura de item**.

## 4. `CLASSIFICACAO_MOBILIZACAO` — a amarração, e o veredito

Este é o ponto que o pedido mandou investigar com cuidado. A amarração é real,
é tripla, e **se fecha**.

**Lado 1 — o item não pode ser construído sem classificação.**
`ItemInvestimento.CLASSIFICACAO_MOBILIZACAO` (`engine/estado.py:369`) e
`ItemAtivo.CLASSIFICACAO_MOBILIZACAO` (`:392`) são obrigatórios, sem default. A
docstring justifica (`:361-363`): *"item sem classificação é erro de contrato na
construção do estado, porque o motor não escolhe classe por omissão enquanto
`OQ-26` estiver aberta"* (`EC-31`).

**Lado 2 — ninguém pode derivá-la.**
`engine/tipos.py:182-186` declara: *"Não existe, e não deve existir enquanto
`OQ-26` estiver aberta, nenhuma função neste projeto que PRODUZA um destes
quatro valores"*. E `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`
torna isso verificável por AST — qualquer função com `CLASSIFICACAO_MOBILIZACAO`
na anotação de retorno reprova (`AC-67`).

**Lado 3 — o usuário não pode ser perguntado.**
`specs/piq-app-spec.md:2614`: *"Derivadas pelo motor, nunca perguntadas (...)
**Nunca perguntar a classificação do ativo.**"* Confirmado no registro: nenhuma
das 49 perguntas do Bloco 4 tem `VARIAVEL_GRAVADA: CLASSIFICACAO_MOBILIZACAO`.

### 4.1. Duas escapatórias aparentes, ambas fechadas

Vale registrar por que as duas saídas "óbvias" não valem:

- **"O lint só cobre `engine/`; derivamos em `app/`."** O teste de fato só varre
  `engine/**/*.py` (`test_sem_derivacao_de_classificacao_mobilizacao.py:53-55`,
  que documenta a limitação como deliberada). Mas derivar em `app/` viola a
  **Lei nº 3** ("a aplicação não calcula", `plans/app-aluno.plan.md` §1, citada
  em `test_fronteira_import_engine.py:3-5`) e `sdd.config.md` §6 ("metodologia
  não se decide implementando"). Passar num lint por ele não cobrir a pasta não
  é cumprir a regra — é achar o ponto cego dela.
- **"Classificamos tudo como `NAO_MOBILIZAR`, que é neutro."** Não é neutro: é
  uma afirmação sobre o patrimônio do aluno que ninguém calculou, no mesmo
  espírito do que `sdd.config.md` §4 proíbe ("valor desconhecido vira
  `INFORMACAO_PENDENTE` (...) nunca uma estimativa silenciosa"). Além disso
  produziria o mesmo número final que a coleção vazia, com a diferença de
  **parecer** que houve classificação.

### 4.2. Veredito

**Esta rodada consegue entregar reserva e caixa por completo; investimentos,
ativos e recursos extraordinários NÃO — e a coleção vazia é a única saída
honesta para os três enquanto `OQ-26` e `OQ-27` estiverem abertas.**

Dizendo com todas as letras, como o pedido exigiu:

- `RESERVA_EXISTE`, `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA`,
  `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` e `DINHEIRO_DISPONIVEL` são
  **leitura real de resposta**, viável agora, sem depender do especialista
  (ressalvada `OQ-21`, que é decisão técnica nossa).
- `investimentos` e `ativos` ficam `()` — **não porque a coleta falte** (ela é
  rica: 49 perguntas, três famílias de ativo), mas porque o contrato exige um
  campo por item cuja regra de produção está proibida de existir.
- `recursos_extraordinarios` fica `()` por motivo **diferente e menos grave**:
  não há `CLASSIFICACAO_MOBILIZACAO` em `RecursoExtraordinario`
  (`engine/estado.py:412-413` diz isso explicitamente — "quem o qualifica são
  janela e certeza"). O bloqueio aqui é só `OQ-22` (o `valor_interno` ausente de
  `B3.05C`) mais a repetição de `OQ-23`. **Isto é destravável dentro deste
  slug**, sem o especialista — ver o fatiamento na §8.

Uma coleção vazia é honesta e é **o que já acontece hoje**, com uma diferença
importante: hoje ela nem sequer é construída. A vazia declarada, com o motivo
registrado em docstring citando `OQ-26`, é o mesmo padrão de "lacuna documentada,
nunca estimativa silenciosa" que este arquivo já pratica em
`_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (`app/montagem/estado.py:315`) e em
`CONFIABILIDADE_DADOS` (`:88-109`).

### 4.3. `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` — mesma conclusão, causa independente

`OQ-27` (`motor-calculo`, aberta) pergunta a fórmula. Mesmo que `OQ-26` fosse
respondida amanhã, os itens continuariam inconstruíveis: os dois campos são
obrigatórios e sem default nas três dataclasses. **As duas precisam estar
respondidas** para que `investimentos`/`ativos` deixem de ser vazios — não uma
ou outra. Vale notar que as docstrings do motor já anteciparam isso: *"o valor
líquido realizável chega JÁ APURADO (`OQ-27`, aberta) (...) e a classificação
chega JÁ FEITA (`OQ-26`, aberta)"* (`engine/estado.py:355-359`). O motor delegou
as duas apurações a esta camada, e esta camada não tem as fórmulas.

## 5. Como as novas leituras devem seguir o padrão já estabelecido

`app/montagem/estado.py` tem hoje **27 funções `_privadas`** de leitura mais 4
públicas de montagem (contagem própria por varredura de `^def `). O padrão é
consistente e as novas funções devem segui-lo sem inventar nada:

1. **Uma função `_privada` por campo, nomeada pelo campo em minúscula.**
   `_tipo_renda` → `TIPO_RENDA` (`:1170`), `_capacidade_ataque_declarada` →
   `CAPACIDADE_ATAQUE_DECLARADA` (`:1187`), `_inventario_completo` →
   `INVENTARIO_COMPLETO` (`:1204`). As novas seriam `_reserva_existe`,
   `_reserva_total`, `_disposicao_uso_reserva`,
   `_valor_maximo_reserva_informado_usuario`, `_dinheiro_disponivel`.
2. **Enum resolvido por `_membro_do_enum`, nunca por cadeia de `if`.**
   `:410-425`, com a justificativa em `:111-122`. Aplicável direto a
   `RESERVA_EXISTE` e `DISPOSICAO_USO_RESERVA` (§2.1 provou que os
   `valor_interno` batem).
3. **"Não sei" atravessa por `_ou_desconhecido`** (`:370-383`), que devolve
   `DESCONHECIDO`. É o caminho de `RESERVA_TOTAL` e
   `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, ambos `DinheiroTalvez`.
4. **Nenhum `Decimal(...)`/`dinheiro(...)` literal neste módulo.** A fronteira
   única é `app/montagem/conversao.py` (`RF-13`, `T-27`), verificada por
   `tests/app_aluno/estatica/test_fronteira_decimal_unica.py`. Por isso existe
   `_ZERO: Final[Dinheiro] = converter_para_dinheiro("0")` em `:266` — a única
   forma de ter um zero neste arquivo. **`DINHEIRO_DISPONIVEL` é `Dinheiro`
   puro, não `DinheiroTalvez`** (`engine/estado.py:517`), então o caso "não
   respondeu" precisa de `_ZERO` ou de erro explícito, e isso é uma decisão —
   ver `OQ-21`.
5. **Erro nomeado, nunca valor inventado.** `ErroRespostaAusente` (`:343`),
   `ErroCampoAgregadoDesconhecido` (`:998`), `ErroValorInternoDesconhecido`
   (`:385`). O precedente de `_renda_principal` (`:1021-1041`) é o mais próximo:
   campo obrigatório `Dinheiro` cuja ausência levanta erro em vez de virar zero.
6. **Mensagem técnica montada por `str.join` sobre segmentos curtos**, para não
   formar literal contíguo que dispare o limiar de `AC-37` (`:1254-1259`).

## 6. O que muda para o usuário final

**Destrava, e é visível.** `Diagnostico.RESERVA_MOBILIZAVEL` deixa de ser sempre
`0`. Verificado: `engine/diagnostico.py:788-815` já chama
`derivar_RESERVA_MOBILIZAVEL` com os quatro campos reais do estado — a derivação
está implementada (`RF-43`, `AC-85`) e é **valor real, não mais placeholder**
(`:841-844`). Hoje ela sempre devolve `dinheiro(0)` porque a Regra 1 da §13.1
(`engine/ataque_imediato.py:128-133`) curto-circuita em
`RESERVA_EXISTE = NAO` — que é o que fixtures e montagem produziriam. Com a
leitura real, um aluno que respondeu `SIM` em `B4.02` e `PARTE` em `B4.03` passa
a ver o valor que ele mesmo declarou em `B4.03A`, limitado por
`MIN(RESERVA_TOTAL, MAX(0, informado))`.

**Correção ao pedido, verificada:** `RESERVA_MOBILIZAVEL` é hoje
`DinheiroTalvez`, não `Dinheiro` (`engine/diagnostico.py:654`, com a nota de
`T-98`/`RF-41`/`AC-68` em `:640-649`). Quem for consumir esse campo em `app/`
precisa tratar `DESCONHECIDO` — que é justamente o resultado da Regra 3 quando
`RESERVA_TOTAL` ou o valor informado são desconhecidos
(`engine/ataque_imediato.py:134-139`). Este é um caminho **novo e alcançável**
assim que a leitura real existir, e nenhuma tela de `app/` foi escrita para ele.
Ver `OQ-25`.

**NÃO destrava o Bloco 10.** Confirmado: `engine/diagnostico.py:845-850` mantém
`ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)` como placeholder explícito, por
`OQ-29`/`AMB-R3-01`, e a docstring de `:712-713` diz *"continua `dinheiro(0)` —
placeholder, NÃO o valor de negócio real"*. Como `T-77`/`T-78`/`T-79`
(`tasks/app-aluno.tasks.md:2241`, `:2282`, `:2313`) dependem de
`ATAQUE_IMEDIATO_RECOMENDADO > 0` para exibir `B10.C01`, **as três continuam
bloqueadas**, agora por `OQ-29` em vez de `OQ-17`. O bloqueio migrou de "o campo
não existe" para "o campo existe e vale zero por decisão registrada" — mesmo
padrão de migração de bloqueio que a Rodada 3 de `motor-calculo` descreveu para
`T-91`.

Vale dizer com clareza para não gerar expectativa errada: **o aluno não verá
ataque imediato recomendado ao fim desta rodada.** Verá a reserva mobilizável
correta.

## 7. Hash congelado (`AC-44`) — lista real conferida

`tests/app_aluno/estatica/hashes_congelados.json` tem 34 entradas. Verificação
própria contra o disco:

- **`engine/ataque_imediato.py` existe** (confirmado por listagem de
  `engine/*.py`) e **não consta do JSON**. Como
  `test_ac44_todo_arquivo_do_conjunto_esta_listado` reconstrói o conjunto
  esperado varrendo `engine/` recursivamente
  (`test_engine_congelado.py:83-106`), **esse teste falha hoje** por arquivo
  ausente do JSON — independente de qualquer edição desta rodada.
- Os arquivos que a Rodada 3 de `motor-calculo` modificou têm hash divergente do
  gravado, o que faz
  `test_ac44_hashes_congelados_batem_com_o_conteudo_atual_dos_arquivos`
  (`:109`) falhar nomeando cada um.

A lista do pedido (6 modificados + 1 novo) é plausível e bate com o que a Rodada
3 declarou ter tocado, mas **a lista autoritativa deve ser obtida executando o
próprio teste**, que nomeia arquivo por arquivo — não transcrita de um pedido.
Recomendo que a tarefa de atualização do JSON seja escrita como "rodar o teste,
regravar exatamente os hashes que ele apontar", nunca como uma lista fixa no
enunciado da tarefa, que envelheceria mal. Registro o procedimento como parte do
plano, não como questão aberta: `AC-44` já documenta que a atualização é
deliberada e explícita.

Duas observações que evitam erro na execução:

1. `persistencia/supabase/migracoes/002_app_aluno.sql` **nunca** entra no JSON —
   é a migração desta feature, deliberadamente fora do congelamento
   (`test_engine_congelado.py:67-71`, `:152-161`).
2. Atualizar o hash é o procedimento **correto** aqui, não um contorno: `AC-44`
   proíbe que *esta feature* modifique `engine/`; quem modificou foi o slug
   `motor-calculo`, legitimamente, na sua Rodada 3. O JSON é o registro de "o
   `engine/` que este slug consome", e ele precisa passar a apontar para o
   `engine/` novo.

## 8. Tamanho da rodada e proposta de fatiamento

**A rodada não cabe numa leva só, mas por motivo diferente do de
`motor-calculo`.** Lá o problema era volume (16 variáveis, 7 derivadas, 6
questões ao especialista). Aqui o volume é menor, mas há um **corte natural e
nítido** entre o que está pronto para ler e o que está bloqueado por questão de
terceiro — e o primeiro pedaço resolve sozinho o `build` quebrado e as ~129
falhas.

### Rodada 2A — Reserva e caixa (destrava `build` e a suíte; sem depender do especialista)

Ler `B4.01A`, `B4.02`, `B4.02A`, `B4.03`, `B4.03A` e preencher os cinco campos
escalares. Passar `()` para `investimentos`, `ativos` e
`recursos_extraordinarios`, com docstring citando `OQ-26`/`OQ-27` como motivo.
Ampliar a allowlist em **dois** nomes apenas (`RESERVA_EXISTE`,
`DISPOSICAO_USO_RESERVA`) — os outros cinco não são necessários para construir
tuplas vazias. Atualizar `hashes_congelados.json`. Atualizar as fixtures de
`tests/app_aluno/`.

Entrega: `build` limpo, suíte verde, `RESERVA_MOBILIZAVEL` real na tela.
Depende de `OQ-20`, `OQ-21`, `OQ-25` — **todas decisão nossa**.

Esta fatia é, de longe, a de melhor relação valor/risco da rodada: é a única que
tira o projeto do estado "não compila e 129 testes falham".

### Rodada 2B — Recursos extraordinários (destravável aqui, sem o especialista)

Corrigir `valor_interno` de `B3.05C` no registro (`OQ-22`), criar o escopo de
repetição e resolver a colisão de nome de variável entre escopos (`OQ-23`),
ampliar a allowlist em três nomes (`RecursoExtraordinario`,
`JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`) e ler as
fichas `B3.05A-D`.

É a única das três coleções sem `CLASSIFICACAO_MOBILIZACAO`
(`engine/estado.py:412-413`), portanto a única implementável hoje. Depende de
`OQ-22`, `OQ-23`, `OQ-26-app` — nossas.

### Rodada 2C — Investimentos e ativos (BLOQUEADA por terceiro)

`ItemInvestimento` e `ItemAtivo`, as três famílias de ficha de ativo, a
repetição em quatro escopos e o mapeamento de liquidez. **Bloqueada por `OQ-26`
e `OQ-27` do slug `motor-calculo`, ambas abertas com o especialista** — e as
duas precisam estar respondidas, não uma. Não iniciar antes das respostas: sem
elas, o único código escrevível é o que a §4.1 mostra ser proibido.

**Recomendação:** abrir 2A imediatamente e sozinha; ela é pequena, não depende
de ninguém e restaura o `build`. Fazer 2B em seguida se houver apetite. Não
iniciar 2C, e usar o fato de que ela está bloqueada como argumento adicional
para priorizar `OQ-26`/`OQ-27` junto ao especialista — hoje elas bloqueiam dois
slugs, não um.

## 9. Questões abertas desta rodada

Numeração continuando a série de `specs/app-aluno.spec.md` §10, que encerra em
`OQ-19` (`:501`). **Nenhuma destas é decidida neste documento.**

### 9.1. Decisão técnica nossa (spec/plano, sem o especialista)

| ID | Questão | Encaminhamento provável |
| --- | --- | --- |
| `OQ-20` | **Ampliar a allowlist de `AC-41` com os sete nomes de `engine.estado`?** (`RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA`, `ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`). A §1.2 mostra que os sete caem no mesmo Critério A já usado quatro vezes (`TIPO_DIVIDA`, os 8 do Bloco 2, `TIPO_RENDA`, `Divida`), e que o próprio arquivo prevê crescimento sob critério (`test_fronteira_import_engine.py:70-72`, sobre `Oportunidade`). Sub-decisão: liberar os sete de uma vez, ou só os dois que a fatia 2A exige? | Provável: ampliar, com o comentário justificativo no padrão dos existentes; liberar por fatia, para que a allowlist nunca contenha nome que ninguém importa |
| `OQ-21` | **Como traduzir os três estados de `B4.03A` e o "não respondeu" de `B4.01A`?** A opção "Prefiro decidir somente depois de ver a análise" (`bloco-04.yaml:154`) não tem `valor_interno` nem `admite_nao_sei` — é um terceiro estado sem representação. E `DINHEIRO_DISPONIVEL` é `Dinheiro` puro (`engine/estado.py:517`): sem resposta, é `_ZERO` ou erro nomeado? Interage com `OQ-25` de `motor-calculo` (aberta), que perguntou se "decidir depois" e "não sei" colapsam | Para `B4.03A`: colapso em `DESCONHECIDO` é o que a §13.1 Regra 3 exige aritmeticamente; a distinção fina, se necessária à devolutiva, vive em `app/`. Para `B4.01A`: `B4.01` (`DINHEIRO_DISPONIVEL_EXISTE`) é `[OBR]` e condiciona `B4.01A` — `NAO` em `B4.01` é o caso legítimo de `_ZERO`; ausência das duas é erro nomeado, padrão `_renda_principal` |
| `OQ-22` | **`B3.05C` (`JANELA_RECURSO_EXTRAORDINARIO`) tem `valor_interno: null` nas cinco opções** (`bloco-03.yaml:284-289`), mas o enum tem cinco membros com valores `ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI` (`engine/estado.py:209-213`). Preencher o `valor_interno` no YAML, no padrão de `B3.05D` (que já tem)? | Provável: sim — é correção de registro, mesma natureza de `OQ-19`, e é a única alternativa a traduzir rótulo em português no código, proibido por `AC-37`. `sdd.config.md` §6 exige que a mudança seja de registro, não de código |
| `OQ-23` | **`valores_do_escopo` não filtra por escopo** (`collection/respostas.py:114-128`, docstring explícita), e três famílias de ficha de ativo compartilham `VARIAVEL_GRAVADA` (`VALOR_ESTIMADO_ATIVO` em `:222`, `:363`, `:570`, `:833`). Ler item por escopo exige filtro real por escopo, ou nomes de variável distintos por família, ou `item_id` prefixado por escopo (`PREFIXO_POR_ESCOPO`, `collection/repeticao.py:59-67`) | Provável: o prefixo do `item_id` já existe e já distingue os escopos — filtrar por ele é a mudança menor. Mas é mudança em `collection/`, não em `app/`, e afeta os cinco escopos já em uso: exige teste de não-regressão em renda adicional e despesa não-mensal |
| `OQ-24` | **Uma coleção `ativos` alimentada por três famílias de ficha** (imóvel `B4.I*`, veículo `B4.V*`, outro `B4.O*`, `bloco-04.yaml:315-960`), cada uma com perguntas e nomes próprios. Um escopo de repetição por família (três) ou um só para "ativo"? A escolha decide `PREFIXO_POR_ESCOPO` e a forma da leitura | Provável: um por família, seguindo o precedente de `OQ-19` (um membro por família de ficha, não um genérico). Bloqueada de fato por `OQ-26`/`OQ-27` — não urge |
| `OQ-25` | **`RESERVA_MOBILIZAVEL` é `DinheiroTalvez`** (`engine/diagnostico.py:654`), e a Regra 3 da §13.1 produz `DESCONHECIDO` de verdade quando `RESERVA_TOTAL` ou o valor informado são desconhecidos (`engine/ataque_imediato.py:134-139`). Nenhuma tela de `app/` trata esse caminho hoje, porque hoje o campo é sempre `0`. Como o app exibe "reserva mobilizável desconhecida" ao aluno? | Provável: mesmo tratamento já dado a outros desconhecidos na devolutiva (plano provisório, `GAB-02`/`GAB-03`), mas a redação ao aluno não existe e `Q-02`/`Q-03` fixam redação canônica só para a ordem projetada. Pode exigir texto novo — e texto ao aluno não se inventa aqui |

### 9.2. Bloqueadas por terceiro (slug `motor-calculo` / especialista do método)

Estas **não são questões novas** — são as questões daquele slug, registradas aqui
porque é aqui que elas passaram a bloquear trabalho concreto.

| ID (naquele slug) | Questão | O que bloqueia aqui |
| --- | --- | --- |
| `OQ-26` | Regra de derivação de `CLASSIFICACAO_MOBILIZACAO` | `investimentos` e `ativos` (fatia 2C inteira). Sem ela, item inconstruível: campo obrigatório sem default (`engine/estado.py:369`, `:392`), derivação proibida por `AC-67`, pergunta proibida por `piq-app-spec.md:2614` |
| `OQ-27` | Fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | Idem — **independente** de `OQ-26`: as duas precisam estar respondidas, não uma |
| `OQ-29` | Fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | `ATAQUE_IMEDIATO_RECOMENDADO` segue `dinheiro(0)` (`engine/diagnostico.py:845-850`), logo `T-77`/`T-78`/`T-79` (Bloco 10) continuam pendentes |

## Resumo executável (checklist)

Pré-requisitos — nenhum é código:

- [ ] `OQ-20` decidida: ampliar ou não a allowlist de `AC-41`, e com quais nomes por fatia
- [ ] `OQ-21` decidida: tradução dos três estados de `B4.03A` e do "não respondeu" de `B4.01A`
- [ ] `OQ-25` decidida: como o app exibe `RESERVA_MOBILIZAVEL` desconhecida
- [ ] `OQ-22`, `OQ-23`, `OQ-24` decididas antes de 2B/2C
- [ ] `OQ-26`/`OQ-27` cobradas do especialista — hoje bloqueiam dois slugs

Rodada 2A:

- [ ] Cinco funções `_privadas` novas em `app/montagem/estado.py`, padrão da §5
- [ ] `montar_estado_financeiro` (`:1326`) passa os 8 campos; três coleções `()` com motivo em docstring citando `OQ-26`/`OQ-27`
- [ ] Allowlist de `AC-41` ampliada conforme `OQ-20`, com comentário justificativo no padrão de `:73-78`
- [ ] `tests/app_aluno/estatica/hashes_congelados.json` regravado a partir da saída do próprio teste — incluindo a entrada nova de `engine/ataque_imediato.py`, hoje ausente
- [ ] Fixtures atualizadas: `tests/app_aluno/fixtures/caso_completo.py`, `test_conversao_decimal.py:300`, `test_plano_ec07_ec08_ec09.py:347`
- [ ] `build` volta a passar (hoje 1 erro) e a suíte de `tests/app_aluno/` volta a passar (hoje ~129 falhas)
- [ ] Teste novo: `RESERVA_MOBILIZAVEL` deixa de ser `0` quando `B4.02=SIM`, `B4.03≠NAO` e `B4.03A` tem valor

Rodada 2B:

- [ ] `valor_interno` de `B3.05C` preenchido no registro (`OQ-22`)
- [ ] Escopo de repetição para recurso extraordinário + prefixo em `PREFIXO_POR_ESCOPO`
- [ ] Filtro real por escopo em `valores_do_escopo` (`OQ-23`), com não-regressão nos cinco escopos já em uso
- [ ] Leitura das fichas `B3.05A-D` → `tuple[RecursoExtraordinario, ...]`

Rodada 2C — **não iniciar antes de `OQ-26` e `OQ-27`**:

- [ ] Escopos de repetição das três famílias de ativo + investimento
- [ ] `ItemInvestimento`/`ItemAtivo` construídos com classificação e valor líquido reais

## O que isto desbloqueia

- **`OQ-37`** (`specs/motor-calculo.discovery.md:691`) — respondida ao fim de 2A
  para reserva e caixa; parcialmente, e por decisão registrada, para patrimônio
- **A suíte inteira de `tests/app_aluno/`** — ~129 falhas de causa raiz única
- **`RESERVA_MOBILIZAVEL` visível e correta** ao aluno (`RF-43`, `AC-85` do slug
  `motor-calculo`, hoje verificável só com `RESERVA_EXISTE = NAO`)
- **NÃO desbloqueia** `T-77`/`T-78`/`T-79` (Bloco 10), que seguem dependendo de
  `ATAQUE_IMEDIATO_RECOMENDADO` — placeholder por `OQ-29`, aberta
