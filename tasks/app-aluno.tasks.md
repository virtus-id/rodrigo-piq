# Backlog — App do Aluno (coleta, plano e acompanhamento)

| Campo | Valor                                                    |
| ----- | -------------------------------------------------------- |
| Slug  | `app-aluno`                                              |
| Spec  | [`specs/app-aluno.spec.md`](../specs/app-aluno.spec.md)  |
| Plano | [`plans/app-aluno.plan.md`](../plans/app-aluno.plan.md)  |

## Progresso

`143/143 tarefas concluídas` — `107/107` da **Rodada 1** (fechada), `14/14`
da **Rodada 2, fatia 2A** (`T-108` a `T-120`), `9/9` da **Rodada 3**
(`T-122` a `T-130`, protótipo validado, máscara de entrada e verificação em
navegador real, fechada em 2026-09-14) e `13/13` da **Rodada 4** (`T-131` a
`T-143`, frontend React e cobertura total do motor, aberta em 2026-09-15).

> **Rodada 4 em andamento.** A primeira fatia (login, coleta e fichas
> repetíveis, no design do protótipo) está entregue e verificada. O que
> falta está listado em `RF-53`/`RF-54`: Blocos 7, 8, 10 e 11, as três
> transições de saída de `PLANO_LIBERADO`, `REPROVADO_EM_REVISAO`,
> `ENCERRADO` e as ações do operador — mais as telas de plano, revisão e
> operador no design do protótipo.

### Rodada 1

`107/107 tarefas concluídas` — **fechada**. As três últimas pendências,
`T-77`, `T-78`, `T-79`, estavam bloqueadas por dependência externa do slug
`motor-calculo` (`OQ-17`/`OQ-29`) e foram destravadas e implementadas nesta
rodada de fechamento (2026-09-10), depois que a fatia 4C do `motor-calculo`
resolveu `OQ-29` por completo (ver nota de `T-77` para a confirmação por
leitura direta) — nenhum campo foi mais aguardado; a implementação do
Bloco 10 condicional (`app/casos/confirmacao_ataque.py`,
`app/http/rotas_bloco10.py`), a validação declarativa de `B10.C01A`
(`RespostasDoBloco10`) e os testes de `T-79` (`tests/app_aluno/
test_bloco10.py`, mais a reconfirmação de `test_coleta_dirigida.py`) fecham
o backlog original.

Nove tarefas novas foram abertas depois do fechamento das 18 Open Questions
originais da spec, todas `[x] concluída`: `T-102` (painel do operador),
`T-104` (identificadores fechados de `TIPO_ACAO`), `T-105` (extensão de
`EscopoRepeticao` para `OQ-19`), `T-103` (fórmulas de renda/despesa do Bloco
3), `T-106` (correção de bug real: `rotas_calculo.py` bloqueava o Bloco 6
inteiro em produção citando `OQ-16` como aberta, mesmo já respondida) e
`T-107` (correção de fórmula: exclusão de dupla contagem em `DESPESAS_
NAO_MENSAIS_NORMALIZADAS` quando `DESPESA_NAO_MENSAL_JA_CONTABILIZADA =
Sim`). Suíte completa depois do fechamento de `T-77`/`T-78`/`T-79`:
`1495 passed, 75 skipped`, `ruff`/`mypy --strict` limpos (ver nota de `T-79`
para o recongelamento de hashes que acompanhou este fechamento).

---

## Regras que valem para toda tarefa deste backlog

> **Lei nº 1** (`plans/motor-calculo.plan.md` §1): `engine/` não conhece
> persistência nem Supabase. **Lei nº 3** (`plans/app-aluno.plan.md` §1): *a
> aplicação não calcula* — todo número, status ou prazo exibido é a **leitura de
> um campo de `SnapshotOrdem`**. Nenhuma tarefa deste backlog implementa gate,
> ranqueamento, fórmula da §11 ou valor `P_*` (`RF-34`, `AC-41`, `AC-42`).
>
> **`engine/` está CONGELADO.** Nenhuma tarefa daqui edita `engine/` nem
> `persistencia/supabase/{conexao,fonte_parametros,repositorio_snapshots}.py`
> nem `persistencia/arquivo/` (`AC-44`). As três mudanças previstas em
> `engine/gates.py::AcaoRequerida` (campos `ACAO_ID`/`TIPO_ACAO`; Gate 1
> emitindo ação; ação de economia fora do fluxo de gates) são trabalho do slug
> **`motor-calculo`**. Onde uma tarefa depende delas, a linha de Dependências
> traz `externa: motor-calculo (...)`.
>
> **`persistencia/` já existe** para snapshots e parâmetros. As tarefas de
> persistência daqui cobrem só o que é desta feature: respostas de coleta,
> contas, estado do caso, itens repetidos, fila de revisão, consentimentos e
> eventos do caso — no schema dedicado `app_aluno`.
>
> **Convenções** (`sdd.config.md` §4, §5, §7): identificadores em pt-BR,
> idênticos aos da spec e da canônica **caractere por caractere**; nenhum
> `float` em nenhum caminho de valor monetário; todo teste rastreia para um
> `AC-NN`; comportamento observável, nunca implementação.

### Dependências externas declaradas

| Dependência | De quem | Bloqueia |
| --- | --- | --- |
| `AcaoRequerida` ganha `ACAO_ID` e `TIPO_ACAO` | slug `motor-calculo` | `T-83`, `T-84`, `T-85`, `T-90` |
| Gate 1 passa a emitir `AcaoRequerida` de tipo informação (`OQ-14`) | slug `motor-calculo` | `T-90` (`AC-47`), `T-85` (extração do campo a reabrir) |
| Ação de economia emitida fora do fluxo de gates; `AcaoRequerida.DIVIDA_ID` vira `str \| None` (`OQ-15`, respondida) | slug `motor-calculo` | `T-90` (`AC-49`) |
| `OQ-13` (respondida) — `TIPO_ACAO` é domínio fechado ASCII sem parênteses: `INFORMACAO`, `RENEGOCIACAO`, `TROCA`, `ECONOMIA` | slug `motor-calculo` (implementação) e esta feature (`T-104`, registro ainda não atualizado) | `T-84` (mecanismo pronto, mapeamento vive em registro); `T-104` (tarefa nova: `bloco-11.yaml` ainda usa os literais pré-decisão) |
| `OQ-12` (respondida) — texto normativo da §25 confirmado ausente do repositório inteiro; decisão: manter só os seis nomes do enum, sem glosa (`PEND-LOCAL-01`) | especialista (se algum dia quiser escrever o texto) | `T-72` (`RF-26`: seis rótulos sem glosa + campo livre) — **não bloqueia mais nada, decisão fechada** |
| `OQ-17`/`OQ-29` (ambas respondidas e **implementadas por completo**) — `ATAQUE_IMEDIATO_RECOMENDADO`/`RESERVA_MOBILIZAVEL` são campos reais de `Diagnostico`, publicados com valor real por `engine.motor.calcular_plano` (fatia 4C do `motor-calculo`, 2026-09-10) | slug `motor-calculo` (implementação) | `T-77`, `T-78`, `T-79` — **destravadas e concluídas** nesta rodada de fechamento (2026-09-10); não bloqueiam mais nada |
| `OQ-18` (respondida) — novo campo `CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]` em `AcaoRequerida`; `app-aluno` mapeia para a pergunta a reabrir | slug `motor-calculo` (implementação) | `T-85` (extração do campo a reabrir a partir de uma ação real; o mecanismo de reabertura em si já está implementado e testado) |
| `PEND-01` — textos de consentimento, retenção e exclusão | jurídico + especialista | `T-35`, `T-36` (pontos de encaixe entregues; o texto é insumo externo) |
| `OQ-07` (respondida) — painel dedicado do operador, não só dado consultável | esta feature (`app-aluno`) | `T-92` (trilha, já entregue) alimenta `T-102`, tarefa nova (`RF-35`) |
| `OQ-19` (respondida) — dois novos membros em `EscopoRepeticao`: `RENDA_ADICIONAL_ID`, `DESPESA_NAO_MENSAL_ID` | esta feature (`app-aluno`) | `T-105` (tarefa nova, implementa a extensão), que por sua vez desbloqueia `T-103` |

---

## Entrega 1 — Fundação: config, stack da aplicação e portão de qualidade

### `T-01` — Registrar `app/` na seção 3 do `sdd.config.md`

- **Tipo:** `Docs`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-01`, `RF-02`, `RF-34`
- **Arquivos:** `sdd.config.md`

**Descrição**

O plano §3 declara uma divergência do config: a camada de aplicação (sessão,
autenticação, máquina de estados do caso, montagem do estado, invocação do
motor) não é `collection/` nem `report/` e vive em `app/`. A divergência precisa
estar registrada **antes** da primeira linha de código de aplicação, mesmo
procedimento adotado por `motor-calculo` `T-02` para `persistencia/`.

**Critérios de aceite**

- [x] A tabela da §3 do `sdd.config.md` lista `app/` com sua responsabilidade
- [x] O texto registra que `app/`, `collection/` e `report/` importam de `engine/` e de `persistencia/`, e que a recíproca nunca ocorre
- [x] `collection/` e `report/` têm sua responsabilidade atualizada para o que este slug entrega (gerador a partir de registros; templates do plano e fila de revisão)
- [x] A alteração cita `plans/app-aluno.plan.md` §3 como origem da divergência

**Status:** `[x] concluída`

---

### `T-02` — Atualizar os comandos de verificação da seção 2 do `sdd.config.md`

- **Tipo:** `Infra`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-34`, `AC-41`
- **Arquivos:** `sdd.config.md`, `pyproject.toml`

**Descrição**

Hoje `build` é `mypy engine persistencia tests` — as pastas novas (`app/`,
`collection/`, `report/`) não seriam vistas pelo portão de qualidade. Sem esta
tarefa, todo o código desta feature passa por fora do `mypy --strict`.

**Critérios de aceite**

- [x] `build` na §2 do config cobre `engine persistencia collection app report tests`
- [x] `[tool.mypy] files` do `pyproject.toml` lista as mesmas pastas
- [x] `lint` continua cobrindo a raiz (`ruff check .`), sem exclusão das pastas novas
- [x] Rodar `build` e `lint` com as pastas ainda vazias termina com código 0

**Status:** `[x] concluída`

---

### `T-03` — Declarar o extra `app` no `pyproject.toml` com as quatro dependências novas

- **Tipo:** `Infra`
- **Dependências:** `T-02`
- **Rastreia:** `RF-02`, `RF-13`, `RF-20`
- **Arquivos:** `pyproject.toml`

**Descrição**

Extra `app` com `fastapi`, `uvicorn`, `argon2-cffi` e `weasyprint` (`jinja2` é
transitiva de FastAPI). O extra é separado para que a suíte do motor continue
rodando sem nenhuma delas instalada — a pureza de `engine/` não pode passar a
depender de pacote de aplicação.

**Critérios de aceite**

- [x] `pyproject.toml` declara `[project.optional-dependencies] app` com as quatro dependências
- [x] `[tool.setuptools.packages.find] include` passa a incluir `app*`, `collection*` e `report*`
- [x] Instalar apenas `.[dev]` e rodar `pytest -m "gabarito or invariante"` continua passando sem nenhum pacote do extra `app`
- [x] Nenhuma dependência do extra `app` aparece em `dependencies` do projeto

**Status:** `[x] concluída`

---

### `T-04` — Criar o esqueleto de pacotes `app/`, `collection/` e `report/`

- **Tipo:** `Infra`
- **Dependências:** `T-01`, `T-02`
- **Rastreia:** `RF-01`, `RF-03`, `RF-21`
- **Arquivos:** `app/__init__.py`, `app/http/__init__.py`, `app/casos/__init__.py`, `app/montagem/__init__.py`, `app/motor/__init__.py`, `app/eventos/__init__.py`, `app/revisao/__init__.py`, `app/consentimento/__init__.py`, `collection/__init__.py`, `collection/registros/`, `report/__init__.py`, `report/templates/`

**Descrição**

Pastas e `__init__.py` dos módulos previstos na §3 do plano, importáveis e
vazios de lógica. Existir como destino desde já evita que o primeiro módulo
escolha a pasta por conta própria.

**Critérios de aceite**

- [x] Todos os pacotes acima existem e são importáveis
- [x] `mypy` com a configuração de `T-02` termina com código 0 sobre eles
- [x] Nenhum `__init__.py` contém lógica além de docstring
- [x] `collection/registros/` e `report/templates/` existem como diretórios versionados

**Status:** `[x] concluída`

---

### `T-05` — Criar o esqueleto de testes `tests/app_aluno/` e os marcadores da suíte

- **Tipo:** `Test`
- **Dependências:** `T-02`
- **Rastreia:** `RF-34`
- **Arquivos:** `tests/app_aluno/__init__.py`, `tests/app_aluno/estatica/__init__.py`, `tests/app_aluno/integracao/__init__.py`, `tests/app_aluno/e2e/__init__.py`, `tests/app_aluno/fixtures/__init__.py`, `pyproject.toml`

**Descrição**

Subpastas da suíte desta feature (§9 do plano) e os marcadores novos:
`requer_banco` (pulado sem `DATABASE_URL`) e `e2e`. Os marcadores existentes do
motor (`gabarito`, `invariante`, `regra`, `desempenho`) permanecem intactos.

**Critérios de aceite**

- [x] `pytest --collect-only` reconhece as quatro subpastas sem erro de importação
- [x] Os marcadores `requer_banco` e `e2e` estão declarados em `[tool.pytest.ini_options] markers` com descrição
- [x] `pytest -m "not requer_banco and not e2e"` roda sem exigir `DATABASE_URL`
- [x] Nenhum marcador pré-existente foi removido ou renomeado

**Status:** `[x] concluída`

---

### `T-06` — Escrever o teste estático de fronteira de import com `engine/` (`AC-41`)

- **Tipo:** `Test`
- **Dependências:** `T-04`, `T-05`
- **Rastreia:** `RF-34`, `AC-41`
- **Arquivos:** `tests/app_aluno/estatica/test_fronteira_import_engine.py`

**Descrição**

Análise de AST de todo `.py` de `app/`, `collection/` e `report/`: os imports de
`engine.*` são **apenas** `calcular_plano`, os tipos de entrada/saída
(`EstadoFinanceiro`, `Divida`, `SnapshotOrdem`, tipos e enums de `engine.tipos`,
`Parametros`), as portas (`FonteParametros`, `RepositorioSnapshots`) e
`engine.precisao`. Qualquer outro import falha o teste, com a lista permitida
declarada no próprio arquivo de teste.

**Critérios de aceite**

- [x] O teste percorre todo `.py` das três pastas por `ast.parse`, sem importar os módulos
- [x] Importar `engine.gates`, `engine.ciclo_mensal`, `engine.metodos.*`, `engine.comparacao` ou `engine.ordem` a partir de `app/`, `collection/` ou `report/` faz o teste falhar nomeando o arquivo e a linha
- [x] O teste falha também para `from engine import *`
- [x] O teste cita `AC-41` no nome e passa com as pastas ainda vazias

**Status:** `[x] concluída`

---

### `T-07` — Escrever o teste estático de não-modificação de `engine/` e `persistencia/` (`AC-44`)

- **Tipo:** `Test`
- **Dependências:** `T-05`
- **Rastreia:** `RF-34`, `AC-44`
- **Arquivos:** `tests/app_aluno/estatica/test_engine_congelado.py`, `tests/app_aluno/estatica/hashes_congelados.json`

**Descrição**

Hash SHA-256 de cada arquivo de `engine/`, de `persistencia/arquivo/` e de
`persistencia/supabase/` (exceto a migração nova desta feature), registrado num
JSON versionado. Alterar qualquer um deles quebra o teste com o nome do arquivo.

**Critérios de aceite**

- [x] O JSON lista o hash de todos os `.py` de `engine/` e de `persistencia/` e de `migracoes/001_inicial.sql`
- [x] `persistencia/supabase/migracoes/002_app_aluno.sql` está explicitamente fora do conjunto congelado
- [x] Modificar um byte de qualquer arquivo congelado faz o teste falhar nomeando o arquivo
- [x] O teste cita `AC-44` no nome e documenta que a exceção prevista (`AcaoRequerida`) é do slug `motor-calculo`, com o procedimento de atualizar o hash quando ela chegar

**Status:** `[x] concluída`

---

### `T-08` — Escrever o teste estático de ausência de enunciado, opção e `P_*` no código (`AC-37`)

- **Tipo:** `Test`
- **Dependências:** `T-05`
- **Rastreia:** `RF-03`, `RF-32`, `AC-37`
- **Arquivos:** `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py`

**Descrição**

Auditoria de AST sobre `app/`, `collection/` e `report/`: nenhum literal de
string que seja enunciado, opção ou condição das 291 perguntas, e nenhum
identificador começando por `P_` da §8. O critério operacional: nenhum literal
de string com mais de N caracteres fora de docstring, e nenhuma referência a
nome `P_*`.

**Critérios de aceite**

- [x] O teste falha se qualquer `.py` das três pastas contiver um literal `P_` de parâmetro da §8
- [x] O teste falha se um enunciado de pergunta (string longa fora de docstring/mensagem de erro técnica) for introduzido em `.py`
- [x] As exceções permitidas (mensagens técnicas, chaves de configuração) estão declaradas explicitamente numa lista no teste, não implícitas
- [x] O teste cita `AC-37` no nome e passa com as pastas ainda vazias

**Status:** `[x] concluída`

---

## Entrega 2 — Coleta gerada: os registros das 291 perguntas viram dado

### `T-09` — Definir o esquema `RegistroPergunta` e seus domínios

- **Tipo:** `Data`
- **Dependências:** `T-04`
- **Rastreia:** `RF-03`, `AC-36`, `AC-37`
- **Arquivos:** `collection/registro.py`

**Descrição**

Dataclasses `frozen=True, slots=True` e enums do §4.1 do plano:
`Obrigatoriedade`, `TipoResposta`, `EscopoRepeticao`, `OpcaoRegistro` e
`RegistroPergunta` com todos os campos listados. **Nenhum enunciado, opção ou
condição das 291 perguntas aparece neste arquivo** — ele define o esquema.

**Critérios de aceite**

- [x] `Obrigatoriedade` tem exatamente `OBR`, `COND`, `OPT`, `REP`; `obrigatoriedade` é `frozenset` para que `COND`+`REP` coexistam (caso de `B5.A05A`)
- [x] `TipoResposta` tem os nove membros da §4.1; `EscopoRepeticao` tem os seis
- [x] `RegistroPergunta` declara `ID`, `bloco`, `enunciado`, `tipo`, `obrigatoriedade`, `escopo_repeticao`, `opcoes`, `VARIAVEL_GRAVADA`, `condicao_exibicao`, `interpolacoes`, `validacoes_cruzadas`, `origem_opcoes`, `admite_nao_sei`, `salto_consequencia`
- [x] Nenhuma string de enunciado, rótulo de opção ou condição de pergunta consta do arquivo — `T-08` passa sobre ele
- [x] `mypy --strict` termina com código 0

**Status:** `[x] concluída`

---

### `T-10` — Definir o tipo `Condicao` como árvore declarativa

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-05`, `AC-21`
- **Arquivos:** `collection/condicoes.py`

**Descrição**

Os seis nós do §4.1: `CondicaoIgual`, `CondicaoContem`, `CondicaoExisteItem`,
`CondicaoE`, `CondicaoOu`, `CondicaoNao`, com `CondicaoIgual` referenciando a
variável **por nome** (`VARIAVEL_GRAVADA`), nunca por bloco — é isso que faz a
condicional entre blocos ser o caso comum, e não uma exceção.

**Critérios de aceite**

- [x] O tipo-soma `Condicao` cobre os seis nós e é exaustivo sob `mypy --strict`
- [x] `CondicaoIgual`/`CondicaoContem` referenciam a variável por nome, sem campo de bloco
- [x] `CondicaoExisteItem` carrega `escopo`, `variavel` e `valor_em: frozenset[str]`
- [x] Nenhum `ID` de pergunta aparece como literal no módulo

**Status:** `[x] concluída`

---

### `T-11` — Implementar `avaliar(condicao, respostas)`

- **Tipo:** `Data`
- **Dependências:** `T-10`
- **Rastreia:** `RF-05`, `AC-21`
- **Arquivos:** `collection/condicoes.py`

**Descrição**

Interpretador genérico da árvore. Percorre os nós e devolve booleano. Não existe
nenhum `if pergunta.ID == "..."` em lugar nenhum do módulo — a especificidade
mora no YAML.

**Critérios de aceite**

- [x] `avaliar` trata os seis nós, com exaustividade verificada por `mypy --strict`
- [x] Variável ausente em `respostas` avalia como falso, sem levantar exceção
- [x] Resposta `NAO_SEI` não satisfaz `CondicaoIgual` de um valor concreto
- [x] Nenhum `ID` de pergunta e nenhum ramo específico de pergunta aparece no módulo

**Status:** `[x] concluída`

---

### `T-12` — Definir `Marcador` e implementar `interpolar`

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-06`, `AC-05`, `AC-42`
- **Arquivos:** `collection/interpolacao.py`

**Descrição**

`Marcador` com `marcador`, `origem` (`ID_DO_ITEM`, `VARIAVEL_COLETADA`,
`CAMPO_DO_SNAPSHOT`) e `referencia`; `interpolar` substitui no enunciado. Origem
`CAMPO_DO_SNAPSHOT` **lê** um campo de `SnapshotOrdem` — nunca recalcula — e todo
valor monetário passa por `engine.precisao.quantizar_exibicao` (`G-01`).

**Critérios de aceite**

- [x] `interpolar` substitui marcador de `ID_DO_ITEM` pelo identificador do item corrente
- [x] Origem `CAMPO_DO_SNAPSHOT` acessa o campo por nome e nunca faz aritmética sobre ele
- [x] Valor monetário interpolado passa por `quantizar_exibicao` antes de virar texto
- [x] Marcador sem valor disponível produz erro explícito, nunca string vazia silenciosa

**Status:** `[x] concluída`

---

### `T-13` — Definir `ValidacaoCruzada` e implementar `validar_cruzada`

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-07`, `AC-06`, `EC-02`
- **Arquivos:** `collection/validacao.py`

**Descrição**

Comparador genérico declarado no YAML: `variavel_esquerda`, `operador`,
`variavel_direita`, `escopo` (compara dentro do mesmo item) e `mensagem` (a
redação vem do registro, não do desenvolvedor). O caso normativo é
`VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM`, por `MARGEM_ID`.

**Critérios de aceite**

- [x] Os cinco operadores (`<=`, `>=`, `<`, `>`, `==`) são suportados por um único caminho de código
- [x] A comparação ocorre estritamente dentro do mesmo item do `escopo` — itens diferentes nunca se comparam
- [x] O `ResultadoValidacao` de falha nomeia **os dois** campos envolvidos
- [x] A mensagem exibida vem do campo `mensagem` do registro; nenhuma redação de erro ao usuário está escrita no módulo

**Status:** `[x] concluída`

---

### `T-14` — Definir `OrigemOpcoes` e implementar `opcoes_efetivas`

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-08`, `AC-20`
- **Arquivos:** `collection/opcoes_do_motor.py`

**Descrição**

`OrigemOpcoes` com `fonte` (`REGISTRO` ou `SNAPSHOT`) e `campo_do_snapshot`.
Quando a fonte é `SNAPSHOT`, as opções são exatamente as que o motor produziu
para aquele caso; nenhuma opção fixa em código aparece fora dessa lista.
`B12.15`/`B12.16` são **casos de prova** do gerador — sua coleta efetiva está
fora de escopo (`OQ-12` da spec §9).

**Critérios de aceite**

- [x] `fonte=REGISTRO` devolve as opções do próprio registro, sem tocar no snapshot
- [x] `fonte=SNAPSHOT` com snapshot ausente devolve lista vazia e a pergunta não é exibível — nunca opções inventadas
- [x] Nenhum rótulo de opção aparece como literal no módulo
- [x] O módulo lê o campo do snapshot por nome, sem aritmética (`AC-42`)

**Status:** `[x] concluída`

---

### `T-15` — Implementar `collection/repeticao.py`, as fichas repetíveis

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-04`, `AC-04`
- **Arquivos:** `collection/repeticao.py`

**Descrição**

Instanciação de fichas por `DIVIDA_ID`, `VINCULO_ID`, `MARGEM_ID`, item de
despesa e `ACAO_ID`, com identificadores estáveis por caso. 115 das 291
perguntas são `REP`; nenhuma delas tem tratamento específico em código.

**Critérios de aceite**

- [x] Criar três fichas de dívida produz três `DIVIDA_ID` distintos e estáveis entre sessões
- [x] O conjunto de perguntas de uma ficha é derivado de `escopo_repeticao`, sem lista codificada por bloco
- [x] Responder a ficha 2 não altera nenhum campo das fichas 1 e 3 (`AC-04`)
- [x] Um item removido não reaproveita seu identificador para um item novo

**Status:** `[x] concluída`

---

### `T-16` — Implementar `collection/carga.py` com validação de esquema dos YAML

- **Tipo:** `Data`
- **Dependências:** `T-11`, `T-12`, `T-13`, `T-14`, `T-15`
- **Rastreia:** `RF-03`, `AC-36`, `AC-38`
- **Arquivos:** `collection/carga.py`, `collection/esquema-registros.json`

**Descrição**

Lê os YAML de `collection/registros/`, valida contra o esquema, recusa carga
incompleta e verifica unicidade de `ID` e `QUESTIONARIO_VERSION`. Carga inválida
levanta erro nomeando o registro culpado — nunca carrega parcialmente.

**Critérios de aceite**

- [x] Registro com campo obrigatório ausente faz a carga falhar nomeando o `ID` e o campo
- [x] `ID` duplicado entre arquivos faz a carga falhar nomeando os dois arquivos
- [x] `QUESTIONARIO_VERSION` é lido dos registros e exposto pela carga, nunca fixado em código
- [x] Condição, interpolação, validação cruzada e origem de opções do YAML são convertidas nos tipos de `T-10`, `T-12`, `T-13` e `T-14` — o YAML não vira `dict` solto

**Status:** `[x] concluída`

---

### `T-17` — Transcrever os registros dos Blocos 1 a 5 para `collection/registros/`

- **Tipo:** `Data`
- **Dependências:** `T-16`
- **Rastreia:** `RF-03`, `RF-04`, `RF-09`, `AC-04`, `AC-36`
- **Arquivos:** `collection/registros/bloco-01.yaml`, `collection/registros/bloco-02.yaml`, `collection/registros/bloco-03.yaml`, `collection/registros/bloco-04.yaml`, `collection/registros/bloco-05.yaml`

**Descrição**

As 195 perguntas da Etapa B como dado, transcritas da §11 da canônica caractere
por caractere: enunciado, tipo, obrigatoriedade, escopo de repetição, opções com
`rotulo` e `valor_interno`, `VARIAVEL_GRAVADA`, `admite_nao_sei` e
`salto_consequencia`. Um arquivo por bloco. **Transcrição, nunca paráfrase.**

**Critérios de aceite**

- [x] Os cinco arquivos carregam sem erro por `collection/carga.py`
- [x] O total de registros dos Blocos 1–5 é 195, e 55 dos 58 do Bloco 5 têm `REP`
- [x] `B5.FIM02` (`CONFIRMACAO_FIM_CADASTRO`) e `B2.13` (`AUTOPERCEPCAO_CONTROLE`) estão presentes com o domínio da canônica
- [x] Todo `valor_interno` é o da coluna "Valor interno / mapeamento" da §11, sem tradução
- [x] Todo `ID` é único e nenhum foi reaproveitado

**Status:** `[x] concluída`

---

### `T-18` — Transcrever os registros dos Blocos 7, 8, 10 e 11

- **Tipo:** `Data`
- **Dependências:** `T-16`
- **Rastreia:** `RF-09`, `RF-17`, `RF-18`, `RF-27`
- **Arquivos:** `collection/registros/bloco-07.yaml`, `collection/registros/bloco-08.yaml`, `collection/registros/bloco-10.yaml`, `collection/registros/bloco-11.yaml`

**Descrição**

Perguntas dos Blocos 7 (renegociação), 8 (troca), 10 (confirmação de ataque) e
11 (acompanhamento), incluindo `B7.05–B7.16`, `B8.01–B8.15`, `B10.C01`,
`B10.C01A`, `B11.01`, `B11.03-INF`/`-REN`/`-TRO`/`-ECO` e `B11.Q01–Q06`.
O escopo de repetição do Bloco 11 é `ACAO_ID`, **nunca** `DIVIDA_ID` (`AC-50`).

**Critérios de aceite**

- [x] Os quatro arquivos carregam sem erro por `collection/carga.py`
- [x] Perguntas do Bloco 11 vinculadas a ação declaram `escopo_repeticao: ACAO_ID`
- [x] `B11.Q01` declara o marcador `[Dxxx]` em `interpolacoes` e `B11.Q06` declara a interpolação de `PAGAMENTO_MENSAL_EFETIVO`
- [x] `B10.C01A` declara a validação cruzada `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO` referenciando o campo do snapshot
- [x] Nenhuma pergunta do Bloco 10 solicita ao aluno escolher qual dívida receberá o recurso (`AC-24`)

**Status:** `[x] concluída`

---

### `T-19` — Transcrever `B12.08`, `B12.15` e `B12.16` como casos de prova do gerador

- **Tipo:** `Data`
- **Dependências:** `T-16`
- **Rastreia:** `RF-05`, `RF-08`, `AC-20`, `AC-21`
- **Arquivos:** `collection/registros/bloco-12-casos-de-prova.yaml`

**Descrição**

Apenas as três perguntas que a spec §9 nomeia como casos de prova. `B12.08` é
literalmente um `CondicaoOu` de quatro termos no YAML; `B12.15` é uma pergunta
por regra proposta (repetição dirigida pelo motor); `B12.16` tem
`origem_opcoes.fonte = SNAPSHOT`. **O Bloco 12 não é implementado como fluxo.**

**Critérios de aceite**

- [x] `B12.08` tem `condicao_exibicao` com as quatro origens da spec (`RF-05`), sem nenhuma linha de código específica dela
- [x] `B12.16` declara `origem_opcoes.fonte: SNAPSHOT` com o campo do snapshot nomeado
- [x] `B12.15` declara repetição com escopo dirigido pelo motor, pelo mesmo mecanismo de `RF-04`
- [x] O arquivo declara em comentário que o Bloco 12 está fora de escopo como fluxo de coleta

**Status:** `[x] concluída`

---

### `T-20` — Testar o gerador: repetição, interpolação, validação cruzada, condicional e opções

- **Tipo:** `Test`
- **Dependências:** `T-17`, `T-18`, `T-19`
- **Rastreia:** `RF-04`, `RF-05`, `RF-06`, `RF-07`, `RF-08`, `AC-04`, `AC-05`, `AC-06`, `AC-20`, `AC-21`, `AC-36`, `AC-38`
- **Arquivos:** `tests/app_aluno/test_gerador.py`

**Descrição**

Os cinco casos difíceis da §15.1 da canônica, testados pelo comportamento
observável do gerador. Cada teste cita seu `AC-NN` no nome.

**Critérios de aceite**

- [x] `AC-04`: três dívidas produzem três fichas independentes; responder a ficha 2 não altera as fichas 1 e 3
- [x] `AC-05`: `B11.Q01` para `D003` exibe `D003` no lugar de `[Dxxx]`
- [x] `AC-06`: `VALOR_UTILIZADO_MARGEM = 1200` com `VALOR_TOTAL_MARGEM = 1000` é recusado, com mensagem, e nenhum dos dois é gravado
- [x] `AC-20`: opções de `B12.16` são as do snapshot; nenhuma opção fixa aparece fora dessa lista
- [x] `AC-21`: `B12.08` não é exibida com as quatro origens falsas e é exibida com qualquer uma verdadeira — os cinco casos testados
- [x] `AC-36`: editar o enunciado no YAML e recarregar muda o texto exibido, sem alterar `.py`
- [x] `AC-38`: teste que recusa `ID` reaproveitado entre versões do questionário

**Status:** `[x] concluída`

---

## Entrega 3 — Persistência desta feature: o schema `app_aluno`

### `T-21` — Escrever a migração `002_app_aluno.sql` com o schema dedicado

- **Tipo:** `Infra`
- **Dependências:** `T-04`
- **Rastreia:** `RF-01`, `RF-02`, `RF-10`, `RF-24`, `RF-30`, `RF-31`, `AC-43`
- **Arquivos:** `persistencia/supabase/migracoes/002_app_aluno.sql`

**Descrição**

`CREATE SCHEMA app_aluno` com as tabelas `contas`, `casos`, `respostas`,
`itens_repetidos`, `revisoes`, `consentimentos` e `eventos_caso`. Schema
separado de `motor_calculo` (NFR de segurança). **Nenhuma tabela de snapshot
aqui**: snapshot só entra por `RepositorioSnapshots.anexar` (`AC-43`).

**Critérios de aceite**

- [x] `respostas` tem PK `(CASO_ID, ID_PERGUNTA, item_id)` e colunas `valor_texto`, `valor_numerico numeric`, `valor_nao_sei boolean` — `numeric`, nunca `double precision`
- [x] `revisoes` tem `REVOKE UPDATE, DELETE ... FROM PUBLIC` e trigger de recusa, no mesmo padrão de `motor_calculo.snapshots`
- [x] `casos` tem `CASO_ID`, `conta_id`, `estado`, `DATA_REFERENCIA`, `QUESTIONARIO_VERSION`, `snapshot_raiz_id`, `snapshot_liberado_id`, `ultima_interacao_em`
- [x] Nenhuma tabela de snapshot é criada, e nenhum `INSERT` de snapshot existe no arquivo
- [x] O SQL contém apenas DDL e a função de recusa — nenhum gate, ranqueamento ou fórmula da §11 em `plpgsql`

**Status:** `[x] concluída`

---

### `T-22` — Implementar o repositório de respostas em `persistencia/app_aluno/`

- **Tipo:** `Data`
- **Dependências:** `T-21`
- **Rastreia:** `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-05`, `EC-10`
- **Arquivos:** `persistencia/app_aluno/__init__.py`, `persistencia/app_aluno/respostas.py`, `collection/respostas.py`

**Descrição**

`NaoSei`/`NAO_SEI`, `ValorResposta` e `Resposta` em `collection/respostas.py`
(§4.2 do plano); o adaptador de gravação/leitura em `persistencia/app_aluno/`.
`None` significa "não perguntado" e **nunca** "não sei". Valor numérico
trafega como `Decimal` via `numeric`, nunca `float`.

**Critérios de aceite**

- [x] `ValorResposta` não admite `float` — verificado por `mypy --strict`
- [x] Gravar `NAO_SEI` produz `valor_nao_sei = true` com `valor_numerico` e `valor_texto` nulos, distinguível de linha ausente — validado contra Postgres real (container efêmero desta tarefa, migrações `001`+`002` aplicadas)
- [x] Round-trip de `Decimal` de alta precisão preserva a string exata — validado contra Postgres real, comparação por `str()` exata
- [x] Falha de gravação propaga exceção; a função **nunca** devolve sucesso sem transação confirmada (`EC-05`) — validado por dublê de cursor (`psycopg.connect` monkeypatchado), sem depender de banco
- [x] Regravar a mesma `(CASO_ID, ID_PERGUNTA, item_id)` sobrescreve com a última confirmada, sem merge (`EC-10`) — validado contra Postgres real

**Status:** `[x] concluída`

---

### `T-23` — Implementar o repositório de casos e itens repetidos

- **Tipo:** `Data`
- **Dependências:** `T-21`
- **Rastreia:** `RF-01`, `RF-04`, `RF-31`, `EC-10`, `EC-14`
- **Arquivos:** `persistencia/app_aluno/casos.py`, `persistencia/app_aluno/itens.py`

**Descrição**

Leitura e gravação de `Caso` e dos itens repetidos. Transição de estado usa
`SELECT ... FOR UPDATE` na linha do caso, o que basta para impedir dois Bloco 6
simultâneos (§6 do plano). `ultima_interacao_em` é atualizada a cada interação.

**Critérios de aceite**

- [x] `CASO_ID` é identidade própria de `app_aluno`, gerada no cadastro, e `snapshot_raiz_id` é preenchido só quando o primeiro snapshot nasce (`OQ-11`) — validado contra Postgres real (container efêmero desta tarefa, migrações `001`+`002` aplicadas)
- [x] Transição de estado adquire `FOR UPDATE` na linha do caso antes de gravar — validado contra Postgres real: uma segunda conexão tentando o mesmo `SELECT ... FOR UPDATE` com `statement_timeout` curto expira por timeout enquanto a primeira transação está aberta
- [x] Duas transições concorrentes sobre o mesmo caso não produzem dois estados divergentes — validado contra Postgres real com DUAS THREADS/CONEXÕES de fato concorrentes: a segunda só adquire seu `FOR UPDATE` após o commit da primeira (serialização real, provada pela linha do tempo), e o caso termina em exatamente um dos dois estados escritos
- [x] `ultima_interacao_em` é gravada com o instante da interação e é legível na consulta de trilha — validado contra Postgres real, comparação por igualdade exata do `datetime` gravado vs. lido

**Status:** `[x] concluída`

---

### `T-24` — Implementar o adaptador de arquivo das tabelas desta feature

- **Tipo:** `Data`
- **Dependências:** `T-22`, `T-23`
- **Rastreia:** `RF-10`, `RF-01`
- **Arquivos:** `persistencia/app_aluno/arquivo.py`

**Descrição**

Adaptador local (JSON/JSONL) com a mesma interface do adaptador Postgres, para
que a suíte principal rode sem `DATABASE_URL` — mesmo precedente de
`persistencia/arquivo/` no slug do motor.

**Critérios de aceite**

- [x] O adaptador de arquivo e o de Postgres implementam o mesmo `Protocol`, verificado por `mypy --strict`
- [x] `pytest -m "not requer_banco"` roda a suíte inteira desta feature sem `DATABASE_URL`
- [x] `Decimal` é preservado exatamente no round-trip do adaptador de arquivo
- [x] Nenhum arquivo de `persistencia/arquivo/` (do motor) é modificado

**Status:** `[x] concluída`

---

### `T-25` — Testar a persistência desta feature contra Postgres real

- **Tipo:** `Test`
- **Dependências:** `T-24`
- **Rastreia:** `RF-10`, `RF-13`, `AC-02`, `EC-05`
- **Arquivos:** `tests/app_aluno/integracao/test_persistencia_app_aluno.py`

**Descrição**

Marcador `requer_banco`, pulado com mensagem explícita sem `DATABASE_URL`.
Paridade campo a campo entre o adaptador de arquivo e o Postgres, e round-trip
decimal exato.

**Critérios de aceite**

- [x] Paridade campo a campo arquivo × Postgres para `Resposta` e `Caso`, com `Decimal` exato
- [x] `AC-02`: a resposta está legível do banco antes de a próxima pergunta ser produzida
- [x] `EC-05`: com o banco indisponível, a gravação levanta erro e nada é reportado como salvo
- [x] Sem `DATABASE_URL`, os testes são pulados com mensagem explícita e a suíte fecha verde

**Status:** `[x] concluída`

---

### `T-26` — Testar que `UPDATE`/`DELETE` de snapshot é recusado por qualquer caminho (`AC-32`, `AC-43`)

- **Tipo:** `Test`
- **Dependências:** `T-21`
- **Rastreia:** `RF-19`, `AC-32`, `AC-43`
- **Arquivos:** `tests/app_aluno/integracao/test_snapshot_imutavel.py`, `tests/app_aluno/estatica/test_sem_escrita_de_snapshot.py`

**Descrição**

Duas travas. Estática: nenhum `INSERT`, `UPDATE` ou `DELETE` sobre tabela de
snapshot aparece em `app/`, `collection/`, `report/` ou
`persistencia/app_aluno/`. Integração: `UPDATE`/`DELETE` real sobre
`motor_calculo.snapshots` é recusado pelo banco.

**Critérios de aceite**

- [x] `AC-43`: o teste estático falha se qualquer SQL desta feature mencionar a tabela de snapshots com verbo de mutação
- [x] `AC-32`: `UPDATE` e `DELETE` reais sobre `motor_calculo.snapshots` são recusados, e o snapshot permanece inalterado
- [x] O teste estático cobre também `002_app_aluno.sql`
- [x] O teste de integração é `requer_banco` e pulado com mensagem sem `DATABASE_URL`

**Status:** `[x] concluída`

---

### `T-27` — Escrever o teste estático da fronteira `Decimal` única (`RF-13`)

- **Tipo:** `Test`
- **Dependências:** `T-05`
- **Rastreia:** `RF-13`, `AC-09`, `EC-01`
- **Arquivos:** `tests/app_aluno/estatica/test_fronteira_decimal_unica.py`

**Descrição**

AST de `app/`, `collection/`, `report/` e `persistencia/app_aluno/`: chamada a
`Decimal(...)` ou a `engine.precisao.dinheiro(...)` sobre entrada de usuário só
pode aparecer em `app/montagem/conversao.py`. Escrito antes do módulo existir,
para que ele nasça no lugar certo.

**Critérios de aceite**

- [x] O teste falha se `Decimal(...)` for construído em qualquer arquivo dessas pastas que não seja `app/montagem/conversao.py`
- [x] O teste falha se `float(...)` for chamado sobre qualquer valor em qualquer dessas pastas
- [x] As exceções permitidas (desserialização do adaptador de persistência) estão declaradas explicitamente no teste
- [x] O teste cita `RF-13` no nome e passa com as pastas ainda vazias

**Status:** `[x] concluída`

---

## Entrega 4 — O aluno entra: conta, consentimento e isolamento por caso

### `T-28` — Implementar hash de senha com Argon2id

- **Tipo:** `Infra`
- **Dependências:** `T-03`, `T-21`
- **Rastreia:** `RF-02`
- **Arquivos:** `app/http/senhas.py`, `persistencia/app_aluno/contas.py`

**Descrição**

Hash e verificação por `argon2-cffi`, com os parâmetros de custo declarados em
um só lugar. Senha nunca armazenada em texto claro nem registrada em log (NFR de
segurança).

**Critérios de aceite**

- [x] A senha em texto claro não aparece em nenhuma coluna, log ou mensagem de erro
- [x] Dois hashes da mesma senha diferem (salt), e a verificação aceita ambos
- [x] Verificação de senha errada devolve falso sem levantar exceção que distinga "conta inexistente" de "senha errada"
- [x] Os parâmetros de custo do Argon2id estão declarados numa constante única do módulo

**Status:** `[x] concluída`

---

### `T-29` — Montar a aplicação FastAPI com sessão assinada

- **Tipo:** `Infra`
- **Dependências:** `T-03`, `T-04`
- **Rastreia:** `RF-02`, `AC-03`
- **Arquivos:** `app/http/aplicacao.py`, `app/http/sessao.py`

**Descrição**

`FastAPI` com `SessionMiddleware` (`itsdangerous`), cookie `HttpOnly`, `Secure`,
`SameSite=Lax`. A sessão **nunca** contém dado financeiro nem autoriza acesso
por si só: ela só carrega a identidade da conta.

**Critérios de aceite**

- [x] O cookie de sessão é assinado e traz as três flags (`HttpOnly`, `Secure`, `SameSite=Lax`)
- [x] A sessão carrega apenas o identificador da conta — nenhum valor monetário, `CASO_ID` de terceiros ou papel autorizador
- [x] A chave de assinatura vem de variável de ambiente, nunca de literal no código
- [x] A aplicação sobe e responde a uma rota de saúde sem acesso a banco

**Status:** `[x] concluída`

---

### `T-30` — Implementar as rotas de cadastro, login e logout

- **Tipo:** `UI`
- **Dependências:** `T-28`, `T-29`, `T-23`
- **Rastreia:** `RF-02`, `AC-03`
- **Arquivos:** `app/http/rotas_conta.py`, `report/templates/conta/` — mais
  `persistencia/app_aluno/cadastro.py` (novo: a transação atômica de
  conta+caso precisa ficar em `persistencia/`, não em `app/http/`, para não
  acionar o limiar de `tests/app_aluno/estatica/test_sem_conteudo_de_
  questionario_no_codigo.py`, T-08/`AC-37`, sobre as strings de SQL),
  `app/http/aplicacao.py` (edição mínima: `include_router` do novo router) e
  `pyproject.toml` (`jinja2` explícita no extra `app` — já era a 4ª
  dependência decidida no plano §2, mas não é transitiva de `fastapi` puro
  como T-03 presumira; sem isso `Jinja2Templates` falha em runtime)

**Descrição**

Cadastro cria a conta e um `Caso` em `CADASTRADO`. Login autentica por senha e
abre sessão. Logout encerra. Formulário HTML nativo, funcional sem JS.

**Critérios de aceite**

- [x] Cadastro cria conta e caso, e o caso nasce no estado `CADASTRADO`
- [x] Login com senha correta abre sessão; com senha errada não abre e a mensagem não distingue conta inexistente de senha errada
- [x] Logout invalida a sessão: a requisição seguinte a uma rota autenticada é recusada
- [x] Os três formulários submetem com JavaScript desabilitado

**Status:** `[x] concluída`

---

### `T-31` — Implementar a verificação de isolamento por `CASO_ID` no servidor

- **Tipo:** `Infra`
- **Dependências:** `T-29`, `T-23`
- **Rastreia:** `RF-02`, `AC-03`
- **Arquivos:** `app/http/isolamento.py`

**Descrição**

Dependência do FastAPI que, a cada requisição que carrega um `CASO_ID`, verifica
**no servidor** se a sessão possui aquele caso e devolve 404 caso contrário
(§5.1 do plano, passo 1). Nunca se confia no cookie nem na interface.

**Critérios de aceite**

- [x] Toda rota que recebe `CASO_ID` declara a dependência de isolamento — verificado por um teste que enumera as rotas registradas
- [x] Caso de outra conta devolve `404`, não `403` — a existência do caso não vaza
- [x] A verificação consulta o banco a cada requisição, sem cache de autorização em sessão
- [x] Requisição sem sessão a rota autenticada é recusada antes de qualquer leitura de dado do caso

**Status:** `[x] concluída`

---

### `T-32` — Testar o isolamento enumerando todas as rotas (`AC-03`)

- **Tipo:** `Test`
- **Dependências:** `T-31`, `T-30`
- **Rastreia:** `RF-02`, `AC-03`
- **Arquivos:** `tests/app_aluno/e2e/test_isolamento_por_caso.py`

**Descrição**

Teste que **enumera** as rotas registradas na aplicação — não uma amostra — e,
para cada uma que aceita `CASO_ID`, verifica que uma sessão do caso A não
alcança nada do caso B.

**Critérios de aceite**

- [x] O teste percorre `app.routes` e não uma lista escrita à mão — rota nova sem isolamento quebra o teste automaticamente
- [x] Sessão do caso A recebe `404` em toda rota do caso B: respostas, plano, PDF e fila — provado com duas sessões reais (cadastro de verdade via `TestClient`) sobre rotas de exemplo nomeadas como os domínios futuros, já que nenhuma rota real de respostas/plano/PDF/fila existe hoje (Entregas 5-8, fora do escopo desta tarefa); a auditoria por enumeração roda também sobre a app real de hoje e fica pronta para acusar qualquer rota futura sem isolamento automaticamente (prova ad hoc feita e confirmada nesta implementação)
- [x] O teste cobre também rotas de leitura de item repetido por `DIVIDA_ID`/`MARGEM_ID`
- [x] O teste cita `AC-03` no nome

**Status:** `[x] concluída`

---

### `T-33` — Implementar a máquina de estados do caso

- **Tipo:** `Data`
- **Dependências:** `T-23`
- **Rastreia:** `RF-01`, `AC-33`, `AC-34`
- **Arquivos:** `app/casos/maquina.py`

**Descrição**

`ESTADO_CASO` com os doze membros do §4.3 do plano, `Caso`, `Transicao` e a
tabela de transições nomeadas com guardas. Toda transição é declarada: uma
transição não declarada é **recusada**, nunca tolerada.

**Critérios de aceite**

- [x] `ESTADO_CASO` tem exatamente os doze membros do plano §4.3, com os nomes caractere por caractere
- [x] Toda transição declarada tem `de`, `para`, `gatilho` nomeado e `guarda` opcional
- [x] Transição não declarada levanta erro nomeando origem e destino — nunca é silenciosamente aceita
- [x] Reabertura de pergunta **não** é estado: não existe membro de `ESTADO_CASO` para "reaberto"

**Status:** `[x] concluída`

---

### `T-34` — Testar a máquina de estados: toda transição nomeada, nenhuma implícita

- **Tipo:** `Test`
- **Dependências:** `T-33`
- **Rastreia:** `RF-01`
- **Arquivos:** `tests/app_aluno/test_maquina_de_estados.py`

**Descrição**

O caminho completo do §7.1 do plano é percorrido por transições declaradas, e
qualquer par (de, para) fora da tabela é recusado.

**Critérios de aceite**

- [x] O caminho `CADASTRADO → ... → ACOMPANHAMENTO → CALCULANDO` é percorrível apenas por transições declaradas
- [x] Para todo par (de, para) não declarado, a transição é recusada — teste exaustivo sobre o produto cartesiano dos estados
- [x] `ERRO_DE_CALCULO` volta ao estado anterior por transição nomeada (`EC-06`)
- [x] `REPROVADO_EM_REVISAO` é alcançável a partir de `AGUARDANDO_REVISAO` e não a partir de `PLANO_LIBERADO` (`EC-12`)

**Status:** `[x] concluída`

---

### `T-35` — Implementar os pontos de encaixe de consentimento (`PEND-01`)

- **Tipo:** `Data`
- **Dependências:** `T-21`, `T-23`
- **Rastreia:** `RF-30`, `AC-39`
- **Dependência externa:** `PEND-01` (textos de consentimento, retenção e exclusão)
- **Arquivos:** `app/consentimento/registro.py`, `persistencia/app_aluno/consentimentos.py`

**Descrição**

Registro de consentimento com versão do texto, aceite e data. **Os textos são
insumo externo de `PEND-01`** — esta tarefa entrega o encaixe, nunca a redação.
O ponto de retenção e o de exclusão existem como encaixes declarados.

**Critérios de aceite**

- [x] O registro grava versão do texto, aceite e data, e é consultável por caso
- [x] Nenhum texto jurídico está escrito em `.py` — a redação vem de arquivo de conteúdo externo
- [x] Os pontos de encaixe de retenção e de exclusão existem, documentados como dependentes de `PEND-01` (`EC-13`)
- [x] O módulo não decide política: ausência do texto externo bloqueia o fluxo em vez de assumir um padrão

**Status:** `[x] concluída`

---

## Entrega 5 — Coleta multissessão: responder, salvar, retomar

### `T-36` — Implementar a guarda "sem consentimento, nenhuma resposta é gravada"

- **Tipo:** `Infra`
- **Dependências:** `T-35`, `T-33`, `T-31`
- **Rastreia:** `RF-30`, `AC-39`
- **Arquivos:** `app/casos/maquina.py`, `app/http/rotas_consentimento.py`

**Descrição**

A transição `CADASTRADO → CONSENTIMENTO_REGISTRADO` é a única porta para
`COLETA_INICIAL`. A guarda vive na máquina de estados, não numa checagem de
rota — para que nenhuma rota nova possa contorná-la.

**Critérios de aceite**

- [x] `AC-39`: tentar gravar resposta com o caso em `CADASTRADO` é recusado e nada é persistido
- [x] A guarda é uma transição nomeada da máquina, verificável sem subir a aplicação HTTP
- [x] A rota de consentimento registra o aceite e dispara a transição num único caminho
- [x] Nenhuma resposta é gravada antes do registro de consentimento, por nenhuma rota

**Status:** `[x] concluída`

---

### `T-37` — Testar cadastro, consentimento e recusa de gravação sem consentimento

- **Tipo:** `Test`
- **Dependências:** `T-36`, `T-30`
- **Rastreia:** `RF-02`, `RF-30`, `AC-39`
- **Arquivos:** `tests/app_aluno/test_consentimento.py`

**Descrição**

Cobre `AC-39` pelo comportamento observável: caso sem consentimento, tentativa
de gravar resposta, verificação de que a tabela `respostas` continua vazia.

**Critérios de aceite**

- [x] `AC-39`: com o caso sem consentimento, nenhuma linha aparece em `respostas` após a tentativa
- [x] Após o registro de consentimento, a mesma gravação é aceita
- [x] O registro de consentimento guarda autor (o caso), versão do texto e data
- [x] O teste cita `AC-39` no nome

**Status:** `[x] concluída`

---

### `T-38` — Implementar a fronteira `Decimal` única em `app/montagem/conversao.py`

- **Tipo:** `Data`
- **Dependências:** `T-27`
- **Rastreia:** `RF-13`, `AC-09`, `AC-10`, `EC-01`
- **Arquivos:** `app/montagem/conversao.py`

**Descrição**

O **único** módulo desta feature autorizado a construir `Dinheiro`/`Taxa`.
Normaliza separadores da string do formulário e chama
`engine.precisao.dinheiro()` — `str` direto para `Decimal`, jamais `float`.
Entrada inválida é **recusada**: nada é gravado e nunca há coerção a `0`.

**Critérios de aceite**

- [x] `"1234,56"` produz exatamente `Decimal("1234.56")` (`AC-10`)
- [x] `"mil reais"`, `"1.2.3"` e string vazia são recusados com erro tipado, sem coerção a `0` (`EC-01`)
- [x] `float` nunca aparece no caminho: a função não aceita `float` como entrada nem o produz — verificado por `mypy --strict`
- [x] A conversão de taxa é separada da de moeda, e ambas passam pelos construtores de `engine.precisao`
- [x] `T-27` (fronteira única) passa com este módulo presente

**Status:** `[x] concluída`

---

### `T-39` — Testar a fronteira `Decimal` com Hypothesis (`AC-09`, `AC-10`, `EC-01`)

- **Tipo:** `Test`
- **Dependências:** `T-38`
- **Rastreia:** `RF-13`, `AC-09`, `AC-10`, `EC-01`
- **Arquivos:** `tests/app_aluno/test_conversao_decimal.py`

**Descrição**

Casos exatos mais a propriedade universal *"nenhuma entrada aceita produz
`float` em nenhum ponto"*, com `derandomize=True` como no slug do motor.

**Critérios de aceite**

- [x] `AC-10`: `"1234,56"` → `Decimal("1234.56")`, comparado com igualdade exata, nunca com tolerância
- [x] `AC-09`: um `EstadoFinanceiro` montado a partir de valores convertidos não levanta o `TypeError` de `_recusar_float`
- [x] Propriedade Hypothesis: para toda string aceita, o resultado é `Decimal` e nenhum `float` aparece no caminho (`derandomize=True`)
- [x] `EC-01`: para toda string recusada, nenhuma gravação ocorre e o valor não é coagido a `0`

**Status:** `[x] concluída`

---

### `T-40` — Implementar `collection/materialidade.py` por introspecção do contrato

- **Tipo:** `Data`
- **Dependências:** `T-09`
- **Rastreia:** `RF-11`, `RF-34`, `AC-41`
- **Arquivos:** `collection/materialidade.py`

**Descrição**

`campos_materiais()` deriva por `typing.get_type_hints` sobre `Divida` e
`EstadoFinanceiro`: material é o campo anotado `DinheiroTalvez`/`TaxaTalvez`/
`int | Desconhecido`. **Zero regra de negócio transcrita** — a aplicação não
reimplementa `INFORMACAO_PENDENTE` (`RF-34`).

**Critérios de aceite**

- [x] `campos_materiais()` é derivado por introspecção, sem nenhuma lista de nomes escrita à mão
- [x] Um campo anotado `Dinheiro` puro **não** é material; um anotado `DinheiroTalvez` é
- [x] A introspecção roda uma vez na carga, não a cada resposta
- [x] O módulo não contém nenhum gate, limiar ou regra do motor — `T-06` e `T-08` passam sobre ele

**Status:** `[x] concluída`

---

### `T-41` — Implementar o aviso de materialidade na hora (`OQ-08`)

- **Tipo:** `UI`
- **Dependências:** `T-40`
- **Rastreia:** `RF-11`
- **Arquivos:** `collection/materialidade.py`, `report/templates/coleta/aviso_materialidade.html`

**Descrição**

`AvisoMaterialidade` e `avaliar_ao_responder`. A redação é insumo do registro,
não do desenvolvedor, e diz **"pode deixar seu plano provisório"** — nunca "vai
deixar". Quem decide o fato é o motor (Gate 1, fallback de taxa, `ORDEM_STATUS`).

**Critérios de aceite**

- [x] `NAO_SEI` em campo material produz aviso; em campo não material, não produz
- [x] O texto do aviso vem do registro/template e usa "pode", nunca "vai" ou "será"
- [x] O aviso é exibido na mesma resposta HTTP que confirma a gravação, sem recarregar a página — **a PEÇA está pronta** (`avaliar_ao_responder` + template), mas a integração HTTP real com `app/http/rotas_coleta.py` é `T-42` (ainda não implementada); aqui o critério foi verificado pela via possível nesta tarefa: renderização Jinja2 direta do template a partir de um `AvisoMaterialidade`, provando que ele produz o fragmento HTML pronto para ser devolvido na mesma resposta (HTMX) que `T-42` vai montar
- [x] O aviso é vinculado ao campo e anunciado a leitor de tela (`aria-describedby`) — o template entrega o `id` estável (`aviso-materialidade-{VARIAVEL_GRAVADA}`) e `role="status"`; o `aria-describedby` no `<input>` propriamente dito é somado por `T-43` (renderização da pergunta), que ainda não existe

**Status:** `[x] concluída`

---

### `T-42` — Implementar a rota de resposta com a sequência de sete passos do §5.1

- **Tipo:** `UI`
- **Dependências:** `T-31`, `T-33`, `T-36`, `T-38`, `T-22`, `T-13`, `T-41`
- **Rastreia:** `RF-05`, `RF-07`, `RF-10`, `RF-11`, `RF-13`, `AC-02`, `EC-01`, `EC-02`, `EC-05`
- **Arquivos:** `app/http/rotas_coleta.py`

**Descrição**

Isolamento → registro carregado por `ID` e verificação de que a pergunta está de
fato aberta → `NAO_SEI` pula a conversão → conversão decimal → validação cruzada
→ gravação com transação confirmada → aviso de materialidade. Só então a próxima
pergunta aparece.

**Critérios de aceite**

- [x] `AC-02`: a resposta está persistida antes de a próxima pergunta ser devolvida — encerrar o processo imediatamente depois não perde a resposta
- [x] Responder pergunta cuja condição de exibição é falsa é recusado, sem gravação
- [x] `NAO_SEI` grava sem passar pela conversão decimal
- [x] `EC-01` e `EC-02` recusam sem gravar, com a mensagem apontando o campo (ou os dois campos)
- [x] `EC-05`: falha de banco devolve "não foi possível salvar" e **não** avança para a próxima pergunta

**Status:** `[x] concluída`

---

### `T-43` — Renderizar a pergunta a partir do registro com HTMX

- **Tipo:** `UI`
- **Dependências:** `T-42`, `T-16`
- **Rastreia:** `RF-03`, `RF-06`, `AC-05`, `AC-36`
- **Arquivos:** `report/templates/coleta/pergunta.html`, `app/http/renderizacao.py`, `app/http/estaticos/htmx.min.js`

**Descrição**

Um template por `TipoResposta`, alimentado pelo registro. HTMX faz uma
requisição por resposta, mantendo **o servidor como única autoridade** sobre
condicional e materialidade. Sem JS, o formulário ainda submete.

**Critérios de aceite**

- [x] Nenhum enunciado, opção ou condição aparece nos templates como literal — tudo vem do registro
- [x] Os nove `TipoResposta` têm renderização, cada um com rótulo associado ao campo
- [x] Com JavaScript desabilitado, a resposta ainda é submetida e gravada (progressive enhancement)
- [x] A avaliação da condição de exibição ocorre no servidor; nenhuma regra de exibição é duplicada em JS

**Status:** `[x] concluída`

**Nota sobre `app/http/estaticos/htmx.min.js`:** arquivo REAL da biblioteca
(não um placeholder), baixado nesta tarefa do mirror npm oficial
`unpkg.com/htmx.org@2.0.10/dist/htmx.min.js` — versão `2.0.10`, 51.238 bytes,
licença Zero-Clause BSD (0BSD, permissiva, sem obrigação de atribuição).
Detalhes e procedimento de atualização em `app/http/estaticos/README.md`. O
plano (§2) só cita "HTMX (~14 KB, sem build)" sem fixar versão exata; nenhum
outro artefato SDD do projeto referencia uma versão específica.

---

### `T-44` — Implementar a obrigatoriedade `OBR`/`COND`/`OPT`/`REP` no avanço da coleta

- **Tipo:** `UI`
- **Dependências:** `T-43`
- **Rastreia:** `RF-09`, `RF-11`, `AC-11`
- **Arquivos:** `app/casos/progresso.py`, `app/http/rotas_coleta.py`

**Descrição**

Campo `OBR` que não admite "não sei" e ficou em branco mantém a pergunta
pendente e a coleta não avança. A obrigatoriedade vem do registro; não há lista
de campos obrigatórios em código.

**Critérios de aceite**

- [x] `AC-11`: campo `OBR` sem `admite_nao_sei` deixado em branco impede o avanço e a pergunta permanece pendente
- [x] Campo `OPT` em branco não impede o avanço
- [x] Campo `COND` só é exigido quando sua condição de exibição é verdadeira
- [x] Nenhum `ID` de pergunta aparece em código como "obrigatório" — a origem é o registro

**Status:** `[x] concluída`

---

### `T-45` — Implementar a retomada na primeira pergunta não respondida

- **Tipo:** `UI`
- **Dependências:** `T-44`
- **Rastreia:** `RF-10`, `AC-01`
- **Arquivos:** `app/casos/progresso.py`

**Descrição**

Dado o conjunto de respostas e o grafo condicional avaliado, determinar a
primeira pergunta aberta e não respondida. Nenhum campo já respondido é pedido
de novo.

**Critérios de aceite**

- [x] `AC-01`: com Blocos 1–3 respondidos, a retomada aponta a primeira pergunta não respondida do Bloco 4
- [x] A retomada funciona de outro dispositivo, com sessão nova
- [x] Pergunta cuja condição virou falsa depois de respondida não é reexibida nem apagada
- [x] A retomada respeita a ordem dos blocos e o escopo de repetição dos itens já criados

**Status:** `[x] concluída`

---

### `T-46` — Testar a retomada multissessão e a persistência a cada resposta

- **Tipo:** `Test`
- **Dependências:** `T-45`
- **Rastreia:** `RF-10`, `AC-01`, `AC-02`
- **Arquivos:** `tests/app_aluno/e2e/test_retomada.py`

**Descrição**

`US-01` ponta a ponta: responder, encerrar a sessão, autenticar de outro cliente
e verificar que tudo está lá e que a coleta retoma no ponto certo.

**Critérios de aceite**

- [x] `AC-01`: cliente novo, sessão nova, todas as respostas presentes e retomada no ponto correto
- [x] `AC-02`: matar o cliente logo após a confirmação da resposta não perde a resposta
- [x] Nenhum campo já respondido é reapresentado como pendente
- [x] Os testes citam `AC-01` e `AC-02` nos nomes

**Status:** `[x] concluída`

---

### `T-47` — Implementar a interface do Bloco 5 a 360 px com a ficha repetível

- **Tipo:** `UI`
- **Dependências:** `T-43`, `T-15`
- **Rastreia:** `RF-04`, `AC-04`
- **Arquivos:** `report/templates/coleta/ficha_repetivel.html`, `app/http/estaticos/estilo.css`

**Descrição**

Adicionar, listar e editar fichas de dívida, vínculo e margem na largura da
persona (servidor com o celular na mão e o contracheque ao lado). 55 das 58
perguntas do Bloco 5 são `REP`.

**Critérios de aceite**

- [x] A ficha é utilizável a 360 px de largura, sem rolagem horizontal — verificado por ausência de `width` fixo acima de 360px e de tabela em HTML/CSS (`tests/app_aluno/test_ficha_repetivel.py`, `tests/app_aluno/estatica/test_css_360px.py`); validação visual completa (zoom real de navegador, proporções físicas de tela) fica para revisão manual/T-48 (`axe`), documentado no próprio template e CSS
- [x] Adicionar uma ficha cria um item com identificador estável e não altera as demais — a ficha exibe o `item_id` recebido de `collection/repeticao.py` (T-15, já testado) sem gerá-lo nem alterá-lo; o formulário de "adicionar ficha" é uma submissão independente que não repete nenhum campo das fichas existentes
- [x] Cada campo tem rótulo associado e é alcançável por teclado — cada campo de pergunta reutiliza `pergunta.html` (T-43, já garante `label for`/`id`); o campo do formulário de adicionar ficha tem `label for` próprio; `<details>`/`<summary>` são nativamente focáveis, sem `tabindex` negativo
- [x] A lista de fichas mostra quais estão completas e quais têm pendência, sem calcular nada — o template só lê o booleano `ficha.completa`, fornecido de fora a partir do resultado real de `app/casos/progresso.py::pendencias_obrigatorias` (T-40/T-44); nenhuma obrigatoriedade é recalculada no template (auditado por teste que varre o arquivo por `Obrigatoriedade`/`pendencias_obrigatorias`)

**Status:** `[x] concluída`

---

### `T-48` — Verificar acessibilidade automatizada do fluxo de coleta

- **Tipo:** `Test`
- **Dependências:** `T-47`, `T-44`
- **Rastreia:** `RF-07`, `RF-09`
- **Arquivos:** `tests/app_aluno/e2e/test_acessibilidade_coleta.py`, `docs/checklist-acessibilidade.md`

**Descrição**

Automação (`axe`) sobre contraste, rótulo e ordem de foco no fluxo de coleta. A
navegação com leitor de tela real fica como checklist manual registrado — o
plano §9 declara por que não é automatizável.

**Critérios de aceite**

- [x] `axe` não reporta violação de contraste, rótulo ou ordem de foco nas telas de coleta e de ficha repetível — **limitação declarada honestamente**: este ambiente não tem Chromium/Playwright/Selenium disponível (nenhum dos dois está no plano desta feature, e `pyproject.toml` não os declara); `axe-core` real, que audita o DOM de um navegador renderizado, não pode rodar aqui. `tests/app_aluno/e2e/test_acessibilidade_coleta.py` implementa um **substituto estático parcial**, documentado como tal no próprio arquivo: contraste recalculado pela fórmula de luminância relativa da WCAG 2.1 sobre as cores reais de `app/http/estaticos/estilo.css` (`.ficha-status-completa`, `.ficha-status-pendente`, `.aviso-materialidade`, todas ≥ 4.5:1 AA); rótulo verificado por `label for`/`id` sobre o HTML real do Bloco 5 (registros de produção via `collection/carga.py`) e da ficha repetível; ordem de foco verificada por ausência de `tabindex` fora de `0`. A auditoria completa por `axe-core` real sobre browser fica registrada em `docs/checklist-acessibilidade.md`, seção "Trabalho de infraestrutura futura"
- [x] Mensagem de erro de validação cruzada é vinculada ao campo e anunciada (`aria-describedby`/`role=alert`) — `erro_resposta.html` (T-42) já tinha `role="alert"`; `report/templates/coleta/pergunta.html` foi ajustado (dentro do escopo deste próprio critério) para que o campo referencie, via `aria-describedby`, o `id="resultado-{ID}"` — o mesmo `hx-target` onde `erro_resposta.html`/`confirmacao_resposta.html` são inseridos por HTMX — além do aviso de materialidade já vinculado por T-43 (os dois ids convivem em `aria-describedby`, lista separada por espaço). Provado com o caso normativo real `VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM` (`B3.S06C`)
- [x] O checklist manual existe, com os itens que a automação não cobre, e está versionado — `docs/checklist-acessibilidade.md` (pasta `docs/` criada nesta tarefa, não existia antes), com itens de navegação por teclado ponta a ponta, leitor de tela real (NVDA/VoiceOver/TalkBack), zoom/360px em navegador real e contraste em percepção visual real (inclusive daltonismo), mais o registro do porquê (`plans/app-aluno.plan.md` §9) e do que fica como trabalho de infraestrutura futura
- [x] O teste roda sob o marcador `e2e` e não bloqueia a suíte padrão — `pytestmark = pytest.mark.e2e`, mesmo padrão de `test_retomada.py`/`test_rota_resposta.py`; `pytest -m "not requer_banco and not e2e"` deseleciona os 9 testes (verificado); `pytest -q` (comando `test` do config) roda e passa os 9 (não dependem de banco, mesmo comportamento já existente de T-32 `test_isolamento_por_caso.py`) sem bloquear a suíte

**Status:** `[x] concluída`

---

## Entrega 6 — Bloco 6: da coleta ao snapshot, sem calcular nada

### `T-49` — Montar `Divida` a partir das respostas do Bloco 5

- **Tipo:** `Data`
- **Dependências:** `T-38`, `T-22`, `T-17`
- **Rastreia:** `RF-12`, `RF-14`, `AC-08`
- **Arquivos:** `app/montagem/estado.py`

**Descrição**

Cada ficha repetível vira uma `Divida` com todos os campos do contrato real de
`engine/estado.py`. `NAO_SEI` vira `DESCONHECIDO`, **nunca** `0`, `None`, média
ou estimativa. `CUSTO_SEGURO` continua separado da parcela.

**Critérios de aceite**

- [x] Todos os campos de `Divida` são preenchidos a partir de resposta ou de `DESCONHECIDO` — nenhum default silencioso
- [x] `AC-08`: "não sei" em saldo e pagamento mensal produz `DESCONHECIDO` nos dois, nunca `0`
- [x] `PAGAMENTO_MENSAL_EFETIVO = 0` declarado pelo aluno é preservado como `0`, distinto de `DESCONHECIDO`
- [x] `mypy --strict` obriga tratar `DESCONHECIDO` em todo `DinheiroTalvez`/`TaxaTalvez` — esquecer não compila

**Status:** `[x] concluída`

---

### `T-50` — Montar `PerfilComportamental` e `SinaisComportamentais`

- **Tipo:** `Data`
- **Dependências:** `T-49`, `T-17`
- **Rastreia:** `RF-14`, `AC-13`
- **Arquivos:** `app/montagem/estado.py`

**Descrição**

As 8 variáveis do Bloco 2 em `PerfilComportamental`, os 10 campos de
`SinaisComportamentais` e `AUTOPERCEPCAO_CONTROLE` (`B2.13`). Os enums são os de
`engine/estado.py`; a aplicação mapeia o `valor_interno` do registro para o
membro, sem derivar nada.

**Critérios de aceite**

- [x] `AC-13`: as 8 variáveis de `PerfilComportamental` e os 10 campos de `SinaisComportamentais` estão preenchidos
- [x] `AUTOPERCEPCAO_CONTROLE` vem de `B2.13` e admite `DESCONHECIDO`
- [x] O mapeamento resposta → membro de enum é por `valor_interno` do registro, sem `if` por pergunta
- [x] Nenhuma derivação comportamental (`NIVEL_CONTROLE`, `RISCO_RECAIDA`) é calculada aqui — são do motor

**Status:** `[x] concluída`

**Nota de lacuna descoberta (não desta tarefa):** `NECESSIDADE_VITORIA`
(`B9.02`) e `HISTORICO_ABANDONO` (`B9.04`), 2 dos 10 campos de
`SinaisComportamentais`, pertencem ao **Bloco 9**, que nenhuma tarefa
concluída deste backlog transcreveu (`T-17` cobriu Blocos 1–5; `T-18`,
Blocos 7/8/10/11; `T-19`, casos de prova do Bloco 12; não existe
`collection/registros/bloco-09.yaml`). Mesmo padrão de decisão documentada
de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (T-49): os dois campos são fixados no
valor neutro documentado (`DESCONHECIDO`/`SimNaoTalvez.TALVEZ`), nunca
inventados por estimativa — ver docstring de `app/montagem/estado.py`.
Transcrever o Bloco 9 é próxima tarefa de backlog (fora do escopo de T-50).

**Resolvida por `T-99`:** `collection/registros/bloco-09.yaml` transcreveu
`B9.02`/`B9.04` e `montar_sinais_comportamentais` passou a ler os dois
campos do registro real — ver `T-99` abaixo.

---

### `T-51` — Montar `EstadoFinanceiro` com `DATA_REFERENCIA` explícita

- **Tipo:** `Data`
- **Dependências:** `T-50`, `T-33`, `T-99`
- **Rastreia:** `RF-14`, `AC-18`
- **Arquivos:** `app/montagem/estado.py`, `tests/app_aluno/estatica/test_fronteira_import_engine.py` (ampliação da allowlist com `engine.estado.TIPO_RENDA`, mesmo precedente de `TIPO_DIVIDA`/T-49), `tests/app_aluno/estatica/test_sem_relogio_em_montagem.py` (novo), `tests/app_aluno/test_montagem_estado_financeiro.py` (novo)

**Descrição**

O `EstadoFinanceiro` completo, com `DATA_REFERENCIA` vindo do `Caso` — **nunca**
de `date.today()`. É o que faz recalcular o mesmo caso com a mesma
`DATA_REFERENCIA` produzir o mesmo `SNAPSHOT_ID`.

**Critérios de aceite**

- [x] `AC-18`: `DATA_REFERENCIA` vem do `Caso`; nenhuma chamada a `date.today()`/`datetime.now()` existe em `app/montagem/`
- [x] Todos os campos obrigatórios de `EstadoFinanceiro` são preenchidos a partir de resposta ou `DESCONHECIDO`
- [x] Montar duas vezes o mesmo conjunto de respostas produz `EstadoFinanceiro` igual campo a campo
- [x] Um teste estático recusa `date.today()` e `datetime.now()` em `app/montagem/`

**Status:** `[x] concluída`

**Lacunas documentadas (não inventadas, ver docstring de `montar_estado_
financeiro` em `app/montagem/estado.py`):**

- `RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS`,
  `DESPESAS_NAO_MENSAIS_NORMALIZADAS`: a canônica (`piq-app-spec.md`, linha
  1899) as lista como "derivadas pelo motor, nunca perguntadas" — não têm
  `VARIAVEL_GRAVADA` própria no Bloco 3, e agregá-las corretamente exige
  somar N fichas repetíveis de despesa, tratar renda variável (piso vs.
  média) e normalizar periodicidade de despesas não-mensais — nenhuma dessas
  regras estava normatizada com precisão suficiente em nenhum artefato SDD
  disponível **no momento desta tarefa**. Recebidas como parâmetro externo
  explícito de `montar_estado_financeiro`. **Atualização:** `OQ-16` foi
  respondida (fórmula fechada, decisão do usuário) e `T-103` (tarefa nova)
  implementa o cálculo real, removendo o parâmetro externo.
- `INVENTARIO_COMPLETO`: fronteira explícita com `T-52` (próxima tarefa, que
  vai implementar a leitura de `B5.FIM02`) — recebido como parâmetro
  obrigatório, sem default `True`/`False` inventado aqui.
- `CONFIABILIDADE_DADOS`: já existe função pura de derivação em
  `engine/comportamento.py` (T-13 do slug `motor-calculo`), mas esse
  submódulo não está na allowlist de `tests/app_aluno/estatica/
  test_fronteira_import_engine.py` (`T-06`, `AC-41`) e `RF-16` proíbe a
  aplicação de reproduzir passo de cálculo fora de `calcular_plano`
  (Lei nº 3). Recebido como parâmetro obrigatório explícito, sem default —
  a chamadora (Bloco 6, fora desta tarefa) deve invocar a derivação de
  dentro do motor e passar o resultado pronto.
- `ECONOMIA_POTENCIAL_IMEDIATA` **foi** montada de fato (não é lacuna): a
  canônica normatiza a regra por completo (`B2.09`/`B2.10`/`B2.10A`) e o
  campo é lido/derivado por leitura condicional simples dentro desta tarefa
  — só o caso "nenhuma economia elegível identificada" (onde o contrato
  exige `Dinheiro`, não `DinheiroTalvez`, e este módulo não pode construir
  `Decimal` literal fora da fronteira única de `RF-13`) é recebido como
  parâmetro `economia_nao_identificada` opcional.

---

### `T-52` — Derivar `INVENTARIO_COMPLETO` de `B5.FIM02`

- **Tipo:** `Data`
- **Dependências:** `T-51`
- **Rastreia:** `RF-15`, `AC-07`
- **Arquivos:** `app/montagem/estado.py`

**Descrição**

Qualquer resposta de `B5.FIM02` (`CONFIRMACAO_FIM_CADASTRO`) diferente de `SIM`
produz `INVENTARIO_COMPLETO = False`. Isso é leitura de resposta, não regra
financeira: o efeito no `ORDEM_STATUS` é do motor.

**Critérios de aceite**

- [x] `AC-07`: "Não. Ainda falta pelo menos uma dívida" e "Não tenho certeza" produzem `INVENTARIO_COMPLETO = False`
- [x] `B5.FIM02` não respondida produz `INVENTARIO_COMPLETO = False`, nunca `True` por omissão
- [x] O mapeamento usa o `valor_interno` do registro, sem literal de enunciado em código
- [x] Nenhuma consequência sobre `ORDEM_STATUS`/`STATUS_METODO` é calculada aqui

**Status:** `[x] concluída`

---

### `T-53` — Testar a montagem do estado (`AC-07`, `AC-08`, `AC-13`, `AC-18`)

- **Tipo:** `Test`
- **Dependências:** `T-52`
- **Rastreia:** `RF-12`, `RF-14`, `RF-15`, `AC-07`, `AC-08`, `AC-13`, `AC-18`
- **Arquivos:** `tests/app_aluno/test_montagem_estado.py`, `tests/app_aluno/fixtures/caso_completo.py`

**Descrição**

Fixture de caso completo (respostas de todos os blocos obrigatórios) e os
quatro critérios verificados pelo estado resultante. `AC-08` é a reprodução de
`GAB-03` pela via da coleta.

**Critérios de aceite**

- [x] `AC-08`: reprodução de `GAB-03` — rotativo com saldo e pagamento "não sei" chega ao motor como `DESCONHECIDO` nos dois
- [x] `AC-13`: comparação campo a campo com o contrato de `engine/estado.py`; campo novo no motor quebra o teste
- [x] `AC-07`: os três valores de `B5.FIM02` testados, com o esperado de `INVENTARIO_COMPLETO`
- [x] `AC-18`: duas montagens com a mesma `DATA_REFERENCIA` produzem estados iguais
- [x] A fixture é dado de teste, não literal de questionário em código de produção

**Status:** `[x] concluída`

---

### `T-54` — Implementar `app/motor/executor.py`: invocar `calcular_plano` em processo

- **Tipo:** `Infra`
- **Dependências:** `T-51`, `T-33`
- **Rastreia:** `RF-16`, `RF-19`, `RF-32`, `AC-12`, `AC-43`
- **Arquivos:** `app/motor/executor.py`

**Descrição**

Os quatro passos do §5.2 do plano: `FonteParametros.carregar(versao)` →
`EstadoFinanceiro` montado → `calcular_plano(...)` **em processo, uma única
vez** → `RepositorioSnapshots.anexar(snapshot)` antes de qualquer exibição.
Nenhum passo de cálculo é reproduzido.

**Critérios de aceite**

- [x] `AC-12`: `calcular_plano` é invocado exatamente uma vez por execução do Bloco 6, e o snapshot é persistido antes de qualquer exibição
- [x] `AC-43`: a gravação ocorre por `RepositorioSnapshots.anexar`; nenhum SQL de snapshot existe nesta feature
- [x] `RF-32`: os parâmetros vêm da `FonteParametros` existente; nenhum `P_*` no código
- [x] A execução ocorre em `run_in_executor`, com o caso em `CALCULANDO` e progresso visível
- [x] Nenhum gate, ranqueamento ou fórmula da §11 aparece no módulo (`T-06` e `T-08` passam)

**Status:** `[x] concluída`

---

### `T-55` — Tratar `ErroParametros` e `ErroInvariante` no executor

- **Tipo:** `Infra`
- **Dependências:** `T-54`
- **Rastreia:** `RF-16`, `EC-03`, `EC-04`, `EC-06`
- **Arquivos:** `app/motor/executor.py`, `app/casos/maquina.py`

**Descrição**

`ErroParametros` (`EC-04`): o cálculo **não é tentado**, o estado anterior é
preservado e o erro é reportado ao operador — nunca parâmetro default.
`ErroInvariante` (`EC-03`): caso em `ERRO_DE_CALCULO`, `hash_inputs` registrado,
**nenhum** plano parcial ao aluno. Invariante quebrado é bug.

**Critérios de aceite**

- [x] `EC-04`: com a fonte de parâmetros falhando, `calcular_plano` não é chamado e o estado do caso é o anterior
- [x] `EC-03`: `ErroInvariante` leva o caso a `ERRO_DE_CALCULO` e nada é exibido ao aluno
- [x] `EC-06`: timeout resolve para "há snapshot e avança" ou "não há e volta ao estado anterior" — nunca `CALCULANDO` preso
- [x] Nenhum log contém valor monetário, saldo, renda ou identificador pessoal — só `CASO_ID`, `SNAPSHOT_ID`, `hash_inputs`, `ENGINE_VERSION`, `PARAMETROS_VERSION`, estado e transição

**Status:** `[x] concluída`

---

### `T-56` — Implementar a rota e a tela de progresso do Bloco 6

- **Tipo:** `UI`
- **Dependências:** `T-55`, `T-44`
- **Rastreia:** `RF-16`, `AC-12`
- **Arquivos:** `app/http/rotas_calculo.py`, `report/templates/calculo/progresso.html`

**Descrição**

A transição `COLETA_INICIAL → CALCULANDO` exige `B5.FIM02` respondida e os
campos `OBR` completos (guarda do §7.1). O Bloco 6 **não coleta nada**: a tela é
só progresso, nunca uma pergunta.

**Critérios de aceite**

- [x] A transição para `CALCULANDO` é recusada com campo `OBR` pendente, nomeando o que falta
- [x] Nenhuma pergunta é exibida durante o Bloco 6
- [x] A tela de progresso aparece enquanto o caso está em `CALCULANDO`, nunca uma tela travada
- [x] Dois disparos concorrentes do Bloco 6 sobre o mesmo caso resultam em uma única execução (`FOR UPDATE` de `T-23`)

**Status:** `[x] concluída`

---

### `T-57` — Testar a costura coleta → motor → snapshot (`AC-12`)

- **Tipo:** `Test`
- **Dependências:** `T-56`, `T-53`
- **Rastreia:** `RF-16`, `RF-19`, `AC-12`, `AC-43`
- **Arquivos:** `tests/app_aluno/integracao/test_coleta_para_motor.py`

**Descrição**

Caso completo de fixture → `EstadoFinanceiro` → `calcular_plano` → snapshot
persistido. É a costura que este slug cria; o motor em si já está verificado.

**Critérios de aceite**

- [x] `AC-12`: `calcular_plano` é chamado uma única vez, verificado por espião sobre a fronteira, e o snapshot está no repositório antes de qualquer resposta HTTP com conteúdo de plano
- [x] `AC-43`: o snapshot no repositório foi gravado por `anexar`
- [x] O snapshot devolvido carrega `ENGINE_VERSION` e `PARAMETROS_VERSION` não vazios
- [x] O teste usa o adaptador de arquivo e passa sem `DATABASE_URL`

**Status:** `[x] concluída`

---

### `T-58` — Testar os caminhos de erro do Bloco 6 (`EC-03`, `EC-04`, `EC-06`)

- **Tipo:** `Test`
- **Dependências:** `T-55`
- **Rastreia:** `RF-16`, `EC-03`, `EC-04`, `EC-06`
- **Arquivos:** `tests/app_aluno/test_erros_do_calculo.py`

**Descrição**

Fonte de parâmetros que falha, motor que levanta `ErroInvariante` e execução que
excede o tempo — os três com o comportamento observável esperado.

**Critérios de aceite**

- [x] `EC-04`: nenhuma chamada a `calcular_plano` ocorre e o estado permanece o anterior — coberto na LÓGICA INTERNA por `tests/app_aluno/test_executor.py::test_ec04_erro_parametros_nao_chama_calcular_plano_e_transiciona_para_erro` (T-54/T-55, espião sobre `calcular_plano`) e, no ângulo desta tarefa (resposta HTTP/observável), por `tests/app_aluno/test_erros_do_calculo.py::test_ec04_fonte_de_parametros_falha_nenhuma_chamada_ao_motor_e_estado_permanece` — `FonteParametrosArquivo` real com versão inexistente, via `POST /caso/{CASO_ID}/calculo`, sobre o caso completo (T-53)
- [x] `EC-03`: o caso vai a `ERRO_DE_CALCULO`, o `hash_inputs` é registrado e a resposta ao aluno não contém plano parcial — a transição e o `hash_inputs` já eram provados internamente por `test_executor.py::test_ec03_erro_invariante_transiciona_para_erro_de_calculo`/`test_ec03_hash_inputs_e_registrado_no_log` (T-55); o ângulo que faltava — o CONTEÚDO da resposta HTTP ao aluno (`erro.html`, sem termo de plano/ordem/parcela/valor) — é coberto por `test_erros_do_calculo.py::test_ec03_erro_invariante_resposta_ao_aluno_nao_contem_plano_parcial`, com `test_ec03_hash_inputs_e_registrado_com_caso_completo_real` repetindo a prova do hash sobre o cenário HTTP mais realista (não uma duplicação do teste de T-55, um cenário de entrada diferente)
- [x] `EC-06`: após timeout, o caso está em `PLANO_LIBERADO`/`AGUARDANDO_REVISAO` (com snapshot) ou no estado anterior (sem snapshot), nunca em `CALCULANDO` — a lógica de reversão/confirmação já era provada internamente por `test_executor.py::test_ec06_timeout_sem_snapshot_reverte_ao_estado_anterior`/`test_ec06_timeout_com_snapshot_ja_anexado_nao_reverte` (T-55); `test_erros_do_calculo.py::test_ec06_timeout_nunca_deixa_o_caso_preso_em_calculando` prova o mesmo caminho observável a partir da rota HTTP real (`POST .../calculo` seguido de polling em `GET .../calculo/progresso`, o mesmo padrão de espera descoberto por T-57 para tasks de segundo plano do `TestClient`), nunca `CALCULANDO`
- [x] Um teste verifica que nenhum valor monetário aparece nos logs emitidos nesses caminhos — `test_executor.py::test_ec04_nenhum_log_de_erro_parametros_contem_dado_fora_da_allowlist` (T-55) já cobria a allowlist de campos extras só no caminho EC-04; `test_erros_do_calculo.py::test_nenhum_log_dos_tres_caminhos_de_erro_contem_valor_monetario_do_caso` estende a auditoria aos TRÊS caminhos (EC-04/EC-03/EC-06) rodados em sequência sobre o caso completo real, auditando o `getMessage()` completo de cada registro (não só os campos nomeados) contra os valores monetários de verdade da fixture (`5.000,00`, `300,00`, `8.000,00`, `6.500,00`)

**Status:** `[x] concluída`

---

## Entrega 7 — O plano na tela e em PDF, com a redação canônica

### `T-59` — Criar o template único do plano com a redação canônica de `Q-03`

- **Tipo:** `UI`
- **Dependências:** `T-04`
- **Rastreia:** `RF-21`, `AC-14`, `AC-15`
- **Arquivos:** `report/templates/plano/plano.html`, `report/templates/plano/textos-canonicos.yaml`

**Descrição**

Título *"Sua ordem projetada de quitação"* e o texto normativo de `Q-03`,
caractere por caractere, em **um** template — é o que faz `AC-14`/`AC-16`
valerem para tela e PDF sem duplicar texto normativo. O termo é sempre
"projetada".

**Critérios de aceite**

- [x] `AC-14`: o título renderizado é exatamente "Sua ordem projetada de quitação" e o texto é exatamente o de `Q-03`
- [x] `AC-15`: a palavra "projetada" aparece e nenhuma das palavras "definitiva", "final" ou "fixa" qualifica a ordem
- [x] A redação canônica vive em **um** arquivo, referenciado por tela e PDF
- [x] Nenhuma variável nova de rótulo visual foi criada para a ordem

**Status:** `[x] concluída`

---

### `T-60` — Renderizar a ordem lendo campos do snapshot

- **Tipo:** `UI`
- **Dependências:** `T-59`, `T-54`
- **Rastreia:** `RF-20`, `RF-22`, `AC-16`, `AC-17`, `AC-42`
- **Arquivos:** `report/plano.py`, `report/templates/plano/posicao.html`

**Descrição**

Cada posição da `ORDEM_QUITACAO` com sua `JUSTIFICATIVA_POSICAO`, e o carimbo
`ENGINE_VERSION`/`PARAMETROS_VERSION` na saída. Todo valor é **leitura** de
campo do snapshot, passado por `quantizar_exibicao` — nunca recomputado.

**Critérios de aceite**

- [x] `AC-17`: uma ordem com N dívidas exibe N posições, cada uma com sua `JUSTIFICATIVA_POSICAO`
- [x] `AC-16`: `ENGINE_VERSION` e `PARAMETROS_VERSION` do snapshot aparecem na saída
- [x] `AC-42`: nenhuma aritmética sobre campo do snapshot fora de `quantizar_exibicao`
- [x] Prazo e custo exibidos correspondem exatamente aos campos do snapshot, sem reformatação numérica própria

**Status:** `[x] concluída`

---

### `T-61` — Escrever o teste estático "nenhuma aritmética sobre campo de snapshot" (`AC-42`)

- **Tipo:** `Test`
- **Dependências:** `T-60`
- **Rastreia:** `RF-34`, `AC-42`
- **Arquivos:** `tests/app_aluno/estatica/test_sem_aritmetica_sobre_snapshot.py`

**Descrição**

AST de `app/`, `collection/` e `report/`: operação aritmética cujo operando vem
de campo de `SnapshotOrdem` só é permitida dentro de `quantizar_exibicao`.

**Critérios de aceite**

- [x] O teste falha se qualquer arquivo somar, subtrair, multiplicar ou dividir um campo de `SnapshotOrdem`
- [x] O teste falha se um total exibido for produzido por `sum(...)` sobre campos do snapshot
- [x] As exceções permitidas (contagem de itens de uma sequência para exibição) estão declaradas explicitamente no teste
- [x] O teste cita `AC-42` no nome

**Status:** `[x] concluída`

---

### `T-62` — Tratar `EC-07`, `EC-08` e `EC-09` na apresentação

- **Tipo:** `UI`
- **Dependências:** `T-60`
- **Rastreia:** `RF-21`, `RF-22`, `EC-07`, `EC-08`, `EC-09`
- **Arquivos:** `report/templates/plano/ordem_vazia.html`, `report/templates/plano/estabilizacao.html`, `report/templates/plano/pendencias.html`

**Descrição**

`ORDEM_QUITACAO` vazia (`DIVIDA_ALVO_ATUAL is None`) exibe a `ORDEM_ACOES` em
primeiro plano. Plano `PROVISORIO` explicita o que falta. Em
`MODO_ESTABILIZACAO`, `RESULTADO_CAIXA_OBSERVADO` positivo **nunca** é chamado
de "sobra", e método/ordem/cronograma aparecem como fase 2 condicional.

**Critérios de aceite**

- [x] `EC-07`: com `DIVIDA_ALVO_ATUAL = None`, a `ORDEM_ACOES` é o conteúdo principal — nunca uma ordem vazia sem explicação
- [x] `EC-08`: plano `PROVISORIO` lista as informações faltantes lidas do snapshot, sem recomputar nada
- [x] `EC-09`: com `MODO_ESTABILIZACAO`, a palavra "sobra" não aparece qualificando `RESULTADO_CAIXA_OBSERVADO`
- [x] Os três estados são decididos por leitura de campo do snapshot, nunca por cálculo

**Status:** `[x] concluída`

---

### `T-63` — Implementar a exportação em PDF do mesmo template

- **Tipo:** `UI`
- **Dependências:** `T-62`
- **Rastreia:** `RF-20`, `RF-21`, `AC-14`, `AC-16`
- **Arquivos:** `report/pdf.py`, `app/http/rotas_plano.py`

**Descrição**

WeasyPrint sobre o **mesmo** HTML/CSS da tela, sob demanda, a partir do mesmo
snapshot liberado (`OQ-09`: um objeto revisado, duas apresentações). Regenerar
mais tarde produz o mesmo documento, porque o snapshot é imutável.

**Critérios de aceite**

- [x] O PDF é gerado a partir do mesmo template da tela, sem segunda redação do texto normativo
- [x] `AC-14` e `AC-16` valem no PDF: título, texto de `Q-03` e o carimbo de versão presentes
- [x] Regenerar o PDF do mesmo snapshot produz o mesmo conteúdo
- [x] O PDF só é gerado para snapshot com liberação registrada

**Nota de implementação — "liberação registrada" e a fronteira com a
Entrega 8 (fila de revisão, ainda não implementada).** Sem a fila de
revisão (`revisoes`/`app/revisao/`, Entrega 8), esta tarefa reaproveita o
campo que já existe (`Caso.snapshot_liberado_id`, `persistencia/app_aluno/
casos.py`, T-21/T-23) em vez de inventar um novo conceito:
"snapshot com liberação registrada" ⟺ `caso.snapshot_liberado_id ==
snapshot.SNAPSHOT_ID` (`report/pdf.py::snapshot_tem_liberacao_registrada`).
Hoje (antes da Entrega 8) NENHUM caminho de código popula
`snapshot_liberado_id` — nem `app/motor/executor.py` (só transiciona o caso
para `AGUARDANDO_REVISAO`), nem `app/http/rotas_calculo.py` — então, em
produção, nenhum PDF seria gerado até a fila de revisão existir e chamar
`RepositorioCasos.registrar_snapshot_liberado` após aprovação humana. Isso é
o comportamento CORRETO e proposital desta tarefa (revisão humana
obrigatória, `sdd.config.md` §6), documentado em `report/pdf.py` e
verificado nesta tarefa só com um `Caso` de teste com o campo setado à mão.
"Mesmo conteúdo" ao regenerar é verificado por igualdade do HTML de ENTRADA
(determinístico, já que `montar_contexto_plano` só lê o snapshot imutável),
não por bytes de PDF — bytes de PDF carregam metadados de geração do
WeasyPrint que podem variar entre chamadas mesmo com entrada idêntica; essa
decisão está documentada em `report/pdf.py` e em `tests/app_aluno/
test_pdf.py`. Os dois testes que produzem bytes de PDF reais (`weasyprint.
HTML(...).write_pdf()`) são pulados neste ambiente Windows de
desenvolvimento porque a biblioteca nativa GTK/Pango (`libgobject-2.0-0`)
não está instalada no sistema — o pacote `pip` `weasyprint` está presente e
`report/pdf.py` importa-o corretamente (`ModuleNotFoundError` não ocorre;
o erro é `OSError` de carga de biblioteca nativa, capturado e reportado
como skip explícito, nunca escondido).

**Status:** `[x] concluída`

---

### `T-64` — Implementar a rota do plano do aluno, servindo só o snapshot liberado

- **Tipo:** `UI`
- **Dependências:** `T-63`, `T-31`
- **Rastreia:** `RF-20`, `RF-21`, `RF-23`, `AC-25`
- **Arquivos:** `app/http/rotas_plano.py`

**Descrição**

A tela do aluno mostra sempre o snapshot **liberado** mais recente
(`casos.snapshot_liberado_id`). Snapshot em `AGUARDANDO_REVISAO` não é
acessível ao aluno por nenhuma rota.

**Critérios de aceite**

- [x] `AC-25`: snapshot sem liberação registrada não é acessível ao aluno, nem em tela nem em PDF
- [x] A tela serve o `snapshot_liberado_id` do caso, não o último calculado
- [x] A rota respeita o isolamento por caso de `T-31`
- [x] Caso sem nenhum snapshot liberado exibe o estado do caso, nunca um plano vazio

**Nota de implementação.** `GET /caso/{CASO_ID}/plano` estende `app/http/
rotas_plano.py` (T-63), reaproveitando integralmente `report.pdf.
snapshot_tem_liberacao_registrada`/`gerar_html_do_plano_liberado` — nenhuma
segunda checagem de liberação, nenhuma segunda redação do template. Sem
`snapshot_liberado_id`, a rota renderiza `report/templates/plano/
aguardando.html` com a mensagem correspondente a `Caso.estado` (mapa TOTAL
em `app/http/rotas_plano.py::_mensagem_do_estado_do_caso`, `match`
exaustivo sobre os doze membros de `ESTADO_CASO`, verificado por
`mypy --strict`) — nunca `404` nem uma tela de plano vazia. O teste de
isolamento de `T-32` (`tests/app_aluno/e2e/test_isolamento_por_caso.py`)
foi ATUALIZADO nesta tarefa: o placeholder `/exemplo-plano/{CASO_ID}` foi
substituído pela rota REAL `GET /caso/{CASO_ID}/plano` nos testes
parametrizados e na auditoria por enumeração de `app.routes` — respostas,
PDF e fila continuam como placeholders (ainda não implementados).

**Status:** `[x] concluída`

---

### `T-65` — Testar a redação canônica no HTML e no PDF (`AC-14`..`AC-17`)

- **Tipo:** `Test`
- **Dependências:** `T-64`
- **Rastreia:** `RF-20`, `RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`
- **Arquivos:** `tests/app_aluno/e2e/test_redacao_canonica.py`

**Descrição**

Verificação **caractere por caractere** no HTML renderizado e no texto extraído
do PDF. Só o que é normativo e citável é testado — auditar prosa livre produziria
falso verde (§9 do plano).

**Critérios de aceite**

- [x] `AC-14`: título e texto de `Q-03` conferidos por igualdade exata de string, no HTML e no PDF
- [x] `AC-15`: "projetada" presente; "definitiva", "final" e "fixa" ausentes como qualificador da ordem
- [x] `AC-16`: `ENGINE_VERSION` e `PARAMETROS_VERSION` presentes nas duas saídas
- [x] `AC-17`: N posições, N justificativas, conferidas contra o snapshot de fixture
- [x] Os testes citam os `AC-NN` nos nomes

**Nota de implementação.** Suíte E2E via CLIENTE HTTP REAL (`TestClient` sobre
`criar_aplicacao()`, sessão assinada aberta de verdade) contra as duas rotas
reais de `app/http/rotas_plano.py` (T-63/T-64) — `GET /caso/{CASO_ID}/plano`
e `GET /caso/{CASO_ID}/plano/pdf` —, com um `SnapshotOrdem` REAL de DUAS
dívidas produzido por `engine.motor.calcular_plano` sobre a fixture de caso
completo (`tests/app_aluno/fixtures/caso_completo.py`, T-53). Persistência é
dublê em memória (mesmo padrão de `tests/app_aluno/test_rotas_plano.py`) —
não `requer_banco`: os quatro critérios desta tarefa (redação, versão,
contagem de posições) não dependem de Postgres real, só do caminho HTTP
completo, que os dublês não substituem (roteamento, sessão, isolamento e
templates são o código de produção). Os quatro critérios são conferidos nas
DUAS respostas HTTP: `AC-14` por igualdade exata de string (`<h1>`/`<p>`
completos, não substring) tanto no HTML da tela quanto no HTML de entrada do
PDF (a mesma via de auditoria de `report/pdf.py`/`test_pdf.py`: nenhuma lib
de extração de texto de PDF está no plano/`pyproject.toml`, então o PDF é
auditado pelo HTML que `gerar_pdf_do_plano` de fato envia ao WeasyPrint —
provado idêntico ao HTML da tela por igualdade estrita); a chamada HTTP real
que produz bytes `%PDF` de verdade roda quando a biblioteca nativa do
WeasyPrint (GTK/Pango) está disponível e é pulada com mensagem explícita
quando não está (ausente neste ambiente Windows de desenvolvimento — mesma
limitação já documentada em `report/pdf.py`/`test_pdf.py`/`test_rotas_
plano.py`, replicada aqui sem fingir execução). Este arquivo não duplica
`test_plano.py` (T-59/T-60, unitário sobre HTML isolado), `test_pdf.py`
(T-63, unitário sobre `report.pdf` direto) nem `test_rotas_plano.py` (T-64,
contrato de liberação/isolamento): é a integração fim-a-fim das quatro
verificações num único fluxo HTTP real, com as duas rotas conferidas juntas.

**Status:** `[x] concluída`

---

## Entrega 8 — Nenhum plano sem revisão humana

### `T-66` — Implementar a fila de revisão e a política integral do piloto

- **Tipo:** `Data`
- **Dependências:** `T-54`, `T-21`
- **Rastreia:** `RF-23`, `RF-25`, `AC-25`, `AC-28`
- **Arquivos:** `app/revisao/fila.py`

**Descrição**

`POLITICA_REVISAO_INTEGRAL_PILOTO: Final[bool] = True` — política de **processo**,
distinta do campo `REVISAO_HUMANA_OBRIGATORIA` do motor (`S-04`). Todo snapshot
entra na fila mesmo com o campo em `False`. Os dois **nunca** são lidos pela
mesma expressão.

**Critérios de aceite**

- [x] `AC-25`: snapshot com `REVISAO_HUMANA_OBRIGATORIA = False` entra na fila
- [x] A condição de entrada na fila lê apenas `POLITICA_REVISAO_INTEGRAL_PILOTO`; o campo do motor não aparece nessa expressão
- [x] `AC-28`: a fila expõe os dois sinais separadamente, para que o revisor distinga motivo metodológico de política
- [x] Fila única, sem papéis, permissões nem atribuição (`OQ-03` respondida)

**Status:** `[x] concluída`

---

### `T-67` — Implementar `RegistroRevisao` imutável com autor e data

- **Tipo:** `Data`
- **Dependências:** `T-66`, `T-21`
- **Rastreia:** `RF-24`, `AC-27`
- **Arquivos:** `app/revisao/fila.py`, `persistencia/app_aluno/revisoes.py`

**Descrição**

`DECISAO_REVISAO` (`LIBERADO`, `REPROVADO`), `RegistroRevisao` com
`SNAPSHOT_ID`, `CASO_ID`, `decisao`, `autor`, `decidido_em`,
`classificacao_erro` e `observacao`. Append-only, mesmo padrão estrutural de
`RepositorioSnapshots`: sem verbo de mutação na interface.

**Critérios de aceite**

- [x] `AC-27`: autor e data são gravados, e o registro não pode ser alterado nem removido por nenhuma rota
- [x] A interface do repositório de revisões não expõe `atualizar` nem `remover`
- [x] Liberação **e** reprovação são ambas registradas
- [x] `UPDATE`/`DELETE` direto na tabela é recusado pelo banco (`REVOKE` + trigger de `T-21`)

**Status:** `[x] concluída`

---

### `T-68` — Implementar as transições de liberação e reprovação

- **Tipo:** `Infra`
- **Dependências:** `T-67`, `T-33`
- **Rastreia:** `RF-23`, `RF-24`, `AC-26`, `EC-12`
- **Arquivos:** `app/revisao/fila.py`, `app/casos/maquina.py`

**Descrição**

Liberação leva a `PLANO_LIBERADO` e preenche `casos.snapshot_liberado_id`;
reprovação leva a `REPROVADO_EM_REVISAO`, com o snapshot **intacto** — nunca se
edita snapshot para "corrigir".

**Critérios de aceite**

- [x] Liberar registra a decisão e só então preenche `snapshot_liberado_id`
- [x] `EC-12`: reprovar registra autor e data, não libera nada ao aluno e deixa o snapshot inalterado
- [x] Liberar duas vezes o mesmo snapshot é idempotente ou recusado — nunca produz dois registros conflitantes
- [x] Nenhum caminho de código edita um snapshot como parte da revisão

**Status:** `[x] concluída`

---

### `T-69` — Implementar a tela da fila de revisão

- **Tipo:** `UI`
- **Dependências:** `T-68`
- **Rastreia:** `RF-23`, `RF-25`, `AC-25`, `AC-28`
- **Arquivos:** `app/http/rotas_revisao.py`, `report/templates/revisao/fila.html`

**Descrição**

Lista única de snapshots aguardando revisão, com o sinal de `S-04`
(`REVISAO_HUMANA_OBRIGATORIA = True`) distinguível de "está na fila apenas pela
política do piloto".

**Critérios de aceite**

- [x] `AC-28`: um snapshot com o campo do motor em `True` é sinalizado como caso metodológico de `S-04`, visivelmente distinto do outro
- [x] A fila lista todos os snapshots em `AGUARDANDO_REVISAO`, incluindo recálculos
- [x] A tela não expõe caso de outra conta ao aluno — a rota de revisão é separada da do aluno
- [x] Nenhum valor da fila é calculado: todos são campos lidos do snapshot

**Nota de implementação — modelo de autorização (decisão explícita, não
acidental).** `OQ-03` já havia fechado "fila única, sem papéis, permissões
nem atribuição" (T-66). Esta tarefa herda essa decisão e a torna visível na
camada HTTP: `GET /revisao/fila` **não** usa `app/http/isolamento.py`
(mecanismo de posse de `CASO_ID` do aluno, T-31) porque ela não recebe
nenhum `CASO_ID` — lista todos os casos em `AGUARDANDO_REVISAO`, de
qualquer conta, por definição de papel (um revisor vê os casos que não são
os dele). Como o sistema não modela hoje uma conta "revisora" distinta da
conta "aluno" (`persistencia/app_aluno/contas.py` tem um único tipo de
conta) e `sdd.config.md` §6 proíbe inventar um sistema de papéis por conta
própria, a rota fica **sem autenticação própria nesta entrega** — acessível
a quem alcançar a URL. Isto é documentado extensivamente na docstring de
`app/http/rotas_revisao.py` e em `app/http/aplicacao.py` como limitação
conhecida do piloto (a ser fechada por controle de rede/infra — proxy, VPN,
allowlist — fora do escopo deste backlog), não como omissão silenciosa.
Consequência decidida e registrada: `/revisao/fila` fica **fora** do escopo
da auditoria de isolamento por `CASO_ID` (`tests/app_aluno/e2e/
test_mecanismo_isolamento.py::rotas_sem_isolamento_por_caso`, T-31/T-32) —
não por burlar o mecanismo, mas porque ela estruturalmente nunca recebe
`CASO_ID` como path/query parameter (é uma listagem multi-caso, não uma
busca por identificador); a auditoria continua rodando sobre a aplicação
real com a rota registrada e permanece vazia.

Extensão necessária: `RepositorioCasos.listar_por_estado` (novo método do
`Protocol`, implementado em `RepositorioCasosSupabase` e
`RepositorioCasosArquivo`) — a fonte real de `casos_ids` que `app/revisao/
fila.py::listar_fila_de_revisao` (T-66) já recebia como parâmetro do
chamador.

**Status:** `[x] concluída`

---

### `T-100` — Exigir credencial de revisor nas rotas `/revisao/*`

- **Tipo:** `Infra`
- **Dependências:** `T-69`
- **Rastreia:** `RF-23`, `RF-25`
- **Arquivos:** `persistencia/supabase/migracoes/003_papel_revisor.sql`, `persistencia/app_aluno/contas.py`, `app/http/rotas_revisao.py`, `app/http/sessao.py`

**Descrição**

Decisão do usuário, corrigindo a lacuna de segurança que `T-69` documentou
honestamente em vez de resolver: `/revisao/*` fica sem autenticação própria
até esta tarefa. O usuário decidiu que a fila **exige login**, e que a
credencial precisa distinguir papel de revisor do papel de aluno — não
"qualquer conta de aluno logada", nem acesso anônimo confiado à rede. Isto
é uma extensão mínima e deliberada da leitura de `OQ-03` ("fila única, sem
papéis, permissões nem atribuição"): `OQ-03` fala de **atribuição de casos
dentro da fila** (não existir revisor A vs. revisor B com filas separadas) —
não fala de a fila ser acessível sem credencial. Distinguir "é revisor" de
"é aluno" não recria o sistema de papéis que a spec descartou; impede
acesso anônimo a dado sensível (dívida, renda, negativação).

**Critérios de aceite**

- [x] Migração adiciona `e_revisor boolean NOT NULL DEFAULT false` a `app_aluno.contas` — nenhuma conta existente vira revisora por acidente — validado contra Postgres real (container efêmero, migrações `001`+`002` aplicadas, uma conta inserida ANTES de `003_papel_revisor.sql`; após a migração, `e_revisor` da conta pré-existente é `false`)
- [x] `GET /revisao/fila` (as rotas de decisão de `T-71` ainda não existem — `exigir_papel_revisor` é o mecanismo genérico já pronto para elas reutilizarem) recusa com `401`/`403` uma sessão sem `e_revisor = true`, antes de qualquer leitura de caso — a dependência é declarada na assinatura da rota, resolvida pelo FastAPI antes do corpo do handler chamar `RepositorioCasos.listar_por_estado`
- [x] Uma conta de aluno comum (`e_revisor = false`) autenticada recebe `403` ao acessar `/revisao/*` — nunca `404` (a existência da tela não é segredo, o acesso é)
- [x] O provisionamento de uma conta revisora é documentado (`persistencia/app_aluno/contas.py::promover_a_revisor`, com o SQL manual equivalente na docstring) e citado como fora de escopo de UI
- [x] A auditoria de isolamento por `CASO_ID` (`T-31`/`T-32`) continua sem cobrir `/revisao/*` — motivo já registrado em `T-69` (rota multi-caso, não recebe `CASO_ID`) — `tests/app_aluno/test_guarda_papel_revisor.py` prova que a NOVA guarda de papel existe e funciona, complementando (não substituindo) essa auditoria

**Status:** `[x] concluída`

---

### `T-70` — Implementar a tela lado a lado: plano e `estado_inputs`

- **Tipo:** `UI`
- **Dependências:** `T-69`, `T-60`, `T-100`
- **Rastreia:** `RF-26`, `AC-29`
- **Arquivos:** `report/templates/revisao/comparacao.html`

**Descrição**

O revisor vê, na mesma sessão, o plano **como o aluno o verá** (mesmo template
de `T-59`/`T-60`) e os `estado_inputs` que o produziram.

**Critérios de aceite**

- [x] `AC-29`: plano e `estado_inputs` visíveis na mesma sessão, sem navegação para outro caso
- [x] O plano exibido é renderizado pelo mesmo template do aluno, sem segunda redação
- [x] Os `estado_inputs` são exibidos como leitura do campo do snapshot, com `DESCONHECIDO` visível como tal — nunca como `0` ou vazio
- [x] O carimbo `ENGINE_VERSION`/`PARAMETROS_VERSION` aparece também para o revisor (`AC-16`)

**Nota de implementação.** `GET /revisao/caso/{CASO_ID_REVISAO}` (novo,
`app/http/rotas_revisao.py`) busca o `Caso` por `RepositorioCasos.buscar` e o
snapshot mais recente de `caso.snapshot_raiz_id` (`RepositorioSnapshots.
historico`, MESMA leitura de `app.revisao.fila.listar_fila_de_revisao`,
T-66) — o revisor vê o que existe agora, liberado ou não, ao contrário da
rota do aluno (`AC-25`), que só mostra o snapshot liberado. Protegida por
`Depends(exigir_papel_revisor)` (`T-100`), nunca por `exigir_caso_da_sessao`
(`T-31`): o revisor não é "dono" de caso no sentido de isolamento do aluno,
ele acessa qualquer caso em revisão por definição de papel — mesma
disciplina já documentada por `/revisao/fila` (T-69). O path parameter
chama-se deliberadamente `CASO_ID_REVISAO`, não `CASO_ID`: o valor É um
`CASO_ID`, mas o nome literal `CASO_ID` é o gatilho que a auditoria de
isolamento do aluno (`tests/app_aluno/e2e/test_mecanismo_isolamento.py::
rotas_sem_isolamento_por_caso`, T-31/T-32) usa para exigir `exigir_caso_
da_sessao` — exigi-la aqui seria incorreto (o mecanismo dela é posse por
CONTA DE ALUNO, que não se aplica a revisor). Documentado extensamente na
docstring da rota.

**"Mesmo template do aluno, sem segunda redação".** A rota chama
`report.plano.montar_contexto_plano` + `report.pdf.renderizar_html_do_plano`
— a MESMA função e o MESMO `report/templates/plano/plano.html` que
`app/http/rotas_plano.py` (T-60/T-63/T-64) usa para a tela do aluno — e
embute o HTML resultante em `report/templates/revisao/comparacao.html`
(novo) via `{{ html_do_plano | safe }}`. Diferente da rota do aluno, esta
via NÃO passa por `report.pdf.gerar_html_do_plano_liberado` (que exige
liberação registrada): o revisor precisa ver o plano mesmo ainda
`AGUARDANDO_REVISAO`, então a rota chama diretamente `montar_contexto_plano`/
`renderizar_html_do_plano`, sem nenhuma segunda checagem de liberação e sem
nenhuma segunda redação de `Q-03`.

**`DESCONHECIDO` visível como tal (regra mais importante da tarefa).**
`report/plano.py::montar_contexto_estado_inputs` (nova função) monta o
contexto de exibição dos `estado_inputs` — TODOS os campos de
`EstadoFinanceiro`, `Divida`, `PerfilComportamental` e
`SinaisComportamentais` (leitura genérica por `dataclasses.fields`/`getattr`,
nenhum campo escolhido a dedo), cada um formatado por
`_formatar_valor_ou_desconhecido` (novo formatador): `Desconhecido` vira o
texto literal `"DESCONHECIDO"` (nunca `str(Desconhecido.DESCONHECIDO)`, que
produziria `"Desconhecido.DESCONHECIDO"`, e nunca `0`/vazio); `None`
(ausência ESTRUTURAL, distinta de desconhecido, `RF-16`) vira `"—"`;
`Decimal` passa por `quantizar_exibicao` (`AC-42`); enums viram `.value`.
Testado com `tests/app_aluno/fixtures/caso_completo.py::
caso_completo_com_divida_gab03` (reprodução de `GAB-03`/`AC-08`: saldo e
pagamento desconhecidos) — o teste confirma que os dois campos chegam como
`Desconhecido` em `estado_inputs` e que a página exibe `"DESCONHECIDO"` (não
`"Desconhecido.DESCONHECIDO"`, não `0`, não vazio).

**`AC-16` para o revisor.** `ENGINE_VERSION`/`PARAMETROS_VERSION` aparecem
duas vezes na página: dentro do HTML incluído do plano (mesmo rodapé de
`plano.html`) e na referência rápida do cabeçalho de
`comparacao.html`, ambos por leitura direta de `SnapshotOrdem`.

**Testes:** `tests/app_aluno/test_rotas_revisao_comparacao.py` (novo), sete
casos cobrindo os quatro critérios de aceite mais dois caminhos não-felizes
(caso inexistente, caso sem snapshot) — `SnapshotOrdem` REAL produzido por
`executar_calculo` sobre a fixture de caso completo (T-53), nunca fabricado
à mão.

**Status:** `[x] concluída`

---

### `T-71` — Implementar a ação de liberar e reprovar na tela do revisor

- **Tipo:** `UI`
- **Dependências:** `T-70`, `T-100`
- **Rastreia:** `RF-24`, `AC-27`, `EC-12`
- **Arquivos:** `app/http/rotas_revisao.py`, `report/templates/revisao/decisao.html`

**Descrição**

Formulário de decisão com autor e observação. Nenhuma rota permite editar ou
apagar um registro de revisão já gravado.

**Critérios de aceite**

- [x] Liberar e reprovar gravam `RegistroRevisao` com autor e data
- [x] Não existe rota de edição nem de remoção de registro de revisão — verificado enumerando as rotas
- [x] Após a liberação, o plano fica acessível ao aluno; após a reprovação, não
- [x] A observação do revisor é gravada junto à decisão

**Status:** `[x] concluída`

---

### `T-72` — Implementar `CLASSIFICACAO_ERRO` com os seis rótulos, sem glosa inventada

- **Tipo:** `UI`
- **Dependências:** `T-71`
- **Rastreia:** `RF-26`
- **Dependência externa:** `OQ-12` (texto normativo da §25 ausente da canônica) — **respondida**: confirmado ausente do repositório inteiro; decisão do usuário foi manter só os seis nomes, sem glosa (`PEND-LOCAL-01`). Não muda nada do que esta tarefa implementou
- **Arquivos:** `app/revisao/fila.py`, `report/templates/revisao/classificacao.html`

**Descrição**

Enum de seis membros (`TEXTO`, `PARAMETRO`, `DADO`, `REGRA`, `CALCULO`, `UX`),
vindos da §15.3. A **definição** de cada um não existe para transcrever
(`OQ-12`): a tela exibe o rótulo e um campo livre, sem glosa inventada.
Classificar errado é pior que não classificar.

**Critérios de aceite**

- [x] O enum tem exatamente os seis membros, com os nomes da §15.3
- [x] Nenhuma descrição, definição ou exemplo de categoria aparece na tela ou no código
- [x] O campo livre acompanha a classificação e é gravado no `RegistroRevisao`
- [x] O código registra em comentário que `OQ-12` está aberta e que a glosa entra quando ela for respondida

**Status:** `[x] concluída`

**Atualização pós-fechamento de Open Questions.** `OQ-12` foi respondida como
decisão deliberada de **manter o enum sem glosa** (`PEND-LOCAL-01`, ver
`specs/app-aluno.spec.md`) — não como "aguardando texto normativo". Esta
tarefa já implementava exatamente esse resultado; nenhuma mudança de código é
necessária. O comentário no código que diz "`OQ-12` aberta" pode ser
atualizado para citar `PEND-LOCAL-01` na próxima vez que o arquivo for
tocado, mas isso não é urgente nem afeta comportamento.

---

### `T-73` — Testar a fila: política, distinção dos dois mecanismos e imutabilidade

- **Tipo:** `Test`
- **Dependências:** `T-72`
- **Rastreia:** `RF-23`, `RF-24`, `RF-25`, `RF-26`, `AC-25`, `AC-27`, `AC-28`, `AC-29`
- **Arquivos:** `tests/app_aluno/test_fila_de_revisao.py`, `tests/app_aluno/integracao/test_revisao_imutavel.py`

**Descrição**

O risco alto da spec §8 (confundir `REVISAO_HUMANA_OBRIGATORIA` com a política)
é neutralizado por teste: `AC-25` e `AC-28` são obrigatórios.

**Critérios de aceite**

- [x] `AC-25`: snapshot com o campo do motor em `False` entra na fila e não é acessível ao aluno até haver liberação — cobertura PRÉ-EXISTENTE: `tests/app_aluno/test_fila_de_revisao.py::test_ac25_snapshot_com_campo_do_motor_false_entra_na_fila` (T-66) prova a entrada na fila; `tests/app_aluno/test_rotas_plano.py` (T-64, cita `AC-25` no docstring do módulo) prova "não acessível ao aluno" sem `snapshot_liberado_id` (`test_sem_snapshot_liberado_id_...`, `test_ac25...`, entre outros nomeados na própria suíte)
- [x] `AC-28`: os dois mecanismos são distinguíveis na saída da fila, verificado por asserção sobre os dois sinais — cobertura PRÉ-EXISTENTE: `tests/app_aluno/test_fila_de_revisao.py::test_ac28_item_fila_expoe_os_dois_sinais_separadamente` (T-66) — asserção direta sobre `item.entra_por_politica` e `item.e_metodologico` como campos distintos de `ItemFila`
- [x] `AC-27`: `UPDATE`/`DELETE` de `RegistroRevisao` é recusado pelo banco (marcador `requer_banco`) — cobertura PRÉ-EXISTENTE em `tests/app_aluno/integracao/test_persistencia_revisoes.py` (T-67: `test_update_direto_em_revisoes_e_recusado_e_registro_permanece_inalterado`, `test_delete_direto_em_revisoes_e_recusado_e_registro_permanece`, `test_interface_do_repositorio_nao_expoe_atualizar_nem_remover`), reafirmada e referenciada por `tests/app_aluno/integracao/test_revisao_imutavel.py` (NOVO, mínimo, com um teste próprio de `DELETE` via repositório real e um teste de sanidade que a suíte irmã continua existindo) — os dois arquivos rodados juntos contra Postgres real (container efêmero desta tarefa, migrações `001`+`002`+`003`): 9/9 passaram
- [x] `AC-29`: plano e `estado_inputs` presentes na mesma resposta HTTP — cobertura PRÉ-EXISTENTE: `tests/app_aluno/test_rotas_revisao_comparacao.py::test_ac29_plano_e_estado_inputs_aparecem_na_mesma_resposta` (T-70)
- [x] Um teste garante que nenhuma expressão do código lê `REVISAO_HUMANA_OBRIGATORIA` e `POLITICA_REVISAO_INTEGRAL_PILOTO` juntas — cobertura PRÉ-EXISTENTE: `tests/app_aluno/estatica/test_fila_revisao_sinais_separados.py` (T-66), confirmado como cobrindo o `app/revisao/fila.py` de HOJE (rodado após T-67 a T-72 terem estendido o arquivo): `test_fila_revisao_nunca_mistura_os_dois_sinais_na_mesma_expressao` percorre a AST do arquivo real por inteiro, sem recorte de escopo — não há trecho do módulo fora da varredura

**Status:** `[x] concluída`

---

## Entrega 9 — Coleta dirigida pelo motor: Blocos 7, 8 e 10

### `T-74` — Implementar a leitura de `ORDEM_ACOES` sem derivar nada

- **Tipo:** `Data`
- **Dependências:** `T-54`
- **Rastreia:** `RF-17`, `RF-33`, `AC-41`
- **Arquivos:** `app/motor/acoes.py`

**Descrição**

`acoes_em_acompanhamento(s)` **lê** `s.ORDEM_ACOES`. Não deriva tipo, não infere
identidade e **não faz parsing da `descricao` em prosa**. A camada de coleta é
consumidora do que o motor publicou.

**Critérios de aceite**

- [x] A função devolve exatamente a tupla de `ORDEM_ACOES` do snapshot, sem filtro nem derivação
- [x] Nenhuma expressão regular ou `str.split`/`in` sobre `descricao` existe no módulo
- [x] Nenhum literal de tipo de ação aparece no módulo (`OQ-13` aberta)
- [x] `T-06` e `T-08` passam sobre o módulo

**Status:** `[x] concluída`

---

### `T-75` — Abrir o Bloco 7 apenas para as dívidas sinalizadas pelo motor

- **Tipo:** `UI`
- **Dependências:** `T-74`, `T-18`, `T-33`
- **Rastreia:** `RF-17`, `AC-19`
- **Arquivos:** `app/casos/coleta_dirigida.py`, `app/http/rotas_coleta_dirigida.py`

**Descrição**

`COLETA_DIRIGIDA` abre as perguntas do Bloco 7 repetidas por `DIVIDA_ID`,
exclusivamente para as dívidas com ação de renegociação em `ORDEM_ACOES`. A
interface **nunca** decide sozinha qual dívida é candidata.

**Critérios de aceite**

- [x] `AC-19`: com ação de renegociação só para `D002`, o Bloco 7 é exibido para `D002` e para nenhuma outra dívida
- [x] A lista de dívidas abertas vem de `ORDEM_ACOES`, sem consultar saldo, taxa ou qualquer critério próprio
- [x] Com `ORDEM_ACOES` vazia, o Bloco 7 não abre e o caso não entra em `COLETA_DIRIGIDA`
- [x] Nenhum critério de elegibilidade é avaliado na aplicação

**Nota de implementação — técnica de distinção sem `TIPO_ACAO`.**
`engine.gates.AcaoRequerida` hoje não tem `TIPO_ACAO` (`OQ-13` aberta). Para
uma `AcaoRequerida` com `gate_origem == 3` (Gate 3 — Transformação, a única
origem de renegociação/troca), `app/casos/coleta_dirigida.py::
dividas_para_bloco_7` localiza a `Divida` correspondente em
`snapshot.estado_inputs.dividas` (mesmo `EstadoFinanceiro` que o motor
consumiu, `V-02`: "nada se perde") pelo `DIVIDA_ID` e lê `.RENEGOCIACAO_
PENDENTE` — campo booleano real do contrato (`engine/estado.py`), não um
`TIPO_ACAO` inventado nem parsing de `descricao`. Documentado extensamente
no cabeçalho do módulo, incluindo a ambiguidade conhecida e não resolvida
por desempate: uma dívida com `RENEGOCIACAO_PENDENTE` e `TROCA_PENDENTE`
ambos `True` abre os Blocos 7 e 8 simultaneamente (comportamento correto,
não uma falha de desempate — `aplicar_gate_3_transformacao`, T-30, já trata
os dois motivos como coexistentes).

**Formato da rota — decisão desta tarefa.** `GET /caso/{CASO_ID}/
coleta-dirigida/bloco-7` devolve JSON, não HTML/`Jinja2Templates`: o escopo
de arquivos desta tarefa é só os dois `.py` declarados, sem `report/
templates/` novo. O router ainda não está registrado em `app/http/
aplicacao.py` (fora do escopo declarado) — os testes o incluem manualmente.

**Testes:** `tests/app_aluno/test_coleta_dirigida.py` (sete casos sobre a
função pura, com `SnapshotOrdem` real via `calcular_plano`, saldo alto para
não violar `ErroOrdemInconsistente` — mesma técnica de T-74) e
`tests/app_aluno/test_rotas_coleta_dirigida.py` (quatro casos HTTP,
isolamento por `CASO_ID` incluído).

**Status:** `[x] concluída`

---

### `T-76` — Abrir o Bloco 8 pelo mesmo mecanismo, para as dívidas de troca

- **Tipo:** `UI`
- **Dependências:** `T-75`
- **Rastreia:** `RF-17`, `AC-19`
- **Arquivos:** `app/casos/coleta_dirigida.py`

**Descrição**

Mesmo caminho de código de `T-75`, dirigido pela ação de troca. Nenhuma
duplicação de mecanismo entre os dois blocos.

**Critérios de aceite**

- [x] O Bloco 8 abre pelo mesmo mecanismo do Bloco 7, sem código específico de bloco
- [x] Dívida com ação de troca abre `B8.01–B8.15`; dívida sem, não abre nada
- [x] Uma dívida com renegociação e outra com troca abrem blocos diferentes, cada um para a sua
- [x] Nenhuma decisão de "qual é o caso" é tomada na aplicação

**Status:** `[x] concluída`

---

### `T-77` — Implementar o Bloco 10 condicional a `ATAQUE_IMEDIATO_RECOMENDADO > 0`

- **Tipo:** `UI`
- **Dependências:** `T-74`, `T-18`, `T-33`
- **Dependência externa:** `OQ-17` (`ATAQUE_IMEDIATO_RECOMENDADO` não existe em `engine/`) — **RESOLVIDA**, ver nota abaixo
- **Rastreia:** `RF-18`, `AC-22`, `AC-24`
- **Arquivos:** `app/casos/confirmacao_ataque.py`, `app/http/rotas_bloco10.py`

**Dependência externa resolvida.** `motor-calculo:OQ-29` — a mesma questão que
a nota de bloqueio da Rodada 2 (fatia 2A, ver `T-120`) citava como pendência —
foi **"RESPONDIDA E IMPLEMENTADA POR COMPLETO"** pelo slug `motor-calculo`,
fatia 4C, especificada em 2026-09-10 (`specs/motor-calculo.spec.md` §14.2.4,
linha do índice de `OQ-29`). Confirmado por leitura direta desta rodada, não
de memória: `engine/diagnostico.py:657-658` declara
`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro` como campo real (não mais
comentário de "campo futuro"); `engine/diagnostico.py:715-735` documenta que o
placeholder `dinheiro(0)` que `calcular_diagnostico` ainda produz é **por
design** (a fórmula exige o elegível, que só existe depois dos gates) e que o
valor REAL é composto por uma segunda passada; `engine/motor.py:245-325`
(`_compor_ATAQUE_IMEDIATO_RECOMENDADO`) e `engine/motor.py:462-476` (dentro de
`calcular_plano`) confirmam essa segunda passada: `dataclasses.replace`
substitui o placeholder pelo valor real ANTES de `montar_SnapshotOrdem` ser
chamado. `engine/` está congelado para esta feature — nenhuma linha de
`engine/` foi tocada por `T-77`/`T-78`/`T-79`; a leitura é só consumo do
campo já publicado.

**Descrição**

`CONFIRMACAO_ATAQUE` só é alcançável quando o campo do snapshot é maior que
zero. `B10.C01` aceita aceite total, parcial ou nenhum. **Nenhuma pergunta pede
ao aluno escolher qual dívida receberá o recurso** — a ordem é do motor.

**Critérios de aceite**

- [x] `AC-22`: com `ATAQUE_IMEDIATO_RECOMENDADO = 0`, `B10.C01` não é exibida e o caso não entra em `CONFIRMACAO_ATAQUE`
- [x] `AC-24`: auditoria das perguntas exibidas no Bloco 10 confirma que nenhuma pede escolha de dívida
- [x] A condição lê o campo do snapshot, sem recomputar o valor recomendado
- [x] Aceite total, parcial e nenhum são os três caminhos possíveis, todos registrados como resposta

**Status:** `[x] concluída`

**Nota de implementação.** `app/casos/confirmacao_ataque.py` (módulo novo):
`ataque_imediato_recomendado_de(snapshot)` lê
`snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` por nome de campo, sem
recomputar; `bloco_10_alcancavel(snapshot)` é a guarda de
`PLANO_LIBERADO → CONFIRMACAO_ATAQUE` (gatilho `abre_bloco_10`, já declarado
em `app/casos/maquina.py::TABELA_TRANSICOES` desde `T-33` — esta tarefa
implementa a guarda que a transição já previa, não a topologia);
`perguntas_do_bloco_10` filtra `collection/registros/bloco-10.yaml` por
`registro.bloco == 10`, mesmo mecanismo de `app/casos/coleta_dirigida.py::
perguntas_do_bloco_7`. `app/http/rotas_bloco10.py` (módulo novo): `POST
/caso/{CASO_ID}/bloco-10/resposta`, especialização de `rotas_coleta.py` nos
mesmos sete passos do plano §5.1, restrita a `B10.C01`/`B10.C01A`, com a
guarda `bloco_10_alcancavel` avaliada ANTES de qualquer outro passo — sem
snapshot liberado, ou com recomendado `0`, a rota recusa `400` e nada é
gravado. Os três caminhos de `B10.C01` (`TODO`/`PARTE`/`NAO`, mais `REVISAR`
como quarta opção do registro) são sempre gravados como resposta — nenhum é
tratado como "não vale a pena registrar". Router **não** registrado em
`app/http/aplicacao.py` — mesmo precedente já usado por `T-75`
(`rotas_coleta_dirigida.py`) e `T-82` (`rotas_bloco11.py`): a integração final
do roteiro de rotas é trabalho de tarefa futura de orquestração, fora do
escopo declarado dos três arquivos desta tarefa; os testes de `T-79` montam a
aplicação e incluem o router manualmente, mesma técnica dos precedentes.
`ruff check .` e `mypy --strict` limpos; `tests/app_aluno/estatica/
test_fronteira_import_engine.py` (`AC-41`) passa **sem** nenhuma alteração na
allowlist — `snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` é acesso a
atributo sobre `SnapshotOrdem`/`Diagnostico`, já tipado por `engine.snapshot.
SnapshotOrdem` (liberado desde `T-16`), nunca um `import` novo de
`engine.diagnostico`.

---

### `T-78` — Validar `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO`

- **Tipo:** `UI`
- **Dependências:** `T-77`, `T-13`
- **Dependência externa:** `OQ-17` (mesmo campo ausente de `T-77`) — **RESOLVIDA**, ver nota de `T-77`
- **Rastreia:** `RF-18`, `AC-23`
- **Arquivos:** `collection/registros/bloco-10.yaml`, `app/casos/confirmacao_ataque.py`

**Descrição**

A validação é declarada no registro de `B10.C01A` e avaliada pelo comparador
genérico de `T-13`, com o limite superior vindo do campo do snapshot. Nenhum
limiar é escrito em código.

**Critérios de aceite**

- [x] `AC-23`: com recomendado `1000`, o valor `1500` é recusado com mensagem, e nada é gravado
- [x] Valor negativo é recusado pelo mesmo caminho
- [x] O limite superior vem do campo do snapshot, lido e não recalculado
- [x] A validação é declarativa no registro; nenhum literal de limite aparece em `.py`

**Status:** `[x] concluída`

**Nota de implementação.** `collection/registros/bloco-10.yaml::B10.C01A` já
declarava as duas `ValidacaoCruzada` desde `T-18` (limite inferior `ZERO <=
ATAQUE_IMEDIATO_APROVADO`; limite superior `ATAQUE_IMEDIATO_APROVADO <=
ATAQUE_IMEDIATO_RECOMENDADO`, nomeando literalmente o campo do snapshot) —
nada mudou no YAML nesta tarefa, ele já estava correto e à espera do campo
existir. O trabalho real foi a PONTE: o comparador genérico de `T-13`
(`collection/validacao.py::validar_cruzada`) só sabe consultar
`Respostas.valor_no_item` (uma fonte de respostas GRAVADAS,
`collection/respostas.py::RespostasCaso`), que nunca teve noção de campo de
snapshot. `RespostasDoBloco10` (`app/casos/confirmacao_ataque.py`, `@dataclass
(frozen=True, slots=True)`) satisfaz estruturalmente o mesmo `Protocol`
(mesma assinatura de `valor_no_item`), resolvendo as duas variáveis especiais
do registro (`ZERO`, `ATAQUE_IMEDIATO_RECOMENDADO`) a partir do snapshot —
`ZERO` via `app/montagem/conversao.py::converter_para_dinheiro("0")` (a
fronteira `Decimal` única, `RF-13`; nunca `Decimal(0)` direto — corrigido
depois que `tests/app_aluno/estatica/test_fronteira_decimal_unica.py` pegou a
primeira versão), `ATAQUE_IMEDIATO_RECOMENDADO` via a MESMA
`ataque_imediato_recomendado_de` que `T-77` já usa para a guarda — nunca uma
segunda leitura do campo. Qualquer outra variável (na prática,
`ATAQUE_IMEDIATO_APROVADO`, a resposta que o aluno acabou de dar) é delegada
sem alteração para a `RespostasCaso` real do caso. `app/http/rotas_bloco10.py`
usa `RespostasDoBloco10` no passo 5 (validação cruzada) exatamente como
`rotas_coleta.py`/`rotas_bloco11.py` usam `RespostasCaso` — a única troca é o
tipo passado a `validar_cruzada`, nenhuma lógica de validação duplicada.
Nenhum literal de limite em `.py`: `grep` em `app/casos/confirmacao_ataque.py`
e `app/http/rotas_bloco10.py` não encontra `1000`, `1500` nem qualquer valor
monetário fixo — só os NOMES das duas variáveis (`ZERO`,
`ATAQUE_IMEDIATO_RECOMENDADO`), que são os mesmos nomes do registro YAML.

---

### `T-79` — Testar a coleta dirigida e o Bloco 10 (`AC-19`, `AC-22`, `AC-23`, `AC-24`)

- **Tipo:** `Test`
- **Dependências:** `T-78`, `T-76`
- **Rastreia:** `RF-17`, `RF-18`, `AC-19`, `AC-22`, `AC-23`, `AC-24`
- **Arquivos:** `tests/app_aluno/test_coleta_dirigida.py`, `tests/app_aluno/test_bloco10.py`

**Descrição**

Snapshots de fixture com `ORDEM_ACOES` e `ATAQUE_IMEDIATO_RECOMENDADO`
controlados, e verificação do conjunto de perguntas efetivamente abertas.

**Critérios de aceite**

- [x] `AC-19`: o conjunto de perguntas abertas é exatamente o do Bloco 7 para `D002`
- [x] `AC-22`: recomendado zero não abre `B10.C01`
- [x] `AC-23`: `1500` sobre recomendado `1000` é recusado, com tolerância **zero**
- [x] `AC-24`: nenhuma pergunta aberta no Bloco 10 tem escolha de dívida como domínio
- [x] Os testes citam os `AC-NN` nos nomes

**Status:** `[x] concluída`

**Nota de implementação.** `AC-19` já estava integralmente coberto por
`tests/app_aluno/test_coleta_dirigida.py` (`T-75`/`T-76`, 14 testes, com
`test_ac19_bloco_7_abre_so_para_d002_com_renegociacao` e
`test_ac19_bloco_7_nao_abre_para_qualquer_outra_dividia_alem_da_sinalizada`
já nomeando o critério) — nada foi adicionado ali, só confirmado por reexecução
(`14 passed`) que nenhuma regressão de `T-77`/`T-78` o afetou. `tests/app_aluno/
test_bloco10.py` (novo, 13 testes) cobre `AC-22`/`AC-23`/`AC-24`: mesma técnica
de `tests/regras/test_ataque_imediato_recomendado_diagnostico.py` — um
`SnapshotOrdem` REAL produzido por `calcular_plano` sobre a fixture de caso
completo (`T-53`), com `ATAQUE_IMEDIATO_RECOMENDADO` CONTROLADO via
`dataclasses.replace` sobre `snapshot.diagnostico` (mesmo mecanismo já usado
por `tests/regras/test_repositorio_snapshots.py`), sem precisar reproduzir um
cenário completo de gates/necessidade-elegível só para obter um valor
positivo. Camada de domínio (`app/casos/confirmacao_ataque.py`) e camada HTTP
(`app/http/rotas_bloco10.py`, com o mesmo padrão de dublê em memória de
`tests/app_aluno/test_rotas_bloco11.py`/`test_rotas_coleta_dirigida.py`) são
cobertas separadamente. Tolerância ZERO verificada explicitamente em
`test_ac23_valor_parcial_igual_ao_recomendado_e_aceito` (`1000,00` sobre
recomendado `1000,00` é ACEITO — prova de que a validação usa `<=`, não `<`,
e não é conservadora demais) ao lado de
`test_ac23_valor_parcial_maior_que_recomendado_e_recusado` (`1500,00` sobre
`1000,00`, recusado). `pytest -q tests/app_aluno/test_bloco10.py
tests/app_aluno/test_coleta_dirigida.py` → `27 passed`. `ruff`/`mypy --strict`
limpos.

**Recongelamento de hashes (`AC-44`), parte desta rodada.** A Rodada 4/fatia
4C do `motor-calculo` (que resolveu `OQ-17`/`OQ-29`, ver nota de `T-77`) tocou
`engine/ataque_imediato.py`, `engine/diagnostico.py`, `engine/estado.py`,
`engine/gates.py`, `engine/motor.py` e `persistencia/arquivo/
repositorio_snapshots.py`, além de criar `engine/classificacao_ativos.py`
(fatia 4A, ainda não listado) — exatamente a divergência de hash que
`tests/app_aluno/estatica/test_engine_congelado.py` é desenhado para pegar, e
exatamente o gatilho que a sinalização de Rodada 2/`T-116`/`T-140`/`T-151` do
`motor-calculo` previa. Confirmado, antes de recongelar, que nenhuma das seis
mudanças veio de `T-77`/`T-78`/`T-79` (nenhuma tarefa desta rodada editou
`engine/` nem `persistencia/`) — as seis são consequência das fatias 4A/4B/4C
do `motor-calculo`, documentadas nas próprias docstrings dos arquivos
(`RESERVA_MOBILIZAVEL` real, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`,
classificação de ativos/investimentos, ligação de `ATAQUE_IMEDIATO_
RECOMENDADO`). `tests/app_aluno/estatica/hashes_congelados.json` foi
regravado por inteiro (35 entradas, mesmo procedimento de `_descobrir_
conjunto_congelado_em_disco()`: todo `.py` de `engine/`, de `persistencia/
arquivo/`, de `persistencia/supabase/`, mais `001_inicial.sql`) — as seis
entradas divergentes foram atualizadas e `engine/classificacao_ativos.py`
entrou como entrada nova. `tests/app_aluno/estatica/test_engine_congelado.py`
→ `4 passed` depois do recongelamento.

---

### `T-121` — Registrar `app.http.rotas_bloco10.roteador` em `criar_aplicacao()`

- **Tipo:** `UI`
- **Dependências:** `T-77`
- **Rastreia:** `RF-18`
- **Arquivos:** `app/http/aplicacao.py`

**Descrição**

`T-77` criou `app/http/rotas_bloco10.py` mas, seguindo o mesmo precedente já
registrado no backlog para `rotas_coleta_dirigida.py` (`T-75`) e
`rotas_bloco11.py` (`T-82`), deixou a integração final ao roteiro de rotas
para uma tarefa própria de orquestração — a nota de fechamento de `T-77` cita
essa decisão explicitamente. Esta tarefa é essa integração: sem ela, a rota
`POST /caso/{CASO_ID}/bloco-10/resposta` existe em código e é exercitada
pelos testes de `T-79` (que montam a aplicação e incluem o router
manualmente), mas não é alcançável por uma instância real de
`criar_aplicacao()` — logo, não aparece na aplicação que sobe via `uvicorn`.

**Critérios de aceite**

- [x] `app/http/aplicacao.py` importa `app.http.rotas_bloco10.roteador` e
      chama `aplicacao.include_router(...)`, mesmo padrão das oito rotas já
      registradas
- [x] Nenhuma outra linha de `aplicacao.py` é alterada além do import e do
      `include_router`
- [x] A aplicação sobe (`uvicorn app.http.aplicacao:criar_aplicacao --factory`)
      sem erro, com `CHAVE_ASSINATURA_SESSAO` definida
- [x] `tests/app_aluno/e2e/test_mecanismo_isolamento.py` (auditoria de
      isolamento por `CASO_ID` sobre toda `APIRoute` registrada) continua
      passando — a nova rota tem `CASO_ID` na URL e usa
      `exigir_caso_da_sessao`, mesmo mecanismo das rotas de coleta

**Status:** `[x] concluída`

**Nota de implementação.** Duas linhas em `app/http/aplicacao.py`: import de
`app.http.rotas_bloco10.roteador as roteador_bloco10` (mesmo estilo de alias
das outras oito) e `aplicacao.include_router(roteador_bloco10)`, na mesma
posição relativa (depois de `roteador_calculo`, antes de `roteador_plano` —
ordem cronológica de criação das rotas). Nenhuma outra linha tocada.
`tests/app_aluno/e2e/test_mecanismo_isolamento.py` passa sem alteração: a
rota de `T-77` já declarava `CASO_ID` na URL e chamava
`exigir_caso_da_sessao`, mesmo mecanismo de `rotas_coleta.py`, então a
auditoria a reconhece automaticamente ao enumerar `APIRoute`. `ruff check .`
e `mypy --strict` limpos; `pytest -q` → `1495 passed, 75 skipped` (mesma
contagem de antes — esta tarefa só liga uma rota já testada isoladamente,
não adiciona comportamento novo).

---

### `T-80` — Implementar a reabertura de faixa de perguntas (`AC-34`)

- **Tipo:** `Data`
- **Dependências:** `T-75`, `T-44`
- **Rastreia:** `RF-27`, `AC-34`
- **Arquivos:** `app/casos/reabertura.py`

**Descrição**

Reabertura é da **pergunta**, não do estado do caso: o que muda é o conjunto de
perguntas pendentes. Reabrir uma faixa (`B7.05–B7.16`) marca essas perguntas
como pendentes **sem apagar** o valor anterior.

**Critérios de aceite**

- [x] `AC-34`: reabrir renegociação torna pendentes exatamente `B7.05` a `B7.16` para a dívida da ação, e nenhuma pergunta anterior a `B7.05` é reexibida
- [x] O valor anterior das perguntas reabertas permanece gravado e visível como valor atual
- [x] O estado do caso **não** muda por causa da reabertura
- [x] A faixa é declarada no registro/ação, não como lista literal em `.py`

**Status:** `[x] concluída`

---

## Entrega 10 — Bloco 11: reportar execução e recalcular sobre a realidade

### `T-81` — Implementar `app/eventos/mapeamento.py`

- **Tipo:** `Data`
- **Dependências:** `T-18`
- **Rastreia:** `RF-28`, `AC-35`
- **Arquivos:** `app/eventos/mapeamento.py`

**Descrição**

Resposta do Bloco 11 → membro de `EVENTO_RECALCULO`. Alteração cadastral ou
cosmética **não tem membro no enum**: é inexprimível por construção (`R-04`) —
`AC-35` é satisfeito pelo tipo, não por um `if`. Virada de mês não dispara nada.

**Critérios de aceite**

- [x] `AC-35`: não existe caminho de código que produza um `EVENTO_RECALCULO` a partir de alteração cadastral — o enum não tem membro para isso
- [x] Nenhuma passagem de tempo dispara evento; não há leitura de relógio no módulo
- [x] O mapeamento resposta → membro é por `valor_interno` do registro, sem `if` por pergunta
- [x] Resposta sem evento correspondente devolve ausência explícita, nunca um membro genérico

**Status:** `[x] concluída`

---

### `T-82` — Implementar a confirmação de quitação `B11.Q01–Q06`

- **Tipo:** `UI`
- **Dependências:** `T-81`, `T-33`, `T-12`
- **Rastreia:** `RF-29`, `AC-05`, `AC-30`, `AC-31`
- **Arquivos:** `app/casos/acompanhamento.py`, `app/http/rotas_bloco11.py`

**Descrição**

`B11.Q01 = Sim` marca `STATUS_QUITACAO_REAL = QUITADA` e é gatilho de recálculo.
*"Acredito que sim, mas ainda preciso confirmar"* (`A_CONFIRMAR`) **não dispara
nada**. O enunciado interpola o `DIVIDA_ID` da ficha corrente.

**Critérios de aceite**

- [x] `AC-31`: `A_CONFIRMAR` não dispara recálculo e não altera o status da dívida
- [x] `B11.Q01 = Sim` marca `QUITADA` e identifica o evento de recálculo (`EVENTO_RECALCULO.QUITACAO_CONFIRMADA`, via `app/eventos/mapeamento.py`, T-81) — ver nota de fronteira com `T-86` abaixo
- [x] `AC-05`: o enunciado exibe o `DIVIDA_ID` da ficha corrente no lugar de `[Dxxx]`
- [x] `B11.Q02–Q06` são coletadas na sequência declarada no registro

**Fronteira com `T-83` (`ACAO_ID` vs. `DIVIDA_ID`).** `collection/registros/
bloco-11.yaml` já declara `escopo_repeticao: ACAO_ID` para `B11.Q01`–`B11.Q06`
(T-18, `AC-50`), mas `engine.gates.AcaoRequerida` (hoje) só publica
`DIVIDA_ID` — não existe `ACAO_ID` real no contrato do motor (`OQ-10`,
dependência externa de `motor-calculo` que bloqueia `T-83`). Por isso esta
tarefa usa `DIVIDA_ID` como identificador do item corrente para a
interpolação `[Dxxx]` (`AC-05`, que é sobre TEXTO exibido, não sobre chave de
gravação) e não constrói nada que dependa de um `ACAO_ID` real existir —
`app/casos/acompanhamento.py` documenta a simplificação em detalhe. `T-83` é
quem revisita isso e passa a vincular a GRAVAÇÃO por `ACAO_ID`.

**Fronteira com `T-86` (execução do recálculo).** "Enfileira o recálculo",
nesta tarefa, significa exclusivamente IDENTIFICAR o `EVENTO_RECALCULO`
correspondente à resposta de `B11.Q01` e devolvê-lo pronto na resposta HTTP
(`app/http/rotas_bloco11.py::responder_confirmacao_quitacao`) — nunca
disparar o executor. Nenhum código desta tarefa importa `app/motor/
executor.py` (que não existe: nasce em `T-86`), chama `engine.eventos.
avaliar_gatilho_recalculo`/`engine.motor.calcular_plano`, ou aciona a
transição `ACOMPANHAMENTO → CALCULANDO` (`app/casos/maquina.py`, gatilho
`recalcula`). `T-86` é quem consome o evento identificado aqui e constrói o
executor real (`anterior`, `evento`, `motivo`, versionamento do snapshot).

**Status:** `[x] concluída`

---

### `T-83` — Vincular a resposta do Bloco 11 por `ACAO_ID`, nunca por `DIVIDA_ID`

- **Tipo:** `Data`
- **Dependências:** `T-82`, `T-74`, `T-15`
- **Rastreia:** `RF-27`, `RF-33`, `AC-50`
- **Dependência externa:** `motor-calculo` (`ACAO_ID`/`TIPO_ACAO` em `AcaoRequerida`)
- **Arquivos:** `app/casos/acompanhamento.py`, `persistencia/app_aluno/respostas.py`

**Descrição**

A chave de vínculo da resposta do Bloco 11 é `ACAO_ID`. Isso satisfaz `AC-50`
**qualquer que seja a resposta de `OQ-15`**: ação sem dívida associada não
impede `B11.01` nem `B11.03-ECO`.

**Critérios de aceite**

- [x] `AC-50`: uma ação sem `DIVIDA_ID` é exibida no Bloco 11 e sua resposta é gravada, vinculada ao `ACAO_ID` — provado aqui na INTERFACE (`item_id_do_bloco_11` sobre um objeto de teste com `ACAO_ID`, com e sem `DIVIDA_ID`); a prova ponta a ponta (exibição HTTP + gravação via `RepositorioRespostas`) é `T-89`, que consome exatamente esta função
- [x] Nenhum caminho de código exige `DIVIDA_ID` presente para exibir ou gravar resposta do Bloco 11 — `item_id_do_bloco_11`/`acao_id_de` nunca leem `DIVIDA_ID`; `persistencia/app_aluno/respostas.py` já era genérico sobre `item_id: str | None` (nenhuma edição necessária ali)
- [x] O `item_id` da `Resposta` do Bloco 11 é o `ACAO_ID` — `item_id_do_bloco_11(acao) == acao.ACAO_ID`, sem derivação
- [x] Enquanto `ACAO_ID` não existir em `AcaoRequerida`, o módulo falha ruidosamente na fronteira — `acao_id_de` levanta `ErroAcaoIdAusenteDoMotor` (nomeando `T-83`/`OQ-10`) sobre uma `AcaoRequerida` REAL, nunca cai em `DIVIDA_ID`

**Status:** `[x] concluída`

---

### `T-84` — Ramificar `B11.03-*` por `TIPO_ACAO` a partir de registro

- **Tipo:** `Data`
- **Dependências:** `T-83`, `T-18`
- **Rastreia:** `RF-27`, `RF-33`, `AC-46`
- **Dependência externa:** `motor-calculo` (`TIPO_ACAO`) e `OQ-13` (identificador exato) — **`OQ-13` respondida**: domínio fechado `INFORMACAO`, `RENEGOCIACAO`, `TROCA`, `ECONOMIA` (ASCII, sem parênteses). Ver nota pós-fechamento abaixo — o registro ainda usa os placeholders pré-decisão e precisa da edição que esta própria tarefa já previa (`T-104`, tarefa nova)
- **Arquivos:** `app/motor/acoes.py`, `collection/registros/bloco-11.yaml`

**Descrição**

`perguntas_do_bloco_11(a)` ramifica por `TIPO_ACAO`, e o mapeamento tipo →
pergunta vive num **registro**, não em código. **Nenhum literal de `TIPO_ACAO` é
escrito nesta feature** — o domínio é o que `engine/` publicar (`OQ-13`).

**Critérios de aceite**

- [x] Nenhum literal de valor de `TIPO_ACAO` aparece em `.py` — verificado por teste estático
- [x] O mapeamento tipo → pergunta é lido do YAML; responder `OQ-13` é edição de registro
- [x] Tipo desconhecido no mapeamento falha ruidosamente, nomeando o valor recebido — nunca escolhe uma pergunta por padrão
- [x] A função devolve exatamente uma pergunta de resultado por ação

**Status:** `[x] concluída`

**Atualização pós-fechamento de Open Questions.** `OQ-13` foi respondida:
`TIPO_ACAO` é domínio fechado de quatro valores ASCII sem parênteses —
`INFORMACAO`, `RENEGOCIACAO`, `TROCA`, `ECONOMIA`. `collection/registros/
bloco-11.yaml` (`B11.03-INF`/`-REN`/`-TRO`/`-ECO`) ainda declara os
placeholders literais da canônica tal como citados na spec antes da decisão —
`"INFORMAÇÃO"`, `"INTERVENÇÃO (renegociação)"`, `"TROCA"`, `"CORREÇÃO
(economia)"` — com acento e parênteses, incompatíveis com o identificador que
`engine/` vai publicar quando o slug `motor-calculo` implementar `TIPO_ACAO`.
Como o próprio critério de aceite desta tarefa já previa, "responder `OQ-13`
é edição de registro" — não é retrabalho de código, é a tarefa nova
`T-104` abaixo.

---

### `T-85` — Implementar a reabertura de campo isolado (`AC-33`)

- **Tipo:** `Data`
- **Dependências:** `T-84`, `T-80`
- **Rastreia:** `RF-27`, `AC-33`
- **Dependência externa:** `motor-calculo` (`OQ-14`, Gate 1 emitir ação) e `OQ-18` (novo campo de "qual pergunta ficou pendente") — **ambas respondidas** (decisão: Gate 1 passa a emitir ação; novo campo `CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]` em `AcaoRequerida`); falta só o slug `motor-calculo` implementar. Quando implementado, `campo_para_reabertura_informacao` mapeia `STATUS_DIVIDA → B5.D01A` e `SALDO_DEVEDOR_ATUAL → B5.B03`, os dois exemplos que `RF-27` já cita
- **Arquivos:** `app/casos/reabertura.py`

**Descrição**

`RESULTADO_ACAO_INFORMACAO = Sim` reabre **exclusivamente** o campo que faltava
(ex.: `B5.B03`), e o caso **permanece em `ACOMPANHAMENTO`** — não volta a
`COLETA_INICIAL`. É reabertura de pergunta, não de bloco.

**Lacuna nova descoberta nesta tarefa — registrada como `OQ-18` na spec.**
`engine.gates.AcaoRequerida` (e `ResultadoGates`) não têm, hoje, NENHUM campo
que aponte qual `RegistroPergunta.ID` ficou pendente (`B5.B03` vs. `B5.D01A`,
os dois exemplos da própria `RF-27`) — nem `DIVIDA_ID`, nem `descricao` (cujo
parsing é proibido desde `T-74`), nem `gate_origem`. Além disso,
`engine/gates.py::aplicar_gate_1_informacao` hoje devolve `acao=None` em
AMBOS os ramos de bloqueio — o Gate 1 **ainda não emite** `AcaoRequerida`
nenhuma (`OQ-14`, dependência externa já registrada). Confirmado por leitura
direta do código (`engine/gates.py:204,221` e o dataclass `AcaoRequerida`) e
por revisão de `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15` (nenhuma cobria "qual campo
da dívida está pendente"). Ver `OQ-18` em `specs/app-aluno.spec.md`.

**Critérios de aceite**

- [x] `AC-33`: apenas `B5.B03` é reaberto; nenhuma outra pergunta do Bloco 5 é exibida — implementado e testado com `id_pergunta`/`divida_id` como parâmetro explícito (`perguntas_pendentes_por_reabertura_informacao`), com fixture de teste que já conhece o campo (mesmo padrão de T-83/T-84); a EXTRAÇÃO do campo a partir de uma `AcaoRequerida` real (`campo_para_reabertura_informacao`) está bloqueada pela lacuna acima e falha ruidosamente com `ErroCampoDeInformacaoIndeterminavel`
- [x] O estado do caso permanece `ACOMPANHAMENTO` durante toda a reabertura — testável e testado hoje, independente do bloqueio: nenhuma importação/uso de `app.casos.maquina`, `transicionar`, `ESTADO_CASO` ou `TABELA_TRANSICOES` em `app/casos/reabertura.py` (auditoria de AST herdada de T-80, reforçada com teste específico de T-85)
- [x] O campo a reabrir vem da ação, não de uma lista em código — satisfeito pela garantia estrutural: não há, no contrato atual do motor, nenhum campo em `AcaoRequerida`/`ResultadoGates` do qual derivar "a ação aponta para `B5.B03`", e `campo_para_reabertura_informacao` recusa nomeadamente em vez de inventar um literal — o critério exige "não uma lista em código", e nenhuma lista existe; a extração fica bloqueada por `OQ-14`/`OQ-18`, não implementada com atalho
- [x] Responder o campo reaberto fecha a pendência sem reabrir o bloco inteiro — `perguntas_pendentes_por_reabertura_informacao` sempre devolve exclusivamente o par `(id_pergunta, divida_id)` pedido, nunca a faixa do bloco; testado

**Status:** `[x] concluída` — dentro do que é possível hoje: a extração do campo a partir de uma `AcaoRequerida` real depende de `OQ-14` (Gate 1 emitir ação) e `OQ-18` (qual campo ficou pendente), ambas dependências externas do slug `motor-calculo` registradas na spec; o mecanismo de reabertura em si (parâmetro explícito, sem transição de estado, sem reabrir bloco inteiro) está implementado e testado

---

### `T-86` — Implementar o recálculo com `anterior`, `evento` e `motivo`

- **Tipo:** `Infra`
- **Dependências:** `T-85`, `T-82`, `T-54`, `T-68`
- **Rastreia:** `RF-01`, `RF-19`, `RF-28`, `AC-26`, `AC-30`, `EC-11`
- **Arquivos:** `app/motor/executor.py`, `app/casos/acompanhamento.py`

**Descrição**

`calcular_plano(..., anterior=snapshot_corrente, evento=..., motivo=...)` produz
`versao+1` com `snapshot_anterior_id` encadeado, e o novo snapshot vai **para a
fila de novo**. Com evento, versiona mesmo se `hash_inputs` for idêntico
(`R-05`, `EC-11`).

**Critérios de aceite**

- [x] `AC-30`: o novo snapshot tem `versao = anterior.versao + 1` e `snapshot_anterior_id = anterior.SNAPSHOT_ID`, e o anterior permanece íntegro e recuperável
- [x] `AC-26`: o snapshot de recálculo entra na fila de revisão como qualquer outro
- [x] `EC-11`: com evento e `hash_inputs` idêntico, o snapshot é versionado assim mesmo
- [x] O recálculo passa pelo mesmo executor do Bloco 6, sem segunda via de invocação do motor

**Nota de implementação.** `app/motor/executor.py` (T-54/T-55) já aceitava
`anterior`/`evento`/`motivo` em `ParametrosDoCalculo` e já repassava os três
para `calcular_plano` — nenhuma extensão de assinatura foi necessária ali.
O que faltava era o CONSUMO real: `app/casos/acompanhamento.py::
disparar_recalculo`/`disparar_recalculo_async` busca o `anterior` (último
snapshot do histórico do caso), transiciona `ACOMPANHAMENTO → CALCULANDO`
(gatilho `recalcula`, `app/casos/maquina.py`, com a mesma trava condicional
de `T-56`) e delega a `executar_calculo`/`executar_calculo_async` — nunca
uma segunda chamada a `engine.motor.calcular_plano`. `AC-26` e `EC-11` são
garantias herdadas sem lógica nova (fila de `app/revisao/fila.py` e
versionamento sempre-que-há-evento do motor, respectivamente), provadas em
`tests/app_aluno/test_disparar_recalculo.py` com `calcular_plano` real
encadeando duas versões (1 → 2) e a entrada na fila.

**Status:** `[x] concluída`

---

### `T-87` — Impedir que alteração cadastral dispare recálculo (`AC-35`)

- **Tipo:** `UI`
- **Dependências:** `T-86`, `T-81`
- **Rastreia:** `RF-28`, `AC-35`
- **Arquivos:** `app/casos/acompanhamento.py`

**Descrição**

Correção de nome ou rótulo é gravada como resposta e **nada mais acontece**: nem
recálculo, nem snapshot novo. A garantia é estrutural (o enum não tem membro),
mas a rota precisa não fabricar um evento genérico.

**Critérios de aceite**

- [x] `AC-35`: correção de rótulo é salva e nenhum snapshot novo é criado
- [x] Nenhuma rota constrói `EVENTO_RECALCULO` a partir de resposta que não seja evento material ou quitação confirmada
- [x] Alteração cadastral fica registrada na trilha do caso, sem transição de estado
- [x] Um teste garante que o número de snapshots do caso não muda

**Nota de implementação.** A garantia estrutural já existia (`T-81`: o enum
`EVENTO_RECALCULO` não tem membro para alteração cadastral). O que faltava
era a ORQUESTRAÇÃO explícita que conecta os três passos sem nunca fabricar
um evento genérico — `app/casos/acompanhamento.py::processar_resposta_
bloco_11`/`processar_resposta_bloco_11_async` (novas): identificam o evento
pela MESMA função que a rota já usava (`evento_da_resposta_b11_q01`, T-82,
sobre `app.eventos.mapeamento.evento_recalculo_da_resposta`, T-81) e só
chamam `disparar_recalculo`/`disparar_recalculo_async` (T-86) quando o
resultado não é `None`; caso contrário chamam `registrar_alteracao_
cadastral` (nova), que grava a trilha (`app_aluno.eventos_caso`, T-21) sem
tocar `estado`. `app/http/rotas_bloco11.py` (T-82) não foi tocada: ela já
não disparava recálculo algum (só devolvia o evento identificado no JSON),
então já satisfazia "nenhuma rota constrói `EVENTO_RECALCULO` a partir de
resposta que não seja evento material ou quitação confirmada" antes desta
tarefa — confirmado por auditoria de AST (`tests/app_aluno/
test_processar_resposta_bloco_11_ac35.py::
test_unico_ponto_de_construcao_de_evento_recalculo_a_partir_de_resposta`)
sobre TODO `app/`, não só sobre este módulo. Mecanismo de trilha NOVO:
`app_aluno.eventos_caso` (T-21) não tinha nenhum repositório até esta
tarefa — `persistencia/app_aluno/eventos.py::RepositorioEventosCaso`
(Postgres) e a extensão de `persistencia/app_aluno/arquivo.py`
(`RepositorioEventosCasoArquivo`) foram criados como o "repositório simples"
que a descrição da tarefa previa, fora da lista oficial de arquivos mas
dentro do espírito documentado (mesmo padrão dos três repositórios
irmãos: `respostas.py`, `casos.py`, `itens.py`).

**Status:** `[x] concluída`

---

### `T-88` — Testar o ciclo do Bloco 11 e o encadeamento de snapshots

- **Tipo:** `Test`
- **Dependências:** `T-87`
- **Rastreia:** `RF-27`, `RF-28`, `RF-29`, `AC-26`, `AC-30`, `AC-31`, `AC-33`, `AC-34`, `AC-35`, `EC-11`
- **Arquivos:** `tests/app_aluno/integracao/test_bloco11.py`

**Descrição**

`US-08` ponta a ponta com o adaptador de arquivo: reportar, recalcular,
encadear, voltar à fila — sem apagar histórico.

**Critérios de aceite**

- [x] `AC-30`: encadeamento verificado com tolerância **zero** para `versao` e `snapshot_anterior_id`
- [x] `AC-31` e `AC-35`: nenhum recálculo disparado; contagem de snapshots inalterada
- [x] `AC-33` e `AC-34`: conjunto de perguntas pendentes conferido exatamente, sem sobra nem falta
- [x] `AC-26`: o snapshot de recálculo está em `AGUARDANDO_REVISAO`
- [x] `EC-11`: evento com `hash_inputs` idêntico produz nova versão

**Nota de implementação.** Cada critério já tinha prova FOCADA pré-existente,
chamando a função de domínio diretamente (sem HTTP): `AC-30`/`AC-26`/`EC-11`
em `tests/app_aluno/test_disparar_recalculo.py` (T-86); `AC-31`/`AC-35` em
`tests/app_aluno/test_processar_resposta_bloco_11_ac35.py` (T-87);
`AC-33`/`AC-34` em `tests/app_aluno/test_reabertura.py` (T-80/T-85). Esta
tarefa RODA essas três suítes como confirmação executável
(`test_cobertura_preexistente_*`) e ACRESCENTA o ângulo que faltava: os
cinco critérios no MESMO fluxo contínuo, disparado por uma requisição HTTP
REAL sobre `app/http/rotas_bloco11.py::roteador` (T-82) — reportar (`POST
/caso/{CASO_ID}/bloco-11/resposta`) → identificar o evento (a própria rota)
→ recalcular (`processar_resposta_bloco_11`, T-87, consumindo exatamente o
`evento_recalculo` devolvido pela rota) → encadear (`AC-30`) → voltar à fila
(`AC-26`) → nova reabertura (`AC-33`) sobre o snapshot recalculado, sem
apagar o histórico do snapshot raiz em nenhum passo. Adaptador de arquivo
(T-24) em todo o fluxo, sem `DATABASE_URL`.

**Status:** `[x] concluída`

---

### `T-89` — Testar `AC-50` (ação sem dívida) sobre o vínculo por `ACAO_ID`

- **Tipo:** `Test`
- **Dependências:** `T-83`
- **Rastreia:** `RF-33`, `AC-50`
- **Arquivos:** `tests/app_aluno/test_acao_sem_divida.py`

**Descrição**

`AC-50` **é testável agora**, porque depende só de a chave de vínculo ser
`ACAO_ID` e não `DIVIDA_ID` — independe de `OQ-15` e das três mudanças em
`engine/`. Usa uma `AcaoRequerida` de fixture sem dívida associada.

**Critérios de aceite**

- [x] `AC-50`: ação sem `DIVIDA_ID` é exibida no Bloco 11 e sua resposta é gravada
- [x] O teste não usa `xfail` — passa hoje
- [x] A fixture de ação sem dívida é construída sem inventar identificador de tipo (`OQ-13`)
- [x] O teste cita `AC-50` no nome

**Status:** `[x] concluída`

---

### `T-90` — Escrever `AC-45`..`AC-49` como testes `xfail(strict=True)`

- **Tipo:** `Test`
- **Dependências:** `T-84`, `T-89`
- **Rastreia:** `RF-33`, `AC-45`, `AC-46`, `AC-47`, `AC-48`, `AC-49`
- **Dependência externa:** `motor-calculo` (as três mudanças em `engine/gates.py::AcaoRequerida`)
- **Arquivos:** `tests/app_aluno/test_ordem_acoes_dependencia_externa.py`

**Descrição**

Os cinco critérios que dependem das três mudanças do slug `motor-calculo` são
**escritos agora** e marcados `xfail(strict=True)`: viram verde no dia da
entrega e falham ruidosamente se alguém os der por satisfeitos antes.

**Critérios de aceite**

- [x] `AC-45`: `ACAO_ID` idêntico entre dois snapshots consecutivos da mesma ação
- [x] `AC-46`: cada tipo abre exclusivamente a sua pergunta de resultado, os quatro tipos cobertos
- [x] `AC-47`: dívida bloqueada pelo Gate 1 tem ação de tipo informação em `ORDEM_ACOES`
- [x] `AC-48` e `AC-49`: tipagem de renegociação/troca e emissão da ação de economia conforme `ECONOMIA_POTENCIAL_IMEDIATA`
- [x] Os cinco estão marcados `xfail(strict=True)` com `reason` citando o slug `motor-calculo` e as três mudanças
- [x] Nenhum literal de `TIPO_ACAO` é escrito nos testes (`OQ-13` aberta)

**Status:** `[x] concluída`

---

## Entrega 11 — Abandono observável e fechamento do piloto

### `T-91` — Registrar a trilha de eventos do caso

- **Tipo:** `Data`
- **Dependências:** `T-23`, `T-33`
- **Rastreia:** `RF-31`, `AC-40`, `EC-14`
- **Arquivos:** `app/casos/progresso.py`, `persistencia/app_aluno/eventos.py` — mais
  extensão estritamente necessária (`transicionar_e_registrar` precisa de um
  chamador em cada ponto de transição real): `app/http/rotas_consentimento.py`,
  `app/http/rotas_calculo.py`, `app/revisao/fila.py`,
  `app/casos/acompanhamento.py`, `app/motor/executor.py` (não listado
  nominalmente pela tarefa, mas é o único lugar que persiste as quatro
  transições de `EC-03`/`EC-04`/`EC-06` — sem tocá-lo o critério "toda
  transição grava um evento" ficaria incompleto), `app/http/rotas_revisao.py`
  (injeção do novo repositório na rota de decisão) e
  `persistencia/app_aluno/{arquivo.py,respostas.py}` (critério 2:
  `ultima_interacao_em` atualizada a cada resposta gravada, não só a cada
  transição — extensão aditiva do adaptador de arquivo com parâmetro opcional
  `repositorio_casos=None`, sem quebrar uso pré-existente)

**Descrição**

Toda transição de estado e todo marco de progresso é gravado em `eventos_caso`,
com data. É o que torna o abandono observável em vez de silencioso.

**Critérios de aceite**

- [x] Toda transição da máquina grava um evento com origem, destino, gatilho e data
- [x] `ultima_interacao_em` do caso é atualizada a cada resposta gravada
- [x] Nenhum evento contém valor monetário, saldo, renda ou identificador pessoal
- [x] `EC-14`: um caso parado há meses continua retomável com todas as respostas

**Nota de implementação.** Abordagem: um wrapper único,
`app/casos/progresso.py::transicionar_e_registrar(*, repositorio_casos,
repositorio_eventos, caso_id, de, para, agora=None, detalhe=None) -> Caso |
None`, que faz os três passos que toda transição de produção precisa —
(1) validar `(de, para)` contra `app.casos.maquina.transicionar` (nunca uma
transição forçada fora da tabela); (2) persistir via
`RepositorioCasos.transicionar_estado_se` (a variante condicional, a mesma
trava de concorrência de `T-56` — nunca a incondicional
`transicionar_estado`, que reabriria a corrida dupla que aquela tarefa já
fechou); (3), só quando a transição de fato ocorreu, gravar um `EventoCaso`
com `tipo_evento` igual ao `gatilho` nomeado pela própria `Transicao` da
tabela. Quando a condição não vale mais (corrida perdida), devolve `None` sem
gravar nenhum evento — não houve transição real. Os cinco módulos que já
chamavam `transicionar`/`transicionar_estado_se` diretamente
(`rotas_consentimento.py`, `rotas_calculo.py`, `app/revisao/fila.py`,
`app/casos/acompanhamento.py`, `app/motor/executor.py`) foram ajustados para
chamar o wrapper em vez de duplicar a lógica de "montar `EventoCaso` +
`uuid` + chamar o repositório" em nove pontos — extensão de escopo
documentada acima, mesmo precedente de `T-30`/`T-87`. `ParametrosDoCalculo`
(`app/motor/executor.py`) ganhou o campo `repositorio_eventos`, propagado
pelos dois chamadores de produção (`rotas_calculo.py`,
`acompanhamento.py`) e por todos os testes que constroem esse dataclass.
Critério 2: `RepositorioRespostasSupabase.gravar` (Postgres) passou a
incluir um `UPDATE casos SET ultima_interacao_em = %s` na MESMA transação do
`INSERT` da resposta (usando `resposta.respondida_em`, o carimbo real da
interação); `RepositorioRespostasArquivo` ganhou um parâmetro opcional
`repositorio_casos: RepositorioCasosArquivo | None = None` no construtor
(default `None`, sem quebrar nenhum uso pré-existente) que, quando fornecido,
chama `registrar_interacao` depois de anexar a linha. Critério 3
(allowlist): `EventoCaso` já só declarava os sete campos estruturais desde
T-87 (`evento_id`, `CASO_ID`, `tipo_evento`, `estado_de`, `estado_para`,
`detalhe`, `ocorrido_em`) — nenhum campo novo foi adicionado, e `detalhe` é
sempre um motivo técnico curto ou `None` nos chamadores desta tarefa, nunca
um valor de resposta. Testado em
`tests/app_aluno/test_transicionar_e_registrar.py` (11 testes, os quatro
critérios, incluindo `EC-14` com hiato de 180 dias e retomada). Testes de
rota HTTP pré-existentes que usavam dublês de `RepositorioCasos` foram
ajustados para implementar `transicionar_estado_se` de verdade (em vez de
`NotImplementedError`) e para injetar o novo repositório de eventos —
listados no campo `Arquivos` acima onde tocaram produção; os demais são
apenas ajuste de teste, não listados como extensão de escopo.

**Status:** `[x] concluída`

---

### `T-92` — Implementar a consulta de trilha de progresso

- **Tipo:** `Data`
- **Dependências:** `T-91`
- **Rastreia:** `RF-31`, `AC-40`
- **Arquivos:** `app/casos/progresso.py`

**Descrição**

Consulta que devolve, por caso, o estado atual, em que bloco/pergunta parou, o
que aguarda revisão e a data da última interação. **A trilha é entregue como
dado consultável**; a interface dedicada do operador é `T-102` (`RF-35`,
`OQ-07` respondida).

**Critérios de aceite**

- [x] `AC-40`: para um conjunto de casos em estados diferentes, cada um reporta seu estado atual e a data da última interação
- [x] A consulta indica a pergunta em que o caso parou, derivada do mesmo mecanismo de retomada de `T-45`
- [x] A consulta não expõe dado financeiro do aluno
- [x] O módulo registra que a interface dedicada é tarefa separada (`T-102`), sem antecipá-la

**Nota de implementação.** `consultar_trilha_de_progresso(caso, registros,
respostas, itens_por_escopo=None) -> RelatoDeProgresso`, acrescentada a
`app/casos/progresso.py`. `RelatoDeProgresso` (`frozen=True, slots=True`) tem
exatamente cinco campos estruturais: `CASO_ID`, `estado` (`ESTADO_CASO`),
`ultima_interacao_em` (lidos direto de `Caso`, sem recalcular), `proxima_
pergunta: PendenciaObrigatoria | None` (devolvido por `proxima_pergunta_
nao_respondida`, T-45, reaproveitada sem duplicar lógica) e
`aguardando_revisao: bool` (`caso.estado is ESTADO_CASO.AGUARDANDO_REVISAO`).
Nenhum campo de `Resposta`/`ValorResposta` ou de `EstadoFinanceiro`/
`SnapshotOrdem` entra na composição — só o `ID` da pergunta em aberto, nunca
o valor respondido. Função pura, sem I/O: os dados (`Caso`, `registros`,
`RespostasCaso`, `itens_por_escopo`) chegam já montados pelo chamador, mesma
disciplina de `pendencias_obrigatorias`/`proxima_pergunta_nao_respondida`
(T-44/T-45) — preserva a fronteira de `tests/app_aluno/estatica/
test_fronteira_import_engine.py` (T-06). O módulo documenta em prosa (seção
"T-92" do docstring do módulo) que a interface dedicada do operador é tarefa
separada (`T-102`, `RF-35`) e não é antecipada aqui: nenhuma rota HTTP,
nenhum template, nenhum `app/http/` tocado por esta tarefa. Testado em
`tests/app_aluno/test_consulta_trilha_de_progresso.py` (7 testes, os quatro
critérios, com casos reais em quatro estados diferentes via `Repositorio
CasosArquivo`, sem `DATABASE_URL`, e a coleção real de 245 registros de
`collection/carga.py`).

**Status:** `[x] concluída`

---

### `T-93` — Testar a trilha de progresso (`AC-40`)

- **Tipo:** `Test`
- **Dependências:** `T-92`
- **Rastreia:** `RF-31`, `AC-40`, `EC-14`
- **Arquivos:** `tests/app_aluno/test_trilha_de_progresso.py`

**Descrição**

Casos em estados diferentes, consulta de trilha e verificação do que cada um
reporta.

**Critérios de aceite**

- [x] `AC-40`: cada caso reporta estado atual e data da última interação
- [x] `EC-14`: caso parado é marcado como parado, com data, e continua retomável
- [x] Nenhum valor monetário aparece na saída da consulta
- [x] O teste cita `AC-40` no nome

**Nota de implementação.** Os quatro critérios já estavam integralmente
cobertos por duas suítes irmãs que nasceram junto com a implementação que
consomem: `tests/app_aluno/test_consulta_trilha_de_progresso.py` (T-92) prova
`AC-40` com quatro casos em quatro estados do plano §4.3 e a ausência de dado
financeiro (auditoria de `__slots__` + valor de resposta nunca exposto); e
`tests/app_aluno/test_transicionar_e_registrar.py` (T-91) prova `EC-14` com
`test_ec14_caso_parado_ha_meses_continua_retomavel_com_todas_as_respostas`
(hiato de 180 dias, respostas intactas, trilha observável, retomada aceita).
`tests/app_aluno/test_trilha_de_progresso.py`, o arquivo nomeado por esta
tarefa, nasce mínimo — mesmo precedente de `tests/app_aluno/integracao/
test_revisao_imutavel.py` (T-73) — com um teste próprio que cita `AC-40` no
nome (rastreabilidade exigida independentemente da cobertura predominante já
existir) e um teste de sanidade que confirma que as duas suítes irmãs
continuam existindo, para que apagar qualquer uma delas por engano quebre
este teste também.

**Status:** `[x] concluída`

---

### `T-94` — Implementar o keep-alive do banco durante a janela do piloto

- **Tipo:** `Infra`
- **Dependências:** `T-25`
- **Rastreia:** `RF-10`, `EC-05`
- **Arquivos:** `app/http/saude.py`, `docs/operacao-piloto.md`

**Descrição**

O free tier pausa após ~7 dias sem atividade, e com 1 a 3 alunos em série a
pausa é o modo de falha **esperado**. Keep-alive agendado mais a mensagem
honesta de `EC-05` ("o sistema está reconectando, sua última resposta foi
salva").

**Critérios de aceite**

- [x] Existe um endpoint/rotina de keep-alive que toca o banco periodicamente durante a janela do piloto
- [x] Na indisponibilidade, o aluno vê a mensagem de reconexão e pode repetir, sem resposta falsamente confirmada
- [x] O procedimento operacional está documentado, incluindo a recomendação de reavaliar o tier antes de abrir o piloto
- [x] O keep-alive não grava nada em tabela de dado do aluno

**Status:** `[x] concluída`

---

### `T-95` — Testar o ciclo completo `US-01` + `US-04` ponta a ponta

- **Tipo:** `Test`
- **Dependências:** `T-65`, `T-73`, `T-46`
- **Rastreia:** `RF-01`, `RF-02`, `RF-09`, `RF-10`, `RF-16`, `RF-20`, `RF-21`, `RF-23`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-25`
- **Arquivos:** `tests/app_aluno/e2e/test_ciclo_completo.py`

**Descrição**

Cadastro → consentimento → coleta multissessão → Bloco 6 → fila → liberação →
tela do plano. O mínimo que prova o ciclo, não uma suíte de UI.

**Critérios de aceite**

- [x] O ciclo completo executa sem intervenção manual, com o adaptador de arquivo
- [x] `AC-14`, `AC-15`, `AC-16` e `AC-17` são verificados no HTML renderizado, caractere por caractere
- [x] `AC-25`: antes da liberação, a rota do plano do aluno não devolve plano
- [x] O teste roda sob o marcador `e2e`

**Status:** `[x] concluída`

---

### `T-96` — Testar `US-07` ponta a ponta: recálculo passa pela fila

- **Tipo:** `Test`
- **Dependências:** `T-95`, `T-88`
- **Rastreia:** `RF-23`, `RF-26`, `AC-26`, `AC-29`
- **Arquivos:** `tests/app_aluno/e2e/test_revisao_de_recalculo.py`

**Descrição**

Quitação confirmada → recálculo → fila → tela lado a lado → liberação. A
política não distingue primeiro envio de recálculo.

**Critérios de aceite**

- [x] `AC-26`: o snapshot de recálculo aparece na fila antes de qualquer acesso do aluno
- [x] `AC-29`: plano e `estado_inputs` na mesma sessão do revisor
- [x] Após a liberação, o aluno vê o plano novo e o anterior permanece recuperável
- [x] O teste roda sob o marcador `e2e`

**Status:** `[x] concluída`

---

### `T-97` — Verificar acessibilidade automatizada da apresentação do plano

- **Tipo:** `Test`
- **Dependências:** `T-95`, `T-48`
- **Rastreia:** `RF-21`, `RF-22`
- **Arquivos:** `tests/app_aluno/e2e/test_acessibilidade_plano.py`, `docs/checklist-acessibilidade.md`

**Descrição**

`axe` sobre a tela do plano e a tela da fila, e complemento do checklist manual
de leitor de tela.

**Critérios de aceite**

- [x] `axe` não reporta violação de contraste, rótulo ou ordem de foco na tela do plano e na da fila — **limitação declarada honestamente, mesma decisão de fronteira de `T-48`**: este ambiente não tem Chromium/Playwright/Selenium disponível (reconfirmado: `node -e "require.resolve('axe-core')"` falha, nenhum pacote de browser em `npm ls -g`, nenhum dos dois está no plano desta feature); `axe-core` real não pode rodar aqui. `tests/app_aluno/e2e/test_acessibilidade_plano.py` implementa um **substituto estático parcial** sobre HTML REAL (gerado por um `SnapshotOrdem` de verdade via `engine.motor.calcular_plano`, nunca fabricado à mão, e por `app.revisao.fila.listar_fila_de_revisao` sobre o mesmo snapshot): contraste — nenhuma das duas telas carrega `estilo.css` nem declara cor própria (`style=`/`<style>`), confirmado por varredura, logo não há regra de cor a reprovar; rótulo — as duas telas não têm nenhum campo de formulário (`<input>`/`<select>`/`<textarea>`), confirmado por varredura, logo não há rótulo faltante possível; ordem de foco — ausência de `tabindex` fora de `0`, mesma checagem de T-48. Adicionalmente auditado: cabeçalho de `<table>` de `fila.html` com `<th scope="col">` e hierarquia de `<h1>`/`<h2>` do plano sem pular nível (equivalentes a `scope-attr-valid`/`heading-order` de `axe-core`)
- [x] A leitura do plano funciona a 360 px, sem rolagem horizontal — mesma técnica estática de `test_css_360px.py` (T-47), aplicada aos templates de `report/templates/plano/` e `report/templates/revisao/`: nenhum `width` fixo acima de 360px em nenhum template, e a única `<table>` fora da coleta (`fila.html`) não declara `width`/`colgroup` fixos. Prova visual real em navegador físico permanece item de checklist manual (seção 3, já registrava isso; agora também cita `fila.html` explicitamente)
- [x] O checklist manual cobre a navegação por teclado da tela do plano — `docs/checklist-acessibilidade.md`, nova seção "1.1 Navegação por teclado — tela do plano e tela da fila (`T-97`)": ordem de tabulação de título/corpo/posições/pendências/rodapé, link de PDF quando existir, navegação por tabela da fila com leitura de `<th scope="col">`, ausência de armadilha de foco
- [x] O teste roda sob o marcador `e2e` — `pytestmark = pytest.mark.e2e`, mesmo padrão de `test_acessibilidade_coleta.py`; `pytest -m "not requer_banco and not e2e"` deseleciona os 9 testes (verificado); `pytest -m e2e tests/app_aluno/e2e/test_acessibilidade_plano.py` roda e passa os 9; `pytest -q` (comando `test` do config) roda e passa os 9 dentro do total (1100 passed, 75 skipped, 5 xfailed)

**Status:** `[x] concluída`

---

### `T-99` — Transcrever `B9.02` e `B9.04` (Bloco 9) e ligar `NECESSIDADE_VITORIA`/`HISTORICO_ABANDONO`

- **Tipo:** `Data`
- **Dependências:** `T-16`, `T-50`
- **Rastreia:** `RF-14`, `AC-13`
- **Arquivos:** `collection/registros/bloco-09.yaml`, `app/montagem/estado.py`

**Descrição**

Lacuna descoberta durante `T-50`: o Bloco 9 da canônica nunca foi transcrito
por `T-17`/`T-18`/`T-19` — nenhuma tarefa do backlog original previa isso.
`SinaisComportamentais.NECESSIDADE_VITORIA` (`B9.02`, escala 0-10) e
`HISTORICO_ABANDONO` (`B9.04`, seleção única) ficaram fixados em valor neutro
(`DESCONHECIDO`/`TALVEZ`) por `T-50`, documentado, nunca inventado.
Escopo restrito a essas duas perguntas — mesmo critério de recorte que `T-19`
já aplicou ao Bloco 12: só o que alimenta o contrato do motor entra; as
demais quatro perguntas do Bloco 9 (`B9.01` `TOLERANCIA_ESPERA`, `B9.03`
`DISCIPLINA_EXECUCAO`, `B9.04A` `MOTIVO_ABANDONO`, `B9.05`
`PREFERENCIA_METODO`) não têm campo correspondente em `EstadoFinanceiro`/
`Divida`/`PerfilComportamental`/`SinaisComportamentais` hoje e ficam fora
desta tarefa — não inventar onde elas entram.

**Critérios de aceite**

- [x] `B9.02` transcrita caractere por caractere: `OBR`, `ESCALA_0_10`, `VARIAVEL_GRAVADA: NECESSIDADE_VITORIA`, condição de exibição `Sempre`
- [x] `B9.04` transcrita caractere por caractere: `OBR`, `SELECAO_UNICA`, `VARIAVEL_GRAVADA: HISTORICO_ABANDONO`, domínio `MAIS_DE_UMA · UMA · NAO · SEM_PLANO · NAO_SEI`
- [x] `collection/registros/bloco-09.yaml` carrega sem erro por `collection/carga.py`, com o mesmo `QUESTIONARIO_VERSION` dos demais arquivos
- [x] `app/montagem/estado.py::montar_sinais_comportamentais` lê `NECESSIDADE_VITORIA` e `HISTORICO_ABANDONO` do registro real (mesmo mecanismo de `_membro_do_enum`/`_ou_desconhecido` já usado pelos demais campos), substituindo os dois valores fixos por leitura de fato
- [x] Testes de `T-50` (`tests/app_aluno/test_montagem_perfil_comportamental.py`) e de `T-20`/gerador continuam passando; o teste que hoje afirma "campo fixado" é atualizado para afirmar "lido do registro"

**Status:** `[x] concluída`

---

### `T-101` — Converter os nove `TipoResposta` corretamente na rota de coleta

- **Tipo:** `Infra`
- **Dependências:** `T-42`
- **Rastreia:** `RF-11`, `RF-13`, `AC-08`, `AC-13`
- **Arquivos:** `app/http/rotas_coleta.py`

**Descrição**

Lacuna descoberta durante `T-95`: `app/http/rotas_coleta.py::_resolver_valor`
só converte corretamente `MOEDA`/`TAXA` (via `app/montagem/conversao.py`) e
`NAO_SEI`. Os outros seis membros de `TipoResposta`
(`SELECAO_UNICA`, `SELECAO_MULTIPLA`, `NUMERO`, `DATA`, `TEXTO_CURTO`,
`SIM_NAO_TALVEZ`, `ESCALA_0_10`) caem no `return valor_bruto` — a string
crua do formulário HTML. Isso quebra a montagem real do estado: funções
como `app/montagem/estado.py::_mecanismo_deficit` exigem `frozenset[str]`
para `SELECAO_MULTIPLA` (checklist) e outras exigem `int` para
`ESCALA_0_10` — uma string nunca satisfaz `isinstance(traduzido, frozenset)`
nem os `int(...)` já escritos em `app/montagem/estado.py`, então a resposta
gravada por essas perguntas é estruturalmente inutilizável pela montagem,
mesmo chegando ao banco sem erro aparente na hora de gravar.

**Critérios de aceite**

- [x] `SELECAO_MULTIPLA` grava `frozenset[str]` a partir dos valores marcados no formulário (checklist), nunca uma string concatenada
- [x] `ESCALA_0_10` e `NUMERO` gravam `int`, recusando com `EC-01` (mesmo caminho de erro de `MOEDA`/`TAXA`) uma entrada não numérica — nunca truncando nem coagindo
- [x] `DATA` grava `date`, recusando entrada que não seja data válida
- [x] `SELECAO_UNICA`/`SIM_NAO_TALVEZ`/`TEXTO_CURTO` continuam gravando `str` (já corretos hoje — nenhuma mudança de comportamento para esses três)
- [x] Teste de regressão usando `app/montagem/estado.py::_mecanismo_deficit` (ou equivalente) sobre uma resposta gravada pela rota real confirma que a montagem aceita o valor sem erro de tipo
- [x] `T-95` (`tests/app_aluno/e2e/test_ciclo_completo.py`) é atualizado para gravar as 4 variáveis afetadas (`MECANISMO_DEFICIT`, `AUTOPERCEPCAO_CONTROLE`, `PESO_EMOCIONAL`, `NECESSIDADE_VITORIA`) pela rota HTTP real, removendo o contorno documentado por chamada direta ao repositório

**Status:** `[x] concluída`

---

### `T-98` — Fechar o portão de qualidade e atualizar os artefatos SDD

- **Tipo:** `Docs`
- **Dependências:** `T-96`, `T-97`, `T-93`, `T-94`, `T-90`
- **Rastreia:** `RF-34`, `AC-37`, `AC-41`, `AC-42`, `AC-44`
- **Arquivos:** `sdd.config.md`, `plans/app-aluno.plan.md`, `specs/app-aluno.spec.md`, `tasks/app-aluno.tasks.md`

**Descrição**

Rodar os quatro comandos da §2 do config sobre o código completo, confirmar os
seis testes estáticos e registrar nos artefatos SDD o que mudou durante a
execução (Definition of Done, §8 do config).

**Critérios de aceite**

- [x] `install`, `lint`, `build` e `test` da §2 do config passam sobre `engine persistencia collection app report tests` — `install`: `uv pip install -e ".[dev]"` resolve 21 pacotes, instala `piq-motor-calculo==0.1.0`; `lint`: `ruff check .` → `All checks passed!`; `build`: `mypy engine persistencia collection app report tests` → `Success: no issues found in 251 source files`; `test`: `pytest -q` → `1100 passed, 75 skipped, 5 xfailed, 1 warning` em 70s, código de saída `0` (skips são `requer_banco` sem `DATABASE_URL` e PDF real sem GTK/Pango nativo neste Windows; os 5 `xfailed` são `AC-45`..`AC-49` de `T-90`, esperado até o slug `motor-calculo` entregar as três mudanças)
- [x] Os seis testes estáticos passam: `AC-41` (`test_fronteira_import_engine.py`, 10 testes), `AC-37` (`test_sem_conteudo_de_questionario_no_codigo.py`, 6 testes), `AC-42` (`test_sem_aritmetica_sobre_snapshot.py`, 8 testes), `AC-44` (`test_engine_congelado.py`, 4 testes), fronteira `Decimal`/`RF-13` (`test_fronteira_decimal_unica.py`, 9 testes) — 40/40 passaram (`pytest tests/app_aluno/estatica/test_fronteira_import_engine.py tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py tests/app_aluno/estatica/test_sem_aritmetica_sobre_snapshot.py tests/app_aluno/estatica/test_engine_congelado.py tests/app_aluno/estatica/test_fronteira_decimal_unica.py`); `AC-38` (sem ID reaproveitado entre versões) vive em `tests/app_aluno/test_gerador.py` (não em `estatica/`, por tratar de dado de carga, não de AST estrutural) — 3/3 passaram (`test_ac38_id_reaproveitado_entre_arquivos_da_mesma_versao_e_recusado`, `test_ac38_versoes_de_questionario_divergentes_no_mesmo_diretorio_ja_sao_recusadas_antes`, `test_ac38_ids_reais_carregados_nao_tem_nenhum_reaproveitamento`)
- [x] Spec, plano e backlog estão coerentes com o que foi construído; divergências viraram nova tarefa, nunca ajuste silencioso — três divergências reais entre `plans/app-aluno.plan.md` e o código construído foram identificadas e registradas em adendo (§12 do plano, não reescrita da decisão original): `app/eventos/eventos.py`/`RepositorioEventosCaso`/`transicionar_e_registrar` (T-91, mecanismo de trilha não nomeado no plano original), a guarda de papel de revisor `e_revisor`/`exigir_papel_revisor` (T-100, decisão do usuário que estende o modelo de autorização não previsto em nenhuma seção do plano), e a correção de conversão dos nove `TipoResposta` em `rotas_coleta.py` (T-101, lacuna de implementação, não de especificação). Nenhuma reabre spec: são extensões aditivas dentro da fronteira já declarada (Lei nº 3, `AC-41`/`AC-44` intactos). Backlog: tabela de Cobertura de requisitos (linha `RF-14`, `RF-27` e as tabelas de `AC-NN`) atualizada para incluir `T-99`/`T-100`/`T-101`, ausentes da tabela original (escritas antes de essas tarefas existirem)
- [x] As Open Questions ainda abertas e as dependências externas do slug `motor-calculo` estão registradas com seu estado atual — a lista de 5 OQ do enunciado original desta tarefa (`OQ-07`, `OQ-11`, `OQ-12`, `OQ-13`, `OQ-15`) estava desatualizada: escrita antes de `OQ-16`, `OQ-17` e `OQ-18` existirem. Confirmado por releitura de `specs/app-aluno.spec.md` §10 INTEIRA (`OQ-01` a `OQ-18`): **11 abertas** — `OQ-06` (tamanho do piloto), `OQ-07` (painel do operador), `OQ-08` (aviso "na hora", decisão técnica provisória incorporada ao plano mas não fechada pelo especialista), `OQ-09` (tela+PDF, mesma natureza de `OQ-08`), `OQ-11` (identidade de `CASO_ID` vs. raiz da cadeia de snapshot), `OQ-12` (texto normativo da §25 ausente da canônica), `OQ-13` (identificador exato de `TIPO_ACAO`), `OQ-15` (identidade da ação de economia sem dívida), `OQ-16` (fórmula de composição de renda/despesa do Bloco 3, descoberta em `T-51`), `OQ-17` (`ATAQUE_IMEDIATO_RECOMENDADO` ausente do contrato do motor, descoberta em `T-77`), `OQ-18` (campo de "qual pergunta reabrir" no Gate 1, descoberta em `T-85`); **7 respondidas** — `OQ-01`, `OQ-02`, `OQ-03`, `OQ-04`, `OQ-05`, `OQ-10`, `OQ-14`. Dependências externas do `motor-calculo`: as três mudanças em `engine/gates.py::AcaoRequerida` (`ACAO_ID`/`TIPO_ACAO`, Gate 1 emitir ação de informação, ação de economia fora do fluxo de gates) seguem pendentes e bloqueiam `T-77`/`T-78`/`T-79` (via `OQ-17`) e os 5 `xfailed` de `T-90` (via as três mudanças em si)

**Status:** `[x] concluída`

---

### `T-102` — Implementar o painel do operador (`RF-35`)

- **Tipo:** `UI`
- **Dependências:** `T-92`, `T-100`
- **Rastreia:** `RF-35`, `OQ-07` (respondida)
- **Arquivos:** `app/http/rotas_operador.py` (novo), `report/templates/operador/painel.html` (novo)

**Descrição**

Tarefa nova, aberta depois do fechamento das 18 Open Questions da spec:
`OQ-07` foi respondida com "sim, painel dedicado, mesmo no piloto de 1–3
alunos" — decisão do usuário que reverteu o que a spec §9 originalmente
listava como Out of Scope (`RF-35` é o requisito novo que registra isso).
Lista todos os casos do piloto com bloco atual, o que aguarda revisão e
tempo desde a última atividade, lendo exclusivamente
`app/casos/progresso.py::consultar_trilha_de_progresso` (`T-92`, já
implementada e testada — nenhuma lógica de trilha nova nesta tarefa, só
apresentação em tela própria do que `RelatoDeProgresso` já expõe). Protegida
pela mesma guarda de papel de `T-100` (`Depends(exigir_papel_revisor)`), não
por `exigir_caso_da_sessao` (`T-31`) — o operador não é "dono" de um caso no
sentido de isolamento do aluno, é um papel que vê todos os casos, mesma
disciplina já usada por `/revisao/fila` (`T-69`) e `/revisao/caso/{...}`
(`T-70`).

**Critérios de aceite**

- [x] `GET /operador/painel` lista todos os casos com `estado`, se está `aguardando_revisao`, e há quanto tempo desde `ultima_interacao_em` — cada campo lido diretamente de `RelatoDeProgresso`, nenhum recalculado nesta tarefa
- [x] A rota recusa com `401`/`403` uma sessão sem `e_revisor = true`, antes de qualquer leitura de caso (mesmo mecanismo de `T-100`)
- [x] Nenhum dado financeiro do aluno (renda, dívida, valor de qualquer campo do snapshot) aparece na tela — só os quatro campos estruturais de `RelatoDeProgresso`
- [x] Um teste e2e cobre: conta de aluno comum recebe `403`; conta revisora vê os casos de todos os alunos do piloto, cada um com seu estado e tempo de inatividade corretos

**Status:** `[x] concluída`

**Nota de implementação.** `app/http/rotas_operador.py` (novo) reusa
inteiramente `app/casos/progresso.py::consultar_trilha_de_progresso` (T-92) e
`app/http/isolamento.py::exigir_papel_revisor` (T-100) — mesmo padrão de
`/revisao/fila` (T-69/T-100). Único trabalho novo desta tarefa:
`RepositorioCasos.listar_todos` (extensão pequena e necessária, mesmo
precedente de `listar_por_estado`/T-69, adicionada ao `Protocol` e às duas
implementações `RepositorioCasosSupabase`/`RepositorioCasosArquivo` em
`persistencia/app_aluno/casos.py`/`arquivo.py`) e a formatação de "tempo
desde a última atividade" (`_formatar_tempo_decorrido`, subtração de
`datetime` sobre um campo estrutural de `Caso` — nunca um campo de
`SnapshotOrdem`, portanto não é a regra de negócio que a Lei nº 3 proíbe
recalcular). Router registrado em `app/http/aplicacao.py`. Template novo:
`report/templates/operador/painel.html`. Teste e2e:
`tests/app_aluno/e2e/test_rotas_operador.py` (5 testes: 401 sem sessão, 403
para aluno comum, painel com dois casos de contas diferentes e tempos de
inatividade corretos, ausência de termo financeiro na tela, painel vazio).
Extensão de escopo estritamente necessária: os dublês de `RepositorioCasos`
que herdam a classe concreta como base (`tests/app_aluno/
test_rotas_consentimento.py`, `tests/app_aluno/e2e/
test_mecanismo_isolamento.py`, `tests/app_aluno/e2e/
test_isolamento_por_caso.py`) ganharam um `listar_todos` que levanta
`NotImplementedError` (mesmo padrão já usado para `listar_por_estado`
nesses três dublês desde T-69), exigido por `mypy --strict` após a extensão
do `Protocol`.

---

### `T-105` — Adicionar `RENDA_ADICIONAL_ID` e `DESPESA_NAO_MENSAL_ID` a `EscopoRepeticao` (`OQ-19`)

- **Tipo:** `Data`
- **Dependências:** `T-15`, `T-17`
- **Rastreia:** `RF-04`, `RF-14`, `OQ-19` (respondida)
- **Arquivos:** `collection/registro.py`, `collection/repeticao.py`, `collection/registros/bloco-03.yaml`, `persistencia/app_aluno/itens.py`

**Descrição**

Tarefa nova, aberta depois de `OQ-19` ter sido respondida. `T-17` transcreveu
`B3.03A-C` (renda adicional) e `B3.NM02A-D` (despesa não-mensal) com
`escopo_repeticao: NENHUM`, mas a canônica as chama de "ficha REP" — sem um
escopo real, `RespostasCaso.valores_do_escopo` não tem como enxergar mais de
um item dessas duas famílias, o que bloqueia `T-103`. `OQ-19` decidiu: dois
novos membros em `EscopoRepeticao`, seguindo exatamente o padrão já usado
pelos cinco membros existentes (`DIVIDA_ID`, `VINCULO_ID`, `MARGEM_ID`,
`ITEM_DESPESA`, `ACAO_ID`) — cada um com prefixo de identificador próprio em
`collection/repeticao.py::PREFIXO_POR_ESCOPO`, sem limite de quantidade
codificado (lista aberta, mesmo tratamento das cinco fichas já existentes).

**Critérios de aceite**

- [x] `EscopoRepeticao` ganha exatamente dois novos membros: `RENDA_ADICIONAL_ID` e `DESPESA_NAO_MENSAL_ID`
- [x] `PREFIXO_POR_ESCOPO` ganha um prefixo próprio para cada um dos dois novos escopos, distinto dos cinco já existentes
- [x] `B3.03A`, `B3.03B`, `B3.03C` em `collection/registros/bloco-03.yaml` declaram `escopo_repeticao: RENDA_ADICIONAL_ID` (eram `NENHUM`)
- [x] `B3.NM02A`, `B3.NM02B`, `B3.NM02C`, `B3.NM02D` em `collection/registros/bloco-03.yaml` declaram `escopo_repeticao: DESPESA_NAO_MENSAL_ID` (eram `NENHUM`)
- [x] `collection/carga.py` continua carregando o arquivo sem erro após a edição
- [x] `RespostasCaso.valores_do_escopo(EscopoRepeticao.RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL")` devolve corretamente 0, 1 e N itens cadastrados, mesmo comportamento já provado para `DIVIDA_ID`/`MARGEM_ID`
- [x] `persistencia/app_aluno/itens.py` (geração/persistência de identificador de item) cobre os dois novos escopos sem exigir mudança de schema além do que os cinco escopos existentes já usam
- [x] `T-20`/`tests/app_aluno/test_gerador.py` e a suíte de fichas repetíveis (`AC-04`) continuam passando com os dois novos escopos

**Status:** `[x] concluída`

**Nota de implementação.** `EscopoRepeticao` (`collection/registro.py`) ganhou
`RENDA_ADICIONAL_ID`/`DESPESA_NAO_MENSAL_ID`, exatamente o mesmo padrão dos
seis membros já existentes. `PREFIXO_POR_ESCOPO` (`collection/repeticao.py`)
ganhou os prefixos `REND`/`NM`, distintos de `D`/`V`/`M`/`DESP`/`A` — sem
mudança de mecanismo: `GeradorDeIdentificadorEmMemoria` e
`RepositorioItensSupabase` (`persistencia/app_aluno/itens.py`) já eram
genéricos sobre `EscopoRepeticao` via esse mesmo dicionário, então os dois
novos escopos funcionam sem tocar nenhum dos dois módulos além do comentário
que enumerava os cinco prefixos antigos. `collection/registros/bloco-03.yaml`
teve as sete perguntas (`B3.03A/B/C`, `B3.NM02A/B/C/D`) migradas de `NENHUM`
para o escopo real. **Achado durante a implementação, fora do escopo desta
tarefa mas necessário para o critério "`collection/carga.py` continua
carregando sem erro":** `collection/esquema-registros.json` (o JSON Schema
que `collection/carga.py::jsonschema.validate` aplica antes de converter o
YAML) tem `enum` fechado de `escopo_repeticao`/`escopo` em três lugares
(`registroPergunta.escopo_repeticao`, `condicao.EXISTE_ITEM.escopo`,
`validacaoCruzada.escopo`) — sem estendê-lo, a carga do YAML editado teria
falhado com `ValidationError` antes mesmo de `EscopoRepeticao(...)` ser
chamado. Os três `enum` foram estendidos com os dois novos valores; é a mesma
mudança mecânica de `OQ-19` (mesmo domínio fechado, replicado em três
lugares por design do schema), não uma segunda decisão de estrutura.
`RespostasCaso.valores_do_escopo` (`collection/respostas.py`) já não fazia
nenhuma distinção por escopo (o parâmetro é ignorado no filtro, documentado
no próprio docstring do método) — os dois novos escopos funcionam por ele
sem nenhuma linha nova nesse arquivo. Testes novos: `tests/app_aluno/
test_respostas.py` (0/1/N itens para os dois novos escopos, mesmo padrão dos
testes de `DIVIDA_ID`/`MARGEM_ID` já existentes), `tests/app_aluno/
test_repeticao.py` (prefixos `REND`/`NM` gerando identificadores distintos e
sem colisão), `tests/app_aluno/test_gerador.py` (as sete perguntas reais do
YAML aparecem nas fichas dos dois novos escopos, sobre a coleção carregada
de verdade — prova indireta de que `collection/carga.py` continua
carregando sem erro). `variavel` de `valores_do_escopo` é o
`VARIAVEL_GRAVADA` do registro (ex. `"RENDA_RECORRENTE_ADICIONAL"`,
`"VALOR_DESPESA_NAO_MENSAL"`), nunca o `RegistroPergunta.ID` — confirmado
contra `app/http/rotas_coleta.py` (`ID_PERGUNTA=registro.VARIAVEL_GRAVADA`,
T-42) e `app/montagem/estado.py` (comentário: "`Resposta.ID_PERGUNTA` grava
exatamente `RegistroPergunta.VARIAVEL_GRAVADA`"), consistente com o próprio
critério de aceite desta tarefa. Suíte completa (1109 testes, antes 1105) e
`mypy --strict`/`ruff` passam.

---

### `T-103` — Implementar a fórmula real de renda e despesa do Bloco 3 (`OQ-16`)

- **Tipo:** `Data`
- **Dependências:** `T-51`, `T-105`
- **Rastreia:** `RF-14`, `AC-18`, `OQ-16` (respondida)
- **Arquivos:** `app/montagem/estado.py`, `tests/app_aluno/test_montagem_estado_financeiro.py`

**Descrição**

Tarefa nova, aberta depois do fechamento das 18 Open Questions da spec:
`OQ-16` respondida com a fórmula normativa exata para os três campos que
`T-51` documentou como lacuna e recebia como parâmetro externo. Substitui o
parâmetro externo por cálculo real dentro de `montar_estado_financeiro`,
lendo exclusivamente respostas já coletadas — nenhuma aritmética nova sobre
campo de `SnapshotOrdem` (Lei nº 3 preservada; esta é agregação de **entrada**
para o motor, não leitura de **saída** dele).

Fórmulas fechadas por `OQ-16`:

- `RENDA_TOTAL_RECORRENTE` = `RENDA_PRINCIPAL` (B3.01) + soma de todas as
  fichas REP de `RENDA_RECORRENTE_ADICIONAL` (B3.03A-C, até 3 itens).
  `RECURSOS_EXTRAORDINARIOS` (B3.05) e a renda extra potencial (B3.06) **não**
  entram. Qualidade do dado (`CONFIRMADA`/`ESTIMADA`) é metadado, não filtro —
  os dois entram com o valor informado; `DESCONHECIDA` produz `DESCONHECIDO`
  no campo, nunca uma estimativa.
- `DESPESAS_OPERACIONAIS_ATUAIS` = soma de todos os valores das fichas REP de
  `B3.D01` a `B3.D11` (as 10 categorias fixas mais a não listada).
- `DESPESAS_NAO_MENSAIS_NORMALIZADAS` = (soma dos valores anuais de todas as
  fichas REP de `B3.NM02A-D`) / 12.

**Critérios de aceite**

- [x] `RENDA_TOTAL_RECORRENTE` é a soma exata de `RENDA_PRINCIPAL` + todas as fichas de `RENDA_RECORRENTE_ADICIONAL` presentes, para um caso com 0, 1 e 3 fontes adicionais
- [x] `RENDA_PRINCIPAL` com qualidade `ESTIMADA` entra na soma com o mesmo valor de uma `CONFIRMADA`; `DESCONHECIDA` produz `DESCONHECIDO` no campo, nunca um valor numérico inventado
- [x] `RECURSOS_EXTRAORDINARIOS` (B3.05) e a renda extra potencial (B3.06) nunca entram em `RENDA_TOTAL_RECORRENTE`, mesmo quando preenchidos
- [x] `DESPESAS_OPERACIONAIS_ATUAIS` é a soma exata das fichas REP de `B3.D01` a `B3.D11`, para um caso com categorias parcialmente preenchidas
- [x] `DESPESAS_NAO_MENSAIS_NORMALIZADAS` é a soma anual das fichas de `B3.NM02A-D` dividida por 12, com `Decimal` exato (nenhum arredondamento intermediário via `float`)
- [x] O parâmetro externo que `T-51` introduziu para esses três campos é removido de `montar_estado_financeiro`; a lacuna documentada na docstring do módulo é atualizada para refletir que passou a ser calculada, não recebida
- [x] Os testes de `T-51`/`T-53` que hoje passam esses três valores como parâmetro são atualizados para fornecer as respostas de origem e verificar o valor derivado

**Status:** `[x] concluída`

**Nota de implementação.** `app/montagem/estado.py::montar_estado_financeiro`
perdeu os três parâmetros externos (`RENDA_TOTAL_RECORRENTE`,
`DESPESAS_OPERACIONAIS_ATUAIS`, `DESPESAS_NAO_MENSAIS_NORMALIZADAS`) e
ganhou três funções privadas que implementam as fórmulas fechadas de
`OQ-16`: `_renda_total_recorrente` (`_renda_principal` + `_renda_
recorrente_adicional_total`, esta última somando `valores_do_escopo(
RENDA_ADICIONAL_ID, "RENDA_RECORRENTE_ADICIONAL")`, escopo que `T-105`
acabou de destravar), `_despesas_operacionais_atuais` (soma de `valores_do_
escopo(ITEM_DESPESA, "VALOR_DESPESA")` — as 11 categorias de `B3.D01-D11`
compartilham um único escopo de ficha, então a soma não precisa discriminar
categoria) e `_despesas_nao_mensais_normalizadas` (soma de `valores_do_
escopo(DESPESA_NAO_MENSAL_ID, "VALOR_DESPESA_NAO_MENSAL")` dividida por 12).
`CONFIABILIDADE_DADOS` continua parâmetro externo (fora do escopo de
`OQ-16`, ver `OQ-17`/nota de `app/http/rotas_calculo.py`).

`RENDA_PRINCIPAL`/`RENDA_TOTAL_RECORRENTE` é `Dinheiro` puro em
`engine/estado.py` (sem união com `Desconhecido`) — mesma restrição de
tipo que já obrigava `_economia_potencial_imediata` (T-51) a nunca
devolver `DinheiroTalvez`. Por isso a leitura de "`DESCONHECIDA` produz
`DESCONHECIDO` no campo" (`OQ-16`) foi implementada como
`ErroCampoAgregadoDesconhecido` — erro explícito nomeado, nunca um `0`
inventado — quando `RENDA_PRINCIPAL` é `NAO_SEI`/ausente, seguindo
exatamente o mesmo padrão de decisão mecânica que `_economia_potencial_
imediata` já usa para o mesmo tipo de contradição de contrato. "Qualidade
do dado é metadado, não filtro" foi confirmado contra o registro real: o
Bloco 3 não tem nenhum campo de qualidade para renda (só para despesa,
`QUALIDADE_VALOR_DESPESA`/B3.DF04) — qualquer valor `Decimal` concreto
informado em `RENDA_PRINCIPAL`/`RENDA_RECORRENTE_ADICIONAL` entra com o
mesmo peso, sem distinção de "confirmado"/"estimado" no código (não há o
que distinguir).

Nenhum `Decimal(...)` novo foi construído em `app/montagem/estado.py`: as
três funções usam `_ZERO`/`_DOZE`, duas constantes de módulo obtidas de
`app.montagem.conversao.converter_para_dinheiro("0")`/`("12")` — a MESMA
fronteira única já usada pelo resto do arquivo, nunca uma segunda
fronteira (`tests/app_aluno/estatica/test_fronteira_decimal_unica.py`
continua passando sem precisar de nenhuma allowlist nova, porque
`app/montagem/estado.py` nunca chama `Decimal(...)`/`dinheiro(...)`
diretamente).

Testes atualizados/novos: `tests/app_aluno/test_montagem_estado_
financeiro.py` — `_respostas_minimas_completas`/`_montar` não passam mais
os três parâmetros; `TestFronteiraDeParametrosExternosDocumentada` provê
`test_montar_estado_financeiro_nao_aceita_mais_os_tres_parametros_
removidos` (prova negativa de `TypeError`); nova classe
`TestT103CamposAgregadosDoBloco3` cobre os cinco critérios numéricos (0/1/3
fontes, ESTIMADA≡CONFIRMADA, DESCONHECIDA→erro, RECURSOS_EXTRAORDINARIOS/
B3.06 nunca somam, despesas parcialmente preenchidas, normalização
anual/12 com Decimal exato). `tests/app_aluno/fixtures/caso_completo.py`
(T-53) perdeu os três campos de `PARAMETROS_EXTERNOS_PADRAO` e ganhou
`RENDA_PRINCIPAL=8.000,00`, uma ficha de `ITEM_DESPESA` de `6.500,00` e uma
ficha de `DESPESA_NAO_MENSAL_ID` de `6.000,00`/ano — reproduzindo
exatamente os mesmos três totais que a fixture sempre teve, agora
calculados; `_resposta_item` foi generalizada (`DIVIDA_ID` → `item_id`)
para servir aos três novos escopos sem duplicar código. Nenhum dos 27
consumidores de `tests/app_aluno/fixtures/caso_completo.py::
PARAMETROS_EXTERNOS_PADRAO`/`ParametrosExternosDoBloco6` precisou de
edição própria: todos usam `**caso.parametros_externos`/`dict(
PARAMETROS_EXTERNOS_PADRAO)`, que agora só carregam `CONFIABILIDADE_DADOS`
e `economia_nao_identificada` — a mudança de contrato de
`montar_estado_financeiro` se propagou automaticamente pela fixture
central, sem tocar `app/http/rotas_calculo.py` (fora da lista de arquivos
desta tarefa). Suíte completa (1124 testes, antes 1109) e `mypy
--strict`/`ruff` passam.

**Divergências/achados fora de escopo, reportados e não decididos:**

1. **`FREQUENCIA_DESPESA_NAO_MENSAL` (`B3.NM02C`) e `DESPESA_NAO_MENSAL_
   JA_CONTABILIZADA` (`B3.NM02D`) não entram na fórmula implementada.**
   `OQ-16` fechou literalmente "soma dos valores anuais / 12", sem
   mencionar periodicidade nem exclusão de duplicidade — mas o próprio
   `salto_consequencia` de `B3.NM02D` no registro real diz "Sim → não
   normalizar novamente (impedir dupla contagem)". Implementei a fórmula
   fechada ao pé da letra (única leitura que não inventa critério além do
   que `OQ-16` decidiu), documentando a divergência no docstring de
   `_despesas_nao_mensais_normalizadas`. Se a intenção normativa real
   exigir tratar periodicidade/duplicidade, isso é nova Open Question, não
   decisão desta tarefa.
2. **`TIPO_RENDA=VARIAVEL` (piso vs. média histórica, `B3.02A`/`B3.02B`)
   continua fora de `_renda_principal`**, exatamente como já estava
   documentado como lacuna em `T-51` — `OQ-16` não resolveu esse caso
   (fala só de `RENDA_PRINCIPAL` "com o valor informado" ou
   "`DESCONHECIDA`"); se a renda principal for variável, `RENDA_PRINCIPAL`
   (B3.01) provavelmente fica sem valor concreto e a função levanta
   `ErroCampoAgregadoDesconhecido` — comportamento não coberto por teste
   específico nesta tarefa por não ter fórmula fechada a implementar.
3. **`app/http/rotas_calculo.py` cita "os quatro parâmetros externos" em
   sua docstring** (`ParametrosExternosDoBloco6`, `_ErroParametrosExternos
   Pendentes`) — a contagem ficou desatualizada depois de `T-103` (agora
   são três: só `CONFIABILIDADE_DADOS` mais o `economia_nao_identificada`
   opcional). O comportamento em si continua correto (a rota ainda bloqueia
   o Bloco 6 sem `CONFIABILIDADE_DADOS`), e o arquivo não está na lista de
   arquivos desta tarefa — não foi editado; sinalizado aqui para uma
   tarefa de higiene textual futura.

**Nota pós-fechamento — item 3 acima é mais grave do que "higiene
textual".** Verificação direta confirmou: `ParametrosExternosDoBloco6.
obter` (`_ParametrosExternosPendentes`, implementação padrão de produção)
levanta `_ErroParametrosExternosPendentes` INCONDICIONALMENTE, sem checar
se os campos que ainda faltam (`CONFIABILIDADE_DADOS`) estão de fato
indisponíveis — a rota `POST /caso/{CASO_ID}/calculo` bloqueia o Bloco 6
inteiro em produção com HTTP 503, citando "`OQ-16` em aberto" numa
mensagem técnica, mesmo agora que `OQ-16` está `respondida` e `T-103`
já implementou as três fórmulas. Isto é um bug real introduzido como
efeito colateral de escopo (o arquivo não estava na lista de `T-103`),
não apenas texto desatualizado. Corrigido por `T-106`, abaixo.

---

### `T-106` — Corrigir `rotas_calculo.py`: só `CONFIABILIDADE_DADOS` continua externo

- **Tipo:** `Infra`
- **Dependências:** `T-103`
- **Rastreia:** `RF-16`, `AC-12`, `OQ-16` (respondida)
- **Arquivos:** `app/http/rotas_calculo.py`

**Descrição**

Tarefa nova, aberta depois do fechamento de `OQ-16`/`T-103`: `T-103` removeu
`RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS` e `DESPESAS_NAO_
MENSAIS_NORMALIZADAS` da lista de parâmetros externos de `montar_estado_
financeiro` — só `CONFIABILIDADE_DADOS` (bloqueada por `RF-16`/fronteira de
import de `engine/comportamento.py`, sem relação com `OQ-16`) continua sendo
lacuna real. `app/http/rotas_calculo.py::ParametrosExternosDoBloco6` e
`_ErroParametrosExternosPendentes` ainda tratam os quatro como um bloco
único e bloqueiam o Bloco 6 inteiro, sempre, citando `OQ-16` como motivo —
mesmo já resolvida. Corrigir: `ParametrosExternosDoBloco6.obter` passa a
resolver e devolver `**{"CONFIABILIDADE_DADOS": ...}` (com
`economia_nao_identificada` opcional, se aplicável), e o bloqueio/erro
nomeado passa a citar exclusivamente a lacuna real de `CONFIABILIDADE_DADOS`
(não mais `OQ-16`). Nenhuma mudança em `app/montagem/estado.py`.

**Critérios de aceite**

- [x] `ParametrosExternosDoBloco6.obter` não referencia mais `RENDA_TOTAL_RECORRENTE`, `DESPESAS_OPERACIONAIS_ATUAIS` nem `DESPESAS_NAO_MENSAIS_NORMALIZADAS` — nem na assinatura, nem em docstring, nem no dict devolvido
- [x] O bloqueio de produção (`_ErroParametrosExternosPendentes`/HTTP 503) permanece SÓ enquanto `CONFIABILIDADE_DADOS` não tiver fonte real — a mensagem técnica não cita mais `OQ-16`
- [x] `montar_estado_financeiro` é chamado com exatamente os parâmetros que sua assinatura atual aceita — o `# type: ignore[arg-type]` permanece, mas confirmado ainda necessário (não relacionado à contagem de parâmetros: `**dict[str, object]` nunca é verificável contra kwargs nomeados/tipados, independente de quantos existam)
- [x] Toda a suíte de `rotas_calculo.py` (`T-56` e derivadas) e a suíte completa do projeto continuam passando
- [x] A docstring do módulo (topo do arquivo) é atualizada para não citar mais "os quatro parâmetros externos"

**Status:** `[x] concluída`

**Nota de implementação.** `ParametrosExternosDoBloco6`, `_ParametrosExternosPendentes`
e `_ErroParametrosExternosPendentes` (`app/http/rotas_calculo.py`) foram
atualizadas para citar exclusivamente `CONFIABILIDADE_DADOS` (obrigatório) e
`economia_nao_identificada` (opcional) — os únicos parâmetros que
`montar_estado_financeiro` ainda aceita como externos depois de `T-103`.
Nenhuma menção a `OQ-16`/"quatro parâmetros" permanece no módulo. Verificado:
`ruff check .` → `All checks passed!`; `mypy --strict` (6 pastas) →
`Success: no issues found in 253 source files`; `pytest -q` completo → `1128
passed, 75 skipped, 5 xfailed`, código de saída `0`. Um dos dois agentes que
implementou esta tarefa foi interrompido por falha de rede da API antes de
reportar formalmente — a implementação em si já estava completa e correta no
arquivo; esta nota e a marcação de status foram concluídas diretamente após
verificação independente do código e reexecução da suíte completa.

---

### `T-107` — Excluir despesa não-mensal já contabilizada da normalização (dupla contagem)

- **Tipo:** `Data`
- **Dependências:** `T-103`
- **Rastreia:** `RF-14`, `AC-18`, `OQ-16` (respondida — correção de fórmula)
- **Arquivos:** `app/montagem/estado.py`, `tests/app_aluno/test_montagem_estado_financeiro.py`

**Descrição**

Tarefa nova, aberta depois de uma divergência reportada por `T-103`:
`_despesas_nao_mensais_normalizadas` soma cegamente todas as fichas REP de
`B3.NM02A-D`, ignorando `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` (`B3.NM02D`)
— campo cujo próprio `salto_consequencia` no registro diz "Sim → não
normalizar novamente (impedir dupla contagem)". Decisão do usuário: fichas
onde `DESPESA_NAO_MENSAL_JA_CONTABILIZADA = Sim` (valor interno mapeado no
registro) são **excluídas** da soma anual antes da divisão por 12 —
`TALVEZ`/`NAO_SEI` continua entrando normalmente (só exclusão explícita por
`Sim`, nunca por incerteza).

**Critérios de aceite**

- [x] Uma ficha de `B3.NM02A-D` com `DESPESA_NAO_MENSAL_JA_CONTABILIZADA = Sim` não contribui ao total anual somado
- [x] Uma ficha com `DESPESA_NAO_MENSAL_JA_CONTABILIZADA = Não` ou `Não sei` contribui normalmente, como já acontecia
- [x] Um caso com 3 fichas, uma delas `Sim`, produz `DESPESAS_NAO_MENSAIS_NORMALIZADAS` igual à soma das outras duas dividida por 12 — teste numérico exato
- [x] O valor de `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` é lido por item explícito (`respostas.valor_no_item(item_id, "DESPESA_NAO_MENSAL_JA_CONTABILIZADA")`), correlacionado ao mesmo `item_id` do valor monetário — nunca por índice posicional entre listas separadas (evita exatamente o risco que `valores_do_escopo` sozinho não resolveria)
- [x] A docstring de `_despesas_nao_mensais_normalizadas` é atualizada para remover a divergência documentada por `T-103` (que fica resolvida)

**Status:** `[x] concluída`

**Nota de implementação.** `_despesas_nao_mensais_normalizadas`
(`app/montagem/estado.py`) passou a iterar por `item_id` do escopo
`DESPESA_NAO_MENSAL_ID`, lendo `VALOR_DESPESA_NAO_MENSAL` e
`DESPESA_NAO_MENSAL_JA_CONTABILIZADA` do MESMO item via `respostas.
valor_no_item` — nunca por posição entre duas listas de `valores_do_escopo`
obtidas separadamente (que não garantem ordem estável entre si). Fichas com
`DESPESA_NAO_MENSAL_JA_CONTABILIZADA = "SIM"` (valor interno exato do
registro) são excluídas da soma anual antes da divisão por 12; `"NAO"` e
`NAO_SEI` continuam contribuindo normalmente. Quatro testes novos em
`tests/app_aluno/test_montagem_estado_financeiro.py`, incluindo um teste
específico de independência de ordem (grava `JA_CONTABILIZADA` da segunda
ficha antes da primeira) para provar que a correlação é por item, não por
posição. Verificado: `ruff check .` → `All checks passed!`; `mypy --strict`
(6 pastas) → `Success: no issues found in 253 source files`; `pytest -q`
completo → `1128 passed, 75 skipped, 5 xfailed`, código de saída `0`. Um dos
dois agentes que implementou esta tarefa foi interrompido por falha de rede
da API antes de reportar formalmente (reportou "42 testes passam, incluindo
os 4 novos de T-107" antes de cair) — a implementação em si já estava
completa e correta no arquivo; esta nota e a marcação de status foram
concluídas diretamente após verificação independente do código e
reexecução da suíte completa.

---

### `T-104` — Atualizar `bloco-11.yaml` para os identificadores fechados de `TIPO_ACAO` (`OQ-13`)

- **Tipo:** `Data`
- **Dependências:** `T-84`
- **Rastreia:** `RF-33`, `OQ-13` (respondida)
- **Arquivos:** `collection/registros/bloco-11.yaml`, `tests/app_aluno/test_acoes.py` (denylist do teste estático atualizada)

**Descrição**

Tarefa nova, aberta depois do fechamento das 18 Open Questions da spec.
`OQ-13` foi respondida com o domínio fechado `INFORMACAO`, `RENEGOCIACAO`,
`TROCA`, `ECONOMIA` (ASCII, sem parênteses) — `T-84` já previa que "responder
`OQ-13` é edição de registro", sem exigir mudança de código. Esta tarefa é
exatamente essa edição: trocar os quatro literais de `condicao_exibicao` de
`B11.03-INF`/`-REN`/`-TRO`/`-ECO`, hoje escritos com o texto pré-decisão da
canônica (`"INFORMAÇÃO"`, `"INTERVENÇÃO (renegociação)"`, `"TROCA"`,
`"CORREÇÃO (economia)"`), pelos quatro identificadores fechados.

**Critérios de aceite**

- [x] `B11.03-INF` tem `condicao_exibicao` comparando `TIPO_ACAO` com `INFORMACAO`
- [x] `B11.03-REN` tem `condicao_exibicao` comparando `TIPO_ACAO` com `RENEGOCIACAO`
- [x] `B11.03-TRO` tem `condicao_exibicao` comparando `TIPO_ACAO` com `TROCA` — já era esse valor antes desta tarefa (único dos quatro que coincidia com o identificador fechado); confirmado sem alteração
- [x] `B11.03-ECO` tem `condicao_exibicao` comparando `TIPO_ACAO` com `ECONOMIA`
- [x] `collection/carga.py` continua carregando o arquivo sem erro após a edição
- [x] `tests/app_aluno/test_gerador.py`/`T-20` e os testes de `T-84` continuam passando; nenhum teste depende do texto antigo com acento/parênteses

**Status:** `[x] concluída`

**Nota de implementação (T-104).** Os quatro literais de `collection/registros/
bloco-11.yaml` foram trocados diretamente (edição de dado, sem tocar
`app/motor/acoes.py`, como a própria `T-84` previa). `tests/app_aluno/
test_acoes.py::test_nenhum_literal_de_tipo_de_acao_no_modulo` (teste estático
AST que audita `app/motor/acoes.py`, não o YAML) tinha uma denylist com os
literais pré-decisão e citava "`OQ-13` aberta" na docstring — atualizada para
incluir os quatro identificadores fechados (`INFORMACAO`, `RENEGOCIACAO`,
`TROCA`, `ECONOMIA`), manter os identificadores técnicos genéricos descartados
(`INTERVENCAO`, `CORRECAO`) e os literais pré-decisão como denylist histórica,
e citar `OQ-13` respondida. Verificado: `ruff check .` → `All checks passed!`;
`mypy engine persistencia collection app report tests` → `Success: no issues
found in 251 source files`; `pytest -q tests/app_aluno/test_gerador.py
tests/app_aluno/test_acoes.py tests/app_aluno/test_ordem_acoes_dependencia_
externa.py tests/app_aluno/test_acao_sem_divida.py tests/app_aluno/
test_rotas_bloco11.py` → `32 passed, 5 xfailed` (os 5 `xfailed` são as
dependências externas do slug `motor-calculo`, sem relação com esta tarefa).

---

# Rodada 2 — fatia 2A: leitura de reserva e caixa do Bloco 4 (2026-09-07)

| Campo | Valor |
| ----- | ----- |
| Slug | `app-aluno` |
| Spec | [`specs/app-aluno.spec.md`](../specs/app-aluno.spec.md) — blocos "Rodada 2 (2026-09-07) — fatia 2A" (`RF-36`–`RF-44`, `AC-51`–`AC-71`, `US-13`–`US-16`, `EC-15`–`EC-20`, `OQ-20`–`OQ-25`) |
| Plano | [`plans/app-aluno.plan.md`](../plans/app-aluno.plan.md) — seção "Rodada 2" (`R2.1`–`R2.11`) |
| Numeração | `T-108` em diante, contígua a `T-107`. Nada da Rodada 1 é renumerado, reaberto ou alterado |

## Progresso da Rodada 2

`14/14 tarefas concluídas` (`T-108` a `T-120`, mais `T-119A`) — **fatia 2A
fechada** por `T-120` em 2026-09-07. As 13 planejadas mais `T-119A`, aberta
durante a execução para uma causa raiz que a contagem original do plano não
previa (premissa de dependência externa vencida; ver a nota de fechamento de
`T-120`).

> **`T-77`, `T-78` e `T-79` NÃO fazem parte desta fatia** e continuam
> `[ ] pendente`. Elas dependem de `ATAQUE_IMEDIATO_RECOMENDADO`, que segue
> `dinheiro(0)` como placeholder explícito por `motor-calculo:OQ-29`, **aberta**
> (`engine/diagnostico.py:845-850`; spec §10 desta rodada). A fatia 2A não
> promete o Bloco 10 — entrega a reserva mobilizável correta, não o ataque
> imediato. Nenhuma tarefa abaixo as toca, destrava ou marca.
>
> **Atualização (2026-09-10, fora desta fatia).** `motor-calculo:OQ-29` foi
> respondida e implementada por completo pela fatia 4C do `motor-calculo` — o
> parágrafo acima descreve fielmente o estado em 2026-09-07 e é preservado
> como registro histórico, mas não reflete mais o estado atual do campo.
> `T-77`/`T-78`/`T-79` foram destravadas e concluídas na rodada de fechamento
> da Rodada 1 (ver as três entradas na Entrega correspondente e a nota de
> `T-77`). Nenhuma tarefa da fatia 2A foi tocada por esse fechamento.

## Regras que valem para toda tarefa da Rodada 2

> Valem, sem exceção, as "Regras que valem para todo backlog" do topo deste
> arquivo (Lei nº 1, Lei nº 3, `engine/` congelado, `sdd.config.md` §4/§5/§7).
> Acrescem-se, específicas desta fatia:
>
> **Ler não é calcular.** Cada uma das cinco leituras é `resposta → conversão →
> tipo`. **Nenhuma** das três regras da §13.1 (`motor-calculo`, normativa e
> congelada) é reproduzida em `app/`: quem aplica `MIN`/`MAX`, quem
> curto-circuita em `0` e quem propaga `DESCONHECIDO` é
> `engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`, invocado por
> `engine/diagnostico.py:788-815`. Esta fatia muda a **entrada**, nunca a
> derivação (`RF-44`, `AC-68`).
>
> **`_membro_do_enum` JÁ EXISTE** (`app/montagem/estado.py:410`, genérico PEP
> 695). Nenhuma tarefa a cria, reescreve ou duplica — só a chama. Os
> `valor_interno` de `collection/registros/bloco-04.yaml` batem **caractere por
> caractere** com os `name` dos enums de `engine/estado.py`, e por isso
> **nenhuma linha de tradução de rótulo em português é escrita** (`AC-37`,
> `AC-53`).
>
> **Ordem obrigatória.** `T-109` (allowlist, `RF-40`) vem **antes** de `T-110`
> (as leituras). Inverter reprova
> `tests/app_aluno/estatica/test_fronteira_import_engine.py::test_pastas_da_
> aplicacao_nao_importam_engine_interno_ac_41` no meio da rodada — foi
> exatamente essa falha que reprovou e forçou a reversão integral da tentativa
> mecânica anterior (spec §8, discovery §1). `T-108` (`RF-41`) é independente
> das demais e **já falha hoje**: é o primeiro passo.
>
> **Nenhum `Decimal(...)`/`dinheiro(...)` literal novo** em
> `app/montagem/estado.py` — `tests/app_aluno/estatica/
> test_fronteira_decimal_unica.py` falha se houver. O único zero disponível é
> `_ZERO` (`:266`). E **nenhuma leitura de relógio**:
> `test_sem_relogio_em_montagem.py` continua verde.

### Dependências externas desta rodada

| Dependência | De quem | Situação nesta fatia |
| --- | --- | --- |
| `motor-calculo:OQ-26` + `OQ-27` | slug `motor-calculo` | **Ambas** abertas. Bloqueiam a fatia **2C** (`investimentos`, `ativos`). Motivo de `T-111` entregar tupla vazia declarada, não item lido |
| `motor-calculo:OQ-29` | slug `motor-calculo` | Situação em 2026-09-07 (registro histórico desta fatia): aberta, bloqueava `T-77`/`T-78`/`T-79` (Bloco 10), fora desta fatia. **Atualização 2026-09-10:** respondida e implementada por completo (fatia 4C); as três tarefas foram destravadas e concluídas fora da fatia 2A |
| `OQ-21` (local) | especialista do método | Aberta. Bloqueia a **redação** de `RF-43`, não o comportamento nem o ponto de encaixe (`T-115`, `T-116`) |
| `OQ-22`(b), `OQ-24` (locais) | decisão de registro/técnica | Abertas. Bloqueiam **2B**. `T-118` prova que a fatia 2A não depende de `OQ-24` |

---

## Entrega 12 — Fatia 2A: a montagem volta a montar

### `T-108` — Regravar `hashes_congelados.json` a partir da saída do próprio teste

- **Tipo:** `Infra`
- **Dependências:** `nenhuma` — independente das demais desta rodada; **já falha hoje**
- **Rastreia:** `RF-41`, `AC-65`, `AC-44`
- **Arquivos:** `tests/app_aluno/estatica/hashes_congelados.json` (regravado integralmente), `tests/app_aluno/estatica/test_engine_congelado.py` (**só leitura** — nenhuma linha editada)

**Descrição**

`engine/ataque_imediato.py` existe no disco e **não consta** do JSON, então
`test_ac44_json_cobre_todo_py_de_engine_e_persistencia_e_a_migracao_antiga`
(`:139`) falha **antes de qualquer edição desta rodada**. Regravar é o
procedimento correto: `AC-44` proíbe que *esta* feature modifique `engine/`, e
quem modificou foi o slug `motor-calculo` legitimamente, na Rodada 3 dele. O
JSON é **registro, não código** — é o registro de "qual `engine/` este slug
consome".

**Critérios de aceite**

- [x] O JSON é regravado a partir da **saída do próprio teste**, que nomeia arquivo por arquivo — **nunca** de uma lista transcrita de enunciado, plano ou memória (`RF-41` é explícito: lista em enunciado envelhece entre a redação e a execução)
- [x] `engine/ataque_imediato.py` passa a constar do conjunto congelado, com o SHA-256 do conteúdo atual do arquivo
- [x] `persistencia/supabase/migracoes/002_app_aluno.sql` continua **fora** do conjunto, deliberadamente — `test_ac44_migracao_nova_desta_feature_esta_fora_do_conjunto_congelado` (`:153`) continua passando
- [x] Os **quatro** testes de `AC-44` em `tests/app_aluno/estatica/test_engine_congelado.py` passam (`:109`, `:139`, `:153`, `:165`)
- [x] Nenhum arquivo de `engine/` ou `persistencia/` é editado por esta tarefa — só o JSON
- [x] `test_engine_congelado.py` não é alterado: se o teste precisar mudar para a tarefa passar, isso é achado a reportar, não edição a fazer

**Status:** `[x] concluída`

**Nota de implementação.** `hashes_congelados.json` regravado integralmente a
partir da **saída do próprio teste**, nunca de lista transcrita: um script
descartável importou `_descobrir_conjunto_congelado_em_disco` e `_hash_sha256`
do próprio `test_engine_congelado.py` (a fonte de verdade de "quais arquivos
deveriam estar congelados hoje") e recalculou o SHA-256 de cada caminho
descoberto, com guarda-corpo abortando se `002_app_aluno.sql` entrasse no
conjunto. O teste apontou **sete** arquivos, e é essa a lista real — não as
"cinco"/"seis"/"6+1" das notas anteriores: um **ausente** do JSON
(`engine/ataque_imediato.py`, pego por `:139`) e **seis com hash divergente**
(pegos por `:109`): `engine/diagnostico.py`, `engine/estado.py`,
`engine/gates.py`, `engine/motor.py`, `engine/tipos.py` e
`persistencia/arquivo/repositorio_snapshots.py`. Todos os sete são entrega
legítima da Rodada 3 do slug `motor-calculo` (Lei nº 1 preservada: nenhuma
tarefa deste slug tocou `engine/`). O JSON foi de **33 para 34** entradas;
`002_app_aluno.sql` continua fora (`grep` → 0 ocorrências). SHA-256 de
`engine/ataque_imediato.py` conferido de forma independente do script:
`42795bfb8d6744e7d25c9bb4aab712677d7532d5a6da4dbc17695f90797ff038`.
`test_engine_congelado.py` **não** foi alterado (mtime anterior ao do JSON;
nenhuma edição foi necessária para a tarefa passar). Verificado: `ruff check
.` → `All checks passed!`; `pytest -q tests/app_aluno/estatica/
test_engine_congelado.py` → `4 passed` (os quatro de `AC-44`; antes da tarefa
eram `2 failed, 2 passed`).

---

### `T-109` — Ampliar a allowlist de `AC-41` com exatamente dois nomes de `engine.estado`

- **Tipo:** `Infra`
- **Dependências:** `nenhuma` — **precede obrigatoriamente `T-110`**
- **Rastreia:** `RF-40`, `AC-63`, `AC-64`, `AC-41`, `OQ-20` (encaminhada pelo plano, R2.6)
- **Arquivos:** `tests/app_aluno/estatica/test_fronteira_import_engine.py` (`NOMES_PERMITIDOS_DE_ENGINE`, `:103-144`; bloco de comentário justificativo, `:55-102`)

**Descrição**

`EstadoFinanceiro.RESERVA_EXISTE` (`engine/estado.py:511`) e
`.DISPOSICAO_USO_RESERVA` (`:513`) são tipados por enums que só existem em
`engine/estado.py` — não são redefinidos nem reexportados por `engine.tipos`
(que já é liberado por inteiro). Sem liberá-los é impossível montar um
`EstadoFinanceiro` tipado fora de `engine/` sob `mypy --strict`: é o **Critério
A**, já aplicado quatro vezes (`TIPO_DIVIDA`/`T-49`; os 8 do Bloco 2/`T-50`;
`TIPO_RENDA`/`T-51`; `AcaoRequerida`/`T-74`). **Esta tarefa vem antes de
`T-110`** — na ordem inversa o teste de fronteira reprova no meio da rodada.

**Critérios de aceite**

- [x] `NOMES_PERMITIDOS_DE_ENGINE` ganha **exatamente dois** nomes: `"engine.estado.RESERVA_EXISTE"` e `"engine.estado.DISPOSICAO_USO_RESERVA"` — nem um a mais
- [x] Cada um vem acompanhado de comentário justificativo no padrão dos quatro precedentes: cita o Critério A, a tarefa que o exige (`T-110`) e a linha de `engine/estado.py` do campo que ele tipa
- [x] Nenhum dos cinco nomes de 2B/2C entra: `ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO` — allowlist não contém nome que ninguém importa, como o próprio arquivo já registrou sobre `Oportunidade` (`:70-72`)
- [x] `CLASSIFICACAO_MOBILIZACAO` e `Desconhecido` **não** são acrescentados: vivem em `engine.tipos`, já em `MODULOS_LIBERADOS_POR_INTEIRO` (`:151-156`)
- [x] As proibições explícitas continuam recusadas pelo teste (`AC-64`): `engine.gates` além de `AcaoRequerida`, `engine.ciclo_mensal` além de `ErroInvariante`, `engine.metodos.*`, `engine.comparacao`, `engine.ordem`, `from engine import *`
- [x] `pytest tests/app_aluno/estatica/test_fronteira_import_engine.py` passa **antes** de `T-110` começar (a allowlist ampliada não quebra nada por si só) e continua passando **depois** dela

**Status:** `[x] concluída`

**Nota de implementação.** `NOMES_PERMITIDOS_DE_ENGINE` foi de **27 para 29**
entradas — delta **exatamente 2**, medido por AST sobre o literal do arquivo
(não por contagem à vista): `"engine.estado.RESERVA_EXISTE"` e
`"engine.estado.DISPOSICAO_USO_RESERVA"`. Ambos entram pelo **Critério A**, o
mesmo dos quatro precedentes (`TIPO_DIVIDA`/`T-49`, os 8 do Bloco 2/`T-50`,
`TIPO_RENDA`/`T-51`, `AcaoRequerida`/`T-74`): são os enums que **tipam** campos
de `EstadoFinanceiro` — `EstadoFinanceiro.RESERVA_EXISTE`
(`engine/estado.py:511`) e `.DISPOSICAO_USO_RESERVA` (`:513`) — e existem só
em `engine/estado.py` (definidos em `:181` e `:192`), confirmado por leitura:
não são redefinidos nem reexportados por `engine.tipos`. Sem liberá-los é
impossível montar um `EstadoFinanceiro` tipado fora de `engine/` sob `mypy
--strict`. Acrescentado bloco de prosa justificativa no padrão do arquivo
(antes do literal) mais comentário curto junto às duas entradas. Confirmado
por leitura do arquivo, como o enunciado pedia: `CLASSIFICACAO_MOBILIZACAO`
(`engine/tipos.py:173`) e `Desconhecido` (`:32`) **não** foram acrescentados —
`engine.tipos` já está em `MODULOS_LIBERADOS_POR_INTEIRO`; e **nenhum** dos
cinco nomes de 2B/2C entrou, pelo mesmo princípio que o arquivo já registrava
sobre `Oportunidade` (`:70-72`), princípio agora estendido na prosa aos cinco.
Verificado por sonda direta: as seis proibições de `AC-64` continuam recusadas
(`engine.gates` além de `AcaoRequerida`, `engine.ciclo_mensal` além de
`ErroInvariante`, `engine.metodos.*`, `engine.comparacao`, `engine.ordem`,
`from engine import *`), e o import que `T-110` fará
(`from engine.estado import RESERVA_EXISTE, DISPOSICAO_USO_RESERVA` +
`from engine.tipos import CLASSIFICACAO_MOBILIZACAO, Desconhecido`) já é
aceito — a allowlist ampliada não quebra nada por si só. `ruff check .` →
`All checks passed!`; `pytest -q tests/app_aluno/estatica/
test_fronteira_import_engine.py` → `10 passed`.

---

### `T-110` — Implementar as cinco funções de leitura do Bloco 4 em `app/montagem/estado.py`

- **Tipo:** `Data`
- **Dependências:** `T-109`
- **Rastreia:** `RF-36`, `RF-37`, `RF-38`, `AC-51`, `AC-52`, `AC-55`, `AC-56`, `AC-57`, `AC-58`, `AC-59`, `EC-15`, `EC-16`, `EC-17`, `EC-20`
- **Arquivos:** `app/montagem/estado.py` (`+5` funções privadas, `+1` exceção nomeada, `+2` imports de `engine.estado`; reusa `_membro_do_enum` `:410`, `_ou_desconhecido` `:370`, `_ZERO` `:266`); **não tocado:** `app/montagem/conversao.py`, `collection/`, `engine/`

**Descrição**

As cinco leituras, com os nomes **fixados pelo plano** (R2.4.1), cada um o
`VARIAVEL_GRAVADA` do registro em minúscula, no padrão de `_tipo_renda`
(`:1170`) e `_inventario_completo` (`:1204`):
`_reserva_existe`, `_reserva_total`, `_disposicao_uso_reserva`,
`_valor_maximo_reserva_informado_usuario`, `_dinheiro_disponivel`. Mais a
exceção nomeada `ErroDinheiroDisponivelIndeterminado`, dedicada ao caminho de
`EC-20`. Toda leitura é escalar, por `respostas.valor(...)`.

**Critérios de aceite**

- [x] `_reserva_existe(respostas) -> RESERVA_EXISTE` resolve `B4.02`/`RESERVA_EXISTE` por `_membro_do_enum(RESERVA_EXISTE, valor_interno)` — os três membros `SIM`/`INFORMAL`/`NAO` (`bloco-04.yaml:52-57`), nenhum colapsado em outro (`AC-51`)
- [x] `B4.02` sem resposta levanta `ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")` — é `[OBR]` e o campo não admite `Desconhecido`, mesmo padrão de `_tipo_renda`
- [x] `_disposicao_uso_reserva(respostas) -> DISPOSICAO_USO_RESERVA` resolve `B4.03` por `_membro_do_enum` — os quatro membros `PARTE`/`GRANDE_PARTE`/`TALVEZ`/`NAO` (`:127-133`) (`AC-52`)
- [x] **Ausência de `B4.03` devolve `DISPOSICAO_USO_RESERVA.NAO` e não levanta erro** (`EC-16`, `EC-17`) — decisão do usuário (2026-09-07), plano R2.4.2
- [x] **A docstring/comentário de `_disposicao_uso_reserva` deixa explícito que esse `NAO` é AUSÊNCIA ESTRUTURAL, NÃO escolha do aluno.** São situações diferentes — "não tenho reserva" (`RESERVA_EXISTE = NAO`, e por isso `B4.03` nem foi exibida, `bloco-04.yaml:135-137`) versus "tenho reserva e prefiro preservá-la integralmente" (`B4.03` respondida `NAO`) — que compartilham o mesmo registro. Sem o comentário alguém lerá o dado cru e confundirá as duas. O texto deve registrar também que o membro é **aritmeticamente inerte** (a Regra 1 da §13.1 já curto-circuitou por `RESERVA_EXISTE = NAO`) e que isto **não** é reproduzir a Regra 1
- [x] `_reserva_total(respostas) -> DinheiroTalvez` lê `B4.02A`: `Decimal` repassado; `"Não sei."` (`admite_nao_sei: true`, `:76`) → `DESCONHECIDO` por `_ou_desconhecido`; ausência estrutural (`B4.02 = NAO`) → `DESCONHECIDO`, **nunca erro, nunca `Decimal("0")`, nunca `None`** (`AC-55`, `EC-16`)
- [x] `_valor_maximo_reserva_informado_usuario(respostas) -> DinheiroTalvez` lê `B4.03A` e devolve `DESCONHECIDO` em **tudo que não seja um `Decimal` real**: `"Não sei."` (`:155`), a opção sem `valor_interno` `"Prefiro decidir somente depois de ver a análise."` (`:154`, `EC-15`/`OQ-22`(a)) e as duas ausências estruturais (`EC-16`, `EC-17`). Valor real → `Decimal` exato da fronteira única, sem `float` no caminho (`AC-56`)
- [x] Comentário registra que `OQ-22`(a) está **aberta** e que, enquanto estiver, a leitura **não pode** distinguir "decidir depois" de "não sei" pelo `valor_interno` — a Regra 3 da §13.1 já os colapsa em `DESCONHECIDO`, e tratar a opção sem `valor_interno` como outra coisa seria inventar
- [x] `_dinheiro_disponivel(respostas) -> Dinheiro` (**`Dinheiro` puro**, `engine/estado.py:517`) cobre os cinco ramos de R2.4.4: `B4.01 = SIM` + `B4.01A` com valor → o `Decimal` (`AC-57`); `B4.01 = NAO` → `_ZERO` (`AC-58`); `B4.01 = NAO_SEI` (`:18`) → erro (`EC-20`); `B4.01` ausente → erro (`AC-59`); `B4.01 = SIM` com `B4.01A` ausente ou `NAO_SEI` → erro
- [x] `_ZERO` (`:266`) é usado no ramo `NAO` — **nenhum `Decimal(...)` nem `dinheiro(...)` literal novo** é escrito no módulo (`test_fronteira_decimal_unica.py` continua verde). Comentário registra que esse zero é a **transcrição de uma resposta `[OBR]` afirmativa** ("não possuo dinheiro disponível"), não a ausência dela
- [x] `ErroDinheiroDisponivelIndeterminado(VARIAVEL_GRAVADA: str, motivo: str)` é criada como classe **nova e dedicada** — decisão fechada (plano R2.4.1/R2.10): `ErroRespostaAusente` carrega `DIVIDA_ID`/`ID_PERGUNTA` e nasceu para ficha `REP` de dívida; `ErroCampoAgregadoDesconhecido` (`:998`) é declaradamente dedicada a agregados do Bloco 3. Este caminho precisa ser **distinguível na captura** pela chamadora
- [x] A mensagem da exceção é montada por `str.join` sobre segmentos curtos, no padrão de `:1254-1259` — nenhum enunciado de pergunta aparece nela (`AC-37`)
- [x] `valor_interno` fora do domínio do enum levanta `ErroValorInternoDesconhecido` nomeando o enum **e** o valor — nunca um membro "parecido", nunca um default (`AC-54`)
- [x] **Nenhuma chamada a `valores_do_escopo`** em nenhuma das cinco funções: só `respostas.valor(...)` escalar (`AC-71`)
- [x] As cinco funções continuam puras: nenhuma toca relógio, ambiente ou estado global (`test_sem_relogio_em_montagem.py` verde)
- [x] `mypy --strict` limpo nas cinco assinaturas; `ruff check .` limpo

**Status:** `[x] concluída`

**Nota de implementação.** As cinco leituras entraram em
`app/montagem/estado.py` com os nomes fixados pelo plano (R2.4.1), cada uma o
`VARIAVEL_GRAVADA` do registro em minúscula, no padrão de `_tipo_renda`/
`_inventario_completo`, mais a exceção dedicada
`ErroDinheiroDisponivelIndeterminado`. Import ampliado com **exatamente os
dois** nomes liberados por `T-109` (`RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA`
de `engine.estado`) — nenhum dos cinco de 2B/2C. `_membro_do_enum` (`:410`)
foi **chamado, nunca recriado**: os `valor_interno` do registro batem
caractere por caractere com os `name` dos enums, e **nenhuma linha de tradução
de rótulo em português foi escrita** (`AC-37`, `AC-53`).

Verificado por sonda direta (23 asserções, 0 falhas), caminho a caminho:
`_reserva_existe` devolve os **três** membros sem colapso e levanta
`ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")` na ausência;
`_disposicao_uso_reserva` devolve os **quatro** membros e
`DISPOSICAO_USO_RESERVA.NAO` na ausência, **sem erro**; `_reserva_total` e
`_valor_maximo_reserva_informado_usuario` devolvem o `Decimal` exato quando há
valor e `DESCONHECIDO` em `NAO_SEI` e em ausência — nunca `0`, nunca `None`;
`_dinheiro_disponivel` cobre os **cinco** ramos (`SIM`+valor → `Decimal`;
`NAO` → `_ZERO`; `NAO_SEI` → erro; `B4.01` ausente → erro; `SIM` com `B4.01A`
ausente/`NAO_SEI` → erro). `AC-54` conferido nos dois enums: `valor_interno`
fora do domínio levanta `ErroValorInternoDesconhecido` nomeando enum **e**
valor (`"RESERVA_EXISTE: valor_interno 'TALVEZ' não corresponde a nenhum
membro do enum."`), nunca um membro "parecido".

A exigência mais delicada — o comentário sobre o `NAO` da ausência estrutural
— foi atendida em docstring que contrasta explicitamente as **duas situações
humanas** que compartilham o mesmo valor gravado ("não tenho reserva", em que
`B4.03` nem foi exibida por `bloco-04.yaml:135-137`, versus "tenho e prefiro
preservá-la integralmente", em que `B4.03` foi respondida `NAO`), registra que
o membro é **aritmeticamente inerte** (a Regra 1 da §13.1 já curto-circuitou
por `RESERVA_EXISTE = NAO`) e afirma que **isto não é reproduzir a Regra 1** —
esta função nem lê `RESERVA_EXISTE`; quem deriva é
`engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`.

`ErroDinheiroDisponivelIndeterminado` confirmada **distinguível na captura**:
herda direto de `Exception` (`__mro__[1:3]` → `(Exception, BaseException)`),
`issubclass` de `ErroRespostaAusente` e de `ErroCampoAgregadoDesconhecido` é
`False` nas duas. Mensagem por `str.join` sobre segmentos curtos, sem nenhum
enunciado de pergunta. `AC-71` verificado por **AST** sobre o módulo: as cinco
funções usam **só** `respostas.valor` — `valores_do_escopo` não aparece em
nenhuma delas. Verificado: `ruff check .` → `All checks passed!`;
`pytest -q tests/app_aluno/estatica` → `70 passed` (inclui
`test_fronteira_import_engine.py`, `test_fronteira_decimal_unica.py` e
`test_sem_relogio_em_montagem.py` — nenhum `Decimal(...)`/`dinheiro(...)`
literal novo, nenhuma leitura de relógio). `mypy --strict` limpo nas cinco
assinaturas: após esta tarefa o **único** erro restante no repositório era o
construtor incompleto de `:1326`, alvo declarado de `T-111`.

---

### `T-111` — Construir os 21 campos de `EstadoFinanceiro`, com as três coleções como tupla vazia declarada

- **Tipo:** `Data`
- **Dependências:** `T-110`
- **Rastreia:** `RF-39`, `RF-42`, `RF-44`, `AC-60`, `AC-62`, `AC-13`, `EC-19`
- **Arquivos:** `app/montagem/estado.py` (`montar_estado_financeiro`, construtor em `:1326-1344`; docstring da função, `:1290-1325`; docstring do módulo)

**Descrição**

`montar_estado_financeiro` constrói hoje **13** dos **21** campos (`:1326`) —
é a causa raiz única do `build` quebrado. Esta tarefa acrescenta os oito
argumentos: os cinco lidos por `T-110` e as três coleções como **tupla vazia
literal no ponto de construção**, com o motivo em docstring. Sem função de
leitura para as três: **não há o que ler**, e uma função vazia sugeriria
leitura parcial existente (plano R2.4.5, mesmo padrão documentado de
`_CAMPOS_DE_GATE_FORA_DE_ESCOPO`, `:315`). A assinatura da função **não muda**:
nenhum dos cinco vira parâmetro externo novo.

**Critérios de aceite**

- [x] O construtor passa a receber os oito argumentos: `RESERVA_EXISTE=_reserva_existe(respostas)`, `RESERVA_TOTAL=_reserva_total(respostas)`, `DISPOSICAO_USO_RESERVA=_disposicao_uso_reserva(respostas)`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=_valor_maximo_reserva_informado_usuario(respostas)`, `DINHEIRO_DISPONIVEL=_dinheiro_disponivel(respostas)`, `investimentos=()`, `ativos=()`, `recursos_extraordinarios=()`
- [x] A assinatura de `montar_estado_financeiro` permanece **inalterada** — nenhum parâmetro externo novo
- [x] A docstring nomeia, **caractere por caractere**, `motor-calculo:OQ-26` **e** `motor-calculo:OQ-27` como motivo de `investimentos`/`ativos` vazios, registrando que **as duas precisam estar respondidas — responder só uma não destrava**, porque `CLASSIFICACAO_MOBILIZACAO` e `VALOR_LIQUIDO_REALIZAVEL*` são obrigatórios e sem default nas três dataclasses de item, por causas independentes (`AC-62`)
- [x] A docstring nomeia `OQ-22` e `OQ-24` como motivo de `recursos_extraordinarios` vazio (`AC-62`)
- [x] As três são tupla vazia **declarada**, com motivo — jamais omissão silenciosa, jamais estimativa, jamais classificação inventada (`RF-39`, `EC-19`)
- [x] Nenhuma função de leitura é criada para as três coleções nesta fatia
- [x] `montar_estado_financeiro` continua pura (`test_sem_relogio_em_montagem.py` verde) e o resultado continua comparável por `==` estrutural
- [x] `mypy --strict` deixa de reportar o erro de `app/montagem/estado.py:1326` (o construtor incompleto)

**Status:** `[x] concluída`

**Nota de implementação.** O construtor de `montar_estado_financeiro` passou
de **13 para os 21** campos com os oito argumentos exatos do enunciado: os
cinco lidos por `T-110` mais `investimentos=()`, `ativos=()` e
`recursos_extraordinarios=()`. A **assinatura não mudou** — nenhum dos cinco
virou parâmetro externo novo; todos são lidos de `respostas`, confirmado por
`inspect.signature`, que devolve os mesmos seis parâmetros de antes
(`respostas`, `DATA_REFERENCIA`, `dividas`, `CONFIABILIDADE_DADOS`,
`economia_nao_identificada`, `DIVIDA_ID_PARA_LINHA_CONTINUA`).

As três coleções são **tupla vazia declarada no ponto de construção**, com
comentário no local e motivo em docstring — jamais omissão silenciosa. Nenhuma
função de leitura foi criada para elas: **não há o que ler**, e uma função
vazia sugeriria leitura parcial existente (plano R2.4.5, mesmo padrão
documentado de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO`, `:315`). A docstring nomeia
**nominalmente e caractere por caractere** `motor-calculo:OQ-26` **e**
`motor-calculo:OQ-27` para `investimentos`/`ativos`, registrando que **as duas
precisam estar respondidas e que responder só uma não destrava** (por causas
independentes: `CLASSIFICACAO_MOBILIZACAO` e `VALOR_LIQUIDO_REALIZAVEL*` são
obrigatórios e sem default nas três dataclasses de item), e nomeia `OQ-22` e
`OQ-24` para `recursos_extraordinarios`. Registra também que
`CLASSIFICACAO_MOBILIZACAO` **não** é derivada nesta camada em hipótese
alguma — seria fórmula patrimonial, proibida pela Lei nº 3 (`RF-44`) — e que a
§13.1 continua sendo aplicada só pelo motor (`AC-68`): esta fatia muda a
**entrada**, nunca a derivação.

**O erro de `build` foi zerado.** Antes: `app/montagem/estado.py:1326: error:
Missing positional arguments "RESERVA_EXISTE", "RESERVA_TOTAL",
"DISPOSICAO_USO_RESERVA", "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO",
"DINHEIRO_DISPONIVEL", "investimentos", "ativos", "recursos_extraordinarios"
in call to "EstadoFinanceiro" [call-arg]` → `Found 1 error in 1 file (checked
274 source files)`. Depois: `Success: no issues found in 274 source files`.
`ruff check .` → `All checks passed!`;
`pytest -q tests/app_aluno/estatica` → `70 passed` (pureza e fronteiras
intactas).

**Sobre as 126 falhas: caíram só de `126 failed` para `125 failed` — e isso
era o esperado, não uma regressão.** A causa raiz é única, mas ela **não é** o
`build`: é a fixture sem Bloco 4, que é `T-112`, a tarefa seguinte
(`tests/app_aluno/fixtures/caso_completo.py` — `grep` por
`RESERVA_EXISTE|DINHEIRO_DISPONIVEL|B4.` → **0 ocorrências**). Medido: das
falhas residuais, **todas** as mensagens de erro são
`ErroRespostaAusente: pergunta obrigatória 'B4.02' ('RESERVA_EXISTE') sem
resposta`; os poucos `AssertionError` são sintoma a jusante do mesmo erro
(requisição cujo cálculo levantou). Comprovado por medição direta, **sem
editar a fixture** (arquivo de `T-112`): injetando as seis respostas de Bloco 4
em memória por plugin descartável de `pytest`, `tests/app_aluno` vai de
`125 failed, 46 errors` para `42 failed, 0 errors` — os **46 erros e 83
falhas** somem de uma vez. Dos 42 restantes, 32 são de
`test_montagem_estado_financeiro.py`, que montam a própria `RespostasCaso`
localmente em vez de usar o dicionário compartilhado — exatamente o
"reconciliar os construtores" que `T-112` já prevê no enunciado. Fora de
`tests/app_aluno/`: `534 passed, 9 skipped`, **idêntico ao antes** — nenhuma
regressão.

**Achado a reportar, fora do escopo destas duas tarefas (vira tarefa nova,
não conserto silencioso).** Os 10 restantes (`test_acoes.py`,
`test_acompanhamento_acao_id.py`, `test_ordem_acoes_dependencia_externa.py`)
falham numa **premissa de dependência externa que chegou**: eles afirmam
`assert not hasattr(AcaoRequerida, "TIPO_ACAO")` com a mensagem *"premissa do
teste: `AcaoRequerida` real ainda não publica `TIPO_ACAO` (`OQ-13`) — se este
assert falhar, a dependência externa chegou e `T-84` precisa ser revisitada"*.
Conferido: `engine.gates.AcaoRequerida.__dataclass_fields__` **já publica**
`ACAO_ID` e `TIPO_ACAO`. É entrega do slug `motor-calculo`, sem nenhuma
relação com esta fatia — estas duas tarefas não tocam `app/motor/acoes.py`
nem `engine/`. Antes destas tarefas essas falhas estavam **mascaradas**: os
testes morriam mais cedo, na montagem, e nem alcançavam a asserção.

---

### `T-112` — Acrescentar as respostas do Bloco 4 à fixture `caso_completo` e reconciliar os construtores de `EstadoFinanceiro` deste slug

- **Tipo:** `Test`
- **Dependências:** `T-111`
- **Rastreia:** `RF-42`, `AC-66`, `AC-13`
- **Arquivos:** varredura real por `EstadoFinanceiro(` no repositório inteiro, com linha:
  - `tests/app_aluno/fixtures/caso_completo.py:127-139` (`_VALORES_CASO`) — **não constrói `EstadoFinanceiro` diretamente**; monta as respostas de onde `montar_estado_financeiro` lê. **É o arquivo com trabalho real desta tarefa**: hoje `_VALORES_CASO` não tem nenhuma resposta de Bloco 4, então toda montagem a partir da fixture cai no caminho de erro de `_dinheiro_disponivel`/`_reserva_existe`
  - `tests/app_aluno/test_conversao_decimal.py:300` — **já tem os 8 campos** (comentário "Rodada 3 (T-96/T-97)", `:314-328`). Verificar e não editar sem motivo
  - `tests/app_aluno/test_plano_ec07_ec08_ec09.py:347` — **já tem os 8 campos** (`:361-373`). Verificar e não editar sem motivo
  - `app/montagem/estado.py:1326` — coberto por `T-111`
  - `persistencia/arquivo/repositorio_snapshots.py:382` — **já tem os 8 campos** (`:396-405`). **Não editar:** `AC-44` proíbe esta feature de modificar `persistencia/arquivo/`
  - Fora deste slug, **já atualizados pela Rodada 3 de `motor-calculo`, nenhum é trabalho desta tarefa** — verificar apenas que continuam verdes: `tests/fixtures/carregar.py:219`, `tests/regras/test_bola_de_neve.py:483`, `tests/regras/test_avalanche.py:313`, `tests/regras/test_A.py:155`, `tests/regras/test_R.py:172`, `tests/regras/test_M.py:167`, `tests/regras/test_F.py:161`, `tests/regras/test_H.py:182`, `tests/regras/test_hibrido.py:200`, `tests/regras/test_troca.py:123`, `tests/regras/test_simular_cenario.py:183`, `tests/regras/test_diagnostico.py:67`, `tests/regras/test_estado.py:120`, `tests/invariantes/test_propriedades.py:259`, `tests/invariantes/test_gab01_seguro.py:120`, `tests/invariantes/test_gab02_inventario.py:155`, `tests/invariantes/test_gab03_rotativo.py:145`, `tests/invariantes/test_gab04_estabilizacao.py:179`, `tests/invariantes/test_gab05_troca.py:136`, `tests/desempenho/test_orcamento_30_dividas.py:170`

**Descrição**

**Lição aplicada da Rodada 3 de `motor-calculo`:** lá, uma tarefa listou só os
arquivos de `engine/` no campo "Arquivos", os consumidores externos ficaram
órfãos e foi preciso abrir tarefa nova no meio da execução. O campo acima é o
resultado de uma **varredura real** (`EstadoFinanceiro(` em todo o
repositório), com número de linha e com o estado de cada ocorrência declarado —
inclusive as que **não** são trabalho desta tarefa, para que ninguém precise
redescobrir isso durante a execução.

**Critérios de aceite**

- [x] `_VALORES_CASO` de `tests/app_aluno/fixtures/caso_completo.py` ganha as respostas do Bloco 4 que `montar_estado_financeiro` passou a ler: `DINHEIRO_DISPONIVEL_EXISTE`, `DINHEIRO_DISPONIVEL`, `RESERVA_EXISTE`, `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` — pelos `valor_interno` exatos do registro, sobrescrevíveis parcialmente como os demais
- [x] Os valores monetários da fixture passam por `converter_para_dinheiro(...)`, o mesmo idioma já usado por `RENDA_PRINCIPAL`/`CAPACIDADE_ATAQUE_DECLARADA` (`:129`, `:134`) — nenhum `float`, nenhum `Decimal` construído à mão
- [x] Um comentário na fixture registra **por que** o caso padrão escolheu cada valor de Bloco 4, no estilo dos comentários já existentes de `T-103`/`T-52`
- [x] `tests/app_aluno/test_conversao_decimal.py:300` e `tests/app_aluno/test_plano_ec07_ec08_ec09.py:347` são **verificados** e, já tendo os 8 campos, não são editados sem motivo registrado
- [x] Nenhum arquivo de `persistencia/` e nenhum de `engine/` é editado (`AC-44`)
- [x] `pytest -q tests/app_aluno/` passa **integralmente**: nenhuma das ~129 falhas de causa raiz única permanece (`AC-66`) — as 125+46 caíram a **zero**; as 9 residuais são de `T-119A`, causa raiz DIFERENTE e declarada
- [x] Qualquer construtor de `EstadoFinanceiro` descoberto durante a execução e **ausente** da lista acima é reportado como achado — a lista foi levantada por varredura e deveria estar completa

**Status:** `[x] concluída`

**Nota de implementação.** A varredura por `EstadoFinanceiro(` foi **refeita** e
bateu com a lista do enunciado, **sem nenhuma ocorrência nova** — 24 no total,
das quais só uma era trabalho desta tarefa. Única correção de coordenada:
`app/montagem/estado.py` migrou de `:1326` para `:1571` porque `T-111`
acrescentou a docstring dos oito campos; é o mesmo construtor. Confirmado por
leitura que `tests/app_aluno/test_conversao_decimal.py:300` e
`test_plano_ec07_ec08_ec09.py:347` **já têm os 8 campos** com o comentário
"Rodada 3 (T-96/T-97)" — nenhum dos dois foi editado. Nenhum arquivo de
`persistencia/` nem de `engine/` foi tocado (`AC-44`).

**O trabalho real foram TRÊS arquivos, não um.** O enunciado previa a fixture;
a execução mostrou que o "reconciliar os construtores" do título tinha um
segundo e um terceiro caso, ambos legítimos e ambos corrigidos:

1. `tests/app_aluno/fixtures/caso_completo.py` — `_VALORES_CASO` ganhou os seis
   `VARIAVEL_GRAVADA` do Bloco 4 pelos `valor_interno` exatos de
   `collection/registros/bloco-04.yaml` (`SIM`, `SIM`, `PARTE`), com os três
   monetários por `converter_para_dinheiro(...)` — a fronteira única (`RF-13`),
   mesmo idioma de `RENDA_PRINCIPAL`. Um comentário de bloco registra **por que
   cada ramo**: o caso completo é o aluno que respondeu tudo, então cada campo
   recebe o ramo afirmativo e conhecido (`B4.01 = SIM` com valor, e não o zero
   de `AC-58` nem o erro de `EC-20`; `B4.02 = SIM`, e não o `NAO` que suprimiria
   três dos cinco campos por `condicao_exibicao`; `B4.03 = PARTE` com valor, e
   não o `TALVEZ` sem valor de `AC-56`). Registra também **por que 3.000,00 <
   10.000,00**: assim o `MIN` da Regra 2 da §13.1 não satura e o motor devolve o
   valor declarado — quem quiser o caso saturado sobrescreve (`T-114`/`AC-68`).
   A fixture **não antecipa esse cálculo em lugar nenhum** (`RF-44`).
2. `tests/app_aluno/test_montagem_estado_financeiro.py` —
   `_respostas_minimas_completas` é o **segundo** construtor da base de
   respostas deste slug e monta a própria `RespostasCaso` em vez de usar a
   fixture. Recebeu os mesmos seis valores, com comentário apontando para a
   fixture como fonte dos motivos; os dois ficam reconciliados, nunca
   divergentes. Este era o grupo dos **32** que `T-111` já havia previsto.
3. `tests/app_aluno/e2e/test_ciclo_completo.py` — **achado da execução,
   corrigido aqui porque é `AC-66` e não outra tarefa.** O e2e reproduz as
   respostas da fixture pela rota HTTP **real**, e ordenava por `sorted()`. Com
   só campos `OBR` incondicionais a ordem alfabética funcionava **por acaso**;
   o Bloco 4 a quebra em dois pares reais: `DINHEIRO_DISPONIVEL` (B4.01A, idx 7)
   vinha antes de `DINHEIRO_DISPONIVEL_EXISTE` (B4.01, idx 8), e
   `DISPOSICAO_USO_RESERVA` (B4.03, idx 9) antes de `RESERVA_EXISTE` (B4.02,
   idx 21). A rota devolvia `400 — "Pergunta não está aberta para resposta."`
   **A rota estava ACERTANDO**: `condicao_exibicao` (`bloco-04.yaml:36`,
   `:135-137`) não estava satisfeita ainda. Errada estava a ordem de reprodução
   do teste. A correção é ordenar pela **ordem do registro**
   (`ambiente.colecao_filtrada.registros`), que é a ordem em que o aluno
   responde na tela — **mais** fiel ao caminho real, não um contorno, e nenhuma
   asserção foi enfraquecida. O e2e agora exercita o Bloco 4 inteiro por HTTP.

**Números medidos.** `tests/app_aluno` antes: `125 failed, 624 passed, 65
skipped, 5 xfailed, 46 errors`. Depois: **`0 failed` da causa raiz desta
tarefa** — `9 failed, 1324 passed, 75 skipped` na suíte inteira, e os **9 são
integralmente de `T-119A`** (`test_acoes.py` ×2,
`test_acompanhamento_acao_id.py` ×2, `test_ordem_acoes_dependencia_externa.py`
×5), a premissa `assert not hasattr(AcaoRequerida, "TIPO_ACAO")` que deixou de
valer quando `motor-calculo` entregou os campos. Causa raiz **diferente**, fora
do escopo por instrução explícita — não corrigidos aqui. `ruff check .` →
`All checks passed!`; `mypy` → `Success: no issues found in 274 source files`
(o `build` limpo de `T-111` **continua** limpo).

---

### `T-113` — Testar as cinco leituras do Bloco 4 e os quatro casos de borda

- **Tipo:** `Test`
- **Dependências:** `T-110`, `T-111`, `T-112`
- **Rastreia:** `AC-51`, `AC-52`, `AC-54`, `AC-55`, `AC-56`, `AC-57`, `AC-58`, `AC-59`, `AC-60`, `EC-15`, `EC-16`, `EC-17`, `EC-20`
- **Arquivos:** `tests/app_aluno/test_montagem_bloco_04.py` (**arquivo novo**), `tests/app_aluno/fixtures/caso_completo.py` (só consumo)

**Descrição**

Unitários de leitura, uma `RespostasCaso` montada em memória por caso, sem
banco — mesmo padrão de `tests/app_aluno/test_montagem_estado_financeiro.py`.
Testa a **saída observável** da montagem (o campo do `EstadoFinanceiro`), não a
função privada isolada. Tolerância **zero**: nenhum valor desta fatia é
acumulado, então `assertar_monetario` (± R$ 0,05) é proibido aqui.

**Critérios de aceite**

- [x] `AC-51` — um teste por membro de `RESERVA_EXISTE`: `SIM`, `INFORMAL`, `NAO`. O caso de `INFORMAL` assere `is RESERVA_EXISTE.INFORMAL`, provando que nenhum é colapsado em outro
- [x] `AC-52` — um teste por membro de `DISPOSICAO_USO_RESERVA`: `PARTE`, `GRANDE_PARTE`, `TALVEZ`, `NAO`
- [x] `AC-54` — `valor_interno` gravado fora do domínio levanta `ErroValorInternoDesconhecido`, e a mensagem **nomeia o enum e o valor**
- [x] `AC-55` — `B4.02A = "Não sei."` → `RESERVA_TOTAL is DESCONHECIDO`; asserção explícita de que **não** é `Decimal("0")` e **não** é `None`
- [x] `AC-56` — `B4.03A = "Não sei."` → `is DESCONHECIDO`; `B4.03A` com valor monetário → `Decimal` exato da fronteira única, sem `float` no caminho
- [x] `AC-57` — `B4.01 = SIM` + `B4.01A = "1234,56"` → `DINHEIRO_DISPONIVEL == Decimal("1234.56")`, e a construção **não** levanta o `TypeError` de `_recusar_float`
- [x] `AC-58` — `B4.01 = NAO` e `B4.01A` sem resposta → `DINHEIRO_DISPONIVEL` é o zero da fronteira única; o teste documenta que é zero **legítimo lido de resposta**, não default
- [x] `AC-59` — `B4.01` e `B4.01A` ambas sem resposta → `ErroDinheiroDisponivelIndeterminado`, citando a variável. Assere que a montagem **nunca** devolve `0` por omissão
- [x] `EC-20` — `B4.01 = NAO_SEI` com `B4.01A` não exibida → a **mesma** exceção nomeada, capturável distintamente de `ErroRespostaAusente` e de `ErroCampoAgregadoDesconhecido`
- [x] `EC-15` — `B4.03A` respondida com a opção sem `valor_interno` ("Prefiro decidir somente depois de ver a análise.") → `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO`, **o mesmo** resultado de `"Não sei."`
- [x] `EC-16` — `B4.02 = NAO` com `B4.02A`/`B4.03` ausentes: a montagem **não levanta erro**; `RESERVA_EXISTE is NAO`, `RESERVA_TOTAL is DESCONHECIDO`, `DISPOSICAO_USO_RESERVA is NAO`
- [x] `EC-17` — `B4.03 = NAO` com `B4.03A` ausente: sem erro; `DISPOSICAO_USO_RESERVA is NAO` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO`. **A montagem não antecipa o zero** — nenhuma asserção do teste espera `RESERVA_MOBILIZAVEL` calculado aqui
- [x] `AC-60` — as três coleções são `()` **mesmo com fichas de investimento, imóvel, veículo e outro ativo preenchidas** nas respostas: a lacuna é do contrato, não da coleta
- [x] Cada teste cita no nome ou na docstring o `AC-NN`/`EC-NN` que rastreia (`sdd.config.md` §5)
- [x] Nenhum uso de `assertar_monetario` neste arquivo — a régua é igualdade exata

**Status:** `[x] concluída`

**Nota de implementação.** Arquivo novo
`tests/app_aluno/test_montagem_bloco_04.py`, **28 testes** para os 15 critérios
(os quatro de `T-114` entram no mesmo arquivo, abaixo). Uma `RespostasCaso` em
memória por caso, sem banco, e a asserção sempre sobre o **campo do
`EstadoFinanceiro` devolvido** — nunca sobre a função privada isolada
(`sdd.config.md` §5). **Zero ocorrência de `assertar_monetario`**: a régua é
`==` exato e `is` para os singletons.

**A ausência de resposta foi reproduzida por REMOÇÃO, não por sobrescrita.** O
helper local `_sem(respostas, *variaveis)` filtra as respostas já montadas pela
fixture, porque sobrescrever com `None` grava uma `Resposta` de valor nulo — que
é coisa DIFERENTE de pergunta não respondida, e justamente a diferença que
`EC-15` (opção com `valor_interno: null`) e `AC-59` (pergunta ausente) precisam
distinguir. Confirmado por medição: com sobrescrita `None` a resposta existe
(`valor` → `None`); com `_sem` ela não existe.

**Duas asserções mereceram nota.** (a) `EC-15` assere a **igualdade entre os
dois resultados**, e não só que cada um é `DESCONHECIDO` — é essa igualdade que
quebrará no dia em que `OQ-22`(a) fechar decidindo distinguir "decidir depois"
de "não sei", avisando que o teste precisa acompanhar a mudança de registro.
(b) `AC-51`/`AC-52` provam "nenhum membro colapsado em outro" por
**cardinalidade** (`len(set(lidos)) == 3` / `== 4`), e não por `is not` depois
do `is`: `mypy --strict` recusa os `is not` como `comparison-overlap`, e **está
certo** — depois de `assert x is INFORMAL` o tipo está estreitado e os `is not`
seguintes são estaticamente mortos. A cardinalidade é asserção viva e mais
forte: pega inclusive a implementação que devolvesse sempre o mesmo membro.
`EC-20` prova a capturabilidade distinta por duas vias independentes:
`issubclass` nas quatro direções **e** execução real do caminho.

**Os testes foram verificados por mutação, não só por ficarem verdes.** Três
mutantes temporários em `app/montagem/estado.py`, cada um revertido em seguida
(hash do arquivo conferido no fim, sem resíduo): (1) colapsar `INFORMAL` em
`SIM` → `1 failed`; (2) `RESERVA_TOTAL` ausente devolvendo `_ZERO` em vez de
`DESCONHECIDO` → `2 failed`; (3) aplicar a Regra 2 (`min`) dentro da montagem →
`1 failed`, pego pelo `AC-68` de `T-114`. Restaurado o original: `32 passed`.
Sem esse passo, "verde" só provaria que os testes rodam.

`ruff check .` → `All checks passed!`; `mypy` →
`Success: no issues found in 275 source files` (274 + o arquivo novo);
`pytest -q tests/app_aluno/test_montagem_bloco_04.py` → `32 passed`.

---

### `T-114` — Provar por integração com o motor real que a reserva declarada chega a `RESERVA_MOBILIZAVEL`

- **Tipo:** `Test`
- **Dependências:** `T-113`
- **Rastreia:** `AC-67`, `AC-68`, `AC-69`, `RF-36`, `RF-37`, `RF-44`
- **Arquivos:** `tests/app_aluno/test_montagem_bloco_04.py` (bloco de integração), `tests/app_aluno/fixtures/caso_completo.py` (só consumo); **leitura de referência:** `engine/diagnostico.py:788-815`, `engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL`

**Descrição**

O **ganho observável** da fatia: `RESERVA_MOBILIZAVEL` deixa de ser o `0` que a
montagem produzia (passando `RESERVA_EXISTE = NAO`) e passa a ser o valor real
da §13.1. `calcular_plano` de verdade, parâmetros reais, tolerância **zero**.
`AC-68` é o teste que prova, por **assimetria**, que a Regra 2 não foi
reproduzida em `app/`: o limite `MIN`/`MAX` aparece na saída do motor e **não
tem contrapartida** em nenhuma linha da montagem.

**Critérios de aceite**

- [x] `AC-67` — `B4.02 = SIM`, `B4.03 = PARTE`, `B4.02A = 10000`, `B4.03A = 3000` → `snapshot.diagnostico.RESERVA_MOBILIZAVEL == Decimal("3000")`
- [x] `AC-68` — mesmo caso com `B4.03A = 30000` e `B4.02A = 10000` → `RESERVA_MOBILIZAVEL == Decimal("10000")`. O teste registra em docstring que o limite é aplicado **pelo motor** (`MIN(RESERVA_TOTAL, MAX(0, informado))`, Regra 2 da §13.1) e que a montagem não o reproduz em lugar nenhum
- [x] `AC-69` — `B4.02 = SIM`, `B4.03 = TALVEZ`, `B4.03A = "Não sei."` → `RESERVA_MOBILIZAVEL is DESCONHECIDO`. Nenhum ponto do caminho o converte em zero
- [x] Os três invocam `calcular_plano` real, com parâmetros reais — não um dublê nem um `Diagnostico` construído à mão
- [x] **`assertar_monetario` (± R$ 0,05) é proibido nos três**: nenhum valor desta fatia é acumulado, todos são leitura direta. A régua é igualdade exata
- [x] Nenhum arquivo de `engine/` é editado (`AC-44`)

**Status:** `[x] concluída`

**Nota de implementação.** Bloco de integração
`TestT114IntegracaoComOMotorReal` em
`tests/app_aluno/test_montagem_bloco_04.py` — **4 testes**, todos por
`calcular_plano` REAL sobre `FonteParametrosArquivo().carregar("1.0.1")`, os 45
parâmetros lidos de `parameters/` e nunca escritos no teste (`sdd.config.md`
§4). Nenhum dublê, nenhum `Diagnostico` construído à mão; a dívida do caso vem
de `montar_divida` sobre as MESMAS respostas, para que o motor tenha inventário
real para ranquear. Zero `assertar_monetario`: `==` exato e `is` para
`DESCONHECIDO`. Nenhum arquivo de `engine/` editado (`AC-44`).

**Os valores que o motor devolveu, medidos:**

| Caso | Entrada MONTADA (app) | Saída do MOTOR |
| --- | --- | --- |
| `AC-67` | `RESERVA_TOTAL=10000.00`, `VALOR_MAXIMO=3000.00` | `RESERVA_MOBILIZAVEL = Decimal("3000.00")` |
| `AC-68` | `RESERVA_TOTAL=10000.00`, `VALOR_MAXIMO=30000.00` | `RESERVA_MOBILIZAVEL = Decimal("10000.00")` |
| `AC-69` | `RESERVA_TOTAL=10000.00`, `VALOR_MAXIMO=DESCONHECIDO` | `RESERVA_MOBILIZAVEL = DESCONHECIDO` |

**`AC-68` é o critério que carrega a fatia, e foi escrito para provar a
assimetria, não só o número.** A tabela mostra o essencial: a montagem entrega
os **30.000 INTACTOS** ao motor, e o motor devolve **10.000**. Alguém aplicou
`MIN(RESERVA_TOTAL, MAX(0, informado))` — e como a entrada saiu ilesa da
montagem, quem aplicou foi `engine/ataque_imediato.py::
derivar_RESERVA_MOBILIZAVEL`, invocado por `engine/diagnostico.py:788-815`. Por
isso o teste assere **os dois lados**: `estado.VALOR_MAXIMO_RESERVA_INFORMADO_
USUARIO == Decimal("30000.00")` (a entrada) E `RESERVA_MOBILIZAVEL ==
Decimal("10000")` (a saída). Asserir só a saída deixaria o bug invisível: se a
montagem passasse a "ajudar" limitando na entrada, o resultado final continuaria
10.000 e o teste seguiria verde enquanto a Regra 2 tivesse vazado para `app/`.
**Comprovado por mutação:** ao inserir `min(total, traduzido)` dentro de
`_valor_maximo_reserva_informado_usuario`, este teste falha (mutante 3 de
`T-113`) — a sentinela funciona de verdade.

Em `AC-69` o `TALVEZ` é deliberado e não intercambiável: com `NAO` a Regra 1 da
§13.1 zeraria antes de a Regra 3 ser alcançada, e o teste passaria pelo motivo
errado, provando zero em vez de `DESCONHECIDO`.

**Um quarto teste, além dos três critérios, registra o GANHO por contraste**
(`test_o_ganho_da_fatia_reserva_declarada_deixa_de_sair_zero`): roda o motor
para o aluno que declara `NAO` e para o que declara `SIM` + `PARTE` + valor, e
assere que os resultados são **diferentes** (`0` × `3000`). Antes da fatia a
montagem não lia o Bloco 4 e o estado saía sempre com `RESERVA_EXISTE = NAO`,
então a Regra 1 zerava `RESERVA_MOBILIZAVEL` para TODO aluno — respostas
diferentes produziam o mesmo zero. É essa indistinção que a fatia elimina, e
este teste é o que quebraria se ela voltasse.

`pytest -q tests/app_aluno/test_montagem_bloco_04.py::TestT114IntegracaoComOMotorReal`
→ `4 passed`. `ruff` limpo; `mypy` → `Success: no issues found in 275 source
files`; suíte inteira `1356 passed, 75 skipped, 9 failed` (os 9 de `T-119A`).

---

### `T-115` — Criar `ContextoReservaMobilizavel` e `_reserva_mobilizavel` em `report/plano.py`

- **Tipo:** `UI`
- **Dependências:** `T-111`
- **Rastreia:** `RF-43`, `AC-70`, `EC-18`
- **Arquivos:** `report/plano.py` (`+1` dataclass, `+1` função, `+1` campo em `ContextoPlano` `:471-492`, montagem em `montar_contexto_plano` `:495`); **não tocado:** `app/`

**Descrição**

**A localização é decisão fechada do plano (R2.4.7): `report/`, não `app/`, e
no padrão `ContextoPendencias`/`_pendencias`/`pendencias.html` (`:410-431`) —
a convenção da tela do ALUNO.** Não se reusa `_formatar_valor_ou_desconhecido`
(`:180`), que é a convenção da tela do **REVISOR** (rótulo técnico
`"DESCONHECIDO"`, `RF-26`/`AC-29`): adequada lá, inadequada aqui. A leitura no
`.py` é pura — `is DESCONHECIDO`, nenhuma aritmética, nenhuma inferência,
mesma disciplina de `_campos_desconhecidos_da_divida` (`:419`).

**Critérios de aceite**

- [x] `ContextoReservaMobilizavel` é `@dataclass(frozen=True, slots=True)` com **dois campos separados**: `pendente_de_decisao: bool` e `valor: str` — não um texto que o template precise interpretar
- [x] `valor` é `""` quando `pendente_de_decisao` é `True`; formatado quando é `False`
- [x] `_reserva_mobilizavel(snapshot: SnapshotOrdem) -> ContextoReservaMobilizavel` decide por `is DESCONHECIDO` sobre `snapshot.diagnostico.RESERVA_MOBILIZAVEL` (`DinheiroTalvez`, `engine/diagnostico.py:654`) — nenhuma aritmética, nenhuma inferência
- [x] O ramo desconhecido **nunca** passa por `_formatar_valor_de_apoio`: aquela função faria `str(valor)` e produziria `"Desconhecido.DESCONHECIDO"`
- [x] `ContextoPlano` ganha **um** campo, `reserva_mobilizavel: ContextoReservaMobilizavel`, preenchido por `montar_contexto_plano`
- [x] Nenhum caminho levanta exceção ao encontrar `DESCONHECIDO` (`EC-18`)
- [x] `RF-43` **não exige ampliação de allowlist**: `DESCONHECIDO` vem de `engine.tipos`, já liberado por inteiro. Se alguma ampliação parecer necessária, é achado a reportar, não edição a fazer
- [x] `mypy --strict` e `ruff check .` limpos

**Status:** `[x] concluída`

**Nota de implementação.** `ContextoReservaMobilizavel` (dois campos
separados, `pendente_de_decisao: bool` + `valor: str`) e
`_reserva_mobilizavel` em `report/plano.py`, imediatamente antes de
`ContextoPosicao`; `ContextoPlano` ganhou **um** campo,
`reserva_mobilizavel`, preenchido na única construção existente
(`montar_contexto_plano` — confirmado por varredura: `ContextoPlano(` aparece
em um só lugar em todo o repositório).

**A localização seguiu a decisão fechada do plano (R2.4.7), sem reabrir.**
Convenção de `ContextoPendencias`/`_pendencias`/`pendencias.html` — a da tela
do **ALUNO** —, não `_formatar_valor_ou_desconhecido`, que renderiza o rótulo
técnico `"DESCONHECIDO"` e é a convenção da tela do **REVISOR**
(`RF-26`/`AC-29`). Os dois padrões foram lidos antes de escrever. Divisão de
trabalho idêntica à de `_pendencias`: leitura pura no `.py`, texto em
português no template.

O corpo da função é uma comparação e dois retornos — `is DESCONHECIDO`,
nenhuma aritmética, nenhuma inferência, mesma disciplina de
`_campos_desconhecidos_da_divida` (`:419`). **A Regra 2 da §13.1 não foi
reimplementada em `report/`**: o valor chega DERIVADO de
`engine/ataque_imediato.py::derivar_RESERVA_MOBILIZAVEL` (via
`engine/diagnostico.py`), e esta camada só decide COMO mostrá-lo. Nenhum
arquivo de `engine/` nem `app/montagem/estado.py` foi tocado.

**Sobre a allowlist, o critério verificou-se sem edição:** `DESCONHECIDO`
vem de `engine.tipos`, já importado por inteiro em `report/plano.py`
(`:135`) para `_pendencias`/`_formatar_valor_ou_desconhecido`. Nenhuma
ampliação foi necessária e nenhuma foi feita.

**Uma mudança fora dos arquivos listados, mínima e obrigatória:**
`report/pdf.py::renderizar_html_do_plano` (`+1` linha) passa
`reserva_mobilizavel=contexto.reserva_mobilizavel` ao `template.render`. É a
**única** função de renderização de `plano.html` — tela e PDF chamam a mesma
—, então sem essa linha o `{% include %}` de `T-116` não receberia contexto
e o bloco simplesmente não apareceria em produção. Registrada aqui porque não
constava do campo **Arquivos** da tarefa.

`ruff check .` → `All checks passed!`; `mypy` → `Success: no issues found in
275 source files` (verificado logo após `T-115`, antes de `T-116`/`T-117`).

---

### `T-116` — Criar `reserva_mobilizavel.html` com o ponto de encaixe do estado pendente (`OQ-21` aberta)

- **Tipo:** `UI`
- **Dependências:** `T-115`
- **Rastreia:** `RF-43` (**cobertura parcial declarada**), `AC-70`, `EC-18`, `OQ-21` (**aberta**)
- **Arquivos:** `report/templates/plano/reserva_mobilizavel.html` (**arquivo novo**), `report/templates/plano/plano.html` (`{% include %}` no mesmo ponto em que `pendencias.html` é incluído)

**Descrição**

**A REDAÇÃO É `OQ-21`, ABERTA, E NÃO SE INVENTA AQUI.** O plano fixa o
**comportamento** e o **ponto de encaixe**; `RF-43` é explícito: *"esta spec
fixa o comportamento, não o texto"*. Esta tarefa entrega a estrutura
condicional e o comportamento testável; o texto definitivo que o aluno lê entra
quando `OQ-21` for respondida pelo especialista. Precedente do projeto:
`app/consentimento/registro.py`, onde texto pendente (`PEND-01`) tem ponto de
encaixe pronto e conteúdo externo.

**Critérios de aceite**

- [x] `reserva_mobilizavel.html` tem a estrutura condicional sobre `reserva_mobilizavel.pendente_de_decisao` — um bloco para o estado pendente, outro para o valor
- [x] O bloco de valor exibe `{{ reserva_mobilizavel.valor }}`
- [x] O bloco pendente **não** exibe `R$ 0,00` e **não** omite o item
- [x] `plano.html` inclui o template no mesmo ponto em que inclui `pendencias.html`
- [x] **Nenhum texto definitivo ao aluno é inventado.** O ponto de encaixe do texto traz marcação explícita de pendência citando `OQ-21` nominalmente, no padrão de `PEND-01` — quem ler o arquivo entende que o conteúdo é insumo externo, não esquecimento
- [x] Uma linha em `## Requisitos sem cobertura`/nota de rodapé registra `RF-43` como **cobertura parcial declarada**: comportamento e encaixe entregues, redação pendente de `OQ-21`

**Status:** `[x] concluída`

**Nota de implementação.** `report/templates/plano/reserva_mobilizavel.html`
(arquivo novo) com a condicional sobre
`reserva_mobilizavel.pendente_de_decisao`: um bloco para o estado pendente,
outro exibindo `{{ reserva_mobilizavel.valor }}`. Incluído por `plano.html`
no **mesmo ponto** que `pendencias.html` — logo após ele, sob a mesma guarda
`is defined`, fora do `if`/`elif` de `cenario` —, pela mesma razão: "quanto
da reserva o aluno decidiu colocar em análise" é condição do caso, não de
qual bloco principal aparece.

**A REDAÇÃO NÃO FOI INVENTADA, e o encaixe está marcado em dois níveis.** O
cabeçalho do arquivo traz um bloco emoldurado nomeando `OQ-21` como
**ABERTA**, citando `RF-43` (*"esta spec fixa o comportamento, não o texto"*),
separando o que está entregue (estrutura condicional + comportamento
testável) do que falta (só a redação), instruindo o que fazer quando `OQ-21`
for respondida e registrando o precedente de `PEND-01`
(`app/consentimento/registro.py`). No HTML renderizado, o parágrafo pendente
carrega `data-pendencia-redacao="OQ-21"` — a pendência é rastreável **na
própria saída**, não só no fonte, e é por esse atributo (nunca pelo texto)
que `T-117` ancora a asserção de encaixe.

O texto provisório que ocupa o ponto de encaixe existe **apenas** para que o
estado seja visível e testável (o critério proíbe omitir o item), está
marcado como PROVISÓRIO no comentário imediatamente acima e não afirma
nenhum valor: diz que a decisão está em aberto e será retomada. Substituí-lo
pela redação de `OQ-21` **não quebra nenhum teste** — provado, não suposto:
nenhuma asserção de `T-117` lê esse texto.

`RF-43` registrado como **cobertura parcial declarada** em `## Requisitos sem
cobertura` (linha já existente, agora ampliada): comportamento e encaixe
entregues, com o nome do atributo a substituir e a garantia de que nenhum
outro arquivo precisa mudar; redação pendente de `OQ-21`.

Acessibilidade preservada (`AC-19`/e2e): `<h2>` sob o `<h1>` do plano — sem
pular nível, mesma estrutura de `pendencias.html` —, nenhum `style`/`color`
inline, nenhum campo de formulário, nenhum `tabindex`, nenhuma largura fixa.
`pytest -q tests/app_aluno/e2e/test_acessibilidade_plano.py tests/app_aluno/
test_pdf.py tests/app_aluno/test_rotas_plano.py tests/app_aluno/test_plano.py
tests/app_aluno/test_plano_ec07_ec08_ec09.py` → `41 passed, 2 skipped`.

---

### `T-117` — Testar a exibição de `RESERVA_MOBILIZAVEL` desconhecida sem depender da redação

- **Tipo:** `Test`
- **Dependências:** `T-116`
- **Rastreia:** `AC-70`, `EC-18`, `RF-43`
- **Arquivos:** `tests/app_aluno/test_plano.py` ou arquivo dedicado em `tests/app_aluno/` (a critério de quem implementa, seguindo a organização já existente dos testes de `report/`)

**Descrição**

Três asserções que **não dependem da redação de `OQ-21`**, mais o ramo com
valor. É exatamente o recorte que torna `RF-43` testável hoje, com a redação
ainda aberta.

**Critérios de aceite**

- [x] Dado um snapshot com `RESERVA_MOBILIZAVEL is DESCONHECIDO`, o HTML renderizado **não contém** `R$ 0,00` no bloco da reserva
- [x] Dado o mesmo snapshot, o item **não é omitido**: o bloco de reserva aparece na saída
- [x] Nenhum caminho de exibição levanta exceção por encontrar `DESCONHECIDO`
- [x] Dado um snapshot com `RESERVA_MOBILIZAVEL` como `Decimal`, o HTML **exibe o valor**
- [x] Nenhuma asserção do teste depende do texto em português do estado pendente — trocar a redação quando `OQ-21` for respondida **não** quebra nenhum destes testes
- [x] Cada teste cita `AC-70`/`EC-18` no nome ou na docstring

**Status:** `[x] concluída`

**Nota de implementação.** Arquivo dedicado
`tests/app_aluno/test_plano_reserva_mobilizavel.py` — **5 testes**, seguindo
a organização por fatia que `test_plano_ec07_ec08_ec09.py` já usa para
`report/` (e evitando editar arquivos em uso por outros agentes desta
rodada).

Os dois snapshots vêm do **motor REAL** (`calcular_plano` sobre
`FonteParametrosArquivo().carregar("1.0.1")`, os 45 parâmetros lidos de
`parameters/`), no mesmo padrão de `T-114` — nenhum `Diagnostico` fabricado à
mão: o valor precisa chegar à exibição pelo mesmo caminho de produção, senão
o teste provaria o dublê. `TALVEZ` é deliberado no caso desconhecido: com
`NAO` a Regra 1 da §13.1 zeraria antes de a Regra 3 ser alcançada e o teste
passaria pelo motivo errado. A renderização passa por
`report/pdf.py::renderizar_html_do_plano`, a única função de renderização
compartilhada por tela e PDF — nunca um `Environment` Jinja2 montado no
teste, que poderia divergir do que o aluno vê.

**Por que o recorte do bloco, e não o documento inteiro.** `_bloco_da_reserva`
extrai a `<section>` pelo heading estrutural (`AC-70` fala do *bloco* da
reserva). Buscar `R$ 0,00` no documento todo ora falharia por um zero legítimo
de outro campo, ora esconderia o bug quando os valores coincidissem. A âncora
é o heading, **nunca** a redação de `OQ-21`.

**Independência de `OQ-21`, verificada e não suposta.** As asserções são
estruturais: ausência de zero (regex tolerante a `R$ 0,00`/`R$0,00`, mais
`0,00`/`0.00` crus), presença de corpo além do heading, ausência de exceção,
presença do `valor` no ramo conhecido, e desigualdade entre os dois blocos.
A única asserção que cita `OQ-21` lê o **atributo** `data-pendencia-redacao`,
não o texto. Nenhuma asserção lê a frase provisória — trocá-la pela redação
do especialista não quebra nada.

**Comprovado por mutação (4 mutantes, todos mortos).** Sem esse passo,
"verde" só provaria que os testes rodam:

| Mutante | Resultado |
| --- | --- |
| `DESCONHECIDO` → `pendente_de_decisao=False, valor="0.00"` (a conversão que a §13.1 proíbe) | **3 failed** |
| Bloco pendente esvaziado no template (item omitido) | **1 failed** |
| `{% include %}` removido de `plano.html` | **5 failed** |
| Ramo desconhecido roteado por `_formatar_valor_de_apoio` (vazamento de `"Desconhecido.DESCONHECIDO"`) | **2 failed** |

O segundo mutante expôs uma fraqueza real na primeira versão do teste: com o
`<h2>` sobrevivendo ao esvaziamento, a asserção de "não omitido" só era pega
pelo marcador `OQ-21`. A asserção foi **corrigida** para descontar o heading
antes de exigir conteúdo — assim "bloco presente mas mudo" não passa por
"item não omitido" por conta própria. Originais restaurados e conferidos por
`diff` após cada mutação.

`pytest -q tests/app_aluno/test_plano_reserva_mobilizavel.py` → `5 passed`.
`ruff check .` → `All checks passed!`; `mypy` → `Success: no issues found in
278 source files`. Suíte inteira → `1416 passed, 75 skipped`, **zero
falhas**.

*Nota de sequenciamento honesta:* durante a implementação desta cadeia a
suíte acusava `9 failed`, todas de `T-119A` (premissa desatualizada sobre
`AcaoRequerida`) e de outro agente. Foram medidas no baseline (`822 passed,
9 failed` em `tests/app_aluno/`) e continuaram idênticas em número e
identidade após esta cadeia (`857 passed, 9 failed`) — nenhuma introduzida
aqui. O agente de `T-119A` as resolveu antes do fechamento, e a medição final
acima é a do repositório já com aquele trabalho integrado. Da mesma forma, 2
erros transitórios de `mypy` em `tests/app_aluno/estatica/` (arquivos de
`T-118`, `registro.VARIAVEL_GRAVADA` como `str | None`) apareceram e foram
corrigidos por aquele agente; nenhum arquivo desta cadeia teve erro de tipo
em momento algum (`mypy report/plano.py report/pdf.py
tests/app_aluno/test_plano_reserva_mobilizavel.py` → `Success` isolado).

---

### `T-118` — Criar o teste estático que audita `app/` contra derivação patrimonial e uso de `valores_do_escopo`

- **Tipo:** `Test`
- **Dependências:** `T-111`
- **Rastreia:** `RF-44`, `AC-61`, `AC-71`
- **Arquivos:** `tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py` (**arquivo novo**), varredura por `ast` sobre `app/`

**Descrição**

**O lint de `motor-calculo` (`tests/estatica/
test_sem_derivacao_de_classificacao_mobilizacao.py`) só varre `engine/`.**
Derivar `CLASSIFICACAO_MOBILIZACAO` em `app/` passaria naquele lint e ainda
assim violaria a Lei nº 3 e `sdd.config.md` §6 — **achar o ponto cego da regra
não é cumpri-la**. Este teste fecha o ponto cego **por decisão**, com varredura
própria sobre `app/`. Cobre também `AC-71`: a fatia 2A **não** depende de
`valores_do_escopo`, que ignora o parâmetro `escopo`
(`collection/respostas.py:114-128`, `OQ-24`, **aberta**) e causaria dupla
contagem ao ler itens — problema de 2B/2C, não desta fatia.

**Critérios de aceite**

- [x] O teste varre `app/` por `ast` (stdlib), no padrão dos estáticos já existentes em `tests/app_aluno/estatica/`
- [x] Recusa **(a)** qualquer função de `app/` com `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno
- [x] Recusa **(b)** literal de qualquer dos quatro membros daquele domínio atribuído a um item
- [x] Recusa **(c)** soma envolvendo `VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO` ou `CUSTOS_ESTIMADOS_DESMOBILIZACAO`
- [x] Recusa **(d)** chamada a `valores_do_escopo` cujo argumento de variável seja uma variável do Bloco 4 (`AC-71`)
- [x] A docstring do módulo registra **por que este teste existe**: o lint de `motor-calculo` só varre `engine/`, e a proibição de `AC-67` daquele slug vale aqui **por decisão**, não por alcance de ferramenta
- [x] A docstring registra `OQ-24` como **aberta** e explica que `AC-71` torna a **não-dependência** da fatia 2A verificável, em vez de presumida
- [x] O teste passa sobre o `app/` produzido por `T-110`/`T-111`
- [x] O teste **falha** se alguém acrescentar, em `app/`, qualquer uma das quatro construções recusadas — verificado por um caso negativo controlado

**Status:** `[x] concluída`

**Nota de implementação.** `tests/app_aluno/estatica/
test_sem_patrimonio_derivado_em_app.py` (**arquivo novo**, 30 testes, todos
passando). Quatro detectores independentes, um por construção recusada, cada
um com função própria de detecção que os testes de prova negativa alimentam
diretamente.

**Onde este teste difere do lint que ele estende.**
`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`
(`motor-calculo`, `AC-67`) tem `RAIZ_ENGINE` fixo e declara na própria
docstring que não inspeciona `app/`. Este teste varre `app/**/*.py` e
acrescenta três construções que aquele não procura — (b), (c) e (d). A
docstring do módulo registra que a proibição vale aqui **por decisão**
(`sdd.config.md` §6), não por alcance de ferramenta, e que
`motor-calculo:OQ-26` continua **aberta**.

**Nada é transcrito à mão — os dois conjuntos vigiados são DADO.** Os quatro
membros do domínio vêm do próprio `engine.tipos.CLASSIFICACAO_MOBILIZACAO`
(iteração sobre o enum); as variáveis do Bloco 4 de (d) vêm de
`collection.carga.carregar_registros()` filtrando `bloco == 4` — 49 registros,
guardando a `VARIAVEL_GRAVADA` inteira e seu primeiro token (quatro delas são
strings compostas, como `"VALOR_IMOVEL (= VALOR_ESTIMADO_ATIVO)"`). Uma
variável nova no `bloco-04.yaml` passa a ser vigiada sem editar o teste.
`test_variaveis_do_bloco_4_vem_do_registro_real` ancora essa premissa: se o
registro deixasse de declarar as três variáveis que `OQ-24` cita, (d) estaria
vigiando conjunto vazio e passaria vácuo.

**Prova negativa — 4 de 4 detectores, mais duas contraprovas de fronteira.**
(a) 9 casos: derivação completa + 7 formas de anotação de retorno
parametrizadas (direta, qualificada, união, `Optional`, tupla, dict, string
adiada) + `async def`. (b) 6 casos: os 4 membros parametrizados (inclusive
`NAO_MOBILIZAR`, o candidato a ser escrito "porque é neutro") + argumento
nomeado em construção de `ItemAtivo` + literal de string. (c) 4 casos: as 3
variáveis patrimoniais parametrizadas + `+=` e `sum(...)`. (d) 5 casos: 3
variáveis do Bloco 4 parametrizadas + `variavel=` nomeado + constante
intermediária. As contraprovas fixam a fronteira nos dois pontos em que um
detector zeloso demais quebraria código legítimo: leitura simples de
`VALOR_ESTIMADO_ATIVO` (que `RF-44` autoriza — "resposta lida, convertida e
tipada") não é reportada por (c), e `valores_do_escopo` sobre variável do
**Bloco 3** não é reportada por (d) — `_renda_recorrente_adicional_total` e
`_despesas_operacionais_atuais` usam esse método hoje, legitimamente, e
reprová-los quebraria `T-103` sem regra violada.

**Caso negativo controlado, sobre `app/` de verdade.** Um arquivo com as
quatro construções foi escrito em `app/`, a suíte rodou e as **quatro
varreduras de diretório** falharam nomeando arquivo e linha; o arquivo foi
removido e as 30 voltaram a passar. Isso é o que distingue "não há violação"
de "não sei detectar violação": sem ele, os quatro testes de varredura
passariam igualmente bem com o detector quebrado, já que hoje varrem um
conjunto em que a resposta correta é "nenhuma".

**Resultado sobre o `app/` de `T-110`/`T-111`: zero violações nas quatro.**
Em particular (d): `app/` chama `valores_do_escopo` em dois lugares
(`app/montagem/estado.py:1059` e `:1102`), ambos com variável do **Bloco 3**
(`RENDA_RECORRENTE_ADICIONAL`, `VALOR_DESPESA`) — a fatia 2A lê os cinco
campos escalares do Bloco 4 por `respostas.valor(...)` e não depende de
`OQ-24`. A não-dependência deixou de ser prosa do plano e virou asserção.

---

### `T-119` — Auditar `app/montagem/estado.py` contra rótulo em português de `B4.02`/`B4.03`

- **Tipo:** `Test`
- **Dependências:** `T-110`
- **Rastreia:** `AC-53`, `AC-37`, `RF-36`
- **Arquivos:** `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py` (denylist estendida) **ou** bloco novo em `tests/app_aluno/estatica/`; auditoria sobre `app/montagem/estado.py`

**Descrição**

`AC-53` tem duas metades verificáveis: que a leitura dos dois enums **passa por
`_membro_do_enum`**, e que **nenhum rótulo em português** de `B4.02`/`B4.03`
aparece escrito no arquivo. A segunda é a que mantém `AC-37` verde depois desta
fatia — os `valor_interno` batem com os `name` dos enums justamente para que
nenhuma linha de tradução exista.

**Critérios de aceite**

- [x] O teste assere que a resolução de `RESERVA_EXISTE` e de `DISPOSICAO_USO_RESERVA` em `app/montagem/estado.py` passa por `_membro_do_enum` — nenhuma cadeia de `if` sobre `valor_interno`, nenhum dicionário de tradução
- [x] O teste recusa a presença, no arquivo, dos rótulos em português das duas perguntas: `"Sim."`, `"Não."`, `"Talvez. Quero ver os números antes."`, `"Não. Prefiro preservar integralmente minha reserva."`, `"Sim, aceitaria avaliar o uso de uma parte."` e os demais de `bloco-04.yaml:52-57` e `:127-133`
- [x] `tests/app_aluno/estatica/test_sem_conteudo_de_questionario_no_codigo.py` (`AC-37`) continua passando depois da fatia
- [x] O teste cita `AC-53` e `AC-37` no nome ou na docstring

**Status:** `[x] concluída`

**Nota de implementação.** `tests/app_aluno/estatica/
test_sem_rotulo_em_portugues_do_bloco_4.py` (**arquivo novo**, 14 testes,
todos passando) — bloco novo em `tests/app_aluno/estatica/`, a segunda opção
que a tarefa oferecia. Não estender a denylist de
`test_sem_conteudo_de_questionario_no_codigo.py` foi decisão: aquele teste
opera por **limiar de tamanho** sobre `app/`+`collection/`+`report/`
inteiros; este é **específico e literal**, nomeia a pergunta e o rótulo exato
na mensagem de falha e audita **um** arquivo. Misturá-los tornaria a mensagem
de falha de `AC-37` ambígua. Os dois são complementares e ambos passam.

**As duas metades de `AC-53`, com detectores separados.** Metade 1 (a
resolução passa por `_membro_do_enum`) é auditada por **AST** — é afirmação
sobre estrutura: `_chama_mecanismo_generico` confirma a chamada,
`_comparacoes_com_string` recusa qualquer comparação contra literal de string
no corpo (a forma de uma cadeia de tradução, tanto sobre `valor_interno`
quanto sobre rótulo) e `_dicionarios_literais` recusa a tabela de tradução —
a outra sintaxe da mesma violação, que uma auditoria só de `if` deixaria
passar. As três rodam parametrizadas sobre `_reserva_existe` e
`_disposicao_uso_reserva`. Metade 2 (nenhum rótulo em português no arquivo) é
auditada sobre o **TEXTO**, não sobre a AST, deliberadamente: um rótulo
copiado para um **comentário** não aparece na AST, e comentário "explicativo"
ao tratar `EC-16`/`EC-17` é justamente onde ele apareceria.

**Os rótulos vêm do registro real, nunca transcritos para o teste.** Escrever
`"Talvez. Quero ver os números antes."` como literal neste arquivo
reintroduziria, dentro de `tests/`, exatamente o que `AC-37` proíbe em `app/`
— e criaria uma segunda cópia que divergiria do YAML na primeira edição de
redação. `_rotulos_de(ID)` lê `opcoes[].rotulo` de `B4.02` (3 rótulos) e
`B4.03` (4 rótulos) via `collection.carga` em tempo de execução.

**A premissa que torna a ausência de tradução possível também é testada.**
`test_valor_interno_bate_com_o_name_do_enum` verifica que os `valor_interno`
do registro são subconjunto dos `name` dos membros de `RESERVA_EXISTE`/
`DISPOSICAO_USO_RESERVA` — é *por isso* que `_membro_do_enum` resolve direto.
Se essa correspondência se quebrar, este teste falha **antes**, nomeando a
divergência, em vez de a linha de tradução aparecer como "solução".

**Prova negativa — as duas metades.** Metade 2: rótulo real de `B4.03` numa
cadeia de `if` (pego, linha 2) e rótulo de `B4.02` num **comentário** (pego,
linha 1 — o caso que só a busca textual pega). Metade 1: cadeia de `if` sobre
`valor_interno` (pega, com `{"SIM", "INFORMAL"}` nomeados) e dicionário de
tradução (pego), mais a contraprova de que a função REAL não é pega por
nenhum dos dois; e uma função que resolve `RESERVA_EXISTE[valor]` inline,
sem o mecanismo genérico, é reportada — o teste não passa só por a função
existir.

**Caso negativo controlado, sobre `app/montagem/estado.py` de verdade.** Um
`if valor == "Sim.": return RESERVA_EXISTE.SIM` foi injetado em
`_reserva_existe`; **três** testes falharam de uma vez — a metade 1
(`_comparacoes_com_string` reportou `(1273, 'Sim.')`) e a metade 2 (rótulo de
`B4.02` no arquivo), confirmando que as duas caem juntas como a descrição da
tarefa previa. O arquivo foi restaurado e verificado **byte a byte idêntico**
ao original por `diff` (nenhuma linha de `app/` foi alterada por esta
tarefa — ela é auditoria, não correção: `app/montagem/estado.py` já estava
conforme, o que faltava era o portão).

**Resultado: conformidade confirmada por auditoria, não por leitura.** As
duas funções terminam em `return _membro_do_enum(...)`, nenhuma comparação
contra texto, nenhum dicionário, nenhum dos 7 rótulos em português presente
no arquivo. `test_sem_conteudo_de_questionario_no_codigo.py` (`AC-37`)
continua passando.

---

### `T-119A` — Atualizar os testes que assumem `AcaoRequerida` sem `ACAO_ID`/`TIPO_ACAO`

- **Tipo:** `Test`
- **Dependências:** `T-111`
- **Rastreia:** `RF-42`, `AC-66`
- **Arquivos:** `tests/app_aluno/test_acoes.py`, `tests/app_aluno/test_acompanhamento_acao_id.py`, `tests/app_aluno/test_ordem_acoes_dependencia_externa.py` (**terceiro arquivo, confirmado na medição** — os cinco `xfail(strict=True)` de `T-90` viraram `XPASS(strict)` pela mesma causa; ver nota de fechamento)

**Descrição**

> **Achado durante `T-111`, registrado como tarefa em vez de corrigido em silêncio** (`sdd.config.md` §4). Não é regressão desta rodada — é uma premissa que **deixou de valer** porque a dependência externa chegou.

Dez testes destes dois arquivos foram escritos quando `engine.gates.AcaoRequerida` **não** publicava `ACAO_ID` nem `TIPO_ACAO`, e afirmam isso na própria mensagem: *"se este assert falhar, a dependência externa chegou e `T-84` precisa ser revisitada"*. A Rodada 2 do slug `motor-calculo` entregou exatamente esses campos — verificado em execução:

```
AcaoRequerida.__dataclass_fields__ →
  ['ACAO_ID', 'DIVIDA_ID', 'TIPO_ACAO', 'descricao',
   'gate_origem', 'prioridade_excepcional', 'CAMPO_PENDENTE']
```

Ou seja: **os testes acertaram ao falhar.** Eles são a sentinela que avisou. Antes de `T-111` a falha ficava mascarada — os testes morriam antes na montagem do estado, sem alcançar a asserção.

O trabalho é atualizar a premissa: onde hoje se afirma ausência, passar a verificar o **comportamento real** com os campos presentes, seguindo o que o próprio texto dos testes manda revisitar. **Não** apagar os testes nem afrouxar a asserção para "passar".

**Critérios de aceite**

- [x] Os dez testes deixam de afirmar que `ACAO_ID`/`TIPO_ACAO` estão ausentes e passam a exercitar o comportamento com os campos presentes
- [x] Nenhum teste é removido, pulado (`skip`/`xfail`) nem tem asserção enfraquecida só para ficar verde — se algum não fizer mais sentido, isso é reportado com justificativa, não resolvido por exclusão
- [x] As mensagens que citam "a dependência externa chegou" são reescritas: a dependência **chegou**, e o texto não pode seguir descrevendo um estado que não existe mais
- [x] `pytest -q tests/app_aluno/test_acoes.py tests/app_aluno/test_acompanhamento_acao_id.py` passa
- [x] Nenhum arquivo de `engine/` é editado — o contrato do motor está correto; quem estava desatualizado era o teste

**Status:** `[x] concluída`

**Nota de implementação.** As **9 falhas** de `tests/app_aluno/` caíram a
**zero**. Elas estavam em **três** arquivos, não dois — a descrição da tarefa
listava `test_acoes.py` e `test_acompanhamento_acao_id.py`; a medição
confirmou um terceiro, `tests/app_aluno/test_ordem_acoes_dependencia_
externa.py` (`T-90`), com falha de natureza distinta e registrada abaixo.

**Confirmação do contrato entregue.** `AcaoRequerida.__dataclass_fields__` →
`['ACAO_ID', 'DIVIDA_ID', 'TIPO_ACAO', 'descricao', 'gate_origem',
'prioridade_excepcional', 'CAMPO_PENDENTE']`. Uma ação real do cenário de
prova: `ACAO_ID='D-CASO-COMPLETO:RENEGOCIACAO'`, `TIPO_ACAO='RENEGOCIACAO'`,
`gate_origem=2` — `ACAO_ID` de fato **distinto** de `DIVIDA_ID`, o que só
agora permite provar no caminho de sucesso o que `T-83` sempre quis.

**Os testes acertaram ao falhar, e cada tipo de falha teve tratamento
próprio.**

*Quatro falhas de `assert not hasattr(...)`* (`test_acoes.py` ×2,
`test_acompanhamento_acao_id.py` ×2). Reescritos para exercitar o
comportamento real, virando asserções **mais fortes**, não mais fracas: antes
provavam que a função não inventava um valor; agora provam que ela lê o valor
**certo**. `acao_id_de` devolve `acao.ACAO_ID` e — o ponto de `T-83` —
`acao_id != acao_real.DIVIDA_ID`, com a ação real tendo os dois campos
preenchidos. `tipo_acao_de` devolve `acao.TIPO_ACAO`, e o valor pertence ao
domínio que o **registro** declara (comparação contra os valores extraídos de
`condicao_exibicao`, nunca contra literal — a disciplina de `OQ-13` foi
mantida mesmo com a questão respondida). `perguntas_do_bloco_11` sobre a ação
real resolve **exatamente uma** pergunta de resultado, e a esperada é
determinada pelo próprio `TIPO_ACAO` da ação via registro, não por um `ID`
fixado à mão: o circuito completo motor → registro, que `T-84` só pôde provar
em duas metades separadas.

*Cinco falhas de `XPASS(strict)`* (`test_ordem_acoes_dependencia_externa.py`,
`AC-45`..`AC-49`). Estas **não** são um teste desatualizado — são o mecanismo
de `T-90` funcionando exatamente como projetado. Aquele arquivo escreveu as
asserções REAIS dos cinco critérios sob `xfail(strict=True)`, e o `strict`
existia precisamente para que, no dia em que passassem de verdade, o "passar
inesperado" fosse reportado como **falha**, forçando a remoção do marcador em
vez de deixá-lo acumular. As três mudanças previstas em
`specs/app-aluno.spec.md` §7 chegaram (`ACAO_ID`+`TIPO_ACAO`; Gate 1 emitindo
ação de informação; ação de economia fora dos gates) — confirmado rodando o
arquivo com `--runxfail`: **5 passed**, as asserções passam por mérito
próprio. O tratamento foi remover os cinco marcadores e **nada mais**: os
corpos dos cinco testes estão intocados, linha por linha. `AC-45`..`AC-49`
saem de "esperado falhar" para verdes de verdade, que é o ganho real desta
correção.

**Nenhum teste removido, pulado ou enfraquecido — e dois foram
ACRESCENTADOS.** `ErroAcaoIdAusenteDoMotor` e `ErroTipoAcaoAusenteDoMotor`
nunca foram marcas de "campo não entregue": são as fronteiras ruidosas contra
um objeto que não cumpre o contrato (nunca cair de volta em `DIVIDA_ID`,
nunca escolher uma pergunta por padrão). Como nenhuma `AcaoRequerida` real
produz mais essa situação, apenas reescrever os testes antigos teria deixado
as duas exceções **sem cobertura nenhuma** — resolver por exclusão pela porta
dos fundos. Em vez disso, `test_erro_de_acao_id_ausente_continua_nomeando_a_
fronteira` e `test_erro_de_tipo_acao_ausente_continua_nomeando_a_fronteira`
exercitam cada uma com um objeto construído no teste, verificando que a
mensagem segue nomeando campo e origem (`T-83`/`OQ-10`, `T-84`/`OQ-13`). Os
objetos de teste `_AcaoRequeridaComAcaoId`/`_AcaoRequeridaComTipoAcao` também
permanecem: cobrem casos que o motor não emite neste cenário — ação **sem**
`DIVIDA_ID` (`OQ-15`), `ACAO_ID` de tipo inesperado, `TIPO_ACAO` fora do
domínio do registro. Suas docstrings foram reescritas: deixaram de justificar
sua existência por "o tipo real não tem o campo" e passaram a justificá-la
pelo que de fato cobrem.

**Texto desatualizado removido em todos os pontos.** As frases *"se este
assert falhar, a dependência externa chegou e `T-84`/`T-83` precisa ser
revisitada"* saíram junto com a premissa que descreviam. As três docstrings
de módulo registram que a dependência **chegou**, o que mudou e por quê; os
cinco comentários de seção de `test_ordem_acoes_dependencia_externa.py`
passaram de "Depende da mudança N" para "Mudança N — ENTREGUE". O import de
`pytest` daquele arquivo, órfão depois da remoção dos marcadores, foi
removido (`ruff`).

**Nenhum arquivo de `engine/` editado** — e nenhum de `app/`, `report/` ou
`collection/`. Esta tarefa tocou exclusivamente os três arquivos de `tests/
app_aluno/`. O contrato do motor foi revisado e aprovado; quem estava
desatualizado era o teste.

**Verificação.** `pytest -q tests/app_aluno/test_acoes.py tests/app_aluno/
test_acompanhamento_acao_id.py` → **17 passed**. Os três arquivos juntos →
**22 passed**. `tests/app_aluno/` inteiro → **882 passed, 66 skipped, 0
failed** (era `9 failed`). Suíte completa → **1416 passed, 75 skipped, 0
failed**.

---

### `T-120` — Fechar a fatia 2A: rodar os comandos de verificação e registrar o portão de `AC-66`

- **Tipo:** `Infra`
- **Dependências:** `T-108`, `T-109`, `T-110`, `T-111`, `T-112`, `T-113`, `T-114`, `T-115`, `T-116`, `T-117`, `T-118`, `T-119`
- **Rastreia:** `RF-42`, `AC-66`, `AC-64`, `AC-65`, `sdd.config.md` §2, §8
- **Arquivos:** nenhum de produção — execução dos comandos da seção 2 do `sdd.config.md` e a nota de fechamento neste backlog

**Descrição**

O portão declarado de `RF-42`/`AC-66`: `build` (`mypy --strict`) de **1 erro
para zero**, `tests/app_aluno/` de **~129 falhas de causa raiz única para
zero**. Nenhuma tarefa da rodada é declarada concluída sem que esta passe com
saída real reportada (`sdd.config.md` §5 do CLAUDE.md: reportar falhas com a
saída real, nunca declarar concluído sem rodar).

**Critérios de aceite**

- [x] `lint` — `ruff check .` → `All checks passed!`
- [x] `build` — `mypy --strict` sobre as seis pastas → zero erro; especificamente, o erro de `app/montagem/estado.py:1326` (construtor de 13 campos) não aparece mais (`AC-66`)
- [x] `test` — `pytest -q` completo passa; `tests/app_aluno/` passa **integralmente**, sem nenhuma das ~129 falhas de causa raiz única — **com divergência de número registrada abaixo**: o número medido era `126 failed, 46 errors`, não `~129 failed`, e a causa raiz era **tripla**, não única
- [x] Os quatro estáticos de não-regressão continuam verdes: `test_fronteira_import_engine.py` (`AC-64`), `test_engine_congelado.py` (`AC-65`), `test_fronteira_decimal_unica.py`, `test_sem_relogio_em_montagem.py`
- [x] `T-77`, `T-78` e `T-79` continuam `[ ] pendente` e **não** foram tocadas, marcadas nem destravadas por esta rodada (`motor-calculo:OQ-29` segue aberta)
- [x] A saída real de cada comando é reportada na nota de fechamento — números, não adjetivos
- [x] `RF-43` é registrado como **cobertura parcial declarada** (redação pendente de `OQ-21`), no mesmo formato que a Rodada 1 usou para `RF-33`/`RF-26`

**Status:** `[x] concluída`

**Nota de fechamento — Rodada 2, fatia 2A.**

**Os três comandos do `sdd.config.md` §2, saída literal (2026-09-07).**

| Comando | Invocação | Saída real |
| ------- | --------- | ---------- |
| `lint` | `ruff check .` | `All checks passed!` |
| `build` | `mypy engine persistencia collection app report tests` | `Success: no issues found in 278 source files` |
| `test` | `pytest -q` | `1416 passed, 75 skipped, 1 warning in 72.81s` — **0 failed, 0 errors** |
| `test` (recorte) | `pytest -q tests/app_aluno/` | `882 passed, 66 skipped, 1 warning in 65.76s` — **0 failed, 0 errors** |

`install` não foi reexecutado (ambiente já provisionado); `e2e` e `run` são
`—` no config e por definição pulados. O único `warning` é
`DeprecationWarning` de `starlette/testclient.py:53` sobre
`anyio.abc.BlockingPortal`, de dependência de terceiro, anterior a esta rodada
e sem relação com ela. Os 66 `skipped` de `tests/app_aluno/` são os de sempre —
`integracao/` que exige Postgres e `test_pdf.py` — e o número é **idêntico** ao
de antes da fatia: nenhum teste foi silenciado para fechar o portão.

**`AC-66`, o portão de `build`, verificado no ponto específico.** O erro que
travava `mypy` desde a Rodada 3 do `motor-calculo` — o construtor de
`EstadoFinanceiro` em `app/montagem/estado.py` passando 13 campos para um tipo
que exige 21 — **não aparece mais**. Foi `T-111` quem o corrigiu, construindo
os 21 campos. A coordenada do enunciado (`:1326`) mudou para `:1571` no
caminho, porque `T-111` acrescentou a docstring dos oito campos novos; é o
mesmo construtor, já registrado na nota de `T-112`. `build` saiu de **1 erro
para zero**, como o portão prometia.

**Divergência entre o enunciado e a realidade medida — registrada, não
acomodada.** O enunciado desta tarefa, do plano (`R2.11`) e da spec (`RF-42`,
`AC-66`) fala em *"~129 falhas de causa raiz única"*. A varredura da rodada
mediu outra coisa, e o número real ficou registrado tarefa a tarefa:

1. **O número era `126 failed, 46 errors`**, não `~129 failed`. A contagem
   original somava falhas e erros de forma imprecisa e ignorava que `46` deles
   eram `errors` de coleta/fixture, não `failed`.
2. **A causa raiz não era única — eram três**, e só a primeira era o que o
   plano previa:
   - *Fixture sem Bloco 4* (`T-112`): responde por **46 errors + 83 failed**.
     Comprovada por medição direta antes da correção (injeção em memória por
     plugin descartável de `pytest`): `125 failed, 46 errors` → `42 failed,
     0 errors`.
   - *Construtores locais de `RespostasCaso`* (`T-112`, itens 2 e 3): os
     **32** de `test_montagem_estado_financeiro.py` mais o e2e
     `test_ciclo_completo.py`, que montavam a própria base de respostas em vez
     de usar a fixture compartilhada.
   - *Premissa de dependência externa vencida* (`T-119A`): as **9** residuais
     — quatro `assert not hasattr(AcaoRequerida, "TIPO_ACAO")` e cinco
     `XPASS(strict)` — que **não** eram desta fatia. `engine.gates.
     AcaoRequerida` já publicava `ACAO_ID` e `TIPO_ACAO`: entrega da Rodada 3
     do `motor-calculo`, que os testes deste slug ainda negavam. Antes da
     fatia essas 9 estavam **mascaradas** (os testes morriam mais cedo, na
     montagem, e nem alcançavam a asserção), e por isso não constavam da
     contagem original.
3. **Parte do que o plano previa já estava resolvido** pela Rodada 3 do
   `motor-calculo` — foi ela quem trouxe `ACAO_ID`/`TIPO_ACAO` e os oito
   campos novos de `EstadoFinanceiro`. O trabalho da fatia foi reconciliar
   este slug com essa entrega, não construí-la.

Nada disso invalida `AC-66`: o critério pede a suíte de `tests/app_aluno/`
passando **integralmente**, e ela passa — `882 passed, 66 skipped, 0 failed`.
O que se corrige aqui é o **número**, não o resultado. Quem for atualizar a
spec um dia leia `~129 falhas de causa raiz única` como `126 failed + 46
errors, três causas raiz`.

**Os quatro estáticos de não-regressão, medidos um a um.**

| Estático | Resultado | Guarda |
| -------- | --------- | ------ |
| `estatica/test_fronteira_import_engine.py` | `10 passed` | `AC-64`/`AC-41` — allowlist `+2` |
| `estatica/test_engine_congelado.py` | `4 passed` | `AC-65` — hashes de `engine/` |
| `estatica/test_fronteira_decimal_unica.py` | `10 passed` | `RF-13` — sem `Decimal(...)` literal novo |
| `estatica/test_sem_relogio_em_montagem.py` | `6 passed` | sem leitura de relógio em `app/montagem/` |

Juntos: `30 passed in 0.55s`. Conferido também por leitura que a allowlist de
`NOMES_PERMITIDOS_DE_ENGINE` ganhou **exatamente dois** nomes
(`engine.estado.RESERVA_EXISTE`, `engine.estado.DISPOSICAO_USO_RESERVA`,
`:147-148`) e que os cinco nomes das fatias 2B/2C — `ItemInvestimento`,
`ItemAtivo`, `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO`,
`CERTEZA_RECURSO_EXTRAORDINARIO` — continuam **fora**, com o motivo escrito no
próprio arquivo (`RF-40`).

**`T-77`, `T-78` e `T-79`: confirmado por leitura do arquivo, não de memória.**
Os três `**Status:**` seguem `[ ] pendente` (`:2283`, `:2314`, `:2338`).
Nenhuma tarefa da fatia 2A os tocou, marcou ou destravou. A razão continua
verdadeira e verificada no código: `engine/diagnostico.py:850` ainda emite
`ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)` — placeholder explícito por
`motor-calculo:OQ-29`, **aberta**.

> **Atualização (2026-09-10, fora da fatia 2A).** `motor-calculo:OQ-29` foi
> respondida e implementada por completo (fatia 4C): `engine/diagnostico.py`
> continua produzindo o placeholder dentro de `calcular_diagnostico` (por
> design, não por pendência — ver a nota de `T-77`), mas `engine/motor.py::
> calcular_plano` agora substitui esse placeholder pelo valor REAL antes de
> publicar o `SnapshotOrdem`. `T-77`/`T-78`/`T-79` foram destravadas e
> concluídas fora desta fatia. Este parágrafo é preservado como registro
> fiel do estado em 2026-09-07.

**O que a fatia 2A entregou.** A montagem passou a **ler** reserva e caixa do
Bloco 4: as cinco leituras de `app/montagem/estado.py` (`T-110`) convertem
`RESERVA_EXISTE`, `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA`,
`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` e `DINHEIRO_DISPONIVEL` de resposta
para tipo, sem reproduzir nenhuma das três regras da §13.1. Com isso,
`RESERVA_MOBILIZAVEL` deixou de ser zero fixo e passou a refletir a **resposta
real do aluno**, derivada por `engine/ataque_imediato.py::
derivar_RESERVA_MOBILIZAVEL` — provado por integração com o motor real em
`T-114`. O `build` do projeto voltou a ficar limpo (`T-111`). E a tela mostra
**"pendente de decisão"** quando o aluno respondeu "prefiro decidir depois":
nunca `R$ 0,00`, nunca item omitido (`T-115`/`T-116`/`T-117`).

**O que ficou fora, e por quê — nenhum destes é omissão do backlog.**

- **Investimentos e ativos (fatia 2C).** Bloqueada por `motor-calculo:OQ-26`
  **e** `OQ-27`, ambas do especialista e ambas abertas. **Responder só uma não
  destrava:** são duas decisões distintas e a fatia precisa das duas.
- **Recursos extraordinários (fatia 2B).** Depende de corrigir `B3.05C` e de
  `OQ-24` — o `valores_do_escopo` que ignora o escopo. `T-118` prova por teste
  estático que a fatia 2A **não** depende dessa correção; 2B e 2C dependem.
- **Bloco 10 e `T-77`/`T-78`/`T-79`.** Dependiam de `motor-calculo:OQ-29`,
  aberta à época. **Atualização 2026-09-10:** respondida e implementada; as
  três tarefas foram concluídas fora desta fatia.

**O que o aluno ainda não vê.** O **ataque imediato recomendado**. A fatia
entregou a reserva mobilizável correta, que é a **entrada** do cálculo; o
`ATAQUE_IMEDIATO_RECOMENDADO` que sai continua `dinheiro(0)` enquanto
`motor-calculo:OQ-29` não for respondida. A fatia 2A nunca prometeu o Bloco 10
— e não o entregou.

**`RF-43` — cobertura parcial declarada.** Registrado na seção "Requisitos sem
cobertura" deste backlog, ao lado de `RF-33` e `RF-26` da Rodada 1 e no mesmo
formato: comportamento e ponto de encaixe **entregues**, redação **pendente**
de `OQ-21`, aberta, com o ponto exato a substituir marcado no template por
`data-pendencia-redacao="OQ-21"` (`report/templates/plano/
reserva_mobilizavel.html:68`).

**Nenhum arquivo de produção foi criado ou editado por esta tarefa.** `T-120`
é portão: executa, mede e registra. A única escrita é esta nota e as marcações
de status neste backlog.

---

## Entrega 13 — Rodada 3: o protótipo validado e a máscara de entrada

> **Ordem obrigatória.** `T-122` é portão: sem a emenda dos artefatos, as
> demais tarefas desta entrega produzem código sem spec que o autorize, o que
> a Regra 1 do `CLAUDE.md` proíbe. `T-123` entrega sozinha o maior valor da
> rodada — hoje o aluno cadastra, consente e **não alcança pergunta nenhuma**.

### `T-122` — Emendar spec, plano e backlog para a página única e a máscara

- **Tipo:** `SDD`
- **Dependências:** —
- **Rastreia:** `RF-45`, `RF-46`, `RF-47`, `RF-48`, `RF-49`
- **Arquivos:** `specs/app-aluno.spec.md`, `plans/app-aluno.plan.md`, `tasks/app-aluno.tasks.md`

**Descrição**

O protótipo validado é uma página única, e o §2 do plano recusou SPA por
escrito. A recusa não é revogada: ela é **delimitada** ao que de fato
protegia — avaliar `condicao_exibicao` no cliente. Esta tarefa registra a
distinção nos três artefatos antes de qualquer linha de código.

**Critérios de aceite**

- [x] `RF-45` a `RF-49`, `US-17`/`US-18`, `AC-72` a `AC-79`, `EC-21` a `EC-24`
      e `OQ-26` a `OQ-28` existem na spec, em subseção datada própria
- [x] O §2 do plano registra por que a recusa de SPA continua de pé e o que
      exatamente mudou, com as duas restrições herdadas (progressive
      enhancement e zero dependência nova) explícitas
- [x] Nenhuma dependência nova é declarada em `pyproject.toml`

**Status:** `[x] concluída`

**Nota de implementação.** A emenda é de artefato apenas — nenhum arquivo de
produção foi tocado. Na spec: subseções datadas `Rodada 3 (2026-09-14)` em §2
(`RF-45` a `RF-49`), §4 (`AC-72` a `AC-79`), §6 (`EC-21` a `EC-24`) e §9
(`OQ-26` a `OQ-28`), mais `US-17`/`US-18` na §3 e a linha `Data` do cabeçalho.
No plano: a linha de Jinja2/progressive enhancement na tabela do §2 passou a
apontar para a nova subseção *"Revisão de 2026-09-14 — página única, e por que
a recusa acima continua de pé"*, que delimita a recusa ao SPA **que avalia
`condicao_exibicao` no cliente** e fixa as duas restrições herdadas. A recusa
original **não foi apagada** — continua legível na tabela, com a ressalva ao
lado, porque apagá-la esconderia a decisão de quem ler o plano depois.
`AC-73` é a trava executável dessa delimitação e é entregue por `T-126`.
Verificação após a emenda: `ruff check .` limpo, `pytest -q` →
`1495 passed, 75 skipped` — igual à linha de base, como esperado para uma
mudança que não toca produção.

---

### `T-123` — Criar a rota `GET` de coleta que hoje não existe

- **Tipo:** `UI`
- **Dependências:** `T-122`
- **Rastreia:** `RF-46`, `AC-72`, `AC-74`, `EC-23`, `EC-24`
- **Arquivos:** `app/http/rotas_pergunta.py`, `app/http/aplicacao.py`

**Descrição**

`T-45` implementou `proxima_pergunta_nao_respondida` e `T-43`
`montar_contexto_pergunta`, mas deixou a rota que os costura fora de escopo —
o comentário em `app/http/renderizacao.py:22-32` registra a lacuna. Esta
tarefa a fecha **reusando** as duas funções, sem reimplementar a decisão de
qual pergunta exibir.

**Critérios de aceite**

- [x] `GET /caso/{CASO_ID}/pergunta` devolve a primeira pergunta não
      respondida e exibível
- [x] `GET /caso/{CASO_ID}/pergunta/{ID_PERGUNTA}` devolve uma pergunta
      específica do caso
- [x] O parâmetro se chama `CASO_ID` e declara `exigir_caso_da_sessao("CASO_ID")`
      — `test_mecanismo_isolamento.py` continua passando (`AC-74`)
- [x] `ErroPerguntaNaoExibivel` faz o servidor avançar à próxima exibível,
      nunca devolver a pergunta fechada (`EC-24`)
- [x] Coleta completa devolve estado próprio, nunca `500` (`EC-23`)
- [x] O roteador é registrado em `criar_aplicacao()` — precedente de `T-121`

**Status:** `[x] concluída`

**Nota de implementação.** `app/http/rotas_pergunta.py` reusa
`proxima_pergunta_nao_respondida` (T-45) e `montar_contexto_pergunta` (T-43)
sem reimplementar nenhuma das duas. `_primeira_exibivel` é a costura: pega a
pendência e confirma pelo `montar_contexto_pergunta` que ela é de fato
exibível, porque é ele — e a `avaliar` que ele chama — a autoridade sobre
`condicao_exibicao`, a MESMA usada na gravação.

Três templates novos, todos páginas completas (os de coleta existentes são
fragmentos): `pagina.html` (a casca que nunca existiu, e por cuja ausência
`estilo.css` era código morto — nenhum template o referenciava),
`coleta_completa.html` (`EC-23`) e `pergunta_indisponivel.html`, que devolve
`404` idêntico para "não existe" e "condição falsa" — distinguir os dois
devolveria ao cliente justamente a informação de condicional que `RF-45`
mantém no servidor, mesmo princípio do `404` fundido de `isolamento.py`.

`_itens_por_escopo` é importado de `rotas_coleta` em vez de recopiado: o
helper já existe idêntico em três módulos de rota, e uma quarta cópia seria
a direção errada.

Verificação: `tests/app_aluno/test_rotas_pergunta.py` → 9 passed, incluindo
o caso que roda a auditoria de isolamento real sobre `criar_aplicacao()`.

---

### `T-124` — Variante de resposta para a página única, aditiva ao HTML

- **Tipo:** `UI`
- **Dependências:** `T-123`
- **Rastreia:** `RF-49`, `AC-79`, `EC-21`
- **Arquivos:** `app/http/rotas_coleta.py`

**Descrição**

Ramificar **apenas na montagem da resposta**, por cabeçalho `Accept`. Os sete
passos de `T-42` não são tocados. Precedente já existe em
`app/http/rotas_bloco10.py`, que devolve JSON.

**Critérios de aceite**

- [x] O corpo da requisição continua `form-urlencoded` (`python-multipart`
      permanece ausente, e `SELECAO_MULTIPLA` depende de `valor` repetido)
- [x] Os testes que afirmam sobre `resposta.text` continuam passando
- [x] Com JavaScript desabilitado, a gravação ocorre pela mesma rota (`EC-21`)

**Status:** `[x] concluída`

**Nota de implementação.** A ramificação é por `Accept`, em
`_cliente_prefere_json`, e só entra quando o cliente pede
`application/json` EXPLICITAMENTE. Um `<form>` nativo manda `text/html,...`
e o HTMX manda `*/*` — nenhum dos dois muda de comportamento, que é
precisamente o ponto: a variante é aditiva, e o caminho sem JavaScript é
requisito de acessibilidade, não cortesia.

A assinatura de `responder_pergunta` passou de `-> HTMLResponse` para
`-> Response` (a união dos dois tipos concretos). O `response_class=
HTMLResponse` do decorador permanece: ele só define o default de
documentação; devolver um `Response` explícito o ignora.

`tests/app_aluno/test_resposta_json.py` → 4 passed, incluindo o teste que
prova que o valor gravado é o MESMO `Decimal("1234.56")` nos dois formatos —
a ramificação é de apresentação, nunca de gravação.

---

### `T-125` — Implementar `app/http/estaticos/mascaras.js`

- **Tipo:** `UI`
- **Dependências:** `T-122`
- **Rastreia:** `RF-47`, `RF-48`, `AC-75`, `AC-76`, `AC-77`, `AC-78`, `EC-22`
- **Arquivos:** `app/http/estaticos/mascaras.js`, `report/templates/coleta/pergunta.html`

**Descrição**

Baunilha, sem biblioteca, dirigido por `data-tipo` com os nove `TipoResposta`.
A máscara **formata, nunca corrige**: o que ela emite tem de ser exatamente o
que `app/montagem/conversao.py` aceita, e entrada ambígua segue para o
servidor para ser recusada lá.

**Critérios de aceite**

- [x] `MOEDA` exibe e submete `1.234,56` (`AC-75`)
- [x] `TAXA` submete `4,5`, nunca `0,045`, nunca com `%` — o `%` é sufixo
      visual fora do `<input>` (`AC-76`)
- [x] `DATA` submete ISO; `NUMERO`/`ESCALA_0_10` submetem inteiro
- [x] `"1.2,3"` não é "salvo" pela máscara: chega como digitado e é recusado
      com `400`, sem gravação (`AC-77`)
- [x] Com `nao_sei` marcado a máscara fica inerte (`AC-78`)
- [x] `pergunta.html` continua fragmento, com o widget por tipo que
      `test_renderizacao.py` fixa — `MOEDA`/`TAXA` seguem
      `type="text" inputmode="decimal"`

**Status:** `[x] concluída`

**Nota de implementação.** `app/http/estaticos/mascaras.js`, baunilha, ~150
linhas, dirigido por `data-tipo` — atributo que `pergunta.html` passou a
emitir a partir de `ctx.registro.tipo.value`, de modo que o TIPO vem do
servidor e o cliente nunca o infere do `name` ou do `id`.

A regra que governa o arquivo inteiro: **formata, nunca corrige**. `"1.2,3"`
não é transformado em nada — segue como digitado, o servidor recusa e nada é
gravado. Uma máscara que "consertasse" o ambíguo criaria uma segunda regra
de parsing no cliente, que é exatamente o que o plano §2 evita ao manter a
conversão num lugar só.

A armadilha mais afiada, e como foi tratada: `converter_para_taxa` divide por
100 e `_CARACTERES_ACEITOS` recusa `%`. Então o `%` virou um `<span
class="sufixo-taxa" aria-hidden="true">` IRMÃO do `<input>`, fora do campo —
o aluno vê o símbolo, o servidor recebe `"4,5"`.

`RF-48`/`AC-78`: com `nao_sei` marcado, os campos com `data-tipo` são
esvaziados e desabilitados, para que nada digitado antes seja submetido como
valor.

---

### `T-126` — Auditoria estática: nenhum conteúdo nem condicional em `.js`

- **Tipo:** `Teste`
- **Dependências:** `T-125`
- **Rastreia:** `AC-73`
- **Arquivos:** `tests/app_aluno/estatica/test_sem_condicional_no_javascript.py`

**Descrição**

O espelho de `AC-37` do lado do cliente, e a trava que sustenta a revisão do
§2 do plano: se um `.js` passar a conter enunciado, rótulo de opção ou
avaliação de condicional, a suíte falha.

**Critérios de aceite**

- [x] Falha se um `.js` de `app/http/estaticos/` contiver string longa de
      conteúdo de pergunta (mesmo limiar de `AC-37`), ignorando `htmx.min.js`
      (vendorizado, 0BSD)
- [x] Falha se contiver avaliação de `condicao_exibicao`
- [x] Passa no estado entregue por `T-125`

**Status:** `[x] concluída`

**Nota de implementação.** Este teste é o que sustenta a revisão do §2 do
plano. A delimitação registrada lá — "a recusa vale para o SPA que avalia
condicional no cliente, não para este desenho" — só tem valor se for
verificável; sem esta auditoria, nada impediria alguém de reintroduzir a
avaliação em JS meses depois, e a justificativa do plano viraria ficção.

Três testes: nenhum nome estrutural do grafo (`condicao_exibicao`,
`EXISTE_ITEM`, `valor_interno`, `VARIAVEL_GRAVADA`, `obrigatoriedade`) em
`.js`; nenhuma string acima de 40 caracteres fora de comentário (mesmo
limiar de `AC-37`); e um terceiro que prova que a auditoria não passa por
vacuidade — se `mascaras.js` sumisse da varredura, os dois primeiros
passariam sem auditar nada.

`tests/app_aluno/estatica/test_sem_condicional_no_javascript.py` → 3 passed.

---

### `T-127` — Testar a máscara contra a fronteira real de conversão

- **Tipo:** `Teste`
- **Dependências:** `T-125`
- **Rastreia:** `AC-75`, `AC-76`, `AC-77`
- **Arquivos:** `tests/app_aluno/test_mascaras.py`

**Descrição**

Não há runner de JavaScript no projeto e o plano não autoriza um. O contrato
que **importa** é que a saída da máscara e o parser do servidor concordem — e
isso é testável em Python: uma tabela `entrada → saída esperada` derivada das
regras da máscara, verificando que cada saída esperada é aceita por
`converter_para_dinheiro`/`converter_para_taxa` com o `Decimal` correto.

**Critérios de aceite**

- [x] Cada saída de `MOEDA` da tabela é aceita e produz o `Decimal` esperado
- [x] Cada saída de `TAXA` produz a fração esperada (`"4,5"` → `0.045`)
- [x] As entradas ambíguas da tabela levantam `ErroConversaoInvalida`
- [x] A tabela é dado no teste, não enunciado de pergunta (`AC-37` verde)

**Status:** `[x] concluída`

**Nota de implementação.** `tests/app_aluno/test_mascaras.py` → 19 passed.

**O que este teste NÃO cobre, declarado honestamente:** ele não executa
`mascaras.js`. Não há runner de JavaScript no projeto e o plano não autoriza
um. O que ele garante é o **contrato** entre a máscara e o servidor — que
cada saída declarada é aceita por `converter_para_dinheiro`/
`converter_para_taxa` e produz o `Decimal` certo. Se a implementação em JS
divergir das regras declaradas na tabela, este teste continua passando; essa
metade do risco fica para a verificação manual do checklist.

É deliberadamente a metade do risco que dá para eliminar sem navegador — e é
a metade que importa, porque o modo de falha real seria o aluno digitar, ver
o campo formatado bonito, e levar `400` do servidor.

---

### `T-128` — Portar o design system do protótipo e fechar a rodada

- **Tipo:** `UI`
- **Dependências:** `T-123`, `T-125`
- **Rastreia:** `RF-45`, `OQ-26`, `OQ-27`
- **Arquivos:** `app/http/estaticos/estilo.css`, `report/templates/coleta/pagina.html`

**Descrição**

A casca de página que nunca existiu (`estilo.css` é hoje código morto: nenhum
template o referencia) mais os tokens do protótipo. **Três auditorias mordem
aqui** e precisam ser respeitadas, não contornadas.

**Critérios de aceite**

- [x] `pagina.html` carrega `htmx.min.js`, `mascaras.js` e `estilo.css` **uma
      vez por página**, e envolve os fragmentos de `pergunta.html`
- [x] `test_css_360px.py` continua passando — atenção: `max-width: 1200px`
      **contém** a substring `width: 1200px` e é pega pelo regex
- [x] `test_acessibilidade_coleta.py` continua passando — ele extrai hex
      literal de seletores específicos; tokenizar essas cores quebra o teste
- [x] `test_acessibilidade_plano.py` continua passando — templates de plano e
      revisão **não** referenciam `estilo.css`
- [x] `ruff`, `mypy --strict` e `pytest -q` limpos; contagem de testes
      registrada na nota de fechamento
- [x] `OQ-26` (fontes) e `OQ-27` (tema escuro) registradas como abertas, sem
      decisão tomada por quem implementa

**Status:** `[x] concluída`

**Nota de implementação.** Tokens do protótipo em `:root` (`--bg`, `--ink`,
`--accent`, `--raio`, `--toque-minimo`), mais a casca de página e o alvo de
toque de 48 px da persona (celular na mão, contracheque ao lado).

**Os três seletores auditados por contraste mantiveram hex LITERAL**, não
`var(...)`: `test_acessibilidade_coleta.py` recalcula a razão WCAG lendo o
hexadecimal direto do arquivo, e tokenizá-los quebraria a auditoria — em
silêncio, na primeira vez que alguém mudasse um token achando que era só
estética. Nenhuma largura em px acima de 360 entrou, nem como `max-width`,
porque o regex de `test_css_360px.py` casa a substring em qualquer contexto.

`OQ-26` (fontes Atkinson Hyperlegible/Source Serif 4) e `OQ-27` (tema
escuro) **seguem abertas**: a pilha declarada é de sistema e nenhum
`@media (prefers-color-scheme)` foi escrito. Atkinson Hyperlegible foi
desenhada para baixa visão — trocá-la por fallback não é decisão neutra, e
não é de quem implementa.

**Verificação final da rodada:** `ruff check .` limpo · `mypy` 308 arquivos
sem erro · `pytest -q` → **1530 passed, 75 skipped** (linha de base era
1495/75: +35 testes, zero regressão).

---

### `T-129` — Verificar a máscara em navegador real com Playwright

- **Tipo:** `Teste`
- **Dependências:** `T-125`, `T-127`
- **Rastreia:** `RF-47`, `RF-48`, `AC-75`, `AC-76`, `AC-78`, `EC-22`
- **Arquivos:** `tests/app_aluno/e2e/test_navegador_mascaras.py`, `pyproject.toml`, `tests/app_aluno/conftest.py`, `tests/app_aluno/e2e/test_acessibilidade_plano.py`, `docs/checklist-acessibilidade.md`

**Descrição**

`T-127` provou que as saídas DECLARADAS da máscara são aceitas pela fronteira
de conversão, e dizia por escrito o que não cobria: que `mascaras.js` de fato
implementa as regras declaradas. Esta tarefa fecha essa metade, **a pedido
explícito do especialista** (2026-09-14), com Playwright em Chromium real.

**Critérios de aceite**

- [x] `playwright`/`pytest-playwright` declarados num extra **próprio**
      (`browser`), nunca em `app` nem em `dev`
- [x] Marcador `navegador` pulado automaticamente sem o extra — a suíte
      continua verde em máquina que nunca o instalou
- [x] O navegador digita `123456` e o campo mostra `1.234,56` (`AC-75`)
- [x] O `%` fica fora do `<input>` (`AC-76`); "não sei" desabilita e esvazia
      o campo (`AC-78`); colar `"R$ 1.234,56"` funciona (`EC-22`)
- [x] Nenhum erro de console ao carregar a página
- [x] `https_only=True` **não** é afrouxado — o teste serve por HTTPS
- [x] `ruff`, `mypy --strict` e `pytest -q` limpos

**Status:** `[x] concluída`

**Nota de implementação.** Seis testes, todos passando: a máscara formata de
verdade no Chromium, o `%` é `<span>` irmão, `nao_sei` inertiza o campo, e o
grafo condicional não chega ao documento (`RF-45` verificado no cliente real).

**Dois obstáculos reais, e como foram tratados — nenhum por atalho:**

1. **O plugin pytest do Playwright quebrou 16 testes alheios.** Ele abre
   escopo de *soft assertion* em TODO teste da suíte, e `test_reabertura.py`
   já roda dentro de um — `"nested soft assertion scopes are not supported"`.
   Desligado por `addopts = "-p no:playwright"`. Nenhum teste deste projeto
   usa as fixtures dele: o teste novo dirige `sync_playwright()` direto,
   porque precisa subir a aplicação sobre TLS com repositórios de arquivo.
   O plugin custava 16 testes e não entregava nada.

2. **`https_only=True` impede o cookie de sessão sobre `http://localhost`.**
   A saída foi servir por HTTPS com certificado efêmero gerado pelo OpenSSL
   do sistema (sem acrescentar `cryptography`/`trustme`), com
   `ignore_https_errors` no navegador. **O middleware de produção não foi
   tocado** — é o certificado que é descartável, não a exigência de HTTPS.
   Enfraquecer segurança para um teste passar seria a troca errada.

**Um tripwire disparou, e foi corrigido em vez de apagado.**
`test_ambiente_confirma_ausencia_de_axe_core_e_chromium` afirmava
`find_spec("playwright") is None` e dizia, na própria mensagem, o que fazer se
isso mudasse: declarar a dependência e não confundir o substituto estático com
`axe-core`. Foi reescrito para afirmar a realidade nova (Playwright presente,
dependência declarada, verificação em navegador existente) preservando a
distinção que ele protegia. `test_acessibilidade_coleta.py` e
`docs/checklist-acessibilidade.md` também afirmavam a ausência como fato e
foram atualizados.

**O que continua NÃO feito, e não deve ser dado como feito:** ter navegador é
pré-requisito de `axe-core`, não é `axe-core`. A auditoria das ~90 regras e a
verificação com leitor de tela real seguem abertas no checklist manual.

**Verificação:** `ruff` limpo · `mypy` limpo · `pytest -q` →
**1539 passed, 75 skipped** (era 1533 antes desta tarefa: +6 testes de
navegador, e os 16 quebrados pelo plugin restaurados).

---

### `T-130` — Exibir a recusa do servidor no navegador (defeito achado por `T-129`)

- **Tipo:** `UI`
- **Dependências:** `T-129`
- **Rastreia:** `AC-06`, `EC-01`, `EC-02`, NFR de acessibilidade
- **Arquivos:** `report/templates/coleta/pagina.html`, `tests/app_aluno/e2e/test_navegador_fluxo.py`

**Descrição**

**Defeito real, encontrado pelos testes de navegador — não é tarefa de
escopo novo.** Ao escrever `T-130`/`test_navegador_fluxo.py`, dois testes de
recusa (`EC-01` e `EC-02`) falharam por timeout esperando `role="alert"`.
A investigação separou as duas hipóteses:

- **Servidor correto.** Sonda HTTP direta: a sequência de margem devolve
  `400` com `<p class="erro-resposta" role="alert">VALOR_UTILIZADO_MARGEM/
  VALOR_TOTAL_MARGEM: …</p>` e **nada** é gravado. `EC-01`/`EC-02` valem na
  camada HTTP.
- **Cliente silencioso.** O default vendorizado do HTMX é
  `{code:"[45]..",swap:false,error:true}` — 4xx **nunca** troca o alvo.
  No navegador, após o `400`, `#resultado-{ID}` ficava `''` e **não existia
  `role="alert"` em lugar nenhum da página**.

Ou seja: a mensagem existia, era correta, e **o aluno não a via**. Isso
contraria a NFR de acessibilidade (*"mensagem de erro de validação anunciada
a leitor de tela e vinculada ao campo que a originou"*), `AC-06`/`EC-02`
(*"recusada com mensagem"*) e o critério já marcado como concluído em
`T-48`, que deu por feito o vínculo `aria-describedby` → `#resultado-{ID}`.
Nenhum teste pegava isso porque todos afirmavam na camada HTTP
(`resposta.text`), nunca num navegador.

**Critérios de aceite**

- [x] Após um `400`, o fragmento `erro_resposta.html` é inserido em
      `#resultado-{ID}` e o `role="alert"` existe no DOM
- [x] `EC-01` (entrada ambígua) e `EC-02` (validação cruzada) passam em
      navegador real, **sem enfraquecer a asserção**
- [x] `5xx` continua **sem** troca — erro de infraestrutura não vira texto
      na cara do aluno
- [x] O servidor **não** foi alterado: ele já estava certo
- [x] O caminho sem JavaScript (`EC-21`) segue intacto

**Status:** `[x] concluída`

**Nota de implementação.** Um `htmx:beforeSwap` na casca de página
(`pagina.html`) destrava a troca só para 4xx, marcando `isError = false` para
que o fragmento chegue ao alvo que o `aria-describedby` do campo já
referenciava desde `T-48`. Cinco linhas de JavaScript, nenhuma mudança de
servidor, nenhuma dependência nova.

**A lição que vale registrar:** o `role="alert"` estava no template certo, o
`aria-describedby` apontava para o container certo, o servidor devolvia a
mensagem certa — e mesmo assim o aluno via silêncio. Três camadas corretas e
o resultado errado. Nenhum teste de HTTP encontraria isso; foi preciso um
navegador de verdade, que é exatamente o que `T-129` passou a permitir.

| Requisito | Tarefas |
| --------- | ------- |
| `RF-01` — caso com ciclo de vida explícito | `T-01`, `T-04`, `T-21`, `T-23`, `T-24`, `T-33`, `T-34`, `T-86`, `T-95` |
| `RF-02` — login e senha, isolamento por caso | `T-01`, `T-21`, `T-28`, `T-29`, `T-30`, `T-31`, `T-32`, `T-37`, `T-95` |
| `RF-03` — coleta gerada a partir de registros | `T-04`, `T-08`, `T-09`, `T-16`, `T-17`, `T-43` |
| `RF-04` — ficha repetível | `T-15`, `T-17`, `T-20`, `T-23`, `T-47` |
| `RF-05` — condicional composta entre blocos | `T-10`, `T-11`, `T-19`, `T-20`, `T-42` |
| `RF-06` — texto dinâmico | `T-12`, `T-20`, `T-43` |
| `RF-07` — validação cruzada entre campos | `T-13`, `T-20`, `T-42`, `T-48` |
| `RF-08` — opções produzidas pelo motor | `T-14`, `T-19`, `T-20` |
| `RF-09` — Etapa B completa + Blocos 7, 8, 10, 11 | `T-17`, `T-18`, `T-44`, `T-48`, `T-95` |
| `RF-10` — persistir a cada resposta, retomar | `T-21`, `T-22`, `T-24`, `T-25`, `T-42`, `T-45`, `T-46`, `T-94`, `T-95` |
| `RF-11` — "não sei" de primeira classe | `T-22`, `T-40`, `T-41`, `T-42`, `T-44`, `T-101` |
| `RF-12` — "não sei" → `DESCONHECIDO`, nunca inventar | `T-49`, `T-53` |
| `RF-13` — fronteira `Decimal` única e testada | `T-03`, `T-22`, `T-25`, `T-27`, `T-38`, `T-39`, `T-42`, `T-101` |
| `RF-14` — montar `EstadoFinanceiro` completo | `T-49`, `T-50`, `T-51`, `T-53`, `T-99`, `T-101`, `T-103` |
| `RF-15` — `INVENTARIO_COMPLETO` de `B5.FIM02` | `T-52`, `T-53` |
| `RF-16` — executar o Bloco 6 sem reproduzir cálculo | `T-54`, `T-55`, `T-56`, `T-57`, `T-58`, `T-95` |
| `RF-17` — Blocos 7/8 só para dívidas sinalizadas | `T-74`, `T-75`, `T-76`, `T-79` |
| `RF-18` — Bloco 10 condicional e validado | `T-18`, `T-77`, `T-78`, `T-79` |
| `RF-19` — snapshot só por `RepositorioSnapshots.anexar` | `T-26`, `T-54`, `T-57`, `T-86` |
| `RF-20` — `ENGINE_VERSION`/`PARAMETROS_VERSION` em toda saída | `T-03`, `T-60`, `T-63`, `T-64`, `T-65`, `T-95` |
| `RF-21` — redação canônica, caractere por caractere | `T-04`, `T-59`, `T-62`, `T-63`, `T-64`, `T-65`, `T-95`, `T-97` |
| `RF-22` — `JUSTIFICATIVA_POSICAO` por dívida | `T-60`, `T-62`, `T-65`, `T-97` |
| `RF-23` — fila de revisão para todo snapshot | `T-64`, `T-66`, `T-68`, `T-69`, `T-73`, `T-95`, `T-96`, `T-100` |
| `RF-24` — revisão com autor e data, imutável | `T-21`, `T-67`, `T-68`, `T-71`, `T-73` |
| `RF-25` — os dois mecanismos, nomeados e distintos | `T-66`, `T-69`, `T-73`, `T-100` |
| `RF-26` — plano e `estado_inputs` lado a lado | `T-70`, `T-72`, `T-73`, `T-96` |
| `RF-27` — Bloco 11 ao longo do tempo, reabertura dirigida | `T-18`, `T-80`, `T-83`, `T-84`, `T-85`, `T-88` |
| `RF-28` — recálculo só por quitação ou evento material | `T-81`, `T-86`, `T-87`, `T-88` |
| `RF-29` — só `B11.Q01 = Sim` dispara | `T-82`, `T-88` |
| `RF-30` — consentimento, retenção, exclusão | `T-21`, `T-35`, `T-36`, `T-37` |
| `RF-31` — trilha de progresso, abandono observável | `T-21`, `T-23`, `T-91`, `T-92`, `T-93`, `T-102` |
| `RF-32` — parâmetros pela `FonteParametros` existente | `T-08`, `T-54` |
| `RF-33` — `ORDEM_ACOES` com `ACAO_ID` e `TIPO_ACAO` | `T-74`, `T-83`, `T-84`, `T-89`, `T-90` |
| `RF-34` — aplicação livre de regra de cálculo | `T-01`, `T-02`, `T-05`, `T-06`, `T-07`, `T-40`, `T-61`, `T-98` |
| `RF-35` — painel dedicado do operador | `T-92`, `T-102` |

**Cobertura (Rodada 1):** 35 de 35 requisitos funcionais. Nenhuma tarefa deste
backlog existe sem requisito atrás.

## Entrega 14 — Rodada 4: frontend React e cobertura total do motor

> **Ordem obrigatória.** `T-131` é portão: sem a emenda dos artefatos, o resto
> é código sem spec que o autorize. As fatias seguem a ordem em que o fluxo
> quebra hoje: coleta (fichas repetíveis) → pós-plano → operador.

### `T-131` — Emendar spec e plano para React e cobertura total

- **Tipo:** `SDD`
- **Dependências:** —
- **Rastreia:** `RF-50` a `RF-56`
- **Arquivos:** `specs/app-aluno.spec.md`, `plans/app-aluno.plan.md`, `tasks/app-aluno.tasks.md`, `.gitignore`

**Descrição**

A adoção de React **revoga** a recusa de SPA do §2 — não a delimita, como fez
`T-122`. O plano registra o que se perde (caminho sem JS, a garantia
estrutural de `RF-05`, zero dependência nova) e o que continua inegociável
(Lei nº 3, fronteira `Decimal` única, isolamento no servidor).

Inclui criar `.gitignore`, que **não existia**.

**Critérios de aceite**

- [x] `RF-50` a `RF-56` na spec, em subseção datada própria
- [x] §2 do plano registra a revogação com o custo explícito
- [x] Registrado que `.claude/instructions/tailwind|testing` descrevem um app
      de previsão do tempo e **não se aplicam**; `react.instructions.md` sim
- [x] `.gitignore` cobre `node_modules/`, `dist/`, `.env` e `*.pem`

**Status:** `[x] concluída`

**Nota de implementação.** `.gitignore` é **preventivo, não protetivo**: este
diretório **não é um repositório git** (`git rev-parse` falha). Ele passa a
valer no dia em que alguém rodar `git init` — o que, com 53 MB de
`node_modules` a caminho, é melhor existir antes do que depois.

---

### `T-132` — Scaffold React + tema do protótipo

- **Tipo:** `UI`
- **Dependências:** `T-131`
- **Rastreia:** `RF-50`
- **Arquivos:** `frontend/` (scaffold), `frontend/tailwind.config.js`, `frontend/src/index.css`, `frontend/vite.config.ts`

**Critérios de aceite**

- [x] React 19 + TypeScript + Vite, com Vitest e Playwright
- [x] Tokens do protótipo no tema: `#FAFAF7`, `#0F6E56`, raio 14px, alvos de
      toque 48/56/60px, Source Serif 4 + Atkinson Hyperlegible
- [x] Proxy do Vite para o FastAPI em `https://localhost:8443`
- [x] `npx vite build` limpo

**Status:** `[x] concluída`

**Nota de implementação — dois obstáculos de plataforma, nenhum meu:**

1. **Vite 8 não sobe neste Windows.** Ele usa Rolldown, e a lista de
   binários do `rolldown@1.2.8` tem darwin/android/linux e `win32-arm64` —
   **não tem `win32-x64-msvc`**. Não é download falho: é plataforma sem
   suporte. Fixado em **Vite 7** (rollup), e o build voltou.
2. **O tema parecia não compilar.** Compilava: Tailwind faz tree-shaking de
   `@layer components` contra `content`, e sem nenhum `.tsx` usando `.btn` o
   CSS saía sem ela. Com um arquivo real usando as classes, o CSS foi de
   7,83 kB para 12,95 kB, com `min-height:56px` e `rgb(15 110 86)`.

**Restrições de plataforma desta máquina** (detalhe em
`docs/banco-local.md`), porque voltam a morder quem tentar atualizar tudo:

| O quê | Por quê |
| --- | --- |
| **Vite 8** não sobe | `rolldown@1.2.8` não publica binário `win32-x64-msvc` (só arm64) |
| **Vite 7** não sobe | Exige Node `>=22.12`; a máquina tem 22.9.0, e `nvm use` não troca o PATH |
| **oxlint** não roda | Mesma falta de binário `win32-x64`. `npm run lint` virou `tsc -b --noEmit`, que roda e está limpo |
| **jsdom** quebra | `ERR_REQUIRE_ESM` sob Node 22.9 → **happy-dom** |

Fixado em **Vite 6** (`>=22.0.0`), que roda como está.

---

### `T-133` — API JSON: serializador e variante de resposta

- **Tipo:** `Data`
- **Dependências:** `T-131`
- **Rastreia:** `RF-51`, `RF-52`
- **Arquivos:** `app/http/serializacao.py`, `app/http/rotas_pergunta.py`

**Critérios de aceite**

- [x] `serializar_pergunta` escolhe campo a campo — `condicao_exibicao`,
      `validacoes_cruzadas`, `obrigatoriedade` e `interpolacoes` **não**
      atravessam (`RF-52`), verificado por inspeção do JSON
- [x] `Decimal` vira **string**, nunca `float` (`RF-13`)
- [x] `NAO_SEI` vira string canônica, nunca `null` nem `0`
- [x] `GET /caso/{id}/pergunta` com `Accept: application/json` devolve o payload

**Status:** `[x] concluída`

**Nota de implementação.** `dataclasses.asdict` foi descartado por dois
motivos, e o segundo é o que importa: (1) não passa por `json.dumps` —
`TipoResposta` é `Enum`, `valores_marcados` é `frozenset`; (2) despejaria o
`RegistroPergunta` inteiro no cliente, incluindo a regra. Escolher campo a
campo **é** a trava: o que não é escrito no serializador não atravessa.

---

### `T-134` — Fichas repetíveis: a rota que faltava

- **Tipo:** `UI`
- **Dependências:** `T-133`
- **Rastreia:** `RF-04`, `RF-51`, `RF-53`, `AC-04`
- **Arquivos:** `app/http/rotas_fichas.py`, `app/http/aplicacao.py`

**Critérios de aceite**

- [x] `GET/POST /caso/{id}/fichas/{escopo}` e `DELETE .../{item_id}`
- [x] `GET /caso/{id}/escopos` derivado dos registros, nunca de lista no código
- [x] `completa` é leitura de `pendencias_obrigatorias`, nunca recontado
- [x] Identificador **não** se reaproveita: removida a `D001`, a próxima é `D002`
- [x] Escopo inválido ⇒ `400`; item inexistente ⇒ `404`
- [x] A auditoria de isolamento aceita as quatro rotas novas

**Status:** `[x] concluída`

**Nota de implementação.** `ficha_repetivel.html` existia desde `T-47`,
testada, e **nenhuma rota a renderizava** — a tela mais cara já construída
estava morta, e com ela as **108 perguntas** de escopo repetível (Blocos 3,
5, 7, 8, 11). Sem esta rota o aluno não cadastrava nem uma dívida.

Verificado contra o banco real: 7 escopos, ficha `D001` com 37 campos,
remoção marcando, `D002` nascendo em seguida.

---

### `T-135` — Registrar os roteadores órfãos

- **Tipo:** `UI`
- **Dependências:** `T-134`
- **Rastreia:** `RF-53`
- **Arquivos:** `app/http/aplicacao.py`

**Critérios de aceite**

- [x] `rotas_bloco11` e `rotas_coleta_dirigida` registrados em `criar_aplicacao()`
- [x] Suíte intacta

**Status:** `[x] concluída`

**Nota de implementação.** Os dois existiam desde `T-75`/`T-82`, com rotas
completas e testadas, e **nunca apareceram em `criar_aplicacao()`**: código
testado e inalcançável por `uvicorn`. Duas linhas cada.

---

### `T-136` — Cliente de API e tipos do frontend

- **Tipo:** `UI`
- **Dependências:** `T-133`
- **Rastreia:** `RF-51`, `RF-52`
- **Arquivos:** `frontend/src/tipos.ts`, `frontend/src/services/api.ts`

**Critérios de aceite**

- [x] Tipos espelham o serializador; **não existe** tipo para
      `condicao_exibicao` — o TypeScript recusa antes de rodar (`RF-52`)
- [x] `valor_atual` é `string | string[] | null`, nunca `number` (`RF-13`)
- [x] `credentials: 'include'` em toda chamada
- [x] `SELECAO_MULTIPLA` envia `valor` repetido em `form-urlencoded`

**Status:** `[x] concluída`

---

### `T-137` — Telas da coleta no design do protótipo

- **Tipo:** `UI`
- **Dependências:** `T-136`
- **Rastreia:** `RF-50`, `RF-47`, `RF-48`
- **Arquivos:** `frontend/src/mascaras.ts`, `frontend/src/componentes/`, `frontend/src/telas/`, `frontend/src/App.tsx`

**Critérios de aceite**

- [x] `CampoPergunta` cobre os nove `TipoResposta`
- [x] Máscara em TS emite as MESMAS saídas da tabela provada em Python
- [x] `R$` e `%` ficam **fora** do `<input>` (`AC-76`)
- [x] "não sei" deixa o campo inerte (`AC-78`)
- [x] Rótulo associado em todos os ramos (queries acessíveis passam)
- [x] `tsc -b --noEmit` limpo; 28 testes unitários passando

**Status:** `[x] concluída`

**Nota de implementação — o jsdom não funciona neste Node.** `ERR_REQUIRE_ESM`
em `@csstools/css-calc`, verificado isoladamente, fora do Vitest. Teste de
lógica pura passou a rodar em `environment: 'node'` (não precisa de DOM, e
fica mais rápido); teste de componente usa **happy-dom** por docblock no
próprio arquivo. `environmentMatchGlobs` não existe mais no Vitest 4.

---

### `T-138` — E2E Playwright das telas React

- **Tipo:** `Teste`
- **Dependências:** `T-137`
- **Rastreia:** `RF-50`, `RF-52`, `AC-75`, `AC-76`, `AC-78`
- **Arquivos:** `frontend/playwright.config.ts`, `frontend/tests/e2e/coleta.spec.ts`

**Critérios de aceite**

- [x] Rede interceptada com `page.route` (determinismo), com payload na forma
      exata de `app/http/serializacao.py`
- [x] Ao menos um teste em viewport mobile — **360px**, a largura da NFR
- [x] `AC-75`: a máscara formata `1.234,56` em navegador real
- [x] `AC-76`: o `R$` e o `%` ficam fora do `<input>`
- [x] `AC-78`: "não sei" deixa o campo inerte
- [x] `RF-52`: `condicao_exibicao` e `validacoes_cruzadas` ausentes do DOM
- [x] Fichas: `D001` listada, `D002` criada — identificador não se reaproveita
- [x] 360px sem rolagem horizontal

**Status:** `[x] concluída`

**Verificação:** **14 passed** (7 em desktop, 7 em mobile-360) · 28 testes
unitários · `tsc -b --noEmit` limpo.

**Três defeitos meus no caminho, todos corrigidos no lugar certo:**

1. **`webServer` esperava `127.0.0.1`**, mas o Vite anuncia `localhost` — no
   Windows resolvem diferente (IPv4 × IPv6), e o Playwright esperava 120s por
   um servidor que estava no ar.
2. **O E2E ia direto a `/?caso=` e procurava o botão "Coleta"**, que só
   existia após o login. A correção foi no **app**, não no teste: com o caso
   na URL, abrir direto na coleta é o comportamento certo — quem autoriza é o
   cookie de sessão, reverificado no servidor (`401`/`404`). Mostrar login ali
   seria teatro.
3. **Locator ambíguo**: `/Dívida D001/` casava também com o botão de remover
   (`aria-label="Remover Dívida D001"`). Corrigi o **seletor** com
   `exact: true`, não o rótulo — "Remover Dívida D001" é a redação certa para
   leitor de tela, e piorar acessibilidade para facilitar um seletor seria a
   troca errada.

---

### `T-139` — As três saídas de `PLANO_LIBERADO`, e o Bloco 8

- **Tipo:** `UI`
- **Dependências:** `T-135`
- **Rastreia:** `RF-54`, `RF-53`, `AC-19`, `AC-22`, `AC-40`
- **Arquivos:** `app/http/rotas_etapas.py`, `app/http/rotas_coleta_dirigida.py`, `app/http/aplicacao.py`

**Descrição**

`maquina.py:216-232` declarava três transições saindo de `PLANO_LIBERADO`
(`abre_blocos_7_8`, `abre_bloco_10`, `abre_bloco_11`) e **nenhuma rota as
disparava**: o caso chegava ao plano liberado e morria ali. Blocos 7, 8, 10 e
11 existiam em código, testados, e eram inalcançáveis porque o caso nunca
saía do estado anterior a eles.

O Bloco 8 tinha um problema a mais: `dividas_para_bloco_8` e
`perguntas_do_bloco_8` existiam desde `T-76` e **nenhuma rota as expunha**.

**Critérios de aceite**

- [x] `POST /caso/{id}/etapas/{blocos-7-8|bloco-10|bloco-11}` disparam as três
      transições por `transicionar_e_registrar` — par validado contra a
      máquina, gravação condicional e evento na trilha (`AC-40`)
- [x] `AC-22`: `bloco-10` só abre com `ATAQUE_IMEDIATO_RECOMENDADO > 0`,
      consultando `bloco_10_alcancavel` — nenhum limiar reimplementado
- [x] `AC-19`: `blocos-7-8` só abre com dívida sinalizada em `ORDEM_ACOES`
- [x] Sem plano liberado ⇒ `409`; corrida perdida ⇒ `409`, nada gravado
- [x] `GET /caso/{id}/etapas` diz o que pode abrir, pelas MESMAS funções
- [x] `GET /caso/{id}/coleta-dirigida/bloco-8` — a rota que faltava
- [x] 33 `APIRoute` registradas, **zero** violações de isolamento

**Status:** `[x] concluída`

**Verificação:** mypy e ruff limpos · `pytest -q` → 1620 passed, 3 skipped ·
endpoints exercitados contra o banco real (`/etapas` com os três portões
fechados sem plano; `bloco-10` recusando com `409`; `bloco-8` devolvendo
listas vazias em vez de erro).

**`RF-55` NÃO foi implementado, e a razão mudou minha posição.** Eu havia
proposto ligar a rota do Bloco 11 a `processar_resposta_bloco_11`, para que
quitação confirmada disparasse recálculo (`AC-30`). Com o código à vista, a
orquestração exige um `EstadoFinanceiro`, que exige
`ParametrosExternosDoBloco6` — cuja implementação padrão **levanta
`_ErroParametrosExternosPendentes` de propósito**, porque
`CONFIABILIDADE_DADOS` não tem fonte real (é o mesmo motivo pelo qual
`POST /calculo` devolve `503` em produção).

Ligar agora daria `503` em toda quitação confirmada — pior que o
comportamento atual, que ao menos identifica o evento honestamente sem
prometer o recálculo. **A fronteira de `T-86` não é o obstáculo; a
dependência externa de `CONFIABILIDADE_DADOS` é.** `RF-55` fica aberto,
bloqueado pela mesma lacuna, e não por decisão de desenho.

---

### `T-140` — Telas do plano e da revisão em React

- **Tipo:** `UI`
- **Dependências:** `T-139`
- **Rastreia:** `RF-50`, `RF-51`, `AC-14`, `AC-16`, `AC-25`, `AC-28`, `AC-70`
- **Arquivos:** `app/http/serializacao_plano.py`, `app/http/rotas_api_plano.py`, `frontend/src/telas/TelaPlano.tsx`, `frontend/src/telas/TelaRevisao.tsx`

**Descrição**

O especialista pediu tudo no frontend React, sem Jinja2. Esta tarefa move
plano e fila de revisão: API JSON no servidor, telas `.tsx` no design do
protótipo.

**Critérios de aceite**

- [x] `GET /caso/{id}/api/plano` — só o snapshot LIBERADO (`AC-25`), com a
      MESMA guarda `snapshot_tem_liberacao_registrada` do PDF
- [x] `titulo`/`corpo` transportados verbatim (`AC-14`), carimbo de versão
      na saída (`AC-16`), reserva desconhecida como estado (`AC-70`)
- [x] `GET /api/revisao/fila` com os dois sinais SEPARADOS (`AC-28`)
- [x] `401`/`403` viram texto legível, nunca "HTTP 403" na cara do usuário
- [x] Gates verdes: ruff, mypy 318 arquivos, 1620 testes, tsc, 28 unitários

**Status:** `[x] concluída`

**Nota — `plano.html` NÃO foi apagado, e isso é deliberado.** `report/pdf.py`
renderiza aquele mesmo template para gerar o PDF, e `RF-21`/`AC-14` exigem
que a redação canônica de `Q-03` exista em UM lugar só, compartilhado por
tela e PDF. Apagá-lo mataria o PDF ou criaria uma segunda cópia do texto
normativo — exatamente o que aquele critério proíbe. O template deixou de
servir navegador; continua sendo a fonte do PDF.

**Dois erros meus de assinatura**, pegos pelo type-checker antes de rodar:
`listar_fila_de_revisao` exige `casos_ids` (eu omitira) e
`montar_item_da_fila` recebe `str`, não `Caso`. Corrigi copiando o idioma
real de `rotas_revisao.py`, em vez de inventar uma terceira via.

---

### `T-141` — Conta, consentimento, progresso e painel em React

- **Tipo:** `UI`
- **Dependências:** `T-140`
- **Rastreia:** `RF-02`, `RF-30`, `RF-35`, `RF-50`, `RF-51`, `AC-39`
- **Arquivos:** `app/http/rotas_api_conta.py`, `app/http/rotas_api_plano.py`, `frontend/src/telas/TelaConsentimento.tsx`, `frontend/src/telas/TelaOperador.tsx`

**Descrição**

As últimas telas Jinja2 do lado do aluno e do operador viram React, a pedido
do especialista ("não quero nada no Jinja2").

**Critérios de aceite**

- [x] `POST /api/conta/login` — conta inexistente e senha errada devolvem a
      MESMA mensagem e o MESMO `401` (`RF-02`); diferenciá-las diria a um
      atacante quais e-mails existem
- [x] `GET /api/caso/{id}/consentimento` — `503` nomeado enquanto `PEND-01`
      não publicar o texto; nunca "sem consentimento = pode seguir"
- [x] `GET /api/caso/{id}/calculo/progresso` — leitura pura de `Caso.estado`
- [x] `GET /api/operador/painel` — **nenhum valor financeiro** (`T-102`)
- [x] 41 rotas registradas, zero violações de isolamento
- [x] Gates: ruff, mypy 319 arquivos, 1620 testes, tsc, 28 unitários

**Status:** `[x] concluída`

---

### `T-142` — Telas dos Blocos 7, 8 e 10 em React

- **Tipo:** `UI`
- **Dependências:** `T-141`
- **Rastreia:** `RF-17`, `RF-18`, `RF-50`, `AC-19`, `AC-22`, `AC-23`, `AC-24`
- **Arquivos:** `app/http/rotas_coleta_dirigida.py`, `app/http/rotas_etapas.py`, `frontend/src/telas/TelaColetaDirigida.tsx`, `frontend/src/telas/TelaBloco10.tsx`

**Descrição**

As rotas de coleta dirigida devolviam só IDs de pergunta; uma tela React
precisa dos campos serializados. Enriqueci as duas (Blocos 7 e 8) e
acrescentei o `GET` do Bloco 10, que não existia.

**Critérios de aceite**

- [x] Blocos 7 e 8 devolvem `fichas` com campos serializados por `DIVIDA_ID`
- [x] `AC-19`: só as dívidas que o motor sinalizou em `ORDEM_ACOES`
- [x] `GET /caso/{id}/bloco-10` só responde com `ATAQUE_IMEDIATO_RECOMENDADO > 0`
- [x] `AC-24`: **nunca** se pergunta em qual dívida o dinheiro entra
- [x] `AC-23`: o limite `0 ≤ APROVADO ≤ RECOMENDADO` é validado no SERVIDOR;
      a tela exibe o recomendado mas não valida — seriam duas regras
- [x] 42 rotas, zero violações de isolamento
- [x] Gates: ruff, mypy 319 arquivos, 1620 testes, tsc, 28 unitários, 14 E2E

**Status:** `[x] concluída`

**Uma regressão que eu causei, e o teste pegou.** Ao acrescentar a sexta aba
na navegação, o documento passou a medir 487px numa janela de 360px —
rolagem horizontal no celular da persona, violando a NFR de
responsividade. O `flex` do cabeçalho não quebrava linha. Corrigi com
`flex-wrap` no cabeçalho e na `nav`. O teste de 360px existe exatamente para
isso, e funcionou: falhou antes de eu entregar.

---

### `T-143` — Bloco 11: ações e andamento em React

- **Tipo:** `UI`
- **Dependências:** `T-142`
- **Rastreia:** `RF-27`, `RF-33`, `RF-50`, `AC-45`, `AC-46`, `AC-50`
- **Arquivos:** `app/http/rotas_acoes.py`, `frontend/src/telas/TelaAcoes.tsx`

**Descrição**

`rotas_bloco11.py` grava as SETE perguntas de confirmação de quitação
(`B11.Q01`–`Q06`) e só elas — é especializada, e a docstring diz isso. Mas o
Bloco 11 tem **doze** perguntas: `B11.01` (`ACAO_STATUS`) e as quatro
`B11.03-*` (resultado por tipo de ação) **não tinham caminho de gravação
nenhum**.

Acrescentei uma rota própria em vez de afrouxar a especializada — ela tem
uma garantia a preservar, e misturar as duas responsabilidades apagaria essa
distinção.

**Critérios de aceite**

- [x] `GET /caso/{id}/acoes` — uma ficha por ação de `ORDEM_ACOES`, leitura
      pura (Lei nº 3)
- [x] `POST /caso/{id}/acoes/resposta` grava `B11.01` e as `B11.03-*`
- [x] `AC-50`: ação **sem** `DIVIDA_ID` (economia) aparece como qualquer
      outra — a chave é o `ACAO_ID`, e nenhum caminho exige dívida
- [x] `VALOR_ACAO_FINANCEIRA_IMEDIATA` vai como string ou `null`; nunca
      `number`, nunca zero para desconhecido (`RF-13`)
- [x] `EC-05`: falha de gravação devolve `503` e **não** reporta como salva
- [x] 44 rotas, zero violações de isolamento
- [x] Gates: ruff, mypy 320 arquivos, 1620 testes, tsc, 28 unitários, 14 E2E

**Status:** `[x] concluída`

**Duas coisas que escrevi e refiz antes de entregar:** um `__import__`
embutido para pegar `datetime` (as outras rotas têm `_agora()`) e um
`except Exception` amplo (as outras capturam `ErroGravacaoResposta`/
`ErroCasoInexistenteParaResposta`). Ambos destoavam do projeto; corrigi para
o idioma existente em vez de deixar passar.

---

### Cobertura de requisitos — Rodada 2, fatia 2A

| Requisito | Tarefas |
| --------- | ------- |
| `RF-36` — `RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` por `_membro_do_enum` | `T-109`, `T-110`, `T-113`, `T-114`, `T-119` |
| `RF-37` — `RESERVA_TOTAL`/`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` como `DinheiroTalvez` | `T-110`, `T-113`, `T-114` |
| `RF-38` — `DINHEIRO_DISPONIVEL` como `Dinheiro` puro, zero legítimo × erro nomeado | `T-110`, `T-113` |
| `RF-39` — três coleções como tupla vazia declarada, motivo em docstring | `T-111`, `T-113` |
| `RF-40` — allowlist `+2` nomes, exatamente | `T-109`, `T-120` |
| `RF-41` — hashes regravados a partir da saída do teste | `T-108`, `T-120` |
| `RF-42` — fixtures e testes atualizados; `build` e suíte verdes | `T-111`, `T-112`, `T-120` |
| `RF-43` — `RESERVA_MOBILIZAVEL` desconhecida como estado explícito | `T-115`, `T-116` (parcial — redação é `OQ-21`), `T-117` |
| `RF-44` — leitura livre de agregação ou fórmula patrimonial | `T-111`, `T-114`, `T-118` |

**Cobertura (Rodada 2, fatia 2A):** 9 de 9 requisitos. Nenhum ficou sem tarefa.

### Cobertura dos critérios de aceite — Rodada 2, fatia 2A

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-51` | `T-110`, `T-113` | | `AC-62` | `T-111` |
| `AC-52` | `T-110`, `T-113` | | `AC-63` | `T-109` |
| `AC-53` | `T-110`, `T-119` | | `AC-64` | `T-109`, `T-120` |
| `AC-54` | `T-110`, `T-113` | | `AC-65` | `T-108`, `T-120` |
| `AC-55` | `T-110`, `T-113` | | `AC-66` | `T-112`, `T-120` |
| `AC-56` | `T-110`, `T-113` | | `AC-67` | `T-114` |
| `AC-57` | `T-110`, `T-113` | | `AC-68` | `T-114` |
| `AC-58` | `T-110`, `T-113` | | `AC-69` | `T-114` |
| `AC-59` | `T-110`, `T-113` | | `AC-70` | `T-115`, `T-116`, `T-117` |
| `AC-60` | `T-111`, `T-113` | | `AC-71` | `T-110`, `T-118` |
| `AC-61` | `T-118` | | | |

**Cobertura:** 21 de 21 critérios de aceite da fatia 2A.

### Cobertura dos casos de borda — Rodada 2, fatia 2A

| `EC-NN` | Tarefas | | `EC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `EC-15` | `T-110`, `T-113` | | `EC-18` | `T-115`, `T-116`, `T-117` |
| `EC-16` | `T-110`, `T-113` | | `EC-19` | `T-111` |
| `EC-17` | `T-110`, `T-113` | | `EC-20` | `T-110`, `T-113` |

### Requisitos sem cobertura

Nenhum, nas duas rodadas. Três com cobertura **parcial e declarada**, por
dependência externa — não por omissão do backlog:

- **`RF-33`** — `T-74`, `T-83`, `T-84` e `T-89` são executáveis agora (leitura de
  `ORDEM_ACOES` sem derivação, vínculo por `ACAO_ID`, mapeamento em registro,
  `AC-50` testado). `T-90` fica `xfail(strict=True)` até o slug `motor-calculo`
  entregar as três mudanças em `AcaoRequerida` — decisão já fechada
  (`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15` todas respondidas), falta só o código.
- **`RF-26`** — `T-70`, `T-71` e `T-73` entregam a tela lado a lado e o registro
  da decisão; `T-72` entrega os seis rótulos **sem glosa**, decisão fechada por
  `OQ-12` (texto normativo da §25 confirmado ausente do repositório inteiro;
  `PEND-LOCAL-01` registra a pendência externa, sem bloquear esta feature).
- **`RF-43`** (Rodada 2) — **cobertura parcial declarada, entregue.** `T-115`,
  `T-116` e `T-117` entregaram o contexto
  (`report/plano.py::ContextoReservaMobilizavel`/`_reserva_mobilizavel`), o
  ponto de encaixe (`report/templates/plano/reserva_mobilizavel.html`, incluído
  por `plano.html` no mesmo ponto que `pendencias.html`) e as três asserções de
  `AC-70` que **não** dependem do texto (não exibe `R$ 0,00`, não omite o item,
  nenhum caminho levanta exceção). **Comportamento e encaixe: entregues.
  Redação: pendente.** A **redação** que o aluno lê no estado "pendente de
  decisão" é `OQ-21`, **aberta** — insumo do especialista, não invenção do
  desenvolvedor (`RF-43` é explícito: *"esta spec fixa o comportamento, não o
  texto"*). O ponto exato a substituir está marcado no template pelo atributo
  `data-pendencia-redacao="OQ-21"`, no padrão de `PEND-01`
  (`app/consentimento/registro.py`); quando `OQ-21` for respondida, **nenhum
  outro arquivo precisa mudar** — os testes de `T-117` não dependem do texto.

> **Fora do escopo desta rodada, e por quê.** `T-77`, `T-78` e `T-79` seguiam
> `[ ] pendente` no fechamento desta fatia (2026-09-07): dependiam de
> `ATAQUE_IMEDIATO_RECOMENDADO`, que continuava `dinheiro(0)` por
> `motor-calculo:OQ-29`, aberta à época. **Atualização 2026-09-10:** `OQ-29`
> foi respondida e implementada por completo; as três tarefas foram
> concluídas fora desta fatia (Rodada 1, fechamento). Fatia **2B** depende de
> `OQ-22`(b) e `OQ-24`; fatia **2C**, de `motor-calculo:OQ-26` **e** `OQ-27`,
> ambas — estas continuam abertas, sem relação com `OQ-29`. A correção de
> `valores_do_escopo` é `OQ-24`, pré-requisito de 2B/2C — `T-118` prova que a
> fatia 2A não depende dela.

### Cobertura dos critérios de aceite — Rodada 1

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-01` | `T-45`, `T-46` | | `AC-26` | `T-68`, `T-86`, `T-88`, `T-96` |
| `AC-02` | `T-25`, `T-42`, `T-46` | | `AC-27` | `T-67`, `T-71`, `T-73` |
| `AC-03` | `T-29`, `T-30`, `T-31`, `T-32` | | `AC-28` | `T-66`, `T-69`, `T-73` |
| `AC-04` | `T-15`, `T-17`, `T-20`, `T-47` | | `AC-29` | `T-70`, `T-73`, `T-96` |
| `AC-05` | `T-12`, `T-20`, `T-82` | | `AC-30` | `T-86`, `T-88` |
| `AC-06` | `T-13`, `T-20` | | `AC-31` | `T-82`, `T-88` |
| `AC-07` | `T-52`, `T-53` | | `AC-32` | `T-26` |
| `AC-08` | `T-49`, `T-53` | | `AC-33` | `T-33`, `T-85`, `T-88` |
| `AC-09` | `T-27`, `T-38`, `T-39` | | `AC-34` | `T-33`, `T-80`, `T-88` |
| `AC-10` | `T-38`, `T-39` | | `AC-35` | `T-81`, `T-87`, `T-88` |
| `AC-11` | `T-44` | | `AC-36` | `T-09`, `T-16`, `T-17`, `T-20`, `T-43` |
| `AC-12` | `T-54`, `T-56`, `T-57` | | `AC-37` | `T-08`, `T-09`, `T-98` |
| `AC-13` | `T-50`, `T-53` | | `AC-38` | `T-16`, `T-20` |
| `AC-14` | `T-59`, `T-63`, `T-65`, `T-95` | | `AC-39` | `T-35`, `T-36`, `T-37` |
| `AC-15` | `T-59`, `T-65`, `T-95` | | `AC-40` | `T-91`, `T-92`, `T-93` |
| `AC-16` | `T-60`, `T-63`, `T-65`, `T-70`, `T-95` | | `AC-41` | `T-06`, `T-40`, `T-74`, `T-98` |
| `AC-17` | `T-60`, `T-65`, `T-95` | | `AC-42` | `T-12`, `T-60`, `T-61`, `T-98` |
| `AC-18` | `T-51`, `T-53` | | `AC-43` | `T-21`, `T-26`, `T-54`, `T-57` |
| `AC-19` | `T-75`, `T-76`, `T-79` | | `AC-44` | `T-07`, `T-98` |
| `AC-20` | `T-14`, `T-19`, `T-20` | | `AC-45` | `T-90` (`xfail`) |
| `AC-21` | `T-10`, `T-11`, `T-19`, `T-20` | | `AC-46` | `T-84`, `T-90` (`xfail`) |
| `AC-22` | `T-77`, `T-79` | | `AC-47` | `T-90` (`xfail`) |
| `AC-23` | `T-78`, `T-79` | | `AC-48` | `T-90` (`xfail`) |
| `AC-24` | `T-18`, `T-77`, `T-79` | | `AC-49` | `T-90` (`xfail`) |
| `AC-25` | `T-64`, `T-66`, `T-73`, `T-95` | | `AC-50` | `T-18`, `T-83`, `T-89` |

**Cobertura:** 50 de 50 critérios de aceite. Cinco (`AC-45` a `AC-49`) são
cobertos por teste `xfail(strict=True)` até a entrega do slug `motor-calculo`,
conforme §9 do plano.

### Cobertura dos casos de borda — Rodada 1

| `EC-NN` | Tarefas | | `EC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `EC-01` | `T-27`, `T-38`, `T-39`, `T-42` | | `EC-08` | `T-62` |
| `EC-02` | `T-13`, `T-20`, `T-42` | | `EC-09` | `T-62` |
| `EC-03` | `T-55`, `T-58` | | `EC-10` | `T-22`, `T-23` |
| `EC-04` | `T-55`, `T-58` | | `EC-11` | `T-86`, `T-88` |
| `EC-05` | `T-22`, `T-25`, `T-42`, `T-94` | | `EC-12` | `T-34`, `T-68`, `T-71` |
| `EC-06` | `T-34`, `T-55`, `T-58` | | `EC-13` | `T-35` (encaixe; política é `PEND-01`) |
| `EC-07` | `T-62` | | `EC-14` | `T-23`, `T-91`, `T-93` |

### Cobertura de requisitos — Rodada 3

| Requisito | Tarefas |
| --------- | ------- |
| `RF-45` — página única que nunca avalia `condicao_exibicao` | `T-122`, `T-123`, `T-126`, `T-128` |
| `RF-46` — a rota `GET` de coleta que não existia | `T-123` |
| `RF-47` — máscara por `TipoResposta`, formata sem corrigir | `T-125`, `T-127`, `T-129` |
| `RF-48` — máscara inerte com `nao_sei` marcado | `T-125`, `T-127`, `T-129` |
| `RF-49` — caminho nativo sem JavaScript preservado | `T-124` |

**Cobertura (Rodada 3):** 5 de 5 requisitos. Nenhum ficou sem tarefa.

`T-129` acrescenta verificação em **navegador real** a `RF-47`/`RF-48`: até
ela, `T-127` provava o contrato entre a máscara e a fronteira de conversão,
mas nada provava que `mascaras.js` implementa as regras declaradas.

### Cobertura dos critérios de aceite — Rodada 3

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-72` | `T-123` | | `AC-76` | `T-125`, `T-127` |
| `AC-73` | `T-126` | | `AC-77` | `T-125`, `T-127` |
| `AC-74` | `T-123` | | `AC-78` | `T-125` |
| `AC-75` | `T-125`, `T-127` | | `AC-79` | `T-124` |

**Cobertura (Rodada 3):** 8 de 8 critérios de aceite.

### Cobertura dos casos de borda — Rodada 3

| `EC-NN` | Tarefas | | `EC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `EC-21` | `T-124` | | `EC-23` | `T-123` |
| `EC-22` | `T-125` | | `EC-24` | `T-123` |

**Cobertura (Rodada 3):** 4 de 4 casos de borda.

> **`T-130` não abre linha nova nestas tabelas, e isso é deliberado.** Ela
> corrige um defeito contra critérios que já existiam desde a **Rodada 1** —
> `AC-06`, `EC-01`, `EC-02` e a NFR de acessibilidade —, cuja cobertura de
> tarefa já está registrada nas tabelas daquela rodada (`T-13`, `T-20`,
> `T-42`, `T-48`). Inventar `AC-NN` novo para um comportamento que a spec já
> exigia seria maquiar a falha como escopo novo.
>
> O que mudou é a **força** da verificação: até `T-129` esses critérios eram
> provados só na camada HTTP, e passavam. `T-130` acrescenta a prova em
> navegador real — onde falhavam. As tabelas da Rodada 1 seguem válidas;
> ganharam uma segunda testemunha.

> **`OQ-26` e `OQ-27` seguem abertas** e estão registradas em `T-128` como
> decisão do especialista — nenhuma delas bloqueia a implementação desta
> rodada, e nenhuma é decidida por quem implementa. **`OQ-28` foi respondida
> por `T-144`** (o caminho HTML foi removido), e o custo dessa resposta —
> a perda do funcionamento sem JavaScript — abriu `OQ-29`.

### `T-144` — Remoção do Jinja2 e migração dos testes para JSON

- **Tipo:** `REFACTOR`
- **Dependências:** `T-143`
- **Rastreia:** `RF-45`, `RF-50`, `RF-51`, `RF-52`, `AC-73`, `OQ-28`, `OQ-29`
- **Arquivos:** `app/http/rotas_coleta.py`, `app/http/rotas_pergunta.py`,
  `app/http/rotas_revisao.py`, `app/http/rotas_api_plano.py`,
  `app/http/rotas_calculo.py`, `app/http/serializacao.py`,
  `app/http/serializacao_plano.py`, `report/templates/` (removidos),
  `app/http/estaticos/` (removidos), `frontend/tests/e2e/coleta.spec.ts`

**Descrição**

Com as telas em React, os templates Jinja2 do aluno, do revisor e do
operador ficaram sem quem os renderizasse. Esta tarefa removeu o que
sobrou e migrou a suíte de asserções sobre markup para asserções sobre os
campos do JSON — a mesma garantia, na camada onde ela hoje vive.

**Três defeitos reais encontrados no caminho**, nenhum deles previsto:

1. `_buscar_caso_e_snapshot_mais_recente` chamava `historico(caso_id)`.
   Aquele método é indexado pelo `SNAPSHOT_ID` da RAIZ (`OQ-11`), nunca
   pelo `CASO_ID` — devolvia vazio sempre, e **toda decisão de revisão
   respondia `404`**. Corrigido para `caso.snapshot_raiz_id`, o idioma que
   os outros 19 chamadores já usavam.
2. `GET /api/revisao/caso/{id}` exigia `snapshot_liberado_id`, deixando a
   tela de comparação vazia exatamente para os casos em
   `AGUARDANDO_REVISAO` — os únicos que o revisor precisa comparar.
3. A rota de progresso do cálculo herdou o prefixo `/api` do roteador de
   conta e mudou de URL sem que ninguém pedisse, quebrando o polling.

**Critérios de aceite**

- [x] Nenhum `TemplateResponse` fora de `report/templates/plano/` (fonte do
      PDF, preservada: `RF-21`/`AC-14` exigem a redação canônica num lugar só)
- [x] `VARIAVEL_GRAVADA` deixa de atravessar a fronteira HTTP — o cliente
      identifica a pergunta por `ID` e o servidor resolve a variável
- [x] `AC-73` continua travado, agora auditando `frontend/src/` contra os
      291 enunciados REAIS em vez de um limiar de comprimento
- [x] `EC-01`, `EC-02` e navegação por teclado portados para
      `frontend/tests/e2e/coleta.spec.ts` ANTES de remover os originais
- [x] O tripwire de "navegador real precisa existir" reaponta para a suíte
      do frontend, em vez de ser apagado
- [x] Gates: ruff, mypy 318 arquivos, tsc, 28 unitários, 20 E2E

**Status:** `[x] concluída`

**O que esta tarefa NÃO fez.** `GET /caso/{id}/plano` (HTML) continuou
existindo por decisão de escopo — 19 chamadas em 6 arquivos de teste, e ela
não conflitava com a rota JSON. **`T-145` removeu essa rota**, junto com o
restante do Jinja2 de tela, quando o especialista decidiu que JavaScript
obrigatório é aceitável para a persona (`OQ-29`).


### `T-145` — Migração total para React: fim do HTML de tela

- **Tipo:** `REFACTOR`
- **Dependências:** `T-144`
- **Rastreia:** `RF-20`, `RF-21`, `RF-50`, `AC-04`, `AC-14`, `AC-25`, `AC-70`,
  `EC-07`, `OQ-09`, `OQ-29`
- **Arquivos:** `app/http/rotas_plano.py`, `app/http/rotas_api_plano.py`,
  `app/http/mensagens_de_estado.py` (novo), `app/http/aplicacao.py`,
  `app/http/estaticos/` (removido), `report/templates/plano/aguardando.html`
  (removido), `frontend/src/telas/TelaPlano.tsx`,
  `frontend/tests/e2e/plano.spec.ts` (novo)

**Descrição**

`OQ-29` foi respondida pelo especialista: *"a maior parte será preenchida no
computador, isso não é uma preocupação"*. Com JavaScript obrigatório
aceito, o último HTML de tela saiu.

**O que foi removido:** `GET /caso/{id}/plano` (HTML), a montagem
`/estaticos` (servia `htmx.min.js`/`mascaras.js`/`estilo.css`, todos já
sem consumidor), `aguardando.html`, e sete `Jinja2Templates` que apontavam
para diretórios apagados — código morto que só não quebrava porque nada o
chamava.

**O que ficou, e por quê.** `report/templates/plano/` gera o **PDF** por
WeasyPrint. `OQ-09` está respondida — *"ambos: tela dentro do app e PDF
exportável"* —, e o PDF é um arquivo para guardar, não uma tela. Não há
duplicação de redação: `textos-canonicos.yaml` é lido pelo serializador
JSON e pelo template do PDF pela MESMA `carregar_textos_canonicos`.

**Dois defeitos reais encontrados no caminho:**

1. A rota JSON do plano usava `rotas_coleta_dirigida.obter_repositorio_
   snapshots`, enquanto a de PDF usava `rotas_plano.obter_repositorio_
   snapshots`. Num teste que sobrescreve só um dos dois, o aluno veria um
   plano que o PDF não confirma. Unificados no ponto de `rotas_plano`.
2. A mensagem por estado do caso (`AC-25`) existia só no caminho HTML: a
   rota JSON devolvia "Nenhum plano liberado ainda." para qualquer estado.
   O aluno em revisão lia uma negativa em vez de "seu plano está em
   revisão". Extraída para `app/http/mensagens_de_estado.py`, com `match`
   exaustivo — um estado novo sem mensagem não compila.

**Uma lacuna de cobertura que a migração expôs.** A auditoria de contraste
WCAG media `estilo.css`, que nenhuma tela usava mais; as cores reais estão
nos tokens do Tailwind. Reapontada para `frontend/tailwind.config.js`, com
sete pares auditados (era três). Mesma coisa com o lint de 360px, agora
sobre `frontend/src/index.css`.

**Critérios de aceite**

- [x] Nenhum `TemplateResponse`/`Jinja2Templates` em `app/` — só o PDF em
      `report/pdf.py`
- [x] `AC-14` provado por igualdade EXATA dos campos do JSON **e** do HTML
      do PDF, ambos contra `carregar_textos_canonicos()`
- [x] `AC-25` devolve a mensagem DAQUELE estado, não um texto único
- [x] `OQ-09`: o PDF é alcançável pela tela (`<a href>` na `TelaPlano`) —
      antes só existia digitando a URL
- [x] Auditorias de contraste e de 360px reapontadas para o CSS real, com
      mutation check confirmando que mordem
- [x] Gates: ruff, mypy 317 arquivos, tsc, 28 unitários, 36 E2E

**Status:** `[x] concluída`


---

## Entrega 12 — Navegação fiel ao protótipo (Rodada 5)

> **`T-149` a `T-152` são uma transação.** A barra de abas morre em `T-149`, e
> os 18 blocos `test` E2E que dependem dela quebram no mesmo instante. Nenhuma
> das quatro é declarável concluída isoladamente: a suíte E2E só volta ao verde
> ao final de `T-152`. Declarar `T-149` pronta com os E2E vermelhos violaria a
> regra 5 do `CLAUDE.md`.
>
> `T-146`, `T-147` e `T-148` são independentes entre si e podem vir em qualquer
> ordem.

### `T-146` — As cinco fases e o contador da coleta

- **Tipo:** `FEATURE`
- **Dependências:** —
- **Rastreia:** `RF-61`, `RF-62`, `AC-89`, `AC-90`, `EC-25`
- **Arquivos:** `app/casos/fases.py` (novo), `app/casos/progresso.py`,
  `tests/app_aluno/test_fases.py` (novo), `tests/app_aluno/test_progresso.py`

**Descrição**

Dois módulos puros, sem I/O e sem FastAPI, na disciplina de
`mensagens_de_estado.py`.

**`fase_do_estado(estado) -> FASE_INICIO`** mapeia os 12 membros de
`ESTADO_CASO` nas 5 fases do protótipo (`coleta`, `revisao`, `reprovado`,
`plano`, `acompanhamento`). `match` **exaustivo, sem `case _`** — a trava que
faz um membro novo sem fase falhar no `mypy`. A tabela completa está em
`plans/app-aluno.plan.md` §R5.1.

Nenhuma fase nova: `ENCERRADO` é `acompanhamento` com ações vazias,
`ERRO_DE_CALCULO` é `revisao` (o erro técnico nunca chega ao aluno).
`PLANO_LIBERADO` é a única exceção a "fase é função do estado" — depende do
snapshot, via `bloco_10_alcancavel`, que já existe. **Nenhum limiar novo**
(`RF-34`); a exceção fica no docstring.

**`contar_coleta(...) -> ContagemDeColeta`** dá o `62 de 195` da barra.
`pendencias_obrigatorias` devolve o que falta; aqui é preciso `respondidas` e
`total`.

> ⚠️ **Extraia `_ocorrencias_abertas` PARAMETRIZADO, não ingênuo.** As duas
> varreduras de `progresso.py` divergem de propósito em dois eixos
> (elegibilidade `OBR`-vs-qualquer, e "é por item" `Obrigatoriedade.REP`-vs-
> `escopo_repeticao`), e a docstring de `_pergunta_em_branco` (`:434-445`)
> registra por quê: os Blocos 7, 8 e 11 são repetíveis por item **sem** o membro
> `REP`. Um gerador que fixe um dos predicados quebra `AC-11` ou `AC-01`.
> Assinatura: `(registros, respostas, itens_por_escopo, *, elegivel, e_por_item)`.
> `contar_coleta` usa os predicados de **retomada**: a barra conta o que o aluno
> vê, não o que bloqueia o avanço.

`total` conta só as perguntas **abertas agora**. O denominador varia conforme o
aluno responde, e isso é correto — exibir 195 quando 80 nunca abrirão mentiria
sobre o trabalho restante.

**Critérios de aceite**

- [x] `AC-89`: um membro novo de `ESTADO_CASO` sem fase **falha** no `mypy`
      (verificado por mutação, não por leitura)
- [x] Os 12 membros têm fase, e o teste os enumera a partir do enum — nunca de
      uma lista transcrita
- [x] `EC-25`: `CALCULANDO`, `ERRO_DE_CALCULO` e `ENCERRADO` têm fase e
      mensagem, nenhum cai em branco
- [x] `PLANO_LIBERADO` devolve `plano` com ataque recomendado > 0 e
      `acompanhamento` com zero — sem nenhum limiar escrito nesta tarefa
- [x] `AC-90`: `respondidas + faltam == total` sobre os registros reais
- [x] `proxima_pergunta_nao_respondida` e `pendencias_obrigatorias` continuam
      com o comportamento de hoje (não-regressão explícita das duas)
- [x] Nenhum teste novo afirma `245` registros — a coleção tem **247**
- [x] Gates: ruff, mypy, pytest

**Status:** `[x] concluída`

---

### `T-147` — `GET /caso/{CASO_ID}/inicio`

- **Tipo:** `FEATURE`
- **Dependências:** `T-146`
- **Rastreia:** `RF-58`, `RF-60`, `AC-81`, `AC-88`, `AC-74`
- **Arquivos:** `app/http/rotas_inicio.py` (novo), `app/http/aplicacao.py`,
  `tests/app_aluno/test_rotas_inicio.py` (novo)

**Descrição**

A rota que alimenta a tela Início: lê a fase e devolve **uma** próxima etapa.
Payload em `plans/app-aluno.plan.md` §R5.4.

Arquivo próprio — `rotas_etapas.py` trata da abertura das etapas pós-plano,
assunto diferente. Quatro pontos de injeção em funções próprias
(`obter_*_do_inicio`), no padrão de `rotas_operador.py:84-111`, para que os
testes sobrescrevam por `app.dependency_overrides` sem `DATABASE_URL`.

Os quatro insumos de `consultar_trilha_de_progresso` são os que
`rotas_api_plano.py:239-247` já monta — **essa rota é o template**, só que para
um `CASO_ID` da URL em vez de um laço.

> ⚠️ **`obter_repositorio_snapshots` vem de `rotas_plano.py:90`, nunca de
> `rotas_coleta_dirigida.py:98`.** Foi o defeito nº 1 corrigido em `T-145`:
> pontos de injeção diferentes fazem a tela e o PDF lerem de repositórios
> distintos num teste que sobrescreve só um dos dois. Aqui faria a tela Início
> discordar do plano que ela anuncia.

> ⚠️ **`Depends(exigir_caso_da_sessao("CASO_ID"))` não é boa prática, é
> obrigação.** `test_mecanismo_isolamento.py` enumera as `APIRoute` e reconhece
> o par `CASO_ID` + subdependência de `app.http.isolamento`. Sem isso o teste
> falha no registro da rota.

**O número nunca entra na frase.** `rotulo` genérico, `valor_em_destaque` como
string separada (`RF-13` + Lei nº 3). Reuse `mensagem_do_estado_do_caso` e
`bloco_10_alcancavel`; não reimplemente nenhum dos dois.

**Critérios de aceite**

- [x] `AC-81`: um caso em cada uma das 5 fases devolve exatamente **uma**
      `proxima_etapa`, e a fase corresponde ao estado
- [x] `AC-88`: na fase `plano`, o valor vem em `valor_em_destaque` como string, e
      o `rotulo` **não** contém o número
- [x] `AC-74`: a rota aparece na auditoria de isolamento com
      `exigir_caso_da_sessao`; conta alheia recebe `404` idêntico ao de caso
      inexistente
- [x] Todo valor monetário do payload é `str`, nunca `float` (`RF-13`)
- [x] Os testes rodam sem `DATABASE_URL`, por `dependency_overrides`
- [x] Gates: ruff, mypy, pytest

**Status:** `[x] concluída`

---

### `T-148` — `e_revisor` no login e a posição na ficha

- **Tipo:** `FEATURE`
- **Dependências:** —
- **Rastreia:** `RF-59`, `RF-63`, `AC-92`
- **Arquivos:** `app/http/rotas_api_conta.py`, `app/http/serializacao.py`,
  `app/http/rotas_pergunta.py`, `tests/app_aluno/test_rotas_conta.py`,
  `tests/app_aluno/integracao/test_rotas_conta.py`,
  `tests/app_aluno/test_serializacao.py`

**Descrição**

Duas mudanças aditivas de payload, independentes uma da outra.

**(a) `e_revisor` no login.** O campo já existe em
`persistencia/app_aluno/contas.py:81-93` e `exigir_papel_revisor` o consulta a
cada requisição. Esta tarefa apenas o acrescenta ao payload de
`/api/conta/login` e `/api/conta/cadastro`.

**Não** guardar na sessão: `sessao.py` grava só `conta_id`, por design
(`isolamento.py:186-189` é explícito de que a consulta é sempre contra o banco).
O campo serve **apenas** para a interface decidir o que oferecer; a autorização
segue inteiramente no servidor. Esconder um botão não é controle de acesso.

**(b) `posicao` e `total_na_ficha`** (`RF-63`, de `OQ-30` respondida). O
localizador do protótipo diz *"Dívida 3 · pergunta 4 de 12"*, e hoje o payload
não tem a posição. A contagem é do servidor — ele conhece o conjunto de
perguntas exibíveis da ficha; o cliente só formata. Fora de ficha repetível, os
dois campos vêm nulos.

**Critérios de aceite**

- [x] `e_revisor` presente nos dois payloads, e os testes existentes de conta
      continuam passando (verificam chaves, não igualdade de dict)
- [x] `e_revisor` **não** aparece em `app/http/sessao.py`
- [x] `AC-92`: a 4ª pergunta exibível da ficha devolve `posicao=4`, e
      `total_na_ficha` conta o escopo **naquele bloco** — 12 testes em
      `tests/app_aluno/test_serializacao_posicao.py`
- [x] `e_revisor` provado nos dois payloads e **ausente da sessão** — 5 testes
      novos em `tests/app_aluno/test_rotas_conta.py`
- [x] `AC-73` continua verde: nenhum campo proibido entrou no payload
- [x] Gates: ruff, mypy, pytest

> **Dois defeitos corrigidos depois da revisão de `/sdd:review`.**
>
> **(a) O denominador da ficha somava três blocos.** `posicao_na_ficha`
> filtrava só por `escopo_repeticao`, e `DIVIDA_ID` tem 88 registros em três
> blocos: 55 no Bloco 5 (inventário), 13 no Bloco 7 e 20 no Bloco 8
> (renegociação e troca, coleta dirigida **pós-plano**). O localizador dizia
> *"pergunta 4 de 37"* a quem estava cadastrando a primeira dívida, contando
> contra ele perguntas de outra etapa da vida dele. Corrigido com filtro por
> bloco — 35 abertas no inventário. **`AC-92` também estava errado**: pedia
> `total = 12`, que nenhuma configuração produz; a spec foi corrigida junto.
>
> **(b) Os dois critérios estavam `[x]` sem teste nenhum.** Foi o achado mais
> sério da revisão, e é exatamente o mecanismo pelo qual a Rodada 4 deixou
> passar a navegação inventada: marcar concluído sem prova.
> `sdd.config.md` §8 exige "testes correspondentes existem e passam". Os 17
> testes que faltavam foram escritos — e o defeito (a) só apareceu porque
> agora eles existem.

**Status:** `[x] concluída`

---

### `T-149` — A casca de tela e o roteador por hash

- **Tipo:** `REFACTOR`
- **Dependências:** `T-147`
- **Rastreia:** `RF-57`, `AC-82`, `AC-84`, `AC-85`, `AC-86`, `AC-91`, `EC-26`,
  `EC-27`
- **Arquivos:** `frontend/src/navegacao.ts` (novo),
  `frontend/src/componentes/Tela.tsx` (novo), `frontend/src/App.tsx`,
  `frontend/src/index.css`, `frontend/tests/unit/navegacao.test.ts` (novo)

**Descrição**

**A barra de sete abas morre aqui.** No lugar, o roteador por hash e a casca de
três partes.

`navegacao.ts` exporta `Rota` como união discriminada (o `switch` do `App.tsx`
fica exaustivo por tipo) e `useRota()`. Replica do protótipo (`go()`, linha
~820) os três comportamentos de acessibilidade que hoje não existem: foco no
`<h1>`, `scrollTo(0,0)`, `document.title`.

**Sem `react-router`** — a justificativa contra a dependência está em
`plans/app-aluno.plan.md` §R5.2, e `sdd.config.md` §6 exige que ela esteja
escrita.

> ⚠️ **`history.pushState` NÃO dispara `popstate`.** `irPara` precisa emitir um
> `CustomEvent('piq:navegou')` e o hook escutar **os dois** eventos. Errar isso
> produz *"o botão não faz nada, mas a URL muda"* — o bug mais provável desta
> reescrita.

`Tela.tsx` implementa `.top` / `.corpo` / `.acoes` com a interface de §R5.5.
Quatro detalhes obrigatórios: `<span />` vazio quando não há voltar; `<h1
className="sr-only">` quando o título não é visível; `useEffect` com `[titulo]`,
não `[]`; e `form="form-entrada"` para o submit que sai do `<form>`.

As classes CSS saem dos valores **literais** do protótipo (linhas 71–160) — não
arredonde. `.wide`/`max-w-equipe` usa `max-width`, nunca `width`
(`test_css_360px.py` recusa `width` acima de 360px). Definir também `.nota` e
`.field`, hoje usadas no JSX e **inexistentes** no CSS.

**Critérios de aceite**

- [x] Nenhuma barra de navegação global em `App.tsx` — `AC-83`
- [x] `AC-84`: navegar foca o `<h1>`, rola ao topo e atualiza o título
- [x] `AC-86`/`EC-27`: o voltar do navegador funciona
- [x] `AC-91`/`EC-26`: hash desconhecido cai em `#inicio`, não em tela branca
- [x] `.field` e `.nota` definidas; nenhuma classe usada no JSX sem definição
- [x] `test_css_360px.py` continua verde
- [x] Gates: tsc, vitest, `npx vite build`
- [x] `T-152` fechou a transação: 62 casos E2E passando nos 2 projects

> **Dois defeitos corrigidos depois da revisão de `/sdd:review`.**
>
> **(a) `AC-84` não valia no caminho mais longo da coleta.** O efeito de foco
> da casca dependia de `[titulo]`, e numa ficha repetível o enunciado é o
> **mesmo** para todos os itens: `B5.A01` ("Para quem você deve nessa
> operação?") não tem interpolação. Passar da dívida `D001` para a `D002` não
> mudava o título, o efeito não disparava, e quem usa leitor de tela respondia
> a dívida 2 ouvindo a pergunta da dívida 1 — na ficha, que é 88 registros ×
> N dívidas. A casca ganhou a prop `chave` (`${ID}/${item_id}`), e o efeito
> depende de `[chave, titulo]`.
>
> **(b) A rota `acao` era tipada, roteada e não implementada** —
> `case 'acao'` renderizava a **lista** de ações, ignorando `acaoId`. Quem
> lesse o `switch` concluiria que existia. O membro foi removido da união até
> a tela existir; a exaustividade por tipo volta a ser trava de verdade.
>
> O mapa morto `TITULO_DA_TELA` (duas fontes de verdade para o título, já
> divergentes) também saiu — registrado em `plans/app-aluno.plan.md` §R5.2.

**Status:** `[x] concluída`

---

### `T-150` — As telas que faltam

- **Tipo:** `FEATURE`
- **Dependências:** `T-149`
- **Rastreia:** `RF-58`, `RF-53`, `AC-29`, `AC-83`, `EC-25`
- **Arquivos:** `frontend/src/telas/TelaInicio.tsx`, `TelaProgresso.tsx`,
  `TelaCalculando.tsx`, `TelaAguardando.tsx`, `TelaRecalculo.tsx`,
  `TelaEquipeCaso.tsx` (todas novas),
  `frontend/src/services/api.ts`, `frontend/src/tipos.ts`

**Descrição**

| Tela | Fonte no protótipo | Consome |
| --- | --- | --- |
| `TelaInicio` | `renderInicio`, ~917 | `GET /caso/{id}/inicio` |
| `TelaProgresso` | `#progresso`, ~272 | mesmo payload |
| `TelaCalculando` | `#calculando`, ~490 | `GET /caso/{id}/calculo/progresso` |
| `TelaAguardando` | `#aguardando`, ~505 | `GET /caso/{id}/inicio` |
| `TelaRecalculo` | `#recalculo`, ~633 | — |
| `TelaEquipeCaso` | `#equipe-caso`, ~679 | `GET /api/revisao/caso/{id}` + `POST /revisao/caso/{id}/decisao` |
| ~~`TelaAcao`~~ | `#acao-status` + `#acao-info`, ~586 | **não entregue** — ver `T-156` |

**`TelaEquipeCaso` é a que mais falta.** As duas rotas já existem e devolvem
`{plano, estado_inputs, fila}` lado a lado (`AC-29`), mas **nenhuma tela as
consome**: hoje o revisor não tem como liberar um plano pela interface.

`TelaInicio` é o centro: cinco ramos por fase, **uma** próxima etapa cada. O
`valor_em_destaque` é composto **aqui**, não no servidor.

Os cinco rótulos de `TelaProgresso` ("Seu compromisso", "Como você controla os
gastos"…) vêm do protótipo **verbatim**. As contagens 16/15/57/49/58 são reais.

`.pulse` e `@keyframes spin` entram — a tela `calculando` é produto, não
andaime. Traga junto o `@media (prefers-reduced-motion: reduce)`.

**Critérios de aceite**

- [x] `TelaInicio` mostra exatamente uma próxima etapa em cada uma das 5 fases
- [x] `EC-25`: `CALCULANDO`/`ERRO_DE_CALCULO`/`ENCERRADO` mostram estado e o que
      esperar — nunca tela vazia, nunca o erro técnico
- [x] `AC-29`: `TelaEquipeCaso` mostra plano e `estado_inputs` lado a lado e
      registra a decisão com as 6 classificações
- [x] `prefers-reduced-motion` desliga a animação
- [x] `AC-29` de fato alcançável: a fila abre a conferência (`abrirCaso`), e o
      Início oferece a fila a quem é revisor — provado em navegador real
- [x] Gates: tsc, vitest
- [x] `T-152` fechou a transação: suíte E2E verde

> **Três defeitos corrigidos depois da revisão de `/sdd:review`.**
>
> **(a) `TelaEquipeCaso` era inalcançável.** A tela existia, as rotas
> existiam desde `T-70`/`T-72`, e a fila não tinha botão para abri-la — o
> revisor via a lista e não podia agir sobre ela. Era a lacuna que `T-150`
> existia para fechar, e ela seguia aberta em outro ponto. Corrigido com
> `abrirCaso` na fila e uma porta para a área da equipe no Início.
>
> **(b) `TelaAguardando` afirmava algo falso.** Dizia *"Seu plano foi
> calculado"* fixo, texto copiado do protótipo (linha 422), onde aquela tela
> só era alcançável de `AGUARDANDO_REVISAO`. Com o mapa de `RF-61`,
> `ERRO_DE_CALCULO` cai na mesma fase e no mesmo destino — e para esse aluno o
> cálculo **falhou**. Agora o cabeçalho é a `mensagem` do servidor.
>
> **(c) `TelaProgresso` misturava duas contagens.** Comparava `respondidas`
> (dinâmico: 172 com três dívidas) com os totais estáticos dos blocos (195)
> para marcar "Feito" por parte. Exibia dois números incoerentes na mesma
> tela, e marcava "Seu compromisso" como concluída quando o aluno respondia
> 16 campos de **dívida**. A tela passou a mostrar só o total do servidor;
> progresso por parte virou `OQ-31`, porque exige dado que nenhuma rota expõe.

**Status:** `[x] concluída`

---

### `T-151` — As dez telas existentes passam a usar a casca

- **Tipo:** `REFACTOR`
- **Dependências:** `T-149`
- **Rastreia:** `RF-57`, `RF-59`, `AC-82`, `AC-87`
- **Arquivos:** os 10 de `frontend/src/telas/`

**Descrição**

Toda tela existente passa a usar `<Tela>`: ganha `.top` com voltar e
localizador, `.acoes` sticky, e perde o layout solto atual.

`TelaRevisao` e `TelaOperador` passam a `largura="equipe"` (900px) e a rotas
próprias, fora da navegação do aluno (`RF-59`).

`TelaPergunta` ganha a barra `.bar` e o localizador *"Dívida 3 · pergunta 4 de
12"* a partir de `posicao`/`total_na_ficha` (`T-148`). É também a única tela
sem `<h1>` hoje — ganha o `sr-only`.

`TelaLogin` move o submit para `acoes` e precisa do par
`id="form-entrada"`/`form="form-entrada"`, senão o Enter para de funcionar.

**Critérios de aceite**

- [x] `AC-82`: toda tela tem `.top` com voltar (exceto Início) e `.acoes` fixo
- [x] `AC-87`: as telas de equipe usam 900px
- [x] Enter continua submetendo o login
- [x] `VARIAVEL_GRAVADA` não vaza para `frontend/src/`
      (`test_sem_condicional_no_javascript.py`)
- [x] Gates: tsc, vitest
- [x] `T-152` fechou a transação: suíte E2E verde

**Status:** `[x] concluída`

---

### `T-152` — Migrar os E2E e provar o modelo novo

- **Tipo:** `TEST`
- **Dependências:** `T-150`, `T-151`
- **Rastreia:** `AC-80`, `AC-81`, `AC-84`, `AC-85`, `AC-86`, `AC-87`, `AC-91`
- **Arquivos:** `frontend/tests/e2e/apoio/navegacao.ts` (novo),
  `frontend/tests/e2e/coleta.spec.ts`, `frontend/tests/e2e/plano.spec.ts`,
  `frontend/tests/e2e/navegacao.spec.ts` (novo)

**Descrição**

**Esta tarefa fecha a transação aberta em `T-149`.** Os 18 blocos `test` (10 em
`coleta.spec.ts`, 8 em `plano.spec.ts` — 36 casos em 2 projects) clicam em
`getByRole('button', {name: 'Coleta'|'Dívidas'|'Plano'})` e quebram quando a
barra morre.

A navegação é centralizada em `apoio/navegacao.ts` (`abrirTela`,
`acaoPrincipal`, `interceptarBase`), não espalhada pelos testes — assim a
próxima mudança de navegação é uma edição em um arquivo.

> ⚠️ **Todo `beforeEach` que abre uma tela intercepta `/inicio`**, mesmo que o
> teste não o verifique. Sem intercept, o proxy do Vite falha e o teste trava
> até o timeout.

> ⚠️ **`coleta.spec.ts` não pode ser renomeado nem movido** —
> `test_acessibilidade_plano.py:340` exige o arquivo naquele caminho. Migre o
> conteúdo, mantenha o nome.

**O teste de teclado melhora.** Hoje tabula até 20 vezes porque a barra polui o
caminho (o comentário em `coleta.spec.ts:237` diz isso). Sem a barra, a ordem
vira `.back` → campo → `Continuar`. **Baixe o limite para 5: o limite baixo
passa a ser a asserção.** Preserve o `campo.focus()` inicial e a comparação
estrita com `'Continuar'`.

Garantias que não podem se perder: `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-25`,
`AC-70`, `AC-75`, `AC-76`, `AC-78`, `EC-01`, `EC-02`, `EC-07`, `EC-22`, `RF-52`.

Testes novos: os sete da tabela de §R5.6.

> Investigar antes de migrar: `frontend/test-results/` indica que o teste de
> `EC-07` (`plano.spec.ts:176`, project `desktop`) falhou na última execução.

**Critérios de aceite**

- [x] Os 18 blocos migrados passam, nos 2 projects
- [x] Os 7 testes novos existem e passam
- [x] O teste de teclado usa limite 5 e passa
- [x] Nenhum seletor de navegação fora de `apoio/navegacao.ts`
- [x] `coleta.spec.ts` segue existindo no mesmo caminho
- [x] Gates: playwright, e **a suíte inteira volta ao verde** — `T-149` a `T-152`
      só são declaráveis concluídas aqui

**Status:** `[x] concluída` — 25 blocos `test` (10 `coleta` + 8 `plano` +
7 `navegacao`), 58 casos nos 2 projects, todos verdes. O `EC-07` que a nota
acima reportava vermelho passou a passar sem mexer no teste: a falha era da
casca antiga (`<h2>Plano</h2>` em vez do heading de `EC-07`), corrigida em
`T-150`.

---

### `T-153` — Esconder a área da equipe por papel

- **Tipo:** `FEATURE`
- **Dependências:** `T-148`, `T-152`
- **Rastreia:** `RF-59`, `AC-80`
- **Arquivos:** `frontend/src/App.tsx`, `frontend/src/services/api.ts`,
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

Com `e_revisor` no payload de login (`T-148`), a interface deixa de oferecer o
caminho para a fila, a conferência e o painel a quem não é revisor.

**A autorização não muda** — ela já está no servidor, reverificada a cada
requisição. Esta tarefa é sobre não bater numa porta fechada: o aluno que vê
"Fila" e recebe `403` conclui que o sistema está quebrado, ou que há algo dele
que não consegue ver.

Implementado junto com `T-149`: `eTelaDaEquipe(rota) && eRevisor !== true`
redireciona para o Início, por `substituirRota` (não `irPara`) para que o
"voltar" do navegador não reapresente o passo negado.

> ⚠️ **Lacuna conhecida, declarada — não resolvida aqui.** `e_revisor` vive em
> estado de componente, então **um revisor que recarrega a página perde o
> acesso às suas próprias telas** até entrar de novo. Negar por omissão é o
> lado certo do erro (o contrário abriria tela de equipe para quem não
> deveria), mas o revisor real vai sentir isso no piloto.
>
> A causa raiz é a mesma de `T-154`: não existe `GET /api/conta/eu`, então o
> cliente não tem como perguntar ao servidor quem ele é depois de um reload.
> Guardar `e_revisor` em `localStorage` foi **descartado**: seria estado de
> autorização cacheado no cliente, exatamente o que `isolamento.py` evita ao
> reconsultar o banco a cada requisição — e daria a impressão de que a
> interface sabe algo que ela não pode saber.
>
> **`T-154` fechou isso.** `GET /api/conta/eu` responde quem é a sessão e qual
> é o caso dela, lendo `e_revisor` do banco a cada chamada — o revisor
> recarrega a página e continua revisor, e revogar alguém tem efeito na
> requisição seguinte em vez de quando o cookie expirar.

**Critérios de aceite**

- [x] `AC-80`: com `e_revisor: false`, **nenhum** elemento do DOM referencia rota
      de equipe — auditado no DOM, não só no servidor
- [x] Com `e_revisor: true`, as três telas são alcançáveis
- [x] O servidor continua devolvendo `403`/`404` independentemente do que a
      interface mostra (teste de não-regressão)
- [x] Gates: tsc, vitest e playwright verdes
- [x] **Persistência do papel entre recargas** — fechada por `T-154`:
      `GET /api/conta/eu` devolve `e_revisor` lido do banco, e `App.tsx` o
      consulta na carga da página. O teste prova que revogar o papel tem
      efeito na requisição seguinte, sem tocar na sessão

**Status:** `[x] concluída`

---

### `T-154` — Descoberta do caso após o login

- **Tipo:** `FEATURE`
- **Dependências:** —
- **Rastreia:** `RF-02`, `RF-58`
- **Arquivos:** a decidir

**Descrição**

**Lacuna encontrada durante o levantamento da Rodada 5, registrada como tarefa
em vez de resolvida em silêncio** (`CLAUDE.md`, regra 4).

`POST /api/conta/login` devolve `{email, conta_id}` — **sem `CASO_ID`**. Só o
cadastro devolve. E não existe `GET /api/conta/eu`. Depois de um login, o
cliente não tem como descobrir o caso pelo backend: hoje ele vem de `?caso=` na
URL, o que funciona por link profundo e falha por digitação.

`/inicio` **não** resolve isso — ela própria exige `CASO_ID` no path.

Duas saídas: acrescentar `CASO_ID` ao payload do login, ou criar
`GET /api/conta/eu`. A segunda é mais geral (serve o `e_revisor` e futuros
campos de sessão) e não muda o contrato de uma rota existente.

**Não faz parte da Rodada 5** e não bloqueia nenhuma tarefa dela.

**Critérios de aceite**

- [x] A decisão entre as duas saídas está registrada antes da implementação
- [x] Após o login, o cliente alcança a tela Início sem `?caso=` na URL

**Status:** `[x] concluída`

---

### `T-155` — Os testes E2E entram na checagem de tipos

- **Tipo:** `CHORE`
- **Dependências:** —
- **Rastreia:** `sdd.config.md` §2 (o gate `build` é a checagem de tipos)
- **Arquivos:** `frontend/tsconfig.app.json` ou `frontend/tsconfig.e2e.json`
  (novo), `frontend/package.json`

**Descrição**

**Lacuna encontrada durante `T-152`, registrada em vez de corrigida em
silêncio** (`CLAUDE.md`, regra 4).

`tsconfig.app.json` inclui só `src`; `tsconfig.node.json`, só `vite.config.ts`.
**Nenhum tsconfig cobre `frontend/tests/`** — nem os E2E, nem os unitários. Um
erro de tipo num teste entra sem ser notado, e `npx tsc --noEmit` passa verde
com o teste quebrado.

Não é teórico: os quatro arquivos de `T-152` tiveram de ser type-checkados à
mão, fora do gate, para se saber que estavam limpos.

A correção é um `tsconfig` próprio para `tests/` (ou ampliar o `include` do
existente) mais uma entrada no `package.json`. O cuidado é o ambiente: os
unitários rodam em `happy-dom`, os E2E têm os tipos do Playwright, e os dois
não compartilham `lib`.

**Não faz parte da Rodada 5** e não bloqueia nenhuma tarefa dela.

**Critérios de aceite**

- [x] `npx tsc --noEmit` (ou o script equivalente) cobre `frontend/tests/`
- [x] Um erro de tipo introduzido de propósito num teste **falha** o gate —
      verificado por mutação, não por leitura
- [x] Os gates existentes continuam verdes

**Status:** `[x] concluída`

---

### `T-156` — A tela de uma ação do Bloco 11

- **Tipo:** `FEATURE`
- **Dependências:** `T-152`
- **Rastreia:** `RF-27`, `RF-33`, `AC-46`, `AC-50`
- **Arquivos:** `frontend/src/telas/TelaAcao.tsx` (novo),
  `frontend/src/navegacao.ts`, `frontend/src/App.tsx`,
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

**Escopo que `T-150` prometeu e não entregou — declarado em vez de escondido**
(`CLAUDE.md`, regra 4).

`T-150` listava sete telas novas e entregou seis. Falta a tela de **uma ação**
(`#acao-status` + `#acao-info` do protótipo, linhas ~586–614): o aluno abre uma
ação da lista, informa em que pé ela está (`B11.01`, os seis valores de
`ACAO_STATUS`) e, se concluiu, registra o resultado pela pergunta do **tipo**
daquela ação (`B11.03-INF`/`-REN`/`-TRO`/`-ECO`).

Hoje `TelaAcoes` (a lista) resolve os dois passos no mesmo lugar, expandindo
campos inline. Funciona, mas foge da casca: o fluxo linear guiado pede uma tela
por passo, com `.top` e `.acoes`.

> A rota `{tela: 'acao'; acaoId}` **existia** em `navegacao.ts`, roteada, e
> renderizava a lista ignorando o `acaoId` — quem lesse o `switch` concluiria
> que a tela existia. Foi **removida** em vez de deixada como promessa falsa;
> esta tarefa a traz de volta junto com a tela.

**Critérios de aceite**

- [x] O membro `{tela: 'acao'; acaoId}` volta à união `Rota`, e o `switch`
      renderiza `TelaAcao` — não a lista
- [x] `AC-46`: a pergunta de resultado exibida é a do **tipo** da ação, e só ela
- [x] `AC-50`: ação de economia (sem `DIVIDA_ID`) abre normalmente
- [x] `AC-82`: a tela usa a casca, com voltar para a lista
- [x] Gates: tsc, vitest, playwright

**Status:** `[x] concluída`

---

### `T-157` — Dois testes de coleta dirigida exigem Postgres sem precisar

- **Tipo:** `CHORE`
- **Dependências:** —
- **Rastreia:** `sdd.config.md` §2 (o gate `test` precisa rodar sem banco)
- **Arquivos:** `tests/app_aluno/test_rotas_coleta_dirigida.py`

**Descrição**

**Lacuna encontrada ao rodar o gate da Rodada 5, registrada em vez de
ignorada.** Não é da rodada e não foi introduzida por ela.

`test_ac19_bloco_7_so_para_a_divida_com_renegociacao` e
`test_ordem_acoes_vazia_nao_abre_bloco_7` falham com
`psycopg.errors.ConnectionTimeout` em máquina sem Postgres local: eles
sobrescrevem alguns pontos de injeção e deixam o de **respostas** de
`rotas_coleta_dirigida.py` apontando para `RepositorioRespostasSupabase`.

Todos os outros testes de rota do slug rodam sem banco por
`app.dependency_overrides` — estes dois são a exceção, e a exceção não é
deliberada: os dois critérios que eles provam (`AC-19`) não têm nada de
integração.

O custo de deixar assim é que o gate `test` só fica verde com Docker no ar, e
quem rodar sem ele vê duas falhas vermelhas que não são dele — exatamente o
ruído que faz alguém aprender a ignorar falha de teste.

**Critérios de aceite**

- [x] Os dois testes passam **sem** `DATABASE_URL` e sem Postgres no ar
- [x] Nenhuma asserção foi afrouxada — `AC-19` continua provado
- [x] Verificado por execução com o banco desligado

**Status:** `[x] concluída`

---

## Entrega 13 — Orientação: onde estou e para onde vou (Rodada 6)

### `T-158` — A trilha da jornada e as boas-vindas

- **Tipo:** `FEATURE`
- **Dependências:** `T-152`
- **Rastreia:** `RF-64`, `RF-65`, `RF-66`, `RF-67`, `AC-93`..`AC-99`
- **Arquivos:** `frontend/src/componentes/TrilhaDaJornada.tsx` (novo),
  `frontend/src/telas/TelaBoasVindas.tsx` (novo),
  `frontend/src/telas/TelaInicio.tsx`, `frontend/src/App.tsx`,
  `frontend/src/index.css`, `frontend/src/componentes/Tela.tsx`,
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

**Origem: teste com usuário, não levantamento técnico.** Ao usar a tela Início
pela primeira vez contra o banco real, o especialista relatou: *"não gostei, me
senti perdido, sem saber o que é, qual o objetivo"*.

A tela estava **fiel ao protótipo e correta**: uma próxima etapa, "Continuar de
onde você parou", "3 de 101". O defeito não era de layout nem de dado — era de
**enquadramento**. `RF-58` respondeu *"o que eu faço agora?"* e deixou intacta a
pergunta anterior: *"onde eu estou, e onde isso vai dar?"*. E "3 de 101" não
informa nada quando o aluno não sabe 101 do quê.

**Nenhuma mudança de backend.** `GET /caso/{id}/inicio` já devolve `fase` e
`progresso` — era tudo o que faltava usar. Confirmado contra a API real antes
de escrever a primeira linha de interface.

**Duas peças:**

1. **A trilha** (`RF-64`): as cinco etapas da jornada — coleta, cálculo,
   conferência, plano, acompanhamento — sempre visíveis no Início, com a atual
   marcada e as concluídas com "Feito". Cada etapa futura diz **o que entrega**,
   que é o que responde "para que serve isto".
2. **As boas-vindas** (`RF-66`): quem tem zero respostas vê primeiro o que o
   PIQ faz. Pedir a alguém endividado que responda cem perguntas sobre o próprio
   dinheiro sem dizer para quê é pedir uma confiança que ainda não foi merecida.

**A barra de progresso do Início saiu.** Ela dizia "3 de 101" e a trilha passou
a dizer "Faltam 98 perguntas", dentro da etapa a que o número pertence — dois
lugares mostrando o mesmo progresso com redações diferentes era parte da
confusão.

> **Defeito de layout encontrado ao fotografar a tela.** Com a trilha, o Início
> ficou mais alto que a janela e o rodapé `sticky` passou a **sobrepor** o
> cartão da próxima etapa, com as letras somadas e ilegíveis. Duas causas:
> `min-h-screen` estava no wrapper em vez da coluna (o protótipo põe na
> `.screen`, linha 73), e o `.acoes` não declarava empilhamento. Corrigido com
> `min-h-screen` na coluna, `z-10` no rodapé e `scroll-padding-bottom` no
> corpo, para que o foco por teclado não pare debaixo dele.

**Critérios de aceite**

- [x] `AC-93`: as 5 etapas aparecem, exatamente uma em curso
- [x] `AC-94`: parametrizado pelas 5 fases — a etapa em curso corresponde à fase
- [x] `AC-95`: a trilha é visível sem interação, e sem rolagem horizontal a 360px
- [x] `AC-96`: o que falta vem com unidade ("Faltam 98 perguntas"), nunca só o
      número
- [x] `AC-97`: caso sem resposta vê as boas-vindas, que mencionam a conferência
      humana
- [x] `AC-98`: caso com resposta NÃO vê; "Começar" nunca bloqueia
- [x] `AC-99`: nem trilha nem boas-vindas leem `localStorage` — as duas derivam
      do estado do caso, que vem do servidor
- [x] Gates: tsc (com `tests/`), vitest, playwright — **94 casos** (eram 66)
- [x] Verificado em navegador real, contra o banco: conta com respostas vê a
      trilha, conta zerada vê as boas-vindas

> **Cobertura parcial declarada em `AC-96`.** O critério diz "no acompanhamento,
> quantas ações aguardam reporte". O texto hoje é genérico — *"Faça a próxima
> ação e conte como foi"* — porque `/inicio` **não carrega** número de ações
> pendentes, e derivá-lo no cliente exigiria pedir a lista de ações só para
> contá-la. As outras fases cumprem o critério (coleta com "Faltam N
> perguntas", revisão e plano com o que se espera). A contagem no
> acompanhamento vira `T-159`, não um extra silencioso.

**Status:** `[x] concluída`

---

### `T-159` — A contagem de ações pendentes na trilha

- **Tipo:** `FEATURE`
- **Dependências:** `T-158`
- **Rastreia:** `RF-65`, `AC-96` (a parte de acompanhamento)
- **Arquivos:** `app/http/rotas_inicio.py`, `frontend/src/tipos.ts`,
  `frontend/src/componentes/TrilhaDaJornada.tsx`

**Descrição**

**Cobertura parcial de `AC-96`, declarada em `T-158` em vez de escondida.**

`RF-65` exige que a etapa em curso diga o que falta **com unidade**. Na coleta
isso funciona ("Faltam 98 perguntas"); no acompanhamento o texto é genérico,
porque o payload de `/inicio` não tem quantas ações aguardam reporte.

Contar no cliente exigiria pedir `GET /caso/{id}/acoes` só para saber o
tamanho da lista — uma requisição inteira para exibir um número, e o cliente
contando o que é do servidor (`RF-45`). O caminho certo é o servidor mandar a
contagem, como já faz com `progresso`.

Cuidado ao implementar: **contar só o que o aluno ainda precisa reportar**, não
toda a `ORDEM_ACOES`. Uma ação concluída não "aguarda" nada, e somá-la faria a
trilha dizer que falta trabalho que já foi feito.

**Critérios de aceite**

- [ ] `/inicio` devolve a contagem de ações que aguardam reporte
- [ ] A trilha diz "N ações aguardando você" na etapa de acompanhamento, com
      singular correto
- [ ] Ação já reportada **não** entra na contagem
- [ ] Gates: ruff, mypy, pytest, tsc, playwright

**Status:** `[ ] pendente` — não iniciada nesta rodada

---

## Entrega 14 — Rever, corrigir e caber na tela (Rodada 7)

### `T-160` — Rever e corrigir as respostas dadas

- **Tipo:** `FEATURE`
- **Dependências:** `T-158`
- **Rastreia:** `RF-68`, `RF-69`, `RF-70`, `AC-100`..`AC-105`
- **Arquivos:** `app/http/rotas_respostas.py` (novo), `app/http/aplicacao.py`,
  `frontend/src/telas/TelaRespostas.tsx` (novo),
  `frontend/src/telas/TelaPergunta.tsx`, `frontend/src/App.tsx`,
  `frontend/src/services/api.ts`, `frontend/src/tipos.ts`,
  `tests/app_aluno/test_rotas_respostas.py` (novo),
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

**Origem: segundo teste com usuário.** Dois relatos, um defeito comum: *"as
perguntas que eu respondi não consigo editar"* e *"nem consigo ver o que foi
respondido, e se eu esquecer"*.

> **O backend SEMPRE permitiu as duas coisas.** `GET /caso/{id}/pergunta/{ID}`
> devolve qualquer pergunta com `valor_atual` preenchido — verificado contra o
> banco real: `B1.01` volta com `'EM_CONSTRUCAO'`, a resposta que o aluno deu.
> E a gravação aceita sobrescrita desde `T-42`. O que nunca existiu foi
> **tela**: a coleta só andava para a frente.
>
> É o mesmo padrão da Rodada 6 — o dado estava lá, a interface não o usava. E é
> o tipo de lacuna que só aparece quando alguém usa o produto de verdade,
> porque nenhum critério de aceite dizia "o aluno consegue reler o que
> respondeu". `RF-10` promete retomada **sem redigitar**; ninguém tinha
> escrito que promete **conferência**.

**A rota nova** (`GET /caso/{CASO_ID}/respostas`) agrupa pelas cinco partes e
devolve, por resposta, o **rótulo que o aluno escolheu** — nunca o
`valor_interno`. Quem respondeu "Empréstimo consignado" precisa reler
"Empréstimo consignado", não `CONSIGNADO`. Reusa
`montar_contexto_pergunta`, que é o que garante que a revisão e a coleta digam
a mesma coisa sobre a mesma resposta.

**Corrigir usa a MESMA rota de gravação** (`RF-69`). Um segundo caminho de
escrita seria uma segunda regra de validação, e `EC-01` deixaria de ser
soberano.

**Critérios de aceite**

- [x] `AC-100`: a revisão mostra pergunta + valor respondido, por parte
- [x] `AC-101`: parte sem resposta aparece dizendo isso — não some, não fica
      vazia sem explicação
- [x] `AC-102`: "Editar" abre a pergunta com o valor anterior preenchido, e
      grava pela mesma rota
- [x] `AC-103`: corrigir não aumenta o total de respondidas
- [x] `AC-104`: correção recusada mostra a mensagem do servidor e **não** apaga
      o valor anterior
- [x] `AC-105`: há caminho para a pergunta anterior; na primeira, não há
- [x] Gates: ruff, mypy, pytest (1611 passed, 75 skipped), tsc, vitest (38),
      playwright (121 passed, 1 skipped)
- [ ] Verificado em navegador real, contra o banco — **pendente**: os E2E rodam
      com a rede interceptada, e a rota já foi conferida contra o banco pelo
      especialista; o que falta é o clique humano no fluxo inteiro

**Defeito de produção encontrado e corrigido (é o cerne de `AC-102`)**

`TelaPergunta` **ignorava `idPergunta`/`itemId` da rota**: ela chamava sempre
`obterProximaPergunta`. `#pergunta/{ID}/{item}` existia desde `T-149`,
`hashParaRota` já o decodificava e `TelaInicio` já o emitia com o alvo da
retomada — e a tela abria outra pergunta, com a URL dizendo o contrário. Era
literalmente o relato *"as perguntas que eu respondi não consigo editar"*, e
nenhum teste o pegava porque todos interceptavam só `**/caso/X/pergunta`.

**Decisões não especificadas, tomadas aqui**

1. **A correção mora em `#respostas/{ID}/{item}`, não em `#pergunta/{ID}`.**
   Os dois hashes carregariam os mesmos parâmetros com destinos diferentes
   depois de gravar: a retomada segue para a próxima pergunta (coleta), a
   correção volta para a lista (`AC-103`). Um hash com dois destinos é a
   ambiguidade que `AC-91` manda evitar. A TELA é a mesma (`TelaPergunta`) nos
   dois casos — `RF-69` proíbe uma segunda via de escrita, e uma segunda tela
   de edição seria uma segunda montagem de campo.
2. **A pergunta anterior (`RF-70`) sai do payload de `/respostas`**, achatado na
   ordem em que o servidor devolve as partes e as linhas. É a ordem dos
   registros, que é a ordem que a coleta percorre. As alternativas foram
   recusadas: deduzir a ordem pelo `ID` seria o cliente reimplementando o
   questionário que ele não conhece (`RF-45`); um histórico de navegação no
   cliente diria por onde o aluno passou NESTA sessão, e `RF-10` promete
   retomada em outro aparelho, onde ele nasceria vazio.
3. **A porta da revisão fica no Início**, como segundo botão discreto, e só a
   partir da primeira resposta. Sem ela a tela só seria alcançável digitando o
   hash — a mesma morte silenciosa que as telas órfãs de `T-150` tiveram.
4. **`interceptarBase` passou a interceptar `/respostas`** com as cinco partes
   vazias, pela regra de §R5.6 do plano (toda rota que a carga de uma tela
   dispara entra lá). O padrão vazio é o que não oferece "anterior", então
   nenhum teste existente mudou de comportamento por isso.

> **Dois defeitos que só a verificação em navegador real encontrou** — os 121
> E2E estavam verdes com os dois presentes.
>
> **(a) `<details open={...}>` prendia o acordeão.** Atributo controlado sem
> handler de `onToggle`: o React o reimpunha a cada render, o clique no
> `<summary>` abria e o render seguinte fechava. A primeira parte abria (pelo
> valor inicial) e **nenhuma outra abria nunca** — numa tela feita para reler
> tudo, o aluno relia um quinto. Corrigido com `ref` que põe `open` uma vez e
> devolve o elemento ao navegador, que é o motivo de `<details>` ter sido
> escolhido.
>
> Nenhum teste pegava porque todos afirmavam sobre a parte que já nasce
> aberta. "Clicar na segunda parte a abre" não estava em critério nenhum.
>
> **(b) O rodapé `sticky` cobria o fim do conteúdo — de novo.** Mesmo defeito
> da Rodada 6, e a correção de lá (empilhamento + fundo opaco) tratava só a
> legibilidade. O que faltava era o corpo **reservar a altura** do rodapé: sem
> isso o último trecho fica atrás dele permanentemente, e rolar não revela,
> porque o rodapé rola junto. Resolvido com `.corpo:has(~ .acoes)::after` na
> casca — vale para toda tela, e some nas que não têm rodapé.
>
> `AC-85` seguia verde nas duas vezes: ele mede se o **rodapé** está visível,
> e estava. Era o conteúdo que sumia atrás dele.

- [x] **Verificado em navegador real, contra o banco**: Início → revisão →
      "Editar" → trocar a resposta → gravar → voltar à lista com o valor novo.
      A contagem seguiu "1 resposta de 16" — `AC-103`: corrigir não conta como
      responder de novo

**Status:** `[x] concluída`

---

### `T-161` — A tela cabe no computador

- **Tipo:** `REFACTOR`
- **Dependências:** `T-158`
- **Rastreia:** `RF-71`, `AC-106`
- **Arquivos:** `frontend/src/componentes/Tela.tsx`,
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

*"Por que está com a largura fixa? A pessoa vai preencher pelo computador."*

Os 560px vêm do protótipo, **desenhado para celular** — e a decisão estava
certa quando foi tomada. Mas `OQ-29` foi respondida com *"a maior parte será
preenchida no computador"*, e ninguém releu a largura à luz disso: no monitor,
cem perguntas por uma fresta no meio de uma tela vazia.

**Progressivo, nunca substitutivo.** No desktop a jornada vai para uma coluna
lateral e o conteúdo ocupa o resto; **a 360px o layout é idêntico ao
validado** — coluna única, trilha acima, sem rolagem horizontal. O protótipo
foi validado com stakeholders para a tela pequena, e é essa a tela que não
pode mudar.

Feito com utilitários responsivos do Tailwind (`lg:`), não com media query em
JS: o layout é decisão de CSS, e resolvê-lo em JavaScript o quebraria antes da
hidratação.

**Critérios de aceite**

- [x] `AC-106`: ≥1024px mostra trilha lateral + conteúdo; 360px permanece
      idêntico ao validado, sem rolagem horizontal
- [x] `tailwind.config.js` **não** foi editado (um teste Python o parseia por
      regex) — as larguras novas são classes arbitrárias (`lg:max-w-[1120px]`,
      `lg:max-w-[760px]`, `lg:w-[300px]`) no TSX
- [x] `test_css_360px.py` continua verde
- [x] Gates: tsc, vitest, playwright

**Decisões não especificadas, tomadas aqui**

1. **A trilha virou prop `lateral` da casca** (`Tela.tsx`), e saiu do corpo de
   `TelaInicio`. É a casca que conhece as duas geometrias; se cada tela
   decidisse a sua, haveria uma geometria por tela — que é contra `AC-82`. No
   celular a `lateral` continua sendo o primeiro filho do corpo, exatamente
   onde o protótipo a validou.
2. **Três larguras, não uma.** Com lateral, a coluna vai a `1120px` no desktop
   (300px de mapa + conteúdo); sem lateral, a `760px`. A tela da equipe segue
   nos `900px` que `AC-87` fixou — aquele requisito é sobre o revisor e não foi
   revogado. Nenhuma é ilimitada: linha de texto longa cansa.
3. **`AC-87` teve o teste atualizado, não afrouxado.** Ele exigia `560px`
   exatos para o aluno em qualquer viewport — o que `AC-106` revoga por
   desenho. A asserção agora se divide por viewport: `560px` a 360px (a tela
   validada, intocada) e "distinta de 560 e de 900" no desktop. O que `AC-87`
   de fato promete — duas áreas com colunas distintas, a do revisor em 900px —
   continua provado nas duas larguras.

**Status:** `[x] concluída`

---

## Rodada 8 (2026-09-19) — acabamento visual

> Rastreia `RF-72`..`RF-78` e `AC-107`..`AC-116`. Ver `plans/app-aluno.plan.md` §R8.
> **Toda tarefa desta rodada e aditiva**: nenhum token, nome de classe ou
> largura validada e alterado (`RF-78`).

### `T-162` — A escala de elevação e a hierarquia tipográfica

- **Tipo:** `FEATURE`
- **Dependências:** `T-161`
- **Rastreia:** `RF-72`, `RF-73`, `RF-78`, `AC-107`, `AC-108`
- **Arquivos:** `frontend/src/index.css`,
  `tests/app_aluno/estatica/test_tokens_intactos.py` (novo)

**Descrição**

A fundação das demais tarefas: três níveis de elevação e a escala tipográfica,
declarados uma vez em `index.css`.

**As sombras derivam de `ink` (`#1B2A2F`), nunca de preto neutro** (`AC-108`).
Não é preciosismo: preto puro sobre um fundo levemente quente (`#FAFAF7`) lê
como sujeira cinza, enquanto o mesmo valor derivado da tinta da paleta lê como
sombra. É a diferença entre parecer um bug de renderização e parecer desenho.

**Elevação por papel, não por padrão** (`RF-72`). O `.cartao` recebe o nível
mais baixo — quase imperceptível, só o suficiente para descolar do fundo. O
nível alto é exclusivo do que precisa de atenção. Se tudo flutua, nada se
destaca, e o resultado é mais plano que o ponto de partida.

**`tailwind.config.js` NÃO é editado** (`AC-107`). Todo o acréscimo vive em
`@layer components` no `index.css`, como `T-161` já fez com as larguras.

**Critérios de aceite**

- [x] `AC-107`: os 11 tokens de cor, `fontFamily`, `minHeight` e `maxWidth`
      têm nome e valor idênticos aos de antes desta rodada
- [x] `AC-108`: `--e1`/`--e2`/`--e3` existem e usam `rgba(27,42,47,…)`;
      nenhum `rgba(0,0,0` em `index.css`
- [x] `test_acessibilidade_coleta.py` e `test_css_360px.py` seguem verdes
      **sem edição**
- [x] Gates: lint, build, test

**Status:** `[x] concluída`

---

### `T-163` — Iconografia própria do PIQ

- **Tipo:** `FEATURE`
- **Dependências:** `T-162`
- **Rastreia:** `RF-74`, `AC-110`, `AC-111`
- **Arquivos:** `frontend/src/componentes/Icone.tsx` (novo),
  `frontend/public/icons.svg` (removido),
  `tests/app_aluno/estatica/test_iconografia.py` (novo)

**Descrição**

Hoje a interface tem **zero** ícones — o único símbolo é um `✓` textual dentro
da trilha. E `public/icons.svg` contém ícones de Bluesky, Discord e GitHub: é
boilerplate do template do Vite, sem uma única referência no código. Sai
(`AC-111`).

**O componente torna o uso incorreto impossível.** `Icone.tsx` emite todo SVG
com `aria-hidden="true"` e sem `<title>`, e **não expõe prop que permita o
contrário**. O motivo está em `AC-114`: `coleta.spec.ts:285` compara o nome
acessível do botão "Continuar" por igualdade estrita, e um `<title>` dentro do
SVG entraria nessa composição em alguns leitores, quebrando o teste. Deixar a
decisão para quem usa o componente é deixar a trava quebrar mais tarde.

**Ícone nunca carrega significado sozinho** (`AC-110`, WCAG 1.4.1): o rótulo
textual sempre existe ao lado. O ícone é reforço visual, nunca substituto.

O vocabulário é o do PIQ — dívida, prazo, conferência, reserva, seta de avanço,
download, escudo de versão —, desenhado aqui. Nenhuma biblioteca: seriam
centenas de ícones baixados para usar oito, num app cuja persona está em rede
instável.

**Critérios de aceite**

- [x] `AC-110`: todo `<svg>` em `frontend/src/` tem `aria-hidden="true"`,
      não é focável e convive com rótulo textual
- [x] `AC-111`: `frontend/public/icons.svg` não existe
- [x] `AC-114`: `coleta.spec.ts` verde **sem edição** — nome acessível do
      botão continua exatamente `Continuar`
- [x] Gates: lint, build, test

**Status:** `[x] concluída`

---

### `T-164` — Esqueleto de carregamento nas treze telas

- **Tipo:** `FEATURE`
- **Dependências:** `T-162`
- **Rastreia:** `RF-75`, `AC-112`, `AC-113`
- **Arquivos:** `frontend/src/componentes/Esqueleto.tsx` (novo),
  `frontend/src/telas/*.tsx` (13 telas),
  `frontend/tests/unit/componentes/Esqueleto.test.tsx` (novo)

**Descrição**

Treze telas mostram literalmente `<p role="status">Carregando…</p>`. Cada troca
de tela pisca um texto solto no canto superior, e quando os dados chegam o
layout salta.

**A árvore de acessibilidade não pode perder informação** (`AC-112`). O
esqueleto é `aria-hidden`; o `role="status"` continua existindo, com a mesma
redação que já havia. Quem usa leitor de tela recebe exatamente o que recebia —
o esqueleto é para quem enxerga, e não substitui o anúncio.

**Só o ramo de carregamento** (R8.5). As telas têm três estados — `carregando`,
`erro`, dados — e a troca acontece **apenas** no primeiro. Um esqueleto
brilhando sobre uma requisição que falhou é pior que o texto que substituiu.

**Movimento é opcional** (`AC-113`): com `prefers-reduced-motion: reduce` o
esqueleto aparece parado, como já acontece com o `.pulse` desde `T-150`.

**Critérios de aceite**

- [x] `AC-112`: esqueleto `aria-hidden`, `role="status"` preservado nas 13 telas
- [x] `AC-113`: nenhuma animação sob `prefers-reduced-motion: reduce`
- [x] Nenhum ramo de **erro** passa a mostrar esqueleto
- [x] Gates: lint, build, test

**Status:** `[x] concluída`

---

### `T-165` — Micro-interação nos controles

- **Tipo:** `FEATURE`
- **Dependências:** `T-162`
- **Rastreia:** `RF-76`, `AC-113`
- **Arquivos:** `frontend/src/index.css`

**Descrição**

Auditoria: **zero** `hover`, **zero** `transition` em todo o `src/`. O aluno não
recebe nenhuma confirmação de que o alvo está sob o cursor antes de clicar —
num app preenchido majoritariamente no computador (`OQ-29`, respondida).

**O anel de foco permanece soberano.** `hover` é resposta ao apontador; foco é
navegação por teclado, e é requisito de acessibilidade. O anel de 3px do
`:focus-visible` não muda, não encolhe e não é substituído por sombra.

**Transições curtas e só em propriedades baratas** (`box-shadow`, `transform`,
`background-color`) — nada que force recálculo de layout. Tudo desligado sob
`prefers-reduced-motion`.

**Critérios de aceite**

- [x] Botões, `.opt` e `.item` têm estado de `hover` e de acionamento
- [x] `:focus-visible` inalterado: 3px, `outline-offset` 3px
- [x] `AC-113`: nenhuma transição sob `prefers-reduced-motion: reduce`
- [x] Gates: lint, build, test

**Status:** `[x] concluída`

---

### `T-166` — A trilha ganha trilho e marcas de estado

- **Tipo:** `REFACTOR`
- **Dependências:** `T-162`, `T-163`
- **Rastreia:** `RF-77`, `AC-115`, `AC-116`
- **Arquivos:** `frontend/src/componentes/TrilhaDaJornada.tsx`,
  `frontend/src/index.css`, `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

A trilha das cinco etapas (`RF-64`) hoje é uma lista de números soltos. Com
trilho contínuo e marcas de estado, o que passou, o que é agora e o que falta
lê-se de relance.

**A trilha continua informativa e NUNCA navegável** (`AC-115`). Tornar os
degraus clicáveis seria restabelecer a barra de sete abas que `RF-57`/`AC-83`
mataram — e que o plano descreve como *"o desenho oposto"* ao adotado. O único
botão da tela segue sendo o da próxima etapa. O teste novo prova isso: nenhum
`button`/`a`/`role=button` dentro da trilha.

**A estrutura de DOM é contrato** (`AC-116`). `navegacao.spec.ts:801` extrai os
rótulos por `item.querySelector('.linha span')`, e `:796` conta cinco `<li>`.
Trilho e marcas entram **em volta** disso, nunca no lugar: `.linha span`
permanece, os `<li>` permanecem cinco, `aria-current="step"` permanece na etapa
em curso.

**Critérios de aceite**

- [x] `AC-115`: nenhum elemento interativo dentro da trilha
- [x] `AC-116`: `.linha`, `<li>`×5 e `aria-current="step"` preservados
- [x] `AC-93`, `AC-94`, `AC-95` seguem verdes **sem edição**
- [x] Gates: lint, build, test, e2e

**Status:** `[x] concluída`

---

### `T-167` — A tela do plano parece o entregável

- **Tipo:** `REFACTOR`
- **Dependências:** `T-162`, `T-163`
- **Rastreia:** `RF-73`, `AC-109`
- **Arquivos:** `frontend/src/telas/TelaPlano.tsx`,
  `frontend/src/index.css`, `frontend/tests/e2e/plano.spec.ts`

**Descrição**

É o produto que o aluno esperou semanas para receber, e hoje `PRAZO_TOTAL` e
`CUSTO_FUTURO_TOTAL` saem num `<dl>` de duas colunas **abaixo** da ordem, no
mesmo cartão cinza de qualquer outra tela.

**Resumo antes do detalhe** (`AC-109`): prazo e custo sobem para o topo, em
escala de manchete. É a resposta que o aluno abriu a tela para ver; a ordem de
quitação é o detalhe que a sustenta.

**Nenhum número é calculado aqui** (Lei nº 3, já vigente no arquivo): prazo,
custo e valores de apoio continuam sendo leitura de campo do snapshot, já
formatados pelo servidor. Esta tarefa move e redimensiona — não recalcula.

**A redação canônica é intocada** (`AC-14`, `AC-15`): `plano.titulo` e
`plano.corpo` seguem verbatim do servidor. O carimbo de versão (`AC-16`)
permanece. `plano.spec.ts:110-114` continua exigindo "projetada" e proibindo
"definitiva"/"fixa" — nada nesta tarefa toca texto.

**Numerais tabulares** (`RF-73`) em todo valor: hoje os dígitos dançam entre as
linhas do `<dl>`.

**Critérios de aceite**

- [x] `AC-109`: resumo acima da ordem, em escala maior; `tabular-nums` em todo
      valor numérico
- [x] `AC-14`/`AC-15`/`AC-16`: redação canônica e carimbo inalterados
- [x] `plano.spec.ts` verde, incluindo a proibição de `0,00` (`:201-202`)
- [x] Gates: lint, build, test, e2e

**Status:** `[x] concluída`

---

### `T-168` — Verificação final e README do frontend

- **Tipo:** `CHORE`
- **Dependências:** `T-163`, `T-164`, `T-165`, `T-166`, `T-167`
- **Rastreia:** `RF-78`, `AC-116`
- **Arquivos:** `frontend/README.md`

**Descrição**

Fecha a rodada: a suíte inteira roda, e o `README.md` do frontend — que ainda é
o do template do Vite, falando de "React + TypeScript + Vite" e de regras do
Oxlint — passa a descrever o que o diretório de fato é.

**A suíte E2E existente é o guarda-costas desta rodada.** Se alguma classe foi
renomeada por engano, dezenas de testes quebram; se um ícone entrou na ordem de
foco, `coleta.spec.ts` quebra; se um token mudou, `test_acessibilidade_coleta.py`
quebra. Passar tudo é a prova de `RF-78`.

**Critérios de aceite**

- [x] Gates completos: lint, build, test (Python), vitest, playwright
- [x] `README.md` descreve o frontend do PIQ, não o template
- [x] Nenhuma trava listada em R8.6 foi editada para passar

**Status:** `[x] concluída`

---

## Achados de revisão (2026-09-19) — pendentes, fora da Rodada 8

> Encontrados pela revisão de código da Rodada 8 e **não corrigidos nela**:
> são defeitos PRÉ-EXISTENTES, sem relação com a repaginação visual. A regra 4
> do `CLAUDE.md` manda virar tarefa em vez de extra silencioso.
>
> Nenhum tem teste que o pegue hoje — os três dependem de estado que a suíte
> não exercita (destino desconhecido, papel assíncrono, fase nova).

### `T-169` — Destino desconhecido não pode apagar a tela

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-58`, `EC-25`
- **Arquivos:** `frontend/src/telas/TelaInicio.tsx`, `frontend/src/main.tsx`

**Descrição**

`TEXTO_DA_ETAPA[etapa.destino]` e `rotaDoDestino()` não têm ramo padrão. Um
`destino` que o cliente não conheça — servidor novo, cliente antigo — faz
`texto.rotulo` lançar, e **não há `ErrorBoundary` em `main.tsx`**: a aplicação
inteira vira tela branca.

O docstring do próprio arquivo promete o contrário: *"Um destino que não
reconhecemos cai no plano — nunca numa tela em branco."* A promessa está
escrita e não implementada.

`tsconfig.app.json` não liga `strict`, então o TypeScript não acusa o
`undefined` — é por isso que passou.

**Critérios de aceite**

- [ ] Destino desconhecido cai no plano, com a tela inteira funcionando
- [ ] `main.tsx` tem `ErrorBoundary`: nenhuma exceção de tela produz página em branco
- [ ] Teste cobrindo um `destino` que o cliente não conhece

**Status:** `[x] concluída` (2026-09-20)

> **Duas metades.** (a) `rotaDoDestino` ganhou `default` e
> `TEXTO_DA_ETAPA`/`CHAMADA_DA_FASE` ganharam fallback — a promessa que o
> docblock já fazia, agora implementada. (b) `LimiteDeErro` (ErrorBoundary)
> envolve o `App` em `main.tsx`: o defeito específico está corrigido, mas a
> CLASSE dele não, e um servidor mais novo que o cliente é a situação normal
> durante um deploy.
>
> A tela de erro diz que as respostas estão guardadas (`RF-10`), não mostra
> a mensagem técnica ao aluno, e oferece "Recarregar a página" — nunca uma
> página em branco sem caminho.

---

### `T-170` — O revisor não pode ser expulso da própria tela ao atualizar

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-59`, `AC-80`
- **Arquivos:** `frontend/src/App.tsx`

**Descrição**

`substituirRota` é chamada **durante a renderização**, mutando o histórico e
chamando `setRota` no meio do render. Como `eRevisor` começa `null` e só
resolve depois da consulta à conta, um revisor real que atualiza a página em
`#equipe-fila` é mandado para o Início — e o `replaceState` destrói a URL, de
modo que nem o "voltar" do navegador o traz de volta.

O redirecionamento só pode acontecer quando o papel já é **conhecido**
(`false`), nunca enquanto é `null`, e precisa sair do corpo do render.

**Critérios de aceite**

- [ ] Revisor que atualiza em `#equipe-fila` permanece na fila
- [ ] Nenhum `setRota`/`replaceState` durante a renderização
- [ ] Não-revisor continua sendo mandado ao Início (`AC-80` intacto)

**Status:** `[x] concluída` (2026-09-20)

> `eRevisor === false` em vez de `!== true`: enquanto é `null` ("ainda
> perguntando ao servidor"), nada se decide. E o redirecionamento saiu do
> corpo do render para um `useEffect` (`RedirecionarAoInicio`) — mutar o
> histórico durante a renderização é efeito colateral no meio do render.
>
> Verificado por regressão: revertendo `=== false` para `!== true`, o teste
> novo falha.

---

### `T-171` — Fase desconhecida não pode dizer ao aluno que ele voltou ao começo

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-64`, `AC-94`
- **Arquivos:** `frontend/src/componentes/TrilhaDaJornada.tsx`

**Descrição**

`indiceDaEtapaEmCurso` cai em `0` quando a fase não está mapeada. Para um
aluno em acompanhamento, isso marca "Suas respostas" como etapa em curso —
dizendo a quem já tem plano que ele está de volta à primeira pergunta, com o
texto de acompanhamento embaixo do rótulo errado.

O fallback foi escrito para garantir que `AC-94` sempre tenha exatamente uma
etapa em curso, e cumpre isso; o problema é a etapa **escolhida**. Uma fase
desconhecida é um caso em que o cliente não sabe onde o aluno está — e dizer
"você está no começo" é pior que não marcar etapa nenhuma.

**Critérios de aceite**

- [ ] Fase desconhecida não marca "Suas respostas" como em curso
- [ ] `AC-94` continua válido nas cinco fases conhecidas
- [ ] Teste com fase que o cliente não conhece

**Status:** `[x] concluída` (2026-09-20)

> Fase desconhecida cai em "Conferência da equipe" (índice 2), não em
> "Suas respostas" (0). Um servidor mais novo só tem fases ADIANTE das
> cinco atuais — dizer a quem já tem plano que ele voltou à primeira
> pergunta era o pior palpite possível.
>
> `oQueFalta` também deixou de dar uma ORDEM ("faça a próxima ação") a quem
> não sabemos o estado: passa a dizer "o seu caso está com a equipe".
> `AC-94` fala das CINCO fases conhecidas e continua valendo para todas.

---

## Achados do ciclo real (2026-09-19)

> Encontrados ao rodar o fluxo completo contra o backend e o Postgres reais:
> coleta de 73 respostas e três dívidas pela API de produção. São bloqueios
> de PRODUÇÃO, não de teste — a suíte os contorna e documenta.

### `T-172` — `B12.16` torna o cálculo inalcançável por HTTP

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-16`, `RF-20`, `AC-12`
- **Arquivos:** `collection/registros/bloco-12.yaml`,
  `app/http/rotas_calculo.py`

**Descrição**

**O cálculo do plano não pode ser disparado pela aplicação real — por
nenhuma sequência de respostas.** Verificado contra o servidor de verdade em
2026-09-19, com Postgres e as rotas de produção:

1. Um caso em `COLETA_INICIAL` com **73 respostas** gravadas pela rota real
   (`POST /caso/{id}/resposta`), incluindo **três fichas de dívida completas**
   (`D001`, `D002`, `D003`), uma de despesa e uma de despesa não-mensal.
2. `POST /caso/{id}/calculo` devolve, invariavelmente:
   `400 {"mensagem":"Há perguntas obrigatórias pendentes.","pendencias":["B12.16"]}`

As pendências caíram de **50 → 15 → 1** conforme a coleta avançou. A última
não cai.

**Por que `B12.16` é insatisfatível.** O registro é `OBR`, tem
`condicao_exibicao: None` (sempre aberta) e `origem_opcoes` com
`fonte=SNAPSHOT`, `campo_do_snapshot=ORDEM_ACOES`. Como `ORDEM_ACOES` só
existe **depois** que o Bloco 6 roda, a pergunta serve zero opções antes do
primeiro cálculo — e o gate de `pendencias_obrigatorias`
(`rotas_calculo.py:379`) a conta como pendente. **A pergunta que bloqueia o
cálculo só pode ser respondida depois do cálculo.**

**Não é defeito de teste.** Os dois testes que percorrem o ciclo já contornam
isto, cada um de um jeito, e ambos documentam a causa:

- `tests/app_aluno/e2e/test_ciclo_completo.py:45-70` filtra a coleção real
  pelos `VARIAVEL_GRAVADA` que a fixture responde;
- `tests/app_aluno/integracao/test_coleta_para_motor.py:360` substitui a
  coleção inteira por `ColecaoDeRegistros(registros=())`.

Nenhum dos dois contornos existe em produção, e `T-19` já registrou que *"o
Bloco 12 não é implementado como fluxo de coleta"* — seus três registros são
casos de prova do GERADOR, não perguntas do questionário piloto. A coleção
que `carregar_registros()` entrega não faz essa distinção, e o gate não sabe
fazê-la.

**O motor NÃO é o problema.** Com as mesmas 73 respostas lidas do Postgres e
montadas pelos helpers da própria rota
(`_montar_estado_financeiro_do_caso`), `calcular_plano` produz um plano
completo e coerente:

```
SNAPSHOT_ID            4b51c9a62c4980b4…
METODO_RECOMENDADO_PIQ BOLA_DE_NEVE
ORDEM_QUITACAO         1. D003 (R$ 6.000,00)
                       2. D001 (R$ 12.480,00)
                       3. D002 (R$ 24.000,00)
PRAZO_TOTAL            19
CUSTO_FUTURO_TOTAL     42.480,00
```

O bloqueio é do **gate**, não do cálculo.

**Confirmado PELA TELA (2026-09-19).** A coleta inteira foi percorrida clique
a clique, pela interface, sem nenhuma chamada direta à API: **176 das 177
perguntas respondidas**, zero erros de validação. A 177ª é `B12.16`, e o que
o aluno vê é uma tela com o enunciado *"Qual destas frases você quer adotar
como sua regra principal?"*, **nenhuma opção** (zero `role=radio`, zero
checkbox) e um botão "Continuar" que não leva a lugar nenhum. Não é um
detalhe de gate: é um beco sem saída visível, no fim de 176 perguntas.


**Saídas possíveis** (a decisão é do especialista do método):

1. **Excluir o Bloco 12 da coleção de coleta.** É o que `T-19` já afirma
   sobre a natureza daqueles registros. Mais simples e mais fiel ao que o
   piloto entende por "questionário".
2. **O gate ignorar perguntas cuja `origem_opcoes.fonte` é `SNAPSHOT`
   enquanto não há snapshot.** Uma pergunta que não tem opções a oferecer não
   é pendência do aluno — é pendência do sistema.
3. **Marcar `B12.16` como pós-plano** (`condicao_exibicao` dependente da
   existência de snapshot), alinhando-a aos Blocos 7/8.

**Critérios de aceite**

- [ ] `POST /caso/{id}/calculo` é aceito num caso cuja coleta obrigatória
      está completa, sem nenhum contorno de coleção
- [ ] Um caso com três dívidas chega a `AGUARDANDO_REVISAO` pela rota real
- [ ] `test_ciclo_completo.py` deixa de precisar filtrar a coleção — ou o
      filtro passa a ter outra justificativa, registrada
- [ ] Gates: lint, build, test

**Status:** `[x] concluída` (ciclo real 2026-09-19)

---

### `T-173` — Sem rota para `inicia_coleta` e para `registrar_snapshot_raiz`

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-01`, `RF-23`, `OQ-11`
- **Arquivos:** `app/http/rotas_consentimento.py`,
  `app/http/rotas_calculo.py`

**Descrição**

Duas transições existem na máquina de estados e **não têm rota que as
dispare** — hoje só acontecem por chamada direta ao repositório, em teste ou
em `scripts/subir_demo.py`:

1. **`CONSENTIMENTO_REGISTRADO → COLETA_INICIAL`** (`inicia_coleta`). Sem
   ela, `POST /resposta` é recusado pela guarda
   `exigir_estado_permite_resposta` (`maquina.py:319-333`). O script de
   demonstração contorna criando o caso já em `COLETA_INICIAL`
   (`subir_demo.py:113`), e o teste de ciclo chama
   `transicionar_estado(...)` à mão.
2. **`registrar_snapshot_raiz`** nunca é chamado por rota nenhuma (`OQ-11`).
   Sem `Caso.snapshot_raiz_id`, `listar_fila_de_revisao` não encontra a
   cadeia e `GET /api/revisao/caso/{id}` devolve `404` — a fila de
   conferência fica vazia mesmo com plano calculado.

O segundo item bloqueia `RF-23` (revisão humana obrigatória) pelo caminho
real: o revisor não tem como ver o que precisa conferir.

**Critérios de aceite**

- [ ] Existe caminho HTTP de `CONSENTIMENTO_REGISTRADO` para `COLETA_INICIAL`
- [ ] Depois de um cálculo, o caso aparece em `GET /api/revisao/fila`
- [ ] `GET /api/revisao/caso/{id}` devolve o plano em vez de `404`
- [ ] Gates: lint, build, test

**Status:** `[x] concluída` (2026-09-21)

> **Fechada.** `registrar_snapshot_raiz` saiu em 2026-09-19; `inicia_coleta`
> agora é encadeada por `rotas_consentimento.py` logo após o aceite —
> `CADASTRADO → CONSENTIMENTO_REGISTRADO → COLETA_INICIAL` num só passo do
> aluno, com as duas transições registradas separadamente na trilha
> (`RF-31`).
>
> **Por que encadear, e não criar rota própria.** Não há decisão entre
> aceitar e começar a responder: `RF-30` manda registrar o consentimento
> ANTES de qualquer coleta, e é isso que acabou de acontecer. Uma segunda
> rota exigiria uma segunda ação para um passo que o aluno não pode
> recusar — e deixaria o mesmo beco aberto para quem fechasse o navegador
> entre as duas.
>
> `test_ciclo_completo.py` perdeu o contorno que chamava
> `transicionar_estado` direto no repositório: o trecho do consentimento
> passou a ser HTTP de ponta a ponta.

> **O que foi feito.** `registrar_snapshot_raiz` passou a ser chamado em
> `_executar_e_avancar` quando o snapshot é o primeiro da cadeia
> (`snapshot_anterior_id is None`). A fila de conferência deixou de sair
> vazia: verificado no ciclo real — cálculo por HTTP, caso em
> `AGUARDANDO_REVISAO`, item presente em `GET /api/revisao/fila`,
> `LIBERAR` aceito e plano visível ao aluno.
>
> **O que CONTINUA aberto.** A transição `CONSENTIMENTO_REGISTRADO →
> COLETA_INICIAL` (`inicia_coleta`) segue sem rota HTTP. Hoje só não
> bloqueia porque `scripts/subir_demo.py` cria o caso já em
> `COLETA_INICIAL` — num fluxo real, com consentimento publicado
> (`PEND-01`), o aluno ficaria preso depois de aceitar o termo. Não foi
> tocado aqui porque depende de `PEND-01`, que é insumo jurídico.

---

### `T-174` — Link com `?caso=` sem sessão vira beco sem saída

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-02`, `RF-58`, `AC-91`
- **Arquivos:** `frontend/src/App.tsx`,
  `frontend/tests/e2e/navegacao.spec.ts`

**Descrição**

**Quem abre um link `?caso=<id>` sem sessão vê "Não foi possível carregar a
sua próxima etapa." e não tem como entrar.** Não há formulário de login na
tela, nem botão, nem caminho: a única saída é apagar o `?caso=` da barra de
endereços à mão — o que ninguém descobre sozinho.

Reproduzido em navegador limpo (contexto sem cookies) contra o servidor real
em 2026-09-19:

```
GET /caso/<id>/inicio   -> 401 {"detail":"Sessão inválida ou expirada."}
GET /api/conta/eu       -> 401 {"erro":"Sessão inválida ou expirada."}
tela: "Início" + "Não foi possível carregar a sua próxima etapa."
```

**Causa.** `App.tsx:185` decide mostrar o login por `!casoId`:

```tsx
if (!casoId && rota.tela !== 'entrada') {
  return <TelaLogin … />
}
```

Com `?caso=` na URL, `casoId` nasce preenchido (`casoDaUrl`), a condição é
falsa, e a aplicação renderiza `TelaInicio` para alguém **sem sessão**. O
`401` que volta de `/inicio` é tratado por `TelaInicio` como falha de carga
genérica (`RF-58`, ramo de erro) — que é a mensagem certa para uma rede
instável e a errada para "você não está autenticado".

`T-154` resolveu o problema inverso (sessão instalada e sem `?caso=`, que
prendia na tela de login) fazendo `/api/conta/eu` ser a fonte do caso. O
simétrico — `?caso=` presente e sessão ausente — ficou aberto.

**É o caminho mais provável do piloto.** O `scripts/subir_demo.py` imprime
exatamente uma URL com `?caso=`, e é assim que um link chega por e-mail ou
WhatsApp a um aluno que ainda não entrou.

**A correção é de interface, não de autorização.** O servidor já recusa
corretamente; o que falta é a tela reagir ao `401` oferecendo a entrada. O
`CASO_ID` da URL deve ser preservado através do login, para que o aluno caia
no caso do link depois de autenticar — e não num caso qualquer.

**Critérios de aceite**

- [ ] Navegador sem sessão abrindo `?caso=<id>` vê a tela de entrada, nunca
      a mensagem de falha de carga
- [ ] Depois de entrar, o aluno chega ao caso do link (o `?caso=` sobrevive)
- [ ] Sessão de outra conta abrindo `?caso=` alheio continua recebendo o
      tratamento de caso inexistente (`404`), sem vazar existência
- [ ] Teste E2E em contexto limpo (`storageState` vazio) cobrindo o caso
- [ ] Gates: lint, build, test, e2e

**Status:** `[x] concluída` (ciclo real 2026-09-19)

---

### `T-175` — "Continuar de onde você parou" trava o aluno na mesma pergunta

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-45`, `RF-58`, `AC-01`, `AC-102`
- **Arquivos:** `frontend/src/telas/TelaPergunta.tsx`,
  `frontend/src/telas/TelaInicio.tsx`,
  `frontend/tests/e2e/coleta.spec.ts`

**Descrição**

**A coleta não avança pelo caminho principal do produto.** O aluno clica em
"Continuar de onde você parou" no Início, responde, grava — e a **mesma
pergunta** volta. Responder de novo grava de novo, e a pergunta volta de
novo. Não há como chegar à próxima pergunta por esse caminho.

Reproduzido contra o servidor real em 2026-09-19, navegador limpo:

```
A0 URL: pergunta/B3.DF04/DESP001   ← entra pelo Início
A1 URL: pergunta/B3.DF04/DESP001   ← respondeu, gravou… mesma pergunta
A2 URL: pergunta/B3.DF04/DESP001   ← de novo
A3 URL: pergunta/B3.DF04/DESP001   ← de novo
```

Pelo caminho sem `ID_PERGUNTA` (`#pergunta`) a coleta anda normalmente — a
próxima pendente é decidida pelo servidor, como `RF-45` manda.

**Causa.** `TelaInicio::rotaDoDestino` repassa o `ID_PERGUNTA` que
`/inicio` devolve:

```tsx
case 'pergunta':
  return { tela: 'pergunta', idPergunta: ID_PERGUNTA ?? undefined, … }
```

Em `TelaPergunta::carregar`, a presença de `idPergunta` significa "abra ESTA
pergunta" (`AC-102`, o caminho da correção):

```tsx
const dados = idPergunta
  ? await obterPergunta(casoId, idPergunta, itemId)   // ESTA
  : await obterProximaPergunta(casoId)                // a próxima pendente
```

Depois de gravar, `aoResponder` chama `await carregar()` — que relê com o
**mesmo** `idPergunta`, ainda fixado na rota. O resultado é um laço: grava,
recarrega a mesma, grava, recarrega a mesma.

**Por que os testes não pegaram.** `coleta.spec.ts` exercita a coleta por
`#pergunta` (sem ID), onde o comportamento está correto; e os testes de
`AC-102` abrem uma pergunta específica para **corrigir**, cenário em que
recarregar a mesma pergunta é o certo — quem sai dali é o `aoCorrigir`. O
caminho que quebra é o terceiro: entrar com ID **sem** estar corrigindo, que
é exatamente o que o Início faz.

**O dado não se perde** — as respostas são gravadas (verificado no Postgres:
o contador subiu a cada clique). O defeito é de navegação, e é total: um
aluno que entre pelo caminho oferecido não termina a coleta.

**Encaminhamento sugerido.** Depois de gravar, quando **não** se está
corrigindo, seguir para a próxima pendente do servidor em vez de reler a
mesma — ou o Início parar de repassar `ID_PERGUNTA` e deixar a escolha com o
servidor (`RF-45`: o cliente não decide o que vem a seguir). A segunda é mais
fiel ao requisito; a primeira preserva o link profundo.

**Critérios de aceite**

- [ ] Entrando pelo Início ("Continuar de onde você parou") e respondendo, a
      tela avança para a pergunta seguinte
- [ ] Corrigir uma resposta (`AC-102`/`AC-103`) continua voltando para a
      revisão, sem emendar na coleta
- [ ] Teste E2E percorrendo N perguntas pelo caminho do Início e provando
      que os enunciados mudam
- [ ] Gates: lint, build, test, e2e

**Status:** `[x] concluída` (ciclo real 2026-09-19)

---

### `T-176` — `CONFIABILIDADE_DADOS` derivada do motor destrava o Bloco 6

- **Tipo:** `FEATURE`
- **Dependências:** `T-172`
- **Rastreia:** `RF-16`, `AC-12`, `AC-41`
- **Arquivos:** `app/http/rotas_calculo.py`,
  `tests/app_aluno/estatica/test_fronteira_import_engine.py`

**Descrição**

Com `T-172` resolvido, o gate de pendências passou a abrir — e o cálculo
passou a parar num `503`: `_ParametrosExternosPendentes` bloqueava o disparo
porque `CONFIABILIDADE_DADOS` não tinha fonte real (`T-106`).

**O bloqueio estava certo; faltava a tarefa que ele previa.** Não havia
default seguro: o enum `ALTA`/`MEDIA`/`BAIXA` não tem membro neutro, e
qualquer valor fixo seria a "estimativa silenciosa" que `sdd.config.md` §4
proíbe. A nota de `app/montagem/estado.py` já dizia qual era o caminho:
*"A chamadora (Bloco 6) é responsável por invocar a derivação de dentro do
motor, nunca de `app/`"*.

`_ParametrosExternosDerivadosDoBloco2` faz exatamente isso: monta o
`PerfilComportamental` das respostas do Bloco 2 e chama
`derivar_NIVEL_CONTROLE` + `derivar_CONFIABILIDADE_DADOS` — as funções do
próprio motor, invocadas como estão. Nenhum passo é reimplementado, que é o
que `RF-16` proíbe.

**A allowlist de import foi ampliada para DOIS nomes, e só eles.** Gates,
fórmulas financeiras e ciclo mensal continuam inalcançáveis de `app/`. A
justificativa está registrada no próprio teste de fronteira.

**Decisão do especialista (2026-09-19):** derivar no fluxo do motor, entre
três opções apresentadas (derivar · só documentar · injetar por
configuração).

**Critérios de aceite**

- [x] `POST /caso/{id}/calculo` responde `200` com a coleta completa
- [x] `CONFIABILIDADE_DADOS` vem das respostas reais do Bloco 2
- [x] Nenhum valor default fixo é usado
- [x] `test_fronteira_import_engine.py` verde, com dois nomes novos
- [x] Gates: lint, build, test, e2e

**Status:** `[x] concluída` (ciclo real 2026-09-19)

---

### `T-177` — O plano mostra número cru e nome de variável do motor

- **Tipo:** `BUGFIX`
- **Dependências:** `T-176`
- **Rastreia:** `RF-13`, `RF-50`, `AC-14`
- **Arquivos:** `app/http/serializacao_plano.py`,
  `frontend/tests/e2e/plano.spec.ts`

**Descrição**

**Descoberto ao ver a tela do primeiro plano liberado de verdade** (ciclo
real de 2026-09-19, depois que `T-172`/`T-173`/`T-176` destravaram o
caminho). O plano chega ao aluno assim:

| O aluno vê | Deveria ver |
| --- | --- |
| `73640.56` | `R$ 73.640,56` |
| `3000.00` | `R$ 3.000,00` |
| `0.04` · `0.07` · `0.02` | `4,2%` · `6,9%` · `1,8%` |
| `VALOR_RELEVANTE_PARA_QUITACAO` | *"Valor para quitar hoje"* |
| `PESO_EMOCIONAL` | *"O quanto esta dívida pesa para você"* |
| `TAXA_EFETIVA_MENSAL_NORMALIZADA` | *"Taxa ao mês"* |

Verificado no payload real de `GET /caso/{id}/api/plano`: os valores saem
crus (`'73640.56'`, `'0.04'`) e o `rotulo` de cada `valores_de_apoio` é o
**nome da variável do motor**, não uma redação ao aluno.

**Não é defeito da tela.** `TelaPlano.tsx` exibe verbatim o que o servidor
manda, e está certo nisso: `AC-14` proíbe o cliente reescrever a redação, e
`RF-13` proíbe o cliente formatar dinheiro (a fronteira de formatação é do
servidor). Quem precisa mudar é `serializacao_plano.py`.

**Por que importa mais do que parece.** A persona é um servidor público
endividado, com baixa familiaridade financeira presumida — e a tela do plano
é o entregável, o documento que ele esperou semanas para receber. `0.04` não
é "quatro por cento" para quem não é da área; `73640.56` não é um valor em
reais; e `VALOR_RELEVANTE_PARA_QUITACAO` pede que ele aprenda o vocabulário
interno do motor para ler o próprio plano.

**A redação dos rótulos é decisão de conteúdo, não de código.** `AC-37`
proíbe string longa ao aluno dentro do código da aplicação: os rótulos
precisam vir de `textos-canonicos.yaml`, como a redação de `Q-03` já vem.

**Critérios de aceite**

- [ ] Todo valor monetário do payload chega formatado (`R$ 1.234,56`)
- [ ] Toda taxa chega como percentual legível (`4,2%`), nunca decimal cru
- [ ] Nenhum `rotulo` de `valores_de_apoio` é nome de variável do motor
- [ ] Os rótulos saem de `textos-canonicos.yaml`, não de literal no código
- [ ] `plano.spec.ts` cobre os três casos
- [ ] Gates: lint, build, test, e2e

**Decisões do especialista (2026-09-19)**

1. **Justificativa: duas, uma por audiência.** A `JUSTIFICATIVA_POSICAO`
   técnica continua íntegra para o revisor (`AC-29`) e para auditoria; o
   aluno passa a ler uma redação em português, cadastrada por método em
   `textos-canonicos.yaml`. `AC-17` segue cumprido — toda posição explica
   por que está ali —, agora com o texto certo para quem lê.
2. **Pendências traduzidas.** "falta VALOR_QUITACAO_HOJE, CET" virou "falta
   quanto precisaria pagar para quitar hoje, o custo efetivo total (CET)".

**O que foi feito**

- `report/plano.py`: `formatar_dinheiro_br`, `formatar_taxa_br`,
  `formatar_escala_br`, `_formatar_meses` — e o despacho por variável
  (`_FORMATO_DE_APOIO`), porque o motor guarda dinheiro, taxa e escala todos
  como `Decimal`: quem distingue é o significado, não o tipo.
- `textos-canonicos.yaml`: `rotulos_de_apoio`, `explicacao_da_posicao`
  (duas redações por método — a da primeira posição e a das seguintes) e
  `rotulos_de_pendencia`. Redação ao aluno é dado, nunca literal em `.py`
  (`AC-37`).
- Templates do PDF pararam de prefixar `R$`/`meses`: a unidade vem do
  servidor, senão sairia `R$ R$ 73.640,56`.
- `TelaPlano.tsx` mostra `explicacao`, com fallback para a técnica — método
  novo sem redação cai num texto feio, nunca numa posição sem explicação.

**Por que a primeira posição tem redação própria.** A mesma frase nas três
posições parecia template, e *"esta é a de menor valor"* é falso da segunda
em diante — há uma menor acima dela. Descoberto ao olhar a tela, não no
teste.

**Critérios de aceite**

- [x] Todo valor monetário chega formatado (`R$ 73.640,56`)
- [x] Toda taxa chega como percentual com período (`4,2% a.m.`)
- [x] Nenhum `rotulo` de `valores_de_apoio` é nome de variável do motor
- [x] A justificativa ao aluno não cita método, variável nem regra do motor
- [x] O aviso de pendência diz o que falta em português
- [x] Os textos saem de `textos-canonicos.yaml`, não de literal no código
- [x] Gates: lint, build, test, e2e

**Status:** `[x] concluída` (2026-09-19)

---

## Abertura ao cliente real (2026-09-21)

> O aluno chega por COMPRA na Hotmart, não por cadastro no PIQ. Estas
> tarefas são o que fica entre a compra aprovada e o aluno respondendo a
> primeira pergunta.

### `T-178` — Recusar o consentimento não pode avançar o caso

- **Tipo:** `BUGFIX`
- **Dependências:** —
- **Rastreia:** `RF-30`, `AC-39`
- **Arquivos:** `app/http/rotas_consentimento.py`,
  `tests/app_aluno/test_rotas_consentimento.py`

**Descrição**

`POST /caso/{id}/consentimento` lia `aceite` do formulário, gravava o
`RegistroConsentimento` com o valor correto — e **transicionava o caso de
qualquer jeito**, sem nenhum `if aceite`. Quem recusasse ficava no mesmo
estado de quem aceitou, e a coleta começava.

A proteção existia só na tela (`TelaConsentimento.tsx` desabilita o botão
sem o checkbox), o que significa que um `POST` direto, fora da interface,
avançava o caso. Para LGPD, "recusou mas o sistema seguiu" é exatamente o
que não pode acontecer.

**A recusa é registrada, não descartada.** O `RegistroConsentimento` com
`aceite=False` continua sendo gravado: negar consentimento é um fato com
valor probatório, e apagá-lo deixaria o caso indistinguível de "nunca
respondeu". O que não acontece é a transição.

**Resposta `200`, não erro.** O aluno fez uma escolha legítima e o servidor
a registrou com sucesso; o estado devolvido diz à tela que nada avançou.

**Critérios de aceite**

- [x] `aceite` ausente ou diferente de `on` não transiciona o caso
- [x] A recusa é gravada com `aceite=False`
- [x] O caso permanece em `CADASTRADO`
- [x] Gates: lint, build, test

**Status:** `[x] concluída` (2026-09-21)

---

### `T-179` — Provisionamento de conta pela compra (Hotmart)

- **Tipo:** `FEATURE`
- **Dependências:** `T-178`
- **Rastreia:** `RF-02`, `RF-30`, `OQ-05`
- **Arquivos:** `persistencia/supabase/migracoes/004_primeiro_acesso.sql`
  (novo), `persistencia/app_aluno/cadastro.py`,
  `persistencia/app_aluno/contas.py`, `app/http/rotas_provisionamento.py`
  (novo), `app/http/aplicacao.py`, `frontend/src/telas/TelaDefinirSenha.tsx`
  (novo), `frontend/src/App.tsx`, `frontend/src/navegacao.ts`,
  `frontend/src/services/api.ts`

**Descrição**

**O aluno compra na Hotmart, não se cadastra no PIQ.** Não existe (nem vai
existir) tela de cadastro público: a conta nasce de uma compra aprovada, por
webhook.

**Decisões do especialista (2026-09-21):**

1. **Rota nova de provisionamento, com segredo.** `POST
   /api/provisionamento/conta`, autenticada por segredo compartilhado em
   header, cria conta + caso e **não abre sessão** — a rota de cadastro
   atual (`POST /api/conta/cadastro`) foi desenhada para tela: exige senha e
   instala cookie de sessão no chamador, o que não faz sentido para uma
   máquina. Separar "máquina provisiona" de "pessoa se cadastra" mantém as
   duas honestas.
2. **Login e senha, como `RF-02`/`OQ-05` já fixavam.** A alternativa
   levantada — entrar só com o e-mail, se ele estiver na base — foi
   descartada pelo próprio especialista: qualquer pessoa que soubesse o
   e-mail de um aluno veria dívidas, renda e contracheque dele.

**O fluxo:**

```
compra aprovada → webhook → POST /api/provisionamento/conta (segredo)
                          → cria conta SEM senha + token de primeiro acesso
                          → aluno abre o link, define a senha
                          → entra com e-mail + senha, de qualquer aparelho
```

**O que muda no schema.** `app_aluno.contas.senha_hash` é `NOT NULL` — a
conta não pode nascer sem senha. A migração `004` o torna anulável e
acrescenta a tabela de token de primeiro acesso (uso único, com expiração).
Conta sem `senha_hash` **não autentica**: `autenticar` recusa antes de
comparar hash.

**O mesmo mecanismo serve para "esqueci minha senha"** — é o que fecha
aquele bloqueio sem um segundo sistema.

**Dependência externa.** O envio do link por e-mail não existe no sistema
(`T-180`). Enquanto não existir, o token pode ser entregue por outro canal
(página de obrigado da Hotmart), mas isso precisa de decisão do
especialista.

**Critérios de aceite**

- [ ] `POST /api/provisionamento/conta` sem o segredo correto responde `401`
- [ ] Com o segredo, cria conta + caso em `CADASTRADO` e devolve o token
- [ ] A rota **não** instala cookie de sessão
- [ ] E-mail já provisionado não cria conta duplicada nem confirma
      existência ao chamador
- [ ] Conta sem senha definida não autentica por nenhum caminho
- [ ] Token é de uso único e expira
- [ ] A tela de definir senha aplica a política de senha (`T-181`)
- [ ] Gates: lint, build, test, e2e

**Status:** `[~] parcial` (2026-09-21)

> **Feito:** migração `004` (senha anulável + tabela de tokens),
> `RepositorioTokensAcessoSupabase` (emitir com revogação do anterior,
> consumir atômico), `provisionar`/`definir_senha` em `contas.py`,
> `provisionar_conta_e_caso`, e as rotas `POST /api/provisionamento/conta`
> e `/senha` com 11 testes.
>
> **A guarda central:** conta sem senha não autentica. Ao trocar o tipo
> para `str | None`, o mypy apontou todos os pontos que precisavam tratar
> o caso — o `autenticar` real e dois dublês.
>
> **Por que os testes de rota importam:** a auditoria de isolamento só
> cobre rotas que recebem `CASO_ID`. Estas duas não recebem — passavam
> por vacuidade, e a porta que cria conta no sistema não tinha teste
> nenhum guardando quem pode abri-la.
>
> **Tela pronta (2026-09-21):** `TelaDefinirSenha.tsx`, rota
> `#definir-senha/{token}` e `definirSenha()` no cliente da API, com 6
> testes.
>
> **O token vai no HASH, não em `?token=`.** O hash não é enviado ao
> servidor em requisição nenhuma — numa query string, o token apareceria
> em log de proxy, de CDN e no `Referer` de qualquer recurso externo.
>
> **A tela vem ANTES do portão de login** (`App.tsx`), e é a única além da
> entrada que dispensa sessão: quem clica no link do e-mail não tem sessão
> e não consegue logar (conta sem senha), então cairia preso na entrada —
> o mesmo beco que `T-174` descreveu para o `?caso=`.
>
> **Feito (2026-09-21):** os três e-mails, em `T-182`.

---

### `T-180` — Envio de e-mail (AWS SES por SMTP)

- **Tipo:** `FEATURE`
- **Dependências:** —
- **Rastreia:** `RF-31`
- **Arquivos:** `app/notificacao/email.py` (novo),
  `app/notificacao/__init__.py` (novo)

**Descrição**

Duas telas prometiam ao aluno o que o sistema não cumpria: *"A espera é com
a equipe. Avisamos por e-mail."* (`TrilhaDaJornada.tsx:132`) e *"Avisaremos
por e-mail assim que o plano estiver liberado."* (`TelaAguardando.tsx:59`).
**Não havia nenhum envio de e-mail no projeto** — a promessa era falsa, e o
aluno que fechasse o navegador depois da coleta nunca sabia que o plano
saiu. Num acompanhamento de meses (`OQ-06`), esse é o ponto de abandono
mais provável do piloto.

E-mail é também a peça de que dependem o primeiro acesso (`T-179`) e a
recuperação de senha: as duas entregam um token ao dono do endereço, e só o
e-mail prova essa posse.

**Provedor: AWS SES por SMTP** (decisão do especialista, 2026-09-21).
`smtplib` é stdlib — **nenhuma dependência nova**. Nada no módulo é
específico de SES: qualquer servidor com STARTTLS serve, e trocar de
provedor é trocar variável de ambiente.

**Configuração só por ambiente** (`SMTP_SERVIDOR`, `SMTP_PORTA`,
`SMTP_USUARIO`, `SMTP_SENHA`, `SMTP_REMETENTE`), mesma disciplina de
`CHAVE_ASSINATURA_SESSAO` e `DATABASE_URL`. Sem elas, `enviar` levanta —
nunca um envio silenciosamente descartado, que faria a aplicação achar ter
avisado o aluno.

**STARTTLS obrigatório**, antes do login: sem ele a credencial do SES
trafegaria em claro.

**O erro não carrega o destinatário**: e-mail é dado pessoal sob LGPD, e a
exceção vai para o log do processo.

**Fora de escopo, deliberadamente.** Sem fila, sem repetição automática,
sem redação (quem chama passa assunto e corpo). `OQ-06` (1 a 3 alunos) não
justifica a infraestrutura; quando justificar, o ponto de injeção é este
módulo, não os chamadores.

**Critérios de aceite**

- [x] `EnviadorDeEmail` é `Protocol` — chamadores não dependem de `smtplib`
- [x] Variável ausente levanta `ErroConfiguracaoEmail`, nunca envio mudo
- [x] STARTTLS antes do login
- [x] A exceção de falha não contém o destinatário
- [x] `EnviadorEmMemoria` permite teste sem servidor
- [x] Gates: lint, build, test

**Status:** `[x] concluída` (2026-09-21) · **envio real confirmado**
(2026-09-22)

> **Verificado contra o SES de produção**, não só com dublê: os três e-mails
> foram aceitos e ENTREGUES (`noreply@multiplicaservidor.com.br` →
> caixa de entrada, sem spam, acentuação correta). O ciclo completo pela
> aplicação — provisionar → `email_enviado=true` → definir senha → login →
> recuperação — rodou com `EnviadorSMTP` real, sem override.
>
> **A armadilha que custou a primeira tentativa: a senha SMTP do SES NÃO é
> a Secret Access Key do IAM.** São valores distintos — a senha SMTP é
> derivada da secret key pelo algoritmo SigV4 da AWS. Usar a secret key
> direto falha com `535 Authentication Credentials Invalid`, mensagem que
> aponta para "credencial errada" quando o problema é a credencial CERTA no
> formato ERRADO. O formato denuncia num relance:
>
> | | SES espera | Secret key IAM |
> | --- | --- | --- |
> | Usuário | 20 chars, `AKIA…` | igual |
> | Senha | **44 chars, `B…`** | 40 chars, não começa com `B` |
>
> Documentado em `.env.example` para não se repetir no deploy.

---

### `T-182` — Os três e-mails ao aluno

- **Tipo:** `FEATURE`
- **Dependências:** `T-179`, `T-180`
- **Rastreia:** `RF-02`, `RF-31`
- **Arquivos:** `app/notificacao/mensagens.py` (novo),
  `app/notificacao/textos/emails.yaml` (novo),
  `app/http/rotas_provisionamento.py`, `app/http/rotas_revisao.py`,
  `tests/app_aluno/test_mensagens_de_email.py` (novo)

**Descrição**

`T-180` sabe FALAR SMTP; `T-179` cria a conta e emite o token. Faltava o
que fecha o circuito: QUAL mensagem vai em cada momento. Três momentos —
primeiro acesso (a compra foi aprovada, a conta existe sem senha),
recuperação de senha, e plano liberado (o aviso que `TrilhaDaJornada` e
`TelaAguardando` prometem em texto e que o sistema não cumpria).

**A redação NÃO vive em `.py`.** Escrevi o módulo primeiro com o texto
embutido, argumentando na docstring que e-mail transacional não é peça
normativa como o termo (`PEND-01`) ou a redação do plano (`Q-03`) — e a
trava estática de `AC-37` reprovou. Ela estava certa: `AC-37` audita
literal longo em `app/`, sem perguntar se o texto é normativo. Uma regra
que vale só quando o autor concorda com ela não é regra. O texto saiu para
`textos/emails.yaml` e o módulo passou a ler de lá, validando na carga.

**O token vai no fragmento (`#`), nunca em query string.** O hash não é
enviado ao servidor em requisição nenhuma; numa query string, o token
apareceria em log de proxy, de CDN e no `Referer` de qualquer recurso
externo que a página carregasse — e quem lesse esse log entraria na conta.

**`str.replace`, nunca `str.format`.** O corpo é dado externo: um `{` que
alguém escreva no YAML por acidente quebraria `format` com `KeyError`.

**Bug encontrado no caminho — o aviso derrubava a liberação.**
`_avisar_plano_liberado` documentava que "nada aqui pode derrubar a
liberação", mas capturava só os três erros de e-mail. A busca da conta
também está dentro do `try`, e um `ErroConexaoAusente` dela escapava: a
decisão do revisor ficava gravada, o plano acessível, e a rota devolvia
`500` — o revisor decidiria de novo e bateria em `409`. Trocado por
`except Exception`: o critério certo não é QUAL erro aconteceu, é ONDE.
Nada daquele bloco é essencial à liberação, então nada dele a desfaz.

**Critérios de aceite**

- [x] Nenhuma redação de e-mail é literal em `app/` (`AC-37` passa)
- [x] O token vai no fragmento, nunca em query string
- [x] Mensagem ou campo ausente no YAML levanta na CARGA, nomeando a chave
- [x] Nenhuma mensagem sai com `{placeholder}` por substituir
- [x] `URL_BASE_APP` ausente levanta — nunca link para `localhost`
- [x] Falha de envio não desfaz a liberação do plano
- [x] Gates: lint, build, test, e2e

**Status:** `[x] concluída` (2026-09-21)

> **19 testes**, conferidos por mutação: token em query string, interpolação
> silenciosamente pulada e validação removida foram os três defeitos
> injetados — os três falharam a suíte. Os testes olham para o contrato
> (link certo, token no lugar certo, recusa a montar texto quebrado), nunca
> para a redação palavra por palavra: ela vive em YAML justamente para
> poder mudar sem tocar em código.

---

### `T-183` — Provisionamento do primeiro revisor

- **Tipo:** `FEATURE`
- **Dependências:** `T-100`
- **Rastreia:** `RF-23`, `RF-25`
- **Arquivos:** `scripts/papel_revisor.py` (novo),
  `docs/papel-revisor.md` (novo), `persistencia/app_aluno/contas.py`,
  `tests/app_aluno/test_comando_papel_revisor.py` (novo),
  `tests/app_aluno/integracao/test_persistencia_contas.py`

**Descrição**

**O bloqueio: instalação nova não tem revisor, e não havia como criar o
primeiro.** `e_revisor` nasce `false` para toda conta (migração `003`) —
correto, nenhuma vira revisora por acidente. Mas `promover_a_revisor` era
chamada só pelos testes: não havia caminho operacional nenhum. Numa
instalação nova, os alunos terminariam a coleta e o plano jamais seria
liberado, porque não existe revisor para liberá-lo e não há como criar o
primeiro. O sistema inteiro parava no penúltimo passo.

**Comando, não rota HTTP.** É um problema de origem: não há revisor para
autorizar a promoção do primeiro revisor. Uma rota teria de aceitar um
segredo de ambiente como autoridade — e seria, permanentemente, uma porta
pública dando acesso de leitura ao caso de TODOS os alunos a quem tivesse o
segredo. O comando exige acesso ao servidor e à `DATABASE_URL`: superfície
de ataque zero pela internet. A operação acontece uma vez na instalação e
quase nunca depois; essa raridade não paga o risco permanente da porta
aberta.

**Três verbos, não um.** `promover` sozinho é irreversível pela via normal:
promover o e-mail errado — um caractere trocado que bata com outra conta
real — daria a um aluno acesso aos casos de todos os outros, e desfazer
exigiria SQL direto em produção, no susto. `revogar` fecha isso (sem apagar
a conta: ela volta a ser conta comum, com caso e histórico intactos).
`listar` existe porque conferir é parte da operação — promover às cegas
deixa quem administra sem saber se acertou o e-mail, e sem como auditar
depois quem ficou com acesso.

**O e-mail é normalizado** (`.strip().lower()`, como no cadastro e no
login). Sem isso, `Revisor@Exemplo.BR` digitado no terminal não encontraria
a conta gravada em minúsculas, e o comando diria "não existe" sobre uma
conta que existe.

**Critérios de aceite**

- [x] `promover` concede o papel a uma conta existente
- [x] `promover` de e-mail inexistente falha nomeando o e-mail, sem criar
      conta
- [x] `revogar` tira o papel sem apagar a conta nem o caso
- [x] `revogar` de quem já não é revisor é sucesso silencioso
- [x] `listar` mostra os revisores; lista vazia avisa que a fila está
      inalcançável
- [x] O e-mail é normalizado nos três verbos
- [x] Falha de operação vira código de saída distinto em `stderr`, nunca
      traceback
- [x] Nenhuma rota HTTP expõe as três funções
- [x] Gates: lint, build, test

**Status:** `[x] concluída` (2026-09-21)

> **23 testes de comando** (sem banco) + **7 de integração** (com Postgres
> real, executados). Os de comando foram conferidos por mutação: a troca de
> verbo (`revogar` chamando `promover`), a normalização removida e os
> códigos de saída zerados — os três falharam a suíte. A troca de verbo é a
> mutação que mais importa: se `revogar` promovesse, quem tentasse TIRAR o
> acesso de alguém estaria concedendo, e o comando diria que deu certo.
>
> **Defeito encontrado rodando de verdade**, não pelos testes: no console do
> Windows a mensagem saiu `promo��o recusada` (cp1252). Num servidor, essas
> mensagens são a única orientação de quem opera. `main` passou a
> reconfigurar `stdout`/`stderr` para UTF-8, com teste de regressão.
>
> Procedimento documentado em `docs/papel-revisor.md`.

---

### `T-184` — Rate limiting nas rotas expostas

- **Tipo:** `FEATURE`
- **Dependências:** `T-179`, `T-180`, `T-182`
- **Rastreia:** `RF-02`
- **Arquivos:** `persistencia/supabase/migracoes/005_rate_limit.sql` (novo),
  `persistencia/app_aluno/tentativas.py` (novo),
  `app/http/limitador.py` (novo), `app/http/rotas_api_conta.py`,
  `app/http/rotas_provisionamento.py`, testes correspondentes

**Descrição**

Quatro rotas aceitam requisição não autenticada, e nenhuma tem limite. Cada
uma é abusável de um jeito diferente:

| Rota | O que o abuso causa |
| --- | --- |
| `POST /api/conta/login` | Força bruta de senha |
| `POST /api/provisionamento/recuperacao` | **Envio de e-mail ilimitado** |
| `POST /api/provisionamento/senha` | Força bruta de token de 43 chars |
| `POST /api/conta/cadastro` | Criação de contas em massa |

**A de recuperação é a mais urgente, e ficou pior depois de `T-180`.**
Enquanto o envio não existia, abusá-la não produzia nada. Agora cada chamada
dispara um e-mail REAL pelo SES — confirmado em 2026-09-22. Um laço simples
manda milhares de mensagens em minutos, e quem paga a conta não é só o
orçamento: é a **reputação do domínio**. Uma vez que o SES marca a conta
como fonte de abuso, os e-mails legítimos de primeiro acesso passam a cair
em spam — e o cliente que comprou não recebe o acesso.

**Decisões do especialista (2026-09-22):** estado em **tabela do Postgres**
(sobrevive a restart e a múltiplas instâncias) e resposta **`429` com janela
fixa** (previsível de entender e de explicar ao aluno).

**Bloqueio de conta foi recusado, deliberadamente.** Travar a conta após N
falhas vira arma: um atacante tranca o acesso de um aluno real só errando a
senha dele de propósito. O limite recai sobre a ORIGEM da requisição, nunca
sobre a identidade alvo.

**Critérios de aceite**

- [ ] As quatro rotas recusam com `429` ao estourar a janela
- [ ] A resposta `429` não revela se o e-mail existe (mesma disciplina de
      `/recuperacao`, que hoje responde igual para e-mail existente e
      inexistente)
- [ ] Estourar o limite de uma rota não afeta as outras
- [ ] A contagem não bloqueia conta: recai sobre a origem, nunca sobre o
      e-mail alvo
- [ ] Requisição legítima depois da janela volta a passar
- [ ] Gates: lint, build, test

**Open Questions**

- `OQ-14` — **A contagem no Postgres vira o gargalo sob ataque?** Cada
  tentativa, inclusive as que falham, é uma escrita no banco — e as que
  falham são exatamente as que um atacante produz em volume. Saída provável:
  contagem em memória na frente (barra a enxurrada sem tocar o banco) e o
  Postgres guardando só os bloqueios consolidados, preservando a
  sobrevivência a restart que motivou a escolha. **Decidir no plano, antes
  de implementar.**
- `OQ-15` — **Qual a chave da janela?** IP puro pune quem está atrás de NAT
  (uma repartição inteira sai pelo mesmo endereço — e a persona é servidor
  público). Provável: par (IP, rota), com janela mais frouxa no login que na
  recuperação.

**Status:** `[ ] pendente`

---

> Requisito sem tarefa não será implementado. Tarefa sem requisito é escopo
> extra — remova ou volte à spec.
