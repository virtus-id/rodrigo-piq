---
description: Faz a análise de discovery de uma feature — interroga o briefing, levanta ambiguidades e restrições antes da spec.
argument-hint: "<slug> [briefing]"
---

# /sdd:discovery — Análise de Discovery

Feature: **$1**
Briefing / contexto: **$ARGUMENTS**

Etapa **anterior à spec**. Aqui você não decide nada — você descobre o que ainda
não se sabe.

## Passos

1. Leia `sdd.config.md` e `templates/discovery.template.md`.
2. Leia specs existentes em `specs/` para não repetir decisões já tomadas.
3. Interrogue o briefing e produza `specs/$1.discovery.md` com:
   - **Problema** — qual dor real está sendo resolvida, e para quem
   - **Personas** — quem usa, com qual objetivo
   - **Cenários de uso** — situações concretas, não abstrações
   - **Restrições** — técnicas, de negócio, de prazo, legais
   - **Sucesso** — como saberemos que funcionou (métrica ou sinal observável)
   - **Riscos e incógnitas**
   - **Perguntas abertas** — numeradas, cada uma com por que ela importa e o
     que muda na solução conforme a resposta
4. Ao final, apresente as perguntas abertas ao usuário, priorizadas pelo impacto
   que a resposta tem sobre o desenho da solução.

## Regras

- **Não proponha solução.** Discovery levanta o problema; a spec o resolve.
- Uma pergunta aberta que não muda nada na solução não é uma pergunta útil —
  corte.
- Ambiguidade explícita é melhor que suposição implícita.
