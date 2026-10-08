# Spec — App do Aluno (coleta, plano e acompanhamento)

| Campo    | Valor                                                        |
| -------- | ------------------------------------------------------------ |
| Slug     | `app-aluno`                                                  |
| Status   | `rascunho`                                                   |
| Autor    | virtushold@gmail.com                                         |
| Data     | 2026-09-30 (Rodada 9 — decisões do especialista `DE-01` a `DE-08`) · 2026-09-14 (Rodada 3 — protótipo validado e máscara · Rodada 2 — fatia 2A em 2026-09-07 · Rodada 1 em 2026-09-03) |
| Fonte    | [`docs/decisoes-especialista/README.md`](../docs/decisoes-especialista/README.md) — decisões `DE-01` a `DE-08` de 2026-09-30 (respostas brutas em `docs/decisoes-especialista/respostas/`), fonte da Rodada 9. `DE-02` e `DE-05` alteram a metodologia e entraram como **v1.0.2** da canônica (`piq-app-spec.md`, Registro de alterações) |
| Fonte    | [`specs/app-aluno.discovery.md`](app-aluno.discovery.md) — discovery desta feature (Rodada 1 e Rodada 2) |
| Fonte    | [`specs/motor-calculo.spec.md`](motor-calculo.spec.md) **§13** — documento canônico PIQ v1.0.1 (`RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO`), **congelado**, fonte normativa da Rodada 2 |
| Fonte    | [`specs/piq-app-spec.md`](piq-app-spec.md) — Matriz Canônica v1.0.1 (§7, §11, §14, §15) |
| Fonte    | [`specs/motor-calculo.spec.md`](motor-calculo.spec.md) e [`plans/motor-calculo.plan.md`](../plans/motor-calculo.plan.md) — a feature consumida |
| Fonte    | Decisões do especialista de 2026-09-03 — fecham `OQ-01`, `OQ-02`, `OQ-03`, `OQ-04`, `OQ-05`, `OQ-10` |

> **Esta spec não substitui a canônica — ela a endereça.** Nenhuma regra é
> parafraseada aqui: cada requisito aponta o ID normativo (`Q-02`, `V-01`,
> `R-01`, `S-04`, `GAB-03`…) e a pergunta (`B5.FIM02`, `B10.C01A`, `B12.15`…)
> que o definem.
>
> **Ordem de precedência, do mais forte ao mais fraco:**
>
> 1. **Matriz Canônica v1.0.1** — soberana para metodologia, redação ao aluno,
>    domínios e conteúdo das 291 perguntas.
> 2. **`specs/motor-calculo.spec.md` e o contrato real de `engine/`** — soberanos
>    para o que a coleta precisa produzir. Esta feature **consome**
>    `calcular_plano(...)`; não altera `engine/`.
> 3. **Decisões do especialista de 2026-09-03** — fecham as perguntas de
>    arquitetura e processo que a canônica deixou em aberto (§14 `PEND-05`).
>
> **Sem stack.** Linguagem, framework, banco e bibliotecas não aparecem nesta
> spec. São decisão de refinamento técnico e vivem na seção `Tech Stack` de
> `plans/app-aluno.plan.md`.

---

## 0. Fronteira desta feature — o que ela é e o que ela não toca

Esta spec cobre **duas camadas, não três**:

1. **Front** — coleta gerada a partir dos registros da §11, retomada, telas do
   aluno e telas do revisor.
2. **Camada de aplicação (fina)** — exposição HTTP, autenticação com senha,
   estado do caso ao longo do tempo, montagem do `EstadoFinanceiro` a partir das
   respostas, chamada a `calcular_plano(...)` e fila de revisão.

O que ela **não** cobre, porque já existe e está entregue:

| Camada | Situação | Como esta feature se relaciona |
| --- | --- | --- |
| `engine/` | Pronto e verificado — 78/78 tarefas, 3 gabaritos numéricos, 5 invariantes | **Congelado.** Consumido via `calcular_plano(...)`. Exceção única e nomeada: `RF-33` |
| `persistencia/` | Pronto — adaptador Supabase/Postgres funcionando (`conexao.py`, `fonte_parametros.py`, `repositorio_snapshots.py`, `migracoes/001_inicial.sql`) | **Consumido**, não reescrito. Implementa as portas `FonteParametros` e `RepositorioSnapshots` de `engine/portas.py` |

> **A camada de aplicação orquestra; ela não calcula.** Não há regra de negócio
> de cálculo financeiro nela: nenhum gate, nenhum ranqueamento, nenhuma fórmula
> da §11, nenhum valor `P_*`. Ela monta a entrada, invoca o motor, guarda o que
> ele devolveu e apresenta. **Toda decisão financeira vem do motor.**

### Por que a fronteira é exatamente aqui

Isto é decisão deliberada, não acidente de organização de pastas. A Lei nº 1 do
`plans/motor-calculo.plan.md` §1 — *"`engine/` não conhece persistência nem
Supabase"* — não é preferência estética: é derivada de requisito (`RF-12` do
motor, mais o NFR de determinismo). É ela que torna `calcular_plano` uma função
pura, sem I/O, sem relógio e sem rede — e é **essa pureza** que faz os três
gabaritos numéricos e os cinco invariantes serem verificáveis.

Dissolver a fronteira por conveniência — deixar a aplicação "só dar uma
espiadinha" num cálculo, replicar uma regra do motor para exibir mais rápido,
ou fazer `engine/` ler direto do banco — custaria exatamente isso: o motor
deixaria de ser reproduzível a partir de uma entrada, os gabaritos deixariam de
provar o que provam, e um erro de cálculo passaria a ter dois lugares possíveis
onde morar. É o cenário que a §15.3 da canônica resume em *"motor errado com
formulário bonito é pior do que o contrário"*.

Por isso a regra prática, verificável em `AC-41` e `AC-42`: se uma tela precisa
de um número, esse número vem de um campo do `SnapshotOrdem`. Se não existe
campo, a resposta é uma Open Question ao especialista — nunca um cálculo novo
na aplicação.

---

## 1. Overview

O motor está pronto e verificado, mas é uma função pura: recebe um
`EstadoFinanceiro` já montado em memória e devolve um `SnapshotOrdem`. Não
existe nada que produza aquela entrada nem nada que traduza aquela saída para o
aluno. O problema não é "construir uma tela": o PIQ é um **acompanhamento
longitudinal**, e hoje só existe a peça que calcula um instante dele. As 291
perguntas da §11 não são um formulário — são cinco superfícies de interação em
momentos distintos da vida do caso: diagnóstico inicial (Blocos 1–5), o motor
rodando sem perguntar nada (Bloco 6), intervenção dirigida pelo motor a dívidas
específicas (Blocos 7 e 8), confirmação do ataque imediato (Bloco 10) e
execução ao longo de meses (Bloco 11, que a canônica declara explicitamente
*"não é um questionário inicial"*).

Esta feature entrega o **front e uma camada de aplicação fina** de um app web
dedicado, sobre o motor e a persistência já prontos (ver §0). O aluno-servidor
endividado se autentica com senha, responde a coleta completa em quantas sessões
precisar, recebe uma ordem projetada de quitação revisada por uma pessoa antes
de chegar a ele, e volta ao longo dos meses para reportar execução, quitações e
mudanças — cada uma delas gerando um novo snapshot encadeado, nunca uma
sobrescrita. A unidade central não é o formulário: é o **caso**, uma máquina de
estados que atravessa coleta, cálculo, revisão, entrega e reentrada. O sistema
não decide nada de metodologia nem de finanças: ele coleta o que a §11 manda
coletar, entrega ao motor sem inventar valor, e apresenta o que o motor devolveu
com a redação canônica obrigatória.

## 2. Functional Requirements

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-01` | Modelar cada aluno como um **caso** com ciclo de vida explícito e transições nomeadas, não como um formulário linear: o caso atravessa coleta inicial, cálculo, revisão, entrega, acompanhamento e recálculo, e pode voltar à coleta dirigida (Blocos 7/8) ou a campos isolados (`B11.03-INF`) sem reiniciar | §11 · Bloco 11 (regra canônica: *"não é um questionário inicial"*) · discovery §6 | essencial |
| `RF-02` | Autenticar o aluno com **login e senha**, de qualquer dispositivo, ao longo de todo o acompanhamento, e isolar integralmente os dados de um caso dos demais | `OQ-05` (respondida) · `PEND-01` (quem acessa a base) | essencial |
| `RF-03` | **Gerar** a interface de coleta a partir dos registros da §11 — nunca codificar pergunta a pergunta. Uma nova versão do questionário deve ser edição de registro, não reescrita de código. IDs de pergunta são estáveis e nunca reaproveitados | §11 (enunciado de abertura) · `sdd.config.md` §6 | essencial |
| `RF-04` | Suportar no gerador, sem exceção codificada à mão: **ficha repetível** por `DIVIDA_ID`, `VINCULO_ID`, `MARGEM_ID` e item de despesa (115 das 291 perguntas são `REP`) | §15.1 (linha "Ficha repetível") · Bloco 5 (55 de 58 `REP`) | essencial |
| `RF-05` | Suportar no gerador **condicional composta entre blocos** — condição de exibição que depende de mais de uma variável, de blocos diferentes (`B12.08` depende de quatro origens: dívida de cartão no Bloco 5, `CARTAO` em `MECANISMO_DEFICIT`, `RISCO_PRINCIPAL_RECAIDA = CARTAO` ou `B12.01`) | §15.1 (linha "Condicional composta") · `B12.08` | essencial |
| `RF-06` | Suportar no gerador **texto dinâmico**, interpolando valores já coletados ou calculados no enunciado exibido (ex.: `B11.Q01` exibe *"A dívida [Dxxx] foi efetivamente quitada?"*; `B11.Q06` mostra o `PAGAMENTO_MENSAL_EFETIVO` vigente) | §15.1 (linha "Texto dinâmico") · `B11.Q01` · `B11.Q06` | essencial |
| `RF-07` | Suportar no gerador **validação cruzada entre campos**, por item repetido — a validação normativa `VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM`, por `MARGEM_ID` | §15.1 (linha "Validação entre campos") · canônica linha 5167 | essencial |
| `RF-08` | Suportar no gerador **perguntas cujas opções são produzidas pelo motor em tempo de execução**: `B12.15` (*"o motor seleciona risco/sinal e apresenta: SE [sinal], ENTÃO [resposta]"*, uma pergunta por regra proposta) e `B12.16` (*"o motor apresenta 2 ou 3 regras coerentes com o caso"*) | §11 · `B12.15` · `B12.16` · discovery §1(b) | essencial |
| `RF-09` | Coletar a **Etapa B completa** (Blocos 1–5, 195 perguntas) mais os Blocos 7, 8, 10 e 11, respeitando obrigatoriedade `OBR`/`COND`/`OPT`/`REP` de cada registro | `OQ-02` (respondida: coleta completa) · §11 | essencial |
| `RF-10` | Persistir o progresso da coleta **a cada resposta**, permitindo ao aluno abandonar e retomar exatamente de onde parou, em outra sessão e em outro dispositivo, sem redigitar nada já respondido | discovery §3 e §5 (retomada) · `OQ-02` (coleta multissessão) | essencial |
| `RF-11` | Tratar **"não sei" como resposta de primeira classe** em todo campo cujo registro da §11 a admite, gravando-a de forma distinguível de "não respondido" e de qualquer valor numérico | `GAB-03` · `RF-16` do motor · §11 (opções "Não sei") | essencial |
| `RF-12` | Traduzir toda resposta "não sei" para o motor como **`INFORMACAO_PENDENTE`/`DESCONHECIDO`**, nunca como zero, média, estimativa ou valor default. Nenhum valor é inventado em nenhum ponto da fronteira | `GAB-02`, `GAB-03` · `sdd.config.md` §4 ("Não inventar dado") | essencial |
| `RF-13` | Converter toda entrada monetária e de taxa vinda do formulário para `Decimal` numa **fronteira de conversão única e testada**, sem que o valor atravesse `float` em nenhum ponto — o motor recusa `float` em construção (`engine/estado.py::_recusar_float`) | `RF-12` do motor · `G-01` · `engine/precisao.dinheiro()` | essencial |
| `RF-14` | Montar o `EstadoFinanceiro` (e as `Divida` que o compõem) a partir das respostas coletadas, preenchendo todos os campos exigidos pelo contrato real de `engine/estado.py`, incluindo `perfil_comportamental` (8 variáveis do Bloco 2), `sinais_comportamentais`, `AUTOPERCEPCAO_CONTROLE` (`B2.13`) e `DATA_REFERENCIA` como entrada explícita — nunca lida do relógio | `engine/estado.py` · `RF-14`/`RF-23` do motor · NFR determinismo | essencial |
| `RF-15` | Derivar `INVENTARIO_COMPLETO` de `B5.FIM02` (`CONFIRMACAO_FIM_CADASTRO`): qualquer resposta ≠ `SIM` produz `INVENTARIO_COMPLETO = falso`, e o plano resultante não pode ser apresentado como definitivo | `B5.FIM02` · `GAB-02` · `AC-09` do motor | essencial |
| `RF-16` | Executar o **Bloco 6** — invocar `calcular_plano(...)` com o estado montado e os parâmetros carregados pela `FonteParametros` já existente, sem coletar nenhuma pergunta nessa etapa e **sem reproduzir nenhum passo do cálculo** na aplicação | §11 (*"o Bloco 6 não coleta dados"*) · `engine/motor.py::calcular_plano` | essencial |
| `RF-17` | Abrir os **Blocos 7 e 8 somente para as dívidas que o motor sinalizou**, repetidos por `DIVIDA_ID`, a partir das ações que o motor devolveu em `ORDEM_ACOES` — a interface nunca decide sozinha qual dívida é candidata a renegociação ou troca | `B7.01` (*"dívida qualificada para B7"*) · `B8.00` · `engine/gates.py::AcaoRequerida` | essencial |
| `RF-18` | Exibir o **Bloco 10** apenas quando `ATAQUE_IMEDIATO_RECOMENDADO > 0`, aceitar aceite total, parcial (`B10.C01A`) ou nenhum, validar `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO` e **nunca perguntar qual dívida receberá o recurso** — a ordem é do motor | `B10.C01` · `B10.C01A` | essencial |
| `RF-19` | Persistir todo `SnapshotOrdem` produzido **através do `RepositorioSnapshots` já existente**, via `anexar` — a garantia append-only já está implementada em `persistencia/` (porta sem `atualizar`/`remover`) e no banco (`REVOKE` + trigger `impedir_sobrescrita_v01`). A aplicação **consome** essa garantia; não a reimplementa nem cria caminho paralelo de escrita de snapshot | `V-01`, `V-02` · `engine/portas.py::RepositorioSnapshots` · `persistencia/supabase/migracoes/001_inicial.sql` | essencial |
| `RF-20` | Exibir `ENGINE_VERSION` e `PARAMETROS_VERSION` em **toda saída entregue ao aluno e ao revisor** — o carimbo do snapshot atravessa a apresentação, não fica só no banco | `V-03` · `AC-16` do motor | essencial |
| `RF-21` | Apresentar a ordem ao aluno com a **redação canônica obrigatória**, caractere por caractere: título *"Sua ordem projetada de quitação"* e o texto normativo de `Q-03`; e usar sempre o termo **"projetada"**, jamais "definitiva", "final" ou "fixa", sem criar variável nova para o rótulo visual | `Q-02` · `Q-03` · canônica §7 | essencial |
| `RF-22` | Exibir a `JUSTIFICATIVA_POSICAO` de cada dívida da sequência projetada | `Q-05` | essencial |
| `RF-23` | Manter uma **fila de revisão** pela qual passa **todo** relatório antes de qualquer envio ao aluno, incluindo os recálculos disparados por quitação confirmada e por evento material do Bloco 11. Nenhum plano chega ao aluno sem registro de liberação | `PEND-06` · `sdd.config.md` §6 · `OQ-04` (respondida: todo snapshot) | essencial |
| `RF-24` | Registrar cada revisão com **autor e data**, e manter o registro imutável junto ao snapshot revisado — liberação e reprovação são ambas registradas | discovery §5 (*"com autor e data"*) · `PEND-06` | essencial |
| `RF-25` | Nomear e tratar como **mecanismos distintos**: (a) `REVISAO_HUMANA_OBRIGATORIA`, campo booleano emitido pelo motor no caso metodológico estreito de `S-04`; e (b) `POLITICA_REVISAO_INTEGRAL_PILOTO`, a política de processo que submete 100% dos relatórios à fila. A política se aplica mesmo com o campo em `False`; o campo, quando `True`, é sinalizado ao revisor como motivo metodológico adicional | `S-04` · `PEND-06` · discovery §4 e §6 | essencial |
| `RF-26` | Apresentar ao revisor, lado a lado, **o plano como o aluno o verá e os dados que o produziram** (`estado_inputs` do snapshot), para que ele possa classificar um erro encontrado em TEXTO, PARÂMETRO, DADO, REGRA, CÁLCULO ou UX — só os seis nomes, sem definição de categoria (`OQ-12` respondida, `PEND-LOCAL-01`) | §15.3 · `OQ-12` (respondida) · `PEND-LOCAL-01` · discovery §2 | importante |
| `RF-27` | Coletar o **Bloco 11** ao longo do tempo, vinculado a `ACAO_ID` ou `DIVIDA_ID` (`RF-33`), reabrindo o que cada resultado manda reabrir: `RESULTADO_ACAO_RENEGOCIACAO` = Sim reabre `B7.05–B7.16`; `RESULTADO_ACAO_TROCA` = Sim reabre `B8.01–B8.15`; `RESULTADO_ACAO_INFORMACAO` = Sim abre **exclusivamente** o campo que faltava (ex.: `B5.B03`, `B5.D01A`) | Bloco 11 · `B11.03-INF` · `B11.03-REN` · `B11.03-TRO` · `B11.03-ECO` | essencial |
| `RF-28` | Disparar recálculo **apenas** por quitação confirmada de qualquer dívida ou por evento material externo, mapeando o evento coletado para o membro correspondente de `EVENTO_RECALCULO` — nunca por virada de mês nem por alteração meramente cadastral | `R-01` · `RF-02` do motor · `engine/tipos.py::EVENTO_RECALCULO` | essencial |
| `RF-29` | Confirmar quitação pela sequência `B11.Q01–Q06` e só tratar `STATUS_QUITACAO_REAL = QUITADA` como gatilho de recálculo quando a resposta for `Sim` — `A_CONFIRMAR` não dispara | `B11.Q01` · `R-01` | essencial |
| `RF-30` | Registrar consentimento explícito do aluno antes de qualquer coleta de dado pessoal, e oferecer procedimento de exclusão e prazo de retenção declarados — os textos são insumo externo (`PEND-01`), não redação do desenvolvedor | `PEND-01` · discovery §4 (Legais) | essencial |
| `RF-31` | Registrar a trilha de progresso de cada caso (em que bloco parou, o que aguarda revisão, o que não reporta execução), de modo que o abandono seja observável e não silencioso | discovery §6 (abandono) · `OQ-07` (respondida) · base de dado consultado por `RF-35` | importante |
| `RF-32` | Carregar os parâmetros **pela `FonteParametros` já existente** e repassá-los ao motor, sem nenhum valor `P_*` escrito no código desta feature e sem segunda via de leitura de parâmetro | `RF-13` do motor · §8 · `engine/portas.py::FonteParametros` · `sdd.config.md` §4 | essencial |
| `RF-33` | Receber, na `ORDEM_ACOES` de cada snapshot, **toda** ação que o aluno precisa reportar no Bloco 11 — cada uma com **identidade estável (`ACAO_ID`)** e **tipo (`TIPO_ACAO`)** —, de modo que `B11.01` seja exibida por ação em acompanhamento e `B11.03-INF`/`-REN`/`-TRO`/`-ECO` ramifiquem pelo tipo. "Toda" inclui as ações de informação (dívida travada no Gate 1) e de economia (redução de gasto identificada e aceita), hoje ausentes da `ORDEM_ACOES`. `ACAO_ID` permanece idêntico entre snapshots enquanto a ação for a mesma. **Depende de três mudanças em `engine/`, todas trabalho do slug `motor-calculo` — esta spec declara a dependência, não a implementa (ver Assumptions)** | `B11.01` (linha 4272) · `B11.03-*` (linhas 4298, 4312, 4326, 4340) · `ACAO_ID (SYS)` (linha 4254) · `B2.09` (linha 960: *"gera ação de conferência (Bloco 11)"*) · `OQ-10`, `OQ-14` (respondidas) | essencial |
| `RF-34` | Manter a camada de aplicação **livre de regra de negócio de cálculo**: nenhum gate, ranqueamento, fórmula da §11 ou valor `P_*` é avaliado fora de `engine/`. Todo número exibido ao aluno ou ao revisor é um campo lido do `SnapshotOrdem` — se o campo não existe, isso é Open Question, nunca um cálculo novo na aplicação | Lei nº 1 · `plans/motor-calculo.plan.md` §1 · §15.3 · `sdd.config.md` §6 | essencial |
| `RF-35` | Fornecer um **painel dedicado do operador** (o especialista/revisor), listando todos os casos do piloto com: bloco atual, o que aguarda revisão, e havendo abandono — tempo desde a última atividade. Lê a mesma trilha de progresso de `RF-31`, apresentada em tela própria, não apenas como dado consultável por query. Decisão do usuário (`OQ-07`, respondida): mesmo no piloto de 1–3 alunos, quer visibilidade direta de quem travou onde, sem depender de consulta manual | `RF-31` · discovery §6 (abandono) · `OQ-07` (respondida) | importante |

### Rodada 2 (2026-09-07) — fatia 2A: reserva e caixa do Bloco 4

> **Origem.** A Rodada 3 do slug `motor-calculo` entregou um contrato de entrada
> novo: `EstadoFinanceiro` passou de 13 para 21 campos (`engine/estado.py:492-528`),
> os 8 novos obrigatórios e sem default. `app/montagem/estado.py:1326` ainda
> constrói os 13 antigos — daí o `build` quebrado e as ~129 falhas de causa raiz
> única em `tests/app_aluno/`. Esta rodada faz a montagem voltar a montar.
>
> **Recorte.** Só a **fatia 2A**: os **cinco campos escalares** de reserva e caixa,
> lidos de resposta real do Bloco 4, mais as três coleções como **tupla vazia
> declarada**. As fatias 2B (recursos extraordinários) e 2C (investimentos e
> ativos) ficam fora — justificativa na seção 9.
>
> **A §13 de `motor-calculo` é normativa e congelada.** Nenhuma regra dela é
> parafraseada nem reinterpretada aqui: esta camada **lê resposta e entrega o
> campo**; quem aplica as três regras da §13.1 é o motor
> (`engine/ataque_imediato.py`, `RF-43`/`AC-85` daquele slug). Ler não é calcular
> (Lei nº 3, `RF-34`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-36` | Ler `RESERVA_EXISTE` de `B4.02` e `DISPOSICAO_USO_RESERVA` de `B4.03` como **membros de enum resolvidos por `valor_interno`**, pelo mecanismo genérico já existente (`_membro_do_enum`, `app/montagem/estado.py:410`) — nunca por cadeia de `if`, nunca por rótulo em português. Os `valor_interno` do registro (`SIM`/`INFORMAL`/`NAO` em `bloco-04.yaml:52-57`; `PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO` em `:127-133`) batem **caractere por caractere** com os `name` dos enums de `engine/estado.py:181-200`, o que torna a resolução direta possível | §13.1 Regra 1 · `B4.02` · `B4.03` · `AC-37` (proíbe rótulo no código) · `sdd.config.md` §7 | essencial |
| `RF-37` | Ler `RESERVA_TOTAL` (`B4.02A`) e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (`B4.03A`) como `DinheiroTalvez`, fazendo "não sei" atravessar até o motor como `DESCONHECIDO` pelo mecanismo já existente (`_ou_desconhecido`) — jamais como `0`, média ou estimativa. A §13.1 é explícita: o estado `DESCONHECIDA` **não** é convertido silenciosamente em zero | §13.1 Regra 3 · `RF-12` · `GAB-03` · `engine/estado.py:512`, `:514` | essencial |
| `RF-38` | Ler `DINHEIRO_DISPONIVEL` (`B4.01A`) como `Dinheiro` **puro**, sem união com desconhecido, tratando os dois caminhos legítimos de ausência de valor de forma distinta e explícita: `DINHEIRO_DISPONIVEL_EXISTE = NAO` (`B4.01`, `OBR`) é o caso de zero legítimo; ausência das **duas** respostas é erro nomeado, nunca zero inventado — mesmo padrão de `_renda_principal` (`app/montagem/estado.py:1021`) | §13.3 (`CAIXA_RECOMENDADO`) · `engine/estado.py:517` · `RF-12` · `OQ-23` | essencial |
| `RF-39` | Preencher `investimentos`, `ativos` e `recursos_extraordinarios` com **tupla vazia declarada**, com o motivo registrado em docstring citando nominalmente `motor-calculo:OQ-26` e `motor-calculo:OQ-27` (investimentos/ativos) e `OQ-22`/`OQ-24` (recursos extraordinários) — lacuna documentada, jamais estimativa silenciosa nem classificação inventada. É o mesmo padrão já praticado em `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (`app/montagem/estado.py:315`) | §13.8 · `sdd.config.md` §4 ("não inventar dado") · `AC-67` do motor · `piq-app-spec.md:2614` | essencial |
| `RF-40` | Ampliar a allowlist de `AC-41` com **exatamente os dois nomes** que a fatia 2A exige — `engine.estado.RESERVA_EXISTE` e `engine.estado.DISPOSICAO_USO_RESERVA` — pelo mesmo critério já aplicado quatro vezes (enum que **compõe** um tipo de entrada liberado: `TIPO_DIVIDA`, os 8 do Bloco 2, `TIPO_RENDA`, `Divida`), com comentário justificativo no padrão dos existentes. Os outros cinco nomes levantados pelo discovery (`ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`) **não** entram: a fatia 2A não os importa, e allowlist não contém nome que ninguém usa. `CLASSIFICACAO_MOBILIZACAO` e `Desconhecido` não exigem decisão — `engine.tipos` já é liberado por inteiro (`test_fronteira_import_engine.py:151-156`) | `AC-41` · discovery §1.2 (Critério A) · `OQ-20` | essencial |
| `RF-41` | Regravar `tests/app_aluno/estatica/hashes_congelados.json` a partir da **saída do próprio teste**, que nomeia arquivo por arquivo — nunca de uma lista transcrita de um enunciado. Inclui a entrada hoje ausente de `engine/ataque_imediato.py`. Atualizar o hash é o procedimento **correto**: `AC-44` proíbe que *esta feature* modifique `engine/`, e quem modificou foi o slug `motor-calculo` legitimamente, na sua Rodada 3 | `AC-44` · `test_engine_congelado.py:109`, `:139` · discovery §7 | essencial |
| `RF-42` | Atualizar as fixtures e os testes deste slug que constroem `EstadoFinanceiro` — `tests/app_aluno/fixtures/caso_completo.py`, `tests/app_aluno/test_conversao_decimal.py:300` e `tests/app_aluno/test_plano_ec07_ec08_ec09.py:347` — de modo que `build` volte a passar (hoje 1 erro) e a suíte de `tests/app_aluno/` volte a passar (hoje ~129 falhas de causa raiz única) | `sdd.config.md` §2 · `sdd.config.md` §8 | essencial |
| `RF-43` | Apresentar `RESERVA_MOBILIZAVEL` **desconhecida** como estado explícito ao aluno, jamais como `R$ 0,00` nem como campo omitido: quando o motor devolve `DESCONHECIDO` (Regra 3 da §13.1), a interface diz que a decisão sobre a reserva está pendente e que isso mantém aquela parte do plano em aberto. A **redação ao aluno é insumo externo** (`OQ-21`) — esta spec fixa o comportamento, não o texto | §13.1 ("não convertido silenciosamente em zero") · `engine/diagnostico.py:654` (`DinheiroTalvez`) · `RF-11`, `RF-12` · `OQ-21` · `motor-calculo:OQ-25` | essencial |
| `RF-44` | Manter a leitura do Bloco 4 **livre de qualquer agregação ou fórmula patrimonial**: nenhuma soma de valor de ativo, nenhum líquido realizável, nenhum corte de liquidez e nenhuma classificação de mobilização é produzida nesta camada. Todo valor entregue ao motor nesta fatia é uma resposta lida, convertida e tipada — nada derivado | `RF-34` (Lei nº 3) · `AC-67` do motor · §13.8 · `sdd.config.md` §6 | essencial |

### Rodada 3 (2026-09-14) — protótipo validado e máscara de entrada

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-45` | Servir a coleta como **aplicação de página única que nunca avalia `condicao_exibicao`**: o servidor entrega **uma pergunta já decidida exibível por vez**, e o cliente não recebe o grafo condicional nem meio de percorrê-lo. `RF-05` continua existindo em **um só lugar** — é esta restrição, e só ela, que separa este desenho do SPA recusado no plano §2 | `RF-03`, `RF-05` (não duplicar o grafo) · `RF-34` (Lei nº 3) · `plans/app-aluno.plan.md` §2 (revisão de 2026-09-14) | essencial |
| `RF-46` | Expor a rota `GET` de coleta que hoje **não existe** — sem ela o aluno cadastra, consente e não alcança pergunta nenhuma. Ela reusa `proxima_pergunta_nao_respondida` (`app/casos/progresso.py`) e `montar_contexto_pergunta` (`app/http/renderizacao.py`), ambos já implementados e testados por `T-45`/`T-43`, e **não** reimplementa a decisão de qual pergunta exibir | `RF-09`, `RF-10` · `AC-01` · `T-45` (deixou a rota fora de escopo) | essencial |
| `RF-47` | Aplicar **máscara de entrada por `TipoResposta`**, emitindo exatamente o formato que a fronteira única de conversão aceita (`app/montagem/conversao.py`). A máscara **formata, nunca corrige**: entrada ambígua segue para o servidor e é recusada lá, sem gravação — `EC-01` permanece soberano e a regra de parsing continua vivendo num lugar só | `RF-13` · `AC-09`, `AC-10` · `EC-01` · `sdd.config.md` §4 | essencial |
| `RF-48` | Manter a máscara **inerte quando `nao_sei` está marcado**: marcar "não sei" faz curto-circuito antes de qualquer conversão, e nenhuma formatação de cliente pode transformar essa resposta em valor numérico | `RF-11`, `RF-12` (não sei nunca vira zero) · `AC-08` | essencial |
| `RF-49` | Preservar o **caminho nativo sem JavaScript**: o `<form method="post">` continua gravando com a mesma rota e os mesmos sete passos, e a variante de resposta para a página única é **aditiva**, nunca substitutiva | `EC-05` · NFR de acessibilidade · `plans/app-aluno.plan.md` §2 (progressive enhancement) | essencial |

### Rodada 4 (2026-09-15) — frontend React e cobertura total do motor

> **Mudança de arquitetura, decidida pelo especialista em 2026-09-15.** A
> interface passa a ser uma aplicação React + TypeScript consumindo uma API
> JSON. Isso **revoga** — não delimita — a recusa de SPA registrada no §2 do
> plano. A consequência em `RF-05` é real e está endereçada por `RF-52`:
> o cliente continua sem avaliar `condicao_exibicao`, porque o servidor segue
> entregando uma pergunta já decidida por vez. O que se perde é o caminho sem
> JavaScript (`RF-49`/`EC-21`). `OQ-29` registrou esse custo e foi
> **respondida em 2026-09-17**: aceitável para este piloto, porque a
> coleta é preenchida majoritariamente no computador. `RF-49`/`EC-21`
> ficam revogados para esta rodada.

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-50` | Servir **todas** as telas do fluxo do aluno, do revisor e do operador a partir do design validado do protótipo `PIQ Meu Plano` — tokens, tipografia (Source Serif 4 + Atkinson Hyperlegible) e componentes. **Nenhuma tela fica fora do template**: uma tela sem o design é entrega incompleta, não "estilo pendente" | Protótipo validado com stakeholders · NFR de acessibilidade | essencial |
| `RF-51` | Expor **API JSON** para todo o fluxo: próxima pergunta, pergunta por `ID`, gravação de resposta, fichas repetíveis (listar/criar/remover item), plano, ações do Bloco 11, coleta dirigida (Blocos 7 e 8), Bloco 10, fila de revisão e painel do operador | `RF-45` · precedente de `rotas_bloco10.py` | essencial |
| `RF-52` | Manter `condicao_exibicao`, obrigatoriedade e materialidade **exclusivamente no servidor**, mesmo com cliente React: a API entrega uma pergunta já decidida exibível, e nenhum `.ts`/`.tsx` avalia condicional. `AC-73` continua valendo, agora sobre o código do frontend | `RF-05` (não duplicar o grafo) · `RF-34` (Lei nº 3) · `AC-73` | essencial |
| `RF-53` | Entregar as telas que **faltam** para o motor ser atendido de ponta a ponta: fichas repetíveis (108 perguntas em 5 escopos), CRUD de dívidas, Blocos 7, 8, 10 e 11, `REPROVADO_EM_REVISAO`, `ENCERRADO` e as ações do operador | §3 do levantamento de 2026-09-15 · `maquina.py:216-232` | essencial |
| `RF-54` | Disparar as três transições que hoje **não têm rota** — `PLANO_LIBERADO` → `COLETA_DIRIGIDA` / `CONFIRMACAO_ATAQUE` / `ACOMPANHAMENTO` —, sem as quais o caso morre no plano liberado | `maquina.py:216-232` · `AC-19`, `AC-22` | essencial |
| `RF-55` | Fazer a rota do Bloco 11 chamar `processar_resposta_bloco_11`, para que quitação confirmada dispare recálculo de fato | `RF-28`, `AC-30` · `app/casos/acompanhamento.py:564` | essencial |
| `RF-56` | Remover do escopo as telas do protótipo que são **redundantes**: `q-tipo`, `q-saldo`, `q-parcela`, `q-peso`, `q-margem`, `q-fim` são a mesma tela de pergunta gerada por registro, e `erro-salvar` é estado dela — nunca telas próprias | `RF-03` (gerar a partir do registro) | importante |

### Rodada 5 (2026-09-17) — navegação fiel ao protótipo

> **Origem.** A Rodada 4 entregou o frontend React e extraiu do protótipo os
> **tokens visuais** — cores, tipografia, raio, alvos de toque. A tela "parece"
> o protótipo. Mas a **arquitetura de navegação** foi inventada durante a
> implementação: uma barra com sete abas (Coleta · Dívidas · Plano · Ataque ·
> Ações · Fila · Painel) no lugar do fluxo linear guiado, sem "‹ Voltar", sem
> localizador, sem rodapé fixo, e sem as telas **Início** e **Meu progresso**.
>
> **A lacuna que permitiu isso está nesta spec.** `RF-50` fala de tokens e de
> componentes; o **modelo de navegação** ficou implícito, e o que não está
> escrito é inventado na implementação. Esta rodada escreve o que faltava.
>
> **O ponto mais grave é a tela Início.** No protótipo ela é o centro: lê a fase
> do caso e oferece **uma única próxima etapa**. Para alguém endividado e
> inseguro, é a diferença entre *"o que eu faço agora?"* e uma parede de sete
> opções, várias inaplicáveis ao momento dele.

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-57` | A navegação do aluno é **fluxo linear guiado**: uma tela por vez, com o caminho de volta e localizador no topo (`.top`) — o caminho de volta diz para onde leva: **"‹ Início"** quando leva ao Início, **"‹ Voltar"** só quando volta de fato à tela anterior (decisão do produto, 2026-10-01, `T-308`) e a ação no rodapé fixo (`.acoes`, `position: sticky`). **Nunca** uma barra que ofereça todas as telas de uma vez | Protótipo `PIQ Meu Plano`, linhas 75–89 (`.top`/`.actions`) e `go()`, linha ~820 · `RF-50` | essencial |
| `RF-58` | A tela **Início** lê o estado do caso e apresenta **uma única próxima etapa**. Nenhuma outra tela do aluno é ponto de entrada, e o destino da etapa é decidido **no servidor**, a partir da fase — o cliente não escolhe o que vem a seguir | Protótipo `renderInicio`, linha ~917 · `RF-01`, `RF-10`, `RF-31` · `RF-34` (Lei nº 3) | essencial |
| `RF-59` | As telas da equipe (fila de conferência, conferência do caso, painel) têm **rota e largura próprias** (900px, `.wide` do protótipo) e **não aparecem** na navegação de quem não é revisor. O papel vem do servidor no login (`e_revisor`), e serve **apenas** para a interface decidir o que oferecer — a autorização continua inteiramente no servidor, reverificada a cada requisição | Protótipo, linha 199 (`.wide`) e telas `equipe-*` · `RF-02` · `RF-35` · `exigir_papel_revisor` | essencial |
| `RF-60` | Expor `GET /caso/{CASO_ID}/inicio`, que devolve a **fase**, a mensagem de estado, o **destino da próxima etapa única** e o progresso da coleta (`respondidas`/`total`). O servidor manda o **destino** — dado estrutural, enum fechado —, nunca a redação: quem decide *qual* é a etapa é ele; quem decide *como dizer* é a interface, e `AC-37` proíbe redação longa no código da aplicação. O valor monetário em destaque viaja como **string em campo separado**, nunca interpolado numa frase montada pelo servidor — `RF-13` (dinheiro nunca atravessa `float`) e Lei nº 3 (o número é leitura de campo do snapshot) | `RF-58` · `RF-13` · `RF-34` · `AC-37` · `AC-42` | essencial |
| `RF-61` | Mapear os **12 membros de `ESTADO_CASO`** nas **cinco fases** do protótipo (`coleta`, `revisao`, `reprovado`, `plano`, `acompanhamento`) em módulo **puro**, com `match` exaustivo e sem `case _` — membro novo sem fase declarada não passa no `mypy`. **Nenhuma fase nova é criada**: `ENCERRADO` é `acompanhamento` com lista de ações vazia, e `ERRO_DE_CALCULO` é `revisao`, porque o erro técnico nunca é exposto ao aluno | Protótipo `renderInicio` (5 ramos) · `maquina.py::ESTADO_CASO` · precedente de `mensagens_de_estado.py` | essencial |
| `RF-63` | Expor no payload de pergunta a **posição da pergunta dentro da ficha corrente** (`posicao` e `total_na_ficha`), para que o localizador do `.top` diga *"Dívida 3 · pergunta 4 de 12"* como no protótipo. A contagem é do **servidor** — é ele que conhece o conjunto de perguntas exibíveis daquela ficha; o cliente formata a frase e nada mais. Numa pergunta fora de ficha repetível, os dois campos vêm nulos e o localizador cai no rótulo do bloco | `OQ-30` (respondida 2026-09-17, saída 1) · Protótipo, linha 323 · `RF-57` · `RF-45` (o cliente não conta o que é do servidor) | importante |
| `RF-62` | Contar a coleta como `respondidas`/`total` **reusando a varredura já existente** de `app/casos/progresso.py`: `proxima_pergunta_nao_respondida` e a contagem consomem o **mesmo** gerador de ocorrências, para que barra de progresso e retomada nunca divirjam. `total` conta apenas as perguntas **abertas agora** (condição verdadeira) — o denominador varia conforme o aluno responde, e isso é correto: exibir um total que inclui perguntas que nunca abrirão mentiria sobre o tamanho do trabalho restante | `RF-31` · `RF-45` (o cliente não avalia condição) · protótipo, `62 de 195` | essencial |

