---
description: Quebra o plano técnico de uma feature em um backlog de tarefas pequenas e testáveis.
argument-hint: "<slug>"
---

# /sdd:tasks — Quebrar em Tarefas

Feature: **$1**

## Pré-condição

`specs/$1.spec.md` e `plans/$1.plan.md` devem existir. Falta algum? **Pare** e
indique qual comando rodar antes.

## Execução

Delegue ao subagente **`sdd-task`**, passando:

- `plans/$1.plan.md` como entrada e `specs/$1.spec.md` como referência;
- o caminho de saída `tasks/$1.tasks.md`;
- instrução de seguir `templates/tasks.template.md` e `sdd.config.md`.

## Após a execução

1. Verifique que cada tarefa tem ID, critérios de aceite, dependências e
   rastreabilidade para `RF-NN`.
2. Verifique que a ordem respeita as dependências — nenhuma tarefa depende de
   outra que aparece depois dela.
3. Apresente: total de tarefas, agrupamento por entrega, quais podem começar
   imediatamente (sem dependências) e qualquer requisito da spec sem tarefa.
