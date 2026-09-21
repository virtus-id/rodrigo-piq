# `plans/` — Planos Técnicos

Artefatos da fase de **decisão técnica**. Uma feature por slug:

- `<slug>.plan.md` — arquitetura, contratos e trade-offs (`/sdd:plan`)

Estrutura obrigatória em [`templates/plan.template.md`](../templates/plan.template.md).

Consome `specs/<slug>.spec.md` · alimenta `tasks/<slug>.tasks.md`.

> Todo item do plano rastreia para um `RF-NN` da spec. O que não rastreia é
> over-engineering.
