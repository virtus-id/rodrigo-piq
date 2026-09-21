-- Migração do schema `app_aluno` — T-21.
-- RF-01, RF-02, RF-10, RF-24, RF-30, RF-31, AC-43. plans/app-aluno.plan.md §4.5.
--
-- Regra inviolável desta migração (mesmo precedente de 001_inicial.sql):
-- NENHUM gate, ranqueamento ou fórmula da §11 existe aqui. Este arquivo é só
-- DDL (schema, tabelas, colunas, constraints, índices) mais UMA trigger de
-- bloqueio TRIVIAL (impedir_sobrescrita_revisao_v01), que não avalia nenhum
-- dado de negócio — só recusa incondicionalmente UPDATE/DELETE. Toda regra de
-- negócio do motor vive em `engine/`, testável contra GAB-A/GAB-B/GAB-C.
--
-- Schema SEPARADO de `motor_calculo` (NFR de segurança) — `app_aluno` guarda
-- só o que é desta feature: contas, casos, respostas, itens repetidos, fila de
-- revisão, consentimento e eventos do caso. NENHUMA tabela de snapshot vive
-- aqui: RF-19/AC-43 — a única porta de escrita de snapshot é
-- `RepositorioSnapshots.anexar` (engine/portas.py), sobre `motor_calculo.
-- snapshots`. Nenhum INSERT de snapshot é escrito nesta feature.

CREATE SCHEMA IF NOT EXISTS app_aluno;

