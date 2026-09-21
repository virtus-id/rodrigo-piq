-- Migração `e_revisor` — T-100.
-- RF-23, RF-25. plans/app-aluno.plan.md (T-100, decisão do usuário sobre a
-- lacuna de autorização documentada honestamente em T-69).
--
-- `/revisao/*` ficava sem autenticação própria até esta tarefa (T-69
-- documentou isso como limitação conhecida do piloto, não como omissão
-- silenciosa). Esta migração adiciona a coluna mínima necessária para
-- distinguir "conta de revisor" de "conta de aluno" — SEM recriar o sistema
-- de papéis que `OQ-03` já descartou (aquela decisão fala de ATRIBUIÇÃO DE
-- CASOS dentro da fila — revisor A vs. revisor B com filas separadas; esta
-- coluna não introduz fila por revisor nenhuma, só impede acesso anônimo).
--
-- `NOT NULL DEFAULT false`: toda conta existente e toda conta nova nasce
-- `e_revisor = false` por padrão — nenhuma conta vira revisora "por
-- acidente" de uma migração. Promover uma conta a revisora é, deliberada e
-- exclusivamente, uma operação manual fora desta migração (ver o
-- procedimento documentado em `persistencia/app_aluno/contas.py`,
-- `promover_a_revisor`, T-100): não existe tela nem rota de "promover a
-- revisor" nesta feature — provisionamento de revisor é operação de
-- administração de banco, fora de escopo de UI.
--
-- Mesma disciplina de `002_app_aluno.sql` (T-21): este arquivo é só DDL —
-- nenhum gate, ranqueamento ou fórmula da §11 aparece aqui.

ALTER TABLE app_aluno.contas
    ADD COLUMN IF NOT EXISTS e_revisor boolean NOT NULL DEFAULT false;
