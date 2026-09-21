# Spec — App do Aluno (coleta, plano e acompanhamento)

| Campo    | Valor                                                        |
| -------- | ------------------------------------------------------------ |
| Slug     | `app-aluno`                                                  |
| Status   | `rascunho`                                                   |
| Autor    | virtushold@gmail.com                                         |
| Data     | 2026-09-14 (Rodada 3 — protótipo validado e máscara · Rodada 2 — fatia 2A em 2026-09-07 · Rodada 1 em 2026-09-03) |
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
| `RF-57` | A navegação do aluno é **fluxo linear guiado**: uma tela por vez, com "‹ Voltar" e localizador no topo (`.top`) e a ação no rodapé fixo (`.acoes`, `position: sticky`). **Nunca** uma barra que ofereça todas as telas de uma vez | Protótipo `PIQ Meu Plano`, linhas 75–89 (`.top`/`.actions`) e `go()`, linha ~820 · `RF-50` | essencial |
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
| `RF-70` | Durante a coleta, o aluno alcança a **pergunta anterior e a seguinte** entre as que já respondeu, sem passar pela lista. Errar a pergunta anterior e perceber na seguinte é o caso mais comum de correção, e mandá-lo à lista para isso é desproporcional | `RF-68` · relato de uso | importante |
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
| `EC-12` | Revisor reprova o relatório | O plano não é liberado, a reprovação é registrada com autor e data, o snapshot permanece intacto (append-only) e o caso vai para tratamento do operador. Nunca se edita o snapshot para "corrigir" |
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
| `OQ-22` | Como o **registro** expressa os estados sem `valor_interno`? Dois casos, mesma natureza: **(a)** `B4.03A` tem três opções e a do meio — "Prefiro decidir somente depois de ver a análise." (`bloco-04.yaml:154`) — não tem `valor_interno` **nem** `admite_nao_sei`, um terceiro estado sem representação; **(b)** `B3.05C` (`JANELA_RECURSO_EXTRAORDINARIO`) tem `valor_interno: null` nas **cinco** opções (`bloco-03.yaml:284-289`) enquanto o enum tem cinco membros (`ATE_30D`/`1_3M`/`4_6M`/`7_12M`/`NAO_SEI`). Preencher o `valor_interno` no YAML, no padrão de `B3.05D` (que já tem)? | É a mesma classe de lacuna de registro que `OQ-19` resolveu para `escopo_repeticao`, agora em `valor_interno`. A alternativa — traduzir rótulo em português dentro do código de `app/` — é proibida por `AC-37`, e `sdd.config.md` §6 exige que nova versão do questionário seja **edição de registro, não reescrita de código**. Interage com `motor-calculo:OQ-25` (aberta), que perguntou se "decidir depois" e "não sei" colapsam. Errar (b) não gera erro de tipo: `ATE_30D` é o único membro que a §13.3 qualifica como "momento atual" — produziria um número silenciosamente errado | `aberta` — o item **(a) bloqueia a fatia 2A**; o item **(b) bloqueia 2B**. Aritmeticamente a Regra 3 da §13.1 já obriga os dois estados de `B4.03A` a colapsarem em `DESCONHECIDO` (`EC-15`); o que falta decidir é se o registro passa a **distinguir** os dois para a devolutiva |
| `OQ-23` | Qual erro nomeado cobre "`B4.01` sem resposta" e como a coleta se recupera dele? `DINHEIRO_DISPONIVEL` é `Dinheiro` **puro** (`engine/estado.py:517`), sem união com desconhecido — não há `DESCONHECIDO` a entregar. `B4.01` é `[OBR]` e condiciona `B4.01A`, então `NAO` em `B4.01` é o caso legítimo de zero (`AC-58`); mas `B4.01 = "Não sei ao certo"` (`valor_interno: NAO_SEI`, `bloco-04.yaml:18`) e a ausência das duas respostas não têm destino definido | Sem a decisão, o caminho de `EC-20` fica sem comportamento especificado, e a tentação é o zero silencioso — exatamente o que `sdd.config.md` §4 proíbe. O precedente existe e é próximo (`_renda_principal`, `app/montagem/estado.py:1021`: campo obrigatório `Dinheiro` cuja ausência levanta erro em vez de virar zero), mas reusar precedente é decisão, não dedução | `aberta` — **bloqueia a fatia 2A** na parte de `RF-38`/`EC-20`. Inclui decidir se o registro deveria impedir o par "`B4.01 = NAO_SEI` + `B4.01A` não exibida" na coleta, em vez de deixar o erro para a montagem |
| `OQ-24` | **`valores_do_escopo` não filtra por escopo.** `collection/respostas.py:114-128`: o corpo é `if nome_variavel == variavel and item_id != ""`, e a docstring admite que o parâmetro `escopo` *"não é usado para filtrar aqui"*. A separação entre escopos é feita hoje pelo **nome da variável**, não pelo escopo. Corrigir por filtro real de escopo, por nomes de variável distintos por família, ou por `item_id` prefixado (`PREFIXO_POR_ESCOPO`, `collection/repeticao.py:59-67`)? | Funcionou até hoje porque cada escopo usa nomes distintos. **`VALOR_ESTIMADO_ATIVO` é gravado em quatro lugares** de `bloco-04.yaml` (`:222`, `:363`, `:570`, `:833`), `SALDO_PASSIVO_VINCULADO` em três, `CUSTOS_ESTIMADOS_DESMOBILIZACAO` em três — ler item sem corrigir isso produz **dupla contagem**, que a §13.8 veda por escrito (*"origem econômica única"*). Não é detalhe de implementação: é a diferença entre somar o patrimônio certo e somá-lo três vezes. A correção é em `collection/` e afeta os cinco escopos já em uso — exige não-regressão em renda adicional e despesa não-mensal | `aberta` — **não bloqueia a fatia 2A** (que não lê item nenhum; `AC-71` verifica isso). **Bloqueia 2B e 2C**, e precisa estar decidida **antes de qualquer linha de leitura de item** |
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
