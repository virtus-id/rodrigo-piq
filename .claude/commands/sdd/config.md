---
description: Preenche o sdd.config.md conversando com você — pergunta em linguagem simples, detecta o que dá, e escreve o arquivo com precisão técnica.
argument-hint: "[descrição do projeto em uma linha]"
---

# /sdd:config — Configurar o projeto, perguntando

Objetivo: deixar `sdd.config.md` preenchido e correto **sem o usuário editar
Markdown na mão**. É o único passo de setup, e pode ser rodado quantas vezes for
preciso — rodar de novo atualiza, não recomeça.

**Quem responde não precisa saber programar.** Este comando é feito para ser
seguido por alguém no ensino médio, sem experiência prévia, possivelmente
assistindo a um vídeo. Se uma pergunta exige saber o que é um framework para ser
respondida, a pergunta está errada — não a pessoa.

Contexto informado pelo usuário: **$ARGUMENTS**

> **Fora de escopo: stack.** Linguagem, framework, banco e bibliotecas são
> decisões de refinamento técnico e pertencem à seção `Tech Stack` do plano da
> feature, em `plans/`. Nunca pergunte sobre stack aqui, nem grave stack no
> config.

---

## Os três princípios

**1. Pergunta fácil, gravação detalhada.** São duas camadas diferentes e nunca
devem ser confundidas. Na superfície, a pessoa escolhe entre frases simples que
descrevem *efeitos no mundo real*. No arquivo, você grava a regra técnica
completa, precisa e rastreável que aquela escolha significa. Facilitar a pergunta
não empobrece o projeto — é você fazendo o trabalho pesado em vez de terceirizá-lo
para quem não tem como fazer.

**2. Não pergunte o que tem uma única resposta defensável.** Pergunta com uma
opção só não é escolha, é ruído. Decida, anuncie, e ofereça a correção.

**3. Opção derivada vale mais que opção genérica.** Antes de propor qualquer
convenção ou restrição, leia a spec do projeto e extraia dela. Uma opção que
nasce da spec a pessoa reconhece como sua; uma opção genérica ela aceita sem
entender, e isso não configura projeto nenhum.

---

## Como escrever as perguntas

**Vocabulário.** Zero jargão na pergunta e no rótulo da opção. Estão proibidos
sem tradução: *greenfield, lint, build, deploy, manifest, boilerplate, mock,
endpoint, hardcoded, snapshot, refatorar, stack*. Se o conceito é necessário,
descreva pelo efeito: "os comandos que conferem se o código não quebrou" em vez
de "lint e build".

**Toda descrição responde uma só pergunta: o que muda se eu escolher isso?**
Descrição não é definição de dicionário, é consequência. Compare:

| Ruim — define | Bom — mostra a consequência |
| --- | --- |
| "Projeto greenfield, sem código legado." | "Estou começando do zero. O robô vai poder propor a organização das pastas do jeito que achar melhor." |
| "Tolerância de ±R$ 0,05 em valores acumulados." | "Diferença de centavo por arredondamento pode passar. Mas se o método recomendado sair errado, o teste falha — nessas coisas não existe quase certo." |

**Frases curtas, uma ideia por frase.** Exemplo com número concreto sempre que
possível. Rótulo curto diz *a escolha*; descrição diz *o efeito*.

**Nunca deixe a pessoa diante de um campo em branco.** Toda pergunta chega com 2
a 4 opções prontas. Escrever a própria resposta é sempre possível, nunca
obrigatório.

**Teste antes de perguntar:** alguém de 15 anos consegue escolher sem perguntar
"o que é isso?". Se a pergunta precisa de mais de duas frases para ser entendida,
ela está mal formulada — quebre em duas, ou decida sozinho pelo princípio 2.

---

## Como expandir a resposta

**O que a pessoa clicou nunca é o que você grava.** O rótulo é a porta; o
conteúdo técnico é o cômodo. Exemplo real deste projeto:

