-- Migração `mensagem ao aluno` — T-333.
-- RF-113, AC-175 (revisa EC-12).
--
-- "Pedir correção" devolve o plano ao aluno com um texto do revisor para
-- ele, separado da `observacao` interna (que nunca vai a rota de aluno).
-- Gravado junto com a decisão, na mesma linha de `app_aluno.revisoes`.
--
-- Anulável e sem default: liberação não tem mensagem, e as revisões
-- gravadas antes desta migração ficam `NULL`. A tabela segue append-only
-- (REVOKE + trigger de `002`): adicionar coluna não é UPDATE de linha.
--
-- Mesma disciplina de `002`–`007`: só DDL. Idempotente.

ALTER TABLE app_aluno.revisoes
    ADD COLUMN IF NOT EXISTS mensagem_aluno text;
