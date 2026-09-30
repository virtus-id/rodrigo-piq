-- Migração `item pai do item repetido` — T-253 (RF-90, AC-137, EC-35, DE-05).
--
-- A margem pertence ao vínculo: cada `MARGEM_ID` é cadastrada dentro de
-- exatamente um `VINCULO_ID` (canônica v1.0.2, `E-09`). A pertença é
-- estrutural, gravada na criação do item:
--
--   `item_pai_id` = identificador LEGÍVEL do pai (ex.: `V001`), do mesmo
--                   caso; `NULL` em todo item que não tem pai.
--
-- Nenhuma FK: a PK de `itens_repetidos` é a chave persistida
-- `"CASO_ID:V001"`, não o identificador legível. A validação (pai existe,
-- ativo, do mesmo caso) é da aplicação (`app/http/rotas_fichas.py`).
--
-- Mesma disciplina de `002`–`006`: só DDL, nenhuma regra da §11 aqui.

ALTER TABLE app_aluno.itens_repetidos
    ADD COLUMN IF NOT EXISTS item_pai_id text;
