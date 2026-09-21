# SDD Base — Kit Spec-Driven Development para Claude Code

Kit reutilizável para conduzir qualquer projeto pelo fluxo
**Discovery → Spec → Plan → Tasks → Code → Test → Review**, com subagentes e
slash commands do Claude Code.

**Agnóstico de stack.** Tudo que é específico do projeto vive em um único
arquivo: [`sdd.config.md`](sdd.config.md). Agentes e comandos nunca conhecem sua
stack — eles leem o config.

---

## Como usar em um projeto novo

```bash
# 1. Copie o kit para dentro do seu projeto
cp -r sdd-base/.claude       meu-projeto/
cp -r sdd-base/templates     meu-projeto/
cp -r sdd-base/specs         meu-projeto/
cp -r sdd-base/plans         meu-projeto/
cp -r sdd-base/tasks         meu-projeto/
cp    sdd-base/sdd.config.md meu-projeto/
cp    sdd-base/CLAUDE.md     meu-projeto/   # ou cole o conteúdo no CLAUDE.md existente

# opcional, se usa GitHub Actions
cp -r sdd-base/.github       meu-projeto/
```

No PowerShell:

```powershell
Copy-Item -Recurse sdd-base\.claude, sdd-base\templates, sdd-base\specs, sdd-base\plans, sdd-base\tasks -Destination meu-projeto\
Copy-Item sdd-base\sdd.config.md, sdd-base\CLAUDE.md -Destination meu-projeto\
```

Depois, dentro do projeto, rode:

```
/sdd:config  <descrição do projeto em uma linha>
```

Ele lê o repositório, detecta o que dá para detectar, **pergunta o resto em
opções** e escreve o `sdd.config.md` por você. **Esse é todo o setup.** Pode
rodar de novo quando quiser — ele atualiza em vez de recomeçar.

> **Stack não entra no config.** Linguagem, framework e bibliotecas são decisão
> de refinamento técnico e vivem na seção `Tech Stack` de
> `plans/<slug>.plan.md`, onde cada escolha se justifica contra um requisito.

---

## O ciclo de uma feature

```
/sdd:discovery  busca-de-cidade  "usuários não acham a cidade certa"
/sdd:spec       busca-de-cidade
/sdd:plan       busca-de-cidade
/sdd:tasks      busca-de-cidade
/sdd:implement  busca-de-cidade  next
/sdd:test       busca-de-cidade
/sdd:review     busca-de-cidade
/sdd:status
```

Cada feature tem um **slug** em `kebab-case`. Os artefatos dela:

| Etapa     | Arquivo                     |
| --------- | --------------------------- |
| Discovery | `specs/<slug>.discovery.md` |
| Spec      | `specs/<slug>.spec.md`      |
| Plan      | `plans/<slug>.plan.md`      |
| Tasks     | `tasks/<slug>.tasks.md`     |

Para features pequenas, `/sdd:discovery` é opcional — comece pela spec.

---

## Comandos

| Comando          | Faz                                                        |
| ---------------- | ---------------------------------------------------------- |
| `/sdd:config`    | Preenche o `sdd.config.md` perguntando (re-executável)     |
| `/sdd:discovery` | Levanta problema, personas, restrições e perguntas abertas |
| `/sdd:spec`      | Gera a especificação com requisitos e critérios de aceite  |
| `/sdd:plan`      | Gera o plano técnico com arquitetura e contratos           |
| `/sdd:tasks`     | Quebra o plano em backlog `T-NN` rastreável                |
| `/sdd:implement` | Implementa `T-NN`, um intervalo, ou `next`                 |
| `/sdd:test`      | Gera testes a partir dos critérios de aceite               |
| `/sdd:review`    | Revisa o diff contra spec, plano e convenções              |
| `/sdd:status`    | Mostra progresso e **furos de rastreabilidade**            |

## Agentes

Seis subagentes em `.claude/agents/`, um por fase, com ferramentas restritas ao
que a fase precisa — o Spec Agent não roda comandos, o Review Agent não edita
arquivos.

`sdd-spec` · `sdd-plan` · `sdd-task` · `sdd-code` · `sdd-test` · `sdd-review`

Os comandos já delegam ao agente certo. Para chamar direto:
`use o subagente sdd-review para revisar o diff atual`.

---

## Estrutura do kit

```
.claude/
  agents/          6 personas, uma por fase do fluxo
  commands/sdd/    9 slash commands /sdd:*
templates/         estrutura obrigatória de discovery, spec, plan e tasks
specs/  plans/  tasks/    onde os artefatos nascem
sdd.config.md      ⭐ o único arquivo a preencher
CLAUDE.md          regras do fluxo, carregadas automaticamente
.github/           validação em CI + template de PR (opcional)
```

---

## O que faz o kit funcionar

**Rastreabilidade em cadeia.** Requisito `RF-NN` → seção do plano → tarefa
`T-NN` → teste do critério `AC-NN`. Cada etapa produz uma tabela de cobertura, e
`/sdd:status` mostra onde a cadeia quebrou. É o que impede requisito de
evaporar entre a spec e o deploy.

**Ordem imposta, não sugerida.** Comandos param quando o artefato anterior não
existe. A CI reprova plano sem spec e tarefa sem plano.

**Ambiguidade explícita.** `Open Questions` é seção obrigatória. O Spec Agent
registra o que não sabe em vez de inventar — e reporta antes de você seguir.

**Escopo fechado.** O Code Agent implementa a tarefa e nada além. Trabalho
descoberto no caminho vira tarefa nova, com ID novo.

**Verificação real.** Nenhuma tarefa é marcada concluída sem os comandos do
config terem rodado. Falhou, o relatório traz a saída real.

---

## Personalizando

| Quero…                              | Mexo em…                              |
| ----------------------------------- | ------------------------------------- |
| Trocar comandos, convenções, restrições | `/sdd:config` — não edite na mão  |
| Trocar a stack                      | seção `Tech Stack` do plano da feature |
| Mudar as seções de uma spec/plano   | `templates/*.template.md`             |
| Mudar como uma fase se comporta     | `.claude/agents/sdd-*.md`             |
| Adicionar uma fase ao fluxo         | agente novo + comando novo em `.claude/commands/sdd/` |
| Afrouxar/apertar a validação em CI  | `.github/workflows/sdd-validate.yml`  |

> Os agentes aceleram, mas **você** é o(a) engenheiro(a) responsável. Revise
> criticamente cada artefato antes de aceitar.
