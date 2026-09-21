-- Migração inicial do adaptador Supabase/Postgres do PIQ — T-75.
-- RF-10, RF-12, RF-13, V-01..V-03. plans/motor-calculo.plan.md §2.1, §6.
--
-- Regra inviolável desta migração (plano §2.1, "Onde Supabase é recusado"):
-- NENHUM gate, ranqueamento ou fórmula da §11 existe aqui. Este arquivo é
-- só DDL (schema, tabelas, colunas, constraints, índices) mais UMA trigger
-- de bloqueio TRIVIAL (impedir_sobrescrita_V01) que não avalia nenhum dado
-- de negócio — só recusa incondicionalmente UPDATE/DELETE. Toda regra de
-- negócio do motor vive em `engine/`, testável contra GAB-A/GAB-B/GAB-C.
--
-- Banco COMPARTILHADO com outros sistemas em produção (tabelas ads_*,
-- core_*, trv_*, vtr_* já existem em outros schemas). Por isso todo objeto
-- desta migração vive dentro do schema dedicado `motor_calculo` — nunca em
-- `public` nem em qualquer schema de outro sistema.

CREATE SCHEMA IF NOT EXISTS motor_calculo;

-- ---------------------------------------------------------------------------
-- Tabela `parametros` — RF-13, AC-17. Espelha parameters/parametros-<versao>
-- .json e parameters/esquema-parametros.json: uma linha por PARAMETROS_VERSION,
-- os 38 P_* ativos como colunas `numeric` (não jsonb — precisão decimal
-- exata cobrada pelo requisito, RF-12) e as três REGRA_* como texto (não são
-- número, são o nome de uma regra de comportamento já implementada em
-- engine/, nunca lógica nova aqui). Os três parâmetros multi-valor
-- (P_PRESSAO_INDIVIDUAL, P_PRESSAO_TOTAL, P_ESCALA_0_10) são `numeric[]`:
-- array de decimal exato, mesma garantia de precisão, sem virar jsonb.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS motor_calculo.parametros (
    "PARAMETROS_VERSION"                        text PRIMARY KEY,
    "ENGINE_VERSION"                             text NOT NULL,
    "DATA_VIGENCIA"                              date NOT NULL,

    "P_DIFERENCA_ECONOMICA_MATERIAL"             numeric NOT NULL,
    "P_CUSTO_ELEVADO_GATILHO_B7"                 numeric NOT NULL,
    "P_PRESSAO_GATILHO_B7"                       numeric NOT NULL,
    "P_DESCONTO_RELEVANTE"                       numeric NOT NULL,
    "P_CUSTO_RELEVANTE_GATILHO_B8"               numeric NOT NULL,
    "P_SALDO_MINIMO_TROCA"                       numeric NOT NULL,
    "P_PRAZO_MINIMO_TROCA"                       numeric NOT NULL,
    "P_QTD_BARREIRAS_CENTRAIS"                   numeric NOT NULL,
    "P_LIMIAR_RISCO_RECAIDA"                     numeric NOT NULL,
    "P_LIMIAR_RISCO_COMPORTAMENTAL_GERAL"        numeric NOT NULL,
    "P_MESES_VITORIA_RAPIDA"                     numeric NOT NULL,
    "P_DIFERENCA_CUSTO_EQUIVALENTE"              numeric NOT NULL,
    "P_DIFERENCA_PRAZO_EQUIVALENTE"              numeric NOT NULL,
    "P_REDUCAO_RENDA_VARIAVEL"                   numeric NOT NULL,
    "P_REDUCAO_CONFIABILIDADE_MEDIA"             numeric NOT NULL,
    "P_REDUCAO_CONFIABILIDADE_BAIXA"             numeric NOT NULL,
    "P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO"        numeric NOT NULL,
    "P_REDUCAO_HISTORICO_RECAIDA"                numeric NOT NULL,
    "P_FATOR_SEGURANCA_MINIMO"                   numeric NOT NULL,
    "P_FATOR_RENDA_VARIAVEL"                     numeric NOT NULL,
    "P_PISO_CAPACIDADE_ABSOLUTO"                 numeric NOT NULL,
    "P_PISO_CAPACIDADE_PERCENTUAL"               numeric NOT NULL,
    "P_TAXA_TOX_MODERADA"                        numeric NOT NULL,
    "P_TAXA_TOX_ALTA"                            numeric NOT NULL,
    "P_TAXA_TOX_MUITO_ALTA"                      numeric NOT NULL,
    "P_TAXA_TOX_CRITICA"                         numeric NOT NULL,
    "P_PRESSAO_INDIVIDUAL"                       numeric[] NOT NULL,
    "P_PRESSAO_TOTAL"                            numeric[] NOT NULL,
    "P_ESCALA_0_10"                              numeric[] NOT NULL,
    "P_DIFERENCA_TAXAS_RELEVANTE"                numeric NOT NULL,
    "P_REVISAO_DESCONTO"                         numeric NOT NULL,
    "P_REVISAO_REDUCAO_CUSTO_TROCA"              numeric NOT NULL,
    "P_REVISAO_CAPACIDADE_PCT"                   numeric NOT NULL,
    "P_REVISAO_CAPACIDADE_MESES"                 numeric NOT NULL,
    "P_HORIZONTE_ALERTA"                         numeric NOT NULL,
    "P_HORIZONTE_MAXIMO_SIMULACAO"               numeric NOT NULL,
    "P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA"    numeric NOT NULL,
    "P_AUTOPERCEPCAO"                            numeric NOT NULL,

    "REGRA_RESIDUO_ATAQUE"                       text NOT NULL,
    "REGRA_RANQUEAMENTO"                         text NOT NULL,
    "REGRA_DELTA_RESIDUO"                        text NOT NULL,

    criado_em                                    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Tabela `snapshots` — RF-10, RF-12, V-01..V-03. Uma linha por SnapshotOrdem
-- (engine/snapshot.py). Os valores DECISIVOS (custo, prazo, capacidades)
-- são colunas `numeric` de primeira classe — não apenas campos dentro de um
-- jsonb (critério de aceite 1 de T-75). O restante da árvore (estado_inputs,
-- diagnostico, cenarios, comparacao, ORDEM_QUITACAO, ORDEM_ACOES — estruturas
-- profundamente aninhadas, sem valor em consulta SQL direta) fica em
-- `dados_completos jsonb`, serializado por `engine.snapshot._serializar_
-- canonico` (Decimal -> string, Enum -> .value) — a MESMA função que o
-- adaptador de arquivo usa, sem segunda fonte de verdade de serialização.
--
-- CUSTO_FUTURO_TOTAL, PRAZO_TOTAL e as capacidades são as do CENÁRIO
-- recomendado (METODO_RECOMENDADO_PIQ) — o único cenário que a ordem
-- publicada de fato segue; os três cenários completos (HIBRIDO, AVALANCHE,
-- BOLA_DE_NEVE) continuam disponíveis em `dados_completos.cenarios`.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS motor_calculo.snapshots (
    "SNAPSHOT_ID"                    text PRIMARY KEY,
    versao                           integer NOT NULL,
    snapshot_anterior_id             text REFERENCES motor_calculo.snapshots("SNAPSHOT_ID"),
    "DATA_REFERENCIA"                date NOT NULL,
    "MOTIVO_RECALCULO"               text NOT NULL,
    "EVENTO_RECALCULO"               text,
    hash_inputs                      text NOT NULL,

    "METODO_RECOMENDADO_PIQ"         text NOT NULL,
    "STATUS_METODO"                  text NOT NULL,
    "ORDEM_STATUS"                   text NOT NULL,
    "REVISAO_HUMANA_OBRIGATORIA"     boolean NOT NULL,
    "DIVIDA_ALVO_ATUAL"              text,
    "PROXIMA_DIVIDA"                 text,

    -- valores decisivos do cenário recomendado — numeric, não jsonb (AC 1)
    "CUSTO_FUTURO_TOTAL"             numeric NOT NULL,
    "PRAZO_TOTAL"                    integer,
    "CAPACIDADE_ATAQUE_ATUAL"        numeric NOT NULL,
    "CAPACIDADE_ATAQUE_CONSERVADORA" numeric NOT NULL,
    "CAPACIDADE_ATAQUE_POTENCIAL"    numeric NOT NULL,

    "ENGINE_VERSION"                 text NOT NULL,
    "PARAMETROS_VERSION"             text NOT NULL,

    -- árvore completa (estado_inputs, diagnostico, cenarios, comparacao,
    -- ORDEM_QUITACAO, ORDEM_ACOES) via _serializar_canonico — round-trip
    -- exato de Decimal como string dentro do jsonb.
    dados_completos                  jsonb NOT NULL,

    criado_em                        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_snapshot_anterior_id
    ON motor_calculo.snapshots (snapshot_anterior_id);

-- ---------------------------------------------------------------------------
-- Imutabilidade por privilégio — V-01. Dupla defesa, não uma só:
--
-- 1) REVOKE: remove o privilégio de UPDATE/DELETE do role público — quem
--    conectar sem privilégio elevado explícito já não consegue a operação.
-- 2) Trigger `impedir_sobrescrita_V01`: defesa em profundidade contra um
--    role que TENHA o privilégio (ex.: dono da tabela, sempre com todos os
--    privilégios independente de REVOKE) — bloqueia incondicionalmente,
--    sem NENHUMA regra de negócio, só RAISE EXCEPTION.
-- ---------------------------------------------------------------------------

REVOKE UPDATE, DELETE ON motor_calculo.snapshots FROM PUBLIC;

CREATE OR REPLACE FUNCTION motor_calculo.impedir_sobrescrita_v01()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'V-01: motor_calculo.snapshots é append-only — % em % não é permitido (SNAPSHOT_ID=%)',
        TG_OP, TG_TABLE_NAME, COALESCE(OLD."SNAPSHOT_ID", 'desconhecido');
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS impedir_sobrescrita_v01 ON motor_calculo.snapshots;

CREATE TRIGGER impedir_sobrescrita_v01
    BEFORE UPDATE OR DELETE ON motor_calculo.snapshots
    FOR EACH ROW
    EXECUTE FUNCTION motor_calculo.impedir_sobrescrita_v01();