### Rodada 6 (2026-09-18) — orientação: onde estou e para onde vou

> **Origem: teste com usuário.** A Rodada 5 entregou a tela Início fiel ao
> protótipo — uma próxima etapa, sem barra de abas. Ao usá-la pela primeira
> vez contra o banco real, o especialista relatou: *"não gostei, me senti
> perdido, sem saber o que é, qual o objetivo"*.
>
> **O diagnóstico não é de layout.** A tela mostra "Continuar de onde você
> parou" e "3 de 101", e ambos estão corretos. O que falta é o **enquadramento**:
> 101 do quê, continuar rumo a quê, e o que acontece quando terminar. `RF-58`
> resolveu *"o que eu faço agora?"* e deixou intacta a pergunta anterior —
> *"onde eu estou, e onde isso vai dar?"*.
>
> Para alguém endividado, essa segunda pergunta não é curiosidade: é o que
> separa "estou construindo algo" de "estou preenchendo um formulário sem fim".

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-64` | A tela Início apresenta a **jornada inteira do caso em cinco etapas** — coleta, cálculo, conferência, plano, acompanhamento —, marcando qual está **em curso**, quais já **passaram** e quais **faltam**. A trilha fica visível, nunca atrás de um clique: é o mapa que responde *"onde eu estou"*, e esconder o mapa é o que produziu o relato de estar perdido | §1 Overview (as cinco superfícies de interação) · `RF-01` (o caso é máquina de estados) · `RF-61` (as cinco fases) | essencial |
| `RF-65` | A etapa em curso mostra **o que falta nela**, em linguagem do aluno: na coleta, quantas perguntas restam; na conferência, que a espera é da equipe; no acompanhamento, quantas ações aguardam reporte. Número sem unidade — *"3 de 101"* — não informa, e um total que o aluno não sabe do que é soa como formulário infinito | `RF-31` · `RF-62` · relato de uso (2026-09-18) | essencial |
| `RF-66` | Um aluno que **ainda não respondeu nada** vê, antes do Início, uma tela de **boas-vindas** que diz o que o PIQ faz, o que ele vai receber ao final, que pode parar e voltar quando quiser, e que **uma pessoa confere o plano** antes de ele chegar. A tela aparece **uma vez** — some assim que houver qualquer resposta — e nunca bloqueia: há sempre como seguir | §1 Overview · `RF-23` (revisão humana obrigatória) · `RF-10` (multissessão) · relato de uso | essencial |
| `RF-67` | A trilha e as boas-vindas **derivam do estado do caso**, nunca de preferência gravada no cliente: quem decide o que já passou é a fase (`RF-61`) e o progresso (`RF-62`), ambos do servidor. Nenhum `localStorage` decide o que o aluno vê — trocar de aparelho não pode mudar em que ponto da jornada ele está | `RF-10` (retomada em outro dispositivo) · `RF-34` (Lei nº 3) · `RF-45` | essencial |

### Rodada 7 (2026-09-18) — rever, corrigir e caber na tela

> **Origem: segundo teste com usuário**, sobre a mesma tela da Rodada 6.
> Três relatos, três defeitos distintos:
>
> 1. *"as perguntas que eu respondi não consigo editar"* — **o backend sempre
>    permitiu**. `GET /caso/{id}/pergunta/{ID}` devolve qualquer pergunta com
>    `valor_atual` preenchido, e a gravação aceita sobrescrita. O que nunca
>    existiu foi **tela**: a coleta só andava para a frente.
> 2. *"nem consigo ver o que foi respondido, e se eu esquecer"* — não há
>    nenhuma superfície que liste as respostas dadas. `RF-10` promete retomada
>    sem redigitar; não promete **conferência**, e é isso que falta.
> 3. *"por que está com a largura fixa?"* — os 560px vêm do protótipo, que foi
>    desenhado para celular. A coleta é preenchida majoritariamente no
>    computador (`OQ-29`, respondida), onde a coluna estreita desperdiça a tela.

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-68` | O aluno **revê todas as respostas que deu**, agrupadas pelas cinco partes da coleta, vendo lado a lado a pergunta e o que respondeu. Retomar sem redigitar (`RF-10`) não é o mesmo que conferir: quem não consegue reler o que disse sobre o próprio dinheiro não tem como confiar no plano que sai dali | `RF-10` · `RF-31` · relato de uso (2026-09-18) | essencial |
| `RF-69` | O aluno **corrige qualquer resposta já dada**, a partir da revisão e também durante a coleta, sem reiniciar nada. A correção usa a **mesma** rota de gravação da resposta original — não existe caminho paralelo de escrita — e o valor anterior chega preenchido, para que corrigir seja editar, nunca redigitar | `RF-10` · `AC-02` · `EC-01` (a validação continua soberana) | essencial |
| `RF-70` | Durante a coleta, o aluno alcança a **pergunta anterior e a seguinte** entre as que já respondeu, sem passar pela lista. Errar a pergunta anterior e perceber na seguinte é o caso mais comum de correção, e mandá-lo à lista para isso é desproporcional. **A anterior é a respondida imediatamente antes no percurso** (ficha item a item, `item_id` incluído, condicionais avaliadas), nomeada pelo servidor no payload da pergunta (`anterior`) — nunca remontada no cliente a partir de `/respostas`, cuja ordem é a dos registros agrupada por parte (decisão do produto, 2026-10-01, `T-309`). **A seguinte** (`seguinte`, "Pergunta seguinte ›") é a imediatamente depois no mesmo percurso, nomeada pelo servidor só quando a pergunta exibida já está respondida — na fronteira (a pendente) não há seguinte, o aluno responde. Ela só navega: não regrava a resposta; com alteração não salva, o aluno confirma o descarte antes (decisão do produto, 2026-10-01, `T-318`) | `RF-68` · relato de uso · `T-309` · `T-318` | importante |
| `RF-71` | A interface **se adapta à largura da janela**: no computador, a jornada ocupa uma coluna lateral e o conteúdo o restante; no celular, a tela permanece **exatamente** como o protótipo validado — coluna única de 560px, na ordem validada. O layout de duas colunas é progressivo e nunca aparece onde não cabe | Protótipo validado (560px) · `OQ-29` (respondida: preenchido no computador) · NFR de responsividade (360px) | importante |

### Rodada 8 (2026-09-19) — acabamento visual: o que nunca foi especificado

> **Origem: avaliação do especialista sobre a plataforma entregue**, não um
> defeito funcional. O relato: *"estou achando a plataforma muito simples […] o
> layout não está dando essa sensação de entrega absurda e personalizada"*.
>
> **O diagnóstico não é de desleixo — é de lacuna de spec.** A auditoria do
> código mediu, em todo o `frontend/src/`: **zero** `box-shadow`, **zero**
> gradiente, **zero** `transition` ou `hover`, **zero** ícones (só um `✓`
> textual), e **treze** estados de carregamento literalmente idênticos
> (`<p>Carregando…</p>`). No CSS compilado, o único `box-shadow` é o
> `box-shadow:none` do reset do Tailwind.
>
> Nada disso foi decidido. `RF-50` fixa **tokens, tipografia e componentes** —
> e é exatamente essa spec que já reconheceu, na Rodada 5 (linha 221), que
> *"o que não está escrito é inventado na implementação"*. Elevação,
> hierarquia tipográfica, iconografia, micro-interação e estado de
> carregamento nunca foram escritos, e o resultado é uma interface plana por
> omissão — correta em tudo que foi especificado, e sem a densidade de
> acabamento que a entrega ao cliente exige.
>
> **A confirmação de que os testes não cobrem isto está no próprio plano**
> (`plans/app-aluno.plan.md:2250-2276`): o rodapé `sticky` chegou a sobrepor o
> cartão da próxima etapa, ilegível, com os 66 E2E verdes. *"Asserção de
> presença não substitui olhar a tela."* Qualidade visual não é medida por
> nenhuma trava — por isso precisa virar requisito.
>
> **Esta rodada é aditiva por construção.** Nenhum token de cor muda (os sete
> pares auditados a 4,5:1 seguem intactos), nenhuma classe é renomeada, nenhuma
> largura validada é tocada, e nenhuma funcionalidade é alterada.

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-72` | A interface tem uma **escala de elevação** aplicada **por papel**, não por padrão: o objeto que exige a atenção do aluno — a próxima etapa, o resumo do plano — se destaca do que é contexto ou nota de rodapé. As sombras derivam da cor `ink` em alfa baixo, nunca de preto neutro, para que a profundidade carregue o viés da paleta validada. **Elevação não substitui nenhum sinal existente**: a borda de 2px do `.cartao-proximo` (`RF-58`) continua sendo o que marca a próxima etapa | `RF-50` (lacuna: componentes sem profundidade) · avaliação do especialista (2026-09-19) | importante |
| `RF-73` | O aluno distingue **hierarquia tipográfica** dentro de uma tela: o número que responde à pergunta que ele veio fazer — prazo do plano, custo futuro — aparece em escala de manchete, e o que é apoio aparece abaixo dele. Todo valor monetário ou numérico comparável usa **numerais tabulares**, para que os dígitos alinhem entre linhas. A escala não altera a base de 19px nem as duas famílias validadas | `RF-50` (tipografia validada) · NFR de acessibilidade · avaliação do especialista | importante |
| `RF-74` | A interface tem **iconografia própria**, desenhada para o vocabulário do PIQ (dívida, prazo, conferência, reserva). Todo ícone é **decorativo e nunca focável** (`aria-hidden`), jamais o único portador de um significado — o rótulo textual sempre existe ao lado. O sprite `public/icons.svg`, que hoje contém apenas ícones de redes sociais do template do Vite e não é referenciado por nenhuma tela, é removido | Auditoria de `frontend/public/icons.svg` (boilerplate não utilizado) · NFR de acessibilidade (WCAG 1.4.1: cor/forma nunca sozinhas) | importante |
| `RF-75` | Toda tela que espera dados mostra um **esqueleto com a forma do conteúdo que vem**, no lugar do texto solto "Carregando…" — hoje repetido em treze telas. O esqueleto é `aria-hidden`; o anúncio a leitor de tela continua sendo o `role="status"` que já existe, com a mesma redação. Quem pediu menos movimento (`prefers-reduced-motion`) recebe o mesmo esqueleto, parado | Auditoria (13 ocorrências idênticas) · NFR de acessibilidade · precedente do `.pulse` (`T-150`) | importante |
| `RF-76` | Os controles **respondem ao apontador e ao toque**: botões, opções e itens de lista têm estado de `hover` e de acionamento. Hoje não existe nenhum — o aluno não recebe confirmação de que o alvo está sob o cursor antes de clicar. O anel de foco de 3px permanece exatamente como está, e a resposta ao apontador nunca o substitui | Auditoria (zero `hover`/`transition` no `src/`) · NFR de acessibilidade (foco permanece soberano) | importante |
| `RF-77` | A **trilha da jornada** (`RF-64`) ganha trilho contínuo e marcas de estado por etapa, tornando visível de relance o que passou, o que é agora e o que falta. Ela permanece **informativa e nunca navegável**: nenhum degrau é clicável, e o único botão da tela continua sendo o da próxima etapa — tornar a trilha clicável seria restabelecer a barra de abas que `RF-57`/`AC-83` mataram | `RF-64` · `RF-57` · `AC-83` · `plans/app-aluno.plan.md:2212-2216` | importante |
| `RF-78` | A repaginação **não altera nenhum sinal validado**: os onze tokens de cor mantêm nome e valor, as duas famílias tipográficas e a base de 19px permanecem, os alvos de toque de 56/60/48px permanecem, as larguras de 560px e 900px permanecem, e os nomes de classe que a suíte usa como seletor (`.top`, `.corpo`, `.acoes`, `.back`, `.linha`, `.cartao-proximo`, `.item`, `.chip`) não são renomeados. Toda adição é **aditiva** | `RF-50` · `AC-87` · `AC-106` · travas de `test_acessibilidade_coleta.py` e `frontend/tests/e2e/` | essencial |

### Rodada 9 (2026-09-30) — decisões do especialista `DE-01` a `DE-08`

> **Origem.** Formulário de decisões respondido pelo especialista (Rodrigo),
> com contribuições do revisor (Marcelo); onde divergiram, vale Rodrigo.
> `DE-02` e `DE-06` confirmadas pelo responsável do produto em 30/09/2026.
> Cada requisito cita o `DE-NN` de origem; o que a decisão não fixava foi
> aberto em §10 (`OQ-52` a `OQ-67`) e **resolvido em 2026-09-30 por decisão
> da equipe técnica** (responsável do produto), com base nas decisões e
> observações do especialista — os requisitos abaixo já refletem as
> resoluções.
>
> **A Lei nº 3 continua valendo.** Sobra da B3.C00, valor líquido do desconto
> e rateio mensal são **agregação de entrada** feita na montagem (`app/`),
> do mesmo tipo de `RENDA_TOTAL_RECORRENTE`/`DESPESAS_OPERACIONAIS_ATUAIS`
> (`OQ-16`) — não regra do motor (`OQ-53`, `OQ-55`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-79` | A tela de confirmação da fotografia do mês (`B3.C00`) mostra **Renda total**, **Despesas totais** e **Sobra do mês** (= Renda total − Despesas totais). Os totais consolidam tudo o que foi informado no Bloco 3 — Renda total é `RENDA_TOTAL_RECORRENTE` e Despesas totais é a parte do Bloco 3 de `DESPESAS_OPERACIONAIS_ATUAIS` + `DESPESAS_NAO_MENSAIS_NORMALIZADAS`, nas composições de `OQ-16` (o seguro cobrado à parte, que a montagem soma às despesas operacionais por `RF-81`, é da dívida e fica fora da fotografia — decisão de 2026-09-30, `T-232`) — e as decomposições (categorias, não mensais) **nunca** são somadas de novo. Parcelas de dívidas continuam cadastradas **só** no Inventário (Bloco 5): a sobra exibida é a do orçamento **antes das dívidas**, e é rotulada assim. Os três valores são agregação de entrada produzida na montagem, não cálculo do motor (`OQ-53`) | `DE-01` (`q1_1`, `q1_2`) · `B3.C00` · `OQ-16` · `OQ-53` (resolvida) | essencial |
| `RF-80` | As decomposições da fotografia (despesas por categoria, despesas não mensais convertidas para o mês) ficam **acessíveis para consulta e edição** a partir da `B3.C00`, sem aparecer na tela de confirmação, pela mesma rota de correção de `RF-69`. A resposta "Ainda não consigo avaliar" (`NAO_SEI`) **não tem ação especial**: o fluxo segue | `DE-01` · `B3.C00` · `RF-68`, `RF-69` | essencial |
| `RF-81` | Na ficha de dívida com seguro (`B5.D05 = Sim`), coletar a **situação do seguro prestamista** em três casos, com consequência distinta: **(1) prêmio único financiado** — já compõe saldo/parcela, **não é somado de novo** em nenhum fluxo; **(2) cobrado mensalmente à parte** — despesa mensal **da própria dívida** (custo da operação), enquanto a cobrança existir; a montagem a soma às despesas mensais operacionais entregues ao motor, uma vez por dívida, nunca à parcela, e ela nunca aparece nos totais do Bloco 3 da `B3.C00` (decisão do responsável do produto de 2026-09-30, risco `R9-1`, `T-232`); **(3) cancelado com restituição** — cessa a cobrança futura, e a restituição só é registrada quando **confirmada**, como recurso extraordinário. Situação **"Não sei"** → o seguro não é somado em lugar nenhum e o dado fica registrado como **"não informado"** (não é "Pendente de confirmação", reservado a informação verbal) | `DE-03` (`q3_1`) · `DE-06` · `B5.D05`, `B5.D05A`, `B5.D05B` · `OQ-54` (resolvida) | essencial |
| `RF-82` | Valor de seguro informado como **total** (`B5.D05A`) é custo total do seguro, **nunca** despesa mensal. Um equivalente mensal só existe para análise, **com período de cobertura informado**, rotulado como **rateio** — nunca como nova despesa. O aluno recebe orientação para verificar apólice/certificado, prêmio total, forma de cobrança, se a contratação é facultativa, e como solicitar cancelamento e eventual restituição proporcional, que **não é garantida** (texto em `textos-canonicos.yaml`, aplicado e pendente de validação do especialista — `T-245`, `T-289`) | `DE-03` (`q3_1`) · `B5.D05A` · `OQ-67` | essencial |
| `RF-83` | Na proposta com desconto (`B7.13A`), coletar e guardar **separadamente**: (1) **valor atual de quitação antes do desconto** — nunca chamado de "saldo devedor"; (2) tipo do desconto, R$ ou %; (3) valor ou percentual informado; (4) **valor final para quitação**; (5) validade da proposta, quando houver (`B7.15`). O valor final informado pelo credor **prevalece** como referência da oferta; o desconto calculado (R$ → bruto − desconto; % → bruto × (1 − %)) serve só para **conferência**. O percentual incide **só** sobre o valor de (1) — nunca sobre valor contratado, saldo histórico ou soma das parcelas, salvo declaração expressa do credor. O valor líquido é agregação de entrada feita na montagem (`OQ-55`) | `DE-03` (`q3_2`) · `B7.13`, `B7.13A`, `B7.15` · `OQ-55` (resolvida) | essencial |
| `RF-84` | Travas do desconto, na gravação: percentual aceito **apenas entre 0% e 100%**; desconto em R$ **nunca maior** que o valor de quitação antes do desconto. Informados R$ **e** % juntos: compara-se o desconto em R$ com bruto × % **arredondado a R$ 0,01**; diferença **> R$ 0,01** → **sinalizar divergência** (a tolerância de `sdd.config.md` §5 não se aplica). Nunca somar os dois (`OQ-55`) | `DE-03` (`q3_2`) · `B7.13A` · mesmo padrão de validação cruzada de `RF-07`/`EC-02` | essencial |
| `RF-85` | Custo informado "por mês" ou "total" (`B8.12A`; também `B5.D05A`): guardar **tipo** (mensal/total), **valor**, **período de incidência** e, quando aplicável, **meses restantes**. Mensal é despesa recorrente enquanto durar; total é custo único da operação e **nunca** é somado a cada mês — se parcelado, entra no fluxo mensal só a parcela efetivamente paga. Custo já embutido na parcela ou no saldo (`B5.D05B`/`B8.12B` = Sim) não é somado de novo. **Mensalização só com prazo informado**: sem prazo, nenhum valor mensal é inventado | `DE-03` (`q3_3`) · `B8.12`, `B8.12A`, `B8.12B` · `B5.D05A` | essencial |
| `RF-86` | Com inventário incompleto, o aluno **pode continuar preenchendo** qualquer etapa, mas **não pode concluir o diagnóstico nem gerar o plano**: o Bloco 6 não executa enquanto houver pendência de `RF-87` ou `RF-88`. Enquanto a pendência existir, um **alerta permanente** de "inventário incompleto" fica visível ao aluno. Este bloqueio **substitui** o "plano provisório" de `RF-15`/`AC-07` sempre que declarado ≠ cadastrado; nos demais casos `RF-15` continua valendo | `DE-04` (`q4_1`, `q4_2`) · `RF-15` · `RF-16` · `OQ-56` (resolvida) | essencial |
| `RF-87` | Dívidas: com `B5.00` numérico, cadastradas **abaixo** do declarado bloqueiam, com mensagem exata: *"Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas."* Cadastradas **acima** do declarado: o sistema pede ao aluno que atualize `B5.00` (ação direta, na própria mensagem) e o cálculo final fica **bloqueado até igualar** (`q4_1`). `B5.00` = "Não sei exatamente quantas": a completude passa a ser a confirmação do aluno em `B5.FIM01` ("Não, esta foi a última"). O aluno pode voltar e completar o cadastro a qualquer momento | `DE-04` (`q4_1`) · `B5.00`, `B5.FIM01` · `OQ-56`, `OQ-57` (resolvidas) | essencial |
| `RF-88` | Renda extra (`B3.03` = Sim, renda recorrente adicional), vínculo consignável (`B3.S01` = Sim) e despesa não mensal (`B3.NM01` = Sim): precisa cadastrar **ao menos um item** antes do cálculo final — ou mudar a resposta para **Não**. Mensagem **específica por caso**, no padrão *"Você informou que possui X, mas ainda não cadastrou nenhum(a)"* (ex.: *"Você informou que possui despesa não mensal, mas ainda não cadastrou nenhuma"*) | `DE-04` (`q4_2`) · `B3.03`, `B3.S01`, `B3.NM01` · `OQ-57` (resolvida) | essencial |
| `RF-89` | O servidor pode cadastrar **mais de um vínculo**, cada um em ficha própria (`VINCULO_ID`) com órgão/ente pagador, tipo de vínculo, `RENDA_BRUTA_VINCULO` (base da margem), renda líquida (**coletada** e usada numa **conferência**: a soma das rendas líquidas dos vínculos é comparada à renda informada no Bloco 3, e a divergência é sinalizada ao aluno e ao revisor — nunca somada de novo nem entregue ao motor como entrada nova), existência de consignação e margens (total, utilizada e disponível). Nomes técnicos dos campos novos: a critério do plano | `DE-05` (`q5_1`) · canônica v1.0.2 `E-09` · `RF-04` · `OQ-58`, `OQ-59` (resolvidas) | essencial |
| `RF-90` | A **margem pertence ao vínculo**: cada `MARGEM_ID` é cadastrada dentro de exatamente um `VINCULO_ID`, e **todo** contrato consignado — inclusive cartão consignado e cartão benefício — aponta para o vínculo em que é descontado. **Nunca somar margens** de vínculos diferentes — nem em tela, nem em relatório, nem no estado entregue ao motor | `DE-05` (`q5_1`, `q5_2`) · canônica v1.0.2 `E-09` · `RF-07` · `OQ-59`, `OQ-60` (resolvidas) | essencial |
| `RF-91` | Renomear para o aluno e o revisor o conceito de fonte do dado (`FONTE_DADO`: `B5.I02`, `B7.16`, `B8.15`) para **"Fonte de comprovação"**, com três níveis: **(1) Comprovado por documento/registro** — contrato, documento, aplicativo/internet banking, mensagem/e-mail, contracheque; **(2) Informado pelo aluno, sem comprovação** — memória, "Não tenho registro", "Uma combinação dessas fontes", "Outra"/"Outra fonte" sem documento associado; **(3) Pendente de confirmação** — informação fornecida verbalmente (ex.: informada em atendimento), sem documento/registro. O nível fica registrado **por dado** e **não** alimenta `CONFIABILIDADE_DADOS` do motor | `DE-06` (`q6_1`) · `B5.I02`, `B7.16`, `B8.15` · `OQ-61`, `OQ-63` (resolvidas) | essencial |
| `RF-92` | Nível 2 ou 3 **não bloqueia** o plano (exceção: dado indispensável em nível 3, `RF-93`): fica **sinalizado para validação posterior**, exibido por dado ao revisor e no plano | `DE-06` · `RF-26` · `OQ-63` (resolvida) | essencial |
| `RF-93` | Dado **indispensável** — campo que o motor exige para calcular aquela dívida/estado (saldo, taxa, parcela/prazo, renda), os mesmos cuja ausência já gera pendência — em "Pendente de confirmação" ou ausente: o cálculo roda, mas a **liberação pelo revisor fica bloqueada** enquanto houver pendência; a tela do revisor **lista** cada pendência (caso, dívida, dado) e a liberação só fica disponível depois que o dado for confirmado ou corrigido. Homologar é essa liberação (`RF-23`), fiel a `q8_1` ("não pode ser homologado"). Taxa: "não sei a taxa" e periodicidade da taxa "não sei" são ausência (pendem); taxa informada como **estimada** não pende — só reduz a confiança (`T-283`, `T-287`; Rodrigo, 2026-09-30) | `DE-06` · `DE-08` · `RF-23` · `OQ-62`, `OQ-64` (resolvidas) | essencial |
| `RF-94` | O Bloco 7 segue fluxo condicional: *existe proposta?* (`B7.04`) → **Não**: todo o bloco da proposta é saltado; **Sim**: a proposta é **à vista, parcelada ou ambas**. Parcelada → número de parcelas, valor da parcela e demais dados do parcelamento; à vista → o valor para quitação à vista, a validade, o desconto e a fonte da proposta (decisão do responsável do produto de 2026-09-30, risco `R9-3`, `T-242`); ambas → os dois conjuntos são coletados. **Validade** da proposta (`B7.15`) pode ser perguntada em qualquer tipo; **prazo do parcelamento** (`B7.09`) só na parcelada | `DE-07` (`q7_1`) · `B7.04`, `B7.07`, `B7.08`, `B7.09`, `B7.15` · `OQ-65` (resolvida) | essencial |
| `RF-95` | Campo não aplicável ao tipo de proposta **não aparece nem conta como ausente**: não entra na contagem de progresso (`RF-62`), não gera pendência e não chega ao motor como `DESCONHECIDO`/`INFORMACAO_PENDENTE` | `DE-07` · `RF-12` · `RF-62` | essencial |
| `RF-96` | Homologação: nenhum resultado é pré-fixado — o motor apura caso a caso. A referência de aprovação são os gabaritos `GAB-A`, `GAB-B`, `GAB-C` e os invariantes. **Todo teste de homologação registra**: ordem final de ataque, mês de quitação de cada dívida, valor mensal destinado ao plano, custo total de juros e uso da reserva — cada item lido ou derivado de forma exata de campos existentes do `SnapshotOrdem` (cronograma incluído), com a correspondência fixada no plano; o que não for derivável de forma exata é registrado "não disponível", nunca estimado (decisão do produto `R9-6`, 2026-09-30; `T-268`) | `DE-08` (`q8_1`, `q8_2`) · `sdd.config.md` §5 · `OQ-66` (resolvida) | essencial |
| `RF-97` | Se faltar dado indispensável (`RF-93`), o sistema sinaliza, nomeando o dado, que o resultado **não pode ser homologado** — a liberação na fila fica bloqueada até o dado ser confirmado ou corrigido (`RF-93`) — e nunca presume valor | `DE-08` (`q8_1`) · `RF-12` · `GAB-03` · `OQ-62`, `OQ-64` (resolvidas) | essencial |
| `RF-98` | Recursos extraordinários (`B3.05A–D`): o aluno cadastra **vários**, cada um com tipo, valor, janela e certeza, e a montagem os entrega ao motor **item a item**, nunca somados como se tivessem a mesma certeza. Em Férias/abono, o valor coletado é **só o acréscimo (1/3)**. O plano apresenta o **cenário adicional** (segunda projeção com os `PROVAVEL` e os `POSSIVEL`; nenhum deles entra na projeção-base até ser recebido), separado e rotulado, lido do snapshot. A regra de projeção é do motor (`motor-calculo` `RF-70`–`RF-76`) — esta camada lê e entrega. Restituição de seguro confirmada (`B5.D05R`) cria um item com `ORIGEM_RECURSO_EXTRAORDINARIO = B5.D05R` (nome ratificado na canônica v1.0.4, `E-16`), cujas perguntas abrem mesmo com `B3.05 = Não`; nesse caso o aluno recebe um aviso curto de que a restituição será considerada valor extraordinário (decisão do produto, 2026-09-30, `T-288`). Textos ao aluno: aprovados pelo responsável do produto em 2026-09-30 (`T-289`); a explicação do cenário adicional e o enunciado de Férias/abono ficam pendentes de validação do especialista | `DE-02` (`q2_1`–`q2_3`) · canônica v1.0.2 `E-10` · `RF-39` (fatia 2B) · `OQ-22`(b) (resolvida, `T-208`) · `OQ-24` (tarefa técnica) · `OQ-67` (resolvida) | essencial |

### Rodada 10 (2026-10-01) — perguntas complementares na mesma tela