-- ---------------------------------------------------------------------------
-- Tabela `contas` — RF-02. Login com senha, de qualquer dispositivo. A senha
-- nunca é armazenada em texto claro: `senha_hash` guarda o hash Argon2id
-- (app/http/senhas.py, T-28), nunca a senha em si. `email` é o identificador
-- de login e é único.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.contas (
    conta_id                text PRIMARY KEY,
    email                   text NOT NULL UNIQUE,
    senha_hash              text NOT NULL,
    criado_em               timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Tabela `casos` — RF-01, RF-14, OQ-11. Uma linha por caso (ciclo de vida do
-- aluno). `estado` é o `ESTADO_CASO` de app/casos/maquina.py — texto, não
-- enum de banco, porque a máquina de estados e suas transições nomeadas vivem
-- em código (app/), nunca em constraint de banco (a validação de transição é
-- responsabilidade de app/casos/maquina.py, não desta migração).
--
-- `DATA_REFERENCIA` é entrada explícita do aluno (RF-14, AC-18) — nunca o
-- relógio do servidor. `QUESTIONARIO_VERSION` amarra o caso à versão do
-- questionário respondido (RF-03, AC-38).
--
-- OQ-11: `CASO_ID` é identidade PRÓPRIA de app_aluno, gerada no cadastro —
-- distinta do `SNAPSHOT_ID` que RepositorioSnapshots.historico usa como
-- identificador de cadeia. `snapshot_raiz_id` é preenchido só quando o
-- primeiro snapshot nasce (Bloco 6); `snapshot_liberado_id` aponta o último
-- snapshot LIBERADO em revisão (RF-23) — o único que o aluno pode ver
-- (OQ-09). Nenhuma FK para motor_calculo.snapshots aqui: os dois schemas são
-- deliberadamente independentes (NFR de segurança) e a referência cruzada
-- é resolvida em app/, nunca por JOIN direto entre schemas nesta migração.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.casos (
    "CASO_ID"               text PRIMARY KEY,
    conta_id                text NOT NULL REFERENCES app_aluno.contas (conta_id),
    estado                  text NOT NULL,
    "DATA_REFERENCIA"       date NOT NULL,
    "QUESTIONARIO_VERSION"  text NOT NULL,
    snapshot_raiz_id        text,
    snapshot_liberado_id    text,
    ultima_interacao_em     timestamptz NOT NULL DEFAULT now(),
    criado_em               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_casos_conta_id
    ON app_aluno.casos (conta_id);

-- ---------------------------------------------------------------------------
-- Tabela `respostas` — RF-10, RF-11, RF-13. Uma linha por (caso, pergunta,
-- item) — a chave inclui `item_id` porque 115 das 291 perguntas são
-- repetíveis por ficha (RF-04): sem `item_id` na chave, respostas de fichas
-- diferentes colidiriam. `item_id` é `''` (nunca NULL) para pergunta não
-- repetível, para que a PK continue funcionando como igualdade simples — NULL
-- não é comparável por `=` e quebraria a unicidade pretendida.
--
-- `valor_numerico numeric` — NUNCA `double precision` nem `real` (RF-13):
-- todo valor monetário/decimal preserva precisão exata, mesmo padrão de
-- motor_calculo.parametros e motor_calculo.snapshots em 001_inicial.sql.
-- `valor_texto` cobre string, data (ISO), seleção e checklist serializados.
-- `valor_nao_sei` distingue "não sei" (RF-11, resposta de primeira classe) de
-- "não respondido" (ausência da linha) — nunca os dois via um valor mágico.
-- Exatamente um entre {valor_texto, valor_numerico, valor_nao_sei = true}
-- é preenchido por resposta; a exclusividade é responsabilidade do adaptador
-- (persistencia/app_aluno/respostas.py, T-22), não desta migração.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.respostas (
    "CASO_ID"               text NOT NULL REFERENCES app_aluno.casos ("CASO_ID"),
    "ID_PERGUNTA"           text NOT NULL,
    item_id                 text NOT NULL DEFAULT '',
    valor_texto             text,
    valor_numerico          numeric,
    valor_nao_sei           boolean NOT NULL DEFAULT false,
    "QUESTIONARIO_VERSION"  text NOT NULL,
    respondida_em           timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY ("CASO_ID", "ID_PERGUNTA", item_id)
);

-- ---------------------------------------------------------------------------
-- Tabela `itens_repetidos` — RF-04. Identidade estável de cada ficha
-- (DIVIDA_ID, VINCULO_ID, MARGEM_ID, item de despesa, ACAO_ID) por caso, para
-- que um item removido nunca reaproveite o identificador de um item novo
-- (T-15). `escopo` guarda o `EscopoRepeticao` (DIVIDA_ID/VINCULO_ID/
-- MARGEM_ID/ITEM_DESPESA/ACAO_ID) do item.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.itens_repetidos (
    item_id                 text PRIMARY KEY,
    "CASO_ID"               text NOT NULL REFERENCES app_aluno.casos ("CASO_ID"),
    escopo                  text NOT NULL,
    removido_em             timestamptz,
    criado_em               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_itens_repetidos_caso_id
    ON app_aluno.itens_repetidos ("CASO_ID");

-- ---------------------------------------------------------------------------
-- Tabela `revisoes` — RF-23, RF-24, RF-25. Uma linha por decisão de revisão
-- humana (liberação ou reprovação) sobre um snapshot, com autor e data
-- (RF-24). `classificacao_erro` é a `CLASSIFICACAO_ERRO` da §25 (RF-26),
-- nula quando a decisão é liberação. `snapshot_id` referencia
-- `motor_calculo.snapshots."SNAPSHOT_ID"` por VALOR, sem FK cruzando schema
-- (mesma independência declarada em `casos`).
--
-- Append-only, MESMO PADRÃO de motor_calculo.snapshots em 001_inicial.sql:
-- REVOKE do privilégio de UPDATE/DELETE do role público, mais trigger de
-- recusa incondicional como defesa em profundidade contra um role que já
-- tenha o privilégio (ex.: dono da tabela). Nenhuma regra de negócio na
-- trigger — só RAISE EXCEPTION (RF-24, AC-27).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.revisoes (
    revisao_id              text PRIMARY KEY,
    snapshot_id             text NOT NULL,
    "CASO_ID"               text NOT NULL REFERENCES app_aluno.casos ("CASO_ID"),
    decisao                 text NOT NULL,
    autor                   text NOT NULL,
    decidido_em             timestamptz NOT NULL DEFAULT now(),
    classificacao_erro      text,
    observacao              text
);

CREATE INDEX IF NOT EXISTS idx_revisoes_caso_id
    ON app_aluno.revisoes ("CASO_ID");

CREATE INDEX IF NOT EXISTS idx_revisoes_snapshot_id
    ON app_aluno.revisoes (snapshot_id);

-- Imutabilidade por privilégio — RF-24, AC-27. Dupla defesa, não uma só,
-- idêntica à de motor_calculo.snapshots (001_inicial.sql):
--
-- 1) REVOKE: remove o privilégio de UPDATE/DELETE do role público — quem
--    conectar sem privilégio elevado explícito já não consegue a operação.
-- 2) Trigger `impedir_sobrescrita_revisao_v01`: defesa em profundidade contra
--    um role que TENHA o privilégio (ex.: dono da tabela, sempre com todos os
--    privilégios independente de REVOKE) — bloqueia incondicionalmente, sem
--    NENHUMA regra de negócio, só RAISE EXCEPTION.

REVOKE UPDATE, DELETE ON app_aluno.revisoes FROM PUBLIC;

CREATE OR REPLACE FUNCTION app_aluno.impedir_sobrescrita_revisao_v01()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'RF-24: app_aluno.revisoes é append-only — % em % não é permitido (revisao_id=%)',
        TG_OP, TG_TABLE_NAME, COALESCE(OLD.revisao_id, 'desconhecido');
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS impedir_sobrescrita_revisao_v01 ON app_aluno.revisoes;

CREATE TRIGGER impedir_sobrescrita_revisao_v01
    BEFORE UPDATE OR DELETE ON app_aluno.revisoes
    FOR EACH ROW
    EXECUTE FUNCTION app_aluno.impedir_sobrescrita_revisao_v01();

-- ---------------------------------------------------------------------------
-- Tabela `consentimentos` — RF-30, AC-39, PEND-01. Registro de consentimento
-- explícito, com a versão do TEXTO (insumo externo de PEND-01, nunca redação
-- do desenvolvedor), aceite e data. Nenhum texto jurídico é gravado nesta
-- migração nem em código — só o carimbo de qual versão foi aceita.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.consentimentos (
    consentimento_id        text PRIMARY KEY,
    "CASO_ID"               text NOT NULL REFERENCES app_aluno.casos ("CASO_ID"),
    versao_texto            text NOT NULL,
    aceite                  boolean NOT NULL,
    aceito_em               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consentimentos_caso_id
    ON app_aluno.consentimentos ("CASO_ID");

-- ---------------------------------------------------------------------------
-- Tabela `eventos_caso` — RF-31, AC-40. Trilha de progresso e transições do
-- caso: em que bloco parou, o que aguarda revisão, o que não reporta
-- execução — para que o abandono seja observável, nunca silencioso.
-- `tipo_evento` nomeia a transição/evento (ex.: o `gatilho` de
-- app/casos/maquina.py::Transicao); `detalhe` carrega contexto adicional sem
-- estrutura fixa (texto livre técnico, não conteúdo do questionário).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_aluno.eventos_caso (
    evento_id               text PRIMARY KEY,
    "CASO_ID"               text NOT NULL REFERENCES app_aluno.casos ("CASO_ID"),
    tipo_evento             text NOT NULL,
    estado_de               text,
    estado_para             text,
    detalhe                 text,
    ocorrido_em             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eventos_caso_caso_id
    ON app_aluno.eventos_caso ("CASO_ID");
