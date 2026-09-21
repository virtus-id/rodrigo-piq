"""Suíte de testes da feature App do Aluno (coleta, plano e acompanhamento).

Espelha a estrutura de `tests/` do motor (`sdd.config.md` §3), mas isolada em
`app_aluno/` porque rastreia os requisitos e critérios de aceite da spec desta
feature (`specs/app-aluno.spec.md`), não da spec canônica do motor. Subpastas
(plans/app-aluno.plan.md §9):

- `estatica/`: AST de `app/`, `collection/`, `report/` — as travas da Lei nº 3
  (`AC-37`, `AC-41`, `AC-42`, `AC-44`, `RF-13`).
- `integracao/`: costuras desta feature contra Postgres real, marcadas
  `requer_banco` e puladas sem `DATABASE_URL`.
- `e2e/`: o ciclo mínimo cadastro → coleta → plano, marcado `e2e`.
- `fixtures/`: dados de apoio compartilhados pelos testes desta feature.
"""
