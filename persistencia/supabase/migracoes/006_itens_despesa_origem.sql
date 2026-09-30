-- Migração `origem e nome do item repetido` — T-217 (RF-04, RF-05, RF-52).
--
-- A spec define "cada item marcado em B3.D01–D11 → B3.DF01–DF04": cada opção
-- marcada num checklist de despesa é uma ficha `ITEM_DESPESA`. Para o
-- servidor saber QUAL ficha pertence a QUAL opção — e removê-la quando o
-- aluno desmarca — o item guarda a sua origem:
--
--   `origem` = `"<ID da pergunta>:<valor_interno>"` (ex.: `B3.D01:ALUGUEL`),
--              ou `B3.D11` para a despesa não listada; `NULL` nas fichas
--              criadas pela lista (dívida, vínculo, ...), como sempre foi.
--   `nome`   = o nome curto que o aluno dá a "Outro" e à despesa não listada
--              (spec: "Outro → texto curto OPT"; "B3.D11 Sim → nome (texto
--              curto) + B3.DF01–DF04"). `NULL` enquanto não informado.
--
-- Mesma disciplina de `002`–`005`: só DDL, nenhuma regra da §11 aqui.

ALTER TABLE app_aluno.itens_repetidos
    ADD COLUMN IF NOT EXISTS origem text,
    ADD COLUMN IF NOT EXISTS nome text;