> **Decisão do responsável do produto, 2026-10-01.** Quando a opção escolhida
> abre perguntas complementares, elas aparecem **na mesma tela, logo abaixo,
> como uma thread**, em vez de em outra página. O servidor continua decidindo
> o que abre. Isto **resolve `OQ-46`** (discovery "Coleta agrupada por
> categoria") **para este caso** — a condicional dentro da mesma tela — pela
> saída "o servidor pré-avalia e manda o mapa": o cliente recebe, por opção,
> a lista já decidida e só a consulta pelo valor escolhido. Agrupamento por
> categoria/bloco (`OQ-47`–`OQ-51`) continua em aberto.

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-99` | Ao servir uma pergunta cuja resposta abre perguntas complementares no **mesmo bloco e na mesma ficha, imediatamente depois dela**, o payload traz `complementares`: para cada opção que abre algo, as perguntas filhas (profundidade 1) que ficariam exibíveis se a mãe recebesse aquele valor — calculado **no servidor**, com a mesma `avaliar` sobre as respostas gravadas mais o valor provisório da mãe. O cliente desenha as filhas sob a opção escolhida, com recuo e transição sutil, e as esconde ao trocar de opção (respostas escondidas não são enviadas). Gravar é **mãe primeiro, filhas depois**, pela mesma rota de `RF-69`, cada filha com a validação de sempre; filha recusada mostra o erro junto dela e a mãe continua gravada. `RF-45`/`RF-52` continuam valendo: nenhum `.ts`/`.tsx` avalia condição | Decisão do produto (2026-10-01) · `OQ-46` (resolvida para este caso) · `RF-45`, `RF-52`, `RF-69` · `T-307` | importante |

### Rodada 10 (2026-10-01) — trilha da coleta e fichas que nascem com o item

> **Decisões do responsável do produto, 2026-10-01**, após teste no sistema
> (`T-308`–`T-311`). Textos novos ao aluno: redação da equipe técnica,
> aprovada pelo produto na mesma data (lista em `T-310`/`T-311`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-100` | Na tela de pergunta e na lista de fichas, a **trilha da coleta** mostra as cinco partes de `/respostas` (`RF-68`) com o estado de cada uma — concluída (✓), atual (destacada, `aria-current`) e próximas (esmaecidas) — e uma barra discreta de **partes concluídas** (nunca de perguntas: o total cresce a cada ficha e a barra pareceria regredir, `T-293`). No desktop é a coluna lateral (`RF-71`); no celular, a barra no topo e o resumo "Parte N de 5 · rótulo". O estado vem do servidor (`trilha` no payload); o cliente não avalia condição nem conta perguntas. A trilha é informativa, nunca navegável (`AC-115`) | Decisão do produto (2026-10-01) · `RF-45`, `RF-62`, `RF-67`, `RF-68`, `RF-71`, `RF-77` · `T-310` | importante |
| `RF-101` | Ao declarar algo que abre fichas ainda sem item (`B3.03` renda extra, `B3.S01` vínculo, `B3.NM01` despesa não mensal, `B3.05` valores extraordinários, `B5.00`/`B5.00A` dívidas), o servidor **cria o primeiro item** e a coleta segue direto para a primeira pergunta dele. Ao terminar um item desses escopos, a lista reabre com "Adicionar outro(a)" — que também abre direto a primeira pergunta do item novo — e "Continuar". As fichas criadas pelo checklist de despesas (`T-217`) seguem como estão | Decisão do produto (2026-10-01) · `RF-04`, `RF-53`, `RF-45` · `T-212`, `T-291` · `T-311` | importante |

### Rodada 10 (2026-10-01) — ficha curta em uma tela

> **Decisões do responsável do produto, 2026-10-01**, após teste no sistema
> (`T-314`–`T-317`). Textos novos ao aluno: redação da equipe técnica,
> aprovada pelo produto na mesma data (lista em `T-314`–`T-317`). Os registros
> novos de `RF-103` entram na canônica como **v1.0.6** (errata `E-18`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-102` | Nas **fichas curtas** — `ITEM_DESPESA`, `RECURSO_EXTRAORDINARIO_ID`, `RENDA_ADICIONAL_ID`, `DESPESA_NAO_MENSAL_ID`, `VINCULO_ID`, `MARGEM_ID` (não `DIVIDA_ID`, que segue pergunta a pergunta) — todas as perguntas exibíveis do item aparecem num **formulário único**, com um botão "Salvar". O servidor decide quais estão exibíveis (`GET /caso/{id}/formulario/{escopo}/{item_id}`, perguntas serializadas como na coleta, com `complementares` de `RF-99`); trocar uma resposta que abre/fecha outras do item só consulta `complementares` — o cliente não avalia condição (`RF-45`). "Salvar" grava em sequência pela rota de `RF-69` (mãe antes das filhas), mostra o erro junto de cada campo e, com o item completo, volta à lista do escopo ("+ Adicionar outro(a)" e "Continuar", `RF-101`). A retomada e o "Continuar" levam ao formulário quando a próxima pendência é de ficha curta | Decisão do produto (2026-10-01) · `RF-45`, `RF-69`, `RF-99`, `RF-101` · `T-314` | importante |
| `RF-103` | No topo do formulário e da lista de toda ficha curta, o aviso "Cadastre um(a) {item} de cada vez. Depois você pode adicionar outros(as)." ("Cadastre um valor de cada vez…" nos valores extraordinários). Opção "Outro" sem campo de texto nas fichas curtas ganha uma pergunta de **texto curto** logo depois da mãe, aberta só por ela (complementar na mesma tela): `B3.05AO` "Descreva a origem do valor." (`DESCRICAO_RECURSO_EXTRAORDINARIO`, `TIPO_RECURSO_EXTRAORDINARIO = OUTRO`), e pelo mesmo padrão `B3.03AO`, `B3.NM02AO`, `B3.NM02CO`, `B3.S06AO`. Só coleta — nenhuma regra do motor as lê | Decisão do produto (2026-10-01) · `RF-99` · canônica v1.0.6 `E-18` · `T-315` | importante |
| `RF-104` | "Sim" em `B3.D11` (despesa não listada) leva **direto ao formulário do item novo** — nome + `B3.DF01`–`DF04` na mesma tela —, sem passar pela lista; na lista, "+ Adicionar outra despesa" abre o formulário de outro item, quantas vezes o aluno quiser. O "Outro" dos checklists `B3.D01`–`D10` segue pedindo o nome na lista (`T-217`) e também no formulário | Decisão do produto (2026-10-01) · `T-217`, `T-311` · `T-316` | importante |
| `RF-105` | No formulário da ficha curta, o localizador diz a **posição do item entre os itens do escopo** ("Despesa 2 de 4") e uma barra mostra os **itens concluídos** do escopo, ambos calculados no servidor (`posicao_do_item`, `total_de_itens`, `itens_concluidos`). Não substitui a trilha de partes (`RF-100`) | Decisão do produto (2026-10-01) · `RF-62`, `RF-100` · `T-317` | importante |

### Rodada 10 (2026-10-01) — fichas curtas na mesma tela, sem branco e em sequência

> **Decisões do responsável do produto, 2026-10-01**, após teste no sistema
> (`T-319`–`T-322`). Textos novos ao aluno: redação da equipe técnica,
> aprovada pelo produto na mesma data (lista em `T-319`–`T-321`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-106` | A pergunta que abre uma **ficha curta ainda sem item** (`B3.03` renda extra, `B3.05` valores extraordinários, `B3.NM01` despesa não mensal, `B3.S01` vínculo, `B3.D11` despesa não listada) mostra, ao marcar a opção que abre, **os campos do primeiro item logo abaixo, na mesma tela** (como a thread de `RF-99`). O servidor decide o que é exibível: o payload da pergunta traz `ficha_nova` — por `valor_interno`, o escopo e as perguntas que o primeiro item exibiria, serializadas como em `RF-102` e avaliadas com a mãe provisória. Ao salvar: grava a mãe → o servidor cria o item (`RF-101`) e a `proxima` o nomeia → o cliente grava os campos naquele `item_id` (`RF-69`) → conclui (`RF-107`) → a lista do escopo abre com "+ Adicionar outro(a)" e "Continuar". Escopo que já tem item segue `RF-101`. Não vale para a dívida nem na correção (`RF-69`) | Decisão do produto (2026-10-01) · `RF-45`, `RF-69`, `RF-99`, `RF-101`, `RF-102`, `RF-104` · `T-319` | importante |
| `RF-107` | No formulário da ficha curta (e na ficha nova de `RF-106`), **todo campo exibível do item precisa de resposta ou "Não sei"** — os mesmos predicados da retomada (`itens_em_aberto`, `T-201`); a despesa que pede nome precisa do nome. O cliente destaca o que falta e não grava; o servidor confirma em `POST /caso/{id}/concluir/{escopo}/{item_id}`, recusando com `400`, mensagem legível e `pendencias`. Resposta gravada em branco (`""`) não conta como respondida. Vale para criar e para revisar | Decisão do produto (2026-10-01) · `RF-11`, `RF-45`, `RF-102` · `T-320` | importante |
| `RF-108` | Concluído um item de ficha curta, o servidor nomeia o **próximo item pendente do mesmo escopo** (mesmo pai; depois do atual, senão o primeiro antes) e o formulário dele abre em seguida ("Despesa 4 de 20"); sem nenhum pendente, a lista do escopo reabre com "+ Adicionar outro(a)" e "Continuar" | Decisão do produto (2026-10-01) · `RF-101`, `RF-105` · `T-321` | importante |

### Rodada 10 (2026-10-01) — "Não sei" no formato das opções e o inventário que diz quais

> **Decisões do responsável do produto, 2026-10-01**, após teste no sistema
> (`T-323`, `T-324`). Textos novos ao aluno: redação da equipe técnica,
> aprovada pelo produto na mesma data (lista em `T-323`/`T-324`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-109` | Nas perguntas de valor (`MOEDA`, `TAXA`, `NUMERO`, `DATA`), **todas as alternativas não numéricas do registro, inclusive "Não sei", aparecem no mesmo formato**: um grupo de opções exclusivas (estilo `.opt`) junto ao campo de valor — nada de checkbox à parte. Escolher uma alternativa limpa o campo; digitar um valor desmarca a alternativa. A gravação não muda (`NAO_SEI`, o código da alternativa ou o valor). Vale na tela da pergunta e no formulário de ficha. Nas perguntas de seleção segue `T-207`. Revisa `AC-78` nos tipos de valor: "inerte" passa a ser campo vazio, não travado | Decisão do produto (2026-10-01) · `RF-11`, `RF-48`, `RF-50`, `AC-78` · `T-323` | importante |
| `RF-110` | O alerta de dívidas faltando (`RF-87`) **diz quais**: abaixo da mensagem de `RF-87` (literal, primeira linha), os **tipos marcados na declaração de tipos (`B5.00A`) que ainda não têm nenhuma ficha** daquele tipo (`TIPO_DIVIDA`, pelo rótulo legível) e as **fichas já cadastradas** (credor e tipo de cada uma), com a ação "Cadastrar a próxima dívida", que reabre a ficha criada e vazia ou cria uma e abre a primeira pergunta (`RF-101`). Como a declaração dá só o total, não há contagem por tipo. Cálculo no servidor (payload de `/inventario`); o cliente só escreve | Decisão do produto (2026-10-01) · `RF-86`, `RF-87`, `RF-101`, `DE-04` · `T-324` | importante |

### Rodada 11 (2026-10-02) — Plano e conferência em linguagem humana

> **Decisão do responsável do produto, 2026-10-02**, após ver o plano do
> caso de teste na conferência: "o relatório gerado está usando siglas do
> sistema, deveria ser mais humano para que possamos interpretar". Rótulos
> novos: redação da equipe técnica, a aprovar pelo produto (lista em `T-326`).

| ID | Requisito | Regras / seções / IDs de origem | Prioridade |
| --- | --- | --- | --- |
| `RF-111` | **Nenhum código interno é o texto principal do plano (aluno) nem da conferência (revisor).** (a) A dívida é identificada pelo **tipo legível e credor** ("Cheque especial — CAIXA ECONOMICA FEDERAL") na ordem, nas ações e nas pendências; o código (`D011`) aparece só ao revisor, como detalhe discreto. (b) Na conferência, cada dado de entrada (`estado_inputs`) tem **rótulo em português** e **valor legível**: opção pelo rótulo do registro, moeda em R$, taxa em %, data dd/mm/aaaa, lista separada por vírgula, item composto (ex.: valores extraordinários) descrito item a item — nunca a representação interna; `DESCONHECIDO` vira "Não informado". (c) Método, status do método, cenário e motivo do recálculo aparecem por rótulo; o **método é do caso, não da dívida**: aparece uma vez, em destaque ("Método selecionado para este aluno"), com o critério da ordem em uma frase (`textos-canonicos.yaml`, `criterio_do_metodo`); cada posição mostra só o nome e a explicação já mostrada ao aluno — a justificativa técnica do motor (`JUSTIFICATIVA_POSICAO`) não aparece (revisão de 2026-10-02, `T-330`). (d) Absorve `T-306`: a descrição das ações requeridas ao aluno vem de `textos-canonicos.yaml` por `TIPO_ACAO`, e o carimbo não mostra código de cenário. (e) Nas telas da equipe (fila, conferência, painel "Quem está onde") o caso é identificado pelo **e-mail do aluno**; o `CASO_ID` fica só como detalhe discreto. A tradução é do relatório/servidor; o motor (`engine/`) não muda e o cliente não traduz códigos | Decisão do produto (2026-10-02) · `EC-07`, `AC-17`, `RF-92`, `T-177`, `T-306` · `T-326`, `T-327`, `T-330` | importante |
| `RF-112` | O painel do operador (`RF-35`) passa a se chamar **"Painel de usuários"** (botão na fila: "Ver painel de usuários") e lista **só alunos** — contas com `e_revisor = true` não aparecem (a gestão de revisores fica para um futuro painel de administração). Layout minimalista em **tabela de largura total**, uma linha por aluno, colunas **E-mail · Etapa · Status**: Etapa é o estado do caso por rótulo (nunca o código `ESTADO_CASO`) e, na coleta, a parte da trilha (`RF-100`); Status é o que já existe — "Aguarda conferência", "Cálculo bloqueado" e o tempo parado ("parado há 15 h"). Nenhum dado financeiro (critério de `RF-35` mantido). No celular, a tabela vira lista compacta sem rolagem lateral. **Coluna Nome** (`OQ-68`): o nome do comprador vindo da Hotmart, gravado na conta no provisionamento; conta sem nome mostra "—" (`T-332`) | Decisão do produto (2026-10-02) · `RF-35`, `RF-59`, `RF-100`, `RF-111` · `T-331`, `T-332` | importante |
| `RF-113` | **"Pedir correção" devolve o plano ao aluno.** Na conferência, além da observação interna, o revisor escreve uma **"Mensagem para o aluno"** (obrigatória para pedir correção). A reprovação continua registrada com autor, data, classificação, observação e a mensagem, e o snapshot segue intacto (append-only); o caso **volta ao questionário** com todas as respostas preservadas. No Início, enquanto não reenviar, o aluno vê um aviso fixo com **a mensagem do revisor** e **a lista dos dados a conferir** (as pendências de homologação de `RF-93`, por nome da dívida e rótulo da pergunta, cada uma levando à pergunta), e a ação **"Enviar para nova conferência"**, que recalcula (`RF-14`) e devolve o caso à fila como nova versão. A observação interna nunca chega ao aluno. Revisa `EC-12` | Decisão do produto (2026-10-02) · `EC-12`, `RF-23`, `RF-26`, `RF-93`, `RF-69` · `T-333` | essencial |
| `RF-114` | **Em cálculo ou em conferência, as respostas ficam só para leitura.** Enquanto o caso está em `CALCULANDO` ou `AGUARDANDO_REVISAO`, o aluno **lê** tudo em "Minhas respostas", mas não há ação "Editar" e o servidor recusa (`409`, "Seu plano está em conferência. Para mudar uma resposta, retire-o da conferência.") qualquer gravação: resposta, criação, nome, remoção ou conclusão de ficha. A regra vale no servidor, não só na tela. O revisor decide sempre sobre o que o aluno enviou: nenhuma resposta muda por baixo do plano que ele está conferindo | Relato de uso (2026-10-05): a taxa do cheque especial foi alterada depois do cálculo e nunca chegou ao revisor · `RF-23`, `RF-26`, `RF-69` · `T-336` | essencial |
| `RF-115` | **"Quero editar minhas respostas" retira o plano da conferência.** Em `AGUARDANDO_REVISAO`, "Minhas respostas" oferece a ação **"Quero editar minhas respostas"**, com confirmação ("Seu plano sai da conferência. Quando você enviar de novo, ele volta para a fila."). Confirmada, o caso **volta a `COLETA_INICIAL`** (gatilho `aluno_retoma_edicao`, evento na trilha), com todas as respostas preservadas, o snapshot intacto (append-only) e o caso **fora da fila do revisor**. O reenvio é o `bloco_6_executa` de sempre e gera a nova versão encadeada à anterior (`V-01`), como em `RF-113`. Em `CALCULANDO` a ação não existe: o aluno espera o cálculo terminar | Decisão do produto (2026-10-05) · `RF-113`, `RF-114`, `V-01`, `RF-31` · `T-336`, `T-337` | essencial |
| `RF-116` | **Quem decide e quem retira não se atropelam.** Se o revisor tenta liberar ou reprovar um caso que o aluno já retirou da conferência, a decisão é recusada (`409`, "Este plano saiu da conferência: o aluno o retirou para editar ou ele foi devolvido. Ele volta à fila quando for reenviado.") e **nenhum registro de revisão é gravado**. Se os dois agem ao mesmo tempo, vence quem primeiro conseguir a transição de estado (mesma trava de `RF-31`); a decisão que perde fica só na trilha de auditoria, sem efeito sobre o estado | Decisão do produto (2026-10-05) · `RF-23`, `RF-24`, `RF-115` · `T-336`, `T-337` | essencial |
| `RF-117` | **A pergunta de renda diz o que informar.** `B3.01` pede o valor **depois do imposto de renda e da previdência e antes de empréstimos e consignados**, com a orientação de que as parcelas dessas dívidas são cadastradas no Bloco 5 e que plano de saúde, sindicato e outros descontos de folha entram nas despesas. O motivo é que o motor desconta as parcelas das dívidas da renda (`RENDA_TOTAL_RECORRENTE`): informar o que cai na conta contaria cada consignado duas vezes | Decisão do produto (2026-10-05) · `RF-79`, `B3.01`, `B3.S` · `T-338` | essencial |
| `RF-118` | **O aluno pede um plano novo depois da liberação.** Em `PLANO_LIBERADO` e `ACOMPANHAMENTO`, "Minhas respostas" oferece **"Gerar um novo plano com as minhas respostas"**. Antes de confirmar, o aluno lê: o plano atual continua disponível; o novo será calculado com **todas** as respostas de agora e **conferido pela equipe de novo**, o que pode levar o tempo da fila; quando ficar pronto, substitui o atual. Confirmada a ação, o caso volta a `COLETA_INICIAL` (gatilho `aluno_refaz_plano`, evento na trilha), o plano liberado fica **intacto e visível** (`OQ-09`: o aluno só vê plano liberado) e o cálculo é disparado pelo reenvio de sempre, que gera a versão seguinte **encadeada** à anterior (`V-01`, como em `RF-113`). **Só o aluno pede**: o revisor não edita o plano, apenas o devolve com mensagem (`RF-113`). Os dados já informados nos Blocos 7, 8, 10 e 11 ficam preservados | Decisão do produto (2026-10-05): depois da liberação, editar uma resposta não gerava plano novo · `RF-113`, `RF-114`, `RF-115`, `OQ-09`, `V-01` · `T-341`, `T-342` | essencial |
| `RF-119` | **O plano novo nasce das respostas atuais.** O `estado_inputs` da versão nova reflete cada resposta alterada desde a anterior (renda, despesas, dívidas, taxas); nada vem do snapshot anterior além do encadeamento. A versão anterior continua gravada como estava (append-only) | `RF-14`, `RF-118`, `V-01` · `T-341` | essencial |
| `RF-120` | **O Início oferece o plano novo e avisa quando há respostas atualizadas.** Com plano liberado (`PLANO_LIBERADO`, `ACOMPANHAMENTO`), o Início mostra a ação **"Gerar um novo plano"** com a mesma confirmação de `RF-118`; quando as respostas mudaram desde o cálculo do plano, a ação vira um **aviso**: "Você atualizou suas respostas depois do seu plano. Quer enviá-las para gerar um novo plano?". Quem decide é o servidor, comparando o estado financeiro montado das respostas atuais com o `estado_inputs` do plano liberado (`respostas_atualizadas`); se a comparação não for possível (a montagem recusa uma resposta), o servidor não afirma mudança (`null`) e o Início oferece só a ação neutra. Em conferência (`AGUARDANDO_REVISAO`) o Início oferece **"Quero editar minhas respostas"** com a confirmação de `RF-115`. Confirmada qualquer das ações, a tela segue para onde o fluxo pede: o cálculo (plano novo) ou "Minhas respostas" (editar) | Decisão do produto (2026-10-05): a opção precisa estar no Início, onde o aluno chega | `RF-115`, `RF-118`, `RF-119`, `RF-58` · `T-343`, `T-344` | essencial |
| `RF-121` | **A conferência mostra o plano como o aluno vai recebê-lo.** A tela do revisor traz o plano com o **mesmo conteúdo e o mesmo visual** da tela do aluno (cabeçalho com o nome, resumo, ponto de partida, primeiro passo, primeira vitória, como funciona, jornada, linha do tempo, dívidas, reserva, pendências, cenário adicional, dúvidas e carimbo), com a **mesma redação canônica** (`AC-14`). No monitor largo o plano do aluno ocupa uma coluna e o painel do revisor (método, homologação, pendências, fontes, dados de entrada) a outra; em tela estreita o plano do aluno vem primeiro. O que é só do aluno (baixar o PDF liberado, "Responder agora") não aparece para o revisor | Decisão do produto (2026-10-05): o especialista valoriza ver o formato que o aluno recebe · `RF-26`, `AC-29`, `AC-14` · `T-345`, `T-347` | essencial |
| `RF-122` | **Cada dívida do plano traz, para o revisor, os dados dela.** No cartão de cada dívida, uma seção recolhível **"Para o revisor"** mostra os dados de entrada **daquela dívida** (os mesmos de `AC-29`, já formatados, com `DESCONHECIDO` visível). A justificativa técnica da posição (`JUSTIFICATIVA_POSICAO`) continua fora da tela — o critério do método aparece uma vez (`T-330`) — e o aluno nunca a recebe. As ações mostram o motivo técnico, só para o revisor | Decisão do produto (2026-10-05) · `RF-26`, `T-305`, `AC-29` · `T-345`, `T-348` | essencial |
| `RF-123` | **O revisor vê o que mudou desde a versão anterior.** Num plano refeito (versão 2 ou mais), a conferência lista, campo a campo, o que mudou nos dados de entrada em relação à versão anterior (renda, despesas, taxas, parcelas, saldos): nome do campo, valor anterior e valor atual, ambos formatados pelo servidor. Campo igual não aparece; campo que só existe de um lado aparece como "novo" ou "removido". Na versão 1 não há comparação | Decisão do produto (2026-10-05): o aluno pode pedir plano novo (`RF-118`) · `RF-118`, `V-01`, `AC-29` · `T-345`, `T-348` | importante |
| `RF-124` | **O revisor abre a prévia do PDF.** Antes de liberar, o revisor abre o PDF que o aluno receberá, marcado "Prévia — ainda não liberado". É a **mesma** montagem do PDF liberado (`OQ-09`), sem exigir liberação, e só para quem tem papel de revisor. O PDF do aluno continua só do plano liberado (`AC-25`) | Decisão do produto (2026-10-05) · `OQ-09`, `AC-25`, `RF-23` · `T-346` | importante |
| `RF-125` | **O plano apresenta o curso de entrada e a nota de incômodo.** O plano traz uma introdução recomendando o curso Servidor Sem Dívidas, um quadro das aulas que ajudam no caso (só do que consta nas legendas do curso) e orientações em texto, sem percentual, para reduzir despesas, aumentar renda e reduzir juros. Em cada dívida, mostra a nota de incômodo que o aluno deu e, com nota 9 ou 10 em dívida fora da 1ª posição, um aviso de que a ordem seguiu o critério do método. Sem valor extra no mês (resultado zero, sem estabilização), avisa o aluno. O revisor vê, por dívida, o que o aluno respondeu sobre atraso, cobrança judicial e garantia. Nada disso altera a ordem nem o cálculo | Pedido do produto (2026-10-05) · `RF-124`, `AC-37` · `T-351` a `T-354` | importante |
| `RF-126` | **O plano mostra o prognóstico em três caminhos.** O capítulo "Seu plano em números" (5º, na mesma posição de antes) mostra, quando há prognóstico, **uma linha por caminho, empilhadas e na mesma escala de meses**, cada uma com uma frase-veredito, uma barra com um círculo numerado em cada dívida quitada, só nas linhas do plano e do plano acelerado, e, dentro de cada um desses blocos, o quadro das dívidas quitadas (número, nome e mês de quitação, em ordem de quitação); abaixo, a tabela "Quando cada dívida termina" (uma coluna por caminho). Sem prognóstico (plano antigo), o capítulo mantém os três números de antes. **Seu plano detalhado** (6º) é um mural com um bloco por mês — "Mês 01", "Mês 02"…, sempre referência, nunca data — do plano seguido e do acelerado, com o saldo devedor e o valor extra do mês; cada bloco é um link para o cartão do mês. **Mês a mês, em detalhe** (7º) traz um cartão por mês de cada plano (dívida da vez e extra, saldo ao fim do mês, quitações e as duas instruções: pagar as parcelas de sempre e guardar o comprovante do pagamento extra). Os capítulos "O que fazer no Mês 1", "Seu checklist do Mês 1", "Seu plano, mês a mês", "Sua primeira dívida quitada" e "Quando cada dívida termina" (como capítulo) deixam de existir. O texto reforça que o Mês 1 é o primeiro mês em que o aluno começa a seguir o plano. O questionário ganha a pergunta opcional `B3.C01A` ("quanto a mais por mês conseguiria acrescentar"). Números do snapshot, mesma tela e PDF; sem prognóstico no snapshot (plano antigo), o capítulo 5 mantém os três números de antes e os capítulos 6 e 7 não aparecem | Pedido do produto (2026-10-06) · `RF-125`, `RF-77`, `RF-78` · `T-171`, `T-172` | importante |

## 3. User Stories

### `US-01` — Responder em várias sessões sem perder nada

> Como **aluno**, quero **fechar o navegador no meio da coleta e voltar dias
> depois de onde parei**, para **não precisar redigitar 195 perguntas nem
> desistir no meio**.

Atende: `RF-01`, `RF-02`, `RF-09`, `RF-10`

### `US-02` — Cadastrar minhas dívidas uma a uma

> Como **aluno**, quero **cadastrar cada dívida em sua própria ficha**, com
> saldo, taxa, garantia, cobrança, documentação e peso emocional, para **ter um
> inventário fiel em vez de um campo de texto livre**.

Atende: `RF-03`, `RF-04`, `RF-06`, `RF-07`, `RF-15`

### `US-03` — Dizer "não sei" sem que o sistema invente por mim

> Como **aluno**, quero **poder responder "não sei" quando de fato não sei o
> saldo ou a parcela**, para **receber um plano honesto e provisório em vez de
> um plano bonito construído sobre um número inventado**.

Atende: `RF-11`, `RF-12`, `RF-13`

### `US-04` — Saber por onde começar

> Como **aluno**, quero **ver qual dívida atacar primeiro, em que ordem as
> demais caem, quanto tempo leva e quanto custa**, para **executar um plano em
> vez de decidir no escuro**.

Atende: `RF-14`, `RF-16`, `RF-20`, `RF-21`, `RF-22`

### `US-05` — Responder só o que o motor abriu para mim

> Como **aluno**, quero **receber perguntas de renegociação e troca apenas para
> as dívidas em que isso faz sentido**, para **não responder 46 perguntas
> irrelevantes ao meu caso**.

Atende: `RF-08`, `RF-17`

### `US-06` — Decidir quanto do recurso disponível eu realmente uso

> Como **aluno**, quero **confirmar quanto do ataque imediato recomendado eu de
> fato pretendo usar**, para **que o plano seja recalculado sobre o valor que eu
> realmente tenho, não sobre o que seria ideal**.

Atende: `RF-18`

### `US-07` — Não receber um plano que ninguém olhou

> Como **revisor**, quero **que todo relatório passe pela minha fila antes de
> chegar ao aluno**, inclusive os recálculos, para **que nenhum erro de texto,
> parâmetro, dado, regra, cálculo ou UX chegue a uma pessoa real**.

Atende: `RF-23`, `RF-24`, `RF-25`, `RF-26`

### `US-08` — Reportar o que aconteceu e ver o plano se ajustar

> Como **aluno**, quero **reportar meses depois que executei uma ação, quitei
> uma dívida ou algo mudou**, para **que meu plano seja recalculado sobre a
> realidade, sem apagar o histórico do que já foi decidido**.

Atende: `RF-01`, `RF-19`, `RF-27`, `RF-28`, `RF-29`, `RF-33`

### `US-09` — Nova versão do questionário sem reescrever o app

> Como **especialista**, quero **publicar uma nova versão do questionário
> editando registros**, para **que corrigir um enunciado ou uma condição não
> vire uma tarefa de desenvolvimento**.

Atende: `RF-03`, `RF-04`, `RF-05`, `RF-06`, `RF-07`, `RF-08`, `RF-32`

### `US-10` — Entregar dado pessoal com garantia de tratamento

> Como **aluno**, quero **saber a que consento, por quanto tempo meus dados
> ficam guardados e como pedir exclusão**, para **entregar dívida, renda e
> contracheque sem estar assinando um cheque em branco**.

Atende: `RF-02`, `RF-30`

### `US-11` — Saber quem travou onde

> Como **operador do piloto**, quero **ver em que ponto cada caso está**, para
> **agir sobre o abandono antes que o piloto termine sem nenhum caso completo**.

Atende: `RF-31`

### `US-12` — Um único lugar onde o cálculo mora

> Como **especialista**, quero **que nenhuma regra de cálculo seja reimplementada
> fora do motor**, para **que um erro de cálculo tenha um só lugar possível onde
> morar, e os gabaritos continuem provando o que provam**.

Atende: `RF-16`, `RF-19`, `RF-32`, `RF-34`

### Rodada 2 (2026-09-07) — fatia 2A

### `US-13` — Ver a reserva que eu mesmo declarei

> Como **aluno que tem uma reserva e aceita colocar parte dela em análise**,
> quero **que o valor que informei apareça no diagnóstico**, para **que o plano
> considere o dinheiro que eu de fato disse estar disposto a usar, e não zero**.

Atende: `RF-36`, `RF-37`, `RF-38`

### `US-14` — Adiar a decisão sobre a reserva sem virar zero

> Como **aluno que respondeu "prefiro decidir depois de ver a análise" ou "não
> sei"**, quero **que o sistema mostre que essa decisão está pendente**, para
> **não descobrir tarde que minha reserva foi tratada como inexistente**.

Atende: `RF-37`, `RF-43`

### `US-15` — Não ver patrimônio inventado no meu lugar

> Como **aluno que declarou investimentos e ativos**, quero **que o sistema não
> decida sozinho o que é mobilizável no meu patrimônio**, para **não receber uma
> recomendação apoiada numa classificação que ninguém fez**.

Atende: `RF-39`, `RF-44`

### `US-17` — Chegar até a primeira pergunta

> Como **aluno recém-cadastrado**, quero **abrir o app e ver a próxima pergunta
> que falta responder**, para **começar a coleta sem depender de alguém me
> mandar um link de pergunta específica**.

Atende: `RF-45`, `RF-46`, `RF-49`

### `US-18` — Digitar dinheiro sem errar a vírgula

> Como **aluno respondendo pelo celular**, quero **ver o valor se formatando
> enquanto digito**, para **não enviar um número ambíguo e ter a resposta
> recusada depois de já ter digitado tudo**.

Atende: `RF-47`, `RF-48`

### `US-16` — Um app que compila e uma suíte que passa

> Como **desenvolvedor deste slug**, quero **que a montagem do estado acompanhe
> o contrato de entrada do motor**, para **que a mudança de contrato de outro
> slug não deixe o app parado com o `build` quebrado e a suíte vermelha**.

Atende: `RF-40`, `RF-41`, `RF-42`

### `US-19` — Saber qual é o meu próximo passo, e só ele

> Como **aluno endividado e inseguro**, quero **abrir o app e ver uma única
> coisa para fazer agora**, para **não ter que decidir sozinho, diante de sete
> opções, qual delas se aplica ao meu momento**.

Atende: `RF-57`, `RF-58`, `RF-60`, `RF-61`, `RF-62`

### `US-21` — Saber onde estou na jornada, e onde isso vai dar

> Como **aluno que acabou de entrar**, quero **ver a jornada inteira e em que
> ponto dela eu estou**, para **saber que estou construindo algo com começo e
> fim, em vez de preencher um formulário sem tamanho conhecido**.

Atende: `RF-64`, `RF-65`, `RF-67`

### `US-22` — Entender o que é isto antes de começar

> Como **aluno entrando pela primeira vez**, quero **que me digam o que o PIQ
> faz e o que vou receber**, para **não começar a responder cem perguntas
> sobre o meu dinheiro sem saber para quê**.

Atende: `RF-66`

### `US-23` — Reler e corrigir o que eu disse

> Como **aluno no meio da coleta**, quero **ver tudo o que já respondi e poder
> corrigir**, para **não ficar com medo de ter errado um valor e não ter como
> voltar atrás**.

Atende: `RF-68`, `RF-69`, `RF-70`

### `US-24` — Usar a tela inteira do computador

> Como **aluno respondendo no computador**, quero **que a tela aproveite o
> monitor**, para **não preencher cem perguntas por uma fresta no meio de uma
> tela vazia**.

Atende: `RF-71`

### `US-25` — Receber algo que parece feito para mim

> Como **aluno que entregou cem respostas sobre o próprio dinheiro**, quero
> **que a tela do meu plano pareça um documento preparado para o meu caso**,
> para **acreditar que alguém olhou a minha situação, e não que preenchi mais
> um formulário genérico**.

Atende: `RF-72`, `RF-73`, `RF-74`, `RF-75`, `RF-76`, `RF-77`, `RF-78`

### `US-20` — Não esbarrar em telas que não são minhas

> Como **aluno**, quero **que a interface não me ofereça a fila de conferência
> nem o painel da equipe**, para **não bater numa porta fechada e achar que o
> sistema está quebrado, ou que há algo meu ali que não estou conseguindo ver**.

Atende: `RF-59`

### Rodada 9 (2026-09-30) — decisões do especialista

### `US-26` — Conferir meu mês em três números (`DE-01`)

> Como **aluno**, quero **ver minha renda total, minhas despesas totais e o
> que sobra antes das dívidas**, para **validar a fotografia do meu mês sem
> ler uma tabela de categorias**.

Atende: `RF-79`, `RF-80`

### `US-27` — Seguro, desconto e custos sem contar duas vezes (`DE-03`)

> Como **aluno**, quero **informar seguro, desconto e custos como o credor me
> passou — por mês, no total, em R$ ou em %**, para **que o plano não conte o
> mesmo dinheiro duas vezes nem invente um valor mensal que ninguém me cobra**.

Atende: `RF-81`, `RF-82`, `RF-83`, `RF-84`, `RF-85`

### `US-28` — Saber o que falta antes do plano (`DE-04`)

> Como **aluno**, quero **continuar preenchendo e saber exatamente quantas
> fichas faltam**, para **não receber um plano calculado sobre um inventário
> que eu mesmo sei que está incompleto**.

Atende: `RF-86`, `RF-87`, `RF-88`

### `US-29` — Cadastrar cada vínculo com sua margem (`DE-05`)

> Como **servidor com mais de um vínculo**, quero **cadastrar cada vínculo com
> a sua margem e ligar cada consignado ao vínculo onde é descontado**, para
> **que o plano não trate duas folhas como uma margem só**.

Atende: `RF-89`, `RF-90`

### `US-30` — Ver o que está comprovado (`DE-06`)

> Como **revisor**, quero **ver, por dado, se ele tem comprovação, foi só
> informado ou está pendente de confirmação**, para **saber em que confiar
> antes de liberar o plano**.

Atende: `RF-91`, `RF-92`, `RF-93`

### `US-31` — Responder só o que a minha proposta tem (`DE-07`)

> Como **aluno**, quero **responder apenas as perguntas que fazem sentido para
> a proposta que recebi**, para **não ser cobrado por parcelas de uma
> quitação à vista**.

Atende: `RF-94`, `RF-95`

### `US-32` — Homologar com evidência comparável (`DE-08`)

> Como **especialista**, quero **que todo teste de homologação registre ordem,
> meses de quitação, valor mensal, juros e uso da reserva**, para **comparar
> objetivamente o esperado com o calculado**.

Atende: `RF-96`, `RF-97`

### `US-33` — Contar com o 13º sem apostar no precatório (`DE-02`)

> Como **aluno**, quero **informar cada valor extraordinário com o quanto ele
> é certo**, para **que o plano use o que é confirmado e me mostre o resto só
> como possibilidade**.

Atende: `RF-98`

### `US-34` — Mudar uma resposta sem desencontrar o plano

> Como **aluno**, quero **poder editar minhas respostas quando percebo um erro, sabendo que meu plano sai da conferência e volta quando eu reenviar**, para **que o revisor nunca confira um plano calculado com dados que já mudaram**.

Atende: `RF-114`, `RF-115`, `RF-116`, `RF-117`

### `US-35` — Refazer meu plano quando minha situação muda

> Como **aluno**, quero **pedir um plano novo depois de corrigir ou atualizar minhas respostas**, sabendo que ele será conferido de novo e que o atual continua valendo até lá, para **que o plano reflita a minha vida de agora sem eu perder o que já tenho**.

Atende: `RF-118`, `RF-119`, `RF-120`

### `US-36` — Conferir o plano como o aluno vai recebê-lo

> Como **revisor**, quero **ver o plano com o mesmo visual e a mesma redação que o aluno vai receber, com os dados e o que mudou ao alcance**, para **liberar ou devolver sabendo exatamente o que ele vai ler**.

Atende: `RF-121`, `RF-122`, `RF-123`, `RF-124`

## 4. Acceptance Criteria

> Todo critério abaixo é verificável sem reinterpretação: descreve entrada e
> resultado observável, e vira teste direto.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-01` | `US-01` | Dado um caso com os Blocos 1–3 respondidos e a sessão encerrada, quando o aluno autenticar de outro dispositivo, então todas as respostas anteriores estão presentes e a coleta retoma na primeira pergunta não respondida do Bloco 4 — nenhum campo já respondido é pedido de novo |
| `AC-02` | `US-01` | Dado um caso em coleta, quando o aluno responder uma pergunta, então a resposta está persistida antes da próxima pergunta ser exibida — encerrar o processo imediatamente depois não perde a resposta |
| `AC-03` | `US-01` | Dadas credenciais de um caso A, quando autenticado, então nenhuma resposta, snapshot ou relatório do caso B é acessível por qualquer rota da aplicação |
| `AC-04` | `US-02` | Dado o Bloco 5, quando o aluno cadastrar três dívidas, então existem três fichas independentes, cada uma com seu `DIVIDA_ID` estável, e responder a ficha 2 não altera nenhum campo das fichas 1 e 3 |
| `AC-05` | `US-02` | Dado `B11.Q01` para a dívida `D003`, quando a pergunta for exibida, então o enunciado apresenta o identificador `D003` interpolado no lugar do marcador `[Dxxx]` |
| `AC-06` | `US-02` | Dada uma margem `MARGEM_ID` com `VALOR_TOTAL_MARGEM = 1000`, quando o aluno informar `VALOR_UTILIZADO_MARGEM = 1200`, então a resposta é recusada com mensagem, e o valor não é gravado nem enviado ao motor |
| `AC-07` | `US-02` | Dado `B5.FIM02` respondido com "Não. Ainda falta pelo menos uma dívida" ou "Não tenho certeza", quando o estado for montado, então `INVENTARIO_COMPLETO = False`, e o plano emitido sai com `ORDEM_STATUS ≠ DEFINITIVA_NA_DATA` e `STATUS_METODO` no máximo `PROVISORIO` |
| `AC-08` | `US-03` | Dada uma dívida rotativa em que o aluno respondeu "não sei" para saldo e para pagamento mensal, quando o `EstadoFinanceiro` for montado, então `SALDO_DEVEDOR_ATUAL` e `PAGAMENTO_MENSAL_EFETIVO` chegam ao motor como `DESCONHECIDO` — nunca `0`, nunca `None`, nunca estimativa (reprodução de `GAB-03`) |
| `AC-09` | `US-03` | Dado qualquer campo monetário do questionário, quando o valor for convertido da entrada do formulário, então o objeto entregue ao motor é `Decimal` e a construção do `EstadoFinanceiro` não levanta o `TypeError` de `_recusar_float` |
| `AC-10` | `US-03` | Dada a entrada `"1234,56"` num campo de moeda, quando convertida na fronteira, então o valor resultante é exatamente `Decimal("1234.56")`, e nenhum `float` aparece em nenhum ponto do caminho de conversão |
| `AC-11` | `US-03` | Dado um campo cujo registro na §11 não admite "não sei", quando o aluno tentar deixá-lo em branco, então a coleta não avança e a pergunta permanece pendente |
| `AC-12` | `US-04` | Dado um caso com a Etapa B completa, quando o Bloco 6 executar, então `calcular_plano(...)` é invocado exatamente uma vez com o estado montado, e o `SnapshotOrdem` devolvido é persistido antes de qualquer exibição |
| `AC-13` | `US-04` | Dado um `EstadoFinanceiro` montado pela coleta, quando comparado ao contrato de `engine/estado.py`, então todos os campos obrigatórios estão preenchidos, incluindo as 8 variáveis de `PerfilComportamental`, os 10 campos de `SinaisComportamentais` e `AUTOPERCEPCAO_CONTROLE` |
| `AC-14` | `US-04` | Dado qualquer plano exibido ao aluno, quando a tela ou o documento for produzido, então o título é exatamente "Sua ordem projetada de quitação" e o texto é exatamente o de `Q-03`, caractere por caractere |
| `AC-15` | `US-04` | Dado qualquer texto apresentado ao aluno sobre a ordem, quando auditado, então a palavra "projetada" aparece e nenhuma das palavras "definitiva", "final" ou "fixa" qualifica a ordem |
| `AC-16` | `US-04` | Dado qualquer plano entregue ao aluno ou exibido ao revisor, quando renderizado, então `ENGINE_VERSION` e `PARAMETROS_VERSION` do snapshot aparecem na saída |
| `AC-17` | `US-04` | Dada uma ordem publicada com N dívidas, quando exibida, então cada uma das N posições apresenta sua `JUSTIFICATIVA_POSICAO` |
| `AC-18` | `US-04` | Dado o `EstadoFinanceiro` montado, quando `DATA_REFERENCIA` for definida, então ela vem de entrada explícita do caso e não de leitura de relógio — recalcular o mesmo caso com a mesma `DATA_REFERENCIA` produz o mesmo `SNAPSHOT_ID` |
| `AC-19` | `US-05` | Dado um snapshot cuja `ORDEM_ACOES` contém ação de renegociação apenas para `D002`, quando os Blocos 7/8 forem abertos, então as perguntas do Bloco 7 são exibidas para `D002` e para nenhuma outra dívida |
| `AC-20` | `US-05` | Dado `B12.16`, quando a pergunta for exibida, então as opções apresentadas são as 2 ou 3 regras que o motor produziu para aquele caso, e nenhuma opção fixa em código aparece fora dessa lista |
| `AC-21` | `US-05` | Dado `B12.08`, quando nenhuma das quatro origens de relevância de cartão for verdadeira, então a pergunta não é exibida; e quando qualquer uma delas for verdadeira, então ela é exibida |
| `AC-22` | `US-06` | Dado `ATAQUE_IMEDIATO_RECOMENDADO = 0`, quando o fluxo chegar ao Bloco 10, então `B10.C01` não é exibida |
| `AC-23` | `US-06` | Dado `ATAQUE_IMEDIATO_RECOMENDADO = 1000` e o aluno respondendo "apenas uma parte" com `B10.C01A = 1500`, quando validado, então o valor é recusado por violar `0 ≤ APROVADO ≤ RECOMENDADO` |
| `AC-24` | `US-06` | Dado o Bloco 10 completo, quando as perguntas exibidas forem auditadas, então nenhuma pergunta solicita ao aluno escolher qual dívida receberá o recurso |
| `AC-25` | `US-07` | Dado um snapshot recém-calculado com `REVISAO_HUMANA_OBRIGATORIA = False`, quando o plano for gerado, então ele entra na fila de revisão e não é acessível ao aluno até haver liberação registrada |
| `AC-26` | `US-07` | Dado um recálculo disparado por quitação confirmada, quando o novo snapshot for produzido, então ele também entra na fila de revisão antes de qualquer envio — a política não distingue primeiro envio de recálculo |
| `AC-27` | `US-07` | Dada uma liberação de revisão, quando registrada, então ficam gravados o autor e a data, e o registro não pode ser alterado nem removido por nenhuma rota da aplicação |
| `AC-28` | `US-07` | Dado um snapshot com `REVISAO_HUMANA_OBRIGATORIA = True`, quando exibido na fila, então ele é sinalizado como caso metodológico de `S-04`, distinguível de um caso que está na fila apenas pela `POLITICA_REVISAO_INTEGRAL_PILOTO` |
| `AC-29` | `US-07` | Dado um caso na fila, quando o revisor abrir, então ele vê o plano como o aluno o verá e os `estado_inputs` que o produziram, na mesma sessão |
| `AC-30` | `US-08` | Dada uma quitação confirmada com `B11.Q01 = Sim`, quando o recálculo executar, então um novo `SnapshotOrdem` é criado com `versao = anterior.versao + 1`, `snapshot_anterior_id = anterior.SNAPSHOT_ID`, e o snapshot anterior permanece íntegro e recuperável |
| `AC-31` | `US-08` | Dada uma resposta `B11.Q01 = "Acredito que sim, mas ainda preciso confirmar"`, quando avaliada, então nenhum recálculo é disparado |
| `AC-32` | `US-08` | Dada uma tentativa de `UPDATE` ou `DELETE` sobre um snapshot já gravado, quando executada por qualquer caminho da aplicação, então a operação é recusada e o snapshot permanece inalterado |
| `AC-33` | `US-08` | Dado `RESULTADO_ACAO_INFORMACAO` = Sim para uma ação de informação sobre o campo `B5.B03`, quando o retorno for processado, então apenas `B5.B03` é reaberto — nenhuma outra pergunta do Bloco 5 é exibida |
| `AC-34` | `US-08` | Dado `RESULTADO_ACAO_RENEGOCIACAO` = Sim, quando o retorno for processado, então as perguntas `B7.05` a `B7.16` são reabertas para a dívida da ação, e nenhuma pergunta do Bloco 7 anterior a `B7.05` é reexibida |
| `AC-35` | `US-08` | Dada uma alteração meramente cadastral (correção de um nome ou rótulo), quando salva, então nenhum recálculo é disparado e nenhum snapshot novo é criado |
| `AC-36` | `US-09` | Dado um registro de pergunta cujo enunciado é editado na fonte de registros, quando a aplicação for reiniciada, então a pergunta aparece com o novo enunciado sem nenhuma alteração de código-fonte |
| `AC-37` | `US-09` | Dado o código-fonte desta feature, quando auditado, então nenhum enunciado, opção ou condição de exibição das 291 perguntas aparece escrito nele, e nenhum valor `P_*` da §8 aparece nele |
| `AC-38` | `US-09` | Dado um `ID` de pergunta já usado em uma versão anterior do questionário, quando uma nova versão for publicada, então esse `ID` não é reaproveitado para outra pergunta |
| `AC-39` | `US-10` | Dado um caso sem consentimento registrado, quando o aluno tentar iniciar a coleta, então nenhuma resposta é gravada até o consentimento ser registrado |
| `AC-40` | `US-11` | Dado um conjunto de casos em estados diferentes, quando a trilha de progresso for consultada, então cada caso reporta seu estado atual e a data da última interação do aluno |
| `AC-41` | `US-12` | Dado o código-fonte da camada de aplicação, quando auditado, então ele não contém nenhum gate, ranqueamento, fórmula da §11 nem valor `P_*`, e não importa nada de `engine/` além de `calcular_plano`, dos tipos de entrada/saída e das portas |
| `AC-42` | `US-12` | Dado qualquer valor monetário, de prazo ou de status exibido ao aluno ou ao revisor, quando sua origem for rastreada, então ele corresponde a um campo do `SnapshotOrdem` — nenhum é recomputado pela aplicação |
| `AC-43` | `US-12` | Dado o `SnapshotOrdem` devolvido pelo motor, quando persistido, então a gravação ocorre por `RepositorioSnapshots.anexar` — não há nenhum `INSERT`, `UPDATE` ou `DELETE` de snapshot escrito nesta feature |
| `AC-44` | `US-12` | Dado o adaptador de persistência existente, quando esta feature for construída, então nenhum arquivo de `persistencia/` e nenhum arquivo de `engine/` é modificado, com a exceção única de `engine/gates.py::AcaoRequerida` prevista em `OQ-10`/`RF-33` |
| `AC-45` | `US-08` | Dada uma `AcaoRequerida` presente na `ORDEM_ACOES` de dois snapshots consecutivos referentes à mesma ação, quando os dois forem comparados, então o `ACAO_ID` é idêntico nos dois — a resposta de `B11.01` dada no primeiro continua vinculada à mesma ação no segundo |
| `AC-46` | `US-08` | Dada uma `AcaoRequerida` de tipo informação e `ACAO_STATUS` = `CONCLUIDA`, quando o Bloco 11 for exibido para ela, então `B11.03-INF` é exibida e `B11.03-REN`, `B11.03-TRO` e `B11.03-ECO` não são — e simetricamente para os outros três tipos, cada um abrindo exclusivamente a sua pergunta de resultado |
| `AC-47` | `US-08` | Dada uma dívida bloqueada pelo Gate 1 (`GATE_PENDENTE.INFORMACAO`, por `STATUS_DIVIDA` = `QUITADA_A_CONFIRMAR` ou `VALOR_RELEVANTE_PARA_QUITACAO` = `DESCONHECIDO`), quando o snapshot for produzido, então existe em `ORDEM_ACOES` uma ação de tipo informação referente àquele `DIVIDA_ID` — a dívida travada nunca fica sem ação reportável |
| `AC-48` | `US-08` | Dada uma dívida com `RENEGOCIACAO_PENDENTE` = True e `TROCA_PENDENTE` = False, quando a ação for tipada, então seu tipo é o de intervenção/renegociação; e dada `TROCA_PENDENTE` = True e `RENEGOCIACAO_PENDENTE` = False, então seu tipo é o de troca |
| `AC-49` | `US-08` | Dado `ECONOMIA_POTENCIAL_IMEDIATA` > 0, quando o snapshot for produzido, então existe em `ORDEM_ACOES` uma ação de tipo correção/economia; e dado `ECONOMIA_POTENCIAL_IMEDIATA` = 0, então nenhuma ação desse tipo é emitida |
| `AC-50` | `US-08` | Dada uma ação de correção/economia, quando a camada de coleta a processar, então ela é exibida no Bloco 11 sem depender de `DIVIDA_ID` — a ausência de dívida associada não impede `B11.01` nem `B11.03-ECO` |

### Rodada 2 (2026-09-07) — fatia 2A

> **Rastreabilidade `RF` → `AC` desta fatia.** `RF-36` → `AC-51`, `AC-52`,
> `AC-53`, `AC-54` · `RF-37` → `AC-55`, `AC-56`, `AC-69` · `RF-38` → `AC-57`,
> `AC-58`, `AC-59` · `RF-39` → `AC-60`, `AC-62` · `RF-40` → `AC-63`, `AC-64` ·
> `RF-41` → `AC-65` · `RF-42` → `AC-66` · `RF-43` → `AC-70` · `RF-44` → `AC-61`,
> `AC-71`. `AC-67` e `AC-68` verificam o **ganho observável** da fatia sobre a
> saída do motor (a reserva real substituindo o `0` que a montagem produzia),
> atendendo `RF-36`+`RF-37` em conjunto.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-51` | `US-13` | Dado `B4.02` respondido com `valor_interno = INFORMAL`, quando o estado for montado, então `EstadoFinanceiro.RESERVA_EXISTE is RESERVA_EXISTE.INFORMAL` — e simetricamente para `SIM` e `NAO`, os três membros do domínio, nenhum colapsado em outro |
| `AC-52` | `US-13` | Dado `B4.03` respondido com `valor_interno = GRANDE_PARTE`, quando o estado for montado, então `EstadoFinanceiro.DISPOSICAO_USO_RESERVA is DISPOSICAO_USO_RESERVA.GRANDE_PARTE` — e simetricamente para `PARTE`, `TALVEZ` e `NAO`, os quatro membros |
| `AC-53` | `US-13` | Dado o código de `app/montagem/estado.py`, quando auditado, então a leitura de `RESERVA_EXISTE` e de `DISPOSICAO_USO_RESERVA` passa por `_membro_do_enum` e **nenhum** rótulo em português de `B4.02`/`B4.03` (`"Sim."`, `"Não."`, `"Talvez. Quero ver os números antes."`, …) aparece escrito no arquivo — `AC-37` continua verde |
| `AC-54` | `US-13` | Dado um `valor_interno` gravado que não corresponde a nenhum membro do enum alvo, quando o estado for montado, então `ErroValorInternoDesconhecido` é levantado nomeando o enum e o valor — nunca um membro "parecido" nem um default |
| `AC-55` | `US-14` | Dado `B4.02A` respondido com "Não sei." (`admite_nao_sei: true`), quando o estado for montado, então `EstadoFinanceiro.RESERVA_TOTAL is DESCONHECIDO` — nunca `Decimal("0")`, nunca `None` |
| `AC-56` | `US-14` | Dado `B4.03A` respondido com "Não sei.", quando o estado for montado, então `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO`; e dado `B4.03A` respondido com um valor monetário, então o campo é exatamente o `Decimal` convertido pela fronteira única, sem passar por `float` |
| `AC-57` | `US-13` | Dado `B4.01 = SIM` e `B4.01A = "1234,56"`, quando o estado for montado, então `EstadoFinanceiro.DINHEIRO_DISPONIVEL == Decimal("1234.56")` e a construção não levanta o `TypeError` de `_recusar_float` |
| `AC-58` | `US-13` | Dado `B4.01` respondido `NAO` (não há dinheiro disponível) e `B4.01A` sem resposta, quando o estado for montado, então `DINHEIRO_DISPONIVEL` é o zero da fronteira única de conversão — zero **legítimo lido de resposta**, não default |
| `AC-59` | `US-14` | Dado `B4.01` **sem resposta** e `B4.01A` sem resposta, quando o estado for montado, então um erro nomeado é levantado citando a variável — a montagem nunca devolve `DINHEIRO_DISPONIVEL = 0` por omissão de resposta |
| `AC-60` | `US-15` | Dado qualquer conjunto de respostas do Bloco 4, inclusive um com fichas de investimento, imóvel, veículo e outro ativo preenchidas, quando o estado for montado nesta fatia, então `investimentos == ()`, `ativos == ()` e `recursos_extraordinarios == ()` |
| `AC-61` | `US-15` | Dado o código-fonte de `app/`, quando auditado, então nenhuma função tem `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno, nenhum literal dos quatro membros daquele domínio aparece atribuído a um item, e nenhuma soma de `VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO` ou `CUSTOS_ESTIMADOS_DESMOBILIZACAO` é escrita — a proibição de `AC-67` do motor vale aqui por decisão, não por o lint não varrer esta pasta |
| `AC-62` | `US-15` | Dada a docstring de `montar_estado_financeiro`, quando lida, então ela nomeia `motor-calculo:OQ-26` e `motor-calculo:OQ-27` como motivo de `investimentos`/`ativos` vazios e `OQ-22`/`OQ-24` como motivo de `recursos_extraordinarios` vazio — a lacuna é documentada, nunca silenciosa |
| `AC-63` | `US-16` | Dada a allowlist de `AC-41` após esta fatia, quando comparada com a anterior, então ela ganhou exatamente dois nomes — `engine.estado.RESERVA_EXISTE` e `engine.estado.DISPOSICAO_USO_RESERVA` —, cada um com comentário justificativo, e nenhum dos cinco nomes de 2B/2C foi acrescentado |
| `AC-64` | `US-16` | Dado `tests/app_aluno/estatica/test_fronteira_import_engine.py`, quando executado após a montagem passar a importar os dois enums, então ele passa — e as proibições explícitas anteriores (`engine.gates` além de `AcaoRequerida`, `engine.ciclo_mensal` além de `ErroInvariante`, `engine.metodos.*`, `engine.comparacao`, `engine.ordem`, `from engine import *`) continuam recusadas |
| `AC-65` | `US-16` | Dado `tests/app_aluno/estatica/test_engine_congelado.py`, quando executado após a regravação do JSON, então os quatro testes de `AC-44` passam, `engine/ataque_imediato.py` consta do conjunto congelado, e `persistencia/supabase/migracoes/002_app_aluno.sql` continua **fora** dele |
| `AC-66` | `US-16` | Dado o repositório após esta fatia, quando os comandos da seção 2 do `sdd.config.md` forem executados, então `build` (`mypy --strict`) reporta zero erro e a suíte de `tests/app_aluno/` passa integralmente — nenhuma das ~129 falhas de causa raiz única permanece |
| `AC-67` | `US-13` | Dado um caso com `B4.02 = SIM`, `B4.03 = PARTE`, `B4.02A = 10000` e `B4.03A = 3000`, quando `calcular_plano` for invocado com o estado montado, então `snapshot.diagnostico.RESERVA_MOBILIZAVEL == Decimal("3000")` — deixa de ser o `0` que a montagem produzia ao passar `RESERVA_EXISTE = NAO` |
| `AC-68` | `US-13` | Dado o mesmo caso com `B4.03A = 30000` e `B4.02A = 10000`, quando o plano for calculado, então `RESERVA_MOBILIZAVEL == Decimal("10000")` — o limite `MIN(RESERVA_TOTAL, MAX(0, informado))` da Regra 2 da §13.1 é aplicado **pelo motor**, e a montagem não o reproduz em lugar nenhum |
| `AC-69` | `US-14` | Dado um caso com `B4.02 = SIM`, `B4.03 = TALVEZ` e `B4.03A = "Não sei."`, quando o plano for calculado, então `snapshot.diagnostico.RESERVA_MOBILIZAVEL is DESCONHECIDO` — a Regra 3 da §13.1 produz desconhecido de verdade, e nenhum ponto do caminho o converte em zero |
| `AC-70` | `US-14` | Dado um snapshot com `RESERVA_MOBILIZAVEL` desconhecida, quando a apresentação ao aluno for produzida, então ela exibe o estado "pendente de decisão" e **não** exibe `R$ 0,00` nem omite o item; e dado o mesmo campo com valor, então exibe o valor. Nenhum caminho de exibição levanta exceção por encontrar `DESCONHECIDO` |
| `AC-71` | `US-15` | Dado o código de leitura do Bloco 4 desta fatia, quando auditado, então nenhuma chamada a `valores_do_escopo` é feita para variável do Bloco 4 — a fatia 2A lê apenas os cinco campos escalares, por `respostas.valor(...)`, e não é afetada pela ausência de filtro por escopo descrita em `OQ-24` |

### Rodada 3 (2026-09-14) — protótipo validado e máscara de entrada

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-72` | `US-17` | Dado um caso em coleta com perguntas pendentes, quando `GET /caso/{CASO_ID}/pergunta` for chamado pela sessão dona do caso, então a resposta traz **a primeira pergunta não respondida e exibível**; e dada uma pergunta cuja `condicao_exibicao` é falsa, então ela **nunca** é devolvida — o servidor avança até a próxima exibível |
| `AC-73` | `US-17` | Dado o conjunto de arquivos `.js` servidos por `app/http/estaticos/`, quando auditados estaticamente, então **nenhum** contém enunciado de pergunta, rótulo de opção, ou qualquer avaliação de `condicao_exibicao` — mesma disciplina de `AC-37`, agora do lado do cliente |
| `AC-74` | `US-17` | Dado que a rota `GET` nova declara `CASO_ID` na URL, quando a auditoria de isolamento enumerar as `APIRoute` registradas, então a rota aparece com `exigir_caso_da_sessao` — e o acesso por conta que não é dona do caso responde `404`, nunca `200` |
| `AC-75` | `US-18` | Dado um campo `MOEDA` com a máscara ativa, quando o aluno digitar `123456`, então o campo exibe `1.234,56` e submete `"1.234,56"`, que `converter_para_dinheiro` aceita produzindo exatamente `Decimal("1234.56")` |
| `AC-76` | `US-18` | Dado um campo `TAXA` para "4,5% a.m.", quando submetido, então o valor enviado é `"4,5"` — **nunca** `"0,045"` e **nunca** com o caractere `%`, que `_CARACTERES_ACEITOS` recusa; o sufixo `%` existe apenas como texto visual fora do `<input>` |
| `AC-77` | `US-18` | Dada uma entrada ambígua (`"1.2,3"`), quando o aluno submeter, então a máscara **não** a transforma em valor válido: a string chega ao servidor como digitada, `ErroConversaoInvalida` é levantada, a resposta é `400` e **nada** é gravado (`EC-01` intacto) |
| `AC-78` | `US-18` | Dado um campo cujo registro admite "não sei", quando o checkbox `nao_sei` for marcado, então a máscara fica inerte e a resposta gravada é `NAO_SEI` — nunca `0`, nunca o conteúdo formatado que estivesse no campo |
| `AC-79` | `US-17` | Dado o mesmo fluxo com JavaScript desabilitado, quando o aluno submeter o `<form>` nativo, então a resposta é gravada pelos mesmos sete passos e pela mesma rota — a variante de resposta da página única é aditiva, e nenhum teste que hoje afirma sobre `resposta.text` deixa de passar |

### Rodada 5 (2026-09-17) — navegação fiel ao protótipo

> **`AC-73` está desatualizado e permanece como está, com esta emenda.** Ele
> cita `app/http/estaticos/*.js`, diretório **removido em `T-145`** quando a
> interface passou a ser React. O teste que o implementa já audita
> `frontend/src/` — leia `AC-73` como referente a `frontend/src/**/*.{ts,tsx}`.
> A disciplina é idêntica e continua valendo; só o diretório mudou.
>
> **Rastreabilidade `RF` → `AC` desta rodada.** `RF-57` → `AC-82`, `AC-84`,
> `AC-85` · `RF-58` → `AC-83`, `AC-86` · `RF-59` → `AC-80`, `AC-87` ·
> `RF-60` → `AC-81`, `AC-88` · `RF-61` → `AC-89`, `EC-25` · `RF-62` → `AC-90` ·
> `RF-63` → `AC-92`. `AC-91` verifica `EC-26`; `AC-86` verifica `EC-27`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-80` | `US-20` | Dada uma sessão de aluno (`e_revisor = False`), quando a aplicação carrega em qualquer tela do fluxo, então **nenhum** elemento de navegação referencia rota de equipe — auditado **no DOM**, não apenas no servidor: nenhum `href`/`onClick` alcança `#equipe-fila`, `#equipe-caso` ou `#equipe-painel` |
| `AC-81` | `US-19` | Dado um caso em cada uma das cinco fases, quando `GET /caso/{CASO_ID}/inicio` for chamado, então a resposta traz exatamente **uma** `proxima_etapa`, e a fase devolvida corresponde ao `ESTADO_CASO` do caso conforme o mapa de `RF-61` |
| `AC-82` | `US-19` | Dada qualquer tela do aluno, quando renderizada, então ela usa a casca de três partes, com `.top` e `.acoes` fixo no rodapé. **Três isenções, e só estas três:** (a) a tela **Início** não tem "‹ Voltar" — é a raiz do fluxo, não há para onde voltar; (b) a tela de **entrada** (login) também não — ela é anterior ao fluxo, e o "voltar" dali é sair do app; (c) a tela de **cálculo em andamento** não tem `.acoes` — não existe ação a oferecer a quem está esperando o motor, e um botão ali só poderia interromper o que não deve ser interrompido (o protótipo faz o mesmo, linha 408). Qualquer outra tela sem `.top` ou sem `.acoes` é entrega incompleta |
| `AC-83` | `US-19` | Dado o código do frontend, quando auditado, então **não existe** nenhum elemento de navegação que ofereça todas as telas de uma vez: nenhuma barra de abas, e nenhuma tela do aluno além de Início é alcançável sem passar por uma ação explícita da tela anterior |
| `AC-84` | `US-19` | Dada qualquer troca de tela, quando concluída, então o foco vai para o `<h1>` da tela nova, a rolagem volta ao topo, e `document.title` passa a `"PIQ Meu Plano · "` mais o título da tela — os três, sempre, inclusive ao trocar de pergunta dentro da mesma tela de pergunta |
| `AC-85` | `US-19` | Dada uma tela cujo conteúdo é mais alto que a janela, quando rolada até o meio, então o botão de ação principal continua visível no rodapé — `position: sticky` funcionando de fato, não apenas declarado |
| `AC-86` | `US-19` | Dado o botão "voltar" do navegador, quando pressionado após navegar entre telas, então a tela anterior é exibida — `history.pushState` **não** dispara `popstate`, e a implementação precisa notificar a navegação própria por outro canal |
| `AC-87` | `US-20` | Dada uma tela da área da equipe, quando renderizada, então sua largura máxima é 900px, distinta dos 560px do fluxo do aluno |
| `AC-88` | `US-19` | Dado um caso na fase `plano` com valor de ataque imediato recomendado, quando `/inicio` for chamado, então o valor viaja em `valor_em_destaque` como **string**, e `proxima_etapa` **não tem campo de frase algum** — só `destino`, `ID_PERGUNTA` e `item_id`. A trava é estrutural: sem campo de texto, não há onde o número ser interpolado, e a composição da frase é do cliente |
| `AC-89` | `US-19` | Dado um membro novo acrescentado a `ESTADO_CASO` sem fase declarada, quando `mypy --strict` for executado, então ele **falha** — o `match` de `fase_do_estado` é exaustivo e não tem `case _` |
| `AC-90` | `US-19` | Dado qualquer caso em coleta, quando `contar_coleta` for executada, então `respondidas + faltam == total` — os três saem da **mesma** varredura, então o invariante vale por construção, não por coincidência. E quando `/inicio` for chamado, então `progresso` traz `respondidas` e `total` (nunca `faltam`: é `total - respondidas`, e campo redundante no payload convida alguém a confiar nele em vez de derivá-lo), com o `total` contando apenas as perguntas cuja condição de exibição é verdadeira no momento da chamada |
| `AC-91` | `US-19` | Dado um hash desconhecido na URL (`#nao-existe`), quando a aplicação carregar, então ela exibe a tela **Início** — nunca uma tela em branco |
| `AC-92` | `US-19` | Dada a quarta pergunta exibível da ficha de uma dívida, quando o payload for produzido, então `posicao = 4` e `total_na_ficha` é **a contagem de perguntas abertas daquele escopo NAQUELE bloco** — nunca a soma dos blocos que compartilham o escopo. `DIVIDA_ID` tem 88 registros em três blocos (55 no Bloco 5, 13 no Bloco 7, 20 no Bloco 8): contar os três juntos diria *"pergunta 4 de 37"* a quem está cadastrando a primeira dívida, incluindo no denominador a coleta dirigida pós-plano, que é outra etapa. E dada uma pergunta fora de ficha repetível, então os dois campos são nulos e o localizador cai no rótulo do bloco |

### Rodada 6 (2026-09-18) — orientação

> **Rastreabilidade.** `RF-64` → `AC-93`, `AC-94`, `AC-95` · `RF-65` → `AC-96`
> · `RF-66` → `AC-97`, `AC-98` · `RF-67` → `AC-99`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-93` | `US-21` | Dada a tela Início em qualquer fase, quando renderizada, então as **cinco** etapas da jornada aparecem, na ordem, e exatamente **uma** está marcada como em curso |
| `AC-94` | `US-21` | Dado um caso em cada uma das cinco fases, quando o Início for renderizado, então a etapa em curso corresponde à fase do caso, as anteriores aparecem como concluídas e as seguintes como futuras — nenhuma fase produz trilha vazia ou duas etapas em curso |
| `AC-95` | `US-21` | Dada a trilha, quando auditada, então ela é **visível sem interação**: não está dentro de `<details>`, nem atrás de botão, nem depende de rolagem horizontal a 360px |
| `AC-96` | `US-21` | Dada a etapa em curso, quando exibida, então ela traz o que falta **com unidade**: na coleta, *"faltam N perguntas"* (nunca só *"3 de 101"*); na revisão, que a espera é da equipe; no acompanhamento, quantas ações aguardam reporte |
| `AC-97` | `US-22` | Dado um caso **sem nenhuma resposta gravada**, quando o aluno chega ao Início, então vê primeiro a tela de boas-vindas, com o que o PIQ faz, o que ele recebe ao final, que pode parar e voltar, e que **uma pessoa confere** o plano antes de chegar a ele |
| `AC-98` | `US-22` | Dado um caso com **ao menos uma** resposta, quando o aluno chega ao Início, então a tela de boas-vindas **não** aparece; e dado o aluno na tela de boas-vindas, quando aciona "Começar", então segue para o fluxo — a tela nunca é bloqueio |
| `AC-99` | `US-21` | Dado o código do cliente, quando auditado, então nem a trilha nem as boas-vindas leem `localStorage`/`sessionStorage` para decidir o que exibir: as duas derivam de `fase` e `progresso`, que vêm do servidor — trocar de aparelho não muda o ponto da jornada |

### Rodada 7 (2026-09-18) — rever, corrigir e caber na tela

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-100` | `US-23` | Dado um caso com respostas gravadas, quando o aluno abrir "Minhas respostas", então vê as perguntas que respondeu agrupadas pelas cinco partes, cada uma com **o valor que deu** — nunca só o identificador da pergunta |
| `AC-101` | `US-23` | Dada uma parte sem nenhuma resposta, quando exibida, então diz que ainda não foi respondida — nunca some da lista nem aparece vazia sem explicação |
| `AC-102` | `US-23` | Dada uma resposta na revisão, quando o aluno aciona "Editar", então a pergunta abre **com o valor anterior preenchido**, e gravar usa a mesma rota da resposta original — nenhuma segunda via de escrita |
| `AC-103` | `US-23` | Dada uma correção gravada, quando a revisão for reaberta, então mostra o valor novo; e o total de respondidas **não aumenta** por uma correção — corrigir não é responder de novo |
| `AC-104` | `US-23` | Dada uma correção recusada pelo servidor (`EC-01`, `EC-02`), quando o aluno submeter, então a mensagem do servidor aparece e o valor anterior **permanece** gravado — uma correção inválida nunca apaga o que era válido |
| `AC-105` | `US-23` | Dada a tela de pergunta durante a coleta, quando há pergunta anterior respondida, então existe caminho para ela; e na primeira pergunta, então não há "anterior" oferecido |
| `AC-106` | `US-24` | Dada uma janela larga (≥1024px), quando qualquer tela do aluno for renderizada, então a jornada aparece em coluna lateral e o conteúdo ocupa o restante; e dada uma janela de 360px, então o layout é **idêntico** ao validado: coluna única, trilha acima do conteúdo, sem rolagem horizontal |

### Rodada 8 (2026-09-19) — acabamento visual

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-107` | `US-25` | Dado `frontend/tailwind.config.js`, quando comparado com a versão anterior a esta rodada, então os **onze tokens de cor** têm nome e valor idênticos (`bg`, `surface`, `ink`, `muted`, `line`, `accent.DEFAULT`, `accent.ink`, `accent.soft`, `warn.DEFAULT`, `warn.soft`, `bad.DEFAULT`, `bad.soft`), e `fontFamily`, `minHeight` (56/60/48px) e `maxWidth` (560/900px) permanecem inalterados — `test_acessibilidade_coleta.py` segue verde sem edição |
| `AC-108` | `US-25` | Dado o CSS da interface, quando auditado, então existe uma escala de elevação de **três níveis** cujas sombras derivam de `ink` em alfa (`rgba(27,42,47,…)`), e **nenhuma** sombra usa preto neutro (`rgba(0,0,0,…)`) |
| `AC-109` | `US-25` | Dada a tela do plano liberado, quando renderizada, então `PRAZO_TOTAL` e `CUSTO_FUTURO_TOTAL` aparecem **acima** da ordem de quitação, em escala tipográfica maior que o corpo, e todo valor numérico da tela usa `font-variant-numeric: tabular-nums` |
| `AC-110` | `US-25` | Dado qualquer ícone da interface, quando auditado, então ele é `aria-hidden="true"`, não é focável (não é `<button>`, `<a>` nem tem `tabindex` ≥ 0), e o elemento que o contém tem rótulo textual visível ou acessível — nenhum ícone é o único portador de significado |
| `AC-111` | `US-25` | Dado `frontend/public/icons.svg`, quando esta rodada concluir, então o arquivo **não existe** — era boilerplate do Vite (ícones de Bluesky, Discord, GitHub) sem nenhuma referência no código |
| `AC-112` | `US-25` | Dada qualquer tela em estado de carregamento, quando renderizada, então mostra um esqueleto `aria-hidden="true"` com a forma do conteúdo esperado, e **continua existindo** um elemento com `role="status"` anunciando o carregamento — a árvore de acessibilidade não perde informação em relação ao `<p>Carregando…</p>` que havia antes |
| `AC-113` | `US-25` | Dado `prefers-reduced-motion: reduce`, quando qualquer tela for renderizada, então nenhum esqueleto anima e nenhuma transição de controle roda — o esqueleto aparece parado, como já acontece com o `.pulse` |
| `AC-114` | `US-25` | Dada a tela de pergunta, quando percorrida por teclado a partir do campo, então o botão "Continuar" é alcançado em **no máximo 2 Tabs**, e o nome acessível do botão é exatamente `Continuar` — nenhum ícone ou elemento novo entra na ordem de foco (`coleta.spec.ts` segue verde) |
| `AC-115` | `US-25` | Dada a trilha da jornada, quando auditada, então **nenhum** dos cinco degraus é elemento interativo (`<button>`, `<a>`, `role="button"`, `onClick`): ela continua informativa, e o único botão da tela é o da próxima etapa |
| `AC-116` | `US-25` | Dado o código do frontend, quando auditado após esta rodada, então as classes `.top`, `.corpo`, `.acoes`, `.back`, `.linha`, `.cartao-proximo`, `.item` e `.chip` continuam existindo com os mesmos nomes — a suíte E2E as usa como seletor, e renomear qualquer uma quebraria dezenas de testes |

### Rodada 9 (2026-09-30) — decisões do especialista

> **Rastreabilidade `RF` → `AC`.** `RF-79` → `AC-117`, `AC-118`, `AC-119` ·
> `RF-80` → `AC-119`, `AC-120` · `RF-81` → `AC-121`, `AC-122`, `AC-123`, `AC-155` ·
> `RF-82` → `AC-124` · `RF-83` → `AC-125`, `AC-126`, `AC-127` · `RF-84` →
> `AC-128`, `AC-129` · `RF-85` → `AC-130`, `AC-131`, `AC-132` · `RF-86` →
> `AC-133`, `AC-134` · `RF-87` → `AC-133`, `AC-153`, `AC-154` · `RF-88` → `AC-135` · `RF-89` →
> `AC-136`, `AC-156` · `RF-90` → `AC-137`, `AC-138`, `AC-139` · `RF-91` → `AC-140` ·
> `RF-92` → `AC-141` · `RF-93` → `AC-142` · `RF-94` → `AC-143`, `AC-144`,
> `AC-145` · `RF-95` → `AC-146` · `RF-96` → `AC-147`, `AC-148` · `RF-97` →
> `AC-149` · `RF-98` → `AC-150`, `AC-151`, `AC-152`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-117` | `US-26` | Dado um caso com `RENDA_TOTAL_RECORRENTE = 8000`, fichas de `B3.D01`–`B3.D11` somando `5000` e `DESPESAS_NAO_MENSAIS_NORMALIZADAS = 500`, quando `B3.C00` for exibida, então a tela mostra exatamente três valores — Renda total `R$ 8.000,00`, Despesas totais `R$ 5.500,00` e Sobra do mês `R$ 2.500,00` —, e o rótulo da sobra contém "antes das dívidas" (`DE-01`) |
| `AC-118` | `US-26` | Dado o mesmo caso com duas fichas de dívida já cadastradas no Bloco 5 (parcelas de `R$ 300` e `R$ 700`), quando `B3.C00` for exibida de novo, então Despesas totais continua `R$ 5.500,00` e a Sobra continua `R$ 2.500,00` — nenhuma parcela de dívida compõe a fotografia (`DE-01`) |
| `AC-119` | `US-26` | Dada a `B3.C00` exibida, quando o aluno abrir a consulta das decomposições, então vê as despesas por categoria e as não mensais convertidas para o mês, cuja soma é igual a Despesas totais (nunca Despesas totais mais as decomposições); e quando corrigir uma ficha por ali, a gravação usa a rota de `RF-69` e a `B3.C00` reexibida reflete o novo total (`DE-01`) |
| `AC-120` | `US-26` | Dado `B3.C00` respondida "Ainda não consigo avaliar" (`NAO_SEI`), quando a resposta for gravada, então a próxima pergunta exibida é a seguinte exibível do fluxo (`B3.C01`), nenhuma ação de Bloco 11 é criada e nenhuma pendência que bloqueie o cálculo é registrada (`DE-01`) |
| `AC-121` | `US-27` | Dada uma dívida com seguro na situação "prêmio único financiado" e custo total `R$ 1.200`, quando o estado for montado, então nenhum valor de seguro é acrescentado ao saldo, à parcela nem às despesas mensais entregues ao motor, e o `R$ 1.200` fica registrado como custo total do seguro da dívida (`DE-03`) |
| `AC-122` | `US-27` | Dada uma dívida com seguro "cobrado mensalmente à parte" de `R$ 40` por mês, quando o estado for montado, então `R$ 40` compõe as **despesas mensais operacionais entregues ao motor** exatamente uma vez — nunca a parcela; nem zero, nem duplicado com `B5.D05B` — e não aparece na `B3.C00` (texto ajustado pela decisão do responsável do produto de 2026-09-30, risco `R9-1`, `T-232`: o motor não tem custo mensal não amortizante por dívida, e somar à parcela amortizaria saldo com dinheiro de seguro) (`DE-03`, `OQ-54`) |
| `AC-123` | `US-27` | Dada uma dívida com seguro "cancelado com restituição", quando a restituição não estiver confirmada, então nenhuma cobrança futura de seguro e nenhum recurso extraordinário existem para ela; e quando o aluno confirmar a restituição de `R$ 300`, então passa a existir um item de recurso extraordinário de `R$ 300` ligado àquela origem (`DE-03`) |
| `AC-124` | `US-27` | Dado seguro informado como `R$ 1.200` "no total" com período de cobertura de 24 meses, quando a análise for exibida, então o equivalente mensal `R$ 50,00` aparece rotulado como rateio e não compõe nenhuma despesa nem desembolso; e dado o mesmo seguro **sem** período de cobertura, então nenhum equivalente mensal é exibido (`DE-03`) |
| `AC-125` | `US-27` | Dado valor atual de quitação antes do desconto `R$ 10.000` e desconto de `R$ 2.000`, sem valor final informado, quando gravado, então bruto, tipo `R$`, valor `2.000` e valor de referência `R$ 8.000` estão registrados em campos separados (`DE-03`) |
| `AC-126` | `US-27` | Dado bruto `R$ 10.000` e desconto de `15%`, sem valor final informado, quando gravado, então o valor de referência é `R$ 8.500`; e nenhum cálculo usa saldo devedor, valor contratado ou soma de parcelas como base (`DE-03`) |
| `AC-127` | `US-27` | Dado bruto `R$ 10.000`, desconto de `20%` e valor final informado pelo credor `R$ 7.900`, quando gravado, então o valor de referência da oferta é `R$ 7.900`, e `R$ 8.000` aparece apenas como conferência (`DE-03`) |
| `AC-128` | `US-27` | Dado um desconto de `120%` ou de `-5%`, ou de `R$ 12.000` sobre bruto de `R$ 10.000`, quando o aluno enviar, então a resposta é recusada com mensagem e nada é gravado (`DE-03`) |
| `AC-129` | `US-27` | Dado bruto `R$ 10.000` com `R$ 2.000` **e** `20%` informados juntos, quando gravado, então não há divergência e o desconto é aplicado uma vez (`R$ 8.000`, nunca `R$ 6.000`); dado bruto `R$ 10.000,20` com `R$ 1.500,03` e `15%` (bruto × 15% = `R$ 1.500,03`; diferença `R$ 0,00`), então não há divergência; dado `R$ 1.500,05` com o mesmo `15%` (diferença `R$ 0,02`), então divergência; e dado `R$ 2.000` com `15%` (diferença `R$ 500`), então uma divergência é sinalizada ao aluno e ao revisor e os dois valores ficam gravados, nenhum descartado nem somado (`DE-03`, `OQ-55`) |
| `AC-130` | `US-27` | Dado `B8.12A` = `R$ 1.200` "total" sem prazo informado, quando o estado ou a análise forem produzidos, então nenhum valor mensal derivado desse custo existe — nem `R$ 1.200` por mês, nem rateio por prazo presumido (`DE-03`) |
| `AC-131` | `US-27` | Dado `B8.12A` = `R$ 30` "por mês" com 10 meses restantes, quando o fluxo for montado **depois de a troca ser contratada** (recálculo pós-plano), então o custo compõe as despesas mensais operacionais — nunca a parcela — enquanto houver meses restantes na data de referência, e o término é reavaliado a cada recálculo (o motor não modela duração de despesa); **antes da contratação, nada é somado** (decisão do responsável do produto de 2026-09-30, riscos `R9-1` e `T-236`); e dado `R$ 1.200` "total" com prazo de 12 meses, então o equivalente mensal `R$ 100` aparece só como rateio analítico (`DE-03`) |
| `AC-132` | `US-27` | Dado `B8.12B = Sim` ou `B5.D05B = Sim` (custo já incluído na parcela), quando o estado for montado, então o custo do seguro não é somado em nenhum fluxo além da parcela já informada (`DE-03`) |
| `AC-133` | `US-28` | Dado `B5.00 = 7` e 5 fichas de dívida cadastradas, quando o aluno navegar por qualquer tela, então ele consegue responder qualquer outra pergunta pendente, e a mensagem exibida é exatamente "Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas." em um alerta presente em toda tela do aluno enquanto a diferença persistir (`DE-04`) |
| `AC-134` | `US-28` | Dado o mesmo caso, quando qualquer rota tentar concluir o diagnóstico ou executar o Bloco 6, então `calcular_plano` não é invocado, nenhum snapshot é criado e o caso permanece em coleta; e quando a 7ª ficha for cadastrada, então o alerta desaparece e o Bloco 6 fica alcançável (`DE-04`) |
| `AC-135` | `US-28` | Dado `B3.NM01 = Sim` e nenhuma ficha de despesa não mensal, quando o aluno tentar gerar o plano, então o cálculo é bloqueado e a mensagem é "Você informou que possui despesa não mensal, mas ainda não cadastrou nenhuma." (ponto final: padronização de pontuação aprovada pelo produto, `T-289`, 2026-09-30); e quando ele mudar `B3.NM01` para Não, então a pendência e o bloqueio desaparecem — e o mesmo vale, com mensagem própria, para `B3.03 = Sim` sem ficha de renda adicional e `B3.S01 = Sim` sem ficha de vínculo (`DE-04`; textos em `OQ-57`) |
| `AC-136` | `US-29` | Dado um aluno que cadastra dois vínculos, quando as fichas forem gravadas, então existem duas fichas independentes com `VINCULO_ID` estável, cada uma com órgão/ente, tipo, renda e margens próprios, e responder a ficha 2 não altera nenhum campo da ficha 1 (`DE-05`) |
| `AC-137` | `US-29` | Dada uma tentativa de gravar margem sem vínculo associado, quando enviada, então ela é recusada; e toda `MARGEM_ID` gravada referencia exatamente um `VINCULO_ID` existente do mesmo caso (`DE-05`) |
| `AC-138` | `US-29` | Dados o vínculo A com margem disponível `R$ 500` e o vínculo B com `R$ 300`, quando qualquer tela, relatório ou estado entregue ao motor for produzido, então nenhum deles contém `R$ 800` como margem disponível — cada margem aparece sob o seu vínculo (`DE-05`) |
| `AC-139` | `US-29` | Dada uma dívida consignada — `TIPO_DIVIDA = CONSIGNADO`, ou contrato de cartão consignado/cartão benefício — num caso com dois vínculos, quando a ficha for concluída, então ela referencia um `VINCULO_ID` existente do caso; sem essa referência a ficha permanece com pendência (`DE-05`) |
| `AC-140` | `US-30` | Dada `B7.16` respondida "Sim, documento/contrato", "Sim, aplicativo ou internet banking" ou "Sim, mensagem/e-mail", quando exibida ao revisor, então a Fonte de comprovação é "Comprovado por documento/registro"; "Não tenho registro" → "Informado pelo aluno, sem comprovação"; "Foi apenas informada em atendimento" → "Pendente de confirmação". Em `B5.I02`: "Documento/contrato", "Aplicativo ou internet banking" e "Contracheque" → nível 1; "Minha memória" e "Uma combinação dessas fontes" → nível 2; "Outra" → nível 2, ou nível 1 se houver documento associado; "Atendimento do credor" → nível 3. Em `B8.15`: "Documento formal", "Aplicativo/internet banking" e "Simulação fornecida pela instituição" → nível 1; "Atendimento" e "Correspondente" → nível 3; "Outra fonte" → como "Outra" (`DE-06`, `OQ-61`, `EC-36`) |
| `AC-141` | `US-30` | Dado um caso em que todas as fontes são de nível 2 ou 3 e nenhum dado indispensável está pendente, quando a coleta terminar, então o Bloco 6 executa e o snapshot entra na fila normalmente, com o nível de cada fonte visível ao revisor por dado (`DE-06`) |
| `AC-142` | `US-30` | Dado um dado indispensável (`OQ-62`) com fonte "Pendente de confirmação", quando o revisor abrir o caso na fila, então a pendência aparece listada, nomeando dívida e dado, e a ação de liberar é **recusada** por qualquer rota; quando o dado for confirmado (nível 1 ou 2) ou corrigido, então a liberação fica disponível (`DE-06`, `DE-08`, `OQ-62`, `OQ-64`) |
| `AC-143` | `US-31` | Dado `B7.04 = NAO`, quando o Bloco 7 da dívida for percorrido, então nenhuma pergunta de conteúdo da proposta (o tipo da proposta e `B7.05`–`B7.16`) é exibida (`DE-07`) |
| `AC-144` | `US-31` | Dada proposta só à vista, quando o Bloco 7 for percorrido, então são exibidos o valor para quitação à vista (`B7.07V`), o desconto (`B7.13`–`B7.13E`), `B7.15` (validade) e `B7.16` (fonte); `B7.07`, `B7.08` e `B7.09` não são exibidas (`DE-07`, `OQ-65`; texto ajustado pela decisão do responsável do produto de 2026-09-30, risco `R9-3`, `T-242`) |
| `AC-145` | `US-31` | Dada proposta parcelada, quando o Bloco 7 for percorrido, então `B7.07`, `B7.08`, `B7.09` e `B7.15` são exibidas; e dada proposta com as duas opções, então são coletados os dois conjuntos — valor à vista e dados do parcelamento — e `B7.15` (`DE-07`, `OQ-65`) |
| `AC-146` | `US-31` | Dada proposta só à vista, quando o progresso e o estado forem produzidos, então `B7.07`–`B7.09` não entram no total de `RF-62`, não geram pendência, e nenhum campo correspondente chega ao motor como `DESCONHECIDO` ou `INFORMACAO_PENDENTE` (`DE-07`) |
| `AC-147` | `US-32` | Dada a suíte de homologação executada, quando `GAB-A`, `GAB-B` e `GAB-C` rodarem, então cada um produz um registro com ordem final de ataque, mês de quitação de cada dívida, valor mensal destinado, custo total de juros e uso da reserva, cada item lido ou derivado do snapshot — ou "não disponível", nunca comparado a estimativa —, comparado ao gabarito quando o gabarito traz o valor (`DE-08`, `R9-6`) |
| `AC-148` | `US-32` | Dado um caso de homologação que não é gabarito, quando executado, então os cinco itens de `AC-147` são registrados como apurados pelo motor, e nenhum valor esperado de ordem, prazo ou uso da reserva está escrito no teste — só os invariantes são asseridos (`DE-08`) |
| `AC-149` | `US-32` | Dado um caso com dado indispensável ausente, quando o resultado for produzido, então o cálculo roda, o registro de homologação e a tela do revisor sinalizam que ele não pode ser homologado, nomeando o dado, a liberação é recusada até o dado ser informado, e nenhum valor presumido o substitui (`DE-08`, `OQ-64`). Vale para a periodicidade da taxa respondida "não sei"; taxa informada como estimada, com periodicidade informada, não impede a liberação (`T-287`, `DE-06`, Rodrigo, 2026-09-30) |
| `AC-150` | `US-33` | Dados três recursos extraordinários — 13º `CONFIRMADO`, restituição `PROVAVEL`, venda `POSSIVEL` —, quando o estado for montado, então `recursos_extraordinarios` contém três itens distintos, cada um com seu tipo, valor, janela e certeza, e nenhum total agregado é entregue (`DE-02`) |
| `AC-151` | `US-33` | Dado `B3.05A = Férias/abono`, quando `B3.05B` for exibida, então a pergunta deixa explícito que o valor é só o acréscimo; e o valor gravado é o informado — a aplicação não calcula o 1/3 (`DE-02`; texto em `OQ-67`) |
| `AC-152` | `US-33` | Dado um snapshot com recurso `PROVAVEL`, quando o plano for exibido, então o cenário adicional aparece separado e rotulado, e ordem, prazo e custo do plano principal são os campos da projeção-base do snapshot, sem nenhum valor do cenário adicional misturado; e um recurso `POSSIVEL` aparece também só no cenário adicional (`DE-02`, `motor-calculo:OQ-49`) |
| `AC-153` | `US-28` | Dado `B5.00` = "Não sei exatamente quantas", quando o aluno responder `B5.FIM01` = "Não, esta foi a última", então não há pendência de inventário por contagem e o Bloco 6 fica alcançável; e antes dessa confirmação, o cálculo final permanece bloqueado (`DE-04`, `OQ-56`) |
| `AC-154` | `US-28` | Dado `B5.00 = 5` e 6 fichas cadastradas, quando o aluno navegar, então o sistema exibe o pedido de atualizar `B5.00` com ação direta para fazê-lo, e `calcular_plano` não é invocado; e quando `B5.00` for atualizado para 6 (ou uma ficha for removida), então o bloqueio cessa (`DE-04`, `q4_1`, `OQ-56`) |
| `AC-155` | `US-27` | Dada uma dívida com seguro de situação "Não sei", quando o estado for montado, então nenhum valor de seguro é somado a saldo, parcela, despesa ou desembolso, e o dado aparece ao revisor como "não informado" — nunca como "Pendente de confirmação" (`DE-03`, `OQ-54`) |
| `AC-156` | `US-29` | Dados dois vínculos com renda líquida `R$ 4.000` e `R$ 2.500` e renda do Bloco 3 `R$ 6.500`, quando a conferência rodar, então nenhuma divergência é sinalizada; com renda do Bloco 3 `R$ 6.000`, então a divergência é sinalizada ao aluno e ao revisor; e em ambos os casos a renda entregue ao motor é a do Bloco 3, sem a soma das líquidas acrescentada, e nenhum campo novo de renda líquida chega ao motor (`DE-05`, `OQ-58`) |

### Rodada 10 (2026-10-01) — perguntas complementares na mesma tela

> **Rastreabilidade `RF` → `AC`.** `RF-99` → `AC-157`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-157` | `US-05` | Dada `B3.02` exibida, quando o aluno escolher "Variável", então `B3.02A` e `B3.02B` aparecem na mesma tela, abaixo da opção, vindas de `complementares["VARIAVEL"]` do servidor; quando trocar para outra opção, então elas somem e não são enviadas; e quando continuar, então `B3.02` é gravada antes das filhas, filha recusada mostra o erro junto dela sem desfazer a mãe, e a próxima pergunta não é nenhuma das já respondidas. Pergunta complementar fora do trecho contíguo (ex.: `B5.G03` sob `B5.A02`) não entra na thread (`RF-99`) |

### Rodada 10 (2026-10-01) — navegação, trilha e fichas na coleta

> **Rastreabilidade `RF` → `AC`.** `RF-57` → `AC-160` · `RF-70` → `AC-161` ·
> `RF-100` → `AC-162` · `RF-101` → `AC-163`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-160` | `US-19` | Dada uma tela do aluno cujo caminho de volta leva ao Início, quando renderizada, então o topo diz "‹ Início"; e dada a correção de uma resposta (volta à revisão) ou uma ação (volta à lista), então diz "‹ Voltar" (`T-308`) |
| `AC-161` | `US-23` | Dado um percurso com duas fichas do mesmo escopo e uma condicional dentro delas, quando qualquer pergunta exibida for aberta, então `anterior` é exatamente a pergunta exibida imediatamente antes (com o `item_id`), e "‹ Pergunta anterior" leva a ela; na primeira, `anterior` é `null` e o botão não existe (`T-309`) |
| `AC-162` | `US-21` | Dada a tela de pergunta ou a lista de fichas na coleta inicial, quando renderizada, então a trilha mostra as cinco partes com exatamente uma atual, as anteriores concluídas e a barra em partes concluídas; e o Bloco 9, no fim do percurso, não tira "Seu compromisso" de concluída (`T-310`) |
| `AC-163` | `US-02` | Dado `B3.05 = Sim` sem item, quando gravado, então nasce `EXT001` e a próxima pergunta é a primeira dele, sem a lista; quando o último campo do item for respondido, então a resposta aponta a lista do escopo; e dado um escopo que já tem item, então responder de novo não cria outro (`T-311`) |

### Rodada 10 (2026-10-01) — ficha curta em uma tela

> **Rastreabilidade `RF` → `AC`.** `RF-102` → `AC-164` · `RF-103` → `AC-165` ·
> `RF-104` → `AC-166` · `RF-105` → `AC-167`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-164` | `US-05` | Dado o item `EXT001` aberto, quando o formulário for pedido, então vêm `B3.05A`, `B3.05C` e `B3.05D` numa lista, e `B3.05AO`/`B3.05B`/`B3.05BF` só em `complementares` de `B3.05A`; quando "Salvar", então a mãe é gravada antes da filha, o erro de um campo fica junto dele sem impedir os demais, e o item completo volta à lista do escopo; dada uma pergunta de ficha curta como próxima (coleta, retomada, "Continuar"), então a tela aberta é o formulário do item (`T-314`) |
| `AC-165` | `US-05` | Dado o formulário de valor extraordinário, então aparece "Cadastre um valor de cada vez. Depois você pode adicionar outros."; quando o tipo for "Outro", então "Descreva a origem do valor." aparece na mesma tela e é aceita; com outro tipo, `B3.05AO` é recusada pelo servidor. `B3.03AO`, `B3.NM02AO`, `B3.NM02CO` e `B3.S06AO` vêm logo depois da mãe, no mesmo escopo, abertas só pelo "Outro" (`T-315`) |
| `AC-166` | `US-02` | Dado `B3.D11 = Sim`, quando gravado, então `abrir_fichas` vem vazio e a próxima pergunta é `B3.DF01` do item novo, cujo formulário pede o nome; e na lista, "+ Adicionar outra despesa" abre o formulário do item criado (`T-316`) |
| `AC-167` | `US-21` | Dados dois itens `EXT` com o primeiro completo, quando o formulário do segundo for pedido, então `posicao_do_item = 2`, `total_de_itens = 2` e `itens_concluidos = 1`, e a tela mostra "Valor extraordinário 2 de 2" e a barra com 1 de 2 (`T-317`) |

### Rodada 10 (2026-10-01) — fichas curtas na mesma tela, sem branco e em sequência

> **Rastreabilidade `RF` → `AC`.** `RF-106` → `AC-168` · `RF-107` → `AC-169` ·
> `RF-108` → `AC-170` · relato de despesas (`T-322`) → `AC-171`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-168` | `US-05` | Dada `B3.03` sem renda adicional cadastrada, quando servida, então `ficha_nova["SIM"]` traz `RENDA_ADICIONAL_ID` com `B3.03A`–`B3.03C` (e o mesmo para `B3.05`, `B3.NM01`, `B3.S01`, `B3.D11`), sem `"NAO"`; quando o aluno marcar "Sim", então os campos aparecem na mesma tela; quando salvar, então a mãe é gravada, os campos vão para o item criado (`REND001`), o item é concluído e a lista abre. Com o escopo já tendo item, `ficha_nova` não vem (`T-319`) |
| `AC-169` | `US-05` | Dado um item de despesa com `B3.DF03`/`DF04` em branco, quando concluir, então o servidor responde `400` com "Antes de salvar, responda nesta ficha: …" e `pendencias` daquelas perguntas; `""` gravado não conta como resposta; "Não sei" conta; a despesa sem nome não conclui. No cliente, "Salvar" com campo em branco destaca "Responda esta pergunta." e não grava nada (`T-320`) |
| `AC-170` | `US-21` | Dadas três despesas do checklist, quando a 2ª for concluída, então `proximo_item` é a 3ª; concluída a 3ª, é a 1ª; concluída a última pendente, é `null`; e a tela abre o formulário do próximo ("Despesa 2 de 3") ou, sem ele, a lista (`T-321`) |
| `AC-171` | `US-05` | Dado um item de despesa preenchido, quando o formulário do item seguinte ou de um item novo for aberto, então nenhum campo vem com valor de outro item (servidor e tela), e o formulário de cada ficha curta só traz perguntas do próprio escopo — nenhuma de dívida, como `B5.A01` (`T-322`) |

### Rodada 10 (2026-10-01) — "Não sei" no formato das opções e o inventário que diz quais

> **Rastreabilidade `RF` → `AC`.** `RF-109` → `AC-172` · `RF-110` → `AC-173`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-172` | `US-18` | Dada uma pergunta de valor como `B4.V09` (alternativa "Não há custo relevante…" e "Não sei."), quando renderizada, então as duas são opções `.opt` do mesmo grupo e não há checkbox; marcar "Não sei." grava `NAO_SEI` e esvazia o campo; marcar a alternativa grava o código e desmarca "Não sei."; digitar um valor desmarca ambas. Dada uma pergunta de valor só com "não sei", então ele é opção do grupo, não checkbox (`T-323`) |
| `AC-173` | `US-28` | Dadas 12 dívidas declaradas, os tipos `CONSIGNADO`, `PESSOAL` e `CARTAO_ROTATIVO` marcados, uma ficha `PESSOAL` com credor, uma sem tipo e uma criada vazia, quando `/inventario` for pedido, então a mensagem é "Você declarou 12 dívidas e cadastrou 2. Faltam 10 fichas." e `dividas` traz `tipos_sem_ficha` = consignado e cartão rotativo (rótulos), as duas fichas com credor/tipo e `ficha_vazia`; e na tela, "Cadastrar a próxima dívida" abre a ficha vazia ou, sem ela, cria uma (`T-324`) |

### Rodada 11 (2026-10-02) — Plano e conferência em linguagem humana

> **Rastreabilidade `RF` → `AC`.** `RF-111` → `AC-174`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-174` | `US-28` | Dado um caso calculado com um cheque especial da CAIXA (`D011`), um consignado com `CET` desconhecido e um valor extraordinário, quando a conferência e o plano forem pedidos, então: a posição do cheque especial diz "Cheque especial — CAIXA ECONOMICA FEDERAL"; nenhum texto principal do payload de plano/conferência contém nome de variável em CAIXA_ALTA, código de opção ou `D0nn` (só os campos de detalhe/identificador); o `CET` desconhecido aparece como "Não informado"; o valor extraordinário aparece por item ("R$ 15.000,00 · em 1 a 3 meses · …"), sem `RecursoExtraordinario(`; método "Híbrido"; e a justificativa técnica só no detalhe recolhido (`T-326`) |

### Rodada 12 (2026-10-02) — Devolução do plano ao aluno

> **Rastreabilidade `RF` → `AC`.** `RF-113` → `AC-175`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-175` | `US-28` | Dado um caso em `AGUARDANDO_REVISAO` com a taxa do cheque especial pendente, quando o revisor pede correção sem mensagem, então a decisão é recusada ("Escreva a mensagem para o aluno."); com a mensagem "Informe a taxa do cheque especial", então a reprovação é registrada (autor, data, mensagem, observação), o snapshot não muda e o caso volta ao questionário com as respostas intactas; o Início do aluno mostra a mensagem, a lista "Cheque especial — CAIXA ECONOMICA FEDERAL · Você sabe qual é a taxa de juros desta operação?" com link para a pergunta, e "Enviar para nova conferência"; a observação interna não aparece em nenhuma rota de aluno; ao reenviar, o plano é recalculado e o caso entra na fila como versão 2 (`T-333`) |

### Rodada 13 (2026-10-05) — Conferência trava a edição

> **Rastreabilidade `RF` → `AC`.** `RF-114` → `AC-176` · `RF-115` → `AC-177`, `AC-179` · `RF-116` → `AC-178` · `RF-117` → `AC-180`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-176` | `US-34` | Dado um caso em `AGUARDANDO_REVISAO` ou `CALCULANDO`, quando a sessão do aluno tenta gravar uma resposta, ou criar, nomear, remover ou concluir uma ficha, então a rota responde `409` com "Seu plano está em conferência. Para mudar uma resposta, retire-o da conferência." e nada é gravado; e `GET /respostas` devolve `editavel: false` e a tela de "Minhas respostas" não oferece "Editar" |
| `AC-177` | `US-34` | Dado um caso em `AGUARDANDO_REVISAO` com o snapshot v1, quando o aluno confirma "Quero editar minhas respostas", então o caso passa a `COLETA_INICIAL`, o evento `aluno_retoma_edicao` é registrado, o caso deixa de aparecer na fila do revisor, e o snapshot v1 e as respostas ficam intactos; e, depois de editar e reenviar, nasce a v2 encadeada à v1 e o caso volta à fila |
| `AC-178` | `US-34` | Dado um caso que o aluno retirou da conferência, quando o revisor tenta liberar ou reprovar, então a rota responde `409` com "Este plano saiu da conferência: o aluno o retirou para editar ou ele foi devolvido. Ele volta à fila quando for reenviado." e nenhuma revisão é registrada |
| `AC-179` | `US-34` | Dado um caso fora de `AGUARDANDO_REVISAO` (em `CALCULANDO`, por exemplo), quando o aluno pede para retomar a edição, então a rota responde `409`, o estado não muda e nenhum evento é gravado |
| `AC-180` | `US-34` | Dada a pergunta `B3.01`, quando exibida, então o enunciado é exatamente "Quanto você recebe por mês, em média, depois do imposto de renda e da previdência, mas antes de empréstimos e consignados? (Não desconte parcelas de empréstimo nem consignado: você cadastra essas dívidas mais adiante. Plano de saúde, sindicato e outros descontos de folha entram nas despesas.)" |

### Rodada 14 (2026-10-05) — Plano novo depois da liberação

> **Rastreabilidade `RF` → `AC`.** `RF-118` → `AC-181`, `AC-182`, `AC-184` · `RF-119` → `AC-183` · `RF-120` → `AC-185`, `AC-186`, `AC-187`, `AC-188`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-181` | `US-35` | Dado um caso em `PLANO_LIBERADO` ou `ACOMPANHAMENTO`, quando o aluno confirma "Gerar um novo plano com as minhas respostas", então o caso passa a `COLETA_INICIAL`, o evento `aluno_refaz_plano` é registrado, o plano liberado continua servido ao aluno e as respostas ficam intactas; e `GET /respostas` devolve `pode_refazer_plano: true` apenas nesses dois estados |
| `AC-182` | `US-35` | Dado um caso fora de `PLANO_LIBERADO` e `ACOMPANHAMENTO` (em `CALCULANDO`, `AGUARDANDO_REVISAO` ou `COLETA_INICIAL`, por exemplo), quando o aluno pede o plano novo, então a rota responde `409` com "Seu plano ainda não foi liberado.", o estado não muda e nenhum evento é gravado |
| `AC-183` | `US-35` | Dado um caso liberado (v1) cuja taxa do cheque especial foi alterada de 4% para 8% depois da liberação, quando o aluno pede o plano novo e envia, então nasce a v2 com `versao = 2` encadeada à v1, o `estado_inputs` da v2 traz 8% e o da v1 continua com 4%, e o caso volta à fila de conferência |
| `AC-184` | `US-35` | Dado o aluno prestes a confirmar, quando a confirmação aparece, então o texto diz que o plano atual continua disponível, que o novo será conferido de novo pela equipe e que isso pode levar o tempo da fila; e, depois de confirmar, o Início continua oferecendo "Ver meu plano" enquanto o novo não é liberado |
| `AC-185` | `US-35` | Dado um caso em `PLANO_LIBERADO` ou `ACOMPANHAMENTO` cujo estado financeiro montado das respostas atuais difere do `estado_inputs` do plano liberado, quando o aluno abre o Início, então `GET /inicio` traz `respostas_atualizadas: true` e `pode_refazer_plano: true`; com estado igual, `respostas_atualizadas: false`; fora desses estados `pode_refazer_plano` é falso e `respostas_atualizadas` é `null` |
| `AC-186` | `US-35` | Dado `respostas_atualizadas: true`, quando o Início é exibido, então ele mostra "Você atualizou suas respostas depois do seu plano." e a ação "Gerar um novo plano"; ao confirmar (texto de `AC-184`) o pedido é feito e a tela vai ao cálculo; com `respostas_atualizadas: false` ou `null`, a ação aparece sem o aviso de atualização |
| `AC-187` | `US-35` | Dado um caso em `AGUARDANDO_REVISAO`, quando o aluno abre o Início, então há a ação "Quero editar minhas respostas" com a confirmação de `RF-115`; confirmada, o caso volta a `COLETA_INICIAL` e a tela vai a "Minhas respostas" |
| `AC-188` | `US-35` | Dado um caso liberado em que a montagem recusa alguma resposta (a comparação é impossível), quando `GET /inicio`, então a rota responde `200` com `respostas_atualizadas: null` — a falha da comparação nunca derruba o Início — e o Início não afirma mudança |

### Rodada 15 (2026-10-05) — Conferência com a visão do aluno

> **Rastreabilidade `RF` → `AC`.** `RF-121` → `AC-189`, `AC-190` · `RF-122` → `AC-191` · `RF-123` → `AC-192` · `RF-124` → `AC-193` · `RF-125` → `AC-194`, `AC-195`, `AC-196`, `AC-197` · `RF-126` → `AC-198`, `AC-199`, `AC-200`.

| ID | Story | Critério (verificável) |
| --- | --- | --- |
| `AC-189` | `US-36` | Dado um caso em `AGUARDANDO_REVISAO`, quando o revisor abre `GET /api/revisao/caso/{id}`, então o `plano` traz **os mesmos campos e textos** que o plano do aluno (`secoes`, `resumo_textos`, `grade_meses_textos`, `fonte` e `orientacao_seguro` por dívida, `nome_do_aluno`), e além deles `JUSTIFICATIVA_POSICAO` por posição e `motivo` por ação, que a rota do aluno nunca devolve |
| `AC-190` | `US-36` | Dado o revisor na conferência, quando a tela carrega, então ela exibe o plano do aluno (título, resumo, jornada, uma seção por dívida, reserva, dúvidas e carimbo) e **não** exibe "Baixar em PDF" nem "Responder agora"; e a tela do aluno continua exatamente como antes |
| `AC-191` | `US-36` | Dado um plano com dívidas, quando o revisor abre a seção "Para o revisor" do cartão de uma dívida, então vê os dados de entrada **dessa** dívida, e a justificativa técnica da posição não aparece; o aluno não vê a seção |
| `AC-192` | `US-36` | Dado um plano versão 2 cuja taxa do cheque especial passou de 4% para 8%, quando o revisor o abre, então `mudancas` lista essa taxa com o valor anterior e o atual e **não** lista campos iguais; na versão 1, `mudancas` é `null` |
| `AC-193` | `US-36` | Dado um caso com snapshot, quando um revisor pede `GET /revisao/caso/{id}/plano/pdf`, então recebe um PDF marcado como prévia mesmo sem liberação; um aluno recebe `403`; caso sem snapshot, `404`; e `GET /caso/{id}/plano/pdf` do aluno segue `404` antes da liberação |
| `AC-194` | `US-36` | Dado um plano normal, quando o plano é montado, então traz a introdução do curso e o quadro com a aula 12; dado plano de estabilização, o quadro traz as aulas 5, 6 e 19 e o HTML não contém a palavra "sobra"; toda aula citada existe em `docs/curso-ssd/estrutura.md` |
| `AC-195` | `US-36` | Dado resultado do mês exatamente zero, quando o plano é montado, então é plano normal (sem estabilização) com o aviso de que não há valor extra; com valor extra, o aviso não aparece |
| `AC-196` | `US-36` | Dada uma dívida com nota de incômodo 9 que não é a 1ª posição, então o aluno vê a nota e o aviso; com nota 5, vê só a nota; sem nota, nada |
| `AC-197` | `US-36` | Dado o plano do revisor, então cada dívida traz as respostas de atraso, cobrança judicial e garantia; o plano do aluno nunca as traz |
| `AC-198` | `US-36` | Dado um plano com prognóstico, então tela e PDF trazem os caminhos vermelho e azul; com `B3.C01A` positiva, também o verde; sem prognóstico no snapshot, o capítulo mostra os três números de antes |
| `AC-199` | `US-36` | Dado um plano com prognóstico, então o PDF tem 10 capítulos e o 5º traz as linhas com marcos de quitação, o mês a mês por caminho e a tabela "Quando cada dívida termina"; sem prognóstico, os três números e a tabela só com a coluna do plano; a frase do Mês 1 aparece no 5º e no 6º capítulo |
| `AC-200` | `US-36` | Dado um plano com mês a mês no snapshot, então o PDF tem 10 capítulos (5 plano em números, 6 plano detalhado, 7 mês a mês em detalhe); cada bloco do mural é um link para o cartão do mesmo mês e plano; os meses aparecem como "Mês 01"…, sem data; sem valor extra, só o plano seguido; nenhum "O que fazer no Mês 1" nem checklist |

## 5. Non-Functional Requirements

- **Performance:** cada transição de pergunta responde em p95 < 500 ms. A
  execução completa do Bloco 6 (montagem do estado + `calcular_plano` +
  persistência do snapshot) conclui em p95 < 10 s para um caso com até 20
  dívidas; acima disso, o aluno vê estado de progresso, nunca uma tela travada.
- **Acessibilidade:** WCAG 2.1 AA no fluxo de coleta e na apresentação do plano;
  navegação completa por teclado; rótulo associado a todo campo; mensagem de erro
  de validação (ex.: `RF-07`) anunciada a leitor de tela e vinculada ao campo que
  a originou.
- **Responsividade:** o fluxo de coleta e a leitura do plano funcionam em tela de
  360 px de largura até desktop. A persona é um servidor respondendo
  provavelmente com o celular na mão e o contracheque ao lado — a ficha repetível
  do Bloco 5 precisa ser utilizável nessa largura.
- **Segurança:** autenticação com senha (`RF-02`); senha nunca armazenada em
  texto claro; isolamento por caso verificado no servidor a cada requisição,
  nunca apenas na interface; dados sensíveis por natureza (dívidas, renda,
  contracheque, negativação, cobrança judicial, patrimônio familiar) trafegam e
  repousam cifrados; a base é compartilhada com outros sistemas, então os objetos
  desta feature vivem em schema dedicado, como já faz `motor_calculo`;
  imutabilidade de snapshot garantida no banco por privilégio e trigger, não
  apenas por disciplina de código.
- **Observabilidade:** todo `calcular_plano` registra `SNAPSHOT_ID`,
  `hash_inputs`, `ENGINE_VERSION` e `PARAMETROS_VERSION`; toda liberação ou
  reprovação de revisão registra autor, data e decisão; a trilha de progresso
  (`RF-31`) permite localizar em que pergunta cada caso parou. Nenhum log contém
  valor monetário, saldo, renda ou identificador pessoal do aluno.

### Rodada 2 (2026-09-07) — fatia 2A

- **Pureza da montagem (mantida).** As cinco leituras novas não introduzem
  relógio, ambiente nem estado global: `montar_estado_financeiro` continua função
  pura, verificada por `tests/app_aluno/estatica/test_sem_relogio_em_montagem.py`.
  A mesma `RespostasCaso` produz sempre o mesmo `EstadoFinanceiro`.
- **Fronteira `Decimal` única (mantida).** Nenhum `Decimal(...)`/`dinheiro(...)`
  literal é acrescentado a `app/montagem/estado.py`. O único zero disponível
  neste módulo é `_ZERO`, que vem da mesma fronteira
  (`app/montagem/conversao.py`, `RF-13`) — verificado por
  `tests/app_aluno/estatica/test_fronteira_decimal_unica.py`.
- **Compatibilidade de contrato.** A fatia 2A é **consumo** de um contrato de
  entrada já publicado por `motor-calculo`: nada em `engine/` é alterado. A única
  mudança em arquivo compartilhado é a regravação de `hashes_congelados.json`,
  que é registro, não código.
- **Observabilidade do desconhecido.** `RESERVA_MOBILIZAVEL` desconhecida é
  estado registrável, não erro: aparece na trilha do caso (`RF-31`) e na tela do
  revisor (`RF-26`) como pendência, sem log de valor monetário (o NFR de
  observabilidade da Rodada 1 continua valendo — nenhum log carrega saldo, renda
  ou valor de reserva).
- **Tolerância.** Zero para os campos desta fatia: `RESERVA_EXISTE`,
  `DISPOSICAO_USO_RESERVA` e a distinção `DESCONHECIDO` × valor não admitem
  aproximação. `± R$ 0,05` só se aplica a valores monetários acumulados, e
  nenhum valor desta fatia é acumulado — todos são leitura direta de resposta.

### Rodada 9 (2026-09-30) — decisões do especialista

- **Acessibilidade.** O alerta de inventário incompleto (`RF-86`) e a
  divergência de desconto (`RF-84`) são anunciados a leitor de tela e
  vinculados ao campo ou à ficha que os originou — mesma exigência da Rodada 1
  para mensagens de validação.
- **Tolerância.** Zero para bloqueio do cálculo (`RF-86`–`RF-88`), nível da
  Fonte de comprovação (`RF-91`) e exibição/ocultação de perguntas do Bloco 7
  (`RF-94`). Valores da `B3.C00` e do desconto são exibidos ao centavo, sem
  arredondamento intermediário (`G-01`).
- **Observabilidade.** Bloqueio por inventário incompleto aparece na trilha do
  caso (`RF-31`) e no painel do operador (`RF-35`) como motivo nomeado — sem log
  de valor monetário.

## 6. Edge Cases

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-01` | Entrada monetária inválida ou ambígua (`"mil reais"`, `"1.2.3"`, texto vazio num campo `OBR`) | A fronteira de conversão recusa, a coleta não avança, e nenhum valor parcial ou default é gravado. Nunca há coerção silenciosa para `0` |
| `EC-02` | Validação cruzada violada (`VALOR_UTILIZADO_MARGEM > VALOR_TOTAL_MARGEM`) | Resposta recusada com mensagem apontando os dois campos envolvidos; nenhum dos dois é gravado com o par inconsistente |
| `EC-03` | O motor levanta `ErroInvariante` durante `calcular_plano` | A falha é registrada com o `hash_inputs` do estado, o caso fica em estado de erro visível ao operador, e **nenhum** plano parcial ou degradado é exibido ao aluno. Invariante quebrado é bug, não situação de negócio |
| `EC-04` | Falha ao carregar os parâmetros da fonte externa (`ErroParametros`) | O cálculo não é tentado; o caso permanece no estado anterior e o erro é reportado ao operador. Nunca se calcula com parâmetro default embutido no código |
| `EC-05` | Banco indisponível ou pausado no meio da coleta | A resposta em curso não é dada como salva; o aluno vê que a gravação falhou e pode repetir. Nenhuma resposta é reportada como persistida sem ter sido |
| `EC-06` | Timeout na execução do Bloco 6 | O caso não fica preso em "calculando": ou o snapshot foi persistido (e o estado avança), ou não foi (e o caso volta ao estado anterior, apto a recalcular). Nunca um estado intermediário sem snapshot correspondente |
| `EC-07` | `ORDEM_QUITACAO` vazia — nenhuma dívida elegível após os gates (`DIVIDA_ALVO_ATUAL = None`) | O plano é apresentado com a `ORDEM_ACOES` em primeiro plano: o que precisa ser resolvido antes de existir ataque. Não se exibe uma ordem vazia sem explicação |
| `EC-08` | Aluno responde "não sei" a todos os campos materiais de todas as dívidas | O plano é gerado, sai `PROVISORIO`, e explicita ao aluno quais informações faltantes o mantêm provisório. Não se recusa a coleta nem se inventa valor |
| `EC-09` | Modo estabilização (`MODO_ESTABILIZACAO = SIM`, `CAPACIDADE_ATAQUE_ATUAL = 0`) | A apresentação nunca chama de "sobra" o `RESULTADO_CAIXA_OBSERVADO` positivo; método, ordem e cronograma aparecem como fase 2 condicional à estabilização (`GAB-04`) |
| `EC-10` | Duas sessões simultâneas do mesmo aluno respondendo a mesma pergunta | A última gravação confirmada vence e é a única persistida; nenhuma resposta é mesclada silenciosamente entre sessões, e o estado do caso permanece consistente |
| `EC-11` | Recálculo produz um snapshot idêntico ao anterior (mesmo `hash_inputs`) porque nada material mudou, mas houve evento | O snapshot é versionado assim mesmo (`R-05`: com evento, sempre versiona) e entra na fila de revisão como qualquer outro |
| `EC-12` | Revisor reprova o relatório | O plano não é liberado, a reprovação é registrada com autor e data, o snapshot permanece intacto (append-only) e ~~o caso vai para tratamento do operador~~ **o caso volta ao aluno com a mensagem do revisor e os dados a conferir (`RF-113`, revisão de 2026-10-02)**. Nunca se edita o snapshot para "corrigir" |
| `EC-13` | Aluno pede exclusão dos dados com casos em andamento | Procedimento de exclusão executado conforme o texto de `PEND-01`. Enquanto `PEND-01` estiver aberto, a resposta é a definida por ele — não uma decisão do desenvolvedor |
| `EC-14` | O aluno abandona a coleta e não volta por meses | O caso permanece retomável com todas as respostas; a trilha de progresso o marca como parado, com data da última interação |

### Rodada 2 (2026-09-07) — fatia 2A

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-15` | `B4.03A` respondida com **"Prefiro decidir somente depois de ver a análise."** — opção que no registro (`bloco-04.yaml:154`) não tem `valor_interno` **nem** `admite_nao_sei`: um terceiro estado sem representação | `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` chega ao motor como `DESCONHECIDO`, porque é o que a Regra 3 da §13.1 exige aritmeticamente ("decisão adiada" e "não sei" produzem o **mesmo** `DESCONHECIDA`). A distinção fina entre os dois — se a devolutiva precisar dela — vive em `app/`, nunca no campo entregue ao motor. **Como o registro expressa esse terceiro estado é `OQ-22`, aberta**; enquanto ela estiver aberta, a leitura não pode distinguir os dois pelo `valor_interno`, e tratar a opção sem `valor_interno` como qualquer coisa diferente de desconhecido seria inventar |
| `EC-16` | `B4.02 = NAO` (não há reserva), e por isso `B4.02A`, `B4.02B` e `B4.03` não foram exibidas (`condicao_exibicao` as suprime) | `RESERVA_EXISTE = NAO` é lido normalmente; os campos condicionais ausentes **não** são erro — a Regra 1 da §13.1 curto-circuita em `RESERVA_MOBILIZAVEL = 0` no motor, e a montagem entrega os campos dependentes no estado que a ausência de resposta legitimamente produz, sem inventar valor e sem levantar erro por pergunta que o próprio registro mandou não exibir |
| `EC-17` | `B4.03 = NAO` (recusa preservar a reserva), e por isso `B4.03A` não foi exibida | Mesmo tratamento de `EC-16`: `DISPOSICAO_USO_RESERVA = NAO` é lido, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` fica desconhecido por ausência legítima, e a Regra 1 zera `RESERVA_MOBILIZAVEL` no motor. A montagem **não** antecipa esse zero |
| `EC-18` | `RESERVA_MOBILIZAVEL` volta do motor como `DESCONHECIDO` e uma tela precisa exibi-la | Nenhuma tela quebra e nenhuma exibe `R$ 0,00`: o estado "pendente de decisão" é apresentado como tal (`RF-43`, `AC-70`). Hoje nenhuma tela de `app/` trata esse caminho, porque o campo era sempre `0` — passa a ser caminho alcançável a partir desta fatia |
| `EC-19` | O aluno preencheu fichas de investimento, imóvel, veículo ou outro ativo no Bloco 4, mas o estado é montado com as coleções vazias | O plano é calculado sem esses recursos, e a lacuna é **visível**, não silenciosa: o caso registra que há patrimônio declarado ainda não considerado (`motor-calculo:OQ-26`/`OQ-27`, abertas). Nunca se classifica por omissão — nem como `NAO_MOBILIZAR`, que não é neutro: é uma afirmação sobre o patrimônio do aluno que ninguém calculou |
| `EC-20` | `B4.01 = "Não sei ao certo"` (`valor_interno: NAO_SEI`, `admite_nao_sei: true` em `bloco-04.yaml:18`), com `B4.01A` não exibida | `DINHEIRO_DISPONIVEL` é `Dinheiro` puro e não admite desconhecido (`engine/estado.py:517`). O caminho é erro nomeado, nunca zero silencioso — a mesma disciplina de `_renda_principal`. **Qual erro e como a coleta se recupera dele é parte de `OQ-23`**, que também pergunta se o registro deveria bloquear esse par de respostas |

### Rodada 3 (2026-09-14) — protótipo validado e máscara de entrada

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-21` | JavaScript desabilitado, indisponível ou ainda não carregado | O `<form method="post">` nativo continua gravando pela mesma rota e pelos mesmos sete passos. Nenhuma resposta depende de máscara para ser aceita: a máscara é conveniência de digitação, nunca condição de gravação |
| `EC-22` | O aluno cola um valor já formatado (`"R$ 1.234,56"`) num campo `MOEDA` | O `R$` e o espaço são caracteres que `_CARACTERES_ACEITOS` recusa. A máscara descarta o prefixo ao formatar; se ainda assim chegar caractere não numérico ao servidor, a resposta é `400` e nada é gravado — jamais uma tentativa de "adivinhar" o número dentro do texto |
| `EC-23` | Não há pergunta pendente quando `GET /caso/{CASO_ID}/pergunta` é chamado (coleta completa) | A rota responde com o estado "coleta completa", encaminhando ao Bloco 6 — nunca uma pergunta arbitrária, nunca `500`, e nunca uma pergunta já respondida reapresentada como pendente |
| `EC-24` | A pergunta seguinte existe, mas sua `condicao_exibicao` é falsa | O servidor avança até a próxima exibível e devolve **essa**. O cliente nunca recebe a pergunta fechada nem qualquer meio de descobrir por que ela foi pulada — `RF-05` não atravessa a fronteira |

### Rodada 5 (2026-09-17) — navegação fiel ao protótipo

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-25` | O caso está num estado sem etapa óbvia para o aluno — `CALCULANDO`, `ERRO_DE_CALCULO` ou `ENCERRADO` | A tela Início mostra **o estado e o que esperar**, nunca uma tela vazia nem uma etapa inventada. `CALCULANDO` e `ERRO_DE_CALCULO` são ambos fase `revisao` — *é com a gente, você não faz nada* —, e o erro técnico **jamais** é exposto ao aluno: `mensagem_do_estado_do_caso` já diz *"Seu plano está em nova análise"*. `ENCERRADO` mostra o cartão de acompanhamento com lista de ações vazia e a mensagem de encerramento — **não** é uma sexta fase |
| `EC-26` | O aluno chega por um hash desconhecido, antigo ou digitado errado (`#nao-existe`) | A aplicação exibe a tela **Início** — a raiz do fluxo, que sabe ler a fase e decidir o próximo passo. Nunca uma tela em branco, e nunca um erro que sugira que o caso está perdido |
| `EC-27` | O aluno usa o botão "voltar" do navegador no meio do fluxo | A tela anterior é exibida, com foco no `<h1>` e título atualizado como em qualquer outra navegação. Navegar por dentro do app e navegar pelo histórico do navegador produzem o mesmo resultado |

### Rodada 9 (2026-09-30) — decisões do especialista

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-28` | Renda principal ou alguma despesa do Bloco 3 respondida "não sei" quando `B3.C00` é exibida (`DE-01`) | Renda principal "não sei" (ou sem resposta): a Renda total aparece como **não informado**, nunca como `R$ 0,00`. Item de renda adicional ou de despesa "não sei": o total mostra o valor dos itens informados, marcado **"parcial (há itens sem valor)"** — o motor segue somando os informados (`OQ-16`); decisão do responsável do produto de 2026-09-30 (risco `R9-2`, `T-225`). A Sobra do mês não é exibida como número enquanto a Renda total for desconhecida (`RF-12`); com um dos totais parcial, a sobra recebe o **mesmo tratamento dos totais** — valor com os informados, marcado "parcial (há itens sem valor)" (decisão do produto de 2026-09-30). A coleta segue |
| `EC-29` | O aluno volta à `B3.C00` depois de cadastrar dívidas (`DE-01`) | A sobra continua sendo a de antes das dívidas, com o mesmo rótulo — parcelas nunca entram na fotografia (`AC-118`) |
| `EC-30` | `B7.13A` = "O credor informou apenas que existe desconto, sem detalhar", sem valor final informado (`DE-03`) | Nenhum desconto é presumido: o valor líquido fica desconhecido, sinalizado, e o valor de quitação antes do desconto continua registrado separado |
| `EC-31` | Percentual de desconto informado, mas valor atual de quitação antes do desconto respondido "não sei" (`DE-03`) | O líquido não é calculado. O percentual **nunca** é aplicado sobre saldo devedor, valor contratado ou soma das parcelas como substituto |
| `EC-32` | `B5.00` = "Não sei exatamente quantas" (`DE-04`) | Não há contagem para comparar e nenhuma mensagem de "faltam N fichas" é exibida; a completude passa a ser a confirmação do aluno em `B5.FIM01` ("Não, esta foi a última") (`OQ-56`, `AC-153`) |
| `EC-33` | Fichas cadastradas **acima** do número declarado em `B5.00` (`DE-04`) | O sistema pede ao aluno que atualize `B5.00` (ação direta) e bloqueia o cálculo final até cadastradas = declaradas (`q4_1`, `OQ-56`, `AC-154`) |
| `EC-34` | `B3.S01 = Não sei` (vínculo consignável incerto) sem nenhuma ficha de vínculo (`DE-04`, `DE-05`) | Não há pendência de `RF-88`: a exigência de ao menos um item vale só para resposta **Sim** |
| `EC-35` | O aluno remove um vínculo ao qual margens ou dívidas consignadas estão ligadas (`DE-05`) | A remoção não deixa margem nem consignado apontando para vínculo inexistente: o aluno vê os itens dependentes antes de confirmar, e os que perderem o vínculo voltam a ficar com pendência (`AC-137`, `AC-139`) |
| `EC-36` | `B8.15` "Simulação fornecida pela instituição" e "Correspondente" (`DE-06`) | "Simulação fornecida pela instituição" é registro da instituição → nível 1 "Comprovado por documento/registro"; "Correspondente", como "Atendimento", é informação verbal → nível 3 "Pendente de confirmação" (decisão da equipe técnica, 2026-09-30) |
| `EC-39` | Seguro com situação "Não sei" (`DE-03`) | Não soma em lugar nenhum; o dado fica registrado como "não informado" — não é "Pendente de confirmação", que é só para informação verbal (`OQ-54`, `AC-155`) |
| `EC-40` | Revisor tenta liberar um caso com dado indispensável em "Pendente de confirmação" ou ausente (`DE-06`, `DE-08`) | A liberação é recusada por qualquer rota; a tela lista as pendências; o snapshot permanece intacto e na fila. Confirmado ou corrigido o dado (o que gera novo cálculo pelos caminhos já existentes), a liberação volta a estar disponível (`OQ-64`, `AC-142`) |
| `EC-41` | Soma das rendas líquidas dos vínculos diverge da renda informada no Bloco 3 (`DE-05`) | Divergência sinalizada ao aluno e ao revisor; nenhum valor é somado de novo nem substitui a renda do Bloco 3; não bloqueia (`OQ-58`, `AC-156`) |
| `EC-42` | O aluno retira o plano da conferência no mesmo instante em que o revisor decide (`RF-116`) | Só uma das duas transições (`AGUARDANDO_REVISAO` → `COLETA_INICIAL` ou → `PLANO_LIBERADO`/`REPROVADO_EM_REVISAO`) é aplicada, pela trava de `RF-31`; quem perde recebe `409`. Se foi o revisor quem perdeu, o registro da decisão (gravado antes da transição, por auditoria) fica sem efeito sobre o estado |
| `EC-43` | O revisor está com o caso aberto quando o aluno o retira (`RF-115`) | A tela do revisor continua mostrando o plano que ele abriu, mas liberar ou reprovar devolve a mensagem de `AC-178`; ao voltar à fila, o caso não está mais lá até ser reenviado |
| `EC-44` | O aluno pede o plano novo, mas o inventário está incompleto ou a montagem recusa uma resposta (`RF-118`) | O caso fica em `COLETA_INICIAL` com o plano liberado intacto; o cálculo recusa como sempre (`400`/`422`, com as pendências) e o aluno corrige e envia de novo. Nada do plano atual se perde |
| `EC-37` | O aluno troca o tipo de proposta de parcelada para à vista depois de responder `B7.07`–`B7.09` (`DE-07`) | As respostas do parcelamento deixam de ser exibidas, de contar no progresso e de chegar ao motor; nenhuma delas vira `DESCONHECIDO` por ter ficado inaplicável |
| `EC-38` | Recurso extraordinário `CONFIRMADO` com valor "Não sei" ou janela "Ainda não sei" (`DE-02`) | Não entra na projeção (não há valor estimável nem mês previsto); o item continua cadastrado e visível ao revisor — nunca vira `0` nem ganha janela presumida |

## 7. Assumptions

- **A arquitetura é um app web dedicado** (front-end + API + banco), decisão do
  especialista em 2026-09-03, que fecha `OQ-01` do discovery e `PEND-05` da
  canônica. A §15.2 da canônica recomenda Sheets + Apps Script + Docs→PDF, mas a
  própria §15 abre declarando que as restrições *"decorrem da especificação, não
  de preferência de ferramenta"* — a recomendação é de viabilidade, não trava
  metodológica. As travas reais da §15.1 (ficha repetível, condicional composta,
  texto dinâmico, validação cruzada, motor entre coletas) permanecem integralmente
  exigíveis e estão em `RF-04` a `RF-08`.
- **A coleta é completa**: as 291 perguntas, Etapa B inteira mais Blocos 7, 8, 10
  e 11 (`OQ-02` respondida). Não há recorte mínimo. Disso decorre que coleta
  multissessão com retomada (`RF-10`) é requisito essencial, não conveniência.
- **Há um único revisor implícito** (`OQ-03` respondida): não se modelam papéis,
  permissões diferenciadas nem atribuição de casos. A fila é uma lista única.
- **Todo snapshot passa por revisão** (`OQ-04` respondida), incluindo recálculos.
  Isso torna o volume de revisão proporcional aos eventos do Bloco 11, não ao
  número de alunos — premissa sustentada pelo volume baixo do piloto
  (`OQ-06` respondida: 1–3 alunos, em série).
- **A fronteira é front + camada de aplicação fina** (§0). `engine/` e
  `persistencia/` estão prontos e são consumidos, não reescritos. A camada de
  aplicação orquestra e não calcula: nenhuma decisão financeira nasce nela.
- **O motor está pronto e correto.** Esta feature o consome como caixa-preta
  verificada: 78/78 tarefas, três gabaritos numéricos, cinco invariantes. Nenhum
  comportamento do motor é reimplementado, contornado ou "ajustado" aqui.
- **`persistencia/` já resolve snapshots e parâmetros.** O adaptador
  Supabase/Postgres existe e funciona, implementando `FonteParametros` e
  `RepositorioSnapshots`. Esta feature acrescenta a persistência que é **sua** —
  respostas de coleta, contas de acesso, estado do caso, fila de revisão — sem
  tocar na de snapshots, e sem criar uma segunda via de escrita para eles.
- **Os parâmetros vêm da fonte externa já existente**, na versão vigente, e o
  carimbo `PARAMETROS_VERSION` do snapshot identifica quais valores produziram
  aquele plano.

> ### ⚠ Exceção ao congelamento de `engine/` — três mudanças, todas de outro slug
>
> Para que `RF-33` possa ser satisfeito, `ORDEM_ACOES` precisa passar a carregar
> **toda** ação que o Bloco 11 pergunta. Isso são **três** mudanças em `engine/`
> (decisões do especialista de 2026-09-03, `OQ-10` e `OQ-14`) — não uma:
>
> | # | Mudança | Efeito |
> | --- | --- | --- |
> | 1 | `AcaoRequerida` ganha os campos `ACAO_ID` e `TIPO_ACAO` | Acréscimo de contrato de saída |
> | 2 | **Gate 1 passa a emitir `AcaoRequerida`** de tipo informação, onde hoje passa `acao=None` (`engine/gates.py:204` e `:221`) | **Altera a saída de um gate já verificado por gabarito** |
> | 3 | **Ação de economia passa a ser emitida fora do fluxo de gates**, quando `ECONOMIA_POTENCIAL_IMEDIATA > 0` | **Quebra o invariante de que toda `AcaoRequerida` é sobre uma dívida** |
>
> **Nenhuma delas é executada por esta feature.** Todas são trabalho do slug
> `motor-calculo`, que já entregou o motor. Esta spec **declara a dependência**:
> `RF-33` não pode ser satisfeito antes dela, e `US-08` — o ciclo que separa
> "gerou um PDF" de "o método está rodando" — depende de `RF-33`.
>
> **Por que não fere a Lei nº 1.** As três são sobre o contrato de **saída**, não
> a interface se acomodando dentro do motor: `ORDEM_ACOES` já é saída pública do
> `SnapshotOrdem`, e o Bloco 11 inteiro é dirigido por ela. Nenhuma introduz I/O,
> lê relógio ou rede, nem altera fórmula de cálculo — `calcular_plano` continua
> função pura. O próprio docstring de `AcaoRequerida` já previa a extensão por
> escrito: *"a estrutura completa de `ORDEM_ACOES` é consolidada em `T-32`, que
> pode estender esta dataclass com novos campos sem quebrar o contrato aqui
> fixado"*. A extensão é o caminho que o motor deixou aberto, não uma violação.
>
> **Mas 2 e 3 não são de graça.** A mudança 2 altera o que um gate verificado
> devolve, e a 3 altera um invariante estrutural do contrato (`DIVIDA_ID` deixa
> de estar sempre presente). Ambas estão registradas em Riscos, e a identidade
> da ação de economia é `OQ-15`, **respondida**: `DIVIDA_ID` passa de `str`
> para `str | None`, identificada só por `ACAO_ID`.
- **O aluno tem acesso a um navegador e a um dispositivo pessoal**, e é capaz de
  responder um questionário longo com apoio de documentos (`DOCUMENTACAO_
  DISPONIVEL`, `FONTE_DADO`). Baixa familiaridade financeira é presumida; a
  redação das telas já é responsabilidade da canônica, não desta feature.

### Rodada 2 (2026-09-07) — fatia 2A

- **`RESERVA_MOBILIZAVEL` já é calculado de verdade — esta fatia não o "liga".**
  `engine/diagnostico.py:788-815` já chama `derivar_RESERVA_MOBILIZAVEL` com os
  quatro campos reais do estado (`RF-43`/`AC-85` de `motor-calculo`, `T-114`).
  Ele devolve `0` hoje porque a montagem passa `RESERVA_EXISTE = NAO` e a Regra 1
  da §13.1 curto-circuita. O que muda com a leitura real é a **entrada**, não a
  derivação. Descrever esta fatia como "passa a calcular a reserva" seria
  factualmente errado e convidaria a reimplementar no app o que o motor já faz.
- **Os `valor_interno` de `B4.02`/`B4.03` batem caractere por caractere com os
  `name` dos enums.** Verificado: `SIM`/`INFORMAL`/`NAO`
  (`bloco-04.yaml:52-57` ↔ `engine/estado.py:187-189`) e
  `PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO` (`:127-133` ↔ `:197-200`). É isso — e só
  isso — que torna a resolução por `_membro_do_enum` possível sem escrever
  tradução de rótulo no código, proibida por `AC-37`. Se um registro futuro
  divergir, `ErroValorInternoDesconhecido` falha explicitamente (`AC-54`); o
  contrato **não** se conserta com um `if`.
- **A §13 de `motor-calculo` é congelada e prevalece.** *"Nenhuma dessas decisões
  fica a critério do desenvolvedor."* Onde a §13 fixa comportamento — em
  especial que `DESCONHECIDA` não vira zero (§13.1) e que nenhum recurso aparece
  em dois componentes (§13.8) — esta spec **endereça**, não reinterpreta.
- **O ganho desta fatia não inclui o Bloco 10.** `ATAQUE_IMEDIATO_RECOMENDADO`
  segue `dinheiro(0)` por decisão registrada (`engine/diagnostico.py:845-850`,
  `motor-calculo:OQ-29`, aberta), logo `T-77`/`T-78`/`T-79` continuam
  bloqueadas. O bloqueio **migrou** de "o campo não existe" (`OQ-17`, respondida)
  para "o campo existe e vale zero por decisão registrada" — não desapareceu. O
  aluno **não** verá ataque imediato recomendado ao fim desta fatia; verá a
  reserva mobilizável correta.
- **A allowlist de `AC-41` foi desenhada para crescer sob critério.** O próprio
  arquivo registra isso por escrito sobre `Oportunidade`: *"deve ser adicionada
  pelo mesmo critério quando uma tarefa futura a consumir"*
  (`test_fronteira_import_engine.py:70-72`). Ampliá-la com os dois enums de
  reserva é o procedimento previsto, não uma exceção aberta — e é ampliação por
  fatia, para que a lista nunca contenha nome que ninguém importa.
- **Coleção vazia é o estado honesto, e é o que já acontece hoje** — com uma
  diferença: hoje ela nem é construída. A vazia **declarada**, com motivo em
  docstring, é o mesmo padrão de lacuna documentada que este módulo já pratica em
  `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` e em `CONFIABILIDADE_DADOS` como parâmetro
  externo.

### Rodada 9 (2026-09-30) — decisões do especialista

- **As decisões de `docs/decisoes-especialista/README.md` são a fonte.** Onde
  Rodrigo e Marcelo divergiram, vale Rodrigo (`q4_1`, `q4_2`, `q6_1`). O
  `obs` de cada resposta foi lido e só entrou aqui o que o README consolidou ou
  o que o próprio `obs` fixa como regra (travas de `q3_2`, `q3_3`).
- **`DE-05` não é mudança de motor.** `engine/` não consome vínculo nem margem
  hoje (nenhuma ocorrência de `MARGEM`/`VINCULO` em `engine/`). A mudança é de
  canônica (v1.0.2, `E-09`), de registro e de coleta. O registro
  `collection/registros/bloco-03.yaml` já trata `B3.S02`–`B3.S05` como
  `VINCULO_ID`; o que falta é a pertença `MARGEM_ID` → `VINCULO_ID` e o
  vínculo da dívida consignada.
- **`DE-02` é mudança de motor** (`motor-calculo` `RF-70`–`RF-76`) e, deste
  lado, depende da **fatia 2B** (leitura item a item dos extraordinários).
  `OQ-22`(b) já está resolvida (`T-208`); resta `OQ-24`, agora **tarefa
  técnica** (filtro real por escopo em `valores_do_escopo`). Até ela,
  `recursos_extraordinarios` continua tupla vazia declarada (`RF-39`).
- **`DE-04` endurece `RF-15`.** Declarado ≠ cadastrado passa a **bloquear**
  o cálculo final em vez de gerar plano provisório; nos demais casos
  `RF-15`/`AC-07` seguem valendo (`OQ-56`).
- **`DE-03`, `DE-06` e `DE-07` mudam registros da §11**, e por isso entraram
  como **v1.0.3** da canônica (`piq-app-spec.md`, Registro de alterações,
  `E-11` a `E-15`) antes de qualquer edição de YAML (`OQ-52`).
- **As 16 questões desta rodada foram resolvidas pela equipe técnica**
  (responsável do produto, 2026-09-30), sem retorno ao especialista, com base
  nos princípios escritos por ele nas observações: prudência, sem dupla
  contagem, não bloquear, o revisor homologa.

## 8. Risks

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| `PEND-01` (LGPD) resolvido tarde — falta texto de consentimento, política de privacidade, prazo de retenção e procedimento de exclusão | **alto** — o sistema chega pronto e impedido de ligar. A canônica registra esse risco por escrito: *"se ficar para o fim, o projeto chega com o sistema pronto e sem poder ligar"* | Está **fora do caminho crítico técnico** (não bloqueia especificar nem programar) e **dentro do caminho crítico do piloto** (bloqueia coletar dado de pessoa real). Dono e prazo definidos agora, correndo em paralelo. `RF-30` deixa os pontos de encaixe prontos (consentimento, retenção, exclusão) para receberem o texto quando ele existir |
| Confundir `REVISAO_HUMANA_OBRIGATORIA` (campo do motor, caso `S-04`) com a política de revisar 100% no piloto | **alto** — o sistema revisaria só uma fração dos casos, violando `PEND-06` sem ninguém perceber, e o primeiro erro chegaria a um aluno real | `RF-25` nomeia os dois mecanismos distintamente (`REVISAO_HUMANA_OBRIGATORIA` × `POLITICA_REVISAO_INTEGRAL_PILOTO`); `AC-25` testa que um snapshot com o campo em `False` entra na fila mesmo assim, e `AC-28` testa que os dois são distinguíveis na tela do revisor |
| Abandono do aluno no meio de 195 perguntas | **alto** — o piloto não gera nenhum caso completo e não se aprende nada sobre o método | Salvar a cada resposta desde o início (`RF-10`, `AC-02`); trilha de progresso que torna o abandono observável (`RF-31`); medir onde o abandono ocorre. Note que `OQ-02` foi fechada em coleta completa, o que **remove** a mitigação por recorte mínimo — resta a instrumentação |
| Tratar as 291 perguntas como um formulário único / wizard linear | **alto** — arquitetura que não comporta Bloco 7/8 dirigido pelo motor nem Bloco 11 longitudinal; retrabalho estrutural | `RF-01` eleva a máquina de estados do caso a requisito de primeira classe; `AC-19`, `AC-33` e `AC-34` exigem reabertura dirigida e parcial, impossíveis de satisfazer com wizard linear |
| Renderizador "quase" gerado, com atalhos codificados à mão nos pontos difíceis (ficha repetível, `B12.08`, `B12.15`/`B12.16`) | **alto** — nova versão do questionário vira reescrita de código, violando exigência explícita da §11 | `RF-03` a `RF-08` cobrem cada caso difícil como requisito nomeado; `AC-37` audita que nenhum enunciado, opção ou condição das 291 perguntas está escrito no código. O plano precisa **provar** que os cinco casos cabem no gerador |
| Conversão de formulário HTML para `Decimal` feita de forma descuidada | **alto** — `float` atravessa a fronteira e corrompe precisão; o motor recusa em runtime, mas o erro aparece tarde e longe da causa | `RF-13` exige fronteira única e testada; `AC-09` e `AC-10` a verificam com valor exato. `_recusar_float` do motor é a última linha de defesa, não a primeira |
| Revisão humana encaixada depois da coleta e do relatório | **médio** — retrabalho estrutural; ou pior, primeiro envio a aluno real sem revisão | Fila como requisito de primeira classe (`RF-23`, `RF-24`), com o estado "aguardando revisão" dentro da máquina de estados do caso (`RF-01`), não como adendo |
| Revisar 100% dos snapshots, incluindo recálculos, com um único revisor | **médio** — o volume de revisão cresce com os eventos do Bloco 11, não com o número de alunos; o revisor vira gargalo e o acompanhamento longitudinal trava | Premissa sustentada pelo volume baixo do piloto (`OQ-06` respondida: 1–3 alunos, em série) — reavaliar a política se o piloto crescer além disso |
| `RF-33` depende de **três** alterações em `engine/` que **outro slug** precisa entregar, e cujo identificador de `TIPO_ACAO` ainda não está fechado (`OQ-13`) | **alto** — é dependência entre slugs no caminho crítico: sem ela o Bloco 11 inteiro não pode ser dirigido por ação, e `US-08` (o ciclo que separa "gerou um PDF" de "o método está rodando") não fecha | Dependência declarada em `RF-33` e detalhada no bloco de Assumptions, para que apareça no sequenciamento do plano em vez de ser descoberta na implementação. `OQ-13` precisa ser respondida pelo especialista **antes** de a alteração ser escrita — caso contrário o domínio seria inventado |
| **Gate 1 passa a emitir `AcaoRequerida`** onde hoje devolve `acao=None` (`engine/gates.py:204`, `:221`) — altera a saída de um gate já verificado | **alto** — os gabaritos e invariantes do slug `motor-calculo` foram fechados contra a saída atual. `GAB-03` (rotativo sem parcela) e `EC-17` (todas bloqueadas, `ORDEM_ACOES` primeiro) tocam exatamente dívidas travadas por informação: uma `ORDEM_ACOES` que antes vinha vazia passa a vir preenchida | Tratar como revisão de gabarito no slug `motor-calculo`, não como efeito colateral: reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes, e atualizar as expectativas de `ORDEM_ACOES` onde elas mudarem. A tolerância zero para "gates" e "aplicação de resíduo" (§10.3) significa que uma divergência aqui **não** é absorvível por arredondamento |
| **Ação de economia emitida fora do fluxo de gates** quebra o invariante de que toda `AcaoRequerida` é sobre uma dívida (`DIVIDA_ID` deixa de estar sempre presente) | **médio** — todo consumidor atual de `ORDEM_ACOES` pode presumir `DIVIDA_ID` preenchido; a mudança é de invariante, não de acréscimo | Nomeada com destaque no bloco de Assumptions (mudança 3) para ser vista antes da primeira linha de código no slug `motor-calculo`. A identidade dessa ação é `OQ-15`, **respondida**: `DIVIDA_ID: str | None`, identificada só por `ACAO_ID` |
| A camada de aplicação absorve, por conveniência, um cálculo que pertence ao motor ("é só para exibir mais rápido") | **alto** — dissolve a Lei nº 1: o motor deixa de ser reproduzível a partir de uma entrada, os gabaritos deixam de provar o que provam, e um erro de cálculo passa a ter dois lugares possíveis onde morar | Fronteira declarada em §0 com a justificativa; `RF-34` a torna requisito; `AC-41` e `AC-42` a tornam verificável por auditoria de código e por rastreio de origem de cada número exibido |
| Banco compartilhado com outros sistemas pausa por inatividade em piloto de baixo volume | **médio** — o aluno encontra o sistema indisponível justamente entre um acesso e outro, meses depois | Volume confirmado em `OQ-06` (1–3 alunos, em série); avaliar tier adequado antes de abrir o piloto |
| Redação canônica alterada por conveniência de layout na tela | **médio** — `Q-02`/`Q-03` são normativos; alterar o texto é alterar a metodologia sem nova versão da spec | `AC-14` e `AC-15` testam o texto caractere por caractere e a ausência de "definitiva"/"final"/"fixa" |

### Rodada 2 (2026-09-07) — fatia 2A

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| **`valores_do_escopo` não filtra por escopo** (`collection/respostas.py:114-128`): o corpo é `if nome_variavel == variavel and item_id != ""` e a própria docstring admite que o parâmetro `escopo` não é usado. Funcionou até hoje porque cada escopo usava nomes de variável distintos. **`VALOR_ESTIMADO_ATIVO` é gravado em quatro lugares de `bloco-04.yaml`** — `:222` (investimento), `:363` (imóvel), `:570` (veículo), `:833` (outro) — e `SALDO_PASSIVO_VINCULADO` em três (`:400`, `:605`, `:868`), `CUSTOS_ESTIMADOS_DESMOBILIZACAO` em três (`:516`, `:772`, `:960`) | **alto** — ler itens sem corrigir isso produz **dupla contagem**: uma chamada a `valores_do_escopo(<imóvel>, "VALOR_ESTIMADO_ATIVO")` devolveria também veículos e investimentos. É exatamente o que a §13.8 veda (*"nenhum recurso pode aparecer simultaneamente em dois componentes"*, *"origem econômica única"*) — e não é falha de tipo, é um número silenciosamente errado no patrimônio do aluno | Registrado como `OQ-24`, **aberta e bloqueante para 2B e 2C**: nenhuma linha de leitura de item pode ser escrita antes dela. **Não afeta a fatia 2A**, que lê apenas cinco campos escalares por `respostas.valor(...)` — e `AC-71` torna essa ausência de dependência verificável, para que a armadilha não seja herdada por engano. A correção é em `collection/`, não em `app/`, e afeta os cinco escopos já em uso: exige não-regressão em renda adicional e despesa não-mensal |
| Descrever a fatia como *"`RESERVA_MOBILIZAVEL` passa a ser calculado"* e alguém reimplementar a Regra 2 (`MIN`/`MAX`) na montagem para "conferir" | **alto** — dissolveria a Lei nº 3 no ponto mais tentador: a fórmula é curta e parece inofensiva. Passaria a existir em dois lugares, e uma divergência futura entre eles não teria dono | Assumptions registra que a derivação **já existe** (`engine/diagnostico.py:788-815`); `RF-44` proíbe qualquer fórmula patrimonial nesta camada; `AC-68` exige explicitamente que o limite `MIN(RESERVA_TOTAL, MAX(0, informado))` seja verificado **na saída do motor**, sem contrapartida na montagem |
| Preencher os 8 campos novos com valores neutros para destravar o `build` | **alto** — já foi tentado e **reprovou** em `test_fronteira_import_engine.py::test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41`; a edição foi revertida integralmente. Repetir a tentativa custa o mesmo tempo de novo, e a versão "que passa" seria a que encontra o ponto cego do lint | `RF-40` trata a ampliação da allowlist como requisito nomeado, com critério e precedente citados, em vez de efeito colateral descoberto na implementação |
| Classificar os itens como `NAO_MOBILIZAR` "porque é neutro", para destravar 2C sem esperar `motor-calculo:OQ-26` | **alto** — não é neutro: é uma afirmação sobre o patrimônio do aluno que ninguém calculou, e produziria o mesmo número final da coleção vazia **com a aparência de que houve classificação**. Derivar em `app/` passaria no lint (que só varre `engine/`) e ainda assim violaria a Lei nº 3 e `sdd.config.md` §6 | `RF-39` fixa a tupla vazia com motivo em docstring; `AC-61` audita a ausência de qualquer derivação ou literal de classificação em `app/`, fechando por decisão o ponto cego que o lint de `engine/` deixa aberto |
| Regravar `hashes_congelados.json` a partir de uma lista transcrita de um enunciado, em vez da saída do teste | **médio** — a lista envelhece entre a redação e a execução; um arquivo a mais ou a menos deixa `AC-44` verde por transcrição e vermelho na realidade seguinte. `engine/ataque_imediato.py` já é um caso concreto: existe no disco e **não** consta do JSON hoje | `RF-41` fixa o procedimento como "rodar o teste, regravar exatamente o que ele apontar", nunca uma lista fixa; `AC-65` verifica os quatro testes de `AC-44`, a presença de `engine/ataque_imediato.py` e a exclusão deliberada de `002_app_aluno.sql` |
| A tela exibe `RESERVA_MOBILIZAVEL` desconhecida como `R$ 0,00` por ser o caminho mais curto de formatação | **médio** — converteria em zero, na apresentação, exatamente o que a §13.1 proíbe converter em zero no cálculo. O aluno leria "sua reserva mobilizável é zero" onde a verdade é "você ainda não decidiu" | `RF-43` e `AC-70` tratam o desconhecido como estado de exibição de primeira classe. A **redação** ao aluno é `OQ-21`, aberta — o comportamento está fixado, o texto não se inventa aqui |

### Rodada 9 (2026-09-30) — decisões do especialista

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Bloqueio de `DE-04` deixa o aluno parado sem saber o que falta | **alto** — o caso não chega ao plano e o abandono vira silencioso | Mensagem exata com números (`RF-87`), mensagem por caso (`RF-88`), alerta permanente (`RF-86`) e motivo visível no painel do operador (NFR de observabilidade) |
| A sobra da `B3.C00` ou o líquido do desconto ser calculado "só para exibir" na aplicação | **alto** — dissolve a Lei nº 3; a mesma conta passa a existir em dois lugares | `OQ-53` e `OQ-55` (resolvidas) fixam que são agregação de entrada, feita **só** na montagem — um lugar, como `OQ-16`; `AC-42` continua exigindo rastrear a origem de cada número exibido |
| Somar margens de vínculos diferentes por conveniência de exibição | **médio** — o aluno leria uma margem disponível que nenhuma folha tem | `RF-90` e `AC-138` proíbem o total em tela, relatório e estado |
| Mudar registros da §11 (`DE-03`/`DE-06`/`DE-07`) sem nova versão da canônica | **médio** — registro e canônica divergem, e a próxima leitura da canônica "desfaz" a decisão | Canônica v1.0.3 (`OQ-52`, resolvida) registra as edições antes dos YAML |

## 9. Out of Scope

- **Alterar `engine/` — congelado, EXCETO as três mudanças de `ORDEM_ACOES`.**
  Esta feature consome `calcular_plano(...)` como está. Nenhuma regra do motor é
  reimplementada, reinterpretada ou duplicada na aplicação. **As únicas exceções**
  são as três mudanças listadas no bloco destacado de Assumptions — campos
  `ACAO_ID`/`TIPO_ACAO` em `AcaoRequerida`, Gate 1 emitindo ação, e ação de
  economia fora do fluxo de gates (`OQ-10`, `OQ-14`, `RF-33`) — e **nenhuma delas
  é feita aqui**: todas são trabalho do slug `motor-calculo`. Se algo mais do
  motor parecer faltar, isso é Open Question — nunca uma mudança presumida.
- **Reescrever `persistencia/`.** O adaptador Supabase/Postgres de snapshots e
  parâmetros já existe e é consumido pelas portas. Esta feature não o modifica,
  não o substitui e não cria caminho paralelo de escrita de `SnapshotOrdem`. A
  imutabilidade (`REVOKE` + trigger `impedir_sobrescrita_v01`) já está garantida
  lá e não é reimplementada aqui.
- **Qualquer cálculo financeiro na camada de aplicação.** Nenhum gate,
  ranqueamento, fórmula da §11 ou valor `P_*` é avaliado fora de `engine/`, nem
  para "só exibir mais rápido" (`RF-34`, `AC-41`, `AC-42`).
- **Bloco 9** (Comportamento e método, 6 perguntas) e **Bloco 12** (Blindagem e
  pós-quitação, 19 perguntas) como fluxos completos. `B12.08`, `B12.15` e
  `B12.16` aparecem aqui apenas como **casos de prova do gerador** (`RF-05`,
  `RF-08`): o gerador precisa comportá-los. Sua coleta efetiva não faz parte
  desta entrega — a decisão do especialista fixou Etapa B mais Blocos 7, 8, 10
  e 11.
- **Redigir os textos jurídicos** de consentimento, política de privacidade,
  prazo de retenção e disclaimer. São `PEND-01`, de responsabilidade do jurídico
  com o especialista. Esta feature entrega os pontos de encaixe (`RF-30`), não
  o conteúdo.
- **Papéis, permissões e atribuição de casos entre revisores.** `OQ-03` foi
  fechada em revisor único implícito.
- ~~**Painel completo do operador.**~~ `OQ-07` respondida: o usuário decidiu que
  o piloto precisa de painel dedicado desde já — passou a ser escopo desta
  entrega (`RF-35`), não mais Out of Scope.
- **Qualquer decisão metodológica.** Ambiguidade na tradução do snapshot para
  linguagem de aluno vira pergunta ao especialista, não decisão de
  desenvolvedor. Nenhuma regra da canônica é reinterpretada aqui.
- **Notificações ativas** (e-mail, SMS, push) lembrando o aluno de reportar
  execução. O Bloco 11 pressupõe que o aluno volte; provocar esse retorno é
  trabalho de processo, ainda não especificado.
- **Importação automática de dados** (contracheque, open finance, extrato
  bancário). Toda resposta é declarada pelo aluno, com `FONTE_DADO` e
  `DOCUMENTACAO_DISPONIVEL` registrando a procedência.

### Rodada 2 (2026-09-07) — o que a fatia 2A deixa de fora, e por quê

- **Investimentos e ativos (fatia 2C) — bloqueados por `motor-calculo:OQ-26`
  **E** `motor-calculo:OQ-27`, ambas abertas com o especialista.** Não é falta de coleta: o
  Bloco 4 tem 49 perguntas e três famílias de ficha de ativo. É que a amarração
  se fecha por três lados, cada um verificado: **(1)** `ItemInvestimento.
  CLASSIFICACAO_MOBILIZACAO` (`engine/estado.py:369`) e `ItemAtivo.
  CLASSIFICACAO_MOBILIZACAO` (`:392`) são obrigatórios e **sem default** — item
  sem classificação é erro de contrato na construção; **(2)** derivar a
  classificação é proibido — `engine/tipos.py:182-186` declara que nenhuma função
  do projeto deve produzir esses quatro valores enquanto aquela questão estiver
  aberta,
  e `AC-67` (`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`)
  torna isso verificável por AST; **(3)** perguntar ao usuário é proibido —
  `specs/piq-app-spec.md:2614`: *"Nunca perguntar a classificação do ativo."*
  Confirmado no registro: nenhuma das 49 perguntas do Bloco 4 grava essa
  variável. **As duas questões precisam estar respondidas — responder só uma não
  destrava:** `VALOR_LIQUIDO_REALIZAVEL`/`VALOR_LIQUIDO_REALIZAVEL_ATIVO_
  DISPONIVEL` (`motor-calculo:OQ-27`) também são obrigatórios e sem default nas três
  dataclasses, e a fórmula não existe. O motor delegou as duas apurações a esta
  camada, e esta camada não tem nenhuma das duas.
- **Recursos extraordinários (fatia 2B) — destraváveis aqui, mas não nesta
  fatia.** É a única das três coleções **sem** `CLASSIFICACAO_MOBILIZACAO`
  (`engine/estado.py:412-413`: *"quem o qualifica são janela e certeza"*),
  portanto a única implementável sem o especialista. Depende de duas correções
  nossas ainda não feitas: `B3.05C` tem `valor_interno: null` nas **cinco**
  opções (`bloco-03.yaml:284-289`) enquanto o enum tem cinco membros
  `ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI` — mapear rótulo em português para
  membro exigiria escrever tradução em código, proibida por `AC-37` (`OQ-22`); e
  o filtro de escopo de `OQ-24`. Errar o mapeamento de janela/certeza não produz
  erro de tipo: `ATE_30D` é o único membro que a §13.3 qualifica como "momento
  atual" e `CONFIRMADO` o único "confirmado" — produziria um número
  silenciosamente errado.
- **Bloco 10 e as tarefas `T-77`, `T-78`, `T-79`.** Dependem de
  `ATAQUE_IMEDIATO_RECOMENDADO > 0` para exibir `B10.C01` (`RF-18`, `AC-22`), e o
  campo segue `dinheiro(0)` como placeholder explícito por
  `motor-calculo:OQ-29`, aberta. O bloqueio migrou de `OQ-17` (respondida — o
  campo passou a existir) para aquela questão; não foi removido.
- **A correção de `valores_do_escopo`.** É pré-requisito de 2B e 2C, mas não desta
  fatia — 2A não lê item nenhum (`AC-71`). Corrigi-la aqui seria mudança em
  `collection/` sem requisito que a consuma, e ela afeta os cinco escopos já em
  uso. Registrada como `OQ-24`.
- **Novos membros de `EscopoRepeticao` e prefixos em `PREFIXO_POR_ESCOPO`** para
  investimento, imóvel, veículo e outro ativo. Todo o Bloco 4 está com
  `escopo_repeticao: NENHUM` no registro, e nenhum dos oito membros atuais cobre
  essas famílias. Decisão de estrutura (uma por família ou uma só) é `OQ-25`, e
  não urge enquanto 2C estiver bloqueada.
- **Redigir o texto que o aluno lê quando `RESERVA_MOBILIZAVEL` é desconhecida.**
  `Q-02`/`Q-03` fixam redação canônica só para a ordem projetada; para este caso
  não há redação publicada. `RF-43` entrega o **comportamento** e o ponto de
  encaixe; o texto é insumo do especialista (`OQ-21`) — texto ao aluno não se
  inventa aqui.
- **Travar a edição do plano já liberado.** `RF-114` fala de cálculo e conferência.
  Depois da liberação (`PLANO_LIBERADO`, `ACOMPANHAMENTO`) as respostas continuam
  editáveis; um plano novo nasce quando o aluno o pede (`RF-118`) ou pelos eventos do
  Bloco 11 (`AC-30`). Editar uma resposta, por si só, não reabre o plano.
- **O revisor editar o plano ou as respostas do aluno.** Hoje ele só aprova ou devolve com
  mensagem (`RF-113`). Edição manual pelo especialista é desejo registrado em 2026-10-05,
  sem requisito ainda.

## 10. Open Questions

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-01` | Arquitetura: seguir a recomendação da canônica (§15.2 — Sheets + Apps Script + Docs→PDF), construir aplicação web dedicada, ou híbrido? | Decide esforço, hospedagem e prazo de tudo que vem depois | `respondida` — **app web dedicado**: front-end, API e banco. Não é Sheets/Apps Script, não é híbrido. A escolha de linguagem, framework e bibliotecas não pertence a esta spec: vai para a seção `Tech Stack` de `plans/app-aluno.plan.md`. As travas da §15.1 continuam valendo integralmente (`RF-04` a `RF-08`) |
| `OQ-02` | O piloto exige a coleta completa (291 perguntas) ou um recorte que alimente só o motor? | Diferença entre um piloto em semanas e um em meses, e entre um aluno que conclui e um que abandona | `respondida` — **coleta completa**: Etapa B inteira (Blocos 1–5) mais Blocos 7, 8, 10 e 11. Sem recorte mínimo. Implica coleta multissessão com retomada obrigatória (`RF-10`), fichas repetíveis (`RF-04`) e o grafo condicional completo (`RF-05`) |
| `OQ-03` | Quem revisa no piloto, e são quantas pessoas? | Define se a fila precisa de papéis, permissões e atribuição | `respondida` — **revisor único implícito**. Sem papéis, sem permissões diferenciadas, sem atribuição de casos. Fila única |
| `OQ-04` | Um recálculo posterior também passa por revisão humana obrigatória, ou só o primeiro envio? | Muda o volume de trabalho do revisor de "uma vez por aluno" para "toda vez que algo acontece" | `respondida` — **todo snapshot passa por revisão**, incluindo os recálculos disparados por quitação confirmada e por evento material do Bloco 11 (`RF-23`, `AC-26`) |
| `OQ-05` | Existe autenticação nesta fase, ou link único por aluno basta? | Login é esforço maior; link único envelhece mal num acompanhamento de meses | `respondida` — **login com senha**. Autenticação real; o aluno volta de qualquer dispositivo ao longo dos meses (`RF-02`) |
| `OQ-06` | Quantos alunos no piloto, e em que janela — 1, 5, 50? Simultâneos ou em série? | Dimensiona infraestrutura e decide se concorrência e isolamento precisam de tratamento real já. **Interage com `OQ-04`**: revisar 100% dos snapshots com um único revisor é sustentável a 1 aluno e possivelmente inviável a 50 | `respondida` — **1 a 3 alunos, em série**. Decisão do usuário. Confirma a sustentabilidade da revisão integral por revisor único (`OQ-04`) e do tier de banco compartilhado nesta janela; não exige tratamento real de concorrência entre alunos nesta entrega — cada caso avança sozinho antes do próximo começar |
| `OQ-07` | O operador precisa de um painel para ver quem travou onde? | Define se entra uma terceira persona na interface ou se `RF-31` (trilha registrada e consultável) basta por ora. Com acompanhamento longitudinal, abandono silencioso é o modo de falha esperado | `respondida` — **sim, painel dedicado, mesmo no piloto de 1–3 alunos**. Decisão do usuário: quer visibilidade direta de quem travou onde, sem depender de consulta manual à trilha. Passa a ser requisito nomeado desta entrega, não mais Out of Scope — ver `RF-35`, que lê a mesma trilha de `RF-31` e apresenta em tela própria |
| `OQ-08` | Quando o aluno responde "não sei" a algo material, ele é avisado na hora ("isso deixará seu plano provisório") ou só descobre no relatório final? | Avisar na hora exige avaliar materialidade durante o preenchimento — antes de o motor rodar —, o que é significativamente mais complexo do que avisar ao final. Se a resposta for "na hora", entra um requisito novo de avaliação incremental de materialidade | `respondida` — **na hora, ao responder**. Decisão do usuário. `RF-11`/`RF-12` já garantem que o "não sei" é preservado e chega ao motor como desconhecido — o que esta decisão fixa é o **quando**: a aplicação avalia materialidade de forma incremental durante o preenchimento (não só ao final), avisando o aluno no momento da resposta que aquilo tornará o plano provisório |
| `OQ-09` | O aluno recebe o plano dentro do app (tela) ou como documento entregue (PDF/e-mail)? Ou ambos? | Muda o que a fila de revisão libera — uma página ou um arquivo — e como o carimbo de versão (`V-03`) aparece na entrega | `respondida` — **ambos: tela dentro do app e PDF exportável**. Decisão do usuário. `RF-20`, `RF-21` e `RF-22` valem para as duas formas; a revisão (`RF-23`) libera o snapshot uma única vez, e a partir daí ambos os objetos — a tela e o PDF gerado sob demanda — refletem a mesma versão carimbada (`V-03`) |
| `OQ-10` | `ACAO_ID` e `TIPO_ACAO` são pressupostos pelas condições de exibição do Bloco 11, mas não existem no contrato do motor: `engine/gates.py::AcaoRequerida` expõe apenas `DIVIDA_ID`, `descricao`, `gate_origem` e `prioridade_excepcional`. Onde eles vivem? | Sem identidade estável de ação entre snapshots, `B11.01` não tem a que se vincular e o ciclo de execução do Bloco 11 não fecha | `respondida` — **os dois campos são acrescentados a `AcaoRequerida`**. É lacuna de contrato de saída, não a interface se acomodando: não introduz I/O, não altera fórmula de cálculo, não fere a Lei nº 1 — e o próprio docstring de `AcaoRequerida` já previa a extensão (*"pode estender esta dataclass com novos campos sem quebrar o contrato aqui fixado"*). `gate_origem` sozinho não basta para tipar a ação, mas `GATE_PENDENTE` mais `RENEGOCIACAO_PENDENTE`/`TROCA_PENDENTE` bastam (ver `OQ-14`). É **uma das três exceções ao congelamento de `engine/`** (ver Assumptions e Out of Scope), todas **executadas pelo slug `motor-calculo`**, não por esta feature. Ver `RF-33` e `OQ-13` (identificador exato do domínio) |
| `OQ-13` | Qual é o **identificador exato** de cada valor de `TIPO_ACAO`? A canônica nomeia o domínio apenas dentro das condições de exibição, e dois dos quatro valores vêm com qualificador entre parênteses: `TIPO_ACAO = INFORMAÇÃO` (linha 4298), `TIPO_ACAO = INTERVENÇÃO (renegociação)` (linha 4312), `TIPO_ACAO = TROCA` (linha 4326), `TIPO_ACAO = CORREÇÃO (economia)` (linha 4340). Os parênteses são **parte do identificador**, glosa explicativa, ou sinal de que o domínio é mais largo do que quatro valores — havendo outras `INTERVENÇÃO` além de renegociação e outras `CORREÇÃO` além de economia? | `RF-33` e `AC-46` dependem de valores de domínio fechado, e a convenção do projeto (`sdd.config.md` §7) exige o nome da canônica **caractere por caractere**. Diferente das outras 270 variáveis, `TIPO_ACAO` e `ACAO_ID` **não têm linha no dicionário de variáveis da canônica** (§11, linhas 4872-5112): `ACAO_STATUS`, `ACAO_DATA_CONCLUSAO` e as quatro `RESULTADO_ACAO_*` estão lá; `TIPO_ACAO` e `ACAO_ID` não. Não há, portanto, domínio publicado a transcrever. Normalizar por conta própria (descartar os parênteses, ou fundir `INTERVENÇÃO`/`TROCA`) seria inventar identificador canônico — exatamente o que a §7 do config proíbe. **Também é preciso decidir se o identificador leva acento**, já que todo o restante do domínio fechado do motor é ASCII (`INFORMACAO_PENDENTE`, `NAO_APLICAVEL`) | `respondida` — **domínio fechado de quatro valores, ASCII, sem parênteses, nomeados pelo conceito específico (não pelo termo genérico que o precede)**: `INFORMACAO`, `RENEGOCIACAO`, `TROCA`, `ECONOMIA`. Decisão do usuário. Justificativa: consistente com a convenção ASCII do resto do domínio fechado do motor (`INFORMACAO_PENDENTE`, `NAO_APLICAVEL`); usar o termo genérico antes do parêntese (`INTERVENCAO`, `CORRECAO`) reabriria a ambiguidade que a própria pergunta levantou — "existe só uma `INTERVENCAO`?" — enquanto o termo específico (`RENEGOCIACAO`, `ECONOMIA`) já responde isso por construção. Esta é a resposta que `T-84`/`T-90` (slug `app-aluno`) e a extensão de `AcaoRequerida` (slug `motor-calculo`, `OQ-10`/`OQ-14`) devem usar caractere por caractere — nenhum outro identificador é válido a partir de agora |
| `OQ-14` | Como `TIPO_ACAO` é **derivado**? | Sem a regra de derivação, `AcaoRequerida` não tem como preencher `TIPO_ACAO`, e o Bloco 11 não pode ramificar | `respondida` — três dos quatro tipos são deriváveis do que o motor **já decide**; o quarto passa a ser emitido. O discriminador não é `gate_origem` (que é `Literal[2, 3]`), e sim `GATE_PENDENTE` (`engine/tipos.py:75-88`), cujo docstring é explícito: *"Gates 2 e 3 compartilham `INTERVENCAO_PENDENTE` e só se distinguem aqui"*. Mapeamento: **informação** ← `GATE_PENDENTE.INFORMACAO` (Gate 1); **intervenção/renegociação** ← Gate 3 + `divida.RENEGOCIACAO_PENDENTE`; **troca** ← Gate 3 + `divida.TROCA_PENDENTE` — o Gate 3 **já ramifica os três casos** em `engine/gates.py:368-374`, escrevendo a origem na `descricao`: a informação existe, só está em prosa em vez de campo tipado. **Correção/economia** não tem origem em gate (gates avaliam dívidas; `ECONOMIA_POTENCIAL_IMEDIATA` é sobre o orçamento) e passa a ser emitida fora do fluxo de gates quando `ECONOMIA_POTENCIAL_IMEDIATA > 0`. Ver as mudanças 2 e 3 no bloco de Assumptions, e `OQ-15` |
| `OQ-15` | Qual é a **identidade** de uma `AcaoRequerida` que não é sobre uma dívida? Com a ação de economia emitida fora do fluxo de gates, `AcaoRequerida` deixa de ser sempre sobre uma dívida: `DIVIDA_ID` passa a poder ser nulo, ou a ação de economia precisa de outra forma de identidade. `ACAO_ID` resolve a identidade **da ação**, mas não diz a que a ação se refere quando não há dívida — a economia nasce de `VALOR_GASTOS_FANTASMAS` com `B2.10A = SIM` (`B2.09`/`B2.10`/`B2.10A`), não de um item com ID próprio | É **mudança de invariante do contrato**, não acréscimo de campo: hoje todo consumidor de `ORDEM_ACOES` pode presumir `DIVIDA_ID` presente. Quem implementar no slug `motor-calculo` precisa ver isso antes de escrever a primeira linha. A canônica contempla ação não-dívida (`B2.09`, linha 960: *"Talvez → gera ação de conferência (Bloco 11)"*) mas **não define identidade para ela** — não há o que transcrever, e decidir aqui seria criar contrato canônico por conta própria | `respondida` — **`AcaoRequerida.DIVIDA_ID` passa de `str` para `str | None`**. Decisão do usuário: é a mudança mínima — nenhum campo novo, só relaxar o tipo de um campo já existente. A ação de economia tem `DIVIDA_ID=None`, identificada exclusivamente pelo `ACAO_ID` (`OQ-10`, já respondida). Consequência que o slug `motor-calculo` precisa observar ao implementar: todo consumidor existente de `ORDEM_ACOES` que hoje presume `DIVIDA_ID: str` presente precisa passar a tratar `None`. O slug `app-aluno` já está pronto para isso — `T-83` construiu o vínculo do Bloco 11 inteiramente sobre `ACAO_ID`, nunca sobre `DIVIDA_ID`, precisamente para não quebrar quando esta decisão chegasse (`AC-50`, já testado em `T-89` sem depender desta resposta) |
| `OQ-11` | Não existe `CASO_ID` de primeira classe: `engine/portas.py::RepositorioSnapshots.historico(caso_id)` usa o `SNAPSHOT_ID` da **raiz da cadeia** como identificador do caso. Com login por aluno (`OQ-05` respondida), o app precisa de um identificador de caso próprio, anterior ao primeiro snapshot. Como os dois se relacionam? | Um aluno existe e responde por semanas **antes** de haver qualquer snapshot; usar a raiz da cadeia como identidade do caso não cobre esse período. É decisão de modelagem desta feature, mas toca o contrato já entregue do motor — que esta feature não pode alterar | `respondida` — **`CASO_ID` é identidade própria de `app_aluno`, gerada no cadastro** (`persistencia/app_aluno/casos.py::RepositorioCasos.criar`), independente de qualquer snapshot. `Caso.snapshot_raiz_id` é a PONTE: fica `None` até o primeiro `calcular_plano` rodar, e só então é preenchido (`registrar_snapshot_raiz`) — nunca alterado depois disso (`AC-18`-like: uma raiz, uma vez). A aplicação chama `RepositorioSnapshots.historico(caso.snapshot_raiz_id)`, nunca `historico(CASO_ID)` diretamente — o motor continua recebendo exatamente o argumento que sempre esperou (a raiz da cadeia), sem alteração de contrato. Os dois identificadores coexistem sem conflito: `CASO_ID` cobre a vida inteira do caso desde o cadastro; `snapshot_raiz_id` só existe a partir do Bloco 6 |
| `OQ-12` | A §25 (classificação de erro em TEXTO, PARÂMETRO, DADO, REGRA, CÁLCULO, UX) é citada pela §15.3 e pelo gabarito `E-08` da canônica, mas seu texto não consta de `specs/piq-app-spec.md` — o documento termina na §15. Onde está a §25, e qual é a definição exata de cada categoria? | `RF-26` exige que o revisor classifique o erro encontrado nessas seis categorias. Sem o texto normativo, a tela de revisão seria construída sobre seis rótulos sem definição — e classificar errado é pior do que não classificar | `respondida` — **confirmado ausente do repositório inteiro** (não só do documento: nenhum `.md`, código ou comentário define as seis categorias em lugar algum). Decisão do usuário: manter, por ora, **só os seis nomes do enum, sem glosa/definição/tooltip** — o revisor classifica pelo nome da categoria, sem ajuda textual na tela. Deixa de ser Open Question técnica e passa a **`PEND-LOCAL-01`** (texto normativo da §25 — definição de cada categoria — é insumo externo, de responsabilidade do especialista do método). Nota de nomenclatura: `PEND-01` a `PEND-06` são um registro fechado e numerado na própria canônica (`piq-app-spec.md` §14) — inventar `PEND-07` ali seria estender um domínio canônico fechado por conta própria (`sdd.config.md` §7, a mesma disciplina de `OQ-13`/`OQ-17`/`OQ-18`). Por isso esta pendência é local a `app-aluno.spec.md`, com prefixo próprio que não colide com a numeração canônica. `app/revisao/fila.py::CLASSIFICACAO_ERRO` já implementa exatamente isso — enum com os seis nomes, nenhuma definição inventada — e `tests/app_aluno/test_classificacao_erro.py` audita que nenhuma glosa foi acrescentada no código nem na tela. Nenhuma mudança de código é necessária para fechar esta questão |
| `OQ-16` | Qual é a fórmula normativa exata de composição de `RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS` e `DESPESAS_NAO_MENSAIS_NORMALIZADAS` a partir das perguntas do Bloco 3? A canônica lista as três como *"derivadas pelo motor, nunca perguntadas"* (§11, Bloco 3, após `B3.S08`), mas não publica uma fórmula de composição em lugar único: renda vem de `RENDA_PRINCIPAL` (com qualidade CONFIRMADA/ESTIMADA/DESCONHECIDA e o caso especial "renda variável sem valor único"), possivelmente somada a `RENDA_RECORRENTE_ADICIONAL` (ficha REP, até 3 itens) — mas `RECURSOS_EXTRAORDINARIOS` (`B3.05`) usa explicitamente `ATAQUE_IMEDIATO_POTENCIAL`, "nunca renda recorrente", então não entra na soma. Despesa vem de 10 categorias fixas (`B3.D01`–`D10`, cada uma checklist com fichas REP por item marcado) mais `B3.D11` (não listada) mais `DESPESAS_NAO_MENSAIS` (ficha REP, precisa de normalização anual→mensal, daí o nome). `engine/diagnostico.py` confirma que o motor **lê** essas três variáveis prontas como campo de `EstadoFinanceiro` — não as deriva de subcomponentes; a agregação, se existir, é trabalho de quem monta o estado, não do motor | Sem a fórmula, `app/montagem/estado.py::montar_estado_financeiro` (T-51) não tem como preencher três dos treze campos de `EstadoFinanceiro` a partir da coleta real — hoje ficam como parâmetro externo (lacuna documentada, nunca inventada). Como envolve juízo sobre qualidade de dado (estimado vs. confirmado), tratamento de renda variável, e o que conta como "recorrente" vs. "extraordinário" vs. "potencial", é decisão metodológica do especialista do método, não inferência de engenharia — errar a composição produziria uma capacidade de ataque incorreta sem que ninguém perceba, porque o motor confia no valor recebido | `respondida` — decisão do usuário, três fórmulas fechadas: **(1) `RENDA_TOTAL_RECORRENTE` = `RENDA_PRINCIPAL` + soma de todas as fichas REP de `RENDA_RECORRENTE_ADICIONAL` (`B3.03A-C`)** — lista aberta, sem limite de quantidade (correção de registro: uma resposta anterior citou "até 3 itens", número que não consta da canônica; ver `OQ-19`). `RECURSOS_EXTRAORDINARIOS` (`B3.05`) e a renda extra potencial (`B3.06`) ficam fora por definição — a própria canônica já afirma que o primeiro "nunca" é renda recorrente, e o segundo é potencial, não realizado. Qualidade do dado (`CONFIRMADA`/`ESTIMADA`/`DESCONHECIDA`) é **metadado, não filtro**: `CONFIRMADA` e `ESTIMADA` entram na soma com o mesmo valor informado — a qualidade pode ser exibida na tela de revisão, mas não desconta nem pondera o valor (nenhum parâmetro `P_*` novo). `DESCONHECIDA` (renda variável sem valor único) não soma um número: o campo correspondente de `EstadoFinanceiro` permanece `DESCONHECIDO`, nunca estimado por conta própria. **(2) `DESPESAS_OPERACIONAIS_ATUAIS`** = soma de todos os valores das fichas REP de `B3.D01` a `B3.D11` (as 10 categorias fixas mais a categoria "não listada") — as despesas não-mensais (`B3.NM*`) ficam de fora desta variável. **(3) `DESPESAS_NAO_MENSAIS_NORMALIZADAS`** = (soma dos valores anuais de todas as fichas REP de `B3.NM02A-D` **cuja `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` (B3.NM02D) não seja `Sim`**) / 12 — a normalização anual→mensal que o próprio nome da variável indica, com a exclusão de dupla contagem que o próprio registro nomeia (`salto_consequencia` de `B3.NM02D`: "Sim → não normalizar novamente"). **Correção de registro, decisão do usuário:** a primeira resposta desta pergunta fechou a fórmula como "soma de todas as fichas / 12", sem a exclusão — implementada assim por `T-103` e depois corrigida por uma tarefa nova (`T-107`) ao constatar o risco de inflar a despesa do aluno quando o mesmo valor já está embutido em outra categoria mensal informada. `TALVEZ`/`NAO_SEI` em `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` entra normalmente na soma (trata como não confirmada a duplicidade — só exclusão explícita por `Sim`). As três fórmulas são a especificação normativa que `app/montagem/estado.py::montar_estado_financeiro` (`T-51`/`T-103`) implementa |
| `OQ-19` | `collection/registros/bloco-03.yaml` (`T-17`) transcreveu `B3.03A-C` (renda adicional) e `B3.NM02A-D` (despesa não-mensal) com `escopo_repeticao: NENHUM`, mas a canônica as chama explicitamente de "ficha REP" (§11, linhas 1128, 1142, 1156, 1569, 1582, 1596, 1611: "Renda adicional — ficha REP", "Despesa não mensal — ficha REP") e o dicionário de variáveis (§11, linhas 5065-5066, 5099, 5119, 4925, 4944) marca `RENDA_RECORRENTE_ADICIONAL`, `TIPO_DESPESA_NAO_MENSAL`, `VALOR_DESPESA_NAO_MENSAL`, `FREQUENCIA_DESPESA_NAO_MENSAL` e `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` como `REP` na coluna "única/REP". `RENDA_RECORRENTE_ADICIONAL (item)` (linha 1153) usa a mesma notação "(item)" de variável por-ficha que outras variáveis `REP` reais usam. `EscopoRepeticao` (`collection/registro.py`) é domínio fechado de seis membros — `NENHUM`, `DIVIDA_ID`, `VINCULO_ID`, `MARGEM_ID`, `ITEM_DESPESA`, `ACAO_ID` — nenhum deles cobre "item de renda adicional" nem "item de despesa não-mensal". Diferente de `MARGEM_ID` (a canônica nomeia explicitamente "SYS: MARGEM_ID por ficha", linha 1785), a canônica **não nomeia** um identificador de sistema para as fichas de `B3.03A-C` nem de `B3.NM02A-D` — não há domínio publicado a transcrever para o nome do novo escopo, só a certeza de que a repetição existe. Descoberto durante a tentativa de implementação de `T-103` (fórmula de `OQ-16`): o agente confirmou por leitura de `collection/registro.py`, `collection/respostas.py` e `collection/registros/bloco-03.yaml` que **nenhum mecanismo do código hoje permite ler mais de um item de renda adicional ou de despesa não-mensal por caso** — `RespostasCaso.valores_do_escopo` exige um `EscopoRepeticao` real, e nenhum dos seis membros existentes se aplica; só `respostas.valor(...)` (valor único) está disponível para essas variáveis hoje. **Correção de registro:** a resposta de `OQ-16` citou "até 3 itens" para renda adicional — checado agora contra `specs/piq-app-spec.md` por busca textual, esse limite **não existe na canônica**; foi uma imprecisão introduzida na resposta anterior, não um dado normativo. A canônica não publica limite de quantidade para nenhuma ficha REP, incluindo as cinco já implementadas (dívida, vínculo, margem, despesa, ação) — todas são listas abertas em código hoje | A fórmula de `RENDA_TOTAL_RECORRENTE` (`OQ-16`, respondida) exige somar as fichas de `RENDA_RECORRENTE_ADICIONAL`, e `DESPESAS_NAO_MENSAIS_NORMALIZADAS` exige somar "todas as fichas" de `B3.NM02B` antes de dividir por 12 — nenhuma das duas é possível hoje sem inventar um mecanismo de repetição que nem o registro nem `collection/registro.py` declaram. Decidir sozinho entre "adicionar novos membros a `EscopoRepeticao` mais corrigir o YAML" ou "tratar como não-repetível na prática e a canônica está desatualizada" seria decisão de estrutura de dado/metodologia, exatamente o que `sdd.config.md` §6 proíbe implementar sem registrar. `T-103` ficou `[ ] pendente`, sem nenhuma linha de código alterada — o agente parou e reportou em vez de escolher um caminho | `respondida` — **dois novos membros em `EscopoRepeticao`: `RENDA_ADICIONAL_ID` e `DESPESA_NAO_MENSAL_ID`**, um por família de ficha, seguindo exatamente o padrão já usado pelos cinco membros existentes (`collection/repeticao.py::PREFIXO_POR_ESCOPO` — cada escopo tem um prefixo de identificador estável e nunca reaproveitado, ex. `D001` para dívida, `M001` para margem). Decisão do usuário. Sem limite de quantidade codificado — lista aberta, mesmo tratamento das cinco fichas REP já implementadas, nenhuma das quais tem limite fixo hoje. `collection/registros/bloco-03.yaml` (`B3.03A-C`, `B3.NM02A-D`) passa a declarar `escopo_repeticao: RENDA_ADICIONAL_ID`/`DESPESA_NAO_MENSAL_ID` em vez de `NENHUM`. Consequência para `T-103`: `RespostasCaso.valores_do_escopo` passa a funcionar para essas duas variáveis exatamente como já funciona para `DIVIDA_ID`/`MARGEM_ID`/etc — a fórmula de `OQ-16` deixa de estar bloqueada |
| `OQ-17` | Onde `ATAQUE_IMEDIATO_RECOMENDADO` e `RESERVA_MOBILIZAVEL` vivem no contrato do motor? A canônica cita `ATAQUE_IMEDIATO_RECOMENDADO` como condição de exibição de `B10.C01` (linha 4236: *"Condição de exibição: `ATAQUE_IMEDIATO_RECOMENDADO > 0`"*) e como "Uso pelo motor" de `RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` (linha 1995) e de `ATAQUE_IMEDIATO_POTENCIAL`/`RECOMENDADO` como "derivados pelo motor" (linha 2614) — mas nenhum dos dois é campo de `EstadoFinanceiro`, `Diagnostico` nem `SnapshotOrdem` hoje (`grep` em todo `engine/*.py` não encontra nenhuma ocorrência), e nenhum dos dois tem linha no dicionário de variáveis da §11: só `ATAQUE_IMEDIATO_APROVADO` (a resposta gravada de `B10.C01`, linha 4879) está lá | Sem o campo, `app/casos/confirmacao_ataque.py` (`T-77`) não tem como ler "o Bloco 10 é alcançável" por leitura de campo, como `RF-18`/`AC-22` exigem — e `T-78` (validação `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO`) também depende do mesmo campo ausente. É a mesma classe de lacuna de `OQ-13` (identificador citado só em condição de exibição, sem entrada no dicionário de variáveis), mas sobre um campo agregado do motor, não um domínio de coleta — decisão do slug `motor-calculo`, não desta feature: `engine/` está congelado, e derivar o valor na aplicação a partir de outros campos violaria a Lei nº 3 (a aplicação não calcula) | `respondida` — **os dois campos entram como campos extras de `Diagnostico`**: `RESERVA_MOBILIZAVEL: Dinheiro` e `ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro`. Decisão do usuário, apoiada em precedente já existente no próprio `engine/diagnostico.py`: `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `RISCO_RECAIDA`, `RISCO_COMPORTAMENTAL_GERAL` e `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` já foram adicionados como "campos comportamentais adicionais" — extras ao bloco literal do plano, num comentário separado, exatamente para atender consumidores futuros sem alterar o contrato de `SnapshotOrdem` (que declara um único campo `diagnostico: Diagnostico`, não uma tupla). Os dois novos campos seguem o mesmo padrão, no mesmo bloco de extras. É a **quarta exceção ao congelamento de `engine/`** (junto com `ACAO_ID`/`TIPO_ACAO` de `OQ-10`, a derivação de `OQ-14`, e o tipo opcional de `OQ-15`) — todas do slug `motor-calculo`, nenhuma desta feature. Consequência para `app-aluno`: `T-77` (`app/casos/confirmacao_ataque.py`) e `T-78` (validação `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO`) passam a ler `caso.snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` por nome de campo — leitura direta, nenhum cálculo do lado da aplicação (Lei nº 3 preservada) |
| `OQ-18` | Qual campo de `EstadoFinanceiro`/`Divida` está pendente quando o Gate 1 bloqueia uma dívida por informação? `RF-27` cita, como exemplo canônico de reabertura, exatamente `B5.B03`/`B5.D01A` — mas `engine.gates.AcaoRequerida` (e `ResultadoGates`) não têm nenhum campo que aponte qual `RegistroPergunta.ID` ficou pendente: só `DIVIDA_ID`, `descricao` (texto livre, parsing proibido desde `RF-33`/T-74), `gate_origem`, `prioridade_excepcional`. Confirmado também que `engine/gates.py::aplicar_gate_1_informacao` hoje devolve `acao=None` nos dois ramos de bloqueio (linhas 204 e 221) — o Gate 1 ainda não emite nenhuma `AcaoRequerida`, então esta lacuna se soma à de `OQ-10`/`OQ-14` (Gate 1 emitir ação), não a substitui | Sem o campo, `app/casos/reabertura.py::campo_para_reabertura_informacao` (`T-85`) não tem como saber que pergunta reabrir a partir de uma `AcaoRequerida` real — a implementação levanta erro nomeado em vez de inventar, como as demais dependências externas desta família (`OQ-13`, `OQ-14`). É decisão do slug `motor-calculo`: qual novo campo (ex.: `RegistroPergunta.ID` pendente, ou `VARIAVEL_GRAVADA` da variável desconhecida) `AcaoRequerida` precisa carregar para o Gate 1 expressar isso sem prosa | `respondida` — **novo campo `CAMPO_PENDENTE` em `AcaoRequerida`, domínio fechado `Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]`**. Decisão do usuário. Justificativa: os dois ramos de bloqueio de `aplicar_gate_1_informacao` (`engine/gates.py:191` e `:207`) reduzem a exatamente duas causas — `STATUS_DIVIDA == QUITADA_A_CONFIRMAR`, ou `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` dentro de `compor_VALOR_RELEVANTE_PARA_QUITACAO` (`engine/valor_quitacao.py:143`, chamado quando não há quitação vigente confirmada). O campo nomeia o **campo de `Divida` do próprio contrato do motor**, nunca um `RegistroPergunta.ID` de coleta — preserva a mesma fronteira que já separa `engine/` de `collection/` (o motor não conhece pergunta, só variável de domínio). Quem traduz `CAMPO_PENDENTE` para a pergunta a reabrir é a aplicação: `app/casos/reabertura.py::campo_para_reabertura_informacao` (`T-85`) ganha uma tabela própria, pequena e fechada, mapeando `STATUS_DIVIDA → B5.D01A` e `SALDO_DEVEDOR_ATUAL → B5.B03` (os dois exemplos que o próprio `RF-27` já cita) — mapeamento de aplicação, não do motor. É a **quinta exceção ao congelamento de `engine/`** (junto com `OQ-10`, `OQ-14`, `OQ-15`, `OQ-17`), toda pelo slug `motor-calculo` |

### Rodada 2 (2026-09-07) — fatia 2A

> **Nenhuma destas é decidida nesta spec.** As de decisão técnica nossa precisam
> ser respondidas no plano; as bloqueadas por terceiro são questões do slug
> `motor-calculo`, registradas aqui porque é aqui que passaram a bloquear
> trabalho concreto. **`OQ-20`, `OQ-21`, `OQ-22` e `OQ-23` são pré-requisito da
> implementação da fatia 2A** — `OQ-22` só na parte que toca `B4.03A`; a parte de
> `B3.05C` é 2B.
>
> **Nota de numeração.** A série local deste slug segue contígua a partir de
> `OQ-20` (§10 encerrava em `OQ-19`). As questões da segunda tabela pertencem à
> série do slug `motor-calculo` e são citadas com o prefixo
> **`motor-calculo:`** para que os dois espaços de numeração nunca se confundam
> — `motor-calculo:OQ-26` não é, e nunca será, uma `OQ-26` deste arquivo.

#### Decisão técnica nossa (spec/plano, sem o especialista)

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-20` | Ampliar a allowlist de `AC-41` com `engine.estado.RESERVA_EXISTE` e `engine.estado.DISPOSICAO_USO_RESERVA`? Os dois são enums que **tipam campos de `EstadoFinanceiro`** (`engine/estado.py:511`, `:513`) e caem no mesmo Critério A já aplicado quatro vezes (`TIPO_DIVIDA`/T-49, os 8 do Bloco 2/T-50, `TIPO_RENDA`/T-51, `Divida`) — *"sem liberá-lo é impossível montar um `EstadoFinanceiro` tipado fora de `engine/`"*. Sub-decisão já encaminhada por `RF-40`: liberar **só os dois** desta fatia, não os sete do levantamento | Sem a decisão, a fatia 2A não é implementável: preencher os campos com valores neutros já foi tentado e **reprovou** em `test_fronteira_import_engine.py`, com a edição revertida integralmente. Ampliar allowlist é mudar critério de aceite desta spec — `sdd.config.md` §6 não deixa isso a critério de quem implementa | `aberta` — **bloqueia a fatia 2A.** O levantamento com critério explicitado e precedente citado está em `RF-40` e no discovery §1.2; a decisão é do plano |
| `OQ-21` | Qual é o **texto** que o aluno lê quando `RESERVA_MOBILIZAVEL` é desconhecida? O comportamento está fixado (`RF-43`, `AC-70`: estado explícito de pendência, nunca `R$ 0,00`, nunca omissão), mas a redação não existe: `Q-02`/`Q-03` fixam texto canônico apenas para a ordem projetada, e a §13.1 só diz o que **não** fazer (*"não é convertido silenciosamente em zero"*) | O caminho é **novo e alcançável** a partir desta fatia — hoje o campo é sempre `0` e nenhuma tela de `app/` o trata. Texto ao aluno é conteúdo metodológico: inventá-lo aqui seria decidir redação sem nova versão da spec (`sdd.config.md` §6). Interage com `OQ-08` (respondida: avisar na hora), que já estabelece que o aluno é informado no momento, não só no relatório | `aberta` — **bloqueia a parte de apresentação de `RF-43`**, não a leitura (`RF-36` a `RF-39`). Insumo do especialista |
| `OQ-22` | Como o **registro** expressa os estados sem `valor_interno`? Dois casos, mesma natureza: **(a)** `B4.03A` tem três opções e a do meio — "Prefiro decidir somente depois de ver a análise." (`bloco-04.yaml:154`) — não tem `valor_interno` **nem** `admite_nao_sei`, um terceiro estado sem representação; **(b)** `B3.05C` (`JANELA_RECURSO_EXTRAORDINARIO`) tem `valor_interno: null` nas **cinco** opções (`bloco-03.yaml:284-289`) enquanto o enum tem cinco membros (`ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI`). Preencher o `valor_interno` no YAML, no padrão de `B3.05D` (que já tem)? | É a mesma classe de lacuna de registro que `OQ-19` resolveu para `escopo_repeticao`, agora em `valor_interno`. A alternativa — traduzir rótulo em português dentro do código de `app/` — é proibida por `AC-37`, e `sdd.config.md` §6 exige que nova versão do questionário seja **edição de registro, não reescrita de código**. Interage com `motor-calculo:OQ-25` (aberta), que perguntou se "decidir depois" e "não sei" colapsam. Errar (b) não gera erro de tipo: `ATE_30D` é o único membro que a §13.3 qualifica como "momento atual" — produziria um número silenciosamente errado | Item **(b) `resolvido` (2026-09-30)** — `T-208` preencheu o `valor_interno` de `B3.05C` com `ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI`. Item (a): `aberta` — o item **(a) bloqueia a fatia 2A**; o item (b) bloqueava 2B. Aritmeticamente a Regra 3 da §13.1 já obriga os dois estados de `B4.03A` a colapsarem em `DESCONHECIDO` (`EC-15`); o que falta decidir é se o registro passa a **distinguir** os dois para a devolutiva |
| `OQ-23` | Qual erro nomeado cobre "`B4.01` sem resposta" e como a coleta se recupera dele? `DINHEIRO_DISPONIVEL` é `Dinheiro` **puro** (`engine/estado.py:517`), sem união com desconhecido — não há `DESCONHECIDO` a entregar. `B4.01` é `[OBR]` e condiciona `B4.01A`, então `NAO` em `B4.01` é o caso legítimo de zero (`AC-58`); mas `B4.01 = "Não sei ao certo"` (`valor_interno: NAO_SEI`, `bloco-04.yaml:18`) e a ausência das duas respostas não têm destino definido | Sem a decisão, o caminho de `EC-20` fica sem comportamento especificado, e a tentação é o zero silencioso — exatamente o que `sdd.config.md` §4 proíbe. O precedente existe e é próximo (`_renda_principal`, `app/montagem/estado.py:1021`: campo obrigatório `Dinheiro` cuja ausência levanta erro em vez de virar zero), mas reusar precedente é decisão, não dedução | `aberta` — **bloqueia a fatia 2A** na parte de `RF-38`/`EC-20`. Inclui decidir se o registro deveria impedir o par "`B4.01 = NAO_SEI` + `B4.01A` não exibida" na coleta, em vez de deixar o erro para a montagem |
| `OQ-24` | **`valores_do_escopo` não filtra por escopo.** `collection/respostas.py:114-128`: o corpo é `if nome_variavel == variavel and item_id != ""`, e a docstring admite que o parâmetro `escopo` *"não é usado para filtrar aqui"*. A separação entre escopos é feita hoje pelo **nome da variável**, não pelo escopo. Corrigir por filtro real de escopo, por nomes de variável distintos por família, ou por `item_id` prefixado (`PREFIXO_POR_ESCOPO`, `collection/repeticao.py:59-67`)? | Funcionou até hoje porque cada escopo usa nomes distintos. **`VALOR_ESTIMADO_ATIVO` é gravado em quatro lugares** de `bloco-04.yaml` (`:222`, `:363`, `:570`, `:833`), `SALDO_PASSIVO_VINCULADO` em três, `CUSTOS_ESTIMADOS_DESMOBILIZACAO` em três — ler item sem corrigir isso produz **dupla contagem**, que a §13.8 veda por escrito (*"origem econômica única"*). Não é detalhe de implementação: é a diferença entre somar o patrimônio certo e somá-lo três vezes. A correção é em `collection/` e afeta os cinco escopos já em uso — exige não-regressão em renda adicional e despesa não-mensal | **Tarefa técnica (2026-09-30)** — não precisa de especialista: filtro real por escopo em `valores_do_escopo`. Continua pré-requisito de 2B e 2C (e, por 2B, de `RF-98`) e precisa estar feita **antes de qualquer linha de leitura de item**; **não bloqueia a fatia 2A** (`AC-71`) |
| `OQ-25` | Uma coleção `ativos` é alimentada por **três famílias de ficha** — imóvel (`B4.I*`), veículo (`B4.V*`) e outro ativo (`B4.O*`, `bloco-04.yaml:315-960`) —, cada uma com perguntas e nomes próprios. Um escopo de repetição por família (três, mais um para investimento) ou um só para "ativo"? Todo o Bloco 4 está hoje com `escopo_repeticao: NENHUM`, e nenhum dos oito membros de `EscopoRepeticao` cobre essas famílias | Decide `PREFIXO_POR_ESCOPO` e a forma da leitura. Nenhuma leitura existente deste slug lida com "três famílias de ficha alimentando uma coleção só". A escala é maior que a de `OQ-19`, que precisou de dois membros para duas famílias | `aberta` — **não bloqueia 2A nem 2B.** Bloqueia 2C, que já está bloqueada por `motor-calculo:OQ-26`/`OQ-27`; não urge. Encaminhamento provável: um membro por família, seguindo o precedente de `OQ-19` |

### Rodada 3 (2026-09-14) — protótipo validado e máscara de entrada

| ID | Pergunta | O que bloqueia | Status |
| --- | --- | --- | --- |
| `OQ-26` | As fontes do protótipo (Atkinson Hyperlegible e Source Serif 4) são carregadas do Google Fonts. Vendorizar os arquivos em `app/http/estaticos/`, ou declarar pilha de fallback e aceitar a degradação? Atkinson Hyperlegible foi desenhada para baixa visão — trocá-la por fallback **não é neutro** para a persona | Se o piloto rodar em rede restrita, a fonte não carrega e a tipografia validada com os stakeholders não é a que o aluno vê. Vendorizar acrescenta arquivo estático (não é dependência de pacote), mas é decisão de licença e de peso | `aberta` — **não bloqueia** a implementação; bloqueia a fidelidade visual no piloto. Encaminhamento provável: vendorizar, por causa da baixa visão |
| `OQ-27` | O modo escuro do protótipo (blocos `prefers-color-scheme` e `[data-theme]`) é requisito do piloto ou conveniência de demonstração? | Decide se o contraste WCAG 2.1 AA precisa ser auditado em **dois** temas ou em um. `test_acessibilidade_coleta.py` recalcula contraste a partir de hex literais do CSS — dois temas dobram o que precisa ser auditado | `aberta` — **não bloqueia** a coleta; bloqueia o fechamento do checklist de acessibilidade |
| `OQ-28` | O caminho `POST` que devolve HTML permanece indefinidamente, ou é removido depois do piloto? | `RF-49`/`EC-21` exigiam que ele existisse. A pergunta era de ciclo de vida: mantê-lo custava dois formatos de resposta na mesma rota; removê-lo mata o funcionamento sem JavaScript | `respondida` (2026-09-15, T-144) — **removido**. A migração para React tornou a resposta HTML inalcançável: nenhuma tela a consome, e mantê-la significaria manter templates que ninguém renderiza. O custo real está em `EC-21`, agora transferido para `OQ-29` |
| `OQ-29` | A aplicação deixou de funcionar sem JavaScript (`RF-49`/`EC-21`). Isso é aceitável para a persona do piloto, ou o caminho nativo precisa voltar em alguma forma? | Uma SPA React não grava resposta sem JS executando. `EC-21` dizia que a máscara é conveniência, nunca condição de gravação — hoje o app inteiro é condição. Para um aluno em rede restrita, celular antigo ou com JS bloqueado, a coleta simplesmente não abre | `respondida` (2026-09-17, T-145) — **aceitável**. Decisão do especialista: "a maior parte será preenchida no computador, isso não é uma preocupação". `RF-49` e `EC-21` ficam **revogados** para este piloto; a interface é React e exige JavaScript. Reabrir se aparecer aluno real afetado |

### Rodada 5 (2026-09-17) — navegação fiel ao protótipo

| ID | Pergunta | O que bloqueia | Status |
| --- | --- | --- | --- |
| `OQ-30` | **Qual é o texto do localizador (`.where`) na tela de pergunta?** O protótipo diz **"Dívida 3 · pergunta 4 de 12"** (linha 323), mas o payload de `serializar_pergunta` tem `bloco` e `total_pendencias` e **não** tem a posição da pergunta dentro da ficha. Três saídas: **(1)** acrescentar `posicao`/`total_na_ficha` ao serializador — mais fiel, mexe no payload de todas as perguntas; **(2)** usar o que já existe, *"Bloco 5 · 12 pendências"* — zero backend, menos fiel, e fala a linguagem do questionário, não a do aluno; **(3)** o cliente derivar a posição da lista de campos da ficha — só funciona nas telas de ficha repetível, e reintroduz no cliente uma contagem que é do servidor | O localizador é metade do `.top` — é ele que diz ao aluno *onde ele está* e quanto falta, e é parte do que `RF-57` exige. Sem decisão, a tela de pergunta sai com um localizador inventado, que é exatamente o tipo de decisão silenciosa que produziu esta rodada de retrabalho | `respondida` (2026-09-17) — **saída (1)**, fiel ao protótipo. Decisão do especialista: o serializador passa a expor `posicao` e `total_na_ficha`, e o localizador diz *"Dívida 3 · pergunta 4 de 12"*. Formalizado em `RF-63`/`AC-92` |

| `OQ-31` | **A tela "Meu progresso" deve marcar cada uma das cinco partes como concluída?** O protótipo (linha ~278) mostra "Feito"/"Agora" por parte, mas isso exige **progresso por bloco**, que nenhuma rota expõe. Derivá-lo no cliente é impossível sem ele contar perguntas que não conhece (`RF-45`/`RF-05`), e a tentativa feita em `T-150` produziu dois erros reais: comparar `respondidas` (dinâmico, 172 com três dívidas) contra os totais estáticos dos blocos (195) exibia dois números incoerentes na mesma tela, e marcava "Seu compromisso" como feita quando o aluno respondia 16 campos de **dívida**. Saídas: **(1)** `/inicio` passar a devolver `progresso_por_bloco`; **(2)** manter só o total geral, como está hoje | O protótipo prometia orientação por parte, e hoje a tela entrega só o total. Não é bloqueio funcional — o aluno sabe quanto falta e retoma de onde parou —, mas é menos do que foi validado com os stakeholders | `aberta` — **não bloqueia** nada. Enquanto estiver aberta vale a saída **(2)**: a tela mostra o total do servidor e as cinco partes como mapa do caminho, sem afirmar progresso que ninguém calculou. Encaminhamento provável: (1), porque a contagem por bloco é do servidor por natureza |
| `OQ-32` | **A repaginação visual da Rodada 8 precisa ser validada com stakeholders antes do piloto?** O protótipo original `PIQ Meu Plano` passou por validação; a camada de acabamento (`RF-72`–`RF-77`) foi aprovada pelo especialista em 2026-09-19 a partir de um protótipo de comparação, mas **não** foi vista por aluno real. Saídas: **(1)** validar com um aluno antes de abrir o piloto; **(2)** abrir o piloto e tratar a repaginação como hipótese a medir no uso | A camada é aditiva e não altera nenhum sinal validado (`RF-78`), então o risco de regressão é baixo; o que está em aberto é se ela **entrega** a percepção pretendida, que só uso real mede | `aberta` — **não bloqueia** a implementação. Encaminhamento provável: (2), porque a mudança não toca fluxo nem redação, e o piloto já tem revisão humana em 100% dos planos |

#### Bloqueadas por terceiro (slug `motor-calculo` / especialista do método)

Não são questões novas — são as daquele slug, registradas aqui porque é aqui que
passaram a bloquear trabalho concreto.

| ID (naquele slug) | Pergunta | O que bloqueia aqui | Status |
| --- | --- | --- | --- |
| `motor-calculo:OQ-26` | Qual é a regra de derivação de `CLASSIFICACAO_MOBILIZACAO`? | **Fatia 2C inteira** (`investimentos` e `ativos`). Item inconstruível: campo obrigatório sem default (`engine/estado.py:369`, `:392`), derivação proibida e auditada por AST (`AC-67`), pergunta proibida (`piq-app-spec.md:2614`) | `aberta` — **bloqueia 2C** |
| `motor-calculo:OQ-27` | Qual é a fórmula de `VALOR_LIQUIDO_REALIZAVEL` / `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`? | Idem, e **independente de `motor-calculo:OQ-26`**: mesmo que aquela fosse respondida amanhã, os itens seguiriam inconstruíveis. **As duas precisam estar respondidas — responder só uma não destrava** | `aberta` — **bloqueia 2C** |
| `motor-calculo:OQ-29` | Qual é a fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`? | `ATAQUE_IMEDIATO_RECOMENDADO` segue `dinheiro(0)` como placeholder explícito (`engine/diagnostico.py:845-850`), logo `T-77`/`T-78`/`T-79` (Bloco 10) continuam pendentes — agora por esta questão, não mais por `OQ-17` deste slug | `aberta` — **não bloqueia 2A** (que não promete Bloco 10); bloqueia `T-77`/`T-78`/`T-79` |
| `motor-calculo:OQ-25` | "Prefiro decidir depois" e "não sei" colapsam num único estado? | Interage com `OQ-22(a)` deste slug. Aritmeticamente a §13.1 Regra 3 já os colapsa em `DESCONHECIDA`; o que a resposta muda é se a **devolutiva** precisa distingui-los | `aberta` — **não bloqueia 2A**: `EC-15` fixa o colapso no campo entregue ao motor, que é o que a §13.1 exige |

### Rodada 9 (2026-09-30) — o que as decisões `DE-01` a `DE-08` não fixam

> **Numeração.** Começa em `OQ-52` porque `OQ-46` a `OQ-51` já existem no
> discovery deste slug (coleta agrupada por categoria). As questões de motor
> de `DE-02` estão em `specs/motor-calculo.spec.md` (`OQ-46` a `OQ-50`
> daquele slug).
>
> **Todas resolvidas em 2026-09-30.** O responsável do produto decidiu que
> nenhuma volta ao especialista: cada resolução deriva dos princípios que o
> próprio especialista escreveu nas observações (prudência, sem dupla
> contagem, não bloquear, o revisor homologa) e não altera metodologia além de
> `DE-01` a `DE-08`. As propostas originais ficam registradas abaixo para
> rastreio. Na mesma data: **`OQ-22`(b) está resolvida** (`T-208` preencheu o
> `valor_interno` de `B3.05C` com `ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI`) e
> **`OQ-24` passa a ser tarefa técnica** (filtro real por escopo em
> `valores_do_escopo`), sem especialista.

| ID | Pergunta | O que bloqueia | Status |
| --- | --- | --- | --- |
| `OQ-52` | `DE-03`, `DE-06` e `DE-07` alteram registros da §11 (pergunta de situação do seguro em `B5.D05A`; campos de bruto/tipo/valor final em `B7.13A`; domínio de três níveis de `FONTE_DADO`; pergunta de tipo de proposta e condições de `B7.07`–`B7.09`). Entram na canônica como nova versão (v1.0.3) antes de editar os YAML, ou basta o registro desta Rodada 9? | Edição de `collection/registros/*.yaml` para `RF-81`–`RF-85`, `RF-91`, `RF-94` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-03`/`DE-06`/`DE-07` e `sdd.config.md` §6: **sim, v1.0.3 da canônica**, erratas `E-11` a `E-15` no Registro de alterações de `piq-app-spec.md` |
| `OQ-53` | Onde se calcula a Sobra do mês da `B3.C00` (`DE-01`)? A tela ocorre **antes** do Bloco 6 — não há snapshot —, e `RF-34` proíbe cálculo na aplicação | `RF-79`, `AC-117`–`AC-119` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-01`/obs de `q1_2`: a sobra é **agregação de entrada** (renda − despesas informadas), do mesmo tipo que a montagem já faz (`OQ-16`) — não é cálculo do motor, e `RF-34` não se aplica. Exibida rotulada "antes das dívidas" (`RF-79`) |
| `OQ-54` | Seguro (`DE-03`): (a) situação respondida "Não sei" — o que acontece? (b) na situação "cobrado mensalmente à parte", o valor entra como desembolso da própria dívida ou como despesa do orçamento do Bloco 3? | `RF-81`, `AC-122` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-03`/`DE-06`/obs de `q3_1`: (a) "Não sei" não soma em lugar nenhum e o dado fica registrado como "não informado" (revisto no mesmo dia: não é "Pendente de confirmação", que em `DE-06` é informação verbal); (b) cobrado à parte é despesa mensal **da dívida** (custo da operação), não do Bloco 3 (`RF-81`, `AC-122`, `AC-155`). **Nota (2026-09-30, decisão do responsável do produto sobre o risco `R9-1` do plano):** sem campo de motor para custo mensal por dívida, a montagem entrega esse valor somado às despesas mensais operacionais (uma vez por dívida, nunca à parcela, fora da `B3.C00`) — `T-232` |
| `OQ-55` | Desconto (`DE-03`): (a) onde se calcula o valor líquido — pela Lei nº 3, é motor, o que faz disto uma mudança de `motor-calculo` não especificada aqui; (b) qual tolerância define "R$ e % compatíveis"? | `RF-83`, `RF-84`, `AC-125`–`AC-129` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-03`/obs de `q3_2`: (a) valor líquido é agregação de entrada, na montagem; (b) revisto no mesmo dia: comparação **ao centavo** — desconto em R$ contra bruto × % arredondado a R$ 0,01; diferença > R$ 0,01 é divergência (não usa a tolerância de `sdd.config.md` §5) (`RF-84`, `AC-129`) |
| `OQ-56` | Inventário (`DE-04`): (a) `B5.00` = "Não sei exatamente quantas" — há bloqueio? (b) fichas **acima** do declarado bloqueiam? Com que mensagem? (c) `B5.FIM02` = "Ainda falta pelo menos uma dívida" com contagem igual — bloqueia (como `DE-04`) ou gera plano provisório (como `AC-07`)? | `RF-86`, `RF-87`, `EC-32`, `EC-33`; compatibilidade com `RF-15`/`AC-07` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-04`/obs de `q4_1`: (a) `B5.00` desconhecido → completude é a confirmação em `B5.FIM01` ("Não, esta foi a última"); (b) revisto no mesmo dia, fiel a `q4_1` (igualdade): fichas acima do declarado → o sistema pede para atualizar `B5.00` (ação direta) e bloqueia o cálculo final até igualar; (c) o bloqueio de `DE-04` substitui o provisório de `RF-15` sempre que declarado ≠ cadastrado — nos demais casos `RF-15`/`AC-07` seguem (`RF-86`, `RF-87`, `AC-153`, `AC-154`) |
| `OQ-57` | Textos de `DE-04` além dos dois exemplos dados: singular ("Falta 1 ficha."), renda extra e vínculo consignável. E "renda extra" é `B3.03` (renda adicional recorrente) ou inclui `B3.05` (extraordinários)? | `RF-87`, `RF-88`, `AC-135` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-04`/obs de `q4_2`: textos no padrão "Você informou que possui X, mas ainda não cadastrou nenhum(a)"; "renda extra" = Sim em `B3.03` (renda recorrente adicional) (`RF-88`) |
| `OQ-58` | `DE-05` pede por vínculo a "renda líquida relevante para o cálculo"; a canônica coleta `RENDA_BRUTA_VINCULO` (`B3.S04`). Substitui, soma-se, ou é outro campo? | `RF-89`; forma do registro `B3.S04` | `resolvida` (2026-09-30, revista no mesmo dia) — decisão da equipe técnica com base em `DE-05`/obs de `q5_1`: mantém `RENDA_BRUTA_VINCULO` (base da margem); renda líquida por vínculo é **coletada** e usada em conferência — soma das líquidas × renda do Bloco 3, divergência sinalizada, sem dupla contagem e sem virar entrada do motor (`RF-89`, `AC-156`, `EC-41`) |
| `OQ-59` | Identificadores dos campos novos de `DE-05`: "existência de consignação" por vínculo e o campo da dívida consignada que aponta o `VINCULO_ID` | `RF-89`, `RF-90`, `AC-139` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-05`: nomes técnicos a critério do plano |
| `OQ-60` | Cartão consignado e cartão benefício são margens (`TIPO_MARGEM`), mas `TIPO_DIVIDA` não tem esses tipos — dívida de cartão descontada em folha também aponta para vínculo? | `RF-90` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-05`/obs de `q5_2`: **todo** contrato consignado, inclusive cartão consignado/benefício, aponta para o vínculo em que é descontado (`RF-90`, `AC-139`) |
| `OQ-61` | Nível de comprovação das opções não cobertas por `DE-06`: `B5.I02` "Uma combinação dessas fontes" e "Outra" (como saber se há documento associado?); `B8.15` "Simulação fornecida pela instituição", "Atendimento", "Correspondente", "Outra fonte" | `RF-91`, `AC-140`, `EC-36` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-06`/obs de `q6_1`: contracheque = Comprovado; "Uma combinação dessas fontes" = Informado pelo aluno (prudência); "Outra" = Informado pelo aluno, salvo documento associado. `B8.15` (complemento do mesmo dia): "Simulação fornecida pela instituição" = Comprovado; "Correspondente" e "Atendimento" = Pendente de confirmação (verbal) (`RF-91`, `AC-140`, `EC-36`) |
| `OQ-62` | Quais dados são **indispensáveis** (`DE-06`, `DE-08`)? | `RF-93`, `RF-97`, `AC-142`, `AC-149` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-06`/`DE-08`: indispensável = campo que o motor exige para calcular aquela dívida/estado (saldo, taxa, parcela/prazo, renda) — os mesmos cuja ausência já gera pendência hoje (`RF-93`). Taxa: "Você sabe a taxa?" (`B5.D01`, `T-283`) e periodicidade da taxa (`B5.D01B`, `T-287`) também são indispensáveis — sem a periodicidade a taxa não se interpreta; taxa estimada não pende (decisão do especialista, Rodrigo, confirmada em 2026-09-30) |
| `OQ-63` | "Reduz o grau de confiança" (`DE-06`) alimenta `CONFIABILIDADE_DADOS` do motor, ou é só sinalização por dado? | `RF-92`; se alimentar, é mudança de motor e de `piq-definicoes-engine.md` §5 (congelada) | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-06`: **não** alimenta `CONFIABILIDADE_DADOS` (seria mudança de motor não decidida); o nível fica registrado por dado e é exibido ao revisor e no plano (`RF-91`, `RF-92`) |
| `OQ-64` | Pendência em dado indispensável (`DE-06`) e falta de dado indispensável (`DE-08`): **impedem** o revisor de liberar o plano, ou só são apontadas? E "homologar" em `DE-08` é a liberação do revisor ou o teste de homologação? | `RF-93`, `RF-97`, `AC-142`, `AC-149` | `resolvida` (2026-09-30, revista no mesmo dia) — decisão da equipe técnica fiel a `q8_1` ("não pode ser homologado"): "homologar" = liberação pelo revisor na fila existente. O cálculo roda, mas a **liberação fica bloqueada** enquanto houver dado indispensável (`OQ-62`) em "Pendente de confirmação" ou ausente; o revisor vê a lista e só libera depois de confirmado/corrigido. Substitui a primeira resolução ("não bloqueia automaticamente") (`RF-93`, `RF-97`, `AC-142`, `AC-149`, `EC-40`) |
| `OQ-65` | Proposta (`DE-07`): (a) quais perguntas do Bloco 7 são "dados da quitação à vista"? (b) com "ambas", como registrar duas ofertas (hoje cada `PROPOSTA_*` é um campo só) e qual o motor compara? | `RF-94`, `AC-144`, `AC-145` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-07`/obs de `q7_1`: à vista = valor para quitação à vista + validade; "ambas" = coleta os dois conjuntos (`RF-94`, `AC-144`, `AC-145`). **Nota (2026-09-30, decisão do responsável do produto sobre o risco `R9-3` do plano):** à vista também mostra o desconto (`B7.13`–`B7.13E`) e a fonte (`B7.16`) — `T-242` |
| `OQ-66` | Os cinco itens de `DE-08` existem como campo do snapshot? "Custo total de juros" e "valor mensal destinado" não têm nome fixado nesta spec | `RF-96`, `AC-147` | `resolvida` (2026-09-30) — decisão da equipe técnica com base em `DE-08`: correspondência a critério do plano, usando campos existentes do `SnapshotOrdem` (`RF-96`) |
| `OQ-67` | Textos ao aluno que as decisões pedem e não redigem: orientação sobre seguro prestamista (apólice, cancelamento, restituição não garantida — `DE-03`), aviso de que em Férias/abono só o acréscimo conta (`DE-02`) e rótulo do cenário adicional (`DE-02`) | `RF-82`, `RF-98`, `AC-151`, `AC-152` (só a redação; o comportamento está fixado) | `resolvida` (2026-09-30) — decisão da equipe técnica: textos ao aluno são **decisão de produto** (responsável do produto), não do especialista; o plano propõe e o produto aprova (`RF-82`, `RF-98`) |
| `OQ-68` | De onde vem o **nome** do aluno no Painel de usuários (`RF-112`)? | Hoje só o e-mail é gravado (cadastro e compra Hotmart). Opções: pedir no cadastro, ler do webhook da Hotmart (comprador), ou cadastrar no futuro painel de administração | `respondida` (2026-10-02) — **do comprador no webhook da Hotmart** (`data.buyer.name`), gravado na conta no provisionamento; ver `RF-112` e `T-332` |
