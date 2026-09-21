---
description: Gera o plano técnico de uma feature a partir da especificação aprovada.
argument-hint: "<slug> [restrições adicionais]"
---

# /sdd:plan — Gerar Plano Técnico

Feature: **$1**
Restrições adicionais: **$ARGUMENTS**

## Pré-condição

`specs/$1.spec.md` deve existir. Se não existir, **pare** e oriente o usuário a
rodar `/sdd:spec $1` antes. Se existir com `Open Questions` não resolvidas,
liste-as e confirme com o usuário antes de prosseguir.

## Execução

Delegue ao subagente **`sdd-plan`**, passando:

- `specs/$1.spec.md` como fonte da verdade;
- o caminho de saída `plans/$1.plan.md`;
- as restrições adicionais acima;
- instrução de seguir `templates/plan.template.md` e `sdd.config.md`.

## Após a execução

1. Confirme que a tabela de **Traceability** cobre todos os `RF-NN` da spec.
2. Aponte qualquer requisito sem cobertura no plano.
3. Apresente ao usuário: arquitetura em duas linhas, decisões técnicas
   relevantes e os trade-offs que merecem confirmação humana.
