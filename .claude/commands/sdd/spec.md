---
description: Gera a especificação de produto de uma feature a partir do briefing e do discovery.
argument-hint: "<slug> [briefing]"
---

# /sdd:spec — Gerar Especificação

Feature: **$1**
Briefing / contexto adicional: **$ARGUMENTS**

## Execução

Delegue ao subagente **`sdd-spec`**, passando:

- o slug `$1` e o briefing acima;
- o caminho de saída `specs/$1.spec.md`;
- `specs/$1.discovery.md` como entrada, se existir;
- instrução de seguir `templates/spec.template.md` e `sdd.config.md`.

## Após a execução

1. Verifique que o arquivo existe e tem **todas** as seções do template.
2. Verifique que todo `RF-NN` tem ao menos um `AC-NN` verificável.
3. Apresente ao usuário:
   - resumo dos requisitos funcionais criados;
   - a lista de **Open Questions**, que precisa de resposta antes do plano;
   - o que ficou explicitamente fora de escopo.

## Regra de parada

Se houver questão aberta que muda a arquitetura da solução, **pare aqui** e
pergunte. Não siga para `/sdd:plan` com ambiguidade estrutural em aberto.
