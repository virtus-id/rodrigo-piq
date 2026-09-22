-- Migração `bloqueio por reembolso` — adicionada operacionalmente em
-- 2026-09-22, junto com o webhook `PURCHASE_REFUNDED` da Hotmart
-- (`app/http/rotas_provisionamento.py`). Fora do fluxo Discovery → Spec
-- do `CLAUDE.md`; reconciliar como RF formal fica para o dev.
--
-- `NULL` = conta ativa (imensa maioria). Timestamp = bloqueada, e quando.
-- Não é `boolean`: saber QUANDO ajuda a auditar depois ("bloqueado há
-- quanto tempo, bate com a data do reembolso na Hotmart?").
--
-- Sem caminho de desbloqueio automático — decisão deliberada: um reembolso
-- revertido ou uma disputa resolvida a favor do aluno é rara e merece
-- decisão humana, não uma regra escondida em código. Desbloqueio manual:
--
--   UPDATE app_aluno.contas SET bloqueado_em = NULL WHERE email = '...';
--
-- Mesma disciplina de `002_app_aluno.sql`/`003_papel_revisor.sql`: só DDL.

ALTER TABLE app_aluno.contas
    ADD COLUMN IF NOT EXISTS bloqueado_em timestamptz;
