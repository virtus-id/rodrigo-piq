-- Migração `primeiro acesso` — T-179.
-- RF-02, RF-30, OQ-05. Decisões do especialista de 2026-09-21.
--
-- **O aluno compra na Hotmart, não se cadastra no PIQ.** Não existe (nem vai
-- existir) tela de cadastro público: a conta nasce de uma compra aprovada,
-- por webhook, e o comprador nunca informa senha nesse momento — a Hotmart
-- entrega nome e e-mail, nada mais.
--
-- Isso cria um estado que o schema não previa: **conta existente, sem senha
-- definida**. Até aqui `senha_hash` era `NOT NULL`, então a conta não podia
-- nascer antes de o aluno escolher uma senha — e não há como ele escolher
-- antes de existir a conta.
--
-- Duas mudanças, as mínimas:
--
-- 1. `senha_hash` passa a aceitar `NULL` — "conta provisionada, senha ainda
--    não definida". **`NULL` nunca autentica**: `contas.py::autenticar`
--    recusa antes de comparar hash, e um teste audita isso. Sem essa
--    guarda, conta sem senha seria conta aberta.
--
-- 2. Tabela `tokens_primeiro_acesso` — o token que o aluno usa para definir
--    a senha dele. Uso único (`usado_em`), com expiração (`expira_em`), e
--    guardado como HASH, nunca em claro: quem ler o banco não consegue se
--    passar por ninguém. Mesma disciplina de `senha_hash`.
--
-- **O mesmo mecanismo serve para "esqueci minha senha"** — é por isso que a
-- tabela não se chama `tokens_de_cadastro`: o fato modelado é "prova de
-- posse do e-mail para definir senha", e ele vale nos dois fluxos.
--
-- Mesma disciplina de `002`/`003`: só DDL, nenhuma regra da §11 aqui.

-- ---------------------------------------------------------------------------
-- 1. `senha_hash` anulável.
-- ---------------------------------------------------------------------------
ALTER TABLE app_aluno.contas
    ALTER COLUMN senha_hash DROP NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Tokens de primeiro acesso / redefinição de senha.
--
-- `token_hash` é PRIMARY KEY: a busca é sempre pelo hash do token que o
-- aluno apresenta, e dois tokens não colidem.
--
-- `ON DELETE CASCADE`: excluída a conta (LGPD, art. 18 — `EC-13`), os tokens
-- dela vão junto. Token órfão é credencial pendurada.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_aluno.tokens_primeiro_acesso (
    token_hash    text PRIMARY KEY,
    conta_id      text NOT NULL REFERENCES app_aluno.contas (conta_id) ON DELETE CASCADE,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    expira_em     timestamptz NOT NULL,
    usado_em      timestamptz
);

-- Busca por conta: revogar os tokens anteriores ao emitir um novo (um pedido
-- de "esqueci a senha" invalida o anterior).
CREATE INDEX IF NOT EXISTS tokens_primeiro_acesso_conta_id_idx
    ON app_aluno.tokens_primeiro_acesso (conta_id);
