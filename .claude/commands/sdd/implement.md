---
description: Implementa uma ou mais tarefas do backlog, verificando os critérios de aceite ao final.
argument-hint: "<slug> <T-NN | T-NN..T-MM | next>"
---

# /sdd:implement — Implementar Tarefa

Feature: **$1**
Alvo: **$2**

## Pré-condição

`tasks/$1.tasks.md` deve existir. Se não existir, **pare** e oriente a rodar
`/sdd:tasks $1`.

## Seleção do alvo

- `T-NN` → implemente essa tarefa.
- `T-NN..T-MM` → implemente na ordem, uma de cada vez, verificando cada uma
  antes de passar para a próxima.
- `next` → a primeira tarefa não concluída cujas dependências já estão prontas.

## Execução

Para **cada** tarefa, delegue ao subagente **`sdd-code`**, passando:

- o ID e o texto completo da tarefa, com critérios de aceite e dependências;
- `plans/$1.plan.md` e `specs/$1.spec.md` como contexto;
- instrução de seguir `sdd.config.md` e rodar os comandos de verificação.

Antes de iniciar uma tarefa, confirme que suas dependências estão marcadas como
concluídas. Se não estiverem, pare e reporte.

## Após cada tarefa

1. Rode os comandos de verificação da seção 2 do `sdd.config.md`.
2. Confira **cada critério de aceite**, um a um, dizendo como foi verificado.
3. Marque a tarefa como concluída em `tasks/$1.tasks.md`.
4. Se algo falhou ou ficou parcial, **diga**, com a saída real do comando. Não
   siga para a próxima tarefa em cima de uma base quebrada.

## Regras

- Escopo restrito à tarefa. Trabalho extra descoberto vira nova tarefa no
  backlog, com ID novo.
- Nenhuma tarefa é marcada concluída sem verificação executada.
