-- Migração `recursos extraordinários por item` — T-271 (RF-98, DE-02).
--
-- `B3.05A`–`D` deixaram de ser perguntas de caso e viraram ficha repetível
-- (escopo `RECURSO_EXTRAORDINARIO_ID`, prefixo `EXT`, T-270): o aluno
-- cadastra vários recursos, cada um com tipo, valor, janela e certeza. As
-- respostas gravadas antes disso estão com `item_id = ''` e a montagem só lê
-- itens — sem esta migração, o recurso já declarado sumiria do cálculo.
--
-- Para cada caso com resposta legada nas quatro variáveis e ainda SEM item
-- `RECURSO_EXTRAORDINARIO_ID`: cria o item `EXT001` e move as respostas para
-- ele. Caso que já tem item daquele escopo fica intocado (não se funde
-- legado com o que o aluno já cadastrou).
--
-- EXCEÇÃO DECLARADA à disciplina "só DDL" de `002`–`007` (`R9-11`): é DML,
-- mas só troca a CHAVE das respostas — nenhuma regra de negócio, nenhum
-- valor alterado. Idempotente: na segunda execução não há mais legado de
-- caso sem item, e as duas instruções não fazem nada.
--
-- A chave persistida do item é `"<CASO_ID>:EXT001"` e a das respostas é o
-- identificador legível `EXT001` (`persistencia/app_aluno/itens.py`).

WITH legados AS (
    SELECT DISTINCT r."CASO_ID"
    FROM app_aluno.respostas r
    WHERE r.item_id = ''
      AND r."ID_PERGUNTA" IN (
          'TIPO_RECURSO_EXTRAORDINARIO',
          'VALOR_RECURSO_EXTRAORDINARIO',
          'JANELA_RECURSO_EXTRAORDINARIO',
          'CERTEZA_RECURSO_EXTRAORDINARIO'
      )
      AND NOT EXISTS (
          SELECT 1 FROM app_aluno.itens_repetidos i
          WHERE i."CASO_ID" = r."CASO_ID"
            AND i.escopo = 'RECURSO_EXTRAORDINARIO_ID'
      )
),
criados AS (
    INSERT INTO app_aluno.itens_repetidos (item_id, "CASO_ID", escopo)
    SELECT l."CASO_ID" || ':EXT001', l."CASO_ID", 'RECURSO_EXTRAORDINARIO_ID'
    FROM legados l
    ON CONFLICT (item_id) DO NOTHING
    RETURNING "CASO_ID"
)
UPDATE app_aluno.respostas r
SET item_id = 'EXT001'
FROM criados c
WHERE r."CASO_ID" = c."CASO_ID"
  AND r.item_id = ''
  AND r."ID_PERGUNTA" IN (
      'TIPO_RECURSO_EXTRAORDINARIO',
      'VALOR_RECURSO_EXTRAORDINARIO',
      'JANELA_RECURSO_EXTRAORDINARIO',
      'CERTEZA_RECURSO_EXTRAORDINARIO'
  );
