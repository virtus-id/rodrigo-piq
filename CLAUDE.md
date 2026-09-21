# Projeto — Regras de Trabalho (SDD)

Este repositório usa **Spec-Driven Development (SDD)**. Todo trabalho segue o
fluxo:

```text
Discovery → Spec → Plan → Tasks → Code → Test → Review → Ship
```

## Princípio fundamental

> **NÃO COMECE PELO CÓDIGO.**
> Cada etapa consome o artefato da etapa anterior e produz o da próxima.

Antes de implementar qualquer feature, confirme que existem os artefatos
correspondentes. Se não existirem, **pare e produza o artefato faltante primeiro**.

## Configuração do projeto

**Leia [sdd.config.md](sdd.config.md) antes de qualquer trabalho técnico.** Ele
define comandos de verificação, estrutura de pastas, convenções e restrições.
Nunca assuma comandos — consulte o config. Para alterá-lo, rode `/sdd:config`
em vez de editar na mão.

A **stack não fica no config**: linguagem, framework e bibliotecas são decisão
de refinamento técnico e vivem na seção `Tech Stack` de `plans/<slug>.plan.md`,
onde cada escolha se justifica contra um requisito.

## Artefatos e nomenclatura

Cada feature tem um **slug** em `kebab-case` (ex.: `busca-de-cidade`). Os
artefatos daquela feature são:

| Etapa     | Arquivo                       | Produzido por        |
| --------- | ----------------------------- | -------------------- |
| Discovery | `specs/<slug>.discovery.md`   | `/sdd:discovery`     |
| Spec      | `specs/<slug>.spec.md`        | `/sdd:spec`          |
| Plan      | `plans/<slug>.plan.md`        | `/sdd:plan`          |
| Tasks     | `tasks/<slug>.tasks.md`       | `/sdd:tasks`         |
| Code      | código-fonte + testes         | `/sdd:implement`     |
| Test      | testes                        | `/sdd:test`          |
| Review    | relatório de revisão          | `/sdd:review`        |

## Agentes

Seis subagentes especializados em `.claude/agents/`, um por fase. Delegue a fase
ao agente correspondente em vez de fazer tudo na conversa principal:

`sdd-spec` · `sdd-plan` · `sdd-task` · `sdd-code` · `sdd-test` · `sdd-review`

## Comandos

`/sdd:config` · `/sdd:discovery` · `/sdd:spec` · `/sdd:plan` · `/sdd:tasks`
· `/sdd:implement` · `/sdd:test` · `/sdd:review` · `/sdd:status`

## Regras invioláveis

1. **Ordem.** Nunca produza um artefato sem que o anterior exista e esteja
   coerente. Plano sem spec, tarefa sem plano e código sem tarefa são erros.
2. **Rastreabilidade.** Todo item de plano rastreia para um requisito da spec.
   Toda tarefa rastreia para um requisito. Todo teste rastreia para um critério
   de aceite.
3. **Ambiguidade não se adivinha.** Registre em `Open Questions` e pergunte.
4. **Escopo.** Implemente a tarefa pedida e nada além dela. Descobriu trabalho
   extra? Vira nova tarefa no backlog, não um extra silencioso.
5. **Verificação.** Rode os comandos da seção 2 do `sdd.config.md` antes de
   declarar qualquer coisa concluída. Reporte falhas com a saída real.
6. **Idioma.** Tudo em pt-BR, inclusive identificadores. Os nomes no código são
   os nomes da spec canônica, caractere por caractere — `CAPACIDADE_ATAQUE_ATUAL`
   no código é `CAPACIDADE_ATAQUE_ATUAL` na spec. Traduzir cria um dicionário
   mental onde a regra se perde. Ver seção 7 do `sdd.config.md`.
