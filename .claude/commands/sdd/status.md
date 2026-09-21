---
description: Mostra o estado do fluxo SDD — artefatos existentes, progresso das tarefas e furos de rastreabilidade.
argument-hint: "[slug]"
---

# /sdd:status — Estado do Fluxo SDD

Feature: **$ARGUMENTS** (vazio = todas as features encontradas)

## Passos

1. Verifique se `sdd.config.md` está preenchido (nenhum placeholder `<...>`).
2. Liste as features descobertas em `specs/`, `plans/` e `tasks/`.
3. Para cada feature, monte a linha de progresso:

   | Feature | Discovery | Spec | Plan | Tasks | Progresso |
   | ------- | :-------: | :--: | :--: | :---: | --------- |
   | `<slug>` | ✅/— | ✅/— | ✅/— | ✅/— | `n/m tarefas` |

4. Conte tarefas concluídas vs. total lendo os checkboxes de `tasks/*.tasks.md`.
5. Aponte os **furos**, que são o valor real deste comando:
   - artefato fora de ordem (plano sem spec, tarefas sem plano);
   - `RF-NN` da spec sem tarefa correspondente;
   - `AC-NN` sem teste correspondente;
   - `Open Questions` ainda em aberto;
   - tarefas bloqueadas por dependência não concluída.
6. Feche com **a próxima ação recomendada** e o comando exato para executá-la.

## Regras

- Relate o que os arquivos realmente dizem, sem otimismo. Furo escondido hoje é
  retrabalho amanhã.
- Não modifique nenhum arquivo — este comando é somente leitura.
