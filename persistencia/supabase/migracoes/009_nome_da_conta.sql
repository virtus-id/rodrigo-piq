-- Migração `nome da conta` — T-332.
-- RF-112, OQ-68 (respondida 2026-10-02: "Pegue do cadastro da Hotmart o
-- nome do aluno").
--
-- `nome` é o do comprador no webhook `PURCHASE_APPROVED` da Hotmart
-- (`data.buyer.name`), gravado no provisionamento. Só a equipe o vê, no
-- Painel de usuários — nunca vai a rota de aluno nem a log.
--
-- Anulável e sem default: conta criada antes desta migração, ou por
-- `/api/provisionamento/conta` (só e-mail), fica `NULL` e o painel mostra
-- "—". Nome vazio também é `NULL`, nunca `''`.
--
-- Mesma disciplina de `002`–`007`: só DDL. Idempotente.

ALTER TABLE app_aluno.contas
    ADD COLUMN IF NOT EXISTS nome text;
