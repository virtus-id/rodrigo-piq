---
description: Revisa as mudanças atuais contra spec, plano, tarefas e boas práticas, com achados priorizados.
argument-hint: "<slug> [diff | staged | <base>..<head>]"
---

# /sdd:review — Revisar Mudanças

Feature: **$1**
Alvo da revisão: **$2** (vazio = mudanças não commitadas)

## Execução

Delegue ao subagente **`sdd-review`**, passando:

- o diff do alvo indicado;
- `specs/$1.spec.md`, `plans/$1.plan.md`, `tasks/$1.tasks.md`;
- `sdd.config.md` como régua de convenções e Definition of Done.

## Após a execução

Apresente o relatório com os achados classificados em `[bloqueante]`,
`[recomendado]` e `[nit]`, cada um com `arquivo:linha`.

Feche com um veredito explícito:

- **Aprovado** — todos os critérios de aceite cobertos, sem bloqueantes;
- **Aprovado com ressalvas** — só itens `[recomendado]`/`[nit]` pendentes;
- **Bloqueado** — liste os bloqueantes e os `AC-NN` descobertos.

## Regras

- Não corrija o código nesta etapa. Diagnóstico primeiro; correção é decisão do
  usuário.
- Sem bloqueante inventado para parecer rigoroso: se está correto, diga que está.
