---
description: Gera ou amplia os testes de uma feature a partir dos critérios de aceite e edge cases da spec.
argument-hint: "<slug> [escopo: unit | e2e | all]"
---

# /sdd:test — Gerar Testes

Feature: **$1**
Escopo: **$2** (vazio = `all`)

## Pré-condição

`specs/$1.spec.md` deve existir — os critérios de aceite são a fonte dos testes.

## Execução

Delegue ao subagente **`sdd-test`**, passando:

- `specs/$1.spec.md` (`Acceptance Criteria` + `Edge Cases`) como lista de
  trabalho;
- `plans/$1.plan.md`, seção `Testing Strategy`;
- o escopo pedido;
- instrução de seguir `sdd.config.md` (frameworks, pastas, convenções).

## Após a execução

1. Rode a suíte com os comandos do `sdd.config.md` e reporte o resultado real.
2. Apresente a tabela **`AC-NN` → teste que o cobre**.
3. Liste explicitamente os critérios e edge cases ainda **descobertos**.

## Regras

- Nunca chamar API real; rede, relógio e aleatoriedade sempre controlados.
- Teste que você não viu passar não é reportado como entregue.