| A pessoa escolheu | O que foi para o arquivo |
| --- | --- |
| "Nenhum número importante escondido no código" | **Zero parâmetro no código.** Nenhum dos 45 valores `P_*` da seção 8 pode ser escrito no código; o motor os lê em tempo de execução a partir de `parameters/`. Calibrável não autoriza o desenvolvedor a alterar. |
| "O robô não pode inventar dado que não tem" | **Não inventar dado.** Valor desconhecido vira `INFORMACAO_PENDENTE` e bloqueia o que depende dele — nunca uma estimativa silenciosa (gabarito `GAB-03`). |

Cada item gravado precisa de três coisas:

1. **A regra**, em uma frase imperativa — dá para apontar a linha que a viola.
2. **O porquê**, quando não for óbvio.
3. **A âncora**: ID de regra, número de seção da spec, gabarito ou requisito.

Se você não consegue expandir uma escolha em algo verificável e ancorado, a opção
estava vaga — o problema é a pergunta, não a resposta. Reescreva a opção.

**Seja generoso na gravação.** Melhor um config longo e específico do que um
enxuto e genérico: ele será lido por agentes, não por humanos apressados.

---

## Passo 0 — Abrir

Antes da primeira pergunta, diga em três linhas: o que vai acontecer, quantas
perguntas mais ou menos, e que **não existe resposta errada**, porque o comando
pode ser rodado de novo a qualquer momento. Isso destrava quem está respondendo
pela primeira vez — e, num vídeo, dá a abertura.

## Passo 1 — Levantar o terreno

Nunca pergunte o que o repositório já responde. Leia o que existir:

- `sdd.config.md` atual — **valores já preenchidos são o padrão de cada
  pergunta**, e a pessoa só confirma ou troca.
- Manifests (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `*.csproj`,
  `Gemfile`, `composer.json`, `Makefile`, `appsscript.json`) — de onde saem os
  comandos reais de instalação, conferência, testes e execução.
- Estrutura de pastas de primeiro e segundo nível.
- `git remote -v` e o nome da pasta — candidatos a repositório e nome do projeto.
- **Specs existentes em `specs/`** — a mina de onde saem as boas opções. Procure
  travas, invariantes, regras numeradas, valores proibidos no código, plataformas
  descartadas, obrigações de processo, gabaritos de homologação.
- 3 a 5 arquivos representativos do código, se houver.

## Passo 2 — Resolver o que não precisa ser perguntado

Aplique esta tabela **antes** de montar qualquer pergunta:

| Condição no repositório | Decida sozinho | Por que não perguntar |
| --- | --- | --- |
| Nenhum manifest encontrado | Comandos de conferência = `—` | Não há o que detectar; ainda não existe código |
| Manifest único, scripts sem ambiguidade | Comandos = os scripts reais | Você vai validá-los rodando no passo 4 |
| `git remote` existe | Repositório = a URL do remote | É fato, não preferência |
| Sem remote, mas há pasta | Repositório = caminho local, marcado como não versionado | Idem |
| Config já preenchido e repositório não mudou | Mantenha o valor | Rodar de novo não é recomeçar |

Depois **anuncie em bloco** o que foi decidido sem perguntar, uma linha por item,
com o motivo ao lado, em linguagem simples. Feche com uma única saída: *"Achou
algo errado aí? Me diga agora. Se estiver tudo bem, sigo para o que só você pode
decidir."*

## Passo 3 — Perguntar só o que sobrou

Use `AskUserQuestion`, no **máximo 4 perguntas por chamada**. Empacote as
perguntas pendentes na ordem abaixo — não force rodadas fixas: se sobraram cinco
perguntas, são duas chamadas.

À esquerda, o que perguntar em linguagem simples. À direita, o que a resposta
vira no arquivo.

| # | Pergunte assim | Grave assim |
| --- | --- | --- |
| 1 | Como você quer chamar esse projeto? — candidatos: nome da pasta, título da spec, nome no manifest | Campo **Projeto** |
| 2 | Qual dessas frases explica melhor o que ele faz? — 2 a 3 redações prontas tiradas da spec, do README ou de `$ARGUMENTS` | Campo **Descrição** |
| 3 | Você está começando do zero, ou já existe alguma coisa pronta? — do zero · já existe uma versão rodando em outro lugar, tipo uma planilha ou um piloto · já tem gente usando de verdade | `greenfield` · `em evolução` · `legado` |
| 4 | Já existem comandos para conferir se o código está certo? — **só pergunte se houver mais de uma resposta possível** | Bloco de comandos de verificação |
| 5 | Onde cada parte do projeto vai morar? — a estrutura existente, ou 2 propostas coerentes com o **assunto** do projeto, nunca com uma tecnologia presumida. Use `preview` para comparar as árvores lado a lado | Tabela de estrutura de pastas |
| 6 | O que o robô nunca pode fazer quando estiver escrevendo o código? (`multiSelect`) — cada opção é um efeito concreto, tirado de uma trava da spec | Convenções de código, cada uma com regra + âncora |
| 7 | Como a gente vai saber que o projeto está funcionando de verdade? (`multiSelect`) — gabaritos, invariantes, tolerâncias e rastreabilidade que a spec já define | Convenções de teste |
| 8 | O que esse projeto decidiu NÃO fazer? (`multiSelect`) — o que a spec proíbe, descarta ou obriga como processo | Restrições e não-objetivos |
| 9 | Os nomes dentro do código devem ser em português ou em inglês? — se a spec nomeia variáveis em português, ofereça pt-BR total como alternativa real e explique o efeito: traduzir cria um dicionário mental entre a spec e o código | Seção de idioma, com a justificativa da escolha |
| 10 | O que precisa estar pronto para uma tarefa poder ser considerada terminada? (`multiSelect`) — a lista padrão mais acréscimos derivados da spec | Definition of Done |

Em toda opção: marque `(detectado)` o que veio do repositório e `(recomendado)` a
sua sugestão, e ponha a recomendada em primeiro lugar.

## Passo 4 — Escrever e validar

1. Reescreva `sdd.config.md` preservando a estrutura de seções e a numeração
   existentes. Não invente seção nova nem reordene.
2. Aplique a expansão: grave a regra completa com âncora, nunca o rótulo clicado.
3. Substitua **todos** os placeholders. O que a pessoa não definiu vira `—`,
   nunca um placeholder e nunca um chute.
4. Crie `specs/`, `plans/` e `tasks/` se não existirem.
5. Rode cada comando declarado e confirme que existe. O que falhar por não
   existir volta a ser `—`, e você avisa.
6. **Rode a validação da CI**: nenhum trecho entre sinais de menor e maior
   iniciado por letra minúscula pode sobrar no arquivo — inclusive dentro de
   exemplos e comentários, onde é fácil escorregar.
7. **Cheque o `CLAUDE.md`.** Ele é carregado em toda sessão e vence o config na
   prática. Se alguma resposta contradisser uma regra dele — idioma, escopo,
   verificação — corrija a regra e reporte a correção. Duas verdades no
   repositório é o pior resultado possível deste comando.

## Passo 5 — Prestar contas

Em linguagem simples, como quem conta para alguém que não estava vendo a tela.
Quatro listas curtas e honestas:

- **Achei sozinho** — o que veio do repositório.
- **Decidi sem perguntar** — o que a tabela do passo 2 resolveu, e por quê.
- **Você decidiu** — o que veio das respostas, dizendo o que cada escolha virou
  na prática dentro do arquivo.
- **Ficou pendente** — o que ficou `—`, e o que precisa acontecer para destravar.

Feche dizendo qual é o próximo comando a rodar. Quem está aprendendo não sabe.

---

## Regras

- Nenhum placeholder sobrando no arquivo final.
- Nenhuma pergunta sobre stack, framework, linguagem ou biblioteca.
- Nenhuma pergunta com uma única resposta defensável.
- Nenhum jargão sem tradução em pergunta, rótulo ou descrição.
- Nenhuma pergunta sem opções prontas.
- O que é gravado é a regra técnica com âncora, nunca o texto do rótulo.
- Comando declarado é comando **verificado**. Não declare o que não rodou.
- Nunca apague um valor já preenchido sem a pessoa ter escolhido trocá-lo.
